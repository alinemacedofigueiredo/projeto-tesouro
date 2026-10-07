import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pytest

from tesouro import config
from tesouro.graficos import custo, estilo, leiloes, vencimentos


# ---------------------------------------------------------------------------
# Candidato 1: perfil completo de vencimentos, ate 2084
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def perfil():
    return vencimentos.dados_perfil_completo()


def test_o_perfil_termina_em_2060_porque_a_ntnb1_ficou_de_fora(perfil):
    # Com a NTN-B1 o grafico ia ate 2084. Sem ela para em 2060: 2064, 2069, 2074,
    # 2079 e 2084 sao RendA+ e mais nada. Decisao da dona do projeto -- a NTN-B1 tem
    # regra propria de cupom e amortizacao e nao empilha com o resto.
    assert perfil.index.min() == 2026
    assert perfil.index.max() == 2060
    assert "NTN-B1" not in perfil.columns
    # Anos ja vencidos entram no CSV com financeiro zero; sem filtrar, o eixo
    # comecaria em 2010 com quatorze anos vazios.
    assert len(perfil) == 16


def test_o_que_ficou_de_fora_do_perfil_esta_dito_e_medido():
    # O asterisco do desenho promete um numero, e este teste confere que o numero
    # prometido e o numero que saiu.
    #
    # A IDENTIDADE E O QUE IMPORTA, e ela vale em qualquer mes: o que sai do
    # desenho e exatamente a diferenca entre o bruto e o completo. Os tres
    # valores mudam todo RMD; a subtracao, nao.
    bruto = vencimentos._perfil_bruto().sum().sum()
    completo = vencimentos.dados_perfil_completo().sum().sum()
    excluido = vencimentos.excluido_do_perfil()
    assert round(bruto - completo, 6) == round(excluido, 6), (
        "o que o asterisco promete nao e a diferenca entre bruto e completo")
    assert excluido > 0

    # Escala, do anexo de AGOSTO: 19,4 bi de NTN-B1 fora de um bruto de
    # 8.927,5. Remedido em 07/10/2026.
    assert round(excluido / 1000, 1) == 19.4
    assert round(bruto / 1000, 1) == 8927.5


def test_a_diferenca_contra_o_cronograma_esta_travada(perfil):
    # Os dois graficos de vencimento coexistem por decisao, e a diferenca entre os
    # totais e travada aqui. Ela tem duas parcelas, e as duas sao escolhas:
    #   16,6 bi -- o que a aba 2.2 nao lista (Demais, Securitizada, TDA);
    #   18,1 bi -- a NTN-B1, que a 2.2 lista e nos tiramos do desenho.
    # Somadas dao 34,7, que e exatamente o balde "Demais" do cronograma.
    # AS DUAS PARCELAS SAO IDENTIDADES, e nao numeros: a diferenca entre os dois
    # totais e o balde "Demais" da 3.4, e esse balde e a NTN-B1 mais os tres
    # titulos que a 2.2 nao lista. As duas valem em qualquer mes.
    total_perfil = perfil.sum().sum() / 1000
    anual = vencimentos.dados_cronograma_anual().sum() / 1000
    cronograma = anual.sum()
    excluido = vencimentos.excluido_do_perfil() / 1000

    assert round(cronograma - total_perfil, 1) == round(anual["Demais"], 1), (
        "a diferenca entre os graficos deixou de ser o balde da 3.4")
    assert round(anual["Demais"] - excluido, 1) > 0, (
        "o balde encolheu abaixo da NTN-B1 que tiramos do desenho")

    # Escala, do anexo de agosto, em R$ bilhoes.
    assert round(total_perfil, 1) == 8908.1
    assert round(cronograma, 1) == 8944.5
    assert round(cronograma - total_perfil, 1) == 36.3
    assert round(excluido, 1) == 19.4


def test_os_papeis_com_nome_batem_papel_a_papel_entre_as_duas_abas(perfil):
    # A diferenca NAO esta espalhada: todo papel com nome bate na casa decimal. A
    # 3.4 agrupa LTN e NTN-F numa coluna so, entao a comparacao soma os dois.
    # SO A IGUALDADE, sem valor cravado: o que este teste afirma e que a
    # diferenca entre as duas abas NAO esta espalhada pelos papeis com nome. Os
    # numeros mudam todo RMD e nao acrescentam nada a afirmacao -- travar os
    # dois lados contra um terceiro numero so criava trabalho mensal.
    cr = vencimentos.dados_cronograma_anual().sum() / 1000
    pf = perfil.sum() / 1000

    assert round(cr["LFT"], 1) == round(pf["LFT"], 1)
    assert round(cr["NTN-B"], 1) == round(pf["NTN-B"], 1)
    assert round(cr["NTN-C"], 1) == round(pf["NTN-C"], 1)
    assert round(cr["LTN / NTN-F"], 1) == round(pf["LTN"] + pf["NTN-F"], 1)
    # E os quatro tem de ter tamanho: uma igualdade entre dois zeros passaria.
    for valor in (cr["LFT"], cr["NTN-B"], cr["NTN-C"], cr["LTN / NTN-F"]):
        assert valor > 10, "papel com nome zerado; a igualdade ficou vazia"


def test_a_diferenca_e_o_que_a_aba_22_NAO_LISTA():
    # A CAUSA, medida em 19/08/2026 -- a spec listava isto como investigacao
    # posterior. Toda a diferenca esta no balde "Demais" da aba 3.4, que vale 34,7
    # bi. Desse balde, a aba 2.2 lista a NTN-B1 (18,1) e mais nada: "Demais" (12,9),
    # Divida Securitizada (3,4) e TDA (0,3) nao tem linha la, porque a 2.2 e uma
    # tabela titulo a titulo, por ISIN e vencimento, e esses tres nao entram nela.
    #
    # 12,9 + 3,4 + 0,3 = 16,6, na casa decimal. Este teste trava a decomposicao, e
    # nao so o total: se a diferenca mudar de tamanho E de causa ao mesmo tempo, o
    # teste do total sozinho poderia continuar passando.
    import pandas as pd

    from tesouro import config

    e = pd.read_csv(config.PROCESSED_DIR / "estoque_dpf.csv", parse_dates=["data"])
    u = e[(e["data"] == e["data"].max()) & (e["nivel"] == "DPMFi")]
    por_titulo = u.groupby("titulo")["valor_milhoes"].sum() / 1000

    fora_da_22 = ["Demais", "D\u00edvida Securitizada", "TDA"]

    # A DECOMPOSICAO E UMA IDENTIDADE: o balde da 3.4 e exatamente esses tres
    # mais a NTN-B1. Vale em qualquer mes, e e ela que impede o teste do total
    # de continuar passando se a diferenca mudar de tamanho E de causa junto.
    cr = vencimentos.dados_cronograma_anual().sum() / 1000
    assert round(por_titulo[fora_da_22].sum() + por_titulo["NTN-B1"], 1) == round(
        cr["Demais"], 1), "o balde da 3.4 deixou de ser os tres mais a NTN-B1"

    # E os tres tem de estar TODOS fora da 2.2 -- se um deles ganhasse linha la,
    # a decomposicao continuaria fechando e a causa teria mudado.
    for titulo in fora_da_22:
        assert por_titulo[titulo] > 0, f"{titulo} zerou; a decomposicao mudou"

    # A escala, do anexo de agosto, em R$ bilhoes. A Divida Securitizada subiu
    # de 2,6 para 3,8 -- o maior movimento relativo dos tres.
    assert round(por_titulo["Demais"], 1) == 12.9
    assert round(por_titulo["D\u00edvida Securitizada"], 1) == 3.8
    assert round(por_titulo["TDA"], 1) == 0.3
    assert round(por_titulo[fora_da_22].sum(), 1) == 17.0
    assert round(cr["Demais"], 1) == 36.3


def test_a_cauda_longa_e_toda_indexada_a_precos(perfil):
    # Depois de 2040 nao ha mais LFT, LTN nem NTN-F: so indice de precos.
    tarde = perfil[perfil.index > 2040]
    for familia in ("LFT", "LTN", "NTN-F"):
        assert tarde[familia].sum() == 0
    # O ULTIMO ANO E SO NTN-B, e e isso que a afirmacao do teste quer: a cauda e
    # toda indexada a precos. O valor anda todo RMD; a identidade nao.
    ultimo = perfil.index.max()
    assert round(perfil.loc[ultimo, "NTN-B"], 6) == round(
        perfil.loc[ultimo].sum(), 6), "o ultimo ano tem papel que nao e NTN-B"
    # Escala, do anexo de agosto: 104,4 bi em 2060.
    assert ultimo == 2060
    assert round(perfil.loc[ultimo].sum() / 1000, 1) == 104.4


def test_a_cauda_que_a_ntnb1_carregava_continua_no_dado(perfil):
    # Tirar do desenho nao e tirar do dado: quem precisar da cauda ate 2084 acha em
    # _perfil_bruto, e sao 6,5 bi de RendA+ em 2084.
    bruto = vencimentos._perfil_bruto()
    # A CAUDA CONTINUA NO BRUTO e nao no desenho -- e o ultimo ano dela e so
    # NTN-B1, que e o motivo de ela existir.
    fim = bruto.index.max()
    assert fim > vencimentos.dados_perfil_completo().index.max()
    assert round(bruto.loc[fim, "NTN-B1"], 6) == round(bruto.loc[fim].sum(), 6)
    # Escala, do anexo de julho: 6,7 bi em 2084.
    assert fim == 2084
    assert round(bruto.loc[fim].sum() / 1000, 1) == 6.7


# ---------------------------------------------------------------------------
# Candidato 2: custo de emissao contra o do estoque
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def emissao():
    return custo.dados_custo_emissao()


def test_o_custo_de_emissao_bate_com_o_medido(emissao):
    # Abas 4.3 (emissoes) e 4.2 (estoque) do anexo de agosto.
    u = emissao.iloc[-1]
    assert round(u["emissao"], 2) == 13.96
    assert round(u["estoque"], 2) == 13.06
    # O fato que o grafico existe para mostrar: emite-se mais caro do que se
    # carrega, entao a divida encarece sem que nada mude.
    assert u["emissao"] > u["estoque"]


def test_o_custo_de_emissao_comeca_em_dezembro_de_2010(emissao):
    # A CONTAGEM ERA CRAVADA EM 187 e crescia um por RMD. Vira relacao: um ponto
    # por mes de dez/2010 ate a data-base, sem buraco.
    assert emissao.index.min() == pd.Timestamp("2010-12-31")
    assert list(emissao.index) == list(pd.date_range(emissao.index.min(),
                                                     emissao.index.max(),
                                                     freq="ME"))
    assert len(emissao) > 180, "a serie encolheu"


def test_o_custo_do_estoque_e_o_mesmo_nos_dois_graficos():
    # Coerencia entre graficos que dividem fonte: o custo da DPMFi aparece no
    # grafico principal e neste, e tem de dar o mesmo numero.
    principal = custo.dados_custo().iloc[-1]["DPMFi"]
    candidato = custo.dados_custo_emissao().iloc[-1]["estoque"]
    assert abs(principal - candidato) < 1e-9


# ---------------------------------------------------------------------------
# Candidato 3: emissao anual por papel, dos leiloes
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def anual():
    return leiloes.dados_emissao_anual_papel()


def test_a_emissao_anual_por_papel_bate_com_o_medido(anual):
    assert round(anual.loc[2025, "LFT"], 1) == 39.6
    assert round(anual.loc[2025, "LTN"], 1) == 33.1
    assert round(anual.loc[2025, "NTN-B"], 1) == 18.1
    assert round(anual.loc[2025, "NTN-F"], 1) == 9.2
    assert round(anual.loc[2024, "LFT"], 1) == 65.1     # o ano da LFT


def test_cada_ano_da_emissao_por_papel_soma_100(anual):
    cols = [c for c in anual.columns
            if c not in ("total_milhoes", "cobertura_pct")]
    assert (anual[cols].sum(axis=1) - 100).abs().max() < 0.01


def test_os_leiloes_sao_cortados_na_ultima_competencia_do_rmd(anual):
    # O leiloes.csv vai alem do RMD, que para na data-base. Sem cortar, a
    # cobertura do ano corrente passaria de 100% -- mais meses de leilao do que
    # de RMD.
    #
    # O CORTE E O AGRUPAMENTO SAO PELA LIQUIDACAO, e nao pela data do leilao:
    # os leiloes do mes da base que liquidam no mes seguinte ficam de fora.
    from tesouro import rolagem

    base, _ = rolagem.base_do_rmd()
    ano = base.year
    # A FONTE E A MESCLADA, e nao leiloes.csv. Medido em 07/10/2026: a planilha
    # do Tesouro para em 13/08 -- ela trava no certificado do SERPRO -- e a base
    # do RMD passou a ser 31/08. A precondicao "o CSV vai alem do RMD" deixou de
    # valer para a planilha, e passou a valer so para rolagem.leiloes(), que
    # junta o provisorio da API e alcanca 24/09.
    bruto = rolagem.leiloes()
    assert bruto["data_leilao"].max() > base, \
        "nao ha leilao alem do RMD nem na fonte mesclada"
    # A RELACAO, que vale em qualquer mes: o total do ano corrente tem de ser
    # MENOR do que o mesmo total sem o corte. Se o corte sumir, os dois se
    # igualam e o teste cai -- sem depender de numero nenhum.
    sem_corte = bruto[bruto["data_leilao"].dt.year == ano]
    assert anual.loc[ano, "total_milhoes"] < sem_corte["financeiro_milhoes"].sum()

    # E a escala, remedida em 07/10/2026 com a base em 31/08: 1.079,8 bi.
    assert round(anual.loc[ano, "total_milhoes"] / 1000, 1) == 1079.8
    # E 2026 nao ganha cobertura: seis meses de RMD nao se comparam com doze de
    # leilao. Ver test_ano_sem_rmd_inteiro_nao_ganha_cobertura.
    assert pd.isna(anual.loc[ano, "cobertura_pct"])


def test_os_leiloes_de_venda_reproduzem_a_oferta_publica_da_aba_11():
    # O cruzamento que explica a cobertura: os leiloes NAO sao 100% da emissao, mas
    # sao 100% de um canal dela. De 2011 em diante, "Venda" bate com "Oferta
    # Publica" da aba 1.1 na casa do bilhao -- duas fontes independentes (o
    # historico de leiloes e o anexo do RMD) contando a mesma coisa.
    #
    # 2016 e nao antes: em 2015 o historico traz 775,0 bi contra 813,7 da aba 1.1,
    # 38,7 de diferenca. Nao investigado -- o intervalo em que as duas fontes casam
    # esta afirmado aqui, e o comeco dele e fato sobre o dado, nao escolha.
    import pandas as pd

    from tesouro import config

    l = pd.read_csv(config.PROCESSED_DIR / "leiloes.csv",
                    parse_dates=["data_liquidacao"])
    venda = l[l["tipo_leilao"] == "Venda"].copy()
    venda["ano"] = venda["data_liquidacao"].dt.year
    por_leilao = venda.groupby("ano")["financeiro_milhoes"].sum() / 1000

    f = pd.read_csv(config.PROCESSED_DIR / "funding_por_canal.csv",
                    parse_dates=["data"])
    e = f[(f["esfera"] == "DPMFi") & (f["operacao"] == "emissao")
          & (f["canal"] == "Oferta P\u00fablica")].copy()
    e["ano"] = e["data"].dt.year
    do_rmd = e.groupby("ano")["valor_milhoes"].sum() / 1000

    for ano in range(2016, 2026):
        assert abs(por_leilao[ano] - do_rmd[ano]) < 2.6, (
            f"{ano}: leiloes {por_leilao[ano]:.1f} x oferta publica {do_rmd[ano]:.1f}")


def test_ano_sem_rmd_inteiro_nao_ganha_cobertura():
    # 2006 tem doze meses de leilao contra dois de RMD (a serie comeca em nov/2006)
    # e 2026 tem seis. Dividir um pelo outro da 375%, e a nota da figura chegou a
    # anunciar "54,2% a 375,0%". Ano incompleto fica sem cobertura, e ponto.
    d = leiloes.dados_emissao_anual_papel(None, anos=100)
    assert pd.isna(d.loc[2006, "cobertura_pct"])
    assert pd.isna(d.loc[2026, "cobertura_pct"])
    assert d["cobertura_pct"].dropna().max() < 98.0
    # E a emissao por papel de 2006 continua desenhada -- so a cobertura sai.
    assert d.loc[2006, "total_milhoes"] > 0


def test_a_cobertura_dos_anos_fechados_fica_entre_90_e_98(anual):
    # A razao de este grafico ser candidato: a aba 1.2 cobre 100% da emissao e os
    # leiloes nao. Na janela de 12 anos a cobertura vai de 90,5% (2015) a 97,3%
    # (2020) -- a spec fala em "93% a 97%" porque mediu de 2017 em diante.
    fechados = anual[anual.index < 2026]["cobertura_pct"].dropna()
    assert round(fechados.min(), 1) == 90.5
    assert round(fechados.max(), 1) == 97.3
    assert round(fechados.loc[2024], 1) == 93.0
    # E nenhum papel entra no desenho sem cor -- nas DUAS janelas. A de 12 anos
    # nao tem NTN-D nem NTN-C; a completa alcanca 2000 e tem as duas, e foi assim
    # que a falta de cor da NTN-D apareceu, no dashboard e nao aqui.
    from tesouro.graficos import estilo
    for janela in (anual, leiloes.dados_emissao_anual_papel(anos=100)):
        for papel in janela.columns:
            if papel not in ("total_milhoes", "cobertura_pct"):
                assert papel in estilo.COR, f"sem cor para {papel}"


def test_a_nota_de_cobertura_aparece_no_desenho(anual):
    # A licao que custou seis rodadas na entrega 2: esta assercao precisa FALHAR
    # quando a linha que escreve a nota e apagada. Ver o Passo 6.
    estilo.aplicar_estilo()
    fig, ax = plt.subplots(figsize=(13, 6))
    leiloes.desenha_emissao_anual_papel(anual, ax, ano_parcial=2026)
    textos = " ".join(t.get_text() for t in ax.texts)
    plt.close(fig)
    assert "cobertura" in textos.lower()
    assert "93" in textos or "97" in textos
