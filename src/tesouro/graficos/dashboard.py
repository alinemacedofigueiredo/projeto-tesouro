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
GRUPOS = ["Funding", "Estoque", "Detentores", "Vencimentos", "Prazo", "Custo",
          "Reserva"]

JANELAS = (("5 anos", 5), ("completa", None))


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
    Grafico("reserva_13m", "Reserva",
            "Reserva de liquidez, treze meses",
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
          padding: 18px 14px; font-size: 13.5px; }
#indice h1 { font-size: 15px; margin: 0 0 4px; }
#indice .data { color: var(--fraco); font-size: 12px; margin-bottom: 14px; }
#indice .grupo { font-weight: 600; margin: 12px 0 4px; font-size: 12px;
                 text-transform: uppercase; letter-spacing: .04em;
                 color: var(--fraco); }
#indice a { display: block; color: var(--tinta); text-decoration: none;
            padding: 3px 0 3px 8px; border-left: 2px solid transparent; }
#indice a:hover { border-left-color: var(--tinta); }
main { margin-left: 250px; padding: 22px 30px 60px; max-width: 1180px; }
#troca-periodo { position: sticky; top: 0; background: var(--fundo);
                 padding: 10px 0; border-bottom: 1px solid var(--linha);
                 z-index: 5; }
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
  var caixa = secao.querySelector('details');
  if (caixa) { caixa.open = true; }
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


def monta(recortes=None, registro=None, grupos=None, titulo=None):
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

    corpo = "\n".join(_bloco(g, recortes) for g in registro)

    return (
        "<!doctype html>\n<html lang=\"pt-br\">\n<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{titulo}</title>\n"
        f"<style>{_CSS}</style>\n</head>\n<body>\n"
        f"{_indice(registro, grupos, titulo)}\n<main>\n{botoes}\n{corpo}\n</main>\n"
        f"<script>{_JS}</script>\n</body>\n</html>\n"
    )


def grava(caminho=None, recortes=None, registro=None, grupos=None, titulo=None):
    """Grava o dashboard e devolve o caminho."""
    caminho = caminho or (config.PROCESSED_DIR / "dashboard.html")
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(monta(recortes, registro, grupos, titulo),
                       encoding="utf-8")
    return caminho
