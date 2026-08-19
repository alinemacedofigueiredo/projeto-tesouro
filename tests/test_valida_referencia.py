"""O validador das tabelas de referencia so vale se ele PEGAR erro.

Cada teste aqui estraga o CSV de um jeito plausivel -- o tipo de coisa que alguem
digita errado ao acrescentar o PAF do ano que vem -- e exige que o validador
reclame. Um validador que nunca reprova nada e pior que nenhum, porque da falsa
seguranca.
"""

import pandas as pd
import pytest

from tesouro import valida_referencia as v


@pytest.fixture
def bom():
    """O arquivo de verdade, que precisa passar."""
    return pd.read_csv(v.caminho_paf())


def _conferir(df, tmp_path):
    caminho = tmp_path / "paf_bandas.csv"
    df.to_csv(caminho, index=False)
    return v.conferir_paf(caminho)


def test_o_arquivo_de_verdade_passa(bom, tmp_path):
    assert _conferir(bom, tmp_path) == []


def test_cobre_de_2003_ate_o_ano_corrente(bom):
    assert bom["ano"].min() == 2003
    assert bom["ano"].max() >= 2026
    # Os seis obrigatorios em todo ano, mais o setimo (vincendo_12m_pct) onde ele
    # existe -- ele e opcional por ano, ver o LEIA-ME da pasta.
    assert set(bom["indicador"]) == set(v.TODOS)
    for (ano, versao), g in bom.groupby(["ano", "versao"]):
        assert set(v.INDICADORES) <= set(g["indicador"]), f"{ano}/{versao}"


def test_pega_minimo_maior_que_maximo(bom, tmp_path):
    bom.loc[0, "minimo"] = bom.loc[0, "maximo"] + 10
    erros = _conferir(bom, tmp_path)
    assert any("maior que maximo" in e for e in erros)


def test_pega_percentual_escrito_como_fracao(bom, tmp_path):
    # 0,21 em vez de 21. Nao adianta limiar de plausibilidade: 0,21 esta entre
    # 0 e 100. O que pega e a soma das quatro bandas de composicao dar ~100.
    alvo = (bom["ano"] == 2026) & (bom["indicador"] == "prefixado_pct")
    bom.loc[alvo, "minimo"] = 0.21
    bom.loc[alvo, "maximo"] = 0.25
    erros = _conferir(bom, tmp_path)
    assert any("somam" in e and "fracao" in e for e in erros)


def test_pega_indicador_com_nome_errado(bom, tmp_path):
    bom.loc[5, "indicador"] = "prefixado"          # falta o sufixo _pct
    erros = _conferir(bom, tmp_path)
    assert any("nao e um dos nomes fixos" in e for e in erros)


def test_pega_ano_duplicado(bom, tmp_path):
    dobrado = pd.concat([bom, bom[bom["ano"] == 2026]])
    erros = _conferir(dobrado, tmp_path)
    assert any("chave repetida" in e for e in erros)


def test_pega_indicador_faltando_no_ano(bom, tmp_path):
    sem = bom[~((bom["ano"] == 2026) & (bom["indicador"] == "cambio_pct"))]
    erros = _conferir(sem, tmp_path)
    assert any("faltam os indicadores" in e for e in erros)


def test_pega_realizado_zerado_no_ano_aberto(bom, tmp_path):
    # Zero nao e "ainda nao fechou": seria "a composicao foi a zero".
    bom.loc[bom["ano"] == 2026, "realizado"] = 0
    erros = _conferir(bom, tmp_path)
    assert erros


def test_pega_realizado_diferente_entre_original_e_revisado(bom, tmp_path):
    # A meta muda quando revisada; o que aconteceu nao muda.
    alvo = ((bom["ano"] == 2021) & (bom["versao"] == "revisado")
            & (bom["indicador"] == "prefixado_pct"))
    bom.loc[alvo, "realizado"] = 99.0
    erros = _conferir(bom, tmp_path)
    assert any("realizado difere" in e for e in erros)


def test_pega_revisado_sem_original(bom, tmp_path):
    so_revisado = bom[~((bom["ano"] == 2021) & (bom["versao"] == "original"))]
    erros = _conferir(so_revisado, tmp_path)
    assert any("sem a original" in e for e in erros)


def test_pega_coluna_ausente(bom, tmp_path):
    erros = _conferir(bom.drop(columns=["maximo"]), tmp_path)
    assert any("colunas ausentes" in e for e in erros)


def test_o_ano_aberto_nao_tem_realizado(bom):
    # Invariante do arquivo: o ano corrente ainda nao fechou.
    abertos = bom[bom["realizado"].isna()]["ano"].unique()
    assert list(abertos) == [bom["ano"].max()]
