import datetime
from datetime import date, timedelta

import pytest
from tesouro import calendario


@pytest.fixture(scope="module")
def cal():
    return calendario.padrao()


def _du_ingenuo(feriados, a, b):
    """Oraculo: a contagem dia a dia do codigo da mesa."""
    if b < a:
        a, b = b, a
    eh = lambda d: d.weekday() < 5 and d not in feriados
    return sum(1 for i in range((b - a).days + 1) if eh(a + timedelta(days=i))) - 1


def test_carrega_o_arquivo_oficial_da_anbima():
    f = calendario.carregar_feriados()
    assert len(f) > 1200
    assert date(2026, 12, 25) in f
    assert date(2026, 1, 1) in f


def test_31_de_dezembro_nao_e_feriado(cal):
    # O arquivo da Anbima nao lista o ultimo dia do ano, e nos nao
    # acrescentamos: e dia util para a contagem.
    assert cal.eh_dia_util(date(2026, 12, 31))
    assert cal.eh_dia_util(date(2025, 12, 31))


def test_quinta_feira_santa_e_dia_util(cal):
    # Dia util desde 2000, por resolucao do Banco Central.
    assert cal.eh_dia_util(date(2026, 4, 2))


def test_carnaval_e_sexta_santa_nao_sao(cal):
    assert not cal.eh_dia_util(date(2026, 2, 16))
    assert not cal.eh_dia_util(date(2026, 2, 17))
    assert not cal.eh_dia_util(date(2026, 4, 3))


def test_du_bate_com_a_contagem_ingenua(cal):
    # O indice pre-computado nao pode mudar nenhum numero.
    f = cal.feriados
    casos = [
        (date(2010, 1, 29), date(2026, 6, 30)),
        (date(2026, 6, 30), date(2026, 7, 1)),
        (date(2026, 6, 30), date(2035, 5, 15)),
        (date(2020, 12, 31), date(2021, 1, 4)),
        (date(2026, 2, 13), date(2026, 2, 18)),   # atravessa o carnaval
        (date(2026, 6, 30), date(2026, 6, 30)),   # mesma data
    ]
    for a, b in casos:
        assert cal.du(a, b) == _du_ingenuo(f, a, b), f"{a} -> {b}"


def test_du_de_252_dias_uteis(cal):
    d = date(2026, 6, 30)
    fim = cal.mover(d, 252)
    assert cal.du(d, fim) == 252


def test_mover_anda_dias_uteis_nos_dois_sentidos(cal):
    d = date(2026, 6, 30)          # terca
    assert cal.mover(d, 1) == date(2026, 7, 1)
    assert cal.mover(d, -1) == date(2026, 6, 29)
    # sexta + 1 du = segunda
    assert cal.mover(date(2026, 5, 29), 1) == date(2026, 6, 1)


def test_ajustar_vencimento_mapeia_feriado_para_o_dia_util_seguinte(cal):
    # 01/01 e feriado; o vencimento efetivo e o primeiro dia util depois.
    assert cal.ajustar_vencimento(date(2027, 1, 1)) == date(2027, 1, 4)
    # dia util ja ajustado devolve ele mesmo
    assert cal.ajustar_vencimento(date(2026, 7, 1)) == date(2026, 7, 1)


def test_ultimo_dia_util_do_mes(cal):
    assert cal.ultimo_dia_util_do_mes(date(2026, 5, 31)) == date(2026, 5, 29)
    assert cal.ultimo_dia_util_do_mes(date(2026, 5, 1)) == date(2026, 5, 29)
    assert cal.ultimo_dia_util_do_mes(date(2026, 6, 30)) == date(2026, 6, 30)
    # dezembro: 31/12 e dia util, entao e ele mesmo quando cai em dia de semana
    assert cal.ultimo_dia_util_do_mes(date(2026, 12, 15)) == date(2026, 12, 31)


def test_du_e_rapido(cal):
    # 20 mil chamadas tem de rodar em bem menos de um segundo.
    import time
    a, b = date(2010, 1, 29), date(2060, 8, 13)
    t0 = time.perf_counter()
    for _ in range(20000):
        cal.du(a, b)
    assert time.perf_counter() - t0 < 1.0


def test_data_anterior_ao_primeiro_ano_com_feriado_levanta_erro(cal):
    # O arquivo da Anbima nao lista feriado nenhum de 2000; a janela
    # indexada comeca no primeiro ano com feriado (2001), entao consultar
    # 2000 tem de falhar alto em vez de tratar todo dia de semana como
    # util por falta de dado.
    with pytest.raises(ValueError):
        cal.eh_dia_util(date(2000, 12, 25))


def test_mover_alem_do_fim_da_janela_levanta_erro(cal):
    with pytest.raises(ValueError):
        cal.mover(date(2099, 12, 28), 5)
