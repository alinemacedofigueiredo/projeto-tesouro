import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pytest

from tesouro.graficos import detentores, estilo


# ---------------------------------------------------------------------------
# Aba 2.7: participacao relativa e variacao
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def part():
    return detentores.dados_participacao()


def test_a_participacao_de_junho_de_2026_bate_com_o_medido(part):
    # Conferido contra a pagina do RMD que a dona do projeto forneceu.
    assert round(part.loc["Inst. Financeiras", "hoje_pct"], 1) == 31.8
    assert round(part.loc["Fundos", "hoje_pct"], 1) == 22.0
    assert round(part.loc["Previd\u00eancia", "hoje_pct"], 1) == 22.5
    assert round(part.loc["N\u00e3o-residentes", "hoje_pct"], 1) == 10.0
    assert round(part.loc["Demais Grupos", "hoje_pct"], 1) == 13.8
    assert round(part["valor_milhoes"].sum() / 1000, 1) == 8920.7


def test_os_cinco_grupos_somam_100(part):
    assert len(part) == 5
    assert abs(part["hoje_pct"].sum() - 100) < 1e-9
    assert abs(part["ha12m_pct"].sum() - 100) < 1e-9


def test_a_variacao_de_12_meses_bate_com_o_medido(part):
    # Em pontos percentuais, contra jun/2025. A Previdencia perdeu 0,57 p.p. e as
    # Instituicoes Financeiras ganharam 0,46 -- o movimento do ano.
    assert round(part.loc["Previd\u00eancia", "var_pp"], 2) == -0.57
    assert round(part.loc["Inst. Financeiras", "var_pp"], 2) == 0.46
    assert round(part.loc["Fundos", "var_pp"], 2) == -0.14
    assert round(part.loc["N\u00e3o-residentes", "var_pp"], 2) == 0.11
    assert round(part.loc["Demais Grupos", "var_pp"], 2) == 0.13
    # A variacao e redistribuicao: a soma fecha em zero.
    assert abs(part["var_pp"].sum()) < 1e-9


def test_o_rotulo_perde_o_numero_da_nota_de_rodape(part):
    # O CSV grava "Instituicoes Financeiras 1", com o numero da nota do RMD colado
    # no nome. Nenhum indice pode carregar digito.
    for nome in part.index:
        assert not nome[-1].isdigit(), f"'{nome}' ainda tem o numero da nota"


# ---------------------------------------------------------------------------
# Aba 2.8: quem carrega cada papel
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def papel():
    return detentores.dados_por_papel()


def test_quem_carrega_cada_papel_bate_com_o_medido(papel):
    # Os quatro fatos que o grafico existe para mostrar: a LFT e de banco e fundo,
    # a NTN-B e da previdencia, e o estrangeiro esta na ponta prefixada.
    assert round(papel.loc["LFT", "Inst. Financeiras"], 1) == 36.5
    assert round(papel.loc["LFT", "Fundos"], 1) == 33.0
    assert round(papel.loc["NTN-B", "Previd\u00eancia"], 1) == 44.9
    assert round(papel.loc["NTN-F", "N\u00e3o-residente"], 1) == 41.8
    assert round(papel.loc["LTN", "N\u00e3o-residente"], 1) == 26.4


def test_cada_papel_soma_100_entre_os_detentores(papel):
    assert sorted(papel.index) == ["LFT", "LTN", "NTN-B", "NTN-F", "OUTROS"]
    assert (papel.sum(axis=1) - 100).abs().max() < 1e-9


# ---------------------------------------------------------------------------
# Aba 2.8: financeiro por detentor, oito paineis
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def fin():
    return detentores.dados_financeiro()


def test_o_financeiro_por_detentor_bate_com_o_medido(fin):
    u = fin.iloc[-1]
    assert round(u["Inst. Financeiras"] / 1000, 1) == 2833.5
    assert round(u["Previd\u00eancia"] / 1000, 1) == 2008.8
    assert round(u["Fundos"] / 1000, 1) == 1962.6
    assert round(u["Tesouro Direto"] / 1000, 1) == 262.5
    assert round(u.sum() / 1000, 1) == 8920.7
    # A 2.8 comeca em fev/2011, quatro anos depois da 2.7. As duas series nao sao
    # a mesma coisa e nao vao para o mesmo eixo.
    assert fin.index.min() == pd.Timestamp("2011-02-28")


def test_o_tesouro_direto_fica_por_ultimo_nos_paineis(fin):
    ordem = detentores.ordem_paineis(fin)
    assert len(ordem) == 8
    assert ordem[-1] == "Tesouro Direto"
    assert ordem[0] == "Inst. Financeiras"
    # Ordem de tamanho, com o Tesouro Direto forcado para o fim mesmo tendo mais
    # financeiro que o Governo (262,5 bi contra 245,5).
    assert ordem[-2] == "Governo"


def test_cada_painel_tem_escala_propria(fin):
    estilo.aplicar_estilo()
    fig = plt.figure(figsize=(13, 9))
    detentores.desenha_financeiro(detentores.dados_financeiro(janela=5), fig)
    topos = [round(ax.get_ylim()[1]) for ax in fig.axes]
    plt.close(fig)
    assert len(topos) == 8
    # Escala comum achataria sete dos oito: o maior detentor tem onze vezes o
    # menor. Se todos os topos forem iguais, a escala virou comum sem ninguem ver.
    assert len(set(topos)) >= 6


def test_o_rotulo_de_percentual_so_aparece_nas_fatias_de_10_ou_mais(papel):
    estilo.aplicar_estilo()
    fig = plt.figure(figsize=(13, 7))
    detentores.desenha_por_papel(papel, fig)
    escritos = []
    for ax in fig.axes:
        for t in ax.texts:
            texto = t.get_text().replace("%", "").replace(",", ".")
            try:
                escritos.append(float(texto))
            except ValueError:
                pass                      # titulo do painel, nao rotulo de fatia
    plt.close(fig)
    assert escritos, "nenhum rotulo de percentual foi desenhado"
    assert min(escritos) >= 10.0
    # E as fatias grandes tem de estar todas la: cinco papeis, e cada um tem pelo
    # menos duas fatias de 10% ou mais.
    assert len(escritos) == sum((papel >= 10).sum())


def test_a_paleta_cobre_os_oito_detentores_da_28(fin):
    for detentor in fin.columns:
        chave = detentores.CHAVE_COR[detentor]
        assert chave in estilo.COR, f"sem cor para '{detentor}'"
    # "Outros" ja e chave de cor de papel: o detentor entra com nome proprio para
    # nao sobrescrever o cinza dos papeis.
    assert detentores.CHAVE_COR["Outros"] == "Outros Detentores"
    assert estilo.COR["Outros Detentores"] != estilo.COR["Outros"]
