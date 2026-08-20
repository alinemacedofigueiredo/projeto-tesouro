"""O desenho da p\u00e1gina de agenda: ofertado contra aceito, nos \u00faltimos preg\u00f5es.

O QUE HAVIA ANTES, e por que saiu. A primeira vers\u00e3o desta p\u00e1gina tinha tr\u00eas
gr\u00e1ficos -- um cronograma de pontos por v\u00e9rtice, um de DV01 por t\u00edtulo e um de "DV
do dia se ele repetir a \u00faltima oferta". Os tr\u00eas foram recusados na revis\u00e3o, e com
raz\u00e3o: o cronograma repetia o que a tabela j\u00e1 dizia melhor, o DV por t\u00edtulo era uma
propriedade do instrumento sem nada de agenda nele, e o terceiro multiplicava por
uma quantidade do passado para produzir um n\u00famero que ningu\u00e9m ia usar.

O QUE ENTROU NO LUGAR responde uma pergunta que nenhuma outra p\u00e1gina responde: ele
n\u00e3o conseguiu colocar, ou n\u00e3o quis?

POR DIA DE PREG\u00c3O, e n\u00e3o "seis de cada papel". A segunda vers\u00e3o contava por fam\u00edlia
e produzia vinte e quatro linhas cobrindo per\u00edodos diferentes em cada bloco -- de
14/07 a 20/08 no prefixado e de 14/07 a 18/08 na NTN-B. N\u00e3o dava para somar o dia,
que \u00e9 justamente a leitura que interessa: quanto risco entrou no mercado NAQUELE
preg\u00e3o. Agora cada linha \u00e9 um preg\u00e3o, e a barra \u00e9 a soma dele.

A BARRA \u00c9 EMPILHADA POR PAPEL, para que a soma do dia n\u00e3o apague a composi\u00e7\u00e3o: num
dia de prefixado a LTN e a NTN-F somam, e saber qual das duas pesou \u00e9 metade da
leitura.

BARRAS DEITADAS porque a data \u00e9 o r\u00f3tulo, e data em p\u00e9 vira etiqueta girada.

A LFT TEM GR\u00c1FICO PR\u00d3PRIO, em quantidade: ela n\u00e3o tem DV por decis\u00e3o de modelagem da
entrega 2, e uma barra zerada dentro da pilha n\u00e3o se distingue de aus\u00eancia.
"""
from . import estilo

# A mesma paleta do resto do projeto: fam\u00edlia do papel.
_COR_FAMILIA = {"LFT": "LFT", "LTN": "LTN", "NTN-F": "NTN-F",
                "NTN-B curta": "NTN-B", "NTN-B longa": "NTN-C"}

# A ordem em que os pap\u00e9is empilham: do mais curto para o mais longo, que \u00e9 a ordem
# em que acrescentam risco.
ORDEM_FAMILIAS = ["LFT", "LTN", "NTN-F", "NTN-B curta", "NTN-B longa"]

# Os que entram no gr\u00e1fico de DV. A LFT fica de fora: sem DV01, a fatia dela seria
# sempre zero e uma fatia de espessura zero n\u00e3o se distingue de aus\u00eancia.
FAMILIAS_COM_DV = ["LTN", "NTN-F", "NTN-B curta", "NTN-B longa"]

# A barra do ofertado \u00e9 a mesma cor do papel, mas vazada: \u00e9 o TETO, e o aceito \u00e9 o
# que coube dentro dele. Duas cores diferentes fariam parecer duas grandezas.
OPACIDADE_DO_OFERTADO = 0.28

# Abaixo disto a fra\u00e7\u00e3o colocada sai em vermelho: deixa de ser arredondamento e
# vira decis\u00e3o.
LIMIAR_DO_ALERTA = 0.95


def _cor(familia):
    return estilo.COR[_COR_FAMILIA.get(familia, "Outros")]


def _pilha(d, dias, familias, coluna):
    """Uma matriz {fam\u00edlia: [valor por dia]}, na ordem dos dias pedida."""
    tabela = {}
    for familia in familias:
        g = d[d["familia"] == familia].set_index("data_leilao")[coluna]
        tabela[familia] = [float(g.get(dia, 0.0)) for dia in dias]
    return tabela


def desenha_ofertado_e_aceito(dados, ax, quantos=6):
    """Barras deitadas por PREG\u00c3O: DV ofertado e aceito, empilhados por papel.

    'dados' vem de agenda.ultimos_dias(): uma linha por (data, fam\u00edlia).
    """
    from matplotlib.colors import to_rgba

    d = dados[dados["familia"].isin(FAMILIAS_COM_DV)
              & (dados["quantos_atras"] < quantos)]
    if d.empty:
        ax.set_axis_off()
        ax.text(0.5, 0.5, "sem leil\u00e3o no hist\u00f3rico para comparar",
                ha="center", va="center", transform=ax.transAxes)
        return

    # Do preg\u00e3o mais recente (em cima) para o mais antigo.
    dias = list(d.sort_values("quantos_atras")["data_leilao"].drop_duplicates())
    familias = [f for f in ORDEM_FAMILIAS if f in set(d["familia"])]
    ofertado = _pilha(d, dias, familias, "dv_ofertado")
    aceito = _pilha(d, dias, familias, "dv_aceito")

    posicoes = list(range(len(dias)))
    altura = 0.38
    base_of = [0.0] * len(dias)
    base_ac = [0.0] * len(dias)

    for familia in familias:
        cor = _cor(familia)
        valores_of = [v * 1000 for v in ofertado[familia]]
        valores_ac = [v * 1000 for v in aceito[familia]]
        ax.barh([p - altura / 2 for p in posicoes], valores_of, left=base_of,
                height=altura,
                color=to_rgba(cor, OPACIDADE_DO_OFERTADO),
                edgecolor=cor, linewidth=1.2, zorder=3)
        ax.barh([p + altura / 2 for p in posicoes], valores_ac, left=base_ac,
                height=altura, color=cor, label=familia, zorder=3)
        base_of = [b + v for b, v in zip(base_of, valores_of)]
        base_ac = [b + v for b, v in zip(base_ac, valores_ac)]

    ax.set_yticks(posicoes)
    ax.set_yticklabels([f"{dia:%d/%m}" for dia in dias], fontsize=9.5)
    ax.invert_yaxis()

    ax.set_xlabel("DV01 do preg\u00e3o, R$ mil por ponto-base")
    ax.axvline(0, color="gray", lw=0.8)
    _grade(ax)
    ax.set_title("Quanto risco ele tentou colocar, e quanto colocou, "
                 "em cada preg\u00e3o",
                 fontsize=11, weight="bold", loc="left", pad=10)

    _rotula_totais(ax, posicoes, base_of, base_ac)
    _legenda(ax, familias)


def _rotula_totais(ax, posicoes, base_of, base_ac):
    """O total do dia na ponta de cada barra, e a fra\u00e7\u00e3o colocada numa coluna fixa.

    O TOTAL \u00c9 O QUE ELA PEDIU: quanto risco entrou no mercado naquele preg\u00e3o. Com a
    barra empilhada, nenhuma fatia sozinha o mostra.

    A fra\u00e7\u00e3o sai numa coluna fixa, e n\u00e3o colada \u00e0 barra: presa a ela, pularia de
    lugar a cada linha e as seis fra\u00e7\u00f5es deixariam de poder ser lidas de cima a
    baixo.
    """
    maior = max(max(base_of, default=0.0), max(base_ac, default=0.0))
    coluna = maior * 1.13

    for p, total_of, total_ac in zip(posicoes, base_of, base_ac):
        for y, v in ((p - 0.19, total_of), (p + 0.19, total_ac)):
            if v:
                ax.annotate(estilo.num_br(v, 0), (v, y),
                            textcoords="offset points", xytext=(4, 0),
                            va="center", ha="left", fontsize=8.5,
                            color="#333333")
        if not total_of:
            continue
        fracao = total_ac / total_of
        ax.annotate(f"{estilo.num_br(fracao * 100, 0)}%", (coluna, p),
                    va="center", ha="left", fontsize=10, weight="bold",
                    color="#333333" if fracao > LIMIAR_DO_ALERTA else "#c00000")

    if maior:
        ax.set_xlim(min(0.0, ax.get_xlim()[0]), maior * 1.26)


def _legenda(ax, familias):
    """A legenda diz o papel pela cor, e o par vazada/cheia por dois ret\u00e2ngulos."""
    from matplotlib.patches import Patch

    marcas = [Patch(facecolor=_cor(f), label=f) for f in familias]
    marcas.append(Patch(facecolor="white", edgecolor="#555555", linewidth=1.2,
                        label="barra de cima: ofertado"))
    marcas.append(Patch(facecolor="#555555", label="barra de baixo: aceito"))
    ax.legend(handles=marcas, ncol=min(len(marcas), 6), frameon=False,
              loc="upper center", bbox_to_anchor=(0.5, -0.12), fontsize=9)


def desenha_quantidade_lft(dados, ax, quantos=4):
    """A LFT em QUANTIDADE, com o financeiro escrito ao lado da barra.

    Ela n\u00e3o tem DV por decis\u00e3o de modelagem, ent\u00e3o a compara\u00e7\u00e3o ofertado/aceito s\u00f3
    existe em t\u00edtulos. O financeiro entra como r\u00f3tulo porque \u00e9 a grandeza que se
    compara com o resto do projeto -- e a LFT \u00e9 mais da metade da emiss\u00e3o.

    'dados' vem de agenda.ultimos_de("LFT").
    """
    from matplotlib.colors import to_rgba

    d = dados[dados["quantos_atras"] < quantos]
    if d.empty:
        ax.set_axis_off()
        ax.text(0.5, 0.5, "sem leil\u00e3o de LFT no hist\u00f3rico",
                ha="center", va="center", transform=ax.transAxes)
        return

    posicoes = list(range(len(d)))
    altura = 0.38
    cor = _cor("LFT")
    ofertado = list(d["qtd_ofertada"] / 1000)
    aceito = list(d["qtd_aceita"] / 1000)

    ax.barh([p - altura / 2 for p in posicoes], ofertado, height=altura,
            label="ofertado", color=to_rgba(cor, OPACIDADE_DO_OFERTADO),
            edgecolor=cor, linewidth=1.4, zorder=3)
    ax.barh([p + altura / 2 for p in posicoes], aceito, height=altura,
            label="aceito", color=cor, zorder=3)

    ax.set_yticks(posicoes)
    ax.set_yticklabels([f"{r['data_leilao']:%d/%m/%y}" for _, r in d.iterrows()],
                       fontsize=9.5)
    ax.invert_yaxis()
    ax.set_xlabel("milhares de t\u00edtulos")
    ax.axvline(0, color="gray", lw=0.8)
    _grade(ax)
    ax.set_title("LFT \u00b7 ofertado e aceito em t\u00edtulos, com o financeiro aceito",
                 fontsize=11, weight="bold", loc="left", pad=10)

    maior = max(ofertado + aceito)
    coluna = maior * 1.14
    for k, (p, of, ac) in enumerate(zip(posicoes, ofertado, aceito)):
        for y, v in ((p - altura / 2, of), (p + altura / 2, ac)):
            ax.annotate(estilo.num_br(v, 0), (v, y), textcoords="offset points",
                        xytext=(4, 0), va="center", ha="left", fontsize=8.5,
                        color="#333333")
        if not of:
            continue
        fracao = ac / of
        financeiro = d.iloc[k]["financeiro_milhoes"] / 1000
        ax.annotate(f"{estilo.num_br(fracao * 100, 0)}%  \u00b7  "
                    f"R$ {estilo.num_br(financeiro, 2)} bi",
                    (coluna, p), va="center", ha="left", fontsize=9.5,
                    weight="bold",
                    color="#333333" if fracao > LIMIAR_DO_ALERTA else "#c00000")
    ax.set_xlim(0, maior * 1.62)
    ax.legend(ncol=2, frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.18))


def _grade(ax):
    """Grade densa no eixo do valor: linha forte na marca, fraca no meio."""
    from matplotlib.ticker import AutoMinorLocator

    ax.xaxis.set_minor_locator(AutoMinorLocator(2))
    ax.grid(axis="x", which="major", alpha=0.28, lw=0.8)
    ax.grid(axis="x", which="minor", alpha=0.14, lw=0.6)
    ax.set_axisbelow(True)
