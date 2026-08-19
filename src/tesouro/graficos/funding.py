"""Funding do DPMFi: emissoes, resgates e o liquido, das abas 1.1 e 1.2.

Tres graficos: o net mes a mes com media movel de 12 meses e acumulado de 12 meses;
a emissao bruta por indexador; e a composicao anual da emissao em 100%.

Decisoes tomadas com a usuaria: so a esfera DPMFi; sem media movel de 3 meses; e a
emissao anual por INDEXADOR e nao por papel, porque pela aba 1.2 a cobertura e 100%
da emissao do RMD contra 93% a 97% se viesse dos leiloes.
"""

import pandas as pd

from .. import config
from . import estilo

JANELAS = {"5 anos": 5, "completa": None}

_ORDEM = ["Prefixados", "\u00cdndice de Pre\u00e7os", "Taxa Flutuante",
          "C\u00e2mbio", "Demais"]

_CHAVE_COR = {"Prefixados": "Prefixado",
              "\u00cdndice de Pre\u00e7os": "Indice Precos",
              "Taxa Flutuante": "Taxa Flutuante",
              "C\u00e2mbio": "Cambio",
              "Demais": "Demais"}


def dados_net(janela=None):
    """Emissao, resgate e net do DPMFi por mes, em R$ milhoes."""
    f = pd.read_csv(config.PROCESSED_DIR / "funding_por_canal.csv",
                    parse_dates=["data"])
    d = (f[f["esfera"] == "DPMFi"]
         .groupby(["data", "operacao"])["valor_milhoes"].sum()
         .unstack())
    d["net"] = d["emissao"] - d["resgate"]
    # Media movel de TRES meses: a de doze alisava demais e escondia o giro
    # trimestral, que e o horizonte em que a decisao de emissao e tomada.
    d["mm3"] = d["net"].rolling(3).mean()
    d["acum12"] = d["net"].rolling(12).sum()
    return estilo.recorta(d, janela)


def dados_emissao_indexador(janela=None):
    """Emissao bruta do DPMFi por indexador e por mes, em R$ milhoes."""
    f = pd.read_csv(config.PROCESSED_DIR / "funding_por_indexador.csv",
                    parse_dates=["data"])
    e = f[(f["esfera"] == "DPMFi") & (f["operacao"] == "emissao")]
    piv = e.pivot_table(index="data", columns="indexador",
                        values="valor_milhoes", aggfunc="sum").fillna(0.0)
    piv = piv.loc[:, piv.sum() > 0]
    return estilo.recorta(piv[[c for c in _ORDEM if c in piv.columns]], janela)


def dados_emissao_anual(anos=12):
    """Composicao da emissao por indexador, ano a ano, em percentual.

    'total_milhoes' carrega o tamanho do ano: sem ele, 100% esconde que 2018 foram
    657 bi e 2025 foram 1.841 bi.
    """
    f = pd.read_csv(config.PROCESSED_DIR / "funding_por_indexador.csv",
                    parse_dates=["data"])
    e = f[(f["esfera"] == "DPMFi") & (f["operacao"] == "emissao")].copy()
    e["ano"] = e["data"].dt.year
    piv = e.pivot_table(index="ano", columns="indexador",
                        values="valor_milhoes", aggfunc="sum").fillna(0.0)
    piv = piv[piv.index >= piv.index.max() - anos + 1]
    piv = piv.loc[:, piv.sum() > 0]
    total = piv.sum(axis=1)
    saida = (piv.div(total, axis=0) * 100)[[c for c in _ORDEM if c in piv.columns]]
    saida = saida.copy()
    saida["total_milhoes"] = total
    return saida


def ultimo_mes_com_emissao():
    """Data do ultimo mes com emissao, para marcar o ano parcial."""
    f = pd.read_csv(config.PROCESSED_DIR / "funding_por_indexador.csv",
                    parse_dates=["data"])
    return f["data"].max()

def _rotula_ultimo(ax, serie, cor):
    """Escreve o valor do ultimo ponto, ao lado dele."""
    serie = serie.dropna()
    if serie.empty:
        return
    ax.annotate(estilo.num_br(serie.iloc[-1], 1),
                xy=(serie.index[-1], serie.iloc[-1]), xytext=(7, 0),
                textcoords="offset points", fontsize=9, weight="bold",
                color=cor, va="center")


def _rotula_extremos(ax, serie, cor):
    """Escreve o maior, o menor e o ultimo valor da serie.

    Os tres pontos que alguem procura numa serie longa: quanto foi o pior mes, o
    melhor, e onde estamos. Sem eles a barra so diz "grande" ou "pequena" -- com a
    escala indo de -302 a +181, isso nao e leitura.
    """
    serie = serie.dropna()
    if serie.empty:
        return
    marcados = {serie.idxmax(), serie.idxmin(), serie.index[-1]}
    for quando in marcados:
        valor = serie.loc[quando]
        acima = valor >= 0
        ax.annotate(estilo.num_br(valor, 1), xy=(quando, valor),
                    xytext=(0, 6 if acima else -13), textcoords="offset points",
                    ha="center", fontsize=8.5, weight="bold", color=cor)


def desenha_net(dados, fig):
    """Dois paineis: o net do mes com a MM3, e o acumulado de 12 meses.

    A BARRA E UMA SERIE SO. Verde e vermelho sao o sinal do MESMO numero -- o net do
    mes -- e nao emissao contra resgate. A distincao importa porque quem olha le
    duas cores como duas categorias: foi o que aconteceu na primeira leitura. Por
    isso as duas cores entram na legenda com nome proprio, em vez de uma entrada so
    dizendo "net do mes".

    Emissao e resgate lado a lado ao longo de 236 meses foi construido e recusado:
    ficou ilegivel a ponto de quem desenhou ler o proprio grafico errado.

    O preenchimento de baixo usa interpolate=True porque sem isso aparecem falhas
    nos cruzamentos do zero.
    """
    import matplotlib.patches as mpatches

    a1, a2 = fig.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": [2, 1]})

    cores = ["#2ca02c" if v >= 0 else "#d62728" for v in dados["net"]]
    a1.bar(dados.index, dados["net"] / 1000, width=18, color=cores, alpha=0.45)
    verde = mpatches.Patch(color="#2ca02c", alpha=0.45,
                           label="net do m\u00eas, positivo (emitiu mais do que resgatou)")
    vermelho = mpatches.Patch(color="#d62728", alpha=0.45,
                              label="net do m\u00eas, negativo (resgatou mais do que emitiu)")
    a1.plot(dados.index, dados["mm3"] / 1000, color="#1f6feb", lw=2.8,
            label="m\u00e9dia m\u00f3vel de 3 meses")
    a1.axhline(0, color="gray", lw=0.8)
    a1.set_ylabel("R$ bilh\u00f5es por m\u00eas")
    marcas, rotulos = a1.get_legend_handles_labels()
    a1.legend([verde, vermelho] + marcas, [verde.get_label(), vermelho.get_label()]
              + rotulos, ncol=1, frameon=False, loc="upper left", fontsize=9)

    # Grade a cada 50 bi com uma linha fraca no meio de cada faixa. Sem ela, a
    # barra de 143 e a de 156 sao indistinguiveis a olho -- e a escala vai de -302
    # a +181, entao o erro de leitura chega a dezenas de bilhoes.
    estilo.grade_fina(a1, 50, 25)
    # Folga no topo para a legenda e para o rotulo do maior mes nao encostarem na
    # moldura, e um pouco embaixo pelo mesmo motivo.
    net = dados["net"] / 1000
    a1.set_ylim(net.min() * 1.14, net.max() * 1.75)
    _rotula_extremos(a1, net, "#333333")
    _rotula_ultimo(a1, dados["mm3"] / 1000, "#1f6feb")

    for cond, cor in [(dados["acum12"] >= 0, "#2ca02c"), (dados["acum12"] < 0, "#d62728")]:
        a2.fill_between(dados.index, dados["acum12"] / 1000, 0, where=cond,
                        color=cor, alpha=0.5, interpolate=True)
    a2.plot(dados.index, dados["acum12"] / 1000, color="#444444", lw=1)
    a2.axhline(0, color="gray", lw=0.8)
    a2.set_ylabel("R$ bilh\u00f5es")
    a2.set_title("Net acumulado de 12 meses", fontsize=10)
    estilo.grade_fina(a2, 200, 100)
    _rotula_extremos(a2, dados["acum12"] / 1000, "#333333")
    estilo.eixo_anual(a2)


def desenha_emissao_indexador(dados, ax):
    """Barra empilhada da emissao bruta por indexador."""
    base = 0
    for k in dados.columns:
        ax.bar(dados.index, dados[k] / 1000, bottom=base, width=18,
               color=estilo.COR[_CHAVE_COR[k]], label=k)
        base = base + dados[k] / 1000
    ax.set_ylabel("R$ bilh\u00f5es emitidos")
    ax.legend(ncol=len(dados.columns), frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.08))
    ax.grid(axis="y", alpha=0.25)
    estilo.eixo_anual(ax)


def desenha_emissao_anual(dados, ax, ano_parcial):
    """Barra de 100% por ano, com o total acima e o ano parcial marcado."""
    cols = [c for c in dados.columns if c != "total_milhoes"]
    base = pd.Series(0.0, index=dados.index)
    for k in cols:
        ax.bar(dados.index, dados[k], bottom=base, width=0.72,
               color=estilo.COR[_CHAVE_COR[k]], label=k)
        for x in dados.index:
            h = dados.loc[x, k]
            if h >= 4:
                ax.text(x, base[x] + h / 2, f"{h:.0f}", ha="center", va="center",
                        fontsize=8.5, color="white", weight="bold")
        base = base + dados[k]

    for x in dados.index:
        ax.text(x, 101.5, estilo.num_br(dados.loc[x, "total_milhoes"] / 1000, 0) + " bi",
                ha="center", fontsize=8, color="#444444")

    ax.set_ylim(0, 108)
    ax.set_xticks(list(dados.index))
    ax.set_xticklabels([str(a) if a != ano_parcial else f"{a}*" for a in dados.index])
    ax.set_ylabel("% do financeiro emitido no ano")
    ax.legend(ncol=len(cols), frameon=False, loc="lower center",
              bbox_to_anchor=(0.5, -0.13))
    ax.grid(axis="y", alpha=0.20)
