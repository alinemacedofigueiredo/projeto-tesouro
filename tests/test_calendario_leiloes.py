"""O calendario de leiloes: o publicado, e o estimado alem dele."""
import pandas as pd

from tesouro import calendario_leiloes


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

    for ano in (2024, 2025):
        de = pd.Timestamp(f"{ano}-09-01")
        ate = pd.Timestamp(f"{ano}-12-31")
        estimado = set(calendario_leiloes.dias_estimados(de, ate))
        real = set(venda[(venda["data_leilao"] >= de)
                         & (venda["data_leilao"] <= ate)]
                   ["data_leilao"].dt.normalize())
        assert estimado <= real, (
            f"{ano}: o estimador previu dia sem leilao: {sorted(estimado - real)}")
        assert len(estimado) >= len(real) - 3, (
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
