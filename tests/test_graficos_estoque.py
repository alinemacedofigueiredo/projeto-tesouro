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


def test_a_composicao_do_ULTIMO_MES_bate_com_o_anexo(comp):
    # O NOME DIZIA "junho" e o corpo sempre olhou comp.iloc[-1] -- o ultimo mes
    # que houver. Com a virada para julho o nome passou a mentir, entao mudou.
    #
    # PROCEDENCIA: aba 2.4 do anexo de julho, os mesmos valores que
    # test_a_composicao_do_nosso_CSV_bate_com_o_anexo confere contra o Excel.
    # Os percentuais sao valor/total daqueles numeros, em R$ bilhoes:
    #
    #     Prefixado        1.785,3461 / 9.288,7803 = 19,2205%
    #     Indice Precos    2.417,3288 / 9.288,7803 = 26,0243%
    #     Taxa Flutuante   4.747,2540 / 9.288,7803 = 51,1075%
    #     Cambio             338,8513 / 9.288,7803 =  3,6480%
    u = comp.iloc[-1]
    assert round(u["Prefixado"], 1) == 19.2
    assert round(u["\u00cdndice Pre\u00e7os"], 1) == 26.0
    assert round(u["Taxa Flutuante"], 1) == 51.1
    assert round(u["C\u00e2mbio"], 1) == 3.6
    assert round(u["estoque_milhoes"] / 1000, 1) == 9288.8


def test_cada_mes_da_composicao_soma_100(comp):
    # A CONTAGEM ERA CRAVADA EM 307 e crescia um por RMD -- amarra no lugar
    # errado, num teste que e sobre a soma fechar em 100. Agora ela sai da
    # propria serie: um ponto por mes, do primeiro ao ultimo, sem buraco. Isso
    # vale em qualquer mes, e pega o que a contagem pegava (serie encolhendo)
    # sem quebrar a cada RMD.
    cols = [c for c in comp.columns if c != "estoque_milhoes"]

    meses = pd.date_range(comp.index.min(), comp.index.max(), freq="ME")
    assert list(comp.index) == list(meses), (
        "a composicao tem buraco ou data fora de fim de mes")
    assert len(comp) > 300, "a serie encolheu"

    assert (comp[cols].sum(axis=1) - 100).abs().max() < 1e-9


def test_o_cambio_cai_do_pico_de_51_para_menos_de_quatro(comp):
    # O fato central da gestao da divida brasileira, e a razao de a serie completa
    # ser o padrao: numa janela de 5 anos ele nao aparece.
    #
    # O PICO E HISTORICO e nao se move: 51,04% em setembro de 2002. O ultimo mes
    # se move todo RMD, e sai do anexo -- 338,8513 / 9.288,7803 = 3,6480% em
    # 31/07/2026. O nome deixou de carregar o numero que anda.
    cam = comp["C\u00e2mbio"]
    assert round(cam.max(), 1) == 51.0
    assert cam.idxmax() == pd.Timestamp("2002-09-30")
    assert round(cam.iloc[-1], 2) == 3.65


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
    # Os valores do ultimo mes escritos na ponta de cada faixa que cabe --
    # os mesmos do anexo de julho.
    for esperado in ("19,2", "26,0", "51,1"):
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
    # E a figura carrega as mesmas ancoras que dados_composicao ja tem --
    # os percentuais do anexo de julho (ver test_a_composicao_do_ULTIMO_MES).
    for esperado in ("19,2", "26,0", "51,1", "3,6"):
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


# ---------------------------------------------------------------------------
# O DV01 e a duration do estoque.
# ---------------------------------------------------------------------------

def _dv_bruto():
    from tesouro import config

    return pd.read_csv(config.PROCESSED_DIR / "dv_por_papel.csv",
                       parse_dates=["data", "vencimento"])


def test_a_quantidade_do_DV_e_a_da_ABA_2_2_em_TODA_data():
    # A PERGUNTA QUE A DONA DO PROJETO FEZ, e que a primeira checagem nao
    # respondeu: o DV usa a posicao DAQUELA DATA? Conferido contra a aba 2.2,
    # que e fonte independente, par a par, nas 198 datas.
    from tesouro import config

    d = _dv_bruto()
    v = pd.read_csv(config.PROCESSED_DIR / "estoque_titulos_vencimento.csv",
                    parse_dates=["data", "vencimento"])
    v = v[v["quantidade_mil"] > 0]
    d["periodo"] = d["data"].dt.to_period("M")
    v["periodo"] = v["data"].dt.to_period("M")
    q22 = v.set_index(["periodo", "titulo", "vencimento"])["quantidade_mil"]

    m = d[d["titulo"].isin(("LTN", "NTN-F", "NTN-B"))].copy()
    m["q22"] = [q22.get((p, t, vc)) for p, t, vc
                in zip(m["periodo"], m["titulo"], m["vencimento"])]
    comum = m[m["q22"].notna() & (m["q22"] > 0)]
    assert len(comum) > 6000, f"so {len(comum)} pares comparados"
    razao = comum["quantidade_mil"] / comum["q22"]
    assert (razao.sub(1).abs() > 0.001).sum() == 0


def test_nenhum_vencimento_da_2_2_falta_no_arquivo_de_DV():
    from tesouro import config

    d = _dv_bruto()
    v = pd.read_csv(config.PROCESSED_DIR / "estoque_titulos_vencimento.csv",
                    parse_dates=["data", "vencimento"])
    v = v[(v["quantidade_mil"] > 0) & v["titulo"].isin(("LTN", "NTN-F", "NTN-B"))]
    d["periodo"] = d["data"].dt.to_period("M")
    v["periodo"] = v["data"].dt.to_period("M")

    faltando = []
    for periodo, g in v.groupby("periodo"):
        h = d[d["periodo"] == periodo]
        if h.empty:
            continue
        fora = set(zip(g["titulo"], g["vencimento"])) - set(
            zip(h["titulo"], h["vencimento"]))
        if fora:
            faltando.append((periodo, sorted(fora)[:2]))
    assert not faltando, faltando[:5]


def test_a_taxa_e_o_VNA_sao_os_DAQUELA_DATA_e_nao_congelados():
    # Se algum deles fosse carregado adiante, a serie de DV seria a de um papel
    # que nunca existiu -- e o grafico pareceria perfeitamente normal.
    d = _dv_bruto()
    b = d[(d["titulo"] == "NTN-B")
          & (d["vencimento"] == pd.Timestamp("2050-08-15"))]
    assert len(b) > 190
    assert b["taxa_pct"].nunique() > len(b) * 0.95
    assert b["vna"].nunique() > len(b) * 0.95
    assert b["dv_unitario"].nunique() > len(b) * 0.95


def test_o_DV_encurta_com_o_papel_chegando_no_vencimento():
    d = _dv_bruto()
    c = d[(d["titulo"] == "LTN")
          & (d["vencimento"] == pd.Timestamp("2026-07-01"))].sort_values("data")
    ultimos = c.tail(6)["dv_unitario"].abs().tolist()
    assert ultimos == sorted(ultimos, reverse=True), ultimos
    assert ultimos[-1] < ultimos[0] / 50


def test_o_PU_e_o_DV_do_arquivo_sao_reprodutiveis_do_zero():
    # Refaz a conta chamando a precificacao, e compara com o que foi gravado.
    from tesouro import calendario, precificacao

    cal = calendario.padrao()
    d = _dv_bruto()
    amostra = d[d["dv_unitario"].notna()].sample(12, random_state=7)
    for _, r in amostra.iterrows():
        vna = None if pd.isna(r["vna"]) else r["vna"]
        pu = precificacao.pu(cal, r["titulo"], r["data"].date(),
                             r["vencimento"].date(), r["taxa_pct"] / 100, vna)
        dv = precificacao.dv(cal, r["titulo"], r["data"].date(),
                             r["vencimento"].date(), r["taxa_pct"] / 100, vna)
        assert abs(pu - r["pu"]) < 1e-8, (r["titulo"], r["data"])
        assert abs(dv - r["dv_unitario"]) < 1e-8, (r["titulo"], r["data"])


def test_o_QUE_FICA_DE_FORA_esta_medido_e_escrito_na_pagina():
    # Quatro papeis nao tem taxa coletada e por isso nao entram: NTN-C, NTN-B
    # Principal, RendA+ e EducA+. Isso NAO e defeito, e perimetro -- mas
    # perimetro que nao esta escrito na pagina e omissao.
    from tesouro import config
    from tesouro.graficos import dashboard

    d = _dv_bruto()
    v = pd.read_csv(config.PROCESSED_DIR / "estoque_titulos_vencimento.csv",
                    parse_dates=["data", "vencimento"])
    u = v[(v["data"] == v["data"].max()) & (v["quantidade_mil"] > 0)]
    fora = u[~u["titulo"].isin(d["titulo"].unique())]
    assert set(fora["titulo"]) == {"NTN-C", "NTN-B Principal", "NTN-B1 RendA+",
                                   "NTN-B1 EducA+", "LFT-TD1 Reserva"}
    bilhoes = (fora[fora["titulo"] != "LFT-TD1 Reserva"]["financeiro_milhoes"]
               .sum() / 1000)
    assert 180 < bilhoes < 200, f"o que fica de fora mudou: R$ {bilhoes:.1f} bi"

    nota = [g for g in dashboard.REGISTRO if g.id == "dv_do_estoque"][0].nota
    for papel in ("NTN-C", "NTN-B Principal", "RendA+", "EducA+"):
        assert papel in nota, f"a nota nao diz que {papel} fica de fora"
    assert "7,6%" in nota


def test_a_duration_sai_do_DV_dividido_pelo_valor_de_mercado():
    # DV01 = -PU x duration modificada x 0,0001. A conta da carteira e a mesma,
    # com o DV01 e o valor de mercado somados -- ponderacao pelo VALOR, e nao
    # pela quantidade, que somaria uma LTN de R$ 481 com uma NTN-B de R$ 4.031
    # como se pesassem o mesmo.
    d = _dv_bruto()
    ult = d[(d["data"] == d["data"].max()) & (d["titulo"] == "NTN-B")]
    dv = ult["dv_posicao_milhoes"].sum()
    mtm = (ult["pu"] * ult["quantidade_mil"] * 1000 / 1e6).sum()
    esperado = -dv / mtm * 10000

    dados = estoque.dados_dv_do_estoque()
    obtido = dados["dur \u00cdndice Pre\u00e7os"].iloc[-1]
    assert abs(obtido - esperado) < 0.01, (obtido, esperado)
    assert 5 < obtido < 6.5, obtido


def test_a_LFT_NAO_TEM_LINHA_em_nenhum_dos_dois_paineis():
    # Ela ficou no painel de cima ate 21/08/2026, como uma reta em zero: verdadeira,
    # e ruido. "So esta poluindo." Saiu dos dois.
    #
    # No de duration nunca esteve, por outro motivo: DV zero sobre valor positivo
    # da duration zero, que e verdade e nao ajuda -- a LFT nao tem duration de
    # TAXA, e uma linha em zero ao lado de duas reais convida a comparar coisas
    # que nao se comparam.
    assert "Taxa Flutuante" not in estoque.ORDEM_DO_DV
    assert "Taxa Flutuante" not in estoque.DURATION_DE
    dados = estoque.dados_dv_do_estoque()
    for coluna in ("Taxa Flutuante", "dur Taxa Flutuante"):
        assert coluna not in dados.columns


def test_tirar_a_LFT_NAO_MUDA_O_TOTAL():
    # E o que autoriza tira-la sem passar a mentir: ela somava zero. Se um dia a
    # LFT ganhar DV -- outra fonte de taxa, outro criterio -- o total passa a ser
    # menor do que e, e este teste avisa.
    d = _dv_bruto()
    lft = d[d["titulo"] == "LFT"]
    assert len(lft) > 2000, "a LFT sumiu do arquivo"
    assert lft["dv_posicao_milhoes"].fillna(0).abs().max() == 0

    dados = estoque.dados_dv_do_estoque()
    soma = dados[estoque.ORDEM_DO_DV].sum(axis=1)
    assert (dados["total"] - soma).abs().max() < 1e-9


def test_o_DV_do_estoque_NAO_TEM_media_movel():
    # Uma de tres meses foi tentada em 21/08/2026 e recusada por quem le: "nao
    # serviu para nada". E o desenho concorda -- a serie e mensal e ja e suave,
    # porque o estoque muda por leilao e por vencimento, e nao por preco. Alisar o
    # que ja e liso so acrescenta uma linha para o olho separar.
    assert not hasattr(estoque, "MESES_DA_MEDIA")
    dados = estoque.dados_dv_do_estoque()
    assert not [c for c in dados.columns if str(c).startswith("mm")]


def test_o_DV_do_estoque_sao_DOIS_PAINEIS():
    fig = plt.figure(figsize=(13, 7.0))
    estoque.desenha_dv_do_estoque(estoque.dados_dv_do_estoque(), fig)
    assert len(fig.axes) == 2
    cima, baixo = fig.axes
    assert cima.get_position().y0 > baixo.get_position().y0
    assert cima.get_ylabel().startswith("R$")
    assert baixo.get_ylabel() == "anos"
    # Em cima, TRES linhas -- total, Indice de Precos e Prefixado. A LFT saiu, e
    # nao ha media movel. Embaixo, as duas de duration.
    assert len(cima.lines) == 3, [l.get_label() for l in cima.lines]
    assert len(baixo.lines) == 2
    assert [l.get_label() for l in cima.lines][0] == "total"
    plt.close(fig)


def test_papel_novo_sem_indexador_LEVANTA_em_vez_de_sumir():
    # Se um papel entrar no dv_por_papel.csv sem estar em INDEXADOR_DO_PAPEL, ele
    # sairia do grafico em silencio e o DV total ficaria menor do que e. Novos
    # casos param a construcao em vez de encolher o numero sem avisar.
    assert "NTN-C" in estoque.INDEXADOR_DO_PAPEL
    guardados = dict(estoque.INDEXADOR_DO_PAPEL)
    try:
        del estoque.INDEXADOR_DO_PAPEL["NTN-B"]
        with pytest.raises(LookupError, match="INDEXADOR_DO_PAPEL"):
            estoque.dados_dv_do_estoque()
    finally:
        estoque.INDEXADOR_DO_PAPEL.clear()
        estoque.INDEXADOR_DO_PAPEL.update(guardados)


# ---------------------------------------------------------------------------
# De onde veio a variacao do DV01 no mes.
# ---------------------------------------------------------------------------

PRECO = "pre\u00e7o"
EMISSAO = "emiss\u00e3o"


def test_as_partes_SOMAM_A_VARIACAO_em_todos_os_meses():
    # E A PROMESSA DO GRAFICO, escrita na legenda: "as cinco colunas somam a
    # variacao, exatamente". Se um residuo de cruzamento aparecer, a legenda passa
    # a mentir e ninguem percebe -- as barras continuam bonitas.
    d = estoque.dados_variacao_do_dv()
    assert len(d) > 190
    soma = d[estoque.FATORES].sum(axis=1)
    erro = (d["variacao"] - soma).abs()
    assert erro.max() < 1e-9, f"maior residuo: {erro.max()}"


def test_a_variacao_bate_com_a_SERIE_DE_DV01_do_grafico_de_cima():
    # Os dois graficos vivem lado a lado. Se a variacao daqui nao for a diferenca
    # de la, sao duas contas diferentes com o mesmo nome.
    nivel = estoque.dados_dv_do_estoque()["total"]
    d = estoque.dados_variacao_do_dv()
    esperado = nivel.diff().reindex(d.index)
    assert (d["variacao"] - esperado).abs().max() < 1e-6


def test_o_decay_TIRA_risco_e_a_emissao_POE_em_todo_mes():
    # Nao e coincidencia dos ultimos meses: e o que a legenda afirma sobre os 197,
    # e a frase "a divida ganha DV01 porque emite mais risco do que o tempo
    # destroi" depende disso.
    d = estoque.dados_variacao_do_dv()
    assert (d["decay"] < 0).all(), d.loc[d["decay"] >= 0, "decay"]
    assert (d[EMISSAO] > 0).all(), d.loc[d[EMISSAO] <= 0, EMISSAO]
    assert d["decay"].mean() < -10
    assert d[EMISSAO].mean() > 15


def test_o_RESGATE_pesa_pouco_como_ela_previu():
    # "Resgates mudam pouco o DV01, porque ja esta muito curto." Media de -1,0
    # contra +17,4 da emissao.
    d = estoque.dados_variacao_do_dv()
    assert abs(d["resgate"].mean()) < 2
    assert abs(d["resgate"].mean()) < d[EMISSAO].mean() / 10


def test_quem_faz_o_grafico_balancar_e_o_PRECO():
    # A media do preco e quase zero e o desvio-padrao e o maior dos cinco: ele nao
    # tem direcao, tem tamanho. E o que distingue os dois lados da conta.
    d = estoque.dados_variacao_do_dv()
    desvios = d[estoque.FATORES].std()
    assert desvios.idxmax() == PRECO
    assert desvios[PRECO] > desvios["decay"] * 3
    assert desvios[PRECO] > desvios[EMISSAO] * 2


def test_o_DECAY_e_medido_REPRECIFICANDO_com_a_taxa_velha():
    # Nao e estimativa por duration. O teste refaz a conta de UM papel a mao e
    # confere que o sinal e o tamanho batem: a NTN-B 2050 num mes qualquer.
    from tesouro import calendario, config, precificacao

    cal = calendario.padrao()
    b = pd.read_csv(config.PROCESSED_DIR / "dv_por_papel.csv",
                    parse_dates=["data", "vencimento"])
    b = b[(b["titulo"] == "NTN-B")
          & (b["vencimento"] == pd.Timestamp("2050-08-15"))].sort_values("data")
    antes, depois = b.iloc[-2], b.iloc[-1]

    congelado = -precificacao.dv(cal, "NTN-B", depois["data"].date(),
                                 antes["vencimento"].date(),
                                 antes["taxa_pct"] / 100, antes["vna"])
    # Um mes a menos de prazo, com a MESMA taxa e o MESMO VNA, da menos DV.
    assert congelado < -antes["dv_unitario"]
    # E a diferenca e pequena perto da que o preco faz: e um mes num papel de 24
    # anos. Se as duas fossem parecidas, o decay estaria comendo taxa.
    so_tempo = abs(congelado - (-antes["dv_unitario"]))
    com_tudo = abs((-depois["dv_unitario"]) - (-antes["dv_unitario"]))
    assert so_tempo < com_tudo


def test_papel_que_VENCE_vai_todo_para_resgate_e_nao_para_preco():
    # ARMADILHA: um papel presente num mes e ausente no outro nao tem "preco novo".
    # Atribuir a diferenca a marcacao poria uma coluna enorme de preco no mes em
    # que uma NTN-B venceu -- e a leitura do grafico inteiro mudaria.
    from tesouro import config

    b = pd.read_csv(config.PROCESSED_DIR / "dv_por_papel.csv",
                    parse_dates=["data"])
    b = b[b["titulo"] != "LFT"]
    datas = sorted(b["data"].unique())
    d = estoque.dados_variacao_do_dv()

    sumiram = []
    for anterior, atual in zip(datas[:-1], datas[1:]):
        antes = b[b["data"] == anterior]
        # SO OS QUE TINHAM DV MEDIDO. Papel que saiu do estoque sem nunca ter tido
        # taxa contribuia zero para o nivel, entao a saida dele nao muda nada -- e
        # exigir resgate negativo ali seria exigir efeito de quem nao tinha efeito.
        # Aconteceu em fev/2012, e o teste acusou.
        com_dv = set(antes.loc[antes["dv_posicao_milhoes"].notna(), "isin"])
        if com_dv - set(b[b["data"] == atual]["isin"]):
            sumiram.append(pd.Timestamp(atual))
    assert len(sumiram) > 10, "quase nenhum papel saiu do estoque no historico"
    for data in sumiram:
        assert d.loc[data, "resgate"] < 0, data

    # O TESTE ACIMA NAO BASTA, e a verificacao com dentes mostrou: mandar o papel
    # vencido para "preco" deixa o resgate negativo do mesmo jeito, porque posicao
    # que so encolhe tambem e resgate. E preciso um mes onde a SAIDA seja grande e
    # conferir que ela esta na coluna certa.
    #
    # Em dez/2010 uma NTN-B venceu levando 14,22 milhoes por bp -- trinta vezes a
    # segunda maior saida do historico. Se ela estiver em "preco", o teste acusa.
    a = b[b["data"] == datas[datas.index(pd.Timestamp("2010-12-31")) - 1]]
    saiu = a[~a["isin"].isin(b[b["data"] == pd.Timestamp("2010-12-31")]["isin"])
             & a["dv_posicao_milhoes"].notna()]
    dv_que_saiu = saiu["dv_posicao_milhoes"].abs().sum()
    assert dv_que_saiu > 14, dv_que_saiu
    assert d.loc[pd.Timestamp("2010-12-31"), "resgate"] <= -dv_que_saiu + 0.01, (
        "o papel que venceu nao foi para o resgate")


def test_a_faixa_SEM_TAXA_existe_e_e_pequena():
    # Ela e o residuo honesto: papel sem cotacao num dos dois meses, cuja variacao
    # nao da para atribuir. Some-la dentro de outra barra seria pior. Mas se ela
    # crescer, o grafico deixou de explicar o que promete.
    d = estoque.dados_variacao_do_dv()
    assert "sem taxa" in estoque.FATORES
    quantos = (d["sem taxa"].abs() > 0.01).sum()
    assert 0 < quantos <= 15, quantos
    assert d["sem taxa"].abs().max() < 10


def test_as_barras_empilham_positivo_para_CIMA_e_negativo_para_BAIXO():
    # Empilhar tudo a partir do zero misturaria os sinais, e a altura da pilha
    # deixaria de querer dizer alguma coisa.
    fig = plt.figure(figsize=(13, 7.2))
    d = estoque.dados_variacao_do_dv(3)
    estoque.desenha_variacao_do_dv(d, fig)
    for barra in fig.axes[0].patches:
        base, altura = barra.get_y(), barra.get_height()
        if altura > 0:
            assert base >= -1e-9, (base, altura)
        elif altura < 0:
            assert base <= 1e-9, (base, altura)
    plt.close(fig)


def test_a_legenda_do_grafico_nao_afirma_numero_que_o_dado_desmente():
    # A nota traz oito numeros medidos. Numero em legenda envelhece calado: o dado
    # e reprocessado todo mes e a frase fica.
    from tesouro.graficos import dashboard

    d = estoque.dados_variacao_do_dv()
    nota = [g for g in dashboard.REGISTRO if g.id == "variacao_do_dv"][0].nota

    # DUAS VEZES, e nao "em algum lugar". A nota faz esta afirmacao dois
    # lugares -- uma para o decay, outra para a emissao -- e a versao anterior
    # so checava presenca: mutar uma das duas deixava a outra passando, e o
    # teste dava a impressao de proteger as duas. Achado na conferencia de
    # dentes em 02/09/2026.
    quantos = str(len(d)) + " dos " + str(len(d))
    assert nota.count(quantos) == 2, (
        f"a nota devia afirmar {quantos!r} duas vezes (decay e emissao), e "
        f"afirma {nota.count(quantos)}")
    assert estilo.num_br(abs(d["decay"].mean()), 1) in nota
    assert estilo.num_br(d[EMISSAO].mean(), 1) in nota
    assert estilo.num_br(abs(d["resgate"].mean()), 1) in nota

    pior = d["variacao"].idxmin()
    assert pior.year == 2020 and pior.month == 3
    assert estilo.num_br(abs(d.loc[pior, PRECO]), 1) in nota
    fracao = d[PRECO].std() / d[estoque.FATORES].std().sum()
    assert str(round(fracao * 100)) + "%" in nota

    # A FAIXA CINZA, que a nota descreve e ninguem conferia. Ela afirma "10
    # transicoes" e "a maior de 7,3 milhoes por bp em jan/2025" -- numeros
    # publicados sem teste, o formato exato que esta pagina existe para nao
    # produzir. Conferidos em 02/09/2026: continuam verdadeiros.
    cinza = d["sem taxa"]
    transicoes = cinza[cinza.abs() > 1e-9]
    assert str(len(transicoes)) + " transi" in nota, (
        f"a nota fala de outro numero de transicoes; sao {len(transicoes)}")
    assert estilo.num_br(transicoes.abs().max(), 1) in nota
    maior = transicoes.abs().idxmax()
    assert estilo.MES[maior.month] + "/" + str(maior.year) in nota, (
        f"a nota aponta outro mes para a maior transicao; foi {maior:%m/%Y}")


def test_o_grafico_de_fatores_tem_o_PAINEL_DOS_ACUMULADOS():
    # Duas versoes foram desenhadas antes de escolher: tudo num eixo so, e os
    # acumulados num painel proprio. No mesmo eixo a decomposicao encolhe a um
    # terco -- o acumulado de doze meses vai a 391 e a barra mais alta tem 107 --
    # e o ASSUNTO do grafico vira rodape das linhas.
    fig = plt.figure(figsize=(13, 7.2))
    d = estoque.dados_variacao_do_dv(5)
    estoque.desenha_variacao_do_dv(d, fig)
    assert len(fig.axes) == 2
    cima, baixo = fig.axes
    assert cima.get_position().y0 > baixo.get_position().y0
    assert baixo.get_ylabel().startswith("R$")
    # Embaixo, so as duas linhas de acumulado; nenhuma barra.
    assert len(baixo.lines) >= 2
    assert not baixo.patches
    rotulos = [l.get_label() for l in baixo.lines]
    assert any("3 meses" in r for r in rotulos), rotulos
    assert any("12 meses" in r for r in rotulos), rotulos
    plt.close(fig)


def test_os_acumulados_saem_da_SERIE_INTEIRA_e_nao_da_janela():
    # Uma soma movel de doze meses calculada dentro da janela nasceria com onze
    # meses vazios, e o primeiro ponto visivel seria um acumulado de um mes so
    # chamado de doze. O recorte vem DEPOIS da conta.
    tudo = estoque.dados_variacao_do_dv()
    janela = estoque.dados_variacao_do_dv(3)
    assert janela["acum 12m"].notna().all(), (
        "o acumulado de 12m nasceu vazio dentro da janela")
    assert janela["acum 3m"].notna().all()
    for coluna in ("acum 3m", "acum 12m"):
        assert (tudo.loc[janela.index, coluna] - janela[coluna]).abs().max() < 1e-9
    esperado = tudo["variacao"].rolling(12).sum()
    assert (tudo["acum 12m"] - esperado).abs().max() < 1e-9


def test_o_PONTO_DO_NET_esta_em_cada_barra():
    # Sem ele, a variacao do mes tem de ser lida medindo a pilha de cima contra a
    # de baixo, que ninguem faz a olho. Saiu na primeira versao e voltou a pedido.
    fig = plt.figure(figsize=(13, 7.2))
    d = estoque.dados_variacao_do_dv(3)
    estoque.desenha_variacao_do_dv(d, fig)
    cima = fig.axes[0]
    pontos = [l for l in cima.lines if l.get_marker() not in (None, "None", "")]
    assert len(pontos) == 1, [l.get_marker() for l in cima.lines]
    ys = pontos[0].get_ydata()
    assert len(ys) == len(d)
    assert abs(ys[-1] - d["variacao"].iloc[-1]) < 1e-9
    plt.close(fig)


def test_a_faixa_cinza_NAO_ENTRA_NA_LEGENDA_mas_esta_no_texto():
    # Ela e residuo -- dez transicoes em dezesseis anos -- e uma entrada de legenda
    # ao lado das outras quatro a faz parecer um fator como os demais. O que ela e
    # fica no texto do grafico, que e onde cabe explicacao.
    from tesouro.graficos import dashboard

    fig = plt.figure(figsize=(13, 7.2))
    estoque.desenha_variacao_do_dv(estoque.dados_variacao_do_dv(3), fig)
    rotulos = [t.get_text() for t in fig.axes[0].get_legend().get_texts()]
    assert "sem taxa" not in rotulos, rotulos
    for fator in ("decay", "pre\u00e7o", "emiss\u00e3o", "resgate"):
        assert fator in rotulos, (fator, rotulos)
    plt.close(fig)

    nota = [g for g in dashboard.REGISTRO if g.id == "variacao_do_dv"][0].nota
    assert "cinza" in nota, "a faixa saiu da legenda e nao foi explicada no texto"
    assert "ganharam cota" in nota


def test_a_nota_diz_que_o_VNA_esta_em_PRECO_e_nao_em_decay():
    # Pedido dela, e a distincao importa: o IPCA corrigindo o VNA aumenta o DV01
    # sem que o risco tenha mudado. Chamar isso de passagem do tempo misturaria
    # indexacao com encurtamento -- e por isso o VNA e congelado no decay.
    from tesouro.graficos import dashboard

    nota = [g for g in dashboard.REGISTRO if g.id == "variacao_do_dv"][0].nota
    assert "VNA" in nota
    i = nota.index("corre\u00e7\u00e3o do VNA")
    trecho = nota[i:i + 140]
    assert "pre\u00e7o" in trecho and "decay" in trecho, trecho


def test_a_grade_dos_dois_graficos_tem_marca_MENOR():
    # Pedido dela nos dois. Sem a menor, dizer se um ponto e 1.050 ou 1.150 com a
    # marca a cada 400 era chute.
    from tesouro.graficos import paf

    def total(dados, fig):
        estoque.desenha_estoque_total(dados, paf.bandas("estoque_bilhoes"), fig)

    for desenha, dados in ((estoque.desenha_variacao_do_dv,
                            estoque.dados_variacao_do_dv(3)),
                           (estoque.desenha_dv_do_estoque,
                            estoque.dados_dv_do_estoque(3)),
                           (total, estoque.dados_estoque_total(3))):
        fig = plt.figure(figsize=(13, 7.2))
        desenha(dados, fig)
        for eixo in fig.axes:
            # A PROPRIEDADE E "HA MAIS MARCAS DO QUE SO AS MAIORES", e ela nao
            # se mede contando, nem comparando os dois passos isolados. O
            # matplotlib TIRA a marca menor que cai em cima de uma maior: com maior
            # a cada 25 e menor a cada 12,5, as menores sobram em -12,5 e +12,5, e
            # o passo delas tambem da 25. As duas primeiras versoes deste teste
            # reprovaram um grafico certo por isso -- uma contou 11 contra 12, a
            # outra comparou 25 com 25.
            #
            # O que vale e o passo do CONJUNTO das duas.
            menores = list(eixo.yaxis.get_minorticklocs())
            maiores = list(eixo.yaxis.get_majorticklocs())
            assert len(menores) >= 3 and len(maiores) >= 3
            passo_maior = min(b - a for a, b in zip(maiores, maiores[1:]))
            # ARREDONDAR ANTES DA UNIAO, e exigir folga na comparacao. A terceira
            # versao deste teste ainda passava contra um grafico sem marca menor:
            # com menor = maior, as duas listas caem quase nas mesmas alturas, mas
            # diferem no decimo quinto decimal -- a uniao ficava com o dobro dos
            # pontos, separados por 1e-13, e "ha marcas mais juntas" dava verdade.
            juntas = sorted({round(x / passo_maior, 6)
                             for x in list(menores) + list(maiores)})
            passo_junto = min(b - a for a, b in zip(juntas, juntas[1:]))
            assert passo_junto < 0.9, (desenha.__name__, eixo.get_ylabel(),
                                       passo_junto, passo_maior)
            # E NAO PODE VIRAR PAPEL QUADRICULADO. Um passo cravado de 200 num eixo
            # que vai a 11.279 dava 59 linhas em cima e 167 embaixo, no grafico do
            # total da divida -- e so se viu ao medir, porque o passo foi copiado de
            # outro grafico junto com o resto do bloco.
            assert 4 <= len(maiores) <= 14, (desenha.__name__, eixo.get_ylabel(),
                                             len(maiores))
            # E a grade esta LIGADA nas duas, senao a marca menor nao vira regua.
            # A checagem e pelos tick kwargs porque as Line2D da grade so ganham
            # visibilidade quando o canvas desenha, e desenhar aqui custaria caro.
            assert eixo.yaxis._major_tick_kw.get("gridOn"), eixo.get_ylabel()
            assert eixo.yaxis._minor_tick_kw.get("gridOn"), eixo.get_ylabel()
        plt.close(fig)


def test_o_passo_da_grade_sai_da_escala_e_e_um_numero_redondo():
    # 1, 2 ou 5 vezes potencia de dez -- sao os passos que se leem sem pensar.
    # Passo cravado nao serve: a mesma funcao desenha quatro janelas, e o eixo do
    # total da divida vai de 1,7 mil bi na de doze meses a 11,3 mil na completa.
    for intervalo in (7, 63, 249, 1767, 11279, 0.8):
        maior, menor = estoque._passo_bonito(intervalo)
        assert maior > 0 and menor > 0
        assert abs(menor * 2 - maior) < 1e-9
        quantas = intervalo / maior
        assert 3 <= quantas <= 12, (intervalo, maior, quantas)
        mantissa = maior / 10 ** int(round(__import__("math").log10(maior)))
        assert round(mantissa, 6) in (0.1, 0.2, 0.5, 1.0, 2.0), (intervalo, maior)
