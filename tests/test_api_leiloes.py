"""A API de leiloes do Tesouro (apiapex) e a traducao do que ela devolve.

OS TESTES NAO TOCAM A REDE. Rodam contra uma amostra REAL congelada em
tests/fixtures/api_leiloes/, capturada em 20/08/2026 -- amostra e nao invencao, que
testaria a minha imaginacao em vez do formato do portal.

O RISCO DESTE CAMINHO nao e a rede cair: se cair, o pipeline segue com a planilha.
E traduzir errado em silencio. Sao tres armadilhas de unidade, e cada uma produz um
numero plausivel:

  financeiro em REAIS lido como MILHOES -- barra um milhao de vezes maior;
  segunda volta somada na mesma linha -- leilao contado em dobro;
  Bacen somado ao aceito -- emissao inflada nos dias em que ele entra.
"""
import json
import pathlib

import pandas as pd
import pytest

from tesouro import api_leiloes, parse_api_leiloes

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "api_leiloes"


def _registros(nome):
    dados = json.loads((FIXTURES / f"{nome}.json").read_text(encoding="utf-8"))
    return dados["registros"]


# --------------------------------------------------------------------------
# O cliente
# --------------------------------------------------------------------------

def test_a_lista_de_endpoints_e_curta_e_declarada():
    # Um endpoint novo merece uma linha dizendo para que serve, e nao entrar de
    # contrabando por string solta no meio do codigo.
    assert "resultados" in api_leiloes.ENDPOINTS
    assert "editais" in api_leiloes.ENDPOINTS
    assert "benchmarks" in api_leiloes.ENDPOINTS
    assert all(isinstance(v, str) and v for v in api_leiloes.ENDPOINTS.values())
    # resultado_homologacao ficou de fora: e byte a byte igual a resultados, e
    # lista-lo daria a impressao de serem duas fontes.
    assert "resultado_homologacao" not in api_leiloes.ENDPOINTS


def test_endpoint_desconhecido_levanta_dizendo_os_que_existem():
    with pytest.raises(LookupError) as erro:
        api_leiloes.buscar("inventado")
    assert "inventado" in str(erro.value)
    assert "resultados" in str(erro.value)


def test_envelope_sem_registros_levanta():
    with pytest.raises(LookupError, match="registros"):
        api_leiloes._registros(b'{"status":"ok"}', "resultados")


def test_status_diferente_de_ok_levanta():
    with pytest.raises(LookupError, match="status"):
        api_leiloes._registros(b'{"registros":[],"status":"erro"}', "resultados")


def test_lista_pura_tambem_serve():
    assert api_leiloes._registros(b'[{"a":1}]', "resultados") == [{"a": 1}]


# --------------------------------------------------------------------------
# As tres armadilhas de unidade
# --------------------------------------------------------------------------

def test_o_financeiro_vem_em_reais_e_sai_em_milhoes():
    # A ARMADILHA: financeiro_aceito vem 3337244949.71 (R$ 3,3 bi). Lido como milhoes
    # viraria R$ 3,3 quatrilhoes -- que ainda e um numero, e ainda desenha uma barra.
    registros = _registros("resultados")
    d = parse_api_leiloes.resultados(registros)
    primeira = d[d["volta"] == parse_api_leiloes.PRIMEIRA_VOLTA]

    # Compara a SOMA, que nao depende de casar linha a linha e por isso nao tem como
    # passar sem asserir nada -- a versao anterior deste teste tinha.
    esperado = sum(r["financeiro_aceito"] for r in registros) / 1e6
    assert primeira["financeiro_milhoes"].sum() == pytest.approx(esperado)
    assert len(primeira) == len(registros)


def test_a_ordem_de_grandeza_do_financeiro_e_plausivel():
    # Trava barata contra o fator 1e6 invertido: leilao do Tesouro nao passa de
    # R$ 100 bi nem fica abaixo de R$ 1 mi numa linha com quantidade aceita.
    d = parse_api_leiloes.resultados(_registros("resultados"))
    com_venda = d[d["venda_qtd"].fillna(0) > 0]
    assert (com_venda["financeiro_milhoes"] > 1).all()
    assert (com_venda["financeiro_milhoes"] < 100_000).all()


def test_a_segunda_volta_vira_LINHA_e_nao_soma_na_primeira():
    # A API poe a 2a volta em COLUNAS da mesma linha; a planilha usa LINHAS. Somar
    # as duas numa linha so inflaria o leilao, e ignorar a segunda subestimaria
    # quanto risco entrou no mercado.
    registros = _registros("resultados")
    com_2a = [r for r in registros
              if (r.get("quantidade_aceita_segunda_volta") or 0) > 0]
    assert com_2a, "a amostra precisa ter ao menos um leilao com segunda volta"

    d = parse_api_leiloes.resultados(registros)
    assert set(d["volta"]) >= {parse_api_leiloes.PRIMEIRA_VOLTA,
                               parse_api_leiloes.SEGUNDA_VOLTA}
    assert len(d) == len(registros) + len(com_2a)

    # E a quantidade de cada volta e a dela, e nao a soma.
    cru = com_2a[0]
    segunda = d[(d["volta"] == parse_api_leiloes.SEGUNDA_VOLTA)
                & (d["titulo"] == cru["titulo"])]
    assert cru["quantidade_aceita_segunda_volta"] in set(segunda["venda_qtd"])


def test_a_segunda_volta_usa_a_liquidacao_dela():
    # Ela liquida noutro dia, e a data da liquidacao e a d0 do fluxo -- usar a da
    # primeira volta precificaria o papel um dia errado.
    registros = _registros("resultados")
    cru = next(r for r in registros
               if (r.get("quantidade_aceita_segunda_volta") or 0) > 0
               and r.get("liquidacao_segunda_volta")
               and r["liquidacao_segunda_volta"] != r["liquidacao"])
    d = parse_api_leiloes.resultados(registros)
    segunda = d[(d["volta"] == parse_api_leiloes.SEGUNDA_VOLTA)
                & (d["titulo"] == cru["titulo"])
                & (d["data_vencimento"] == pd.to_datetime(cru["vencimento"],
                                                          dayfirst=True))]
    esperada = pd.to_datetime(cru["liquidacao_segunda_volta"], dayfirst=True)
    assert esperada in set(segunda["data_liquidacao"])


def test_o_bacen_vai_para_as_colunas_dele_e_nao_para_o_aceito():
    # Conferido no dado: pu_medio x quantidade_aceita reproduz financeiro_aceito com
    # razao 1,000000, o que so fecha se o Bacen estiver FORA do aceito. Soma-lo
    # inflaria a emissao nos dias em que ele entra.
    registros = _registros("resultados")
    cru = next((r for r in registros if (r.get("quantidade_bcb") or 0) > 0), None)
    if cru is None:
        pytest.skip("a amostra nao tem leilao com Bacen")
    d = parse_api_leiloes.resultados(registros)
    linha = d[(d["titulo"] == cru["titulo"]) & (d["venda_qtd"] == cru["quantidade_aceita"])
              & (d["volta"] == parse_api_leiloes.PRIMEIRA_VOLTA)].iloc[0]
    assert linha["venda_qtd"] == cru["quantidade_aceita"]
    assert linha["venda_bacen_qtd"] == cru["quantidade_bcb"]


def test_a_taxa_vem_em_percentual_e_nao_e_convertida():
    # A AUSENCIA de conversao e uma decisao, e nao um esquecimento: a API traz
    # 8.1285 para 8,1285% ao ano, igual a planilha. Dividir por 100 aqui daria um PU
    # plausivel e completamente errado.
    registros = _registros("resultados")
    d = parse_api_leiloes.resultados(registros)
    cru = registros[0]
    casada = d[(d["titulo"] == cru["titulo"])
               & (d["volta"] == parse_api_leiloes.PRIMEIRA_VOLTA)]
    assert cru["taxa_media"] in set(casada["taxa_media_pct"])
    # E as taxas ficam na faixa de percentual, nunca na de fracao.
    reais = d[d["titulo"] != "LFT"]["taxa_media_pct"].dropna()
    assert (reais > 1.0).all()


# --------------------------------------------------------------------------
# Datas: a API mistura dd/mm/aaaa e aaaa-mm-dd
# --------------------------------------------------------------------------

def test_data_brasileira_e_data_iso_convivem():
    # /resultados escreve 18/08/2026; /editais escreve 2026-08-20. dayfirst aplicado
    # a ISO faz o pandas avisar; nao aplicado a brasileira poe o leilao no mes errado
    # SEM levantar nada -- as duas leituras sao datas validas.
    brasileira = parse_api_leiloes._data(pd.Series(["08/03/2026"]))
    assert brasileira.iloc[0] == pd.Timestamp("2026-03-08")
    iso = parse_api_leiloes._data(pd.Series(["2026-03-08"]))
    assert iso.iloc[0] == pd.Timestamp("2026-03-08")
    misturada = parse_api_leiloes._data(pd.Series(["08/03/2026", "2026-03-08"]))
    assert misturada.iloc[0] == misturada.iloc[1]


# --------------------------------------------------------------------------
# Rigor: escrito contra o payload real, entao levanta em vez de adivinhar
# --------------------------------------------------------------------------

def test_campo_essencial_faltando_levanta_dizendo_o_que_veio():
    registros = [dict(_registros("resultados")[0])]
    del registros[0]["financeiro_aceito"]
    with pytest.raises(LookupError) as erro:
        parse_api_leiloes.resultados(registros)
    assert "financeiro_aceito" in str(erro.value)
    assert "taxa_media" in str(erro.value)     # mostra os que vieram


def test_lista_vazia_levanta():
    with pytest.raises(LookupError, match="registro nenhum"):
        parse_api_leiloes.resultados([])


# --------------------------------------------------------------------------
# Editais: a oferta do dia, sem taxa e sem financeiro
# --------------------------------------------------------------------------

def test_o_edital_entra_como_oferta_sem_inventar_o_que_nao_aconteceu():
    d = parse_api_leiloes.editais(_registros("editais"))
    assert len(d) == 6
    assert (d["oferta_qtd"] > 0).all()
    # Nada disto existe na hora do edital, e zero seria uma afirmacao.
    assert d["venda_qtd"].isna().all()
    assert d["financeiro_milhoes"].isna().all()
    assert d["taxa_media_pct"].isna().all()
    # A liquidacao tambem nao vem no edital: quem sabe a regra do dia e quem chama.
    assert d["data_liquidacao"].isna().all()


def test_o_edital_traz_o_benchmark_do_tesouro():
    d = parse_api_leiloes.editais(_registros("editais"))
    assert d["referencia"].notna().all()
    assert any("anos" in str(r) or "meses" in str(r) for r in d["referencia"])


# --------------------------------------------------------------------------
# Benchmarks: a fonte que destrava curta e longa
# --------------------------------------------------------------------------

def test_o_benchmark_vira_vertice_em_anos():
    d = parse_api_leiloes.benchmarks(_registros("benchmarks"))
    assert len(d) == 18
    assert d["vertice_anos"].notna().all()

    ntnb = d[d["titulo"] == "NTN-B"].set_index("benchmark")["vertice_anos"]
    assert ntnb["NTN-B 3 anos"] == 3
    assert ntnb["NTN-B 35 anos"] == 35


def test_benchmark_em_MESES_vira_fracao_de_ano():
    # "LTN 6 meses" nao casa com "anos". Sem esta conversao o vertice ficaria vazio,
    # e a comparacao com o corte deixaria de ser comparacao de numeros.
    d = parse_api_leiloes.benchmarks(_registros("benchmarks"))
    seis_meses = d[d["benchmark"] == "LTN 6 meses"].iloc[0]
    assert seis_meses["vertice_anos"] == pytest.approx(0.5)
    doze = d[d["benchmark"] == "LTN 12 meses"].iloc[0]
    assert doze["vertice_anos"] == pytest.approx(1.0)


def test_benchmarks_com_chave_renomeada_levanta():
    registros = [dict(r) for r in _registros("benchmarks")]
    for r in registros:
        r["BENCH"] = r.pop("BENCHMARK")
    with pytest.raises(LookupError, match="BENCHMARK"):
        parse_api_leiloes.benchmarks(registros)


# --------------------------------------------------------------------------
# Calendario: o que vem pela frente
# --------------------------------------------------------------------------

def test_o_calendario_olha_para_a_frente():
    d = parse_api_leiloes.calendario(_registros("calendario"))
    assert len(d) == 60
    assert d["data_leilao"].notna().all()
    assert d["data_vencimento"].notna().all()
    # E o vencimento e sempre posterior ao leilao.
    assert (d["data_vencimento"] > d["data_leilao"]).all()


# --------------------------------------------------------------------------
# O contrato com o resto do caminho
# --------------------------------------------------------------------------

def test_a_saida_encaixa_no_esquema_do_leiloes_csv():
    from tesouro import leiloes_recentes as lr

    d = parse_api_leiloes.resultados(_registros("resultados"))
    assert set(lr.CHAVE) <= set(d.columns)
    assert list(d.columns) == parse_api_leiloes.COLUNAS

    e = parse_api_leiloes.editais(_registros("editais"))
    assert list(e.columns) == parse_api_leiloes.COLUNAS
