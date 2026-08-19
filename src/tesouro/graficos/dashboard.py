"""O registro dos dezesseis graficos e a montagem do HTML.

O registro e uma LISTA LITERAL, sem decorador e sem descoberta automatica: quem
abre este arquivo ve os dezesseis, em ordem, com grupo e fonte, e entende em trinta
segundos. A indirecao de um sistema de registro nao se paga para dezesseis itens, e
um decorador espalharia por dez arquivos a informacao que interessa junta.

O HTML e autocontido: os SVGs vao dentro dele. Abre com duplo clique, sem servidor,
e continua funcionando copiado para outra maquina ou mandado por e-mail -- num banco
isso vale mais que elegancia. O limiar de 10 MB e medido por teste; se estourar, os
SVGs saem para arquivos ao lado.

Nove dos dezesseis aceitam janela, entao sao 25 SVGs. (A spec diz sete e 23 no
texto, mas a tabela da secao 5 marca nove; a tabela e que esta certa.)
"""

import collections
import io
import re

import matplotlib.pyplot as plt

from .. import config
from . import (custo, detentores, estilo, estoque, funding, leiloes, paf,
               prazo, reserva, vencimentos)

Grafico = collections.namedtuple(
    "Grafico", "id grupo titulo fonte nota janela padrao figura")

GRUPOS = ["Funding", "Estoque", "Detentores", "Vencimentos", "Prazo", "Custo",
          "Reserva", "Candidatos"]

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
    # barras, e a completa vira a serie inteira.
    anos = janela if isinstance(janela, int) else 100
    dados = funding.dados_emissao_anual(anos=anos)
    fig = _figura()
    funding.desenha_emissao_anual(dados, fig.subplots(),
                                 funding.ultimo_mes_com_emissao().year)
    return fig


def _fig_composicao(janela):
    fig = _figura(6.8)
    bandas = {k: paf.bandas(k) for k in paf.COMPOSICAO}
    estoque.desenha_composicao(estoque.dados_composicao(janela), bandas,
                               fig.subplots())
    return fig


def _fig_participacao(janela):
    fig = _figura(5.0)
    detentores.desenha_participacao(detentores.dados_participacao(), fig)
    return fig


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


def _fig_custo(janela):
    fig = _figura()
    custo.desenha_custo(custo.dados_custo(janela), fig.subplots())
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
                                        fig.subplots())
    return fig


def _fig_custo_emissao(janela):
    fig = _figura()
    custo.desenha_custo_emissao(custo.dados_custo_emissao(janela),
                                fig.subplots())
    return fig


def _fig_emissao_papel(janela):
    anos = janela if isinstance(janela, int) else 100
    dados = leiloes.dados_emissao_anual_papel(anos=anos)
    fig = _figura()
    leiloes.desenha_emissao_anual_papel(
        dados, fig.subplots(), leiloes.ultima_competencia_do_rmd().year)
    return fig


REGISTRO = [
    Grafico("funding_net", "Funding",
            "Net do DPMFi, com m\u00e9dia m\u00f3vel e acumulado de 12 meses",
            "aba 1.1",
            "Emiss\u00e3o menos resgate do DPMFi, m\u00eas a m\u00eas. Sem m\u00e9dia de 3 meses, "
            "por decis\u00e3o de quem l\u00ea. Cobre 100% do DPMFi.",
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
    Grafico("estoque_composicao", "Estoque",
            "Composi\u00e7\u00e3o da DPF por indexador, com a banda do PAF",
            "aba 2.1 e referencia/paf_bandas.csv",
            "Participa\u00e7\u00e3o de cada indexador na DPF. A banda \u00e9 a meta do PAF, ano "
            "a ano; onde houve revis\u00e3o, a banda original aparece pontilhada. "
            "Abre na s\u00e9rie completa: o c\u00e2mbio sai de 51,0% em set/2002 para 3,7%.",
            True, "completa", _fig_composicao),
    Grafico("detentores_participacao", "Detentores",
            "Participa\u00e7\u00e3o por grupo, e a varia\u00e7\u00e3o em 12 meses",
            "aba 2.7",
            "Os oito detentores da aba agrupados em cinco. A varia\u00e7\u00e3o \u00e9 contra o "
            "mesmo m\u00eas do ano anterior, em pontos percentuais.",
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
    Grafico("vencimentos_cronograma", "Vencimentos",
            "Cronograma de vencimentos, com o balde da cauda",
            "aba 3.4",
            "Os 60 meses que a aba detalha (6.913,8 bi) mais o balde 'Ap\u00f3s 5 "
            "anos' (2.006,9 bi). 2026 \u00e9 jul\u2013dez e 2031 \u00e9 jan\u2013jun.",
            False, None, _fig_cronograma),
    Grafico("vencimentos_faixas", "Vencimentos",
            "Composi\u00e7\u00e3o da DPF por horizonte, com a banda do PAF",
            "aba 3.1 e aba 5.7",
            "A banda vem da aba 5.7 (2003 a 2022) e de referencia/paf_bandas.csv "
            "(2026). Em 2023, 2024 e 2025 nenhuma das duas tem banda, e nada "
            "\u00e9 desenhado ali.",
            False, None, _fig_faixas),
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
            "meses do nosso pr\u00f3prio VNA, e come\u00e7am em jan/2011.",
            True, "5 anos", _fig_custo),
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
    Grafico("perfil_completo", "Candidatos",
            "Perfil completo de vencimentos, at\u00e9 2084",
            "aba 2.2",
            "Papel a papel, diferente do cronograma, que vem da 3.4. Os dois n\u00e3o "
            "fecham: 8.904,1 bi aqui contra 8.920,7 l\u00e1, e a causa dos 16,6 bi de "
            "diferen\u00e7a est\u00e1 em aberto.",
            False, None, _fig_perfil_completo),
    Grafico("custo_emissao", "Candidatos",
            "Custo de emiss\u00e3o contra o custo do estoque",
            "abas 4.2 e 4.3",
            "DPMFi. Emite-se a 14,20% e carrega-se a 13,19%: a d\u00edvida encarece "
            "sem que nenhuma decis\u00e3o nova seja tomada.",
            True, "5 anos", _fig_custo_emissao),
    Grafico("emissao_papel", "Candidatos",
            "Composi\u00e7\u00e3o anual da emiss\u00e3o por papel, dos leil\u00f5es",
            "leiloes.csv",
            "Recusado como gr\u00e1fico principal: os leil\u00f5es cobrem de 90,5% a 97,3% "
            "da emiss\u00e3o que o RMD registra, contra 100% da aba 1.2.",
            True, "5 anos", _fig_emissao_papel),
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
"""

_JS = """
function trocaPeriodo(janela) {
  document.querySelectorAll('[data-grafico]').forEach(function (bloco) {
    var alvo = bloco.parentElement.querySelector('[data-janela="' + janela + '"]');
    if (alvo) { bloco.style.display = (bloco === alvo) ? '' : 'none'; }
  });
  document.querySelectorAll('#troca-periodo button').forEach(function (b) {
    b.classList.toggle('ativo', b.dataset.janela === janela);
  });
}
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
    import re
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
    """Uma secao: titulo, as versoes do SVG, a fonte e a legenda."""
    partes = [f'<section id="{grafico.id}">',
              f"  <h2>{grafico.titulo}</h2>"]

    usados = recortes if grafico.janela else recortes[:1]
    for nome, janela in usados:
        visivel = "" if (nome == grafico.padrao or len(usados) == 1) \
            else ' style="display:none"'
        svg = svg_de(grafico.figura(janela), prefixo=f"{grafico.id}-{nome}")
        partes.append(f'  <div data-grafico="{grafico.id}" '
                      f'data-janela="{nome}"{visivel}>{svg}</div>')

    partes.append(f'  <p class="fonte">Fonte: {grafico.fonte}</p>')
    partes.append(f'  <p class="legenda">{grafico.nota}</p>')
    partes.append("</section>")
    return "\n".join(partes)


def _indice():
    linhas = ['<nav id="indice">', "  <h1>D\u00edvida P\u00fablica Federal</h1>"]
    for grupo in GRUPOS:
        do_grupo = [g for g in REGISTRO if g.grupo == grupo]
        if not do_grupo:
            continue
        linhas.append(f'  <div class="grupo">{grupo}</div>')
        for g in do_grupo:
            linhas.append(f'  <a href="#{g.id}">{g.titulo}</a>')
    linhas.append("</nav>")
    return "\n".join(linhas)


def monta(recortes=None):
    """O HTML inteiro, com os SVGs embutidos.

    'recortes' e uma lista de pares (nome, janela). Com um par so, o botao de
    periodo nao aparece -- e o caso do --de/--ate na linha de comando.
    """
    estilo.aplicar_estilo()
    recortes = list(recortes) if recortes else list(JANELAS)

    botoes = ""
    if len(recortes) > 1:
        marcas = "".join(
            f'<button data-janela="{nome}" onclick="trocaPeriodo(\'{nome}\')">'
            f"{nome}</button>" for nome, _ in recortes)
        botoes = f'<div id="troca-periodo">{marcas}</div>'

    corpo = "\n".join(_bloco(g, recortes) for g in REGISTRO)

    return (
        "<!doctype html>\n<html lang=\"pt-br\">\n<head>\n"
        '<meta charset="utf-8">\n'
        "<title>D\u00edvida P\u00fablica Federal</title>\n"
        f"<style>{_CSS}</style>\n</head>\n<body>\n"
        f"{_indice()}\n<main>\n{botoes}\n{corpo}\n</main>\n"
        f"<script>{_JS}</script>\n</body>\n</html>\n"
    )


def grava(caminho=None, recortes=None):
    """Grava o dashboard e devolve o caminho."""
    caminho = caminho or (config.PROCESSED_DIR / "dashboard.html")
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(monta(recortes), encoding="utf-8")
    return caminho
