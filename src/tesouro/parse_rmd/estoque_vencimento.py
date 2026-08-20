"""Aba 2.2 -- estoque dos principais titulos da DPMFi, por vencimento.

Layout: blocos por indexador (uma linha isolada com o nome), cabecalho
fixo 'Titulo | Data de Vencimento | Codigo ISIN | Estoque', uma linha de
meses em que cada mes ocupa DUAS colunas, e a linha seguinte dizendo qual
delas e quantidade e qual e financeiro.

Esta e a aba que sustenta o calculo de DV01: a quantidade e a posicao.
O financeiro serve de conferencia -- nao esta confirmado se e marcacao a
mercado ou na curva.
"""
import re

import pandas as pd

from .. import config
from ..conversoes import limpar_nulo, mes_para_data, para_milhoes
from ..leitura_rmd import aba

_COL_TITULO = 0
_COL_VENCIMENTO = 1
_COL_ISIN = 2
_PRIMEIRA_COL_DE_DADOS = 3

_CABECALHOS = {"t\u00edtulo", "titulo", "data de vencimento", "c\u00f3digo isin"}

# Nota numerada de rodape: '1 Nao estao incluidos os titulos LFT-A e LFT-B.'
_PADRAO_NOTA_NUMERADA = re.compile(r"^\d+\s")


def _eh_ruido(texto):
    """Diz se a linha e subtotal, nota de rodape ou titulo da aba.

    Precisa ser reconhecida ANTES de a celula ser tratada como cabecalho
    de bloco, porque 'Total LTN' e 'Obs.: ...' tem a coluna de vencimento
    vazia igual a um cabecalho de verdade. Se uma delas virar o indexador
    corrente, contamina todas as linhas seguintes -- as 19 linhas de NTN-F
    sairiam com indexador 'Total LTN' em vez de 'Prefixados', sem erro
    nenhum.

    Os subtotais tambem sao valores derivados, e por isso nao entram na
    tabela de jeito nenhum.
    """
    limpo = texto.strip().lower()
    if limpo.startswith(("anexo", "obs", "total")):
        return True
    return bool(_PADRAO_NOTA_NUMERADA.match(limpo))


def _linha_dos_meses(bruto):
    for indice in range(len(bruto)):
        reconhecidos = sum(
            1 for v in bruto.iloc[indice] if mes_para_data(v) is not None
        )
        if reconhecidos >= 3:
            return indice
    raise LookupError("aba 2.2: nenhuma linha com rotulos de mes")


def _mapear_meses(bruto, linha):
    """Devolve {coluna_da_quantidade: (data, coluna_do_financeiro)}."""
    mapa = {}
    for coluna in range(_PRIMEIRA_COL_DE_DADOS, len(bruto.columns)):
        data = mes_para_data(bruto.iloc[linha, coluna])
        if data is not None:
            mapa[coluna] = (data, coluna + 1)
    return mapa


def _para_data_de_vencimento(valor):
    if pd.isna(valor):
        return None
    if isinstance(valor, (int, float)):
        # Numero de serie do Excel (base 1899-12-30).
        return (pd.Timestamp("1899-12-30") + pd.Timedelta(days=int(valor))).date()
    convertido = pd.to_datetime(valor, errors="coerce")
    return None if pd.isna(convertido) else convertido.date()


def parse(xl):
    bruto = aba(xl, "2.2")
    linha_meses = _linha_dos_meses(bruto)
    meses = _mapear_meses(bruto, linha_meses)

    registros = []
    indexador_corrente = None

    for indice in range(len(bruto)):
        celula = bruto.iloc[indice, _COL_TITULO]
        if pd.isna(celula) or not str(celula).strip():
            continue
        texto = str(celula).strip()

        # Ruido primeiro: subtotais e notas tem a coluna de vencimento
        # vazia e seriam confundidos com cabecalho de bloco.
        if texto.lower() in _CABECALHOS or _eh_ruido(texto):
            continue

        vencimento = _para_data_de_vencimento(bruto.iloc[indice, _COL_VENCIMENTO])
        if vencimento is None:
            # Linha isolada com o nome do bloco de indexador.
            indexador_corrente = texto
            continue

        isin = bruto.iloc[indice, _COL_ISIN]
        isin = None if pd.isna(isin) else str(isin).strip()

        for coluna_qtd, (data, coluna_fin) in meses.items():
            quantidade = limpar_nulo(bruto.iloc[indice, coluna_qtd])
            financeiro = None
            if coluna_fin < len(bruto.columns):
                financeiro = para_milhoes(
                    limpar_nulo(bruto.iloc[indice, coluna_fin]), "bilhoes"
                )
            registros.append(
                (data, indexador_corrente, texto, vencimento, isin,
                 quantidade, financeiro)
            )

    df = pd.DataFrame(
        registros,
        columns=["data", "indexador", "titulo", "vencimento", "isin",
                 "quantidade_mil", "financeiro_milhoes"],
    )

    # O laco acima produz o produto cartesiano de todo papel por todo mes,
    # e a aba so tem dado para os meses em que aquele papel estava em
    # carteira. Uma linha com quantidade E financeiro ausentes nao e dado
    # ausente: e nao-observacao, o papel nao existia naquele mes. Nao
    # grava-la nao perde informacao nenhuma e corta mais da metade das
    # linhas (25.236 de 47.124 no arquivo real).
    #
    # Os zeros ficam: posicao zerada e observacao legitima, e a regra do
    # projeto e que zero e valor, nao ausencia. Linha com um dos dois
    # preenchido tambem fica (sao duas no arquivo real).
    nao_observacao = (
        df["quantidade_mil"].isna() & df["financeiro_milhoes"].isna()
    )
    df = df[~nao_observacao]

    return df.sort_values(
        ["data", "titulo", "vencimento"]
    ).reset_index(drop=True)


def gravar(xl):
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df = parse(xl)
    saida = config.PROCESSED_DIR / "estoque_titulos_vencimento.csv"
    df.to_csv(saida, index=False, encoding="utf-8")
    print(f"gravado: {saida} ({len(df)} linhas)")
