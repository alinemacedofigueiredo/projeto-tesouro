"""Quais dias tem leilao, e quantos faltam ate uma data.

AS REGRAS SAO DO TESOURO, e foram descritas pela dona do projeto e conferidas contra
o historico de 2021 em diante:

    prefixado (LTN e NTN-F)   quinta-feira    94% dos 288 dias
    NTN-B                     terca-feira     97% dos 280 dias
    LFT                       terca-feira     81% -- e 18% na quinta
    feriado no dia            antecipa um dia util  (71% dos casos fora do padrao)
    fim de ano                sem leilao depois da terceira semana de dezembro

O estimador construido com elas erra de 0 a 2 dias em ~32, de setembro a dezembro,
nos anos de 2021 a 2025 -- e acerta 32 de 32 DATAS EXATAS em 2024 e 2025, sem nenhum
falso positivo. Os dias que faltam sao leiloes extraordinarios.

2019 e 2020 erram mais (+8 e +4 dias) e nao entram na validacao: sao anteriores ao
padrao atual, e 2020 foi o ano da pandemia.

ISTO E ESTIMATIVA, e o calendario publicado pelo Tesouro tem precedencia onde
existir -- ver dias_ate, que junta os dois e diz onde um acaba.
"""

import pandas as pd

from . import calendario

# Terca e quinta, na numeracao do pandas (segunda = 0).
_DIAS_DA_SEMANA = (1, 3)

# Depois deste dia de dezembro nao ha mais leilao.
_ULTIMO_DIA_DE_DEZEMBRO = 21


def _anterior_util(cal, d):
    """O dia, ou o dia util anterior a ele se cair em feriado."""
    while not cal.eh_dia_util(d.date()):
        d -= pd.Timedelta(days=1)
    return d


def dias_estimados(de, ate):
    """Os dias de leilao entre 'de' e 'ate', pelas regras do cabecalho.

    Devolve datas normalizadas e sem repeticao, em ordem. Terca e quinta caem no
    mesmo conjunto porque o que interessa a projecao e o DIA DE LEILAO, e nao qual
    papel foi ofertado nele -- o pace ja e medido por papel.
    """
    cal = calendario.padrao()
    de, ate = pd.Timestamp(de).normalize(), pd.Timestamp(ate).normalize()
    dias = set()
    for d in pd.date_range(de, ate, freq="D"):
        if d.dayofweek not in _DIAS_DA_SEMANA:
            continue
        dia = _anterior_util(cal, d)
        if dia < de:
            continue
        if dia.month == 12 and dia.day > _ULTIMO_DIA_DE_DEZEMBRO:
            continue
        dias.add(dia)
    return sorted(dias)
