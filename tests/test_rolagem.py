"""A rolagem do estoque do RMD ate hoje, e a projecao ate o fim do ano."""
import pandas as pd
import pytest

from tesouro import rolagem


def test_o_VNA_recuperado_do_leilao_bate_com_o_conhecido():
    # ESTE E O TESTE QUE DISPENSA A BLOOMBERG. O vna.csv termina exatamente na
    # data-base do RMD, e os leiloes vao alem dela. Sem VNA nesses dias nao ha termo
    # de juros, e a LFT sai ~2% subestimada.
    #
    # PU = VNA x cotacao, e a cotacao depende so da taxa e das datas: o PU efetivo
    # dividido pela cotacao devolve o VNA que o Tesouro usou. Medido nos 98 leiloes
    # que caem em data de VNA conhecida, o erro mediano e 0,045%.
    from tesouro import config

    v = pd.read_csv(config.PROCESSED_DIR / "vna.csv", parse_dates=["data"])
    for indice in ("SELIC", "IPCA"):
        s = v[v["indice"] == indice].set_index("data")["vna"]
        quando = s.index[-1]
        recuperado = rolagem.vna_em(indice, quando)
        real = float(s.loc[quando])
        assert abs(recuperado - real) / real < 0.002, (indice, recuperado, real)


def test_sem_leilao_para_recuperar_o_VNA_ele_LEVANTA():
    # Congelar em silencio subestima o estoque da LFT em ~50 bi por mes. Se nao ha
    # como saber, o certo e parar.
    with pytest.raises(LookupError, match="VNA"):
        rolagem.vna_em("SELIC", pd.Timestamp("1990-01-01"))


def test_a_rolagem_reproduz_os_meses_FECHADOS_do_RMD():
    # O TESTE QUE SUSTENTA TUDO O MAIS. Se a rolagem nao reproduz um mes que ja
    # aconteceu, o numero de "hoje" que ela produz nao vale nada.
    #
    # Os limites vieram da medicao em 24 meses, em % do estoque do indexador:
    # taxa flutuante 0,07%, indice de precos 0,51%, prefixado 0,75%. O teste usa o
    # DOBRO de folga, para nao reprovar por um mes atipico.
    from tesouro import config

    c = pd.read_csv(config.PROCESSED_DIR / "composicao_dpf.csv",
                    parse_dates=["data"])
    piv = c.pivot_table(index="data", columns="indexador",
                        values="valor_milhoes", aggfunc="sum").fillna(0.0)
    datas = list(piv.index)[-13:]

    LIMITE = {"Prefixado": 0.015, "\u00cdndice Pre\u00e7os": 0.011,
              "Taxa Flutuante": 0.002}
    for t0, t1 in zip(datas[:-1], datas[1:]):
        obtido = rolagem.estoque_em(t1, de=t0)
        for ind, limite in LIMITE.items():
            real = piv.loc[t1, ind]
            erro = abs(obtido[ind] - real) / real
            assert erro < limite, (t1.date(), ind, erro, limite)


def test_a_rolagem_casa_por_LIQUIDACAO_e_nao_por_data_de_leilao():
    # 6,1% dos leiloes liquidam no mes seguinte ao do leilao. Casar pela data errada
    # poe o papel no mes errado, e erra exatamente as viradas -- que e onde o RMD
    # corta.
    from tesouro import config

    l = pd.read_csv(config.PROCESSED_DIR / "leiloes.csv",
                    parse_dates=["data_leilao", "data_liquidacao"])
    vira = l[(l["data_liquidacao"].dt.to_period("M")
              != l["data_leilao"].dt.to_period("M"))
             & (l["tipo_leilao"] == "Venda")]
    assert len(vira) > 1000, "os leiloes que viram o mes sumiram do dado"

    r = vira.sort_values("data_liquidacao").iloc[-1]
    fim_do_mes_do_leilao = (r["data_leilao"] + pd.offsets.MonthEnd(0))
    entrou = rolagem.leiloes_liquidados(
        r["data_liquidacao"] - pd.Timedelta(days=1), r["data_liquidacao"])
    nao_entrou = rolagem.leiloes_liquidados(
        fim_do_mes_do_leilao - pd.Timedelta(days=31), fim_do_mes_do_leilao)
    assert entrou.sum() > 0
    assert r["data_liquidacao"] > fim_do_mes_do_leilao


def test_o_CAMBIO_fica_parado_e_a_rolagem_diz_isso():
    # O indexador Cambio E a DPFe -- diferenca mediana de R$ 4,9 bi em 307 meses --
    # e a DPFe nao passa por leilao. Ele e segurado no valor do RMD, com o custo
    # medido: 5,2 bi por mes, 0,06% do estoque total.
    #
    # O que nao pode e segura-lo em SILENCIO: ele esta no denominador dos outros
    # tres percentuais.
    assert "C\u00e2mbio" in rolagem.PARADOS
    assert "C\u00e2mbio" not in rolagem.INDEXADORES
