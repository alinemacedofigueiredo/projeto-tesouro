"""Quando a divida vence: as abas 3.4 (cronograma) e 3.1 (faixas).

Dois graficos. O cronograma e a foto de curto prazo -- os 60 meses que a 3.4
detalha, mais o balde "Apos 5 anos" que a Task 2 acrescentou ao parser. As faixas
sao a serie historica de quanto da DPF vence em cada horizonte, com a banda que o
PAF prometeu para o vincendo em doze meses.

ARMADILHA 1: os dois anos das pontas tem SEIS meses. A 3.4 detalha de jul/26 a
jun/31, entao a barra de 2026 e jul-dez e a de 2031 e jan-jun. Comparar 833,5 bi com
os 1.771,9 de 2027 sem saber disso e ler o grafico errado.

ARMADILHA 2: a aba do cronograma e a 3.4; a 3.1 e a de faixas. As duas falam de
vencimento e ja foram confundidas num rascunho.

ARMADILHA 3: a banda de vincendo em 12 meses vem de DUAS fontes. A aba 5.7 do anexo
de jun/26 termina em "PAF 2022"; o referencia/paf_bandas.csv alcanca 2026 e guarda o
indicador vincendo_12m_pct, que e opcional por ano justamente porque a 5.7 ja cobre o
passado. Onde os dois tem o mesmo ano, tem de dar a mesma banda -- e isso e teste,
nao confianca.
"""

import pandas as pd

from .. import config
from . import estilo

# Os dois anos das pontas do cronograma, que tem seis meses cada.
ANOS_PARCIAIS = (2026, 2031)

_ORDEM_GRUPOS = ["LFT", "LTN / NTN-F", "NTN-B", "NTN-C", "Demais"]

_CHAVE_COR = {"LFT": "LFT", "LTN / NTN-F": "LTN", "NTN-B": "NTN-B",
              "NTN-C": "NTN-C", "Demais": "Outros"}

# As tres faixas do meio viram uma so: "De 2 a 5 anos".
_DE_2_A_5 = ["De 2 a 3 anos", "De 3 a 4 anos", "De 4 a 5 anos"]

ORDEM_FAIXAS = ["At\u00e9 12 meses", "De 1 a 2 anos",
                "De 2 a 5 anos", "Acima de 5 anos"]

_COR_FAIXA = {"At\u00e9 12 meses": "#c00000",
              "De 1 a 2 anos": "#ed7d31",
              "De 2 a 5 anos": "#3d9be9",
              "Acima de 5 anos": "#1f3864"}


def _cronograma():
    d = pd.read_csv(config.PROCESSED_DIR / "cronograma_vencimentos.csv",
                    parse_dates=["data_referencia", "mes_vencimento"])
    if "faixa" not in d.columns:
        raise LookupError(
            "cronograma_vencimentos.csv nao tem a coluna 'faixa'. Ela vem da "
            "Task 2, que acrescentou o balde 'Apos 5 anos' ao parser; sem ela o "
            "grafico mostra 6.913,8 bi -- 78% do estoque -- como se fosse o todo."
        )
    return d


def dados_cronograma_anual():
    """Vencimentos por ano, mais a linha do balde, em R$ milhoes.

    O indice mistura inteiro (os anos) e texto (o balde) de proposito: o balde nao
    tem ano, e dar um a ele -- 2032, digamos -- seria inventar dado. Quem desenha
    trata a ultima posicao como categoria.
    """
    d = _cronograma()
    mensal = d[d["faixa"] == "mensal"].copy()
    mensal["ano"] = mensal["mes_vencimento"].dt.year
    piv = mensal.pivot_table(index="ano", columns="grupo_titulo",
                             values="valor_milhoes", aggfunc="sum").fillna(0.0)

    balde = (d[d["faixa"] == "apos_5_anos"]
             .groupby("grupo_titulo")["valor_milhoes"].sum())
    piv.loc["Ap\u00f3s 5 anos"] = balde

    return piv.fillna(0.0)[[g for g in _ORDEM_GRUPOS if g in piv.columns]]


def dados_cronograma_mensal():
    """Os 60 meses detalhados, em R$ milhoes. O balde nao entra: ele nao tem mes."""
    d = _cronograma()
    mensal = d[d["faixa"] == "mensal"]
    piv = mensal.pivot_table(index="mes_vencimento", columns="grupo_titulo",
                             values="valor_milhoes", aggfunc="sum").fillna(0.0)
    return piv[[g for g in _ORDEM_GRUPOS if g in piv.columns]]


def dados_faixas():
    """Composicao da DPF por horizonte de vencimento, em percentual.

    Quatro faixas: as tres do meio do CSV (2-3, 3-4 e 4-5 anos) viram uma so, porque
    a leitura util e "vence logo, vence em breve, vence no medio, vence longe".
    """
    v = pd.read_csv(config.PROCESSED_DIR / "vencimentos_faixa.csv",
                    parse_dates=["data"])
    dpf = v[v["nivel"] == "DPF"]
    piv = dpf.pivot_table(index="data", columns="faixa",
                          values="valor_milhoes", aggfunc="sum").fillna(0.0)
    piv["De 2 a 5 anos"] = piv[_DE_2_A_5].sum(axis=1)
    piv = piv[ORDEM_FAIXAS]

    # Os dez primeiros meses do bloco DPF (jan a out/2006) vem zerados: a serie so
    # comeca em nov/2006. Sem tirar, a divisao pelo total da 0/0 e a area empilhada
    # abre com dez meses somando zero por cento -- que se le como dado faltando.
    piv = piv[piv.sum(axis=1) > 0]

    return piv.div(piv.sum(axis=1), axis=0) * 100


def banda_da_57():
    """Banda do vincendo em 12 meses como a aba 5.7 do RMD a publica: 2003 a 2022.

    Onde ha revisao, vale a revisada -- a que estava em vigor no fechamento -- pelo
    mesmo criterio do modulo paf.
    """
    m = pd.read_csv(config.PROCESSED_DIR / "paf_metas.csv")
    d = m[m["indicador"] == "% Vincendo em 12 meses"]
    orig = d[d["versao"] == "original"].set_index("ano").sort_index()
    rev = d[d["versao"] == "revisado"].set_index("ano").sort_index()

    saida = orig[["minimo", "maximo", "realizado"]].copy()
    for ano in rev.index:
        saida.loc[ano, "minimo"] = rev.loc[ano, "minimo"]
        saida.loc[ano, "maximo"] = rev.loc[ano, "maximo"]
    return saida


def banda_vincendo_12m():
    """Banda do PAF para o vincendo em 12 meses, das duas fontes que a publicam.

    A aba 5.7 do RMD cobre 2003 a 2022 e vem por parser; o referencia/paf_bandas.csv
    e digitado a mao da planilha do PAF e cobre o que veio depois. As duas entram, e
    a de referencia PREVALECE onde as duas tem o ano -- ela e a fonte oficial, e e a
    que guarda oito revisoes contra as quatro da 5.7.

    Prevalecer nao e o mesmo que divergir em silencio: um teste confere que as duas
    dao a mesma banda em todo ano compartilhado. Se um dia divergirem, alguem
    descobre pelo teste, e nao por um grafico com a banda errada.
    """
    from . import paf

    saida = banda_da_57()[["minimo", "maximo"]]
    referencia = paf.bandas("vincendo_12m_pct")[["minimo", "maximo"]]
    for ano in referencia.index:
        saida.loc[ano, "minimo"] = referencia.loc[ano, "minimo"]
        saida.loc[ano, "maximo"] = referencia.loc[ano, "maximo"]
    return saida.sort_index()

def desenha_cronograma(anual, mensal, fig):
    """Painel anual com o balde, e o detalhe mensal embaixo.

    Os dois anos das pontas levam asterisco porque tem seis meses; sem a marca, a
    barra de 2026 parece um ano fraco em vez de meio ano.
    """
    a1, a2 = fig.subplots(2, 1, gridspec_kw={"height_ratios": [1, 1]})

    posicoes = range(len(anual))
    base = pd.Series(0.0, index=anual.index)
    for grupo in anual.columns:
        a1.bar(list(posicoes), anual[grupo] / 1000, bottom=base / 1000, width=0.7,
               color=estilo.COR[_CHAVE_COR[grupo]], label=grupo)
        base = base + anual[grupo]
    for x, total in zip(posicoes, base / 1000):
        a1.text(x, total + 40, estilo.num_br(total, 0), ha="center", fontsize=9)

    a1.set_xticks(list(posicoes))
    a1.set_xticklabels([f"{r}*" if r in ANOS_PARCIAIS else str(r)
                        for r in anual.index])
    a1.set_ylabel("R$ bilh\u00f5es")
    # Folga no topo, e a legenda na esquerda: a barra mais alta e a do balde,
    # na direita, e sem isso a legenda cobre o rotulo dela. Visto ao olhar a
    # figura, nao ao ler o codigo.
    a1.set_ylim(0, (base / 1000).max() * 1.16)
    a1.set_title("* 2026 \u00e9 jul\u2013dez e 2031 \u00e9 jan\u2013jun: a aba 3.4 detalha "
                 "60 meses a partir da data-base", fontsize=9, loc="left",
                 color=estilo.COR["neutro"])
    a1.legend(ncol=len(anual.columns), frameon=False, loc="upper left")
    a1.grid(axis="y", alpha=0.25)

    base = pd.Series(0.0, index=mensal.index)
    for grupo in mensal.columns:
        a2.bar(mensal.index, mensal[grupo] / 1000, bottom=base / 1000, width=22,
               color=estilo.COR[_CHAVE_COR[grupo]])
        base = base + mensal[grupo]

    for ano in range(mensal.index.min().year + 1, mensal.index.max().year + 1):
        a2.axvline(pd.Timestamp(year=ano, month=1, day=1), color="gray",
                   lw=0.8, ls="--")

    marcas = [d for d in mensal.index if d.month in (1, 4, 7, 10)]
    a2.set_xticks(marcas)
    a2.set_xticklabels([estilo.rotulo_mes(d) for d in marcas], fontsize=8)
    a2.set_ylabel("R$ bilh\u00f5es por m\u00eas")
    a2.grid(axis="y", alpha=0.25)


def desenha_faixas(dados, banda, fig):
    """Area empilhada de 100% em cima, e o vincendo em 12 meses com a banda embaixo.

    A banda vai no painel de baixo, sozinha: por cima da area de 100% ela e a area
    disputariam o mesmo espaco e nenhuma das duas seria legivel.

    Onde nao ha banda -- de 2023 em diante -- nada e desenhado. Esticar o ultimo
    retangulo ate hoje inventaria uma meta que o PAF nao publicou nesta aba.
    """
    a1, a2 = fig.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": [2, 1]})

    a1.stackplot(dados.index, [dados[f] for f in ORDEM_FAIXAS],
                 labels=ORDEM_FAIXAS,
                 colors=[_COR_FAIXA[f] for f in ORDEM_FAIXAS], alpha=0.9)
    a1.set_ylim(0, 100)
    a1.set_ylabel("% da DPF")
    a1.legend(ncol=4, frameon=False, loc="lower center")

    curto = dados["At\u00e9 12 meses"]
    for ano in range(dados.index.min().year, dados.index.max().year + 1):
        if ano not in banda.index:
            continue
        a2.fill_between([pd.Timestamp(year=ano, month=1, day=1),
                         pd.Timestamp(year=ano, month=12, day=31)],
                        banda.loc[ano, "minimo"], banda.loc[ano, "maximo"],
                        color=estilo.COR["banda"], alpha=0.15, linewidth=0)
    a2.plot(curto.index, curto, color=_COR_FAIXA["At\u00e9 12 meses"], lw=2.2)
    a2.annotate(estilo.num_br(curto.iloc[-1], 1),
                xy=(curto.index[-1], curto.iloc[-1]), xytext=(6, 0),
                textcoords="offset points", fontsize=9, weight="bold",
                color=_COR_FAIXA["At\u00e9 12 meses"], va="center")
    a2.set_ylabel("% vincendo em 12 meses")
    a2.set_title("banda do PAF publicada na aba 5.7 at\u00e9 2022", fontsize=9,
                 loc="left", color=estilo.COR["neutro"])
    estilo.grade_fina(a2, 10, 5)
    estilo.eixo_anual(a2, a_cada=2)


# A aba 2.2 traz nove nomes de titulo. Eles viram seis familias, e a NTN-B1 fica
# SEPARADA da NTN-B de proposito: tudo que vence depois de 2060 e NTN-B1 RendA+, e
# juntar as duas apagaria a cauda inteira do grafico.
_FAMILIA = {"LFT": "LFT",
            "LFT-TD1 Reserva": "LFT",
            "LTN": "LTN",
            "NTN-B": "NTN-B",
            "NTN-B Principal": "NTN-B",
            "NTN-B1 EducA+": "NTN-B1",
            "NTN-B1 RendA+": "NTN-B1",
            "NTN-C": "NTN-C",
            "NTN-F": "NTN-F"}

ORDEM_FAMILIAS = ["LFT", "LTN", "NTN-F", "NTN-B", "NTN-B1", "NTN-C"]

_COR_FAMILIA = {"LFT": "LFT", "LTN": "LTN", "NTN-F": "NTN-F",
                "NTN-B": "NTN-B", "NTN-B1": "NTN-C", "NTN-C": "Outros"}


def dados_perfil_completo():
    """Vencimentos por ano ate 2084, por familia de titulo, em R$ milhoes.

    Vem da aba 2.2, papel a papel -- diferente do cronograma, que vem da 3.4 e para
    em 60 meses. Os dois nao fecham: 8.904,1 aqui contra 8.920,7 la, 16,6 bi de
    diferenca cuja causa esta em aberto e travada por teste.

    ARMADILHA: papeis ja vencidos ficam no CSV com financeiro zero e ano de
    vencimento no passado. Sem filtrar, o eixo comeca em 2010 com quatorze anos
    vazios.
    """
    e = pd.read_csv(config.PROCESSED_DIR / "estoque_titulos_vencimento.csv",
                    parse_dates=["data", "vencimento"])
    u = e[(e["data"] == e["data"].max()) & (e["financeiro_milhoes"] > 0)].copy()
    u["ano"] = u["vencimento"].dt.year
    u["familia"] = [_FAMILIA[t] for t in u["titulo"]]

    piv = u.pivot_table(index="ano", columns="familia",
                        values="financeiro_milhoes", aggfunc="sum").fillna(0.0)
    for familia in ORDEM_FAMILIAS:
        if familia not in piv.columns:
            piv[familia] = 0.0
    return piv[ORDEM_FAMILIAS]


def desenha_perfil_completo(dados, ax):
    """Barras empilhadas por ano, do proximo ao ultimo.

    O eixo do tempo e categorico e nao continuo: entre 2060 e 2084 ha quatro anos
    com divida e vinte sem, e um eixo continuo gastaria metade da largura com
    espaco vazio.
    """
    posicoes = range(len(dados))
    base = pd.Series(0.0, index=dados.index)
    for familia in dados.columns:
        ax.bar(list(posicoes), dados[familia] / 1000, bottom=base / 1000,
               width=0.78, color=estilo.COR[_COR_FAMILIA[familia]], label=familia)
        base = base + dados[familia]

    ax.set_xticks(list(posicoes))
    ax.set_xticklabels([str(a) for a in dados.index], rotation=90, fontsize=8)
    ax.set_ylabel("R$ bilh\u00f5es a vencer")
    ax.legend(ncol=6, frameon=False, loc="upper right")
    ax.grid(axis="y", alpha=0.25)
