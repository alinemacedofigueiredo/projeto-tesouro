"""O desenho da p\u00e1gina de agenda: ofertado contra aceito, nos \u00faltimos leil\u00f5es.

O QUE HAVIA ANTES, e por que saiu. A primeira vers\u00e3o desta p\u00e1gina tinha tr\u00eas
gr\u00e1ficos -- um cronograma de pontos por v\u00e9rtice, um de DV01 por t\u00edtulo e um de "DV
do dia se ele repetir a \u00faltima oferta". Os tr\u00eas foram recusados na revis\u00e3o, e com
raz\u00e3o: o cronograma repetia o que a tabela j\u00e1 dizia melhor, o DV por t\u00edtulo era uma
propriedade do instrumento sem nada de agenda nele, e o terceiro multiplicava por
uma quantidade do passado para produzir um n\u00famero que ningu\u00e9m ia usar.

O QUE ENTROU NO LUGAR responde uma pergunta que nenhuma outra p\u00e1gina responde: ele
n\u00e3o conseguiu colocar, ou n\u00e3o quis?

BARRAS HORIZONTAIS, e n\u00e3o verticais. A primeira vers\u00e3o mostrava s\u00f3 o \u00faltimo leil\u00e3o
de cada fam\u00edlia e cabia em p\u00e9. Com seis leil\u00f5es por fam\u00edlia s\u00e3o vinte e quatro
grupos, e em p\u00e9 as datas viram etiqueta girada e ileg\u00edvel -- deitado, cada data \u00e9 um
r\u00f3tulo de linha que se l\u00ea sem esfor\u00e7o. A linha pontilhada separa uma fam\u00edlia da
outra.

"\u00daLTIMOS SEIS DAQUELA FAM\u00cdLIA", e n\u00e3o \u00faltimos seis dias: LFT e NTN-B v\u00e3o a mercado
num dia e o prefixado no outro, ent\u00e3o um corte por data deixaria metade das fam\u00edlias
sem barra. Cada uma tem o seu calend\u00e1rio, e a data de cada uma est\u00e1 no r\u00f3tulo.

A LFT TEM GR\u00c1FICO PR\u00d3PRIO, em quantidade: ela n\u00e3o tem DV por decis\u00e3o de modelagem da
entrega 2, e barras zeradas ao lado das outras se leriam como "n\u00e3o colocou nada".
"""
from . import estilo

# A mesma paleta do resto do projeto: fam\u00edlia do papel.
_COR_FAMILIA = {"LFT": "LFT", "LTN": "LTN", "NTN-F": "NTN-F",
                "NTN-B curta": "NTN-B", "NTN-B longa": "NTN-C"}

ORDEM_FAMILIAS = ["LTN", "NTN-F", "NTN-B curta", "NTN-B longa"]

# A barra do ofertado \u00e9 a mesma cor do papel, mas vazada: \u00e9 o TETO, e o aceito \u00e9 o
# que coube dentro dele. Duas cores diferentes fariam parecer duas grandezas.
OPACIDADE_DO_OFERTADO = 0.28

# Abaixo disto a fra\u00e7\u00e3o colocada sai em vermelho: deixa de ser arredondamento e
# vira decis\u00e3o.
LIMIAR_DO_ALERTA = 0.95


def _cor(familia):
    return estilo.COR[_COR_FAMILIA.get(familia, "Outros")]


def _prepara(dados, familias, quantos):
    """As linhas a desenhar, da mais recente para a mais antiga, por fam\u00edlia."""
    d = dados[dados["familia"].isin(familias) & (dados["quantos_atras"] < quantos)]
    if d.empty:
        return d, []
    blocos, limites = [], []
    for familia in familias:
        g = d[d["familia"] == familia].sort_values("quantos_atras")
        if g.empty:
            continue
        blocos.append(g)
        limites.append(len(g))
    if not blocos:
        return d.iloc[0:0], []
    import pandas as pd
    return pd.concat(blocos, ignore_index=True), limites


def _separadores(ax, limites):
    """Linha pontilhada entre uma fam\u00edlia e a seguinte.

    Sem ela, vinte e quatro barras deitadas viram um bloco s\u00f3 e n\u00e3o se v\u00ea onde uma
    fam\u00edlia termina e a outra come\u00e7a.
    """
    posicao = 0
    for tamanho in limites[:-1]:
        posicao += tamanho
        ax.axhline(posicao - 0.5, color="#999999", lw=0.9, ls=":", zorder=1)


def _rotulos_das_linhas(d):
    """O nome da fam\u00edlia s\u00f3 na primeira linha dela; a data em todas.

    Repetir "NTN-B longa" seis vezes empilhadas \u00e9 ru\u00eddo: o nome marca o bloco, e a
    data identifica a linha.
    """
    rotulos, anterior = [], None
    for _, r in d.iterrows():
        familia = r["familia"]
        nome = familia if familia != anterior else ""
        anterior = familia
        data = f"{r['data_leilao']:%d/%m}"
        rotulos.append(f"{nome}  {data}" if nome else f"{'':12s}{data}")
    return rotulos


def desenha_ofertado_e_aceito(dados, ax, quantos=6, familias=None):
    """Barras deitadas: DV ofertado e DV aceito, \u00faltimos N leil\u00f5es de cada fam\u00edlia."""
    from matplotlib.colors import to_rgba

    familias = familias or [f for f in ORDEM_FAMILIAS
                            if f in set(dados["familia"])]
    d, limites = _prepara(dados, familias, quantos)
    if d.empty:
        ax.set_axis_off()
        ax.text(0.5, 0.5, "sem leil\u00e3o no hist\u00f3rico para comparar",
                ha="center", va="center", transform=ax.transAxes)
        return

    posicoes = list(range(len(d)))
    altura = 0.38
    cores = [_cor(f) for f in d["familia"]]

    ax.barh([p - altura / 2 for p in posicoes], d["dv_ofertado"] * 1000,
            height=altura, label="ofertado",
            color=[to_rgba(c, OPACIDADE_DO_OFERTADO) for c in cores],
            edgecolor=cores, linewidth=1.4, zorder=3)
    ax.barh([p + altura / 2 for p in posicoes], d["dv_aceito"] * 1000,
            height=altura, label="aceito", color=cores, zorder=3)

    ax.set_yticks(posicoes)
    ax.set_yticklabels(_rotulos_das_linhas(d), fontsize=8.5,
                       fontfamily="monospace")
    ax.invert_yaxis()
    _separadores(ax, limites)

    ax.set_xlabel("DV01, R$ mil por ponto-base")
    ax.axvline(0, color="gray", lw=0.8)
    _grade(ax)
    ax.set_title("Quanto risco ele tentou colocar, e quanto colocou",
                 fontsize=11, weight="bold", loc="left", pad=10)

    _rotula(ax, posicoes, d, altura, "dv_ofertado", "dv_aceito", 1000,
            lambda v: estilo.num_br(v, 0))
    ax.legend(ncol=2, frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.06))


def desenha_quantidade_lft(dados, ax, quantos=4):
    """A LFT em QUANTIDADE, com o financeiro escrito no topo da barra.

    Ela n\u00e3o tem DV por decis\u00e3o de modelagem, ent\u00e3o a compara\u00e7\u00e3o ofertado/aceito s\u00f3
    existe em t\u00edtulos. O financeiro entra como r\u00f3tulo porque \u00e9 a grandeza que se
    compara com o resto do projeto -- e como a LFT \u00e9 mais da metade da emiss\u00e3o, o
    n\u00famero importa mesmo sem DV.
    """
    from matplotlib.colors import to_rgba

    d, limites = _prepara(dados, ["LFT"], quantos)
    if d.empty:
        ax.set_axis_off()
        ax.text(0.5, 0.5, "sem leil\u00e3o de LFT no hist\u00f3rico",
                ha="center", va="center", transform=ax.transAxes)
        return

    posicoes = list(range(len(d)))
    altura = 0.38
    cor = _cor("LFT")

    ax.barh([p - altura / 2 for p in posicoes], d["qtd_ofertada"] / 1000,
            height=altura, label="ofertado",
            color=to_rgba(cor, OPACIDADE_DO_OFERTADO),
            edgecolor=cor, linewidth=1.4, zorder=3)
    ax.barh([p + altura / 2 for p in posicoes], d["qtd_aceita"] / 1000,
            height=altura, label="aceito", color=cor, zorder=3)

    ax.set_yticks(posicoes)
    ax.set_yticklabels([f"{r['data_leilao']:%d/%m/%y}" for _, r in d.iterrows()],
                       fontsize=9)
    ax.invert_yaxis()

    ax.set_xlabel("milhares de t\u00edtulos")
    ax.axvline(0, color="gray", lw=0.8)
    _grade(ax)
    ax.set_title("LFT \u00b7 ofertado e aceito em t\u00edtulos, com o financeiro aceito",
                 fontsize=11, weight="bold", loc="left", pad=10)

    _rotula(ax, posicoes, d, altura, "qtd_ofertada", "qtd_aceita", 0.001,
            lambda v: estilo.num_br(v, 0),
            financeiro=d["financeiro_milhoes"])
    ax.legend(ncol=2, frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.14))


def _rotula(ax, posicoes, d, altura, coluna_ofertado, coluna_aceito, escala,
            formato, financeiro=None):
    """O n\u00famero na ponta de cada barra, e a fra\u00e7\u00e3o colocada ao lado do par.

    A FRA\u00c7\u00c3O \u00c9 O QUE SE QUER LER -- "colocou 59% do que ofertou" -- e ela n\u00e3o aparece
    em barra nenhuma: \u00e9 a raz\u00e3o entre as duas.

    'financeiro', quando vem, \u00e9 escrito no topo do par. \u00c9 o caso da LFT, cuja
    compara\u00e7\u00e3o \u00e9 em t\u00edtulos mas cuja grandeza compar\u00e1vel com o resto do projeto \u00e9 o
    dinheiro.
    """
    # A fracao sai numa COLUNA FIXA, e nao ao lado da barra de cada linha: presa a
    # barra, ela pula de lugar a cada linha e as vinte e quatro fracoes deixam de
    # poder ser lidas de cima a baixo. Aqui todas comecam no mesmo x.
    maior = 0.0
    for _, r in d.iterrows():
        maior = max(maior, r[coluna_ofertado] * escala, r[coluna_aceito] * escala)
    folga = 1.55 if financeiro is not None else 1.32
    coluna_da_fracao = maior * (1.16 if financeiro is None else 1.14)

    for k, (p, (_, r)) in enumerate(zip(posicoes, d.iterrows())):
        ofertado = r[coluna_ofertado] * escala
        aceito = r[coluna_aceito] * escala
        for y, v in ((p - altura / 2, ofertado), (p + altura / 2, aceito)):
            ax.annotate(formato(v), (v, y), textcoords="offset points",
                        xytext=(4, 0), va="center", ha="left",
                        fontsize=8, color="#333333")
        if not ofertado:
            continue
        fracao = aceito / ofertado
        texto = f"{estilo.num_br(fracao * 100, 0)}%"
        if financeiro is not None:
            texto += f"  \u00b7  R$ {estilo.num_br(financeiro.iloc[k] / 1000, 2)} bi"
        ax.annotate(texto, (coluna_da_fracao, p), va="center", ha="left",
                    fontsize=9, weight="bold",
                    color="#333333" if fracao > LIMIAR_DO_ALERTA else "#c00000")

    if maior:
        ax.set_xlim(min(0.0, ax.get_xlim()[0]), maior * folga)


def _grade(ax):
    """Grade densa no eixo do valor: linha forte na marca, fraca no meio."""
    from matplotlib.ticker import AutoMinorLocator

    ax.xaxis.set_minor_locator(AutoMinorLocator(2))
    ax.grid(axis="x", which="major", alpha=0.28, lw=0.8)
    ax.grid(axis="x", which="minor", alpha=0.14, lw=0.6)
    ax.set_axisbelow(True)
