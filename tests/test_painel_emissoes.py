"""As tres paginas de emissao, uma por combinacao de compra e segunda volta."""
import re

import matplotlib
matplotlib.use("Agg")
import pytest

from tesouro.graficos import emissao, estilo, painel_emissoes


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
    assert len(so_venda) == len(com_compra) == 11
    assert "S\u00f3 venda" in so_venda[0].nota
    assert "compra" in com_compra[0].nota
    assert so_venda[0].nota != com_compra[0].nota


@pytest.fixture(scope="module")
def pagina(tmp_path_factory):
    destino = tmp_path_factory.mktemp("emissoes") / "emissoes.html"
    caminho = painel_emissoes.grava(destino, com_compra=False, com_2a=True)
    return caminho.read_text(encoding="utf-8")


def test_a_pagina_traz_os_onze_graficos_e_os_tres_grupos(pagina):
    for g in painel_emissoes.registro():
        assert f'id="{g.id}"' in pagina, g.id
    for grupo in painel_emissoes.GRUPOS:
        assert grupo in pagina
    assert pagina.count("<section") == 11


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

    # E a pagina de fato embute imagem, em vez de apontar para ela: a barra de cor
    # das duas dispersoes. Se isto deixar de valer, o teste acima ficou vazio.
    assert 'data:image/png;base64,' in pagina
    assert "<link" not in pagina
    assert not re.search(r"<script[^>]+src=", pagina)
    # E os links entre as quatro paginas sao RELATIVOS, que e o que os faz
    # funcionar com duplo clique.
    for _, _, arquivo, _ in painel_emissoes.COMBINACOES[1:]:
        assert f'href="{arquivo}"' in pagina


# --------------------------------------------------------------------------
# As tres aparencias, para os tres momentos: ofertado (fantasma com contorno),
# aceito (hachurado) e planilha (solido).
#
# O risco aqui nao e o grafico ficar feio. E alguem olhar um numero hoje, outro
# amanha, e nao ter como saber por que mudou.
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
    # So o aceito e hachurado.
    assert a["hatch"] == ["", "", emissao.HACHURA_ACEITO, ""]
    # E so a oferta tem contorno grosso, que e o que a faz ler como contorno.
    assert a["linewidth"][3] > a["linewidth"][2] > a["linewidth"][0]


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


def test_a_legenda_explica_so_os_estagios_presentes():
    # Listra sem legenda e enfeite. E legenda de um estagio que nao esta na tela e
    # ruido: quem olha procura a barra e nao acha.
    ambos = emissao._legenda_dos_estagios(["planilha", "aceito", "ofertado"])
    assert [e.get_label() for e in ambos] == [
        emissao._ROTULO_DO_ESTAGIO["ofertado"], emissao._ROTULO_DO_ESTAGIO["aceito"]]

    so_aceito = emissao._legenda_dos_estagios(["planilha", "aceito"])
    assert len(so_aceito) == 1
    assert "API" in so_aceito[0].get_label()

    assert emissao._legenda_dos_estagios(None) == []


def test_o_rotulo_da_oferta_diz_que_e_teto_e_nao_de_onde_veio_a_taxa():
    # A palavra TETO importa: sem ela, a barra mais alta do grafico parece emissao
    # recorde quando e so o anuncio. O Tesouro aceita 83,9% do que oferta.
    rotulo = emissao._ROTULO_DO_ESTAGIO["ofertado"]
    assert "TETO" in rotulo

    # E o rotulo NAO fala de taxa. A proveniencia varia linha a linha, e uma frase
    # fixa mentiria nos dias em que ela digita todas -- foi o que aconteceu no
    # primeiro dia de uso. Quem conta e o aviso do topo da pagina.
    assert "leil\u00e3o anterior" not in rotulo
    assert "taxa" not in rotulo.lower()


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


def test_o_aviso_do_provisorio_diz_quais_dias_e_em_que_momento(tmp_path,
                                                               monkeypatch):
    # A marca no grafico diz "esta barra e provisoria"; o aviso diz QUAL DIA e EM
    # QUE MOMENTO. Sao os dois dados que permitem conferir contra a planilha depois.
    import pandas as pd
    from tesouro import config

    pd.DataFrame({"estagio": ["planilha", "aceito", "ofertado"],
                  "data_leilao": ["2026-08-11", "2026-08-20", "2026-08-25"]}
                 ).to_csv(tmp_path / "dv_emitido_por_leilao.csv", index=False)
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)

    aviso = painel_emissoes._aviso_do_provisorio()
    assert "2026-08-20" in aviso
    assert "2026-08-25" in aviso
    assert "2026-08-11" not in aviso     # esse a planilha ja confirmou
    # E cada data com o seu momento, e nao os dois no mesmo saco: um vai mudar de
    # quantidade, o outro so de taxa.
    assert aviso.index("2026-08-25") < aviso.index("2026-08-20")
    assert "teto" in aviso


def test_o_aviso_so_mostra_o_momento_que_existe(tmp_path, monkeypatch):
    # Aviso sobre um estagio que nao esta na tela e ruido: quem le procura a barra
    # e nao acha.
    import pandas as pd
    from tesouro import config

    pd.DataFrame({"estagio": ["planilha", "aceito"],
                  "data_leilao": ["2026-08-11", "2026-08-20"]}
                 ).to_csv(tmp_path / "dv_emitido_por_leilao.csv", index=False)
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)

    aviso = painel_emissoes._aviso_do_provisorio()
    assert "hachurado" in aviso
    assert "teto" not in aviso


def test_sem_provisorio_a_pagina_nao_ganha_aviso_nenhum(tmp_path, monkeypatch):
    # Pagina de historico nao precisa de aviso sobre uma coisa que nao esta la --
    # e um aviso permanente vira ruido que ninguem le quando importar.
    import pandas as pd
    from tesouro import config

    pd.DataFrame({"estagio": ["planilha"], "data_leilao": ["2026-08-11"]}
                 ).to_csv(tmp_path / "dv_emitido_por_leilao.csv", index=False)
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)
    assert painel_emissoes._aviso_do_provisorio() == ""


def test_csv_sem_a_coluna_estagio_nao_quebra_a_pagina(tmp_path, monkeypatch):
    import pandas as pd
    from tesouro import config

    pd.DataFrame({"data_leilao": ["2026-08-11"]}
                 ).to_csv(tmp_path / "dv_emitido_por_leilao.csv", index=False)
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)
    assert painel_emissoes._aviso_do_provisorio() == ""


# --------------------------------------------------------------------------
# As janelas do leilao. O dashboard do RMD fala em anos porque estoque se move
# em anos; leilao se move em semanas, e a barra de hoje tem de ser visivel.
# --------------------------------------------------------------------------

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
    # entao 50 pregoes colapsam sobre "12 meses" -- mediram-se 50 contra 51 pontos,
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
    # "20 leiloes" conta PONTOS do grafico. Nos dois graficos por semana um ponto e
    # uma semana, entao a janela mostra 20 semanas -- e o rotulo mentiria em
    # silencio sem esta nota.
    por_semana = [g for g in painel_emissoes.registro()
                  if g.grupo == "Por semana"]
    assert len(por_semana) == 2
    for g in por_semana:
        assert "semana" in g.nota
        assert "20 leil\u00f5es" in g.nota


def test_de_quantidade_e_taxa_sobrou_so_a_dispersao():
    # A opcao A repetia o idioma de dois eixos que ja aparece sete vezes na pagina.
    # Guardar as duas "para decidir depois" e uma forma de nunca decidir.
    grupo = [g for g in painel_emissoes.registro()
             if g.grupo == "Quantidade e taxa"]
    assert len(grupo) == 2
    assert all("taxa contra quantidade" in g.titulo for g in grupo)
    assert not hasattr(emissao, "desenha_quantidade_e_taxa")


# --------------------------------------------------------------------------
# De onde veio a taxa da barra de oferta. Contada, e nao afirmada.
# --------------------------------------------------------------------------

def _recorte(supostas, total):
    import pandas as pd
    return pd.DataFrame({"taxa_suposta": [True] * supostas
                                          + [False] * (total - supostas)})


def test_a_nota_da_taxa_conta_em_vez_de_afirmar():
    # O DEFEITO QUE ISTO CONSERTA: a legenda dizia "a taxa e a do leilao anterior"
    # fixo. No primeiro dia de uso ela digitou as tres taxas, e a legenda mentiu.
    toda_dela = painel_emissoes._nota_da_taxa(_recorte(0, 3), "ofertado")
    assert "sua" in toda_dela
    assert "emprestada" not in toda_dela

    toda_emprestada = painel_emissoes._nota_da_taxa(_recorte(3, 3), "ofertado")
    assert "emprestada" in toda_emprestada
    assert "11 bp" in toda_emprestada

    misturada = painel_emissoes._nota_da_taxa(_recorte(1, 3), "ofertado")
    assert "2 de 3" in misturada
    assert "sua" in misturada and "emprestada" in misturada


def test_a_nota_da_taxa_nao_aparece_no_estagio_do_resultado():
    # No aceito a taxa e a publicada: nao ha o que contar, e a frase seria ruido.
    assert painel_emissoes._nota_da_taxa(_recorte(0, 3), "aceito") == ""


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
