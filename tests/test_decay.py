from datetime import date

import pandas as pd
import pytest
from tesouro import calendario, config, dv, precificacao

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

    degrau_unitario = (1e-6 * s["vna"]).where(s["titulo"] == "NTN-B", 1e-6)
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


# ---------------------------------------------------------------------------
# Pontual: mesma conta de _decay_de, com uma data-alvo escolhida na hora em
# vez de um dos tres horizontes fixos.
# ---------------------------------------------------------------------------

def test_pontual_fecha_a_identidade():
    r = dv.pontual(date(2027, 12, 31))
    soma = r["dv_base"] + r["dv_que_vence"] + r["decay_sobreviventes"]
    assert abs(soma - r["dv_alvo"]) < 1e-6


def test_pontual_separa_o_que_vence():
    # Ate o fim de 2027 vence bastante papel; a parcela nao pode ser zero.
    r = dv.pontual(date(2027, 12, 31))
    assert r["dv_que_vence"] != 0
    assert r["dv_base"] < 0            # convencao de sinal
    assert abs(r["dv_alvo"]) < abs(r["dv_base"])


def test_pontual_por_titulo_soma_o_total():
    r = dv.pontual(date(2027, 12, 31))
    assert set(r["por_titulo"]["titulo"]) <= {"LTN", "NTN-F", "NTN-B"}
    assert abs(r["por_titulo"]["dv_base"].sum() - r["dv_base"]) < 1e-6


def test_pontual_recusa_data_no_passado():
    with pytest.raises(ValueError, match="posterior"):
        dv.pontual(date(2010, 1, 31))


def test_pontual_em_data_muito_distante_zera_tudo():
    # Depois de 2060 nao sobra papel vivo.
    r = dv.pontual(date(2070, 1, 2))
    assert abs(r["dv_alvo"]) < 1e-6
    # Minor da revisao: sem checar dv_base, um DataFrame vazio (por
    # exemplo se o filtro de titulo quebrasse e nao sobrasse linha
    # nenhuma) tambem daria sum() == 0.0 e passaria vacuamente.
    assert r["dv_base"] < 0


# ---------------------------------------------------------------------------
# Casos de erro e de omissao que o brief da Tarefa 7 exige alem dos cinco
# testes acima: data fora da janela do calendario nao pode vazar o
# ValueError cru de dentro de calendario.Calendario, e omitir --alvo tem que
# fazer algo sensato (documentado no proprio resultado, em "alvo_padrao").
# ---------------------------------------------------------------------------

def test_pontual_data_alvo_fora_da_janela_do_calendario_da_mensagem_clara():
    with pytest.raises(ValueError, match="calendario de dias uteis"):
        dv.pontual(date(2100, 1, 1))


def test_pontual_data_base_fora_da_janela_do_calendario_da_mensagem_clara():
    with pytest.raises(ValueError, match="calendario de dias uteis"):
        dv.pontual(date(2027, 12, 31), data_base=date(1990, 1, 31))


def test_pontual_data_base_fora_do_painel_da_mensagem_clara():
    with pytest.raises(ValueError, match="painel"):
        dv.pontual(date(2027, 12, 31), data_base=date(2026, 6, 15))


def test_pontual_sem_alvo_usa_data_base_mais_um_ano():
    r = dv.pontual()
    assert r["alvo_padrao"] is True
    assert r["data_alvo"] == date(r["data_base"].year + 1, r["data_base"].month,
                                   r["data_base"].day)


def test_pontual_com_alvo_marca_alvo_padrao_como_falso():
    r = dv.pontual(date(2027, 12, 31))
    assert r["alvo_padrao"] is False


# ---------------------------------------------------------------------------
# O quadro impresso tem que nomear a cobertura do DV01 (docs/convencoes-
# dv.md) -- senao quem le supoe que o total mede a divida inteira -- e os
# numeros tem que sair em portugues (virgula decimal), nao no formato
# americano que pandas/Python usam por padrao.
# ---------------------------------------------------------------------------

def test_formatar_pontual_menciona_cobertura_do_dv01():
    r = dv.pontual(date(2027, 12, 31))
    texto = dv._formatar(r)
    assert "cobertura do DV01" in texto
    assert "LFT" in texto


def test_formatar_pontual_usa_virgula_decimal():
    r = dv.pontual(date(2027, 12, 31))
    texto = dv._formatar(r)
    # dv_base do total, negativo, formatado com virgula e ponto de milhar.
    assert dv._num_br(r["dv_base"]) in texto
    assert dv._num_br(1234.5) == "1.234,50"
    assert dv._num_br(-1234.5) == "-1.234,50"
    assert dv._num_br(45.2, forcar_sinal=True) == "+45,20"


# ---------------------------------------------------------------------------
# Achados da revisao da Tarefa 7. Cada teste abaixo corresponde a um item
# do relatorio de revisao (numerado no comentario) e falha sem a correcao
# correspondente -- confirmado a mao revertendo cada correcao uma de cada
# vez antes de escrever o teste definitivo.
# ---------------------------------------------------------------------------

def test_cobertura_do_dv01_nao_e_constante_muda_com_a_data_base():
    # Item 2 (Important): a cobertura impressa era uma constante de junho
    # de 2026 (46,6%), afirmada para QUALQUER --base. O revisor mediu a
    # cobertura real por data e achou 60,4% em 2020-12-31, 14 pontos
    # acima. Os numeros abaixo foram calculados uma vez, a mao, com um
    # script separado sobre estoque_titulos_vencimento.csv (financeiro
    # bruto, nao o financeiro_calculado_milhoes do painel) -- nao vem de
    # dv._cobertura, que e a propria funcao sob teste.
    esperado = {
        date(2026, 6, 30): {"cobertos": 46.5, "lft": 51.3},
        date(2020, 12, 31): {"cobertos": 60.4, "lft": 36.8},
    }
    for data_base, valores in esperado.items():
        c = dv._cobertura(CAL, data_base)
        assert c is not None
        assert c["cobertos_pct"] == pytest.approx(valores["cobertos"], abs=0.15)
        assert c["lft_pct"] == pytest.approx(valores["lft"], abs=0.15)
        # cobertos + lft + excluidos fecha em 100%, por construcao.
        assert c["cobertos_pct"] + c["lft_pct"] + c["excluidos_pct"] == pytest.approx(100.0, abs=1e-6)

    # As duas datas tem que dar numeros DIFERENTES -- e a trava real
    # contra a regressao para uma constante fixa, o bug que a revisao
    # encontrou.
    c1 = dv._cobertura(CAL, date(2026, 6, 30))
    c2 = dv._cobertura(CAL, date(2020, 12, 31))
    assert abs(c1["cobertos_pct"] - c2["cobertos_pct"]) > 5


def test_quadro_impresso_usa_a_cobertura_da_propria_data_base():
    # Complementa o teste acima checando o texto que a usuaria le de
    # verdade: --base 31/12/2020 tem que imprimir 60,x%, nao 46,6%.
    r = dv.pontual(date(2027, 12, 31), data_base=date(2020, 12, 31))
    texto = dv._formatar(r)
    assert "60,4%" in texto
    assert "46,6%" not in texto


def test_por_titulo_agrega_as_quatro_colunas_corretamente():
    # Item 4 (Important): o revisor mutou a agregacao de por_titulo (troca
    # de coluna, soma por maximo, nunique por count, soma por minimo) e a
    # suite inteira continuou passando, porque so dv_base tinha ancora.
    # No dado real cada ISIN aparece uma unica vez por (titulo, data),
    # entao "nunique" e "count" dao o mesmo resultado ali -- por isso este
    # teste usa um DataFrame sintetico com ISIN "A" duplicado de
    # proposito, testando _por_titulo isolada (extraida de pontual()).
    df = pd.DataFrame({
        "titulo": ["LTN", "LTN", "LTN", "NTN-F"],
        "isin": ["A", "A", "B", "C"],
        "dv_base": [-1.0, -1.0, -2.0, -5.0],
        "dv_alvo": [-0.4, -0.4, -1.5, -4.0],
        "venceu_no_caminho": [False, False, True, False],
    })
    r = dv._por_titulo(df).set_index("titulo")

    assert r.loc["LTN", "dv_base"] == pytest.approx(-4.0)     # soma das 3 linhas
    assert r.loc["LTN", "dv_alvo"] == pytest.approx(-2.3)     # soma, nao max (-0.4)
    assert r.loc["LTN", "papeis"] == 2                        # isin unico (A, B), nao 3 linhas
    assert r.loc["LTN", "vencendo"] == 1                      # soma de bool, nao min (0)

    assert r.loc["NTN-F", "dv_base"] == pytest.approx(-5.0)
    assert r.loc["NTN-F", "dv_alvo"] == pytest.approx(-4.0)
    assert r.loc["NTN-F", "papeis"] == 1
    assert r.loc["NTN-F", "vencendo"] == 0


def test_formatar_pontual_imprime_as_quatro_linhas_da_decomposicao():
    # Item 4 (Important), continuacao: apagar a linha "DV na data-alvo" de
    # _formatar tambem deixava a suite inteira passar.
    r = dv.pontual(date(2027, 12, 31))
    texto = dv._formatar(r)
    assert "DV na data-base" in texto
    assert "DV que vence no caminho" in texto
    assert "decay dos sobreviventes" in texto
    assert "DV na data-alvo" in texto


def test_pontual_nao_vaza_o_valueerror_cru_do_calendario():
    # Item 5 (Important): a mensagem certa nao basta -- sem "from None" em
    # _validar_no_calendario, o ValueError cru de
    # Calendario._verificar_janela continua anexado como __context__ e
    # reaparece no traceback ("During handling of the above exception...")
    # sempre que pontual() e chamada fora de um try/except, mesmo com a
    # mensagem final correta. match=... (usado nos testes de mensagem
    # acima) passa nos dois casos, entao nao serve pra travar isso -- e
    # __context__ tambem NAO serve (Python o preenche de qualquer forma,
    # "from None" so muda __suppress_context__, conferido a mao no
    # interpretador antes de escrever este teste). A assercao certa e
    # sobre __suppress_context__, que e o que o formatador de traceback do
    # Python de fato consulta para decidir se imprime a cadeia.
    with pytest.raises(ValueError) as excinfo:
        dv.pontual(date(2100, 1, 1))
    assert excinfo.value.__context__ is not None       # o calendario levantou algo
    assert excinfo.value.__suppress_context__ is True   # mas a cadeia fica escondida


def test_formatar_pontual_explica_por_que_vence_e_decay_sao_positivos():
    # Minor: o rodape que evita a leitura errada "(-) numero positivo =
    # subtraia isto" tambem podia ser apagado sem derrubar nenhum teste.
    r = dv.pontual(date(2027, 12, 31))
    texto = dv._formatar(r)
    assert "sinal positivo" in texto


def test_gravar_regrava_os_tres_csvs_de_producao(tmp_path, monkeypatch, capsys):
    # Item 3 (Important, Tarefa 7): __main__ trocou gravar_painel() por
    # main(), e o pipeline nao gera dv_por_papel.csv/decay_por_papel.csv
    # em lugar nenhum -- "python -m tesouro.dv" era a UNICA forma de
    # regerar os dois. --gravar devolve essa capacidade sem reintroduzir
    # o comportamento antigo como padrao.
    #
    # I6 (Important, revisao da Tarefa 8): resultado_mensal.csv (gravado
    # por gravar_resultado(), Tarefa 8) nunca era chamado por --gravar --
    # o CSV gravado uma vez ficaria parado, envelhecendo em silencio ao
    # lado dos outros dois, sempre atualizados. Dois meses sinteticos
    # (nao um so) para o resultado ter pelo menos uma linha de verdade,
    # com "financeiro_milhoes" no estoque porque gravar_resultado() agora
    # tambem imprime a nota de cobertura (achado I5), que le esse campo.
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)
    d0 = CAL.ultimo_dia_util_do_mes(date(2026, 5, 31))
    d1 = CAL.ultimo_dia_util_do_mes(date(2026, 6, 30))
    venc = date(2028, 1, 1)
    pd.DataFrame(
        [(str(d0), "Prefixados", "LTN", str(venc), "ISINTESTE1", 10.0, 8.7),
         (str(d1), "Prefixados", "LTN", str(venc), "ISINTESTE1", 10.0, 8.6)],
        columns=["data", "indexador", "titulo", "vencimento", "isin",
                 "quantidade_mil", "financeiro_milhoes"],
    ).to_csv(tmp_path / "estoque_titulos_vencimento.csv", index=False)
    pd.DataFrame(
        # +200 bp, nao +50: a um mes do vencimento o efeito de carrego
        # (menos dias para descontar) supera um choque de taxa pequeno e
        # o resultado sai positivo mesmo com a taxa subindo -- confirmado
        # a mao com precificacao.pu antes de escolher este delta. +200 bp
        # garante o sinal negativo esperado sem depender de coincidencia.
        [(str(d0), "ISINTESTE1", "LTN", str(venc), 12.0),
         (str(d1), "ISINTESTE1", "LTN", str(venc), 14.0)],
        columns=["data", "isin", "titulo", "vencimento", "taxa_pct"],
    ).to_csv(tmp_path / "taxa_por_papel.csv", index=False)
    pd.DataFrame(
        [(str(d0), "SELIC", 15000.0)],  # LTN nao usa; so evita CSV vazio
        columns=["data", "indice", "vna"],
    ).to_csv(tmp_path / "vna.csv", index=False)

    dv.main(["--gravar"])
    saida = capsys.readouterr().out

    assert (tmp_path / "dv_por_papel.csv").exists()
    assert (tmp_path / "decay_por_papel.csv").exists()
    assert (tmp_path / "resultado_mensal.csv").exists()
    painel_gravado = pd.read_csv(tmp_path / "dv_por_papel.csv")
    assert len(painel_gravado) == 2
    assert painel_gravado.iloc[0]["titulo"] == "LTN"

    resultado_gravado = pd.read_csv(tmp_path / "resultado_mensal.csv")
    assert len(resultado_gravado) == 1
    # taxa subiu 200 bp (12.0 -> 14.0): o prefixado perde, resultado < 0.
    assert resultado_gravado.iloc[0]["resultado_milhoes"] < 0

    assert "resultado_mensal.csv" in saida
    assert "cobertura do estoque" in saida
