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

NIVEIS = ["DPF", "DPMFi"]
INDICES = ["SELIC", "IPCA"]

# A DPFe entra so quando pedida. Ela nao mede a mesma coisa que as outras duas: e
# divida externa medida em real, entao o custo e cupom MAIS variacao cambial, e a
# serie vai de -16,0% (jan/2017) a +62,6% (set/2015) enquanto a DPF e a DPMFi vivem
# entre 10% e 14%. Desenhada junto por padrao, ela achata as outras e convida a
# leitura de que as tres sao comparaveis.
NIVEL_OPCIONAL = "DPFe"

_COR = {"DPF": "#1f3864",
        "DPMFi": "#3d9be9",
        "DPFe": "#8c564b",
        "SELIC": "#2ca02c",
        "IPCA": "#ed7d31"}

_ROTULO = {"DPF": "custo da DPF",
           "DPMFi": "custo da DPMFi",
           "DPFe": "custo da DPFe (carrega c\u00e2mbio)",
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


def dados_custo(janela=None, com_dpfe=False):
    """Custo acumulado em 12 meses da DPF e da DPMFi, com a Selic e o IPCA.

    Com com_dpfe=True a DPFe entra como quinta serie. Ela e opcional porque mede
    outra coisa: divida externa em real, com o cambio dentro. Ver NIVEL_OPCIONAL.

    A juncao com o VNA e por competencia: o VNA e do ultimo dia util e o custo e do
    ultimo dia do mes, e so 137 das 198 datas coincidem.
    """
    niveis = NIVEIS + ([NIVEL_OPCIONAL] if com_dpfe else [])
    c = pd.read_csv(config.PROCESSED_DIR / "custo_medio.csv", parse_dates=["data"])
    agregado = c[(c["medida"] == "acum_12m")
                 & c["entidade"].isna() & c["titulo"].isna()
                 & c["nivel"].isin(niveis)]
    saida = agregado.pivot_table(index="data", columns="nivel",
                                 values="custo_aa_pct")[niveis]

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
    desenhadas = [c for c in dados.columns]
    ultimos = {}
    for coluna in desenhadas:
        serie = dados[coluna].dropna()
        largura = 2.6 if coluna not in INDICES else 1.6
        estilo_linha = "-" if coluna not in INDICES else "--"
        ax.plot(serie.index, serie, color=_COR[coluna], lw=largura,
                ls=estilo_linha, label=_ROTULO[coluna])
        ultimos[coluna] = (serie.index[-1], serie.iloc[-1])

    ax.axhline(0, color="gray", lw=0.8)
    ax.set_ylabel("% ao ano")

    # O eixo sai do dado, e nao de um limite fixo: com a DPFe ele precisa abrir
    # para baixo de zero e bem mais para cima. Fixar o eixo faria a DPFe sair
    # cortada ou espremeria as outras quatro num tapete.
    piso = min(0.0, float(dados.min().min())) - 1.5
    teto = float(dados.max().max()) + 1.5
    ax.set_ylim(piso, teto)

    # O rotulo de cada linha vai no ultimo ponto, e dois deles se sobrepoem quando o
    # eixo abre: com a DPFe dentro, a DPF (12,68) e a DPMFi (13,19) ficam a meio
    # ponto uma da outra num eixo de 47 pontos, e os textos viram um borrao. Aqui
    # eles sao empurrados para cima ate caberem, na ordem do valor.
    minimo = (teto - piso) * 0.035
    anterior = None
    for coluna, (x, y) in sorted(ultimos.items(), key=lambda item: item[1][1]):
        alvo = y if anterior is None else max(y, anterior + minimo)
        ax.annotate(estilo.num_br(y, 2), xy=(x, alvo), xytext=(6, 0),
                    textcoords="offset points", fontsize=9.5, weight="bold",
                    color=_COR[coluna], va="center")
        anterior = alvo

    passo = 5 if teto - piso <= 45 else 10
    estilo.grade_fina(ax, passo, passo / 2)
    estilo.eixo_anual(ax, a_cada=2)
    ax.legend(ncol=len(desenhadas), frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.08))


def dados_custo_emissao(janela=None):
    """Custo das emissoes dos ultimos 12 meses contra o custo do estoque, DPMFi.

    O custo de emissao sozinho nao diz nada; contra o do estoque mostra a direcao:
    em jun/26 o Tesouro emite a 14,20% e carrega a 13,19%, entao a divida encarece
    sem que nenhuma decisao nova seja tomada.

    A serie de emissoes comeca em dez/2010, cinco anos depois da do estoque, e por
    isso este grafico e mais curto que o principal.
    """
    c = pd.read_csv(config.PROCESSED_DIR / "custo_medio.csv", parse_dates=["data"])
    agregado = c[(c["nivel"] == "DPMFi")
                 & c["entidade"].isna() & c["titulo"].isna()]
    piv = agregado.pivot_table(index="data", columns="medida",
                               values="custo_aa_pct")

    saida = pd.DataFrame(index=piv.index)
    saida["emissao"] = piv["emissoes_12m"]
    saida["estoque"] = piv["acum_12m"]
    saida = saida.dropna(subset=["emissao"])
    return estilo.recorta(saida, janela)


def desenha_custo_emissao(dados, ax):
    """As duas linhas, com a diferenca sombreada entre elas."""
    ax.plot(dados.index, dados["emissao"], color="#c00000", lw=2.4,
            label="custo das emiss\u00f5es em 12m")
    ax.plot(dados.index, dados["estoque"], color="#1f3864", lw=2.4,
            label="custo do estoque em 12m")
    ax.fill_between(dados.index, dados["emissao"], dados["estoque"],
                    where=dados["emissao"] >= dados["estoque"], interpolate=True,
                    color="#c00000", alpha=0.14)
    ax.fill_between(dados.index, dados["emissao"], dados["estoque"],
                    where=dados["emissao"] < dados["estoque"], interpolate=True,
                    color="#1f3864", alpha=0.14)

    for coluna, cor in (("emissao", "#c00000"), ("estoque", "#1f3864")):
        ax.annotate(estilo.num_br(dados[coluna].iloc[-1], 2),
                    xy=(dados.index[-1], dados[coluna].iloc[-1]), xytext=(6, 0),
                    textcoords="offset points", fontsize=9.5, weight="bold",
                    color=cor, va="center")

    ax.set_ylabel("% ao ano")
    estilo.grade_fina(ax, 2, 1)
    estilo.eixo_anual(ax, a_cada=2)
    ax.legend(ncol=2, frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.08))
