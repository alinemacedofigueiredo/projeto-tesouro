from datetime import date

import pytest
from tesouro import calendario, precificacao


@pytest.fixture(scope="module")
def cal():
    return calendario.padrao()


def test_ltn_com_252_dias_uteis_a_10_por_cento(cal):
    # Ancora aritmetica exata: 1000 / 1,10 = 909,090909...
    d0 = date(2026, 6, 30)
    venc = cal.mover(d0, 252)
    assert precificacao.pu_ltn(cal, d0, venc, 0.10) == pytest.approx(909.090909, abs=1e-6)


def test_ltn_no_vencimento_vale_zero(cal):
    d0 = date(2026, 7, 1)
    assert precificacao.pu_ltn(cal, d0, date(2026, 7, 1), 0.13) == 0.0


def test_ntnb_multiplica_a_cotacao_pelo_vna(cal):
    # Dobrar o VNA dobra o PU: a cotacao nao depende dele.
    d0, venc = date(2026, 6, 30), date(2035, 5, 15)
    a = precificacao.pu_ntnb(cal, d0, venc, 0.07, 4000.0)
    b = precificacao.pu_ntnb(cal, d0, venc, 0.07, 8000.0)
    assert b == pytest.approx(2 * a, rel=1e-4)


def test_ntnb_pu_bate_com_valor_recalculado_por_fora(cal):
    # Ancora o PU inteiro, nao so a proporcionalidade com o VNA. Sem isso,
    # remover a corrente de cupons inteira, ou usar a constante de cupom
    # errada (3,00 em vez de 2,9563), ou truncar a cotacao em 6 casas em
    # vez de 4, ainda deixam a suite verde -- foram tres mutacoes que
    # sobreviveram na revisao. Valor recalculado por fora, de forma
    # independente: cotacao truncada 94,6496 sobre 18 fluxos de cupom.
    pu = precificacao.pu_ntnb(cal, date(2026, 6, 30), date(2035, 5, 15), 0.07, 4739.66)
    assert pu == pytest.approx(4486.069231, abs=1e-6)


def test_lft_perto_do_par_vale_perto_do_vna(cal):
    # Com agio quase nulo, o PU da LFT e praticamente o VNA.
    pu = precificacao.pu_lft(cal, date(2026, 6, 30), date(2030, 6, 1), 0.0001, 19323.94)
    assert pu == pytest.approx(19323.94, rel=2e-3)


def test_ntnf_soma_cupons_semestrais(cal):
    # Taxa igual ao cupom (10% a.a.) deixa o papel proximo do par -- mas
    # so quando a data de posicao nao esta colada num pagamento de cupom.
    # O PU e o preco "sujo" (soma de fluxos futuros, sem descontar juros
    # acumulados): a um dia util de um cupom de 2026-07-01, o PU embute
    # quase o cupom inteiro e passa longe do par por construcao, nao por
    # erro de formula. 2026-07-02 e o dia util seguinte ao cupom, entao
    # o juro acumulado e quase nulo e o PU fica perto do par de novo.
    # A tolerancia e 0,5%: nesta data o desvio real da formula correta e
    # 0,27%, entao ela passa com folga; com 2% (tolerancia antiga) um
    # cupom de 50,00 em vez de 48,8088 (+1,40%) passaria despercebido.
    pu = precificacao.pu_ntnf(cal, date(2026, 7, 2), date(2033, 1, 1), 0.10)
    assert pu == pytest.approx(1000, rel=0.005)


def test_ntnf_nao_paga_cupom_de_novo_na_data_do_pagamento(cal):
    # Quem carrega o titulo no dia exato do pagamento de um cupom ja o
    # recebeu; o loop de pu_ntnf usa `cupom > d0` (estrito) de proposito,
    # para nao contar esse fluxo de novo na mesma data. Inalcancavel em
    # producao -- datas de posicao sao sempre ultimo dia util do mes, e
    # cupom cai no dia 1 ou no dia 15 -- mas e uma linha facil de mudar
    # sem que a suite reclame, entao trava o comportamento aqui.
    #
    # Prova indireta: se o cupom da propria data fosse incluido (mutacao
    # `>=`), o PU nessa data saltaria quase o valor cheio do cupom acima
    # do PU um dia util depois, em vez de derivar suavemente por efeito
    # de desconto de um dia.
    venc = date(2033, 1, 1)
    d0 = date(2028, 1, 3)  # cai exatamente numa data de cupom desta serie
    d1 = cal.mover(d0, 1)
    pu_no_cupom = precificacao.pu_ntnf(cal, d0, venc, 0.10)
    pu_dia_seguinte = precificacao.pu_ntnf(cal, d1, venc, 0.10)
    assert abs(pu_dia_seguinte - pu_no_cupom) < 5.0


def test_dv_e_negativo_para_titulo(cal):
    # Convencao: PU(taxa+1bp) - PU(taxa). Alta de taxa faz o mercado perder.
    d0 = date(2026, 6, 30)
    for titulo, venc, taxa, vna in [
        ("LTN", date(2029, 1, 1), 0.13, None),
        ("NTN-F", date(2033, 1, 1), 0.13, None),
        ("NTN-B", date(2035, 5, 15), 0.07, 4739.66),
    ]:
        assert precificacao.dv(cal, titulo, d0, venc, taxa, vna) < 0


def test_dv_cresce_com_o_prazo(cal):
    d0 = date(2026, 6, 30)
    curto = precificacao.dv(cal, "LTN", d0, date(2027, 7, 1), 0.13)
    longo = precificacao.dv(cal, "LTN", d0, date(2031, 7, 1), 0.13)
    assert abs(longo) > abs(curto)


def test_dv_da_lft_e_none_e_nao_zero(cal):
    # Decisao de modelagem: a LFT nao entra no DV01. None e nao zero,
    # porque "nao se aplica" e diferente de "risco nulo medido".
    d = precificacao.dv(cal, "LFT", date(2026, 6, 30), date(2030, 6, 1), 0.0006, 19323.94)
    assert d is None


def test_dv_da_ltn_bate_com_o_fechado_analitico(cal):
    # Ancora o tamanho do choque de 1 bp. Sem isso, um _UM_BP errado (por
    # exemplo 0,0010 em vez de 0,0001) ainda passa nos testes de sinal,
    # monotonia no prazo e multiplo de 1e-6, porque os tres sao
    # invariantes a escala do choque -- todo DV01 do projeto sairia 10x
    # com a suite verde. O fechado analitico -PU*n/(1+i)*1e-4, com
    # n = du/252, da -0,0826446; a diferenca de ~7e-6 e o degrau da
    # truncagem, esperado.
    d0 = date(2026, 6, 30)
    venc = cal.mover(d0, 252)
    d = precificacao.dv(cal, "LTN", d0, venc, 0.10)
    assert d == pytest.approx(-0.082638, abs=1e-6)


def test_dv_usa_precos_truncados(cal):
    # A truncagem faz parte do DV de proposito: o preco truncado e o
    # negociavel. Logo o DV e sempre um multiplo de 1e-6.
    d = precificacao.dv(cal, "LTN", date(2026, 6, 30), date(2029, 1, 1), 0.13)
    assert abs(round(d * 1e6) - d * 1e6) < 1e-6


def test_titulo_desconhecido_falha_alto(cal):
    with pytest.raises(ValueError, match="NTN-Z"):
        precificacao.pu(cal, "NTN-Z", date(2026, 6, 30), date(2030, 1, 1), 0.1)


def test_ntnb_precisa_de_vna(cal):
    with pytest.raises(ValueError, match="VNA"):
        precificacao.pu(cal, "NTN-B", date(2026, 6, 30), date(2035, 5, 15), 0.07)
