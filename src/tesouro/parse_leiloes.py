"""Converte o historico de leiloes da DPMFi na tabela canonica.

O arquivo tem uma aba por ano, todas com o mesmo layout: coluna 0 vazia,
cabecalho em portugues na linha 5 (base zero) e em ingles na linha 6,
dados a partir da linha 7.
"""
from pathlib import Path

import pandas as pd

from . import config
from .conversoes import fracao_para_percentual, limpar_nulo, para_milhoes

LINHA_DOS_DADOS = 7
COLUNAS_UTEIS = list(range(1, 15))

COLUNAS = [
    "data_leilao", "titulo", "tipo_leilao", "volta",
    "data_liquidacao", "data_vencimento", "oferta_qtd",
    "taxa_media_pct", "taxa_corte_pct", "venda_qtd",
    "financeiro_milhoes", "venda_bacen_qtd",
    "financeiro_bacen_milhoes", "referencia",
]

_COLUNAS_DE_DATA = ["data_leilao", "data_liquidacao", "data_vencimento"]
_COLUNAS_DE_TAXA = ["taxa_media_pct", "taxa_corte_pct"]
_COLUNAS_DE_REAIS = ["financeiro_milhoes", "financeiro_bacen_milhoes"]
_COLUNAS_DE_QUANTIDADE = ["oferta_qtd", "venda_qtd", "venda_bacen_qtd"]


def _para_data(valor):
    if pd.isna(valor):
        return None
    if isinstance(valor, str):
        valor = pd.to_datetime(valor, errors="coerce")
        if pd.isna(valor):
            return None
    return valor.date() if hasattr(valor, "date") else None


def ler_aba_de_ano(caminho, aba):
    """Le uma aba de ano e devolve as linhas de dados ja nomeadas."""
    bruto = pd.read_excel(
        caminho, sheet_name=aba, header=None,
        skiprows=LINHA_DOS_DADOS, usecols=COLUNAS_UTEIS,
    )
    bruto.columns = COLUNAS
    # Linhas sem data de leilao sao rodape ou separadores.
    return bruto[bruto["data_leilao"].notna()].copy()


def parse(caminho=None):
    """Le todas as abas de ano e devolve a tabela canonica de leiloes."""
    caminho = Path(caminho) if caminho else config.LEILOES_DIR / config.ARQUIVO_LEILOES

    abas = [a for a in pd.ExcelFile(caminho).sheet_names if a.startswith("Ano ")]
    if not abas:
        raise LookupError(f"nenhuma aba 'Ano NNNN' encontrada em {caminho}")

    partes = [ler_aba_de_ano(caminho, aba) for aba in abas]
    df = pd.concat(partes, ignore_index=True)

    for coluna in _COLUNAS_DE_DATA:
        df[coluna] = df[coluna].map(_para_data)
    for coluna in _COLUNAS_DE_QUANTIDADE:
        df[coluna] = df[coluna].map(limpar_nulo)
    for coluna in _COLUNAS_DE_TAXA:
        df[coluna] = df[coluna].map(limpar_nulo).map(fracao_para_percentual)
    for coluna in _COLUNAS_DE_REAIS:
        df[coluna] = df[coluna].map(limpar_nulo).map(
            lambda v: para_milhoes(v, "reais")
        )
    for coluna in ("titulo", "tipo_leilao", "volta", "referencia"):
        df[coluna] = df[coluna].map(
            lambda v: None if pd.isna(v) else str(v).strip()
        )

    df = df[df["data_leilao"].notna()]
    return df.sort_values(
        ["data_leilao", "titulo", "data_vencimento", "volta"]
    ).reset_index(drop=True)


def gravar(caminho=None):
    df = parse(caminho)
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    saida = config.PROCESSED_DIR / "leiloes.csv"
    df.to_csv(saida, index=False, encoding="utf-8")
    print(f"gravado: {saida} ({len(df)} linhas)")
    return saida


if __name__ == "__main__":
    gravar()
