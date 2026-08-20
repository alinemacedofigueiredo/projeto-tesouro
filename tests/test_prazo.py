# tests/test_prazo.py
from pathlib import Path

import pytest
from tesouro import leitura_rmd
from tesouro.parse_rmd import prazo

AMOSTRA = Path(__file__).parent / "fixtures" / "rmd_amostra.xlsx"


@pytest.fixture(scope="module")
def xl():
    return leitura_rmd.abrir(AMOSTRA)


def test_por_titulo_tem_as_colunas_canonicas(xl):
    df = prazo.parse_por_titulo(xl)
    assert list(df.columns) == [
        "data", "nivel", "entidade", "titulo", "prazo_anos"
    ]


def test_por_titulo_traz_prazos_plausiveis(xl):
    # O limite superior tem que caber na familia RendA+/EducA+ (NTN-B1),
    # legitimamente longa: no arquivo real ela chega a 28,71 anos, em 42
    # linhas. Um teto de 15 anos passa apenas porque a amostra da 3.7 esta
    # cortada em 30 colunas, e quem ampliar a amostra iria cacar um bug
    # que nao existe.
    df = prazo.parse_por_titulo(xl)
    valores = df["prazo_anos"].dropna()
    assert (valores >= 0).all()
    assert valores.between(0, 40).all()


def test_por_indexador_separa_dpmfi_de_dpfe(xl):
    df = prazo.parse_por_indexador(xl)
    assert list(df.columns) == [
        "data", "nivel", "entidade", "categoria", "prazo_anos"
    ]
    niveis = set(df["nivel"].dropna().unique())
    assert "DPMFi" in niveis


def test_demais_da_dpmfi_nao_se_confunde_com_o_da_dpfe(xl):
    # 'Demais' aparece duas vezes nas duas abas: sob o Tesouro Nacional e
    # sob a Divida Mobiliaria. Indexado por rotulo, o segundo sobrescreve
    # o primeiro e a linha da DPMFi acaba dentro da DPFe.
    por_titulo = prazo.parse_por_titulo(xl)
    demais = por_titulo[por_titulo["titulo"] == "Demais"]
    assert {"DPMFi", "DPFe"} <= set(demais["nivel"].unique())
    assert not por_titulo.duplicated(
        subset=["data", "nivel", "entidade", "titulo"]
    ).any()


def test_subgrupos_da_dpfe_sao_entidade_e_nao_folha(xl):
    # 'Divida Mobiliaria' e 'Divida Contratual' agrupam os instrumentos da
    # DPFe; o prazo medio deles e media ponderada dos filhos, e portanto
    # derivado. Nao podem aparecer como folha.
    for df, folha in (
        (prazo.parse_por_titulo(xl), "titulo"),
        (prazo.parse_por_indexador(xl), "categoria"),
    ):
        assert "D\u00edvida Mobili\u00e1ria" not in set(df[folha].dropna().unique())
        assert "D\u00edvida Mobili\u00e1ria" in set(df["entidade"].dropna().unique())
        assert "D\u00edvida Contratual" in set(df["entidade"].dropna().unique())


def test_preserva_o_prazo_medio_da_dpf(xl):
    # E o numero que a analise compara com a banda do PAF; se a linha de
    # nivel fosse descartada junto com os agregados, ele se perderia.
    df = prazo.parse_por_titulo(xl)
    da_dpf = df[(df["nivel"] == "DPF") & df["titulo"].isna()]
    assert len(da_dpf) > 0
    assert da_dpf["prazo_anos"].notna().any()


def test_ignora_a_nota_de_rodape_numerada(xl):
    # A ultima linha das duas abas comeca com '1 ' e explica a
    # Reestruturada; nao e dado.
    for df, folha in (
        (prazo.parse_por_titulo(xl), "titulo"),
        (prazo.parse_por_indexador(xl), "categoria"),
    ):
        rotulos = [str(v) for v in df[folha].dropna().unique()]
        assert not any(r[:1].isdigit() for r in rotulos)


def test_emissoes_tem_indexadores(xl):
    df = prazo.parse_emissoes(xl)
    assert list(df.columns) == ["data", "indexador", "prazo_anos"]
    assert "Prefixado" in set(df["indexador"].unique())


def test_emissoes_trata_traco_como_ausente(xl):
    # A aba 3.9 usa '-' onde nao houve emissao daquele indexador no mes.
    df = prazo.parse_emissoes(xl)
    assert df["prazo_anos"].isna().any()
