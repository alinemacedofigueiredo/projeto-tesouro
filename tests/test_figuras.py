from datetime import date

import pytest
from tesouro import dv, figuras

# O calendario e pedido SO QUANDO USADO -- ver tests/calendario_tardio.py.
# No topo do modulo ele quebrava a COLETA do pytest numa maquina sem
# data/raw/anbima/feriados_nacionais.xls, e com isso a suite inteira.
from calendario_tardio import CAL


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

        # A DATA ERA CRAVADA EM 2026-06-30 e anda todo RMD. Sai da fonte: o
        # painel de DV parte da data-base do RMD carregado.
        from tesouro import rolagem

        do_rmd, _ = rolagem.base_do_rmd()
        ultima_data = serie.index.max()
        assert ultima_data == do_rmd.date(), (
            f"a figura desenha ate {ultima_data} e o RMD carregado e de "
            f"{do_rmd.date()}")

        por_rotulo = {linha.get_label(): linha for linha in eixo.lines}
        # ydata[-1]: ultimo ponto de cada linha, na mesma ordem do eixo x
        # (serie.index, ordenado). Confere contra os mesmos ancoras do
        # teste acima, agora olhando o que foi de fato desenhado.
        # O QUE ESTE TESTE PROVA e que o DESENHO carrega o mesmo numero que o
        # dado -- ele existe para pegar a figura divergindo do CSV. Entao o
        # esperado sai da PROPRIA serie, e nao de constantes copiadas: assim
        # ele para de envelhecer e passa a pegar mais, porque compara os dois
        # lados em vez de comparar cada um contra um terceiro numero digitado.
        ultima = serie.loc[ultima_data]
        for rotulo in ("LTN", "NTN-F", "NTN-B"):
            assert por_rotulo[rotulo].get_ydata()[-1] == pytest.approx(
                float(ultima[rotulo]), abs=1e-6), rotulo
        assert por_rotulo["total"].get_ydata()[-1] == pytest.approx(
            float(ultima[list(("LTN", "NTN-F", "NTN-B"))].sum()), abs=1e-6)

        # E o nivel, medido em 04/09/2026 com a base em 31/07 -- e ele que pega
        # VNA fora de escala, que a igualdade acima nao pegaria (os dois lados
        # escalariam juntos).
        assert por_rotulo["total"].get_ydata()[-1] == pytest.approx(
            -1498.093988, abs=1e-5)

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
        # A DATA da frase tem de ser a do RMD carregado -- cravar um dia
        # fazia o teste quebrar todo RMD sem checar nada de novo. A cobertura
        # fica como medida: ela e uma fracao do estoque e nao ha, neste teste,
        # uma fonte independente dela para comparar.
        assert f"{do_rmd:%d/%m/%Y}" in textos, (
            f"a figura nao cita a data-base do RMD ({do_rmd:%d/%m/%Y})")
        # A COBERTURA CAIU 1,7 pp, de 44,8% para 43,1%, e isso e leitura e nao
        # ruido: o papel que venceu em 15/08 era NTN-B, ou seja, papel COBERTO
        # pelo DV01 -- sai do numerador e do denominador, e a fracao coberta
        # cai. Remedida em 07/10/2026. Fica como ancora de valor porque neste
        # teste nao ha fonte independente dela: compara-la com quem a calcula
        # seria circular.
        assert "43,1%" in textos
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
        # A CASCATA E UMA IDENTIDADE: a base mais o que vence mais o decay da
        # o alvo. Vale em qualquer mes, e e o que o grafico afirma.
        assert valores[0] + valores[1] + valores[2] == pytest.approx(
            valores[3], abs=1e-5), "a cascata nao fecha"
        # E os valores remedidos em 07/10/2026, com a base em 31/08.
        #
        # OS DOIS TERMOS DO MEIO ENCOLHERAM JUNTOS -- vence de 2,31 para 0,70 e
        # decay de 73,0 para 61,6 -- e pelo mesmo motivo: o que ia vencer dentro
        # da janela ate dez/26 era a NTN-B 15/08/2026, e ela JA venceu, entao
        # saiu da base em vez de vencer no meio do caminho.
        assert valores == pytest.approx(
            [-1498.093988, 0.700341, 61.641532, -1435.752114], abs=1e-5
        )

        barras = eixo.patches
        assert len(barras) == 4
        alturas = [b.get_height() for b in barras]
        assert alturas == pytest.approx(valores, abs=1e-5)

        assert "milh\u00f5es por bp" in eixo.get_ylabel()
        assert "Conta B" in eixo.get_title()

        textos = " ".join(t.get_text() for t in fig.texts)
        # A COBERTURA E A DATA VEM DO RESUMO, e nao de um texto cravado: a
        # frase da figura tem de repetir o que a conta apurou. Assim o teste
        # deixa de quebrar por RMD e passa a checar o que ele quer -- que a
        # figura e o resumo concordam.
        from tesouro.graficos import estilo

        assert estilo.num_br(resumo["cobertura"]["cobertos_pct"], 1) + "%" in textos
        assert f"{resumo['data_base']:%d/%m/%Y}" in textos
        # E a escala, remedida em 07/10/2026: a cobertura caiu para 43,1% com o
        # vencimento da NTN-B 15/08/2026, que era papel coberto pelo DV01.
        #
        # A DATA SAIU DAQUI. Ela ja e conferida duas linhas acima, contra
        # resumo["data_base"]; repetida cravada, envelhecia todo RMD sem checar
        # nada de novo.
        assert "43,1%" in textos
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
