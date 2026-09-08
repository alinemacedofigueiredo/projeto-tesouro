"""Cruza os detentores contra a pagina de detentores do RMD de jul/26.

A transcricao esta em referencia/detentores_pagina_rmd.csv. A de jun/26 veio de
uma foto que ela forneceu em 19/08/2026; a de jul/26 saiu do PDF que ela salvou
em 04/09/2026 (data/raw/rmd, a Apresentacao). Nenhum grafico le aquele arquivo: ele
existe so para este cruzamento.

O que estes testes travam nao e "os dois batem" -- eles NAO batem em toda parte.
Eles travam EXATAMENTE ONDE batem e onde nao, que e a unica forma de a divergencia
continuar visivel em vez de virar lenda.
"""
import pandas as pd
import pytest

from tesouro import config
from tesouro.graficos import detentores


@pytest.fixture(scope="module")
def pagina():
    caminho = config.RAIZ / "referencia" / "detentores_pagina_rmd.csv"
    return pd.read_csv(caminho)


@pytest.fixture(scope="module")
def nosso_participacao():
    return detentores.dados_participacao()


@pytest.fixture(scope="module")
def nossa_variacao():
    return detentores.dados_variacao() / 1000


def test_a_transcricao_tem_a_pagina_inteira(pagina):
    part = pagina[pagina["painel"] == "participacao"]
    var = pagina[pagina["painel"] == "variacao"]
    assert len(part) == 40, "oito colunas vezes cinco grupos"
    assert len(var) == 12, "quatro grupos vezes tres horizontes"
    # Toda coluna do painel de cima soma 100 na propria pagina, com o
    # arredondamento de uma casa que ela imprime.
    for coluna, g in part.groupby("coluna"):
        assert abs(g["valor"].sum() - 100) <= 0.15, coluna


def test_a_participacao_bate_exatamente_nos_tres_pontos_recentes(
        pagina, nosso_participacao):
    # 2025, mai-26 e jun-26: os tres batem na casa decimal para os cinco grupos.
    part = pagina[pagina["painel"] == "participacao"]
    for coluna in ("2025", "mai-26", "jun-26"):
        for _, linha in part[part["coluna"] == coluna].iterrows():
            nosso = nosso_participacao.loc[coluna, linha["grupo"]]
            assert abs(nosso - linha["valor"]) < 0.05, \
                f"{coluna}/{linha['grupo']}: nosso {nosso:.2f} x pagina {linha['valor']}"


def test_a_participacao_diverge_pouco_nos_anos_de_2020_a_2024(
        pagina, nosso_participacao):
    # A divergencia que a spec ja registrava, agora medida: ela existe SO nos anos
    # fechados de 2020 a 2024, e concentra-se em Instituicoes Financeiras (ate 0,73
    # p.p.) e Fundos (0,58). Previdencia e Nao-residentes praticamente nao se movem.
    # O nosso numero foi verificado contra a celula crua da aba 2.7 e e fiel ao
    # anexo; a pagina e outra fonte.
    part = pagina[pagina["painel"] == "participacao"]
    piores = {}
    for coluna in ("2020", "2021", "2022", "2023", "2024"):
        for _, linha in part[part["coluna"] == coluna].iterrows():
            nosso = nosso_participacao.loc[coluna, linha["grupo"]]
            diferenca = abs(nosso - linha["valor"])
            piores[linha["grupo"]] = max(piores.get(linha["grupo"], 0), diferenca)

    assert max(piores.values()) < 0.8, piores
    # E existe: se um dia zerar, alguem corrigiu a fonte e o comentario acima
    # precisa mudar.
    assert round(piores["Inst. Financeiras"], 2) == 0.73
    assert round(piores["Fundos"], 2) == 0.58
    # Os dois que quase nao se movem sao os mesmos dois do painel de variacao em
    # que a base de doze meses tambem quase nao se move.
    assert piores["Previd\u00eancia"] < 0.06
    assert piores["N\u00e3o-residentes"] < 0.06


def test_a_variacao_no_ano_e_no_mes_batem_na_casa_decimal(pagina, nossa_variacao):
    # Os dois horizontes curtos batem para os quatro grupos. Isso prova que jun/26,
    # mai/26 e dez/25 sao identicos nas duas fontes.
    var = pagina[pagina["painel"] == "variacao"]
    for horizonte in ("no ano", "no m\u00eas"):
        for _, linha in var[var["coluna"] == horizonte].iterrows():
            nosso = nossa_variacao.loc[linha["grupo"], horizonte]
            assert abs(nosso - linha["valor"]) < 0.15, \
                f"{linha['grupo']}/{horizonte}: nosso {nosso:.1f} x {linha['valor']}"


def test_so_a_variacao_de_12_meses_diverge_e_so_em_DOIS_grupos(
        pagina, nossa_variacao):
    # O achado. Como "no ano" e "no mes" batem EXATO nos quatro grupos, a
    # divergencia esta na BASE de doze meses: o jul/2025 que a pagina usou nao e
    # o jul/2025 do anexo que temos.
    #
    # O PADRAO MUDOU DE JUNHO PARA JULHO, e mudou para melhor:
    #
    #                    contra a pagina de jun/26   contra a de jul/26
    #     Inst. Fin.            +41,8                     +42,5
    #     Fundos               +125,6                     -28,9
    #     Previdencia          -154,1                      0,0  <- passou a bater
    #     Nao-residentes          0,0                      0,0
    #     soma                  +13,4                     +13,6
    #
    # Em junho eram TRES grupos divergindo, com valores grandes se compensando.
    # Agora sao DOIS, trocando entre si -- e a soma ficou praticamente igual.
    # Isso reforca a leitura de reclassificacao ENTRE grupos aplicada ao anexo
    # depois de a pagina antiga ter sido publicada: a parte que se compensava
    # migrou, e o que sobra e um nivel de ~13,5 bi que nao se cancela.
    #
    # Nao da para confirmar sem um anexo de jul/2025, e nao temos: data/raw/rmd
    # guarda so junho e julho de 2026. Documentado, nao perseguido.
    var = pagina[pagina["painel"] == "variacao"]
    doze = var[var["coluna"] == "em 12 meses"].set_index("grupo")["valor"]

    diferencas = {g: nossa_variacao.loc[g, "em 12 meses"] - doze[g]
                  for g in doze.index}

    assert abs(diferencas["N\u00e3o-residentes"]) < 0.15, "este bate"
    assert abs(diferencas["Previd\u00eancia"]) < 0.15, "este passou a bater"
    assert round(diferencas["Inst. Financeiras"], 1) == 42.5
    assert round(diferencas["Fundos"], 1) == -28.9
    assert round(sum(diferencas.values()), 1) == 13.6

    # E OS DOIS QUE DIVERGEM TROCAM DE SINAL -- e o que sustenta a leitura de
    # reclassificacao. Se um dia os dois forem para o mesmo lado, a explicacao
    # muda e este teste tem de cair junto com ela.
    assert (diferencas["Inst. Financeiras"] > 0) != (diferencas["Fundos"] > 0), (
        "os dois grupos que divergem foram para o mesmo lado; a leitura de "
        "reclassificacao entre eles nao se sustenta mais")
