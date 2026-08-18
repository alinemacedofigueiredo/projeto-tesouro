from datetime import date

import pandas as pd
import pytest
from tesouro import parse_bloomberg


@pytest.fixture(scope="module")
def taxas():
    return parse_bloomberg.parse_taxas()


@pytest.fixture(scope="module")
def vna():
    return parse_bloomberg.parse_vna()


def test_taxas_tem_as_colunas_canonicas(taxas):
    assert list(taxas.columns) == ["data", "isin", "titulo", "vencimento", "taxa_pct"]
    assert len(taxas) > 8000


def test_taxa_fica_em_percentual(taxas):
    # Convencao do projeto: 13.5 significa 13,5%.
    prefixados = taxas[taxas["titulo"] == "LTN"]["taxa_pct"]
    assert prefixados.median() > 5
    assert prefixados.median() < 20


def test_agio_da_lft_e_pequeno_e_pode_ser_negativo(taxas):
    lft = taxas[taxas["titulo"] == "LFT"]["taxa_pct"]
    assert lft.abs().median() < 1
    assert (lft < 0).any()


def test_datas_sao_dia_util(taxas):
    from tesouro import calendario
    cal = calendario.padrao()
    assert all(cal.eh_dia_util(d) for d in taxas["data"].head(500))


def test_vna_tem_as_colunas_canonicas(vna):
    assert list(vna.columns) == ["data", "indice", "vna"]
    assert set(vna["indice"].unique()) == {"IPCA", "SELIC"}


def test_vna_da_selic_nunca_cai(vna):
    # A Selic acumula sempre; queda indica erro de leitura.
    s = vna[vna["indice"] == "SELIC"].sort_values("data")["vna"]
    assert (s.diff().dropna() >= 0).all()


def test_vna_do_ipca_cai_em_meses_de_deflacao(vna):
    i = vna[vna["indice"] == "IPCA"].sort_values("data")["vna"]
    assert (i.diff().dropna() < 0).any()


def test_vna_em_ordem_de_grandeza_de_reais(vna):
    ult = vna[vna["data"] == vna["data"].max()].set_index("indice")["vna"]
    assert 4000 < ult["IPCA"] < 6000
    assert 15000 < ult["SELIC"] < 25000


def test_nao_ha_chave_duplicada(taxas, vna):
    assert not taxas.duplicated(subset=["data", "isin"]).any()
    assert not vna.duplicated(subset=["data", "indice"]).any()
