"""Composicao da DPF por indexador, com a banda do PAF por cima.

O retrato da gestao: quanto da divida esta em cada indexador, mes a mes desde
dez/2000, contra o que o PAF prometeu para cada ano.

A serie completa e o padrao, e nao os 5 anos: o cambio sai de 51,0% em set/2002
para 3,7% hoje, e essa queda -- que e o fato central da gestao da divida brasileira
-- nao existe dentro de uma janela curta.

ARMADILHA: a aba 2.1 grava o indexador como "Indice Precos" e a aba 1.2, que
alimenta o funding.py, grava "Indice de Precos", com "de" no meio. Copiar a lista
de nomes de la deixa uma coluna vazia e um indexador fora do grafico.
"""

import pandas as pd

from .. import config
from . import estilo

_ORDEM = ["Prefixado", "\u00cdndice Pre\u00e7os", "Taxa Flutuante",
          "C\u00e2mbio", "Demais"]

_CHAVE_COR = {"Prefixado": "Prefixado",
              "\u00cdndice Pre\u00e7os": "Indice Precos",
              "Taxa Flutuante": "Taxa Flutuante",
              "C\u00e2mbio": "Cambio",
              "Demais": "Demais"}

# Qual banda do PAF corresponde a qual coluna do nosso CSV.
BANDA_DE = {"prefixado_pct": "Prefixado",
            "indice_precos_pct": "\u00cdndice Pre\u00e7os",
            "taxa_flutuante_pct": "Taxa Flutuante",
            "cambio_pct": "C\u00e2mbio"}


def dados_composicao(janela=None):
    """Participacao de cada indexador na DPF, em percentual, mes a mes.

    'estoque_milhoes' viaja junto porque o percentual sozinho nao diz que a divida
    saiu de 654 bi para 9.268 bi no mesmo periodo.
    """
    c = pd.read_csv(config.PROCESSED_DIR / "composicao_dpf.csv",
                    parse_dates=["data"])
    piv = c.pivot_table(index="data", columns="indexador",
                        values="valor_milhoes", aggfunc="sum").fillna(0.0)
    total = piv.sum(axis=1)
    share = piv.div(total, axis=0) * 100
    share = share[[k for k in _ORDEM if k in share.columns]].copy()
    share["estoque_milhoes"] = total
    return estilo.recorta(share, janela)


def desenha_composicao_100(dados, ax):
    """A mesma composicao, empilhada em 100%.

    O grafico de linha responde "onde estamos contra a meta do PAF"; este responde
    "de que a divida e feita". Sao perguntas diferentes e por isso os dois existem
    -- e e neste que a queda do cambio se le como o que ela foi: uma faixa que
    ocupava metade do grafico em 2002 e hoje e um fio.

    A faixa "Demais" entra aqui, ao contrario do grafico de linha: numa area
    empilhada de 100% ela tem de entrar, ou a soma nao fecha.
    """
    colunas = [c for c in dados.columns if c != "estoque_milhoes"]
    ax.stackplot(dados.index, *[dados[c] for c in colunas],
                 labels=colunas,
                 colors=[estilo.COR[_CHAVE_COR[c]] for c in colunas],
                 edgecolor="white", linewidth=0.3)

    # O valor de cada faixa no ultimo mes, escrito na altura do meio da faixa.
    base = 0.0
    for coluna in colunas:
        altura = dados[coluna].iloc[-1]
        if altura >= 2.0:
            ax.annotate(estilo.num_br(altura, 1), xy=(dados.index[-1], base + altura / 2),
                        xytext=(7, 0), textcoords="offset points", fontsize=9,
                        weight="bold", color=estilo.COR[_CHAVE_COR[coluna]],
                        va="center")
        base += altura

    # O pico do cambio marcado, porque e o fato que o grafico existe para contar.
    #
    # A seta aponta para o MEIO DA FAIXA do cambio, e nao para a altura do valor: a
    # faixa e a quarta da pilha, entao 51% dela mora entre 74 e 100, e nao entre 0 e
    # 51. Apontar para 25,5 poria a seta dentro da faixa do prefixado -- que e o
    # tipo de erro que passa despercebido porque a seta continua "parecendo certa".
    cambio = dados["C\u00e2mbio"]
    if cambio.max() > 30:
        quando = cambio.idxmax()
        abaixo = sum(dados[c].loc[quando] for c in colunas[:colunas.index("C\u00e2mbio")])
        ax.annotate(f"c\u00e2mbio no pico: {estilo.num_br(cambio.max(), 1)}%",
                    xy=(quando, abaixo + cambio.loc[quando] / 2),
                    xytext=(30, -22), textcoords="offset points", fontsize=9,
                    color="white", weight="bold",
                    arrowprops={"arrowstyle": "-", "color": "white", "lw": 1.2})

    ax.set_ylim(0, 100)
    ax.set_xlim(dados.index.min(), dados.index.max())
    ax.set_ylabel("% da DPF")
    estilo.eixo_anual(ax, a_cada=2)
    ax.legend(ncol=len(colunas), frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.08))


def desenha_composicao(dados, bandas, ax):
    """Uma linha por indexador, com a banda do PAF desenhada ano a ano.

    A banda vai por cima do proprio grafico, ano a ano, e nao como caixa estatica
    embaixo do jeito que o RMD faz: assim da para ver, em cada ano, se o realizado
    ficou dentro ou fora do que foi prometido.

    Nos anos revisados a banda original aparece em linha pontilhada por baixo, para
    que a mudanca de meta nao desapareca.
    """
    visiveis = range(dados.index.min().year, dados.index.max().year + 1)

    for indicador, coluna in BANDA_DE.items():
        b = bandas[indicador]
        cor = estilo.COR[_CHAVE_COR[coluna]]
        for ano in visiveis:
            if ano not in b.index:
                continue
            inicio = pd.Timestamp(year=ano, month=1, day=1)
            fim = pd.Timestamp(year=ano, month=12, day=31)
            ax.fill_between([inicio, fim],
                            b.loc[ano, "minimo"], b.loc[ano, "maximo"],
                            color=cor, alpha=0.12, linewidth=0, zorder=1)
            if pd.notna(b.loc[ano, "minimo_original"]):
                for nivel in ("minimo_original", "maximo_original"):
                    ax.plot([inicio, fim], [b.loc[ano, nivel]] * 2,
                            color=cor, lw=0.8, ls=":", zorder=2)

    for coluna in [c for c in dados.columns if c != "estoque_milhoes"]:
        if coluna == "Demais":
            continue                     # nunca passa de 0,06% da DPF
        ax.plot(dados.index, dados[coluna], lw=2.2,
                color=estilo.COR[_CHAVE_COR[coluna]], label=coluna, zorder=3)
        ax.annotate(estilo.num_br(dados[coluna].iloc[-1], 1),
                    xy=(dados.index[-1], dados[coluna].iloc[-1]),
                    xytext=(6, 0), textcoords="offset points",
                    fontsize=9, color=estilo.COR[_CHAVE_COR[coluna]],
                    va="center", weight="bold")

    ax.set_ylabel("% da DPF")
    ax.set_ylim(0, 60)
    estilo.grade_fina(ax, 10, 5)
    estilo.eixo_anual(ax, a_cada=2)
    ax.legend(ncol=4, frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.08))


# ---------------------------------------------------------------------------
# O TOTAL DA DIVIDA: interna, externa e a banda do PAF.
#
# E o primeiro grafico da pagina, e responde a pergunta que vem antes de todas as
# outras -- de quanto e a divida, e ela esta onde o PAF prometeu?
#
# QUAL SERIE E "O TOTAL". Sao quatro niveis no CSV, e escolher errado erra o
# grafico inteiro. O que o PAF mira e "Estoque da DPF em Mercado", que no nosso
# dado se chama "DPF em poder do publico" -- e NAO inclui a carteira do Banco
# Central, R$ 2.971,0 bi em jun/2026. Somar a carteira do Bacen daria uma divida
# 32% maior do que a que o PAF persegue, e a banda pareceria estourada todo ano.
#
# CONFERIDO, e nao suposto: a coluna "realizado" do paf_bandas.csv bate com o nosso
# dezembro em 22 dos 23 anos ATE A PRIMEIRA CASA DECIMAL. O unico que discorda e
# 2003, por 0,95% -- numero antigo, republicado depois. E DPMFi + DPFe da o total
# em todos os 307 meses, com erro zero.
#
# DOIS PAINEIS, e nao dois eixos no mesmo. A externa era 31,0% da divida em
# set/2002 e hoje e 3,8%: num eixo so ela e uma linha viva no comeco da serie e um
# fio colado no chao no resto, e nas janelas curtas some de vez. Mas o proprio
# movimento dela e informacao -- de 222,5 para 349,2 bi em cinco anos, 57% de alta.
#
# A PRIMEIRA TENTATIVA FOI UM SEGUNDO EIXO A DIREITA, e ficou pior do que o
# problema: a linha da externa, esticada ate o topo da sua escala, passava por cima
# da linha do total e se lia como se a divida externa fosse a maior das tres. Um
# cruzamento que so existe no desenho e uma mentira que o leitor nao tem como
# desconfiar.
#
# Dois paineis empilhados, com o mesmo eixo do tempo: cada linha na sua escala, e
# nenhuma passa por cima de nenhuma. O de baixo e um terco da altura, porque a
# pergunta principal esta no de cima.
# ---------------------------------------------------------------------------

# O nivel que o PAF mira. O nome no CSV vem sem acento, do parser.
NIVEL_TOTAL = "DPF em poder do publico"

_COR_NIVEL = {"total": "#1f3864", "DPMFi": "#1f6feb", "DPFe": "#ed7d31"}


def dados_estoque_total(janela=None):
    """Estoque da DPF em mercado, e a quebra entre interna e externa, em R$ milhoes.

    Tres colunas: 'total', 'DPMFi' e 'DPFe'. O total e a linha PUBLICADA, e nao a
    soma que fariamos aqui -- as duas dao o mesmo em todos os 307 meses, e usar a
    publicada faz o teste que compara as duas ter alguma coisa para comparar.

    ARMADILHA: as linhas agregadas do CSV sao as que tem 'entidade' E 'titulo'
    vazios. Filtrar so por nivel traz tambem uma linha por titulo e uma por
    entidade, e o estoque sai multiplicado.
    """
    e = pd.read_csv(config.PROCESSED_DIR / "estoque_dpf.csv",
                    parse_dates=["data"])
    agregado = e[e["entidade"].isna() & e["titulo"].isna()]
    piv = agregado.pivot_table(index="data", columns="nivel",
                               values="valor_milhoes", aggfunc="sum")
    saida = pd.DataFrame({"total": piv[NIVEL_TOTAL],
                          "DPMFi": piv["DPMFi"],
                          "DPFe": piv["DPFe"]}).dropna(how="all")
    return estilo.recorta(saida, janela)


def desenha_estoque_total(dados, banda, fig):
    """Total e interna em cima, externa embaixo, com a banda do PAF no de cima.

    Recebe a FIGURA e nao um eixo, porque sao dois paineis -- o mesmo que
    vencimentos.desenha_cronograma e detentores.desenha_participacao ja fazem.

    A banda vale para o TOTAL, e a legenda diz isso: deixar o leitor supor que ela
    vale para a linha mais grossa qualquer que seja e como um grafico mente sem
    dizer nada falso.
    """
    cima, baixo = fig.subplots(2, 1, sharex=True,
                               gridspec_kw={"height_ratios": [3, 1],
                                            "hspace": 0.26})

    _banda_do_paf(dados, banda, cima)

    cima.plot(dados.index, dados["total"] / 1000, color=_COR_NIVEL["total"],
              lw=2.8, zorder=4, label="DPF em mercado")
    cima.plot(dados.index, dados["DPMFi"] / 1000, color=_COR_NIVEL["DPMFi"],
              lw=1.8, zorder=3, label="DPMFi \u2014 interna")
    baixo.plot(dados.index, dados["DPFe"] / 1000, color=_COR_NIVEL["DPFe"],
               lw=1.8, zorder=3, label="DPFe \u2014 externa")

    for eixo, coluna in ((cima, "total"), (cima, "DPMFi"), (baixo, "DPFe")):
        valor = dados[coluna].iloc[-1] / 1000
        eixo.annotate(estilo.num_br(valor, 0), xy=(dados.index[-1], valor),
                      xytext=(6, 0), textcoords="offset points", fontsize=9.5,
                      weight="bold", color=_COR_NIVEL[coluna], va="center",
                      zorder=5, annotation_clip=False)

    # A ESCALA ENQUADRA O DADO E A BANDA, e nao parte do zero a forca. Com o zero
    # cravado, a janela de 12 meses gastava 80% do painel em espaco vazio -- a
    # divida vai de 7,6 a 9,3 mil bi no periodo, e o movimento virava um risco
    # achatado no topo. Na serie completa o minimo e 654 bi contra um teto de
    # 10.300, entao o piso fica em 6% da altura e o grafico sai igual ao que
    # partiria do zero.
    #
    # O que torna isto honesto e a BANDA estar sempre dentro do quadro: ela e a
    # referencia contra a qual o nivel se le, e nao o zero.
    anos = range(dados.index.min().year, dados.index.max().year + 1)
    faixa = banda.reindex(anos)
    _enquadra(cima, [dados["total"] / 1000, dados["DPMFi"] / 1000,
                     faixa["minimo"], faixa["maximo"]])
    _enquadra(baixo, [dados["DPFe"] / 1000])

    cima.set_ylabel("R$ bilh\u00f5es")
    baixo.set_ylabel("R$ bilh\u00f5es")
    baixo.set_title("d\u00edvida externa (DPFe) \u2014 escala pr\u00f3pria, um trigesimo da "
                    "de cima", fontsize=9, loc="left",
                    color=estilo.COR["neutro"], pad=4)

    # O EIXO DO TEMPO PARA ONDE O DADO PARA. Sem isto o matplotlib folga os dois
    # lados, e na janela de 12 meses o quadro ia de jan/25 a jan/27 para desenhar
    # jul/25 a jul/26 -- metade da largura em branco. A folga a direita fica so a
    # que o rotulo do ultimo valor precisa.
    folga = (dados.index[-1] - dados.index[0]) * 0.06
    for eixo in (cima, baixo):
        eixo.set_xlim(dados.index[0], dados.index[-1] + folga)
        eixo.grid(axis="y", alpha=0.25)
        eixo.set_axisbelow(True)
    estilo.eixo_anual(baixo, a_cada=2)

    cima.legend(ncol=2, frameon=False, loc="upper left",
                title="faixa vermelha: meta do PAF para o estoque da DPF em "
                      "mercado")


def _enquadra(ax, series, folga=0.10):
    """Limites do eixo y que cabem tudo, com folga, e nunca abaixo de zero."""
    valores = pd.concat([pd.Series(s).dropna() for s in series])
    baixo, alto = float(valores.min()), float(valores.max())
    margem = (alto - baixo) * folga or max(alto * 0.1, 1.0)
    ax.set_ylim(max(0.0, baixo - margem), alto + margem)


def _banda_do_paf(dados, banda, ax):
    """A faixa do PAF, ano a ano, no fundo do painel de cima.

    A banda ja vem em R$ BILHOES do paf_bandas.csv, e o eixo esta em bilhoes: nao
    ha conversao a fazer. A primeira versao multiplicava por 1000 e punha a faixa em
    9,7 milhoes de bilhoes, fora da figura. Ela simplesmente nao aparecia.
    """
    for ano in range(dados.index.min().year, dados.index.max().year + 1):
        if ano not in banda.index:
            continue
        inicio = pd.Timestamp(year=ano, month=1, day=1)
        fim = pd.Timestamp(year=ano, month=12, day=31)
        ax.fill_between([inicio, fim], banda.loc[ano, "minimo"],
                        banda.loc[ano, "maximo"], color=estilo.COR["banda"],
                        alpha=0.13, linewidth=0, zorder=1)
        # A banda ORIGINAL so vira pontilhado quando ela de fato mudou. Em 2018 e
        # 2024 houve "revisao" que repetiu os mesmos numeros, e desenhar as duas
        # poria um pontilhado exatamente sobre a borda da faixa.
        if pd.isna(banda.loc[ano, "minimo_original"]):
            continue
        mudou = (banda.loc[ano, "minimo_original"] != banda.loc[ano, "minimo"]
                 or banda.loc[ano, "maximo_original"] != banda.loc[ano, "maximo"])
        if mudou:
            for nivel in ("minimo_original", "maximo_original"):
                ax.plot([inicio, fim], [banda.loc[ano, nivel]] * 2,
                        color=estilo.COR["banda"], lw=0.8, ls=":", zorder=2)


# ---------------------------------------------------------------------------
# O DV01 DO ESTOQUE, por indexador.
#
# Quanto a divida perde de valor num choque de +1 ponto-base em toda a curva. O
# grafico de composicao ao lado diz quanto da divida esta em cada indexador; este
# diz quanto do RISCO DE TAXA esta em cada um, e os dois numeros nao se parecem:
#
#   indexador        % do estoque   % do DV01
#   Taxa Flutuante          54,3%        0,0%
#   Indice de Precos        23,3%       74,5%
#   Prefixado               22,4%       25,5%
#
# A LFT e mais da metade da divida e nao carrega risco de taxa nenhum -- o cupom
# acompanha a Selic, e o PU nao anda com a curva. E a NTN-B, com um quarto do
# estoque, carrega tres quartos do risco, porque e onde estao os prazos longos.
#
# DE ONDE VEM O NUMERO: dv_por_papel.csv, coluna 'dv_posicao_milhoes', que e o DV
# unitario vezes a posicao, ISIN a ISIN. A serie e MENSAL e comeca em jan/2010 --
# nao ha DV antes disso, e o dashboard do RMD vai a 2000. As janelas do dashboard
# recortam esta serie como recortam as outras; a "completa" aqui e 2010 em diante.
#
# CONFERIDO: as quantidades do dv_por_papel batem com a aba 2.2 vencimento a
# vencimento, em todos os papeis, com razao 1,000. E o financeiro sem DV -- linhas
# que ficaram sem taxa e portanto sem preco -- e 0,00% do financeiro nao-LFT em
# TODAS as 198 datas. Nao ha buraco escondido nesta soma.
#
# O SINAL. dv_posicao_milhoes vem na convencao de P&L, negativa: alta de taxa faz
# quem carrega perder. Aqui se desenha o MODULO, e o eixo diz "perda num choque de
# +1 bp" -- que e a mesma informacao dita do lado de quem pergunta "de quanto e o
# meu risco". Ver docs/convencoes-dv.md antes de mexer nisto.
# ---------------------------------------------------------------------------

# Qual papel entra em qual indexador. A LFT entra de proposito, com DV zero: ela
# ser mais da metade da divida e nao carregar risco de taxa E a informacao.
INDEXADOR_DO_PAPEL = {"LTN": "Prefixado", "NTN-F": "Prefixado",
                      "NTN-B": "\u00cdndice Pre\u00e7os", "NTN-C": "\u00cdndice Pre\u00e7os",
                      "LFT": "Taxa Flutuante"}

# A LFT SAIU DAQUI em 21/08/2026. Ela era uma linha reta em zero ao longo de toda a
# serie -- verdadeira, e ruido: "so esta poluindo", disse a dona do projeto. O fato
# de ela ser 54,3% do estoque e 0,0% do DV01 continua dito, no texto do grafico, que
# e onde se le um numero que nao muda.
#
# O total nao se altera com a saida: a LFT somava zero.
ORDEM_DO_DV = ["\u00cdndice Pre\u00e7os", "Prefixado"]


# Quais ganham linha de duration. A LFT fica fora -- ver dados_dv_do_estoque.
DURATION_DE = ["\u00cdndice Pre\u00e7os", "Prefixado"]


def dados_dv_do_estoque(janela=None):
    """DV01 da carteira por indexador, em R$ milhoes por ponto-base.

    Uma coluna por indexador mais 'total'. Em MODULO -- ver o cabecalho da secao.

    ARMADILHA: a LFT nao tem dv_unitario, e somar com min_count=1 devolveria NaN
    para ela e apagaria a linha. Ela vale ZERO, que e diferente de "nao sei", e o
    grafico precisa mostrar o zero.
    """
    d = pd.read_csv(config.PROCESSED_DIR / "dv_por_papel.csv",
                    parse_dates=["data"])
    d["indexador"] = d["titulo"].map(INDEXADOR_DO_PAPEL)
    faltando = sorted(set(d.loc[d["indexador"].isna(), "titulo"]))
    if faltando:
        raise LookupError(
            f"papel sem indexador em INDEXADOR_DO_PAPEL: {faltando}. Sem isso ele "
            f"sai do grafico em silencio, e o DV total fica menor do que e.")

    piv = d.pivot_table(index="data", columns="indexador",
                        values="dv_posicao_milhoes", aggfunc="sum").fillna(0.0)
    piv = piv.abs()
    for coluna in ORDEM_DO_DV:
        if coluna not in piv.columns:
            piv[coluna] = 0.0
    piv = piv[ORDEM_DO_DV]
    piv["total"] = piv.sum(axis=1)

    # A DURATION SAI DE GRACA do que ja esta calculado. Por definicao,
    # DV01 = -PU x duration modificada x 0,0001, entao a duration da carteira e
    # o DV01 dela dividido pelo valor de mercado, vezes 10.000.
    #
    # PONDERADA PELO VALOR DE MERCADO, que e a unica ponderacao correta. Ponderar
    # por quantidade somaria uma LTN de R$ 481 com uma NTN-B de R$ 4.031 como se
    # pesassem o mesmo, e a duration sairia puxada para o papel barato.
    #
    # A LFT NAO ENTRA no painel de duration. DV zero sobre valor positivo da
    # duration zero, que e verdade e nao ajuda: ela nao tem duration de taxa, tem
    # duration de credito, e desenhar uma linha em zero ao lado de duas linhas
    # reais convida a comparar coisas que nao se comparam.
    com_preco = d[d["pu"].notna() & d["dv_posicao_milhoes"].notna()
                  & (d["quantidade_mil"] > 0)].copy()
    com_preco["mtm_milhoes"] = (com_preco["pu"] * com_preco["quantidade_mil"]
                                * 1000 / 1e6)
    for coluna in DURATION_DE:
        g = com_preco[com_preco["indexador"] == coluna]
        dv = g.groupby("data")["dv_posicao_milhoes"].sum()
        mtm = g.groupby("data")["mtm_milhoes"].sum()
        piv["dur " + coluna] = (-dv / mtm * 10000).reindex(piv.index)

    return estilo.recorta(piv, janela)


def desenha_dv_do_estoque(dados, fig):
    """DV01 em cima, duration da carteira embaixo, no mesmo eixo do tempo.

    OS DOIS JUNTOS PORQUE CONTAM O CONTRARIO UM DO OUTRO. O DV01 da NTN-B triplicou
    desde 2010 e a duration dela ENCOLHEU -- de 8,77 anos em out/2019 para 5,57
    hoje. O risco cresceu por TAMANHO e nao por prazo: e mais divida, mais curta.
    Separados em dois graficos, essa leitura nao acontece.

SEM MEDIA MOVEL. Uma de tres meses foi tentada em 21/08/2026 e recusada por quem
    le: "nao serviu para nada". E o desenho concorda com ela -- a serie de DV01 e
    mensal e ja e suave, porque o estoque muda por leilao e por vencimento, e nao
    por preco. Alisar o que ja e liso so acrescenta uma linha para o olho separar.

    Recebe a FIGURA, como desenha_estoque_total.
    """
    cima, baixo = fig.subplots(2, 1, sharex=True,
                               gridspec_kw={"height_ratios": [2, 1],
                                            "hspace": 0.26})

    for coluna in ["total"] + ORDEM_DO_DV:
        cor = _COR_DA_LINHA_DO_DV(coluna)
        cima.plot(dados.index, dados[coluna], color=cor,
                  lw=2.8 if coluna == "total" else 1.8,
                  zorder=4 if coluna == "total" else 3, label=coluna)
        _rotulo_do_fim(cima, dados, coluna, cor, 0)

    for coluna in DURATION_DE:
        baixo.plot(dados.index, dados["dur " + coluna], lw=1.8,
                   color=estilo.COR[_CHAVE_COR[coluna]], label=coluna)
        _rotulo_do_fim(baixo, dados, "dur " + coluna,
                       estilo.COR[_CHAVE_COR[coluna]], 2)

    cima.set_ylabel("R$ milh\u00f5es por ponto-base")
    cima.set_ylim(0, dados["total"].max() * 1.12)
    baixo.set_ylabel("anos")
    duracoes = dados[["dur " + c for c in DURATION_DE]]
    baixo.set_ylim(0, duracoes.max().max() * 1.15)
    baixo.set_title("duration modificada da carteira, ponderada pelo valor de "
                    "mercado \u2014 a LFT n\u00e3o entra, n\u00e3o tem duration de taxa",
                    fontsize=9, loc="left", color=estilo.COR["neutro"], pad=4)

    folga = (dados.index[-1] - dados.index[0]) * 0.06
    for eixo in (cima, baixo):
        eixo.set_xlim(dados.index[0], dados.index[-1] + folga)
        eixo.grid(axis="y", alpha=0.25)
        eixo.set_axisbelow(True)
    estilo.eixo_anual(baixo, a_cada=2)

    cima.legend(ncol=3, frameon=False, loc="upper left",
                title="quanto a carteira perde num choque de +1 bp em toda a "
                      "curva")


def _COR_DA_LINHA_DO_DV(coluna):
    return "#1f3864" if coluna == "total" else estilo.COR[_CHAVE_COR[coluna]]


def _rotulo_do_fim(ax, dados, coluna, cor, casas):
    """O ultimo valor da linha, escrito na ponta dela."""
    valor = dados[coluna].iloc[-1]
    if pd.isna(valor):
        return
    ax.annotate(estilo.num_br(valor, casas), xy=(dados.index[-1], valor),
                xytext=(6, 0), textcoords="offset points", fontsize=9.5,
                weight="bold", color=cor, va="center", annotation_clip=False)


# ---------------------------------------------------------------------------
# DE ONDE VEM A VARIACAO DO DV01 NO MES.
#
# A pergunta e da dona do projeto, e ela ja trouxe a resposta em duas partes:
# muda o preco do que ja esta em carteira, e muda a carteira.
#
# A CONTA E EXATA, e nao uma aproximacao. Para cada ISIN, com dv positivo
# (magnitude) e q a posicao:
#
#   DECAY    = [dv(t, taxa e VNA de t-1) - dv(t-1)] x q(t-1)
#   PRECO    = [dv(t)                    - dv(t, taxa e VNA de t-1)] x q(t-1)
#   EMISSAO  = [q(t) - q(t-1)] x dv(t),  quando a posicao CRESCEU
#   RESGATE  = [q(t) - q(t-1)] x dv(t),  quando a posicao CAIU
#
# Somando, o termo do meio se cancela duas vezes e sobra dv(t)q(t) - dv(t-1)q(t-1),
# que e a variacao. Nao ha residuo de cruzamento escondido em lugar nenhum -- um
# teste confere isso mes a mes, nos 197.
#
# O DECAY E MEDIDO REPRECIFICANDO, e nao estimado por duration: reprecificar cada
# papel na data nova com a taxa e o VNA VELHOS e a "Conta B" da spec. Congelar o
# VNA importa: o IPCA corrigindo o VNA aumenta o DV01 sem que nada tenha mudado no
# risco, e isso pertence a PRECO e nao a decay.
#
# ARMADILHA: papel que aparece so num dos dois meses. Se nasceu, e emissao inteira;
# se sumiu, e resgate inteiro. Atribuir a diferenca a preco poria uma coluna enorme
# de "marcacao" no mes em que uma NTN-B venceu.
#
# ARMADILHA 2: papel sem taxa num dos dois meses. Ele nao tem DV medido, entao a
# variacao dele nao e atribuivel a nada -- e some da conta, deixando a soma das
# partes menor do que a variacao. Aconteceu em 10 dos 197 meses, ate 7,3 milhoes
# por bp. Em vez de esconder, vira a sua propria coluna: "sem taxa no mes".
#
# A LFT NAO ENTRA, como no grafico de cima: DV zero em todos os meses, e as quatro
# colunas dela seriam quatro zeros.
# ---------------------------------------------------------------------------

FATORES = ["decay", "pre\u00e7o", "emiss\u00e3o", "resgate", "sem taxa"]

_COR_DO_FATOR = {"decay": "#8faadc", "pre\u00e7o": "#ed7d31",
                 "emiss\u00e3o": "#2ca02c", "resgate": "#c00000",
                 "sem taxa": "#c9c9c9"}

# A conta reprecifica cada papel de cada mes: sao ~8 mil chamadas a precificacao,
# e a pagina desenha o mesmo grafico em quatro janelas. Sem cache, quatro vezes.
_DECOMPOSICAO_EM_CACHE = {}


def dados_variacao_do_dv(janela=None):
    """Variacao mensal do DV01, aberta em decay, preco, emissao e resgate.

    Em R$ milhoes por ponto-base, e em MAGNITUDE: positivo e risco ENTRANDO na
    carteira. Ver o cabecalho da secao para a algebra e para as duas armadilhas.
    """
    if not _DECOMPOSICAO_EM_CACHE:
        _DECOMPOSICAO_EM_CACHE["tudo"] = _calcula_decomposicao()
    return estilo.recorta(_DECOMPOSICAO_EM_CACHE["tudo"], janela)


def _calcula_decomposicao():
    from .. import calendario, precificacao

    cal = calendario.padrao()
    d = pd.read_csv(config.PROCESSED_DIR / "dv_por_papel.csv",
                    parse_dates=["data", "vencimento"])
    d = d[d["titulo"] != "LFT"].copy()
    d["dvpos"] = -d["dv_unitario"]
    d["qtd"] = d["quantidade_mil"] * 1000

    datas = sorted(d["data"].unique())
    linhas = []
    for anterior, atual in zip(datas[:-1], datas[1:]):
        a = d[d["data"] == anterior].set_index("isin")
        b = d[d["data"] == atual].set_index("isin")
        parte = dict.fromkeys(FATORES, 0.0)

        # SORTED, e nao o set cru: a ordem de iteracao de um set de strings
        # depende do PYTHONHASHSEED, e soma de float nao e associativa. Sem isto
        # o mesmo dado dava SVGs diferentes em processos diferentes -- e o
        # test_o_html_e_reprodutivel_entre_processos pegou.
        for isin in sorted(set(a.index) | set(b.index)):
            ra = a.loc[isin] if isin in a.index else None
            rb = b.loc[isin] if isin in b.index else None
            antes = 0.0 if ra is None or pd.isna(ra["dvpos"]) else (
                ra["dvpos"] * ra["qtd"])
            depois = 0.0 if rb is None or pd.isna(rb["dvpos"]) else (
                rb["dvpos"] * rb["qtd"])

            if ra is None:
                parte["emiss\u00e3o"] += depois
                continue
            if rb is None:
                parte["resgate"] -= antes
                continue
            if pd.isna(ra["dvpos"]) or pd.isna(rb["dvpos"]):
                # Sem DV num dos dois meses: nao da para dizer de onde veio.
                parte["sem taxa"] += depois - antes
                continue

            congelado = precificacao.dv(
                cal, ra["titulo"], pd.Timestamp(atual).date(),
                ra["vencimento"].date(), ra["taxa_pct"] / 100,
                None if pd.isna(ra["vna"]) else ra["vna"])
            if congelado is None:
                parte["sem taxa"] += depois - antes
                continue
            congelado = -congelado

            parte["decay"] += (congelado - ra["dvpos"]) * ra["qtd"]
            parte["pre\u00e7o"] += (rb["dvpos"] - congelado) * ra["qtd"]
            dq = rb["qtd"] - ra["qtd"]
            parte["emiss\u00e3o" if dq >= 0 else "resgate"] += dq * rb["dvpos"]

        linha = {f: parte[f] / 1e6 for f in FATORES}
        linha["variacao"] = ((b["dvpos"] * b["qtd"]).sum()
                              - (a["dvpos"] * a["qtd"]).sum()) / 1e6
        linha["data"] = pd.Timestamp(atual)
        linhas.append(linha)

    return pd.DataFrame(linhas).set_index("data")


def desenha_variacao_do_dv(dados, ax):
    """Barras empilhadas por mes, com a variacao liquida marcada por cima.

    EMPILHADA foi a sugestao dela, e e a certa: as partes SOMAM a variacao, e barra
    empilhada e o desenho que diz "isto soma aquilo". Lado a lado diria "compare
    estes", que e outra pergunta.

    Positivas para cima e negativas para baixo, cada lado com a sua base. Empilhar
    tudo a partir do zero misturaria os sinais e a altura da pilha deixaria de
    querer dizer alguma coisa.
    """
    largura = 20 if len(dados) > 40 else 24
    cima = pd.Series(0.0, index=dados.index)
    baixo = pd.Series(0.0, index=dados.index)
    for fator in FATORES:
        valores = dados[fator].fillna(0.0)
        positivo = valores.clip(lower=0)
        negativo = valores.clip(upper=0)
        ax.bar(dados.index, positivo, bottom=cima, width=largura,
               color=_COR_DO_FATOR[fator], label=fator, zorder=2)
        ax.bar(dados.index, negativo, bottom=baixo, width=largura,
               color=_COR_DO_FATOR[fator], zorder=2)
        cima = cima + positivo
        baixo = baixo + negativo

    ax.plot(dados.index, dados["variacao"], color="#111111", lw=0, marker="_",
            markersize=6, markeredgewidth=1.6, label="varia\u00e7\u00e3o do m\u00eas",
            zorder=4)
    ax.axhline(0, color="#333333", lw=0.9, zorder=3)

    ax.set_ylabel("R$ milh\u00f5es por ponto-base")
    # FOLGA NO TOPO PARA A LEGENDA. Ela tem seis entradas e mora dentro do quadro;
    # sem folga, ela deita sobre as barras mais altas -- que sao justamente os
    # meses que se quer olhar. A folga sai da pilha positiva mais alta, e nao de um
    # numero cravado, senao ela some quando a escala muda de janela.
    pilha = cima.max()
    fundo = baixo.min()
    ax.set_ylim(fundo * 1.08, max(pilha, 1.0) * 1.42)
    estilo.eixo_anual(ax, a_cada=2)
    ax.grid(axis="y", alpha=0.25)
    ax.set_axisbelow(True)
    folga = (dados.index[-1] - dados.index[0]) * 0.02
    ax.set_xlim(dados.index[0] - folga, dados.index[-1] + folga)
    ax.legend(ncol=6, frameon=False, loc="upper left", fontsize=9,
              title="de onde veio a mudan\u00e7a do DV01 no m\u00eas \u2014 as cinco "
                    "colunas somam a varia\u00e7\u00e3o, exatamente")
