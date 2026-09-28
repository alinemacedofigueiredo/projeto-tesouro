"""Traduz o que a API de leiloes devolve para o esquema do leiloes.csv.

Ao contrario do parse_leiloes_api.py -- que foi escrito no escuro, sem ver resposta
nenhuma, e por isso e tolerante a cinco formatos -- este foi escrito CONTRA O
PAYLOAD REAL. Entao ele e estrito: se um campo sumir ou mudar de nome, ele levanta,
em vez de adivinhar.

Os dois modulos convivem de proposito. Este e o caminho normal; aquele e o que le o
arquivo que alguem salvou a mao quando a rede nao coopera, e ali a tolerancia paga.

AS TRES ARMADILHAS DESTE PAYLOAD, todas medidas:

  1. financeiro_aceito vem em REAIS. O resto do projeto trabalha em MILHOES. Um
     fator de 1e6 esquecido nao levanta nada -- vira uma barra um milhao de vezes
     maior, que ainda e um numero;

  2. a SEGUNDA VOLTA vem em COLUNAS da mesma linha (oferta_segunda_volta,
     quantidade_aceita_segunda_volta, financeiro_aceito_segunda_volta), enquanto a
     planilha usa LINHAS separadas. Este modulo desdobra em linhas, para que a chave
     de leiloes_recentes continue funcionando e para que o filtro de segunda volta
     dos graficos continue querendo dizer o que quer;

  3. o BACEN vem em colunas proprias (quantidade_bcb, financeiro_bcb) e NAO esta
     somado em quantidade_aceita -- conferido: pu_medio x quantidade_aceita reproduz
     financeiro_aceito com razao 1,000000 nas 454 linhas com PU, o que so fecha se o
     Bacen estiver fora. Elas vao para as colunas de Bacen do esquema, como na
     planilha.

E UMA DIFERENCA DE ESCALA NA TAXA: taxa_media e taxa_maxima vem em PERCENTUAL
(8.1285 = 8,1285% ao ano), igual a planilha. Nao ha conversao a fazer, e e por isso
que ha um teste dizendo isso -- a ausencia de conversao e uma decisao, nao um
esquecimento.
"""
import pandas as pd

# O nome da volta como a planilha do Tesouro escreve. Mantido igual para que o
# filtro `volta.startswith("2")` dos graficos continue valendo para as duas fontes.
PRIMEIRA_VOLTA = "1a volta"
SEGUNDA_VOLTA = "2a volta"

# Os campos que /resultados tem de trazer. Sem um destes a linha nao vira leilao, e
# e melhor parar do que gravar meia linha.
CAMPOS_RESULTADO = ("data_leilao", "liquidacao", "titulo", "vencimento",
                    "tipo_leilao", "quantidade_aceita", "financeiro_aceito",
                    "taxa_media")

CAMPOS_EDITAL = ("data_leilao", "titulo", "vencimento", "tipo_leilao", "oferta")

# As colunas do leiloes.csv, para que a saida encaixe sem o resto do caminho saber
# de onde veio.
COLUNAS = ["data_leilao", "data_liquidacao", "titulo", "data_vencimento",
           "tipo_leilao", "volta", "oferta_qtd", "venda_qtd",
           "financeiro_milhoes", "taxa_media_pct", "taxa_corte_pct",
           "venda_bacen_qtd", "financeiro_bacen_milhoes", "referencia"]


def _conferir(registros, campos, nome):
    if not registros:
        raise LookupError(f"{nome}: a API nao devolveu registro nenhum.")
    faltando = [c for c in campos if c not in registros[0]]
    if faltando:
        raise LookupError(
            f"{nome}: faltam os campos {faltando}.\n\n"
            f"Os que vieram: {sorted(registros[0])}\n\n"
            f"O formato do portal mudou. Ajuste parse_api_leiloes.py -- e o unico "
            f"lugar que precisa saber como a API escreve cada coisa."
        )


def _data(serie):
    """As datas da API vem em dd/mm/aaaa (resultados) ou aaaa-mm-dd (editais).

    A forma decide, e nao uma bandeira global: dayfirst aplicado a "2032-09-01" faz
    o pandas avisar, e nao aplicado a "18/08/2026" poe o leilao no mes errado sem
    levantar nada.
    """
    texto = serie.astype(str).str.strip()
    iso = texto.str.match(r"^\d{4}-\d{2}-\d{2}")
    saida = pd.Series(pd.NaT, index=serie.index, dtype="datetime64[ns]")
    if iso.any():
        saida[iso] = pd.to_datetime(texto[iso], format="ISO8601", errors="coerce")
    if (~iso).any():
        saida[~iso] = pd.to_datetime(texto[~iso], dayfirst=True, errors="coerce")
    return saida


def resultados(registros):
    """Os resultados da API, no esquema do leiloes.csv, com a 2a volta desdobrada.

    Uma linha da API pode virar DUAS: a primeira volta sempre, e a segunda quando
    houve quantidade aceita nela. Somar as duas numa linha so inflaria o leilao; e
    ignorar a segunda subestimaria quanto risco entrou no mercado, que e a leitura
    que os graficos oferecem.
    """
    _conferir(registros, CAMPOS_RESULTADO, "resultados")
    d = pd.DataFrame(registros)

    for coluna in ("data_leilao", "liquidacao", "vencimento",
                   "liquidacao_segunda_volta"):
        if coluna in d:
            d[coluna] = _data(d[coluna])

    primeira = pd.DataFrame({
        "data_leilao": d["data_leilao"],
        "data_liquidacao": d["liquidacao"],
        "titulo": d["titulo"].astype(str).str.strip(),
        "data_vencimento": d["vencimento"],
        "tipo_leilao": d["tipo_leilao"].astype(str).str.strip(),
        "volta": PRIMEIRA_VOLTA,
        "oferta_qtd": pd.to_numeric(d.get("oferta"), errors="coerce"),
        "venda_qtd": pd.to_numeric(d["quantidade_aceita"], errors="coerce"),
        # REAIS -> MILHOES. Ver a nota do modulo.
        "financeiro_milhoes": pd.to_numeric(
            d["financeiro_aceito"], errors="coerce") / 1e6,
        "taxa_media_pct": pd.to_numeric(d["taxa_media"], errors="coerce"),
        "taxa_corte_pct": pd.to_numeric(d.get("taxa_maxima"), errors="coerce"),
        "venda_bacen_qtd": pd.to_numeric(d.get("quantidade_bcb"), errors="coerce"),
        "financeiro_bacen_milhoes": pd.to_numeric(
            d.get("financeiro_bcb"), errors="coerce") / 1e6,
        # O vertice do proprio Tesouro, no formato em que a planilha o traz. E o que
        # permite classificar curta e longa sem inferir do prazo.
        "referencia": d.get("benchmark"),
    })

    aceita_2a = pd.to_numeric(
        d.get("quantidade_aceita_segunda_volta", 0), errors="coerce").fillna(0)
    teve_2a = aceita_2a > 0
    if not teve_2a.any():
        return primeira[COLUNAS].reset_index(drop=True)

    s = d[teve_2a]
    segunda = pd.DataFrame({
        "data_leilao": s["data_leilao"],
        # A segunda volta liquida noutro dia, e a data dela e que vale para
        # precificar: e a d0 do fluxo.
        "data_liquidacao": s.get("liquidacao_segunda_volta", s["liquidacao"]),
        "titulo": s["titulo"].astype(str).str.strip(),
        "data_vencimento": s["vencimento"],
        "tipo_leilao": s["tipo_leilao"].astype(str).str.strip(),
        "volta": SEGUNDA_VOLTA,
        "oferta_qtd": pd.to_numeric(
            s.get("oferta_segunda_volta"), errors="coerce"),
        "venda_qtd": aceita_2a[teve_2a],
        "financeiro_milhoes": pd.to_numeric(
            s.get("financeiro_aceito_segunda_volta"), errors="coerce") / 1e6,
        # A segunda volta sai pela taxa media apurada na primeira -- e por isso que
        # a diferenca entre corte e media do dia e quase sempre zero.
        "taxa_media_pct": pd.to_numeric(s["taxa_media"], errors="coerce"),
        "taxa_corte_pct": pd.to_numeric(s.get("taxa_maxima"), errors="coerce"),
        "venda_bacen_qtd": None,
        "financeiro_bacen_milhoes": None,
        "referencia": s.get("benchmark"),
    })
    juntas = pd.concat([primeira, segunda], ignore_index=True)
    return juntas[COLUNAS].sort_values(
        ["data_leilao", "titulo", "data_vencimento", "volta"]).reset_index(drop=True)


def editais(registros):
    """O edital do dia, no esquema do leiloes.csv, como estagio de OFERTA.

    Sem taxa, sem quantidade aceita e sem financeiro: nada disso aconteceu ainda.
    Quem completa e leilao_ofertado.preencher(), e a taxa que ela digitar vence a
    emprestada.

    A liquidacao NAO vem no edital. Fica vazia aqui e e preenchida por quem chama,
    que sabe a regra do dia -- inventar D+1 dentro do tradutor esconderia a
    suposicao no lugar errado.
    """
    _conferir(registros, CAMPOS_EDITAL, "editais")
    d = pd.DataFrame(registros)
    saida = pd.DataFrame({
        "data_leilao": _data(d["data_leilao"]),
        "data_liquidacao": pd.NaT,
        "titulo": d["titulo"].astype(str).str.strip(),
        "data_vencimento": _data(d["vencimento"]),
        "tipo_leilao": d["tipo_leilao"].astype(str).str.strip(),
        "volta": PRIMEIRA_VOLTA,
        "oferta_qtd": pd.to_numeric(d["oferta"], errors="coerce"),
        "venda_qtd": None,
        "financeiro_milhoes": None,
        "taxa_media_pct": None,
        "taxa_corte_pct": None,
        "venda_bacen_qtd": None,
        "financeiro_bacen_milhoes": None,
        "referencia": d.get("benchmark"),
    })
    return saida[COLUNAS].reset_index(drop=True)


def benchmarks(registros):
    """A tabela de vertices vigentes: por (titulo, vencimento), o rotulo e os anos.

    E a fonte que faltava para separar NTN-B ate 10 anos de longa sem inferir do prazo.
    Medido: 401 leiloes de NTN-B (9,8%) trocam de faixa quando a classificacao passa
    do prazo calculado para o vertice publicado -- todos com vertice 5 e prazo entre
    5,00 e 6,42 anos, que e o mesmo papel visto no comeco da vigencia dele.
    """
    if not registros:
        raise LookupError("benchmarks: a API nao devolveu registro nenhum.")
    d = pd.DataFrame(registros)
    # As chaves vem ACENTUADAS e em maiuscula neste endpoint, ao contrario dos
    # outros. Nao normalizo em silencio: se mudarem, quero saber.
    faltando = [c for c in ("BENCHMARK", "VENCIMENTO", "T\u00cdTULO")
                if c not in d.columns]
    if faltando:
        raise LookupError(
            f"benchmarks: faltam {faltando}. Vieram: {list(d.columns)}."
        )
    saida = pd.DataFrame({
        "titulo": d["T\u00cdTULO"].astype(str).str.strip(),
        "data_vencimento": _data(d["VENCIMENTO"]),
        "benchmark": d["BENCHMARK"].astype(str).str.strip(),
        "vertice_anos": d["BENCHMARK"].astype(str).str.extract(
            r"(\d+)\s*anos?")[0].astype("Float64"),
    })
    # "LTN 6 meses" e "LTN 12 meses" nao casam com "anos": viram fracao de ano, para
    # que a comparacao com o corte continue sendo uma comparacao de numeros.
    meses = d["BENCHMARK"].astype(str).str.extract(r"(\d+)\s*meses?")[0]
    saida.loc[saida["vertice_anos"].isna() & meses.notna(), "vertice_anos"] = (
        meses[saida["vertice_anos"].isna() & meses.notna()].astype(float) / 12.0)
    return saida


def calendario(registros):
    """O que o Tesouro planeja ofertar: uma linha por (data, titulo, vencimento).

    Nao tem quantidade -- so a intencao de ofertar aquele benchmark naquele dia.
    Serve para montar a planilha de entrada antes de o edital sair.
    """
    if not registros:
        raise LookupError("calendario: a API nao devolveu registro nenhum.")
    d = pd.DataFrame(registros)
    faltando = [c for c in ("DATA_LEILAO", "TITULO", "VENCIMENTO", "TIPO_LEILAO")
                if c not in d.columns]
    if faltando:
        raise LookupError(
            f"calendario: faltam {faltando}. Vieram: {list(d.columns)}."
        )
    return pd.DataFrame({
        "data_leilao": _data(d["DATA_LEILAO"]),
        "titulo": d["TITULO"].astype(str).str.strip(),
        "data_vencimento": _data(d["VENCIMENTO"]),
        "tipo_leilao": d["TIPO_LEILAO"].astype(str).str.strip(),
        "benchmark": d.get("BENCHMARK"),
    })
