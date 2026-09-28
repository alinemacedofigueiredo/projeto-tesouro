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

ARQUIVO = "calendario.html"

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
        fig = dashboard._figura(5.4)
        cronograma.desenha_ofertado_e_aceito(_por_dia(), fig.subplots())
        return fig
    return figura


def _fig_lft():
    def figura(janela=None):
        fig = dashboard._figura(4.0)
        cronograma.desenha_quantidade_lft(_lft(), fig.subplots())
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


def _por_dia():
    """Os ultimos PREGOES, abertos por familia. Ver agenda.ultimos_dias()."""
    if "por_dia" not in _EM_CACHE:
        _EM_CACHE["por_dia"] = dados_agenda.ultimos_dias()
    return _EM_CACHE["por_dia"]


def _detalhe():
    """Os ultimos leiloes, papel a papel. Ver agenda.ultimos_leiloes()."""
    if "detalhe" not in _EM_CACHE:
        _EM_CACHE["detalhe"] = dados_agenda.ultimos_leiloes()
    return _EM_CACHE["detalhe"]


def _lft():
    """Os ultimos leiloes de LFT. Ela tem grafico proprio, em titulos."""
    if "lft" not in _EM_CACHE:
        _EM_CACHE["lft"] = dados_agenda.ultimos_de("LFT")
    return _EM_CACHE["lft"]


def limpar_cache():
    _EM_CACHE.clear()


Grafico = dashboard.Grafico

REGISTRO = [
    Grafico("agenda_ofertado_aceito", "O que ele colocou",
            "Ofertado x colocado",
            "dv_emitido_por_leilao.csv",
            "O DV01 <b>ofertado</b> (barra de cima, vazada) e o <b>aceito</b> "
            "(de baixo, cheia) nos <b>seis \u00faltimos leil\u00f5es</b>. A "
            "pergunta que isto responde, e que o aceito sozinho n\u00e3o "
            "responde: ele n\u00e3o conseguiu colocar, ou n\u00e3o quis? Medido "
            "no agregado do hist\u00f3rico, ele coloca <b>68,5% do DV que "
            "oferta</b>. "
            "O n\u00famero na ponta \u00e9 o <b>total do leil\u00e3o</b>, e a "
            "barra vem empilhada por papel para que a soma n\u00e3o apague a "
            "composi\u00e7\u00e3o \u2014 num dia de prefixado a LTN e a NTN-F "
            "somam, e saber qual das duas pesou \u00e9 metade da leitura. "
            "A LFT n\u00e3o entra: sem DV01 por decis\u00e3o de modelagem, a "
            "fatia dela seria sempre zero. Ela tem gr\u00e1fico pr\u00f3prio, "
            "logo abaixo.",
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
    """A taxa com a idade dela, e um aviso quando ela passou dos 45 dias.

    A ORDEM AQUI IMPORTA. Um vertice que nunca foi a leilao nao tem taxa nem
    data da taxa, e a guarda abaixo ja devolvia travessao para esse caso -- mas
    a data era formatada ANTES dela, e NaT nao aceita strftime. Em 24/09/2026 o
    calendario do 4o trimestre trouxe a LFT 01/12/2032, estreante, e a agenda
    inteira parou de ser gravada por causa de uma celula.
    """
    idade = int(r["taxa_dias_de_idade"]) if pd.notna(r["taxa_dias_de_idade"]) else None
    if idade is None:
        return "\u2014"
    quando = f"{r['taxa_de_quando']:%d/%m}"
    marca = ' class="velha"' if r["taxa_velha"] else ""
    aviso = " \u26a0" if r["taxa_velha"] else ""
    return (f'<span{marca}>{estilo.num_br(r["taxa_pct"], 4)}%'
            f'<small> {quando} \u00b7 {idade}d{aviso}</small></span>')


def tabela_dos_ultimos(dados=None, quantos=None):
    """Os ultimos leiloes, NO MESMO FORMATO da tabela da agenda: papel a papel.

    MESMO FORMATO de proposito. As duas tabelas respondem a mesma pergunta em
    tempos diferentes -- o que vem e o que veio -- e ler as duas exige que as
    colunas estejam no mesmo lugar. A versao anterior parava na familia, e ai nao
    dava para ver que dentro de uma faixa de NTN-B o corte foi num vencimento so.

    RECOLHIDA, e antes do calendario: e referencia, e nao o assunto da pagina.
    Aberta, empurraria a agenda para baixo da dobra.

    A LINHA DE CADA LEILAO SAI EM OUTRA COR e traz a SOMA do dia -- DV e financeiro.
    E o numero que a abertura por papel sozinha nao da.

    A LFT ENTRA, sem DV: ela e mais da metade do financeiro, e deixa-la de fora
    esconderia o maior numero do dia.
    """
    d = _detalhe() if dados is None else dados
    if d.empty:
        return ""
    quantos = quantos or dados_agenda.LEILOES_NA_COMPARACAO
    d = d[d["quantos_atras"] < quantos]
    totais = dados_agenda.total_dos_leiloes(d).set_index("data_leilao")

    linhas = ['<div id="tabela-ultimos">',
              '<p class="legenda">Mesmo formato do calend\u00e1rio abaixo, para poderem ser '
              'lidas lado a lado. A linha em destaque \u00e9 a <b>soma do '
              'leil\u00e3o</b> \u2014 DV01 e financeiro. A fra\u00e7\u00e3o '
              '\u00e9 o que ele colocou do que ofertou; no agregado do '
              'hist\u00f3rico, 68,5% do DV. A <b>LFT</b> aparece sem DV01, por '
              'decis\u00e3o de modelagem, mas com quantidade e financeiro \u2014 '
              'ela \u00e9 mais da metade da emiss\u00e3o.</p>',
              "<table><thead><tr>"
              "<th>papel</th><th>vencimento</th>"
              '<th class="n">taxa m\u00e9dia</th>'
              '<th class="n">ofertou</th>'
              '<th class="n">aceitou</th>'
              '<th class="n">DV01 ofertado</th>'
              '<th class="n">DV01 aceito</th>'
              '<th class="n">colocou</th>'
              '<th class="n">financeiro</th>'
              "</tr></thead><tbody>"]

    for dia, g in d.groupby("data_leilao", sort=False):
        total = totais.loc[dia]
        linhas.append(
            f'<tr class="passado"><td colspan="2"><b>{dia:%d/%m/%Y}</b> '
            f'\u00b7 o leil\u00e3o todo</td>'
            f'<td class="n">\u2014</td>'
            f'<td class="n">{_qtd(total["qtd_ofertada"])}</td>'
            f'<td class="n">{_qtd(total["qtd_aceita"])}</td>'
            f'<td class="n">{_mil(total["dv_ofertado"])}</td>'
            f'<td class="n">{_mil(total["dv_aceito"])}</td>'
            f'<td class="n">{_fracao(total)}</td>'
            f'<td class="n"><b>'
            f'{estilo.num_br(total["financeiro_milhoes"] / 1000, 2)} bi</b>'
            f"</td></tr>")
        for _, r in g.iterrows():
            taxa = ("\u2014" if pd.isna(r["taxa_media_pct"])
                    else estilo.num_br(r["taxa_media_pct"], 4) + "%")
            linhas.append(
                f"<tr><td>{r['titulo']}</td>"
                f"<td>{r['data_vencimento']:%d/%m/%Y}</td>"
                f'<td class="n">{taxa}</td>'
                f'<td class="n">{_qtd(r["qtd_ofertada"])}</td>'
                f'<td class="n">{_qtd(r["qtd_aceita"])}</td>'
                f'<td class="n">{_mil(r["dv_ofertado"])}</td>'
                f'<td class="n">{_mil(r["dv_aceito"])}</td>'
                f'<td class="n">{_fracao(r)}</td>'
                f'<td class="n">'
                f'{estilo.num_br(r["financeiro_milhoes"] / 1000, 2)} bi</td></tr>')

    linhas += ["</tbody></table>", "</div>"]
    return "\n".join(linhas)


def _fracao(r):
    """A fracao colocada: pelo DV quando ha, pela quantidade quando nao ha (LFT)."""
    valor = r.get("colocado_pct")
    if pd.isna(valor):
        valor = r.get("colocado_qtd_pct")
    if pd.isna(valor):
        return "\u2014"
    cor = "" if valor > 0.95 else ' class="baixo"'
    return f'<span{cor}>{estilo.num_br(valor * 100, 0)}%</span>'


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
        return ('<div id="tabela-calendario"><p>O calend\u00e1rio publicado n\u00e3o tem '
                'nenhum leil\u00e3o daqui para a frente.</p></div>')

    linhas = ['<div id="tabela-calendario">',
              "<h2>O calend\u00e1rio, papel a papel</h2>",
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


_DIA_DA_SEMANA = {0: "seg", 1: "ter", 2: "qua", 3: "qui", 4: "sex",
                  5: "s\u00e1b", 6: "dom"}

_PAPEL_DO_INDEXADOR = {"Prefixado": "LTN + NTN-F",
                       "\u00cdndice Pre\u00e7os": "NTN-B",
                       "Taxa Flutuante": "LFT"}

# O motivo do descarte sai por extenso na propria linha, e nao numa nota de
# rodape: quem bate o olho na tabela tem de ler o motivo junto com a data.
_MOTIVO_DO_DESCARTE = ("n\u00e3o consideramos \u00b7 fim do ano")

_NOTA_DA_EXPECTATIVA = (
    "Onde o Tesouro j\u00e1 publicou, a linha \u00e9 <b>transcri\u00e7\u00e3o</b> e "
    "os pap\u00e9is s\u00e3o os que ele listou. Depois disso \u00e9 "
    "<b>infer\u00eancia nossa</b>: leil\u00e3o de LFT e NTN-B na ter\u00e7a, de "
    "prefixado na quinta, antecipando um dia \u00fatil quando cai feriado. As "
    "linhas em cinza s\u00e3o dias que a regra descarta \u2014 supomos que n\u00e3o "
    "h\u00e1 leil\u00e3o nas \u00faltimas semanas do ano. <b>Se o Tesouro publicar "
    "leil\u00e3o numa delas, esta tabela mostra na hora o que a proje\u00e7\u00e3o "
    "deixou de fora.</b>")


def tabela_da_expectativa(hoje=None, ate=None, registros=None):
    """Todo dia de leilao ate o fim do ano, e o que fazemos com cada um.

    PARA QUE ELA EXISTE. A secao de cima transcreve o calendario que o Tesouro
    publicou -- e ele publica poucas semanas de cada vez. Da fronteira em diante
    a projecao da pagina do PAF conta com dias que NOS inferimos, e ate
    25/08/2026 nao havia onde conferir quais eram.

    Ela pediu para dar de bater o nosso contra o dele assim que ele publicar:
    "em um cenario hipotetico que ele va emitir na ultima semana do ano, consigo
    ver rapido que nao estamos considerando esse cenario".

    POR ISSO A TABELA MOSTRA TAMBEM O QUE DESCARTAMOS. Listar so os dias que
    contamos responderia "o que esperamos"; o que ela quer ver e o que NAO
    esperamos. As linhas descartadas pela regra do fim do ano ficam ali, em
    cinza, com o motivo escrito -- uma ausencia so e visivel se estiver escrita.

    Tres situacoes, e cada uma com procedencia diferente:

      publicado          o Tesouro ja disse. Os papeis saem do que ELE listou.
      estimado           inferencia nossa, pela regra de terca e quinta.
      nao consideramos   cai depois do ultimo dia util de emissao de dezembro.
    """
    from .. import calendario_leiloes, rolagem

    hoje = pd.Timestamp(hoje).normalize() if hoje is not None \
        else pd.Timestamp.today().normalize()
    ate = pd.Timestamp(ate) if ate is not None \
        else pd.Timestamp(f"{hoje.year}-12-31")

    # A fronteira nao serve para rotular linha: desde 24/09/2026 ela e a do
    # papel MENOS publicado, e usar ela como data de corte chamaria de
    # estimadas as quintas que o Tesouro ja publicou. A procedencia de cada
    # dia sai de papeis_publicados, que e a lista dele.
    contados, _ = calendario_leiloes.dias_ate(
        ate, registros=registros, hoje=hoje)
    contados = set(contados)
    possiveis = calendario_leiloes.dias_possiveis(hoje, ate)
    # Um dia publicado pode cair fora da grade de terca/quinta -- leilao extra,
    # ou remarcacao. Ele entra na lista mesmo assim: a tabela e sobre o que vai
    # acontecer, e nao sobre o que a nossa regra previa.
    todos = sorted(set(possiveis) | contados)

    papeis_publicados = _papeis_por_dia(registros)
    por_dia_da_semana = {}
    for indexador, dia in rolagem.DIA_DO_PAPEL.items():
        por_dia_da_semana.setdefault(dia, []).append(_PAPEL_DO_INDEXADOR[indexador])

    linhas = ['<div id="tabela-expectativa">',
              "<h2>O que estamos contando daqui at\u00e9 "
              f"{ate:%d/%m/%Y}</h2>",
              f'<p class="legenda">{_NOTA_DA_EXPECTATIVA}</p>',
              "<table>",
              "<thead><tr><th>data</th><th>dia</th><th>pap\u00e9is</th>"
              "<th>de onde vem</th></tr></thead><tbody>"]

    quantos = {"publicado": 0, "estimado": 0}
    for dia in todos:
        if dia in contados and dia in papeis_publicados:
            situacao, classe = "publicado", "publicado"
            papeis = papeis_publicados.get(dia) or "\u2014"
        elif dia in contados:
            situacao, classe = "estimado", "estimado"
            # ORDENADO, como o publicado: o do Tesouro sai da lista dele
            # ja em ordem, e o estimado saia na ordem do dicionario --
            # "LFT + NTN-B" numa linha e "NTN-B + LFT" na de baixo, para o
            # mesmo dia da semana. Nada de errado no numero, mas a tabela e
            # para bater o olho, e olho tropeca nisso.
            papeis = " + ".join(
                sorted(por_dia_da_semana.get(dia.dayofweek, []))) or "\u2014"
        else:
            situacao, classe = _MOTIVO_DO_DESCARTE, "fora"
            papeis = "\u2014"
        if situacao in quantos:
            quantos[situacao] += 1
        linhas.append(
            f'<tr class="{classe}"><td>{dia:%d/%m/%Y}</td>'
            f"<td>{_DIA_DA_SEMANA[dia.dayofweek]}</td>"
            f"<td>{papeis}</td><td>{situacao}</td></tr>")

    linhas += ["</tbody></table>",
               f'<p class="rodape">{quantos["publicado"]} dia(s) publicado(s) e '
               f'{quantos["estimado"]} estimado(s) entram na proje\u00e7\u00e3o da '
               f'p\u00e1gina do PAF \u2014 {quantos["publicado"] + quantos["estimado"]} '
               f'no total. As linhas em cinza N\u00c3O entram.</p>',
               "</div>"]
    return "\n".join(linhas)


def _papeis_por_dia(registros):
    """Os papeis que o Tesouro listou em cada dia do calendario publicado.

    O IMPORT FALTAVA, e o `except Exception` o escondia. Ate 24/09/2026 esta
    funcao chamava parse_api_leiloes sem que o modulo jamais o importasse: o
    NameError caia no except, virava {}, e a coluna "papeis" das linhas
    publicadas mostrava travessao. Silencioso, porque a rotulagem da linha vinha
    da data da fronteira e nao deste mapa -- ninguem cruzava os dois.

    O except agora e LookupError, que e o que calendario() levanta quando a
    resposta nao tem as colunas esperadas. Erro de programacao volta a estourar.
    """
    from .. import parse_api_leiloes

    if registros is not None and not len(registros):
        return {}
    try:
        d = _dados() if registros is None else parse_api_leiloes.calendario(registros)
    except LookupError:
        return {}
    saida = {}
    for dia, g in d.groupby(d["data_leilao"].dt.normalize()):
        saida[dia] = " + ".join(sorted(set(g["titulo"].astype(str))))
    return saida


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
#tabela-expectativa { margin: 26px auto 40px; max-width: 1180px; }
#tabela-expectativa table { border-collapse: collapse; width: 100%;
  font-size: 13.5px; }
#tabela-expectativa th, #tabela-expectativa td { padding: 5px 10px;
  text-align: left; border-bottom: 1px solid #eee; }
#tabela-expectativa th { font-weight: 600; color: var(--fraco);
  border-bottom: 2px solid #ccc; }
#tabela-expectativa tr.fora td { color: var(--fraco); font-style: italic; }
#tabela-expectativa tr.publicado td:last-child { font-weight: 600; }
#tabela-calendario { margin: 26px auto 40px; max-width: 1180px; }
#tabela-calendario table { border-collapse: collapse; width: 100%;
                       font-size: 13px; }
#tabela-calendario th, #tabela-calendario td { padding: 5px 9px; text-align: left;
                                       border-bottom: 1px solid #e6e6e6; }
#tabela-calendario th { font-weight: 600; color: var(--fraco);
                    border-bottom: 2px solid #ccc; }
#tabela-calendario td.n, #tabela-calendario th.n { text-align: right;
                                           font-variant-numeric: tabular-nums; }
#tabela-calendario tr.dia td { background: #eaf1f8; font-weight: 600;
                           padding-top: 9px; }
#tabela-calendario small { color: var(--fraco); font-size: 11px; }
#tabela-calendario .velha { color: #a33; }
.secao { margin: 0 auto 18px; max-width: 1180px; }
.secao > summary { cursor: pointer; font-size: 16px; font-weight: 600;
  color: var(--tinta); padding: 8px 0 8px 10px; border-left: 4px solid #ccc;
  list-style-position: outside; }
.secao > summary:hover { background: #fafafa; }
/* O HISTORICO em tom quente, o CALENDARIO em tom frio. As duas tabelas tem o
   mesmo formato de proposito, e a cor e o que diz num relance qual delas se esta
   lendo -- o que ja aconteceu ou o que ainda vai acontecer. */
.secao-ultimos > summary { border-left-color: #b08968; }
.secao-calendario > summary { border-left-color: #3d7ab8; }
#tabela-ultimos { margin: 8px auto 10px; max-width: 1180px; }
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
#tabela-ultimos .baixo { color: #c00000; font-weight: 600; }\n#tabela-ultimos tr.passado td { background: #f4efe8;\n    border-top: 2px solid #ddd; padding-top: 8px; }
"""


# As tres secoes da pagina, na ordem em que aparecem. Todas RECOLHIVEIS, e a
# primeira aberta: quem abre a pagina ve os graficos, e desce para o resto quando
# quiser. Sem isso a pagina tem quase dois metros de rolagem.
SECOES = [
    ("graficos", "Os gr\u00e1ficos", True),
    ("ultimos", "Os \u00faltimos leil\u00f5es \u00b7 hist\u00f3rico", False),
    ("calendario", "Calend\u00e1rio emiss\u00f5es Tesouro", False),
    ("expectativa", "Expectativa de calend\u00e1rio", False),
]


def _recolhe(conteudo, chave, rotulo, aberta):
    """Poe um bloco dentro de um <details>, com a setinha e o rotulo.

    <details>/<summary> e HTML puro: a setinha nao custa uma linha de JavaScript, e
    o conteudo continua no arquivo -- quem procurar com Ctrl+F acha, e quem imprimir
    leva tudo.
    """
    marca = " open" if aberta else ""
    return (f'<details class="secao secao-{chave}"{marca}>'
            f"<summary>{rotulo}</summary>\n{conteudo}\n</details>")


def grava(caminho=None, hoje=None):
    """Grava a pagina do calendario e devolve o caminho."""
    from .. import config

    limpar_cache()
    if hoje is not None:
        _EM_CACHE[str(hoje)] = dados_agenda.proximos(hoje=hoje)
        _EM_CACHE[str(None)] = _EM_CACHE[str(hoje)]

    caminho = caminho or (config.PROCESSED_DIR / ARQUIVO)
    # agrupar=False: esta pagina faz o proprio seccionamento em tres, e com o
    # agrupamento do dashboard por cima ela saia com duas setinhas aninhadas
    # dizendo quase a mesma coisa.
    escrito = dashboard.grava(caminho, [("agenda", None)], REGISTRO, GRUPOS,
                              "Calend\u00e1rio de leil\u00f5es", agrupar=False)
    html = escrito.read_text(encoding="utf-8")

    # OS GRAFICOS ficam entre <main> e </main>, montados pelo dashboard. Aqui eles
    # sao envolvidos num <details> sem que o montador precise saber disso -- a mesma
    # tecnica da barra de paginas.
    # ANCORADO NO FIM DO CABECALHO, e nao na abertura do <main>: a marca do main
    # aparece antes, dentro de um comentario do CSS, e o recorte pegava metade da
    # folha de estilo junto. A do cabecalho so existe uma vez.
    marca = "</header>"
    inicio = html.index(marca) + len(marca)
    fim = html.rindex("</main>")
    graficos = html[inicio:fim]

    corpo = "\n".join([
        _recolhe(graficos, *SECOES[0][:1] + SECOES[0][1:]),
        _recolhe(tabela_dos_ultimos(), *SECOES[1][:1] + SECOES[1][1:]),
        _recolhe(tabela(), *SECOES[2][:1] + SECOES[2][1:]),
        _recolhe(tabela_da_expectativa(hoje=hoje),
                 *SECOES[3][:1] + SECOES[3][1:]),
    ])
    html = html[:inicio] + "\n" + corpo + "\n" + html[fim:]
    html = html.replace("</style>", _CSS + "</style>", 1)
    escrito.write_text(html, encoding="utf-8")
    return escrito
