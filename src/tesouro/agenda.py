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


# Quantos DIAS DE LEILAO passados entram na comparacao ofertado x aceito.
#
# DIAS, e nao "seis de cada papel". A primeira versao contava por familia, e o
# resultado era um grafico com vinte e quatro linhas cobrindo periodos diferentes em
# cada bloco -- de 14/07 a 20/08 no prefixado e de 14/07 a 18/08 na NTN-B. Nao dava
# para somar o dia, que e justamente a leitura que interessa: quanto risco entrou no
# mercado NAQUELE pregao.
LEILOES_NA_COMPARACAO = 6

# A LFT tem grafico proprio, em QUANTIDADE e nao em DV -- ela nao tem DV por decisao
# de modelagem. Ali a contagem E por papel, porque o grafico e de um papel so.
LEILOES_DA_LFT = 4


def _leiloes_realizados():
    """A base de leiloes ja realizados: so venda, so primeira volta.

    So VENDA e so PRIMEIRA VOLTA: a segunda volta sai pela taxa media da primeira e
    tem oferta propria, e somar as duas misturaria dois leiloes num numero so.

    O estagio "ofertado" fica de fora: ele ainda nao tem aceito, e uma barra de
    aceito zerada ao lado de uma de ofertado cheia se le como "nao colocou nada"
    quando o certo e "ainda nao aconteceu".
    """
    from . import config

    d = pd.read_csv(config.PROCESSED_DIR / "dv_emitido_por_leilao.csv",
                    parse_dates=["data_leilao"])
    d = d[d["operacao"] == "venda"]
    d = d[~d["volta"].fillna("").astype(str).str.startswith("2")]
    if "estagio" in d.columns:
        d = d[d["estagio"] != "ofertado"]
    return d


def _somar(d, por):
    """DV e quantidade, ofertados e aceitos, agrupados pelas colunas pedidas."""
    saida = d.groupby(por).agg(
        dv_aceito=("dv_milhoes", "sum"),
        dv_ofertado=("dv_ofertado_milhoes", "sum"),
        qtd_aceita=("quantidade", "sum"),
        qtd_ofertada=("oferta_qtd", "sum"),
        financeiro_milhoes=("financeiro_milhoes", "sum"),
        papeis=("titulo", "size"),
    ).reset_index()
    saida["colocado_pct"] = (
        saida["dv_aceito"] / saida["dv_ofertado"].replace(0, pd.NA))
    saida["colocado_qtd_pct"] = (
        saida["qtd_aceita"] / saida["qtd_ofertada"].replace(0, pd.NA))
    return saida


def ultimos_dias(quantos=LEILOES_NA_COMPARACAO, base=None):
    """Os ultimos N DIAS de leilao, abertos por familia de papel.

    Uma linha por (data, familia), e a soma da data e o que interessa: quanto risco
    entrou no mercado naquele pregao. As familias que nao foram a mercado no dia
    simplesmente nao aparecem -- LFT e NTN-B vao num dia e o prefixado no outro.

    'quantos_atras' e 0 para o pregao mais recente, 1 para o anterior, e assim por
    diante. E o que permite rotular sem depender da data.
    """
    d = _leiloes_realizados() if base is None else base
    if d.empty:
        return pd.DataFrame(columns=["data_leilao", "familia", "dv_aceito",
                                     "dv_ofertado", "quantos_atras"])

    dias = sorted(d["data_leilao"].unique())[-quantos:]
    d = d[d["data_leilao"].isin(dias)]
    saida = _somar(d, ["data_leilao", "familia"])

    ordem = {dia: k for k, dia in enumerate(reversed(dias))}
    saida["quantos_atras"] = saida["data_leilao"].map(ordem)
    return saida.sort_values(["quantos_atras", "familia"]).reset_index(drop=True)


def total_por_dia(dias=None, quantos=LEILOES_NA_COMPARACAO):
    """A soma de cada dia: o DV que entrou no mercado naquele pregao.

    E a leitura que a abertura por familia sozinha nao da -- num dia de prefixado a
    LTN e a NTN-F somam, e e a soma que se compara com o dia anterior.
    """
    d = ultimos_dias(quantos) if dias is None else dias
    if d.empty:
        return d
    total = _somar(d.assign(**{
        "dv_milhoes": d["dv_aceito"],
        "dv_ofertado_milhoes": d["dv_ofertado"],
        "quantidade": d["qtd_aceita"],
        "oferta_qtd": d["qtd_ofertada"],
        "titulo": d["papeis"],
    }), ["data_leilao"])
    total["papeis"] = d.groupby("data_leilao")["papeis"].sum().values
    ordem = d.drop_duplicates("data_leilao").set_index("data_leilao")["quantos_atras"]
    total["quantos_atras"] = total["data_leilao"].map(ordem)
    return total.sort_values("quantos_atras").reset_index(drop=True)


def ultimos_de(familia, quantos=LEILOES_DA_LFT, base=None):
    """Os ultimos N leiloes DE UM PAPEL.

    Existe para a LFT, que tem grafico proprio: sendo um papel so, contar por papel
    e contar por dia dao a mesma coisa.
    """
    d = _leiloes_realizados() if base is None else base
    d = d[d["familia"] == familia]
    if d.empty:
        return pd.DataFrame(columns=["data_leilao", "familia", "qtd_ofertada",
                                     "qtd_aceita", "quantos_atras"])

    saida = _somar(d, ["data_leilao", "familia"])
    saida = saida.nlargest(quantos, "data_leilao").sort_values(
        "data_leilao", ascending=False).reset_index(drop=True)
    saida["quantos_atras"] = range(len(saida))
    return saida


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
