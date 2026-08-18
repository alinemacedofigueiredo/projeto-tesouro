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
    dup = vn.duplicated(subset=["data", "indice"])
    if dup.any():
        exemplos = vn.loc[dup, ["data", "indice"]].drop_duplicates().head(5).values.tolist()
        raise ValueError(
            f"vna.csv tem (data, indice) duplicado em {int(dup.sum())} linha(s), "
            f"exemplos: {exemplos}. O dicionario vna_por fica com a ultima "
            f"ocorrencia em silencio; corrija a origem antes de montar o painel."
        )
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


# ---------------------------------------------------------------------------
# Decay: Conta B da spec -- so a passagem do tempo, taxa e VNA constantes.
#
# Nao envolve dinheiro nem VNA reprojetado: e mecanico, prazo menor implica
# DV menor em modulo. A outra conta, o resultado realizado com movimento de
# taxa (Conta A), fica na Tarefa 8 e nao usa nada daqui.
#
# Convencao de sinal do decay: dv e negativo para titulo (docs/convencoes-
# dv.md). Com menos prazo o DV fica MENOS negativo, entao decay = dv_alvo -
# dv_base e POSITIVO para um sobrevivente -- o numero mede o quanto o DV
# "encolheu" em modulo. Para um papel que vence no caminho, dv_alvo e 0.0 e
# decay tambem sai positivo (a mesma formula), mas dv_alvo=0 misturado com
# o encolhimento normal e exatamente o que venceu_no_caminho existe para
# marcar -- nunca somar as duas coisas sem olhar essa coluna.
# ---------------------------------------------------------------------------

HORIZONTES = {"1du": 1, "5du": 5, "21du": 21}

_COLUNAS_DECAY = [
    "data_base", "horizonte", "data_alvo", "isin", "titulo",
    "venceu_no_caminho", "dv_base", "dv_alvo", "decay",
]


def _decay_de(cal, linhas, data_base, data_alvo, rotulo):
    """Reprecifica cada papel na data-alvo, com taxa e VNA constantes.

    Conta B da spec: so o efeito da passagem do tempo. Papel que vence no
    caminho recebe dv_alvo zero -- ele existia e deixou de existir, o que
    e informacao, nao ausencia -- e fica marcado em venceu_no_caminho para
    nao se confundir com queda de risco de um papel vivo. Para papel
    vencido, precificacao.dv nunca e chamado: o zero vem direto, sem
    reprecificar nada (ver test_venceu_no_caminho_nunca_chama_precificacao
    em tests/test_decay.py).
    """
    saida = []
    for r in linhas.itertuples(index=False):
        venceu = cal.ajustar_vencimento(r.vencimento) <= data_alvo
        if pd.isna(r.taxa_pct) or pd.isna(r.dv_unitario):
            # Sem taxa ou sem dv_unitario na base, nao ha decay medivel --
            # nao dava para medir o risco de partida, entao nao da para
            # medir a variacao, mesmo que o papel tambem tenha vencido no
            # caminho. None, nao zero -- "nao se aplica" e diferente de
            # "risco genuinamente nulo". Esta guarda vem ANTES da de
            # vencimento de proposito: um papel vencido sem dv_base
            # medido (ex.: NTN-F ja vencida no estoque, sem taxa na
            # data) nao pode virar "risco foi a zero", porque o risco de
            # partida nunca foi conhecido.
            alvo = None
        elif venceu:
            alvo = 0.0
        else:
            unitario = precificacao.dv(
                cal, r.titulo, data_alvo, r.vencimento, r.taxa_pct / 100.0, r.vna
            )
            alvo = unitario * r.quantidade_mil / 1000
        base = r.dv_posicao_milhoes
        decaimento = None if (alvo is None or pd.isna(base)) else alvo - base
        saida.append((data_base, rotulo, data_alvo, r.isin, r.titulo,
                      venceu, base, alvo, decaimento))
    return saida


def decay(horizontes=None):
    """Decay a taxa constante, por papel, nos horizontes pedidos.

    horizontes: dict rotulo -> passos em dias uteis (base 252). Default
    HORIZONTES = {"1du": 1, "5du": 5, "21du": 21}.
    """
    horizontes = horizontes or HORIZONTES
    cal = calendario.padrao()
    p = painel()
    p = p[p["titulo"] != "LFT"]           # LFT nao tem DV no projeto (None)

    linhas = []
    for data_base, grupo in p.groupby("data", sort=True):
        for rotulo, passos in horizontes.items():
            alvo = cal.mover(data_base, passos)
            linhas += _decay_de(cal, grupo, data_base, alvo, rotulo)
    return pd.DataFrame(linhas, columns=_COLUNAS_DECAY).sort_values(
        ["data_base", "horizonte", "titulo", "isin"]
    ).reset_index(drop=True)


def gravar_decay():
    """Grava decay_por_papel.csv em data/processed/.

    Mesmo padrao de gravar_painel: conteudo gerado localmente a partir de
    data/processed/ ja validado, entao df.to_csv direto, sem gravar_atomico
    (essa protege download bruto de rede, nao e o caso aqui).
    """
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df = decay()
    saida = config.PROCESSED_DIR / "decay_por_papel.csv"
    df.to_csv(saida, index=False, encoding="utf-8")
    print(f"gravado: {saida} ({len(df)} linhas)")


if __name__ == "__main__":
    gravar_painel()
