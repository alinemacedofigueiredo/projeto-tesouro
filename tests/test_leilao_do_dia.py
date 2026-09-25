"""O edital do dia: a oferta entra sozinha, antes de sair resultado."""
import pandas as pd

from tesouro import leilao_do_dia


DIA = pd.Timestamp("2026-09-24")


def _edital(quando=DIA):
    """Dois vertices, no formato cru que o endpoint /editais devolve."""
    return [
        {"data_leilao": quando.strftime("%Y-%m-%d"), "titulo": "LTN",
         "vencimento": "2028-01-01", "tipo_leilao": "Venda",
         "oferta": 5000000, "edital": "Edital n 238", "oferta_bcb": 5000000,
         "benchmark": "LTN 12 meses"},
        {"data_leilao": quando.strftime("%Y-%m-%d"), "titulo": "NTN-F",
         "vencimento": "2031-01-01", "tipo_leilao": "Venda",
         "oferta": 4000000, "edital": "Edital n 239", "oferta_bcb": 4000000,
         "benchmark": "NTN-F 5 anos"},
    ]


def _fingir_a_api(monkeypatch, registros):
    monkeypatch.setattr(leilao_do_dia.api_leiloes, "buscar",
                        lambda nome, timeout=None: (registros, b""))


def test_a_tabela_do_edital_traz_as_pernas_ofertadas_sem_taxa(monkeypatch):
    # A oferta nao tem taxa nem quantidade aceita: nada disso aconteceu ainda.
    # Quem empresta a taxa do leilao anterior e leiloes_dv, ja no calculo do DV.
    _fingir_a_api(monkeypatch, _edital())
    t = leilao_do_dia.tabela_do_edital(quando=DIA)

    assert len(t) == 2
    assert sorted(t["titulo"]) == ["LTN", "NTN-F"]
    assert t["oferta_qtd"].tolist() == [5000000, 4000000]
    assert t["taxa_media_pct"].isna().all(), (
        "a oferta nao tem taxa publicada; inventar uma aqui seria plausivel e "
        "errado")
    assert t["venda_qtd"].isna().all(), "nada foi aceito ainda"


def test_a_liquidacao_do_edital_pula_FERIADO_e_nao_so_fim_de_semana(monkeypatch):
    # O tradutor deixa a liquidacao vazia de proposito -- ela nao vem no edital.
    # Quem preenche e este caminho, e ele tem de usar o calendario de verdade:
    # 21/04/2026 e Tiradentes, numa terca. Um leilao na segunda 20/04 liquida em
    # 22/04, e nao em 21.
    #
    # O caminho da planilha usa D+1 pulando so o fim de semana, porque la ELA
    # corrige o feriado a mao. Aqui nao ha planilha nem ninguem para corrigir.
    from tesouro import calendario

    segunda = pd.Timestamp("2026-04-20")
    cal = calendario.padrao()
    assert not cal.eh_dia_util(pd.Timestamp("2026-04-21").date()), (
        "este teste depende de 21/04/2026 ser feriado")

    _fingir_a_api(monkeypatch, _edital(segunda))
    t = leilao_do_dia.tabela_do_edital(quando=segunda)

    assert (t["data_liquidacao"] == pd.Timestamp("2026-04-22")).all(), (
        f"liquidacao veio {sorted(set(t['data_liquidacao']))}, mas 21/04 e "
        f"feriado")


def test_o_edital_de_OUTRO_dia_nao_entra(monkeypatch):
    # O endpoint devolve o edital vigente. Se ele ainda estiver com o do leilao
    # anterior, pegar tudo o que vier gravaria oferta de ontem como de hoje.
    _fingir_a_api(monkeypatch, _edital(pd.Timestamp("2026-09-22")))
    assert leilao_do_dia.tabela_do_edital(quando=DIA) is None


def test_sem_edital_o_caminho_devolve_zero_e_nao_quebra(monkeypatch):
    # Dia sem leilao, ou API fora do ar antes das 10h30: nao ha o que gravar, e
    # isso nao e erro.
    _fingir_a_api(monkeypatch, [])
    assert leilao_do_dia.do_edital(quando=DIA, refazer_graficos=False) == 0
