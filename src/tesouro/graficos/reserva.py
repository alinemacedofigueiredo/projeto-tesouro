"""Reserva de liquidez, aba 6.1, em duas versoes que coexistem.

A de treze meses e a linguagem do RMD -- e o formato que a mesa e a diretoria ja
conhecem, e serve para apresentar. A de cinco anos responde a pergunta que treze
meses nao respondem: 8,33 e alto ou baixo? As duas ficam, por decisao da usuaria.

ARMADILHA: a folga (reserva menos valor prudencial) e NEGATIVA em jan e fev/2015 --
133,5 e 129,3 bi abaixo do colchao minimo. Sao os dois unicos meses da serie em que
isso acontece, e um fill_between sem where= e sem interpolate=True pinta os dois
como se fossem folga positiva. O grafico fica bonito e mente exatamente onde a
informacao importa.

Eixo duplo e permitido aqui; eixo truncado nao. A versao descartada comecava o eixo
do indice em 5,7 e transformava 2,6 meses de variacao num despencar.
"""

import pandas as pd

from .. import config
from . import estilo

JANELAS = {"5 anos": 5, "completa": None}

_COR_RESERVA = "#1f3864"
_COR_PRUDENCIAL = "#a6a6a6"
_COR_INDICE = "#ed7d31"


def dados_reserva(janela=None):
    """Reserva, valor prudencial, folga e indice de liquidez, mes a mes."""
    r = pd.read_csv(config.PROCESSED_DIR / "reserva_liquidez.csv",
                    parse_dates=["data"]).set_index("data").sort_index()
    saida = pd.DataFrame(index=r.index)
    saida["reserva"] = r["reserva_milhoes"]
    saida["prudencial"] = r["valor_prudencial_milhoes"]
    saida["folga"] = saida["reserva"] - saida["prudencial"]
    saida["indice"] = r["indice_liquidez_meses"]
    return estilo.recorta(saida, janela)


def dados_treze_meses():
    """Os ultimos treze meses, que e o recorte que a pagina do RMD usa."""
    return dados_reserva().tail(13)


def desenha_treze_meses(dados, ax):
    """O formato do RMD: duas barras por mes e o indice em linha a direita."""
    posicoes = range(len(dados))
    largura = 0.38
    ax.bar([p - largura / 2 for p in posicoes], dados["reserva"] / 1000,
           width=largura, color=_COR_RESERVA, label="reserva de liquidez")
    ax.bar([p + largura / 2 for p in posicoes], dados["prudencial"] / 1000,
           width=largura, color=_COR_PRUDENCIAL, label="valor prudencial")

    ax.set_xticks(list(posicoes))
    ax.set_xticklabels([estilo.rotulo_mes(d) for d in dados.index], fontsize=9)
    ax.set_ylabel("R$ bilh\u00f5es")
    ax.set_ylim(0, dados["reserva"].max() / 1000 * 1.25)
    ax.grid(axis="y", alpha=0.25)

    direita = ax.twinx()
    direita.plot(list(posicoes), dados["indice"], color=_COR_INDICE, lw=2.4,
                 marker="o", ms=4, label="\u00edndice de liquidez")
    direita.set_ylabel("meses de vencimento cobertos")
    # Comeca em zero SEMPRE: comecar no minimo da serie exagera a variacao.
    direita.set_ylim(0, dados["indice"].max() * 1.35)

    marcas, rotulos = ax.get_legend_handles_labels()
    m2, r2 = direita.get_legend_handles_labels()
    ax.legend(marcas + m2, rotulos + r2, ncol=3, frameon=False,
              loc="upper center", bbox_to_anchor=(0.5, -0.10))


def desenha_reserva(dados, ax):
    """A serie longa, com a folga sombreada e o indice a direita.

    O sombreado usa where= com interpolate=True: sem isso os dois meses de 2015 em
    que a reserva ficou ABAIXO do prudencial aparecem pintados como folga.
    """
    ax.plot(dados.index, dados["reserva"] / 1000, color=_COR_RESERVA, lw=2.4,
            label="reserva de liquidez")
    ax.plot(dados.index, dados["prudencial"] / 1000, color=_COR_PRUDENCIAL,
            lw=1.6, label="valor prudencial")

    ax.fill_between(dados.index, dados["reserva"] / 1000,
                    dados["prudencial"] / 1000,
                    where=dados["folga"] >= 0, interpolate=True,
                    color=_COR_RESERVA, alpha=0.18, label="folga")
    ax.fill_between(dados.index, dados["reserva"] / 1000,
                    dados["prudencial"] / 1000,
                    where=dados["folga"] < 0, interpolate=True,
                    color="#d62728", alpha=0.30, label="abaixo do prudencial")

    ax.set_ylabel("R$ bilh\u00f5es")
    ax.set_ylim(0, dados["reserva"].max() / 1000 * 1.20)
    ax.grid(axis="y", alpha=0.25)
    estilo.eixo_anual(ax)

    direita = ax.twinx()
    direita.plot(dados.index, dados["indice"], color=_COR_INDICE, lw=1.8, ls="--",
                 label="\u00edndice de liquidez")
    direita.set_ylabel("meses de vencimento cobertos")
    direita.set_ylim(0, dados["indice"].max() * 1.30)
    direita.annotate(estilo.num_br(dados["indice"].iloc[-1], 2),
                     xy=(dados.index[-1], dados["indice"].iloc[-1]),
                     xytext=(6, 0), textcoords="offset points", fontsize=9.5,
                     weight="bold", color=_COR_INDICE, va="center")

    marcas, rotulos = ax.get_legend_handles_labels()
    m2, r2 = direita.get_legend_handles_labels()
    ax.legend(marcas + m2, rotulos + r2, ncol=5, frameon=False,
              loc="upper center", bbox_to_anchor=(0.5, -0.08))
