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
    # A DATA VEM DA PRODUCAO, e nao de d["data"].max(): a regra e "a
    # mais recente COM cotacao" desde 02/10/2026, quando o RMD de agosto
    # trouxe 52 linhas sem taxa nenhuma. Perguntar em vez de reproduzir
    # mantem o teste no assunto dele.
    ult = d[d["data"] == curva.data_da_curva()]
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
    # A DATA VEM DA PRODUCAO, e nao de d["data"].max(): a regra e "a
    # mais recente COM cotacao" desde 02/10/2026, quando o RMD de agosto
    # trouxe 52 linhas sem taxa nenhuma. Perguntar em vez de reproduzir
    # mantem o teste no assunto dele.
    ult = d[(d["data"] == curva.data_da_curva())
            & (d["titulo"] == "LTN") & d["taxa_pct"].notna()]
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
    """Medido em 04/09/2026, com a curva de 31/07: 13,6852%.

    ESTA E UMA CHECAGEM DE ESCALA, E NAO UMA ANCORA DE MES -- e a distincao foi
    medida, nao suposta. A PROVA 2 da entrega das ancoras (rodar a suite contra
    o RMD de junho, onde toda ancora de valor tem de ficar vermelha) mostrou que
    esta passa nos DOIS meses: a Selic implicita andou 0,075 pp de junho para
    julho e a tolerancia e de 0,1 pp.

    Nao e espelho -- o numero sai da curva, e nao de uma rodada do teste. Mas
    tambem nao trava mes nenhum, e chamar isso de ancora seria mentir sobre o
    que ela protege. O que ela pega e curva lida na escala errada ou vertice
    trocado, que e outra coisa, e util.

    A da INFLACAO implicita, logo abaixo, trava o mes: la o movimento foi de
    0,49 pp, cinco vezes a tolerancia, e ela cai contra junho.

    APERTAR A TOLERANCIA ATE DISTINGUIR O MES foi considerado e descartado: o
    limiar teria de sair de 0,1 pp para menos de 0,075, escolhido para caber
    entre dois meses que por acaso andaram pouco. Seria numero ajustado contra o
    proprio dado, que e o vicio que esta entrega inteira remove.
    """
    taxa = curva.selic_implicita(pd.Timestamp("2026-12-31"))
    assert abs(taxa - 0.1369) < 0.001, taxa


def test_inflacao_implicita_bate_o_valor_medido():
    # Medido em 04/09/2026, com a curva de 31/07: 5,1880% de breakeven.
    infl = curva.inflacao_implicita(pd.Timestamp("2026-12-31"))
    assert abs(infl - 0.0519) < 0.001, infl


def test_o_juro_real_implicito_e_positivo_e_plausivel():
    """A RELACAO QUE SOBREVIVE ao mercado andar, e que as duas ancoras acima
    nao dao sozinhas.

    A inflacao implicita e o breakeven entre a curva nominal e a real, entao a
    Selic implicita tem de ficar ACIMA dela -- juro real positivo. Se um dia as
    duas se cruzarem, ou uma leitura esta na escala errada, ou o pais mudou de
    regime; nos dois casos alguem precisa olhar antes de a pagina publicar.

    A banda de 2% a 15% e larga de proposito: ela nao julga politica monetaria,
    so pega numero impossivel. Medido em 04/09/2026: 8,08%.
    """
    ate = pd.Timestamp("2026-12-31")
    selic = curva.selic_implicita(ate)
    infl = curva.inflacao_implicita(ate)

    assert selic > infl, (
        f"juro real implicito NEGATIVO: selic {selic:.4%} contra inflacao "
        f"{infl:.4%}")
    real = (1 + selic) / (1 + infl) - 1
    assert 0.02 < real < 0.15, f"juro real implausivel: {real:.4%}"


def test_extrapolacao_plana_antes_da_primeira_ponta():
    # 'ate' antes do primeiro vencimento com cotacao: du fica menor que xs[0], e
    # _interpola devolve a ponta curta, sem extrapolar para fora da curva.
    from tesouro import config

    d = pd.read_csv(config.PROCESSED_DIR / "dv_por_papel.csv",
                    parse_dates=["data", "vencimento"])
    # A DATA VEM DA PRODUCAO, e nao de d["data"].max(): a regra e "a
    # mais recente COM cotacao" desde 02/10/2026, quando o RMD de agosto
    # trouxe 52 linhas sem taxa nenhuma. Perguntar em vez de reproduzir
    # mantem o teste no assunto dele.
    base = curva.data_da_curva()
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
    # A DATA VEM DA PRODUCAO, e nao de d["data"].max(): a regra e "a
    # mais recente COM cotacao" desde 02/10/2026, quando o RMD de agosto
    # trouxe 52 linhas sem taxa nenhuma. Perguntar em vez de reproduzir
    # mantem o teste no assunto dele.
    base = curva.data_da_curva()
    ult = d[(d["data"] == base) & (d["titulo"] == "LTN") & d["taxa_pct"].notna()]
    taxa_longa = ult.sort_values("vencimento").iloc[-1]["taxa_pct"] / 100

    taxa = curva.selic_implicita(pd.Timestamp("2040-01-01"))
    assert abs(taxa - taxa_longa) < 1e-9, taxa


def test_data_base_explicita_e_usada_em_vez_do_dado_mais_recente():
    # Passar data_base deve mudar a base da curva, nao so aceitar o parametro.
    from tesouro import config

    d = pd.read_csv(config.PROCESSED_DIR / "dv_por_papel.csv",
                    parse_dates=["data", "vencimento"])
    # A PENULTIMA COM COTACAO, e nao a penultima do arquivo. Com o RMD de
    # agosto em disco, a ultima do arquivo (31/08) nao tem taxa nenhuma: a
    # penultima do arquivo virou a PRIMEIRA que a producao usa, e o teste
    # comparava a base padrao com ela mesma.
    datas = sorted(d.loc[d["taxa_pct"].notna(), "data"].unique())
    assert len(datas) > 1, "precisa de duas datas com cotacao para este teste"
    base_anterior = pd.Timestamp(datas[-2])
    assert base_anterior != curva.data_da_curva(), (
        "a base anterior tem de ser diferente da que a producao usa por padrao")

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


def test_a_curva_aceita_data_base_que_nao_existe_no_arquivo():
    # O composicao_dpf usa o ultimo dia CORRIDO e o dv_por_papel o ultimo dia UTIL.
    # 30/06/2024 caiu num domingo: existe num e nao no outro. E a projecao real parte
    # da ultima LIQUIDACAO, que vai alem do ultimo RMD -- o caminho principal da
    # entrega levantava LookupError, e nenhum teste o exercitava.
    assert curva.data_da_curva(pd.Timestamp("2024-06-30")) == pd.Timestamp("2024-06-28")
    assert curva.selic_implicita(pd.Timestamp("2024-12-31"),
                                 data_base=pd.Timestamp("2024-06-30")) > 0

    # E alem do fim do arquivo: a curva mais recente vale, e quem chama fica sabendo.
    depois = pd.Timestamp("2026-08-17")
    usada = curva.data_da_curva(depois)
    assert usada < depois
    assert curva.selic_implicita(pd.Timestamp("2026-12-31"), data_base=depois) > 0


def test_sem_curva_nenhuma_ate_a_data_ele_LEVANTA():
    with pytest.raises(LookupError, match="curva"):
        curva.data_da_curva(pd.Timestamp("1999-01-01"))


def test_a_data_base_PULA_mes_sem_cotacao_nenhuma():
    # O QUE ACONTECEU EM 02/10/2026: ela trouxe o RMD de agosto. O
    # dv_por_papel.csv ganhou 52 linhas em 31/08 -- quantidade e vencimento, que
    # vem do RMD -- e ZERO taxas, que vem da Bloomberg e nao foi puxada.
    #
    # _data_base escolhia a data mais recente com QUALQUER linha, entao parava
    # em 31/08 e _curva estourava: "nenhuma LTN com cotacao em 31/08/2026". A
    # pagina do PAF nao saia.
    #
    # DECISAO DELA: usar a curva de julho, dizendo de quando ela e. O rodape da
    # projecao ja imprime data_da_curva, entao a mistura de datas fica escrita.
    import pandas as pd

    from tesouro import curva

    d = pd.DataFrame({
        "data": pd.to_datetime(["2026-07-31", "2026-07-31",
                                "2026-08-31", "2026-08-31"]),
        "titulo": ["LTN", "NTN-B", "LTN", "NTN-B"],
        "vencimento": pd.to_datetime(["2028-01-01", "2029-05-15",
                                      "2028-01-01", "2029-05-15"]),
        "taxa_pct": [13.5, 7.1, float("nan"), float("nan")],
    })

    # Pedindo agosto, tem de cair em julho -- a ultima data COM cotacao.
    assert curva._data_base(d, pd.Timestamp("2026-08-31")) == pd.Timestamp("2026-07-31")
    # E sem pedir nada, tambem: "a mais recente" quer dizer a mais recente util.
    assert curva._data_base(d, None) == pd.Timestamp("2026-07-31")


def test_sem_cotacao_em_lugar_nenhum_ainda_LEVANTA():
    # A degradacao tem limite: se nao ha cotacao em data nenhuma, nao ha curva,
    # e inventar premissa continua sendo pior que parar.
    import pandas as pd
    import pytest

    from tesouro import curva

    d = pd.DataFrame({
        "data": pd.to_datetime(["2026-08-31"]),
        "titulo": ["LTN"],
        "vencimento": pd.to_datetime(["2028-01-01"]),
        "taxa_pct": [float("nan")],
    })
    with pytest.raises(LookupError, match="curva"):
        curva._data_base(d, pd.Timestamp("2026-08-31"))
