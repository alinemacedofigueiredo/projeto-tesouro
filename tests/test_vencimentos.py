import datetime
from pathlib import Path

import pytest
from tesouro import leitura_rmd
from tesouro.parse_rmd import vencimentos

AMOSTRA = Path(__file__).parent / "fixtures" / "rmd_amostra.xlsx"


@pytest.fixture(scope="module")
def xl():
    return leitura_rmd.abrir(AMOSTRA)


def test_faixa_tem_as_colunas_canonicas(xl):
    df = vencimentos.parse_por_faixa(xl)
    assert list(df.columns) == ["data", "nivel", "faixa", "valor_milhoes"]


def test_faixa_cobre_as_seis_faixas(xl):
    df = vencimentos.parse_por_faixa(xl)
    faixas = set(df["faixa"].unique())
    assert "Até 12 meses" in faixas
    assert "Acima de 5 anos" in faixas


def test_faixa_separa_os_tres_blocos_empilhados(xl):
    # A aba 3.1 traz DPF, DPMFi e DPFe um abaixo do outro, cada um com a
    # serie completa. Lidos juntos, cada data apareceria tres vezes sem
    # nada dizendo a qual serie pertence.
    df = vencimentos.parse_por_faixa(xl)
    assert set(df["nivel"].unique()) == {"DPF", "DPMFi", "DPFe"}
    assert not df.duplicated(subset=["data", "nivel", "faixa"]).any()


def test_faixa_dpf_e_maior_que_dpmfi(xl):
    # DPF = DPMFi + DPFe, entao o total tem de ser maior que a parte --
    # mas so dentro do periodo em que os tres niveis tem dado. A serie de
    # DPMFi comeca em 1999, quase sete anos antes da de DPF (N/D ate
    # 2006), entao somar o historico inteiro de cada nivel compararia
    # janelas de tamanhos diferentes e poderia inverter o resultado sem
    # que os blocos tivessem se misturado. Restringir ao periodo em que
    # DPF tem dado real elimina esse efeito.
    df = vencimentos.parse_por_faixa(xl)
    dpf = df[df["nivel"] == "DPF"]
    primeira_data_com_dado = dpf.loc[dpf["valor_milhoes"].notna(), "data"].min()
    comparavel = df[df["data"] >= primeira_data_com_dado]
    por_nivel = comparavel.groupby("nivel")["valor_milhoes"].sum()
    assert por_nivel["DPF"] > por_nivel["DPMFi"] > 0


def test_faixa_trata_nd_como_ausente(xl):
    df = vencimentos.parse_por_faixa(xl)
    assert df["valor_milhoes"].isna().any()


def test_faixa_nao_grava_o_total_derivado(xl):
    # A aba 3.1 traz 'Total' como se fosse mais uma faixa de prazo, na
    # ultima posicao de cada bloco. Se o filtro sumisse, quem somasse as
    # faixas para conferir o total contaria tudo em dobro.
    df = vencimentos.parse_por_faixa(xl)
    faixas = {f.lower() for f in df["faixa"].unique()}
    assert "total" not in faixas
    assert "part %" not in faixas


def test_a_vencer_12m_tem_indexadores(xl):
    df = vencimentos.parse_a_vencer_12m(xl)
    assert list(df.columns) == ["data", "indexador", "valor_milhoes"]
    assert "Prefixado" in set(df["indexador"].unique())


def test_a_vencer_12m_nao_grava_o_total_derivado(xl):
    df = vencimentos.parse_a_vencer_12m(xl)
    indexadores = {i.lower() for i in df["indexador"].unique()}
    assert "total" not in indexadores
    assert "part %" not in indexadores


def test_cronograma_usa_data_de_referencia_e_nao_data(xl):
    # E retrato, nao serie: carrega a data de fechamento do RMD.
    df = vencimentos.parse_cronograma(xl)
    assert list(df.columns) == [
        "data_referencia", "mes_vencimento", "grupo_titulo", "valor_milhoes"
    ]
    assert df["data_referencia"].nunique() == 1
    assert df["data_referencia"].iloc[0] == datetime.date(2026, 6, 30)


def test_cronograma_olha_para_frente(xl):
    df = vencimentos.parse_cronograma(xl)
    assert (df["mes_vencimento"] > df["data_referencia"]).all()


def test_cronograma_nao_grava_o_percentual_derivado(xl):
    df = vencimentos.parse_cronograma(xl)
    assert "PART %" not in set(df["grupo_titulo"].unique())
