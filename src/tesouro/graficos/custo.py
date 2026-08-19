"""Custo do estoque da divida contra a Selic e o IPCA.

O custo sozinho nao responde se a divida esta cara: 12,68% ao ano e caro ou barato
conforme onde estao a Selic e a inflacao. As tres linhas juntas mostram o custo
acompanhando a Selic com atraso, porque metade da divida e LFT e a outra metade foi
contratada no passado.

A SELIC E O IPCA SAEM DO NOSSO PROPRIO VNA. A variacao de 12 meses do VNA e o
indice acumulado -- 14,78% e 4,81% em jun/2026. A pagina do RMD busca isso no site
do Bacen; nos nao precisamos, e e por isso que esta branch nasceu de dv01-decay.

ARMADILHA 1: o custo_medio.csv tem tres medidas na mesma coluna. Este grafico e o
'acum_12m'. O 'mensal' da 13,64 para a DPF em junho, numero plausivel e errado.

ARMADILHA 2: o VNA e do ultimo dia util e o custo e do ultimo dia do mes -- so 137
das 198 datas coincidem. A juncao e por competencia (ano e mes), nunca por data.

ARMADILHA 3: shift(12) conta posicoes, nao meses. Com um buraco na serie do VNA a
variacao compara contra 13 meses atras em silencio, e por isso a completude do VNA
e travada por teste.
"""

import pandas as pd

from .. import config
from . import estilo

JANELAS = {"5 anos": 5, "completa": None}

NIVEIS = ["DPF", "DPMFi"]
INDICES = ["SELIC", "IPCA"]

_COR = {"DPF": "#1f3864",
        "DPMFi": "#3d9be9",
        "SELIC": "#2ca02c",
        "IPCA": "#ed7d31"}

_ROTULO = {"DPF": "custo da DPF",
           "DPMFi": "custo da DPMFi",
           "SELIC": "Selic acumulada em 12m",
           "IPCA": "IPCA acumulado em 12m"}


def variacao_12m_do_vna():
    """Selic e IPCA acumulados em 12 meses, a partir do VNA da entrega 2.

    O VNA e um indice acumulado: a razao entre o de hoje e o de doze meses atras,
    menos um, E a variacao do periodo. Nao ha nada a buscar no Bacen.
    """
    v = pd.read_csv(config.PROCESSED_DIR / "vna.csv", parse_dates=["data"])
    piv = v.pivot_table(index="data", columns="indice", values="vna")
    piv.index = piv.index.to_period("M")

    esperado = pd.period_range(piv.index.min(), piv.index.max(), freq="M")
    if list(piv.index) != list(esperado):
        faltam = sorted(set(esperado) - set(piv.index))
        raise LookupError(
            f"vna.csv tem {len(faltam)} mes(es) faltando ({faltam[:3]}...). A "
            f"variacao de 12 meses usa shift(12), que conta POSICOES: com buraco "
            f"na serie ela compara contra 13 ou 14 meses atras sem avisar."
        )

    return (piv / piv.shift(12) - 1) * 100


def dados_custo(janela=None):
    """Custo acumulado em 12 meses da DPF e da DPMFi, com a Selic e o IPCA.

    A juncao com o VNA e por competencia: o VNA e do ultimo dia util e o custo e do
    ultimo dia do mes, e so 137 das 198 datas coincidem.
    """
    c = pd.read_csv(config.PROCESSED_DIR / "custo_medio.csv", parse_dates=["data"])
    agregado = c[(c["medida"] == "acum_12m")
                 & c["entidade"].isna() & c["titulo"].isna()
                 & c["nivel"].isin(NIVEIS)]
    saida = agregado.pivot_table(index="data", columns="nivel",
                                 values="custo_aa_pct")[NIVEIS]

    indices = variacao_12m_do_vna()
    competencia = saida.index.to_period("M")
    for indice in INDICES:
        saida[indice] = indices[indice].reindex(competencia).to_numpy()

    return estilo.recorta(saida, janela)


def desenha_custo(dados, ax):
    """Quatro linhas, com o numero escrito so no ultimo ponto de cada uma.

    O eixo do tempo e anual e o dado continua mensal: a pagina do RMD usa cerca de
    170 rotulos mensais e ninguem le.
    """
    for coluna in NIVEIS + INDICES:
        serie = dados[coluna].dropna()
        largura = 2.6 if coluna in NIVEIS else 1.6
        estilo_linha = "-" if coluna in NIVEIS else "--"
        ax.plot(serie.index, serie, color=_COR[coluna], lw=largura,
                ls=estilo_linha, label=_ROTULO[coluna])
        ax.annotate(estilo.num_br(serie.iloc[-1], 2),
                    xy=(serie.index[-1], serie.iloc[-1]), xytext=(6, 0),
                    textcoords="offset points", fontsize=9.5, weight="bold",
                    color=_COR[coluna], va="center")

    ax.axhline(0, color="gray", lw=0.8)
    ax.set_ylabel("% ao ano")
    estilo.grade_fina(ax, 5, 2.5)
    estilo.eixo_anual(ax, a_cada=2)
    ax.legend(ncol=4, frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.08))
