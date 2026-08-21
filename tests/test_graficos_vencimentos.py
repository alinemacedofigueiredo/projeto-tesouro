import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pytest

from tesouro.graficos import estilo, vencimentos


# ---------------------------------------------------------------------------
# Aba 3.4: o cronograma
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def anual():
    return vencimentos.dados_cronograma_anual()


def test_o_cronograma_anual_bate_com_o_medido(anual):
    por_ano = anual.sum(axis=1) / 1000
    assert round(por_ano[2026], 1) == 833.5
    assert round(por_ano[2027], 1) == 1771.9
    assert round(por_ano[2028], 1) == 1133.2
    assert round(por_ano[2029], 1) == 1315.6
    assert round(por_ano[2030], 1) == 1223.2
    assert round(por_ano[2031], 1) == 636.5


def test_o_balde_entra_no_cronograma_e_o_total_fecha(anual):
    # Sem o balde da Task 2 o grafico mostraria 78% do estoque como se fosse tudo.
    por_ano = anual.sum(axis=1) / 1000
    assert round(por_ano["Ap\u00f3s 5 anos"], 1) == 2006.9
    assert round(por_ano.sum(), 1) == 8920.7


def test_os_dois_anos_das_pontas_sao_parciais(anual):
    # A aba 3.4 detalha jul/26 a jun/31: 2026 e jul-dez e 2031 e jan-jun. Comparar
    # 833,5 com 1.771,9 sem saber disso e ler o grafico errado.
    assert vencimentos.ANOS_PARCIAIS == (2026, 2031)
    mensal = vencimentos.dados_cronograma_mensal()
    meses = mensal.index.to_series().dt.year.value_counts()
    assert meses[2026] == 6
    assert meses[2031] == 6
    assert meses[2027] == 12


def test_o_cronograma_mensal_tem_os_sessenta_meses():
    m = vencimentos.dados_cronograma_mensal()
    total = m.sum(axis=1) / 1000
    assert len(m) == 60
    assert m.index.min() == pd.Timestamp("2026-07-31")
    assert m.index.max() == pd.Timestamp("2031-06-30")
    assert round(total.max(), 1) == 562.8
    assert total.idxmax() == pd.Timestamp("2027-03-31")
    assert round(total[pd.Timestamp("2026-07-31")], 1) == 256.0
    # O balde NAO entra no detalhe mensal: ele nao tem mes.
    assert round(total.sum(), 1) == 6913.8


# ---------------------------------------------------------------------------
# Aba 3.1: as faixas da DPF, com a banda
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def faixas():
    return vencimentos.dados_faixas()


def test_as_faixas_da_dpf_batem_com_o_medido(faixas):
    u = faixas.iloc[-1]
    assert round(u["At\u00e9 12 meses"], 1) == 20.1
    assert round(u["De 1 a 2 anos"], 1) == 14.1
    assert round(u["De 2 a 5 anos"], 1) == 42.2
    assert round(u["Acima de 5 anos"], 1) == 23.6


def test_cada_mes_das_faixas_soma_100(faixas):
    assert len(faixas.columns) == 4
    assert (faixas.sum(axis=1) - 100).abs().max() < 1e-9
    # O bloco DPF da aba 3.1 tem 246 meses, mas os dez primeiros (jan a out/2006)
    # vem ZERADOS -- a serie so comeca de fato em nov/2006, a mesma data em que a
    # do prazo medio comeca. Mantidos, eles viram dez meses somando zero por cento,
    # e a area empilhada abre com um buraco que parece dado faltando.
    assert faixas.index.min() == pd.Timestamp("2006-11-30")
    assert len(faixas) == 236


def test_a_banda_do_vincendo_cobre_de_2003_a_2026():
    # A aba 5.7 do anexo de jun/26 tem quatro blocos e o ultimo termina em
    # "PAF 2022"; o resto vem do arquivo de referencia.
    b = vencimentos.banda_vincendo_12m()
    assert b.index.min() == 2003
    assert b.index.max() == 2026


def test_o_realizado_do_vincendo_bate_com_o_nosso_dado(faixas):
    # Cruzamento contra fonte independente: a faixa sai da aba 3.1 pelo nosso
    # parser e o realizado sai da 5.7, que e outra aba e outro parser. A tolerancia
    # de 0,05 e o arredondamento com que o proprio RMD imprime o realizado.
    #
    # Este realizado E lido, diferente do de referencia/paf_bandas.csv: ele vem de
    # uma aba do RMD, por parser, e nao de tabela digitada a mao. O cruzamento
    # confere dois parsers nossos um contra o outro, que e o que pega defeito.
    # banda_da_57 e nao banda_vincendo_12m: o realizado so existe na aba 5.7. O
    # arquivo de referencia tem a coluna, mas ela nao e lida por decisao da dona do
    # projeto -- de la vem a banda, e so.
    b = vencimentos.banda_da_57()
    for ano in range(2011, 2023):
        nosso = faixas.loc[pd.Timestamp(f"{ano}-12-31"), "At\u00e9 12 meses"]
        assert abs(nosso - b.loc[ano, "realizado"]) < 0.05, f"vincendo em {ano}"


# ---------------------------------------------------------------------------
# Desenho
# ---------------------------------------------------------------------------

def test_o_desenho_marca_os_dois_anos_parciais():
    estilo.aplicar_estilo()
    fig = plt.figure(figsize=(13, 9))
    vencimentos.desenha_cronograma(vencimentos.dados_cronograma_anual(),
                                   vencimentos.dados_cronograma_mensal(), fig)
    rotulos = [t.get_text() for ax in fig.axes for t in ax.get_xticklabels()]
    plt.close(fig)
    assert "2026*" in rotulos and "2031*" in rotulos
    assert "2027" in rotulos and "2027*" not in rotulos


def test_o_desenho_do_mensal_divide_a_virada_do_ano():
    estilo.aplicar_estilo()
    fig = plt.figure(figsize=(13, 9))
    vencimentos.desenha_cronograma(vencimentos.dados_cronograma_anual(),
                                   vencimentos.dados_cronograma_mensal(), fig)
    # Quatro viradas de ano dentro dos 60 meses: 26/27, 27/28, 28/29, 29/30, 30/31.
    divisorias = [l for ax in fig.axes for l in ax.lines
                  if l.get_linestyle() == "--"]
    plt.close(fig)
    assert len(divisorias) == 5


def test_o_cronograma_inclui_cupom_e_o_perfil_nao():
    # A dona do projeto apontou isto em 19/08/2026, contra o que estava escrito. A
    # prova esta em tres papeis com regras diferentes de cupom:
    #
    #   LFT   -- nao paga cupom: a 3.4 e a 2.2 batem na casa decimal;
    #   NTN-F -- paga em jan e jul: a 3.4 traz 33,2 bi a mais em jul/26;
    #   NTN-B -- a 3.4 traz 25,8 bi em nov/26, mes em que NENHUMA NTN-B vence.
    import pandas as pd

    from tesouro import config

    cr = pd.read_csv(config.PROCESSED_DIR / "cronograma_vencimentos.csv",
                     parse_dates=["mes_vencimento"])
    mensal = cr[cr["faixa"] == "mensal"]
    por_grupo = mensal.pivot_table(index="mes_vencimento", columns="grupo_titulo",
                                   values="valor_milhoes", aggfunc="sum") / 1000

    bruto = vencimentos._perfil_bruto()
    ev = pd.read_csv(config.PROCESSED_DIR / "estoque_titulos_vencimento.csv",
                     parse_dates=["data", "vencimento"])
    u = ev[(ev["data"] == ev["data"].max()) & (ev["financeiro_milhoes"] > 0)]
    vence = u.groupby([u["vencimento"].dt.to_period("M"), "titulo"])[
        "financeiro_milhoes"].sum() / 1000

    def venceu(periodo, titulos):
        return sum(vence.get((periodo, t), 0.0) for t in titulos)

    nov26 = pd.Period("2026-11", "M")
    assert round(por_grupo.loc["2026-11-30", "NTN-B"], 1) == 25.8
    assert venceu(nov26, ["NTN-B", "NTN-B Principal"]) == 0.0

    jul26 = pd.Period("2026-07", "M")
    assert round(por_grupo.loc["2026-07-31", "LTN / NTN-F"]
                 - venceu(jul26, ["LTN", "NTN-F"]), 1) == 33.2

    set26 = pd.Period("2026-09", "M")
    assert round(por_grupo.loc["2026-09-30", "LFT"]
                 - venceu(set26, ["LFT", "LFT-TD1 Reserva"]), 1) == 0.0

    # E mesmo incluindo cupom a 3.4 soma o estoque, porque cada fluxo esta a preco
    # de curva: nao ha caixa nominal projetado, e nenhuma premissa de inflacao.
    assert round(cr["valor_milhoes"].sum() / 1000, 1) == 8920.7
    assert round(bruto.sum().sum() / 1000, 1) == 8904.1


def test_a_banda_do_vincendo_vem_das_duas_fontes():
    # 2022 so existe na aba 5.7; 2026 so existe no arquivo de referencia. As duas
    # tem de aparecer, ou uma das fontes nao esta sendo lida.
    b = vencimentos.banda_vincendo_12m()
    assert (b.loc[2022, "minimo"], b.loc[2022, "maximo"]) == (19.0, 23.0)
    assert (b.loc[2026, "minimo"], b.loc[2026, "maximo"]) == (18.0, 22.0)
    # A revisao de 2021 continua valendo sobre a original (24-29 vira 22-27).
    assert (b.loc[2021, "minimo"], b.loc[2021, "maximo"]) == (22.0, 27.0)


def test_o_vincendo_de_hoje_esta_dentro_da_banda_de_2026():
    # 20,07% contra a banda de 18 a 22. Nao e teste de politica: e o cruzamento que
    # pega banda digitada na escala errada, ou a faixa lida da coluna errada.
    faixas = vencimentos.dados_faixas()
    b = vencimentos.banda_vincendo_12m()
    hoje = faixas["At\u00e9 12 meses"].iloc[-1]
    assert round(hoje, 2) == 20.07
    assert b.loc[2026, "minimo"] <= hoje <= b.loc[2026, "maximo"]


def test_a_banda_do_vincendo_nao_tem_buraco():
    # A 5.7 cobre 2003 a 2022 e o arquivo de referencia cobre 2016 a 2026. Juntas,
    # nao sobra ano sem banda -- e o desenho nao tem trecho vazio.
    b = vencimentos.banda_vincendo_12m()
    assert [a for a in range(2003, 2027) if a not in b.index] == []


def test_as_duas_fontes_concordam_nos_sete_anos_que_compartilham():
    # Cruzamento contra fonte independente, e nao formalidade: a 5.7 vem do anexo do
    # RMD por parser, e as linhas de 2016 a 2026 do arquivo de referencia foram
    # digitadas de uma tabela de bandas que a dona do projeto mantem a parte. Duas
    # origens diferentes, sete anos em comum, mesma banda vigente nos sete.
    from tesouro.graficos import paf

    da_57 = vencimentos.banda_da_57()
    da_referencia = paf.bandas("vincendo_12m_pct")
    compartilhados = sorted(set(da_57.index) & set(da_referencia.index))
    assert compartilhados == [2016, 2017, 2018, 2019, 2020, 2021, 2022]
    for ano in compartilhados:
        assert da_57.loc[ano, "minimo"] == da_referencia.loc[ano, "minimo"], ano
        assert da_57.loc[ano, "maximo"] == da_referencia.loc[ano, "maximo"], ano


def test_a_57_perdeu_a_banda_ORIGINAL_de_2020_e_a_referencia_a_guarda():
    # A armadilha 5 da spec, com um caso medido. A aba 5.7 guarda UMA linha por ano
    # e registra a banda revisada como se fosse a original: para 2020 ela traz
    # 24-28, que e a revisao de ago/20. A original era 20-23, e so o arquivo de
    # referencia a tem.
    #
    # A banda DESENHADA nao muda -- as duas dao 24-28, que e a que estava em vigor no
    # fechamento. O que se perde na 5.7 e a memoria de que a meta mudou no meio do
    # ano, e mudou muito: de "ate 23%" para "ate 28%".
    from tesouro.graficos import paf

    da_57 = vencimentos.banda_da_57()
    assert (da_57.loc[2020, "minimo"], da_57.loc[2020, "maximo"]) == (24.0, 28.0)

    b = paf.bandas("vincendo_12m_pct")
    assert (b.loc[2020, "minimo"], b.loc[2020, "maximo"]) == (24.0, 28.0)
    assert (b.loc[2020, "minimo_original"], b.loc[2020, "maximo_original"]) == (20.0, 23.0)


def test_a_banda_nao_e_desenhada_onde_nao_existe():
    # A guarda `if ano not in banda.index: continue` deixou de ser exercitada quando
    # a tabela de bandas fechou a lacuna de 2023-2025: com a banda cobrindo
    # 2003-2026, TODO ano visivel tem banda e a guarda virou codigo morto -- apagar
    # a linha nao quebrava nada. Medido na revisao de 19/08/2026.
    #
    # Aqui a banda e TRUNCADA de proposito. E dado de teste, nao de producao: o que
    # se exercita e o desenho diante de uma banda que acaba antes da serie, que e
    # exatamente a situacao de antes de a tabela ser completada -- e a que volta se
    # alguem acrescentar um ano de dado sem acrescentar a banda dele.
    estilo.aplicar_estilo()
    fig = plt.figure(figsize=(13, 8))
    banda = vencimentos.banda_vincendo_12m()
    truncada = banda[banda.index <= 2018]
    vencimentos.desenha_faixas(vencimentos.dados_faixas(), truncada, fig)
    faixas = list(fig.axes[1].collections)
    plt.close(fig)
    # 2006 a 2018: treze anos com banda, e nada desenhado de 2019 em diante.
    assert len(faixas) == 13


def test_a_banda_cobre_todo_ano_visivel_hoje():
    # Depois de 2022 nao ha banda. Um retangulo esticado ate 2026 inventaria meta.
    estilo.aplicar_estilo()
    fig = plt.figure(figsize=(13, 8))
    vencimentos.desenha_faixas(vencimentos.dados_faixas(),
                               vencimentos.banda_vincendo_12m(), fig)
    # So o painel de baixo: o stackplot do de cima tambem cria colecoes, uma por
    # faixa, e contar as duas coisas juntas mede outra coisa.
    faixas_desenhadas = list(fig.axes[1].collections)
    de_cima = list(fig.axes[0].collections)
    plt.close(fig)
    assert len(de_cima) == 4, "as quatro faixas da area empilhada"
    # Uma banda por ano visivel: 2006 (inicio da nossa serie) a 2026, sem buraco,
    # desde que a tabela de bandas fechou a lacuna de 2023 a 2025.
    assert len(faixas_desenhadas) == 21


# --------------------------------------------------------------------------
# Estoque em QUANTIDADE, por vencimento e por papel.
#
# O RISCO DESTE GRAFICO nao e calcular errado -- e somar titulos como se um
# valesse o mesmo que outro. Medido em 30/06/2026: um de LFT vale R$ 19.220 e
# um de LFT-TD1 Reserva, R$ 10,68. Mil e oitocentas vezes menos.
# --------------------------------------------------------------------------

def test_o_estoque_traz_uma_linha_por_papel_e_vencimento():
    d = vencimentos.dados_estoque_por_vencimento()
    assert len(d) > 40
    assert not d.duplicated(subset=["vencimento", "titulo"]).any()
    # Em ordem de vencimento, que e a ordem em que o eixo os desenha.
    assert list(d["vencimento"]) == sorted(d["vencimento"])


def test_o_estoque_so_traz_papel_que_ainda_tem_estoque():
    # Papel ja vencido fica no CSV com quantidade zero. Incluir zeros poria dezenas
    # de barras de altura nenhuma no eixo.
    d = vencimentos.dados_estoque_por_vencimento()
    assert (d["quantidade_mil"] > 0).all()


def test_o_TESOURO_DIRETO_fica_de_fora():
    # Decisao da dona do projeto, e a medicao explica por que ela esta certa: um
    # titulo nao vale o mesmo que outro. Com os papeis de varejo dentro, a barra
    # mais alta do grafico era a LFT-TD1 de 2036 -- 328 milhoes de titulos e R$ 3,5
    # bilhoes -- ao lado de uma LTN de R$ 180 bilhoes.
    d = vencimentos.dados_estoque_por_vencimento()
    assert set(d["titulo"]).isdisjoint(vencimentos.PAPEIS_DE_VAREJO)
    # E a familia NTN-B1, que so tem papel de varejo, some junto.
    assert "NTN-B1" not in set(d["familia"])


def test_UM_TITULO_NAO_VALE_O_MESMO_QUE_OUTRO():
    # A medicao que justifica a exclusao, feita no dado BRUTO -- se um dia os
    # valores unitarios convergirem, a exclusao deixa de ter motivo.
    bruto = vencimentos._estoque_bruto()
    por_papel = bruto.groupby("titulo")["valor_unitario"].median()
    assert por_papel["LFT"] > 15000
    assert por_papel["LFT-TD1 Reserva"] < 50
    assert por_papel["LFT"] / por_papel["LFT-TD1 Reserva"] > 500


def test_o_excluido_e_muito_dos_titulos_e_quase_nada_da_divida():
    qtd, fin = vencimentos.excluido_do_estoque()
    bruto = vencimentos._estoque_bruto()
    em_qtd = qtd / bruto["quantidade_mil"].sum()
    em_fin = fin / bruto["financeiro_milhoes"].sum()
    assert em_qtd > 0.05, "os papeis de varejo deixaram de pesar na quantidade"
    assert em_fin < 0.02, "eles passaram a pesar no financeiro"
    # E a distancia entre as duas leituras e de mais de uma ordem de grandeza.
    assert em_qtd / em_fin > 10


def test_o_asterisco_diz_o_numero_excluido():
    # O que ficou de fora tem de estar escrito NA FIGURA, e nao so na legenda do
    # HTML: quem copia o grafico para um slide leva a ressalva junto. E a mesma
    # regra do perfil ao lado, que ja fazia isso com a NTN-B1.
    import matplotlib.pyplot as plt

    qtd, fin = vencimentos.excluido_do_estoque()
    fig = plt.figure()
    vencimentos.desenha_estoque_por_vencimento(
        vencimentos.dados_estoque_por_vencimento(), fig)
    # get_title() sem argumento devolve so o titulo CENTRAL; o asterisco esta com
    # loc="right", que o matplotlib guarda noutro objeto. Ler os tres evita um
    # teste que passa por procurar no lugar errado.
    titulos = " ".join(ax.get_title(loc=onde)
                       for ax in fig.axes
                       for onde in ("left", "center", "right"))
    assert "Tesouro Direto" in titulos
    assert f"{qtd / 1000:.0f}" in titulos
    plt.close(fig)


def test_UM_PAINEL_POR_PAPEL():
    # O pedido: um grafico por tipo de papel. A primeira versao punha os cinco num
    # painel so, e as barras de cada um ficavam intercaladas com as dos outros --
    # dava para ver o estoque total por vencimento, e nao o perfil de cada papel.
    import matplotlib.pyplot as plt

    d = vencimentos.dados_estoque_por_vencimento()
    fig = plt.figure()
    vencimentos.desenha_estoque_por_vencimento(d, fig)
    familias = [f for f in vencimentos.ORDEM_FAMILIAS
                if f in set(d["familia"])]
    assert len(fig.axes) == len(familias)
    # Cada painel tem as barras do SEU papel, e so.
    for ax, familia in zip(fig.axes, familias):
        assert len(ax.patches) == len(d[d["familia"] == familia])
    plt.close(fig)


def test_o_EIXO_DE_VENCIMENTOS_E_O_MESMO_nos_cinco():
    # E o que faz os paineis valerem mais que cinco graficos soltos: da para ver de
    # relance que a LTN se concentra ate 2032 e a NTN-B se espalha ate 2060.
    # Com eixos independentes, cada painel teria a sua escala de tempo e a
    # comparacao seria impossivel.
    import matplotlib.pyplot as plt

    d = vencimentos.dados_estoque_por_vencimento()
    fig = plt.figure()
    vencimentos.desenha_estoque_por_vencimento(d, fig)
    limites = {ax.get_xlim() for ax in fig.axes}
    assert len(limites) == 1, limites
    # E o eixo cobre TODOS os vencimentos, e nao so os do painel.
    assert len(fig.axes[-1].get_xticks()) == d["vencimento"].nunique()
    plt.close(fig)


def test_a_ESCALA_VERTICAL_E_A_MESMA_nos_cinco():
    # Com escala livre, a NTN-C sozinha -- 11 milhoes de titulos -- desenharia uma
    # barra do tamanho da maior LTN, de 251 milhoes, e o grafico diria o contrario
    # do que o dado diz.
    import matplotlib.pyplot as plt

    d = vencimentos.dados_estoque_por_vencimento()
    fig = plt.figure()
    vencimentos.desenha_estoque_por_vencimento(d, fig)
    limites = {ax.get_ylim() for ax in fig.axes}
    assert len(limites) == 1, limites
    # E o teto cobre a maior barra de todas.
    (_, teto), = limites
    assert teto >= d["quantidade_mil"].max() / 1000
    plt.close(fig)
