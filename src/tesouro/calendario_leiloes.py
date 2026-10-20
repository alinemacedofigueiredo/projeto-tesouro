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


def cobertura_por_papel(registros):
    """Ate quando o calendario publica cada papel: {titulo: data}.

    POR PAPEL, e nao por data. O calendario do Tesouro fica completo papel a
    papel -- em 23/09/2026 o prefixado ia ate 17/12 e a terca de LFT/NTN-B so
    ate 29/09 -- e uma cobertura global esconde isso. Ver dias_ate.
    """
    from . import parse_api_leiloes

    if not registros:
        return {}
    agenda = parse_api_leiloes.calendario(registros)
    dias = agenda["data_leilao"].dt.normalize()
    return {titulo: dias[agenda["titulo"] == titulo].max()
            for titulo in sorted(set(agenda["titulo"]))}


def mudou_a_cobertura(antes, depois):
    """O que mudou de um calendario para o outro, em linhas para a tela.

    Devolve lista vazia quando nada mudou -- e a rodada normal nao diz nada.

    PEDIDO DELA em 20/10/2026: "quando ter uma rotina para quando sai um
    calendario novo?". Ate aqui o projeto baixava, salvava e ficava calado, e a
    publicacao de um comunicado novo e o evento mais importante para a
    projecao: dezenas de dias passam de estimado para publicado de uma vez.

    O CASO QUE ENCURTA TAMBEM SAI. "O mais recente vence" e a regra certa, mas
    um calendario novo que cobre MENOS que o guardado piora a projecao, e isso
    nao pode passar em silencio.
    """
    de = cobertura_por_papel(antes)
    para = cobertura_por_papel(depois)
    linhas = []
    for titulo in sorted(set(de) | set(para)):
        velho, novo = de.get(titulo), para.get(titulo)
        if novo is None:
            linhas.append("%s: saiu do calendario (ia ate %s)"
                          % (titulo, velho.strftime("%d/%m/%Y")))
        elif velho is None:
            linhas.append("%s: entrou no calendario, ate %s"
                          % (titulo, novo.strftime("%d/%m/%Y")))
        elif novo > velho:
            linhas.append("%s: esticou de %s para %s"
                          % (titulo, velho.strftime("%d/%m/%Y"),
                             novo.strftime("%d/%m/%Y")))
        elif novo < velho:
            linhas.append("%s: ENCURTOU de %s para %s -- a projecao vai "
                          "depender mais do estimador"
                          % (titulo, velho.strftime("%d/%m/%Y"),
                             novo.strftime("%d/%m/%Y")))
    return linhas


def dias_possiveis(de, ate, dias_da_semana=_DIAS_DA_SEMANA):
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
        if d.dayofweek not in dias_da_semana:
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


def dias_estimados(de, ate, dias_da_semana=_DIAS_DA_SEMANA):
    """Os dias de leilao entre 'de' e 'ate', pelas regras do cabecalho.

    Devolve datas normalizadas e sem repeticao, em ordem. Terca e quinta caem no
    mesmo conjunto porque o que interessa a projecao e o DIA DE LEILAO, e nao qual
    papel foi ofertado nele -- o pace ja e medido por papel.

    E os possiveis MENOS o fim do ano. Ver dias_possiveis para por que as duas
    coisas sao funcoes separadas.
    """
    return [d for d in dias_possiveis(de, ate, dias_da_semana)
            if not fora_pela_regra_do_fim_do_ano(d)]


def dias_ate(ate, registros=None, hoje=None):
    """Os dias de leilao ate 'ate', e a data em que o calendario publicado acaba.

    O PUBLICADO TEM PRECEDENCIA. Onde o Tesouro ja disse o que vai fazer, e
    transcricao; alem disso e inferencia nossa. Devolver a fronteira junto nao e
    detalhe: sem ela a pagina apresentaria palpite com a mesma cara de fato.

    'registros' e a resposta ja baixada da API. Os testes passam a amostra
    congelada, e por isso nao tocam a rede.
    """
    from . import api_leiloes, parse_api_leiloes, rolagem

    ate = pd.Timestamp(ate).normalize()
    hoje = pd.Timestamp(hoje).normalize() if hoje is not None \
        else pd.Timestamp.today().normalize()

    if registros is None:
        # DISCO PRIMEIRO -- ver api_leiloes.calendario_publicado. O comunicado
        # do Tesouro e trimestral; buscar na rede a cada gravacao de pagina
        # gastava rede e, com a API fora, impedia a pagina de sair.
        registros, _, _ = api_leiloes.calendario_publicado()

    publicados = []
    ultimo_do_dia = {}
    if len(registros):
        agenda = parse_api_leiloes.calendario(registros)
        agenda = agenda.assign(_data=agenda["data_leilao"].dt.normalize())
        na_janela = agenda[(agenda["_data"] >= hoje) & (agenda["_data"] <= ate)]
        publicados = sorted(set(na_janela["_data"]))
        for titulo, bloco in na_janela.groupby("titulo"):
            dia = rolagem.dia_do_titulo(titulo)
            if dia is None:
                # Papel que nao sabemos encaixar entra como dia publicado, mas
                # nao define fronteira de ninguem. Melhor nao afirmar do que
                # afirmar por analogia.
                continue
            ate_quando = bloco["_data"].max()
            # Dois papeis dividem a terca (NTN-B e LFT). O grupo so esta
            # publicado ate onde os DOIS estao: o menor dos dois.
            ultimo_do_dia[dia] = min(ultimo_do_dia.get(dia, ate_quando),
                                     ate_quando)

    # UMA FRONTEIRA POR PAPEL, e nao uma global. Medido em 23/09/2026 contra o
    # "Comunicado Cronograma 4T-2026": o Tesouro publicava o prefixado ate 17/12
    # e a terca de LFT/NTN-B so ate 29/09. Com a fronteira global em 17/12, o
    # estimador nunca rodava, e as 11 tercas de 06/10 a 15/12 sumiam da
    # projecao -- 279 bi no estoque de 31/12.
    #
    # O calendario do Tesouro fica completo POR PAPEL, e nao por data. Supor que
    # ele esta completo ate a ultima data publicada e o modo de falha batizado
    # deste projeto: plausivel, e errado justamente onde a pagina diz ter mais
    # confianca, porque ali esta rotulado PUBLICADO.
    #
    # O estimado de cada papel so comeca DEPOIS da fronteira dele -- nunca nela.
    # dias_estimados ja descarta por conta propria qualquer dia que a
    # antecipacao por feriado jogue para antes do inicio pedido (ver o teste de
    # virada de janela em dias_estimados), entao a fronteira nao pode reaparecer
    # aqui nem por coincidencia de data.
    estimados = set()
    for dia_da_semana in _DIAS_DA_SEMANA:
        ultimo = ultimo_do_dia.get(dia_da_semana)
        inicio = ultimo + pd.Timedelta(days=1) if ultimo is not None else hoje
        estimados |= set(dias_estimados(inicio, ate,
                                        dias_da_semana=(dia_da_semana,)))
    estimados -= set(publicados)

    # A FRONTEIRA DEVOLVIDA E O MENOR DOS PAPEIS: ate ali TUDO e transcricao.
    # Depois dali ALGUM papel ja e inferencia nossa, e a pagina tem de dizer
    # isso. Se algum papel nao tem nada publicado na janela, nao existe trecho
    # em que tudo seja transcricao -- e a fronteira e None.
    fronteira = (min(ultimo_do_dia.values())
                 if len(ultimo_do_dia) == len(_DIAS_DA_SEMANA) else None)
    return sorted(set(publicados) | estimados), fronteira
