# tests/test_paf_reserva.py
import datetime
from pathlib import Path

import pandas as pd
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
        "ano", "versao", "indicador", "unidade",
        "minimo", "maximo", "realizado",
    ]


def test_paf_rotula_as_tres_unidades_da_aba(xl):
    # minimo/maximo/realizado valem R$ bilhoes para o estoque, anos para o
    # prazo medio e pontos percentuais para todo o resto -- nas mesmas
    # colunas. Sem o rotulo, comparar a banda de estoque (casa de 5.600)
    # contra estoque_dpf.csv (5.613.655) erra por mil.
    df = paf_reserva.parse_paf(xl)
    por_indicador = df.groupby("indicador")["unidade"].unique()

    for indicador, unidades in por_indicador.items():
        assert len(unidades) == 1, f"{indicador} com mais de uma unidade"

    unidade = df.set_index("indicador")["unidade"]
    assert unidade["Estoque da DPF em Mercado (R$ Bilhões)"].iloc[0] == "R$ bilhoes"
    assert unidade["Prazo Médio da DPF (anos)"].iloc[0] == "anos"
    assert unidade["Prefixado"].iloc[0] == "percentual"
    assert unidade["% Vincendo em 12 meses"].iloc[0] == "percentual"


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
    #
    # A ausencia, depois do construtor de DataFrame, e NaN (float), nao
    # o singleton None -- e 'NaN is not None' e sempre True. Um teste que
    # checasse 'is not None' passaria mesmo com o defeito reintroduzido,
    # porque nunca falharia; pd.notna reconhece NaN de verdade.
    df = paf_reserva.parse_paf(xl)
    for ano in (2003, 2011, 2016, 2021):
        linha = df[
            (df["ano"] == ano)
            & (df["versao"] == "original")
            & (df["indicador"].str.contains("Estoque"))
        ]
        assert len(linha) > 0, f"ano {ano} ausente da amostra"
        assert pd.notna(linha.iloc[0]["realizado"]), (
            f"realizado do ano {ano} (primeiro do seu bloco) ficou vazio"
        )


def test_paf_converte_realizado_percentual_de_2021_2022(xl):
    # No bloco de 2021-2022, o realizado dos indicadores percentuais e
    # gravado na planilha como fracao (0.21), formatado como percentual;
    # nos blocos anteriores (e no minimo/maximo da mesma linha) o
    # realizado ja vem em pontos percentuais (30.7). Sem converter pelo
    # formato da celula, 21.02 apareceria como 0.21 -- cem vezes abaixo
    # da banda que deveria estar comparando.
    df = paf_reserva.parse_paf(xl)
    linha_2021 = df[
        (df["ano"] == 2021) & (df["versao"] == "original")
        & (df["indicador"] == "% Vincendo em 12 meses")
    ].iloc[0]
    assert linha_2021["realizado"] == pytest.approx(21.02, abs=0.1)


def test_paf_nao_multiplica_percentual_que_ja_estava_em_pontos(xl):
    # 'Demais' de 2010 vale legitimamente 0.79 em pontos percentuais (nao
    # e fracao) -- uma heuristica de magnitude confundiria isso com um
    # valor em fracao e multiplicaria por engano.
    df = paf_reserva.parse_paf(xl)
    linha_2010 = df[
        (df["ano"] == 2010) & (df["versao"] == "original")
        & (df["indicador"] == "Demais")
    ].iloc[0]
    assert linha_2010["realizado"] == pytest.approx(0.79, abs=0.01)


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


def _aba_6_1(colunas_extra=0, cabecalhos=None):
    """Uma 6.1 sintetica, opcionalmente com colunas inseridas antes dos dados."""
    if cabecalhos is None:
        cabecalhos = [
            "Reserva de Liquidez", "Valor Prudencial (3 meses)",
            "Índice de Liquidez",
        ]
    vazias = [None] * colunas_extra
    return pd.DataFrame([
        [None, *vazias, None, None, None],
        ["Mês", *vazias, *cabecalhos],
        [None, *vazias, "(R$ Bilhões)", "(R$ Bilhões)", "(Meses)"],
        [datetime.date(2015, 1, 31), *vazias, 72.0, 205.5, 1.71],
        [datetime.date(2015, 2, 28), *vazias, 133.8, 263.2, 1.54],
    ])


def test_reserva_acha_as_colunas_pelo_cabecalho_e_nao_pela_posicao(monkeypatch):
    """Uma coluna inserida na aba nao pode deslocar as grandezas.

    Era o unico parser do projeto que nao conferia nada: com posicoes
    fixas, reserva_milhoes passaria a trazer outra coluna sem erro nenhum.
    """
    monkeypatch.setattr(
        paf_reserva, "aba", lambda *a, **k: _aba_6_1(colunas_extra=2)
    )

    df = paf_reserva.parse_reserva(None)

    assert len(df) == 2
    primeira = df.sort_values("data").iloc[0]
    assert primeira["reserva_milhoes"] == pytest.approx(72_000.0)
    assert primeira["valor_prudencial_milhoes"] == pytest.approx(205_500.0)
    assert primeira["indice_liquidez_meses"] == pytest.approx(1.71)


def test_reserva_falha_alto_se_o_cabecalho_mudar(monkeypatch):
    monkeypatch.setattr(
        paf_reserva, "aba",
        lambda *a, **k: _aba_6_1(cabecalhos=["Coluna A", "Coluna B", "Coluna C"]),
    )

    with pytest.raises(LookupError, match="6.1"):
        paf_reserva.parse_reserva(None)
