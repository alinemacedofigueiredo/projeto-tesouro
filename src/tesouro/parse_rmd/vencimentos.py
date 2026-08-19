"""Abas 3.1, 3.3 e 3.4 -- perfil de vencimento.

A 3.1 e a 3.3 sao series historicas (padrao B, R$ bilhoes). A 3.4 e o
unico retrato do projeto: olha para frente a partir da data de fechamento
e e substituida a cada mes, por isso leva data_referencia. Seus valores
incluem juros, nao apenas principal.
"""
import re

import pandas as pd

from .. import config
from ..conversoes import limpar_nulo, normalizar_data, para_milhoes
from ..leitura_rmd import aba, ler_padrao_b

_PADRAO_FECHAMENTO = re.compile(r"(\d{2})/(\d{2})/(\d{4})")

_COLUNAS_DERIVADAS = {"part %", "total"}


_NIVEIS_DA_31 = ("DPF", "DPMFi", "DPFe")


def _blocos_da_31(bruto):
    """Acha os blocos empilhados da aba 3.1.

    A aba traz tres series completas uma abaixo da outra -- DPF, DPMFi e
    DPFe -- cada uma com o rotulo numa linha isolada, o cabecalho de
    faixas duas linhas depois, e os meses em seguida. Ler a aba de uma vez
    so misturaria as tres: cada data apareceria tres vezes, com valores
    diferentes e nada dizendo a qual serie pertence.

    Devolve [(nivel, linha_cabecalho, linha_final), ...].
    """
    inicios = []
    for indice in range(len(bruto)):
        celula = bruto.iloc[indice, 0]
        if pd.isna(celula) or not isinstance(celula, str):
            continue
        if celula.strip() in _NIVEIS_DA_31:
            inicios.append((celula.strip(), indice))

    if not inicios:
        raise LookupError(
            "aba 3.1: nenhum bloco DPF/DPMFi/DPFe encontrado; "
            "o layout da aba pode ter mudado"
        )

    blocos = []
    for ordem, (nivel, linha) in enumerate(inicios):
        fim = inicios[ordem + 1][1] if ordem + 1 < len(inicios) else len(bruto)
        blocos.append((nivel, linha + 2, fim))
    return blocos


def parse_por_faixa(xl):
    """Aba 3.1 -- vencimentos por faixa de prazo, nos tres niveis."""
    bruto = aba(xl, "3.1")

    partes = []
    for nivel, linha_cabecalho, linha_final in _blocos_da_31(bruto):
        parte = ler_padrao_b(
            xl, "3.1", linha_cabecalho=linha_cabecalho, unidade="bilhoes",
            linha_final=linha_final,
        )
        parte = parte[~parte["categoria"].str.lower().isin(_COLUNAS_DERIVADAS)]
        partes.append(parte.assign(nivel=nivel))

    df = pd.concat(partes, ignore_index=True).rename(
        columns={"categoria": "faixa"}
    )
    return df[["data", "nivel", "faixa", "valor_milhoes"]].sort_values(
        ["data", "nivel", "faixa"]
    ).reset_index(drop=True)


def parse_a_vencer_12m(xl):
    """Aba 3.3 -- titulos a vencer em 12 meses, por indexador."""
    df = ler_padrao_b(xl, "3.3", linha_cabecalho=4, unidade="bilhoes")
    df = df[~df["categoria"].str.lower().isin(_COLUNAS_DERIVADAS)]
    return df.rename(columns={"categoria": "indexador"}).reset_index(drop=True)


def _data_de_fechamento(bruto):
    """Le a data do carimbo 'Fechamento de DD/MM/AAAA' da aba 3.4."""
    for indice in range(min(12, len(bruto))):
        for valor in bruto.iloc[indice]:
            if pd.isna(valor):
                continue
            achado = _PADRAO_FECHAMENTO.search(str(valor))
            if achado:
                dia, mes, ano = (int(g) for g in achado.groups())
                return pd.Timestamp(year=ano, month=mes, day=dia).date()
    raise LookupError("aba 3.4: carimbo 'Fechamento de DD/MM/AAAA' nao encontrado")


def _linha_do_cabecalho(bruto):
    # Procura o texto completo 'data de vencimento', nao so 'vencimento':
    # o titulo da aba na linha 1 ('...CRONOGRAMA DE VENCIMENTOS DA DPMFi')
    # ja contem 'vencimento' como substring e seria confundido com o
    # cabecalho de verdade, que fica bem mais abaixo.
    for indice in range(len(bruto)):
        primeira = bruto.iloc[indice, 0]
        if pd.isna(primeira):
            continue
        if "data de vencimento" in str(primeira).strip().lower():
            return indice
    raise LookupError("aba 3.4: cabecalho com 'Data de Vencimento' nao encontrado")


def _sem_acento(texto):
    """Compara rotulo do RMD sem depender de acentuacao."""
    import unicodedata
    normal = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in normal if not unicodedata.combining(c)).strip().lower()


def _linha_do_balde(bruto):
    """Acha a linha 'Apos 5 anos', pelo rotulo e nunca pela posicao.

    A aba muda de tamanho conforme o mes -- os 60 meses detalhados andam, e as
    linhas de resumo andam junto. Procurar pela posicao funcionaria neste anexo e
    leria a linha errada no proximo.
    """
    for indice in range(len(bruto)):
        if _sem_acento(bruto.iloc[indice, 0]).startswith("apos 5 anos"):
            return indice
    raise LookupError(
        "aba 3.4: linha 'Apos 5 anos' nao encontrada. Ela existe desde que "
        "acompanhamos a aba, e sem ela o CSV soma so os 60 meses detalhados, "
        "cerca de 78% do estoque. Confira se o layout da aba mudou."
    )


def parse_cronograma(xl):
    """Aba 3.4 -- cronograma de vencimentos da DPMFi (retrato).

    A aba detalha 60 meses e joga tudo o que vence depois num balde unico, "Apos 5
    anos". As duas coisas entram no CSV, separadas pela coluna 'faixa': sem o balde
    o arquivo soma 78% do estoque, e quem somar nao percebe.

    A linha do balde nasce sem mes_vencimento -- ela nao tem mes, e dar um a ela
    seria inventar dado.
    """
    bruto = aba(xl, "3.4")
    referencia = _data_de_fechamento(bruto)
    linha_cabecalho = _linha_do_cabecalho(bruto)

    grupos = {}
    for coluna in range(1, len(bruto.columns)):
        nome = bruto.iloc[linha_cabecalho, coluna]
        if pd.isna(nome) or not str(nome).strip():
            continue
        nome = str(nome).strip()
        if nome.lower() in _COLUNAS_DERIVADAS:
            continue
        grupos[coluna] = nome

    registros = []
    for indice in range(linha_cabecalho + 1, len(bruto)):
        mes = normalizar_data(bruto.iloc[indice, 0])
        if mes is None:
            continue
        for coluna, grupo in grupos.items():
            valor = para_milhoes(limpar_nulo(bruto.iloc[indice, coluna]), "milhoes")
            registros.append((referencia, mes, grupo, valor, "mensal"))

    linha_balde = _linha_do_balde(bruto)
    for coluna, grupo in grupos.items():
        valor = para_milhoes(limpar_nulo(bruto.iloc[linha_balde, coluna]), "milhoes")
        registros.append((referencia, None, grupo, valor, "apos_5_anos"))

    return pd.DataFrame(
        registros,
        columns=["data_referencia", "mes_vencimento", "grupo_titulo",
                 "valor_milhoes", "faixa"],
    ).sort_values(["faixa", "mes_vencimento", "grupo_titulo"]).reset_index(drop=True)


def gravar(xl):
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    for nome, df in (
        ("vencimentos_faixa", parse_por_faixa(xl)),
        ("vencer_12m_indexador", parse_a_vencer_12m(xl)),
        ("cronograma_vencimentos", parse_cronograma(xl)),
    ):
        saida = config.PROCESSED_DIR / f"{nome}.csv"
        df.to_csv(saida, index=False, encoding="utf-8")
        print(f"gravado: {saida} ({len(df)} linhas)")
