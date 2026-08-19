"""Prazo medio da divida, por nivel, com a banda do PAF.

Tres linhas: DPF, DPMFi e DPFe. A DPF e a media ponderada das outras duas, e por
isso fica sempre entre elas -- se algum mes sair do sanduiche, o filtro pegou linha
que nao devia.

ARMADILHA 1: as linhas agregadas do CSV sao as que tem 'entidade' E 'titulo'
vazios. Filtrar so por nivel traz tambem uma linha por titulo (LTN, NTN-B, ...) e
uma por entidade, e a media sai errada sem nenhum sinal.

ARMADILHA 2: a serie nao e mensal no comeco -- vai de dez/2005 direto para nov/2006.
Sao 237 observacoes em vinte anos e meio, nao 247. Conta que suponha espacamento
constante erra os dois primeiros anos.
"""

import pandas as pd

from .. import config
from . import estilo

NIVEIS = ["DPF", "DPMFi", "DPFe"]

# So estes dois levam rotulo no fim da linha: sao os numeros que a usuaria usa. O
# da DPF e consequencia aritmetica dos dois, e fica como contexto.
COM_ROTULO = ("DPMFi", "DPFe")

_COR = {"DPF": estilo.COR["neutro"],
        "DPMFi": "#1f6feb",
        "DPFe": "#ed7d31"}


def dados_prazo():
    """Prazo medio em anos, por nivel e por data."""
    p = pd.read_csv(config.PROCESSED_DIR / "prazo_medio_por_titulo.csv",
                    parse_dates=["data"])
    agregado = p[p["entidade"].isna() & p["titulo"].isna()]
    piv = agregado.pivot_table(index="data", columns="nivel",
                               values="prazo_anos", aggfunc="mean")
    return piv[NIVEIS].dropna(how="all")


def desenha_prazo(dados, banda, ax):
    """As tres linhas, com a banda do PAF da DPF desenhada ano a ano.

    A banda e do prazo medio da DPF -- que e justamente a linha de contexto, a mais
    fina. A legenda diz isso em vez de deixar o leitor supor que ela vale para a
    linha mais grossa.
    """
    for ano in range(dados.index.min().year, dados.index.max().year + 1):
        if ano not in banda.index:
            continue
        inicio = pd.Timestamp(year=ano, month=1, day=1)
        fim = pd.Timestamp(year=ano, month=12, day=31)
        ax.fill_between([inicio, fim], banda.loc[ano, "minimo"],
                        banda.loc[ano, "maximo"], color=estilo.COR["banda"],
                        alpha=0.13, linewidth=0, zorder=1)
        if pd.notna(banda.loc[ano, "minimo_original"]):
            for nivel in ("minimo_original", "maximo_original"):
                ax.plot([inicio, fim], [banda.loc[ano, nivel]] * 2,
                        color=estilo.COR["banda"], lw=0.8, ls=":", zorder=2)

    for nivel in NIVEIS:
        grossura = 2.6 if nivel in COM_ROTULO else 1.3
        ax.plot(dados.index, dados[nivel], color=_COR[nivel], lw=grossura,
                label=nivel, zorder=3)
        if nivel in COM_ROTULO:
            ax.annotate(estilo.num_br(dados[nivel].iloc[-1], 2),
                        xy=(dados.index[-1], dados[nivel].iloc[-1]),
                        xytext=(6, 0), textcoords="offset points",
                        fontsize=9.5, weight="bold", color=_COR[nivel],
                        va="center")

    ax.set_ylabel("anos")
    ax.set_ylim(0, max(8.0, dados.max().max() * 1.08))
    estilo.grade_fina(ax, 1, 0.5)
    estilo.eixo_anual(ax, a_cada=2)
    ax.legend(ncol=3, frameon=False, loc="upper left",
              title="banda: meta do PAF para o prazo m\u00e9dio da DPF")
