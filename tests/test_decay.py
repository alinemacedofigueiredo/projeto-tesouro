from datetime import date

import numpy as np
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
# Cada horizonte tem que mover EXATAMENTE o numero certo de dias uteis, nao
# so ficar em ordem crescente. "5du: 5->6" ou "1du: 1->2" continuariam
# ordenados (1 < 6 < 21) e passariam no teste acima sem reclamar -- so uma
# ancora por rotulo, contra cal.mover(data_base, n) com o n de HORIZONTES,
# fecha isso. Feito para toda (data_base, horizonte) do painel, nao so o
# ultimo mes.
# ---------------------------------------------------------------------------

def test_cada_horizonte_move_o_numero_certo_de_dias_uteis(d):
    # Os passos ficam FIXOS aqui, escritos a mao -- nao vem de
    # dv.HORIZONTES. Se o teste lesse dv.HORIZONTES para saber quanto
    # esperar, uma mutacao em HORIZONTES ("5du": 5->6, por exemplo)
    # moveria o lado esperado e o lado medido juntos, e o teste passaria
    # de forma tautologica sem pegar nada -- foi exatamente o que
    # aconteceu numa primeira versao deste teste, confirmado a mao
    # revertendo HORIZONTES para {"1du": 2, "5du": 6, "21du": 21}: o
    # teste continuou passando porque os dois lados usavam a mesma
    # fonte. Com os numeros fixos abaixo, a mesma mutacao derruba.
    passos_esperados = {"1du": 1, "5du": 5, "21du": 21}
    for rotulo, passos in passos_esperados.items():
        pares = d[d["horizonte"] == rotulo][["data_base", "data_alvo"]].drop_duplicates()
        assert len(pares) > 100  # muitos meses de painel, nao so um ponto
        for base, alvo in pares.itertuples(index=False):
            assert alvo == CAL.mover(base, passos), (
                f"{rotulo}: esperava mover {passos} dias uteis de {base} e "
                f"chegar em {CAL.mover(base, passos)}, mas data_alvo e {alvo}"
            )


# ---------------------------------------------------------------------------
# A separacao entre "encurtou" e "venceu" -- a razao de existir da tarefa.
# ---------------------------------------------------------------------------

def test_papel_vencido_tem_dv_alvo_zero_quando_o_risco_de_partida_era_conhecido(d):
    # dv_alvo so pode virar "0.0 confirmado" quando dv_base existia; um
    # papel vencido sem dv_base medido (taxa ausente na base) fica None --
    # "nao se aplica" nunca vira "risco foi a zero" (ver a guarda invertida
    # em dv._decay_de).
    v = d[d["venceu_no_caminho"]]
    assert len(v) > 0

    com_base = v[v["dv_base"].notna()]
    assert len(com_base) > 200
    assert (com_base["dv_alvo"] == 0).all()
    assert com_base["dv_alvo"].notna().all()

    sem_base = v[v["dv_base"].isna()]
    assert len(sem_base) > 0  # caso real existe (ex.: BRSTNCNTF071 em 2014-01-31)
    assert sem_base["dv_alvo"].isna().all()
    assert sem_base["decay"].isna().all()


def test_vencimento_aparece_nos_horizontes_longos(d):
    # Contagens exatas, nao so ordenacao frouxa (que sobreviveria a boa
    # parte de um erro na marcacao de vencimento).
    por_h = d.groupby("horizonte")["venceu_no_caminho"].sum()
    assert por_h["1du"] == 80
    assert por_h["5du"] == 80
    assert por_h["21du"] == 126


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
    # A comparacao ingenua (dv_alvo >= dv_base, tolerancia de 1e-9) reprova
    # o dado real: a cotacao da NTN-B e truncada em 4 casas
    # (docs/convencoes-dv.md, "a truncagem faz parte do DV, de proposito"),
    # e no horizonte de 1 dia util o sinal real de decay de um papel longo
    # (poucos milesimos) fica do tamanho do proprio degrau de truncagem --
    # entao uma fracao inverte de sinal por quantizacao, nao por erro de
    # calculo (medido: 100% das reversoes sao NTN-B, nenhuma cruza data de
    # cupom, magnitude sempre <= um degrau).
    #
    # A tolerancia certa nao e uma folga arbitraria: e o proprio degrau de
    # truncagem, na mesma unidade de dv_base/dv_alvo (R$ milhoes). A
    # cotacao trunca em 4 casas antes de multiplicar pelo VNA, entao um
    # passo minimo de cotacao (1e-4) vira 1e-4/100*vna = 1e-6*vna no PU/DV
    # unitario; para LTN e NTN-F, sem VNA, o degrau mais fino e a propria
    # truncagem do PU em 6 casas (1e-6). Convertido para dv_base/dv_alvo
    # (que ja escalam por quantidade_mil/1000), o degrau em R$ milhoes e
    # degrau_unitario * quantidade_mil / 1000. 1% de folga sobre esse
    # degrau (fator 1.01) absorve arredondamento de soma; com essa
    # tolerancia, ZERO sobreviventes invertem nos tres horizontes -- entao
    # a exigencia pode ser 100%, mais forte que os 98% do brief.
    s = d[~d["venceu_no_caminho"] & d["dv_alvo"].notna() & d["dv_base"].notna()]
    assert len(s) > 1000

    p = dv.painel()[["data", "isin", "vna", "quantidade_mil"]].rename(
        columns={"data": "data_base"}
    )
    s = s.merge(p, on=["data_base", "isin"], how="left")
    assert s["quantidade_mil"].notna().all()

    degrau_unitario = np.where(s["titulo"] == "NTN-B", 1e-6 * s["vna"], 1e-6)
    tolerancia = 1.01 * degrau_unitario * s["quantidade_mil"] / 1000

    violacoes = s[s["dv_alvo"] < s["dv_base"] - tolerancia]
    assert len(violacoes) == 0, (
        f"{len(violacoes)} sobreviventes com dv_alvo mais negativo que "
        f"dv_base alem de um degrau de truncagem -- possivel regressao de "
        f"sinal, nao so ruido de quantizacao:\n"
        f"{violacoes[['data_base', 'horizonte', 'isin', 'titulo', 'dv_base', 'dv_alvo']].head(10)}"
    )

    # Checagem complementar, mais fraca (sobrevive a um deslocamento
    # uniforme de todos os horizontes): com a tolerancia ingenua de
    # 1e-9, a taxa de sobreviventes monotonicos ainda tem que CRESCER de
    # 1du para 5du para 21du, porque o ruido de truncagem e fixo em
    # modulo mas o sinal real de decay cresce com o horizonte.
    taxas = {}
    for h in ("1du", "5du", "21du"):
        sub = s[s["horizonte"] == h]
        assert len(sub) > 1000
        taxas[h] = (sub["dv_alvo"] >= sub["dv_base"] - 1e-9).mean()
    assert taxas["1du"] < taxas["5du"] < taxas["21du"]


def test_decay_e_a_diferenca_entre_alvo_e_base(d):
    x = d[d["dv_base"].notna() & d["dv_alvo"].notna()]
    assert len(x) > 15000  # amostra inteira: e formula vetorizada, custa pouco
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
# Ancora do decay em si (nao so do dv_base) em 2026-06-30, nos tres
# horizontes -- os sobreviventes decaem de forma crescente com o prazo,
# e o total fica fora do papel que venceu no caminho (marcado a parte).
# ---------------------------------------------------------------------------

def test_decay_do_sistema_em_2026_06_30_bate_com_o_valor_medido(d):
    base = d["data_base"].max()
    assert base == date(2026, 6, 30)
    esperado_sobreviventes = {"1du": 0.6548, "5du": 3.9642, "21du": 15.9106}
    medidos = {}
    for horizonte, valor in esperado_sobreviventes.items():
        sub = d[(d["data_base"] == base) & (d["horizonte"] == horizonte)]
        sobreviventes = sub[~sub["venceu_no_caminho"]]
        medido = sobreviventes["decay"].sum()
        assert medido == pytest.approx(valor, rel=0.01)
        medidos[horizonte] = medido
    # O decay dos sobreviventes cresce com o horizonte.
    assert medidos["1du"] < medidos["5du"] < medidos["21du"]


# ---------------------------------------------------------------------------
# Coerencia: o decay direto de cada horizonte (o N de dv.HORIZONTES, hoje
# 1, 5, 21 dias uteis) contra a soma de N passos diarios de 1 dia util
# cada, com a MESMA taxa e o MESMO VNA fixos em toda a janela.
# Matematicamente essa soma e telescopica -- soma das diferencas
# consecutivas de uma sequencia e igual a diferenca entre as pontas --
# entao qualquer motor deterministico bate quase exato (o numero que
# sobra e ruido de ponto flutuante, ~1e-12 no total do sistema, medido
# nesta sessao). A convexidade real (medida pelo revisor: 13,6% de
# divergencia entre 21du e 21x o decay de 1 dia, mediana de 19,5% no
# historico) e ordens de grandeza maior do que essa tolerancia -- entao
# esta comparacao (cadeia telescopica) NAO mede convexidade.
#
# O que este teste pega, e o que ele NAO pega: como o "N" de cada rotulo
# vem do proprio dv.HORIZONTES (mesma fonte usada por decay()), uma
# mutacao NO VALOR de HORIZONTES (ex.: "5du": 5->6) desloca os dois lados
# junto e nao quebra esta cadeia -- essa mutacao e pega pelos dois testes
# de ancora acima (test_cada_horizonte_move_o_numero_certo_de_dias_uteis,
# com os passos escritos a mao, e test_decay_do_sistema_em_2026_06_30_
# bate_com_o_valor_medido, com o numero final medido). O que ESTE teste
# pega e uma inconsistencia dentro do proprio calculo do horizonte N
# atual: se _decay_de/decay() passasse a contar o alvo em dias corridos,
# ou reprecificasse numa data deslocada (ex.: mover(data_alvo, 1) em vez
# de data_alvo), o alvo dos N passos diarios (sempre por
# calendario.mover de 1 em 1) deixaria de coincidir com o alvo do calculo
# direto, e a divergencia saltaria do ruido de ponto flutuante para uma
# fracao apreciavel do decay total -- ordens de grandeza acima da
# tolerancia abaixo. Cobre os tres horizontes, nao so 21du.
# ---------------------------------------------------------------------------

def test_cada_horizonte_bate_com_a_soma_dos_passos_diarios_equivalentes(d):
    base = d["data_base"].max()
    p = dv.painel()
    grupo = p[(p["data"] == base) & (p["titulo"] != "LFT")]

    def unit_dv(row, t):
        if pd.isna(row.taxa_pct) or pd.isna(row.dv_unitario):
            return None
        if CAL.ajustar_vencimento(row.vencimento) <= t:
            return 0.0
        return precificacao.dv(
            CAL, row.titulo, t, row.vencimento, row.taxa_pct / 100.0, row.vna
        )

    for rotulo, passos in dv.HORIZONTES.items():
        direto = d[(d["data_base"] == base) & (d["horizonte"] == rotulo)]["decay"].sum()

        datas = [base]
        for _ in range(passos):
            datas.append(CAL.mover(datas[-1], 1))

        soma_cadeia = 0.0
        papeis_usados = 0
        for row in grupo.itertuples(index=False):
            valores = [unit_dv(row, t) for t in datas]
            if any(v is None for v in valores):
                continue
            qtd = row.quantidade_mil
            soma_cadeia += sum(
                (valores[i + 1] - valores[i]) * qtd / 1000 for i in range(passos)
            )
            papeis_usados += 1

        assert papeis_usados > 20  # senao a comparacao e vazia
        divergencia = abs(direto - soma_cadeia)
        assert divergencia < 1e-6, (
            f"{rotulo}: divergencia {divergencia} entre decay direto "
            f"({direto}) e a soma dos {passos} passos diarios "
            f"({soma_cadeia}) -- maior do que ruido de ponto flutuante, "
            f"investigar contagem de dias uteis"
        )
