"""Abas 2.1, 2.4, 2.7 e 2.8 -- estoque, composicao e detentores.

Todas em R$ bilhoes. A 2.1 e padrao A com hierarquia por indentacao; as
demais sao padrao B com pares (valor, percentual), dos quais so o valor
e lido.
"""
import pandas as pd

from .. import config
from ..conversoes import data_da_celula, limpar_nulo, para_milhoes
from ..leitura_rmd import (
    aba,
    aplicar_papel,
    descartar_folhas_sem_dado,
    ler_padrao_a,
    ler_padrao_b,
    ordem_dos_rotulos,
)

_EM_PODER_DO_PUBLICO = "DPF EM PODER DO PÚBLICO"
_DPMFI_NO_BACEN = "DPMFi EM PODER DO BANCO CENTRAL"
# 'Divida Mobiliaria' e 'Divida Contratual' sao cabecalhos de subgrupo
# dentro de DPFe, nao titulos: a celula deles traz o subtotal exato dos
# titulos logo abaixo (conferido contra o arquivo real, todas as datas).
# Tratados como entidade -- o mesmo papel de 'Tesouro Nacional' e 'Banco
# Central' sob DPMFi -- ficam com titulo=None e os titulos abaixo herdam
# a entidade; sem isso, o subtotal e gravado como se fosse titulo folha e
# um consumidor que some por titulo.notna() conta a divida externa em
# dobro.
_ENTIDADES = {
    "Tesouro Nacional", "Banco Central",
    "Dívida Mobiliária", "Dívida Contratual",
}
_ESFERAS = {"DPMFi", "DPFe"}


def parse_dpf(xl):
    """Aba 2.1 -- estoque da DPF, por esfera, entidade e titulo.

    A hierarquia e resolvida por linha_origem, nunca pelo texto do
    rotulo: 'Demais' se repete tres vezes na aba (sob Tesouro Nacional,
    sob DPFe/Divida Mobiliaria e sob o memo de DPMFi no Banco Central, ver
    abaixo). Indexar por rotulo faria as tres colapsarem numa so entrada
    -- a primeira encontrada -- e todo o resto do arquivo com esse texto
    herdaria o papel dela, plausivel e errado, sem erro nenhum. E o mesmo
    cuidado que o parser de funding.py (abas 1.1/1.2) ja precisou tomar.

    O fim da aba traz notas de rodape em linhas soltas -- chamadas de nota
    (o texto que explica cada marcador de rodape usado la em cima) e
    observacoes ('Obs.1: ...', 'Obs.2: ...'). Nenhuma delas tem dado em
    coluna de mes nenhuma; sao descartadas por isso, nao por casar com um
    prefixo especifico, para nao depender de como o Tesouro as redige. Um
    cabecalho legitimo (ex.: 'Tesouro Nacional') tambem nao tem valor
    proprio, mas tem titulo None -- so os rotulos tratados como titulo
    (folha da hierarquia) entram nessa checagem, para nao os confundir.

    A aba tambem traz, depois do bloco de DPFe, uma tabela memorando a
    composicao por titulo do que o Banco Central detem de DPMFi. E dado
    de verdade (nao derivado), mas nao faz parte da hierarquia DPF em
    poder do publico / DPFe descrita no anexo -- por isso ganha o proprio
    nivel, em vez de ser absorvida (errado) pelo nivel DPFe corrente.

    Dentro de DPFe, 'Divida Mobiliaria' e 'Divida Contratual' sao
    cabecalhos de subgrupo, nao titulos: a celula deles traz o subtotal
    exato da soma dos titulos logo abaixo. Tratados como entidade (o
    mesmo papel de 'Tesouro Nacional'/'Banco Central' sob DPMFi), ficam
    com titulo=None; sem isso, o subtotal e gravado como se fosse titulo
    folha e some junto com os titulos reais, contando a divida externa em
    dobro para quem agrupar por titulo.notna().
    """
    bruto = ler_padrao_a(xl, "2.1", "bilhoes")

    # A hierarquia e a mesma em toda data: resolve-se uma vez, na ordem
    # da planilha.
    ordem = ordem_dos_rotulos(bruto)

    papel = {}
    nivel_corrente = None
    entidade_corrente = None
    for _, linha in ordem.iterrows():
        origem = linha["linha_origem"]
        limpo = linha["rotulo"].strip()
        if limpo == _EM_PODER_DO_PUBLICO:
            nivel_corrente = "DPF em poder do publico"
            entidade_corrente = None
            papel[origem] = (nivel_corrente, None, None)
        elif limpo == _DPMFI_NO_BACEN:
            nivel_corrente = "DPMFi em poder do Banco Central"
            entidade_corrente = None
            papel[origem] = (nivel_corrente, None, None)
        elif limpo.startswith("DPFe"):
            nivel_corrente = "DPFe"
            entidade_corrente = None
            papel[origem] = (nivel_corrente, None, None)
        elif limpo in _ESFERAS:
            nivel_corrente = limpo
            entidade_corrente = None
            papel[origem] = (nivel_corrente, None, None)
        elif limpo in _ENTIDADES:
            entidade_corrente = limpo
            papel[origem] = (nivel_corrente, entidade_corrente, None)
        else:
            papel[origem] = (nivel_corrente, entidade_corrente, limpo)

    df = aplicar_papel(bruto, papel, ["nivel", "entidade", "titulo"])

    # Descarta as notas de rodape: linhas de titulo (nao cabecalho) sem
    # nenhum valor em nenhuma data. Mesma defesa nas abas 1.1/1.2, 3.7/3.8
    # e 4.1/4.2/4.3 -- ver descartar_folhas_sem_dado.
    df = descartar_folhas_sem_dado(df, df["titulo"].notna())

    return df[
        ["data", "nivel", "entidade", "titulo", "valor_milhoes"]
    ].sort_values(["data", "nivel", "entidade", "titulo"]).reset_index(drop=True)


def parse_composicao(xl):
    """Aba 2.4 -- composicao da DPF por indexador."""
    df = ler_padrao_b(xl, "2.4", linha_cabecalho=4, unidade="bilhoes")
    df = df[df["categoria"].str.lower() != "total"]
    return df.rename(columns={"categoria": "indexador"}).reset_index(drop=True)


def parse_detentores(xl):
    """Aba 2.7 -- detentores dos titulos da DPMFi.

    A aba traz uma coluna 'Total' com o mesmo par (valor, %) de cada
    detentor -- e a soma dos demais, conferida linha a linha contra o
    arquivo real. E derivada, e por isso descartada, como em 2.4.
    """
    df = ler_padrao_b(xl, "2.7", linha_cabecalho=4, unidade="bilhoes")
    df = df[df["categoria"].str.lower() != "total"]
    return df.rename(columns={"categoria": "detentor"}).reset_index(drop=True)


def parse_detentores_por_titulo(xl):
    """Aba 2.8 -- participacao dos detentores, em blocos por titulo.

    A aba repete o mesmo bloco para cada titulo (LFT, LTN, NTN-B, NTN-F,
    OUTROS), a cerca de 189 linhas de distancia um do outro: uma linha
    isolada com o nome do titulo, um cabecalho de detentores duas linhas
    abaixo, e as datas em seguida.

    A ordem dos testes abaixo importa. Duas linhas de cada bloco trazem a
    data como TEXTO com asterisco ('mar/18*', 'abr/18*') -- os meses que o
    Tesouro retificou. Se a checagem de data nao vier primeiro, elas sao
    lidas como rotulo de titulo, o dicionario de detentores e zerado, e as
    cerca de cem linhas seguintes do bloco desaparecem sem erro nenhum.

    Cada bloco tambem traz uma coluna 'Total', soma dos demais detentores
    (conferida contra o arquivo real). E derivada, e por isso descartada,
    como a mesma coluna e descartada em 2.4 e 2.7.
    """
    bruto = aba(xl, "2.8")

    registros = []
    titulo_corrente = None
    detentores = {}

    for indice in range(len(bruto)):
        primeira = bruto.iloc[indice, 0]

        # Primeiro: e uma data? (inclusive as escritas como texto)
        data = data_da_celula(primeira)
        if data is not None:
            for coluna, detentor in detentores.items():
                valor = para_milhoes(
                    limpar_nulo(bruto.iloc[indice, coluna]), "bilhoes"
                )
                registros.append((data, detentor, titulo_corrente, valor))
            continue

        # Coluna 0 vazia: candidata a linha de cabecalho de detentores.
        if pd.isna(primeira) or not str(primeira).strip():
            if titulo_corrente and not detentores:
                candidatos = {}
                coluna = 1
                while coluna < len(bruto.columns):
                    nome = bruto.iloc[indice, coluna]
                    if not pd.isna(nome) and str(nome).strip():
                        nome = str(nome).strip()
                        if nome.lower() != "total":
                            candidatos[coluna] = nome
                    coluna += 2
                if candidatos:
                    detentores = candidatos
            continue

        texto = str(primeira).strip()
        if texto.upper().startswith("ANEXO") or texto.startswith("*"):
            continue  # titulo da aba, ou rodape explicando a retificacao

        titulo_corrente = texto
        detentores = {}

    return pd.DataFrame(
        registros, columns=["data", "detentor", "titulo", "valor_milhoes"]
    ).sort_values(["data", "titulo", "detentor"]).reset_index(drop=True)


def gravar(xl):
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    for nome, df in (
        ("estoque_dpf", parse_dpf(xl)),
        ("composicao_dpf", parse_composicao(xl)),
        ("detentores", parse_detentores(xl)),
        ("detentores_por_titulo", parse_detentores_por_titulo(xl)),
    ):
        saida = config.PROCESSED_DIR / f"{nome}.csv"
        df.to_csv(saida, index=False, encoding="utf-8")
        print(f"gravado: {saida} ({len(df)} linhas)")
