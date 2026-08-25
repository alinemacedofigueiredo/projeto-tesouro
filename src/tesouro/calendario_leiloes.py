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


def dias_possiveis(de, ate):
    """Os dias de leilao pelas regras de SEMANA e FERIADO, sem a de dezembro.

    SEPARADO DE dias_estimados DE PROPOSITO. A regra do fim do ano -- nada depois
    de _ULTIMO_DIA_DE_DEZEMBRO -- e a suposicao mais forte que este modulo faz, e
    ate 25/08/2026 ela vivia como um `continue` no meio do laco: aplicada, e
    invisivel. Quem olhasse a pagina via os dias que contamos, nunca os que
    DESCARTAMOS.

    Ela pediu o contrario: "em um cenario hipotetico que ele va emitir na ultima
    semana do ano, consigo ver rapido que nao estamos considerando esse cenario".
    Uma ausencia so e visivel se for dado, e nao filtro -- entao a diferenca entre
    esta funcao e dias_estimados E a suposicao, e a pagina mostra as duas.
    """
    cal = calendario.padrao()
    de, ate = pd.Timestamp(de).normalize(), pd.Timestamp(ate).normalize()
    dias = set()
    for d in pd.date_range(de, ate, freq="D"):
        if d.dayofweek not in _DIAS_DA_SEMANA:
            continue
        dia = _anterior_util(cal, d)
        if dia < de:
            # A antecipacao por feriado pode jogar o dia para antes do inicio
            # pedido; esse leilao pertence a janela anterior, entao fica de
            # fora daqui em vez de ser reatribuido.
            continue
        dias.add(dia)
    return sorted(dias)


def fora_pela_regra_do_fim_do_ano(dia):
    """Este dia de leilao cai depois do ultimo dia util de emissao de dezembro?"""
    dia = pd.Timestamp(dia)
    return dia.month == 12 and dia.day > _ULTIMO_DIA_DE_DEZEMBRO


def dias_estimados(de, ate):
    """Os dias de leilao entre 'de' e 'ate', pelas regras do cabecalho.

    Devolve datas normalizadas e sem repeticao, em ordem. Terca e quinta caem no
    mesmo conjunto porque o que interessa a projecao e o DIA DE LEILAO, e nao qual
    papel foi ofertado nele -- o pace ja e medido por papel.

    E os possiveis MENOS o fim do ano. Ver dias_possiveis para por que as duas
    coisas sao funcoes separadas.
    """
    return [d for d in dias_possiveis(de, ate)
            if not fora_pela_regra_do_fim_do_ano(d)]


def dias_ate(ate, registros=None, hoje=None):
    """Os dias de leilao ate 'ate', e a data em que o calendario publicado acaba.

    O PUBLICADO TEM PRECEDENCIA. Onde o Tesouro ja disse o que vai fazer, e
    transcricao; alem disso e inferencia nossa. Devolver a fronteira junto nao e
    detalhe: sem ela a pagina apresentaria palpite com a mesma cara de fato.

    'registros' e a resposta ja baixada da API. Os testes passam a amostra
    congelada, e por isso nao tocam a rede.
    """
    from . import api_leiloes, parse_api_leiloes

    ate = pd.Timestamp(ate).normalize()
    hoje = pd.Timestamp(hoje).normalize() if hoje is not None \
        else pd.Timestamp.today().normalize()

    if registros is None:
        registros, _ = api_leiloes.buscar("calendario")

    publicados = []
    fronteira = None
    if len(registros):
        agenda = parse_api_leiloes.calendario(registros)
        datas = sorted(set(agenda["data_leilao"].dt.normalize()))
        publicados = [d for d in datas if hoje <= d <= ate]
        if publicados:
            fronteira = max(publicados)

    # O estimado so comeca DEPOIS da fronteira -- nunca nela. dias_estimados ja
    # descarta por conta propria qualquer dia que a antecipacao por feriado jogue
    # para antes do inicio pedido (ver o teste de virada de janela em
    # dias_estimados), entao a fronteira nao pode reaparecer aqui nem por
    # coincidencia de data.
    inicio = fronteira + pd.Timedelta(days=1) if fronteira is not None else hoje
    estimados = [d for d in dias_estimados(inicio, ate) if d not in set(publicados)]
    return sorted(set(publicados) | set(estimados)), fronteira
