from datetime import date

import pandas as pd
import pytest
from tesouro import calendario, dv, precificacao

CAL = calendario.padrao()


@pytest.fixture(scope="module")
def d():
    return dv.decay()


# ---------------------------------------------------------------------------
# Estrutura basica: colunas, horizontes, exclusao da LFT.
# ---------------------------------------------------------------------------

def test_colunas_canonicas(d):
    assert list(d.columns) == [
        "data_base", "horizonte", "data_alvo", "isin", "titulo",
        "venceu_no_caminho", "dv_base", "dv_alvo", "decay",
    ]


def test_tres_horizontes(d):
    assert set(d["horizonte"].unique()) == {"1du", "5du", "21du"}


def test_lft_fica_de_fora(d):
    # A LFT nao tem DV no projeto, entao nao tem decay.
    assert "LFT" not in set(d["titulo"].unique())


def test_data_alvo_e_posterior_a_base(d):
    assert (pd.to_datetime(d["data_alvo"]) > pd.to_datetime(d["data_base"])).all()


def test_horizonte_maior_produz_alvo_mais_distante(d):
    base = d["data_base"].max()
    no_mes = d[d["data_base"] == base]
    alvos = no_mes.groupby("horizonte")["data_alvo"].first()
    assert alvos["1du"] < alvos["5du"] < alvos["21du"]


# ---------------------------------------------------------------------------
# A separacao entre "encurtou" e "venceu" -- a razao de existir da tarefa.
# ---------------------------------------------------------------------------

def test_papel_vencido_tem_dv_alvo_zero_e_nao_vazio(d):
    v = d[d["venceu_no_caminho"]]
    assert len(v) > 0
    assert (v["dv_alvo"] == 0).all()
    assert v["dv_alvo"].notna().all()


def test_vencimento_aparece_nos_horizontes_longos(d):
    # Em 1 dia util quase nunca vence; em 21 vence com frequencia.
    por_h = d.groupby("horizonte")["venceu_no_caminho"].sum()
    assert por_h["21du"] > por_h["1du"]


def test_venceu_no_caminho_nunca_chama_precificacao(monkeypatch):
    # O que importa aqui e que a reprecificacao NAO aconteca para um papel
    # ja marcado como vencido -- um teste que so olhasse dv_alvo==0 passaria
    # igual se _decay_de chamasse precificacao.dv com d0 pos-vencimento e o
    # motor devolvesse 0.0 por acidente (pu_ltn/pu_lft fazem isso). A
    # garantia real e comportamental: o motor nunca e chamado para essa
    # combinacao (data, isin), entao espionamos a chamada em vez de so
    # conferir o resultado (mesma licao do teste
    # test_vna_ausente_pula_a_linha_em_vez_de_precificar_com_nan em
    # tests/test_dv.py).
    chamadas = []
    original = precificacao.dv

    def espiao(cal, titulo, d0, vencimento, taxa, vna=None):
        chamadas.append((d0, titulo, vencimento))
        return original(cal, titulo, d0, vencimento, taxa, vna)

    monkeypatch.setattr(precificacao, "dv", espiao)

    resultado = dv.decay(horizontes={"1du": 1})

    # BRSTNCLTN848 vence em 2026-07-01, exatamente o alvo de 1du a partir
    # de 2026-06-30 (ultimo mes do painel) -- caso real, sem fixture
    # sintetica.
    linha = resultado[
        (resultado["isin"] == "BRSTNCLTN848")
        & (resultado["data_base"] == date(2026, 6, 30))
    ]
    assert len(linha) == 1
    assert bool(linha["venceu_no_caminho"].iloc[0])
    assert linha["dv_alvo"].iloc[0] == 0.0

    alvo_deste_papel = date(2026, 7, 1)
    assert (alvo_deste_papel, "LTN", date(2026, 7, 1)) not in chamadas


# ---------------------------------------------------------------------------
# Sinal: DV e negativo para titulo: com menos prazo ele fica MENOS negativo.
# decay = dv_alvo - dv_base, entao decay >= 0 para um sobrevivente.
# ---------------------------------------------------------------------------

def test_decay_reduz_o_modulo_do_dv_dos_sobreviventes(d):
    # Nao e 100% dos sobreviventes: a cotacao da NTN-B e truncada em 4
    # casas (docs/convencoes-dv.md, "a truncagem faz parte do DV, de
    # proposito"), e no horizonte de 1 dia util o sinal real de decay de
    # um papel longo (poucos milesimos) fica do tamanho do proprio degrau
    # de truncagem -- entao uma pequena fracao inverte de sinal por
    # quantizacao, nao por erro de calculo. Medido nesta sessao: 91,7% em
    # 1du, 97,7% em 5du, 99,9% em 21du, 96,4% no agregado. 0,98 de
    # exigencia geral e alto demais e reprovaria o dado real; 0,95 fica
    # com folga do medido (0,964) sem aceitar uma regressao de sinal.
    s = d[~d["venceu_no_caminho"] & d["dv_alvo"].notna() & d["dv_base"].notna()]
    assert len(s) > 1000
    assert (s["dv_alvo"] >= s["dv_base"] - 1e-9).mean() > 0.95

    # A garantia mais forte que uma banda unica: o ruido de truncagem e
    # fixo em modulo, mas o sinal real de decay cresce com o horizonte,
    # entao a taxa de reversoes tem que CAIR de 1du para 5du para 21du.
    # Se essa ordem quebrasse, seria sinal de erro de sinal genuino (nao
    # so quantizacao), nao de mais ruido.
    taxas = {}
    for h in ("1du", "5du", "21du"):
        sub = s[s["horizonte"] == h]
        assert len(sub) > 1000
        taxas[h] = (sub["dv_alvo"] >= sub["dv_base"] - 1e-9).mean()
    assert taxas["1du"] < taxas["5du"] < taxas["21du"]


def test_decay_e_a_diferenca_entre_alvo_e_base(d):
    x = d[d["dv_base"].notna() & d["dv_alvo"].notna()].head(200)
    assert ((x["dv_alvo"] - x["dv_base"]) - x["decay"]).abs().max() < 1e-9


# ---------------------------------------------------------------------------
# Ancora de nivel: o dv_base do decay tem que bater com o dv_posicao_
# milhoes medido do painel em 2026-06-30 (docs/convencoes-dv.md /
# tests/test_dv.py), nao so a ordem de grandeza. Isso trava _decay_de
# carregando o base errado (por exemplo, recalculando em vez de reusar
# r.dv_posicao_milhoes) com a mesma tolerancia usada em test_dv.py.
# ---------------------------------------------------------------------------

def test_dv_base_do_decay_bate_com_o_valor_medido_do_painel(d):
    base = d["data_base"].max()
    ult = d[(d["data_base"] == base) & (d["horizonte"] == "21du")]
    esperado = {"LTN": -198.54, "NTN-F": -177.76, "NTN-B": -1096.58}
    for titulo, valor in esperado.items():
        medido = ult[ult["titulo"] == titulo]["dv_base"].sum()
        assert medido == pytest.approx(valor, rel=0.01)
    total = ult["dv_base"].sum()
    assert total == pytest.approx(-1472.87, rel=0.01)


# ---------------------------------------------------------------------------
# Coerencia: o decay de 21 dias uteis contra a soma de 21 passos diarios
# de 1 dia util cada, com a MESMA taxa e o MESMO VNA fixos em toda a
# janela. Matematicamente essa soma e telescopica -- soma das diferencas
# consecutivas de uma sequencia e igual a diferenca entre as pontas --
# entao qualquer motor deterministico bate quase exato (o numero que sobra
# e ruido de ponto flutuante, ~1e-12 no total do sistema, medido nesta
# sessao). O valor desse teste esta em travar a CONTAGEM DE DIAS: se
# _decay_de ou HORIZONTES passasse a usar dias corridos em vez de
# cal.mover em algum dos dois caminhos, o alvo dos 21 passos diarios e o
# alvo do calculo direto deixariam de coincidir, e a divergencia pularia
# de ruido de ponto flutuante para uma fracao apreciavel do decay total
# (o efeito de um dia inteiro a mais ou a menos, ordem de grandeza maior
# que a tolerancia abaixo).
# ---------------------------------------------------------------------------

def test_21du_e_proximo_da_soma_dos_1du_diarios(d):
    base = d["data_base"].max()
    p = dv.painel()
    grupo = p[(p["data"] == base) & (p["titulo"] != "LFT")]

    direto = d[(d["data_base"] == base) & (d["horizonte"] == "21du")]["decay"].sum()

    datas = [base]
    for _ in range(21):
        datas.append(CAL.mover(datas[-1], 1))

    def unit_dv(row, t):
        if pd.isna(row.taxa_pct) or pd.isna(row.dv_unitario):
            return None
        if CAL.ajustar_vencimento(row.vencimento) <= t:
            return 0.0
        return precificacao.dv(
            CAL, row.titulo, t, row.vencimento, row.taxa_pct / 100.0, row.vna
        )

    soma_cadeia = 0.0
    papeis_usados = 0
    for row in grupo.itertuples(index=False):
        valores = [unit_dv(row, t) for t in datas]
        if any(v is None for v in valores):
            continue
        qtd = row.quantidade_mil
        soma_cadeia += sum(
            (valores[i + 1] - valores[i]) * qtd / 1000 for i in range(21)
        )
        papeis_usados += 1

    assert papeis_usados > 20  # senao a comparacao e vazia
    divergencia = abs(direto - soma_cadeia)
    assert divergencia < 1e-6, (
        f"divergencia {divergencia} entre decay 21du direto ({direto}) e a "
        f"soma dos 21 passos diarios ({soma_cadeia}) -- maior do que ruido "
        f"de ponto flutuante, investigar contagem de dias uteis"
    )
