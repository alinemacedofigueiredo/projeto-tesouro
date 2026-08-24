"""A curva do proprio dado: Selic implicita e inflacao implicita."""
import pandas as pd
import pytest

from tesouro import curva


def test_a_interpolacao_IGNORA_vencimento_sem_cotacao():
    # A ARMADILHA DESTA TAREFA. A LTN de vencimento mais proximo de 31/12/2026 e a
    # 01/01/2027 -- e ela NAO TEM COTACAO: e um dos dois papeis que so existem no
    # Tesouro Direto. Quem escolher "o vencimento mais proximo" pega justamente o
    # que nao tem taxa, e a conta sai NaN sem reclamar.
    from tesouro import config

    d = pd.read_csv(config.PROCESSED_DIR / "dv_por_papel.csv",
                    parse_dates=["data", "vencimento"])
    ult = d[d["data"] == d["data"].max()]
    sem_taxa = ult[(ult["titulo"] == "LTN") & ult["taxa_pct"].isna()]
    assert len(sem_taxa), "a LTN sem cotacao sumiu do dado; reveja este teste"

    taxa = curva.selic_implicita(pd.Timestamp("2026-12-31"))
    assert taxa == taxa, "a taxa saiu NaN: a interpolacao pegou papel sem cotacao"
    assert 0.05 < taxa < 0.30, taxa


def test_a_selic_implicita_fica_entre_as_pontas_da_curva():
    # Interpolacao nao inventa: o valor tem de ficar entre os dois vizinhos.
    from tesouro import config

    d = pd.read_csv(config.PROCESSED_DIR / "dv_por_papel.csv",
                    parse_dates=["data", "vencimento"])
    ult = d[(d["data"] == d["data"].max()) & (d["titulo"] == "LTN")
            & d["taxa_pct"].notna()]
    taxa = curva.selic_implicita(pd.Timestamp("2026-12-31")) * 100
    assert ult["taxa_pct"].min() <= taxa <= ult["taxa_pct"].max()


def test_a_inflacao_implicita_sai_da_relacao_de_Fisher():
    # (1 + nominal) / (1 + real) - 1. Uma inflacao implicita que nao respeite isso
    # nao e breakeven, e outra coisa.
    infl = curva.inflacao_implicita(pd.Timestamp("2026-12-31"))
    assert 0.0 < infl < 0.15, infl


def test_a_NTN_B_de_referencia_nao_e_a_mais_proxima():
    # A mais proxima em 30/06/2026 e a de 15/08/2026, a 33 dias uteis, com taxa real
    # de 11,25% -- ponta de curva, e nao expectativa. A de referencia e a MAIS CURTA
    # COM COTACAO cujo vencimento passe da data-alvo -- nao qualquer uma depois, e
    # nao a mais longa. "> 2026-12-31" sozinho nao distingue a de 15/05/2027 (a
    # certa) da de 2060 (a mais longa da curva); o valor exato trava as duas.
    escolhida = curva.ntnb_de_referencia(pd.Timestamp("2026-12-31"))
    assert escolhida == pd.Timestamp("2027-05-15"), escolhida


def test_selic_implicita_bate_o_valor_medido():
    # Numero medido a mao em 30/06/2026: ~13,76%. Nao e so o tipo, e o valor.
    taxa = curva.selic_implicita(pd.Timestamp("2026-12-31"))
    assert abs(taxa - 0.1376) < 0.001, taxa


def test_inflacao_implicita_bate_o_valor_medido():
    # Numero medido a mao em 30/06/2026: ~4,70% de breakeven.
    infl = curva.inflacao_implicita(pd.Timestamp("2026-12-31"))
    assert abs(infl - 0.0470) < 0.001, infl


def test_extrapolacao_plana_antes_da_primeira_ponta():
    # 'ate' antes do primeiro vencimento com cotacao: du fica menor que xs[0], e
    # _interpola devolve a ponta curta, sem extrapolar para fora da curva.
    from tesouro import config

    d = pd.read_csv(config.PROCESSED_DIR / "dv_por_papel.csv",
                    parse_dates=["data", "vencimento"])
    base = d["data"].max()
    ult = d[(d["data"] == base) & (d["titulo"] == "LTN") & d["taxa_pct"].notna()]
    taxa_curta = ult.sort_values("vencimento").iloc[0]["taxa_pct"] / 100

    # A propria data-base: du = 0, antes de qualquer vencimento na curva.
    taxa = curva.selic_implicita(base)
    assert abs(taxa - taxa_curta) < 1e-9, taxa


def test_extrapolacao_plana_depois_da_ultima_ponta():
    # 'ate' depois do ultimo vencimento com cotacao: devolve a ponta longa.
    from tesouro import config

    d = pd.read_csv(config.PROCESSED_DIR / "dv_por_papel.csv",
                    parse_dates=["data", "vencimento"])
    base = d["data"].max()
    ult = d[(d["data"] == base) & (d["titulo"] == "LTN") & d["taxa_pct"].notna()]
    taxa_longa = ult.sort_values("vencimento").iloc[-1]["taxa_pct"] / 100

    taxa = curva.selic_implicita(pd.Timestamp("2040-01-01"))
    assert abs(taxa - taxa_longa) < 1e-9, taxa


def test_data_base_explicita_e_usada_em_vez_do_dado_mais_recente():
    # Passar data_base deve mudar a base da curva, nao so aceitar o parametro.
    from tesouro import config

    d = pd.read_csv(config.PROCESSED_DIR / "dv_por_papel.csv",
                    parse_dates=["data", "vencimento"])
    datas = sorted(d["data"].unique())
    assert len(datas) > 1, "precisa de mais de uma data no dado para este teste"
    base_anterior = pd.Timestamp(datas[-2])

    taxa_ultima = curva.selic_implicita(pd.Timestamp("2026-12-31"))
    taxa_anterior = curva.selic_implicita(pd.Timestamp("2026-12-31"),
                                           data_base=base_anterior)
    assert taxa_ultima != taxa_anterior


def test_ate_anterior_a_data_base_e_rejeitado():
    # calendario.du() e simetrico: du(base, ate) com ate antes de base devolve a
    # mesma distancia positiva que se ate viesse depois, e _interpola pegaria a
    # ponta errada da curva sem reclamar. Tem de barrar, nao responder errado.
    with pytest.raises(ValueError):
        curva.selic_implicita(pd.Timestamp("2026-01-01"),
                               data_base=pd.Timestamp("2026-06-30"))


def test_ntnb_de_referencia_rejeita_ate_anterior_a_data_base():
    # Mesma armadilha do 'du' simetrico, na segunda interface publica: sem a
    # guarda, isso devolveria uma NTN-B (a de 15/08/2026, primeira depois de
    # 2026-01-01) sem reclamar, ainda que 'ate' esteja antes da data-base.
    with pytest.raises(ValueError):
        curva.ntnb_de_referencia(pd.Timestamp("2026-01-01"),
                                  data_base=pd.Timestamp("2026-06-30"))


def test_inflacao_implicita_rejeita_ate_anterior_a_data_base():
    # A mesma armadilha, na terceira interface publica. Sem a guarda isto
    # devolvia 0.02518 (breakeven plausivel, e errado) em vez de recusar --
    # exatamente a classe de defeito que a guarda existe para impedir.
    with pytest.raises(ValueError):
        curva.inflacao_implicita(pd.Timestamp("2026-01-01"),
                                  data_base=pd.Timestamp("2026-06-30"))
