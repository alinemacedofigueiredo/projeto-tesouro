"""A reta da media da janela nos graficos de dois eixos (emissao.py).

Ela entrou em 27/10/2026 para os e-mails de leilao: o rotulo do e-mail promete
"media dos 50 leiloes", e uma reta e o unico desenho que cumpre essa frase.

O QUE ESTES TESTES PRECISAM DEFENDER, e que nao e obvio:

  1. a reta e PLANA e da JANELA INTEIRA. Media movel passaria por qualquer
     verificacao ingenua de "existe uma linha nova" e diria outra coisa;
  2. ela e TRACEJADA e nao pontilhada. O pontilhado ja e da media MOVEL de
     desenha_lft, e os dois graficos aparecem no mesmo e-mail -- duas medias
     diferentes com o mesmo traco seria o "plausivel e errado" de sempre;
  3. ela NAO APARECE por padrao. As paginas do painel ja estao gravadas e nao
     podem mudar por causa de um parametro novo.

Os dados de teste sao montados para que media, ultimo valor e media movel sejam
NUMEROS DIFERENTES -- senao o teste passaria com qualquer uma das tres.
"""
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from tesouro.graficos import emissao  # noqa: E402


# DV que sobe sempre: a media da janela (2.500) nao e o ultimo valor (4.000),
# nao e o primeiro e nao e nenhuma media movel do fim da serie.
_DV_MILHOES = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
_FINANCEIRO = [5000.0, 5200.0, 4800.0, 5100.0, 5300.0, 4900.0, 5000.0]


def _dados(dv=None):
    dv = _DV_MILHOES if dv is None else dv
    indice = pd.to_datetime(
        ["2026-09-%02d" % d for d in (1, 8, 15, 22, 29)] +
        ["2026-10-06", "2026-10-13"])[:len(dv)]
    d = pd.DataFrame({"financeiro_milhoes": _FINANCEIRO[:len(dv)],
                      "dv_milhoes": dv,
                      "estagio": ["aceito"] * len(dv)}, index=indice)
    d.index.name = "data_leilao"
    return d


def _dados_empilhado():
    d = _dados()
    d["LTN"] = d["financeiro_milhoes"] * 0.6
    d["NTN-F"] = d["financeiro_milhoes"] * 0.4
    return d


def _eixo_do_dv(fig, ax):
    """O twinx que desenha_dois_eixos criou para o DV."""
    gemeos = [e for e in fig.axes if e is not ax]
    assert gemeos, "a funcao nao criou o eixo do DV"
    return gemeos[-1]


def _retas_planas(eixo):
    """As linhas horizontais do eixo, como (valor, estilo do traco).

    O axhline do matplotlib guarda y constante; a linha do DV varia. Filtrar
    por "y e constante" acha a reta sem depender da ordem em que foi desenhada.
    """
    achadas = []
    for linha in eixo.get_lines():
        y = np.asarray(linha.get_ydata(), dtype=float)
        if len(y) and np.allclose(y, y[0]):
            achadas.append((float(y[0]), linha.get_linestyle(),
                            linha.get_label()))
    return achadas


def test_a_reta_NAO_APARECE_por_padrao():
    """As paginas ja gravadas nao podem ganhar uma linha sem pedir."""
    fig = plt.figure()
    ax = fig.subplots()
    emissao.desenha_dois_eixos(_dados(), ax, "sem media")
    assert _retas_planas(_eixo_do_dv(fig, ax)) == []
    plt.close(fig)


def test_a_reta_esta_na_MEDIA_DA_JANELA_e_nao_no_ultimo_nem_na_movel():
    fig = plt.figure()
    ax = fig.subplots()
    emissao.desenha_dois_eixos(_dados(), ax, "com media", media=True)

    planas = _retas_planas(_eixo_do_dv(fig, ax))
    assert len(planas) == 1, "esperava uma reta so, achei %d" % len(planas)
    valor = planas[0][0]

    em_mil = [v * 1000 for v in _DV_MILHOES]
    esperado = sum(em_mil) / len(em_mil)
    assert valor == pytest.approx(esperado), (
        "a reta nao esta na media da janela")

    # As tres respostas erradas que passariam por "existe uma reta".
    assert valor != pytest.approx(em_mil[-1]), "desenhou o ultimo valor"
    assert valor != pytest.approx(max(em_mil)), "desenhou o maximo"
    movel = sum(em_mil[-3:]) / 3
    assert valor != pytest.approx(movel), "desenhou media movel de 3"
    plt.close(fig)


def test_a_reta_e_TRACEJADA_para_nao_virar_a_movel_pontilhada_da_LFT():
    fig = plt.figure()
    ax = fig.subplots()
    emissao.desenha_dois_eixos(_dados(), ax, "com media", media=True)
    _valor, traco, _rotulo = _retas_planas(_eixo_do_dv(fig, ax))[0]
    assert traco not in ("-", "solid"), "reta continua se confunde com o DV"
    assert traco not in (":", "dotted"), (
        "pontilhado e da media MOVEL da LFT; as duas aparecem no mesmo e-mail")
    plt.close(fig)


def test_a_reta_se_ANUNCIA_na_legenda_com_o_tamanho_da_janela():
    fig = plt.figure()
    ax = fig.subplots()
    emissao.desenha_dois_eixos(_dados(), ax, "com media", media=True)
    rotulos = [t.get_text() for t in ax.get_legend().get_texts()]
    assert any("m\u00e9dia" in r for r in rotulos), (
        "reta sem rotulo na legenda: %s" % rotulos)
    assert any(str(len(_DV_MILHOES)) in r for r in rotulos if
               "m\u00e9dia" in r), (
        "a legenda nao diz de quantos leiloes e a media: %s" % rotulos)
    plt.close(fig)


def test_a_reta_entra_tambem_no_EMPILHADO():
    """O e-mail de prefixado usa a funcao empilhada, e nao a outra."""
    fig = plt.figure()
    ax = fig.subplots()
    emissao.desenha_dois_eixos_empilhado(
        _dados_empilhado(), ax, "com media", media=True)

    planas = _retas_planas(_eixo_do_dv(fig, ax))
    assert len(planas) == 1
    em_mil = [v * 1000 for v in _DV_MILHOES]
    assert planas[0][0] == pytest.approx(sum(em_mil) / len(em_mil))
    plt.close(fig)


def test_o_EMPILHADO_tambem_fica_sem_reta_por_padrao():
    fig = plt.figure()
    ax = fig.subplots()
    emissao.desenha_dois_eixos_empilhado(_dados_empilhado(), ax, "sem media")
    assert _retas_planas(_eixo_do_dv(fig, ax)) == []
    plt.close(fig)


def test_recorte_SEM_DV_NENHUM_desenha_em_vez_de_levantar():
    """Regressao do NameError achado em 27/10/2026.

    O galho de "nenhum DV na serie" dizia 'elif series != "dv"', e 'series' nao
    existe nesta funcao -- veio copiado de desenha_acumulado. Levantava
    NameError em vez de desenhar. Nunca apareceu porque o unico recorte sem DV
    e a LFT, que tem funcao propria; o e-mail de leilao passou a chamar esta
    funcao com recortes novos.
    """
    sem_dv = _dados()
    sem_dv["dv_milhoes"] = np.nan
    fig = plt.figure()
    ax = fig.subplots()
    emissao.desenha_dois_eixos(sem_dv, ax, "sem DV nenhum")
    assert ax.get_ylim()[1] > 0, "desenhou, mas sem escala no eixo"
    plt.close(fig)
