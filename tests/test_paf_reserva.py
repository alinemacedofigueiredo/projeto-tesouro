# tests/test_paf_reserva.py
import datetime
from pathlib import Path

import pytest
from tesouro import leitura_rmd
from tesouro.parse_rmd import paf_reserva

AMOSTRA = Path(__file__).parent / "fixtures" / "rmd_amostra.xlsx"


@pytest.fixture(scope="module")
def xl():
    return leitura_rmd.abrir(AMOSTRA)


def test_paf_tem_as_colunas_canonicas(xl):
    df = paf_reserva.parse_paf(xl)
    assert list(df.columns) == [
        "ano", "versao", "indicador", "minimo", "maximo", "realizado"
    ]


def test_paf_distingue_original_de_revisado(xl):
    df = paf_reserva.parse_paf(xl)
    versoes = set(df["versao"].unique())
    assert "original" in versoes
    assert "revisado" in versoes


def test_paf_traz_a_banda_de_estoque_de_2003(xl):
    df = paf_reserva.parse_paf(xl)
    linha = df[
        (df["ano"] == 2003)
        & (df["versao"] == "original")
        & (df["indicador"].str.contains("Estoque"))
    ].iloc[0]
    assert linha["minimo"] == pytest.approx(940.0)
    assert linha["maximo"] == pytest.approx(1020.0)
    assert linha["realizado"] == pytest.approx(965.8, abs=0.1)


def test_paf_preserva_a_revisao_de_2008(xl):
    df = paf_reserva.parse_paf(xl)
    revisado = df[(df["ano"] == 2008) & (df["versao"] == "revisado")]
    assert len(revisado) > 0


def test_paf_reconhece_revisao_escrita_com_parenteses(xl):
    # O quarto bloco (a partir da linha 55) escreve a revisao como
    # 'PAF 2021 (Revisado)' -- parenteses e maiuscula -- diferente dos
    # blocos anteriores ('PAF <ano> revisado', minusculo, sem parenteses).
    # Um regex que so aceitasse a primeira forma perderia essa revisao
    # em silencio, sem erro nenhum.
    df = paf_reserva.parse_paf(xl)
    revisado = df[(df["ano"] == 2021) & (df["versao"] == "revisado")]
    assert len(revisado) > 0


def test_paf_traz_realizado_do_primeiro_ano_de_cada_bloco(xl):
    # A linha 'Indicadores' guarda o ano realizado como numero; quando a
    # coluna mistura texto e numero (a coluna 'Indicadores' tem o rotulo
    # em texto e os anos em numero), o pandas grava esses numeros como
    # float -- entao o primeiro ano de cada bloco chega como '2003.0',
    # nao '2003'. Um reconhecimento que exigisse digitos puros deixaria o
    # realizado do primeiro ano de cada um dos quatro blocos vazio.
    df = paf_reserva.parse_paf(xl)
    for ano in (2003, 2011, 2016, 2021):
        linha = df[
            (df["ano"] == ano)
            & (df["versao"] == "original")
            & (df["indicador"].str.contains("Estoque"))
        ]
        assert len(linha) > 0, f"ano {ano} ausente da amostra"
        assert linha.iloc[0]["realizado"] is not None, (
            f"realizado do ano {ano} (primeiro do seu bloco) ficou vazio"
        )


def test_reserva_tem_as_colunas_canonicas(xl):
    df = paf_reserva.parse_reserva(xl)
    assert list(df.columns) == [
        "data", "reserva_milhoes", "valor_prudencial_milhoes",
        "indice_liquidez_meses",
    ]


def test_reserva_converte_bilhoes_mas_nao_o_indice(xl):
    df = paf_reserva.parse_reserva(xl)
    primeira = df.sort_values("data").iloc[0]
    # 71,998 bilhoes viram 71.998 milhoes; o indice em meses fica intacto.
    assert primeira["reserva_milhoes"] == pytest.approx(71997.6, abs=1.0)
    assert primeira["indice_liquidez_meses"] == pytest.approx(1.713, abs=0.01)
