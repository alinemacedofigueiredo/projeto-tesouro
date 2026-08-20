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

_ROTULO_DO_ESTAGIO = {
    "ofertado": "ofertado hoje \u00b7 teto, e a taxa \u00e9 a do leil\u00e3o anterior",
    "aceito": "aceito hoje (API) \u00b7 muda quando a planilha sair",
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


def desenha_dois_eixos(dados, ax, rotulo, dv_para_cima=False):
    """Barra de financeiro num eixo, linha de DV no outro.

    O SINAL DO DV E O VERDADEIRO, negativo (docs/convencoes-dv.md). A barra sobe e a
    linha desce: as duas medem a mesma atividade, e o espelho e o assunto -- entra
    dinheiro e entra risco. Plotar o modulo faria o grafico bater com a intuicao e
    deixar de bater com o CSV, e o projeto ja recusou essa troca na entrega 2.

    Os dois eixos partem do zero, para que a altura de cada serie continue
    proporcional ao numero.
    """
    largura = _largura(dados.index)
    estagios = _estagios(dados)
    ax.bar(dados.index, dados["financeiro_milhoes"] / 1000, width=largura,
           label="financeiro aceito", **_aparencia(estagios, _COR_FINANCEIRO))
    ax.set_ylabel("R$ bilh\u00f5es aceitos")
    ax.axhline(0, color="gray", lw=0.8)

    tem_dv = dados["dv_milhoes"].notna().any()
    direita = None
    if tem_dv:
        direita = ax.twinx()
        direita.plot(dados.index, dados["dv_milhoes"], color=_COR_DV, lw=1.8,
                     label="DV01 emitido")
        direita.set_ylabel("DV01 emitido, R$ milh\u00f5es por ponto-base")
        # Os dois ancorados no zero: sem isso, uma serie parece maior que a outra
        # so porque o eixo dela foi cortado mais perto.
        piso = min(0.0, float(dados["dv_milhoes"].min()) * 1.12)
        if dv_para_cima:
            # Eixo invertido: mais risco emitido sobe, junto com a barra. Os
            # ROTULOS continuam negativos -- o numero nao mente, so a direcao de
            # leitura muda. E a alternativa a ter a linha morando no teto do
            # grafico, que foi como saiu na primeira versao.
            direita.set_ylim(0, piso)
        else:
            direita.set_ylim(piso, 0)
        direita.spines["top"].set_visible(False)

    teto = max(0.0, float(dados["financeiro_milhoes"].max()) / 1000 * 1.12)
    chao = min(0.0, float(dados["financeiro_milhoes"].min()) / 1000 * 1.12)
    ax.set_ylim(chao, teto)
    ax.grid(axis="y", alpha=0.20)
    estilo.eixo_anual(ax, a_cada=1 if len(dados) < 400 else 2)
    ax.set_title(rotulo, fontsize=11, weight="bold", loc="left", pad=10)

    marcas, rotulos = ax.get_legend_handles_labels()
    if direita is not None:
        m2, r2 = direita.get_legend_handles_labels()
        marcas, rotulos = marcas + m2, rotulos + r2
    extras = _legenda_dos_estagios(estagios)
    ax.legend(marcas + extras, rotulos + [e.get_label() for e in extras],
              ncol=2 + len(extras), frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.10))


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
    ax.grid(axis="y", alpha=0.20)
    estilo.eixo_anual(ax, a_cada=1 if len(dados) < 400 else 2)
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
    ax.grid(axis="y", alpha=0.20)
    estilo.eixo_anual(ax, a_cada=1 if len(dados) < 200 else 2)
    marcas, rotulos = ax.get_legend_handles_labels()
    extras = _legenda_dos_estagios(estagios)
    ax.legend(marcas + extras, rotulos + [e.get_label() for e in extras],
              ncol=len(ORDEM_FAMILIAS) + len(extras), frameon=False,
              loc="upper center", bbox_to_anchor=(0.5, -0.10))


def desenha_quantidade_e_taxa(dados, ax, rotulo):
    """OPCAO A: barra de quantidade, linha de taxa media no eixo da direita.

    Mesmo idioma dos demais graficos de dois eixos, entao quem ja le aqueles le este
    sem reaprender nada. Responde "quanto e a que preco", dia a dia.
    """
    largura = _largura(dados.index)
    ax.bar(dados.index, dados["quantidade"] / 1e6, width=largura,
           color="#8faadc", alpha=0.8, label="quantidade aceita")
    ax.set_ylabel("milh\u00f5es de t\u00edtulos")
    ax.grid(axis="y", alpha=0.20)

    direita = ax.twinx()
    direita.plot(dados.index, dados["taxa_media_pct"], color="#c00000", lw=1.8,
                 label="taxa m\u00e9dia (ponderada pelo financeiro)")
    direita.set_ylabel("% ao ano")
    direita.spines["top"].set_visible(False)

    estilo.eixo_anual(ax, a_cada=1 if len(dados) < 400 else 2)
    ax.set_title(rotulo, fontsize=11, weight="bold", loc="left", pad=10)
    marcas, rotulos = ax.get_legend_handles_labels()
    m2, r2 = direita.get_legend_handles_labels()
    ax.legend(marcas + m2, rotulos + r2, ncol=2, frameon=False,
              loc="upper center", bbox_to_anchor=(0.5, -0.10))


def desenha_taxa_contra_quantidade(dados, ax, rotulo):
    """OPCAO B: dispersao -- taxa no eixo Y, quantidade no X, cor pelo tempo.

    Responde outra pergunta, e e a pergunta interessante: o Tesouro coloca MAIS
    quando a taxa esta alta? Num grafico de duas linhas isso so aparece se as duas
    subirem juntas por acaso; aqui a relacao e o proprio desenho.

    A cor e o tempo, entao da para ver o regime mudar de lugar na nuvem.
    """
    anos = dados.index.year
    pontos = ax.scatter(dados["quantidade"] / 1e6, dados["taxa_media_pct"],
                        c=anos, cmap="viridis", s=26, alpha=0.75,
                        edgecolor="white", linewidth=0.3)
    ax.set_xlabel("milh\u00f5es de t\u00edtulos aceitos no dia")
    ax.set_ylabel("taxa m\u00e9dia do dia, % ao ano")
    ax.grid(alpha=0.20)
    ax.set_title(rotulo, fontsize=11, weight="bold", loc="left", pad=10)

    barra = ax.get_figure().colorbar(pontos, ax=ax, pad=0.02)
    barra.set_label("ano", fontsize=9)
