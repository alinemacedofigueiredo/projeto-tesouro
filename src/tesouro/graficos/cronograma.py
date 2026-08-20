"""O desenho da pagina de agenda: DV ofertado contra DV aceito, por familia.

O QUE HAVIA ANTES, e por que saiu. A primeira versao desta pagina tinha tres
graficos -- um cronograma de pontos por vertice, um de DV01 por titulo e um de "DV
do dia se ele repetir a ultima oferta". Os tres foram recusados na revisao, e com
razao: o cronograma repetia o que a tabela ja dizia melhor, o DV por titulo era uma
propriedade do instrumento sem nada de agenda nele, e o terceiro multiplicava por
uma quantidade do passado para produzir um numero que ninguem ia usar.

O QUE ENTROU NO LUGAR responde uma pergunta que nenhuma outra pagina responde: ele
nao conseguiu colocar, ou nao quis?

Barras lado a lado, por familia de papel: o DV que ele OFERTOU e o que ACEITOU no
ultimo leilao de cada uma. Medido no agregado do historico, o Tesouro coloca 68,5%
do DV que oferta -- e a razao varia muito de leilao para leilao.

"ULTIMO LEILAO DAQUELA FAMILIA", e nao ultimo dia: LFT e NTN-B vao a mercado num dia
e o prefixado no outro, entao um corte por data deixaria metade das familias sem
barra. Cada uma tem o seu calendario, e a data de cada uma aparece no eixo.

A LFT NAO ENTRA: sem DV por decisao de modelagem da entrega 2, duas barras zeradas
ao lado das outras se leriam como "nao colocou nada".
"""
from . import estilo

# A mesma paleta do resto do projeto: familia do papel.
_COR_FAMILIA = {"LFT": "LFT", "LTN": "LTN", "NTN-F": "NTN-F",
                "NTN-B curta": "NTN-B", "NTN-B longa": "NTN-C"}

ORDEM_FAMILIAS = ["LTN", "NTN-F", "NTN-B curta", "NTN-B longa"]

# A barra do ofertado e a mesma cor do papel, mas vazada: e o TETO, e o aceito e o
# que coube dentro dele. Duas cores diferentes fariam parecer duas grandezas.
OPACIDADE_DO_OFERTADO = 0.28


def _cor(familia):
    return estilo.COR[_COR_FAMILIA.get(familia, "Outros")]


def desenha_ofertado_e_aceito(dados, ax, quantos_atras=0):
    """Barras lado a lado: DV ofertado e DV aceito, por familia.

    'quantos_atras' escolhe qual leilao mostrar -- 0 e o ultimo de cada familia.
    """
    from matplotlib.colors import to_rgba

    d = dados[(dados["quantos_atras"] == quantos_atras)
              & dados["familia"].isin(ORDEM_FAMILIAS)]
    if d.empty:
        ax.set_axis_off()
        ax.text(0.5, 0.5, "sem leil\u00e3o no hist\u00f3rico para comparar",
                ha="center", va="center", transform=ax.transAxes)
        return
    ordem = [f for f in ORDEM_FAMILIAS if f in set(d["familia"])]
    d = d.set_index("familia").reindex(ordem)

    posicoes = list(range(len(d)))
    largura = 0.38
    cores = [_cor(f) for f in d.index]

    ax.bar([p - largura / 2 for p in posicoes], d["dv_ofertado"] * 1000,
           width=largura, label="ofertado",
           color=[to_rgba(c, OPACIDADE_DO_OFERTADO) for c in cores],
           edgecolor=cores, linewidth=1.6)
    ax.bar([p + largura / 2 for p in posicoes], d["dv_aceito"] * 1000,
           width=largura, label="aceito", color=cores)

    # O rotulo do eixo traz a DATA de cada familia, porque elas nao coincidem: LFT e
    # NTN-B num dia, prefixado no outro. Sem a data, quatro barras de dias
    # diferentes pareceriam do mesmo leilao.
    ax.set_xticks(posicoes)
    ax.set_xticklabels([f"{f}\n{r['data_leilao']:%d/%m}"
                        for f, r in d.iterrows()], fontsize=9)

    ax.set_ylabel("DV01, R$ mil por ponto-base")
    ax.axhline(0, color="gray", lw=0.8)
    _grade(ax)
    ax.set_title("Quanto risco ele tentou colocar, e quanto colocou",
                 fontsize=11, weight="bold", loc="left", pad=10)

    _rotula(ax, posicoes, d, largura)
    ax.legend(ncol=2, frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.18))


def _rotula(ax, posicoes, d, largura):
    """O numero em cima de cada barra, e a fracao colocada entre as duas.

    A FRACAO E O QUE SE QUER LER -- "colocou 59% do risco que ofertou" -- e ela nao
    aparece em barra nenhuma: e a razao entre as duas. Sai em vermelho quando fica
    abaixo de 95%, que e onde deixa de ser arredondamento e vira decisao.
    """
    teto = 0.0
    for p, (_, r) in zip(posicoes, d.iterrows()):
        ofertado = r["dv_ofertado"] * 1000
        aceito = r["dv_aceito"] * 1000
        teto = max(teto, ofertado, aceito)
        for x, v in ((p - largura / 2, ofertado), (p + largura / 2, aceito)):
            ax.annotate(estilo.num_br(v, 0), (x, v), textcoords="offset points",
                        xytext=(0, 4 if v >= 0 else -12), ha="center",
                        fontsize=8.5, color="#333333")
        if ofertado:
            fracao = aceito / ofertado
            ax.annotate(f"{estilo.num_br(fracao * 100, 0)}%",
                        (p, max(ofertado, aceito)), textcoords="offset points",
                        xytext=(0, 20), ha="center", fontsize=10, weight="bold",
                        color="#333333" if fracao > 0.95 else "#c00000")
    # Folga no topo para o rotulo da fracao caber dentro da figura.
    if teto:
        ax.set_ylim(min(0.0, ax.get_ylim()[0]), teto * 1.22)


def _grade(ax):
    """Grade densa: linha forte na marca, fraca no meio."""
    from matplotlib.ticker import AutoMinorLocator

    ax.yaxis.set_minor_locator(AutoMinorLocator(2))
    ax.grid(axis="y", which="major", alpha=0.28, lw=0.8)
    ax.grid(axis="y", which="minor", alpha=0.14, lw=0.6)
