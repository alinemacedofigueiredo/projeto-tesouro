"""Cores, formato de numero e de data, e reprodutibilidade do SVG.

Tudo que se repetiria em dezesseis graficos mora aqui. Em especial tres coisas que
o matplotlib nao da de graca: mes em portugues (a locale do sistema devolve "may"),
numero no formato brasileiro, e SVG reprodutivel.
"""

MES = {1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun",
       7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez"}

MES_LONGO = {1: "Janeiro", 2: "Fevereiro", 3: "Mar\u00e7o", 4: "Abril",
             5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
             9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"}

# Paleta unica do projeto. Os indexadores seguem as cores que a usuaria aprovou nos
# rascunhos; os papeis usam a mesma familia para o mesmo indexador (LTN e NTN-F em
# azul porque sao prefixados, NTN-B em roxo, LFT em cinza).
COR = {
    # indexadores
    "Prefixado": "#1f6feb",
    "Indice Precos": "#ff7f0e",
    "Taxa Flutuante": "#2ca02c",
    "Cambio": "#d62728",
    "Demais": "#9467bd",
    # papeis
    "LTN": "#2f5597",
    "NTN-F": "#8faadc",
    "NTN-B": "#674ea7",
    "LFT": "#7f7f7f",
    "NTN-C": "#8c564b",
    # A NTN-D nao e emitida desde 2002, mas aparece na janela completa do grafico
    # de leiloes. Sem cor, o desenho levanta KeyError -- e so na janela completa,
    # que e o pior tipo de defeito: passa nos 12 anos e quebra na serie inteira.
    "NTN-D": "#c0504d",
    "Outros": "#c9c9c9",
    # detentores, na paleta das paginas do RMD
    "Inst. Financeiras": "#1f3864",
    "Fundos": "#3d9be9",
    "Previdencia": "#a6a6a6",
    "Nao-residente": "#ed7d31",
    "Demais Grupos": "#70ad47",
    # os quatro que a aba 2.8 abre e a 2.7 agrupa em "Demais Grupos".
    # "Outros Detentores" tem nome proprio porque "Outros" ja e a chave do
    # cinza dos papeis, e a paleta e um dicionario so.
    "Governo": "#8c6d31",
    "Seguradoras": "#b07aa1",
    "Tesouro Direto": "#e15759",
    "Outros Detentores": "#bab0ac",
    # elementos
    "banda": "#c00000",
    "neutro": "#666666",
}


def aplicar_estilo():
    """Fixa os parametros globais do matplotlib. Chamar antes de desenhar.

    O svg.hashsalt e o que torna o SVG reprodutivel: sem ele o matplotlib sorteia
    os identificadores internos e dois desenhos identicos geram arquivos
    diferentes, tornando impossivel saber se o dashboard mudou porque o dado mudou.
    """
    # O import mora AQUI, e nao no topo: a spec 3.1 vende que a camada de dado nao
    # conhece matplotlib, e como toda funcao de dado chama estilo.recorta, o import
    # no topo fazia `import tesouro.graficos.custo` puxar matplotlib. A propriedade
    # existia no espirito e nao no mecanismo. O resto do modulo ja adiava os imports
    # de matplotlib.dates e matplotlib.ticker pelo mesmo motivo.
    import matplotlib

    matplotlib.use("Agg")
    matplotlib.rcParams["svg.hashsalt"] = "tesouro"
    matplotlib.rcParams["figure.dpi"] = 110
    matplotlib.rcParams["axes.grid"] = False
    matplotlib.rcParams["font.size"] = 10


def salvar_svg(figura, destino, bbox_inches="tight"):
    """Grava a figura em SVG de forma REPRODUTIVEL.

    Duas coisas fazem o SVG do matplotlib mudar entre execucoes com o mesmo dado.
    A primeira sao os identificadores internos, que o svg.hashsalt de
    aplicar_estilo() fixa. A segunda e a data de criacao, que ele escreve em
    <dc:date> com precisao de microssegundo -- e essa so sai passando
    metadata={"Date": None} no savefig.

    O helper existe porque a segunda parte e invisivel: com o hashsalt fixo e sem
    isto, dois desenhos do mesmo dado diferem em UMA linha, no meio do cabecalho
    RDF, e quem comparar dois dashboards vai achar que o dado mudou. Aqui
    reprodutibilidade e propriedade de uma funcao, nao convencao que todo mundo
    precisa lembrar em cada savefig.
    """
    figura.savefig(destino, format="svg", bbox_inches=bbox_inches,
                   metadata={"Date": None})


# DUAS JANELAS QUE O LEILAO PEDE E O ESTOQUE NAO.
#
# O dashboard do RMD fala em anos, porque estoque de divida se move em anos. Leilao
# se move em semanas: "5 anos" mostra 250 barras de 3 pixels, e a barra de hoje --
# a que motivou a pagina existir -- some no meio delas.
#
# Sao namedtuple e nao string para que recorta() as reconheca por tipo, e nao por
# decifrar texto. ATENCAO: namedtuple E tuple, entao recorta() precisa testa-las
# ANTES da forma (de, ate) -- senao um Ultimos(50) seria lido como o par (50,).
import collections

Ultimos = collections.namedtuple("Ultimos", "quantidade")
DesdeJaneiro = collections.namedtuple("DesdeJaneiro", "anos_atras")


def recorta(df, janela):
    """Recorte de um DataFrame indexado por data.

    'janela' vem em cinco formas:
      None                       -> a serie inteira
      um numero de anos          -> os ultimos N anos
      um par (de, ate)           -> o intervalo pedido na linha de comando
      Ultimos(n)                 -> as ultimas N linhas, seja qual for a data
      DesdeJaneiro(k)            -> desde 1o de janeiro de k anos atras (0 = no ano)

    A terceira existe para que --de/--ate chegue as dez funcoes de dado sem mudar
    a assinatura de nenhuma delas: todas ja chamam esta funcao. As duas ultimas
    existem para os graficos de leilao, cuja escala e de semanas e nao de anos.
    """
    import pandas as pd
    if janela is None:
        return df

    # ANTES do teste de tuple: namedtuple e tuple, e a ordem inversa leria
    # Ultimos(50) como o par (de, ate) = (50,) e estouraria no desempacotamento.
    if isinstance(janela, Ultimos):
        # A ultima linha e a mais recente porque o indice vem ordenado das funcoes
        # de dado -- todas terminam num groupby, que ordena.
        return df.tail(janela.quantidade)

    if isinstance(janela, DesdeJaneiro):
        # Ancorado no fim da SERIE, e nao em datetime.today(): um grafico que muda
        # de conteudo conforme o dia em que roda quebra a reprodutibilidade, que e
        # testada. Com a serie terminando hoje, da no mesmo.
        ano = df.index.max().year - janela.anos_atras
        return df[df.index >= pd.Timestamp(year=ano, month=1, day=1)]

    if isinstance(janela, tuple):
        de, ate = janela
        recorte = df[(df.index >= de) & (df.index <= ate)]
        # Recorte vazio falhava la na frente, dentro do matplotlib, com "Axis limits
        # cannot be NaN or Inf" e outras tres mensagens que nao dizem o que houve.
        # Uma guarda aqui conserta os quatorze graficos de uma vez.
        if recorte.empty:
            raise LookupError(
                f"o recorte de {de.date()} a {ate.date()} nao pega nenhum mes da "
                f"serie, que vai de {df.index.min().date()} a "
                f"{df.index.max().date()}"
            )
        return recorte
    return df[df.index >= df.index.max() - pd.DateOffset(years=janela)]


def num_br(valor, casas=1):
    """Numero no formato brasileiro: ponto de milhar, virgula decimal."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def rotulo_mes(d):
    """'mai/26' a partir de uma data."""
    return f"{MES[d.month]}/{d.year % 100:02d}"


def eixo_anual(ax, a_cada=1):
    """Marca o eixo do tempo, com a densidade que a JANELA pede.

    A pagina do RMD usa ~170 rotulos mensais e ninguem le. Marca anual com dado
    mensal e legivel e nao perde resolucao.

    MAS A JANELA NAO E SEMPRE LONGA. Em 21/08/2026 o dashboard ganhou janelas de 12
    meses e de 3 anos, e com 'a_cada' fixo o eixo de doze meses saia com UM rotulo
    -- o unico ano que a janela atravessa. O grafico ficava sem eixo do tempo.
    Visto na figura, e nao no codigo.
    """
    import matplotlib.dates as mdates

    inicio, fim = ax.get_xlim()
    anos = (fim - inicio) / 365.25

    if anos <= 2.2:
        # Um rotulo por trimestre, em mes/ano. Doze meses dao quatro ou cinco.
        ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 4, 7, 10)))
        from matplotlib.ticker import FuncFormatter
        ax.xaxis.set_major_formatter(FuncFormatter(
            lambda x, _: rotulo_mes(mdates.num2date(x))))
        ax.xaxis.set_minor_locator(mdates.MonthLocator())
        return

    passo = 1 if anos <= 8 else a_cada
    ax.xaxis.set_major_locator(mdates.YearLocator(passo))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    if passo > 1:
        ax.xaxis.set_minor_locator(mdates.YearLocator())


def grade_fina(ax, maior, menor, eixo="y"):
    """Grade com linha cheia a cada 'maior' e linha fraca a cada 'menor'."""
    from matplotlib.ticker import MultipleLocator
    alvo = ax.yaxis if eixo == "y" else ax.xaxis
    alvo.set_major_locator(MultipleLocator(maior))
    alvo.set_minor_locator(MultipleLocator(menor))
    ax.grid(axis=eixo, which="major", alpha=0.30)
    ax.grid(axis=eixo, which="minor", alpha=0.12)
