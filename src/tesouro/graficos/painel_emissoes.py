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


def _fig_dois_eixos(recorte):
    def figura(janela):
        fig = dashboard._figura(5.6)
        dados = emissao.por_dia(recorte, janela, COM_COMPRA, COM_SEGUNDA_VOLTA)
        emissao.desenha_dois_eixos(dados, fig.subplots(),
                                   f"{recorte} \u00b7 por dia de leil\u00e3o",
                                   dv_para_cima=DV_PARA_CIMA)
        return fig
    return figura


def _fig_lft(janela):
    fig = dashboard._figura(5.6)
    dados = emissao.por_dia("LFT", janela, COM_COMPRA, COM_SEGUNDA_VOLTA)
    emissao.desenha_lft(dados, fig.subplots())
    return fig


def _fig_semanal(janela):
    fig = dashboard._figura(5.6)
    dados = emissao.por_semana(janela, COM_COMPRA, COM_SEGUNDA_VOLTA)
    emissao.desenha_dois_eixos(
        dados, fig.subplots(),
        "Soma da semana \u00b7 financeiro e DV, sem LFT",
        dv_para_cima=DV_PARA_CIMA)
    return fig


def _fig_empilhado(janela):
    fig = dashboard._figura(5.6)
    dados = emissao.financeiro_semanal_por_papel(janela, COM_COMPRA,
                                                 COM_SEGUNDA_VOLTA)
    emissao.desenha_empilhado(dados, fig.subplots())
    return fig


def _fig_qtd_taxa(recorte, dispersao=False):
    def figura(janela):
        fig = dashboard._figura(6.4 if dispersao else 5.6)
        dados = emissao.quantidade_e_taxa(recorte, janela, COM_SEGUNDA_VOLTA)
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


_NOTA_ACEITO = ("Sempre o <b>aceito</b> no leil\u00e3o, nunca o ofertado. "
                "S\u00f3 venda, com segunda volta \u2014 ver a nota do m\u00f3dulo "
                "sobre as outras combina\u00e7\u00f5es.")

_NOTA_DV = ("O DV01 \u00e9 <b>negativo</b> por conven\u00e7\u00e3o do projeto "
            "(docs/convencoes-dv.md): pre\u00e7o cai quando a taxa sobe. O eixo da "
            "direita est\u00e1 invertido para que mais risco emitido suba junto com "
            "a barra; os r\u00f3tulos continuam negativos.")

Grafico = dashboard.Grafico

REGISTRO = [
    Grafico("emissao_ntnb", "Por dia de leil\u00e3o",
            "NTN-B \u00b7 financeiro e DV",
            "leiloes.csv e dv_emitido_por_leilao.csv",
            f"Curta e longa somadas. {_NOTA_ACEITO} {_NOTA_DV}",
            True, "5 anos", _fig_dois_eixos("NTN-B")),
    Grafico("emissao_ntnb_curta", "Por dia de leil\u00e3o",
            "NTN-B curta \u00b7 financeiro e DV",
            "leiloes.csv e dv_emitido_por_leilao.csv",
            "At\u00e9 5 anos de prazo na emiss\u00e3o \u2014 <b>corte provis\u00f3rio</b>, "
            "esperando a defini\u00e7\u00e3o do Tesouro. O dado gravado carrega o "
            "v\u00e9rtice que ele mesmo publica (3, 5, 7, 10, 15, 20, 25, 30, 35 e 40 "
            f"anos), ent\u00e3o mudar a fronteira \u00e9 uma linha. {_NOTA_ACEITO}",
            True, "5 anos", _fig_dois_eixos("NTN-B curta")),
    Grafico("emissao_ntnb_longa", "Por dia de leil\u00e3o",
            "NTN-B longa \u00b7 financeiro e DV",
            "leiloes.csv e dv_emitido_por_leilao.csv",
            f"Acima de 5 anos. {_NOTA_ACEITO} {_NOTA_DV}",
            True, "5 anos", _fig_dois_eixos("NTN-B longa")),
    Grafico("emissao_ntnf", "Por dia de leil\u00e3o",
            "NTN-F \u00b7 financeiro e DV",
            "leiloes.csv e dv_emitido_por_leilao.csv",
            f"{_NOTA_ACEITO} {_NOTA_DV}",
            True, "5 anos", _fig_dois_eixos("NTN-F")),
    Grafico("emissao_ltn", "Por dia de leil\u00e3o",
            "LTN \u00b7 financeiro e DV",
            "leiloes.csv e dv_emitido_por_leilao.csv",
            f"{_NOTA_ACEITO} {_NOTA_DV}",
            True, "5 anos", _fig_dois_eixos("LTN")),
    Grafico("emissao_pre", "Por dia de leil\u00e3o",
            "LTN + NTN-F \u00b7 financeiro e DV",
            "leiloes.csv e dv_emitido_por_leilao.csv",
            f"O prefixado inteiro. {_NOTA_ACEITO} {_NOTA_DV}",
            True, "5 anos", _fig_dois_eixos("LTN + NTN-F")),
    Grafico("emissao_lft", "Por dia de leil\u00e3o",
            "LFT \u00b7 s\u00f3 financeiro",
            "leiloes.csv",
            "A LFT n\u00e3o tem DV, por decis\u00e3o de modelagem da entrega 2 "
            "(premissa de duration zero) \u2014 ent\u00e3o o segundo eixo n\u00e3o "
            "existe, e a m\u00e9dia m\u00f3vel de 3 meses entra no lugar dele. "
            f"{_NOTA_ACEITO}",
            True, "5 anos", _fig_lft),
    Grafico("emissao_semanal", "Por semana",
            "Soma da semana \u00b7 financeiro e DV",
            "dv_emitido_por_leilao.csv",
            "Sem a LFT: o gr\u00e1fico tem dois eixos e ela s\u00f3 tem um dos dois "
            f"n\u00fameros. {_NOTA_ACEITO} {_NOTA_DV}",
            True, "5 anos", _fig_semanal),
    Grafico("emissao_empilhado", "Por semana",
            "Financeiro da semana, por papel",
            "leiloes.csv",
            "Aqui a LFT <b>entra</b>: \u00e9 gr\u00e1fico de financeiro s\u00f3, e ela "
            f"\u00e9 mais da metade dele. {_NOTA_ACEITO}",
            True, "5 anos", _fig_empilhado),
    Grafico("qtd_taxa_pre_linha", "Quantidade e taxa",
            "LTN + NTN-F \u00b7 quantidade e taxa (op\u00e7\u00e3o A: duas s\u00e9ries)",
            "leiloes.csv",
            "Mesmo idioma dos gr\u00e1ficos de dois eixos acima. A taxa \u00e9 a "
            "m\u00e9dia <b>ponderada pelo financeiro</b> do dia \u2014 a simples "
            "trataria um lote de 100 milh\u00f5es e um de 10 bilh\u00f5es como iguais.",
            True, "5 anos", _fig_qtd_taxa("LTN + NTN-F")),
    Grafico("qtd_taxa_pre_disp", "Quantidade e taxa",
            "LTN + NTN-F \u00b7 taxa contra quantidade (op\u00e7\u00e3o B: "
            "dispers\u00e3o)",
            "leiloes.csv",
            "Cada ponto \u00e9 um dia de leil\u00e3o; a cor \u00e9 o ano. Responde "
            "outra pergunta: o Tesouro coloca mais quando a taxa est\u00e1 alta? Num "
            "gr\u00e1fico de duas s\u00e9ries isso s\u00f3 apareceria por acaso.",
            True, "5 anos", _fig_qtd_taxa("LTN + NTN-F", dispersao=True)),
    Grafico("qtd_taxa_ntnb_linha", "Quantidade e taxa",
            "NTN-B \u00b7 quantidade e taxa (op\u00e7\u00e3o A: duas s\u00e9ries)",
            "leiloes.csv",
            "A taxa da NTN-B \u00e9 <b>real</b>, e as duas s\u00e9ries dividem o dia "
            "com v\u00e9rtices muito diferentes \u2014 a m\u00e9dia ponderada mistura "
            "3 e 40 anos numa linha s\u00f3.",
            True, "5 anos", _fig_qtd_taxa("NTN-B")),
    Grafico("qtd_taxa_ntnb_disp", "Quantidade e taxa",
            "NTN-B \u00b7 taxa contra quantidade (op\u00e7\u00e3o B: dispers\u00e3o)",
            "leiloes.csv",
            "Aqui a dispers\u00e3o mostra o regime mudando de lugar na nuvem: a taxa "
            "real sai de 5% em 2023 para 8% em 2026, e o tamanho do lote quase "
            "n\u00e3o acompanha.",
            True, "5 anos", _fig_qtd_taxa("NTN-B", dispersao=True)),
]


def grava(caminho=None, recortes=None):
    """Grava a pagina de emissoes e devolve o caminho."""
    from .. import config

    caminho = caminho or (config.PROCESSED_DIR / "emissoes.html")
    return dashboard.grava(caminho, recortes, REGISTRO, GRUPOS,
                           "Emiss\u00f5es e DV01 \u00b7 vis\u00e3o de leil\u00e3o")
