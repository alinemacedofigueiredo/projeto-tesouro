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
    # A mensagem especifica, e nao um "assert erros" pelado: zerar SO os quatro
    # percentuais nao produz erro nenhum -- o validador nao tem checagem de
    # "composicao zerada", e o teste passava por causa do estoque (0 < 100) e do
    # prazo (0 < 1) caindo na faixa de plausibilidade. Nomear a mensagem deixa
    # claro o que esta protegido de verdade.
    assert erros
    assert any("fora da faixa" in e for e in erros), erros


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
    #
    # So os SEIS obrigatorios entram na conta. As linhas do setimo indicador
    # (vincendo_12m_pct) nascem sem realizado de proposito -- nenhum realizado deste
    # arquivo e lido por nada, e o do vincendo, quando interessa, sai da aba 5.7.
    obrigatorios = bom[bom["indicador"].isin(v.INDICADORES)]
    abertos = obrigatorios[obrigatorios["realizado"].isna()]["ano"].unique()
    assert list(abertos) == [bom["ano"].max()]

    # E o setimo nao tem realizado em nenhum ano, que e o combinado.
    # Dezessete linhas: 2016 a 2026, mais as seis revisoes (out/16, set/18, ago/20,
    # mai/21, dez/24, set/25).
    vincendo = bom[bom["indicador"] == "vincendo_12m_pct"]
    assert len(vincendo) == 17
    assert sorted(vincendo["ano"].unique()) == list(range(2016, 2027))
    assert vincendo["realizado"].isna().all()

# ---------------------------------------------------------------------------
# paf_bandas_conferencia.csv -- a transcricao da tabela que a dona do projeto
# mantem a parte, usada para cruzar o paf_bandas.csv contra fonte independente.
#
# Estes testes SAO a validacao daquele arquivo: nao ha entrada dele no
# valida_referencia.main(), de proposito. Divergencia entre as duas tabelas
# significa "alguem precisa olhar", nao "o numero na tela esta errado" -- a banda
# desenhada sai do paf_bandas.csv, que tem validador proprio e roda antes de
# qualquer leitura.
# ---------------------------------------------------------------------------

# Como cada coluna da transcricao vira um dos indicadores do paf_bandas.csv.
# O estoque e o unico com conversao: a tabela dela esta em R$ trilhoes.
_DE_PARA = {
    "estoque_bilhoes": ("estoque_tri_min", "estoque_tri_max", 1000.0),
    "prefixado_pct": ("prefixado_min", "prefixado_max", 1.0),
    "indice_precos_pct": ("ipca_min", "ipca_max", 1.0),
    "taxa_flutuante_pct": ("flutuante_min", "flutuante_max", 1.0),
    "cambio_pct": ("cambio_min", "cambio_max", 1.0),
    "prazo_medio_anos": ("prazo_min", "prazo_max", 1.0),
    "vincendo_12m_pct": ("vincendo_min", "vincendo_max", 1.0),
}


@pytest.fixture(scope="module")
def conferencia():
    return pd.read_csv(v.caminho_paf().parent / "paf_bandas_conferencia.csv")


def test_a_transcricao_cobre_2016_a_2026_com_as_seis_revisoes(conferencia):
    assert len(conferencia) == 17
    assert sorted(conferencia["ano"].unique()) == list(range(2016, 2027))
    revisados = sorted(conferencia[conferencia["versao"] == "revisado"]["ano"])
    assert revisados == [2016, 2018, 2020, 2021, 2024, 2025]
    # O rotulo guarda o mes da revisao, que o paf_bandas.csv nao tem espaco para
    # carregar -- e a unica informacao que so existe aqui.
    assert set(conferencia[conferencia["versao"] == "revisado"]["rotulo"]) == {
        "out/16 (revis\u00e3o)", "set/18 (revis\u00e3o)", "ago/20 (revis\u00e3o)",
        "mai/21 (revis\u00e3o)", "dez/24 (revis\u00e3o)", "set/25 (revis\u00e3o)",
    }


def test_toda_banda_minima_e_menor_que_a_maxima(conferencia):
    for indicador, (cmin, cmax, _) in _DE_PARA.items():
        assert (conferencia[cmin] < conferencia[cmax]).all(), indicador


def test_a_transcricao_confirma_o_paf_bandas_linha_a_linha(conferencia, bom):
    # O cruzamento que motivou versionar este arquivo: 119 comparacoes entre duas
    # origens independentes -- a planilha oficial do PAF, digitada em paf_bandas.csv
    # ao longo do projeto, e a tabela que a dona do projeto mantem a parte.
    #
    # Em 19/08/2026 as 119 bateram. Se um dia divergirem, e porque uma das duas
    # mudou: o teste diz qual ano, qual indicador e os dois valores.
    chave = bom.set_index(["ano", "versao", "indicador"])
    comparadas = 0
    for _, r in conferencia.iterrows():
        for indicador, (cmin, cmax, fator) in _DE_PARA.items():
            k = (int(r["ano"]), r["versao"], indicador)
            assert k in chave.index, f"paf_bandas.csv nao tem {k}"
            n = chave.loc[k]
            esperado = (r[cmin] * fator, r[cmax] * fator)
            assert abs(n["minimo"] - esperado[0]) < 0.001, (
                f"{k}: paf_bandas {n['minimo']} x transcricao {esperado[0]}")
            assert abs(n["maximo"] - esperado[1]) < 0.001, (
                f"{k}: paf_bandas {n['maximo']} x transcricao {esperado[1]}")
            comparadas += 1
    assert comparadas == 119
