"""A pagina de emissoes: os graficos de leilao da entrega 3.

Pagina PROPRIA, e nao um grupo dentro do dashboard do RMD. O motivo e medido: sao
treze graficos, e cada um pede duas janelas e as combinacoes de compra e segunda
volta. A matriz inteira daria 104 SVGs e 15,6 MB, contra o limiar de 10 que a spec
fixou -- e engordaria a pagina do RMD sem necessidade, porque quem olha uma
raramente olha a outra ao mesmo tempo.

O QUE ESTA PAGINA NAO FAZ, e e decisao a tomar: as combinacoes de compra e segunda
volta ficam FORA do HTML. Duas janelas ja sao 26 SVGs e 3,9 MB; as quatro
combinacoes seriam 15,6 MB. Elas existem na linha de comando -- cada rodada gera a
pagina de um recorte -- e a versao gravada por padrao e "so venda, com segunda
volta", que e a leitura de quanto risco entrou no mercado.

Trocar isso por caixas de marcar no proprio HTML exige interatividade de verdade
(desenhar no navegador em vez de embutir SVG pronto), que e a decisao adiada da
secao 10 da spec do dashboard.
"""
import pandas as pd

from . import dashboard, emissao

GRUPOS = ["Por dia de leil\u00e3o", "Por semana", "Quantidade e taxa"]

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


def _fig_qtd_taxa(recorte, com_2a, dispersao=False):
    def figura(janela):
        fig = dashboard._figura(6.4 if dispersao else 5.6)
        dados = emissao.quantidade_e_taxa(recorte, janela, com_2a)
        if dispersao:
            emissao.desenha_taxa_contra_quantidade(
                dados, fig.subplots(),
                f"{recorte} \u00b7 taxa contra quantidade, cada ponto \u00e9 um dia")
        else:
            emissao.desenha_quantidade_e_taxa(
                dados, fig.subplots(),
                f"{recorte} \u00b7 quantidade aceita e taxa m\u00e9dia")
        return fig
    return figura


# As quatro combinacoes, com o arquivo de cada uma. Cada pagina diz qual e, e aponta
# para as outras tres: sem isso, quem abre uma nao sabe que as outras existem.
COMBINACOES = [
    (False, True, "emissoes.html", "s\u00f3 venda, com 2\u00aa volta"),
    (False, False, "emissoes-1a-volta.html", "s\u00f3 venda, s\u00f3 1\u00aa volta"),
    (True, True, "emissoes-com-compra.html", "venda e compra, com 2\u00aa volta"),
    (True, False, "emissoes-com-compra-1a-volta.html",
     "venda e compra, s\u00f3 1\u00aa volta"),
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
            True, "5 anos", _fig_dois_eixos(com_compra=com_compra, com_2a=com_2a, recorte="NTN-B")),
    Grafico("emissao_ntnb_curta", "Por dia de leil\u00e3o",
            "NTN-B curta \u00b7 financeiro e DV",
            "leiloes.csv e dv_emitido_por_leilao.csv",
            "At\u00e9 5 anos de prazo na emiss\u00e3o \u2014 <b>corte provis\u00f3rio</b>, "
            "esperando a defini\u00e7\u00e3o do Tesouro. O dado gravado carrega o "
            "v\u00e9rtice que ele mesmo publica (3, 5, 7, 10, 15, 20, 25, 30, 35 e 40 "
            f"anos), ent\u00e3o mudar a fronteira \u00e9 uma linha. {nota_aceito}",
            True, "5 anos", _fig_dois_eixos(com_compra=com_compra, com_2a=com_2a, recorte="NTN-B curta")),
    Grafico("emissao_ntnb_longa", "Por dia de leil\u00e3o",
            "NTN-B longa \u00b7 financeiro e DV",
            "leiloes.csv e dv_emitido_por_leilao.csv",
            f"Acima de 5 anos. {nota_aceito} {_NOTA_DV}",
            True, "5 anos", _fig_dois_eixos(com_compra=com_compra, com_2a=com_2a, recorte="NTN-B longa")),
    Grafico("emissao_ntnf", "Por dia de leil\u00e3o",
            "NTN-F \u00b7 financeiro e DV",
            "leiloes.csv e dv_emitido_por_leilao.csv",
            f"{nota_aceito} {_NOTA_DV}",
            True, "5 anos", _fig_dois_eixos(com_compra=com_compra, com_2a=com_2a, recorte="NTN-F")),
    Grafico("emissao_ltn", "Por dia de leil\u00e3o",
            "LTN \u00b7 financeiro e DV",
            "leiloes.csv e dv_emitido_por_leilao.csv",
            f"{nota_aceito} {_NOTA_DV}",
            True, "5 anos", _fig_dois_eixos(com_compra=com_compra, com_2a=com_2a, recorte="LTN")),
    Grafico("emissao_pre", "Por dia de leil\u00e3o",
            "LTN + NTN-F \u00b7 financeiro e DV",
            "leiloes.csv e dv_emitido_por_leilao.csv",
            f"O prefixado inteiro. {nota_aceito} {_NOTA_DV}",
            True, "5 anos", _fig_dois_eixos(com_compra=com_compra, com_2a=com_2a, recorte="LTN + NTN-F")),
    Grafico("emissao_lft", "Por dia de leil\u00e3o",
            "LFT \u00b7 s\u00f3 financeiro",
            "leiloes.csv",
            "A LFT n\u00e3o tem DV, por decis\u00e3o de modelagem da entrega 2 "
            "(premissa de duration zero) \u2014 ent\u00e3o o segundo eixo n\u00e3o "
            "existe, e a m\u00e9dia m\u00f3vel de 3 meses entra no lugar dele. "
            f"{nota_aceito}",
            True, "5 anos", _fig_lft(com_compra, com_2a)),
    Grafico("emissao_semanal", "Por semana",
            "Soma da semana \u00b7 financeiro e DV",
            "dv_emitido_por_leilao.csv",
            "Sem a LFT: o gr\u00e1fico tem dois eixos e ela s\u00f3 tem um dos dois "
            f"n\u00fameros. {nota_aceito} {_NOTA_DV}",
            True, "5 anos", _fig_semanal(com_compra, com_2a)),
    Grafico("emissao_empilhado", "Por semana",
            "Financeiro da semana, por papel",
            "leiloes.csv",
            "Aqui a LFT <b>entra</b>: \u00e9 gr\u00e1fico de financeiro s\u00f3, e ela "
            f"\u00e9 mais da metade dele. {nota_aceito}",
            True, "5 anos", _fig_empilhado(com_compra, com_2a)),
    Grafico("qtd_taxa_pre_linha", "Quantidade e taxa",
            "LTN + NTN-F \u00b7 quantidade e taxa (op\u00e7\u00e3o A: duas s\u00e9ries)",
            "leiloes.csv",
            "Mesmo idioma dos gr\u00e1ficos de dois eixos acima. A taxa \u00e9 a "
            "m\u00e9dia <b>ponderada pelo financeiro</b> do dia \u2014 a simples "
            "trataria um lote de 100 milh\u00f5es e um de 10 bilh\u00f5es como iguais.",
            True, "5 anos", _fig_qtd_taxa("LTN + NTN-F", com_2a)),
    Grafico("qtd_taxa_pre_disp", "Quantidade e taxa",
            "LTN + NTN-F \u00b7 taxa contra quantidade (op\u00e7\u00e3o B: "
            "dispers\u00e3o)",
            "leiloes.csv",
            "Cada ponto \u00e9 um dia de leil\u00e3o; a cor \u00e9 o ano. Responde "
            "outra pergunta: o Tesouro coloca mais quando a taxa est\u00e1 alta? Num "
            "gr\u00e1fico de duas s\u00e9ries isso s\u00f3 apareceria por acaso.",
            True, "5 anos", _fig_qtd_taxa("LTN + NTN-F", com_2a, dispersao=True)),
    Grafico("qtd_taxa_ntnb_linha", "Quantidade e taxa",
            "NTN-B \u00b7 quantidade e taxa (op\u00e7\u00e3o A: duas s\u00e9ries)",
            "leiloes.csv",
            "A taxa da NTN-B \u00e9 <b>real</b>, e as duas s\u00e9ries dividem o dia "
            "com v\u00e9rtices muito diferentes \u2014 a m\u00e9dia ponderada mistura "
            "3 e 40 anos numa linha s\u00f3.",
            True, "5 anos", _fig_qtd_taxa("NTN-B", com_2a)),
    Grafico("qtd_taxa_ntnb_disp", "Quantidade e taxa",
            "NTN-B \u00b7 taxa contra quantidade (op\u00e7\u00e3o B: dispers\u00e3o)",
            "leiloes.csv",
            "Aqui a dispers\u00e3o mostra o regime mudando de lugar na nuvem: a taxa "
            "real sai de 5% em 2023 para 8% em 2026, e o tamanho do lote quase "
            "n\u00e3o acompanha.",
            True, "5 anos", _fig_qtd_taxa("NTN-B", com_2a, dispersao=True)),
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
    d = pd.read_csv(caminho, usecols=lambda c: c in ("estagio", "data_leilao"))
    if "estagio" not in d.columns:
        return ""

    partes = []
    for estagio, texto in (
        ("ofertado",
         "<b>ofertado, ainda n\u00e3o aceito</b> \u2014 a barra \u00e9 um <b>teto</b>: "
         "a quantidade anunciada, que historicamente cai para 83,9% dela, e a taxa "
         "\u00e9 a do leil\u00e3o anterior do mesmo papel. Aparece com contorno claro"),
        ("aceito",
         "<b>aceito, ainda n\u00e3o na planilha</b> \u2014 a quantidade j\u00e1 \u00e9 "
         "final, mas a taxa publicada na hora pode ser preliminar, e ent\u00e3o o "
         "DV01 muda. Aparece hachurado"),
    ):
        dias = sorted(set(d.loc[d["estagio"] == estagio, "data_leilao"].astype(str)))
        if not dias:
            continue
        quais = ", ".join(dia[:10] for dia in dias)
        partes.append(f"<li>{quais}: {texto}.</li>")

    if not partes:
        return ""
    return ('<div id="provisorio">'
            "<b>Provis\u00f3rio nesta p\u00e1gina:</b>"
            "<ul>" + "".join(partes) + "</ul>"
            "Cada linha some sozinha quando o momento seguinte chegar."
            "</div>")


def grava(caminho=None, recortes=None, com_compra=False, com_2a=True):
    """Grava UMA das quatro paginas e devolve o caminho."""
    from .. import config

    arquivo = next((a for c, v, a, _ in COMBINACOES
                    if c == com_compra and v == com_2a), "emissoes.html")
    caminho = caminho or (config.PROCESSED_DIR / arquivo)
    rotulo = next(r for c, v, _, r in COMBINACOES
                  if c == com_compra and v == com_2a)

    escrito = dashboard.grava(caminho, recortes, registro(com_compra, com_2a),
                              GRUPOS, f"Emiss\u00f5es e DV01 \u00b7 {rotulo}")
    # A barra entra depois da montagem, logo antes do <main>: assim o montador do
    # dashboard continua sem saber que existem quatro paginas.
    html = escrito.read_text(encoding="utf-8")
    html = html.replace(
        "<main>",
        _barra_das_combinacoes(arquivo) + "\n" + _aviso_do_provisorio() + "\n<main>",
        1)
    html = html.replace("</style>",
                        _CSS_COMBINACOES + _CSS_PROVISORIO + "</style>", 1)
    escrito.write_text(html, encoding="utf-8")
    return escrito


def grava_as_quatro(recortes=None):
    """Grava as quatro combinacoes. Devolve a lista de caminhos."""
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
