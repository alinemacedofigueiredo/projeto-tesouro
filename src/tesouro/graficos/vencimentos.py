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

ARMADILHA 2b: A 3.4 INCLUI CUPOM, a 2.2 nao. Isso foi afirmado ao contrario ate a
dona do projeto apontar que ha "vencimentos pequenos em todo cupom de B". Medido:
em nov/26 a 3.4 traz 25,8 bi de NTN-B e nenhuma NTN-B vence naquele mes; em jul/26 a
coluna LTN/NTN-F traz 33,2 bi a mais do que vence, que e cupom de NTN-F; e a LFT,
que nao paga cupom, bate na casa decimal com a 2.2 em todo mes.

Nenhuma das duas exige premissa de inflacao: os valores da 3.4 sao cada fluxo
avaliado pelo preco da curva na data-base, e nao caixa nominal projetado -- e por
isso que a soma dos fluxos da exatamente o estoque, 8.920,7.

ARMADILHA 3: a banda de vincendo em 12 meses vem de DUAS fontes. A aba 5.7 do anexo
de jun/26 termina em "PAF 2022"; o referencia/paf_bandas.csv cobre 2016 a 2026 pelo
indicador vincendo_12m_pct. As duas se sobrepoem em sete anos e dao a mesma banda
vigente nos sete -- conferido por teste, nao por confianca.

Em 2020 elas contam historias diferentes sobre COMO se chegou la: a 5.7 guarda uma
linha so, com 24-28, que e a revisao de ago/20; a original era 20-23, e so o arquivo
de referencia a tem. A banda desenhada e a mesma; o que a 5.7 perde e a memoria de
que a meta subiu no meio do ano.
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
    a2.set_title("banda do PAF; onde houve revis\u00e3o, vale a que estava em vigor no "
                 "fechamento do ano", fontsize=9,
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


# A NTN-B1 -- RendA+ e EducA+ -- fica FORA do grafico, por decisao da dona do
# projeto: ela tem regra propria de cupom e amortizacao, e empilhar com a NTN-B
# comum soma coisas que nao se comportam igual. Sao 18,1 bi, e o desenho diz isso
# num asterisco em vez de escond\u00ea-los.
FORA_DO_PERFIL = ("NTN-B1",)


def excluido_do_perfil():
    """Quanto de NTN-B1 ficou fora do grafico, em R$ milhoes.

    Existe para o asterisco do desenho poder dizer o numero, e para o teste poder
    conferir que o numero dito e o numero excluido.
    """
    return _perfil_bruto()[list(FORA_DO_PERFIL)].sum().sum()


def _perfil_bruto():
    """A aba 2.2 inteira, por ano e familia, ANTES de tirar a NTN-B1."""
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


def dados_perfil_completo():
    """Vencimentos por ano, por familia de titulo, em R$ milhoes.

    Vem da aba 2.2, papel a papel -- diferente do cronograma, que vem da 3.4 e para
    em 60 meses.

    SEM a NTN-B1: com ela o grafico ia ate 2084; sem ela termina em 2060, porque
    2064, 2069, 2074, 2079 e 2084 sao RendA+ e mais nada. A cauda longa some do
    desenho de proposito -- ver FORA_DO_PERFIL.

    ARMADILHA: papeis ja vencidos ficam no CSV com financeiro zero e ano de
    vencimento no passado. Sem filtrar, o eixo comeca em 2010 com quatorze anos
    vazios.
    """
    piv = _perfil_bruto().drop(columns=list(FORA_DO_PERFIL))
    # Anos que so existiam por causa da NTN-B1 saem junto: uma barra de altura zero
    # em 2084 seria pior do que nao ter 2084 nenhum.
    return piv[piv.sum(axis=1) > 0]


def desenha_perfil_completo(dados, ax, excluido):
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

    # O asterisco: o que ficou de fora tem de estar escrito na figura, nao so na
    # legenda do HTML. Quem copia o grafico para um slide leva a ressalva junto.
    #
    # 'excluido' vem por parametro e nao e lido aqui dentro: um `desenha_*` que le
    # CSV quebra a separacao da spec 3.1 exatamente onde ela importa, e relia o
    # mesmo arquivo uma segunda vez a cada render.
    ax.set_title(
        "* n\u00e3o considera as NTN-B1 (RendA+ e EducA+), "
        + estilo.num_br(excluido / 1000, 1)
        + " bi: elas t\u00eam regra pr\u00f3pria de cupom e "
        "amortiza\u00e7\u00e3o",
        fontsize=9, loc="left", color=estilo.COR["neutro"], pad=10)
    ax.legend(ncol=6, frameon=False, loc="upper right")
    ax.grid(axis="y", alpha=0.25)


# ---------------------------------------------------------------------------
# Estoque em QUANTIDADE, por vencimento e por papel.
#
# Diferente do perfil logo acima em duas coisas, e as duas importam: aquele
# soma por ANO e conta em FINANCEIRO; este poe uma barra por VENCIMENTO e
# conta TITULOS.
#
# A ARMADILHA DA QUANTIDADE, medida em 30/06/2026: um titulo nao vale o mesmo
# que outro. Um de LFT vale R$ 19.220; um de LFT-TD1 Reserva vale R$ 10,68 --
# mil e oitocentas vezes menos. Os papeis do Tesouro Direto (LFT-TD1 e as duas
# NTN-B1) sao 10,8% da QUANTIDADE e 0,2% do FINANCEIRO.
#
# Eles NAO sao escondidos: o pedido foi "todos os papeis", e a barra alta deles
# e um fato sobre o estoque -- ha muitos papeizinhos. O que o desenho faz e
# DIZER isso, num rodape com o numero medido, para que ninguem leia a barra
# como divida.
# ---------------------------------------------------------------------------

# Os papeis vendidos no Tesouro Direto, cujo valor unitario e de outra ordem.
PAPEIS_DE_VAREJO = ("LFT-TD1 Reserva", "NTN-B1 EducA+", "NTN-B1 RendA+")


def dados_estoque_por_vencimento():
    """Uma linha por (vencimento, titulo), com a quantidade em estoque.

    Ordenada por VENCIMENTO, que e a ordem em que o eixo os desenha. O mesmo
    vencimento pode ter ate tres papeis diferentes -- 15/05/2035 tem NTN-B,
    NTN-B Principal e NTN-B1 -- e cada um vira a sua barra.

    So o que TEM estoque: papel ja vencido fica no CSV com quantidade zero, e
    incluir zeros poria dezenas de barras de altura nenhuma no eixo.
    """
    e = pd.read_csv(config.PROCESSED_DIR / "estoque_titulos_vencimento.csv",
                    parse_dates=["data", "vencimento"])
    u = e[(e["data"] == e["data"].max()) & (e["quantidade_mil"] > 0)].copy()
    u["familia"] = [_FAMILIA[t] for t in u["titulo"]]
    u["varejo"] = u["titulo"].isin(PAPEIS_DE_VAREJO)
    # O valor unitario nao entra no desenho, mas entra no CSV: e o numero que
    # explica por que a barra de um papel de varejo e alta.
    u["valor_unitario"] = (u["financeiro_milhoes"] * 1e6
                           / (u["quantidade_mil"] * 1000))
    colunas = ["vencimento", "titulo", "familia", "varejo", "quantidade_mil",
               "financeiro_milhoes", "valor_unitario"]
    return u[colunas].sort_values(["vencimento", "titulo"]).reset_index(drop=True)


def quanto_e_varejo(dados=None):
    """A fatia dos papeis de varejo, em quantidade e em financeiro.

    Existe para o rodape do desenho poder dizer o numero, e para o teste poder
    conferir que o numero dito e o numero medido.
    """
    d = dados_estoque_por_vencimento() if dados is None else dados
    varejo = d[d["varejo"]]
    return (varejo["quantidade_mil"].sum() / d["quantidade_mil"].sum(),
            varejo["financeiro_milhoes"].sum() / d["financeiro_milhoes"].sum())


def desenha_estoque_por_vencimento(dados, ax):
    """Uma barra por papel-vencimento, em ordem de vencimento.

    O EIXO E CATEGORICO e nao continuo, pelo mesmo motivo do perfil acima: entre
    2060 e 2084 ha quatro vencimentos e vinte e quatro anos, e um eixo continuo
    gastaria metade da largura com vazio.

    A cor e a familia do papel. Os de varejo saem HACHURADOS -- a cor ja diz a
    familia, e roubar uma cor para dizer "varejo" criaria duas leituras para o
    mesmo sinal. E a hachura e o mesmo idioma que a pagina de emissoes usa para
    "este numero merece uma ressalva".
    """
    posicoes = list(range(len(dados)))
    cores = [estilo.COR[_COR_FAMILIA[f]] for f in dados["familia"]]
    hachuras = ["///" if v else "" for v in dados["varejo"]]

    ax.bar(posicoes, dados["quantidade_mil"] / 1000, width=0.78, color=cores,
           hatch=hachuras, edgecolor="#333333",
           linewidth=[0.5 if v else 0.0 for v in dados["varejo"]])

    ax.set_xticks(posicoes)
    ax.set_xticklabels([f"{v:%m/%y}" for v in dados["vencimento"]],
                       rotation=90, fontsize=6.5)
    ax.set_ylabel("milh\u00f5es de t\u00edtulos em estoque")
    ax.margins(x=0.005)
    ax.grid(axis="y", which="major", alpha=0.28, lw=0.8)
    ax.set_axisbelow(True)
    # Folga no topo para o rodape nao cair em cima da barra mais alta -- que e
    # justamente a que ele explica.
    ax.set_ylim(0, float(dados["quantidade_mil"].max()) / 1000 * 1.16)

    from matplotlib.patches import Patch
    marcas = [Patch(facecolor=estilo.COR[_COR_FAMILIA[f]], label=f)
              for f in ORDEM_FAMILIAS if f in set(dados["familia"])]
    marcas.append(Patch(facecolor="white", edgecolor="#333333", hatch="///",
                        label="Tesouro Direto"))
    ax.legend(handles=marcas, ncol=len(marcas), frameon=False,
              loc="upper center", bbox_to_anchor=(0.5, -0.16), fontsize=9)

    # O RODAPE QUE IMPEDE A LEITURA ERRADA. Sem ele, a barra mais alta do grafico
    # e um papel que vale R$ 10,68 e que responde por 0,2% da divida.
    em_qtd, em_fin = quanto_e_varejo(dados)
    ax.text(0.995, 0.97,
            f"Tesouro Direto ({', '.join(PAPEIS_DE_VAREJO)}): "
            f"{estilo.num_br(em_qtd * 100, 1)}% dos t\u00edtulos e "
            f"{estilo.num_br(em_fin * 100, 1)}% do financeiro \u2014 "
            f"um t\u00edtulo n\u00e3o vale o mesmo que outro.",
            transform=ax.transAxes, ha="right", va="top", fontsize=8.5,
            color="#666666")
