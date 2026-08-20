"""Os desenhos da agenda de leiloes: o que o Tesouro planeja ofertar.

Tres graficos, e a ordem entre eles e do mais firme para o mais suposto -- que e
tambem a ordem em que merecem confianca:

  1. O CRONOGRAMA. So fatos: em que dia, qual papel, qual vertice. Nada calculado;
  2. O DV01 POR TITULO. Calculado, mas so a partir da ultima taxa observada -- e
     propriedade do instrumento, nao depende de quantidade nenhuma;
  3. O DV01 DO DIA SE REPETIR A ULTIMA OFERTA. Um produto por um numero do passado.
     E o numero que se quer olhar, e o que menos merece confianca.

A cor e a familia do papel, como no resto do projeto. O terceiro grafico ganha
hachura inteira, porque a pagina toda e sobre coisa que ainda nao aconteceu e a
distincao ali e entre "medido" e "suposto", nao entre "hoje" e "ontem".
"""
import pandas as pd

from . import estilo

# A mesma paleta dos graficos de emissao: familia do papel, e nao proveniencia.
_COR_FAMILIA = {"LFT": "LFT", "LTN": "LTN", "NTN-F": "NTN-F",
                "NTN-B curta": "NTN-B", "NTN-B longa": "NTN-C"}

ORDEM_FAMILIAS = ["LFT", "LTN", "NTN-F", "NTN-B curta", "NTN-B longa"]

# A hachura que marca o que foi SUPOSTO, e nao medido. Igual a do provisorio nos
# graficos de emissao, e de proposito: e o mesmo idioma.
HACHURA_SUPOSTO = "///"


def _cor(familia):
    return estilo.COR[_COR_FAMILIA.get(familia, "Outros")]


def desenha_cronograma(dados, ax):
    """Cada papel da agenda no seu dia, com o vertice no eixo vertical.

    O VERTICE NO EIXO Y, e nao o papel: assim se ve a COBERTURA DA CURVA em cada
    dia, que e a leitura que interessa. Um dia com 3, 7 e 15 anos e outro com 5 e 30
    fazem coisas diferentes com o prazo medio da divida, e num grafico por papel os
    dois pareceriam iguais.

    A escala do Y e logaritmica porque os vertices vao de meio ano a 35: linear
    empilharia tudo o que e curto numa faixa de dois pixels.
    """
    for familia in ORDEM_FAMILIAS:
        g = dados[dados["familia"] == familia]
        if g.empty:
            continue
        ax.scatter(g["data_leilao"], g["vertice_anos"].astype(float),
                   s=90, color=_cor(familia), label=familia,
                   edgecolor="white", linewidth=0.8, zorder=3)

    ax.set_yscale("log")
    marcas = [0.5, 1, 2, 3, 5, 7, 10, 15, 25, 30, 35]
    ax.set_yticks(marcas)
    ax.set_yticklabels([("6m" if m == 0.5 else f"{m:g}a") for m in marcas])
    ax.set_ylabel("v\u00e9rtice do benchmark")
    ax.grid(axis="y", alpha=0.20, which="major")
    ax.grid(axis="x", alpha=0.12)
    _eixo_de_dias(ax, dados["data_leilao"])
    ax.set_title("O que est\u00e1 agendado, por dia e por v\u00e9rtice",
                 fontsize=11, weight="bold", loc="left", pad=10)
    ax.legend(ncol=len(ORDEM_FAMILIAS), frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.14))


def desenha_dv_unitario(dados, ax):
    """O DV01 de UM titulo de cada papel da agenda.

    E o numero mais firme da pagina: nao depende de quantidade, so da taxa -- e a
    taxa suposta move o DV do lote em 0,55% na mediana. Responde "qual destes papeis
    carrega risco", que e a pergunta que o cronograma sozinho nao responde.

    Uma barra por PAPEL, e nao por linha da agenda: o mesmo benchmark aparece varias
    vezes no calendario, e repetir a barra nao acrescenta nada.

    A LFT nao aparece, por decisao de modelagem da entrega 2 e nao por falha de
    calculo. Quem diz isso e a legenda da pagina: a primeira versao punha o aviso
    dentro da figura, e ele caia em cima da barra mais longa.
    """
    d = (dados[dados["dv_unitario"].notna()]
         .drop_duplicates("benchmark")
         .sort_values("vertice_anos"))
    if d.empty:
        ax.set_axis_off()
        ax.text(0.5, 0.5, "nenhum papel da agenda tem DV01 calcul\u00e1vel",
                ha="center", va="center", transform=ax.transAxes)
        return

    posicoes = range(len(d))
    ax.barh(list(posicoes), d["dv_unitario"],
            color=[_cor(f) for f in d["familia"]], height=0.72)
    ax.set_yticks(list(posicoes))
    ax.set_yticklabels(d["benchmark"])
    ax.invert_yaxis()
    ax.axvline(0, color="gray", lw=0.8)
    ax.set_xlabel("DV01 de um t\u00edtulo, R$ por ponto-base")
    ax.grid(axis="x", alpha=0.20)
    ax.set_title("Quanto risco carrega CADA T\u00cdTULO da agenda",
                 fontsize=11, weight="bold", loc="left", pad=10)

    # Folga a esquerda para o rotulo da barra mais longa caber. Sem ela, o texto do
    # "NTN-B 35 anos" atravessava o nome do papel -- e a primeira versao saiu assim.
    menor = float(d["dv_unitario"].min())
    ax.set_xlim(menor * 1.32, 0)

    for i, (valor, taxa) in enumerate(zip(d["dv_unitario"], d["taxa_pct"])):
        ax.text(valor, i, f"  {estilo.num_br(abs(valor), 3)} \u00b7 "
                          f"{estilo.num_br(taxa, 2)}%  ",
                va="center", ha="right" if valor < 0 else "left", fontsize=8.5)



def desenha_dv_por_dia(dados, ax):
    """O DV01 de cada dia da agenda, SE ele repetir a ultima oferta de cada papel.

    HACHURADO INTEIRO, de proposito. A quantidade nao esta no calendario: ela sai no
    edital das 10h30 do proprio dia. Isto aqui e uma multiplicacao pelo que ele
    ofertou da vez passada, e o Tesouro muda de tamanho de leilao para leilao.

    Sem a hachura a barra pareceria uma previsao, e nao e.
    """
    por_dia = dados.groupby("data_leilao").agg(
        dv=("dv_se_repetir", "sum"),
        velha=("taxa_velha", "any"),
    )
    if por_dia.empty:
        ax.set_axis_off()
        return

    ax.bar(por_dia.index, por_dia["dv"], width=1.6,
           color="#c00000", alpha=0.30, hatch=HACHURA_SUPOSTO,
           edgecolor="#c00000", linewidth=1.0,
           label="se repetir a \u00faltima oferta de cada papel")
    ax.axhline(0, color="gray", lw=0.8)
    ax.set_ylabel("DV01 do dia, R$ milh\u00f5es por ponto-base")
    ax.invert_yaxis()
    ax.grid(axis="y", alpha=0.20)
    _eixo_de_dias(ax, por_dia.index)
    ax.set_title("Se ele repetir a \u00faltima oferta \u00b7 "
                 "a quantidade real s\u00f3 sai \u00e0s 10h30 do dia",
                 fontsize=11, weight="bold", loc="left", pad=10)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.14))


def _eixo_de_dias(ax, datas):
    """Um rotulo por dia de leilao, e nao por mes.

    A agenda tem doze dias em seis semanas: rotular por mes deixaria dois rotulos
    numa figura em que cada dia e uma coluna que se quer identificar.
    """
    import matplotlib.dates as mdates

    dias = pd.DatetimeIndex(sorted(set(pd.DatetimeIndex(datas))))
    ax.set_xticks(dias)
    ax.set_xticklabels([f"{d.day:02d}/{estilo.MES[d.month]}" for d in dias],
                       rotation=45, ha="right", fontsize=9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter(""))
    ax.set_xticks(dias)
    ax.set_xticklabels([f"{d.day:02d}/{estilo.MES[d.month]}" for d in dias],
                       rotation=45, ha="right", fontsize=9)
    margem = pd.Timedelta(days=2)
    ax.set_xlim(dias.min() - margem, dias.max() + margem)
