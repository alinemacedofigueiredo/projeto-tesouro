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


def test_a_guarda_do_denominador_olha_o_CSV_e_nao_a_propria_constante():
    """As duas perguntas que so podem ser feitas ao dado.

    A PRIMEIRA versao desta guarda recebia list(INDEXADORES) + list(PARADOS) e
    comparava contra set(INDEXADORES) | set(PARADOS): os dois lados saiam da
    mesma constante, era impossivel divergir, e a guarda nao podia disparar. O
    teste que a acompanhava tambem montava as listas a mao -- testava a funcao,
    nunca o lugar onde ela e chamada. Achado na revisao da branch.
    """
    do_csv = list(rolagem.INDEXADORES) + list(rolagem.PARADOS)

    # 'Demais' pode estar no CSV: ela fica fora do denominador de proposito.
    assert (banda._confere_colunas_do_denominador(do_csv + ["Demais"])
            == list(rolagem.INDEXADORES) + list(rolagem.PARADOS))

    # Rotulo desacentuado pelo parser: a coluna some e o indexador iria a ZERO
    # em silencio. E o defeito do ruling 4, agora travado do lado do dado.
    sem_acento = [c.replace("\u00cd", "I").replace("\u00e7", "c")
                  for c in do_csv]
    with pytest.raises(ValueError, match="zera o indexador"):
        banda._confere_colunas_do_denominador(sem_acento)

    # Indexador novo no CSV: ficaria fora do denominador sem ninguem ver.
    with pytest.raises(ValueError, match="indexador novo"):
        banda._confere_colunas_do_denominador(do_csv + ["Hibrido"])


def test_o_denominador_IGNORA_a_coluna_Demais_mesmo_quando_ela_NAO_e_zero():
    """O teste que so um dado sintetico consegue fazer.

    No CSV de verdade 'Demais' e zero desde 06/2006, e por isso somar as quatro
    colunas certas ou somar o pivo inteiro da EXATAMENTE o mesmo numero. Nenhum
    teste contra o dado real distingue as duas coisas -- confirmado na revisao,
    que trocou o denominador por comp.sum(axis=1) e viu a suite inteira passar.

    Com 'Demais' diferente de zero as duas contas divergem, e a diferenca e
    grande de proposito: 1.000 de 'Demais' sobre 9.000 de denominador muda cada
    percentual em ~10%.
    """
    comp = pd.DataFrame(
        {"Prefixado": [2000.0], "\u00cdndice Pre\u00e7os": [2000.0],
         "Taxa Flutuante": [4000.0], "C\u00e2mbio": [1000.0],
         "Demais": [1000.0]},
        index=pd.DatetimeIndex([pd.Timestamp("2026-06-30")], name="data"))

    pct = banda._percentuais(comp)

    # Denominador 9.000 (sem 'Demais'), e nao 10.000.
    assert pct.loc[pct.index[0]].sum() == pytest.approx(100.0)
    assert pct.iloc[0]["Prefixado"] == pytest.approx(2000 / 9000 * 100)
    assert "Demais" not in pct.columns


def test_o_percentual_de_HOJE_na_data_base_reproduz_o_do_RMD():
    """A ancora dos numeros que a pagina publica.

    ESTE E O TESTE QUE FALTAVA. A revisao trocou "prefixado_pct" por
    "taxa_flutuante_pct" em _valores_de_hoje -- a pagina passaria a publicar
    Prefixado 52,81% (fora da banda por +2,81 pp) e Taxa Flutuante 20,15% (fora
    por -0,85 pp), invertendo o veredito dos dois indicadores de maior peso -- e
    os quinze testes deste arquivo passaram. Nenhum comparava o valor de 'hoje'
    com coisa alguma.

    A ancora e a identidade da JANELA NULA: rolar o estoque do RMD ate a propria
    data-base nao emite, nao resgata e nao apropria nada, entao 'hoje' tem de
    devolver o RMD de volta. Vale contra qualquer fiacao trocada, contra erro de
    unidade, e sobrevive ao pipeline rodar de novo, porque os dois lados andam
    juntos quando o dado muda -- mas NAO andam juntos quando o codigo erra, que
    e a diferenca que interessa.
    """
    base, _ = banda._realizado_do_rmd()
    d = banda.dados_hoje(hoje=base).set_index("indicador")

    rolados = d[d["rolado"].astype(bool)]
    assert len(rolados) >= 4, "a ancora precisa cobrir os indicadores rolados"
    for indicador, linha in rolados.iterrows():
        assert linha["hoje"] == pytest.approx(linha["no_rmd"], rel=1e-9), (
            f"{indicador}: rolar ate a propria data-base do RMD tem de "
            f"devolver o valor do RMD, e devolveu {linha['hoje']}")

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


def test_a_guarda_e_ALIMENTADA_PELO_CSV_e_nao_pela_constante(tmp_path,
                                                             monkeypatch):
    """Trava o LUGAR onde a guarda e chamada, e nao apenas a guarda.

    Passar comp.columns em vez da constante conserta o defeito, mas nada impede
    alguem de realimentar a constante depois: medido, os outros dezesseis testes
    ficam todos verdes se isso acontecer, porque nenhum deles poe um CSV
    diferente na frente de _realizado_do_rmd.

    Este poe. Um 'Hibrido' no composicao_dpf.csv tem de fazer a leitura levantar.
    Se a guarda estiver olhando a constante, ela nunca enxerga o 'Hibrido', nao
    levanta, e este teste fica vermelho.
    """
    import shutil

    from tesouro import config

    for nome in ("composicao_dpf.csv", "prazo_medio_por_titulo.csv",
                 "vencimentos_faixa.csv", "estoque_dpf.csv"):
        shutil.copy(config.PROCESSED_DIR / nome, tmp_path / nome)

    # Um indexador que o parser passou a devolver e que ninguem poe no
    # denominador: sem a guarda, ele sai do percentual em silencio.
    comp = pd.read_csv(tmp_path / "composicao_dpf.csv", parse_dates=["data"])
    ultima = comp["data"].max()
    intrusa = pd.DataFrame({"data": [ultima], "indexador": ["Hibrido"],
                            "valor_milhoes": [123456.0]})
    pd.concat([comp, intrusa], ignore_index=True).to_csv(
        tmp_path / "composicao_dpf.csv", index=False)

    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)

    with pytest.raises(ValueError, match="indexador novo"):
        banda._realizado_do_rmd()

def test_o_ESTOQUE_nao_traz_distancia_na_tabela_de_hoje_mas_traz_na_projecao():
    """A banda de estoque e alvo de 31/12, e em agosto o estoque nao chegou la.

    Medido nos 23 anos de PAF: o estoque de AGOSTO caiu fora da banda de
    dezembro em 18 deles, e 14 desses 18 fecharam o ano DENTRO. Publicar
    "R$ -610 bi" como distancia convida a ler descumprimento onde so ha
    calendario -- e o leitor desta pagina leva o numero para os colegas.

    Na projecao a distancia fica: la os dois lados sao 31/12.
    """
    import re

    hoje = banda.tabela(banda.dados_hoje(), "t-hoje")
    proj = banda.tabela(banda.dados_projecao(registros=[]), "t-proj")

    def celula_do_estoque(html):
        linha = re.search(r"<tr[^>]*><td>Estoque</td>(.*?)</tr>", html, re.S)
        celulas = re.findall(r"<td[^>]*>(.*?)</td>", linha.group(0), re.S)
        return celulas[-1]

    assert "alvo de 31/12" in celula_do_estoque(hoje)
    assert "bi" not in celula_do_estoque(hoje), (
        "a tabela de hoje nao pode publicar distancia em reais para o estoque")
    # A projecao continua medindo, e neste dado ela esta dentro.
    assert "alvo de 31/12" not in celula_do_estoque(proj)


def test_um_ano_SEM_BANDA_no_arquivo_falha_em_voz_alta():
    """Antes ele saia como tabela VAZIA, com o rodape normal por cima.

    paf_bandas.csv e digitado a mao e cobre 2003-2026. Em janeiro de 2027, antes
    de alguem digitar o PAF novo, _linhas() pulava cada indicador em silencio e a
    pagina publicava uma tabela de conformidade em branco -- ou, pior, faltando
    so alguns indicadores. Classe "dependencia de relogio" mais "caminho nunca
    exercitado": nenhum teste passava por ali porque hoje e 2026.
    """
    with pytest.raises(LookupError, match="paf_bandas"):
        banda._linhas({}, 2099)


def test_a_coluna_da_banda_avisa_quando_ela_foi_REVISADA():
    """Em 8 dos 23 anos a banda mudou no meio do ano.

    A coluna sempre mostrou a vigente sem dizer que era a vigente -- e logo
    abaixo da tabela a pagina afirma, em negrito, que em 14 de 14 casos a revisao
    pos o realizado DENTRO. As duas coisas juntas, sem aviso, enganam.

    Em 2026 nao houve revisao, entao a celula do dado real sai limpa; o caso
    revisado e montado a mao para o ramo nao ficar sem teste.
    """
    sem_revisao = pd.Series({"minimo": 21.0, "maximo": 25.0,
                             "minimo_original": 21.0, "maximo_original": 25.0,
                             "unidade": "pp"})
    assert "revisada" not in banda._banda_da_celula(sem_revisao)

    revisada = pd.Series({"minimo": 21.0, "maximo": 25.0,
                          "minimo_original": 20.0, "maximo_original": 24.0,
                          "unidade": "pp"})
    celula = banda._banda_da_celula(revisada)
    assert "revisada" in celula
    assert "20,00 a 24,00" in celula, "a banda ORIGINAL tem de aparecer"

    # E o dado de verdade de 2026 nao traz o aviso, porque nao houve revisao.
    assert "revisada" not in banda.tabela(banda.dados_hoje(), "t")


def test_o_rodape_diz_MEDIA_e_nao_MAXIMO_do_erro_de_emissao():
    """153 bi e o erro MEDIO de dez anos de backtest, nao o pior caso.

    O texto dizia "errou ate 153 bi", que le como teto. Numa pagina cuja unica
    quantificacao de incerteza do estoque projetado e essa frase, dizer "ate"
    subestima -- metade dos anos foi pior. Achado na revisao da branch.
    """
    html = banda.tabela(banda.dados_projecao(registros=[]), "t")
    assert "M{E}DIA".replace("{E}", "\u00c9") in html
    assert "errou at{E}".replace("{E}", "\u00e9") not in html
    assert "153" in html


def test_o_rodape_de_hoje_diz_o_QUE_NAO_ESTA_MODELADO():
    """Spec 4.5 e 4.6: o que a rolagem nao cobre tem de estar escrito.

    Faltavam as tres frases. A do Tesouro Direto e a que mais importa: o residuo
    e da ordem de 0,25 pp nesta janela, e a pagina publica distancias de 0,85 pp
    -- sem a frase o leitor nao tem como saber que a margem e dessa ordem.
    """
    html = banda.tabela(banda.dados_hoje(), "t")
    assert "Tesouro Direto" in html
    assert "0,25 pp" in html
    assert "d{I}vida".replace("{I}", "\u00ed") in html      # o cambio e a DPFe
    assert "it{A}lico".replace("{A}", "\u00e1") in html     # o que a marca quer dizer
