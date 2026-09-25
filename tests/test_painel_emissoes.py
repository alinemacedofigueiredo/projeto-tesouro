"""As tres paginas de emissao, uma por combinacao de compra e segunda volta."""
import re

import matplotlib
matplotlib.use("Agg")
import pytest

from tesouro.graficos import dashboard, emissao, estilo, painel_emissoes


def test_sao_tres_combinacoes_e_cada_uma_tem_arquivo_proprio():
    # Eram quatro ate 20/08/2026. Saiu "venda e compra, so 1a volta": recompra sem
    # segunda volta e o recorte de que ninguem sentiu falta.
    assert len(painel_emissoes.COMBINACOES) == 3
    combos = {(c, v) for c, v, _, _ in painel_emissoes.COMBINACOES}
    assert combos == {(False, True), (False, False), (True, True)}
    assert (True, False) not in combos
    arquivos = [a for _, _, a, _ in painel_emissoes.COMBINACOES]
    assert len(set(arquivos)) == 3
    # A combinacao padrao e a que fica com o nome curto: e a que se abre primeiro.
    assert painel_emissoes.COMBINACOES[0][2] == "emissoes.html"


def test_as_tres_combinacoes_dao_numeros_diferentes():
    # Se duas dessem o mesmo numero, uma delas seria pagina a toa. Medido no ultimo
    # ano: a segunda volta responde por ~90 bi de financeiro e a compra por ~49.
    totais = {}
    for com_compra, com_2a in {(c, v) for c, v, _, _
                               in painel_emissoes.COMBINACOES}:
        d = emissao.por_semana(janela=1, com_compra=com_compra,
                               com_segunda_volta=com_2a)
        totais[(com_compra, com_2a)] = round(
            d["financeiro_milhoes"].sum() / 1000, 1)

    assert len(set(totais.values())) == 3, totais
    # Tirar a segunda volta reduz; incluir compra tambem reduz, porque ela entra
    # com sinal negativo.
    assert totais[(False, False)] < totais[(False, True)]
    assert totais[(True, True)] < totais[(False, True)]


def test_o_registro_muda_com_a_combinacao():
    # A nota de rodape de cada grafico diz qual recorte a pagina mostra. Se ela nao
    # mudasse, as tres paginas seriam indistinguiveis para quem le.
    so_venda = painel_emissoes.registro(com_compra=False, com_2a=True)
    com_compra = painel_emissoes.registro(com_compra=True, com_2a=True)
    # AS DUAS TEM O MESMO CONJUNTO DE GRAFICOS, e e isso que importa aqui: a
    # combinacao muda a NOTA, e nao quais graficos a pagina tem. Antes esta
    # linha cravava "== 12", uma contagem que nao era o assunto deste teste e
    # que envelhecia a cada grafico novo -- caiu ao entrar os acumulados de 12
    # meses em 09/09/2026.
    assert [g.id for g in so_venda] == [g.id for g in com_compra]
    assert "S\u00f3 venda" in so_venda[0].nota
    assert "compra" in com_compra[0].nota
    assert so_venda[0].nota != com_compra[0].nota


@pytest.fixture(scope="module")
def pagina(tmp_path_factory):
    destino = tmp_path_factory.mktemp("emissoes") / "emissoes.html"
    caminho = painel_emissoes.grava(destino, com_compra=False, com_2a=True)
    return caminho.read_text(encoding="utf-8")


def test_a_pagina_traz_todos_os_graficos_e_todos_os_grupos(pagina):
    for g in painel_emissoes.registro():
        assert f'id="{g.id}"' in pagina, g.id
    for grupo in painel_emissoes.GRUPOS:
        assert grupo in pagina
    assert pagina.count("<section") == len(painel_emissoes.registro())


def test_a_barra_liga_as_paginas_irmas_e_os_recortes(pagina):
    # Sem a barra, quem abre uma nao sabe que as outras existem. Os links sao
    # relativos, entao continuam funcionando com duplo clique e sem servidor.
    #
    # A barra passou a ser montada em dashboard.grava e a chamar-se "paginas" em
    # 20/08/2026: antes cada painel tinha a sua copia da lista, e o dashboard --
    # que nao e montado por painel nenhum -- ficava sem saida para os outros.
    from tesouro.graficos import dashboard

    assert 'id="paginas"' in pagina
    # UMA marca de pagina atual, e nenhuma a mais. Com duas, quem le nao sabe onde
    # esta -- e a primeira versao desta barra saia com duas em emissoes.html.
    assert pagina.count('class="atual"') == 1

    # As irmas de primeiro nivel...
    for arquivo, _ in dashboard.PAGINAS:
        if arquivo != "emissoes.html":
            assert f'href="{arquivo}"' in pagina
    # ...e os recortes desta familia.
    for _, _, arquivo, _ in painel_emissoes.COMBINACOES[1:]:
        assert f'href="{arquivo}"' in pagina

    # E nenhum destino repetido: emissoes.html e ao mesmo tempo a entrada da
    # familia e o primeiro recorte, e sem cuidado aparecia duas vezes.
    import re
    i = pagina.index('<div id="paginas">')
    barra = pagina[i:pagina.index("</div>", i)]
    alvos = re.findall(r'href="([^"]+)"', barra)
    assert len(alvos) == len(set(alvos)), alvos


def test_a_pagina_nao_tem_referencia_externa(pagina):
    # Mesma propriedade do dashboard, e conferida do mesmo jeito: o que importa e
    # src= e href= apontando para fora, e nao a palavra "http" solta.
    #
    # Procurar "http://" cru acusa duas coisas que nao buscam nada: o xmlns do SVG
    # e os dois URIs de metadado RDF que o matplotlib escreve (purl.org e
    # matplotlib.org). Sao texto dentro do arquivo, nao requisicao.
    #
    # A VERSAO ANTERIOR DESTE TESTE PASSAVA POR SORTE. Ela era
    #     re.search(r'(?:src|href)\s*=\s*"(?!#)[^"]*//', pagina)
    # e a barra de cor da dispersao entra como data:image/png;base64 -- cujo
    # alfabeto inclui "/". Bastava a base64 conter "//" em qualquer posicao para o
    # teste acusar referencia externa onde nao ha nenhuma. Ele acusou em 20/08/2026,
    # quando as janelas mudaram e a barra de cor mudou de tamanho.
    #
    # Agora a checagem e por ESQUEMA, e nao por procurar duas barras no meio do
    # texto: o que importa e o valor apontar para outra maquina.
    externos = [m.group(1) for m in
                re.finditer(r'(?:src|href|xlink:href)\s*=\s*"([^"]*)"', pagina)
                if "://" in m.group(1)]
    assert externos == [], externos[:3]

    # E O TESTE ACIMA NAO PODE ESTAR VAZIO. Ele so vale se houver de fato src= e
    # href= na pagina para examinar. Ate 21/08/2026 isto era conferido pela barra de
    # cor das dispersoes, que entrava como data:image/png;base64 -- e as dispersoes
    # sairam. A propriedade em si nao mudou: o grafico continua embutido, agora
    # inteiro em SVG, e nenhuma imagem e apontada de fora.
    achados = re.findall(r'(?:src|href|xlink:href)\s*=\s*"([^"]*)"', pagina)
    assert len(achados) > 50, f"so {len(achados)} atributos: o teste ficou vazio"
    assert pagina.count("<svg") >= 30, "a pagina deixou de embutir os graficos"
    assert "<img" not in pagina
    assert "<link" not in pagina
    assert not re.search(r"<script[^>]+src=", pagina)
    # E os links entre as quatro paginas sao RELATIVOS, que e o que os faz
    # funcionar com duplo clique.
    for _, _, arquivo, _ in painel_emissoes.COMBINACOES[1:]:
        assert f'href="{arquivo}"' in pagina


# --------------------------------------------------------------------------
# As tres aparencias, para os tres momentos: ofertado (fantasma com contorno
# E HACHURADO), aceito (solido) e planilha (solido).
#
# O risco aqui nao e o grafico ficar feio. E alguem olhar um numero hoje, outro
# amanha, e nao ter como saber por que mudou.
#
# A REGRA MUDOU EM 09/09/2026, por decisao dela: "so coloque hachurado os
# leiloes que ainda nao saiu o resultado". Antes a hachura marcava o ACEITO --
# resultado publicado, planilha ainda nao confirmou -- e o ofertado ficava so
# com o contorno esmaecido.
#
# O QUE A HACHURA PASSA A SIGNIFICAR: "este numero ainda vai mudar", e nao
# "este numero veio da API". Entre a oferta das 10h30 e o resultado, o grafico
# desenha a QUANTIDADE OFERTADA, que e um teto e historicamente cai para 83,9%
# dela. Saido o resultado, a quantidade e final e a barra fica solida.
#
# O PRECO, aceito de propria vontade: 'aceito' passa a ficar VISUALMENTE IGUAL a
# 'planilha'. Some da tela a distincao "a planilha do Tesouro ainda nao
# confirmou" -- que e bookkeeping do Tesouro, e nao informacao sobre o numero.
# --------------------------------------------------------------------------

def _dia_com_os_tres_estagios():
    import pandas as pd
    idx = pd.to_datetime(["2026-08-04", "2026-08-11", "2026-08-20", "2026-08-25"])
    d = pd.DataFrame({"financeiro_milhoes": [676.0, 1571.0, 2650.0, 3100.0],
                      "dv_milhoes": [-0.48, -0.76, -1.25, -1.48],
                      "leiloes": [6, 3, 1, 1],
                      "estagio": ["planilha", "planilha", "aceito", "ofertado"]},
                     index=idx)
    d.index.name = "data_leilao"
    return d


def test_cada_estagio_ganha_a_sua_aparencia():
    d = _dia_com_os_tres_estagios()
    estagios = emissao._estagios(d)
    assert estagios == ["planilha", "planilha", "aceito", "ofertado"]

    a = emissao._aparencia(estagios, "#3d9be9")
    # A oferta e fantasma: o preenchimento quase some, mas a cor do papel fica --
    # foi por isso que a barra OCA foi abandonada, ela apagava a composicao do
    # grafico empilhado.
    assert a["color"][3][3] == emissao.OPACIDADE_DO_OFERTADO
    assert a["color"][0][3] > emissao.OPACIDADE_DO_OFERTADO
    # SO O OFERTADO E HACHURADO. O indice 3 e o ofertado e o 2 e o aceito.
    assert a["hatch"] == ["", "", "", emissao.HACHURA_OFERTADO]
    assert emissao.HACHURA_OFERTADO, "o ofertado precisa de alguma hachura"
    assert not emissao.HACHURA_ACEITO, "o aceito nao pode mais ter hachura"
    # E SO O OFERTADO TEM CONTORNO. Ate 09/09/2026 o aceito levava um contorno
    # escuro fino (0,4) contra nenhum da planilha, e era o que sobrava da regra
    # antiga -- ela viu na pagina e perguntou por que as colunas eram
    # diferentes. Resultado saido, quantidade final: nao ha o que distinguir.
    assert a["linewidth"][3] > 0
    assert a["linewidth"][2] == a["linewidth"][0] == 0.0
    assert a["edgecolor"][2] == a["edgecolor"][0]


def test_o_ACEITO_fica_IDENTICO_a_planilha_em_tudo():
    """Nao basta a hachura e o contorno: qualquer chave que os separe reaparece
    como coluna diferente na tela."""
    d = _dia_com_os_tres_estagios()
    a = emissao._aparencia(emissao._estagios(d), "#3d9be9")
    for chave, valores in a.items():
        assert valores[2] == valores[0], (chave, valores[2], valores[0])


def test_SEM_OFERTA_o_grafico_sai_como_antes_da_API():
    """Se so o ofertado se distingue, entao um dia com resultado ja saido nao
    precisa de aparencia por barra nenhuma.

    E o que o proprio docstring de _estagios promete: "a aparencia antiga e nada
    mais". Ate 09/09 ele so cumpria isso quando TUDO era planilha; com o aceito
    tendo virado indistinguivel, passa a valer tambem com aceito na tela.
    """
    d = _dia_com_os_tres_estagios()
    d.loc[d["estagio"] == "ofertado", "estagio"] = "aceito"
    assert emissao._estagios(d) is None
    assert set(emissao._aparencia(emissao._estagios(d), "#3d9be9")) == {"color"}

    # E com oferta na tela ele volta a distinguir.
    d2 = _dia_com_os_tres_estagios()
    assert emissao._estagios(d2) is not None


def test_sem_provisorio_nao_ha_marca_nenhuma():
    # Importa para a reprodutibilidade: enquanto tudo vem da planilha, o SVG tem de
    # sair identico ao que saia antes de a API existir. Passar hatch=["",""] em vez
    # de hatch=None ja muda o arquivo.
    d = _dia_com_os_tres_estagios()
    d["estagio"] = "planilha"
    assert emissao._estagios(d) is None
    assert set(emissao._aparencia(None, "#3d9be9")) == {"color"}


def test_csv_antigo_sem_a_coluna_estagio_continua_desenhando():
    # O dv_emitido_por_leilao.csv gravado antes da API nao tem a coluna. Quebrar
    # nesse caso trocaria "grafico um dia atrasado" por "grafico nenhum".
    d = _dia_com_os_tres_estagios().drop(columns=["estagio"])
    assert emissao._estagios(d) is None


def test_a_legenda_explica_SO_O_OFERTADO():
    """Desde 09/09/2026 so o ofertado tem aparencia propria.

    Com a hachura marcando o ofertado, 'aceito' ficou VISUALMENTE IGUAL a
    'planilha' -- e uma entrada de legenda para ele apontaria para uma barra
    indistinguivel das outras. O comentario da versao anterior deste teste ja
    dizia a regra que agora o condena: "legenda de um estagio que nao esta na
    tela e ruido: quem olha procura a barra e nao acha".
    """
    ambos = emissao._legenda_dos_estagios(["planilha", "aceito", "ofertado"])
    assert [e.get_label() for e in ambos] == [
        emissao._ROTULO_DO_ESTAGIO["ofertado"]]

    so_aceito = emissao._legenda_dos_estagios(["planilha", "aceito"])
    assert so_aceito == [], (
        "aceito nao tem mais aparencia propria, e nao pode ter legenda")

    assert emissao._legenda_dos_estagios(None) == []


def test_os_rotulos_do_estagio_sao_CURTOS():
    # A primeira versao explicava o estagio inteiro na legenda -- "aceito hoje
    # (API), muda quando a planilha sair" -- e a frase competia com o grafico.
    # A explicacao mora no texto da pagina, que e onde se le texto; a legenda so
    # precisa dizer qual barra e qual.
    for estagio, rotulo in emissao._ROTULO_DO_ESTAGIO.items():
        assert len(rotulo) <= 24, (estagio, rotulo)
        assert "taxa" not in rotulo.lower(), estagio

    # E o do ofertado ainda diz que e TETO: sem essa palavra, a barra mais alta do
    # grafico parece emissao recorde quando e so o anuncio.
    assert "teto" in emissao._ROTULO_DO_ESTAGIO["ofertado"].lower()

    # E SO ELE SOBROU. O rotulo existe para nomear uma aparencia; 'aceito'
    # deixou de ter uma em 09/09/2026, entao um rotulo para ele seria nome sem
    # coisa nomeada.
    assert set(emissao._ROTULO_DO_ESTAGIO) == {"ofertado"}


def test_a_barra_somada_recebe_o_estagio_menos_firme():
    # Um dia de leilao soma varios papeis. Se um deles ainda e teto, o total daquele
    # dia tambem e teto -- a soma nao pode ser mais firme que a sua parte mais fraca.
    assert emissao._menos_firme(["planilha", "aceito"]) == "aceito"
    assert emissao._menos_firme(["planilha", "aceito", "ofertado"]) == "ofertado"
    assert emissao._menos_firme(["planilha", "planilha"]) == "planilha"
    assert emissao._menos_firme([]) == emissao.ESTAGIO_MAIS_FIRME


def test_o_dia_inteiro_fica_no_estagio_menos_firme_do_csv(tmp_path, monkeypatch):
    # O mesmo, mas atravessando por_dia() e o CSV de verdade -- e nao so a funcao
    # auxiliar.
    import pandas as pd
    from tesouro import config

    base = pd.read_csv(config.PROCESSED_DIR / "dv_emitido_por_leilao.csv",
                       parse_dates=["data_leilao", "data_liquidacao"])
    recorte = base[base["familia"] == "NTN-B longa"].tail(2).copy()
    recorte["data_leilao"] = pd.Timestamp("2026-08-20")
    recorte["estagio"] = ["planilha", "ofertado"]

    falso = tmp_path / "dv_emitido_por_leilao.csv"
    recorte.to_csv(falso, index=False, encoding="utf-8")
    monkeypatch.setattr(emissao.config, "PROCESSED_DIR", tmp_path)

    d = emissao.por_dia("NTN-B longa")
    assert len(d) == 1
    assert d.iloc[0]["estagio"] == "ofertado"


def test_a_linha_do_estado_diz_qual_o_ultimo_leilao(tmp_path, monkeypatch):
    # ITEM 12 DA REVISAO: "colocar la em cima qual o ultimo leilao considerado".
    # Sem isso, quem abre a pagina nao sabe se esta vendo o leilao de hoje ou o da
    # semana passada -- e as duas coisas se parecem.
    import pandas as pd
    from tesouro import config

    pd.DataFrame({"estagio": ["planilha", "aceito"],
                  "data_leilao": ["2026-08-11", "2026-08-20"]}
                 ).to_csv(tmp_path / "dv_emitido_por_leilao.csv", index=False)
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)

    linha = painel_emissoes._uma_linha_do_estado()
    assert "20/08/2026" in linha
    assert "\u00faltimo leil\u00e3o" in linha.lower()


def test_a_linha_do_estado_e_UMA_LINHA(tmp_path, monkeypatch):
    # ITEM 11: "o aviso provisorio esta poluindo". A versao anterior era um bloco
    # com lista e dois paragrafos explicando cada estagio, no topo de toda pagina.
    # Agora so cabe o que muda todo dia -- a data.
    import pandas as pd
    from tesouro import config

    pd.DataFrame({"estagio": ["planilha", "aceito", "ofertado"],
                  "data_leilao": ["2026-08-11", "2026-08-18", "2026-08-20"]}
                 ).to_csv(tmp_path / "dv_emitido_por_leilao.csv", index=False)
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)

    linha = painel_emissoes._uma_linha_do_estado()
    assert "<ul>" not in linha and "<li>" not in linha
    assert linha.count("<div") == 1
    # Curta: o texto sem marcacao cabe numa linha de tela.
    import re
    texto = re.sub("<[^>]+>", "", linha)
    assert len(texto) < 220, texto


def test_a_linha_do_estado_separa_ofertado_de_aceito(tmp_path, monkeypatch):
    import pandas as pd
    from tesouro import config

    pd.DataFrame({"estagio": ["planilha", "aceito", "ofertado"],
                  "data_leilao": ["2026-08-11", "2026-08-18", "2026-08-20"]}
                 ).to_csv(tmp_path / "dv_emitido_por_leilao.csv", index=False)
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)

    linha = painel_emissoes._uma_linha_do_estado()
    assert "18/08/2026" in linha and "20/08/2026" in linha
    assert "11/08/2026" not in linha      # esse a planilha ja confirmou


def test_sem_provisorio_a_linha_traz_so_a_data(tmp_path, monkeypatch):
    # Pagina de historico nao precisa de aviso sobre uma coisa que nao esta la --
    # mas continua precisando dizer ate quando o dado vai.
    import pandas as pd
    from tesouro import config

    pd.DataFrame({"estagio": ["planilha"], "data_leilao": ["2026-08-11"]}
                 ).to_csv(tmp_path / "dv_emitido_por_leilao.csv", index=False)
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)

    linha = painel_emissoes._uma_linha_do_estado()
    assert "11/08/2026" in linha
    assert "ofertado" not in linha
    assert "aceito" not in linha


def test_csv_sem_a_coluna_estagio_nao_quebra_a_pagina(tmp_path, monkeypatch):
    import pandas as pd
    from tesouro import config

    pd.DataFrame({"data_leilao": ["2026-08-11"]}
                 ).to_csv(tmp_path / "dv_emitido_por_leilao.csv", index=False)
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)
    assert "11/08/2026" in painel_emissoes._uma_linha_do_estado()


def test_as_janelas_sao_curtas_e_nenhuma_e_a_serie_inteira():
    nomes = [n for n, _ in painel_emissoes.JANELAS]
    assert nomes == ["20 leil\u00f5es", "no ano", "12 meses",
                     "desde o ano anterior", "5 anos"]
    # A "completa" saiu: 5,9 MB dos 9,67 da pagina, para 702 barras de um pixel.
    assert None not in [j for _, j in painel_emissoes.JANELAS]
    # E a que abre e "12 meses", que fecha um ciclo do PAF.
    assert painel_emissoes.JANELA_PADRAO in nomes


def test_a_escada_de_janelas_e_crescente_e_sem_degrau_repetido():
    # O contador e 20 e nao 50 POR MEDICAO: o Tesouro leiloa quase toda semana,
    # entao 50 leiloes colapsam sobre "12 meses" -- mediram-se 50 contra 51 pontos,
    # com um dia de diferenca no inicio. Duas janelas iguais e uma janela a toa.
    d = emissao.por_dia("NTN-B")
    tamanhos = [len(estilo.recorta(d, j)) for _, j in painel_emissoes.JANELAS]
    assert tamanhos == sorted(tamanhos)
    assert len(set(tamanhos)) == len(tamanhos)
    # E cada degrau e sensivelmente maior que o anterior, e nao um empate disfarcado.
    for antes, depois in zip(tamanhos, tamanhos[1:]):
        assert depois >= antes * 1.25, (antes, depois)


def test_ultimos_conta_pontos_e_desdejaneiro_conta_calendario():
    import pandas as pd

    idx = pd.date_range("2023-01-04", "2026-08-19", freq="W")
    d = pd.DataFrame({"x": range(len(idx))}, index=idx)

    assert len(estilo.recorta(d, estilo.Ultimos(20))) == 20

    # DesdeJaneiro(0) e o ano da ULTIMA DATA DA SERIE, e nao o de hoje. Ancorar em
    # datetime.today() faria o grafico mudar de conteudo conforme o dia em que roda,
    # e a reprodutibilidade e testada.
    #
    # A SERIE DESTE TESTE TERMINA EM 2024, DE PROPOSITO: com ela terminando no ano
    # corrente as duas ancoras dao o mesmo resultado, e o teste passaria mesmo com a
    # linha errada -- foi o que aconteceu na primeira versao dele.
    velha = pd.date_range("2022-01-05", "2024-11-27", freq="W")
    antiga = pd.DataFrame({"x": range(len(velha))}, index=velha)

    no_ano = estilo.recorta(antiga, estilo.DesdeJaneiro(0))
    assert not no_ano.empty
    assert no_ano.index.min().year == 2024
    assert no_ano.index.min().month == 1

    desde_o_anterior = estilo.recorta(antiga, estilo.DesdeJaneiro(1))
    assert desde_o_anterior.index.min().year == 2023


def test_ultimos_nao_e_lido_como_o_par_de_datas():
    # A ARMADILHA: namedtuple E tuple. Se recorta() testasse a forma (de, ate)
    # antes de Ultimos, um Ultimos(20) seria desempacotado como (de, ate) e
    # estouraria -- ou pior, recortaria por uma data absurda.
    import pandas as pd

    idx = pd.date_range("2026-01-01", periods=40, freq="D")
    d = pd.DataFrame({"x": range(40)}, index=idx)
    assert len(estilo.recorta(d, estilo.Ultimos(20))) == 20
    assert estilo.recorta(d, estilo.Ultimos(20)).index.max() == idx[-1]


def test_a_nota_do_grafico_semanal_avisa_que_ali_o_ponto_e_a_semana():
    """"20 leiloes" conta PONTOS do grafico, e o que e um ponto varia.

    Nos graficos SEMANAIS um ponto e uma semana, entao a janela mostra 20
    semanas -- e o rotulo mentiria em silencio sem a nota.

    NEM TODO GRAFICO DO GRUPO E SEMANAL desde 09/09/2026: os dois acumulados de
    12 meses moram ali por vizinhanca, e neles um ponto e um DIA DE LEILAO com
    soma movel. A versao anterior deste teste exigia a nota de TODO grafico do
    grupo, e cravava que eram dois -- as duas coisas cairam quando os
    acumulados entraram.

    O corte agora e pela propria nota, e nao por uma lista de nomes: quem
    carrega _NOTA_SEMANAL declara ser semanal, e tem de cumprir. Quem nao
    carrega nao pode falar de semana como se fosse o ponto.
    """
    por_semana = [g for g in painel_emissoes.registro()
                  if g.grupo == "Por semana"]
    semanais = [g for g in por_semana
                if painel_emissoes._NOTA_SEMANAL in g.nota]
    outros = [g for g in por_semana
              if painel_emissoes._NOTA_SEMANAL not in g.nota]

    assert semanais, "nenhum grafico se declara semanal"
    assert outros, "a divisao ficou degenerada; o teste nao esta separando nada"

    for g in semanais:
        assert "semana" in g.nota, g.id
        assert "20 leil\u00f5es" in g.nota, g.id

    # E os acumulados dizem qual e a janela DELES, que nao e a semana.
    for g in outros:
        assert "12 meses" in g.titulo, g.id


def test_a_dispersao_saiu_da_pagina():
    # DUAS TENTATIVAS, e as duas recusadas por quem le. O item 10 da revisao disse
    # "eles ainda nao passam nenhuma info", e o eixo migrou de quantidade para DV01
    # -- a quantidade mistura uma LTN de seis meses com uma NTN-B de 35 anos como se
    # fossem a mesma coisa. Com o risco no eixo a nuvem ainda nao ganhou forma, e em
    # 21/08/2026 ela saiu: "nao ficaram bons os graficos de dispersao".
    assert "Taxa e risco" not in painel_emissoes.GRUPOS
    ids = [g.id for g in painel_emissoes.registro()]
    assert "dv_taxa_pre" not in ids and "dv_taxa_ntnb" not in ids
    # O dado e o desenho FICAM no modulo, sem ninguem chamando: sao o ponto de
    # partida de quem tentar responder a pergunta de outro jeito.
    assert hasattr(emissao, "dv_e_taxa")
    assert hasattr(emissao, "desenha_taxa_contra_dv")
    # As versoes contra QUANTIDADE, essas nao voltam.
    assert not hasattr(emissao, "desenha_quantidade_e_taxa")
    assert not hasattr(emissao, "desenha_taxa_contra_quantidade")


# --------------------------------------------------------------------------
# De onde veio a taxa da barra de oferta. Contada, e nao afirmada.
# --------------------------------------------------------------------------

def _recorte(supostas, total):
    import pandas as pd
    return pd.DataFrame({"taxa_suposta": [True] * supostas
                                          + [False] * (total - supostas)})


def test_a_marca_de_taxa_suposta_chega_ao_csv():
    # Ela nasce em leilao_ofertado.preencher() e precisa atravessar leiloes_dv ate o
    # CSV -- senao a pagina nao tem como saber de onde veio a taxa da barra.
    import pandas as pd
    from tesouro import config

    d = pd.read_csv(config.PROCESSED_DIR / "dv_emitido_por_leilao.csv")
    assert "taxa_suposta" in d.columns
    # E no que veio da planilha do Tesouro ela e sempre falsa: ali a taxa e a que
    # ele publicou, nunca uma suposicao nossa.
    da_planilha = d[d["estagio"] == "planilha"]
    assert not da_planilha["taxa_suposta"].fillna(False).astype(bool).any()


# --------------------------------------------------------------------------
# Os ajustes da revisao de 20/08/2026.
# --------------------------------------------------------------------------

def _dois_lados():
    """Uma serie com financeiro dos DOIS lados do zero e DV so de um.

    E o caso que separa eixos alinhados de eixos independentes: com tudo positivo
    os dois zeros caem no chao da figura de qualquer jeito, e o teste passaria sem
    proteger nada.
    """
    import pandas as pd
    idx = pd.to_datetime(["2026-01-05", "2026-02-05", "2026-03-05", "2026-04-06"])
    d = pd.DataFrame({"financeiro_milhoes": [5000.0, -3000.0, 4000.0, 1000.0],
                      "dv_milhoes": [1.0, 0.2, 2.5, 1.4],
                      "leiloes": [1, 1, 1, 1],
                      "estagio": ["planilha"] * 4}, index=idx)
    d.index.name = "data_leilao"
    return d


def _fracao_do_zero(limites):
    chao, teto = limites
    return -chao / (teto - chao)


def test_os_dois_eixos_poem_o_zero_na_MESMA_altura():
    # ITEM 5 DA REVISAO. Com eixos independentes, o zero de um cai a 30% da altura e
    # o do outro a 60% -- a linha cruza a barra em lugares que nao querem dizer
    # nada, e um periodo de recompra aparece com as duas series de lados diferentes
    # do proprio zero.
    import matplotlib.pyplot as plt

    d = _dois_lados()
    fig, ax = plt.subplots()
    emissao.desenha_dois_eixos(d, ax, "teste")
    direita = [a for a in fig.axes if a is not ax][0]

    esquerda_zero = _fracao_do_zero(ax.get_ylim())
    direita_zero = _fracao_do_zero(direita.get_ylim())
    assert abs(esquerda_zero - direita_zero) < 0.01, (
        esquerda_zero, direita_zero)
    # E o zero esta DENTRO da figura, e nao no chao: a serie tem valor negativo.
    assert 0.05 < esquerda_zero < 0.95
    plt.close(fig)


def test_alinhar_os_zeros_nao_corta_dado():
    # A conta estica o lado que precisa, e nunca encolhe: encolher poria uma barra
    # para fora da area de desenho, que e pior que o desalinhamento que se veio
    # consertar.
    import matplotlib.pyplot as plt

    d = _dois_lados()
    fig, ax = plt.subplots()
    emissao.desenha_dois_eixos(d, ax, "teste")
    direita = [a for a in fig.axes if a is not ax][0]

    chao_e, teto_e = ax.get_ylim()
    assert chao_e <= d["financeiro_milhoes"].min() / 1000
    assert teto_e >= d["financeiro_milhoes"].max() / 1000
    chao_d, teto_d = direita.get_ylim()
    assert teto_d >= d["dv_milhoes"].max() * 1000
    plt.close(fig)


def test_o_dv_do_grafico_sai_em_MIL_e_nao_em_milhoes():
    # ITEM 3: em milhoes as etiquetas do eixo ficam todas em 0,00 e 0,01, e a serie
    # inteira parece nula.
    import matplotlib.pyplot as plt

    d = _dois_lados()
    fig, ax = plt.subplots()
    emissao.desenha_dois_eixos(d, ax, "teste")
    direita = [a for a in fig.axes if a is not ax][0]
    assert "mil" in direita.get_ylabel()
    # E a escala bate: o maior valor desenhado e o DV em milhoes vezes mil.
    linha = direita.get_lines()[0]
    assert max(linha.get_ydata()) == d["dv_milhoes"].max() * 1000
    plt.close(fig)


def test_o_financeiro_ganha_rotulo_com_duas_casas():
    # ITEM 3 e ITEM 7: rotulo nos ultimos numeros, em bilhoes, com duas casas.
    import matplotlib.pyplot as plt

    d = _dois_lados()
    fig, ax = plt.subplots()
    emissao.desenha_dois_eixos(d, ax, "teste")
    textos = [a.get_text() for a in ax.texts]
    assert textos, "nenhum rotulo foi escrito"
    # O ultimo valor e 1000 milhoes = 1,00 bilhao.
    assert "1,00" in textos
    plt.close(fig)


def test_os_rotulos_nao_se_amontoam_no_fim_da_serie():
    # A primeira versao escrevia o ultimo ponto E os extremos, sem olhar se estavam
    # perto -- e numa serie que so cai, o minimo fica ao lado do ultimo. Os dois
    # rotulos sairam um por cima do outro no acumulado de 3 meses.
    #
    # A SERIE DESTE TESTE CAI E DEPOIS SOBE UM POUCO, de proposito: assim o minimo e
    # VIZINHO do ultimo, e nao o proprio ultimo. Com o minimo caindo exatamente no
    # ultimo ponto os dois viram a mesma chave e o teste passaria sem guarda nenhuma
    # -- foi o que aconteceu na primeira versao dele.
    import matplotlib.pyplot as plt
    import pandas as pd

    indice = pd.date_range("2026-01-01", periods=30, freq="W")
    valores = pd.Series([float(30 - k) for k in range(29)] + [5.0], index=indice)
    assert valores.idxmin() != indice[-1], "o minimo tem de ser vizinho, nao o ultimo"

    fig, ax = plt.subplots()
    emissao._marca_pontos(ax, indice, valores, lambda v: f"{v:.0f}", "#000")
    escritos = [a.get_text() for a in ax.texts]
    # O maximo (longe) e o ultimo. O minimo e vizinho do ultimo e fica de fora.
    assert len(escritos) == 2, escritos
    assert "5" in escritos       # o ultimo
    assert "30" in escritos      # o maximo, no comeco da serie
    assert "1" not in escritos   # o minimo, vizinho do ultimo
    plt.close(fig)


# --------------------------------------------------------------------------
# Demanda: ofertado contra colocado.
#
# A pergunta que a emissao sozinha nao responde -- uma barra baixa pode ser um
# dia em que ele ofertou pouco, ou um em que ofertou muito e o mercado nao
# levou, e sao coisas opostas.
# --------------------------------------------------------------------------

def test_a_demanda_traz_os_dois_lados_e_a_fracao():
    d = emissao.demanda("NTN-B", janela=1)
    assert not d.empty
    for coluna in ("dv_ofertado", "dv_aceito", "colocado_pct"):
        assert coluna in d.columns
    # O colocado nunca passa do ofertado -- uma folga minuscula cobre o
    # arredondamento do proprio dado do Tesouro.
    assert (d["dv_aceito"] <= d["dv_ofertado"] * 1.001).all()
    esperado = d["dv_aceito"] / d["dv_ofertado"]
    assert d["colocado_pct"].round(9).equals(esperado.round(9))


def test_a_demanda_e_medida_em_DV_e_nao_em_quantidade():
    # A DIFERENCA E MATERIAL: no historico inteiro a NTN-B longa colocou 37,5% da
    # quantidade ofertada e 46,6% do DV. Em quantidade, um lote de LTN de seis
    # meses pesa igual a um de NTN-B de trinta anos -- e o que esta pagina conta e
    # risco.
    d = emissao.demanda("NTN-B longa")
    em_dv = d["dv_aceito"].sum() / d["dv_ofertado"].sum()
    em_qtd = d["qtd_aceita"].sum() / d["qtd_ofertada"].sum()
    assert em_dv == pytest.approx(0.466, abs=0.02)
    assert em_qtd == pytest.approx(0.375, abs=0.02)
    assert em_dv > em_qtd, "as duas leituras deixaram de divergir"


def test_a_LFT_cai_na_quantidade_porque_nao_tem_DV():
    # Ela nao tem DV01 por decisao de modelagem. A fracao dela existe, mas so em
    # titulos -- e o grafico dela troca de eixo por isso.
    d = emissao.demanda("LFT")
    assert d["dv_ofertado"].isna().all()
    assert d["colocado_pct"].notna().any()
    esperado = d["qtd_aceita"] / d["qtd_ofertada"]
    assert d["colocado_pct"].dropna().round(9).equals(
        esperado.loc[d["colocado_pct"].dropna().index].round(9))


def test_a_serie_por_familia_nao_tem_buracos_alternados():
    # LFT e NTN-B vao a mercado num dia e o prefixado no outro. Guardar so os dias
    # de leilao de cada papel produziria cinco linhas tracejadas em alternancia, e
    # cinco linhas tracejadas nao se comparam -- a soma movel vale todo dia.
    d = emissao.colocado_por_familia(janela=5)
    assert len(d) > 1000
    for familia in ("LTN", "NTN-F"):
        assert d[familia].isna().sum() == 0, familia


def test_a_quebra_de_2021_na_ntnb_longa_esta_no_dado():
    # O achado que a pagina mostra, travado aqui para que uma mudanca de dado que o
    # apague seja notada: a NTN-B longa saiu de ~20% em 2020 para ~81% em 2021.
    d = emissao.colocado_por_familia()
    por_ano = d.groupby(d.index.year)["NTN-B longa"].mean()
    assert por_ano[2020] < 0.30
    assert por_ano[2021] > 0.70
    assert por_ano.iloc[-1] > 0.85, "o nivel recente deixou de ser alto"


def test_a_barra_do_colocado_fica_DENTRO_da_do_ofertado():
    # E nao ao lado: o colocado e PARTE do ofertado, e duas barras lado a lado
    # sugeririam duas grandezas que se somam. A de dentro precisa de zorder maior,
    # senao a de tras a cobre -- foi assim que a primeira versao saiu, so com
    # barras claras.
    import matplotlib.pyplot as plt

    d = emissao.demanda("NTN-B", janela=1)
    fig, ax = plt.subplots()
    emissao.desenha_demanda(d, ax, "teste")
    ofertado = [p for p in ax.patches if p.get_zorder() == 2]
    colocado = [p for p in ax.patches if p.get_zorder() == 3]
    assert len(ofertado) == len(colocado) == len(d)
    # Mesma posicao x, alturas diferentes: uma dentro da outra.
    assert ofertado[0].get_x() == colocado[0].get_x()
    plt.close(fig)


def test_o_grupo_demanda_esta_na_pagina(pagina):
    assert "Demanda" in painel_emissoes.GRUPOS
    assert 'id="demanda_ntnb"' in pagina


def test_a_fracao_por_papel_saiu_da_pagina(pagina):
    # Recusada na revisao de 21/08/2026: nao trazia informacao. O resumo por
    # familia mostrava o nivel de cada papel, mas quem quer saber se ele cortou
    # olha o grafico do papel -- e la a linha da fracao esta.
    assert 'id="demanda_resumo"' not in pagina
    assert "demanda_resumo" not in [g.id for g in painel_emissoes.registro()]
    # A funcao de dado continua existindo: ela e usada pelo teste da quebra de
    # 2021, que trava um achado sobre o dado e nao sobre o desenho.
    assert hasattr(emissao, "colocado_por_familia")


def test_a_linha_do_estado_fica_dentro_do_conteudo_e_fora_do_cabecalho(pagina):
    # DUAS COISAS, e as duas foram vistas na tela e nao no codigo.
    #
    # DENTRO do <main>, porque fora dele ela nao tem a margem de 250px e e
    # desenhada por baixo do indice fixo -- foi assim que ela saiu, e as duas
    # coisas se entrelacavam no alto da pagina.
    #
    # E FORA do cabecalho grudado: dentro dele o cabecalho ia a 145px e comia um
    # sexto da tela o tempo todo. Isto e contexto que se le uma vez, e nao um
    # controle que se usa a toda hora.
    i_main = pagina.index("\n<main>")
    i_header = pagina.index("</header>")
    i_estado = pagina.index('id="estado"')
    assert i_estado > i_main, "a linha do estado ficou fora do main"
    assert i_estado > i_header, "a linha do estado entrou no cabecalho grudado"
    assert i_estado < pagina.index("</main>")

def test_a_serie_de_uma_familia_vai_ate_o_FIM_mesmo_que_ela_pare_antes(
        tmp_path, monkeypatch):
    """O buraco na cauda, forcado por dado sintetico.

    O teste acima, contra o dado de verdade, so tem dentes quando o ultimo
    leilao do arquivo e de TERCA: ai LFT e NTN-B estao em dia e o prefixado esta
    dois dias atras, e a cauda dele fica NaN. Numa quinta o prefixado esta em dia
    e o mesmo defeito passa despercebido. Foi assim que ele entrou -- e so
    apareceu em 25/08/2026, uma terca, com o resultado do dia ja no dado.

    Aqui as duas familias param em datas DIFERENTES de proposito, todo dia do
    ano. A LFT vai ate o fim; a LTN para tres dias antes. As duas series tem de
    chegar ao mesmo ultimo dia, porque a razao e uma soma movel de seis meses e
    ela nao deixa de existir no dia em que aquele papel nao foi a mercado.
    """
    import pandas as pd

    from tesouro import config
    from tesouro.graficos import emissao

    dias_de_leilao = pd.date_range("2024-01-02", "2025-01-02", freq="7D")
    linhas = []
    for data in dias_de_leilao:
        for familia, titulo in (("LFT", "LFT"), ("LTN", "LTN")):
            # A LTN para tres dias antes do fim: sem leilao no ultimo pregao.
            if familia == "LTN" and data == dias_de_leilao[-1]:
                continue
            linhas.append({
                "estagio": "planilha", "data_leilao": data,
                "data_liquidacao": data + pd.Timedelta(days=1),
                "titulo": titulo, "familia": familia, "operacao": "venda",
                "volta": "1a volta", "data_vencimento": "2030-01-01",
                "quantidade": 1000.0, "oferta_qtd": 2000.0,
                "financeiro_milhoes": 100.0, "taxa_media_pct": 10.0,
                "dv_milhoes": 5.0, "dv_ofertado_milhoes": 10.0,
            })
    pd.DataFrame(linhas).to_csv(
        tmp_path / "dv_emitido_por_leilao.csv", index=False)
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)

    d = emissao.colocado_por_familia()

    assert not d.empty, "o dado sintetico nao produziu serie"
    for familia in ("LFT", "LTN"):
        assert familia in d.columns, familia
        assert d[familia].isna().sum() == 0, (
            f"{familia} ficou com buraco: a serie de cada familia tem de cobrir "
            f"o periodo inteiro, e nao so os dias em que ela foi a leilao")
    assert d["LFT"].last_valid_index() == d["LTN"].last_valid_index()


# --------------------------------------------------------------------------
# OS DOIS ACUMULADOS DE 12 MESES, pedido dela em 09/09/2026.
#
# Cada um espelha o semanal logo acima: MESMA cesta de papeis e MESMA grandeza.
# Quem olha de um para o outro ve o mesmo conjunto na semana e nos doze meses,
# sem trocar de universo no meio.
#
#   Soma da semana - financeiro por papel e DV total (sem LFT)
#     -> acumulado 12 meses de DV01,       sem LFT
#   Financeiro da semana, por papel        (com LFT)
#     -> acumulado 12 meses de financeiro, com LFT
#
# A LFT ENTRA NUM E NAO NO OUTRO, e nao e descuido: ela nao tem DV01 -- medido,
# a coluna e inteiramente nula para ela --, entao num grafico de DV ela nao tem
# o que somar, e num de financeiro ela e mais da metade do total.
# --------------------------------------------------------------------------

def test_os_recortes_novos_separam_a_LFT():
    """'sem LFT' e 'tudo' diferem por exatamente uma familia."""
    sem = set(emissao.RECORTES["sem LFT"])
    tudo = set(emissao.RECORTES["tudo"])
    assert tudo - sem == {"LFT"}, (tudo, sem)
    assert "LFT" not in sem


def test_o_recorte_TUDO_cobre_TODAS_as_familias_do_dado():
    """Relacao, e nao lista cravada: se o Tesouro criar uma familia nova, este
    teste fica vermelho em vez de ela sumir do grafico em silencio."""
    import pandas as pd

    from tesouro import config

    d = pd.read_csv(config.PROCESSED_DIR / "dv_emitido_por_leilao.csv")
    assert set(d["familia"].dropna()) == set(emissao.RECORTES["tudo"])


def test_o_acumulado_de_12_meses_SOMA_MAIS_que_o_de_3():
    """A soma movel de doze meses tem de conter a de tres. Pega janela trocada
    e recorte vazio -- os dois modos de a serie sair errada sem parecer."""
    a3 = emissao.acumulado("sem LFT", meses=3, janela=1)
    a12 = emissao.acumulado("sem LFT", meses=12, janela=1)
    assert not a12.empty
    comuns = a3.index.intersection(a12.index)
    assert len(comuns) > 10
    assert (a12.loc[comuns, "financeiro_milhoes"]
            >= a3.loc[comuns, "financeiro_milhoes"] - 1e-6).all()


def test_o_acumulado_COM_LFT_e_maior_que_o_sem():
    """A LFT e mais da metade do financeiro leiloado -- se incluir nao mudar
    nada, o recorte nao esta filtrando o que diz filtrar."""
    sem = emissao.acumulado("sem LFT", meses=12, janela=1)
    com = emissao.acumulado("tudo", meses=12, janela=1)
    comuns = sem.index.intersection(com.index)
    assert len(comuns) > 10
    assert (com.loc[comuns, "financeiro_milhoes"]
            > sem.loc[comuns, "financeiro_milhoes"]).all()


def test_o_desenho_do_acumulado_faz_SO_a_serie_pedida():
    """Ela pediu DV num grafico e financeiro no outro, e nao os dois nos dois.

    O eixo da direita so existe quando ha DV para desenhar; pedir 'financeiro'
    nao pode deixa-lo la vazio, que e o defeito que passa despercebido.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    dados = emissao.acumulado("sem LFT", meses=12, janela=1)

    fig, ax = plt.subplots()
    emissao.desenha_acumulado(dados, ax, "so DV", meses=12, series="dv")
    rotulos = [t.get_text() for t in [ax.yaxis.label]
               + [a.yaxis.label for a in fig.axes if a is not ax]]
    plt.close(fig)
    assert any("DV01" in r for r in rotulos), rotulos
    assert not any("bilh" in r for r in rotulos), (
        "pediu so DV e o eixo de reais apareceu: %s" % rotulos)

    fig, ax = plt.subplots()
    emissao.desenha_acumulado(dados, ax, "so financeiro", meses=12,
                              series="financeiro")
    rotulos = [t.get_text() for t in [ax.yaxis.label]
               + [a.yaxis.label for a in fig.axes if a is not ax]]
    plt.close(fig)
    assert any("bilh" in r for r in rotulos), rotulos
    assert not any("DV01" in r for r in rotulos), (
        "pediu so financeiro e o eixo de DV apareceu: %s" % rotulos)


def test_cada_acumulado_de_12_MESES_vem_LOGO_ABAIXO_do_seu_semanal():
    """A ORDEM E O TESTE, e nao so a presenca.

    O acumulado so se le como companheiro do semanal se estiver colado nele.
    Solto no fim do grupo, ele vira mais um grafico e o leitor perde a ligacao
    entre "esta semana" e "os ultimos doze meses do MESMO conjunto".
    """
    nomes = [g.id for g in painel_emissoes.registro()
             if g.grupo == "Por semana"]
    assert nomes == [
        "emissao_semanal",
        "emissao_acumulado_dv_12m",
        "emissao_empilhado",
        "emissao_acumulado_financeiro_12m",
    ], nomes


def test_o_acumulado_de_DV_nao_leva_LFT_e_o_de_financeiro_leva():
    """A regra que as duas linhas de cima do arquivo explicam, travada aqui.

    Le o TITULO de cada um, que e o que o leitor ve -- se um dia alguem trocar
    o recorte e esquecer o titulo, a pagina passa a mentir e este teste cai.
    """
    porgrupo = {g.id: g for g in painel_emissoes.registro()}
    dv = porgrupo["emissao_acumulado_dv_12m"]
    fin = porgrupo["emissao_acumulado_financeiro_12m"]
    assert "sem LFT" in dv.titulo, dv.titulo
    assert "DV01" in dv.titulo, dv.titulo
    assert "com LFT" in fin.titulo, fin.titulo
    assert "12 meses" in dv.titulo and "12 meses" in fin.titulo


def test_cada_acumulado_novo_desenha_A_SERIE_QUE_O_TITULO_PROMETE():
    """Nao basta desenhar: tem de desenhar o que o titulo diz.

    A primeira versao deste teste so exigia que a figura tivesse alguma linha,
    e passava com a serie ERRADA ligada -- o titulo dizendo DV01 e o grafico
    mostrando reais. Figura que levanta excecao o painel engole por desenho;
    figura que mostra a grandeza errada ninguem engole, mas tambem ninguem ve.

    O EIXO E A PROVA: pedir uma serie so nao pode deixar o eixo da outra
    rotulado e vazio.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    porgrupo = {g.id: g for g in painel_emissoes.registro()}
    esperado = {
        "emissao_acumulado_dv_12m": ("DV01", "bilh"),
        "emissao_acumulado_financeiro_12m": ("bilh", "DV01"),
    }
    for nome, (tem, nao_tem) in esperado.items():
        fig = porgrupo[nome].figura(1)
        rotulos = [ax.yaxis.label.get_text() for ax in fig.axes]
        assert any(ax.lines or ax.collections for ax in fig.axes), (
            f"{nome} saiu sem nenhuma linha nem area desenhada")
        assert any(tem in r for r in rotulos), (nome, rotulos)
        assert not any(nao_tem in r for r in rotulos), (
            f"{nome} mostra a grandeza errada: {rotulos}")
        plt.close(fig)


def test_a_JANELA_do_acumulado_bate_com_o_que_o_titulo_promete():
    """O titulo diz "12 meses"; a legenda diz "soma de N meses", e o N e o
    MESMO que abre a janela movel do dado. Se os dois discordarem, o grafico
    mostra tres meses com cara de doze.

    ACHADO POR MUTACAO em 09/09/2026: trocar meses=12 por meses=3 na ligacao
    da pagina nao deixava NENHUM teste vermelho -- o titulo e um texto literal
    e continuava prometendo doze. Plausivel e errado, do tipo que so aparece
    quando alguem compara com outra fonte.

    O QUE ESTE TESTE NAO PEGA, e esta escrito para nao se supor demais: o
    recorte do grafico de DV. Medido -- a LFT tem a coluna de DV inteiramente
    nula, entao somar "sem LFT" ou "tudo" da a MESMA serie de DV. Ali o
    recorte e questao de rotulo, e quem o guarda e o titulo.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    porgrupo = {g.id: g for g in painel_emissoes.registro()}
    for nome in ("emissao_acumulado_dv_12m", "emissao_acumulado_financeiro_12m"):
        g = porgrupo[nome]
        assert "12 meses" in g.titulo, g.titulo
        fig = g.figura(1)
        rotulos = []
        for ax in fig.axes:
            marcas, textos = ax.get_legend_handles_labels()
            rotulos += textos
            if ax.get_legend() is not None:
                rotulos += [x.get_text() for x in ax.get_legend().get_texts()]
        plt.close(fig)
        assert rotulos, f"{nome} saiu sem legenda; nao da para conferir a janela"
        assert any("soma de 12 meses" in r for r in rotulos), (
            f"{nome}: o titulo promete 12 meses e a legenda diz {rotulos}")


# --------------------------------------------------------------------------
# A AGREGACAO MENSAL, para a pagina do historico completo (09/09/2026).
#
# A serie vai de 02/01/2001 a hoje -- 25,7 anos. Medido em barras:
#
#     por dia de leilao  2.222     por semana  1.287     por mes  309
#
# Numa figura de ~1.100 px a semanal da MENOS DE UM PIXEL por barra, que e o
# borrao que fez a janela "completa" ser cortada da pagina de emissoes em
# 20/08/2026. A mensal da ~3,5 px: nao e confortavel, mas se le -- deixa-se de
# ver meses e passa-se a ver epocas, que e a leitura certa para 25 anos.
#
# PARAMETRO, e nao funcao nova: duplicar a agregacao criaria duas versoes da
# mesma conta, e um dia elas divergiriam sem ninguem notar.
# --------------------------------------------------------------------------

def test_a_agregacao_MENSAL_tem_menos_pontos_que_a_semanal():
    """E a razao de a pagina do historico ser mensal.

    Relacao, e nao contagem cravada: vale em qualquer serie e nao envelhece a
    cada leilao novo.
    """
    semanal = emissao.por_semana_por_familia(janela=None, periodo="W")
    mensal = emissao.por_semana_por_familia(janela=None, periodo="M")
    assert len(mensal) < len(semanal) / 3, (len(mensal), len(semanal))
    assert len(mensal) > 100, "a serie tem 25 anos; menos que isso e recorte"


def test_a_agregacao_MENSAL_conserva_o_total():
    """Trocar a janela nao pode criar nem sumir com dinheiro.

    O total do financeiro tem de ser o MESMO nas duas agregacoes -- se nao for,
    alguma linha esta caindo fora do groupby.
    """
    familias = ["LTN", "NTN-F", "NTN-B curta", "NTN-B longa"]
    semanal = emissao.por_semana_por_familia(janela=None, periodo="W")
    mensal = emissao.por_semana_por_familia(janela=None, periodo="M")
    for f in familias:
        if f not in semanal.columns:
            continue
        assert mensal[f].sum() == pytest.approx(semanal[f].sum(), rel=1e-9), f


def test_o_financeiro_por_papel_tambem_agrega_por_MES():
    semanal = emissao.financeiro_semanal_por_papel(janela=None, periodo="W")
    mensal = emissao.financeiro_semanal_por_papel(janela=None, periodo="M")
    assert len(mensal) < len(semanal) / 3
    assert "LFT" in mensal.columns, "este e o grafico que leva a LFT"
    assert mensal["LFT"].sum() == pytest.approx(semanal["LFT"].sum(), rel=1e-9)


def test_o_ROTULO_DO_EIXO_acompanha_o_periodo():
    """"R$ bilhoes aceitos na semana" numa pagina mensal e legenda mentindo.

    E o mesmo defeito do mutante dos 12 meses: texto literal prometendo uma
    coisa e dado sendo outra. So que aqui no eixo, que e onde mais se acredita.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    for periodo, palavra in (("W", "semana"), ("M", "m\u00eas")):
        dados = emissao.financeiro_semanal_por_papel(janela=1, periodo=periodo)
        fig, ax = plt.subplots()
        emissao.desenha_empilhado(dados, ax, periodo=periodo)
        rotulo = ax.yaxis.label.get_text()
        plt.close(fig)
        assert palavra in rotulo, (periodo, rotulo)


# --------------------------------------------------------------------------
# A PAGINA DO HISTORICO COMPLETO, pedida por ela em 09/09/2026.
#
# "todos os graficos da parte 'por semana', de venda e compra, com segunda
# volta, para o prazo maximo possivel. pode ser uma pagina nova, para nao
# atrapalhar as outras."
#
# PAGINA PROPRIA e a decisao certa, e a razao esta medida: a janela "completa"
# foi CORTADA da pagina de emissoes em 20/08/2026 porque custava 5,9 MB dos
# 9,67 dela. Isolada, com quatro graficos e agregacao mensal, ela custa 0,92 MB
# -- e nao encosta na pagina que ja existe.
#
# E MENSAL, e nao semanal, tambem por medicao: 1.287 barras semanais em 1.100
# px sao menos de um pixel cada. Foi sugestao dela quando eu disse que os
# semanais nao se leriam nessa distancia.
# --------------------------------------------------------------------------

def test_a_pagina_do_historico_tem_OS_SETE_graficos_na_ordem():
    """A ORDEM E O TESTE, e ela tem duas regras, nao uma.

    DO GROSSO PARA O FINO: os dois anuais primeiro -- 26 barras, uma soma so --
    e depois os mensais, 309 barras abertas por papel. Foi ela quem pediu os
    anuais depois de achar o mensal poluido, e o que poluia era o
    EMPILHAMENTO, nao a quantidade de barras.

    E CADA ACUMULADO COLADO NO SEU: o de DV logo abaixo do que mostra DV, o de
    financeiro logo abaixo do que mostra financeiro. Solto no fim do grupo, o
    acumulado vira mais um grafico e some a ligacao com o de cima.

    O ANUAL POR INDEXADOR vem colado no anual detalhado, pelo mesmo motivo: e o
    mesmo dado com tres faixas em vez de cinco, e le-se um olhando o outro.

    Eram dois testes parciais -- um exigia os quatro mensais, outro que os
    anuais viessem primeiro. Com a lista inteira num lugar so, a ordem tem uma
    fonte da verdade.
    """
    nomes = [g.id for g in painel_emissoes.registro_historico()]
    assert nomes == [
        "historico_anual_financeiro",
        "historico_anual_financeiro_agrupado",
        "historico_anual_dv",
        "historico_mensal",
        "historico_acumulado_dv_12m",
        "historico_empilhado",
        "historico_acumulado_financeiro_12m",
    ], nomes


def test_a_pagina_do_historico_e_VENDA_E_COMPRA_com_segunda_volta():
    """A combinacao que ela pediu, e a unica desta pagina.

    Le a NOTA, que e o que o leitor ve -- se alguem trocar a combinacao e
    esquecer a nota, a pagina passa a mentir e este teste cai.
    """
    notas = [g.nota for g in painel_emissoes.registro_historico()]
    assert notas, "a pagina ficou sem grafico"
    assert any("compra" in n for n in notas), notas
    assert any("2\u00aa volta" in n for n in notas), notas


def test_os_graficos_do_historico_dizem_que_sao_MENSAIS():
    """Rotulo que nao acompanha o dado e o defeito que esta pagina mais corre
    risco de ter: ela e a unica mensal do projeto."""
    for g in painel_emissoes.registro_historico():
        assert "semana" not in g.titulo.lower(), g.titulo


def test_a_pagina_do_historico_NAO_oferece_as_janelas_curtas():
    """Oferecer "20 leiloes" aqui seria repetir, mal, a pagina que ja existe.

    Ate 09/09/2026 este teste cravava UMA janela, e a contagem envelheceu no
    mesmo dia, quando ela pediu o zoom de 2014. A regra que ele guardava
    continua valendo, e agora esta escrita como regra: as janelas curtas -- as
    que contam leiloes ou partem de janeiro -- nao entram nesta pagina, que
    existe para a distancia longa.
    """
    from tesouro.graficos import estilo

    for _, janela in painel_emissoes.JANELAS_DO_HISTORICO:
        assert not isinstance(janela, estilo.Ultimos), janela
        assert not isinstance(janela, estilo.DesdeJaneiro), janela
    # E nenhuma delas e uma contagem de anos, que e a forma "ultimos N anos".
    assert not any(isinstance(j, int)
                   for _, j in painel_emissoes.JANELAS_DO_HISTORICO)


def test_a_pagina_do_historico_GRAVA_e_esta_na_barra(tmp_path):
    destino = tmp_path / painel_emissoes.ARQUIVO_HISTORICO
    escrito = painel_emissoes.grava_historico(destino)
    html = escrito.read_text(encoding="utf-8")
    assert len(html) > 100_000, "a pagina saiu vazia demais para ter grafico"

    # AS IRMAS FICARAM A DOIS CLIQUES, e isso e escolha e nao esquecimento.
    #
    # Ate 09/09/2026 esta pagina era um EXTRA da familia de emissoes, e a barra
    # dela listava as tres combinacoes. Ao virar primeiro nivel ela saiu dos
    # extras -- estar nos dois lugares a faria aparecer duas vezes na mesma
    # faixa, que e o defeito que o parametro 'familia' de barra_das_paginas
    # existe para evitar.
    #
    # O que fica: "o que ja foi emitido" continua na barra, e de la se alcanca
    # qualquer uma das tres. Um clique a mais, sem duplicata.
    assert 'href="emissoes.html"' in html, (
        "a entrada da familia de emissoes sumiu da barra")
    for arquivo, _ in dashboard.PAGINAS:
        if arquivo != painel_emissoes.ARQUIVO_HISTORICO:
            assert f'href="{arquivo}"' in html, arquivo


def test_a_pagina_do_historico_cabe_no_limiar_de_dez_megabytes(tmp_path):
    """Medido antes de construir: 0,92 MB nos quatro SVG. O limiar da spec e
    10 MB por pagina, e esta e a unica que desenha 25 anos."""
    destino = tmp_path / painel_emissoes.ARQUIVO_HISTORICO
    escrito = painel_emissoes.grava_historico(destino)
    mb = escrito.stat().st_size / 1048576
    assert mb < 10, f"{mb:.2f} MB"


def test_a_largura_da_barra_MENSAL_nao_fica_estrangulada_pelo_teto():
    """O teto de 5 dias serve ao diario e ao semanal, e nao ao mensal.

    ACHADO OLHANDO O DESENHO, e nao por teste: a pagina do historico saiu com
    barras finas e vaos largos. _largura devolve
    max(0,8, min(espacamento * 0,75, TETO)) -- com espacamento mensal de ~30
    dias, 0,75 daria ~22 e o teto de 5 cortava para um sexto do vao. O
    resultado lia como rendilhado, e a composicao por papel (que e o assunto do
    grafico empilhado) desaparecia.

    O TETO CONTINUA EXISTINDO, e continua em 5 por padrao: ele impede que um
    trecho de serie esparsa vire bloco. O que muda e poder afrouxa-lo onde o
    espacamento e regular e conhecido.
    """
    import pandas as pd

    mensal = pd.date_range("2001-01-01", "2026-09-01", freq="MS")
    semanal = pd.date_range("2024-01-01", "2026-09-01", freq="W")

    # O PADRAO NAO MUDA -- as paginas que ja existem tem de sair identicas.
    assert emissao._largura(semanal) == 5.0
    assert emissao._largura(mensal) == 5.0

    # E com o teto afrouxado a barra mensal ocupa a maior parte do vao.
    larga = emissao._largura(mensal, maximo=emissao.TETO_MENSAL)
    assert larga > 20, larga
    espacamento = (mensal.max() - mensal.min()).days / (len(mensal) - 1)
    assert larga < espacamento, "barra mais larga que o vao encavala as vizinhas"


def test_o_grafico_MENSAL_do_historico_usa_o_teto_afrouxado():
    """Nao basta a funcao aceitar o parametro: a pagina tem de passa-lo.

    Sem isto o defeito continuaria na tela e o teste acima passaria feliz --
    exatamente o vao que a conferencia dos 12 meses achou por mutacao.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    d = {g.id: g for g in painel_emissoes.registro_historico()}
    # OS DOIS graficos de barra da pagina, e nao so um: o empilhado e o de
    # dois eixos desenham por caminhos diferentes, e consertar um so deixaria
    # metade da pagina rendilhada.
    for nome in ("historico_empilhado", "historico_mensal"):
        fig = d[nome].figura(None)
        larguras = [p.get_width() for ax in fig.axes for p in ax.patches]
        plt.close(fig)
        assert larguras, f"{nome} saiu sem barra nenhuma"
        assert max(larguras) > 20, (
            f"{nome}: barras estranguladas, maior largura {max(larguras)}")


# --------------------------------------------------------------------------
# OS DOIS GRAFICOS ANUAIS, pedido dela em 09/09/2026: "um grafico anual da soma
# de dv, e da soma de financeiro... igual voce fez o mensal agora, mas ainda
# achei poluido".
#
# O que poluia era o EMPILHAMENTO por papel, e nao a quantidade de barras: sao
# 26 anos contra 309 meses. Aqui a barra e uma soma so, e sao dois graficos --
# escolha dela -- em vez de um com dois eixos.
#
# A LFT ENTRA NO DE FINANCEIRO E NAO NO DE DV, como nos acumulados: ela nao tem
# DV01.
# --------------------------------------------------------------------------

def test_a_agregacao_ANUAL_da_uma_barra_por_ano():
    """Relacao, e nao contagem cravada: a serie ganha um ano por ano."""
    import pandas as pd

    anual = emissao.por_dia("tudo", periodo="Y")
    assert len(anual) > 20, "a serie tem 25 anos"
    anos = pd.DatetimeIndex(anual.index).year
    assert len(set(anos)) == len(anual), "ha mais de uma barra no mesmo ano"
    assert list(anos) == sorted(anos)


def test_a_agregacao_ANUAL_conserva_o_financeiro():
    """Trocar a janela nao pode criar nem sumir com dinheiro."""
    diario = emissao.por_dia("tudo")
    anual = emissao.por_dia("tudo", periodo="Y")
    assert anual["financeiro_milhoes"].sum() == pytest.approx(
        diario["financeiro_milhoes"].sum(), rel=1e-9)


def test_o_ANUAL_de_financeiro_leva_LFT_e_o_de_DV_nao():
    """A mesma regra dos acumulados, pela mesma razao medida."""
    com = emissao.por_dia("tudo", periodo="Y")
    sem = emissao.por_dia("sem LFT", periodo="Y")
    assert com["financeiro_milhoes"].sum() > sem["financeiro_milhoes"].sum()
    # E o DV e o MESMO nos dois, porque a LFT nao tem DV nenhum para somar.
    assert com["dv_milhoes"].sum() == pytest.approx(
        sem["dv_milhoes"].sum(), rel=1e-9)


def test_a_largura_da_barra_ANUAL_nao_fica_estrangulada():
    """Sem teto proprio, 26 barras num vao de 365 dias saem com 5 -- um pente.

    E o mesmo defeito do mensal, achado olhando o desenho.
    """
    import pandas as pd

    anual = pd.date_range("2001-01-01", "2026-01-01", freq="YS")
    assert emissao._largura(anual) == 5.0, "o padrao nao pode mudar"
    larga = emissao._largura(anual, maximo=emissao.TETO_ANUAL)
    assert larga > 200, larga
    espacamento = (anual.max() - anual.min()).days / (len(anual) - 1)
    assert larga < espacamento, "barra mais larga que o vao encavala as vizinhas"


def test_o_ANO_PARCIAL_sai_MARCADO_no_grafico():
    """A armadilha deste grafico, e a unica dele.

    2026 vai ate 08/09 e soma 1.235,7 bi contra 1.727,0 de 2025. Ao lado da
    outra, essa barra PARECE QUEDA e e so o ano nao ter acabado -- plausivel e
    errado, do tipo que ninguem confere porque o grafico esta certo.

    A DATA SAI DO DADO, e nao cravada: no dia em que o ano fechar, a marca tem
    de sumir sozinha.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd

    dados = emissao.por_dia("tudo", periodo="Y")
    ate = emissao.ultima_data()
    parcial = pd.Timestamp(dados.index.max()).year == ate.year and (
        ate.month, ate.day) != (12, 31)
    assert parcial, (
        "hoje o ultimo ano esta incompleto; se isto mudar, o teste precisa de "
        "outro caso")

    dados = emissao.por_familia("financeiro_milhoes", periodo="Y")
    fig, ax = plt.subplots()
    emissao.desenha_empilhado(dados, ax, periodo="Y", ate=ate,
                              rotulo="financeiro por ano")
    rotulos = [r.get_text() for r in ax.get_xticklabels()]
    # loc="left" E A CONVENCAO DA PAGINA, e ax.get_title() sem argumento
    # devolve o titulo CENTRAL -- que esta vazio. A primeira versao deste teste
    # perguntou pelo lugar errado e acusou o codigo por erro proprio.
    titulo = ax.get_title(loc="left")
    plt.close(fig)
    assert any("*" in r for r in rotulos), rotulos
    assert f"{ate:%d/%m/%Y}" in titulo, titulo


# --------------------------------------------------------------------------
# OS ANUAIS SAO EMPILHADOS POR PAPEL. Correcao dela em 09/09/2026.
#
# EU TINHA CONCLUIDO ERRADO. Quando ela disse que o mensal estava "poluido", eu
# li que o problema era o EMPILHAMENTO e fiz os anuais com uma soma so. Ela
# corrigiu: o que poluia era a QUANTIDADE DE BARRAS -- 309 contra 26. Com 26
# barras largas, o empilhamento cabe e mostra a composicao, que e o que se quer
# ver a 25 anos de distancia.
#
# A licao, que vale para o proximo palpite: "poluido" descrevia o desenho, e eu
# converti em causa sem perguntar. Duas causas cabiam na mesma palavra.
# --------------------------------------------------------------------------

def test_por_familia_abre_QUALQUER_grandeza_por_papel():
    """Ate aqui so o financeiro se abria por familia; o DV precisa do mesmo."""
    fin = emissao.por_familia("financeiro_milhoes", periodo="Y")
    dv = emissao.por_familia("dv_milhoes", periodo="Y")
    assert set(emissao.ORDEM_FAMILIAS) <= set(fin.columns)
    assert set(emissao.ORDEM_FAMILIAS) <= set(dv.columns)
    # E cada uma soma o que promete.
    diario = emissao.por_dia("tudo")
    assert fin[list(emissao.ORDEM_FAMILIAS)].sum().sum() == pytest.approx(
        diario["financeiro_milhoes"].sum(), rel=1e-9)


def test_os_DOIS_anuais_sao_EMPILHADOS_por_papel():
    """Barra empilhada tem uma faixa por familia; barra simples tem uma so.

    Conta os retangulos: com cinco familias e 26 anos, o empilhado desenha
    muito mais do que 26.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    d = {g.id: g for g in painel_emissoes.registro_historico()}
    for nome in ("historico_anual_financeiro", "historico_anual_dv"):
        fig = d[nome].figura(None)
        barras = [p for ax in fig.axes for p in ax.patches]
        plt.close(fig)
        assert len(barras) > 26 * 2, (
            f"{nome} desenhou {len(barras)} retangulos; empilhado por familia "
            f"desenha varios por ano")


def test_o_anual_de_DV_nao_desenha_a_faixa_da_LFT():
    """A LFT nao tem DV01: uma faixa dela num grafico de DV seria uma faixa de
    altura zero com nome, que e pior que nao ter."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    d = {g.id: g for g in painel_emissoes.registro_historico()}
    fig = d["historico_anual_dv"].figura(None)
    rotulos = [t.get_text() for ax in fig.axes
               if ax.get_legend() is not None
               for t in ax.get_legend().get_texts()]
    plt.close(fig)
    assert rotulos, "o grafico saiu sem legenda de familia"
    assert "LFT" not in rotulos, rotulos

    fig = d["historico_anual_financeiro"].figura(None)
    rotulos = [t.get_text() for ax in fig.axes
               if ax.get_legend() is not None
               for t in ax.get_legend().get_texts()]
    plt.close(fig)
    assert "LFT" in rotulos, ("o de financeiro leva a LFT", rotulos)


def test_o_anual_de_DV_sai_na_unidade_de_DV():
    """Escala e rotulo andam juntos: o empilhado divide por mil por padrao,
    porque nasceu para reais. Em DV isso daria numero mil vezes menor com o
    rotulo certo -- plausivel e errado."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    d = {g.id: g for g in painel_emissoes.registro_historico()}
    fig = d["historico_anual_dv"].figura(None)
    rotulo = fig.axes[0].yaxis.label.get_text()
    alturas = [abs(p.get_height()) for p in fig.axes[0].patches]
    plt.close(fig)
    assert "DV01" in rotulo, rotulo
    assert "bilh" not in rotulo, rotulo
    # O DV anual chega a centenas de milhoes por ponto-base; dividido por mil
    # por engano, nao passaria de um.
    assert max(alturas) > 10, max(alturas)


def test_desenha_barra_anual_NAO_EXISTE_MAIS():
    """Ela nasceu e morreu no mesmo dia, quando os anuais viraram empilhados.

    Funcao morta ao lado da viva engana quem le depois -- foi o caso da
    HACHURA_PROVISORIO, que ficou meses definida e sem uso.
    """
    assert not hasattr(emissao, "desenha_barra_anual")


# --------------------------------------------------------------------------
# OS ANUAIS SEM NUMERO SOLTO, E A JANELA DE 2014. Pedido dela em 09/09/2026:
# "no anual de financeiro tem um numero (1236), nao sei o que ele esta
# marcando, pode tirar. e faz esse mesmo grafico com um zoom de 2014 ate hoje".
#
# O numero era o _marca_pontos, que escreve o ULTIMO ponto e os extremos. Nos
# graficos de dia e de semana ele ajuda: sao centenas de barras finas e o
# ultimo valor e o que se foi ver. No anual sao 26 barras rotuladas, com eixo
# legivel -- e o "ultimo ponto" e justamente 2026*, o ano PARCIAL, que e o
# numero que menos se quer destacado.
# --------------------------------------------------------------------------

def test_os_anuais_NAO_ESCREVEM_numero_solto_sobre_as_barras():
    """Ela apontou o 1.236 e perguntou o que ele marcava. Marcava o ano que
    ainda nao acabou."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    d = {g.id: g for g in painel_emissoes.registro_historico()}
    for nome in ("historico_anual_financeiro", "historico_anual_dv"):
        fig = d[nome].figura(None)
        textos = [t.get_text() for ax in fig.axes for t in ax.texts]
        plt.close(fig)
        assert textos == [], (nome, textos)


def test_o_EMPILHADO_POR_PAPEL_nao_escreve_numero_solto():
    """Ela pediu em 10/09/2026: "no grafico financeiro da semana por papel tem
    uns numeros no meio do grafico, tira eles".

    _marca_pontos escreve o valor do ULTIMO ponto e dos extremos. Numa barra
    EMPILHADA o topo e a soma das faixas, entao o numero cai no meio do desenho
    e sem dizer a que se refere -- nao e o valor de nenhuma faixa, e o eixo ja
    da a escala.

    SAI DA SEMANA E DO MES: e o mesmo grafico desenhado em dois periodos.
    Manter num e nao no outro seria arbitrario, e ninguem lembraria por que.

    Ate 09/09 havia aqui um teste exigindo o contrario para o mensal -- eu
    tinha lido a remocao no anual como "so no anual". Ela corrigiu.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    d = {g.id: g for g in painel_emissoes.registro_historico()}
    fig = d["historico_empilhado"].figura(None)
    textos = [t.get_text() for ax in fig.axes for t in ax.texts]
    plt.close(fig)
    assert textos == [], ("o empilhado mensal ainda escreve numero", textos)

    # E o semanal, que e o que ela viu.
    porgrupo = {g.id: g for g in painel_emissoes.registro()}
    fig = porgrupo["emissao_empilhado"].figura(1)
    textos = [t.get_text() for ax in fig.axes for t in ax.texts]
    plt.close(fig)
    assert textos == [], ("o empilhado semanal ainda escreve numero", textos)


def test_o_grafico_de_DOIS_EIXOS_continua_com_a_marca():
    """Nao foi para tirar de todo lado.

    No de dois eixos o numero diz qual e o valor da LINHA de DV no ultimo
    ponto -- ali ele identifica uma serie, e nao uma soma anonima de faixas.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    porgrupo = {g.id: g for g in painel_emissoes.registro()}
    fig = porgrupo["emissao_semanal"].figura(1)
    textos = [t.get_text() for ax in fig.axes for t in ax.texts]
    plt.close(fig)
    assert textos, "o de dois eixos perdeu a marca junto, e nao era para perder"


def test_a_pagina_do_historico_tem_a_janela_de_2014():
    """Duas janelas: a serie inteira e o zoom de 2014."""
    rotulos = [r for r, _ in painel_emissoes.JANELAS_DO_HISTORICO]
    assert rotulos == ["completa", "2014 em diante"], rotulos


def test_a_janela_de_2014_e_FIXA_e_nao_relativa():
    """Se fosse "ultimos 12 anos", no ano que vem o rotulo diria 2014 e o
    grafico mostraria 2015 -- rotulo mentindo, que e o defeito que este projeto
    ja pegou tres vezes hoje."""
    import pandas as pd

    _, janela = painel_emissoes.JANELAS_DO_HISTORICO[1]
    de, ate = janela
    assert pd.Timestamp(de) == pd.Timestamp("2014-01-01"), de
    assert ate is None, "o fim e a ponta da serie, e nao uma data cravada"


def test_a_janela_de_2014_corta_a_serie_de_verdade():
    import pandas as pd

    _, janela = painel_emissoes.JANELAS_DO_HISTORICO[1]
    inteira = emissao.por_familia("financeiro_milhoes", periodo="Y")
    zoom = emissao.por_familia("financeiro_milhoes", janela, periodo="Y")
    assert len(zoom) < len(inteira)
    assert pd.DatetimeIndex(zoom.index).year.min() == 2014
    assert pd.DatetimeIndex(zoom.index).year.max() == (
        pd.DatetimeIndex(inteira.index).year.max()), "o zoom vai ate hoje"


def test_a_pagina_do_historico_esta_na_BARRA_DO_TOPO():
    """Ate 09/09/2026 ela so era alcancavel de dentro da familia de emissoes:
    quem estava no dashboard tinha de passar por emissoes.html para achar. Ela
    responde outra pergunta -- 25 anos -- e merece o primeiro nivel."""
    from tesouro.graficos import dashboard

    arquivos = [a for a, _ in dashboard.PAGINAS]
    assert painel_emissoes.ARQUIVO_HISTORICO in arquivos, arquivos


def test_a_pagina_do_historico_aparece_UMA_VEZ_SO_na_barra(tmp_path):
    """Primeiro nivel E extra ao mesmo tempo sairia duas vezes na mesma faixa.

    E o defeito que a propria barra ja teve com emissoes.html, e que o
    parametro 'familia' existe para evitar -- o docstring dela conta.
    """
    destino = tmp_path / painel_emissoes.ARQUIVO_HISTORICO
    html = painel_emissoes.grava_historico(destino).read_text(encoding="utf-8")
    barra = html[html.index('<div id="paginas">'):html.index("</div>",
                                                             html.index('<div id="paginas">'))]
    assert barra.count(painel_emissoes.ARQUIVO_HISTORICO) <= 1, barra

    # E a partir de uma das irmas ela e link, uma vez so.
    outro = tmp_path / "emissoes.html"
    html2 = painel_emissoes.grava(outro, com_compra=False, com_2a=True).read_text(
        encoding="utf-8")
    barra2 = html2[html2.index('<div id="paginas">'):html2.index("</div>",
                                                                 html2.index('<div id="paginas">'))]
    assert barra2.count(f'href="{painel_emissoes.ARQUIVO_HISTORICO}"') == 1, barra2


def test_a_nota_da_RECOMPRA_fora_de_leilao_chega_ao_grafico_anual():
    # Medido em 24/09/2026 contra a aba 1.3 do RMD, em 237 meses: a nossa unica
    # fonte de compra e a planilha de leiloes, e o Tesouro tambem recomprou fora
    # de leilao. Como a compra entra com sinal negativo, o liquido das barras
    # anuais fica ALTO nos anos em que isso aconteceu.
    #
    # A nota nomeia MES e VALOR, a pedido dela -- porcentagem exigia que o
    # leitor soubesse o tamanho da barra para dimensionar o erro.
    from tesouro.graficos import painel_emissoes

    anuais = [g for g in painel_emissoes.registro_historico()
              if "anual_financeiro" in g.id]
    assert len(anuais) == 2, "esperava os dois anuais de financeiro"

    for g in anuais:
        d = g.nota
        assert "fora de leil" in d, g.nome
        # Os quatro eventos, com o valor em bilhoes.
        for quando, quanto in (("dez/2012", "16,1"), ("dez/2016", "40,7"),
                               ("set/2017", "15,3"), ("dez/2019", "8,6")):
            assert quando in d, f"{g.id}: falta {quando}"
            assert quanto in d, f"{g.id}: falta o valor {quanto} bi"
        # E o que ELA sabia e o dado nao dizia.
        assert "BNDES" in d, g.nome
        # O limite que impede a nota de soar como defeito permanente.
        assert "2020" in d and "3,2" in d, g.nome


def test_a_nota_da_recompra_NAO_entra_no_grafico_de_DV01():
    # O buraco foi medido em FINANCEIRO, contra a aba 1.3. O DV01 tambem tem
    # compra, mas ninguem conferiu aquele numero -- por a nota ali seria
    # estender uma medicao para onde ela nao chegou.
    from tesouro.graficos import painel_emissoes

    dv = [g for g in painel_emissoes.registro_historico()
          if "anual_dv" in g.id]
    assert dv, "esperava o anual de DV01"
    for g in dv:
        assert "BNDES" not in g.nota, (
            f"{g.id}: a nota da recompra fala de financeiro, nao de DV01")


def test_a_pagina_RAPIDA_tem_arquivo_proprio_e_sobrevive_a_fase_2():
    # MUDANCA DE 24/09/2026, pedida por ela. Ate aqui a fase rapida gravava por
    # cima da emissoes.html e a fase 2 a substituia ~140 s depois: a versao de
    # 1 MB existia numa janela de dois minutos.
    #
    # O uso mudou. Em setembro era abrir no navegador, e sobrescrever fazia
    # sentido -- mesmo endereco, conteudo melhor. Agora e ANEXO DE E-MAIL, e
    # anexo precisa continuar existindo: 1 MB passa em qualquer caixa, os 7,25
    # MB da completa nao.
    from tesouro.graficos import painel_emissoes

    assert painel_emissoes.ARQUIVO_RAPIDA != "emissoes.html"
    assert painel_emissoes.ARQUIVO_RAPIDA not in [
        a for _, _, a, _ in painel_emissoes.COMBINACOES], (
        "a rapida nao pode dividir arquivo com nenhuma das tres combinacoes")


def test_a_rapida_grava_no_arquivo_dela_e_nao_na_completa(tmp_path,
                                                          monkeypatch):
    # A prova de que sobrevive: gravar a rapida e depois a completa, e a rapida
    # continuar la, com UMA janela.
    import shutil

    from tesouro import config
    from tesouro.graficos import painel_emissoes

    # O CSV vai JUNTO para a pasta temporaria: PROCESSED_DIR e onde a pagina
    # grava E de onde o grafico le. Redirecionar so a escrita deixaria o teste
    # sem dado; escrever na pasta de verdade faria o teste sobrescrever a
    # pagina publicada -- que e o defeito que esta rodada esta consertando.
    # TODOS os CSVs, e nao os que eu achar que a pagina le. A primeira versao
    # copiava so o dv_emitido_por_leilao.csv e quebrava no composicao_dpf.csv;
    # adivinhar a lista deixaria o teste refem de qualquer grafico novo. Sao
    # 15 MB e uma copia de disco.
    for csv in config.PROCESSED_DIR.glob("*.csv"):
        shutil.copy(csv, tmp_path / csv.name)
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path, raising=False)

    rapida = painel_emissoes.grava_rapida()
    assert rapida.name == painel_emissoes.ARQUIVO_RAPIDA
    tamanho_antes = rapida.stat().st_size

    completa = painel_emissoes.grava(com_compra=False, com_2a=True)
    assert completa.name == "emissoes.html"
    assert completa != rapida, "a fase 2 nao pode escrever por cima da rapida"
    assert rapida.exists() and rapida.stat().st_size == tamanho_antes, (
        "a pagina rapida sumiu ou mudou depois da fase 2")

    # E ela e mesmo a de UMA janela. A COMPARACAO E DIFERENCIAL, contra a
    # completa, e nao "quantos nomes de janela faltam": rotulos como "12 meses"
    # e "5 anos" aparecem em outros lugares da pagina (acumulados, benchmarks),
    # entao procurar substring solta nao distingue janela de texto qualquer --
    # erro que eu cometi duas vezes nesta mesma sessao.
    hr = rapida.read_text(encoding="utf-8")
    hc = completa.read_text(encoding="utf-8")
    for nome in ("no ano", "desde o ano anterior"):
        assert nome in hc, f"a completa devia ter a janela {nome!r}"
        assert nome not in hr, (
            f"a rapida trouxe a janela {nome!r}: ela e so a de 20 leiloes")
    assert len(hr) < len(hc) / 2, (
        "a rapida devia ser bem menor que a completa -- e por isso que ela "
        "serve de anexo de e-mail")
