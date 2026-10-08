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
    # AGOSTO de 2026, e o net ficou AINDA MAIS negativo: -83,9, contra -61,9 de
    # julho. E o mes do vencimento da NTN-B 15/08/2026 (258,2 bi de principal),
    # que puxou o resgate para 295,4 contra emissao de 211,5.
    #
    # Nao e erro de sinal -- o teste abaixo (net = emissao - resgate em toda
    # linha) e quem garante que a leitura esta certa.
    u = net.iloc[-1]
    assert round(u["emissao"] / 1000, 1) == 211.5
    assert round(u["resgate"] / 1000, 1) == 295.4
    assert round(u["net"] / 1000, 1) == -83.9


def test_a_mm3_e_o_acumulado_batem_com_o_medido(net):
    # A media movel e de TRES meses, por decisao da usuaria em 19/08/2026: a de
    # doze alisava demais e escondia o giro trimestral. Naquele dia a de doze
    # dava 27,7 -- numero da EPOCA, guardado como registro da decisao.
    u = net.iloc[-1]
    # A MEDIA DE TRES MESES FICOU NEGATIVA: -0,8, contra +72,4 em julho. Dois
    # meses de net negativo seguidos bastaram para virar o sinal da media -- e
    # exatamente o giro que a de doze meses esconderia, que foi o motivo de ela
    # ter escolhido a de tres.
    assert round(u["mm3"] / 1000, 1) == -0.8
    assert "mm12" not in net.columns
    # O acumulado de doze meses caiu de 301,4 para 80,6.
    assert round(u["acum12"] / 1000, 1) == 80.6


def test_o_net_e_emissao_menos_resgate_em_toda_linha(net):
    assert len(net) > 200
    assert (net["net"] - (net["emissao"] - net["resgate"])).abs().max() < 1e-6


def test_so_o_dpmfi_entra(net):
    bruto = pd.read_csv(config.PROCESSED_DIR / "funding_por_canal.csv")
    assert set(bruto["esfera"]) > {"DPMFi"}, "o teste so vale se houver outra esfera"
    assert round(net.iloc[-1]["net"] / 1000, 1) == -83.9


def test_a_janela_de_5_anos_corta_mas_preserva_o_ultimo_mes():
    curto = funding.dados_net(janela=5)
    longo = funding.dados_net()
    assert len(curto) < len(longo)
    assert curto.index.max() == longo.index.max()
    assert curto.index.min() >= longo.index.max() - pd.DateOffset(years=5)


def test_a_emissao_por_indexador_do_ultimo_mes_bate():
    u = funding.dados_emissao_indexador().iloc[-1]
    # A emissao indexada TRIPLICOU, de 7,3 para 21,9: o Tesouro reemitiu parte
    # do que venceu em NTN-B. O prefixado tambem subiu, de 66,7 para 84,1.
    assert round(u["Taxa Flutuante"] / 1000, 1) == 105.5
    assert round(u["Prefixados"] / 1000, 1) == 84.1
    assert round(u["\u00cdndice de Pre\u00e7os"] / 1000, 1) == 21.9


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


def test_o_net_leva_rotulo_no_maior_no_menor_e_no_ultimo():
    # Sem numero escrito, a barra so diz "grande" ou "pequena" -- e a escala vai de
    # -302 a +181. Tres pontos sao rotulados em cada painel: o pior mes, o melhor e
    # onde estamos.
    estilo.aplicar_estilo()
    fig = plt.figure(figsize=(13, 8))
    funding.desenha_net(funding.dados_net(janela=5), fig)
    escritos = [a.get_text() for ax in fig.axes for a in ax.texts]
    plt.close(fig)

    # OS VALORES SAEM DO DADO, e nao cravados. Os seis viviam escritos aqui
    # ("155,9", "-302,3", ...) e envelheciam por DOIS motivos a cada RMD: o
    # ultimo mes muda, e a janela de cinco anos desliza, trocando os extremos.
    #
    # O assunto deste teste e a REGRA -- o pior mes, o melhor e onde estamos
    # levam rotulo -- e nao quanto cada um vale. Trocado em 07/10/2026.
    d = funding.dados_net(janela=5)
    n = d["net"] / 1000
    for valor, papel in ((n.max(), "o maior net da janela"),
                         (n.min(), "o menor"),
                         (n.iloc[-1], "o ultimo"),
                         (d["mm3"].iloc[-1] / 1000,
                          "o ultimo ponto da media movel")):
        assert estilo.num_br(valor, 1) in escritos, papel
    a = d["acum12"] / 1000
    assert estilo.num_br(a.max(), 1) in escritos, "o maximo do acumulado"
    assert estilo.num_br(a.min(), 1) in escritos, "o minimo do acumulado"


def test_o_net_tem_grade_menor_alem_da_maior():
    # Uma linha a cada 50 bi e outra fraca a cada 25. Com so a de 50, a barra de 143
    # e a de 156 sao a mesma coisa a olho.
    estilo.aplicar_estilo()
    fig = plt.figure(figsize=(13, 8))
    funding.desenha_net(funding.dados_net(janela=5), fig)
    a1 = fig.axes[0]
    maiores = list(a1.get_yticks())
    menores = list(a1.get_yticks(minor=True))
    plt.close(fig)

    assert round(maiores[1] - maiores[0], 1) == 50.0
    # O matplotlib nao repete uma posicao menor onde ja existe marca maior, entao
    # as menores sozinhas tambem andam de 50 em 50 -- deslocadas. O que prova a
    # grade fina e a UNIAO das duas, que anda de 25.
    todas = sorted(set(round(v, 6) for v in maiores + menores))
    passos = {round(b - a, 1) for a, b in zip(todas, todas[1:])}
    assert passos == {25.0}, passos
    assert len(menores) >= len(maiores) - 1


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
