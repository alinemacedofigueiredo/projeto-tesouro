import datetime
from pathlib import Path

import pytest
from tesouro import parse_leiloes

AMOSTRA = Path(__file__).parent / "fixtures" / "leiloes_amostra.xlsx"


@pytest.fixture(scope="module")
def df():
    return parse_leiloes.parse(AMOSTRA)


def test_colunas_sao_as_canonicas(df):
    assert list(df.columns) == [
        "data_leilao", "titulo", "tipo_leilao", "volta",
        "data_liquidacao", "data_vencimento", "oferta_qtd",
        "taxa_media_pct", "taxa_corte_pct", "venda_qtd",
        "financeiro_milhoes", "venda_bacen_qtd",
        "financeiro_bacen_milhoes", "referencia",
    ]


def test_descarta_as_linhas_de_cabecalho(df):
    # Nenhuma linha pode ter texto de cabecalho vazado para os dados.
    assert not df["titulo"].astype(str).str.contains("Bond Type").any()
    assert df["data_leilao"].notna().all()


def test_taxa_vira_percentual(df):
    # No arquivo a taxa e fracao: 0.07828 significa 7,828% ao ano.
    linha = df[
        (df["data_leilao"] == datetime.date(2026, 1, 6))
        & (df["titulo"] == "NTN-B")
        & (df["data_vencimento"] == datetime.date(2029, 5, 15))
        & (df["volta"] == "1.\u00aa volta")
    ].iloc[0]
    assert linha["taxa_media_pct"] == pytest.approx(7.828, abs=1e-3)


def test_financeiro_vira_milhoes(df):
    linha = df[
        (df["data_leilao"] == datetime.date(2026, 1, 6))
        & (df["titulo"] == "LFT")
        & (df["volta"] == "1.\u00aa volta")
    ].iloc[0]
    # 13.506.269.547,68 reais = 13.506,27 milhoes
    assert linha["financeiro_milhoes"] == pytest.approx(13506.27, abs=0.01)


def test_bacen_em_branco_vira_nulo_e_nao_zero(df):
    # Em 2000 as colunas do Bacen vem vazias; virar zero afirmaria que
    # nenhuma colocacao ocorreu, o que o arquivo nao diz.
    de_2000 = df[df["data_leilao"].map(lambda d: d.year) == 2000]
    assert de_2000["venda_bacen_qtd"].isna().all()


def test_preserva_as_duas_voltas(df):
    voltas = set(df["volta"].dropna().unique())
    assert "1.\u00aa volta" in voltas
    assert "2.\u00aa volta" in voltas
