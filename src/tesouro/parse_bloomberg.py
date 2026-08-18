"""Converte os brutos da Bloomberg nas tabelas canonicas.

A coleta e incremental por desenho: cada puxada grava um arquivo novo em
data/raw/bloomberg/ e nada e sobrescrito -- data/raw/ e imutavel por
invariante do projeto. Por isso o parser le TODOS os arquivos de cada
tipo, concatena, e em caso de repeticao fica com a ultima ocorrencia --
que e a puxada mais recente.

As duas fontes trazem a data em convencoes diferentes: a de taxas ja vem
no ultimo dia util do mes (e o que a periodicidade mensal da Bloomberg
devolve via HistoricalDataRequest), e a de VNA vem no ultimo dia corrido,
porque foi assim que o override de SETTLE_DT foi pedido. Verificado
durante o design que o VNA e identico nos dois dias, porque nao acumula
em dia nao util. As duas sao normalizadas para o ultimo dia util, que e a
chave de juncao do projeto -- ver docs/convencoes-dv.md: casar por data
crua descarta cerca de um terco do painel em silencio, porque a Bloomberg
devolve o ultimo dia util (ex.: 29/05) onde o RMD traz o ultimo dia
corrido (31/05).

Este modulo nunca toca a rede. Ele so le o que a coleta ja deixou em
data/raw/bloomberg/ e nunca escreve em data/raw/ -- so em
data/processed/.
"""
from pathlib import Path

import pandas as pd

from . import calendario, config


def _ler_todos(padrao, caminho=None):
    """Le e concatena todos os arquivos que casam com o padrao de nome.

    caminho, se dado, substitui o diretorio padrao (config.BLOOMBERG_DIR)
    -- usado pelos testes para apontar para uma pasta com fixtures.
    """
    diretorio = Path(caminho) if caminho else config.BLOOMBERG_DIR
    arquivos = sorted(diretorio.glob(padrao))
    if not arquivos:
        raise FileNotFoundError(
            f"nenhum arquivo {padrao!r} em {diretorio}; rode a coleta com "
            f"'python -m tesouro.fetch_bloomberg' ou coloque a exportacao "
            f"do BDH nessa pasta (veja docs/convencoes-dv.md)"
        )
    return pd.concat([pd.read_csv(a) for a in arquivos], ignore_index=True)


def parse_taxas(caminho=None):
    """Taxa indicativa Anbima por papel e fim de mes, em percentual.

    A taxa vem de HistoricalDataRequest (YLD_YTM_MID, fonte ANDE), nao de
    SETTLE_DT -- ver docs/convencoes-dv.md sobre por que o override de
    liquidacao nao serve para taxa historica. Fica em percentual (13.5
    significa 13,5%), a mesma convencao que o resto do projeto usa para
    taxa antes de entrar em decimal no calculo do PU.

    Ha agio/desagio negativo na LFT (ex.: -0.0039): e esperado, nao e
    erro.
    """
    cal = calendario.padrao()
    df = _ler_todos("bbg_taxas_*.csv", caminho)
    df["data"] = pd.to_datetime(df["data"]).dt.date.map(cal.ultimo_dia_util_do_mes)
    df["vencimento"] = pd.to_datetime(df["vencimento"]).dt.date
    df = df.rename(columns={"yld_ytm_mid": "taxa_pct"})
    df = df.drop_duplicates(subset=["data", "isin"], keep="last")
    return df[["data", "isin", "titulo", "vencimento", "taxa_pct"]].sort_values(
        ["data", "titulo", "isin"]
    ).reset_index(drop=True)


def parse_vna(caminho=None):
    """VNA por indice e fim de mes, em reais.

    O VNA e por indice, nao por papel: verificado que o valor e identico
    entre papeis diferentes na mesma data, em todas as datas do painel --
    ver docs/convencoes-dv.md.
    """
    cal = calendario.padrao()
    df = _ler_todos("bbg_vna_*.csv", caminho)
    df["data"] = pd.to_datetime(df["data"]).dt.date.map(cal.ultimo_dia_util_do_mes)
    df = df.drop_duplicates(subset=["data", "indice"], keep="last")
    return df[["data", "indice", "vna"]].sort_values(
        ["data", "indice"]
    ).reset_index(drop=True)


def gravar():
    """Grava as duas tabelas canonicas em data/processed/.

    Nao usa gravar_atomico: essa funcao existe para proteger downloads
    brutos de rede contra escrita parcial e paginas de erro salvas como
    planilha. Aqui o conteudo e gerado localmente a partir de arquivos ja
    validados em data/raw/, e o padrao do projeto para esse caso (ver
    src/tesouro/parse_rmd/) e df.to_csv direto em data/processed/.
    """
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    for nome, df in (("taxa_por_papel", parse_taxas()), ("vna", parse_vna())):
        saida = config.PROCESSED_DIR / f"{nome}.csv"
        df.to_csv(saida, index=False, encoding="utf-8")
        print(f"gravado: {saida} ({len(df)} linhas)")


if __name__ == "__main__":
    gravar()
