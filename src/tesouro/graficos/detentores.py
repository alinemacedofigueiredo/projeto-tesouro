"""Quem carrega a divida: as abas 2.7 e 2.8.

Tres graficos. A participacao relativa de cada grupo e o quanto ela mudou em doze
meses (2.7); quem compra cada papel (2.8); e o financeiro de cada detentor ao longo
do tempo, em oito paineis (2.8).

As duas abas NAO se cruzam por nome. A 2.7 grava "Nao-residentes 4", com o numero da
nota de rodape colado; a 2.8 grava "Nao-residente", singular e sem nota. Alem disso
a 2.7 comeca em jan/2007 e a 2.8 em fev/2011. Sao duas fontes vizinhas, nao a mesma.

A divergencia de 12 meses contra o slide do RMD e conhecida: o nosso dado foi
conferido contra a celula crua da aba 2.7 e esta fiel ao anexo, e a origem do numero
do slide e desconhecida. Documentada, nao perseguida (ver a spec, secao 10).
"""

import re

import pandas as pd

from .. import config
from . import estilo

JANELAS = {"5 anos": 5, "completa": None}

# Aba 2.7, agrupada em cinco: os quatro grandes, e o resto junto.
ORDEM_GRUPOS = ["Inst. Financeiras", "Fundos", "Previd\u00eancia",
                "N\u00e3o-residentes", "Demais Grupos"]

_GRUPO_DE = {"Institui\u00e7\u00f5es Financeiras": "Inst. Financeiras",
             "Fundos de Investimento": "Fundos",
             "Previd\u00eancia": "Previd\u00eancia",
             "N\u00e3o-residentes": "N\u00e3o-residentes"}

# Do rotulo que aparece na tela para a chave da paleta, que e ASCII.
CHAVE_COR = {"Inst. Financeiras": "Inst. Financeiras",
             "Fundos": "Fundos",
             "Previd\u00eancia": "Previdencia",
             "N\u00e3o-residentes": "Nao-residente",
             "N\u00e3o-residente": "Nao-residente",
             "Demais Grupos": "Demais Grupos",
             "Governo": "Governo",
             "Seguradoras": "Seguradoras",
             "Tesouro Direto": "Tesouro Direto",
             "Outros": "Outros Detentores"}


def _sem_nota(nome):
    """'Instituicoes Financeiras 1' -> 'Instituicoes Financeiras'.

    A aba 2.7 cola o numero da nota de rodape no nome do detentor. Sem tirar, o
    rotulo do grafico sai com o digito e nenhum agrupamento por nome funciona.
    """
    return re.sub(r"\s*\d+$", "", str(nome)).strip()


def dados_participacao():
    """Participacao dos cinco grupos hoje e ha doze meses, e a variacao em p.p."""
    d = pd.read_csv(config.PROCESSED_DIR / "detentores.csv", parse_dates=["data"])
    d["grupo"] = [_GRUPO_DE.get(_sem_nota(n), "Demais Grupos") for n in d["detentor"]]

    piv = d.pivot_table(index="data", columns="grupo",
                        values="valor_milhoes", aggfunc="sum").fillna(0.0)
    share = piv.div(piv.sum(axis=1), axis=0) * 100

    hoje = share.index.max()
    ha12m = hoje - pd.DateOffset(months=12)
    if ha12m not in share.index:
        raise LookupError(
            f"detentores.csv nao tem o mes de {ha12m.date()}, doze meses antes do "
            f"ultimo ({hoje.date()}). A variacao de 12 meses e o segundo painel do "
            f"grafico e nao pode ser calculada contra um mes vizinho em silencio."
        )

    saida = pd.DataFrame(index=ORDEM_GRUPOS)
    saida["hoje_pct"] = share.loc[hoje]
    saida["ha12m_pct"] = share.loc[ha12m]
    saida["var_pp"] = saida["hoje_pct"] - saida["ha12m_pct"]
    saida["valor_milhoes"] = piv.loc[hoje]
    return saida


def dados_por_papel():
    """Participacao de cada detentor dentro de cada papel, em percentual."""
    d = pd.read_csv(config.PROCESSED_DIR / "detentores_por_titulo.csv",
                    parse_dates=["data"])
    u = d[d["data"] == d["data"].max()]
    piv = u.pivot_table(index="titulo", columns="detentor",
                        values="valor_milhoes", aggfunc="sum").fillna(0.0)
    return piv.div(piv.sum(axis=1), axis=0) * 100


def dados_financeiro(janela=None):
    """Financeiro de cada detentor por mes, em R$ milhoes."""
    d = pd.read_csv(config.PROCESSED_DIR / "detentores_por_titulo.csv",
                    parse_dates=["data"])
    piv = d.pivot_table(index="data", columns="detentor",
                        values="valor_milhoes", aggfunc="sum").fillna(0.0)
    return estilo.recorta(piv, janela)


def ordem_paineis(dados):
    """Os oito detentores por tamanho, com o Tesouro Direto forcado para o fim.

    Ordem de importancia, decisao da usuaria: o Tesouro Direto e o menor em
    relevancia para a gestao mesmo tendo mais financeiro que o Governo.
    """
    ultimo = dados.iloc[-1].drop("Tesouro Direto").sort_values(ascending=False)
    return list(ultimo.index) + ["Tesouro Direto"]

def desenha_participacao(dados, fig):
    """Dois paineis: a participacao de hoje, e a variacao em doze meses."""
    a1, a2 = fig.subplots(1, 2, gridspec_kw={"width_ratios": [2, 1]})

    y = range(len(dados))
    a1.barh(list(y), dados["hoje_pct"],
            color=[estilo.COR[CHAVE_COR[g]] for g in dados.index])
    for i, (g, v) in enumerate(dados["hoje_pct"].items()):
        a1.text(v + 0.4, i, estilo.num_br(v, 1) + "%", va="center", fontsize=9.5)
    a1.set_yticks(list(y))
    a1.set_yticklabels(list(dados.index))
    a1.invert_yaxis()
    a1.set_xlim(0, max(dados["hoje_pct"]) * 1.18)
    a1.set_xlabel("% do estoque em poder do p\u00fablico")
    a1.grid(axis="x", alpha=0.20)

    cores = ["#2ca02c" if v >= 0 else "#d62728" for v in dados["var_pp"]]
    a2.barh(list(y), dados["var_pp"], color=cores, alpha=0.85)
    for i, v in enumerate(dados["var_pp"]):
        desloca = 0.02 if v >= 0 else -0.02
        a2.text(v + desloca, i, estilo.num_br(v, 2), va="center",
                ha="left" if v >= 0 else "right", fontsize=9)
    a2.set_yticks(list(y))
    a2.set_yticklabels([])
    a2.invert_yaxis()
    a2.axvline(0, color="gray", lw=0.8)
    a2.set_xlabel("varia\u00e7\u00e3o em 12 meses (p.p.)")
    a2.grid(axis="x", alpha=0.20)


def desenha_por_papel(dados, fig):
    """Uma rosca por papel, com rotulo so nas fatias de 10% ou mais.

    Abaixo de 10% o numero nao cabe dentro da fatia e vira sujeira -- decisao da
    usuaria depois de ver a versao com todos os rotulos.
    """
    eixos = fig.subplots(1, len(dados.index))
    for ax, papel in zip(eixos, dados.index):
        linha = dados.loc[papel]
        linha = linha[linha > 0]
        ax.pie(linha, startangle=90, counterclock=False,
               colors=[estilo.COR[CHAVE_COR[d]] for d in linha.index],
               wedgeprops={"width": 0.42, "edgecolor": "white", "linewidth": 0.8},
               labels=None,
               autopct=lambda p: estilo.num_br(p, 1) if p >= 10 else "",
               pctdistance=0.79, textprops={"fontsize": 8.5})
        ax.set_title(papel, fontsize=11, weight="bold")

    marcas = [plt_patch(estilo.COR[CHAVE_COR[d]], d) for d in dados.columns]
    fig.legend(handles=marcas, ncol=4, frameon=False, loc="lower center")


def plt_patch(cor, rotulo):
    """Retangulo colorido para a legenda comum das cinco roscas."""
    from matplotlib.patches import Patch
    return Patch(facecolor=cor, label=rotulo)


def desenha_financeiro(dados, fig):
    """Oito paineis, cada um com escala propria.

    Escala comum achataria sete dos oito: as Instituicoes Financeiras tem
    onze vezes o financeiro do Governo. O preco e que os paineis nao sao
    comparaveis entre si a olho, e por isso cada um leva o valor do ultimo mes
    escrito.
    """
    eixos = fig.subplots(2, 4, sharex=True)
    for ax, detentor in zip(eixos.ravel(), ordem_paineis(dados)):
        serie = dados[detentor] / 1000
        cor = estilo.COR[CHAVE_COR[detentor]]
        ax.fill_between(serie.index, serie, 0, color=cor, alpha=0.30)
        ax.plot(serie.index, serie, color=cor, lw=1.8)
        ax.set_title(detentor, fontsize=10, weight="bold")
        ax.set_ylim(0, serie.max() * 1.22)
        ax.text(0.03, 0.90, estilo.num_br(serie.iloc[-1], 0) + " bi",
                transform=ax.transAxes, fontsize=9.5, color=cor, weight="bold")
        ax.grid(axis="y", alpha=0.20)
        estilo.eixo_anual(ax, a_cada=3)
