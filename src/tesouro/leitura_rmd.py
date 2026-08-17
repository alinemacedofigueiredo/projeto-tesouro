"""Leitores genericos para as abas do anexo do RMD.

As dezoito abas usadas caem em dois formatos:

  Padrao A -- meses nas colunas, rotulos nas linhas (1.1, 1.2, 2.1, 3.7,
  3.8, 4.1, 4.2, 4.3). A indentacao do rotulo carrega a hierarquia.

  Padrao B -- meses nas linhas, categorias nas colunas (2.4, 2.7, 2.8,
  3.1, 3.3, 3.9, 6.1). Cada categoria costuma ocupar duas colunas, valor
  e percentual; so o valor e lido, porque percentual e derivado.

As abas 2.2, 3.4 e 5.7 nao seguem nenhum dos dois e tem parser proprio.
"""
from pathlib import Path

import pandas as pd

from . import config
from .conversoes import limpar_nulo, mes_para_data, normalizar_data, para_milhoes


def caminho_do_rmd(diretorio=None):
    """Devolve o .xlsx de RMD mais recente disponivel em data/raw/rmd/."""
    diretorio = Path(diretorio) if diretorio else config.RMD_DIR
    candidatos = sorted(diretorio.glob("*.xlsx"))
    if not candidatos:
        raise FileNotFoundError(
            f"nenhum .xlsx encontrado em {diretorio}; baixe com "
            f"'python -m tesouro.fetch_rmd <ano> <mes>' ou coloque o "
            f"arquivo na pasta manualmente"
        )
    return max(candidatos, key=lambda p: p.stat().st_mtime)


def abrir(caminho=None):
    caminho = Path(caminho) if caminho else caminho_do_rmd()
    return pd.ExcelFile(caminho)


def aba(xl, nome):
    """Le uma aba pelo nome, falhando de forma legivel se ela nao existir.

    O Tesouro descontinua abas de tempos em tempos (a 3.5 e a 5.6 sairam
    em junho de 2025) e continua listando-as no indice do anexo. Quando
    isso acontecer com uma aba que usamos, quem for investigar precisa
    ler qual sumiu -- nao um KeyError cru do pandas.

    Todos os parsers passam por aqui, inclusive os das abas especiais.
    """
    if nome not in xl.sheet_names:
        raise LookupError(
            f"aba {nome!r} nao existe neste anexo do RMD. "
            f"Ela pode ter sido descontinuada -- confira o indice do "
            f"arquivo. Abas presentes: {', '.join(xl.sheet_names)}"
        )
    return xl.parse(sheet_name=nome, header=None)


def _linha_do_cabecalho_de_meses(bruto):
    """Acha a linha cujo conteudo sao rotulos de mes ('Nov/06').

    A posicao varia entre abas -- a 4.3 tem um nivel de cabecalho a mais
    que as demais -- entao e detectada, nao fixada.
    """
    for indice, linha in bruto.iterrows():
        reconhecidos = sum(1 for v in linha if mes_para_data(v) is not None)
        if reconhecidos >= 3:
            return indice
    raise LookupError("nenhuma linha de cabecalho com rotulos de mes")


def _indentacao(texto):
    return len(texto) - len(texto.lstrip())


def ler_padrao_a(xl, nome_da_aba, unidade):
    """Le uma aba com meses nas colunas e rotulos nas linhas.

    Devolve tambem `linha_origem` -- o indice da linha na planilha lida.
    O rotulo sozinho nao e uma chave confiavel: abas como a 1.1 repetem o
    mesmo texto (ex.: "Trocas Oferta Publica", "Tesouro Direto") sob
    secoes diferentes (emissao e resgate) e, em outras abas, ate a
    indentacao pode ser identica em todas as linhas. linha_origem e a
    unica chave estavel para quem for reconstruir a hierarquia ou separar
    secoes repetidas.
    """
    bruto = aba(xl, nome_da_aba)
    linha_cabecalho = _linha_do_cabecalho_de_meses(bruto)

    # So as colunas cujo cabecalho e um mes de verdade; isso descarta os
    # totais anuais que a aba 1.1 intercala entre os meses.
    datas = {}
    for coluna in bruto.columns:
        data = mes_para_data(bruto.iloc[linha_cabecalho, coluna])
        if data is not None:
            datas[coluna] = data

    registros = []
    for indice in range(linha_cabecalho + 1, len(bruto)):
        rotulo_bruto = bruto.iloc[indice, 0]
        if pd.isna(rotulo_bruto) or not str(rotulo_bruto).strip():
            continue
        rotulo_bruto = str(rotulo_bruto)
        rotulo = rotulo_bruto.strip()
        nivel = _indentacao(rotulo_bruto.replace("\xa0", " "))
        for coluna, data in datas.items():
            valor = para_milhoes(limpar_nulo(bruto.iloc[indice, coluna]), unidade)
            registros.append((data, indice, rotulo, nivel, valor))

    return pd.DataFrame(
        registros,
        columns=["data", "linha_origem", "rotulo", "nivel_indentacao", "valor_milhoes"],
    )


def ler_padrao_b(xl, nome_da_aba, linha_cabecalho, unidade, colunas_por_categoria=2):
    """Le uma aba com meses nas linhas e categorias nas colunas.

    Assume que a coluna 0 traz a data e que cada categoria ocupa
    `colunas_por_categoria` colunas a partir da coluna 1, sendo a primeira
    delas o valor. As demais (tipicamente o percentual) sao ignoradas, por
    serem derivadas.
    """
    bruto = aba(xl, nome_da_aba)

    categorias = {}
    coluna = 1
    while coluna < len(bruto.columns):
        nome = bruto.iloc[linha_cabecalho, coluna]
        if not pd.isna(nome) and str(nome).strip():
            categorias[coluna] = str(nome).strip()
        coluna += colunas_por_categoria

    registros = []
    for indice in range(linha_cabecalho + 1, len(bruto)):
        data = normalizar_data(bruto.iloc[indice, 0])
        if data is None:
            continue
        for coluna, categoria in categorias.items():
            valor = para_milhoes(limpar_nulo(bruto.iloc[indice, coluna]), unidade)
            registros.append((data, categoria, valor))

    return pd.DataFrame(registros, columns=["data", "categoria", "valor_milhoes"])
