"""A pagina contra o PAF: distancia, projecao e o arquivo."""
import os
import pathlib

import re

import pandas as pd
import pytest

from tesouro import config, rolagem
from tesouro.graficos import banda

RAIZ_DO_PROJETO = pathlib.Path(
    config.PROCESSED_DIR).parent.parent


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
    # OS DOIS ARQUIVOS, lidos aqui direto -- e nao via rolagem.leiloes(), que e
    # o que a producao chama. Desde 25/08/2026 a rolagem conta tambem o leilao
    # que a planilha ainda nao traz (decisao dela), e recontar so pelo
    # leiloes.csv passou a dar menos. Chamar rolagem.leiloes() aqui consertaria
    # o numero e destruiria o teste: os dois lados andariam juntos sob qualquer
    # mutacao. Entao a recontagem refaz a juncao, a mao.
    l = pd.read_csv(config.PROCESSED_DIR / "leiloes.csv",
                    parse_dates=["data_liquidacao"])
    provisorio = config.PROCESSED_DIR / "leiloes_recentes.csv"
    if provisorio.exists():
        r = pd.read_csv(provisorio, parse_dates=["data_liquidacao"])
        r = r[r["data_liquidacao"] > l["data_liquidacao"].max()]
        l = pd.concat([l[["data_liquidacao"]], r[["data_liquidacao"]]],
                      ignore_index=True)
    entre = l[(l["data_liquidacao"] > base) & (l["data_liquidacao"] <= hoje)]
    esperado = entre["data_liquidacao"].nunique()

    html = banda.tabela(d, "tabela-hoje")
    # NO RODAPE, E COM A FRASE INTEIRA. "str(esperado) in html" casava com
    # qualquer numero da pagina: com esperado == 20 ele passava por causa de
    # "2026", de "20,15" e de "9.268". Achado na revisao da branch.
    rodape = re.search(r"<p class='rodape'>(.*?)</p>", html, re.S).group(1)
    assert f"{esperado} dia(s) de leil\u00e3o entraram na rolagem" in rodape


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
    # registros=[] PARA NAO TOCAR A REDE. Sem isto a fixture busca o
    # calendario na API do Tesouro quatro vezes -- uma da projecao e uma por
    # tabela da simulacao -- e este projeto tem um teste dedicado a garantir
    # que a rede nao seja tocada sem necessidade. Nenhum teste que usa esta
    # fixture depende de dado real do calendario (conferido na re-revisao).
    return painel_paf.grava(destino, registros=[]).read_text(encoding="utf-8")


def test_a_pagina_tem_os_TRES_blocos_recolhiveis(pagina):
    # Eram tres na primeira versao da spec, cairam para dois quando o historico
    # saiu por decisao dela -- era analise, e nao monitoramento -- e voltaram a
    # tres com a Task 5, que acrescentou o bloco da simulacao.
    import re

    corpo = pagina[pagina.index("</header>"):pagina.rindex("</main>")]
    assert corpo.count("<details class=\"secao") == 3
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

    caminho = painel_paf.grava(tmp_path / painel_paf.ARQUIVO, registros=[])
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

    O CASO SINTETICO CONTINUA, e agora o real tambem: em 26/08/2026 o Tesouro
    revisou 2026, entao a tabela de hoje passou a trazer o aviso de verdade.
    Ate aqui este teste afirmava o contrario -- "em 2026 nao houve revisao" --
    e ficou vermelho no dia em que houve, que e o que se espera dele.
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

    # E O DADO DE VERDADE TRAZ O AVISO, porque 2026 foi revisado. Este e o
    # ramo que importa: o sintetico acima prova que a funcao sabe avisar, e
    # este prova que ela AVISA no dado que a pagina publica.
    real = banda.tabela(banda.dados_hoje(), "t")
    assert "revisada" in real, (
        "2026 foi revisado em 26/08 e a tabela tem de dizer isso")
    assert "21,00 a 25,00" in real, (
        "a banda ORIGINAL do prefixado tem de aparecer junto do aviso")


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

def test_o_rodape_do_calendario_PUBLICADO_tem_teste(monkeypatch):
    """O ramo que a producao usa era o unico sem teste.

    Todo teste desta pagina chama dados_projecao(registros=[]) para nao tocar a
    rede -- e com isso so exercita o ramo "calendario inteiramente estimado". A
    frase que o pipeline de verdade escreve, "de calendario publicado ate DD/MM
    e estimado depois", podia ser trocada por qualquer coisa sem ficar vermelho.
    Achado na revisao da branch.

    A amostra congelada de tests/fixtures/api_leiloes resolve sem rede.
    """
    import json
    import pathlib as _pathlib

    fixtures = _pathlib.Path(__file__).parent / "fixtures" / "api_leiloes"
    registros = json.loads(
        (fixtures / "calendario.json").read_text(encoding="utf-8"))["registros"]

    d = banda.dados_projecao(registros=registros)
    html = banda.tabela(d, "t")

    fronteira = d.attrs["premissa"]["fronteira_do_calendario"]
    assert fronteira is not None, "a amostra tem de ter calendario publicado"
    assert "publicado at\u00e9" in html
    assert f"{fronteira:%d/%m/%Y}" in html
    assert "inteiramente estimado" not in html

    # NAO se exige que a CONTAGEM mude. Era o que este teste fazia, e estava
    # errado: quando o estimador acerta o calendario publicado -- que e o
    # objetivo dele -- as duas contagens coincidem e o teste quebrava por acerto.
    # Aconteceu em 25/08/2026, com 33 dias dos dois lados. O que tem de mudar e
    # a PROCEDENCIA declarada, e isso as tres assercoes acima ja travam.
    so_estimado = banda.dados_projecao(registros=[])
    assert so_estimado.attrs["premissa"]["fronteira_do_calendario"] is None


def test_os_numeros_do_ACHADO_historico_saem_do_DADO_MEDIDO():
    """70%, 79% e 14-de-14 eram prosa fixa, sem nada conferindo.

    E A FONTE NAO E OBVIA. A coluna 'realizado' do referencia/paf_bandas.csv NAO
    serve para recontar: ela nao tem uma unica linha de vincendo_12m_pct, e tem
    23 de prazo_medio onde a conta da spec usa 21. Recontar por ela da 69% / 78%
    / 13 -- tres numeros diferentes dos tres que a pagina publica, e todos
    errados. Foi o que aconteceu com duas tentativas independentes de reconta.

    A fonte e o dado MEDIDO em data/processed/, o mesmo que _realizado_do_rmd()
    ja le -- so que no fechamento de cada dezembro. Reconstruido assim, bate com
    a tabela da spec 3.2 linha por linha: 102 de 146 e 116 de 146.
    """
    from tesouro.graficos import painel_paf

    fecha = _fechamentos_de_dezembro()
    b = pd.read_csv(RAIZ_DO_PROJETO / "referencia" / "paf_bandas.csv")
    orig = b[b["versao"] == "original"].set_index(["indicador", "ano"])
    rev = b[b["versao"] == "revisado"].set_index(["indicador", "ano"])

    n = dentro_original = dentro_vigente = 0
    inversoes = para_dentro = 0
    for chave, _, _ in banda.INDICADORES:
        for ano in sorted(set(orig.loc[chave].index)):
            if ano not in fecha.index or pd.isna(fecha.loc[ano, chave]):
                continue
            real = fecha.loc[ano, chave]
            o = orig.loc[(chave, ano)]
            d_o = o["minimo"] <= real <= o["maximo"]
            if (chave, ano) in rev.index:
                r = rev.loc[(chave, ano)]
                d_v = r["minimo"] <= real <= r["maximo"]
            else:
                d_v = d_o
            n += 1
            dentro_original += d_o
            dentro_vigente += d_v
            if d_o != d_v:
                inversoes += 1
                para_dentro += d_v

    assert n == 146, f"a contagem da spec 3.2 e sobre 146 pares, e deu {n}"
    assert f"{round(100 * dentro_original / n)}%" in painel_paf._ACHADO
    assert f"{round(100 * dentro_vigente / n)}%" in painel_paf._ACHADO
    assert f"{inversoes} de {inversoes}" in painel_paf._ACHADO
    assert para_dentro == inversoes, (
        "a pagina afirma que TODAS as inversoes puseram o realizado dentro; "
        f"foram {para_dentro} de {inversoes}")


def _fechamentos_de_dezembro():
    """Os sete indicadores do PAF em cada 31/12, do dado medido.

    Mesma leitura que banda._realizado_do_rmd faz para uma data so.
    """
    c = pd.read_csv(config.PROCESSED_DIR / "composicao_dpf.csv",
                    parse_dates=["data"])
    comp = c.pivot_table(index="data", columns="indexador",
                         values="valor_milhoes", aggfunc="sum").fillna(0.0)
    pct = banda._percentuais(comp)

    p = pd.read_csv(config.PROCESSED_DIR / "prazo_medio_por_titulo.csv",
                    parse_dates=["data"])
    prazo = p[(p["nivel"] == "DPF") & p["entidade"].isna()
              & p["titulo"].isna()].set_index("data")["prazo_anos"]

    v = pd.read_csv(config.PROCESSED_DIR / "vencimentos_faixa.csv",
                    parse_dates=["data"])
    fx = v[v["nivel"] == "DPF"].pivot_table(
        index="data", columns="faixa", values="valor_milhoes", aggfunc="sum")

    e = pd.read_csv(config.PROCESSED_DIR / "estoque_dpf.csv",
                    parse_dates=["data"])
    ag = e[e["entidade"].isna() & e["titulo"].isna()]
    est = ag[ag["nivel"] == "DPF em poder do publico"].set_index(
        "data")["valor_milhoes"] / 1000

    d = pd.DataFrame({
        "prefixado_pct": pct["Prefixado"],
        "indice_precos_pct": pct["\u00cdndice Pre\u00e7os"],
        "taxa_flutuante_pct": pct["Taxa Flutuante"],
        "cambio_pct": pct["C\u00e2mbio"],
        "prazo_medio_anos": prazo,
        "vincendo_12m_pct": fx["At\u00e9 12 meses"] / fx.sum(axis=1) * 100,
        "estoque_bilhoes": est,
    })
    d = d[d.index.month == 12]
    d.index = d.index.year
    return d

def test_as_frases_do_rodape_de_hoje_chegam_INTEIRAS():
    """Uma frase emendada no meio de outra passa por todo teste de substring.

    Aconteceu: a frase do estoque foi inserida por indice e caiu entre "furou a"
    e "banda.", produzindo "...concluir que um indicador furou a O estoque nao
    traz distancia: [...] dentro dela. banda." Os testes que procuravam pedaco
    de texto no rodape continuaram todos verdes, porque TODOS os pedacos
    continuavam la -- so a ordem tinha mudado. Quem pegou foi abrir a pagina no
    navegador.

    Aqui ficam as frases INTEIRAS, com o ponto final, que e o que a emenda
    quebra.
    """
    import re

    texto = re.sub(r"<[^>]+>", "", banda.tabela(banda.dados_hoje(), "t"))
    for frase in ("antes de concluir que um indicador furou a banda.",
                  "o prazo m{E}dio e o vincendo ficam para a entrega 5.",
                  "14 dessas fecharam o ano dentro dela."):
        esperada = frase.replace("{E}", "\u00e9")
        assert esperada in texto, f"frase quebrada no rodape: {esperada!r}"

def test_nenhuma_frase_do_rodape_COLA_na_seguinte():
    """O primo da frase emendada, e o teste anterior nao pegava.

    Os rodapes desta pagina sao montados por concatenacao de literais, e cada
    fragmento tem de terminar com o espaco que o separa do proximo. Esquecer esse
    espaco produz "fecharam o ano dentro dela.O denominador desta tabela" -- que
    e legivel o bastante para passar despercebido numa leitura rapida e feio o
    bastante para ela ver na hora.

    Aconteceu em 25/08/2026, ao acrescentar a frase dos denominadores. O teste
    que guarda as frases INTEIRAS nao pega isto, porque as duas frases continuam
    inteiras -- so falta o espaco entre elas.

    Vale para os dois rodapes e para o achado, e vai valer para o que vier
    depois: e generico de proposito, porque o rodape so cresce.
    """
    def cola(html):
        texto = re.sub(r"<[^>]+>", "", html)
        # Ponto (ou dois-pontos) seguido direto de maiuscula, sem espaco. O
        # "\u00b7" e o separador de titulo e nao entra; numeros tambem nao,
        # senao "R$ 1.234" e "0,05%" acusariam.
        return re.findall(r"[a-z\u00e0-\u00fc][.:][A-Z\u00c0-\u00dc]", texto)

    for nome, dados in (("hoje", banda.dados_hoje()),
                        ("projecao", banda.dados_projecao(registros=[]))):
        html = banda.tabela(dados, f"t-{nome}")
        assert not cola(html), (
            f"rodape de {nome}: frase colada na seguinte em {cola(html)}")

    from tesouro.graficos import painel_paf
    assert not cola(painel_paf._ACHADO), "o achado tem frase colada"


def test_a_pagina_aceita_um_HOJE_que_nao_e_data_de_RMD(tmp_path):
    """O caminho que eu quebrei ao atender o item 6.6 da revisao.

    'hoje' queria dizer duas coisas neste projeto. Em dados_hoje e "role o
    estoque ate esta data"; em rolagem.projecao era "parta do snapshot do RMD
    desta data", um parametro que o proprio docstring dizia existir para o
    BACKTEST. Ligar um no outro fez painel_paf.grava(hoje=X) levantar
    LookupError para qualquer X que nao fosse fim de mes de RMD -- e o unico
    X que os testes passavam era None, entao ninguem viu.

    Classe: caminho nunca exercitado, com um empurrao de nome enganoso.

    A DATA E DE PROPOSITO ANTERIOR A ULTIMA LIQUIDACAO. A primeira versao
    deste teste usava a propria ultima liquidacao, e com ela uma projecao que
    IGNORASSE o parametro daria exatamente o mesmo resultado -- passava contra
    codigo quebrado (medido). So uma data que nao coincide separa "usou o que
    recebeu" de "usou o padrao".
    """
    import pandas as pd

    from tesouro.graficos import banda, painel_paf

    ultima = banda._ultima_liquidacao()
    hoje = ultima - pd.Timedelta(days=14)
    assert hoje != ultima

    # 1) o que quebrava: a pagina inteira, com um hoje que nao e data de RMD.
    caminho = painel_paf.grava(tmp_path / painel_paf.ARQUIVO,
                               hoje=hoje, registros=[])
    assert caminho.exists()

    # 2) e os DOIS blocos partem da data pedida, que e o ponto do item 6.6.
    de_hoje = banda.dados_hoje(hoje=hoje)
    projetado = banda.dados_projecao(hoje=hoje, registros=[])
    assert de_hoje.attrs["hoje"] == hoje
    assert projetado.attrs["premissa"]["de"] == hoje, (
        "a projecao tem de partir do 'hoje' que recebeu, e nao da ultima "
        "liquidacao")


def test_a_pagina_tem_TRES_blocos_recolhiveis(pagina):
    corpo = pagina[pagina.index("</header>"):pagina.rindex("</main>")]
    assert corpo.count('<details class="secao') == 3


def test_o_bloco_da_simulacao_tem_as_TRES_tabelas(pagina):
    for chave in ("prefixado-pct", "indice-precos-pct", "taxa-flutuante-pct"):
        assert f'id="simulacao-{chave}"' in pagina, chave


def test_o_bloco_da_simulacao_confessa_o_CALENDARIO_ESTIMADO(tmp_path):
    """C2, achado da revis\u00e3o: gerando a p\u00e1gina com o calend\u00e1rio
    vazio (tudo estimado), a se\u00e7\u00e3o da simula\u00e7\u00e3o saia byte a byte
    id\u00eantica \u00e0 com calend\u00e1rio publicado -- enquanto o bloco da
    proje\u00e7\u00e3o, logo acima na MESMA p\u00e1gina, dizia "inteiramente
    estimado" num caso e "publicado at\u00e9 DD/MM" no outro. Regress\u00e3o do
    pr\u00f3prio padr\u00e3o da p\u00e1gina: o bloco irm\u00e3o confessa, este n\u00e3o
    confessava.

    A CONFISS\u00c3O TEM DE ESTAR DENTRO DO RODAP\u00c9 DA SIMULA\u00c7\u00c3O -- e
    n\u00e3o em qualquer lugar do HTML. "estimado" j\u00e1 aparecia na p\u00e1gina
    antes da corre\u00e7\u00e3o, porque o bloco da proje\u00e7\u00e3o confessa a dele; um
    assert "estimado" in pagina inteira passaria mesmo sem a simula\u00e7\u00e3o
    dizer nada, e foi exatamente isso que a revis\u00e3o mediu.
    """
    from tesouro.graficos import painel_paf

    caminho = painel_paf.grava(tmp_path / painel_paf.ARQUIVO, registros=[])
    html = caminho.read_text(encoding="utf-8")

    inicio = html.index('id="simulacao-prefixado-pct"')
    fim = html.index("</div>", inicio)
    bloco = html[inicio:fim]

    rodape = bloco[bloco.index('class="rodape"'):]
    assert "estimado" in rodape


def test_a_pagina_e_reprodutivel_entre_processos(tmp_path):
    """Spec 8, teste 6. Duas geracoes, o mesmo HTML.

    Ja quebrou neste projeto: iterar um `set` de ISINs produzia ordem diferente
    a cada processo (PYTHONHASHSEED), e os SVGs saiam diferentes sem nada ter
    mudado no dado. A simulacao itera INDEXADOR_DA_CHAVE, que e dict -- ordem de
    insercao, estavel -- mas isso e propriedade que se perde sem aviso.

    EM DOIS PROCESSOS, e nao duas chamadas no mesmo: o embaralhamento por
    hash so muda entre processos.
    """
    import subprocess
    import sys

    codigo = (
        "from tesouro.graficos import painel_paf;"
        "import hashlib, pathlib;"
        "c = painel_paf.grava(pathlib.Path(r'%s') / 'p.html', registros=[]);"
        "print(hashlib.sha256(c.read_bytes()).hexdigest())")

    saidas = []
    for k in range(2):
        destino = tmp_path / str(k)
        destino.mkdir()
        r = subprocess.run([sys.executable, "-c", codigo % destino],
                           capture_output=True, text=True,
                           env={**os.environ, "PYTHONPATH": "src"})
        assert r.returncode == 0, r.stderr[-600:]
        saidas.append(r.stdout.strip())

    assert saidas[0] == saidas[1], "a pagina saiu diferente em dois processos"


def test_a_pagina_continua_cabendo_no_limiar(tmp_path):
    from tesouro.graficos import painel_paf

    caminho = painel_paf.grava(tmp_path / painel_paf.ARQUIVO, registros=[])
    tamanho = caminho.stat().st_size
    assert tamanho > 20_000, "a pagina com tres blocos nao pode encolher"
    assert tamanho < 10 * 1024 * 1024


def test_a_tabela_do_RITMO_abre_o_bloco_da_projecao(pagina):
    """Pedido dela em 08/09/2026: a pagina tem de dizer de que ritmo a
    projecao saiu, e nao so onde ela chega.

    A ORDEM E O TESTE: o ritmo vem ANTES da tabela do veredito, dentro do
    mesmo bloco recolhivel. Posto depois, ele leria como nota de rodape; posto
    em outro bloco, quem abrisse so a projecao nao veria a premissa.
    """
    corpo = pagina[pagina.index("</header>"):pagina.rindex("</main>")]
    assert 'id="tabela-ritmo"' in corpo, "a tabela do ritmo nao entrou"

    bloco = corpo[corpo.index('class="secao secao-projecao"'):]
    bloco = bloco[:bloco.index("</details>")]
    assert 'id="tabela-ritmo"' in bloco, (
        "a tabela do ritmo tem de estar DENTRO do bloco da projecao")
    assert bloco.index('id="tabela-ritmo"') < bloco.index("id='tabela-projecao'"), (
        "o ritmo vem antes do veredito")


def test_o_CSS_da_tabela_do_ritmo_entrou_na_pagina(pagina):
    """Sem isto a tabela sai sem alinhamento numerico e sem a regra do total.

    A pagina e autocontida: se a folha nao for injetada, nada quebra em voz
    alta -- a tabela so sai feia, que e o defeito que ninguem nota.
    """
    assert ".ritmo tr.total" in pagina


def test_o_rodape_diz_que_a_inflacao_implicita_CORRIGE_O_VNA_e_entre_que_datas():
    """Pedido dela em 09/09/2026: "deixa no rodape que esta considerando tanto
    de inflacao anualizada entre tal e tal data para o vna".

    O rodape ja declarava a inflacao implicita, mas nao dizia PARA QUE ela
    serve nem SOBRE QUE PERIODO corre. Quem le via um numero de premissa solto;
    o que ele faz e corrigir o VNA da NTN-B do fim do RMD ate a data-alvo, que
    hoje sao cinco meses -- distancia em que premissa pesa.

    AS DATAS SAEM DA PROJECAO, e nao cravadas: sao as mesmas 'de' e 'ate' que o
    rodape ja usa duas linhas acima, entao nao ha como uma envelhecer sem a
    outra.
    """
    d = banda.dados_projecao(registros=[])
    html = banda.tabela(d, "tabela-projecao")
    p = d.attrs["premissa"]

    assert "VNA" in html, "o rodape nao diz o que a inflacao implicita corrige"
    for data in (p["de"], p["ate"]):
        assert f"{data:%d/%m/%Y}" in html, data
    # E a inflacao continua declarada em numero.
    assert f"{banda._numero(100 * p['inflacao'])}%" in html
