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
