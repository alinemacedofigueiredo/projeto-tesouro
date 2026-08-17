import datetime
from pathlib import Path

import pytest
from tesouro import leitura_rmd

AMOSTRA = Path(__file__).parent / "fixtures" / "rmd_amostra.xlsx"


@pytest.fixture(scope="module")
def xl():
    return leitura_rmd.abrir(AMOSTRA)


def test_padrao_a_devolve_formato_longo(xl):
    df = leitura_rmd.ler_padrao_a(xl, "1.1", "milhoes")
    assert list(df.columns) == [
        "data", "linha_origem", "rotulo", "nivel_indentacao", "valor_milhoes"
    ]
    assert len(df) > 0


def test_padrao_a_descarta_colunas_de_total_anual(xl):
    # A aba 1.1 intercala colunas '2007', '2008' entre os meses. Cada
    # (linha da planilha, data) so pode aparecer uma vez; uma coluna de
    # total anual lida como mes criaria uma segunda entrada para a mesma
    # linha e a mesma data.
    #
    # A chave e linha_origem, nao o rotulo: a aba repete rotulos entre as
    # secoes de emissao e de resgate, e essas repeticoes sao legitimas.
    df = leitura_rmd.ler_padrao_a(xl, "1.1", "milhoes")
    assert not df.duplicated(subset=["linha_origem", "data"]).any()


def test_padrao_a_distingue_rotulos_repetidos_pela_linha_de_origem(xl):
    # A aba 1.1 repete 'Trocas Oferta Publica' e 'Tesouro Direto' sob
    # emissoes e sob resgates. Sem linha_origem nao ha como separa-los.
    df = leitura_rmd.ler_padrao_a(xl, "1.1", "milhoes")
    repetidos = df[df["rotulo"] == "Tesouro Direto"]
    if len(repetidos):
        numa_data = repetidos[repetidos["data"] == repetidos["data"].min()]
        assert numa_data["linha_origem"].nunique() == len(numa_data)


def test_padrao_a_le_a_primeira_data_da_serie(xl):
    df = leitura_rmd.ler_padrao_a(xl, "1.1", "milhoes")
    assert df["data"].min() == datetime.date(2006, 11, 30)


def test_padrao_a_preserva_a_hierarquia_pela_indentacao(xl):
    df = leitura_rmd.ler_padrao_a(xl, "2.1", "milhoes")
    niveis = df.groupby("rotulo")["nivel_indentacao"].first()
    assert niveis["DPF EM PODER DO PÚBLICO"] == 0
    assert niveis["LFT"] > niveis["DPMFi"]


def test_padrao_a_converte_bilhoes_para_milhoes(xl):
    em_milhoes = leitura_rmd.ler_padrao_a(xl, "2.1", "milhoes")
    em_bilhoes = leitura_rmd.ler_padrao_a(xl, "2.1", "bilhoes")
    a = em_milhoes["valor_milhoes"].dropna().iloc[0]
    b = em_bilhoes["valor_milhoes"].dropna().iloc[0]
    assert b == pytest.approx(a * 1000)


def test_padrao_b_devolve_formato_longo(xl):
    df = leitura_rmd.ler_padrao_b(xl, "2.4", linha_cabecalho=4, unidade="bilhoes")
    assert list(df.columns) == ["data", "categoria", "valor_milhoes"]
    assert set(df["categoria"]) >= {"Prefixado", "Taxa Flutuante", "Câmbio"}


def test_padrao_b_ignora_a_coluna_de_percentual(xl):
    # Cada categoria ocupa duas colunas (valor, %); so o valor e lido.
    df = leitura_rmd.ler_padrao_b(xl, "2.4", linha_cabecalho=4, unidade="bilhoes")
    uma_data = df[df["data"] == df["data"].min()]
    # Se o percentual tivesse entrado, haveria valores entre 0 e 1
    # convivendo com valores na casa das centenas de bilhoes.
    assert (uma_data["valor_milhoes"].dropna() > 1.0).all()


def test_padrao_b_trata_marcadores_de_ausente(xl):
    # A aba 3.1 usa 'N/D' nos primeiros anos.
    df = leitura_rmd.ler_padrao_b(xl, "3.1", linha_cabecalho=6, unidade="bilhoes")
    assert df["valor_milhoes"].isna().any()
    assert not (df["valor_milhoes"] == 0).all()


def test_aba_ausente_falha_dizendo_qual_sumiu(xl):
    # O Tesouro descontinua abas (3.5 e 5.6 sairam em junho/2025) e as
    # mantem no indice. O erro precisa ser legivel um ano depois.
    with pytest.raises(LookupError) as erro:
        leitura_rmd.aba(xl, "3.5")
    mensagem = str(erro.value)
    assert "3.5" in mensagem
    assert "2.1" in mensagem  # lista as abas que existem
