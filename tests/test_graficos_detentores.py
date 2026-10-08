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


def test_as_colunas_sao_os_anos_fechados_mais_os_dois_ultimos_meses(part):
    # O formato da pagina 7 do RMD, pedido pela dona do projeto em 19/08/2026.
    #
    # OS DOIS ULTIMOS MESES ANDAM A CADA RMD -- eram mai-26 e jun-26, hoje sao
    # jun-26 e jul-26. Cravar os rotulos quebrava todo mes sem proteger o
    # formato, que e o assunto do teste: seis anos fechados seguidos de dois
    # meses. A FORMA fica travada; os nomes saem do dado.
    anos = [r for r in part.index if r.isdigit()]
    meses = [r for r in part.index if not r.isdigit()]
    assert len(anos) == 6 and len(meses) == 2, list(part.index)
    assert anos == sorted(anos), "os anos fechados fora de ordem"
    assert [int(a) for a in anos] == list(range(int(anos[0]),
                                                int(anos[0]) + 6)), (
        "os seis anos nao sao consecutivos")
    for m in meses:
        assert "-" in m and len(m) == 6, f"rotulo de mes fora do formato: {m}"
    assert list(part.columns) == detentores.ORDEM_GRUPOS


def test_a_participacao_dos_DOIS_ULTIMOS_MESES_bate_com_o_anexo(part):
    # O NOME DIZIA "junho" e os dois meses andam a cada RMD. Aba 2.7 do anexo de
    # julho -- o mes da base e o anterior, pegos pela posicao e nao pelo rotulo.
    ultimo, anterior = part.index[-1], part.index[-2]
    assert round(part.loc[ultimo, "Inst. Financeiras"], 1) == 31.2
    assert round(part.loc[ultimo, "Fundos"], 1) == 22.5
    assert round(part.loc[ultimo, "Previd\u00eancia"], 1) == 22.6
    assert round(part.loc[ultimo, "N\u00e3o-residentes"], 1) == 9.9
    assert round(part.loc[ultimo, "Demais Grupos"], 1) == 13.7
    assert round(part.loc[anterior, "Inst. Financeiras"], 1) == 31.3
    assert round(part.loc[anterior, "Fundos"], 1) == 22.2


def test_toda_coluna_soma_100(part):
    assert len(part) == 8
    assert (part.sum(axis=1) - 100).abs().max() < 1e-9


def test_a_variacao_vai_em_reais_e_bate_com_a_pagina_do_rmd():
    # A pagina traz os tres horizontes em R$ bi. "No ano" e "no mes" batem na casa
    # decimal para os quatro; a de 12 meses diverge para tres deles, e a
    # divergencia esta documentada em tests/test_conferencia_detentores.py.
    v = detentores.dados_variacao() / 1000
    assert list(v.columns) == ["em 12 meses", "no ano", "no m\u00eas"]
    assert list(v.index) == detentores.PRINCIPAIS

    # Aba 2.7 do anexo de julho, em R$ bilhoes. REPARE NOS SINAIS: no mes, as
    # Instituicoes Financeiras e os Nao-residentes REDUZIRAM posicao (-28,5 e
    # -8,8), enquanto Fundos e Previdencia aumentaram. Em junho os quatro eram
    # positivos.
    #
    # REMEDIDO PARA AGOSTO em 07/10/2026. Os sinais do MES mudaram de grupo: em
    # agosto quem reduziu foi Inst. Financeiras (-12,9) e Previdencia (-9,8),
    # e quem aumentou foi Fundos (+25,1) e Nao-residentes (+7,2). O mes do
    # vencimento da NTN-B mexeu com todo mundo.
    assert round(v.loc["Inst. Financeiras", "no ano"], 1) == 59.7
    assert round(v.loc["Inst. Financeiras", "no m\u00eas"], 1) == -12.9
    assert round(v.loc["Fundos", "no ano"], 1) == 286.9
    assert round(v.loc["Previd\u00eancia", "no ano"], 1) == 133.2
    assert round(v.loc["N\u00e3o-residentes", "em 12 meses"], 1) == 114.8


def test_a_variacao_falha_alto_se_faltar_o_mes_de_referencia(monkeypatch):
    # Calcular contra o mes vizinho mais proximo daria numero plausivel e errado.
    real = detentores._estoque_por_grupo()

    def sem_dezembro():
        return real.drop(index=pd.Timestamp("2025-12-31"))

    monkeypatch.setattr(detentores, "_estoque_por_grupo", sem_dezembro)
    with pytest.raises(LookupError) as erro:
        detentores.dados_variacao()
    assert "no ano" in str(erro.value)


def test_o_rotulo_perde_o_numero_da_nota_de_rodape(part):
    # O CSV grava "Instituicoes Financeiras 1", com o numero da nota do RMD colado
    # no nome. Nenhum rotulo de grupo pode carregar digito.
    for nome in part.columns:
        assert not nome[-1].isdigit(), f"'{nome}' ainda tem o numero da nota"


def test_a_quebra_por_papel_soma_o_estoque_do_papel():
    # A quebra de um papel entre os oito detentores tem de somar o estoque
    # daquele papel: 4.896,6 bi de LFT em ago/26 (aba 2.8 do anexo).
    # Remedido em 07/10/2026 -- era 4.744,1 em julho.
    lft = detentores.dados_financeiro_do_papel("LFT")
    assert round(lft.iloc[-1].sum() / 1000, 1) == 4896.6
    assert len(lft.columns) == 8
    assert round(lft.iloc[-1]["Inst. Financeiras"] / 1000, 1) == 1834.8

    ntnb = detentores.dados_financeiro_do_papel("NTN-B")
    # 2.330,4 -> 2.070,1 com o vencimento da NTN-B 15/08/2026 (258,2 bi de
    # principal). Conferido: o anexo diz o mesmo, e a serie de julho nao foi
    # revisada entre os dois anexos.
    assert round(ntnb.iloc[-1].sum() / 1000, 1) == 2070.1
    # A Previdencia carrega quase metade da NTN-B, e e o fato do papel. SUBIU de
    # 44,8 para 48,3 porque o papel que venceu era distribuido e o que sobrou e
    # mais concentrado nela -- concentracao por saida, e nao por compra.
    assert round(ntnb.iloc[-1]["Previd\u00eancia"] / ntnb.iloc[-1].sum() * 100, 1) == 48.3


def test_papel_que_nao_existe_falha_alto():
    with pytest.raises(LookupError) as erro:
        detentores.dados_financeiro_do_papel("NTN-Z")
    assert "NTN-Z" in str(erro.value)


# ---------------------------------------------------------------------------
# Aba 2.8: quem carrega cada papel
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def papel():
    return detentores.dados_por_papel()


def test_quem_carrega_cada_papel_bate_com_o_medido(papel):
    # Os quatro fatos que o grafico existe para mostrar: a LFT e de banco e fundo,
    # a NTN-B e da previdencia, e o estrangeiro esta na ponta prefixada.
    # Remedido para agosto. A NTN-B na previdencia subiu de 44,8 para 48,3 --
    # tres pontos e meio num mes, o maior movimento dos quatro.
    assert round(papel.loc["LFT", "Inst. Financeiras"], 1) == 37.5
    assert round(papel.loc["LFT", "Fundos"], 1) == 32.3
    assert round(papel.loc["NTN-B", "Previd\u00eancia"], 1) == 48.3
    assert round(papel.loc["NTN-F", "N\u00e3o-residente"], 1) == 40.9
    assert round(papel.loc["LTN", "N\u00e3o-residente"], 1) == 28.8


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
    assert round(u["Inst. Financeiras"] / 1000, 1) == 2792.1
    assert round(u["Previd\u00eancia"] / 1000, 1) == 2024.4
    assert round(u["Fundos"] / 1000, 1) == 2014.6
    assert round(u["Tesouro Direto"] / 1000, 1) == 272.0
    # A soma bate com o estoque total da DPF do mesmo anexo (aba 2.4): 8.948,7
    # e o total da 2.8, que exclui o que a 2.4 chama de fora do detalhe.
    assert round(u.sum() / 1000, 1) == 8944.5
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
