import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pytest

from tesouro import config
from tesouro.graficos import estilo, funding


@pytest.fixture(scope="module")
def net():
    return funding.dados_net()


def test_o_net_do_ultimo_mes_bate_com_o_medido(net):
    u = net.iloc[-1]
    assert round(u["emissao"] / 1000, 1) == 149.5
    assert round(u["resgate"] / 1000, 1) == 6.1
    assert round(u["net"] / 1000, 1) == 143.4


def test_a_mm3_e_o_acumulado_batem_com_o_medido(net):
    # A media movel e de TRES meses, por decisao da usuaria em 19/08/2026: a de doze
    # alisava demais e escondia o giro trimestral. A de doze dava 27,7.
    u = net.iloc[-1]
    assert round(u["mm3"] / 1000, 1) == 115.7
    assert "mm12" not in net.columns
    assert round(u["acum12"] / 1000, 1) == 332.3


def test_o_net_e_emissao_menos_resgate_em_toda_linha(net):
    assert len(net) > 200
    assert (net["net"] - (net["emissao"] - net["resgate"])).abs().max() < 1e-6


def test_so_o_dpmfi_entra(net):
    bruto = pd.read_csv(config.PROCESSED_DIR / "funding_por_canal.csv")
    assert set(bruto["esfera"]) > {"DPMFi"}, "o teste so vale se houver outra esfera"
    assert round(net.iloc[-1]["net"] / 1000, 1) == 143.4


def test_a_janela_de_5_anos_corta_mas_preserva_o_ultimo_mes():
    curto = funding.dados_net(janela=5)
    longo = funding.dados_net()
    assert len(curto) < len(longo)
    assert curto.index.max() == longo.index.max()
    assert curto.index.min() >= longo.index.max() - pd.DateOffset(years=5)


def test_a_emissao_por_indexador_do_ultimo_mes_bate():
    u = funding.dados_emissao_indexador().iloc[-1]
    assert round(u["Taxa Flutuante"] / 1000, 1) == 102.6
    assert round(u["Prefixados"] / 1000, 1) == 35.5
    assert round(u["\u00cdndice de Pre\u00e7os"] / 1000, 1) == 11.4


def test_a_emissao_anual_em_100_bate_com_o_medido():
    d = funding.dados_emissao_anual()
    assert round(d.loc[2025, "Prefixados"], 1) == 40.3
    assert round(d.loc[2025, "Taxa Flutuante"], 1) == 41.0
    assert round(d.loc[2025, "\u00cdndice de Pre\u00e7os"], 1) == 18.6
    assert round(d.loc[2025, "total_milhoes"] / 1000) == 1841
    assert round(d.loc[2024, "Taxa Flutuante"], 1) == 64.9   # o ano da LFT


def test_cada_ano_da_emissao_anual_soma_100():
    d = funding.dados_emissao_anual()
    cols = [c for c in d.columns if c != "total_milhoes"]
    assert (d[cols].sum(axis=1) - 100).abs().max() < 0.01


def test_a_legenda_nomeia_as_duas_cores_da_barra():
    # A barra e UMA serie so, colorida pelo sinal. Verde e vermelho foram lidos como
    # emissao e resgate na primeira leitura -- por isso as duas cores tem nome na
    # legenda, em vez de uma entrada dizendo so "net do mes".
    estilo.aplicar_estilo()
    fig = plt.figure(figsize=(13, 8))
    funding.desenha_net(funding.dados_net(janela=5), fig)
    # Le a legenda DESENHADA, e nao os artistas registrados no eixo: as duas cores
    # entram como Patch construido a mao, que nao aparece em
    # get_legend_handles_labels(). Ler o que foi registrado em vez do que foi
    # desenhado deixaria o teste passar com a legenda vazia.
    rotulos = []
    for ax in fig.axes:
        legenda = ax.get_legend()
        if legenda is not None:
            rotulos += [texto.get_text() for texto in legenda.get_texts()]
    plt.close(fig)

    positivo = [r for r in rotulos if "positivo" in r]
    negativo = [r for r in rotulos if "negativo" in r]
    assert len(positivo) == 1 and len(negativo) == 1
    assert "emitiu mais" in positivo[0]
    assert "resgatou mais" in negativo[0]
    # E a media movel desenhada e a de 3 meses.
    assert any("3 meses" in r for r in rotulos)
    assert not any("12" in r and "m\u00e9dia" in r for r in rotulos)
