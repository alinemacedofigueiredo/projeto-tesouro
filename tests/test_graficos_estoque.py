import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pytest

from tesouro.graficos import estilo, estoque, paf


# ---------------------------------------------------------------------------
# A banda do PAF
# ---------------------------------------------------------------------------

def test_a_banda_de_2026_do_prefixado_bate_com_a_planilha_do_paf():
    b = paf.bandas("prefixado_pct")
    assert b.loc[2026, "minimo"] == 21.0
    assert b.loc[2026, "maximo"] == 25.0
    # Da planilha do PAF sai a banda, e so: o que aconteceu vem do nosso dado.
    assert "realizado" not in b.columns


def test_a_revisao_de_2025_vira_a_banda_vigente_e_guarda_a_original():
    # O estoque de 2025 foi revisado de 8.100-8.500 para 8.500-8.800. A banda
    # vigente e a revisada, porque e a que valia no fechamento; a original vai por
    # baixo em linha pontilhada, para a mudanca de meta ficar visivel.
    b = paf.bandas("estoque_bilhoes")
    assert b.loc[2025, "minimo"] == 8500.0
    assert b.loc[2025, "maximo"] == 8800.0
    assert b.loc[2025, "minimo_original"] == 8100.0
    assert b.loc[2025, "maximo_original"] == 8500.0
    # Ano sem revisao nao tem original separada.
    assert pd.isna(b.loc[2023, "minimo_original"])


def test_os_oito_anos_revisados_estao_todos_presentes():
    # A aba 5.7 do RMD guarda so quatro revisoes; a planilha do PAF guarda oito.
    # E por isso que a fonte da banda e referencia/paf_bandas.csv e nao a 5.7.
    b = paf.bandas("prefixado_pct")
    revisados = sorted(b.index[b["minimo_original"].notna()])
    assert revisados == [2008, 2015, 2016, 2018, 2020, 2021, 2024, 2025]


def test_o_paf_falha_alto_quando_a_referencia_esta_quebrada(tmp_path):
    # Pre-requisito de execucao: banda quebrada derruba, nunca desenha errado.
    # O percentual escrito como fracao (0,21 em vez de 21) e o erro que um
    # limiar de plausibilidade nao pega -- 0,21 esta entre 0 e 100.
    ruim = tmp_path / "paf_bandas.csv"
    ruim.write_text(
        "ano,versao,indicador,minimo,maximo,realizado\n"
        "2026,original,prefixado_pct,0.21,0.25,\n",
        encoding="ascii",
    )
    with pytest.raises(ValueError) as erro:
        paf.bandas("prefixado_pct", caminho=ruim)
    assert "paf_bandas.csv" in str(erro.value)


# ---------------------------------------------------------------------------
# A composicao
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def comp():
    return estoque.dados_composicao()


def test_a_composicao_de_junho_de_2026_bate_com_o_medido(comp):
    # Conferido contra a pagina do RMD que a dona do projeto forneceu.
    u = comp.iloc[-1]
    assert round(u["Prefixado"], 1) == 21.0
    assert round(u["\u00cdndice Pre\u00e7os"], 1) == 25.9
    assert round(u["Taxa Flutuante"], 1) == 49.3
    assert round(u["C\u00e2mbio"], 1) == 3.7
    assert round(u["estoque_milhoes"] / 1000, 1) == 9268.4


def test_cada_mes_da_composicao_soma_100(comp):
    cols = [c for c in comp.columns if c != "estoque_milhoes"]
    assert len(comp) == 307
    assert (comp[cols].sum(axis=1) - 100).abs().max() < 1e-9


def test_o_cambio_cai_do_pico_de_51_para_37(comp):
    # O fato central da gestao da divida brasileira, e a razao de a serie completa
    # ser o padrao: numa janela de 5 anos ele nao aparece.
    cam = comp["C\u00e2mbio"]
    assert round(cam.max(), 1) == 51.0
    assert cam.idxmax() == pd.Timestamp("2002-09-30")
    assert round(cam.iloc[-1], 2) == 3.74


def test_a_area_de_100_por_cento_empilha_as_cinco_faixas():
    # O par do grafico de linha: um responde onde estamos contra a meta, o outro de
    # que a divida e feita. A faixa "Demais" entra AQUI e nao la -- numa area de
    # 100% ela tem de entrar, ou a soma nao fecha.
    estilo.aplicar_estilo()
    fig, ax = plt.subplots(figsize=(13, 6))
    dados = estoque.dados_composicao()
    estoque.desenha_composicao_100(dados, ax)
    faixas = list(ax.collections)
    rotulos = [texto.get_text() for texto in ax.texts]
    limites = ax.get_ylim()
    plt.close(fig)

    assert len(faixas) == 5, "uma faixa por indexador, com Demais"
    assert limites == (0, 100)
    # Os valores do ultimo mes escritos na ponta de cada faixa que cabe.
    for esperado in ("21,0", "25,9", "49,3"):
        assert esperado in rotulos
    # E o pico do cambio dito com todas as letras.
    assert any("51,0" in r for r in rotulos)


def test_a_seta_do_pico_aponta_para_dentro_da_faixa_do_cambio():
    # A faixa do cambio e a QUARTA da pilha: em set/2002 ela mora entre 74 e 100,
    # nao entre 0 e 51. Apontar para a altura do valor poria a seta dentro da faixa
    # do prefixado, e a seta continuaria "parecendo certa".
    estilo.aplicar_estilo()
    fig, ax = plt.subplots(figsize=(13, 6))
    dados = estoque.dados_composicao()
    estoque.desenha_composicao_100(dados, ax)
    seta = [a for a in ax.texts if "pico" in a.get_text()][0]
    _, altura = seta.xy
    plt.close(fig)

    pico = pd.Timestamp("2002-09-30")
    abaixo = (dados.loc[pico, "Prefixado"] + dados.loc[pico, "\u00cdndice Pre\u00e7os"]
              + dados.loc[pico, "Taxa Flutuante"])
    assert abaixo < altura < abaixo + dados.loc[pico, "C\u00e2mbio"]
    assert altura > 70, "a faixa do cambio no pico mora acima de 70%"


def test_o_desenho_da_composicao_traz_as_quatro_linhas_e_os_rotulos():
    # Os dois testes de banda contam artistas da BANDA. Apagando o bloco que desenha
    # as quatro linhas e escreve os quatro rotulos, os dois continuavam verdes -- o
    # grafico principal do Estoque podia virar um quadro de bandas vazias sem nada
    # ficar vermelho. Medido na revisao de 19/08/2026.
    estilo.aplicar_estilo()
    fig, ax = plt.subplots(figsize=(13, 6))
    dados = estoque.dados_composicao()
    bandas = {k: paf.bandas(k) for k in paf.COMPOSICAO}
    estoque.desenha_composicao(dados, bandas, ax)
    solidas = [l for l in ax.lines if l.get_linestyle() == "-"]
    nomes = [l.get_label() for l in solidas]
    rotulos = [texto.get_text() for texto in ax.texts]
    plt.close(fig)

    assert len(solidas) == 4, "uma linha por indexador que particiona a divida"
    # A decisao de desenho da spec: "Demais" entra no empilhado e NAO neste.
    assert "Demais" not in nomes
    assert set(nomes) == {"Prefixado", "\u00cdndice Pre\u00e7os", "Taxa Flutuante",
                          "C\u00e2mbio"}
    # E a figura carrega as mesmas ancoras que dados_composicao ja tem.
    for esperado in ("21,0", "25,9", "49,3", "3,7"):
        assert esperado in rotulos


def test_o_desenho_traz_a_banda_de_cada_ano_visivel():
    estilo.aplicar_estilo()
    fig, ax = plt.subplots(figsize=(13, 6))
    dados = estoque.dados_composicao(janela=5)
    bandas = {k: paf.bandas(k) for k in paf.COMPOSICAO}
    estoque.desenha_composicao(dados, bandas, ax)
    faixas = list(ax.collections)
    plt.close(fig)
    # Seis anos visiveis (2021 a 2026) vezes quatro indexadores.
    assert len(faixas) == 24


def test_o_desenho_marca_a_banda_original_dos_anos_revisados():
    estilo.aplicar_estilo()
    fig, ax = plt.subplots(figsize=(13, 6))
    dados = estoque.dados_composicao()
    bandas = {k: paf.bandas(k) for k in paf.COMPOSICAO}
    estoque.desenha_composicao(dados, bandas, ax)
    finas = [l for l in ax.lines if l.get_linestyle() == ":"]
    plt.close(fig)
    # Oito anos revisados, quatro indexadores, duas linhas cada (piso e teto).
    assert len(finas) == 64


# ---------------------------------------------------------------------------
# O total da divida: interna, externa e a banda do PAF.
# ---------------------------------------------------------------------------

def test_o_total_e_A_SERIE_QUE_O_PAF_MIRA_e_nao_outra():
    # A ESCOLHA QUE PODE ERRAR O GRAFICO INTEIRO. Sao quatro niveis no CSV, e o que
    # o PAF mira e "Estoque da DPF em Mercado" -- que NAO inclui a carteira do Banco
    # Central. Com ela dentro, a divida sairia 32% maior e a banda pareceria
    # estourada todo ano.
    #
    # A prova nao e um argumento: a coluna "realizado" do paf_bandas.csv e o numero
    # que o proprio Tesouro publicou para cada ano, e ele bate com o nosso dezembro.
    import pandas as pd

    from tesouro import config, valida_referencia

    d = estoque.dados_estoque_total()
    ref = pd.read_csv(valida_referencia.caminho_paf())
    ref = ref[(ref["indicador"] == "estoque_bilhoes")
              & (ref["versao"] == "original")].set_index("ano")["realizado"]

    conferidos = 0
    for ano, publicado in ref.dropna().items():
        dez = d[(d.index.year == ano) & (d.index.month == 12)]
        if dez.empty or ano == 2003:   # 2003 e numero antigo, republicado depois
            continue
        nosso = dez["total"].iloc[0] / 1000
        assert abs(nosso - publicado) / publicado < 0.001, (
            f"{ano}: nosso {nosso:.1f} bi contra {publicado:.1f} do PAF")
        conferidos += 1
    assert conferidos >= 20, f"so {conferidos} anos conferidos"


def test_a_carteira_do_banco_central_fica_de_fora():
    import pandas as pd

    from tesouro import config

    d = estoque.dados_estoque_total()
    e = pd.read_csv(config.PROCESSED_DIR / "estoque_dpf.csv",
                    parse_dates=["data"])
    bacen = e[(e["nivel"] == "DPMFi em poder do Banco Central")
              & e["entidade"].isna() & e["titulo"].isna()]
    ultimo = bacen.set_index("data")["valor_milhoes"].iloc[-1]
    assert ultimo > 2_000_000, "a carteira do Bacen encolheu muito no dado"
    # Se ela estivesse somada, o total seria pelo menos 25% maior.
    assert d["total"].iloc[-1] < d["total"].iloc[-1] + ultimo * 0.9


def test_o_total_e_a_soma_da_interna_com_a_externa_em_TODO_mes():
    d = estoque.dados_estoque_total()
    dif = (d["DPMFi"] + d["DPFe"] - d["total"]).abs()
    assert len(d) > 300
    assert dif.max() < 0.01, f"maior divergencia: {dif.max()} milhoes"


def test_a_banda_e_desenhada_em_BILHOES_como_o_eixo():
    # A PRIMEIRA VERSAO MULTIPLICAVA POR 1000 e punha a faixa em 9,7 milhoes de
    # bilhoes: ela caia fora da figura e simplesmente nao aparecia. O teste confere
    # que a faixa desenhada cabe no eixo, que e o que o olho conferiu.
    fig = plt.figure(figsize=(13, 6.6))
    dados = estoque.dados_estoque_total()
    banda = paf.bandas("estoque_bilhoes")
    estoque.desenha_estoque_total(dados, banda, fig)
    cima = fig.axes[0]
    faixas = [c for c in cima.collections if c.get_paths()]
    assert faixas, "nenhuma banda desenhada"
    topo_do_eixo = cima.get_ylim()[1]
    for faixa in faixas:
        alturas = [p.vertices[:, 1].max() for p in faixa.get_paths()]
        assert max(alturas) <= topo_do_eixo, (
            f"banda em {max(alturas):.0f} contra teto do eixo {topo_do_eixo:.0f}")
    # E a banda de 2026 esta de fato dentro do quadro: 9.700 a 10.300.
    assert topo_do_eixo >= 10300
    plt.close(fig)


def test_sao_DOIS_PAINEIS_e_a_externa_tem_o_de_baixo():
    # Um eixo so nao serve: a externa e 3,8% do total e vira um fio no chao. E um
    # SEGUNDO EIXO no mesmo painel foi pior -- a linha da externa passava por cima
    # da do total e se lia como se a externa fosse a maior das tres.
    fig = plt.figure(figsize=(13, 6.6))
    estoque.desenha_estoque_total(estoque.dados_estoque_total(),
                                  paf.bandas("estoque_bilhoes"), fig)
    assert len(fig.axes) == 2, "deixou de ser dois paineis"
    cima, baixo = fig.axes
    assert cima.get_position().y0 > baixo.get_position().y0
    # Tres linhas ao todo: duas em cima, uma embaixo.
    assert len(cima.lines) >= 2 and len(baixo.lines) >= 1
    # E as escalas sao mesmo diferentes: a de baixo e uma ordem menor.
    assert cima.get_ylim()[1] > baixo.get_ylim()[1] * 10
    plt.close(fig)


def test_a_escala_curta_nao_gasta_o_painel_com_vazio():
    # Com o zero cravado, a janela de 12 meses gastava 80% da altura em branco: a
    # divida vai de 7,6 a 9,3 mil bi no periodo, e o movimento virava um risco no
    # topo. O enquadramento pela banda mantem a referencia dentro do quadro.
    fig = plt.figure(figsize=(13, 6.6))
    d = estoque.dados_estoque_total(1)
    estoque.desenha_estoque_total(d, paf.bandas("estoque_bilhoes"), fig)
    cima = fig.axes[0]
    piso, teto = cima.get_ylim()
    usado = (d["total"].max() - d["total"].min()) / 1000 / (teto - piso)
    assert usado > 0.30, f"a serie ocupa so {usado:.0%} da altura do painel"
    assert teto >= 10300, "a banda de 2026 saiu do quadro"
    plt.close(fig)
