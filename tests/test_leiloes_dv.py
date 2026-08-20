"""O DV01 emitido em cada leilao.

As ancoras aqui nao sao numeros que eu escolhi: a maioria e cruzamento contra o
financeiro que o proprio Tesouro publica para cada leilao. Se a precificacao estiver
errada, o financeiro calculado nao bate com o dele -- e sao 14 mil oportunidades de
nao bater.
"""
import pandas as pd
import pytest

from tesouro import calendario, leiloes_dv, precificacao


@pytest.fixture(scope="module")
def dv():
    return leiloes_dv.dv_por_leilao()


@pytest.fixture(scope="module")
def cal():
    return calendario.padrao()


# ---------------------------------------------------------------------------
# O cruzamento que vale por todos: o PU calculado, vezes a quantidade, tem de
# reproduzir o financeiro que o Tesouro publicou.
# ---------------------------------------------------------------------------

def test_o_pu_calculado_reproduz_o_financeiro_do_tesouro(cal):
    # LTN e NTN-F nao dependem de VNA nenhum: o PU sai so da taxa e das datas. Se as
    # formulas do projeto estiverem certas, qtd x PU tem de dar o financeiro do
    # Tesouro na casa do centesimo de por cento -- e da.
    #
    # Este e o teste mais forte do modulo. Ele nao afirma um numero que eu escolhi;
    # afirma que a nossa conta e a dele chegam ao mesmo lugar, milhares de vezes.
    l = pd.read_csv(leiloes_dv.config.PROCESSED_DIR / "leiloes.csv",
                    parse_dates=["data_liquidacao", "data_vencimento"])
    v = l[(l["tipo_leilao"] == "Venda") & (l["venda_qtd"] > 0)
          & (l["financeiro_milhoes"] > 0)
          & (l["data_liquidacao"].dt.year >= 2011)
          & (l["titulo"].isin(["LTN", "NTN-F"]))]
    assert len(v) > 5000, "a amostra encolheu; o teste perdeu forca"

    erros = []
    for _, r in v.iterrows():
        pu = precificacao.pu(cal, r["titulo"], r["data_liquidacao"].date(),
                             r["data_vencimento"].date(),
                             r["taxa_media_pct"] / 100.0)
        calculado = r["venda_qtd"] * pu / 1e6
        erros.append(abs(calculado - r["financeiro_milhoes"])
                     / r["financeiro_milhoes"])

    erros = pd.Series(erros)
    assert erros.median() < 0.0005, f"mediana {erros.median():.6f}"
    assert erros.max() < 0.005, f"maior desvio {erros.max():.6f}"


def test_a_taxa_vai_como_fracao_e_o_percentual_da_numero_errado(cal):
    # A armadilha entre os dois modulos: leiloes.csv grava percentual e precificacao
    # espera fracao. Passar o percentual NAO levanta -- devolve PU de 84,75 onde o
    # certo e 4.490, e DV que arredonda para zero.
    import datetime

    d0 = datetime.date(2026, 6, 3)
    venc = datetime.date(2029, 5, 15)
    vna = 4716.315

    certo = precificacao.pu(cal, "NTN-B", d0, venc, 8.115 / 100.0, vna)
    errado = precificacao.pu(cal, "NTN-B", d0, venc, 8.115, vna)

    assert 4400 < certo < 4600, "o PU tem de ficar perto do VNA"
    assert errado < 100, "o percentual direto devolve numero pequeno e plausivel"
    assert precificacao.dv(cal, "NTN-B", d0, venc, 8.115, vna) == 0.0


# ---------------------------------------------------------------------------
# O VNA recuperado do proprio leilao
# ---------------------------------------------------------------------------

def test_o_pu_da_ntnb_e_linear_no_vna(cal):
    # E o que permite recuperar o VNA por divisao. Se um dia deixar de ser linear,
    # a recuperacao para de valer e este teste avisa antes de o numero sair torto.
    import datetime

    d0 = datetime.date(2026, 6, 3)
    venc = datetime.date(2029, 5, 15)
    cotacoes = [precificacao.pu(cal, "NTN-B", d0, venc, 0.08115, vna) / vna
                for vna in (1.0, 1000.0, 4716.315)]
    # 1e-8 e nao zero: o PU e truncado em seis casas pela convencao da Anbima, e com
    # VNA = 1 o truncamento aparece na oitava casa da cotacao. A linearidade e da
    # formula; o residuo e do arredondamento, e some para VNA de tamanho real.
    assert max(cotacoes) - min(cotacoes) < 1e-8


def test_o_vna_recuperado_fica_dentro_da_acumulacao_do_mes(dv):
    # O VNA sai do financeiro do leilao; o vna.csv traz o fechamento do mes. Os dois
    # tem de ficar a menos de um mes de acumulacao um do outro -- medido: mediana de
    # 0,16% e percentil 95 de 0,66%, que e exatamente o tamanho do erro que o VNA
    # mensal produzia no PU. Desvio grande denunciaria dado errado.
    b = dv[(dv["titulo"] == "NTN-B") & dv["vna_usado"].notna()
           & dv["vna_do_mes"].notna()]
    assert len(b) > 3000
    desvio = ((b["vna_usado"] - b["vna_do_mes"]) / b["vna_do_mes"]).abs()
    assert round(desvio.median() * 100, 2) == 0.16
    assert desvio.quantile(0.95) < 0.01
    assert desvio.max() < 0.02


# ---------------------------------------------------------------------------
# Convencoes que mudam o numero
# ---------------------------------------------------------------------------

def test_compra_entra_com_sinal_negativo(dv):
    # Recompra TIRA risco do mercado. Somar com emissao da o liquido, que e o que
    # interessa -- e por isso o sinal tem de estar no dado, nao no desenho.
    compras = dv[dv["operacao"] == "compra"]
    assert len(compras) > 100
    assert (compras["financeiro_milhoes"] < 0).all()
    assert (compras["quantidade"] < 0).all()
    com_dv = compras[compras["dv_milhoes"].notna()]
    assert (com_dv["dv_milhoes"] < 0).all(), \
        "recomprar RETIRA risco emitido, entao o DV da recompra e negativo"


def test_a_lft_entra_com_financeiro_e_sem_dv(dv):
    # Decisao de modelagem da entrega 2: a LFT nao tem DV (premissa de duration
    # zero). Vazio e nao zero -- zero seria uma afirmacao sobre o risco dela.
    lft = dv[dv["titulo"] == "LFT"]
    assert len(lft) > 2000
    assert lft["financeiro_milhoes"].abs().sum() > 0
    assert lft["dv_unitario"].isna().all()
    assert lft["dv_milhoes"].isna().all()


def test_o_bacen_nao_entra(dv):
    # venda_bacen_qtd e financeiro_bacen_milhoes sao colunas proprias no leiloes.csv
    # e nao sao emissao do Tesouro. Nenhuma delas chega aqui.
    assert "venda_bacen_qtd" not in dv.columns
    assert "financeiro_bacen_milhoes" not in dv.columns

    l = pd.read_csv(leiloes_dv.config.PROCESSED_DIR / "leiloes.csv")
    assert l["financeiro_bacen_milhoes"].sum() > 100000, \
        "o teste so vale se houver financeiro do Bacen para deixar de fora"


def test_a_troca_fica_de_fora(dv):
    # Troca substitui um papel por outro: o liquido dela nao e emissao nem resgate.
    assert set(dv["operacao"].unique()) == {"venda", "compra"}


def test_os_leiloes_de_2000_ficam_de_fora_porque_o_calendario_comeca_em_2001(dv):
    # O calendario da Anbima cobre de 2001 em diante. Em vez de deixar levantar no
    # meio do laco, a exclusao e explicita -- e conferida aqui.
    assert dv["data_liquidacao"].dt.year.min() >= 2001
    l = pd.read_csv(leiloes_dv.config.PROCESSED_DIR / "leiloes.csv",
                    parse_dates=["data_leilao"])
    de_2000 = l[l["data_leilao"].dt.year == 2000]
    assert len(de_2000) > 100, "o teste so vale se existirem leiloes em 2000"


# ---------------------------------------------------------------------------
# O vertice do Tesouro
# ---------------------------------------------------------------------------

def test_o_vertice_vem_do_rotulo_do_tesouro_quando_existe():
    # "NTN-B 40 anos" -> 40. E a classificacao dele, nao a nossa.
    assert leiloes_dv._vertice("NTN-B", "NTN-B 40 anos", 39.2) == 40
    assert leiloes_dv._vertice("NTN-B", "NTN-B 5 anos", 4.8) == 5
    # Sem rotulo, cai no vertice mais proximo do prazo real.
    assert leiloes_dv._vertice("NTN-B", None, 9.7) == 10
    assert leiloes_dv._vertice("NTN-B", float("nan"), 21.0) == 20


def test_o_dv_e_POSITIVO_em_toda_emissao(dv):
    # A CONVENCAO DE RISCO EMITIDO, e nao a de P&L. docs/convencoes-dv.md ja dizia:
    # "Risco emitido -- positivo e o Tesouro emitindo; negativo e vencimento ou
    # recompra".
    #
    # A PRIMEIRA VERSAO DESTE MODULO DEIXOU PASSAR O SINAL DE P&L, que e o que
    # precificacao.dv devolve -- correto la, errado aqui, porque esta tabela mede
    # EMISSAO. O resultado foi um grafico de emissao com todas as barras para baixo,
    # que ainda exigiu inverter o eixo do DV para ficar legivel. Nao levantou nada:
    # o numero estava certo em modulo, e so o lado estava trocado.
    vendas = dv[(dv["operacao"] == "venda") & dv["dv_milhoes"].notna()]
    assert len(vendas) > 10000
    assert (vendas["dv_milhoes"] > 0).all()
    # E o DV unitario segue a mesma convencao, para que o produto feche.
    assert (vendas["dv_unitario"] > 0).all()


def test_o_dv_ofertado_existe_e_e_maior_ou_igual_ao_aceito(dv):
    # O DV que ele TENTOU colocar. Comparar com o aceito responde uma pergunta que o
    # aceito sozinho nao responde: nao conseguiu, ou nao quis?
    vendas = dv[(dv["operacao"] == "venda")
                & dv["dv_ofertado_milhoes"].notna()
                & dv["dv_milhoes"].notna()]
    assert len(vendas) > 10000
    # Aceitar mais do que ofertou nao existe -- e uma folga minuscula cobre o
    # arredondamento do proprio dado do Tesouro.
    assert (vendas["dv_milhoes"] <= vendas["dv_ofertado_milhoes"] * 1.001).all()
    # E ele de fato deixa de colocar parte: medido, 68,5% do DV ofertado.
    razao = vendas["dv_milhoes"].sum() / vendas["dv_ofertado_milhoes"].sum()
    assert 0.5 < razao < 0.9, razao


def test_a_ordem_de_grandeza_bate_com_o_estoque(dv):
    # Um mes de leiloes acrescenta poucos milhoes por ponto-base, contra os
    # -1.472,87 do estoque inteiro medido na entrega 2. Se um dia der a mesma ordem
    # do estoque, alguma escala se perdeu -- foi o que aconteceu ao tratar a
    # quantidade como se estivesse em milhares.
    agosto = dv[(dv["data_leilao"] >= "2026-08-01") & dv["dv_milhoes"].notna()]
    total = agosto["dv_milhoes"].sum()
    assert 0 < total < 20, f"DV de agosto/26: {total:.2f}"
