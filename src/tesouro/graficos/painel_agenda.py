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

GRUPOS = ["O que ele colocou"]

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


def _fig_ofertado_aceito():
    def figura(janela=None):
        # Alta o bastante para vinte e quatro barras deitadas: em pe as datas
        # viravam etiqueta girada e ilegivel.
        fig = dashboard._figura(9.5)
        cronograma.desenha_ofertado_e_aceito(_comparacao(), fig.subplots())
        return fig
    return figura


def _fig_lft():
    def figura(janela=None):
        fig = dashboard._figura(4.0)
        cronograma.desenha_quantidade_lft(_comparacao(), fig.subplots())
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


def _comparacao():
    """Os ultimos leiloes de cada familia, com DV ofertado e aceito."""
    if "comparacao" not in _EM_CACHE:
        _EM_CACHE["comparacao"] = dados_agenda.ofertado_e_aceito()
    return _EM_CACHE["comparacao"]


def limpar_cache():
    _EM_CACHE.clear()


Grafico = dashboard.Grafico

REGISTRO = [
    Grafico("agenda_ofertado_aceito", "O que ele colocou",
            "Quanto risco ele tentou colocar, e quanto colocou",
            "dv_emitido_por_leilao.csv",
            "O DV01 <b>ofertado</b> (barra vazada) e o <b>aceito</b> (cheia) nos "
            "<b>seis \u00faltimos leil\u00f5es</b> de cada fam\u00edlia. A "
            "pergunta que isto responde, e que o aceito sozinho n\u00e3o "
            "responde: ele n\u00e3o conseguiu colocar, ou n\u00e3o quis? Medido "
            "no agregado do hist\u00f3rico, ele coloca <b>68,5% do DV que "
            "oferta</b>. "
            "S\u00e3o os seis \u00faltimos <b>de cada fam\u00edlia</b>, e "
            "n\u00e3o os seis \u00faltimos dias: LFT e NTN-B v\u00e3o a mercado "
            "num dia e o prefixado no outro. A linha pontilhada separa uma "
            "fam\u00edlia da outra. "
            "A LFT tem gr\u00e1fico pr\u00f3prio, logo abaixo \u2014 ela "
            "n\u00e3o tem DV01, por decis\u00e3o de modelagem.",
            False, None, _fig_ofertado_aceito()),
    Grafico("agenda_lft", "O que ele colocou",
            "LFT \u00b7 em t\u00edtulos, com o financeiro aceito",
            "dv_emitido_por_leilao.csv",
            "A LFT n\u00e3o tem DV01, ent\u00e3o a compara\u00e7\u00e3o "
            "ofertado/aceito dela s\u00f3 existe em <b>t\u00edtulos</b>. O "
            "financeiro entra como r\u00f3tulo porque \u00e9 a grandeza que se "
            "compara com o resto do projeto \u2014 e a LFT \u00e9 mais da "
            "metade da emiss\u00e3o.",
            False, None, _fig_lft()),
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


def tabela_dos_ultimos(dados=None, quantos=None):
    """Os ultimos leiloes de cada familia, no MESMO MOLDE da tabela da agenda.

    RECOLHIDA, e antes do calendario. Ela e referencia -- "o que aconteceu" -- e nao
    o assunto da pagina, que e "o que vem". Deixa-la aberta empurraria a agenda para
    baixo da dobra, e quem abre a pagina quer ver a agenda.

    A PRIMEIRA LINHA DE CADA DIA SAI EM OUTRA COR, para deixar claro que aquilo ja
    aconteceu: as duas tabelas tem o mesmo formato, e sem a marca elas se parecem
    demais.

    POR FAMILIA e nao por data, porque as familias tem calendarios diferentes: LFT e
    NTN-B num dia, prefixado no outro. Uma tabela por data deixaria metade das
    linhas vazias em cada dia.
    """
    d = _comparacao() if dados is None else dados
    if d.empty:
        return ""
    quantos = quantos or dados_agenda.LEILOES_NA_COMPARACAO
    d = d[d["quantos_atras"] < quantos]

    linhas = ['<details id="tabela-ultimos">',
              "<summary>Os \u00faltimos "
              f"{quantos} leil\u00f5es de cada papel</summary>",
              '<p class="legenda">O DV01 que ele <b>ofertou</b> e o que '
              '<b>aceitou</b>, e a fra\u00e7\u00e3o entre os dois \u2014 no '
              'agregado do hist\u00f3rico, 68,5%. A LFT aparece sem DV01, por '
              'decis\u00e3o de modelagem; para ela a compara\u00e7\u00e3o '
              'est\u00e1 no gr\u00e1fico acima, em t\u00edtulos.</p>',
              "<table><thead><tr>"
              "<th>papel</th><th>data</th>"
              '<th class="n">ofertou</th>'
              '<th class="n">aceitou</th>'
              '<th class="n">DV01 ofertado</th>'
              '<th class="n">DV01 aceito</th>'
              '<th class="n">colocou</th>'
              '<th class="n">financeiro</th>'
              "</tr></thead><tbody>"]

    for familia in dados_agenda._ORDEM_FAMILIAS:
        g = d[d["familia"] == familia].sort_values("quantos_atras")
        if g.empty:
            continue
        for k, (_, r) in enumerate(g.iterrows()):
            classe = ' class="passado"' if k == 0 else ""
            papel = f"<b>{familia}</b>" if k == 0 else ""
            fracao = r.get("colocado_pct")
            if pd.isna(fracao):
                fracao = r.get("colocado_qtd_pct")
            if pd.isna(fracao):
                marca = "\u2014"
            else:
                cor = "" if fracao > 0.95 else ' class="baixo"'
                marca = f'<span{cor}>{estilo.num_br(fracao * 100, 0)}%</span>'
            linhas.append(
                f"<tr{classe}><td>{papel}</td>"
                f"<td>{r['data_leilao']:%d/%m/%Y}</td>"
                f'<td class="n">{_qtd(r["qtd_ofertada"])}</td>'
                f'<td class="n">{_qtd(r["qtd_aceita"])}</td>'
                f'<td class="n">{_mil(r["dv_ofertado"])}</td>'
                f'<td class="n">{_mil(r["dv_aceito"])}</td>'
                f'<td class="n">{marca}</td>'
                f'<td class="n">{estilo.num_br(r["financeiro_milhoes"] / 1000, 2)}'
                f" bi</td></tr>")

    linhas += ["</tbody></table>", "</details>"]
    return "\n".join(linhas)


def _mil(dv):
    """O DV em R$ mil por ponto-base. Vazio quando nao ha DV (LFT)."""
    if pd.isna(dv) or dv == 0:
        return "\u2014"
    return estilo.num_br(dv * 1000, 0)


def tabela(dados=None):
    """A agenda inteira, em HTML, agrupada por dia de leilao.

    Vem DEPOIS do grafico: ninguem le cinquenta linhas para saber o formato da
    semana. Ela existe para conferir papel a papel e para copiar.
    """
    d = _dados() if dados is None else dados
    if d.empty:
        return ('<div id="tabela-agenda"><p>O calend\u00e1rio publicado n\u00e3o tem '
                'nenhum leil\u00e3o daqui para a frente.</p></div>')

    linhas = ['<div id="tabela-agenda">',
              "<h2>A agenda, papel a papel</h2>",
              f'<p class="legenda">{_NOTA_QUANTIDADE} {_NOTA_TAXA} '
              "O \u26a0 marca a taxa com mais de 45 dias, fora da faixa em que o "
              "erro foi medido.</p>",
              "<table>",
              "<thead><tr>"
              "<th>papel</th><th>benchmark</th><th>vencimento</th>"
              '<th class="n">\u00faltima taxa</th>'
              '<th class="n">ofertou</th>'
              '<th class="n">aceitou</th>'
              '<th class="n">DV01 ofertado</th>'
              '<th class="n">DV01 aceito</th>'
              "</tr></thead><tbody>"]

    for dia, g in d.groupby("data_leilao"):
        linhas.append(
            f'<tr class="dia"><td colspan="8">{dia:%d/%m/%Y} \u00b7 '
            f"{len(g)} papel(is)</td></tr>")
        for _, r in g.iterrows():
            # O DV DO LOTE, e nao o do titulo: o unitario e propriedade do papel e
            # nao diz nada sobre o tamanho do leilao. Sai do dv por titulo vezes a
            # quantidade da vez passada -- que e o que a coluna ao lado mostra.
            dv_of = _dv_do_lote(r["dv_unitario"], r["oferta_anterior_qtd"])
            dv_ac = _dv_do_lote(r["dv_unitario"], r["aceito_anterior_qtd"])
            linhas.append(
                f"<tr><td>{r['titulo']}</td><td>{r['benchmark']}</td>"
                f"<td>{r['data_vencimento']:%d/%m/%Y}</td>"
                f'<td class="n">{_celula_taxa(r)}</td>'
                f'<td class="n">{_qtd(r["oferta_anterior_qtd"])}</td>'
                f'<td class="n">{_qtd(r["aceito_anterior_qtd"])}</td>'
                f'<td class="n">{dv_of}</td>'
                f'<td class="n">{dv_ac}</td></tr>')

    linhas += ["</tbody></table>", "</div>"]
    return "\n".join(linhas)


def _dv_do_lote(dv_unitario, quantidade):
    """O DV01 do lote em R$ mil por ponto-base, ou travessao quando falta parte."""
    if pd.isna(dv_unitario) or pd.isna(quantidade):
        return "\u2014"
    return estilo.num_br(dv_unitario * quantidade / 1e6 * 1000, 0)


def _qtd(valor):
    """Quantidade em milhares de titulos, ou travessao quando nao ha."""
    if pd.isna(valor):
        return "\u2014"
    return estilo.num_br(valor / 1000, 0) + " mil"


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
#tabela-ultimos { margin: 26px auto 10px; max-width: 1180px;
                  border-left: 3px solid #ddd; padding-left: 12px; }
#tabela-ultimos > summary { cursor: pointer; font-size: 15px; font-weight: 600;
                            color: var(--tinta); padding: 4px 0; }
#tabela-ultimos table { border-collapse: collapse; width: 100%;
                        font-size: 13px; }
#tabela-ultimos th, #tabela-ultimos td { padding: 5px 9px;
    text-align: left; border-bottom: 1px solid #e6e6e6; }
#tabela-ultimos th { font-weight: 600; color: var(--fraco);
                     border-bottom: 2px solid #ccc; }
#tabela-ultimos td.n, #tabela-ultimos th.n { text-align: right;
    font-variant-numeric: tabular-nums; }
#tabela-ultimos tr.dia td { border-top: 2px solid #ddd;
                            font-weight: 600; padding-top: 9px; }
#tabela-ultimos .baixo { color: #c00000; font-weight: 600; }\n#tabela-ultimos tr.passado td { background: #f0eee9;\n    border-top: 2px solid #ddd; padding-top: 8px; }
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
    # As DUAS tabelas: a dos ultimos leiloes primeiro, porque responde a
    # pergunta da pagina; a agenda depois, que e referencia para conferir.
    html = html.replace(
        "</main>", tabela_dos_ultimos() + "\n" + tabela() + "\n</main>", 1)
    html = html.replace("</style>", _CSS + "</style>", 1)
    escrito.write_text(html, encoding="utf-8")
    return escrito
