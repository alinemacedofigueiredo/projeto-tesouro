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


def test_a_banda_do_vincendo_cobre_de_2003_a_2026():
    # A aba 5.7 do anexo de jun/26 tem quatro blocos e o ultimo termina em
    # "PAF 2022"; o resto vem do arquivo de referencia.
    b = vencimentos.banda_vincendo_12m()
    assert b.index.min() == 2003
    assert b.index.max() == 2026


def test_o_realizado_do_vincendo_bate_com_o_nosso_dado(faixas):
    # Cruzamento contra fonte independente: a faixa sai da aba 3.1 pelo nosso
    # parser e o realizado sai da 5.7, que e outra aba e outro parser. A tolerancia
    # de 0,05 e o arredondamento com que o proprio RMD imprime o realizado.
    #
    # Este realizado E lido, diferente do de referencia/paf_bandas.csv: ele vem de
    # uma aba do RMD, por parser, e nao de tabela digitada a mao. O cruzamento
    # confere dois parsers nossos um contra o outro, que e o que pega defeito.
    # banda_da_57 e nao banda_vincendo_12m: o realizado so existe na aba 5.7. O
    # arquivo de referencia tem a coluna, mas ela nao e lida por decisao da dona do
    # projeto -- de la vem a banda, e so.
    b = vencimentos.banda_da_57()
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


def test_a_banda_do_vincendo_vem_das_duas_fontes():
    # 2022 so existe na aba 5.7; 2026 so existe no arquivo de referencia. As duas
    # tem de aparecer, ou uma das fontes nao esta sendo lida.
    b = vencimentos.banda_vincendo_12m()
    assert (b.loc[2022, "minimo"], b.loc[2022, "maximo"]) == (19.0, 23.0)
    assert (b.loc[2026, "minimo"], b.loc[2026, "maximo"]) == (18.0, 22.0)
    # A revisao de 2021 continua valendo sobre a original (24-29 vira 22-27).
    assert (b.loc[2021, "minimo"], b.loc[2021, "maximo"]) == (22.0, 27.0)


def test_o_vincendo_de_hoje_esta_dentro_da_banda_de_2026():
    # 20,07% contra a banda de 18 a 22. Nao e teste de politica: e o cruzamento que
    # pega banda digitada na escala errada, ou a faixa lida da coluna errada.
    faixas = vencimentos.dados_faixas()
    b = vencimentos.banda_vincendo_12m()
    hoje = faixas["At\u00e9 12 meses"].iloc[-1]
    assert round(hoje, 2) == 20.07
    assert b.loc[2026, "minimo"] <= hoje <= b.loc[2026, "maximo"]


def test_os_anos_sem_banda_do_vincendo_estao_declarados():
    # A 5.7 vai ate 2022 e o arquivo de referencia comeca em 2026: 2023, 2024 e 2025
    # nao tem banda de vincendo em fonte nenhuma. Sao os anos que faltam digitar da
    # planilha do PAF. Declarados aqui para que a lacuna seja visivel e para que o
    # teste avise quando ela for preenchida.
    b = vencimentos.banda_vincendo_12m()
    faltando = [a for a in range(2003, 2027) if a not in b.index]
    assert faltando == [2023, 2024, 2025]


def test_as_duas_fontes_concordam_onde_compartilham_o_ano():
    # HOJE NAO HA ANO COMPARTILHADO -- a 5.7 termina em 2022 e a referencia comeca
    # em 2026 -- e por isso o laco abaixo nao roda. A contagem esta afirmada de
    # proposito: no dia em que alguem digitar 2003-2022 na planilha de referencia,
    # este teste falha e obriga a olhar a comparacao, em vez de deixar um laco vazio
    # passando para sempre.
    from tesouro.graficos import paf

    da_57 = vencimentos.banda_da_57()
    da_referencia = paf.bandas("vincendo_12m_pct")
    compartilhados = sorted(set(da_57.index) & set(da_referencia.index))
    assert len(compartilhados) == 0, (
        "as duas fontes passaram a compartilhar ano(s): "
        f"{compartilhados}. Troque este assert pela comparacao abaixo."
    )
    for ano in compartilhados:
        assert da_57.loc[ano, "minimo"] == da_referencia.loc[ano, "minimo"]
        assert da_57.loc[ano, "maximo"] == da_referencia.loc[ano, "maximo"]


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
    # Uma banda por ano com banda: 2006 a 2022 (dezessete, da aba 5.7) mais 2026
    # (do arquivo de referencia). 2023 a 2025 nao tem banda em fonte nenhuma e
    # nada e desenhado ali -- o buraco no desenho e a lacuna, nao um defeito.
    assert len(faixas_desenhadas) == 18
