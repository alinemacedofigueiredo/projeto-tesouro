# tests/test_custo.py
import datetime
from pathlib import Path

import pytest
from tesouro import leitura_rmd
from tesouro.parse_rmd import custo

AMOSTRA = Path(__file__).parent / "fixtures" / "rmd_amostra.xlsx"


@pytest.fixture(scope="module")
def df():
    return custo.parse(leitura_rmd.abrir(AMOSTRA))


def test_colunas_canonicas(df):
    assert list(df.columns) == [
        "data", "medida", "nivel", "entidade", "titulo", "custo_aa_pct"
    ]


def test_demais_da_dpmfi_nao_se_confunde_com_o_da_dpfe(df):
    # 'Demais' aparece duas vezes em 4.1 e 4.2: sob a DPMFi e sob a
    # Divida Mobiliaria. Indexado por rotulo, o segundo sobrescreve o
    # primeiro e a linha da DPMFi acaba dentro da DPFe.
    demais = df[df["titulo"] == "Demais"]
    assert {"DPMFi", "DPFe"} <= set(demais["nivel"].unique())
    assert not df.duplicated(
        subset=["data", "medida", "nivel", "entidade", "titulo"]
    ).any()


def test_subgrupos_da_dpfe_sao_entidade_e_nao_titulo(df):
    assert "Dívida Mobiliária" not in set(df["titulo"].dropna().unique())
    assert "Dívida Mobiliária" in set(df["entidade"].dropna().unique())
    assert "Dívida Contratual" in set(df["entidade"].dropna().unique())


def test_ignora_as_duas_formas_de_nota_de_rodape(df):
    # As abas terminam com nota numerada ('1  Titulos de renegociacao')
    # e com nota prefixada ('Obs: O Tesouro Nacional...').
    rotulos = [str(v) for v in df["titulo"].dropna().unique()]
    assert not any(r[:1].isdigit() for r in rotulos)
    assert not any(r.lower().startswith("obs") for r in rotulos)


def test_traz_as_tres_medidas(df):
    assert set(df["medida"].unique()) == {"mensal", "acum_12m", "emissoes_12m"}


def test_comparar_emissao_com_estoque_e_um_filtro(df):
    # O ganho da consolidacao: as duas medidas alinhadas na mesma chave.
    estoque = df[(df["medida"] == "acum_12m") & (df["nivel"] == "DPMFi")]
    emissao = df[(df["medida"] == "emissoes_12m") & (df["nivel"] == "DPMFi")]
    assert len(estoque) > 0
    assert len(emissao) > 0
    assert set(emissao["data"]) <= set(estoque["data"])


def test_preserva_custo_negativo(df):
    # NTN-D em 2005 tem custo negativo de verdade na aba 4.1.
    assert (df["custo_aa_pct"].dropna() < 0).any()


def test_abre_por_titulo(df):
    titulos = set(df["titulo"].dropna().unique())
    assert {"LFT", "LTN", "NTN-B"} <= titulos


def test_aba_4_3_pos_2021_le_a_coluna_cme_da_trinca(df):
    # A partir de jan/2021 a 4.3 muda de leiaute: cada mes vira um
    # cabecalho mesclado de duas linhas -- o rotulo do mes cobrindo tres
    # colunas, e as tres sub-colunas por baixo ('Taxa media', 'Variacao
    # do Indexador', 'CME'). So a CME equivale ao valor unico de antes.
    #
    # A amostra so cruza essa fronteira (COLUNAS_POR_ABA['4.3'] = 140 em
    # gerar_fixtures.py) para que este teste va alem de jan/2021 -- sem
    # isso o ramo da trinca em _colunas_de_data_4_3 nunca roda nos
    # testes. Os valores abaixo vem do arquivo real (Anexo RMD_Junho_26):
    # a coluna errada da trinca ('Taxa media') da 2.124644 para a NTN-B e
    # 0.139746 para a LFT -- um numero plausivel e errado, nao um NaN --
    # entao a ancoragem tem que ser num valor exato, nao so 'nao e NaN'.
    jan21 = df[
        (df["medida"] == "emissoes_12m") & (df["data"] == datetime.date(2021, 1, 31))
    ]
    ntnb = jan21.loc[jan21["titulo"] == "NTN-B", "custo_aa_pct"].iloc[0]
    lft = jan21.loc[jan21["titulo"] == "LFT", "custo_aa_pct"].iloc[0]
    assert ntnb == pytest.approx(10.519469)
    assert lft == pytest.approx(2.185361)
