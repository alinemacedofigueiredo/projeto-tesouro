import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pytest

from tesouro.graficos import estilo, paf, prazo


@pytest.fixture(scope="module")
def dados():
    return prazo.dados_prazo()


def test_o_prazo_de_junho_de_2026_bate_com_o_medido(dados):
    u = dados.iloc[-1]
    assert round(u["DPF"], 2) == 4.01
    assert round(u["DPMFi"], 2) == 3.90
    assert round(u["DPFe"], 2) == 6.93


def test_as_tres_series_vem_das_linhas_agregadas(dados):
    # As linhas agregadas sao as que tem entidade e titulo vazios. Filtrar so por
    # nivel traz tambem as linhas por titulo, e a media sai errada em silencio.
    assert list(dados.columns) == ["DPF", "DPMFi", "DPFe"]
    assert dados.notna().all().all()
    assert len(dados) == 237
    assert dados.index.min() == pd.Timestamp("2005-12-31")
    # A serie NAO e mensal no comeco: de dez/2005 ela pula para nov/2006.
    assert dados.index[1] == pd.Timestamp("2006-11-30")


def test_a_dpf_fica_sempre_entre_a_dpmfi_e_a_dpfe(dados):
    # Verdade estrutural: a DPF e a media ponderada das duas. Se um mes sair do
    # sanduiche, o filtro pegou linha que nao devia.
    assert (dados["DPMFi"] <= dados["DPF"]).all()
    assert (dados["DPF"] <= dados["DPFe"]).all()


def test_a_banda_do_prazo_medio_bate_com_o_paf():
    b = paf.bandas("prazo_medio_anos")
    assert b.loc[2026, "minimo"] == 3.8
    assert b.loc[2026, "maximo"] == 4.2
    # A linha desenhada e a NOSSA serie; da planilha vem so a banda.
    assert "realizado" not in b.columns


def test_so_a_dpmfi_e_a_dpfe_levam_rotulo(dados):
    estilo.aplicar_estilo()
    fig, ax = plt.subplots(figsize=(13, 6))
    prazo.desenha_prazo(dados, paf.bandas("prazo_medio_anos"), ax)
    rotulados = [a.get_text() for a in ax.texts]
    plt.close(fig)
    assert prazo.COM_ROTULO == ("DPMFi", "DPFe")
    # Os dois valores de junho, e nada mais: 3,90 e 6,93.
    assert sorted(rotulados) == ["3,90", "6,93"]


def test_a_dpf_e_a_linha_de_contexto(dados):
    estilo.aplicar_estilo()
    fig, ax = plt.subplots(figsize=(13, 6))
    prazo.desenha_prazo(dados, paf.bandas("prazo_medio_anos"), ax)
    largura = {l.get_label(): l.get_linewidth() for l in ax.lines}
    plt.close(fig)
    assert largura["DPF"] < largura["DPMFi"]
    assert largura["DPF"] < largura["DPFe"]


def test_a_banda_e_desenhada_ano_a_ano(dados):
    estilo.aplicar_estilo()
    fig, ax = plt.subplots(figsize=(13, 6))
    prazo.desenha_prazo(dados, paf.bandas("prazo_medio_anos"), ax)
    faixas = list(ax.collections)
    plt.close(fig)
    # De 2005 (inicio da serie) a 2026: o paf_bandas.csv cobre 2003 a 2026 com os
    # seis indicadores em todos os anos, entao sao 22 faixas.
    assert len(faixas) == 22


def test_nenhuma_serie_fica_fora_do_eixo(dados):
    # Eixo truncado e a armadilha 7 da spec. Aqui ela apareceria como a DPFe
    # saindo pela borda de cima sem ninguem notar.
    estilo.aplicar_estilo()
    fig, ax = plt.subplots(figsize=(13, 6))
    prazo.desenha_prazo(dados, paf.bandas("prazo_medio_anos"), ax)
    baixo, alto = ax.get_ylim()
    plt.close(fig)
    assert baixo <= dados.min().min()
    assert alto >= dados.max().max()
