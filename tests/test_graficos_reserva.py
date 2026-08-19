import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pytest

from tesouro.graficos import estilo, reserva


@pytest.fixture(scope="module")
def dados():
    return reserva.dados_reserva()


def test_a_reserva_de_junho_de_2026_bate_com_o_medido(dados):
    # Conferido contra a pagina do RMD que a dona do projeto forneceu.
    u = dados.iloc[-1]
    assert round(u["reserva"] / 1000) == 1346
    assert round(u["prudencial"] / 1000) == 783
    assert round(u["indice"], 2) == 8.33


def test_a_folga_e_a_reserva_menos_o_prudencial(dados):
    assert round(dados.iloc[-1]["folga"] / 1000, 1) == 563.0
    diferenca = dados["folga"] - (dados["reserva"] - dados["prudencial"])
    assert diferenca.abs().max() < 1e-6


def test_a_folga_e_negativa_nos_dois_primeiros_meses(dados):
    # Em jan e fev/2015 a reserva ficou ABAIXO do valor prudencial. E o unico
    # trecho da serie em que isso acontece, e e onde o desenho pode mentir.
    negativos = dados[dados["folga"] < 0]
    assert list(negativos.index) == [pd.Timestamp("2015-01-31"),
                                     pd.Timestamp("2015-02-28")]
    assert round(negativos.iloc[0]["folga"] / 1000, 1) == -133.5


def test_a_versao_de_treze_meses_tem_treze_meses():
    t = reserva.dados_treze_meses()
    assert len(t) == 13
    assert t.index.min() == pd.Timestamp("2025-06-30")
    assert t.index.max() == pd.Timestamp("2026-06-30")
    assert round(t["indice"].min(), 2) == 5.69
    assert round(t["indice"].max(), 2) == 9.33


def test_a_janela_de_cinco_anos_bate_com_o_medido():
    c = reserva.dados_reserva(janela=5)
    assert len(c) == 61
    assert round(c["indice"].min(), 2) == 5.69
    assert round(c["indice"].max(), 2) == 10.59
    assert round(c["reserva"].min() / 1000, 1) == 743.9
    assert round(c["reserva"].max() / 1000, 1) == 1345.8


def test_as_duas_versoes_dizem_o_mesmo_no_mes_comum(dados):
    # Coerencia entre graficos que dividem fonte: o mesmo mes tem de dar o mesmo
    # numero nos dois.
    t = reserva.dados_treze_meses()
    for coluna in ("reserva", "prudencial", "indice"):
        assert abs(t.iloc[-1][coluna] - dados.iloc[-1][coluna]) < 1e-9


def test_o_eixo_do_indice_comeca_em_zero(dados):
    # Armadilha 7 da spec: a versao descartada comecava o eixo do indice em 5,7 e
    # transformava 2,6 meses de variacao num despencar. Eixo duplo pode; eixo
    # truncado nao.
    estilo.aplicar_estilo()
    for desenha, entrada in ((reserva.desenha_treze_meses,
                              reserva.dados_treze_meses()),
                             (reserva.desenha_reserva,
                              reserva.dados_reserva(janela=5))):
        fig, ax = plt.subplots(figsize=(13, 6))
        desenha(entrada, ax)
        direito = [a for a in fig.axes if a is not ax]
        limites = [a.get_ylim() for a in [ax] + direito]
        plt.close(fig)
        for baixo, _ in limites:
            assert baixo == 0, f"{desenha.__name__} truncou um eixo em {baixo}"


def test_a_folga_negativa_nao_e_pintada_como_folga(dados):
    # Sem where= e interpolate=True, os dois meses de 2015 aparecem sombreados do
    # mesmo jeito que os 136 de folga positiva.
    estilo.aplicar_estilo()
    fig, ax = plt.subplots(figsize=(13, 6))
    reserva.desenha_reserva(dados, ax)
    areas = [c for c in ax.collections]
    plt.close(fig)
    # Duas areas: a folga positiva e o deficit. Uma so significa que o sinal se
    # perdeu no caminho.
    assert len(areas) == 2
