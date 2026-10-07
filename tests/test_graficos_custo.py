import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pytest

from tesouro import config
from tesouro.graficos import custo, estilo


@pytest.fixture(scope="module")
def dados():
    return custo.dados_custo()


def test_o_custo_do_ULTIMO_MES_bate_com_o_anexo(dados):
    # O NOME DIZIA "junho" e o corpo sempre olhou dados.iloc[-1] -- o ultimo mes
    # que houver. Com a virada para julho o nome passou a mentir.
    #
    # Aba 4.2, custo acumulado em 12 meses. Remedido para AGOSTO em 07/10/2026.
    u = dados.iloc[-1]
    assert round(u["DPF"], 2) == 12.59
    assert round(u["DPMFi"], 2) == 13.06


def test_a_selic_e_o_ipca_saem_do_nosso_vna(dados):
    # A variacao de 12 meses do VNA E o indice acumulado. A pagina do RMD busca
    # isso no site do Bacen; nos temos em casa desde a entrega 2.
    u = dados.iloc[-1]
    assert round(u["SELIC"], 2) == 14.63
    assert round(u["IPCA"], 2) == 4.36


def test_a_medida_e_o_acumulado_de_12_meses_e_nao_o_mensal(dados):
    # A medida 'mensal' da 12,04 para a DPF em agosto, contra 12,59 do
    # acumulado: plausivel, e errado. E o exemplo mais limpo do medo deste
    # projeto -- os dois numeros existem, os dois vem do Tesouro, e so um
    # responde a pergunta do grafico.
    #
    # EM JULHO A DISTANCIA ERA MAIOR (10,92 contra 12,45). Em agosto os dois se
    # aproximaram, e a assercao de que diferem continua valendo -- mas vale
    # reparar: se um mes os dois coincidirem, este teste perde o sentido e a
    # linha abaixo avisa.
    bruto = pd.read_csv(config.PROCESSED_DIR / "custo_medio.csv",
                        parse_dates=["data"])
    mensal = bruto[(bruto["medida"] == "mensal") & (bruto["nivel"] == "DPF")
                   & bruto["entidade"].isna() & bruto["titulo"].isna()]
    valor_mensal = mensal.set_index("data")["custo_aa_pct"].iloc[-1]
    assert round(valor_mensal, 2) == 12.04          # existe, e nao e o nosso
    assert round(dados.iloc[-1]["DPF"], 2) == 12.59
    assert valor_mensal != dados.iloc[-1]["DPF"], (
        "as duas medidas colidiram; o teste perdeu o sentido")


def test_o_vna_e_mensal_e_completo():
    # shift(12) conta posicoes, nao meses: com um buraco na serie a variacao de 12
    # meses compara contra 13 ou 14 meses atras sem avisar.
    v = pd.read_csv(config.PROCESSED_DIR / "vna.csv", parse_dates=["data"])
    meses = v["data"].dt.to_period("M").drop_duplicates().sort_values()
    esperado = pd.period_range(meses.min(), meses.max(), freq="M")
    # A CONTAGEM ERA CRAVADA EM 198 e crescia um por coleta -- amarra no lugar
    # errado, num teste que e sobre a serie nao ter buraco. A completude, essa,
    # e a assercao de verdade e vale em qualquer mes.
    assert list(meses) == list(esperado), "o VNA tem mes faltando"
    assert len(meses) > 190, "a serie do VNA encolheu"


def test_a_juncao_e_por_competencia_e_nao_por_data(dados):
    # O VNA e do ultimo dia util e o custo e do ultimo dia do mes: em 02/09/2026,
    # so 138 das 199 datas coincidem. Juntar por data exata perderia 61 meses.
    # O numero anda a cada coleta; o teste trava a RELACAO (coincidem de menos
    # para que juntar por data seja seguro), e nao a contagem.
    v = pd.read_csv(config.PROCESSED_DIR / "vna.csv", parse_dates=["data"])
    coincidem = set(v["data"]) & set(dados.index)
    assert len(coincidem) < 150, "as datas coincidem demais; o teste perdeu sentido"
    # Ainda assim nenhum mes de 2011 em diante fica sem Selic.
    de_2011 = dados[dados.index >= "2011-01-01"]
    assert de_2011["SELIC"].notna().all()
    assert len(de_2011) >= 180


def test_os_indices_ficam_vazios_antes_de_2011_e_nunca_zerados(dados):
    antes = dados[dados.index < "2011-01-01"]
    assert len(antes) > 50
    assert antes["SELIC"].isna().all()
    assert antes["IPCA"].isna().all()
    # Zero seria lido como "a Selic foi a zero".
    assert not (antes["SELIC"] == 0).any()
    # O custo, esse, existe desde dez/2005.
    assert antes["DPF"].notna().all()


def test_a_janela_de_5_anos_corta_mas_preserva_o_ultimo_mes():
    curto = custo.dados_custo(janela=5)
    longo = custo.dados_custo()
    assert len(curto) < len(longo)
    assert curto.index.max() == longo.index.max()
    assert curto.index.min() >= longo.index.max() - pd.DateOffset(years=5)
    assert round(curto.iloc[-1]["DPF"], 2) == 12.59


def test_so_o_ultimo_ponto_de_cada_linha_leva_rotulo(dados):
    estilo.aplicar_estilo()
    fig, ax = plt.subplots(figsize=(13, 6))
    custo.desenha_custo(dados, ax)
    escritos = sorted(a.get_text() for a in ax.texts)
    plt.close(fig)
    # Quatro linhas, quatro numeros, todos na borda direita. O proprio
    # comentario antigo ja dizia que sao OS MESMOS valores dos dois testes
    # acima -- entao agora eles SAEM DO DADO em vez de cravados, e este teste
    # para de envelhecer a cada RMD. O assunto dele e "so o ultimo ponto leva
    # rotulo", e nao quanto vale cada um. Trocado em 07/10/2026.
    u = dados.iloc[-1]
    esperado = sorted(estilo.num_br(u[c], 2) for c in dados.columns)
    assert escritos == esperado
    assert len(escritos) == len(dados.columns), (
        "sobrou ou faltou rotulo: um por linha, no ultimo ponto")
