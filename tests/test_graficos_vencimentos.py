import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pytest

from tesouro import config
from tesouro.graficos import estilo, vencimentos


# ---------------------------------------------------------------------------
# Aba 3.4: o cronograma
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def anual():
    return vencimentos.dados_cronograma_anual()


def test_o_cronograma_anual_bate_com_o_medido(anual):
    # Aba 3.4 do anexo de julho, em R$ bilhoes. 2026 e 2031 sao PARCIAIS -- a
    # janela detalha ago/26 a jul/31, entao 2026 e ago-dez e 2031 e jan-jul.
    por_ano = anual.sum(axis=1) / 1000
    assert round(por_ano[2026], 1) == 584.1
    assert round(por_ano[2027], 1) == 1794.8
    assert round(por_ano[2028], 1) == 1183.8
    assert round(por_ano[2029], 1) == 1342.0
    assert round(por_ano[2030], 1) == 1239.9
    assert round(por_ano[2031], 1) == 657.8


def test_o_balde_entra_no_cronograma_e_o_total_fecha(anual):
    # Sem o balde da Task 2 o grafico mostraria 78% do estoque como se fosse tudo.
    por_ano = anual.sum(axis=1) / 1000
    assert round(por_ano["Ap\u00f3s 5 anos"], 1) == 2146.4
    assert round(por_ano.sum(), 1) == 8948.7


def test_os_dois_anos_das_pontas_sao_parciais(anual):
    # Comparar 584,1 com 1.794,8 sem saber que o primeiro e parcial e ler o
    # grafico errado.
    #
    # AS CONTAGENS ERAM CRAVADAS EM 6 E 6, e a janela anda todo RMD: ela
    # detalhava jul/26 a jun/31 e hoje detalha ago/26 a jul/31, ou seja CINCO
    # meses em 2026 e SETE em 2031. Agora saem do mes-base: a janela comeca no
    # mes seguinte a ele, entao o primeiro ano leva 12 - mes_base meses e o
    # ultimo leva mes_base. Vale em qualquer mes, e as duas somam 12.
    assert vencimentos.ANOS_PARCIAIS == (2026, 2031)
    mensal = vencimentos.dados_cronograma_mensal()
    meses = mensal.index.to_series().dt.year.value_counts()

    base = mensal.index.min() - pd.offsets.MonthEnd(1)
    primeiro, ultimo = vencimentos.ANOS_PARCIAIS
    assert meses[primeiro] == 12 - base.month
    assert meses[ultimo] == base.month
    assert meses[primeiro] + meses[ultimo] == 12
    assert meses[primeiro + 1] == 12


def test_o_cronograma_mensal_tem_os_sessenta_meses():
    m = vencimentos.dados_cronograma_mensal()
    total = m.sum(axis=1) / 1000

    # SESSENTA e invariante da aba: ela sempre detalha cinco anos. As DATAS
    # andam com o RMD e por isso saem do proprio dado, e nao cravadas -- a
    # janela comeca no mes seguinte a base e vai 59 meses adiante.
    assert len(m) == 60
    assert m.index.max() == m.index.min() + pd.offsets.MonthEnd(59)
    assert list(m.index) == list(pd.date_range(m.index.min(), periods=60,
                                               freq="ME"))

    # Aba 3.4 do anexo de julho, em R$ bilhoes.
    assert round(total.max(), 1) == 569.5
    assert total.idxmax() == pd.Timestamp("2027-03-31")
    assert round(total.iloc[0], 1) == 290.4
    # O balde NAO entra no detalhe mensal: ele nao tem mes.
    assert round(total.sum(), 1) == 6802.3


# ---------------------------------------------------------------------------
# Aba 3.1: as faixas da DPF, com a banda
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def faixas():
    return vencimentos.dados_faixas()


def test_as_faixas_da_dpf_batem_com_o_medido(faixas):
    # Aba 3.1 do anexo de julho.
    u = faixas.iloc[-1]
    assert round(u["At\u00e9 12 meses"], 1) == 18.9
    assert round(u["De 1 a 2 anos"], 1) == 13.7
    assert round(u["De 2 a 5 anos"], 1) == 42.4
    assert round(u["Acima de 5 anos"], 1) == 25.0


def test_cada_mes_das_faixas_soma_100(faixas):
    assert len(faixas.columns) == 4
    assert (faixas.sum(axis=1) - 100).abs().max() < 1e-9
    # O bloco DPF da aba 3.1 tem 246 meses, mas os dez primeiros (jan a out/2006)
    # vem ZERADOS -- a serie so comeca de fato em nov/2006, a mesma data em que a
    # do prazo medio comeca. Mantidos, eles viram dez meses somando zero por cento,
    # e a area empilhada abre com um buraco que parece dado faltando.
    assert faixas.index.min() == pd.Timestamp("2006-11-30")
    # A CONTAGEM ERA CRAVADA e crescia um por RMD. Vira relacao: um ponto por
    # mes, de nov/2006 ate a data-base, sem buraco.
    assert list(faixas.index) == list(pd.date_range(faixas.index.min(),
                                                    faixas.index.max(),
                                                    freq="ME"))
    assert len(faixas) > 230, "a serie encolheu"


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

    # AS TRES PROVAS ERAM TRES MESES CRAVADOS, e um deles (jul/26) saiu da
    # janela quando o RMD virou. Viraram relacoes, que valem em qualquer mes e
    # provam mais: a LFT bate em TODOS os meses, e nao so naquele setembro.

    # LFT nao paga cupom: a 3.4 e o perfil batem em todo mes da janela.
    for d in por_grupo.index:
        if pd.isna(por_grupo.get("LFT", pd.Series(dtype=float)).get(d)):
            continue
        p = pd.Period(d, "M")
        assert abs(por_grupo.loc[d, "LFT"]
                   - venceu(p, ["LFT", "LFT-TD1 Reserva"])) < 0.05, (
            f"LFT diverge em {d:%m/%Y}, e ela nao paga cupom")

    # NTN-B: existe mes em que NENHUMA vence e a 3.4 traz valor -- so cupom.
    so_cupom = [d for d in por_grupo.index
                if venceu(pd.Period(d, "M"), ["NTN-B", "NTN-B Principal"]) == 0.0
                and float(por_grupo.get("NTN-B", pd.Series(dtype=float))
                          .get(d, 0.0) or 0.0) > 1.0]
    assert so_cupom, "nenhum mes de cupom puro de NTN-B; a prova sumiu"
    # O primeiro deles, medido no anexo de julho: nov/2026, 26,1 bi.
    assert so_cupom[0] == pd.Timestamp("2026-11-30")
    assert round(por_grupo.loc[so_cupom[0], "NTN-B"], 1) == 26.1

    # LTN / NTN-F: cupom so em jan e jul, e nos outros meses a diferenca some.
    for d in por_grupo.index:
        if pd.isna(por_grupo.get("LTN / NTN-F",
                                 pd.Series(dtype=float)).get(d)):
            continue
        p = pd.Period(d, "M")
        dif = por_grupo.loc[d, "LTN / NTN-F"] - venceu(p, ["LTN", "NTN-F"])
        if d.month not in (1, 7):
            assert abs(dif) < 0.05, f"cupom fora de jan/jul em {d:%m/%Y}"

    # E um mes de cupom medido, como o teste original fazia: jan/2027, +27,2 bi.
    jan27 = pd.Timestamp("2027-01-31")
    assert round(por_grupo.loc[jan27, "LTN / NTN-F"]
                 - venceu(pd.Period(jan27, "M"), ["LTN", "NTN-F"]), 1) == 27.2

    # NAO SE AFIRMA QUE A DIFERENCA E POSITIVA EM TODO JAN/JUL, e isso e achado
    # e nao contorno. Medido em 02/09/2026, ela e positiva em 8 dos 10 meses de
    # cupom da janela e NEGATIVA em dois: jan/2029 (-3,78) e jan/2031 (-59,51),
    # justamente os dois com vencimento grande de LTN. Se fosse so cupom, nunca
    # seria negativa. Falta explicacao, e inventar uma assercao que passasse por
    # cima disso enterraria a pergunta.

    # E mesmo incluindo cupom a 3.4 soma o estoque, porque cada fluxo esta a preco
    # de curva: nao ha caixa nominal projetado, e nenhuma premissa de inflacao.
    assert round(cr["valor_milhoes"].sum() / 1000, 1) == 8948.7
    assert round(bruto.sum().sum() / 1000, 1) == 8933.1


def test_a_banda_do_vincendo_vem_das_duas_fontes():
    # 2022 so existe na aba 5.7; 2026 so existe no arquivo de referencia. As duas
    # tem de aparecer, ou uma das fontes nao esta sendo lida.
    b = vencimentos.banda_vincendo_12m()
    assert (b.loc[2022, "minimo"], b.loc[2022, "maximo"]) == (19.0, 23.0)
    assert (b.loc[2026, "minimo"], b.loc[2026, "maximo"]) == (18.0, 22.0)
    # A revisao de 2021 continua valendo sobre a original (24-29 vira 22-27).
    assert (b.loc[2021, "minimo"], b.loc[2021, "maximo"]) == (22.0, 27.0)


def test_o_vincendo_de_hoje_esta_dentro_da_banda_de_2026():
    # 18,91% contra a banda de 18 a 22. Nao e teste de politica: e o cruzamento
    # que pega banda digitada na escala errada, ou a faixa lida da coluna
    # errada. O valor sai da aba 3.1 do anexo de julho.
    faixas = vencimentos.dados_faixas()
    b = vencimentos.banda_vincendo_12m()
    hoje = faixas["At\u00e9 12 meses"].iloc[-1]
    assert round(hoje, 2) == 18.91
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
    # Mede os TRES papeis de valor unitario minusculo, e nao a exclusao inteira: a
    # NTN-B Principal tambem sai do grafico, mas por outro motivo -- ela nao e papel
    # de leilao -- e pesa 4,0% do financeiro da familia. Somada aqui, faria este
    # teste afirmar sobre ela uma coisa que nao e verdade.
    bruto = vencimentos._estoque_bruto()
    fora = bruto[bruto["titulo"].isin(vencimentos.PAPEIS_DE_VAREJO)]
    qtd = fora["quantidade_mil"].sum()
    fin = fora["financeiro_milhoes"].sum()
    em_qtd = qtd / bruto["quantidade_mil"].sum()
    em_fin = fin / bruto["financeiro_milhoes"].sum()
    assert em_qtd > 0.05, "os papeis de varejo deixaram de pesar na quantidade"
    assert em_fin < 0.02, "eles passaram a pesar no financeiro"
    # E a distancia entre as duas leituras e de mais de uma ordem de grandeza.
    assert em_qtd / em_fin > 10


def test_ha_um_grafico_por_papel_e_a_NTN_C_fica_de_fora():
    # A NTN-C tem UM vencimento e 11 milhoes de titulos: um grafico de uma barra so
    # nao e grafico. Os outros quatro tem de dez a dezessete vencimentos cada.
    assert vencimentos.PAPEIS_COM_GRAFICO == ("LFT", "LTN", "NTN-F", "NTN-B")
    d = vencimentos.dados_estoque_por_vencimento()
    assert "NTN-C" in set(d["familia"]), "a NTN-C sumiu do dado, e nao do grafico"
    assert len(d[d["familia"] == "NTN-C"]) == 1


def test_cada_papel_desenha_uma_barra_por_vencimento_dele():
    import matplotlib.pyplot as plt

    d = vencimentos.dados_estoque_por_vencimento()
    for familia in vencimentos.PAPEIS_COM_GRAFICO:
        fig, ax = plt.subplots()
        vencimentos.desenha_estoque_de(d, ax, familia)
        assert len(ax.patches) == len(d[d["familia"] == familia]), familia
        plt.close(fig)


def test_as_barras_sao_DEITADAS_e_em_ordem_cronologica():
    # Deitadas porque o rotulo e uma data completa -- 01/07/2026 -- e data em pe
    # vira etiqueta girada. E o vencimento mais proximo em cima, que e a ordem em
    # que a divida vence e a ordem em que se le uma lista.
    import matplotlib.pyplot as plt

    d = vencimentos.dados_estoque_por_vencimento()
    fig, ax = plt.subplots()
    vencimentos.desenha_estoque_de(d, ax, "LTN")
    # Barra deitada: a altura e fixa e a largura varia.
    alturas = {round(p.get_height(), 6) for p in ax.patches}
    assert len(alturas) == 1
    assert len({round(p.get_width(), 6) for p in ax.patches}) > 1

    rotulos = [r.get_text() for r in ax.get_yticklabels()]
    datas = [pd.to_datetime(r, dayfirst=True) for r in rotulos]
    assert datas == sorted(datas)
    # invert_yaxis(): o primeiro rotulo fica em cima.
    assert ax.get_ylim()[0] > ax.get_ylim()[1]
    plt.close(fig)


def test_a_quantidade_vai_ESCRITA_NA_FRENTE_da_barra():
    # E o numero que se foi ver: com quinze barras, ler a altura contra o eixo e
    # mirar.
    import matplotlib.pyplot as plt

    d = vencimentos.dados_estoque_por_vencimento()
    g = d[d["familia"] == "LTN"]
    fig, ax = plt.subplots()
    vencimentos.desenha_estoque_de(d, ax, "LTN")
    assert len(ax.texts) == len(g)
    maior = g["quantidade_mil"].max() / 1000
    assert estilo.num_br(maior, 1) in [x.get_text() for x in ax.texts]
    plt.close(fig)


def test_cada_papel_tem_a_SUA_escala():
    # Sao quatro graficos separados, e o que se compara dentro de cada um e um
    # vencimento com o outro do MESMO papel. Com escala comum a NTN-B ficaria
    # espremida num quinto da largura: a maior LTN tem 251 milhoes de titulos e a
    # maior NTN-B tem 54.
    import matplotlib.pyplot as plt

    d = vencimentos.dados_estoque_por_vencimento()
    tetos = {}
    for familia in vencimentos.PAPEIS_COM_GRAFICO:
        fig, ax = plt.subplots()
        vencimentos.desenha_estoque_de(d, ax, familia)
        tetos[familia] = ax.get_xlim()[1]
        plt.close(fig)
    assert len(set(tetos.values())) == len(tetos), tetos
    assert tetos["LTN"] > tetos["NTN-B"] * 3


def test_a_altura_da_figura_acompanha_o_numero_de_vencimentos():
    # A LFT tem dezessete vencimentos e a NTN-F tem seis: com altura fixa, um sai
    # apertado e o outro com metade da figura vazia.
    alta = vencimentos.altura_do_estoque("LFT")
    baixa = vencimentos.altura_do_estoque("NTN-F")
    assert alta > baixa
    assert baixa >= 2.6


def test_a_NTN_B_Principal_fica_de_fora_do_estoque_em_quantidade():
    # Ela dividia sete das quinze datas da NTN-B, e as duas saiam como barras com a
    # MESMA data e a MESMA cor -- que se le como dado repetido, e foi assim que a
    # dona do projeto perguntou.
    #
    # Nao e papel de leilao: CONFERIDO em 19.739 linhas, onde ela nao aparece
    # nenhuma vez. E Tesouro Direto, e o grafico nao leva Tesouro Direto.
    assert "NTN-B Principal" in vencimentos.FORA_DO_ESTOQUE
    # E NAO em PAPEIS_DE_VAREJO: o motivo dela e outro -- ver a constante.
    assert "NTN-B Principal" not in vencimentos.PAPEIS_DE_VAREJO
    d = vencimentos.dados_estoque_por_vencimento()
    assert "NTN-B Principal" not in set(d["titulo"])
    assert set(d[d["familia"] == "NTN-B"]["titulo"]) == {"NTN-B"}
    assert len(d[d["familia"] == "NTN-B"]) == 15


def test_nenhuma_familia_repete_um_vencimento():
    # A GUARDA GERAL, e nao so a da NTN-B: duas barras com a mesma data e a mesma
    # cor nao dizem que sao papeis diferentes, e quem le conta a divida duas vezes
    # ou acha que ha um defeito. Se um dia entrar outro papel dividindo data com o
    # da familia dele, e aqui que alguem descobre.
    d = vencimentos.dados_estoque_por_vencimento()
    repetidos = d[d.duplicated(["familia", "vencimento"], keep=False)]
    assert repetidos.empty, (
        "ha vencimento repetido dentro de uma familia:"
        + repetidos[["familia", "vencimento", "titulo"]].to_string())


def test_a_Principal_CONTINUA_no_perfil_por_ano():
    # Ela sai do grafico de QUANTIDADE, e nao da divida. O perfil conta REAIS a
    # vencer, e R$ 91,5 bi de NTN-B Principal sao divida que o Tesouro deve e que
    # vence naquele ano -- 1,03% do estoque. Tirar la seria contar errado.
    bruto = vencimentos._perfil_bruto()
    e = pd.read_csv(config.PROCESSED_DIR / "estoque_titulos_vencimento.csv",
                    parse_dates=["data", "vencimento"])
    u = e[(e["data"] == e["data"].max()) & (e["titulo"] == "NTN-B Principal")]
    assert not u.empty
    for ano, grupo in u.groupby(u["vencimento"].dt.year):
        assert bruto.loc[ano, "NTN-B"] >= grupo["financeiro_milhoes"].sum() - 0.01


def test_o_asterisco_diz_o_numero_excluido():
    # Agora vive na legenda da pagina, e nao na figura: sao quatro figuras, e
    # repetir a mesma ressalva em todas seria ruido. O teste confere que o numero
    # existe e e o medido.
    qtd, fin = vencimentos.excluido_do_estoque()
    assert qtd > 400000, "o Tesouro Direto encolheu no dado"
    # Era < 30.000 quando so saiam os tres papeis de valor unitario minusculo. A
    # NTN-B Principal sozinha traz R$ 91,5 bi, e por isso o teto subiu.
    assert fin < 130000
