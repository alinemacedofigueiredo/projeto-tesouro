import datetime
from pathlib import Path

import pytest
from tesouro import leitura_rmd
from tesouro.parse_rmd import estoque_vencimento

AMOSTRA = Path(__file__).parent / "fixtures" / "rmd_amostra.xlsx"


@pytest.fixture(scope="module")
def df():
    return estoque_vencimento.parse(leitura_rmd.abrir(AMOSTRA))


def test_colunas_canonicas(df):
    assert list(df.columns) == [
        "data", "indexador", "titulo", "vencimento", "isin",
        "quantidade_mil", "financeiro_milhoes",
    ]


def test_identifica_o_papel_por_titulo_vencimento_e_isin(df):
    linha = df[df["isin"] == "BRSTNCLTN6D5"].iloc[0]
    assert linha["titulo"] == "LTN"
    assert linha["vencimento"] == datetime.date(2010, 4, 1)


def test_separa_quantidade_de_financeiro(df):
    # Em Jan/10 a LTN BRSTNCLTN6D5 tinha 20.416,696 mil titulos
    # e R$ 20,121 bilhoes -- ou seja, 20.121 milhoes.
    linha = df[
        (df["isin"] == "BRSTNCLTN6D5")
        & (df["data"] == datetime.date(2010, 1, 31))
    ].iloc[0]
    assert linha["quantidade_mil"] == pytest.approx(20416.696, abs=0.01)
    assert linha["financeiro_milhoes"] == pytest.approx(20121.02, abs=1.0)


def test_marca_o_bloco_de_indexador(df):
    assert "Prefixados" in set(df["indexador"].dropna().unique())


def test_nao_confunde_o_cabecalho_com_dado(df):
    assert not df["titulo"].astype(str).str.contains("Título").any()
    assert df["vencimento"].notna().all()


def test_cobre_os_tres_blocos_de_indexador(df):
    assert {"Prefixados", "Selic", "Índices de Preços"} <= set(
        df["indexador"].dropna().unique()
    )


def test_ntn_f_fica_em_prefixados_e_nao_no_subtotal_anterior(df):
    # 'Total LTN' aparece entre as linhas de LTN e as de NTN-F, com a
    # coluna de vencimento vazia igual a um cabecalho de bloco. Se virar
    # indexador corrente, as 19 linhas de NTN-F saem com 'Total LTN'.
    indexadores = set(df[df["titulo"] == "NTN-F"]["indexador"].unique())
    assert indexadores == {"Prefixados"}


def test_nao_grava_subtotais_nem_notas(df):
    rotulos = set(df["titulo"].dropna().astype(str).unique())
    assert not any(r.lower().startswith("total") for r in rotulos)
    assert not any(r.lower().startswith("obs") for r in rotulos)
    indexadores = set(df["indexador"].dropna().astype(str).unique())
    assert not any(i.lower().startswith(("total", "obs")) for i in indexadores)
