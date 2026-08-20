"""Emissao vista pelo leilao: financeiro de um lado, DV do outro.

O RMD conta emissao em reais. Estes graficos contam nas duas moedas ao mesmo tempo,
e a diferenca entre elas e o assunto: dez bilhoes de LTN curta e dez bilhoes de NTN-B
2060 sao a mesma barra na aba 1.2 e coisas incomparaveis aqui.

TODOS os graficos usam o ACEITO no leilao, nunca o ofertado. Ofertado e intencao;
aceito e o que virou divida.

Tres eixos de escolha, porque a pergunta muda a resposta:

  - COMPRA: incluir ou nao os leiloes de recompra, que entram com sinal negativo,
    como resgate. Sem eles se ve emissao bruta; com eles, o liquido;
  - SEGUNDA VOLTA: incluir ou nao. Para o tamanho do leilao no dia, o que importa e
    o que foi ofertado e colocado na primeira; para quanto de risco entrou no
    mercado num periodo, a segunda volta faz parte e tirar subestima;
  - JANELA: o recorte de tempo, como no resto do dashboard.

A LFT nao tem DV, por decisao de modelagem da entrega 2 -- ela aparece so em
financeiro, com media movel de 3 meses.
"""
import pandas as pd

from .. import config, leiloes_recentes
from . import estilo

# A ordem em que as familias empilham e aparecem na legenda: do mais curto para o
# mais longo, que e a ordem em que elas acrescentam risco.
ORDEM_FAMILIAS = ["LFT", "LTN", "NTN-F", "NTN-B curta", "NTN-B longa"]

_COR_FAMILIA = {"LFT": "LFT", "LTN": "LTN", "NTN-F": "NTN-F",
                "NTN-B curta": "NTN-B", "NTN-B longa": "NTN-C"}

# Os recortes que ganham grafico proprio de dois eixos.
RECORTES = {
    "NTN-B": ("NTN-B curta", "NTN-B longa"),
    "NTN-B curta": ("NTN-B curta",),
    "NTN-B longa": ("NTN-B longa",),
    "NTN-F": ("NTN-F",),
    "LTN": ("LTN",),
    "LTN + NTN-F": ("LTN", "NTN-F"),
    "LFT": ("LFT",),
}

_COR_FINANCEIRO = "#3d9be9"
_COR_DV = "#c00000"


# TRES APARENCIAS PARA TRES MOMENTOS. Um leilao aparece na tela tres vezes, e a
# barra vai ficando mais solida conforme o numero fica mais firme:
#
#   ofertado -- so contorno, vazia por dentro. E um TETO: a quantidade anunciada,
#               que historicamente cai para 83,9% dela, com taxa emprestada do
#               leilao anterior;
#   aceito   -- hachurada. A quantidade ja e final; a taxa publicada na hora pode
#               ser preliminar;
#   planilha -- solida. Nao muda mais.
#
# E hachura e contorno, e nao cor, porque no grafico empilhado a cor JA significa
# papel -- roubar uma cor para significar momento criaria duas leituras para o
# mesmo sinal.
HACHURA_PROVISORIO = "///"
HACHURA_ACEITO = "///"
HACHURA_OFERTADO = ""

ESTAGIO_MAIS_FIRME = "planilha"

# A LEGENDA NAO DIZ DE ONDE VEIO A TAXA, e ha um motivo. A proveniencia varia linha
# a linha -- ela digita a taxa de alguns papeis e deixa outros em branco -- e uma
# barra somada pode ter as duas dentro. Afirmar "a taxa e a do leilao anterior" na
# legenda seria mentira nos dias em que ela digitou todas, que foi o primeiro dia de
# uso. Quem diz e o aviso do topo da pagina, que conta as duas.
# CURTO DE PROPOSITO. A primeira versao explicava o estagio inteiro na legenda
# ("aceito hoje (API) - muda quando a planilha sair"), e a frase competia com o
# grafico. A explicacao mora no texto da pagina, que e onde se le texto; a legenda
# so precisa dizer qual barra e qual.
_ROTULO_DO_ESTAGIO = {
    "ofertado": "ofertado hoje (teto)",
    "aceito": "leil\u00e3o de hoje",
}


def _menos_firme(estagios):
    """De um grupo de linhas, o estagio menos adiantado.

    Um dia de leilao soma varios papeis. Se um deles ainda e teto, a soma daquele
    dia tambem e teto -- ela nao pode ser mais firme que a sua parte mais fraca.
    """
    presentes = [e for e in estagios if isinstance(e, str)]
    if not presentes:
        return ESTAGIO_MAIS_FIRME
    return min(presentes, key=lambda e: leiloes_recentes.ORDEM_DOS_ESTAGIOS.get(e, 9))


def _base(com_compra=False, com_segunda_volta=True):
    """O CSV do DV por leilao, com os dois filtros de escolha aplicados."""
    d = pd.read_csv(config.PROCESSED_DIR / "dv_emitido_por_leilao.csv",
                    parse_dates=["data_leilao", "data_liquidacao"])
    # CSVs gravados antes de a API existir nao tem a coluna. Sem este default, todo
    # grafico quebraria ao ler um arquivo antigo -- e o certo e ele continuar
    # lendo, dizendo que tudo ali e definitivo, porque e.
    if "estagio" not in d.columns:
        d["estagio"] = "planilha" if "origem" not in d.columns else d["origem"].map(
            {"planilha": "planilha", "api": "aceito"}).fillna("planilha")
    if not com_compra:
        d = d[d["operacao"] == "venda"]
    if not com_segunda_volta:
        # O rotulo vem do arquivo do Tesouro com o ordinal por extenso.
        d = d[~d["volta"].fillna("").str.startswith("2")]
    return d


def por_dia(recorte, janela=None, com_compra=False, com_segunda_volta=True):
    """Financeiro e DV somados por DIA DE LEILAO, para um recorte de papel.

    Um dia de leilao pode ter varios vertices do mesmo papel; aqui eles somam, que e
    a leitura de "quanto entrou naquele dia".
    """
    if recorte not in RECORTES:
        raise LookupError(
            f"recorte '{recorte}' nao existe. Os que existem: "
            f"{sorted(RECORTES)}."
        )
    d = _base(com_compra, com_segunda_volta)
    d = d[d["familia"].isin(RECORTES[recorte])]

    saida = d.groupby("data_leilao").agg(
        financeiro_milhoes=("financeiro_milhoes", "sum"),
        dv_milhoes=("dv_milhoes", "sum"),
        leiloes=("titulo", "size"),
        # A barra do dia recebe o estagio MENOS firme entre as linhas dele: se um
        # papel do dia ainda e teto, o total daquele dia tambem e teto. Marcar so
        # "parte" de uma barra somada nao existe.
        estagio=("estagio", _menos_firme),
    )
    # A LFT nao tem DV: a soma de uma coluna toda vazia devolve zero, e zero aqui
    # seria uma afirmacao sobre o risco dela. Volta a ser vazio.
    if d["dv_milhoes"].notna().sum() == 0:
        saida["dv_milhoes"] = float("nan")
    return estilo.recorta(saida, janela)


def por_semana(janela=None, com_compra=False, com_segunda_volta=True):
    """Financeiro e DV somados por SEMANA, sem a LFT.

    Sem a LFT porque o grafico tem os dois eixos e ela so tem um dos dois numeros --
    inclui-la faria o financeiro e o DV falarem de conjuntos diferentes de papel.
    """
    d = _base(com_compra, com_segunda_volta)
    d = d[d["familia"] != "LFT"]
    semana = d["data_leilao"].dt.to_period("W").dt.start_time
    saida = d.groupby(semana).agg(
        financeiro_milhoes=("financeiro_milhoes", "sum"),
        dv_milhoes=("dv_milhoes", "sum"),
        estagio=("estagio", _menos_firme),
    )
    saida.index.name = "semana"
    return estilo.recorta(saida, janela)


def por_semana_por_familia(janela=None, com_compra=False,
                           com_segunda_volta=True):
    """A soma da semana, com o financeiro aberto por familia. Sem LFT.

    Sem a LFT pelo mesmo motivo de por_semana(): o grafico tem dois eixos e ela so
    tem um dos dois numeros -- inclui-la faria o financeiro e o DV falarem de
    conjuntos diferentes de papel. Ela tem o grafico empilhado so dela.
    """
    d = _base(com_compra, com_segunda_volta)
    d = d[d["familia"] != "LFT"]
    semana = d["data_leilao"].dt.to_period("W").dt.start_time

    piv = d.pivot_table(index=semana, columns="familia",
                        values="financeiro_milhoes", aggfunc="sum").fillna(0.0)
    familias = [f for f in ORDEM_FAMILIAS if f != "LFT"]
    for familia in familias:
        if familia not in piv.columns:
            piv[familia] = 0.0
    piv = piv[familias]

    resto = d.groupby(semana).agg(
        financeiro_milhoes=("financeiro_milhoes", "sum"),
        dv_milhoes=("dv_milhoes", "sum"),
        estagio=("estagio", _menos_firme),
    )
    saida = piv.join(resto)
    saida.index.name = "semana"
    return estilo.recorta(saida, janela)


def financeiro_semanal_por_papel(janela=None, com_compra=False,
                                 com_segunda_volta=True):
    """Financeiro por semana, uma coluna por familia -- para a barra empilhada.

    Aqui a LFT ENTRA: e um grafico de financeiro so, e ela e mais da metade dele.
    """
    d = _base(com_compra, com_segunda_volta)
    semana = d["data_leilao"].dt.to_period("W").dt.start_time
    piv = d.pivot_table(index=semana, columns="familia",
                        values="financeiro_milhoes", aggfunc="sum").fillna(0.0)
    piv.index.name = "semana"
    for familia in ORDEM_FAMILIAS:
        if familia not in piv.columns:
            piv[familia] = 0.0
    piv = piv[ORDEM_FAMILIAS]
    piv["estagio"] = d.groupby(semana)["estagio"].apply(_menos_firme).reindex(
        piv.index).fillna(ESTAGIO_MAIS_FIRME)
    return estilo.recorta(piv, janela)


def por_dia_por_familia(recorte, janela=None, com_compra=False,
                        com_segunda_volta=True):
    """Como por_dia(), mas com o financeiro ABERTO POR FAMILIA de papel.

    Serve aos graficos em que a barra e empilhada: no recorte "LTN + NTN-F" a barra
    somada esconde qual dos dois moveu o dia, e sao papeis com prazos muito
    diferentes. O DV continua vindo somado, porque a linha e uma so.
    """
    if recorte not in RECORTES:
        raise LookupError(f"recorte '{recorte}' nao existe: {sorted(RECORTES)}.")
    d = _base(com_compra, com_segunda_volta)
    d = d[d["familia"].isin(RECORTES[recorte])]

    piv = d.pivot_table(index="data_leilao", columns="familia",
                        values="financeiro_milhoes", aggfunc="sum").fillna(0.0)
    for familia in RECORTES[recorte]:
        if familia not in piv.columns:
            piv[familia] = 0.0
    piv = piv[[f for f in ORDEM_FAMILIAS if f in RECORTES[recorte]]]

    resto = d.groupby("data_leilao").agg(
        financeiro_milhoes=("financeiro_milhoes", "sum"),
        dv_milhoes=("dv_milhoes", "sum"),
        estagio=("estagio", _menos_firme),
    )
    if d["dv_milhoes"].notna().sum() == 0:
        resto["dv_milhoes"] = float("nan")
    return estilo.recorta(piv.join(resto), janela)


def acumulado(recorte, meses=3, janela=None, com_compra=False,
              com_segunda_volta=True):
    """Soma movel dos ultimos N MESES de financeiro e de DV, por dia de leilao.

    A serie diaria de leilao e serrilhada por construcao: o Tesouro leiloa NTN-B num
    dia e prefixado no outro, entao dia sim dia nao a barra e zero para um recorte.
    A soma movel tira o serrilhado e mostra o que o trimestre acumulou, que e a
    escala em que emissao se compara com PAF e com meta.

    A JANELA E DE CALENDARIO, e nao de numero de leiloes: "ultimos 3 meses" tem de
    querer dizer tres meses mesmo, inclusive quando o Tesouro muda a frequencia dos
    leiloes no meio do periodo. Por isso a soma corre sobre uma serie diaria
    reindexada, e nao sobre as linhas.
    """
    if recorte not in RECORTES:
        raise LookupError(f"recorte '{recorte}' nao existe: {sorted(RECORTES)}.")
    d = _base(com_compra, com_segunda_volta)
    d = d[d["familia"].isin(RECORTES[recorte])]
    if d.empty:
        return pd.DataFrame(columns=["financeiro_milhoes", "dv_milhoes"])

    por_leilao = d.groupby("data_leilao").agg(
        financeiro_milhoes=("financeiro_milhoes", "sum"),
        dv_milhoes=("dv_milhoes", "sum"),
    )
    tem_dv = d["dv_milhoes"].notna().sum() > 0

    # Reindexa em dias corridos para que a janela seja de calendario, soma, e volta
    # a ficar so com os dias em que houve leilao -- desenhar os zeros no meio faria
    # a linha cair todo dia sem leilao.
    diario = por_leilao.reindex(
        pd.date_range(por_leilao.index.min(), por_leilao.index.max(), freq="D")
    ).fillna(0.0)
    soma = diario.rolling(f"{int(meses * 30.44)}D").sum()
    soma = soma.loc[por_leilao.index]
    if not tem_dv:
        soma["dv_milhoes"] = float("nan")
    soma.index.name = "data_leilao"
    return estilo.recorta(soma, janela)


def dv_e_taxa(recorte, janela=None, com_segunda_volta=True):
    """DV01 emitido no dia e taxa media do dia, para a dispersao.

    ANTES ERA QUANTIDADE, e nao dizia nada: a quantidade de titulos mistura uma LTN
    de seis meses com uma NTN-B de 35 anos como se fossem a mesma coisa, e a nuvem
    saia sem forma. O DV emitido e a moeda comum -- e a pergunta que a dispersao
    responde passa a ser a que interessa: quando a taxa esta alta, ele coloca mais
    RISCO no mercado, ou menos?

    A taxa e a media PONDERADA pelo financeiro. A simples trataria um lote de 100
    milhoes e um de 10 bilhoes como iguais, o que nao descreve leilao nenhum.
    """
    if recorte not in RECORTES:
        raise LookupError(f"recorte '{recorte}' nao existe: {sorted(RECORTES)}.")
    d = _base(com_compra=False, com_segunda_volta=com_segunda_volta)
    d = d[d["familia"].isin(RECORTES[recorte])]
    d = d[d["taxa_media_pct"].notna() & (d["financeiro_milhoes"] > 0)]
    d = d[d["dv_milhoes"].notna()]
    if d.empty:
        return pd.DataFrame(columns=["dv_milhoes", "taxa_media_pct",
                                     "financeiro_milhoes"])

    def ponderada(g):
        return (g["taxa_media_pct"] * g["financeiro_milhoes"]).sum() \
            / g["financeiro_milhoes"].sum()

    saida = d.groupby("data_leilao").apply(
        lambda g: pd.Series({
            "dv_milhoes": g["dv_milhoes"].sum(),
            "financeiro_milhoes": g["financeiro_milhoes"].sum(),
            "taxa_media_pct": ponderada(g),
        }),
        include_groups=False,
    )
    return estilo.recorta(saida, janela)


def quantidade_e_taxa(recorte, janela=None, com_segunda_volta=True):
    """Quantidade aceita e taxa media, por dia de leilao, para um recorte.

    A taxa e a media PONDERADA pelo financeiro. A media simples trataria um lote de
    100 milhoes e um de 10 bilhoes como iguais, o que nao descreve leilao nenhum.

    So venda: taxa media de recompra e outra coisa e misturar as duas nao tem
    leitura.
    """
    if recorte not in RECORTES:
        raise LookupError(f"recorte '{recorte}' nao existe: {sorted(RECORTES)}.")
    d = _base(com_compra=False, com_segunda_volta=com_segunda_volta)
    d = d[d["familia"].isin(RECORTES[recorte])]
    d = d[d["taxa_media_pct"].notna() & (d["financeiro_milhoes"] > 0)]

    def ponderada(g):
        return (g["taxa_media_pct"] * g["financeiro_milhoes"]).sum() \
            / g["financeiro_milhoes"].sum()

    saida = d.groupby("data_leilao").apply(
        lambda g: pd.Series({
            "quantidade": g["quantidade"].sum(),
            "financeiro_milhoes": g["financeiro_milhoes"].sum(),
            "taxa_media_pct": ponderada(g),
        }),
        include_groups=False,
    )
    return estilo.recorta(saida, janela)


def _estagios(dados):
    """A lista de estagios, uma por barra. None quando tudo ja e definitivo.

    Devolve None -- e nao uma lista de "planilha" -- para que o SVG do historico
    continue byte a byte o mesmo de antes de a API existir. A reprodutibilidade e
    testada, e passar hatch=["",""] em vez de hatch=None ja muda o arquivo.
    """
    if "estagio" not in dados.columns:
        return None
    marcas = dados["estagio"].fillna(ESTAGIO_MAIS_FIRME).astype(str)
    if (marcas == ESTAGIO_MAIS_FIRME).all():
        return None
    return list(marcas)


# Quanto do preenchimento sobra na barra da oferta. Zero -- barra oca -- foi a
# primeira tentativa e apagava a composicao do grafico empilhado, que e a coisa que
# ele existe para mostrar. Fantasma preserva a cor do papel e continua lendo como
# "ainda nao aconteceu".
OPACIDADE_DO_OFERTADO = 0.22


def _aparencia(estagios, cor, opacidade=0.75):
    """Os argumentos de barra que traduzem estagio em aparencia.

    Devolve um dicionario pronto para ax.bar(**...). Quando nao ha nada provisorio,
    devolve a aparencia antiga e nada mais -- ver _estagios().

    A opacidade entra na COR, e nao no alpha= da barra: alpha e um so para a serie
    inteira, e aqui cada barra precisa da sua.
    """
    from matplotlib.colors import to_rgba

    if estagios is None:
        return {"color": to_rgba(cor, opacidade)}
    return {
        "color": [to_rgba(cor, OPACIDADE_DO_OFERTADO if e == "ofertado"
                          else opacidade) for e in estagios],
        "hatch": [HACHURA_ACEITO if e == "aceito" else HACHURA_OFERTADO
                  for e in estagios],
        # O contorno forte na oferta e o que faz o fantasma parecer contorno, e nao
        # cor desbotada por acidente.
        "edgecolor": [to_rgba(cor, 1.0) if e == "ofertado" else
                      ("#333333" if e == "aceito" else "none") for e in estagios],
        "linewidth": [1.6 if e == "ofertado" else (0.4 if e == "aceito" else 0.0)
                      for e in estagios],
    }


def _legenda_dos_estagios(estagios):
    """As entradas de legenda que explicam contorno e hachura.

    Uma entrada por estagio provisorio PRESENTE, e nenhuma quando nao ha nenhum.
    Listra sem legenda e enfeite: quem olha nao tem como saber que aquela barra pode
    mudar de altura amanha.
    """
    if estagios is None:
        return []
    from matplotlib.patches import Patch

    marcas = []
    for estagio in ("ofertado", "aceito"):
        if estagio not in estagios:
            continue
        marcas.append(Patch(
            facecolor=("#cccccc" if estagio == "ofertado" else "white"),
            edgecolor="#555555",
            hatch=HACHURA_ACEITO if estagio == "aceito" else HACHURA_OFERTADO,
            linewidth=1.4 if estagio == "ofertado" else 0.4,
            label=_ROTULO_DO_ESTAGIO[estagio]))
    return marcas


def _largura(indice):
    """Largura da barra em dias, para o eixo de datas nao virar um borrao."""
    if len(indice) < 2:
        return 3.0
    dias = (indice.max() - indice.min()).days / max(len(indice) - 1, 1)
    return max(0.8, min(dias * 0.75, 5.0))


def _alinha_zeros(esquerda, direita, dados_esq, dados_dir):
    """Poe o zero dos dois eixos na MESMA altura da figura.

    O PROBLEMA QUE ISTO RESOLVE: com dois eixos independentes, o zero de um cai a
    30% da altura e o do outro a 60%. Ai a linha cruza a barra em lugares que nao
    querem dizer nada, e um periodo de recompra -- em que financeiro e DV ficam
    negativos -- aparece com as duas series de lados diferentes do proprio zero.

    A conta: a fracao da altura em que o zero fica e |chao| / (teto + |chao|). Basta
    igualar essa fracao nos dois, esticando o lado que precisa.
    """
    def limites(valores, folga=1.12):
        teto = max(0.0, float(valores.max()) * folga)
        chao = min(0.0, float(valores.min()) * folga)
        if teto == 0 and chao == 0:
            return 0.0, 1.0
        return chao, teto

    chao_e, teto_e = limites(dados_esq)
    chao_d, teto_d = limites(dados_dir)

    # A fracao mais generosa dos dois: esticar e sempre seguro, encolher cortaria
    # dado da tela.
    fracao_e = (-chao_e / (teto_e - chao_e)) if teto_e > chao_e else 0.0
    fracao_d = (-chao_d / (teto_d - chao_d)) if teto_d > chao_d else 0.0
    fracao = max(fracao_e, fracao_d)

    def estica(chao, teto, alvo):
        if alvo <= 0:
            return min(chao, 0.0), teto
        if alvo >= 1:
            return chao, max(teto, 0.0)
        # altura total tal que |chao| seja 'alvo' dela, sem cortar nem chao nem teto
        altura = max(teto / (1 - alvo), (-chao) / alvo)
        return -altura * alvo, altura * (1 - alvo)

    esquerda.set_ylim(*estica(chao_e, teto_e, fracao))
    direita.set_ylim(*estica(chao_d, teto_d, fracao))


def _marca_pontos(ax, indice, valores, formato, cor, deslocamento=(0, 7),
                  so_ultimo=False):
    """Escreve o valor do ULTIMO ponto e dos extremos da serie.

    So tres numeros, e nao um por barra: rotular tudo vira ruido e some com o
    desenho. O ultimo porque e o que se foi ver; os extremos porque sao a escala.

    'deslocamento' existe porque as duas series de um grafico de dois eixos
    costumam ter o pico NO MESMO DIA -- entra muito dinheiro e entra muito risco no
    mesmo leilao -- e ai os dois rotulos caem um em cima do outro. Foi o que
    aconteceu na primeira versao. Quem chama afasta um dos dois para o lado.
    """
    import numbers

    validos = [(i, v) for i, v in zip(indice, valores)
               if isinstance(v, numbers.Number) and v == v]
    if not validos:
        return
    # O ultimo ponto entra sempre. Os extremos entram DESDE QUE LONGE DELE: numa
    # serie que so cai, o minimo E o ultimo ou o vizinho dele, e os dois rotulos
    # saem um por cima do outro. Aconteceu no acumulado de 3 meses.
    posicao = {chave: k for k, (chave, _) in enumerate(validos)}
    distancia_minima = max(2, len(validos) // 12)

    escolhidos = {validos[-1][0]: validos[-1][1]}
    if not so_ultimo and len(validos) > 2:
        for extremo in (max(validos, key=lambda p: p[1]),
                        min(validos, key=lambda p: p[1])):
            longe = all(abs(posicao[extremo[0]] - posicao[j]) >= distancia_minima
                        for j in escolhidos)
            if longe:
                escolhidos[extremo[0]] = extremo[1]

    dx, dy = deslocamento
    for i, v in escolhidos.items():
        ax.annotate(formato(v), (i, v), textcoords="offset points",
                    xytext=(dx, dy if v >= 0 else -abs(dy) - 6),
                    ha="left" if dx > 0 else ("right" if dx < 0 else "center"),
                    fontsize=8.5, color=cor, weight="bold",
                    zorder=6,
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none",
                              alpha=0.75))


def desenha_dois_eixos(dados, ax, rotulo, dv_para_cima=None):
    """Barra de financeiro num eixo, linha de DV no outro.

    O SINAL E O DE RISCO EMITIDO (docs/convencoes-dv.md): venda positiva, recompra
    negativa. As duas series sobem juntas, porque medem a mesma atividade -- entra
    dinheiro e entra risco.

    'dv_para_cima' nao faz mais nada. Ele existia para INVERTER o eixo do DV quando
    o sinal vinha de P&L e a linha morava no teto do grafico; corrigido o sinal na
    origem, a inversao virou desnecessaria. O parametro sobrevive para nao quebrar
    quem ja chamava.
    """
    largura = _largura(dados.index)
    estagios = _estagios(dados)
    financeiro = dados["financeiro_milhoes"] / 1000
    ax.bar(dados.index, financeiro, width=largura,
           label="financeiro aceito", **_aparencia(estagios, _COR_FINANCEIRO))
    ax.set_ylabel("R$ bilh\u00f5es aceitos")
    ax.axhline(0, color="gray", lw=0.8)
    _marca_pontos(ax, dados.index, financeiro, lambda v: estilo.num_br(v, 2),
                  "#1f4e79", deslocamento=(-6, 8))

    tem_dv = dados["dv_milhoes"].notna().any()
    direita = None
    if tem_dv:
        # O DV vai para MIL por ponto-base: em milhoes as etiquetas ficam todas em
        # 0,00 e 0,01, e a serie inteira parece nula.
        dv = dados["dv_milhoes"] * 1000
        direita = ax.twinx()
        direita.plot(dados.index, dv, color=_COR_DV, lw=1.8,
                     label="DV01 emitido")
        direita.set_ylabel("DV01 emitido, R$ mil por ponto-base")
        _marca_pontos(direita, dados.index, dv, lambda v: estilo.num_br(v, 0),
                      _COR_DV, deslocamento=(8, 8))
        _alinha_zeros(ax, direita, financeiro, dv)
        direita.spines["top"].set_visible(False)
        direita.grid(False)
    else:
        ax.set_ylim(*_limites_simples(financeiro))

    _grade(ax)
    _eixo_do_tempo(ax, dados.index)
    ax.set_title(rotulo, fontsize=11, weight="bold", loc="left", pad=10)

    marcas, rotulos = ax.get_legend_handles_labels()
    if direita is not None:
        m2, r2 = direita.get_legend_handles_labels()
        marcas, rotulos = marcas + m2, rotulos + r2
    extras = _legenda_dos_estagios(estagios)
    ax.legend(marcas + extras, rotulos + [e.get_label() for e in extras],
              ncol=2 + len(extras), frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.10))


def _limites_simples(valores, folga=1.12):
    teto = max(0.0, float(valores.max()) * folga)
    chao = min(0.0, float(valores.min()) * folga)
    return (chao, teto) if teto > chao else (0.0, 1.0)


def _eixo_do_tempo(ax, indice):
    """Rotulos que dependem do tamanho da janela.

    "eixo_anual" foi feito para a serie mensal do RMD, de 25 anos. Numa janela de
    doze meses ele escreve UM rotulo -- "2026" -- e o grafico fica sem eixo. Aqui a
    janela decide: meses quando ela cabe em dois anos, anos quando nao cabe.
    """
    import matplotlib.dates as mdates
    import matplotlib.ticker as mticker

    def mes_br(x, _pos=None):
        # O %b do matplotlib devolve "Aug" -- a locale do sistema esta em ingles, e
        # o projeto ja resolve isso com uma tabela propria em estilo.MES.
        d = mdates.num2date(x)
        return f"{estilo.MES[d.month]}/{d.year % 100:02d}"

    dias = (indice.max() - indice.min()).days if len(indice) > 1 else 0
    if dias <= 120:
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0, interval=2))
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(
            lambda x, _p=None: f"{mdates.num2date(x):%d}/"
                               f"{estilo.MES[mdates.num2date(x).month]}"))
    elif dias <= 400:
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(mes_br))
    elif dias <= 900:
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(mes_br))
    else:
        estilo.eixo_anual(ax, a_cada=1 if dias < 4000 else 2)
        return
    for rotulo in ax.get_xticklabels():
        rotulo.set_rotation(45)
        rotulo.set_horizontalalignment("right")
        rotulo.set_fontsize(8.5)


def _grade(ax, eixo="y"):
    """Grade mais densa: uma linha forte a cada marca, uma fraca no meio.

    A grade anterior tinha so as marcas principais, e ler a altura de uma barra no
    meio do grafico exigia mirar. As menores entram com metade da opacidade, para
    ajudar sem competir com o dado.
    """
    from matplotlib.ticker import AutoMinorLocator

    if eixo in ("y", "ambos"):
        ax.yaxis.set_minor_locator(AutoMinorLocator(2))
        ax.grid(axis="y", which="major", alpha=0.28, lw=0.8)
        ax.grid(axis="y", which="minor", alpha=0.14, lw=0.6)
    if eixo in ("x", "ambos"):
        ax.grid(axis="x", which="major", alpha=0.14, lw=0.6)


def desenha_dois_eixos_empilhado(dados, ax, rotulo, familias=None):
    """Como desenha_dois_eixos, mas com a barra ABERTA POR FAMILIA de papel.

    A barra somada de "LTN + NTN-F" esconde qual dos dois moveu o dia, e eles tem
    prazos muito diferentes: dez bilhoes de LTN curta e dez de NTN-F 2037 sao a
    mesma barra e coisas incomparaveis. A linha do DV continua uma so, porque o
    risco do dia e um so.
    """
    familias = familias or [f for f in ORDEM_FAMILIAS if f in dados.columns]
    largura = _largura(dados.index)
    estagios = _estagios(dados)

    base = pd.Series(0.0, index=dados.index)
    for familia in familias:
        altura = dados[familia] / 1000
        ax.bar(dados.index, altura, bottom=base, width=largura, label=familia,
               **_aparencia(estagios, estilo.COR[_COR_FAMILIA[familia]], 1.0))
        base = base + altura

    ax.set_ylabel("R$ bilh\u00f5es aceitos")
    ax.axhline(0, color="gray", lw=0.8)
    _marca_pontos(ax, dados.index, base, lambda v: estilo.num_br(v, 2),
                  "#333333", deslocamento=(-6, 8))

    direita = None
    if dados["dv_milhoes"].notna().any():
        dv = dados["dv_milhoes"] * 1000
        direita = ax.twinx()
        direita.plot(dados.index, dv, color=_COR_DV, lw=1.8, label="DV01 emitido")
        direita.set_ylabel("DV01 emitido, R$ mil por ponto-base")
        _marca_pontos(direita, dados.index, dv, lambda v: estilo.num_br(v, 0),
                      _COR_DV, deslocamento=(8, 8))
        _alinha_zeros(ax, direita, base, dv)
        direita.spines["top"].set_visible(False)
        direita.grid(False)
    else:
        ax.set_ylim(*_limites_simples(base))

    _grade(ax)
    _eixo_do_tempo(ax, dados.index)
    ax.set_title(rotulo, fontsize=11, weight="bold", loc="left", pad=10)

    marcas, rotulos = ax.get_legend_handles_labels()
    if direita is not None:
        m2, r2 = direita.get_legend_handles_labels()
        marcas, rotulos = marcas + m2, rotulos + r2
    extras = _legenda_dos_estagios(estagios)
    ax.legend(marcas + extras, rotulos + [e.get_label() for e in extras],
              ncol=len(marcas) + len(extras), frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.14))


def desenha_acumulado(dados, ax, rotulo, meses=3):
    """A soma movel de N meses: area para o financeiro, linha para o DV.

    AREA E NAO BARRA porque isto e um nivel acumulado, e nao um evento: barra sugere
    "entrou tanto naquele dia", e o que a serie diz e "nos ultimos tres meses,
    tanto". O grafico de cima ja mostra o evento.
    """
    financeiro = dados["financeiro_milhoes"] / 1000
    ax.fill_between(dados.index, 0, financeiro, color=_COR_FINANCEIRO, alpha=0.35,
                    label=f"financeiro, soma de {meses} meses")
    ax.plot(dados.index, financeiro, color=_COR_FINANCEIRO, lw=1.4)
    ax.set_ylabel("R$ bilh\u00f5es")
    ax.axhline(0, color="gray", lw=0.8)
    _marca_pontos(ax, dados.index, financeiro, lambda v: estilo.num_br(v, 2),
                  "#1f4e79", deslocamento=(-6, 8))

    direita = None
    if dados["dv_milhoes"].notna().any():
        dv = dados["dv_milhoes"] * 1000
        direita = ax.twinx()
        direita.plot(dados.index, dv, color=_COR_DV, lw=1.8,
                     label=f"DV01, soma de {meses} meses")
        direita.set_ylabel("DV01, R$ mil por ponto-base")
        _marca_pontos(direita, dados.index, dv, lambda v: estilo.num_br(v, 0),
                      _COR_DV, deslocamento=(8, 8))
        _alinha_zeros(ax, direita, financeiro, dv)
        direita.spines["top"].set_visible(False)
        direita.grid(False)
    else:
        ax.set_ylim(*_limites_simples(financeiro))

    _grade(ax)
    _eixo_do_tempo(ax, dados.index)
    ax.set_title(rotulo, fontsize=11, weight="bold", loc="left", pad=10)
    marcas, rotulos = ax.get_legend_handles_labels()
    if direita is not None:
        m2, r2 = direita.get_legend_handles_labels()
        marcas, rotulos = marcas + m2, rotulos + r2
    ax.legend(marcas, rotulos, ncol=2, frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.12))


def desenha_lft(dados, ax, meses_da_media=3):
    """So financeiro, com media movel pontilhada.

    A LFT nao tem DV por decisao de modelagem (premissa de duration zero), entao o
    segundo eixo nao existe -- e a media movel entra no lugar dele, porque o que se
    quer ver na LFT e o ritmo, nao o risco.
    """
    largura = _largura(dados.index)
    estagios = _estagios(dados)
    ax.bar(dados.index, dados["financeiro_milhoes"] / 1000, width=largura,
           label="financeiro aceito", **_aparencia(estagios, estilo.COR["LFT"]))

    # A media movel e de dias de leilao, nao de dias corridos: e a serie que existe.
    # 3 meses ~ 13 leiloes semanais.
    janela = max(2, int(round(meses_da_media * 52 / 12)))
    media = dados["financeiro_milhoes"].rolling(janela).mean() / 1000
    ax.plot(dados.index, media, color="#333333", lw=2.0, ls=":",
            label=f"m\u00e9dia m\u00f3vel de {meses_da_media} meses")

    ax.set_ylabel("R$ bilh\u00f5es aceitos")
    ax.axhline(0, color="gray", lw=0.8)
    _marca_pontos(ax, dados.index, dados["financeiro_milhoes"] / 1000,
                  lambda v: estilo.num_br(v, 2), "#555555", deslocamento=(-6, 8))
    _grade(ax)
    _eixo_do_tempo(ax, dados.index)
    ax.set_title("LFT \u00b7 s\u00f3 financeiro: ela n\u00e3o tem DV, por decis\u00e3o de modelagem",
                 fontsize=11, weight="bold", loc="left", pad=10)
    marcas, rotulos = ax.get_legend_handles_labels()
    extras = _legenda_dos_estagios(estagios)
    ax.legend(marcas + extras, rotulos + [e.get_label() for e in extras],
              ncol=2 + len(extras), frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.10))


def desenha_empilhado(dados, ax):
    """Financeiro da semana, empilhado por familia de papel."""
    largura = _largura(dados.index)
    estagios = _estagios(dados)
    base = pd.Series(0.0, index=dados.index)
    for familia in ORDEM_FAMILIAS:
        altura = dados[familia] / 1000
        ax.bar(dados.index, altura, bottom=base, width=largura, label=familia,
               **_aparencia(estagios, estilo.COR[_COR_FAMILIA[familia]], 1.0))
        base = base + altura

    ax.set_ylabel("R$ bilh\u00f5es aceitos na semana")
    ax.axhline(0, color="gray", lw=0.8)
    _marca_pontos(ax, dados.index, base, lambda v: estilo.num_br(v, 2),
                  "#333333", deslocamento=(-6, 8))
    _grade(ax)
    _eixo_do_tempo(ax, dados.index)
    marcas, rotulos = ax.get_legend_handles_labels()
    extras = _legenda_dos_estagios(estagios)
    ax.legend(marcas + extras, rotulos + [e.get_label() for e in extras],
              ncol=len(ORDEM_FAMILIAS) + len(extras), frameon=False,
              loc="upper center", bbox_to_anchor=(0.5, -0.10))


def desenha_taxa_contra_dv(dados, ax, rotulo):
    """Dispersao: taxa no eixo Y, DV01 EMITIDO no X, cor pelo tempo.

    ERA CONTRA QUANTIDADE, e nao dizia nada. A quantidade de titulos mistura uma LTN
    de seis meses com uma NTN-B de 35 anos como se fossem a mesma coisa -- lotes de
    tamanho parecido com risco dez vezes diferente caiam na mesma coluna da nuvem, e
    a nuvem saia sem forma.

    Com o DV emitido no eixo, a pergunta vira a que interessa: quando a taxa esta
    alta, ele coloca mais RISCO no mercado, ou menos? A cor e o tempo, entao da para
    ver o regime mudar de lugar.
    """
    if dados.empty:
        ax.set_axis_off()
        ax.text(0.5, 0.5, "sem dado no recorte", ha="center", va="center",
                transform=ax.transAxes)
        return

    anos = dados.index.year
    pontos = ax.scatter(dados["dv_milhoes"] * 1000, dados["taxa_media_pct"],
                        c=anos, cmap="viridis", s=28, alpha=0.8,
                        edgecolor="white", linewidth=0.3)
    ax.set_xlabel("DV01 emitido no dia, R$ mil por ponto-base")
    ax.set_ylabel("taxa m\u00e9dia do dia, % ao ano")
    _grade(ax, "ambos")
    ax.set_title(rotulo, fontsize=11, weight="bold", loc="left", pad=10)

    # O ultimo dia marcado: e o que se foi ver, e num mar de pontos ele some.
    ultimo = dados.iloc[-1]
    ax.scatter([ultimo["dv_milhoes"] * 1000], [ultimo["taxa_media_pct"]],
               s=120, facecolor="none", edgecolor="#c00000", linewidth=1.8,
               zorder=5)
    ax.annotate(f"{dados.index[-1]:%d/%m/%y}",
                (ultimo["dv_milhoes"] * 1000, ultimo["taxa_media_pct"]),
                textcoords="offset points", xytext=(10, 6), fontsize=8.5,
                color="#c00000", weight="bold")

    barra = ax.get_figure().colorbar(pontos, ax=ax, pad=0.02)
    barra.set_label("ano", fontsize=9)
