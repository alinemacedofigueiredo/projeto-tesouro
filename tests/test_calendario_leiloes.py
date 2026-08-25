"""O calendario de leiloes: o publicado, e o estimado alem dele."""
import pandas as pd

from tesouro import calendario_leiloes, parse_api_leiloes


def test_o_estimador_acerta_as_datas_de_2024_e_2025():
    # A VALIDACAO QUE SUSTENTA A PROJECAO. As regras vieram da dona do projeto e
    # foram conferidas contra o historico: prefixado na quinta (94% dos dias),
    # NTN-B na terca (97%), antecipando um dia util em feriado, e sem leilao depois
    # da terceira semana de dezembro.
    #
    # Medido: 32 de 32 datas acertadas em 2024 e em 2025, SEM NENHUM FALSO
    # POSITIVO. Os dias que faltam sao leiloes extraordinarios, que nao ha como
    # prever -- por isso o teste exige subconjunto, e nao igualdade.
    from tesouro import config

    l = pd.read_csv(config.PROCESSED_DIR / "leiloes.csv",
                    parse_dates=["data_leilao"])
    venda = l[l["tipo_leilao"].isin(["Venda", "Extra Venda"])]

    # 2021 EM DIANTE, como a spec 12 pede. O plano encolheu para 2024-2025 sem
    # dizer por que. O criterio tambem e o da spec -- "dentro de dois" -- e nao
    # "zero falso positivo": medido, o estimador erra UM dia para mais em 2021 e
    # em 2022, e acerta na mosca de 2023 em diante. Exigir zero em todos os anos
    # seria exigir do estimador mais do que a spec pediu, e mascarar que ele
    # melhorou com o tempo em vez de sempre ter sido exato.
    for ano in (2021, 2022, 2023, 2024, 2025):
        de = pd.Timestamp(f"{ano}-09-01")
        ate = pd.Timestamp(f"{ano}-12-31")
        estimado = set(calendario_leiloes.dias_estimados(de, ate))
        real = set(venda[(venda["data_leilao"] >= de)
                         & (venda["data_leilao"] <= ate)]
                   ["data_leilao"].dt.normalize())
        falsos = estimado - real
        assert len(falsos) <= 1, (
            f"{ano}: o estimador previu {len(falsos)} dias sem leilao: "
            f"{sorted(falsos)}")
        assert abs(len(estimado) - len(real)) <= 2, (
            f"{ano}: estimou {len(estimado)} contra {len(real)} reais")


def test_nao_ha_leilao_depois_da_terceira_semana_de_dezembro():
    # Medido: o ultimo leilao do ano caiu entre 15 e 21 de dezembro nos cinco anos.
    dias = calendario_leiloes.dias_estimados(pd.Timestamp("2026-12-01"),
                                             pd.Timestamp("2026-12-31"))
    assert dias
    assert max(dias).day <= 21


def test_o_leilao_antecipa_quando_o_dia_cai_em_feriado():
    # Natal de 2025 caiu numa quinta. O leilao de prefixado daquela semana nao
    # existiu, mas a regra de antecipacao vale para os feriados do meio do ano.
    # 21/04/2026 (Tiradentes) cai numa terca: o leilao daquela semana antecipa.
    from tesouro import calendario

    cal = calendario.padrao()
    assert not cal.eh_dia_util(pd.Timestamp("2026-04-21").date())
    dias = calendario_leiloes.dias_estimados(pd.Timestamp("2026-04-19"),
                                             pd.Timestamp("2026-04-25"))
    assert pd.Timestamp("2026-04-21") not in dias
    assert pd.Timestamp("2026-04-20") in dias


def test_dia_antecipado_antes_do_inicio_da_janela_nao_reaparece():
    # Achado do revisor: quando 'de' cai exatamente no dia que a regra antecipa,
    # o dia antecipado (2026-04-20, segunda) fica ANTES de 'de' -- e pertence a
    # janela anterior, entao nao pode ser reatribuido para dentro desta. Medido:
    # dias_estimados(2026-04-21, 2026-04-25) devolve so [2026-04-23].
    dias = calendario_leiloes.dias_estimados(pd.Timestamp("2026-04-21"),
                                             pd.Timestamp("2026-04-25"))
    assert pd.Timestamp("2026-04-20") not in dias
    assert pd.Timestamp("2026-04-21") not in dias
    assert pd.Timestamp("2026-04-23") in dias


def test_virada_de_ano_nao_devolve_leilao_fantasma():
    # Achado do revisor: 01/01/2026 e quinta E feriado, entao a antecipacao por
    # feriado empurraria o leilao para 31/12/2025 -- que seria falso positivo,
    # pois leiloes.csv nao registra nenhum leilao entre 18/12/2025 e 06/01/2026.
    # Quem descarta esse fantasma e o corte de dezembro, nao a antecipacao: as
    # duas regras so parecem concordar aqui por coincidencia, e esse teste trava
    # o resultado para que a coincidencia nao se desfaca em silencio se uma delas
    # mudar.
    dias = calendario_leiloes.dias_estimados(pd.Timestamp("2025-12-20"),
                                             pd.Timestamp("2026-01-10"))
    assert pd.Timestamp("2025-12-31") not in dias


def test_o_calendario_PUBLICADO_tem_precedencia_sobre_o_estimado():
    # Onde o Tesouro ja disse o que vai fazer, e transcricao. So alem disso e
    # inferencia -- e a pagina precisa saber onde uma acaba, senao apresenta
    # palpite com a mesma cara de fato.
    import json
    import pathlib

    fixtures = pathlib.Path(__file__).parent / "fixtures" / "api_leiloes"
    registros = json.loads(
        (fixtures / "calendario.json").read_text(encoding="utf-8"))["registros"]

    # HOJE FIXO, como o test_agenda.py ja faz. A amostra congelada vai de 20/08 a
    # 29/09/2026: com a data real do relogio, este teste comeca a reprovar sozinho
    # em 30/09, quando 'publicados' fica vazio e a fronteira vira None. Data movel
    # em teste e teste que quebra num dia qualquer, sem ninguem ter mexido em nada.
    dias, ate_quando = calendario_leiloes.dias_ate(
        pd.Timestamp("2026-12-31"), registros=registros,
        hoje=pd.Timestamp("2026-08-24"))
    assert ate_quando is not None
    assert pd.Timestamp("2026-08-20") <= ate_quando <= pd.Timestamp("2026-10-31")
    # Achado do revisor (Minor): 'dias[:len(dias)]' era a lista inteira, nao o
    # subconjunto publicado -- o nome enganava, e a assercao seguinte nao media o
    # que o comentario prometia. Recalcula o publicado de verdade, a partir da
    # mesma amostra, para conferir que os dias do publicado entram como estao.
    agenda = parse_api_leiloes.calendario(registros)
    hoje = pd.Timestamp("2026-08-24")
    publicados = {d for d in agenda["data_leilao"].dt.normalize()
                  if hoje <= d <= pd.Timestamp("2026-12-31")}
    assert ate_quando in publicados
    assert publicados <= set(dias)
    # E depois dele, o estimado continua ate o fim do ano.
    assert max(dias) > ate_quando


def test_sem_registros_a_lista_e_toda_estimada():
    dias, ate_quando = calendario_leiloes.dias_ate(pd.Timestamp("2026-12-31"),
                                                   registros=[],
                                                   hoje=pd.Timestamp("2026-08-24"))
    assert ate_quando is None
    assert dias


def test_o_estimado_nao_recalcula_a_fronteira():
    # Achado do revisor (Critical, sobre este teste): a versao anterior conferia
    # len(dias) == len(set(dias)) e dias.count(x) == 1. dias_ate junta os dois
    # componentes com set(publicados) | set(estimados) -- um set() NUNCA guarda
    # duplicata, por definicao do TIPO, entao as duas assercoes eram verdadeiras
    # para QUALQUER entrada, inclusive para um mutante que descarta o publicado
    # inteiro e preenche tudo com o estimador. Elas nao provavam nada sobre o
    # algoritmo.
    #
    # Aqui a assercao mede os COMPONENTES, nao so o resultado final ja deduplicado:
    # reconstroi o publicado e o estimado de fora, do mesmo jeito que dias_ate faz
    # por dentro (estimado a partir do dia SEGUINTE a fronteira, nunca dela), e
    # cruza contra o que dias_ate realmente devolveu. Isso trava que a fronteira
    # continua vindo do publicado -- e nao de um estimado que so concorda com ela
    # por coincidencia de calendario.
    import json
    import pathlib

    fixtures = pathlib.Path(__file__).parent / "fixtures" / "api_leiloes"
    registros = json.loads(
        (fixtures / "calendario.json").read_text(encoding="utf-8"))["registros"]

    ate = pd.Timestamp("2026-12-31")
    hoje = pd.Timestamp("2026-08-24")
    dias, fronteira = calendario_leiloes.dias_ate(ate, registros=registros, hoje=hoje)
    assert fronteira is not None

    agenda = parse_api_leiloes.calendario(registros)
    publicados = {d for d in agenda["data_leilao"].dt.normalize() if hoje <= d <= ate}
    assert fronteira == max(publicados)

    estimados = calendario_leiloes.dias_estimados(fronteira + pd.Timedelta(days=1), ate)
    assert fronteira not in estimados
    assert set(dias) == publicados | set(estimados)


def test_fronteira_na_borda_do_ate_nao_deixa_estimado_vazar():
    # Achado nosso: quando 'ate' cai EXATAMENTE no ultimo dia publicado, nao deve
    # sobrar nenhum dia estimado depois dele -- dias_estimados(fronteira + 1 dia,
    # fronteira) e uma janela invertida (de > ate), que tem de devolver vazio, e
    # nao um dia fantasma reaproveitado da janela anterior.
    import json
    import pathlib

    fixtures = pathlib.Path(__file__).parent / "fixtures" / "api_leiloes"
    registros = json.loads(
        (fixtures / "calendario.json").read_text(encoding="utf-8"))["registros"]

    ultimo_publicado = pd.Timestamp("2026-09-29")
    dias, ate_quando = calendario_leiloes.dias_ate(
        ultimo_publicado, registros=registros, hoje=pd.Timestamp("2026-08-24"))
    assert ate_quando == ultimo_publicado
    assert max(dias) == ultimo_publicado
    assert dias.count(ultimo_publicado) == 1


def test_leilao_publicado_numa_quarta_sobrevive_no_resultado():
    # CRITICAL do revisor: os testes anteriores passavam ate num mutante que
    # descarta o publicado inteiro e preenche tudo com dias_estimados -- porque,
    # na amostra congelada, as 11 datas publicadas caem todas em terca ou quinta,
    # exatamente o que o estimador ja produziria por conta propria. Os dois
    # conjuntos sao identicos, entao nenhum teste anterior conseguia distinguir
    # "o publicado tem precedencia" de "o publicado e ignorado e o estimado
    # imita ele por coincidencia".
    #
    # A UNICA forma de provar precedencia e um dia em que os dois DIVERGEM: uma
    # quarta-feira, dia que _DIAS_DA_SEMANA nunca produz (so terca e quinta).
    # Injeta um leilao sintetico em 26/08/2026 (quarta) na amostra publicada e
    # confere que ele sobrevive em dias_ate -- se o publicado fosse descartado,
    # esse dia nao apareceria em lugar nenhum, porque o estimador jamais o
    # gera.
    import json
    import pathlib

    fixtures = pathlib.Path(__file__).parent / "fixtures" / "api_leiloes"
    registros = json.loads(
        (fixtures / "calendario.json").read_text(encoding="utf-8"))["registros"]

    quarta = pd.Timestamp("2026-08-26")
    assert quarta.day_name() == "Wednesday"

    registro_sintetico = {
        "DATA_LEILAO": "2026-08-26",
        "TITULO": "LTN",
        "VENCIMENTO": "2028-01-01",
        "TIPO_LEILAO": "Venda",
        "BENCHMARK": "LTN 12 meses",
    }
    registros_com_quarta = registros + [registro_sintetico]

    dias, ate_quando = calendario_leiloes.dias_ate(
        pd.Timestamp("2026-12-31"), registros=registros_com_quarta,
        hoje=pd.Timestamp("2026-08-24"))

    # A quarta nunca sairia de dias_estimados: confirma que o dia isolado, so
    # pela regra estimada, realmente nao a produziria (senao o teste nao
    # distinguiria nada).
    assert quarta not in calendario_leiloes.dias_estimados(
        pd.Timestamp("2026-08-24"), pd.Timestamp("2026-12-31"))
    assert quarta in dias


def test_dias_possiveis_NAO_aplica_a_regra_de_dezembro():
    """A regra que corta o fim do ano tem de ser VISIVEL, e nao so aplicada.

    Ela mora numa constante -- nada de leilao depois de 21/12 -- e ate agora
    estava enterrada num filtro dentro de dias_estimados. Quem olhasse a pagina
    via os dias que a gente conta, e nao os que a gente DESCARTA.

    Ela pediu justamente o contrario: "em um cenario hipotetico que ele va emitir
    na ultima semana do ano, consigo ver rapido que nao estamos considerando esse
    cenario". Para mostrar a ausencia e preciso te-la como dado.
    """
    de = pd.Timestamp("2026-12-01")
    ate = pd.Timestamp("2026-12-31")

    possiveis = calendario_leiloes.dias_possiveis(de, ate)
    contados = calendario_leiloes.dias_estimados(de, ate)

    descartados = [d for d in possiveis if d not in set(contados)]
    assert descartados, "dezembro tem de ter dia descartado pela regra"
    assert all(d.day > calendario_leiloes._ULTIMO_DIA_DE_DEZEMBRO
               for d in descartados), (
        "so a regra de dezembro pode descartar dia; apareceu outro motivo")
    # E o que sobrou e exatamente o que dias_estimados ja devolvia.
    assert set(contados) <= set(possiveis)
    assert all(d.day <= calendario_leiloes._ULTIMO_DIA_DE_DEZEMBRO
               for d in contados)


def test_dias_possiveis_respeita_semana_e_feriado():
    """O que dias_possiveis NAO abre mao: terca/quinta e antecipacao por feriado.

    Tirar a regra de dezembro nao pode ter tirado as outras duas junto -- seria
    trocar um filtro escondido por uma lista errada.
    """
    from tesouro import calendario

    cal = calendario.padrao()
    for d in calendario_leiloes.dias_possiveis("2026-01-01", "2026-11-30"):
        assert cal.eh_dia_util(d.date()), f"{d:%d/%m/%Y} nao e dia util"
        # Terca ou quinta, ou o dia util anterior a uma delas por feriado. A
        # INVARIANTE E O CAMINHO, e nao a distancia: _anterior_util so anda para
        # tras por cima de dia NAO util, entao tudo entre o dia devolvido e a
        # terca/quinta de origem tem de ser feriado ou fim de semana.
        #
        # Primeiro limite que escrevi foi "no maximo 3 dias", e estava errado:
        # em 2026 o Carnaval cai na segunda e na terca, e o leilao de terca
        # 17/02 recua para sexta 13/02 -- quatro dias. Numero arbitrario num
        # teste e so o meu palpite disfarcado de regra.
        original = d
        while original.dayofweek not in calendario_leiloes._DIAS_DA_SEMANA:
            original += pd.Timedelta(days=1)
        pulados = pd.date_range(d + pd.Timedelta(days=1), original)
        assert all(not cal.eh_dia_util(x.date()) for x in pulados), (
            f"{d:%d/%m/%Y} nao e a terca/quinta {original:%d/%m/%Y} nem o dia "
            f"util anterior a ela: ha dia util no meio")
