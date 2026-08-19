import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pytest

from tesouro import config
from tesouro.graficos import custo, estilo, leiloes, vencimentos


# ---------------------------------------------------------------------------
# Candidato 1: perfil completo de vencimentos, ate 2084
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def perfil():
    return vencimentos.dados_perfil_completo()


def test_o_perfil_completo_vai_ate_2084(perfil):
    assert perfil.index.min() == 2026
    assert perfil.index.max() == 2084
    # Anos ja vencidos entram no CSV com financeiro zero; sem filtrar, o eixo
    # comecaria em 2010 com quatorze anos vazios.
    assert len(perfil) == 34


def test_a_diferenca_de_166_bi_contra_o_cronograma_esta_travada(perfil):
    # Os dois graficos de vencimento coexistem por decisao. A diferenca e travada
    # com o valor de hoje para que mudar sem querer seja detectado; a causa fica
    # para investigacao posterior (ver a spec, secao 10).
    total_perfil = perfil.sum().sum() / 1000
    cronograma = vencimentos.dados_cronograma_anual().sum().sum() / 1000
    assert round(total_perfil, 1) == 8904.1
    assert round(cronograma, 1) == 8920.7
    assert round(cronograma - total_perfil, 1) == 16.6


def test_a_cauda_longa_e_toda_indexada_a_precos(perfil):
    # Depois de 2040 nao ha mais LFT, LTN nem NTN-F: so indice de precos. E o
    # motivo de a NTN-B1 ficar separada da NTN-B -- o ultimo ano da divida,
    # 2084, sao 6,5 bi de RendA+ e mais nada.
    tarde = perfil[perfil.index > 2040]
    for familia in ("LFT", "LTN", "NTN-F"):
        assert tarde[familia].sum() == 0
    assert round(perfil.loc[2084, "NTN-B1"] / 1000, 1) == 6.5
    assert round(perfil.loc[2084].sum() / 1000, 1) == 6.5


# ---------------------------------------------------------------------------
# Candidato 2: custo de emissao contra o do estoque
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def emissao():
    return custo.dados_custo_emissao()


def test_o_custo_de_emissao_bate_com_o_medido(emissao):
    u = emissao.iloc[-1]
    assert round(u["emissao"], 2) == 14.20
    assert round(u["estoque"], 2) == 13.19
    # O fato que o grafico existe para mostrar: emite-se mais caro do que se
    # carrega, entao a divida encarece sem que nada mude.
    assert u["emissao"] > u["estoque"]


def test_o_custo_de_emissao_comeca_em_dezembro_de_2010(emissao):
    assert emissao.index.min() == pd.Timestamp("2010-12-31")
    assert len(emissao) == 187


def test_o_custo_do_estoque_e_o_mesmo_nos_dois_graficos():
    # Coerencia entre graficos que dividem fonte: o custo da DPMFi aparece no
    # grafico principal e neste, e tem de dar o mesmo numero.
    principal = custo.dados_custo().iloc[-1]["DPMFi"]
    candidato = custo.dados_custo_emissao().iloc[-1]["estoque"]
    assert abs(principal - candidato) < 1e-9


# ---------------------------------------------------------------------------
# Candidato 3: emissao anual por papel, dos leiloes
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def anual():
    return leiloes.dados_emissao_anual_papel()


def test_a_emissao_anual_por_papel_bate_com_o_medido(anual):
    assert round(anual.loc[2025, "LFT"], 1) == 39.6
    assert round(anual.loc[2025, "LTN"], 1) == 33.1
    assert round(anual.loc[2025, "NTN-B"], 1) == 18.1
    assert round(anual.loc[2025, "NTN-F"], 1) == 9.2
    assert round(anual.loc[2024, "LFT"], 1) == 65.1     # o ano da LFT


def test_cada_ano_da_emissao_por_papel_soma_100(anual):
    cols = [c for c in anual.columns
            if c not in ("total_milhoes", "cobertura_pct")]
    assert (anual[cols].sum(axis=1) - 100).abs().max() < 0.01


def test_os_leiloes_sao_cortados_na_ultima_competencia_do_rmd(anual):
    # O leiloes.csv vai ate 13/08/2026 e o RMD para em jun/26. Sem cortar, a
    # cobertura de 2026 da 120% -- oito meses de leilao contra seis de RMD.
    bruto = pd.read_csv(config.PROCESSED_DIR / "leiloes.csv",
                        parse_dates=["data_leilao"])
    assert bruto["data_leilao"].max() > pd.Timestamp("2026-06-30"), \
        "o teste so vale se o CSV de leiloes for alem do RMD"
    assert round(anual.loc[2026, "total_milhoes"] / 1000, 1) == 842.6
    assert anual.loc[2026, "cobertura_pct"] < 100


def test_a_cobertura_dos_anos_fechados_fica_entre_90_e_98(anual):
    # A razao de este grafico ser candidato: a aba 1.2 cobre 100% da emissao e os
    # leiloes nao. Na janela de 12 anos a cobertura vai de 90,5% (2015) a 97,3%
    # (2020) -- a spec fala em "93% a 97%" porque mediu de 2017 em diante.
    fechados = anual[anual.index < 2026]["cobertura_pct"]
    assert round(fechados.min(), 1) == 90.5
    assert round(fechados.max(), 1) == 97.3
    assert round(fechados.loc[2024], 1) == 93.0
    # E nenhum papel entra no desenho sem cor -- nas DUAS janelas. A de 12 anos
    # nao tem NTN-D nem NTN-C; a completa alcanca 2000 e tem as duas, e foi assim
    # que a falta de cor da NTN-D apareceu, no dashboard e nao aqui.
    from tesouro.graficos import estilo
    for janela in (anual, leiloes.dados_emissao_anual_papel(anos=100)):
        for papel in janela.columns:
            if papel not in ("total_milhoes", "cobertura_pct"):
                assert papel in estilo.COR, f"sem cor para {papel}"


def test_a_nota_de_cobertura_aparece_no_desenho(anual):
    # A licao que custou seis rodadas na entrega 2: esta assercao precisa FALHAR
    # quando a linha que escreve a nota e apagada. Ver o Passo 6.
    estilo.aplicar_estilo()
    fig, ax = plt.subplots(figsize=(13, 6))
    leiloes.desenha_emissao_anual_papel(anual, ax, ano_parcial=2026)
    textos = " ".join(t.get_text() for t in ax.texts)
    plt.close(fig)
    assert "cobertura" in textos.lower()
    assert "93" in textos or "97" in textos
