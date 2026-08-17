import datetime
from pathlib import Path

import pytest
from tesouro import leitura_rmd
from tesouro.parse_rmd import estoque

AMOSTRA = Path(__file__).parent / "fixtures" / "rmd_amostra.xlsx"


@pytest.fixture(scope="module")
def xl():
    return leitura_rmd.abrir(AMOSTRA)


def test_estoque_dpf_tem_as_colunas_canonicas(xl):
    df = estoque.parse_dpf(xl)
    assert list(df.columns) == [
        "data", "nivel", "entidade", "titulo", "valor_milhoes"
    ]


def test_estoque_dpf_marca_a_linha_em_poder_do_publico(xl):
    # E a linha que o PAF bandeia; precisa ser distinguivel das demais.
    df = estoque.parse_dpf(xl)
    assert (df["nivel"] == "DPF em poder do publico").any()


def test_estoque_dpf_separa_tesouro_de_banco_central(xl):
    df = estoque.parse_dpf(xl)
    entidades = set(df["entidade"].dropna().unique())
    assert "Tesouro Nacional" in entidades
    assert "Banco Central" in entidades


def test_estoque_dpf_converte_bilhoes_para_milhoes(xl):
    df = estoque.parse_dpf(xl)
    publico = df[
        (df["nivel"] == "DPF em poder do publico")
        & (df["data"] == datetime.date(2000, 12, 31))
    ]
    # 653,559 bilhoes = 653.559 milhoes
    assert publico["valor_milhoes"].iloc[0] == pytest.approx(653559.07, abs=1.0)


def test_composicao_tem_os_indexadores(xl):
    df = estoque.parse_composicao(xl)
    assert list(df.columns) == ["data", "indexador", "valor_milhoes"]
    assert {"Prefixado", "Taxa Flutuante", "Câmbio"} <= set(df["indexador"])


def test_composicao_nao_grava_o_percentual_derivado(xl):
    df = estoque.parse_composicao(xl)
    # Se o percentual tivesse vazado, haveria valores menores que 1.
    assert (df["valor_milhoes"].dropna() > 1.0).all()


def test_detentores_tem_as_colunas_canonicas(xl):
    df = estoque.parse_detentores(xl)
    assert list(df.columns) == ["data", "detentor", "valor_milhoes"]
    assert len(df) > 0


def test_detentores_por_titulo_preserva_o_bloco_do_titulo(xl):
    df = estoque.parse_detentores_por_titulo(xl)
    assert list(df.columns) == ["data", "detentor", "titulo", "valor_milhoes"]
    assert "LFT" in set(df["titulo"].unique())


def test_detentores_por_titulo_atravessa_mais_de_um_bloco(xl):
    # Os blocos ficam a ~189 linhas um do outro. Se a deteccao de bloco
    # falhar, so o primeiro titulo aparece -- e o teste acima passaria
    # mesmo assim.
    df = estoque.parse_detentores_por_titulo(xl)
    assert {"LFT", "LTN"} <= set(df["titulo"].unique())


def test_detentores_por_titulo_nao_perde_os_meses_retificados(xl):
    # 'mar/18*' e 'abr/18*' vem como texto no meio do bloco. Tratados como
    # rotulo de titulo, zerariam os detentores e as ~100 linhas seguintes
    # do bloco sumiriam sem erro nenhum.
    df = estoque.parse_detentores_por_titulo(xl)
    do_lft = df[df["titulo"] == "LFT"]
    assert datetime.date(2018, 3, 31) in set(do_lft["data"])
    assert datetime.date(2018, 4, 30) in set(do_lft["data"])
    # e o bloco continua depois deles
    assert (do_lft["data"] > datetime.date(2018, 4, 30)).any()


def test_detentores_por_titulo_ignora_o_rodape_de_asterisco(xl):
    # A ultima linha da aba comeca com '*' e explica a retificacao.
    df = estoque.parse_detentores_por_titulo(xl)
    assert not any(str(t).startswith("*") for t in df["titulo"].unique())
