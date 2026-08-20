"""Traduz o arquivo do dia -- venha ele da API ou salvo a mao -- para o esquema do
leiloes.csv.

O PROBLEMA QUE ESTE MODULO RESOLVE: eu nao vi a resposta real da API antes de
escrever isto (a rede da maquina intercepta TLS). Escrever um leitor que so aceita um
formato exato seria adivinhar, e adivinhacao neste projeto vira defeito
plausivel-e-errado.

A SAIDA E SER TOLERANTE NA ENTRADA E RIGOROSO NA SAIDA:

  - aceita JSON no formato do CKAN (`result.records`), JSON de lista pura, CSV e
    Excel. Um deles vai ser o que o portal entrega;
  - mapeia os nomes de coluna por uma tabela de sinonimos, porque o portal escreve
    "Data do Leilao", "DataLeilao" ou "data_leilao" conforme o endpoint;
  - e quando NAO consegue mapear, levanta dizendo quais colunas encontrou e quais
    faltaram. Nunca devolve tabela pela metade.

Sem esse rigor na saida, um leilao entraria com data errada ou financeiro faltando, e
o grafico do dia mostraria um numero que ninguem consegue explicar.
"""
import json
from pathlib import Path

import pandas as pd

# As colunas que o leiloes.csv tem, e os nomes por que o portal pode chama-las.
# A comparacao e feita sem acento, sem espaco e em minusculas -- entao "Data do
# Leilao", "DATA_LEILAO" e "dataLeilao" caem todos no mesmo lugar.
SINONIMOS = {
    "data_leilao": ("dataleilao", "datadoleilao", "dtleilao", "data"),
    "titulo": ("titulo", "papel", "tipotitulo", "sigla"),
    "tipo_leilao": ("tipoleilao", "tipo", "operacao", "tipooperacao"),
    "volta": ("volta", "numerovolta", "rodada"),
    "data_liquidacao": ("dataliquidacao", "dtliquidacao", "liquidacao"),
    "data_vencimento": ("datavencimento", "dtvencimento", "vencimento",
                        "maturidade"),
    "oferta_qtd": ("ofertaqtd", "quantidadeofertada", "qtdofertada", "oferta"),
    "taxa_media_pct": ("taxamediapct", "taxamedia", "taxamediaaa"),
    "taxa_corte_pct": ("taxacortepct", "taxacorte", "taxadecorte"),
    "venda_qtd": ("vendaqtd", "quantidadeaceita", "qtdaceita", "quantidadevendida",
                  "qtdvendida", "aceito"),
    "financeiro_milhoes": ("financeiromilhoes", "financeiro", "valorfinanceiro",
                           "volumefinanceiro"),
}

# O QUE E OBRIGATORIO DEPENDE DO MOMENTO, e este e o ponto do modulo.
#
# No arquivo da OFERTA nao existe taxa, nem quantidade aceita, nem financeiro --
# nada disso aconteceu ainda. Exigi-los ali recusaria justamente o arquivo que se
# quer ver primeiro. No arquivo do RESULTADO eles existem, e ai sao obrigatorios:
# aceitar um resultado sem financeiro seria deixar entrar uma barra menor sem
# ninguem saber por que.
COMUNS = ("data_leilao", "titulo", "tipo_leilao", "data_liquidacao",
          "data_vencimento")
OBRIGATORIAS_POR_ESTAGIO = {
    "ofertado": COMUNS + ("oferta_qtd",),
    "aceito": COMUNS + ("venda_qtd", "financeiro_milhoes"),
}

# Compatibilidade: era o nome antigo, de quando so existia o estagio do resultado.
OBRIGATORIAS = OBRIGATORIAS_POR_ESTAGIO["aceito"]

_DATAS = ("data_leilao", "data_liquidacao", "data_vencimento")
_NUMEROS = ("oferta_qtd", "taxa_media_pct", "taxa_corte_pct", "venda_qtd",
            "financeiro_milhoes")


def _simplificar(nome):
    """Tira acento, espaco, pontuacao e caixa, para comparar nome de coluna."""
    import unicodedata

    normal = unicodedata.normalize("NFKD", str(nome))
    sem_acento = "".join(c for c in normal if not unicodedata.combining(c))
    return "".join(c for c in sem_acento.lower() if c.isalnum())


def _tabela_do_arquivo(caminho):
    """Le o arquivo bruto como DataFrame, seja ele qual for."""
    caminho = Path(caminho)
    sufixo = caminho.suffix.lower()

    if sufixo == ".json":
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        # CKAN datastore: {"result": {"records": [...]}}
        registros = dados.get("result", {}).get("records") \
            if isinstance(dados, dict) else None
        if registros is None and isinstance(dados, dict):
            # Alguns endpoints devolvem {"result": [...]} ou {"records": [...]}
            for chave in ("result", "records", "data", "items"):
                valor = dados.get(chave)
                if isinstance(valor, list):
                    registros = valor
                    break
        if registros is None and isinstance(dados, list):
            registros = dados
        if registros is None:
            raise LookupError(
                f"{caminho.name}: nao encontrei a lista de registros no JSON. "
                f"Procurei em result.records, result, records, data e items; "
                f"as chaves do arquivo sao "
                f"{sorted(dados)[:12] if isinstance(dados, dict) else type(dados)}."
            )
        return pd.DataFrame(registros)

    if sufixo == ".csv":
        return pd.read_csv(caminho, sep=None, engine="python")
    if sufixo in (".xls", ".xlsx"):
        return pd.read_excel(caminho)

    raise LookupError(
        f"{caminho.name}: extensao {sufixo!r} nao reconhecida. "
        f"Salve como json, csv, xls ou xlsx."
    )


def detectar_estagio(bruto):
    """Se o arquivo e de oferta ou de resultado, olhando o que ele traz.

    A pergunta nao e "que nome tem o arquivo" -- o portal pode chama-lo de qualquer
    coisa -- e sim "ja existe quantidade ACEITA aqui dentro?". Se existe e tem
    numero, o leilao ja aconteceu.

    Uma coluna de aceito TODA vazia conta como oferta: alguns editais trazem a
    coluna preparada com as celulas em branco, e trata-la como resultado geraria um
    leilao de tamanho zero, que e um numero e nao uma ausencia.
    """
    disponiveis = {_simplificar(c): c for c in bruto.columns}
    for nome in SINONIMOS["venda_qtd"]:
        if nome in disponiveis:
            valores = pd.to_numeric(bruto[disponiveis[nome]], errors="coerce")
            if valores.notna().any():
                return "aceito"
    return "ofertado"


def _mapear_colunas(bruto, estagio):
    """De coluna do arquivo para coluna do leiloes.csv. Levanta se faltar essencial."""
    disponiveis = {_simplificar(c): c for c in bruto.columns}
    mapa = {}
    for destino, nomes in SINONIMOS.items():
        for candidato in nomes:
            if candidato in disponiveis:
                mapa[destino] = disponiveis[candidato]
                break

    faltando = [c for c in OBRIGATORIAS_POR_ESTAGIO[estagio] if c not in mapa]
    if faltando:
        raise LookupError(
            f"o arquivo parece ser de {estagio!r}, e nesse estagio {faltando} "
            f"sao obrigatorias -- nao consegui mapea-las.\n\n"
            f"O arquivo tem estas colunas: {list(bruto.columns)}\n\n"
            f"Se algum desses nomes for o certo, acrescente-o a SINONIMOS em "
            f"parse_leiloes_api.py -- e o unico lugar que precisa saber como o "
            f"portal escreve cada coisa."
        )
    return mapa


def _para_data(valores):
    """Datas brasileiras E datas ISO, sem confundir uma com a outra.

    dayfirst=True e obrigatorio no formato brasileiro: 03/08 lido como marco poe o
    leilao no mes errado e NAO levanta nada -- as duas leituras sao datas validas.
    Mas o mesmo dayfirst aplicado a "2055-05-15" faz o pandas avisar, porque ali o
    ano vem primeiro e a bandeira nao se aplica.

    Entao a forma decide: o que comeca com quatro digitos e um hifen e ISO; o resto
    e brasileiro.
    """
    texto = valores.astype(str).str.strip()
    iso = texto.str.match(r"^\d{4}-\d{2}-\d{2}")
    saida = pd.Series(pd.NaT, index=valores.index, dtype="datetime64[ns]")
    if iso.any():
        saida[iso] = pd.to_datetime(texto[iso], format="ISO8601",
                                    errors="coerce")
    if (~iso).any():
        saida[~iso] = pd.to_datetime(valores[~iso], dayfirst=True,
                                     errors="coerce")
    return saida


def normalizar(caminho, estagio=None):
    """O arquivo do dia, no esquema do leiloes.csv, mais o estagio em que ele esta.

    Devolve (tabela, estagio). A tabela tem as mesmas colunas que o parser da
    planilha produz, para que leiloes_recentes.novidades() possa compara-la pela
    chave; o estagio e "ofertado" ou "aceito".

    O estagio e detectado do conteudo, e nao pedido a quem chama. Passar estagio=
    explicitamente serve para o caso em que o arquivo engana -- e ai a exigencia de
    colunas passa a ser a daquele estagio, e a mensagem de erro diz qual foi.
    """
    bruto = _tabela_do_arquivo(caminho)
    if bruto.empty:
        raise LookupError(f"{Path(caminho).name}: o arquivo nao tem nenhuma linha.")

    estagio = estagio or detectar_estagio(bruto)
    if estagio not in OBRIGATORIAS_POR_ESTAGIO:
        raise LookupError(
            f"estagio {estagio!r} nao existe aqui; use 'ofertado' ou 'aceito'."
        )

    mapa = _mapear_colunas(bruto, estagio)
    saida = pd.DataFrame({destino: bruto[origem] for destino, origem in mapa.items()})

    for coluna in _DATAS:
        if coluna in saida:
            saida[coluna] = _para_data(saida[coluna])
    for coluna in _NUMEROS:
        if coluna in saida:
            saida[coluna] = pd.to_numeric(saida[coluna], errors="coerce")

    sem_data = saida["data_leilao"].isna().sum()
    if sem_data:
        raise LookupError(
            f"{Path(caminho).name}: {sem_data} linha(s) sem data de leilao "
            f"legivel. Uma linha sem data nao tem como ser comparada com o "
            f"historico, e deixa-la passar duplicaria o leilao."
        )

    # As colunas que o leiloes.csv tem e o arquivo do dia nao traz ficam vazias, e
    # nao ausentes: assim a concatenacao com o historico nao muda o formato.
    #
    # taxa_media_pct entra VAZIA no estagio da oferta, e nao zerada. Zero e uma taxa
    # -- e uma taxa de zero por cento precifica um titulo pelo valor de face. Vazia
    # e o que ela e: ainda nao existe. Quem preenche e leilao_ofertado.py, e marca
    # que preencheu.
    for coluna in ("venda_qtd", "financeiro_milhoes", "taxa_media_pct",
                   "taxa_corte_pct", "oferta_qtd", "volta",
                   "venda_bacen_qtd", "financeiro_bacen_milhoes", "referencia"):
        if coluna not in saida:
            saida[coluna] = None

    return saida, estagio
