"""A pagina de emissoes: os graficos de leilao da entrega 3.

Pagina PROPRIA, e nao um grupo dentro do dashboard do RMD -- quem olha uma raramente
olha a outra ao mesmo tempo, e a matriz de graficos daqui engordaria aquela sem
necessidade.

O QUE FOI CORTADO EM 20/08/2026, e por que. A primeira versao oferecia todas as
opcoes e nao decidia nenhuma: 13 graficos x 5 janelas x 4 paginas = 260 SVGs.
Guardar as duas versoes de um grafico "para decidir depois" e uma forma de nunca
decidir, e o custo era medido.

  - a janela COMPLETA saiu. Ela sozinha custava 5,9 MB dos 9,67 da pagina -- 61% do
    arquivo -- para desenhar 702 barras de um pixel, em que nada se le. A serie
    longa fica no dashboard do RMD, que e onde ela tem sentido;
  - as janelas passaram a ser CURTAS, porque leilao se move em semanas e nao em
    anos: 20 leiloes, no ano, 12 meses, desde o ano anterior, 5 anos;
  - de QUANTIDADE E TAXA sobrou so a dispersao. A versao de duas series repetia o
    idioma de dois eixos que ja aparece sete vezes na pagina; a dispersao responde
    uma pergunta que nenhum outro grafico responde -- o Tesouro coloca mais quando
    a taxa esta alta?
  - das quatro combinacoes de compra e segunda volta sobraram TRES. A que saiu e
    "venda e compra, so 1a volta": recompra sem segunda volta e o recorte de que
    ninguem sentiu falta.

Sao 11 graficos x 5 janelas x 3 paginas = 165 SVGs, e cada pagina fica em ~4,8 MB.

O QUE ESTA PAGINA CONTINUA NAO FAZENDO: as combinacoes de compra e segunda volta sao
tres ARQUIVOS, e nao caixas de marcar no HTML. Poe-las na mesma pagina exige
interatividade de verdade (desenhar no navegador em vez de embutir SVG pronto), que
e a decisao adiada da secao 10 da spec do dashboard. Os arquivos ficam ligados por
uma barra de links relativos no topo, que funciona com duplo clique e sem servidor.
"""
import pandas as pd

from . import dashboard, emissao, estilo

GRUPOS = ["Por dia de leil\u00e3o", "Por semana", "Demanda",
          "Taxa e risco"]

# AS JANELAS DO LEILAO SAO CURTAS, e as do dashboard do RMD nao servem aqui.
#
# Estoque de divida se move em anos; leilao se move em semanas. Em "5 anos" cabem
# umas 250 barras de tres pixels, e a barra de hoje -- a que motivou esta pagina
# existir -- some no meio delas.
#
# O CONTADOR E 20, E NAO 50, POR MEDICAO. O Tesouro leiloa quase toda semana, entao
# 50 leiloes sao ~50 semanas e a janela colapsa sobre "12 meses": medido na serie
# diaria de NTN-B, "50 leiloes" comeca em 19/08/2025 e "12 meses" em 12/08/2025 --
# um ponto de diferenca. Vinte da ~5 meses, que e uma janela de verdade.
#
# A escada sai com cada degrau ~1,5x o anterior (NTN-B por dia):
#   20 leiloes 20 | no ano 31 | 12 meses 51 | desde o ano anterior 82 | completa 702
#
# A ordem e do mais curto para o mais longo, que e a ordem em que se olha: primeiro
# o que aconteceu agora, depois o contexto.
JANELAS = (
    ("20 leil\u00f5es", estilo.Ultimos(20)),
    ("no ano", estilo.DesdeJaneiro(0)),
    ("12 meses", 1),
    ("desde o ano anterior", estilo.DesdeJaneiro(1)),
    ("5 anos", 5),
)

# A JANELA "COMPLETA" FOI CORTADA em 20/08/2026, e por medicao: ela sozinha custava
# 5,9 MB dos 9,67 da pagina -- 61% do arquivo -- para desenhar 702 barras de um
# pixel, em que nada se le. A serie longa continua no dashboard do RMD, que e onde
# ela tem sentido. Quem precisar dela aqui passa recortes=[("completa", None)].

# A janela que abre. "12 meses" e nao "20 leiloes": vinte leiloes sao ~5 meses e nao
# fecham um ciclo do PAF -- o ano rolado e a referencia com que ela compara. Quem
# quer so o que aconteceu agora troca num clique.
JANELA_PADRAO = "12 meses"

# NOS GRAFICOS SEMANAIS, um ponto e uma semana. Entao "20 leiloes" ali sao as
# ultimas 20 SEMANAS, e nao os ultimos 20 leiloes. Dito na nota daqueles dois
# graficos, para que o rotulo da janela nao minta em silencio.
_NOTA_SEMANAL = ("A janela <b>20 leil\u00f5es</b> conta pontos do gr\u00e1fico, e "
                 "aqui cada ponto \u00e9 uma <b>semana</b> \u2014 ent\u00e3o ela "
                 "mostra as \u00faltimas 20 semanas.")

# O eixo do DV aponta para CIMA por padrao: com ele para baixo, a linha mora no teto
# do grafico e a comparacao com a barra some. Os rotulos continuam negativos, entao o
# numero nao mente -- so a direcao de leitura muda. Ver as duas versoes em
# scratchpad/opcao_a_dv_para_baixo.png e opcao_b_dv_para_cima.png.
DV_PARA_CIMA = True

# O que a pagina gravada por padrao mostra.
COM_COMPRA = False
COM_SEGUNDA_VOLTA = True


def _fig_dois_eixos(recorte, com_compra, com_2a):
    def figura(janela):
        fig = dashboard._figura(5.6)
        dados = emissao.por_dia(recorte, janela, com_compra, com_2a)
        emissao.desenha_dois_eixos(dados, fig.subplots(),
                                   f"{recorte} \u00b7 por dia de leil\u00e3o")
        return fig
    return figura


def _fig_empilhado_por_dia(recorte, com_compra, com_2a):
    """Como _fig_dois_eixos, mas com a barra aberta por papel.

    Usado no recorte de prefixado: a barra somada de LTN + NTN-F esconde qual dos
    dois moveu o dia, e sao papeis de prazo muito diferente.
    """
    def figura(janela):
        fig = dashboard._figura(5.8)
        dados = emissao.por_dia_por_familia(recorte, janela, com_compra, com_2a)
        emissao.desenha_dois_eixos_empilhado(
            dados, fig.subplots(), f"{recorte} \u00b7 por dia, aberto por papel")
        return fig
    return figura


def _fig_acumulado(recorte, com_compra, com_2a, meses=3):
    def figura(janela):
        fig = dashboard._figura(4.8)
        dados = emissao.acumulado(recorte, meses, janela, com_compra, com_2a)
        emissao.desenha_acumulado(
            dados, fig.subplots(),
            f"{recorte} \u00b7 acumulado dos \u00faltimos {meses} meses", meses)
        return fig
    return figura


def _fig_lft(com_compra, com_2a):
    def figura(janela):
        fig = dashboard._figura(5.6)
        dados = emissao.por_dia("LFT", janela, com_compra, com_2a)
        emissao.desenha_lft(dados, fig.subplots())
        return fig
    return figura


def _fig_semanal(com_compra, com_2a):
    def figura(janela):
        fig = dashboard._figura(5.8)
        dados = emissao.por_semana_por_familia(janela, com_compra, com_2a)
        emissao.desenha_dois_eixos_empilhado(
            dados, fig.subplots(),
            "Soma da semana \u00b7 financeiro por papel e DV total, sem LFT")
        return fig
    return figura


def _fig_empilhado(com_compra, com_2a):
    def figura(janela):
        fig = dashboard._figura(5.6)
        dados = emissao.financeiro_semanal_por_papel(janela, com_compra, com_2a)
        emissao.desenha_empilhado(dados, fig.subplots())
        return fig
    return figura


def _fig_demanda(recorte, com_2a, em_dv=True):
    def figura(janela):
        fig = dashboard._figura(5.6)
        dados = emissao.demanda(recorte, janela, com_2a)
        emissao.desenha_demanda(
            dados, fig.subplots(),
            f"{recorte} \u00b7 ofertado e colocado, por dia de leil\u00e3o",
            em_dv=em_dv)
        return fig
    return figura


def _fig_colocado(com_2a, meses=6):
    def figura(janela):
        fig = dashboard._figura(5.2)
        dados = emissao.colocado_por_familia(janela, com_2a, meses)
        emissao.desenha_colocado_por_familia(dados, fig.subplots(), meses)
        return fig
    return figura


def _fig_dv_taxa(recorte, com_2a):
    def figura(janela):
        fig = dashboard._figura(6.0)
        dados = emissao.dv_e_taxa(recorte, janela, com_2a)
        emissao.desenha_taxa_contra_dv(
            dados, fig.subplots(),
            f"{recorte} \u00b7 taxa contra DV01 emitido, cada ponto \u00e9 um dia")
        return fig
    return figura


# As tres combinacoes, com o arquivo de cada uma. Cada pagina diz qual e, e aponta
# para as outras tres: sem isso, quem abre uma nao sabe que as outras existem.
COMBINACOES = [
    (False, True, "emissoes.html", "s\u00f3 venda, com 2\u00aa volta"),
    (False, False, "emissoes-1a-volta.html", "s\u00f3 venda, s\u00f3 1\u00aa volta"),
    (True, True, "emissoes-com-compra.html", "venda e compra, com 2\u00aa volta"),
]


def _nota_aceito(com_compra, com_2a):
    """A nota que diz, em cada pagina, qual recorte ela mostra."""
    compra = ("Inclui os leil\u00f5es de <b>compra</b>, com sinal negativo: o que se "
              "v\u00ea \u00e9 o l\u00edquido."
              if com_compra else
              "<b>S\u00f3 venda</b> \u2014 emiss\u00e3o bruta, sem as recompras.")
    volta = ("Inclui a <b>2\u00aa volta</b>, que \u00e9 a leitura de quanto risco entrou "
             "no mercado."
             if com_2a else
             "<b>S\u00f3 1\u00aa volta</b>, que \u00e9 a leitura do tamanho do leil\u00e3o no dia.")
    return ("Sempre o <b>aceito</b> no leil\u00e3o, nunca o ofertado. "
            + compra + " " + volta)

_NOTA_DV = ("O DV01 \u00e9 <b>negativo</b> por conven\u00e7\u00e3o do projeto "
            "(docs/convencoes-dv.md): pre\u00e7o cai quando a taxa sobe. O eixo da "
            "direita est\u00e1 invertido para que mais risco emitido suba junto com "
            "a barra; os r\u00f3tulos continuam negativos.")

Grafico = dashboard.Grafico


def registro(com_compra=False, com_2a=True):
    """As entradas da pagina, ja com a combinacao escolhida embutida.

    Funcao e nao constante porque cada combinacao de compra e segunda volta e
    uma pagina diferente: as figuras precisam nascer sabendo qual delas sao.
    """
    nota_aceito = _nota_aceito(com_compra, com_2a)
    return [
    Grafico("emissao_ntnb", "Por dia de leil\u00e3o",
            "NTN-B \u00b7 financeiro e DV",
            "dv_emitido_por_leilao.csv",
            f"Curta e longa somadas. {nota_aceito} {_NOTA_DV}",
            True, JANELA_PADRAO, _fig_dois_eixos("NTN-B", com_compra, com_2a)),
    Grafico("emissao_ntnb_acum", "Por dia de leil\u00e3o",
            "NTN-B \u00b7 acumulado de 3 meses",
            "dv_emitido_por_leilao.csv",
            "A s\u00e9rie di\u00e1ria \u00e9 serrilhada por constru\u00e7\u00e3o \u2014 ele "
            "leiloa NTN-B num dia e prefixado no outro, ent\u00e3o dia sim dia n\u00e3o "
            "a barra \u00e9 zero. A soma m\u00f3vel tira o serrilhado e mostra o que o "
            "trimestre acumulou, que \u00e9 a escala em que emiss\u00e3o se compara com "
            f"o PAF. {nota_aceito}",
            True, JANELA_PADRAO, _fig_acumulado("NTN-B", com_compra, com_2a)),
    Grafico("emissao_ntnb_curta", "Por dia de leil\u00e3o",
            "NTN-B curta \u00b7 financeiro e DV",
            "dv_emitido_por_leilao.csv",
            "At\u00e9 o v\u00e9rtice de 5 anos, pelo <b>benchmark publicado</b> pelo "
            "Tesouro e n\u00e3o pelo prazo calculado \u2014 um papel que ele chama de "
            "NTN-B 5 anos \u00e9 curta durante toda a vig\u00eancia, mesmo com 6,4 anos "
            f"a correr. {nota_aceito} {_NOTA_DV}",
            True, JANELA_PADRAO,
            _fig_dois_eixos("NTN-B curta", com_compra, com_2a)),
    Grafico("emissao_ntnb_longa", "Por dia de leil\u00e3o",
            "NTN-B longa \u00b7 financeiro e DV",
            "dv_emitido_por_leilao.csv",
            f"V\u00e9rtice de 7 anos para cima. {nota_aceito} {_NOTA_DV}",
            True, JANELA_PADRAO,
            _fig_dois_eixos("NTN-B longa", com_compra, com_2a)),
    Grafico("emissao_ntnf", "Por dia de leil\u00e3o",
            "NTN-F \u00b7 financeiro e DV",
            "dv_emitido_por_leilao.csv",
            f"{nota_aceito} {_NOTA_DV}",
            True, JANELA_PADRAO, _fig_dois_eixos("NTN-F", com_compra, com_2a)),
    Grafico("emissao_ltn", "Por dia de leil\u00e3o",
            "LTN \u00b7 financeiro e DV",
            "dv_emitido_por_leilao.csv",
            f"{nota_aceito} {_NOTA_DV}",
            True, JANELA_PADRAO, _fig_dois_eixos("LTN", com_compra, com_2a)),
    Grafico("emissao_pre", "Por dia de leil\u00e3o",
            "LTN + NTN-F \u00b7 financeiro por papel e DV total",
            "dv_emitido_por_leilao.csv",
            "O prefixado inteiro, com a barra <b>aberta por papel</b>: a barra "
            "somada esconderia qual dos dois moveu o dia, e eles t\u00eam prazos "
            f"muito diferentes. {nota_aceito} {_NOTA_DV}",
            True, JANELA_PADRAO,
            _fig_empilhado_por_dia("LTN + NTN-F", com_compra, com_2a)),
    Grafico("emissao_pre_acum", "Por dia de leil\u00e3o",
            "LTN + NTN-F \u00b7 acumulado de 3 meses",
            "dv_emitido_por_leilao.csv",
            f"A mesma soma m\u00f3vel da NTN-B, para o prefixado. {nota_aceito}",
            True, JANELA_PADRAO,
            _fig_acumulado("LTN + NTN-F", com_compra, com_2a)),
    Grafico("emissao_lft", "Por dia de leil\u00e3o",
            "LFT \u00b7 s\u00f3 financeiro",
            "dv_emitido_por_leilao.csv",
            "A LFT n\u00e3o tem DV por decis\u00e3o de modelagem, ent\u00e3o o segundo eixo "
            "n\u00e3o existe, e a m\u00e9dia m\u00f3vel de 3 meses entra no lugar dele. "
            f"{nota_aceito}",
            True, JANELA_PADRAO, _fig_lft(com_compra, com_2a)),
    Grafico("emissao_semanal", "Por semana",
            "Soma da semana \u00b7 financeiro por papel e DV total",
            "dv_emitido_por_leilao.csv",
            "Sem a LFT: o gr\u00e1fico tem dois eixos e ela s\u00f3 tem um dos dois "
            "n\u00fameros. A barra \u00e9 <b>empilhada por papel</b>; a linha do DV \u00e9 "
            f"o total da semana. {nota_aceito} {_NOTA_DV} {_NOTA_SEMANAL}",
            True, JANELA_PADRAO, _fig_semanal(com_compra, com_2a)),
    Grafico("emissao_empilhado", "Por semana",
            "Financeiro da semana, por papel",
            "dv_emitido_por_leilao.csv",
            "Aqui a LFT <b>entra</b>: \u00e9 gr\u00e1fico de financeiro s\u00f3, e ela "
            f"\u00e9 mais da metade dele. {nota_aceito} {_NOTA_SEMANAL}",
            True, JANELA_PADRAO, _fig_empilhado(com_compra, com_2a)),
    Grafico("demanda_resumo", "Demanda",
            "Fra\u00e7\u00e3o colocada, por papel",
            "dv_emitido_por_leilao.csv",
            "A pergunta que a emiss\u00e3o sozinha n\u00e3o responde: ele "
            "<b>n\u00e3o conseguiu colocar, ou n\u00e3o quis</b>? Uma barra "
            "baixa de emiss\u00e3o pode ser um dia em que ofertou pouco, ou um "
            "em que ofertou muito e o mercado n\u00e3o levou \u2014 e s\u00e3o "
            "coisas opostas. "
            "A fra\u00e7\u00e3o \u00e9 medida em <b>DV01</b>, n\u00e3o em "
            "quantidade: em quantidade, um lote de LTN de seis meses pesa igual a "
            "um de NTN-B de trinta anos. A LFT entra pela quantidade, porque "
            "n\u00e3o tem DV01. "
            "<b>Houve uma quebra em 2021</b>: a NTN-B longa saiu de 20,7% em 2020 "
            "para 80,9% em 2021, e est\u00e1 em 95,6% em 2026. Os dois lados "
            "mudaram \u2014 ele passou a leiloar o dobro de vezes (25 para 50 "
            "dias por ano), em lotes 44% menores, e a colocar quase tudo. "
            "N\u00e3o \u00e9 artefato do dado: \u00e9 mudan\u00e7a de "
            "estrat\u00e9gia.",
            True, JANELA_PADRAO, _fig_colocado(com_2a)),
    Grafico("demanda_ntnb", "Demanda",
            "NTN-B \u00b7 ofertado e colocado",
            "dv_emitido_por_leilao.csv",
            "A barra clara \u00e9 o que ele <b>ofertou</b>; a escura, dentro "
            "dela, o que <b>colocou</b>. O vazio que sobra em cima \u00e9 o que "
            "deixou de colocar, e \u00e9 o assunto. A linha vermelha \u00e9 a "
            "fra\u00e7\u00e3o, com 100% pontilhado. "
            "\u00c9 na NTN-B que o corte aparece \u2014 no prefixado a linha "
            "fica colada nos 95% e n\u00e3o h\u00e1 o que ver. "
            f"{nota_aceito}",
            True, JANELA_PADRAO, _fig_demanda("NTN-B", com_2a)),
    Grafico("dv_taxa_pre", "Taxa e risco",
            "LTN + NTN-F \u00b7 taxa contra DV01 emitido",
            "dv_emitido_por_leilao.csv",
            "Cada ponto \u00e9 um dia de leil\u00e3o; a cor \u00e9 o ano, e o c\u00edrculo "
            "vermelho \u00e9 o \u00faltimo. <b>O eixo era quantidade e passou a ser "
            "DV01</b>: a quantidade de t\u00edtulos mistura uma LTN de seis meses com "
            "uma NTN-F de 2037 como se fossem a mesma coisa, e a nuvem sa\u00eda sem "
            "forma. Com o risco no eixo, a pergunta vira a que interessa \u2014 com "
            "a taxa alta, ele coloca mais risco no mercado, ou menos?",
            True, JANELA_PADRAO, _fig_dv_taxa("LTN + NTN-F", com_2a)),
    Grafico("dv_taxa_ntnb", "Taxa e risco",
            "NTN-B \u00b7 taxa contra DV01 emitido",
            "dv_emitido_por_leilao.csv",
            "A taxa da NTN-B \u00e9 <b>real</b>. A dispers\u00e3o mostra o regime "
            "mudando de lugar na nuvem: a taxa real sai de 5% em 2023 para 8% em "
            "2026.",
            True, JANELA_PADRAO, _fig_dv_taxa("NTN-B", com_2a)),
    ]


def _uma_linha_do_estado():
    """A faixa do topo: QUAL o ultimo leilao no grafico, e o que ainda e provisorio.

    UMA LINHA, e nao um bloco. A versao anterior era uma lista com dois paragrafos
    explicando cada estagio, e ficou poluindo o topo de todas as paginas -- a
    explicacao de como funciona pertence ao texto de cada grafico, que e onde se le
    texto. Aqui so cabe o que muda todo dia: a data.
    """
    from .. import config

    caminho = config.PROCESSED_DIR / "dv_emitido_por_leilao.csv"
    if not caminho.exists():
        return ""
    d = pd.read_csv(caminho, usecols=lambda c: c in ("estagio", "data_leilao"))
    if d.empty:
        return ""
    if "estagio" not in d.columns:
        d["estagio"] = "planilha"

    ultimo = str(d["data_leilao"].max())[:10]
    partes = [f"\u00daltimo leil\u00e3o no gr\u00e1fico: <b>{_dia_br(ultimo)}</b>"]

    for estagio, texto in (("ofertado", "ofertado, ainda sem resultado"),
                           ("aceito", "aceito, ainda n\u00e3o confirmado pela "
                                      "planilha do Tesouro")):
        dias = sorted(set(d.loc[d["estagio"] == estagio, "data_leilao"].astype(str)))
        if dias:
            quais = ", ".join(_dia_br(x[:10]) for x in dias)
            partes.append(f"{quais}: {texto}")

    return ('<div id="estado">' + " \u00b7 ".join(partes) + "</div>")


def _dia_br(iso):
    """2026-08-20 -> 20/08/2026. Sem pandas: e uma string de dez caracteres."""
    if len(iso) != 10 or iso[4] != "-":
        return iso
    return f"{iso[8:10]}/{iso[5:7]}/{iso[0:4]}"


def grava(caminho=None, recortes=None, com_compra=False, com_2a=True):
    """Grava UMA das tres paginas e devolve o caminho."""
    from .. import config

    arquivo = next((a for c, v, a, _ in COMBINACOES
                    if c == com_compra and v == com_2a), "emissoes.html")
    caminho = caminho or (config.PROCESSED_DIR / arquivo)
    rotulo = next(r for c, v, _, r in COMBINACOES
                  if c == com_compra and v == com_2a)

    # As janelas do leilao, e nao as do dashboard do RMD: se recortes vier vazio,
    # quem manda e JANELAS daqui. Sem esta linha a pagina herdaria "5 anos" e
    # "completa", que e a escala de estoque.
    escrito = dashboard.grava(caminho, recortes or list(JANELAS),
                              registro(com_compra, com_2a),
                              GRUPOS, f"Emiss\u00f5es e DV01 \u00b7 {rotulo}",
                              extras=[(a, f"\u00b7 {r}")
                                      for _, _, a, r in COMBINACOES],
                              familia="emissoes.html")
    html = escrito.read_text(encoding="utf-8")
    html = html.replace("<main>", _uma_linha_do_estado() + "\n<main>", 1)
    html = html.replace("</style>", _CSS_PROVISORIO + "</style>", 1)
    escrito.write_text(html, encoding="utf-8")
    return escrito


def grava_todas(recortes=None):
    """Grava as tres combinacoes. Devolve a lista de caminhos."""
    return [grava(None, recortes, com_compra, com_2a)
            for com_compra, com_2a, _, _ in COMBINACOES]


_CSS_PROVISORIO = """
#estado { margin: 0 auto 16px; max-width: 1180px; font-size: 12.5px;
  color: var(--fraco); border-left: 3px solid #ccc; padding: 2px 0 2px 10px; }
#estado b { color: var(--tinta); }
"""

