import datetime
from pathlib import Path

import pytest
from tesouro import leitura_rmd
from tesouro.parse_rmd import funding

AMOSTRA = Path(__file__).parent / "fixtures" / "rmd_amostra.xlsx"


@pytest.fixture(scope="module")
def xl():
    return leitura_rmd.abrir(AMOSTRA)


def test_por_canal_tem_as_colunas_canonicas(xl):
    df = funding.parse_por_canal(xl)
    assert list(df.columns) == [
        "data", "esfera", "operacao", "canal", "valor_milhoes"
    ]


def test_por_canal_traz_emissoes_E_resgates(xl):
    # A aba nomeia as esferas de resgate como 'III - DPMFi' e 'IV - DPFe',
    # diferente de 'I - DPMFi' e 'II - DPFe' das emissoes. Um mapeamento
    # que so conheca as duas primeiras descarta todos os resgates em
    # silencio, e a tabela sai pela metade sem erro nenhum.
    df = funding.parse_por_canal(xl)
    assert set(df["operacao"].unique()) == {"emissao", "resgate"}


def test_por_canal_nao_colapsa_rotulo_repetido_entre_secoes(xl):
    # 'Tesouro Direto' existe sob emissoes e sob resgates. Se a hierarquia
    # for indexada pelo texto do rotulo, uma secao sobrescreve a outra.
    df = funding.parse_por_canal(xl)
    operacoes = set(
        df[df["canal"] == "Tesouro Direto"]["operacao"].unique()
    )
    assert operacoes == {"emissao", "resgate"}


def test_por_canal_preserva_os_canais_da_dpmfi(xl):
    df = funding.parse_por_canal(xl)
    canais = set(df[df["esfera"] == "DPMFi"]["canal"].dropna().unique())
    assert "Oferta Pública" in canais
    assert "Tesouro Direto" in canais
    assert "Vencimentos" in canais


def test_por_canal_recupera_o_valor_de_emissao_de_novembro_de_2006(xl):
    df = funding.parse_por_canal(xl)
    linha = df[
        (df["data"] == datetime.date(2006, 11, 30))
        & (df["operacao"] == "emissao")
        & (df["esfera"] == "DPMFi")
        & (df["canal"] == "Oferta Pública")
    ]
    assert linha["valor_milhoes"].iloc[0] == pytest.approx(41042.54, abs=0.01)


def test_por_canal_exclui_os_totais_derivados(xl):
    # 'EMISSAO LIQUIDA' e as linhas sob ela sao I-III e II-IV: derivadas.
    df = funding.parse_por_canal(xl)
    rotulos = set(df["canal"].dropna().unique())
    assert not any("LÍQUIDA" in r.upper() for r in rotulos)
    assert not any(r.startswith("DPMFi ") for r in rotulos)


def test_por_canal_nao_tem_chave_duplicada(xl):
    df = funding.parse_por_canal(xl)
    assert not df.duplicated(
        subset=["data", "esfera", "operacao", "canal"]
    ).any()


def test_por_canal_trata_banco_central_como_esfera_propria(xl):
    # 'Banco Central' e um cabecalho de esfera sob RESGATES/III - DPMFi,
    # nao um canal. Se o ramo que reconhece esse rotulo quebrar, a linha
    # 'Banco Central' vira detalhe espurio herdando a esfera anterior
    # (DPMFi) e o NBC-E se funde silenciosamente dentro da DPMFi -- os
    # outros testes desta suite nao pegam essa quebra porque nenhum deles
    # olha para a esfera 'Banco Central' especificamente.
    df = funding.parse_por_canal(xl)
    assert "Banco Central" not in set(df["canal"].dropna().unique())
    assert "Banco Central" in set(df["esfera"].dropna().unique())

    nbce = df[df["canal"] == "NBC-E"]
    assert not nbce.empty
    assert set(nbce["esfera"].unique()) == {"Banco Central"}
    assert set(nbce["operacao"].unique()) == {"resgate"}


def test_por_indexador_tem_as_colunas_canonicas(xl):
    df = funding.parse_por_indexador(xl)
    assert list(df.columns) == [
        "data", "esfera", "operacao", "indexador", "valor_milhoes"
    ]


def test_por_indexador_cobre_os_indexadores(xl):
    df = funding.parse_por_indexador(xl)
    indexadores = set(df["indexador"].unique())
    assert {"Prefixados", "Índice de Preços", "Taxa Flutuante"} <= indexadores


def test_por_indexador_separa_demais_da_dpmfi_do_demais_da_dpfe(xl):
    # 'Demais' aparece quatro vezes na aba 1.2: em DPMFi e em DPFe, sob
    # emissoes e sob resgates. Sem a esfera na chave, viram linhas
    # indistinguiveis com valores diferentes.
    df = funding.parse_por_indexador(xl)
    demais = df[df["indexador"] == "Demais"]
    assert set(demais["esfera"].unique()) == {"DPMFi", "DPFe"}
    assert not df.duplicated(
        subset=["data", "esfera", "operacao", "indexador"]
    ).any()


def test_por_indexador_ignora_as_notas_de_rodape(xl):
    # A aba 1.2 termina com linhas 'Obs:' e 'Obs 2:' que nao sao dados.
    df = funding.parse_por_indexador(xl)
    assert not df["indexador"].str.startswith("Obs").any()
