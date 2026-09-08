"""O registro dos dezesseis graficos e a montagem do HTML.

O registro e uma LISTA LITERAL, sem decorador e sem descoberta automatica: quem
abre este arquivo ve os dezesseis, em ordem, com grupo e fonte, e entende em trinta
segundos. A indirecao de um sistema de registro nao se paga para dezesseis itens, e
um decorador espalharia por dez arquivos a informacao que interessa junta.

O HTML e autocontido: os SVGs vao dentro dele. Abre com duplo clique, sem servidor,
e continua funcionando copiado para outra maquina ou mandado por e-mail -- num banco
isso vale mais que elegancia. O limiar de 10 MB e medido por teste; se estourar, os
SVGs saem para arquivos ao lado.

Quatorze dos vinte e um aceitam janela e um aceita variante, entao sao 37 SVGs. (A spec diz sete e 23 no
texto, mas a tabela da secao 5 marca nove; a tabela e que esta certa.)
"""

import collections
import io
import re

import matplotlib.pyplot as plt

from .. import config
from . import (custo, detentores, estilo, estoque, funding, leiloes, paf,
               prazo, reserva, vencimentos)

# 'variantes' e o segundo eixo de troca, alem da janela: um par
# (rotulo_da_caixa, (valor_desmarcado, valor_marcado)) ou None. Hoje so o custo usa,
# para incluir ou nao a DPFe. Um campo opcional custa menos que um sistema de opcoes,
# e a lista continua legivel de cima a baixo.
# 'recolhido' fecha a secao atras de uma setinha (<details>), aberta so por quem
# quiser o detalhe. Existe porque a quebra por papel sao quatro graficos densos que
# respondem a mesma pergunta do quinto: sem recolher, eles empurram metade do
# dashboard para baixo da dobra.
Grafico = collections.namedtuple(
    "Grafico",
    "id grupo titulo fonte nota janela padrao figura variantes recolhido")
Grafico.__new__.__defaults__ = (None, False)

# "Candidatos" deixou de existir em 19/08/2026: os tres que estavam la entraram nos
# grupos a que pertencem. Guardar grafico bom num apendice chamado "candidato" e uma
# forma de nunca decidir sobre ele.
# "O total" entrou em 21/08/2026 e vem PRIMEIRO de proposito: e a pergunta que
# antecede todas as outras da pagina -- de quanto e a divida, e ela esta onde o PAF
# prometeu? Sendo o primeiro grupo, e o unico que abre com a pagina.
# A ORDEM AQUI E A ORDEM DAS DUAS PAGINAS, e o REGISTRO segue a mesma -- um teste
# confere. Os cinco primeiros grupos sao a pagina do estoque; os tres ultimos, a de
# funding e detentores. Ver PAGINAS_DO_RMD.
GRUPOS = ["O total", "Estoque", "Vencimentos", "Prazo", "Custo",
          "Funding", "Detentores", "Reserva"]

# AS JANELAS DO DASHBOARD DO RMD. Eram duas -- "5 anos" e "completa" -- e cinco
# anos e muito para quem quer ver o que mudou no ano. Entraram "12 meses" e
# "3 anos" em 21/08/2026.
#
# Medido, porque cada janela multiplica o numero de SVGs embutidos: com as quatro o
# arquivo vai a 7,65 MB, contra 5,26 com duas e o limiar de 10 da spec. Uma quinta
# janela nao cabe.
JANELAS = (("12 meses", 1), ("3 anos", 3), ("5 anos", 5), ("completa", None))


def _figura(altura=6.2):
    fig = plt.figure(figsize=(13, altura))
    return fig


def _fig_net(janela):
    fig = _figura(8.0)
    funding.desenha_net(funding.dados_net(janela), fig)
    return fig


def _fig_emissao_indexador(janela):
    fig = _figura()
    funding.desenha_emissao_indexador(funding.dados_emissao_indexador(janela),
                                      fig.subplots())
    return fig


def _fig_emissao_anual(janela):
    # Este grafico conta ANOS, nao recorta datas: a janela de 5 anos vira cinco
    # barras, e a completa vira a serie inteira. A funcao de dado resolve as tres
    # formas de janela, inclusive o par (de, ate) do --de/--ate -- que antes caia
    # no ramo "completa" e deixava este painel num periodo diferente dos demais.
    dados = funding.dados_emissao_anual(janela, anos=100)
    fig = _figura()
    funding.desenha_emissao_anual(dados, fig.subplots(),
                                 funding.ultimo_mes_com_emissao().year)
    return fig


def _fig_estoque_total(janela):
    fig = _figura(6.6)
    estoque.desenha_estoque_total(estoque.dados_estoque_total(janela),
                                  paf.bandas("estoque_bilhoes"), fig)
    return fig


def _fig_dv_do_estoque(janela):
    fig = _figura(7.0)
    estoque.desenha_dv_do_estoque(estoque.dados_dv_do_estoque(janela), fig)
    return fig


def _fig_variacao_do_dv(janela):
    fig = _figura(7.2)
    estoque.desenha_variacao_do_dv(estoque.dados_variacao_do_dv(janela), fig)
    return fig


def _fig_composicao_100(janela):
    fig = _figura()
    estoque.desenha_composicao_100(estoque.dados_composicao(janela), fig.subplots())
    return fig


def _fig_composicao(janela):
    fig = _figura(6.8)
    bandas = {k: paf.bandas(k) for k in paf.COMPOSICAO}
    estoque.desenha_composicao(estoque.dados_composicao(janela), bandas,
                               fig.subplots())
    return fig


def _fig_participacao(janela):
    fig = _figura(8.4)
    detentores.desenha_participacao(detentores.dados_participacao(),
                                    detentores.dados_variacao(), fig)
    return fig


# Os quatro papeis cuja quebra por detentor a dona do projeto pediu. Sao os quatro
# que respondem por 98,9% do estoque -- OUTROS fica de fora porque e balde.
PAPEIS_COM_QUEBRA = ("LFT", "NTN-B", "LTN", "NTN-F")


def _fig_do_papel(papel):
    """Fabrica a funcao de figura de um papel.

    Uma funcao por papel, e nao uma funcao com parametro, porque o registro guarda
    callables de assinatura (janela) -- e porque assim cada entrada da lista
    literal continua legivel sozinha.
    """
    def figura(janela):
        fig = _figura(6.4)
        detentores.desenha_financeiro_do_papel(
            detentores.dados_financeiro_do_papel(papel, janela), fig, papel)
        return fig
    figura.__name__ = f"_fig_papel_{papel.replace('-', '').lower()}"
    return figura


def _fig_por_papel(janela):
    # 3.6 e nao 4.6: cinco roscas numa linha so nao ocupam a altura, e o vazio
    # entre elas e a legenda ficava maior que as proprias roscas.
    fig = _figura(3.6)
    detentores.desenha_por_papel(detentores.dados_por_papel(), fig)
    return fig


def _fig_financeiro_detentor(janela):
    fig = _figura(8.6)
    detentores.desenha_financeiro(detentores.dados_financeiro(janela), fig)
    return fig


def _fig_cronograma(janela):
    fig = _figura(9.0)
    vencimentos.desenha_cronograma(vencimentos.dados_cronograma_anual(),
                                   vencimentos.dados_cronograma_mensal(), fig)
    return fig


def _fig_faixas(janela):
    fig = _figura(8.0)
    vencimentos.desenha_faixas(vencimentos.dados_faixas(),
                               vencimentos.banda_vincendo_12m(), fig)
    return fig


def _fig_prazo(janela):
    fig = _figura()
    prazo.desenha_prazo(prazo.dados_prazo(), paf.bandas("prazo_medio_anos"),
                        fig.subplots())
    return fig


def _fig_estoque_de(familia):
    def figura(janela=None):
        dados = vencimentos.dados_estoque_por_vencimento()
        fig = _figura(vencimentos.altura_do_estoque(familia, dados))
        vencimentos.desenha_estoque_de(dados, fig.subplots(), familia)
        return fig
    return figura


def _fig_custo(janela, com_dpfe=False):
    fig = _figura()
    custo.desenha_custo(custo.dados_custo(janela, com_dpfe=com_dpfe),
                        fig.subplots())
    return fig


def _fig_reserva_13m(janela):
    fig = _figura(5.4)
    reserva.desenha_treze_meses(reserva.dados_treze_meses(), fig.subplots())
    return fig


def _fig_reserva(janela):
    fig = _figura()
    reserva.desenha_reserva(reserva.dados_reserva(janela), fig.subplots())
    return fig


def _fig_perfil_completo(janela):
    fig = _figura(6.6)
    vencimentos.desenha_perfil_completo(vencimentos.dados_perfil_completo(),
                                        fig.subplots(),
                                        vencimentos.excluido_do_perfil())
    return fig


def _fig_custo_emissao(janela):
    fig = _figura()
    custo.desenha_custo_emissao(custo.dados_custo_emissao(janela),
                                fig.subplots())
    return fig


def _fig_emissao_papel(janela):
    dados = leiloes.dados_emissao_anual_papel(janela, anos=100)
    fig = _figura()
    leiloes.desenha_emissao_anual_papel(
        dados, fig.subplots(), leiloes.ultima_competencia_do_rmd().year)
    return fig


REGISTRO = [
    Grafico("estoque_total", "O total",
            "O estoque da DPF, interna e externa, com a banda do PAF",
            "aba 2.1 e referencia/paf_bandas.csv",
            "<b>Quanto \u00e9 a d\u00edvida, e ela est\u00e2 onde o PAF prometeu.</b> A linha "
            "escura \u00e9 a DPF em mercado \u2014 a mesma que o PAF mira, e que "
            "<b>n\u00e3o inclui a carteira do Banco Central</b> (R$ 2.971,0 bi em "
            "jun/2026). A faixa vermelha \u00e9 a meta do ano; onde houve revis\u00e3o, "
            "a banda original aparece pontilhada. "
            "<b>A externa vai num painel pr\u00f3prio</b>, e n\u00e3o no mesmo eixo: ela "
            "era 31,0% da d\u00edvida em set/2002 e hoje \u00e9 3,8%, ent\u00e3o no eixo de "
            "cima seria um fio colado no ch\u00e3o \u2014 e o movimento dela \u00e9 "
            "informa\u00e7\u00e3o, de 222,5 para 349,2 bi em cinco anos. "
            "A escala enquadra o dado e a banda em vez de partir do zero: a "
            "refer@Encia contra a qual o n\u00edvel se l@E \u00e9 a banda, e n\u00e3o o zero.",
            True, "completa", _fig_estoque_total),
    Grafico("estoque_composicao", "Estoque",
            "Composi\u00e7\u00e3o da DPF por indexador, com a banda do PAF",
            "aba 2.1 e referencia/paf_bandas.csv",
            "Participa\u00e7\u00e3o de cada indexador na DPF. A banda \u00e9 a meta do PAF, ano "
            "a ano; onde houve revis\u00e3o, a banda original aparece pontilhada. "
            "Abre na s\u00e9rie completa: o c\u00e2mbio sai de 51,0% em set/2002 para 3,7%.",
            True, "completa", _fig_composicao),
    Grafico("estoque_composicao_100", "Estoque",
            "Composi\u00e7\u00e3o da DPF por indexador, em 100%",
            "aba 2.1",
            "A mesma s\u00e9rie do gr\u00e1fico acima, empilhada. O de linha responde onde "
            "estamos contra a meta do PAF; este responde de que a d\u00edvida \u00e9 feita \u2014 "
            "e \u00e9 nele que a queda do c\u00e2mbio se l\u00ea como o que foi: uma faixa que "
            "ocupava metade do gr\u00e1fico em 2002 e hoje \u00e9 um fio de 3,7%.",
            True, "completa", _fig_composicao_100),
    Grafico("dv_do_estoque", "Estoque",
            "DV01 e duration do estoque, por indexador",
            "dv_por_papel.csv",
            "<b>Quanto a carteira perde num choque de +1 ponto-base</b> em toda a "
            "curva, e <b>quantos anos de duration</b> ela carrega. "
            "O gr\u00e3fico acima diz quanto da d\u00edvida est\u00e3 em cada indexador; este "
            "diz quanto do <b>risco de taxa</b> est\u00e3 em cada um, e os dois "
            "n\u00fameros n\u00e3o se parecem: a <b>LFT \u00e9 54,3% do estoque e 0,0% do "
            "DV01</b> \u2014 o cupom acompanha a Selic e o PU n\u00e3o anda com a curva "
            "\u2014 enquanto a <b>NTN-B \u00e9 23,3% do estoque e 74,5% do DV01</b>, "
            "porque \u00e9 onde est\u00e3o os prazos longos \u2014 e a LFT, por isso mesmo, "
            "<b>n\u00e3o tem linha aqui</b>: seria uma reta em zero ao longo de "
            "dezesseis anos. "
            "<b>Os dois pain\u00e9is contam o contr\u00e3rio um do outro:</b> o DV01 da "
            "NTN-B triplicou desde 2010 e a duration dela <i>encolheu</i>, de "
            "8,77 anos em out/2019 para 5,57 hoje. O risco cresceu por "
            "<b>tamanho</b>, e n\u00e3o por prazo. "
            "A duration \u00e9 a modificada, ponderada pelo valor de mercado; a LFT "
            "n\u00e3o entra nela, porque n\u00e3o tem duration de taxa. "
            "A s\u00e9rie \u00e9 mensal e come\u00e7a em <b>jan/2010</b>: n\u00e3o h\u00e3 DV "
            "calculado antes disso, e por isso ela n\u00e3o vai a 2000 como as "
            "vizinhas. "
            "<b>Quatro pap\u00e9is ficam de fora</b>, porque n\u00e3o h\u00e3 taxa de mercado "
            "coletada para eles: NTN-C, NTN-B Principal, RendA+ e EducA+ \u2014 "
            "R$ 190,0 bi de estoque, ou cerca de <b>7,6% do DV01 verdadeiro</b>. "
            "Tr\u00eas dos quatro s\u00e3o Tesouro Direto, que esta p\u00e3gina n\u00e3o leva; a "
            "NTN-C fica de fora por falta de taxa, e sozinha vale perto de 2%. "
            "O sinal vem invertido do arquivo, na conven\u00e7\u00e3o de P&amp;L; aqui se "
            "desenha o m\u00f5dulo, do lado de quem pergunta de quanto \u00e9 o pr\u00f3prio "
            "risco.",
            True, "completa", _fig_dv_do_estoque),
    Grafico("variacao_do_dv", "Estoque",
            "De onde veio a mudan\u00e7a do DV01 no m\u00eas",
            "dv_por_papel.csv",
            "O gr\u00e1fico acima diz <b>de quanto \u00e9 o risco</b>; este diz "
            "<b>de onde veio a mudan\u00e7a dele</b>. Cada m\u00eas abre em quatro "
            "faixas que <b>somam a varia\u00e7\u00e3o exatamente</b> \u2014 n\u00e3o \u00e9 "
            "aproxima\u00e7\u00e3o \u2014 e o ponto branco marca o total do m\u00eas. "
            "O painel de baixo acumula essa varia\u00e7\u00e3o em <b>3 e em 12 meses</b>. "
            "<b>Decay</b> \u00e9 s\u00f3 a passagem do tempo: cada papel reprecificado no "
            "m\u00eas novo com a <i>taxa e o VNA velhos</i>. "
            "<b>Pre\u00e7o</b> \u00e9 o que sobrou. <b>Aten\u00e7\u00e3o: a corre\u00e7\u00e3o do VNA "
            "est\u00e1 em <i>pre\u00e7o</i>, e n\u00e3o em <i>decay</i></b> \u2014 o IPCA "
            "corrigindo o VNA aumenta o DV01 sem que o risco tenha mudado, e "
            "chamar isso de passagem do tempo misturaria indexa\u00e7\u00e3o com "
            "encurtamento. Por isso o VNA \u00e9 congelado no c\u00e1lculo do decay. "
            "<b>Emiss\u00e3o</b> e <b>resgate</b> s\u00e3o a carteira mudando de tamanho. "
            "<b>O que o gr\u00e1fico mostra \u00e9 uma m\u00e1quina de duas pe\u00e7as.</b> O "
            "decay tirou risco em <b>198 dos 198 meses</b> (m\u00e9dia de "
            "\u221212,1 milh\u00f5es por bp) e a emiss\u00e3o p\u00f3s risco em <b>198 dos "
            "198</b> (+17,4). A d\u00edvida ganha DV01 porque o Tesouro emite mais "
            "risco do que o tempo destr\u00f3i, e n\u00e3o porque o mercado se mexeu. "
            "<b>E os resgates mudam pouco</b>, como se esperava de papel que "
            "vence curto: m\u00e9dia de \u22121,0 contra os +17,4 da emiss\u00e3o. "
            "O <b>pre\u00e7o</b> \u00e9 quem faz o gr\u00e1fico balan\u00e7ar \u2014 sozinho, 65% do "
            "desvio-padr\u00e3o mensal. Em <b>mar\u00e7o de 2020</b> ele tirou 160,6 "
            "milh\u00f5es por bp num m\u00eas, a curva abrindo; em dezembro do mesmo ano "
            "devolveu 97,4. "
            "<b>A faixa cinza n\u00e3o est\u00e1 na legenda de prop\u00f3sito</b>, para n\u00e3o "
            "parecer um fator como os outros: ela \u00e9 res\u00edduo. S\u00e3o pap\u00e9is que "
            "<i>ganharam cota\u00e7\u00e3o</i> de um m\u00eas para o outro \u2014 LTN que nasceu "
            "fora do leil\u00e3o e depois entrou no calend\u00e1rio \u2014 e no m\u00eas da "
            "virada o DV01 delas aparece inteiro de uma vez, sem dar para dizer "
            "se veio de pre\u00e7o ou de quantidade. S\u00e3o <b>10 transi\u00e7\u00f5es em "
            "dezesseis anos</b>, a maior de 7,3 milh\u00f5es por bp em jan/2025. A "
            "faixa existe para a soma fechar; esconder res\u00edduo dentro de outra "
            "barra seria pior. "
            "Como no gr\u00e1fico acima, a <b>LFT n\u00e3o entra</b>.",
            True, "5 anos", _fig_variacao_do_dv),
    Grafico("estoque_lft", "Estoque",
            "LFT \u00b7 estoque por vencimento",
            "aba 2.2",
            "Um vencimento por linha, em ordem cronol\u00f3gica, com a "
            "<b>quantidade em t\u00edtulos</b> escrita na frente da "
            "barra \u2014 os gr\u00e1ficos de vencimento contam reais, "
            "e este conta pap\u00e9is. Dezessete vencimentos, quase todos de tamanho parecido \u2014 e o papel que ele rola com mais regularidade. "
            "<b>Sem os t\u00edtulos do Tesouro Direto</b>: um de "
            "LFT-TD1 vale R$ 10,68 e um de LFT, R$ 19.220 \u2014 "
            "somar os dois em quantidade n\u00e3o descreve nada.",
            False, None, _fig_estoque_de("LFT")),
    Grafico("estoque_ltn", "Estoque",
            "LTN \u00b7 estoque por vencimento",
            "aba 2.2",
            "Um vencimento por linha, em ordem cronol\u00f3gica, com a "
            "<b>quantidade em t\u00edtulos</b> escrita na frente da "
            "barra \u2014 os gr\u00e1ficos de vencimento contam reais, "
            "e este conta pap\u00e9is. Concentrada at\u00e9 2032: fora dela n\u00e3o h\u00e1 LTN nenhuma. Os picos de 01/2029 e 07/2029 s\u00e3o os dois maiores estoques em t\u00edtulos de toda a d\u00edvida. "
            "<b>Sem os t\u00edtulos do Tesouro Direto</b>: um de "
            "LFT-TD1 vale R$ 10,68 e um de LFT, R$ 19.220 \u2014 "
            "somar os dois em quantidade n\u00e3o descreve nada.",
            False, None, _fig_estoque_de("LTN")),
    Grafico("estoque_ntnf", "Estoque",
            "NTN-F \u00b7 estoque por vencimento",
            "aba 2.2",
            "Um vencimento por linha, em ordem cronol\u00f3gica, com a "
            "<b>quantidade em t\u00edtulos</b> escrita na frente da "
            "barra \u2014 os gr\u00e1ficos de vencimento contam reais, "
            "e este conta pap\u00e9is. Seis vencimentos s\u00f3, todos em 1\u00ba de janeiro \u2014 e o papel mais concentrado dos quatro. "
            "<b>Sem os t\u00edtulos do Tesouro Direto</b>: um de "
            "LFT-TD1 vale R$ 10,68 e um de LFT, R$ 19.220 \u2014 "
            "somar os dois em quantidade n\u00e3o descreve nada.",
            False, None, _fig_estoque_de("NTN-F")),
    Grafico("estoque_ntnb", "Estoque",
            "NTN-B \u00b7 estoque por vencimento",
            "aba 2.2",
            "Um vencimento por linha, em ordem cronol\u00f3gica, com a "
            "<b>quantidade em t\u00edtulos</b> escrita na frente da "
            "barra \u2014 os gr\u00e1ficos de vencimento contam reais, "
            "e este conta pap\u00e9is. Espalhada at\u00e9 2060, com quinze vencimentos. "
            "\u00c9 onde est\u00e1 o prazo da d\u00edvida. "
            "<b>S\u00f3 a NTN-B que paga cupom</b>: a NTN-B Principal, que n\u00e3o paga, "
            "divide sete destas quinze datas e aparecia como uma segunda barra na "
            "mesma linha do tempo. Ela n\u00e3o \u00e9 papel de leil\u00e3o \u2014 em 19.739 "
            "linhas de leil\u00e3o ela n\u00e3o aparece nenhuma vez \u2014 e sai junto com o "
            "resto do Tesouro Direto. S\u00e3o 35,1 milh\u00f5es de t\u00edtulos, "
            "R$ 91,5 bi. "
            "<b>Sem os t\u00edtulos do Tesouro Direto</b>: um de "
            "LFT-TD1 vale R$ 10,68 e um de LFT, R$ 19.220 \u2014 "
            "somar os dois em quantidade n\u00e3o descreve nada.",
            False, None, _fig_estoque_de("NTN-B")),
    Grafico("vencimentos_cronograma", "Vencimentos",
            "Cronograma de vencimentos",
            "aba 3.4",
            "Os 60 meses que a aba detalha (6.913,8 bi) mais o balde 'Ap\u00f3s 5 "
            "anos' (2.006,9 bi). 2026 \u00e9 jul\u2013dez e 2031 \u00e9 jan\u2013jun. "
            "<b>Inclui cupom:</b> a aba traz principal E juros, cada fluxo avaliado "
            "pelo pre\u00e7o da curva na data-base. \u00c9 por isso que h\u00e1 NTN-B em "
            "nov/26 e fev/27, meses em que nenhuma NTN-B vence.",
            False, None, _fig_cronograma),
    Grafico("vencimentos_faixas", "Vencimentos",
            "Composi\u00e7\u00e3o da DPF por horizonte, com a banda do PAF",
            "aba 3.1 e aba 5.7",
            "A banda do vincendo em 12 meses vem da aba 5.7 (2003 a 2022) e de "
            "referencia/paf_bandas.csv (2016 a 2026). Onde h\u00e1 revis\u00e3o, vale a "
            "revisada, que \u00e9 a que estava em vigor no fechamento.",
            False, None, _fig_faixas),
    Grafico("perfil_completo", "Vencimentos",
            "Perfil de vencimentos, papel a papel",
            "aba 2.2",
            "N\u00e3o considera as NTN-B1 (RendA+ e EducA+), 18,1 bi, que t\u00eam regra "
            "pr\u00f3pria de cupom e amortiza\u00e7\u00e3o. Sem elas o gr\u00e1fico termina em 2060: "
            "2064, 2069, 2074, 2079 e 2084 s\u00e3o RendA+ e mais nada. O total desenhado "
            "\u00e9 8.886,0 bi, contra 8.920,7 do cronograma. "
            "<b>Diferente do cronograma, este n\u00e3o inclui cupom:</b> a 2.2 aloca o "
            "estoque \u00e0 data de vencimento do papel, e o cupom pago antes disso n\u00e3o "
            "aparece. Para pagamento m\u00eas a m\u00eas, o cronograma \u00e9 a figura certa.",
            False, None, _fig_perfil_completo),
    Grafico("prazo_medio", "Prazo",
            "Prazo m\u00e9dio por n\u00edvel, com a banda do PAF",
            "aba 3.7 e referencia/paf_bandas.csv",
            "R\u00f3tulo na DPMFi e na DPFe; a DPF \u00e9 linha de contexto. A banda \u00e9 a "
            "meta do PAF para o prazo m\u00e9dio da DPF.",
            False, None, _fig_prazo),
    Grafico("custo_estoque", "Custo",
            "Custo do estoque contra a Selic e o IPCA",
            "abas 4.1 e 4.2, e vna.csv",
            "Custo acumulado em 12 meses. A Selic e o IPCA saem da varia\u00e7\u00e3o de 12 "
            "meses do nosso pr\u00f3prio VNA, e come\u00e7am em jan/2011. A DPFe fica fora por "
            "padr\u00e3o: ela \u00e9 d\u00edvida externa medida em real, ent\u00e3o carrega c\u00e2mbio e "
            "vai de -16,0% a +62,6% enquanto as outras duas vivem entre 10% e 14%. "
            "Marque a caixa para inclu\u00ed-la; o eixo se ajusta.",
            True, "5 anos", _fig_custo,
            ("incluir a DPFe", (False, True))),
    Grafico("custo_emissao", "Custo",
            "Custo de emiss\u00e3o contra o custo do estoque",
            "abas 4.2 e 4.3",
            "DPMFi. Emite-se a 14,20% e carrega-se a 13,19%: a d\u00edvida encarece "
            "sem que nenhuma decis\u00e3o nova seja tomada.",
            True, "5 anos", _fig_custo_emissao),
    Grafico("funding_net", "Funding",
            "Net do DPMFi, com m\u00e9dia m\u00f3vel e acumulado de 12 meses",
            "aba 1.1",
            "Emiss\u00e3o menos resgate do DPMFi, m\u00eas a m\u00eas. A barra \u00e9 <b>uma s\u00e9rie "
            "s\u00f3</b>, colorida pelo sinal \u2014 verde quando emitiu mais do que resgatou, "
            "vermelho no contr\u00e1rio \u2014 e n\u00e3o emiss\u00e3o contra resgate. A linha \u00e9 a "
            "m\u00e9dia m\u00f3vel de 3 meses. Cobre 100% do DPMFi.",
            True, "5 anos", _fig_net),
    Grafico("funding_indexador", "Funding",
            "Emiss\u00e3o do DPMFi por indexador, mensal",
            "aba 1.2",
            "Emiss\u00e3o bruta, em reais do m\u00eas. Cobre 100% da emiss\u00e3o do DPMFi.",
            True, "5 anos", _fig_emissao_indexador),
    Grafico("funding_anual", "Funding",
            "Composi\u00e7\u00e3o anual da emiss\u00e3o, em 100%",
            "aba 1.2",
            "Por indexador, e n\u00e3o por papel: pela aba 1.2 a cobertura \u00e9 100% da "
            "emiss\u00e3o, contra 93% a 97% se viesse dos leil\u00f5es. O ano ainda aberto "
            "leva asterisco.",
            True, "5 anos", _fig_emissao_anual),
    Grafico("emissao_papel", "Funding",
            "Composi\u00e7\u00e3o anual da emiss\u00e3o, por papel",
            "leiloes.csv",
            "A mesma forma do gr\u00e1fico acima, por <b>papel</b> em vez de indexador \u2014 "
            "e \u00e9 a\u00ed que est\u00e1 o que ele acrescenta: o prefixado de 40,3% em 2025 se "
            "abre em 33,1% de LTN e 9,2% de NTN-F, que t\u00eam prazo m\u00e9dio muito "
            "diferente. Vem dos leil\u00f5es, que s\u00e3o exatamente a Oferta P\u00fablica da aba "
            "1.1 \u2014 conferido ano a ano \u2014 e portanto n\u00e3o incluem Tesouro Direto "
            "nem emiss\u00e3o direta: 93% a 97% do total emitido.",
            True, "5 anos", _fig_emissao_papel, None, True),
    Grafico("detentores_participacao", "Detentores",
            "Participa\u00e7\u00e3o por grupo, e a varia\u00e7\u00e3o em 12 meses",
            "aba 2.7",
            "O formato da p\u00e1gina 7 do RMD: uma coluna de 100% por ano fechado, mais "
            "os dois \u00faltimos meses. Os oito detentores da aba agrupados em cinco. A "
            "varia\u00e7\u00e3o vai em <b>reais</b>, e n\u00e3o em pontos percentuais: participa\u00e7\u00e3o "
            "que cai com estoque subindo \u00e9 ru\u00eddo de composi\u00e7\u00e3o, n\u00e3o venda.",
            False, None, _fig_participacao),
    Grafico("detentores_papel", "Detentores",
            "Quem carrega cada papel",
            "aba 2.8",
            "Participa\u00e7\u00e3o de cada detentor dentro de cada papel, no \u00faltimo m\u00eas. "
            "R\u00f3tulo s\u00f3 nas fatias de 10% ou mais.",
            False, None, _fig_por_papel),
    Grafico("detentores_financeiro", "Detentores",
            "Financeiro por detentor, oito pain\u00e9is",
            "aba 2.8",
            "Cada painel tem escala pr\u00f3pria: os detentores diferem em ordem de "
            "grandeza. S\u00e9rie come\u00e7a em fev/2011, n\u00e3o em jan/2007 como a 2.7.",
            True, "5 anos", _fig_financeiro_detentor),
    Grafico("detentores_lft", "Detentores",
            "LFT: financeiro por detentor",
            "aba 2.8",
            "A mesma leitura do gr\u00e1fico acima, restrita \u00e0 LFT. Quem carrega o papel "
            "que responde por 51,2% do estoque.",
            True, "5 anos", _fig_do_papel("LFT"), None, True),
    Grafico("detentores_ntnb", "Detentores",
            "NTN-B: financeiro por detentor",
            "aba 2.8",
            "A mesma leitura, restrita \u00e0 NTN-B \u00b7 25,7% do estoque, e o papel em que "
            "a Previd\u00eancia concentra 44,9%.",
            True, "5 anos", _fig_do_papel("NTN-B"), None, True),
    Grafico("detentores_ltn", "Detentores",
            "LTN: financeiro por detentor",
            "aba 2.8",
            "A mesma leitura, restrita \u00e0 LTN \u00b7 14,4% do estoque.",
            True, "5 anos", _fig_do_papel("LTN"), None, True),
    Grafico("detentores_ntnf", "Detentores",
            "NTN-F: financeiro por detentor",
            "aba 2.8",
            "A mesma leitura, restrita \u00e0 NTN-F \u00b7 7,4% do estoque, e o papel com maior "
            "participa\u00e7\u00e3o estrangeira: 41,8%.",
            True, "5 anos", _fig_do_papel("NTN-F"), None, True),
    Grafico("reserva_13m", "Reserva",
            "Reserva de liquidez",
            "aba 6.1",
            "O formato da p\u00e1gina do RMD, para apresenta\u00e7\u00e3o. O eixo do \u00edndice "
            "come\u00e7a em zero.",
            False, None, _fig_reserva_13m),
    Grafico("reserva_serie", "Reserva",
            "Reserva de liquidez, s\u00e9rie longa com a folga",
            "aba 6.1",
            "A folga \u00e9 a reserva menos o valor prudencial. Em jan e fev/2015 ela "
            "foi negativa, e esses dois meses aparecem em vermelho.",
            True, "5 anos", _fig_reserva),
]

_CSS = """
:root { --tinta: #1a1a1a; --fraco: #666; --linha: #e3e3e3; --fundo: #fff; }
* { box-sizing: border-box; }
body { margin: 0; font-family: Segoe UI, Arial, sans-serif; color: var(--tinta);
       background: var(--fundo); }
#indice { position: fixed; top: 0; left: 0; width: 250px; height: 100vh;
          overflow-y: auto; border-right: 1px solid var(--linha);
          padding: 18px 14px 40px; font-size: 13.5px;
          background: var(--fundo); z-index: 30; }
#indice h1 { position: sticky; top: -18px; background: var(--fundo);
             padding: 4px 0 8px; z-index: 1; }
#indice h1 { font-size: 15px; margin: 0 0 4px; }
#indice .data { color: var(--fraco); font-size: 12px; margin-bottom: 14px; }
#indice .grupo { font-weight: 600; margin: 12px 0 4px; font-size: 12px;
                 text-transform: uppercase; letter-spacing: .04em;
                 color: var(--fraco); }
#indice a { display: block; color: var(--tinta); text-decoration: none;
            padding: 3px 0 3px 8px; border-left: 2px solid transparent; }
#indice a:hover { border-left-color: var(--tinta); }
main { margin-left: 250px; padding: 0 34px 60px; max-width: 1240px; }
/* O SVG de cada grafico nao pode passar da largura do conteudo: sem isto, um
   grafico largo empurra a pagina e cria rolagem horizontal, que e o que fazia o
   cabecalho parecer "travado" -- ele ficava preso a uma largura maior que a tela. */
section > div { max-width: 100%; overflow-x: auto; }
/* UM CABECALHO SO, e nao dois. Antes a barra de paginas ficava fora da area de
   conteudo e escorregava para debaixo do indice fixo, e o seletor de janela
   grudava sozinho no alto da tela -- duas faixas competindo pelo mesmo lugar.
   Agora e um bloco unico, grudado no topo, com a largura do conteudo.
   ATENCAO: nenhum comentario deste CSS pode conter tag entre sinais de menor e
   maior. Ele vai inteiro para dentro do HTML, e quem procurar a tag no arquivo
   acha o comentario primeiro -- foi o que quebrou a pagina do calendario. */
#topo { position: sticky; top: 0; z-index: 20; background: var(--fundo);
        padding: 10px 0 9px; margin-bottom: 6px;
        border-bottom: 1px solid var(--linha);
        display: flex; align-items: center; justify-content: space-between;
        gap: 18px; flex-wrap: wrap; }
/* AS DUAS FAIXAS NA MESMA LINHA. Empilhadas, o cabecalho grudado tinha 86px e
   comia um decimo da tela o tempo todo -- e um cabecalho fixo que ocupa tanto
   parece travado. Lado a lado ele cai para ~44px. Em tela estreita o flex-wrap
   os empilha de novo, que e quando o espaco justifica. */
#topo #paginas { margin: 0; flex: 1 1 auto; }
#topo #troca-periodo { position: static; padding: 0; border: 0;
                       background: transparent; flex: 0 0 auto; }
#troca-periodo { padding: 10px 0; }
#troca-periodo button { font: inherit; padding: 5px 14px; margin-right: 6px;
                        border: 1px solid var(--linha); background: #fff;
                        cursor: pointer; border-radius: 3px; }
#troca-periodo button.ativo { background: var(--tinta); color: #fff;
                              border-color: var(--tinta); }
section { margin: 34px 0 0; padding-top: 6px; }
section h2 { font-size: 17px; margin: 0 0 2px; }
.legenda { color: var(--fraco); font-size: 12.5px; margin: 6px 0 0;
           max-width: 900px; line-height: 1.45; }
.fonte { color: var(--fraco); font-size: 12px; margin: 2px 0 10px; }
svg { max-width: 100%; height: auto; }
label.variante { display: inline-flex; align-items: center; gap: 6px;
                 font-size: 12.5px; color: var(--fraco); margin: 0 0 6px;
                 cursor: pointer; user-select: none; }
label.variante input { cursor: pointer; }
section.recolhida { margin-top: 10px; }
section.recolhida summary { font-size: 15px; font-weight: 600; cursor: pointer;
                            padding: 7px 0; color: var(--tinta); }
section.recolhida summary:hover { text-decoration: underline; }
section.recolhida details[open] summary { margin-bottom: 8px; }
"""

# Escrito a mao, sem biblioteca -- a lista permitida do projeto nao tem nenhuma de
# JavaScript, e nem precisaria: trocar qual <div> esta visivel e tudo o que ha aqui.
#
# Dois eixos de troca. A JANELA e global (um botao no topo, vale para todos) e a
# VARIANTE e local (uma caixa dentro da secao). 'mostra' resolve os dois juntos.
#
# janelaAtiva comeca nula de proposito: enquanto ninguem toca no botao, cada grafico
# fica na janela em que foi gravado -- a composicao do estoque abre na serie
# completa e os demais em 5 anos, que e a decisao de projeto. Ler a janela do bloco
# visivel preserva isso.
_JS = """
var janelaAtiva = null;

function mostra(secao) {
  var blocos = secao.querySelectorAll('[data-grafico]');
  if (!blocos.length) { return; }

  var caixa = secao.querySelector('input.variante');
  var variante = caixa ? (caixa.checked ? caixa.dataset.sim : caixa.dataset.nao) : '';

  var visivel = null;
  blocos.forEach(function (b) {
    if (b.style.display !== 'none' && visivel === null) { visivel = b; }
  });
  var janela = janelaAtiva || (visivel ? visivel.dataset.janela : null);

  var candidatos = [];
  blocos.forEach(function (b) {
    if ((b.dataset.variante || '') === variante) { candidatos.push(b); }
  });
  if (!candidatos.length) { candidatos = Array.prototype.slice.call(blocos); }

  var alvo = null;
  candidatos.forEach(function (b) {
    if (b.dataset.janela === janela && alvo === null) { alvo = b; }
  });
  if (alvo === null) { alvo = candidatos[0]; }

  blocos.forEach(function (b) { b.style.display = (b === alvo) ? '' : 'none'; });
}

function trocaPeriodo(janela) {
  janelaAtiva = janela;
  document.querySelectorAll('section').forEach(mostra);
  document.querySelectorAll('#troca-periodo button').forEach(function (b) {
    b.classList.toggle('ativo', b.dataset.janela === janela);
  });
}

function trocaVariante(id) {
  mostra(document.getElementById(id));
}

// Clicar no indice numa secao recolhida levava ao titulo e mais nada: o <details>
// continuava fechado e o leitor via uma linha de texto onde esperava um grafico.
// Abre a secao que o endereco aponta, na carga e a cada clique no indice.
function abreSeApontada() {
  if (!location.hash) { return; }
  var secao = document.querySelector(location.hash);
  if (!secao) { return; }
  // O <details> DE DENTRO -- as quebras por papel, que sao recolhidas uma a uma.
  var caixa = secao.querySelector('details');
  if (caixa) { caixa.open = true; }
  // E os de FORA: desde que os grupos viraram recolhiveis, o alvo pode estar
  // dentro de um grupo fechado, e ai o link levava a uma secao invisivel.
  var acima = secao.parentElement;
  while (acima) {
    if (acima.tagName === 'DETAILS') { acima.open = true; }
    acima = acima.parentElement;
  }
  secao.scrollIntoView();
}

window.addEventListener('hashchange', abreSeApontada);
window.addEventListener('DOMContentLoaded', abreSeApontada);
"""


def _prefixa_ids(svg, prefixo):
    """Poe um prefixo em todo id do SVG e em toda referencia a ele.

    MEDIDO, nao suposto: com 25 SVGs no mesmo HTML, dois deles trazem o mesmo
    <clipPath id="pf677ba8d19">. Os ids do matplotlib sao derivados do conteudo, e
    dois paineis com a mesma caixa de recorte geram o mesmo hash. O navegador
    resolve url(#id) para o PRIMEIRO id do documento inteiro -- entao o recorte de
    um grafico passa a valer para o outro.

    Neste caso as duas definicoes eram identicas e o desenho nao mudaria. Mas isso
    e coincidencia, nao propriedade: basta um par de caixas diferentes com o mesmo
    hash para um grafico aparecer cortado. Prefixar torna a propriedade verdadeira
    em vez de deixa-la depender de sorte.
    """
    limpo = re.sub(r"[^A-Za-z0-9]+", "-", prefixo).strip("-")
    svg = re.sub(r'id="([^"]+)"', lambda m: 'id="%s-%s"' % (limpo, m.group(1)), svg)
    svg = re.sub(r"url\(#([^)]+)\)",
                 lambda m: "url(#%s-%s)" % (limpo, m.group(1)), svg)
    svg = re.sub(r'(xlink:href|href)="#([^"]+)"',
                 lambda m: '%s="#%s-%s"' % (m.group(1), limpo, m.group(2)), svg)
    return svg


def svg_de(figura, prefixo=""):
    """SVG pronto para embutir: sem prologo XML, sem DOCTYPE e com ids proprios.

    O matplotlib escreve '<?xml ...?>' e '<!DOCTYPE svg ...>' antes do '<svg'.
    Embutir isso no meio de um HTML e invalido, entao tudo antes do primeiro
    '<svg' sai fora.

    A gravacao passa por estilo.salvar_svg, que e o unico lugar do projeto que
    chama savefig para SVG: e la que a data de criacao e suprimida, sem o que o
    teste de reprodutibilidade do dashboard nao passa.
    """
    buffer = io.StringIO()
    estilo.salvar_svg(figura, buffer)
    plt.close(figura)
    bruto = buffer.getvalue()
    svg = bruto[bruto.index("<svg"):]
    return _prefixa_ids(svg, prefixo) if prefixo else svg


# AS PAGINAS IRMAS. Sao arquivos separados, ligados por links relativos -- que e o
# que os faz funcionar com duplo clique e sem servidor, a propriedade que o
# dashboard inteiro protege.
#
# A lista mora aqui, e nao em cada painel, porque tres copias de uma lista de tres
# links viram tres listas diferentes na primeira vez que uma pagina entra ou sai.
# O DASHBOARD DO RMD SAO DUAS PAGINAS, e nao uma. Medido em 21/08/2026: com os 28
# graficos numa pagina so, o arquivo chegou a 9,62 MB contra o limiar de 10 da spec
# -- sobravam 0,38 MB, e o proximo grafico com quatro janelas nao caberia.
#
# As alternativas eram cortar janela ou cortar grafico, e as duas custam informacao.
# Quebrar em duas custa um clique, e o limiar passa a valer por pagina.
#
# O CORTE E POR ASSUNTO, e nao por tamanho: a primeira responde "de quanto e a
# divida, quando ela vence, quanto ela custa"; a segunda, "o que o Tesouro emitiu,
# quanto de colchao ele tem, e quem carrega o papel". Que elas fiquem em 3,4 e 5,0
# MB e consequencia, nao criterio.
PAGINAS_DO_RMD = [
    ("dashboard.html", "estoque, prazo e custo",
     ["O total", "Estoque", "Vencimentos", "Prazo", "Custo"],
     "D\u00edvida P\u00fablica Federal \u00b7 estoque"),
    ("dashboard-funding.html", "funding e detentores",
     ["Funding", "Detentores", "Reserva"],
     "D\u00edvida P\u00fablica Federal \u00b7 funding"),
]

PAGINAS = [(arquivo, rotulo) for arquivo, rotulo, _, _ in PAGINAS_DO_RMD] + [
    ("paf.html", "contra o PAF"),
    ("emissoes.html", "o que j\u00e1 foi emitido"),
    ("calendario.html", "o calend\u00e1rio"),
]


# As duas paginas do RMD nao dependem de leilao nenhum: elas so mudam quando
# entra um RMD novo. Dizer a data do ultimo leilao ali nao seria so ruido --
# sugeriria que aqueles graficos andam toda semana, quando andam uma vez por mes.
PAGINAS_SEM_LEILAO = frozenset(arquivo for arquivo, _, _, _ in PAGINAS_DO_RMD)


def procedencia(nome_do_arquivo):
    """A linha do topo que diz DE QUANDO e o dado desta pagina.

    Decisao dela, 27/08/2026: "SEMPRE deixar no comeco da pagina qual o rmd
    utilizado; nas de leiloes qual o ultimo leilao puxado".

    O QUE ISSO PROTEGE, e vale escrever porque nao e obvio: o projeto escolhe o
    anexo do RMD pelo MTIME do arquivo (leitura_rmd.caminho_do_rmd), e vive
    dentro do OneDrive, que reescreve arquivo por conta propria. Se ele tocasse
    no anexo de junho depois do de julho, o projeto inteiro voltaria a junho SEM
    AVISO -- publicando o mes errado com cara de certo. Esta linha nao conserta o
    criterio; faz a falha aparecer na primeira olhada.

    A DATA DO LEILAO SO E BUSCADA NAS PAGINAS QUE PRECISAM DELA. rolagem.leiloes()
    junta a planilha com o provisorio da API, ou seja, VAI A REDE -- e o dashboard
    do RMD nao ia. Busca-la para toda pagina desfaria o commit "os testes da
    pagina param de ir a rede". Ha um teste que trava isso.

    Leilao e liquidacao sao datas DIFERENTES e as duas aparecem: a rolagem casa
    por liquidacao, entao quem le a tabela precisa das duas para conferir.
    """
    from .. import rolagem

    base, _ = rolagem.base_do_rmd()
    mes = estilo.MES_LONGO[base.month].lower()
    partes = [f"RMD de {mes}/{base.year} (base {base.strftime('%d/%m/%Y')})"]

    if nome_do_arquivo not in PAGINAS_SEM_LEILAO:
        d = rolagem.leiloes()
        leilao = d["data_leilao"].max()
        liquidacao = d["data_liquidacao"].max()
        partes.append(
            f"\u00faltimo leil\u00e3o {leilao.strftime('%d/%m/%Y')}, "
            f"liquidado em {liquidacao.strftime('%d/%m/%Y')}")

    return ('<div id="procedencia">' + " \u00b7 ".join(partes) + "</div>")



def grava_o_rmd(recortes=None, destino=None):
    """Grava as DUAS paginas do dashboard do RMD e devolve os caminhos.

    Cada uma leva os grupos dela; a barra do topo liga as quatro paginas do
    projeto, entao quem abre uma acha a outra. Ver PAGINAS_DO_RMD.

    'destino' e a PASTA onde gravar, e existe para o teste poder escrever num
    diretorio temporario. Trocar config.PROCESSED_DIR nao serve: ele tambem e de
    onde os CSVs sao LIDOS, e a montagem morria sem achar estoque_dpf.csv.
    """
    destino = destino or config.PROCESSED_DIR
    escritos = []
    for arquivo, _, grupos, titulo in PAGINAS_DO_RMD:
        do_grupo = [g for g in REGISTRO if g.grupo in grupos]
        if not do_grupo:
            raise LookupError(
                f"a pagina {arquivo} ficou sem grafico nenhum: os grupos "
                f"{grupos} nao existem no registro.")
        escritos.append(grava(destino / arquivo, recortes,
                              do_grupo, grupos, titulo))
    return escritos


def barra_das_paginas(atual, extras=None, familia=None):
    """A faixa do topo que liga as paginas entre si.

    'extras' sao os links da propria familia da pagina -- as tres combinacoes de
    compra e segunda volta, no caso das emissoes.

    'familia' diz a qual entrada do primeiro nivel esses extras pertencem. Sem ela,
    a pagina emissoes.html saia com DOIS itens em negrito ("o que ja foi emitido" e
    "so venda, com 2a volta"), e a emissoes-1a-volta.html saia com o mesmo destino
    duas vezes -- porque emissoes.html e ao mesmo tempo a entrada do primeiro nivel
    e o primeiro dos extras.

    Com ela, a entrada da familia vira texto simples quando se esta dentro dela: nao
    e link, porque nao leva a lugar nenhum novo, e nao e negrito, porque o negrito
    marca a pagina exata.
    """
    partes = ['<div id="paginas">', "  <span>p\u00e1ginas:</span>"]
    for arquivo, rotulo in PAGINAS:
        # A entrada da familia nunca e link nem negrito quando ha extras: quem
        # aponta a pagina exata sao eles. Sem esta regra, emissoes.html saia com
        # DOIS itens em negrito, e emissoes-1a-volta.html com o mesmo destino duas
        # vezes.
        dentro_da_familia = (familia is not None and extras
                             and arquivo == familia)
        if dentro_da_familia:
            partes.append(f'  <span class="familia">{rotulo}</span>')
        elif arquivo == atual:
            partes.append(f'  <b class="atual">{rotulo}</b>')
        else:
            partes.append(f'  <a href="{arquivo}">{rotulo}</a>')
    for arquivo, rotulo in (extras or []):
        if arquivo == atual:
            partes.append(f'  <b class="atual">{rotulo}</b>')
        else:
            partes.append(f'  <a href="{arquivo}">{rotulo}</a>')
    partes.append("</div>")
    return "\n".join(partes)


CSS_DOS_GRUPOS = """
details.grupo-secao { margin: 0 0 10px; }
details.grupo-secao > summary { cursor: pointer; font-size: 17px;
  font-weight: 600; color: var(--tinta); padding: 10px 0 10px 10px;
  border-left: 4px solid #ccc; letter-spacing: .01em; }
details.grupo-secao > summary:hover { background: #fafafa; }
details.grupo-secao[open] > summary { border-left-color: var(--tinta);
  margin-bottom: 6px; }
"""

CSS_DAS_PAGINAS = """
#paginas { margin: 0 0 14px; font-size: 13px; display: flex;
           align-items: center; gap: 12px; flex-wrap: wrap; }
#paginas span { color: var(--fraco); }
#paginas span.familia { color: var(--tinta); }
#paginas a { color: var(--tinta); text-decoration: none;
             border-bottom: 1px solid transparent; }
#paginas a:hover { border-bottom-color: var(--tinta); }
#paginas b.atual { color: var(--tinta); border-bottom: 2px solid var(--tinta);
                   padding-bottom: 1px; }
""" + """\n#procedencia { font-size: 12px; color: var(--fraco); margin: 2px 0 14px;
  padding-bottom: 10px; border-bottom: 1px solid var(--linha); }
"""


def _bloco(grafico, recortes):
    """Uma secao: titulo, as versoes do SVG, a fonte e a legenda.

    Cada versao e um par (janela, variante). Sem variantes sao uma ou duas versoes;
    com variantes, o dobro -- e a caixa de marcar escolhe qual metade aparece.
    """
    # <details>/<summary> e HTML puro: a setinha nao custa uma linha de JavaScript,
    # e o conteudo continua no arquivo -- quem procurar com Ctrl+F acha, e quem
    # imprimir leva tudo.
    if grafico.recolhido:
        partes = [f'<section id="{grafico.id}" class="recolhida">',
                  "  <details>",
                  f"    <summary>{grafico.titulo}</summary>"]
    else:
        partes = [f'<section id="{grafico.id}">',
                  f"  <h2>{grafico.titulo}</h2>"]

    if grafico.variantes:
        rotulo, (desmarcada, marcada) = grafico.variantes
        partes.append(
            f'  <label class="variante"><input type="checkbox" class="variante" '
            f'data-nao="{desmarcada}" data-sim="{marcada}" '
            f"onchange=\"trocaVariante('{grafico.id}')\"> {rotulo}</label>")
        opcoes = [(str(desmarcada), desmarcada), (str(marcada), marcada)]
    else:
        opcoes = [("", None)]

    usados = recortes if grafico.janela else recortes[:1]
    for nome, janela in usados:
        for marca, variante in opcoes:
            padrao_da_janela = (nome == grafico.padrao or len(usados) == 1)
            padrao_da_variante = (marca == opcoes[0][0])
            visivel = "" if (padrao_da_janela and padrao_da_variante) \
                else ' style="display:none"'
            figura = (grafico.figura(janela, variante) if grafico.variantes
                      else grafico.figura(janela))
            svg = svg_de(figura, prefixo=f"{grafico.id}-{nome}-{marca}")
            # Grafico sem janela recebe data-janela="" e nao o nome do primeiro
            # recorte: dizer "5 anos" num retrato de uma data e atributo que
            # mente. O JavaScript ja trata o caso pelo fallback, mas quem
            # inspecionar o HTML nao tem como saber disso.
            rotulo_janela = nome if grafico.janela else ""
            partes.append(f'  <div data-grafico="{grafico.id}" '
                          f'data-janela="{rotulo_janela}" data-variante="{marca}"'
                          f"{visivel}>{svg}</div>")

    partes.append(f'  <p class="fonte">Fonte: {grafico.fonte}</p>')
    partes.append(f'  <p class="legenda">{grafico.nota}</p>')
    if grafico.recolhido:
        partes.append("  </details>")
    partes.append("</section>")
    return "\n".join(partes)


# Qual grupo abre com a pagina. So o primeiro: com os sete abertos, o dashboard
# tem oito metros de rolagem e quem chega nao ve onde as coisas estao.
def _abre_por_padrao(grupo, grupos):
    return grupo == grupos[0]


def _corpo_por_grupo(registro, grupos, recortes):
    """Os graficos, agrupados dentro de um <details> por grupo.

    <details>/<summary> e HTML puro: a setinha nao custa uma linha de JavaScript, e
    o conteudo continua no arquivo -- quem procurar com Ctrl+F acha, e quem imprimir
    leva tudo.

    ATENCAO AO INDICE: com o grupo fechado, clicar num link do indice levava a uma
    secao invisivel. abreSeApontada() passou a abrir tambem os <details> ANCESTRAIS
    do alvo, e nao so o de dentro dele.
    """
    partes = []
    for grupo in grupos:
        do_grupo = [g for g in registro if g.grupo == grupo]
        if not do_grupo:
            continue
        marca = " open" if _abre_por_padrao(grupo, grupos) else ""
        partes.append(f'<details class="grupo-secao" data-grupo="{grupo}"{marca}>')
        partes.append(f"<summary>{grupo}</summary>")
        partes.extend(_bloco(g, recortes) for g in do_grupo)
        partes.append("</details>")
    return "\n".join(partes)


def _indice(registro, grupos, titulo):
    linhas = ['<nav id="indice">', f"  <h1>{titulo}</h1>"]
    for grupo in grupos:
        do_grupo = [g for g in registro if g.grupo == grupo]
        if not do_grupo:
            continue
        linhas.append(f'  <div class="grupo">{grupo}</div>')
        for g in do_grupo:
            linhas.append(f'  <a href="#{g.id}">{g.titulo}</a>')
    linhas.append("</nav>")
    return "\n".join(linhas)


def monta(recortes=None, registro=None, grupos=None, titulo=None,
          agrupar=True):
    """O HTML inteiro, com os SVGs embutidos.

    'recortes' e uma lista de pares (nome, janela). Com um par so, o botao de
    periodo nao aparece -- e o caso do --de/--ate na linha de comando.

    'registro', 'grupos' e 'titulo' existem para que a mesma montagem sirva uma
    segunda pagina -- a de emissoes da entrega 3, que nao cabe nesta: medido, a
    matriz de graficos dela daria 15,6 MB contra o limiar de 10. O padrao continua
    sendo o dashboard do RMD.
    """
    estilo.aplicar_estilo()
    recortes = list(recortes) if recortes else list(JANELAS)
    registro = REGISTRO if registro is None else registro
    grupos = GRUPOS if grupos is None else grupos
    titulo = titulo or "D\u00edvida P\u00fablica Federal"

    botoes = ""
    if len(recortes) > 1:
        marcas = "".join(
            f'<button data-janela="{nome}" onclick="trocaPeriodo(\'{nome}\')">'
            f"{nome}</button>" for nome, _ in recortes)
        botoes = f'<div id="troca-periodo">{marcas}</div>'

    # 'agrupar' existe para a pagina do calendario, que faz o proprio
    # seccionamento: com os dois, ela saia com DUAS setinhas aninhadas dizendo
    # quase a mesma coisa.
    corpo = (_corpo_por_grupo(registro, grupos, recortes) if agrupar
             else "\n".join(_bloco(g, recortes) for g in registro))

    return (
        "<!doctype html>\n<html lang=\"pt-br\">\n<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{titulo}</title>\n"
        f"<style>{_CSS}</style>\n</head>\n<body>\n"
        f"{_indice(registro, grupos, titulo)}\n<main>\n"
        f'<header id="topo">{botoes}</header>\n'
        f"{corpo}\n</main>\n"
        f"<script>{_JS}</script>\n</body>\n</html>\n"
    )


def grava(caminho=None, recortes=None, registro=None, grupos=None, titulo=None,
          extras=None, familia=None, agrupar=True):
    """Grava a pagina e devolve o caminho.

    A BARRA DAS PAGINAS ENTRA AQUI, e nao em cada painel. Os paineis injetavam a
    barra depois da montagem, cada um com a sua copia da lista de links -- e o
    dashboard, que nao e montado por painel nenhum, ficava sem barra e sem saida
    para as outras paginas.

    'extras' sao os links da propria familia da pagina: as combinacoes de compra e
    segunda volta, no caso das emissoes.
    """
    caminho = caminho or (config.PROCESSED_DIR / "dashboard.html")
    caminho.parent.mkdir(parents=True, exist_ok=True)

    html = monta(recortes, registro, grupos, titulo, agrupar)
    # A BARRA DAS PAGINAS ENTRA DENTRO DO CABECALHO, e nao antes do <main>.
    #
    # Antes ela era irma do <main> e do <nav>, e como o <nav> e position:fixed com
    # 250px de largura, a barra -- que nao tinha margem -- era desenhada DEBAIRO
    # dele. Os dois se entrelacavam no alto da tela. Dentro do cabecalho ela herda
    # a margem do <main> e o problema some.
    html = html.replace(
        '<header id="topo">',
        '<header id="topo">' + barra_das_paginas(caminho.name, extras, familia)
        + procedencia(caminho.name),
        1)
    html = html.replace("</style>",
                        CSS_DAS_PAGINAS + CSS_DOS_GRUPOS + "</style>", 1)
    caminho.write_text(html, encoding="utf-8")
    return caminho
