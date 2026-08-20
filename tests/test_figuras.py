from datetime import date

import pytest
from tesouro import calendario, dv, figuras

CAL = calendario.padrao()


def test_usa_backend_sem_janela():
    import matplotlib
    assert matplotlib.get_backend().lower() == "agg"


# ---------------------------------------------------------------------------
# _serie_por_titulo: os dados que alimentam o grafico do sistema, testados
# contra os ancoras conhecidos de 30/06/2026 (nao derivados do proprio
# codigo sob teste -- ver docs/convencoes-dv.md e o painel de dv.py).
# ---------------------------------------------------------------------------

def test_serie_por_titulo_bate_com_as_ancoras_de_30_06_2026():
    serie = figuras._serie_por_titulo()
    linha = serie.loc[date(2026, 6, 30)]
    assert linha["LTN"] == pytest.approx(-198.535484, abs=1e-6)
    assert linha["NTN-F"] == pytest.approx(-177.755607, abs=1e-6)
    assert linha["NTN-B"] == pytest.approx(-1096.581570, abs=1e-6)
    assert linha.sum() == pytest.approx(-1472.872661, abs=1e-6)


# ---------------------------------------------------------------------------
# grafico_dv_do_sistema: verifica os artistas do matplotlib (linhas,
# rotulos, valores plotados), nao so a existencia do PNG -- um arquivo
# nao-vazio nao prova que os dados certos foram desenhados.
# ---------------------------------------------------------------------------

def test_figura_do_sistema_plota_ltn_ntnf_ntnb_e_total_com_valor_certo():
    fig, eixo, serie = figuras._figura_do_sistema()
    try:
        # linhas sem rotulo explicito (ex.: a linha do axhline(0)) ganham
        # do matplotlib um rotulo interno comecando com "_", que nao
        # entra na legenda -- filtradas aqui pelo mesmo motivo.
        rotulos = {linha.get_label() for linha in eixo.lines
                   if not linha.get_label().startswith("_")}
        assert rotulos == {"LTN", "NTN-F", "NTN-B", "total"}

        ultima_data = serie.index.max()
        assert ultima_data == date(2026, 6, 30)

        por_rotulo = {linha.get_label(): linha for linha in eixo.lines}
        # ydata[-1]: ultimo ponto de cada linha, na mesma ordem do eixo x
        # (serie.index, ordenado). Confere contra os mesmos ancoras do
        # teste acima, agora olhando o que foi de fato desenhado.
        assert por_rotulo["LTN"].get_ydata()[-1] == pytest.approx(-198.535484, abs=1e-6)
        assert por_rotulo["NTN-F"].get_ydata()[-1] == pytest.approx(-177.755607, abs=1e-6)
        assert por_rotulo["NTN-B"].get_ydata()[-1] == pytest.approx(-1096.581570, abs=1e-6)
        assert por_rotulo["total"].get_ydata()[-1] == pytest.approx(-1472.872661, abs=1e-6)

        # Unidade e conta precisam aparecer no proprio grafico, nao so no
        # relatorio -- e o que a usuaria ve antes de qualquer CSV. "\u00f5"
        # e "\u00e3" sao escapes Unicode (nao caracteres acentuados literais
        # no arquivo-fonte, que precisa continuar ASCII puro) para "milh\u00f5es"
        # e "n\u00e3o" -- ver docs/como-baixar.md e a Tarefa 9 sobre ASCII.
        assert "milh\u00f5es por bp" in eixo.get_ylabel()
        assert "resultado em dinheiro" in eixo.get_title()

        # Achado da revisao da Tarefa 9 (item 3): a asser\u00e7\u00e3o anterior aqui
        # era "'resultado em dinheiro' in textos or 'nao e resultado em
        # dinheiro' in eixo.get_title()" -- a segunda clausula do "or" e
        # sempre verdadeira (o titulo sempre tem essa frase), entao o teste
        # nunca forcava a nota de rodape a existir. Direto contra fig.texts,
        # com o percentual de verdade da data (nao uma string generica),
        # para a asser\u00e7\u00e3o falhar se a chamada de _nota_cobertura sumir do
        # fig.text() -- verificado a mao removendo a linha correspondente
        # em _figura_do_sistema e confirmando que este teste quebra.
        textos = " ".join(t.get_text() for t in fig.texts)
        assert "DV01 cobre 46,5% do estoque em 30/06/2026" in textos
    finally:
        import matplotlib.pyplot as plt
        plt.close(fig)


def test_grafico_do_sistema_grava_arquivo(tmp_path):
    alvo = tmp_path / "dv_sistema.png"
    saida = figuras.grafico_dv_do_sistema(alvo)
    assert saida == alvo
    assert saida.exists()
    assert saida.stat().st_size > 10000


# ---------------------------------------------------------------------------
# grafico_pontual: mesma logica -- confere os valores das quatro barras
# contra o resumo de dv.pontual(), com tolerancia apertada (banda larga
# ja deixou passar bug de 3,3x nesta branch). Desde a revisao da Tarefa 9
# (item 2), as barras sao uma cascata (bridge chart): "vence" e "decay"
# flutuam, cada uma comecando onde a anterior termina, para a soma
# dv_base + dv_que_vence + decay_sobreviventes = dv_alvo ficar visivel --
# quatro barras partindo todas do zero deixavam os dois termos do meio
# (~50x menores) quase invisiveis. b.get_height() continua sendo o delta
# de cada termo (nao o topo acumulado); quem muda e b.get_y(), o "pe" de
# cada barra, testado separadamente abaixo.
# ---------------------------------------------------------------------------

def test_figura_pontual_plota_as_quatro_barras_com_o_valor_do_resumo():
    resumo = dv.pontual(date(2026, 12, 31))
    fig, eixo, rotulos, valores = figuras._figura_pontual(resumo)
    try:
        assert rotulos == ["DV na base", "vence", "decay", "DV no alvo"]
        assert valores == pytest.approx(
            [-1472.872661, 5.248806, 86.540294, -1381.083561], abs=1e-5
        )

        barras = eixo.patches
        assert len(barras) == 4
        alturas = [b.get_height() for b in barras]
        assert alturas == pytest.approx(valores, abs=1e-5)

        assert "milh\u00f5es por bp" in eixo.get_ylabel()
        assert "Conta B" in eixo.get_title()

        textos = " ".join(t.get_text() for t in fig.texts)
        assert "DV01 cobre 46,5% do estoque em 30/06/2026" in textos
    finally:
        import matplotlib.pyplot as plt
        plt.close(fig)


def test_figura_pontual_e_uma_cascata_nao_quatro_barras_do_zero():
    """A barra 'vence' tem que comecar onde 'DV na base' termina, e 'decay'
    onde 'vence' termina -- e isso, nao so os deltas em si, que prova que
    dv_base + dv_que_vence + decay_sobreviventes = dv_alvo fica visivel no
    desenho (achado I2 da revisao). Os "pes" esperados sao calculados a
    partir dos proprios valores do resumo (ja conferidos contra os ancoras
    do brief no teste acima), nao da constante que o codigo sob teste usa
    internamente."""
    resumo = dv.pontual(date(2026, 12, 31))
    fig, eixo, rotulos, valores = figuras._figura_pontual(resumo)
    try:
        pes_esperados = [
            0,
            valores[0],
            valores[0] + valores[1],
            0,
        ]
        pes_reais = [b.get_y() for b in eixo.patches]
        assert pes_reais == pytest.approx(pes_esperados, abs=1e-5)

        # As duas barras de total ("DV na base", "DV no alvo") sao as
        # unicas que partem do zero -- as do meio flutuam.
        assert eixo.patches[0].get_y() == pytest.approx(0.0, abs=1e-9)
        assert eixo.patches[3].get_y() == pytest.approx(0.0, abs=1e-9)
        assert eixo.patches[1].get_y() != pytest.approx(0.0, abs=1e-6)
        assert eixo.patches[2].get_y() != pytest.approx(0.0, abs=1e-6)
    finally:
        import matplotlib.pyplot as plt
        plt.close(fig)


def test_grafico_pontual_grava_arquivo(tmp_path):
    r = dv.pontual(date(2027, 12, 31))
    alvo = tmp_path / "pontual.png"
    saida = figuras.grafico_pontual(r, alvo)
    assert saida == alvo
    assert saida.exists()
    assert saida.stat().st_size > 10000


# ---------------------------------------------------------------------------
# Cobertura: tem que vir da data de verdade, nunca de uma constante fixa
# -- achado da revisao da Tarefa 7 (46,6% impresso para qualquer data
# ficava 14 pontos errado em 2020). Comparar duas datas bem diferentes
# prova que a nota recalcula, em vez de repetir um numero gravado.
# ---------------------------------------------------------------------------

def test_nota_de_cobertura_usa_a_data_pedida_e_nao_uma_constante():
    nota_2026 = figuras._nota_cobertura(CAL, date(2026, 6, 30))
    nota_2020 = figuras._nota_cobertura(CAL, date(2020, 12, 31))

    assert "46,5%" in nota_2026
    assert "60,4%" in nota_2020
    assert nota_2026 != nota_2020
