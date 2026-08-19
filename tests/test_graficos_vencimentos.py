import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pytest

from tesouro.graficos import estilo, vencimentos


# ---------------------------------------------------------------------------
# Aba 3.4: o cronograma
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def anual():
    return vencimentos.dados_cronograma_anual()


def test_o_cronograma_anual_bate_com_o_medido(anual):
    por_ano = anual.sum(axis=1) / 1000
    assert round(por_ano[2026], 1) == 833.5
    assert round(por_ano[2027], 1) == 1771.9
    assert round(por_ano[2028], 1) == 1133.2
    assert round(por_ano[2029], 1) == 1315.6
    assert round(por_ano[2030], 1) == 1223.2
    assert round(por_ano[2031], 1) == 636.5


def test_o_balde_entra_no_cronograma_e_o_total_fecha(anual):
    # Sem o balde da Task 2 o grafico mostraria 78% do estoque como se fosse tudo.
    por_ano = anual.sum(axis=1) / 1000
    assert round(por_ano["Ap\u00f3s 5 anos"], 1) == 2006.9
    assert round(por_ano.sum(), 1) == 8920.7


def test_os_dois_anos_das_pontas_sao_parciais(anual):
    # A aba 3.4 detalha jul/26 a jun/31: 2026 e jul-dez e 2031 e jan-jun. Comparar
    # 833,5 com 1.771,9 sem saber disso e ler o grafico errado.
    assert vencimentos.ANOS_PARCIAIS == (2026, 2031)
    mensal = vencimentos.dados_cronograma_mensal()
    meses = mensal.index.to_series().dt.year.value_counts()
    assert meses[2026] == 6
    assert meses[2031] == 6
    assert meses[2027] == 12


def test_o_cronograma_mensal_tem_os_sessenta_meses():
    m = vencimentos.dados_cronograma_mensal()
    total = m.sum(axis=1) / 1000
    assert len(m) == 60
    assert m.index.min() == pd.Timestamp("2026-07-31")
    assert m.index.max() == pd.Timestamp("2031-06-30")
    assert round(total.max(), 1) == 562.8
    assert total.idxmax() == pd.Timestamp("2027-03-31")
    assert round(total[pd.Timestamp("2026-07-31")], 1) == 256.0
    # O balde NAO entra no detalhe mensal: ele nao tem mes.
    assert round(total.sum(), 1) == 6913.8


# ---------------------------------------------------------------------------
# Aba 3.1: as faixas da DPF, com a banda
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def faixas():
    return vencimentos.dados_faixas()


def test_as_faixas_da_dpf_batem_com_o_medido(faixas):
    u = faixas.iloc[-1]
    assert round(u["At\u00e9 12 meses"], 1) == 20.1
    assert round(u["De 1 a 2 anos"], 1) == 14.1
    assert round(u["De 2 a 5 anos"], 1) == 42.2
    assert round(u["Acima de 5 anos"], 1) == 23.6


def test_cada_mes_das_faixas_soma_100(faixas):
    assert len(faixas.columns) == 4
    assert (faixas.sum(axis=1) - 100).abs().max() < 1e-9
    # O bloco DPF da aba 3.1 tem 246 meses, mas os dez primeiros (jan a out/2006)
    # vem ZERADOS -- a serie so comeca de fato em nov/2006, a mesma data em que a
    # do prazo medio comeca. Mantidos, eles viram dez meses somando zero por cento,
    # e a area empilhada abre com um buraco que parece dado faltando.
    assert faixas.index.min() == pd.Timestamp("2006-11-30")
    assert len(faixas) == 236


def test_a_banda_de_vincendo_em_12_meses_para_em_2022():
    # Nao e o parser parando cedo: a aba 5.7 do anexo de jun/26 tem quatro blocos e
    # o ultimo termina em "PAF 2022". E o paf_bandas.csv, que vai ate 2026, guarda
    # seis indicadores e vincendo nao e um deles.
    b = vencimentos.banda_vincendo_12m()
    assert b.index.min() == 2003
    assert b.index.max() == 2022
    assert b.loc[2022, "minimo"] == 19.0
    assert b.loc[2022, "maximo"] == 23.0


def test_o_realizado_do_vincendo_bate_com_o_nosso_dado(faixas):
    # Cruzamento contra fonte independente: a faixa sai da aba 3.1 pelo nosso
    # parser e o realizado sai da 5.7, que e outra aba e outro parser. A tolerancia
    # de 0,05 e o arredondamento com que o proprio RMD imprime o realizado.
    #
    # Este realizado E lido, diferente do de referencia/paf_bandas.csv: ele vem de
    # uma aba do RMD, por parser, e nao de tabela digitada a mao. O cruzamento
    # confere dois parsers nossos um contra o outro, que e o que pega defeito.
    b = vencimentos.banda_vincendo_12m()
    for ano in range(2011, 2023):
        nosso = faixas.loc[pd.Timestamp(f"{ano}-12-31"), "At\u00e9 12 meses"]
        assert abs(nosso - b.loc[ano, "realizado"]) < 0.05, f"vincendo em {ano}"


# ---------------------------------------------------------------------------
# Desenho
# ---------------------------------------------------------------------------

def test_o_desenho_marca_os_dois_anos_parciais():
    estilo.aplicar_estilo()
    fig = plt.figure(figsize=(13, 9))
    vencimentos.desenha_cronograma(vencimentos.dados_cronograma_anual(),
                                   vencimentos.dados_cronograma_mensal(), fig)
    rotulos = [t.get_text() for ax in fig.axes for t in ax.get_xticklabels()]
    plt.close(fig)
    assert "2026*" in rotulos and "2031*" in rotulos
    assert "2027" in rotulos and "2027*" not in rotulos


def test_o_desenho_do_mensal_divide_a_virada_do_ano():
    estilo.aplicar_estilo()
    fig = plt.figure(figsize=(13, 9))
    vencimentos.desenha_cronograma(vencimentos.dados_cronograma_anual(),
                                   vencimentos.dados_cronograma_mensal(), fig)
    # Quatro viradas de ano dentro dos 60 meses: 26/27, 27/28, 28/29, 29/30, 30/31.
    divisorias = [l for ax in fig.axes for l in ax.lines
                  if l.get_linestyle() == "--"]
    plt.close(fig)
    assert len(divisorias) == 5


def test_a_banda_nao_e_desenhada_onde_nao_existe():
    # Depois de 2022 nao ha banda. Um retangulo esticado ate 2026 inventaria meta.
    estilo.aplicar_estilo()
    fig = plt.figure(figsize=(13, 8))
    vencimentos.desenha_faixas(vencimentos.dados_faixas(),
                               vencimentos.banda_vincendo_12m(), fig)
    # So o painel de baixo: o stackplot do de cima tambem cria colecoes, uma por
    # faixa, e contar as duas coisas juntas mede outra coisa.
    faixas_desenhadas = list(fig.axes[1].collections)
    de_cima = list(fig.axes[0].collections)
    plt.close(fig)
    assert len(de_cima) == 4, "as quatro faixas da area empilhada"
    # Uma banda por ano, de 2006 (inicio da nossa serie) a 2022 (fim da banda).
    assert len(faixas_desenhadas) == 17
