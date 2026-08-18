import pandas as pd
import pytest
from tesouro import dv


@pytest.fixture(scope="module")
def r():
    return dv.resultado_mensal()


@pytest.fixture(scope="module")
def v():
    return dv.variacao_de_dv()


def test_colunas_canonicas(r):
    assert list(r.columns) == [
        "data_ini", "data_fim", "isin", "titulo", "venceu_no_periodo",
        "quantidade_mil_ini", "pu_ini", "pu_fim", "resultado_milhoes",
    ]


def test_periodos_sao_meses_consecutivos(r):
    pares = r[["data_ini", "data_fim"]].drop_duplicates()
    assert (pd.to_datetime(pares["data_fim"]) > pd.to_datetime(pares["data_ini"])).all()
    dias = (pd.to_datetime(pares["data_fim"]) - pd.to_datetime(pares["data_ini"])).dt.days
    # Faixa 22-35, nao 26-35: fevereiro de 2017 e de 2022 tem Carnaval na
    # ultima semana do mes (27 e 28/02/2017; 28/02 e 01/03/2022 nao, mas
    # 26-28/02/2022 sim), entao o ultimo dia util do mes cai em 24/02/2017
    # e 25/02/2022 -- confirmado com calendario.padrao().eh_dia_util,
    # nao suposto. Um mes inteiro faltando (a falha real que este teste
    # protege) da um gap de ~55-65 dias, bem fora dessa faixa.
    assert dias.between(22, 35).all()


def test_quantidade_e_a_do_inicio_do_periodo(r):
    # A posicao e congelada: papel emitido no meio do mes nao entra.
    p = dv.painel()
    uma = r[r["quantidade_mil_ini"].notna()].iloc[0]
    no_painel = p[(p["data"] == uma["data_ini"]) & (p["isin"] == uma["isin"])]
    assert no_painel["quantidade_mil"].iloc[0] == pytest.approx(uma["quantidade_mil_ini"])


def test_papel_que_venceu_fica_marcado_e_sem_pu_final(r):
    venceu = r[r["venceu_no_periodo"]]
    assert len(venceu) > 0
    assert venceu["pu_fim"].isna().all()
    assert venceu["resultado_milhoes"].isna().all()


def test_resultado_e_a_diferenca_de_pu_vezes_a_quantidade(r):
    x = r[r["resultado_milhoes"].notna()].head(300)
    esperado = (x["pu_fim"] - x["pu_ini"]) * x["quantidade_mil_ini"] / 1000
    assert (esperado - x["resultado_milhoes"]).abs().max() < 1e-9


def test_resultado_tem_os_dois_sinais(r):
    # Ha meses de alta e de queda de taxa; se so houver um sinal, algo
    # esta errado na convencao.
    s = r["resultado_milhoes"].dropna()
    assert (s > 0).any() and (s < 0).any()


def test_ordem_de_grandeza_do_resultado_mensal(r):
    # O resultado de um mes da carteira inteira fica na casa de dezenas de
    # bilhoes de reais no maximo -- ou seja, dezenas de milhares de milhoes.
    por_mes = r.groupby("data_fim")["resultado_milhoes"].sum().abs()
    assert por_mes.max() < 500000


def test_variacao_de_dv_usa_o_estoque_real(v):
    assert list(v.columns) == ["data", "titulo", "dv_milhoes", "variacao_milhoes"]
    assert set(v["titulo"].unique()) <= {"LTN", "NTN-F", "NTN-B"}
    # A primeira data de cada titulo nao tem variacao.
    assert v.groupby("titulo")["variacao_milhoes"].apply(lambda s: s.isna().sum()).eq(1).all()


def test_variacao_e_a_diferenca_do_dv_entre_meses(v):
    for _, g in v.groupby("titulo"):
        g = g.sort_values("data")
        esperado = g["dv_milhoes"].diff()
        assert (esperado - g["variacao_milhoes"]).abs().max() < 1e-9


def test_lft_entra_no_resultado_mas_nao_na_variacao_de_dv(r, v):
    # A LFT nao tem DV (dv_unitario e None por decisao de modelagem), mas
    # tem PU real e portanto resultado em dinheiro real -- ela e metade do
    # estoque e excluir esse dinheiro do resultado mensal esconderia a
    # maior parte do financeiro da divida. variacao_de_dv, ao contrario,
    # e sobre risco de taxa: a LFT nao pertence la, e dv_posicao_milhoes
    # dela e sempre None.
    assert "LFT" in set(r["titulo"].unique())
    assert "LFT" not in set(v["titulo"].unique())
    lft_com_resultado = r[(r["titulo"] == "LFT") & r["resultado_milhoes"].notna()]
    assert len(lft_com_resultado) > 0
