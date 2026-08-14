import datetime
import math
import pandas as pd
import pytest
from tesouro import conversoes


def test_mes_para_data_converte_abreviacao_portuguesa():
    assert conversoes.mes_para_data("Jan/10") == datetime.date(2010, 1, 31)
    assert conversoes.mes_para_data("Dez/06") == datetime.date(2006, 12, 31)
    assert conversoes.mes_para_data("Fev/24") == datetime.date(2024, 2, 29)


def test_mes_para_data_resolve_seculo_pelo_corte_de_90():
    assert conversoes.mes_para_data("Dez/99") == datetime.date(1999, 12, 31)
    assert conversoes.mes_para_data("Jan/00") == datetime.date(2000, 1, 31)


def test_mes_para_data_tolera_espacos_e_caixa():
    assert conversoes.mes_para_data("  nov/06 ") == datetime.date(2006, 11, 30)


def test_mes_para_data_rejeita_coluna_anual():
    # A aba 1.1 mistura totais anuais entre os meses; precisam ser descartados.
    assert conversoes.mes_para_data("2007") is None
    assert conversoes.mes_para_data("") is None
    assert conversoes.mes_para_data(None) is None


def test_normalizar_data_aceita_datetime_e_vai_para_fim_do_mes():
    entrada = datetime.datetime(2011, 2, 28, 0, 0)
    assert conversoes.normalizar_data(entrada) == datetime.date(2011, 2, 28)
    assert conversoes.normalizar_data(datetime.datetime(2007, 1, 1)) == datetime.date(2007, 1, 31)


def test_normalizar_data_devolve_none_para_nat_do_pandas():
    # pd.NaT e o sentinela do pandas para data ausente numa coluna
    # datetime64; e o caso real que motivou este teste (colunas vazias
    # numa aba do RMD chegam como NaT, nao como None).
    assert conversoes.normalizar_data(pd.NaT) is None


def test_normalizar_data_devolve_none_para_none():
    assert conversoes.normalizar_data(None) is None


def test_normalizar_data_devolve_none_para_valor_que_nao_e_data():
    assert conversoes.normalizar_data("nao e uma data") is None


def test_para_milhoes_converte_bilhoes_e_reais():
    assert conversoes.para_milhoes(1.5, "bilhoes") == pytest.approx(1500.0)
    assert conversoes.para_milhoes(2_000_000.0, "reais") == pytest.approx(2.0)
    assert conversoes.para_milhoes(42.0, "milhoes") == pytest.approx(42.0)


def test_para_milhoes_propaga_nulo():
    assert conversoes.para_milhoes(None, "bilhoes") is None


def test_para_milhoes_rejeita_unidade_desconhecida():
    with pytest.raises(ValueError):
        conversoes.para_milhoes(1.0, "trilhoes")


def test_fracao_para_percentual():
    assert conversoes.fracao_para_percentual(0.07828) == pytest.approx(7.828)
    assert conversoes.fracao_para_percentual(None) is None


def test_limpar_nulo_reconhece_marcadores_do_rmd():
    # A aba 3.1 usa "N/D"; a 3.9 usa "-". Ambos sao ausencia, nao zero.
    assert conversoes.limpar_nulo("N/D") is None
    assert conversoes.limpar_nulo("-") is None
    assert conversoes.limpar_nulo("") is None
    assert conversoes.limpar_nulo(None) is None
    assert conversoes.limpar_nulo(float("nan")) is None


def test_limpar_nulo_preserva_zero_e_negativo():
    # Zero e valor legitimo; custo negativo aparece na aba 4.1 (NTN-D em 2005).
    assert conversoes.limpar_nulo(0) == 0.0
    assert conversoes.limpar_nulo(-2.1014) == pytest.approx(-2.1014)
