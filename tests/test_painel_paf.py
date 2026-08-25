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


@pytest.fixture(scope="module")
def pagina(tmp_path_factory):
    from tesouro.graficos import painel_paf

    destino = tmp_path_factory.mktemp("paf") / painel_paf.ARQUIVO
    return painel_paf.grava(destino).read_text(encoding="utf-8")


def test_a_pagina_tem_os_DOIS_blocos_recolhiveis(pagina):
    # Eram tres na primeira versao da spec. O historico saiu por decisao dela: era
    # analise, e nao monitoramento.
    import re

    corpo = pagina[pagina.index("</header>"):pagina.rindex("</main>")]
    assert corpo.count("<details class=\"secao") == 2
    # ASPAS SIMPLES: quem escreve o id e banda.tabela(), que monta a tabela com
    # aspas simples. O brief pedia aspas duplas aqui; a producao e que manda.
    assert "id='tabela-hoje'" in pagina
    assert "id='tabela-projecao'" in pagina
    assert re.search(r"<details class=\"secao[^\"]*\" open>", corpo)


def test_a_pagina_esta_na_barra_e_aponta_para_as_irmas(pagina):
    from tesouro.graficos import dashboard, painel_paf

    assert any(a == painel_paf.ARQUIVO for a, _ in dashboard.PAGINAS)
    assert f'href="{painel_paf.ARQUIVO}"' not in pagina
    for outra, _ in dashboard.PAGINAS:
        if outra != painel_paf.ARQUIVO:
            assert f'href="{outra}"' in pagina


def test_a_pagina_nao_tem_referencia_externa(pagina):
    import re

    externos = [m.group(1) for m in
                re.finditer(r'(?:src|href|xlink:href)\s*=\s*"([^"]*)"', pagina)
                if "://" in m.group(1)]
    assert externos == [], externos[:3]


def test_a_pagina_cabe_no_limiar_de_dez_megabytes(tmp_path):
    from tesouro.graficos import painel_paf

    caminho = painel_paf.grava(tmp_path / painel_paf.ARQUIVO)
    tamanho = caminho.stat().st_size
    # O TETO e o da spec (secao 5): a pagina e autocontida e tem de abrir com duplo
    # clique. O PISO e MEDIDO, e nao os 20 kB que o brief chutava -- esta pagina nao
    # tem SVG nenhum (REGISTRO e vazio) e mede 12.519 bytes, assim repartidos:
    #
    #     moldura sozinha (estilo, script, barra)   7.914
    #     tabela de hoje                            1.382
    #     tabela da projecao                        1.676
    #     achado, folha desta pagina e as tags      1.547
    #
    # Perder a tabela de hoje deixa 11.137; perder a da projecao deixa 10.843; e
    # perder o corpo inteiro deixa 7.914. O piso de 11.500 fica acima dos tres, e
    # por isso pega qualquer um dos casos -- que e para o que ele serve.
    #
    # Ele encolhe com o tempo, porem: se as tabelas ganharem linhas, perder uma
    # delas pode passar a caber acima de 11.500. Quem guarda isto de verdade e o
    # teste dos dois ids, logo acima; este aqui e a rede embaixo dele.
    assert tamanho > 11_500, "a pagina saiu pequena demais; algo nao entrou"
    assert tamanho < 10 * 1024 * 1024


def test_o_achado_do_historico_ficou_como_TEXTO(pagina):
    # O bloco dos sete graficos saiu; o numero fica. 70% pela banda original contra
    # 79% pela vigente, e 14 de 14 inversoes para dentro.
    assert "70%" in pagina and "79%" in pagina


def test_a_pagina_se_grava_com_a_REDE_BLOQUEADA_e_confessa_a_estimativa(
        tmp_path, monkeypatch):
    """O modo offline do pipeline, exercitado de ponta a ponta.

    O teste do pipeline confere que --sem-coleta PEDE registros=[]; este confere
    que pedir isso FUNCIONA -- os dois juntos cobrem o caminho, e nenhum deles
    sozinho cobre. Sem este, `grava(registros=[])` poderia levantar excecao e o
    outro teste seguiria verde, porque la o gravador esta stubado.

    O socket e bloqueado de proposito: se algum caminho ainda for a rede buscar o
    calendario publicado, isto fica vermelho em vez de passar devagar.
    """
    import socket

    from tesouro.graficos import painel_paf

    def rede_proibida(*args, **kwargs):
        raise AssertionError("a pagina do PAF foi a rede em modo offline")

    monkeypatch.setattr(socket, "socket", rede_proibida)
    monkeypatch.setattr(socket, "getaddrinfo", rede_proibida)

    caminho = painel_paf.grava(tmp_path / painel_paf.ARQUIVO, registros=[])
    html = caminho.read_text(encoding="utf-8")

    # A CONFISSAO: sem calendario publicado nao ha fronteira, e o rodape troca
    # "publicado ate <data> e estimado depois" por "inteiramente estimado". A
    # pagina sai mais fraca, mas sai DIZENDO que esta mais fraca -- numero sem
    # procedencia nao serve.
    assert "inteiramente estimado" in html
    assert "publicado at\u00e9" not in html
    # E continua sendo a pagina inteira, e nao um esqueleto.
    assert html.count("id='tabela-") == 2
