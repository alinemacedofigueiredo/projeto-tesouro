"""A pagina contra o PAF: onde estamos hoje, e onde fechamos o ano.

E PAGINA PROPRIA, e nao secao do dashboard, por tres razoes que estao na spec 6.4. A
que decide: as entregas 4 e 5 sao a pergunta e a resposta -- "estou dentro?" e "o que
faco para entrar?" -- e a 5 acrescenta um bloco AQUI, em vez de criar outra pagina.

A que quase passou batido: esta pagina muda a cada leilao liquidado, e o dashboard
muda uma vez por mes. Enterrar uma tabela que muda toda semana num arquivo de 4 MB e
reescrever 4 MB para mudar uma linha.
"""

from .. import config
from . import banda, dashboard

ARQUIVO = "paf.html"
GRUPOS = ["Contra o PAF"]
REGISTRO = []

SECOES = [
    ("hoje", "Onde estamos hoje", True),
    ("projecao", "Onde fechamos o ano", False),
]

# O achado do historico, que perdeu os sete graficos e ficou como texto. Ver spec
# 7.3: aquele bloco era analise e nao monitoramento.
_ACHADO = (
    "<p class='achado'>Em 23 anos de PAF, o Tesouro fechou o ano dentro da banda "
    "em <b>70% dos casos pela banda original</b> e <b>79% pela vigente</b>. Em "
    "<b>14 de 14</b> revis\u00f5es que inverteram o veredito, a banda revisada "
    "p\u00f4s o realizado <i>dentro</i> \u2014 nunca fora.</p>")

# NENHUMA TAG LITERAL DENTRO DE COMENTARIO DE CSS -- e por isso que esta folha nao
# tem comentario nenhum. Um <main> escrito dentro de um comentario aparece antes do
# <main> de verdade, e o recorte de grava() leva metade da folha de estilo junto.
# Defeito real, achado em 20/08/2026.
_CSS = """
#tabela-hoje, #tabela-projecao { margin: 20px auto 30px; max-width: 1180px; }
#tabela-hoje table, #tabela-projecao table { border-collapse: collapse;
  width: 100%; font-size: 13.5px; }
#tabela-hoje th, #tabela-hoje td, #tabela-projecao th, #tabela-projecao td {
  padding: 6px 10px; text-align: left; border-bottom: 1px solid #e6e6e6; }
#tabela-hoje th, #tabela-projecao th { font-weight: 600; color: var(--fraco);
  border-bottom: 2px solid #ccc; }
td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; }
tr.parado td { color: var(--fraco); font-style: italic; }
p.rodape, p.achado { font-size: 12.5px; color: var(--fraco); max-width: 1180px;
  margin: 6px auto 0; }
.secao { margin: 0 auto 18px; max-width: 1180px; }
.secao > summary { cursor: pointer; font-size: 16px; font-weight: 600;
  color: var(--tinta); padding: 8px 0 8px 10px; border-left: 4px solid #ccc;
  list-style-position: outside; }
.secao > summary:hover { background: #fafafa; }
.secao-hoje > summary { border-left-color: #3d7ab8; }
.secao-projecao > summary { border-left-color: #b08968; }
"""


def _recolhe(conteudo, chave, rotulo, aberta):
    """Poe um bloco dentro de um <details>, com a setinha e o rotulo.

    <details>/<summary> e HTML puro: a setinha nao custa uma linha de JavaScript, e
    o conteudo continua no arquivo -- quem procurar com Ctrl+F acha, e quem imprimir
    leva tudo.
    """
    marca = " open" if aberta else ""
    return (f'<details class="secao secao-{chave}"{marca}>'
            f"<summary>{rotulo}</summary>\n{conteudo}\n</details>")


# O RODAPE E DA TABELA, e nao desta pagina. A Task 9 fez `tabela()` monta-lo
# sozinha a partir dos attrs que `dados_hoje` e `dados_projecao` ja carregam -- a
# data do "hoje", quantos dias de leilao entraram na rolagem, e a premissa inteira
# da projecao. Um segundo rodape aqui duplicaria a fonte da verdade, e a pagina
# poderia acabar dizendo uma coisa enquanto a tabela diz outra.


def grava(caminho=None, hoje=None, registros=None):
    """Grava a pagina do PAF e devolve o caminho.

    'registros' e a resposta ja baixada do calendario da API. Passar uma LISTA
    VAZIA e o modo offline: `dias_ate` cai para o calendario inteiramente
    estimado, e o rodape da projecao passa a dizer isso com todas as letras. E
    o que o pipeline faz com --sem-coleta, onde a rede esta proibida.

    Nao e degradacao silenciosa: a pagina sai, e sai dizendo de onde veio o
    calendario que usou.
    """
    caminho = caminho or (config.PROCESSED_DIR / ARQUIVO)
    escrito = dashboard.grava(caminho, [("paf", None)], REGISTRO, GRUPOS,
                              "Contra o PAF", agrupar=False)
    html = escrito.read_text(encoding="utf-8")

    # ANCORADO NO FIM DO CABECALHO, e nao na abertura do <main>: a marca do main
    # aparece antes, dentro de um comentario do CSS, e o recorte pegava metade da
    # folha de estilo junto. Defeito real, achado em 20/08/2026.
    marca = "</header>"
    inicio = html.index(marca) + len(marca)
    fim = html.rindex("</main>")

    de_hoje = banda.dados_hoje(hoje)
    projetado = banda.dados_projecao(registros=registros)
    corpo = "\n".join([
        _recolhe(banda.tabela(de_hoje, "tabela-hoje"), *SECOES[0]),
        _recolhe(banda.tabela(projetado, "tabela-projecao") + _ACHADO,
                 *SECOES[1]),
    ])
    html = html[:inicio] + "\n" + corpo + "\n" + html[fim:]
    html = html.replace("</style>", _CSS + "</style>", 1)
    escrito.write_text(html, encoding="utf-8")
    return escrito
