"""A planilha que ela preenche na hora da oferta.

POR QUE ISTO EXISTE. No momento em que o Tesouro anuncia a oferta, o resultado ainda
nao aconteceu: nao ha taxa, nao ha quantidade aceita, nao ha financeiro. Para
desenhar qualquer barra e preciso supor duas coisas -- e uma delas eu suponho mal.

A alternativa automatica emprestava a taxa do leilao anterior do mesmo papel, e erra
11,0 bp na mediana (36,7 no p90). Quem acompanha o mercado sabe a taxa do momento e
nao precisa dessa aproximacao. Entao a ordem certa e: ela digita o que sabe, e a
suposicao automatica so preenche o que ela deixar em branco.

O DESENHO, portanto:

  - `modelo()` grava um .xlsx com as colunas rotuladas e as linhas mais provaveis ja
    montadas -- papel, vencimento, datas e tipo pre-preenchidos a partir do proprio
    historico. Sobra digitar quantidade e taxa;
  - `ler()` le de volta e devolve a tabela no esquema do leiloes.csv, mais o registro
    de o que veio digitado. Recusa em voz alta o que estiver incompleto;
  - dali para a frente o caminho e o mesmo do arquivo da API: estagio "ofertado",
    barra fantasma com contorno, e o resultado substitui tudo quando sair.

E .XLSX, E NAO .CSV, por um motivo pratico e nao estetico: num Windows em portugues,
o Excel abre CSV interpretando "7,12" e "7.12" de formas diferentes conforme a
configuracao regional, e uma taxa lida como 712 nao levanta erro nenhum -- ela
precifica. No xlsx um numero e um numero.

NADA AQUI VAI PARA data/raw/. O arquivo que ela preenche fica em data/entrada/, que e
material de trabalho e pode ser reescrito.
"""
import datetime

import pandas as pd

from . import api_leiloes, config, parse_api_leiloes

PASTA = "entrada"
ARQUIVO = "leilao_hoje.xlsx"
ABA = "leilao"

# As colunas na ordem em que ela vai le-las, e o que cada uma quer dizer. A ordem
# importa: o que ela digita vem primeiro, o que ja vem pronto vem depois.
COLUNAS = [
    ("titulo", "T\u00edtulo"),
    ("data_vencimento", "Vencimento"),
    ("quantidade_ofertada", "Quantidade ofertada (t\u00edtulos)"),
    ("taxa_pct", "Taxa % a.a. (em branco = uso a do leil\u00e3o anterior)"),
    ("data_leilao", "Data do leil\u00e3o"),
    ("data_liquidacao", "Data de liquida\u00e7\u00e3o"),
    ("tipo_leilao", "Tipo (Venda ou Compra)"),
    ("volta", "Volta"),
]

# Sem estas nao ha barra: nao da para saber que papel e, nem de que tamanho.
OBRIGATORIAS = ("titulo", "data_vencimento", "quantidade_ofertada",
                "data_leilao", "data_liquidacao")

PAPEIS = ("LFT", "LTN", "NTN-F", "NTN-B")

# Quantos vencimentos recentes de cada papel entram no modelo. Quatro cobre o leilao
# tipico sem encher a tela -- e linhas sobrando sao apagadas em um segundo, enquanto
# linhas faltando obrigam a digitar vencimento a mao.
VENCIMENTOS_POR_PAPEL = 4


def _base():
    return pd.read_csv(
        config.PROCESSED_DIR / "leiloes.csv",
        parse_dates=["data_leilao", "data_liquidacao", "data_vencimento"],
    )


def linhas_do_edital(quando=None):
    """As pernas do leilao de hoje, com a QUANTIDADE JA PREENCHIDA pelo edital.

    O /editais da API sai a partir das 10h30 do dia do leilao e traz exatamente o
    que foi ofertado, por benchmark. Com ele a planilha chega pronta: sobra conferir
    e, se quiser, digitar a taxa.

    ISTO NAO E CONFORTO, E CORRECAO. No primeiro dia de uso, com a planilha montada
    pelo historico, o leilao de 20/08/2026 tinha SEIS pernas -- tres LTN e tres
    NTN-F -- e so as tres NTN-F foram digitadas. As tres LTN, 18 milhoes de titulos
    contra 3,65 milhoes de NTN-F, ficaram de fora do grafico sem que nada avisasse.

    Devolve None quando a API nao responde ou nao ha edital para o dia -- e ai quem
    chama volta para o palpite do historico, que e melhor que planilha nenhuma.
    """
    quando = quando or datetime.date.today()
    try:
        registros, _ = api_leiloes.buscar("editais")
        edital = parse_api_leiloes.editais(registros)
    except Exception:                                    # noqa: BLE001
        return None

    do_dia = edital[edital["data_leilao"].dt.date == quando]
    if do_dia.empty:
        return None

    linhas = [{
        "titulo": r["titulo"],
        "data_vencimento": r["data_vencimento"].date(),
        "quantidade_ofertada": r["oferta_qtd"],
        "taxa_pct": None,
        "data_leilao": quando,
        "data_liquidacao": _proximo_util(quando),
        "tipo_leilao": r["tipo_leilao"],
        "volta": "1a",
    } for _, r in do_dia.sort_values(["titulo", "data_vencimento"]).iterrows()]
    return pd.DataFrame(linhas, columns=[c for c, _ in COLUNAS])


def linhas_provaveis(quando=None, base=None):
    """Os papeis e vencimentos que o Tesouro leiloou por ultimo, um por linha.

    E O PALPITE, e nao o edital: usado so quando a API nao responde ou ainda nao ha
    edital publicado. Nao e previsao -- e a lista do que ele vem leiloando, para que
    a planilha chegue com algum trabalho feito. Vencimento errado se apaga;
    vencimento faltando obriga a consultar o edital e digitar.
    """
    quando = quando or datetime.date.today()
    base = _base() if base is None else base

    d = base[base["tipo_leilao"].isin(["Venda", "Extra Venda"])]
    d = d[d["venda_qtd"].fillna(0) > 0]
    d = d[d["data_vencimento"] > pd.Timestamp(quando)]

    linhas = []
    for titulo in PAPEIS:
        g = d[d["titulo"] == titulo]
        if g.empty:
            continue
        # Os vencimentos leiloados mais RECENTEMENTE, e nao os mais longos: o que
        # interessa e o que esta em oferta agora.
        ultimos = (g.sort_values("data_leilao")
                    .drop_duplicates("data_vencimento", keep="last")
                    .nlargest(VENCIMENTOS_POR_PAPEL, "data_leilao"))
        for _, r in ultimos.sort_values("data_vencimento").iterrows():
            linhas.append({
                "titulo": titulo,
                "data_vencimento": r["data_vencimento"].date(),
                "quantidade_ofertada": None,
                "taxa_pct": None,
                "data_leilao": quando,
                "data_liquidacao": _proximo_util(quando),
                "tipo_leilao": "Venda",
                "volta": "1a",
            })
    return pd.DataFrame(linhas, columns=[c for c, _ in COLUNAS])


def _proximo_util(quando):
    """D+1, pulando o fim de semana. Feriado ela corrige na propria planilha."""
    dia = quando + datetime.timedelta(days=1)
    while dia.weekday() >= 5:
        dia = dia + datetime.timedelta(days=1)
    return dia


def modelo(caminho=None, quando=None, base=None):
    """Grava o .xlsx para ela preencher. Devolve (caminho, veio_do_edital).

    Tenta o EDITAL do dia primeiro, que traz as pernas certas com as quantidades
    certas. So quando ele nao existe -- API fora do ar, ou antes das 10h30 -- cai
    no palpite tirado do historico, e ai as quantidades vem vazias.

    NAO sobrescreve um arquivo ja preenchido: se o modelo de hoje ja existe, ele
    pode ja ter numeros digitados dentro, e regrava-lo apagaria o trabalho sem
    perguntar.
    """
    caminho = caminho or (config.RAIZ / "data" / PASTA / ARQUIVO)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    if caminho.exists():
        raise FileExistsError(
            f"{caminho} ja existe, e pode ter numeros digitados dentro. "
            f"Apague-o ou renomeie-o antes de pedir um modelo novo."
        )

    tabela = linhas_do_edital(quando)
    veio_do_edital = tabela is not None
    if not veio_do_edital:
        tabela = linhas_provaveis(quando, base)
    tabela.columns = [rotulo for _, rotulo in COLUNAS]
    with pd.ExcelWriter(caminho, engine="openpyxl") as escritor:
        tabela.to_excel(escritor, sheet_name=ABA, index=False)
        _ajustar_largura(escritor.book[ABA], tabela)
    # Quem chama precisa saber se as quantidades sao as do edital ou zeros a
    # preencher -- as duas planilhas se parecem, e a instrucao a dar e outra.
    return caminho, veio_do_edital


def _ajustar_largura(aba, tabela):
    """Colunas largas o bastante para o rotulo aparecer inteiro.

    Um rotulo cortado obriga a adivinhar o que a coluna pede -- e a coluna que mais
    importa e justamente a que diz que a taxa e opcional.
    """
    for i, rotulo in enumerate(tabela.columns, start=1):
        letra = aba.cell(row=1, column=i).column_letter
        aba.column_dimensions[letra].width = min(max(len(str(rotulo)) + 2, 12), 46)


def ler(caminho=None):
    """Le a planilha preenchida e devolve (tabela, quantas_taxas_digitadas).

    A tabela sai no esquema do leiloes.csv, pronta para leiloes_recentes. As linhas
    inteiramente vazias sao ignoradas -- sao as que ela apagou por nao estarem em
    oferta hoje.
    """
    caminho = caminho or (config.RAIZ / "data" / PASTA / ARQUIVO)
    if not caminho.exists():
        raise FileNotFoundError(
            f"nao achei {caminho}.\n\n"
            f"Para criar o modelo:  python -m tesouro.leilao_do_dia modelo"
        )

    bruto = pd.read_excel(caminho, sheet_name=ABA)
    rotulos = {rotulo: nome for nome, rotulo in COLUNAS}
    faltando = [r for r in rotulos if r not in bruto.columns]
    if faltando:
        raise LookupError(
            f"a planilha perdeu estas colunas: {faltando}.\n\n"
            f"Ela tem: {list(bruto.columns)}\n\n"
            f"Renomear ou apagar coluna quebra a leitura. Se precisar recomecar, "
            f"apague o arquivo e gere um modelo novo."
        )
    d = bruto.rename(columns=rotulos)[[nome for nome, _ in COLUNAS]]

    # Linha vazia e linha apagada, e nao erro: o modelo chega com mais vencimentos
    # do que um leilao costuma ter, de proposito.
    d = d.dropna(how="all")
    d = d[d["quantidade_ofertada"].notna()]
    if d.empty:
        raise LookupError(
            f"{caminho.name}: nenhuma linha tem quantidade ofertada preenchida.\n\n"
            f"Preencha ao menos a coluna "
            f"{COLUNAS[2][1]!r} nas linhas que estao em oferta hoje."
        )

    for coluna in ("data_leilao", "data_liquidacao", "data_vencimento"):
        d[coluna] = pd.to_datetime(d[coluna], dayfirst=True, errors="coerce")
    for coluna in ("quantidade_ofertada", "taxa_pct"):
        d[coluna] = pd.to_numeric(d[coluna], errors="coerce")

    _conferir(d, caminho)

    saida = pd.DataFrame({
        "data_leilao": d["data_leilao"],
        "data_liquidacao": d["data_liquidacao"],
        "titulo": d["titulo"].astype(str).str.strip().str.upper(),
        "data_vencimento": d["data_vencimento"],
        "tipo_leilao": d["tipo_leilao"].fillna("Venda").astype(str).str.strip(),
        "volta": d["volta"].fillna("1a").astype(str).str.strip(),
        "oferta_qtd": d["quantidade_ofertada"],
        # A taxa digitada entra como taxa DE VERDADE. leilao_ofertado.preencher()
        # respeita a que ja existe e so empresta a do leilao anterior onde ela
        # ficou em branco -- que e exatamente a ordem certa: ela sabe, eu suponho.
        "taxa_media_pct": d["taxa_pct"],
        "taxa_corte_pct": None,
        "venda_qtd": None,
        "financeiro_milhoes": None,
        "venda_bacen_qtd": None,
        "financeiro_bacen_milhoes": None,
        "referencia": None,
    })
    return saida.reset_index(drop=True), int(d["taxa_pct"].notna().sum())


def _conferir(d, caminho):
    """Recusa em voz alta o que nao da para desenhar, dizendo a linha do Excel.

    A linha do Excel, e nao o indice do pandas: ela vai olhar a planilha, e "linha
    7" so ajuda se for a linha 7 que ela ve na tela.
    """
    def linha_do_excel(indice):
        return indice + 2      # +1 do cabecalho, +1 porque o Excel conta de 1

    for coluna in OBRIGATORIAS:
        vazias = d[d[coluna].isna()]
        if len(vazias):
            quais = ", ".join(str(linha_do_excel(i)) for i in vazias.index)
            rotulo = dict(COLUNAS)[coluna]
            raise LookupError(
                f"{caminho.name}: {rotulo!r} esta vazia nas linhas {quais}.\n\n"
                f"Sem ela nao da para desenhar essa linha. Preencha ou apague a "
                f"linha inteira."
            )

    desconhecidos = d[~d["titulo"].astype(str).str.strip().str.upper().isin(PAPEIS)]
    if len(desconhecidos):
        quais = ", ".join(str(linha_do_excel(i)) for i in desconhecidos.index)
        raise LookupError(
            f"{caminho.name}: titulo que eu nao sei precificar nas linhas {quais} "
            f"({sorted(set(desconhecidos['titulo']))}).\n\n"
            f"Os que existem: {list(PAPEIS)}."
        )

    # Vencimento antes da liquidacao nao e leilao, e um erro de digitacao -- e sem
    # esta guarda ele viraria um PU negativo, que e um numero e passa despercebido.
    invertidas = d[d["data_vencimento"] <= d["data_liquidacao"]]
    if len(invertidas):
        quais = ", ".join(str(linha_do_excel(i)) for i in invertidas.index)
        raise LookupError(
            f"{caminho.name}: nas linhas {quais} o vencimento nao e posterior a "
            f"liquidacao.\n\nProvavelmente uma data foi digitada trocada."
        )

    negativas = d[d["quantidade_ofertada"] <= 0]
    if len(negativas):
        quais = ", ".join(str(linha_do_excel(i)) for i in negativas.index)
        raise LookupError(
            f"{caminho.name}: quantidade ofertada zero ou negativa nas linhas "
            f"{quais}. Para tirar um papel do leilao, apague a linha."
        )

    # Taxa em fracao e o erro classico deste projeto: 0,0712 no lugar de 7,12 nao
    # levanta nada, ele precifica -- e devolve um PU plausivel e completamente
    # errado. O corte em 1% deixa passar a LFT, cujo agio e mesmo perto de zero.
    suspeitas = d[d["taxa_pct"].notna() & (d["taxa_pct"] > 0)
                  & (d["taxa_pct"] < 1.0) & (d["titulo"].astype(str).str.upper()
                                             != "LFT")]
    if len(suspeitas):
        quais = ", ".join(str(linha_do_excel(i)) for i in suspeitas.index)
        raise LookupError(
            f"{caminho.name}: taxa menor que 1% nas linhas {quais} "
            f"({list(suspeitas['taxa_pct'])}).\n\n"
            f"A coluna e em PERCENTUAL: 7,12 e nao 0,0712. Uma taxa em fracao nao "
            f"levanta erro nenhum -- ela precifica, e devolve um numero plausivel e "
            f"errado. Se for mesmo uma taxa abaixo de 1%, some um zero a direita "
            f"(0,90 -> 0,900001) ou me avise para eu afrouxar a guarda."
        )
