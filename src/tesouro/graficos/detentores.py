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


# Quantos anos fechados aparecem antes dos dois ultimos meses. Seis e o que cabe na
# pagina do RMD, e e o que a dona do projeto pediu.
ANOS_NA_PARTICIPACAO = 6

# Os quatro que a pagina do RMD nomeia no painel de variacao. "Demais Grupos" fica
# de fora la, e fica aqui tambem: e um balde, e variacao de balde nao se le.
PRINCIPAIS = ["Inst. Financeiras", "Fundos", "Previd\u00eancia", "N\u00e3o-residentes"]


def _estoque_por_grupo():
    """Estoque de cada um dos cinco grupos, mes a mes, em R$ milhoes."""
    d = pd.read_csv(config.PROCESSED_DIR / "detentores.csv", parse_dates=["data"])
    d["grupo"] = [_GRUPO_DE.get(_sem_nota(n), "Demais Grupos") for n in d["detentor"]]
    piv = d.pivot_table(index="data", columns="grupo",
                        values="valor_milhoes", aggfunc="sum").fillna(0.0)
    return piv[ORDEM_GRUPOS]


def colunas_da_participacao():
    """As datas que viram coluna: os anos fechados mais os dois ultimos meses.

    Devolve pares (rotulo, data). O rotulo do ano fechado e o ano; o dos dois
    ultimos meses e 'mai-26', 'jun-26' -- como a pagina do RMD escreve.
    """
    piv = _estoque_por_grupo()
    ultimo = piv.index.max()
    penultimo = piv.index[piv.index < ultimo].max()

    fechados = []
    for ano in range(ultimo.year - ANOS_NA_PARTICIPACAO, ultimo.year):
        fim = pd.Timestamp(year=ano, month=12, day=31)
        if fim in piv.index:
            fechados.append((str(ano), fim))

    def rotulo_curto(d):
        return f"{estilo.MES[d.month]}-{d.year % 100:02d}"

    return fechados + [(rotulo_curto(penultimo), penultimo),
                       (rotulo_curto(ultimo), ultimo)]


def dados_participacao():
    """Participacao dos cinco grupos em cada coluna, em percentual.

    O formato e o da pagina 7 do RMD: uma coluna de 100% por ano fechado, mais os
    dois ultimos meses. Substituiu o par barra-horizontal-mais-variacao por pedido
    da dona do projeto -- a serie por coluna mostra o movimento, que o retrato de
    um mes nao mostra.
    """
    piv = _estoque_por_grupo()
    colunas = colunas_da_participacao()
    recorte = piv.loc[[data for _, data in colunas]]
    share = recorte.div(recorte.sum(axis=1), axis=0) * 100
    share.index = [rotulo for rotulo, _ in colunas]
    return share


def dados_variacao():
    """Variacao do estoque dos quatro principais, em R$ milhoes, em tres horizontes.

    Os mesmos tres da pagina do RMD: em 12 meses, no ano (contra o fechamento do ano
    anterior) e no mes. Em R$ e nao em pontos percentuais -- participacao que cai
    com estoque subindo e ruido de composicao, nao venda.
    """
    piv = _estoque_por_grupo()
    hoje = piv.index.max()

    referencias = {
        "em 12 meses": hoje - pd.DateOffset(months=12),
        "no ano": pd.Timestamp(year=hoje.year - 1, month=12, day=31),
        "no m\u00eas": piv.index[piv.index < hoje].max(),
    }
    for nome, data in referencias.items():
        if data not in piv.index:
            raise LookupError(
                f"detentores.csv nao tem {data.date()}, que e a base de '{nome}' "
                f"contra o ultimo mes ({hoje.date()}). Calcular contra o mes vizinho "
                f"mais proximo daria um numero plausivel e errado."
            )

    saida = pd.DataFrame(index=PRINCIPAIS)
    for nome, data in referencias.items():
        saida[nome] = piv.loc[hoje, PRINCIPAIS] - piv.loc[data, PRINCIPAIS]
    return saida


def dados_por_papel():
    """Participacao de cada detentor dentro de cada papel, em percentual."""
    d = pd.read_csv(config.PROCESSED_DIR / "detentores_por_titulo.csv",
                    parse_dates=["data"])
    u = d[d["data"] == d["data"].max()]
    piv = u.pivot_table(index="titulo", columns="detentor",
                        values="valor_milhoes", aggfunc="sum").fillna(0.0)
    return piv.div(piv.sum(axis=1), axis=0) * 100


def dados_financeiro_do_papel(papel, janela=None):
    """Financeiro de cada detentor DENTRO de um papel, mes a mes, em R$ milhoes.

    A aba 2.8 abre o estoque por papel e por detentor. Isto e a mesma leitura do
    grafico dos oito paineis, restrita a um papel -- e o que responde "quem esta
    comprando LFT" em vez de "quem esta comprando divida".
    """
    d = pd.read_csv(config.PROCESSED_DIR / "detentores_por_titulo.csv",
                    parse_dates=["data"])
    do_papel = d[d["titulo"] == papel]
    if do_papel.empty:
        raise LookupError(
            f"detentores_por_titulo.csv nao tem o papel '{papel}'. Os que existem "
            f"sao {sorted(d['titulo'].unique())}."
        )
    piv = do_papel.pivot_table(index="data", columns="detentor",
                               values="valor_milhoes", aggfunc="sum").fillna(0.0)
    return estilo.recorta(piv, janela)


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

def desenha_participacao(dados, variacao, fig):
    """Os dois paineis da pagina 7 do RMD.

    Em cima, uma coluna de 100% por ano fechado mais os dois ultimos meses, com o
    percentual escrito dentro de cada faixa. Embaixo, a variacao do estoque dos
    quatro principais em R$ bilhoes, nos tres horizontes.

    A variacao vai em REAIS e nao em pontos percentuais. Participacao que cai com
    estoque subindo e ruido de composicao -- o grupo comprou, mas os outros
    compraram mais -- e ler isso como venda e o erro que o painel em p.p. convida.
    """
    # hspace generoso e titulo em cada painel: colados, a legenda do painel de
    # baixo era lida como se fosse do de cima -- os dois falam de detentores, e nada
    # no desenho dizia onde um terminava e o outro comecava.
    a1, a2 = fig.subplots(2, 1,
                          gridspec_kw={"height_ratios": [3, 2], "hspace": 0.55})

    posicoes = range(len(dados))
    base = [0.0] * len(dados)
    for grupo in ORDEM_GRUPOS:
        alturas = list(dados[grupo])
        a1.bar(list(posicoes), alturas, bottom=base, width=0.62,
               color=estilo.COR[CHAVE_COR[grupo]], label=grupo)
        for x, (altura, pe) in enumerate(zip(alturas, base)):
            # 3,5% e o limiar em que o texto ainda cabe dentro da faixa. Abaixo
            # disso ele encavala na faixa vizinha, que e pior do que faltar.
            if altura >= 3.5:
                a1.text(x, pe + altura / 2, estilo.num_br(altura, 1) + "%",
                        ha="center", va="center", fontsize=8.5, color="white",
                        weight="bold")
        base = [b + h for b, h in zip(base, alturas)]

    a1.set_xticks(list(posicoes))
    a1.set_xticklabels(list(dados.index), fontsize=9.5)
    a1.set_ylim(0, 100)
    a1.set_yticks([])
    a1.set_ylabel("% do estoque da DPMFi")
    a1.set_title("Participa\u00e7\u00e3o relativa dos detentores da DPMFi", fontsize=11,
                 weight="bold", loc="left", pad=26)
    a1.legend(ncol=len(ORDEM_GRUPOS), frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, 1.11), fontsize=9)
    for lado in ("top", "right", "left"):
        a1.spines[lado].set_visible(False)

    horizontes = list(variacao.columns)
    largura = 0.26
    cores_horizonte = {horizontes[0]: "#3d9be9", horizontes[1]: "#ed7d31",
                       horizontes[2]: "#a6a6a6"}
    centros = range(len(variacao))
    for i, horizonte in enumerate(horizontes):
        deslocamento = (i - 1) * largura
        valores = variacao[horizonte] / 1000
        a2.bar([c + deslocamento for c in centros], valores, width=largura,
               color=cores_horizonte[horizonte], label=horizonte)
        for c, v in zip(centros, valores):
            a2.annotate(estilo.num_br(v, 1), xy=(c + deslocamento, v),
                        xytext=(0, 3 if v >= 0 else -11),
                        textcoords="offset points", ha="center", fontsize=8,
                        color="#333333")

    a2.set_xticks(list(centros))
    a2.set_xticklabels(list(variacao.index), fontsize=9.5)
    a2.axhline(0, color="gray", lw=0.8)
    a2.set_ylabel("varia\u00e7\u00e3o do estoque, R$ bilh\u00f5es")
    a2.set_title("Varia\u00e7\u00e3o do estoque dos principais detentores", fontsize=11,
                 weight="bold", loc="left", pad=26)
    # A legenda deste painel fica DENTRO dele, e nao no espaco entre os dois: era
    # ali que ela parecia pertencer ao painel de cima.
    a2.legend(ncol=3, frameon=False, loc="upper right", fontsize=9)
    a2.grid(axis="y", alpha=0.20)
    for lado in ("top", "right"):
        a2.spines[lado].set_visible(False)


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


def desenha_financeiro_do_papel(dados, fig, papel):
    """Os mesmos oito paineis, restritos a um papel.

    Mesmo desenho do grafico geral de proposito: quem ja aprendeu a ler aquele le
    este sem reaprender nada, e a comparacao entre papeis fica possivel.
    """
    desenha_financeiro(dados, fig)
    fig.suptitle(f"{papel}: financeiro por detentor", fontsize=11, weight="bold",
                 y=0.98)
