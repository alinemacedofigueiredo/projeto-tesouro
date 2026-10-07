import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pytest

from tesouro.graficos import estilo, reserva


@pytest.fixture(scope="module")
def dados():
    return reserva.dados_reserva()


def test_a_reserva_do_ULTIMO_MES_bate_com_o_anexo(dados):
    # ABA 6.1 do anexo, em R$ bilhoes. Remedido contra o de AGOSTO.
    #
    # O PRUDENCIAL CAIU MUITO -- 611 para 336. Nao e erro de leitura: a celula
    # diz 336,3537, e o valor prudencial sao TRES MESES de vencimento, que se
    # move com o cronograma. Movimento grande ali e esperado.
    u = dados.iloc[-1]
    assert round(u["reserva"] / 1000) == 1208
    assert round(u["prudencial"] / 1000) == 336
    assert round(u["indice"], 2) == 7.18


def test_a_folga_e_a_reserva_menos_o_prudencial(dados):
    # SO A RELACAO. O valor do ultimo mes vivia cravado aqui ao lado (760,2 em
    # julho, 871,8 em agosto) e envelhecia a cada RMD sem proteger nada a mais:
    # reserva e prudencial ja sao ancorados contra o anexo no teste acima, e
    # esta relacao amarra a folga aos dois. Tirado em 07/10/2026.
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
    # TREZE e o invariante; as DATAS andam com o RMD e por isso saem do proprio
    # dado -- treze meses corridos terminando na base.
    assert len(t) == 13
    assert list(t.index) == list(pd.date_range(end=t.index.max(), periods=13,
                                               freq="ME")), (
        "os treze meses nao sao corridos")
    # A DATA SAI DO DADO, como o comentario acima ja prometia -- havia um
    # Timestamp("2026-07-31") cravado aqui, contradizendo a propria promessa.
    # A janela de treze meses termina na base da serie completa.
    assert t.index.max() == reserva.dados_reserva().index.max()
    assert round(t["indice"].min(), 2) == 5.69
    assert round(t["indice"].max(), 2) == 9.33


def test_a_janela_de_cinco_anos_bate_com_o_medido():
    c = reserva.dados_reserva(janela=5)
    assert len(c) == 61
    assert round(c["indice"].min(), 2) == 5.69
    assert round(c["indice"].max(), 2) == 10.59
    assert round(c["reserva"].min() / 1000, 1) == 743.9
    # A DUVIDA DE SETEMBRO SE RESOLVEU. O maximo era 1.371,2 em 31/07/2026, no
    # proprio mes da base, e ficou a observacao de que "maximo na ponta e o caso
    # em que o grafico pode estar cortando dado, e nao mostrando pico".
    #
    # Agosto respondeu: a reserva caiu para 1.208,1 e o maximo voltou para o
    # INTERIOR da janela, em julho. Era pico de verdade.
    #
    # O maximo continua 1.371,2 -- a janela deslizou e julho continua dentro
    # dela.
    assert round(c["reserva"].max() / 1000, 1) == 1371.2
    assert c["reserva"].idxmax() < c.index.max(), (
        "o maximo voltou para a ponta; vale reparar se e pico ou corte")


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
