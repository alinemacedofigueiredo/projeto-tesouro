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
# FORA O TESOURO DIRETO, por decisao da dona do projeto -- e a medicao explica
# por que ela esta certa. Um titulo nao vale o mesmo que outro: em 30/06/2026
# um de LFT valia R$ 19.220 e um de LFT-TD1 Reserva, R$ 10,68. Mil e
# oitocentas vezes menos.
#
# Com eles dentro, a barra mais alta do grafico era a LFT-TD1 de 2036 -- 328
# milhoes de titulos e R$ 3,5 bilhoes, contra os R$ 180 bilhoes da LTN 2029
# que ficava do lado. Os tres papeis de varejo somavam 10,8% dos titulos e
# 0,2% do financeiro.
#
# E o mesmo tratamento que o perfil ao lado ja dava a NTN-B1, e pelo mesmo
# motivo. O que ficou de fora vai num asterisco, com o numero.
# ---------------------------------------------------------------------------

# Os papeis que so existem no Tesouro Direto, e que por isso nao entram no estoque
# em quantidade. Sao DOIS motivos diferentes, e vale nao confundi-los:
#
# Os tres primeiros distorcem a UNIDADE: um LFT-TD1 Reserva vale R$ 10,68 e um LFT,
# R$ 19.220 -- mil e oitocentas vezes mais. Somar os dois em "titulos" nao descreve
# nada.
#
# A NTN-B PRINCIPAL nao distorce a unidade: ela vale de R$ 926 a R$ 4.708 por
# titulo, da mesma ordem da NTN-B. Ela sai por ser papel de varejo -- CONFERIDO, e
# nao suposto: em 19.739 linhas de leilao, das quais 6.275 de NTN-B, ela nao aparece
# NENHUMA vez. Nunca foi ofertada a dealer. Dentro do grafico ela punha uma segunda
# barra na mesma data em sete dos quinze vencimentos, o que se lia como dado
# repetido. Sao 35,1 milhoes de titulos e R$ 91,5 bilhoes -- 7,1% dos titulos e 4,0%
# do financeiro da familia.
#
# ONDE ELA CONTINUA: no perfil por ano (dados_perfil_completo), que conta REAIS a
# vencer e nao titulos. La ela e divida que o Tesouro deve e que vence naquele ano,
# 1,03% do estoque -- tirar seria contar a divida errado.
PAPEIS_DE_VAREJO = ("LFT-TD1 Reserva", "NTN-B1 EducA+", "NTN-B1 RendA+")

# As duas listas ficam SEPARADAS de proposito. A de cima sustenta uma medicao -- "e
# muito dos titulos e quase nada da divida", que um teste confere -- e essa medicao
# so vale para papeis de valor unitario minusculo. A NTN-B Principal nao e um deles:
# ela pesa 4,0% do financeiro da familia. Juntar as duas numa constante so faria o
# teste medir uma coisa e afirmar outra.
FORA_DO_ESTOQUE = PAPEIS_DE_VAREJO + ("NTN-B Principal",)


def _estoque_bruto():
    """A aba 2.2 na data mais recente, ANTES de tirar o Tesouro Direto."""
    e = pd.read_csv(config.PROCESSED_DIR / "estoque_titulos_vencimento.csv",
                    parse_dates=["data", "vencimento"])
    u = e[(e["data"] == e["data"].max()) & (e["quantidade_mil"] > 0)].copy()
    u["familia"] = [_FAMILIA[t] for t in u["titulo"]]
    u["valor_unitario"] = (u["financeiro_milhoes"] * 1e6
                           / (u["quantidade_mil"] * 1000))
    return u


def excluido_do_estoque():
    """O Tesouro Direto que ficou de fora: (titulos em milhares, R$ milhoes).

    Existe para o asterisco do desenho poder dizer o numero, e para o teste poder
    conferir que o numero dito e o numero excluido -- o mesmo par que
    excluido_do_perfil() forma com o grafico ao lado.
    """
    u = _estoque_bruto()
    fora = u[u["titulo"].isin(FORA_DO_ESTOQUE)]
    return fora["quantidade_mil"].sum(), fora["financeiro_milhoes"].sum()


def dados_estoque_por_vencimento():
    """Uma linha por (vencimento, titulo), com a quantidade em estoque.

    Ordenada por VENCIMENTO, que e a ordem em que o eixo os desenha. O mesmo
    vencimento pode ter mais de um papel -- 15/08/2026 tem NTN-B e NTN-B
    Principal -- e cada um vira a sua barra.

    So o que TEM estoque: papel ja vencido fica no CSV com quantidade zero, e
    incluir zeros poria dezenas de barras de altura nenhuma no eixo.

    SEM os papeis do Tesouro Direto -- ver o cabecalho desta secao.
    """
    u = _estoque_bruto()
    u = u[~u["titulo"].isin(FORA_DO_ESTOQUE)]
    colunas = ["vencimento", "titulo", "familia", "quantidade_mil",
               "financeiro_milhoes", "valor_unitario"]
    return u[colunas].sort_values(["vencimento", "titulo"]).reset_index(drop=True)


# Os papeis que ganham grafico proprio de estoque. A NTN-C fica de fora: tem UM
# vencimento e 11 milhoes de titulos, e um grafico de uma barra so nao e grafico.
PAPEIS_COM_GRAFICO = ("LFT", "LTN", "NTN-F", "NTN-B")


def desenha_estoque_de(dados, ax, familia):
    """Barras DEITADAS, um vencimento por linha, em ordem cronologica.

    DEITADAS porque o rotulo e uma data completa -- 01/07/2026 -- e data em pe vira
    etiqueta girada. E a quantidade vai escrita na frente da barra, que e o numero
    que se foi ver: com quinze barras, ler a altura contra o eixo e mirar.

    CADA PAPEL COM A SUA ESCALA, e nao uma comum aos quatro. Sao quatro graficos
    separados, e o que se compara dentro de cada um e um vencimento com o outro do
    MESMO papel -- para comparar volumes entre papeis existe o total no titulo. Com
    escala comum a NTN-B ficaria espremida num quinto da largura, porque a maior
    LTN tem 251 milhoes de titulos e a maior NTN-B tem 54.
    """
    g = dados[dados["familia"] == familia].sort_values("vencimento")
    if g.empty:
        ax.set_axis_off()
        ax.text(0.5, 0.5, f"sem estoque de {familia}", ha="center", va="center",
                transform=ax.transAxes)
        return

    posicoes = list(range(len(g)))
    quantidades = list(g["quantidade_mil"] / 1000)
    ax.barh(posicoes, quantidades, height=0.72,
            color=estilo.COR[_COR_FAMILIA[familia]])

    ax.set_yticks(posicoes)
    ax.set_yticklabels([f"{v:%d/%m/%Y}" for v in g["vencimento"]], fontsize=9)
    # O vencimento mais PROXIMO em cima: e a ordem em que a divida vence, e a
    # ordem em que se le uma lista.
    ax.invert_yaxis()

    ax.set_xlabel("milh\u00f5es de t\u00edtulos em estoque")
    ax.grid(axis="x", alpha=0.25, lw=0.8)
    ax.set_axisbelow(True)

    for posicao, quantidade in zip(posicoes, quantidades):
        ax.annotate(estilo.num_br(quantidade, 1), (quantidade, posicao),
                    textcoords="offset points", xytext=(5, 0), va="center",
                    ha="left", fontsize=9, color="#333333")
    # Folga a direita para o numero caber dentro da figura.
    ax.set_xlim(0, max(quantidades) * 1.16)

    total = g["quantidade_mil"].sum() / 1000
    ax.set_title(f"{familia} \u00b7 estoque por vencimento \u00b7 "
                 f"{len(g)} vencimentos \u00b7 "
                 f"{estilo.num_br(total, 0)} milh\u00f5es de t\u00edtulos",
                 fontsize=11, weight="bold", loc="left", pad=10)


def altura_do_estoque(familia, dados=None):
    """A altura da figura, proporcional ao numero de vencimentos do papel.

    A LFT tem dezessete vencimentos e a NTN-F tem seis: com altura fixa, um sai
    apertado e o outro com metade da figura vazia.
    """
    d = dados_estoque_por_vencimento() if dados is None else dados
    quantos = len(d[d["familia"] == familia])
    return max(2.6, 1.5 + quantos * 0.32)
