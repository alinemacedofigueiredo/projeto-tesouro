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

GRUPOS = ["Por dia de leil\u00e3o", "Por semana", "Quantidade e taxa"]

# AS JANELAS DO LEILAO SAO CURTAS, e as do dashboard do RMD nao servem aqui.
#
# Estoque de divida se move em anos; leilao se move em semanas. Em "5 anos" cabem
# umas 250 barras de tres pixels, e a barra de hoje -- a que motivou esta pagina
# existir -- some no meio delas.
#
# O CONTADOR E 20, E NAO 50, POR MEDICAO. O Tesouro leiloa quase toda semana, entao
# 50 pregoes sao ~50 semanas e a janela colapsa sobre "12 meses": medido na serie
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

# A janela que abre. "12 meses" e nao "20 leiloes": vinte pregoes sao ~5 meses e nao
# fecham um ciclo do PAF -- o ano rolado e a referencia com que ela compara. Quem
# quer so o que aconteceu agora troca num clique.
JANELA_PADRAO = "12 meses"

# NOS GRAFICOS SEMANAIS, um ponto e uma semana. Entao "20 leiloes" ali sao as
# ultimas 20 SEMANAS, e nao os ultimos 20 pregoes. Dito na nota daqueles dois
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
                                   f"{recorte} \u00b7 por dia de leil\u00e3o",
                                   dv_para_cima=DV_PARA_CIMA)
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
        fig = dashboard._figura(5.6)
        dados = emissao.por_semana(janela, com_compra, com_2a)
        emissao.desenha_dois_eixos(
            dados, fig.subplots(),
            "Soma da semana \u00b7 financeiro e DV, sem LFT",
            dv_para_cima=DV_PARA_CIMA)
        return fig
    return figura


def _fig_empilhado(com_compra, com_2a):
    def figura(janela):
        fig = dashboard._figura(5.6)
        dados = emissao.financeiro_semanal_por_papel(janela, com_compra, com_2a)
        emissao.desenha_empilhado(dados, fig.subplots())
        return fig
    return figura


def _fig_qtd_taxa(recorte, com_2a):
    def figura(janela):
        fig = dashboard._figura(6.4)
        dados = emissao.quantidade_e_taxa(recorte, janela, com_2a)
        emissao.desenha_taxa_contra_quantidade(
            dados, fig.subplots(),
            f"{recorte} \u00b7 taxa contra quantidade, cada ponto \u00e9 um dia")
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
    """As treze entradas, ja com a combinacao escolhida embutida.

    Funcao e nao constante porque cada combinacao de compra e segunda volta e
    uma pagina diferente: as figuras precisam nascer sabendo qual delas sao.
    """
    nota_aceito = _nota_aceito(com_compra, com_2a)
    return [
    Grafico("emissao_ntnb", "Por dia de leil\u00e3o",
            "NTN-B \u00b7 financeiro e DV",
            "leiloes.csv e dv_emitido_por_leilao.csv",
            f"Curta e longa somadas. {nota_aceito} {_NOTA_DV}",
            True, JANELA_PADRAO, _fig_dois_eixos(com_compra=com_compra, com_2a=com_2a, recorte="NTN-B")),
    Grafico("emissao_ntnb_curta", "Por dia de leil\u00e3o",
            "NTN-B curta \u00b7 financeiro e DV",
            "leiloes.csv e dv_emitido_por_leilao.csv",
            "At\u00e9 5 anos de prazo na emiss\u00e3o \u2014 <b>corte provis\u00f3rio</b>, "
            "esperando a defini\u00e7\u00e3o do Tesouro. O dado gravado carrega o "
            "v\u00e9rtice que ele mesmo publica (3, 5, 7, 10, 15, 20, 25, 30, 35 e 40 "
            f"anos), ent\u00e3o mudar a fronteira \u00e9 uma linha. {nota_aceito}",
            True, JANELA_PADRAO, _fig_dois_eixos(com_compra=com_compra, com_2a=com_2a, recorte="NTN-B curta")),
    Grafico("emissao_ntnb_longa", "Por dia de leil\u00e3o",
            "NTN-B longa \u00b7 financeiro e DV",
            "leiloes.csv e dv_emitido_por_leilao.csv",
            f"Acima de 5 anos. {nota_aceito} {_NOTA_DV}",
            True, JANELA_PADRAO, _fig_dois_eixos(com_compra=com_compra, com_2a=com_2a, recorte="NTN-B longa")),
    Grafico("emissao_ntnf", "Por dia de leil\u00e3o",
            "NTN-F \u00b7 financeiro e DV",
            "leiloes.csv e dv_emitido_por_leilao.csv",
            f"{nota_aceito} {_NOTA_DV}",
            True, JANELA_PADRAO, _fig_dois_eixos(com_compra=com_compra, com_2a=com_2a, recorte="NTN-F")),
    Grafico("emissao_ltn", "Por dia de leil\u00e3o",
            "LTN \u00b7 financeiro e DV",
            "leiloes.csv e dv_emitido_por_leilao.csv",
            f"{nota_aceito} {_NOTA_DV}",
            True, JANELA_PADRAO, _fig_dois_eixos(com_compra=com_compra, com_2a=com_2a, recorte="LTN")),
    Grafico("emissao_pre", "Por dia de leil\u00e3o",
            "LTN + NTN-F \u00b7 financeiro e DV",
            "leiloes.csv e dv_emitido_por_leilao.csv",
            f"O prefixado inteiro. {nota_aceito} {_NOTA_DV}",
            True, JANELA_PADRAO, _fig_dois_eixos(com_compra=com_compra, com_2a=com_2a, recorte="LTN + NTN-F")),
    Grafico("emissao_lft", "Por dia de leil\u00e3o",
            "LFT \u00b7 s\u00f3 financeiro",
            "leiloes.csv",
            "A LFT n\u00e3o tem DV, por decis\u00e3o de modelagem da entrega 2 "
            "(premissa de duration zero) \u2014 ent\u00e3o o segundo eixo n\u00e3o "
            "existe, e a m\u00e9dia m\u00f3vel de 3 meses entra no lugar dele. "
            f"{nota_aceito}",
            True, JANELA_PADRAO, _fig_lft(com_compra, com_2a)),
    Grafico("emissao_semanal", "Por semana",
            "Soma da semana \u00b7 financeiro e DV",
            "dv_emitido_por_leilao.csv",
            "Sem a LFT: o gr\u00e1fico tem dois eixos e ela s\u00f3 tem um dos dois "
            f"n\u00fameros. {nota_aceito} {_NOTA_DV} {_NOTA_SEMANAL}",
            True, JANELA_PADRAO, _fig_semanal(com_compra, com_2a)),
    Grafico("emissao_empilhado", "Por semana",
            "Financeiro da semana, por papel",
            "leiloes.csv",
            "Aqui a LFT <b>entra</b>: \u00e9 gr\u00e1fico de financeiro s\u00f3, e ela "
            f"\u00e9 mais da metade dele. {nota_aceito} {_NOTA_SEMANAL}",
            True, JANELA_PADRAO, _fig_empilhado(com_compra, com_2a)),
    Grafico("qtd_taxa_pre_disp", "Quantidade e taxa",
            "LTN + NTN-F \u00b7 taxa contra quantidade",
            "leiloes.csv",
            "Cada ponto \u00e9 um dia de leil\u00e3o; a cor \u00e9 o ano. Responde "
            "outra pergunta: o Tesouro coloca mais quando a taxa est\u00e1 alta? Num "
            "gr\u00e1fico de duas s\u00e9ries isso s\u00f3 apareceria por acaso.",
            True, JANELA_PADRAO, _fig_qtd_taxa("LTN + NTN-F", com_2a)),
    Grafico("qtd_taxa_ntnb_disp", "Quantidade e taxa",
            "NTN-B \u00b7 taxa contra quantidade",
            "leiloes.csv",
            "Aqui a dispers\u00e3o mostra o regime mudando de lugar na nuvem: a taxa "
            "real sai de 5% em 2023 para 8% em 2026, e o tamanho do lote quase "
            "n\u00e3o acompanha.",
            True, JANELA_PADRAO, _fig_qtd_taxa("NTN-B", com_2a)),
    ]


def _barra_das_combinacoes(arquivo_atual):
    """A faixa no topo que diz qual recorte esta aberto e liga para os outros tres.

    Sao links relativos entre arquivos da mesma pasta, entao continuam funcionando
    com duplo clique e sem servidor -- que e a propriedade que o dashboard inteiro
    protege.
    """
    partes = ['<div id="combinacoes">', "  <span>recorte:</span>"]
    for _, _, arquivo, rotulo in COMBINACOES:
        if arquivo == arquivo_atual:
            partes.append(f'  <b class="atual">{rotulo}</b>')
        else:
            partes.append(f'  <a href="{arquivo}">{rotulo}</a>')
    partes.append("</div>")
    return "\n".join(partes)


def _nota_da_taxa(recorte, estagio):
    """De onde veio a taxa daquelas linhas: digitada, emprestada, ou as duas.

    So faz sentido no estagio da oferta. E precisa ser contada, e nao afirmada: ela
    digita a taxa de alguns papeis e deixa outros em branco, e uma frase fixa
    mentiria em metade dos dias.
    """
    if estagio != "ofertado":
        return ""
    supostas = int(recorte["taxa_suposta"].fillna(False).astype(bool).sum())
    total = len(recorte)
    if supostas == 0:
        return (". A <b>taxa \u00e9 sua</b>, digitada na planilha de entrada \u2014 "
                "s\u00f3 a quantidade \u00e9 que ainda vai cair")
    if supostas == total:
        return (". A taxa foi <b>emprestada</b> do leil\u00e3o anterior de cada "
                "papel, que erra 11 bp na mediana")
    return (f". Em {total - supostas} de {total} linhas a taxa \u00e9 sua; nas "
            f"outras {supostas} ela foi emprestada do leil\u00e3o anterior")


def _aviso_do_provisorio():
    """A faixa que aparece SO quando ha leilao provisorio na base.

    Ela diz a data do que ainda nao foi confirmado, e separa os dois momentos: o que
    ja aconteceu (aceito) e o que so foi anunciado (ofertado). A marca no grafico
    diz "esta barra e provisoria"; esta faixa diz QUAL DIA e EM QUE MOMENTO, e e
    isso que permite conferir contra a planilha quando ela sair.

    Quando nao ha nada provisorio, a faixa nao existe -- pagina de historico nao
    precisa de aviso sobre uma coisa que nao esta la, e um aviso permanente vira
    ruido que ninguem le quando importar.
    """
    from .. import config

    caminho = config.PROCESSED_DIR / "dv_emitido_por_leilao.csv"
    if not caminho.exists():
        return ""
    d = pd.read_csv(caminho, usecols=lambda c: c in ("estagio", "data_leilao",
                                                     "taxa_suposta"))
    if "estagio" not in d.columns:
        return ""
    if "taxa_suposta" not in d.columns:
        d["taxa_suposta"] = False

    partes = []
    for estagio, texto in (
        ("ofertado",
         "<b>ofertado, ainda n\u00e3o aceito</b> \u2014 a barra \u00e9 um "
         "<b>teto</b>: a quantidade anunciada, que historicamente cai para 83,9% "
         "dela. Aparece com contorno claro"),
        ("aceito",
         "<b>aceito, ainda n\u00e3o na planilha</b> \u2014 a quantidade j\u00e1 \u00e9 "
         "final, mas a taxa publicada na hora pode ser preliminar, e ent\u00e3o o "
         "DV01 muda. Aparece hachurado"),
    ):
        recorte = d[d["estagio"] == estagio]
        dias = sorted(set(recorte["data_leilao"].astype(str)))
        if not dias:
            continue
        quais = ", ".join(dia[:10] for dia in dias)
        partes.append(f"<li>{quais}: {texto}{_nota_da_taxa(recorte, estagio)}.</li>")

    if not partes:
        return ""
    return ('<div id="provisorio">'
            "<b>Provis\u00f3rio nesta p\u00e1gina:</b>"
            "<ul>" + "".join(partes) + "</ul>"
            "Cada linha some sozinha quando o momento seguinte chegar."
            "</div>")


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
                              GRUPOS, f"Emiss\u00f5es e DV01 \u00b7 {rotulo}")
    # A barra entra depois da montagem, logo antes do <main>: assim o montador do
    # dashboard continua sem saber que existem tres paginas.
    html = escrito.read_text(encoding="utf-8")
    html = html.replace(
        "<main>",
        _barra_das_combinacoes(arquivo) + "\n" + _aviso_do_provisorio() + "\n<main>",
        1)
    html = html.replace("</style>",
                        _CSS_COMBINACOES + _CSS_PROVISORIO + "</style>", 1)
    escrito.write_text(html, encoding="utf-8")
    return escrito


def grava_todas(recortes=None):
    """Grava as tres combinacoes. Devolve a lista de caminhos."""
    return [grava(None, recortes, com_compra, com_2a)
            for com_compra, com_2a, _, _ in COMBINACOES]


_CSS_PROVISORIO = """
#provisorio { margin: 0 auto 14px; max-width: 1180px; padding: 10px 14px;
  border-left: 4px solid #555; background: #f4f4f4; font-size: 0.92em;
  line-height: 1.45; color: #333; }
#provisorio ul { margin: 6px 0 6px 0; padding-left: 20px; }
#provisorio li { margin: 3px 0; }
"""

_CSS_COMBINACOES = """
#combinacoes { margin: 0 0 14px; font-size: 13px; display: flex;
               align-items: center; gap: 12px; flex-wrap: wrap; }
#combinacoes span { color: var(--fraco); }
#combinacoes a { color: var(--tinta); text-decoration: none;
                 border-bottom: 1px solid transparent; }
#combinacoes a:hover { border-bottom-color: var(--tinta); }
#combinacoes b.atual { color: var(--tinta); border-bottom: 2px solid var(--tinta);
                       padding-bottom: 1px; }
"""
