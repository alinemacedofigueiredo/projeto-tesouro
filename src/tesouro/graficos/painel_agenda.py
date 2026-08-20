"""A pagina da agenda: o que o Tesouro planeja ofertar nas proximas semanas.

Pagina PROPRIA, como a de emissoes, e pelo mesmo motivo: quem olha o que JA foi
emitido e quem olha o que VEM PELA FRENTE raramente olham ao mesmo tempo, e a barra
de links no topo liga as duas.

O QUE ESTA PAGINA E, E O QUE ELA NAO E. O /calendario da API diz QUAIS benchmarks vao
a mercado em cada dia. Nao diz QUANTO -- isso so sai no edital das 10h30 do proprio
dia. Entao esta pagina e uma agenda enriquecida com o que o historico sabe, e nao uma
previsao de emissao.

Os tres graficos vao do mais firme para o mais suposto, de proposito:

  o cronograma       so fatos publicados;
  o DV01 por titulo  calculado da ultima taxa, mas sem quantidade nenhuma dentro;
  o DV01 do dia      um produto pelo que ele ofertou da vez passada. Hachurado
                     inteiro, porque nao e previsao.

A TABELA vem depois dos graficos e nao antes: ela tem tudo, mas ninguem le uma tabela
de cinquenta linhas para saber o formato da semana. Ela existe para conferir e
copiar, que e outra tarefa.

SEM JANELAS. As cinco janelas da pagina de emissoes nao fazem sentido aqui: a agenda
e uma so, a que o Tesouro publicou, e ela vai ate onde ele publicou.
"""
import pandas as pd

from .. import agenda as dados_agenda
from . import cronograma, dashboard, estilo

GRUPOS = ["A agenda", "Quanto risco vem"]

ARQUIVO = "agenda.html"

_NOTA_TAXA = (
    "A taxa de cada papel \u00e9 a do <b>\u00faltimo leil\u00e3o dele</b>, e n\u00e3o uma "
    "taxa de mercado \u2014 este projeto n\u00e3o tem fonte para ler curva. Medido: a do "
    "leil\u00e3o anterior erra <b>11,0 bp na mediana</b> e 36,7 no p90, e isso move o "
    "DV01 do lote em 0,55% / 2,1%."
)

_NOTA_QUANTIDADE = (
    "<b>A quantidade n\u00e3o est\u00e1 no calend\u00e1rio.</b> Ela sai no edital, a partir "
    "das 10h30 do pr\u00f3prio dia. O que aparece aqui \u00e9 o que ele ofertou da "
    "<b>vez passada</b> daquele papel \u2014 e ele muda de tamanho de leil\u00e3o para "
    "leil\u00e3o."
)


def _fig(desenha, altura):
    def figura(janela=None):
        fig = dashboard._figura(altura)
        desenha(_dados(), fig.subplots())
        return fig
    return figura


_EM_CACHE = {}


def _dados(hoje=None):
    """A agenda, buscada uma vez por rodada.

    Guardada porque a pagina a usa em tres graficos e na tabela, e cada chamada
    baixaria o calendario de novo e recalcularia o DV01 de cinquenta linhas.
    """
    chave = str(hoje)
    if chave not in _EM_CACHE:
        _EM_CACHE[chave] = dados_agenda.proximos(hoje=hoje)
    return _EM_CACHE[chave]


def limpar_cache():
    _EM_CACHE.clear()


Grafico = dashboard.Grafico

REGISTRO = [
    Grafico("agenda_cronograma", "A agenda",
            "O calend\u00e1rio publicado, por dia e por v\u00e9rtice",
            "API do Tesouro \u00b7 /calendario",
            "S\u00f3 fatos: o Tesouro publica quais benchmarks v\u00e3o a mercado em cada "
            "dia. O v\u00e9rtice fica no eixo vertical para mostrar a <b>cobertura da "
            "curva</b> de cada dia \u2014 um dia com 3, 7 e 15 anos faz com o prazo "
            "m\u00e9dio da d\u00edvida algo diferente de um com 5 e 30, e num gr\u00e1fico "
            "por papel os dois pareceriam iguais. Escala logar\u00edtmica porque os "
            "v\u00e9rtices v\u00e3o de meio ano a 35.",
            False, None, _fig(cronograma.desenha_cronograma, 5.0)),

    Grafico("agenda_dv_unitario", "Quanto risco vem",
            "Quanto risco carrega cada t\u00edtulo da agenda",
            "API do Tesouro \u00b7 /calendario + hist\u00f3rico de leil\u00f5es",
            "O n\u00famero mais firme desta p\u00e1gina: <b>n\u00e3o depende de quantidade "
            "nenhuma</b>, s\u00f3 da taxa. Responde qual dos papeis agendados carrega "
            "risco \u2014 um NTN-B 35 anos carrega mais de <b>cem vezes</b> o DV01 de "
            "uma LTN de 6 meses, t\u00edtulo a t\u00edtulo. "
            "A LFT n\u00e3o aparece: DV01 zero por decis\u00e3o de modelagem da entrega "
            "2, e n\u00e3o por falha de c\u00e1lculo. " + _NOTA_TAXA,
            False, None, _fig(cronograma.desenha_dv_unitario, 5.4)),

    Grafico("agenda_dv_por_dia", "Quanto risco vem",
            "Se ele repetir a \u00faltima oferta de cada papel",
            "API do Tesouro \u00b7 /calendario + hist\u00f3rico de leil\u00f5es",
            "<b>Isto n\u00e3o \u00e9 previs\u00e3o</b>, e por isso a barra sai hachurada "
            "inteira. " + _NOTA_QUANTIDADE + " O que d\u00e1 para ler aqui \u00e9 o "
            "<b>ritmo</b>: os dias de prefixado (LTN e NTN-F juntos) carregam duas a "
            "quatro vezes o risco dos dias de LFT e NTN-B.",
            False, None, _fig(cronograma.desenha_dv_por_dia, 4.6)),
]


def _celula_taxa(r):
    """A taxa com a idade dela, e um aviso quando ela passou dos 45 dias."""
    quando = f"{r['taxa_de_quando']:%d/%m}"
    idade = int(r["taxa_dias_de_idade"]) if pd.notna(r["taxa_dias_de_idade"]) else None
    if idade is None:
        return "\u2014"
    marca = ' class="velha"' if r["taxa_velha"] else ""
    aviso = " \u26a0" if r["taxa_velha"] else ""
    return (f'<span{marca}>{estilo.num_br(r["taxa_pct"], 4)}%'
            f'<small> {quando} \u00b7 {idade}d{aviso}</small></span>')


def tabela(dados=None):
    """A agenda inteira, em HTML, agrupada por dia de leilao.

    Vem DEPOIS dos graficos: ninguem le cinquenta linhas para saber o formato da
    semana. Ela existe para conferir papel a papel e para copiar.
    """
    d = _dados() if dados is None else dados
    if d.empty:
        return ('<div id="tabela-agenda"><p>O calend\u00e1rio publicado n\u00e3o tem '
                'nenhum leil\u00e3o daqui para a frente.</p></div>')

    linhas = ['<div id="tabela-agenda">',
              "<h2>A agenda, papel a papel</h2>",
              f"<p class=\"legenda\">{_NOTA_QUANTIDADE} {_NOTA_TAXA} "
              "O \u26a0 marca a taxa com mais de 45 dias, fora da faixa em que o "
              "erro foi medido.</p>",
              "<table>",
              "<thead><tr>"
              "<th>papel</th><th>benchmark</th><th>vencimento</th>"
              "<th class=\"n\">\u00faltima taxa</th>"
              "<th class=\"n\">ofertou da vez passada</th>"
              "<th class=\"n\">DV01 por t\u00edtulo</th>"
              "<th class=\"n\">DV01 se repetir</th>"
              "</tr></thead><tbody>"]

    for dia, g in d.groupby("data_leilao"):
        soma = g["dv_se_repetir"].sum()
        linhas.append(
            f'<tr class="dia"><td colspan="6">{dia:%d/%m/%Y} \u00b7 '
            f'{len(g)} papel(is)</td>'
            f'<td class="n">{estilo.num_br(soma, 3)}</td></tr>')
        for _, r in g.iterrows():
            oferta = ("\u2014" if pd.isna(r["oferta_anterior_qtd"])
                      else estilo.num_br(r["oferta_anterior_qtd"] / 1000, 0) + " mil")
            dv_u = ("\u2014" if pd.isna(r["dv_unitario"])
                    else estilo.num_br(r["dv_unitario"], 3))
            dv_r = ("\u2014" if pd.isna(r["dv_se_repetir"])
                    else estilo.num_br(r["dv_se_repetir"], 3))
            linhas.append(
                f"<tr><td>{r['titulo']}</td><td>{r['benchmark']}</td>"
                f"<td>{r['data_vencimento']:%d/%m/%Y}</td>"
                f'<td class="n">{_celula_taxa(r)}</td>'
                f'<td class="n">{oferta}</td>'
                f'<td class="n">{dv_u}</td>'
                f'<td class="n">{dv_r}</td></tr>')

    linhas += ["</tbody></table>", "</div>"]
    return "\n".join(linhas)


_CSS = """
#tabela-agenda { margin: 26px auto 40px; max-width: 1180px; }
#tabela-agenda table { border-collapse: collapse; width: 100%;
                       font-size: 13px; }
#tabela-agenda th, #tabela-agenda td { padding: 5px 9px; text-align: left;
                                       border-bottom: 1px solid #e6e6e6; }
#tabela-agenda th { font-weight: 600; color: var(--fraco);
                    border-bottom: 2px solid #ccc; }
#tabela-agenda td.n, #tabela-agenda th.n { text-align: right;
                                           font-variant-numeric: tabular-nums; }
#tabela-agenda tr.dia td { background: #f4f4f4; font-weight: 600;
                           padding-top: 9px; }
#tabela-agenda small { color: var(--fraco); font-size: 11px; }
#tabela-agenda .velha { color: #a33; }
"""


def grava(caminho=None, hoje=None):
    """Grava a pagina da agenda e devolve o caminho."""
    from .. import config

    limpar_cache()
    if hoje is not None:
        _EM_CACHE[str(hoje)] = dados_agenda.proximos(hoje=hoje)
        _EM_CACHE[str(None)] = _EM_CACHE[str(hoje)]

    caminho = caminho or (config.PROCESSED_DIR / ARQUIVO)
    escrito = dashboard.grava(caminho, [("agenda", None)], REGISTRO, GRUPOS,
                              "Agenda de leil\u00f5es")
    html = escrito.read_text(encoding="utf-8")
    html = html.replace("</main>", tabela() + "\n</main>", 1)
    html = html.replace("</style>", _CSS + "</style>", 1)
    escrito.write_text(html, encoding="utf-8")
    return escrito
