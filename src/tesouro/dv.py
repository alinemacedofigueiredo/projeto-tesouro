"""Painel de DV01 por papel, decay e calculo pontual.

O painel e persistido, e nao calculado sob demanda, porque as entregas 3
(analise de leiloes) e 5 (simulacao contra o PAF) vao consumi-lo. Tres
implementacoes independentes de DV que discordam entre si seria o pior
resultado possivel.

Unidades: quantidade_mil e o estoque em milhares de titulos; pu e
dv_unitario sao reais por titulo. Logo o financeiro e o DV da posicao,
em milhoes de reais, sao (valor por titulo) * quantidade_mil / 1000.

A taxa entra em PERCENTUAL nos tres CSVs de origem (13.5 = 13,5% a.a.);
a conversao para decimal (/100) acontece so aqui, uma vez, porque o
motor de precificacao (precificacao.pu/dv) exige decimal e um fator 100
errado e a classe de defeito que este projeto mais teme.

A juncao e pelo ultimo dia util do mes nos tres lados. O estoque
(estoque_titulos_vencimento.csv) traz o ultimo dia CORRIDO; taxa e VNA
(taxa_por_papel.csv, vna.csv, produzidos por parse_bloomberg) ja vem no
ultimo dia UTIL. Um merge(on="data") direto entre estoque cru e taxa
perde por volta de um terco do painel em silencio -- ver
docs/convencoes-dv.md. _posicoes normaliza o lado do estoque com
calendario.ultimo_dia_util_do_mes antes de qualquer juncao.
"""
import pandas as pd

from . import calendario, config, precificacao

TITULOS = ("LTN", "NTN-F", "NTN-B", "LFT")
_INDICE_DO_TITULO = {"NTN-B": "IPCA", "LFT": "SELIC"}

_COLUNAS = [
    "data", "isin", "titulo", "vencimento", "taxa_pct", "vna", "pu",
    "dv_unitario", "quantidade_mil", "dv_posicao_milhoes",
    "financeiro_calculado_milhoes",
]


def _ler(nome, **kw):
    caminho = config.PROCESSED_DIR / f"{nome}.csv"
    if not caminho.exists():
        raise FileNotFoundError(
            f"{caminho} nao existe. Rode a camada de dados e o parser da "
            f"Bloomberg antes: 'python -m tesouro.pipeline --sem-coleta'"
        )
    return pd.read_csv(caminho, **kw)


def _posicoes(cal):
    """Estoque do escopo, com a data ja no ultimo dia util do mes."""
    e = _ler("estoque_titulos_vencimento", parse_dates=["data", "vencimento"])
    e = e[(e["quantidade_mil"].fillna(0) > 0) & e["titulo"].isin(TITULOS)].copy()
    e["data"] = e["data"].dt.date.map(cal.ultimo_dia_util_do_mes)
    e["vencimento"] = e["vencimento"].dt.date
    return e[["data", "isin", "titulo", "vencimento", "quantidade_mil"]]


def _com_precos(cal):
    """Junta posicao, taxa e VNA, e calcula PU e DV linha a linha."""
    pos = _posicoes(cal)
    tx = _ler("taxa_por_papel", parse_dates=["data"])
    tx["data"] = tx["data"].dt.date
    vn = _ler("vna", parse_dates=["data"])
    vn["data"] = vn["data"].dt.date
    vna_por = {(r.data, r.indice): r.vna for r in vn.itertuples(index=False)}

    df = pos.merge(tx[["data", "isin", "taxa_pct"]], on=["data", "isin"], how="left")
    df["vna"] = [
        vna_por.get((d, _INDICE_DO_TITULO[t])) if t in _INDICE_DO_TITULO else None
        for d, t in zip(df["data"], df["titulo"])
    ]

    pus, dvs = [], []
    for r in df.itertuples(index=False):
        precisa_vna = r.titulo in _INDICE_DO_TITULO
        # pd.isna(r.vna), nao "r.vna is None": df["vna"] e uma coluna
        # numerica, e uma vez que ela recebe qualquer valor float o
        # pandas converte os None ausentes em NaN -- e NaN is None e
        # False. Com "is None" aqui, uma NTN-B sem VNA passa da guarda,
        # e precificacao._truncar(NaN, 6) tanto pode devolver um PU NaN
        # silencioso quanto levantar ValueError (math.trunc de NaN), em
        # vez de a linha ser pulada como None. Ver tests/test_dv.py,
        # test_vna_ausente_pula_a_linha_em_vez_de_precificar_com_nan.
        if pd.isna(r.taxa_pct) or (precisa_vna and pd.isna(r.vna)):
            pus.append(None)
            dvs.append(None)
            continue
        taxa = r.taxa_pct / 100.0
        pus.append(precificacao.pu(cal, r.titulo, r.data, r.vencimento, taxa, r.vna))
        dvs.append(precificacao.dv(cal, r.titulo, r.data, r.vencimento, taxa, r.vna))
    df["pu"] = pus
    df["dv_unitario"] = dvs
    return df


def painel():
    """Uma linha por papel e fim de mes, com insumos e resultado."""
    cal = calendario.padrao()
    df = _com_precos(cal)
    df["financeiro_calculado_milhoes"] = df["pu"] * df["quantidade_mil"] / 1000
    df["dv_posicao_milhoes"] = df["dv_unitario"] * df["quantidade_mil"] / 1000
    return df[_COLUNAS].sort_values(["data", "titulo", "vencimento"]).reset_index(drop=True)


def gravar_painel():
    """Grava dv_por_papel.csv em data/processed/.

    Nao usa gravacao.gravar_atomico: essa funcao protege downloads brutos
    de rede contra escrita parcial e paginas de erro salvas como
    planilha. Aqui o conteudo e gerado localmente a partir de arquivos ja
    validados em data/processed/, o padrao do projeto para esse caso (ver
    parse_bloomberg.gravar) e df.to_csv direto.
    """
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df = painel()
    saida = config.PROCESSED_DIR / "dv_por_papel.csv"
    df.to_csv(saida, index=False, encoding="utf-8")
    print(f"gravado: {saida} ({len(df)} linhas)")


if __name__ == "__main__":
    gravar_painel()
