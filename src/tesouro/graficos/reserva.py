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

_COR_RESERVA = "#1f3864"
_COR_PRUDENCIAL = "#a6a6a6"
_COR_INDICE = "#ed7d31"

# O nome completo da coluna na aba 6.1 e "Valor Prudencial (3 meses)". O "(3 meses)"
# se perdeu no nome da coluna do nosso CSV, e sem ele o numero fica sem definicao:
# 783 bi so quer dizer alguma coisa sabendo que sao tres meses de vencimento.
ROTULO_PRUDENCIAL = "valor prudencial (3 meses)"


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
           width=largura, color=_COR_PRUDENCIAL, label=ROTULO_PRUDENCIAL)

    # Rotulo em cada barra: sao treze meses e duas series, e o formato do RMD e de
    # apresentacao -- quem olha o slide quer ler o numero, nao estima-lo pela altura.
    for p, (_, linha) in zip(posicoes, dados.iterrows()):
        ax.annotate(estilo.num_br(linha["reserva"] / 1000, 0),
                    xy=(p - largura / 2, linha["reserva"] / 1000),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", fontsize=7.5, color=_COR_RESERVA, weight="bold")
        ax.annotate(estilo.num_br(linha["prudencial"] / 1000, 0),
                    xy=(p + largura / 2, linha["prudencial"] / 1000),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", fontsize=7.5, color="#6f6f6f")

    ax.set_xticks(list(posicoes))
    ax.set_xticklabels([estilo.rotulo_mes(d) for d in dados.index], fontsize=9)
    ax.set_ylabel("R$ bilh\u00f5es")
    ax.set_ylim(0, dados["reserva"].max() / 1000 * 1.25)
    ax.grid(axis="y", alpha=0.25)

    direita = ax.twinx()
    direita.plot(list(posicoes), dados["indice"], color=_COR_INDICE, lw=2.4,
                 marker="o", ms=4, label="\u00edndice de liquidez")
    for p, valor in zip(posicoes, dados["indice"]):
        direita.annotate(estilo.num_br(valor, 2), xy=(p, valor), xytext=(0, 7),
                         textcoords="offset points", ha="center", fontsize=7.5,
                         color=_COR_INDICE, weight="bold")
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
            lw=1.6, label=ROTULO_PRUDENCIAL)

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
