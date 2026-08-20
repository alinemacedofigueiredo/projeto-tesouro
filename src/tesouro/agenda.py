"""A agenda de leiloes: o que o Tesouro planeja ofertar, e o que ja se sabe disso.

O /calendario da API publica, por dia de leilao, QUAIS benchmarks vao a mercado.
Medido em 20/08/2026: 60 linhas, 12 dias de leilao, cobrindo ate 29/09.

O QUE ELE NAO PUBLICA E A QUANTIDADE. E essa e a diferenca que organiza este modulo,
porque as duas coisas que faltam custam muito diferente:

  A TAXA e barata de supor. A do ultimo leilao do mesmo papel-vencimento erra 11,0 bp
  na mediana e 36,7 no p90, e isso move o DV01 do lote em 0,55% / 2,1%. Como o
  calendario e proximo -- idade mediana da ultima taxa: 28 dias, maxima 56 -- a
  suposicao esta dentro da faixa em que foi medida, com algumas linhas fora.

  A QUANTIDADE e cara, e nao ha o que supor: o Tesouro decide no edital, e o edital
  so sai as 10h30 do proprio dia. Ele varia MUITO de leilao para leilao no mesmo
  benchmark, e nao ha media que descreva.

DAI A REGRA DESTA PAGINA: ela mostra FATOS sobre cada papel da agenda -- quando foi
leiloado por ultimo, a que taxa, quanto foi ofertado -- e o DV01 POR TITULO, que e
propriedade do instrumento e nao depende de quantidade nenhuma.

O produto "DV01 se repetir a ultima oferta" tambem aparece, porque e o numero que se
quer olhar, MAS marcado como o que e: uma multiplicacao por um numero do passado. Nao
e previsao, e a agenda nao vira previsao por ser desenhada.
"""
import pandas as pd

from . import (api_leiloes, calendario, leilao_ofertado, leiloes_dv,
               leiloes_recentes, parse_api_leiloes, precificacao)

# Ate quantos dias atras a ultima taxa ainda esta na faixa em que o erro foi medido.
# A mesma constante do leilao_ofertado, e pelo mesmo motivo -- alem disso o mercado
# ja e outro, e o erro deixa de ser o que esta medido.
DIAS_ATE_A_TAXA_ENVELHECER = leilao_ofertado.DIAS_MAXIMOS_PARA_A_TAXA


def _ultimos_leiloes(base=None):
    """Por (titulo, vencimento), o ultimo leilao COM aceite: data, taxa e oferta.

    So leiloes com aceite: quando nada e aceito a planilha grava taxa 0,00, que nao
    e taxa -- na LFT o zero e legitimo (agio sobre a Selic), e por isso o filtro e
    por quantidade e nunca por taxa diferente de zero.
    """
    if base is None:
        base = leiloes_recentes.completo("aceito")
    d = base[base["tipo_leilao"].isin(["Venda", "Extra Venda"])]
    d = d[d["venda_qtd"].fillna(0) > 0]
    d = d[d["taxa_media_pct"].notna()]
    return (d.sort_values("data_leilao")
             .groupby(["titulo", "data_vencimento"])
             .agg(taxa_pct=("taxa_media_pct", "last"),
                  quando=("data_leilao", "last"),
                  liquidacao=("data_liquidacao", "last"),
                  oferta_qtd=("oferta_qtd", "last"),
                  aceito_qtd=("venda_qtd", "last"))
             .reset_index())


def proximos(registros=None, base=None, hoje=None, cal=None):
    """A agenda enriquecida: uma linha por (dia de leilao, papel, vencimento).

    Devolve as colunas do calendario mais o que o historico sabe de cada papel:

      taxa_pct, taxa_de_quando, taxa_dias_de_idade, taxa_velha
      oferta_anterior_qtd, aceito_anterior_qtd
      dv_unitario          o DV01 de UM titulo, na ultima taxa. Nao depende de
                           quantidade, e por isso e o numero mais firme da pagina;
      dv_se_repetir        dv_unitario x oferta_anterior_qtd / 1e6. Um PRODUTO por
                           um numero do passado, e nao previsao.

    'registros' permite passar a resposta ja baixada -- os testes usam a amostra
    congelada, e assim nao tocam a rede.
    """
    if registros is None:
        registros, _ = api_leiloes.buscar("calendario")
    agenda = parse_api_leiloes.calendario(registros)

    hoje = pd.Timestamp(hoje) if hoje is not None else pd.Timestamp.today().normalize()
    agenda = agenda[agenda["data_leilao"] >= hoje].copy()

    ultimos = _ultimos_leiloes(base)
    d = agenda.merge(ultimos, on=["titulo", "data_vencimento"], how="left")

    d["taxa_de_quando"] = d["quando"]
    d["taxa_dias_de_idade"] = (d["data_leilao"] - d["quando"]).dt.days
    d["taxa_velha"] = (
        d["taxa_dias_de_idade"] > DIAS_ATE_A_TAXA_ENVELHECER).fillna(True)
    d = d.rename(columns={"oferta_qtd": "oferta_anterior_qtd",
                          "aceito_qtd": "aceito_anterior_qtd"})

    d["dv_unitario"] = _dv_unitario(d, cal)
    d["dv_se_repetir"] = d["dv_unitario"] * d["oferta_anterior_qtd"] / 1e6
    d["prazo_anos"] = (d["data_vencimento"] - d["data_leilao"]).dt.days / 365.25
    d["vertice_anos"] = d["benchmark"].astype(str).str.extract(
        r"(\d+)\s*anos?")[0].astype("Float64")
    meses = d["benchmark"].astype(str).str.extract(r"(\d+)\s*meses?")[0]
    falta = d["vertice_anos"].isna() & meses.notna()
    d.loc[falta, "vertice_anos"] = meses[falta].astype(float) / 12.0
    d["familia"] = [
        leiloes_dv._familia(t, p, v)
        for t, p, v in zip(d["titulo"], d["prazo_anos"], d["vertice_anos"])
    ]

    colunas = ["data_leilao", "titulo", "familia", "benchmark", "data_vencimento",
               "vertice_anos", "prazo_anos", "taxa_pct", "taxa_de_quando",
               "taxa_dias_de_idade", "taxa_velha", "oferta_anterior_qtd",
               "aceito_anterior_qtd", "dv_unitario", "dv_se_repetir"]
    return d[colunas].sort_values(
        ["data_leilao", "titulo", "data_vencimento"]).reset_index(drop=True)


def _dv_unitario(d, cal=None):
    """O DV01 de UM titulo de cada linha, na ultima taxa observada.

    A LIQUIDACAO SUPOSTA E D+1 do dia de leilao, e nao a do leilao anterior: o DV
    varia com o prazo restante, e usar uma data velha o mediria no dia errado. D+1 e
    a regra dos leiloes de venda; feriado desloca, e o efeito de um dia no DV e
    menor que o erro da taxa suposta.

    A LFT fica sem DV, por decisao de modelagem da entrega 2 (premissa de duration
    zero) -- e nao por nao dar para calcular.
    """
    cal = cal or calendario.padrao()
    saida = []
    for _, r in d.iterrows():
        if r["titulo"] in leiloes_dv.SEM_DV or pd.isna(r["taxa_pct"]):
            saida.append(None)
            continue
        d0 = _proximo_util(cal, r["data_leilao"])
        venc = r["data_vencimento"].date()
        if d0 >= venc:
            saida.append(None)
            continue
        vna = None
        if r["titulo"] == "NTN-B":
            # Sem financeiro publicado nao da para recuperar o VNA exato; fica o do
            # mes, cujo erro medido e de 0,156% na mediana -- pequeno perto do que a
            # ausencia de quantidade ja custa nesta pagina.
            vna = _vna_do_mes(r["data_leilao"])
            if vna is None:
                saida.append(None)
                continue
        try:
            # Sinal de RISCO EMITIDO, como no dv_emitido_por_leilao.csv: positivo e
            # o Tesouro emitindo. precificacao.dv devolve o sinal de P&L.
            saida.append(abs(precificacao.dv(cal, r["titulo"], d0, venc,
                                             r["taxa_pct"] / 100.0, vna)))
        except Exception:                                # noqa: BLE001
            saida.append(None)
    return saida


def _proximo_util(cal, quando):
    """D+1 util a partir do dia de leilao, pelo calendario de feriados do projeto.

    cal.mover(d, 1) sempre sai da data inicial, entao um dia de leilao numa sexta
    devolve a segunda, e feriado e pulado. Reimplementar isso aqui com weekday()
    daria o resultado errado no carnaval e na Semana Santa, que sao justamente
    semanas de leilao.
    """
    return cal.mover(quando.date(), 1)


_VNA_EM_CACHE = {}


def _vna_do_mes(quando):
    """O ultimo VNA do IPCA ate a data. Uma leitura so do CSV, guardada."""
    from . import config

    if "ipca" not in _VNA_EM_CACHE:
        vna = pd.read_csv(config.PROCESSED_DIR / "vna.csv", parse_dates=["data"])
        _VNA_EM_CACHE["ipca"] = vna[vna["indice"] == "IPCA"].sort_values("data")
    serie = _VNA_EM_CACHE["ipca"]
    ate = serie[serie["data"] <= quando]
    if ate.empty:
        return None
    return float(ate.iloc[-1]["vna"])


# Quantos leiloes passados entram na comparacao ofertado x aceito. Tres porque a
# pergunta e "o ultimo foi diferente?", e para isso bastam os dois anteriores como
# referencia -- com mais, a tabela vira serie temporal e ja existe uma pagina para
# isso.
LEILOES_NA_COMPARACAO = 6

# A LFT tem grafico proprio, em QUANTIDADE e nao em DV -- ela nao tem DV por decisao
# de modelagem, e quatro leiloes bastam ali porque a serie dela e mais regular.
LEILOES_DA_LFT = 4


def ofertado_e_aceito(familias=None, quantos=LEILOES_NA_COMPARACAO):
    """Por familia de papel, os ultimos N leiloes com o DV OFERTADO e o ACEITO.

    A PERGUNTA QUE ISTO RESPONDE, e que o aceito sozinho nao responde: ele nao
    conseguiu colocar, ou nao quis? Medido no agregado, o Tesouro coloca 68,5% do
    DV que oferta -- e a razao varia muito por papel e por dia.

    "Ultimos N leiloes DAQUELA FAMILIA", e nao os ultimos N dias: LFT e NTN-B vao a
    mercado num dia e o prefixado no outro, entao um corte por data deixaria metade
    das familias sem linha. Cada uma tem o seu proprio calendario.

    So VENDA e so PRIMEIRA VOLTA: a segunda volta sai pela taxa media da primeira e
    tem oferta propria, e somar as duas misturaria dois leiloes num numero so.
    """
    from . import config

    d = pd.read_csv(config.PROCESSED_DIR / "dv_emitido_por_leilao.csv",
                    parse_dates=["data_leilao"])
    d = d[d["operacao"] == "venda"]
    d = d[~d["volta"].fillna("").astype(str).str.startswith("2")]
    if "estagio" in d.columns:
        # O ofertado ainda nao tem aceito: incluir-lo poria uma barra de aceito
        # zerada ao lado de uma de ofertado cheia, que se le como "nao colocou
        # nada" quando o certo e "ainda nao aconteceu".
        d = d[d["estagio"] != "ofertado"]

    familias = familias or [f for f in _ORDEM_FAMILIAS if f in set(d["familia"])]
    d = d[d["familia"].isin(familias)]

    por_dia_familia = d.groupby(["familia", "data_leilao"]).agg(
        dv_aceito=("dv_milhoes", "sum"),
        dv_ofertado=("dv_ofertado_milhoes", "sum"),
        # A QUANTIDADE TAMBEM, porque a LFT nao tem DV: o grafico dela compara
        # ofertado e aceito em titulos, com o financeiro escrito em cima da barra.
        qtd_aceita=("quantidade", "sum"),
        qtd_ofertada=("oferta_qtd", "sum"),
        financeiro_milhoes=("financeiro_milhoes", "sum"),
        papeis=("titulo", "size"),
    ).reset_index()

    saida = []
    for familia in familias:
        g = por_dia_familia[por_dia_familia["familia"] == familia]
        ultimos = g.nlargest(quantos, "data_leilao").sort_values(
            "data_leilao", ascending=False)
        for ordem, (_, r) in enumerate(ultimos.iterrows()):
            linha = r.to_dict()
            # 0 = o ultimo, 1 = o anterior, 2 = dois atras. E o que a tabela usa
            # para rotular sem depender de a data ser a mesma entre familias.
            linha["quantos_atras"] = ordem
            saida.append(linha)
    if not saida:
        return pd.DataFrame(columns=["familia", "data_leilao", "dv_aceito",
                                     "dv_ofertado", "quantos_atras"])
    fora = pd.DataFrame(saida)
    fora["colocado_pct"] = fora["dv_aceito"] / fora["dv_ofertado"].replace(0, pd.NA)
    # Na LFT a fracao colocada so existe em quantidade, porque o DV e vazio.
    fora["colocado_qtd_pct"] = (
        fora["qtd_aceita"] / fora["qtd_ofertada"].replace(0, pd.NA))
    return fora


_ORDEM_FAMILIAS = ["LFT", "LTN", "NTN-F", "NTN-B curta", "NTN-B longa"]


def por_dia(agenda=None, **kwargs):
    """A agenda somada por dia de leilao: quantos papeis, e o DV se repetir a oferta.

    E a leitura de "quanto risco esta agendado para cada dia", com a ressalva de que
    a quantidade e a da vez passada.
    """
    agenda = proximos(**kwargs) if agenda is None else agenda
    saida = agenda.groupby("data_leilao").agg(
        papeis=("titulo", "size"),
        dv_se_repetir=("dv_se_repetir", "sum"),
        oferta_anterior_qtd=("oferta_anterior_qtd", "sum"),
        alguma_taxa_velha=("taxa_velha", "any"),
    )
    return saida
