from datetime import date

import pandas as pd
import pytest
from tesouro import calendario, dv


@pytest.fixture(scope="module")
def r():
    return dv.resultado_mensal()


@pytest.fixture(scope="module")
def v():
    return dv.variacao_de_dv()


@pytest.fixture(scope="module")
def dc():
    return dv.resultado_decomposto()


def test_colunas_canonicas(r):
    assert list(r.columns) == [
        "data_ini", "data_fim", "isin", "titulo", "venceu_no_periodo",
        "quantidade_mil_ini", "pu_ini", "pu_fim", "resultado_milhoes",
    ]


def test_periodos_sao_meses_consecutivos(r):
    # Afirma diretamente que data_fim cai no mes seguinte ao de data_ini
    # (ano*12+mes anda exatamente 1), em vez de uma faixa de dias
    # corridos. Achado da revisao (Minor): a faixa 26-35 falhava de
    # verdade em jan->fev/2017 e jan->fev/2022 (24 e 25 dias -- Carnaval
    # empurra o ultimo dia util de fevereiro para tras), e mesmo a faixa
    # 22-35 que substituiu era mais frouxa que o necessario (o minimo
    # real e 24 dias, no calendario inteiro de 2001 a 2098) e o comentario
    # antigo tinha o calendario de 2022 invertido: 28/02 e 01/03/2022 SAO
    # os feriados de Carnaval da Anbima; 26 e 27/02/2022 sao so sabado e
    # domingo (conferido com calendario.padrao().eh_dia_util). A afirmacao
    # de mes seguinte nao depende de contar dias, entao nao tem esse
    # problema: um mes inteiro faltando quebra "mes seguinte" tao bem
    # quanto quebraria qualquer faixa de dias.
    pares = r[["data_ini", "data_fim"]].drop_duplicates()
    ini = pd.to_datetime(pares["data_ini"])
    fim = pd.to_datetime(pares["data_fim"])
    assert (fim > ini).all()
    meses_ini = ini.dt.year * 12 + ini.dt.month
    meses_fim = fim.dt.year * 12 + fim.dt.month
    assert (meses_fim - meses_ini == 1).all()


def test_quantidade_e_a_do_inicio_do_periodo(r):
    # C1 (Critical) da revisao: o teste original olhava uma linha so
    # (r[...].iloc[0]) -- a linha sorteada era BRSTNCLF18J3, LFT em
    # 2010-01-29, com quantidade IDENTICA nas duas pontas do periodo. O
    # revisor trocou o estoque final pelo congelado na coluna e na conta
    # (dv.py, na epoca linhas 539/541) e a suite continuou passando (10
    # passed) -- o teste era vacuamente verdadeiro para aquela linha.
    #
    # Aqui varremos TODAS as linhas vivas (nao so a primeira), comparamos
    # quantidade_mil_ini contra o painel em data_ini via merge vetorizado,
    # e exigimos que exista pelo menos um caso onde a quantidade do
    # painel MUDOU entre data_ini e data_fim -- sem essa segunda parte, o
    # teste voltaria a ser vacuo se por acaso nenhuma linha do dado real
    # tivesse emissao/resgate no meio do caminho. No dado real ha 5.973
    # dessas linhas (de 9.314), entao a checagem nao e vacua aqui.
    p = dv.painel()
    vivas = r[r["quantidade_mil_ini"].notna()][
        ["data_ini", "data_fim", "isin", "quantidade_mil_ini"]
    ]

    no_ini = p[["data", "isin", "quantidade_mil"]].rename(
        columns={"data": "data_ini", "quantidade_mil": "q_painel_ini"})
    m = vivas.merge(no_ini, on=["data_ini", "isin"], how="left")
    assert m["q_painel_ini"].notna().all()
    assert (m["quantidade_mil_ini"] == m["q_painel_ini"]).all()

    no_fim = p[["data", "isin", "quantidade_mil"]].rename(
        columns={"data": "data_fim", "quantidade_mil": "q_painel_fim"})
    m = m.merge(no_fim, on=["data_fim", "isin"], how="left")
    diferentes = m["q_painel_fim"].notna() & (m["q_painel_fim"] != m["quantidade_mil_ini"])
    assert diferentes.sum() > 0


def test_papel_que_venceu_fica_marcado_e_sem_pu_final(r):
    venceu = r[r["venceu_no_periodo"]]
    assert len(venceu) > 0
    assert venceu["pu_fim"].isna().all()
    assert venceu["resultado_milhoes"].isna().all()


def test_resultado_e_a_diferenca_de_pu_vezes_a_quantidade(r):
    x = r[r["resultado_milhoes"].notna()].head(300)
    esperado = (x["pu_fim"] - x["pu_ini"]) * x["quantidade_mil_ini"] / 1000
    assert (esperado - x["resultado_milhoes"]).abs().max() < 1e-9


def test_resultado_tem_os_dois_sinais(r):
    # Ha meses de alta e de queda de taxa; se so houver um sinal, algo
    # esta errado na convencao.
    s = r["resultado_milhoes"].dropna()
    assert (s > 0).any() and (s < 0).any()


def test_resultado_bate_com_meses_conhecidos_de_alta_e_queda_de_taxa(r):
    # I3 (Important) da revisao: nenhum teste anterior ancorava o SINAL
    # do resultado contra a realidade -- test_resultado_e_a_diferenca_de_
    # pu_vezes_a_quantidade deriva o "esperado" das proprias colunas
    # pu_ini/pu_fim do frame sob teste, entao uma inversao coerente (o
    # revisor trocou pu_ini por pu_fim na tupla E na formula) so derruba
    # o teste de vencimento, por acidente.
    #
    # Os dois meses abaixo foram conferidos rodando dv.resultado_mensal()
    # sem alterar nada, e batem com o que o revisor mediu por fora:
    #
    #   set/2021 -> out/2021: taxa prefixada SOBE ~199,6 bp; resultado
    #   prefixado (LTN+NTN-F) = -R$ 37.308,21 milhoes.
    #   set/2018 -> out/2018: taxa prefixada CAI ~145,3 bp; resultado
    #   prefixado = +R$ 43.230,68 milhoes.
    #
    # Uma inversao pu_ini<->pu_fim troca o sinal dos dois casos ao mesmo
    # tempo -- qualquer um dos dois sozinho ja pegaria essa mutacao.
    casos = [
        (date(2021, 9, 30), date(2021, 10, 29), -37308.212438),
        (date(2018, 9, 28), date(2018, 10, 31), 43230.682846),
    ]
    for ini, fim, esperado in casos:
        seg = r[(r["data_ini"] == ini) & (r["data_fim"] == fim) &
                r["titulo"].isin(["LTN", "NTN-F"])]
        assert len(seg) > 0
        total = seg["resultado_milhoes"].sum()
        assert total == pytest.approx(esperado, abs=1.0)


def test_ordem_de_grandeza_do_resultado_mensal(r):
    # O resultado de um mes da carteira inteira fica na casa de dezenas de
    # bilhoes de reais -- dezenas de milhares de milhoes. Achado Minor da
    # revisao: o teto de 500.000 tinha 4,3x de folga sobre o maximo real
    # do historico (116.310,5, em out/2018) e nao pegaria uma LFT
    # duplicada (o pior caso simulado, total + LFT do mesmo mes de novo,
    # chega a 150.170,5). 140.000 fica acima do maximo real (margem de
    # ~1,2x, sem falso positivo) e abaixo do pior caso de duplicacao.
    por_mes = r.groupby("data_fim")["resultado_milhoes"].sum().abs()
    assert por_mes.max() < 140000


def test_variacao_de_dv_usa_o_estoque_real(v):
    assert list(v.columns) == ["data", "titulo", "dv_milhoes", "variacao_milhoes"]
    assert set(v["titulo"].unique()) <= {"LTN", "NTN-F", "NTN-B"}
    # A primeira data de cada titulo nao tem variacao.
    assert v.groupby("titulo")["variacao_milhoes"].apply(lambda s: s.isna().sum()).eq(1).all()

    # I2 (Important) da revisao: o corpo original so conferia colunas,
    # titulos e "um NaN por titulo" -- nada da propriedade que o nome da
    # funcao afirma. O revisor congelou o universo de ISIN no primeiro
    # mes e a suite continuou passando. Duas checagens que so a base REAL
    # (nao um snapshot fixo) satisfaz:
    #
    # (1) o numero de ISIN por (data, titulo) muda ao longo do tempo --
    #     um universo congelado teria contagem constante em toda data.
    # (2) dv_milhoes bate, mes a mes, com a soma de dv_posicao_milhoes do
    #     painel NAQUELA data -- nao a soma de um snapshot fixo, que
    #     divergiria assim que houvesse emissao ou resgate.
    p = dv.painel()
    vivos = p[p["dv_posicao_milhoes"].notna()]

    contagem = vivos.groupby(["data", "titulo"])["isin"].nunique()
    contagem_muda = contagem.groupby("titulo").apply(lambda s: s.nunique() > 1)
    assert contagem_muda.all()

    soma_painel = (vivos.groupby(["data", "titulo"])["dv_posicao_milhoes"]
                         .sum().rename("dv_painel"))
    comparado = v.set_index(["data", "titulo"]).join(soma_painel)
    assert comparado["dv_painel"].notna().all()
    assert (comparado["dv_milhoes"] - comparado["dv_painel"]).abs().max() < 1e-9


def test_variacao_e_a_diferenca_do_dv_entre_meses(v):
    for _, g in v.groupby("titulo"):
        g = g.sort_values("data")
        esperado = g["dv_milhoes"].diff()
        assert (esperado - g["variacao_milhoes"]).abs().max() < 1e-9


def test_lft_entra_no_resultado_mas_nao_na_variacao_de_dv(r, v):
    # A LFT nao tem DV (dv_unitario e None por decisao de modelagem), mas
    # tem PU real e portanto resultado em dinheiro real -- ela e metade do
    # estoque e excluir esse dinheiro do resultado mensal esconderia a
    # maior parte do financeiro da divida. variacao_de_dv, ao contrario,
    # e sobre risco de taxa: a LFT nao pertence la, e dv_posicao_milhoes
    # dela e sempre None.
    assert "LFT" in set(r["titulo"].unique())
    assert "LFT" not in set(v["titulo"].unique())
    lft_com_resultado = r[(r["titulo"] == "LFT") & r["resultado_milhoes"].notna()]
    assert len(lft_com_resultado) > 0


# ---------------------------------------------------------------------------
# resultado_decomposto(): I4 (Important) da revisao. resultado_mensal()
# sozinho mistura, na NTN-B e na LFT, acumulacao de indice (VNA) com
# movimento de taxa real -- o mesmo fenomeno nos dois papeis indexados.
# Nao vira coluna nova em resultado_mensal() (quebraria test_colunas_
# canonicas sem necessidade) nem CSV -- e analise calculada na hora,
# mesma regra de variacao_de_dv().
# ---------------------------------------------------------------------------

def test_resultado_decomposto_colunas_canonicas(dc):
    assert list(dc.columns) == [
        "data_ini", "data_fim", "isin", "titulo", "quantidade_mil_ini",
        "resultado_milhoes", "resultado_indice_milhoes",
        "resultado_taxa_e_carrego_milhoes",
    ]


def test_resultado_decomposto_fecha_a_identidade(dc):
    # E um experimento controlado (mesma data de precificacao, mesma
    # taxa, so o VNA muda), nao uma estimativa -- as duas partes tem que
    # somar de volta o resultado_milhoes original, sempre.
    x = dc[dc["resultado_indice_milhoes"].notna()]
    assert len(x) > 0
    soma = x["resultado_indice_milhoes"] + x["resultado_taxa_e_carrego_milhoes"]
    assert (soma - x["resultado_milhoes"]).abs().max() < 1e-6


def test_resultado_decomposto_titulos_nao_indexados_tem_indice_zero(dc):
    # LTN e NTN-F nao tem VNA -- a acumulacao de indice e genuinamente
    # zero ali, nao "nao se aplica" (None).
    nao_indexados = dc[dc["titulo"].isin(["LTN", "NTN-F"])]
    assert len(nao_indexados) > 0
    assert (nao_indexados["resultado_indice_milhoes"] == 0.0).all()
    assert (nao_indexados["resultado_taxa_e_carrego_milhoes"] ==
            nao_indexados["resultado_milhoes"]).all()


def test_resultado_decomposto_separa_inflacao_da_ntnb(dc, r):
    # Ancora dos doze meses medidos na revisao: sem separar,
    # resultado_mensal() sozinho mostra a NTN-B ganhando dinheiro
    # (+R$ 29.495,0 milhoes) quando por baixo a inflacao rendeu
    # +R$ 90.095,9 milhoes e a taxa real PERDEU -R$ 60.600,9 milhoes -- o
    # sinal do total nem bate com o sinal da parcela de taxa real.
    ultimos_12 = sorted(r["data_fim"].unique())[-12:]
    seg = dc[(dc["data_fim"].isin(ultimos_12)) & (dc["titulo"] == "NTN-B")]
    assert len(seg) > 0
    assert seg["resultado_milhoes"].sum() == pytest.approx(29494.972496, abs=1.0)
    assert seg["resultado_indice_milhoes"].sum() == pytest.approx(90095.877165, abs=1.0)
    assert seg["resultado_taxa_e_carrego_milhoes"].sum() == pytest.approx(-60600.904669, abs=1.0)


def test_resultado_decomposto_lft_e_quase_toda_indexacao(dc, r):
    # Mesmo mecanismo, generalizado para a LFT: o revisor mediu que
    # R$ 568.716,3 dos R$ 738.059,3 milhoes do total de doze meses (77%,
    # somando todos os titulos) sao acumulacao de Selic no VNA da LFT. A
    # decomposicao fina confirma e refina: 561.516,8 (98,7% do PROPRIO
    # total da LFT) e indice, e so 7.199,6 (1,3%) e movimento de
    # agio/carrego -- coerente com a LFT nao ter duration de juros por
    # construcao.
    ultimos_12 = sorted(r["data_fim"].unique())[-12:]
    seg = dc[(dc["data_fim"].isin(ultimos_12)) & (dc["titulo"] == "LFT")]
    assert len(seg) > 0
    total = seg["resultado_milhoes"].sum()
    indice = seg["resultado_indice_milhoes"].sum()
    assert total == pytest.approx(568716.321927, abs=1.0)
    assert indice == pytest.approx(561516.767065, abs=1.0)
    assert indice / total > 0.95


# ---------------------------------------------------------------------------
# Cobertura: I5 (Important) da revisao. Nenhum total desta tarefa nomeava
# a cobertura -- ao contrario de pontual(), que imprime e tem dois testes
# travando isso.
# ---------------------------------------------------------------------------

def test_nota_cobertura_resultado_distingue_as_duas_bases():
    # A nota tem que citar as duas coberturas -- resultado_mensal
    # (dinheiro, inclui LFT) e variacao_de_dv (risco de taxa, sem LFT) --
    # e elas tem que ser numeros DIFERENTES, senao a nota nao estaria de
    # fato avisando que sao bases distintas. Os dois numeros vem de
    # dv._cobertura, ja ancorada para 30/06/2026 em tests/test_decay.py
    # (46,5% cobertos, 51,3% LFT -- 46,5 + 51,3 = 97,8% em dinheiro).
    cal = calendario.padrao()
    texto = dv._nota_cobertura_resultado(cal, date(2026, 6, 30))
    assert "resultado_mensal" in texto
    assert "variacao_de_dv" in texto
    assert "46,5%" in texto
    assert "97,8%" in texto
