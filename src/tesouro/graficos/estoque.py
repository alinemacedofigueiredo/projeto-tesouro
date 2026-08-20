"""Composicao da DPF por indexador, com a banda do PAF por cima.

O retrato da gestao: quanto da divida esta em cada indexador, mes a mes desde
dez/2000, contra o que o PAF prometeu para cada ano.

A serie completa e o padrao, e nao os 5 anos: o cambio sai de 51,0% em set/2002
para 3,7% hoje, e essa queda -- que e o fato central da gestao da divida brasileira
-- nao existe dentro de uma janela curta.

ARMADILHA: a aba 2.1 grava o indexador como "Indice Precos" e a aba 1.2, que
alimenta o funding.py, grava "Indice de Precos", com "de" no meio. Copiar a lista
de nomes de la deixa uma coluna vazia e um indexador fora do grafico.
"""

import pandas as pd

from .. import config
from . import estilo

_ORDEM = ["Prefixado", "\u00cdndice Pre\u00e7os", "Taxa Flutuante",
          "C\u00e2mbio", "Demais"]

_CHAVE_COR = {"Prefixado": "Prefixado",
              "\u00cdndice Pre\u00e7os": "Indice Precos",
              "Taxa Flutuante": "Taxa Flutuante",
              "C\u00e2mbio": "Cambio",
              "Demais": "Demais"}

# Qual banda do PAF corresponde a qual coluna do nosso CSV.
BANDA_DE = {"prefixado_pct": "Prefixado",
            "indice_precos_pct": "\u00cdndice Pre\u00e7os",
            "taxa_flutuante_pct": "Taxa Flutuante",
            "cambio_pct": "C\u00e2mbio"}


def dados_composicao(janela=None):
    """Participacao de cada indexador na DPF, em percentual, mes a mes.

    'estoque_milhoes' viaja junto porque o percentual sozinho nao diz que a divida
    saiu de 654 bi para 9.268 bi no mesmo periodo.
    """
    c = pd.read_csv(config.PROCESSED_DIR / "composicao_dpf.csv",
                    parse_dates=["data"])
    piv = c.pivot_table(index="data", columns="indexador",
                        values="valor_milhoes", aggfunc="sum").fillna(0.0)
    total = piv.sum(axis=1)
    share = piv.div(total, axis=0) * 100
    share = share[[k for k in _ORDEM if k in share.columns]].copy()
    share["estoque_milhoes"] = total
    return estilo.recorta(share, janela)


def desenha_composicao_100(dados, ax):
    """A mesma composicao, empilhada em 100%.

    O grafico de linha responde "onde estamos contra a meta do PAF"; este responde
    "de que a divida e feita". Sao perguntas diferentes e por isso os dois existem
    -- e e neste que a queda do cambio se le como o que ela foi: uma faixa que
    ocupava metade do grafico em 2002 e hoje e um fio.

    A faixa "Demais" entra aqui, ao contrario do grafico de linha: numa area
    empilhada de 100% ela tem de entrar, ou a soma nao fecha.
    """
    colunas = [c for c in dados.columns if c != "estoque_milhoes"]
    ax.stackplot(dados.index, *[dados[c] for c in colunas],
                 labels=colunas,
                 colors=[estilo.COR[_CHAVE_COR[c]] for c in colunas],
                 edgecolor="white", linewidth=0.3)

    # O valor de cada faixa no ultimo mes, escrito na altura do meio da faixa.
    base = 0.0
    for coluna in colunas:
        altura = dados[coluna].iloc[-1]
        if altura >= 2.0:
            ax.annotate(estilo.num_br(altura, 1), xy=(dados.index[-1], base + altura / 2),
                        xytext=(7, 0), textcoords="offset points", fontsize=9,
                        weight="bold", color=estilo.COR[_CHAVE_COR[coluna]],
                        va="center")
        base += altura

    # O pico do cambio marcado, porque e o fato que o grafico existe para contar.
    #
    # A seta aponta para o MEIO DA FAIXA do cambio, e nao para a altura do valor: a
    # faixa e a quarta da pilha, entao 51% dela mora entre 74 e 100, e nao entre 0 e
    # 51. Apontar para 25,5 poria a seta dentro da faixa do prefixado -- que e o
    # tipo de erro que passa despercebido porque a seta continua "parecendo certa".
    cambio = dados["C\u00e2mbio"]
    if cambio.max() > 30:
        quando = cambio.idxmax()
        abaixo = sum(dados[c].loc[quando] for c in colunas[:colunas.index("C\u00e2mbio")])
        ax.annotate(f"c\u00e2mbio no pico: {estilo.num_br(cambio.max(), 1)}%",
                    xy=(quando, abaixo + cambio.loc[quando] / 2),
                    xytext=(30, -22), textcoords="offset points", fontsize=9,
                    color="white", weight="bold",
                    arrowprops={"arrowstyle": "-", "color": "white", "lw": 1.2})

    ax.set_ylim(0, 100)
    ax.set_xlim(dados.index.min(), dados.index.max())
    ax.set_ylabel("% da DPF")
    estilo.eixo_anual(ax, a_cada=2)
    ax.legend(ncol=len(colunas), frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.08))


def desenha_composicao(dados, bandas, ax):
    """Uma linha por indexador, com a banda do PAF desenhada ano a ano.

    A banda vai por cima do proprio grafico, ano a ano, e nao como caixa estatica
    embaixo do jeito que o RMD faz: assim da para ver, em cada ano, se o realizado
    ficou dentro ou fora do que foi prometido.

    Nos anos revisados a banda original aparece em linha pontilhada por baixo, para
    que a mudanca de meta nao desapareca.
    """
    visiveis = range(dados.index.min().year, dados.index.max().year + 1)

    for indicador, coluna in BANDA_DE.items():
        b = bandas[indicador]
        cor = estilo.COR[_CHAVE_COR[coluna]]
        for ano in visiveis:
            if ano not in b.index:
                continue
            inicio = pd.Timestamp(year=ano, month=1, day=1)
            fim = pd.Timestamp(year=ano, month=12, day=31)
            ax.fill_between([inicio, fim],
                            b.loc[ano, "minimo"], b.loc[ano, "maximo"],
                            color=cor, alpha=0.12, linewidth=0, zorder=1)
            if pd.notna(b.loc[ano, "minimo_original"]):
                for nivel in ("minimo_original", "maximo_original"):
                    ax.plot([inicio, fim], [b.loc[ano, nivel]] * 2,
                            color=cor, lw=0.8, ls=":", zorder=2)

    for coluna in [c for c in dados.columns if c != "estoque_milhoes"]:
        if coluna == "Demais":
            continue                     # nunca passa de 0,06% da DPF
        ax.plot(dados.index, dados[coluna], lw=2.2,
                color=estilo.COR[_CHAVE_COR[coluna]], label=coluna, zorder=3)
        ax.annotate(estilo.num_br(dados[coluna].iloc[-1], 1),
                    xy=(dados.index[-1], dados[coluna].iloc[-1]),
                    xytext=(6, 0), textcoords="offset points",
                    fontsize=9, color=estilo.COR[_CHAVE_COR[coluna]],
                    va="center", weight="bold")

    ax.set_ylabel("% da DPF")
    ax.set_ylim(0, 60)
    estilo.grade_fina(ax, 10, 5)
    estilo.eixo_anual(ax, a_cada=2)
    ax.legend(ncol=4, frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.08))
