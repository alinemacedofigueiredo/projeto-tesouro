"""A pagina contra o PAF: distancia, projecao e o arquivo."""
import pandas as pd
import pytest

from tesouro import config, rolagem
from tesouro.graficos import banda


def test_a_distancia_tem_o_sinal_certo_dos_dois_lados_e_zero_DENTRO():
    # Dentro da banda a distancia e zero, e nao "a distancia ate o meio". Quem esta
    # dentro cumpriu o que prometeu; medir distancia ate o centro inventaria um
    # alvo que o PAF nao define.
    assert banda.distancia(25.0, 21.0, 28.0) == 0.0
    assert banda.distancia(21.0, 21.0, 28.0) == 0.0
    assert banda.distancia(28.0, 21.0, 28.0) == 0.0
    assert banda.distancia(19.5, 21.0, 28.0) == pytest.approx(-1.5)
    assert banda.distancia(30.0, 21.0, 28.0) == pytest.approx(2.0)


def test_a_tabela_de_hoje_tem_uma_linha_por_indicador():
    d = banda.dados_hoje()
    assert len(d) == len(banda.INDICADORES)
    assert set(d.columns) >= {"indicador", "no_rmd", "hoje", "minimo", "maximo",
                              "distancia", "unidade", "rolado"}


def test_a_linha_do_CAMBIO_aparece_marcada_como_NAO_ROLADA():
    # Ele e a DPFe, que nao passa por leilao. Segura-lo e aceitavel; segura-lo em
    # silencio nao e, porque ele esta no denominador dos outros tres percentuais.
    d = banda.dados_hoje().set_index("indicador")
    assert d.loc["C\u00e2mbio", "rolado"] is False or \
        not bool(d.loc["C\u00e2mbio", "rolado"])
    assert bool(d.loc["Prefixado", "rolado"])


def test_a_tabela_diz_DE_QUANDO_e_o_hoje_e_quantos_leiloes_entraram():
    # Numero sem procedencia nao serve: quem le precisa saber se o "hoje" e de
    # ontem ou de tres semanas atras. A CONTAGEM e refeita aqui, direto do
    # leiloes.csv, e NAO chamando banda.quantos_leiloes_entraram() -- se os dois
    # lados chamassem a mesma funcao, uma mutacao nela moveria os dois juntos e o
    # teste nao pegaria nada (foi o que aconteceu na Task 8 com a projecao).
    d = banda.dados_hoje()
    base = d.attrs["leiloes_de"]
    hoje = d.attrs["hoje"]
    l = pd.read_csv(config.PROCESSED_DIR / "leiloes.csv",
                    parse_dates=["data_liquidacao"])
    entre = l[(l["data_liquidacao"] > base) & (l["data_liquidacao"] <= hoje)]
    esperado = entre["data_liquidacao"].nunique()

    html = banda.tabela(d, "tabela-hoje")
    assert "leil" in html
    assert str(esperado) in html


def test_prazo_medio_e_vincendo_mostram_a_DATA_e_nao_asterisco():
    # Decisao dela (ruling 17): as duas linhas paradas ganham a data do RMD ao
    # lado do valor -- "3,57 anos (30/06)" -- e nao um asterisco solto. O asterisco
    # sozinho e fraco demais para dois indicadores que andam ~25% da largura da
    # banda deles em sete semanas.
    d = banda.dados_hoje()
    html = banda.tabela(d, "tabela-hoje")
    base = d["data_base"].iloc[0]
    marca_da_data = f"({base:%d/%m})"
    assert marca_da_data in html
    assert "*" not in html


def test_dados_projecao_exercita_o_caminho_real_sem_tocar_rede():
    # 'registros=[]' evita a rede -- calendario_leiloes.dias_ate bateria na API do
    # Tesouro se registros=None. Este teste garante que o caminho da projecao, que
    # ninguem ainda exercitava nesta pagina, nao quebra sozinho.
    d = banda.dados_projecao(registros=[])
    assert len(d) == len(banda.INDICADORES)
    idx = d.set_index("indicador")
    assert not bool(idx.loc["C\u00e2mbio", "rolado"])
    assert bool(idx.loc["Prefixado", "rolado"])


def test_o_estoque_projetado_sai_como_numero_e_o_rodape_diz_a_premissa():
    # Decisao dela (ruling 16): a incerteza do estoque projetado (~+/-153 bi, o
    # erro medido do ritmo de emissao) vai ESCRITA no rodape, e nao vira faixa --
    # a premissa de Selic sozinha move a projecao so ~8 bi, ruido perto disso.
    d = banda.dados_projecao(registros=[])
    linha = d.set_index("indicador").loc["Estoque"]
    assert isinstance(linha["hoje"], float)
    html = banda.tabela(d, "tabela-projecao")
    assert "153" in html


def test_a_tabela_de_projecao_nao_e_identica_a_de_hoje():
    # Guarda contra copiar uma tabela para a outra: as premissas (leiloes vs.
    # Selic/inflacao) sao coisas diferentes, e a tabela tem de saber qual delas
    # esta desenhando.
    html_hoje = banda.tabela(banda.dados_hoje(), "tabela-hoje")
    html_projecao = banda.tabela(banda.dados_projecao(registros=[]),
                                 "tabela-projecao")
    assert html_hoje != html_projecao
    assert "leil\u00e3o" in html_hoje
    assert "Selic" in html_projecao


def test_o_denominador_do_RMD_e_travado_por_ESTRUTURA_nao_por_valor():
    # 'Demais' esta zerada desde 06/2006 (medido): com o dado de hoje, somar as
    # quatro colunas certas (INDEXADORES + PARADOS) ou somar TODAS as colunas do
    # composicao_dpf.csv da o MESMO NUMERO -- nenhum teste de VALOR pega se
    # _realizado_do_rmd voltar a somar comp.sum(axis=1) inteiro. Este teste trava
    # o CONJUNTO de colunas que a guarda confere, direto, sem depender de
    # _realizado_do_rmd nem de dado nenhum ter mudado de valor.
    certo = list(rolagem.INDEXADORES) + list(rolagem.PARADOS)
    banda._confere_colunas_do_denominador(certo)  # nao levanta

    with pytest.raises(ValueError):
        banda._confere_colunas_do_denominador(certo + ["Demais"])

    with pytest.raises(ValueError):
        banda._confere_colunas_do_denominador(list(rolagem.INDEXADORES))
