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
    assert len(so_venda) == len(com_compra) == 13
    assert "S\u00f3 venda" in so_venda[0].nota
    assert "compra" in com_compra[0].nota
    assert so_venda[0].nota != com_compra[0].nota


@pytest.fixture(scope="module")
def pagina(tmp_path_factory):
    destino = tmp_path_factory.mktemp("emissoes") / "emissoes.html"
    caminho = painel_emissoes.grava(destino, com_compra=False, com_2a=True)
    return caminho.read_text(encoding="utf-8")


def test_a_pagina_traz_os_treze_graficos_e_os_tres_grupos(pagina):
    for g in painel_emissoes.registro():
        assert f'id="{g.id}"' in pagina, g.id
    for grupo in painel_emissoes.GRUPOS:
        assert grupo in pagina
    assert pagina.count("<section") == 13


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
    assert so_aceito[0].get_label() == emissao._ROTULO_DO_ESTAGIO["aceito"]

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
    assert emissao._ROTULO_DO_ESTAGIO["aceito"] == "leil\u00e3o de hoje"


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


def test_a_dispersao_e_contra_DV01_e_nao_contra_quantidade():
    # ITEM 10 DA REVISAO: "eles ainda nao passam nenhuma info". E nao passavam: a
    # quantidade de titulos mistura uma LTN de seis meses com uma NTN-B de 35 anos
    # como se fossem a mesma coisa, entao lotes de tamanho parecido e risco dez
    # vezes diferente caiam na mesma coluna, e a nuvem saia sem forma.
    grupo = [g for g in painel_emissoes.registro() if g.grupo == "Taxa e risco"]
    assert len(grupo) == 2
    assert all("DV01" in g.titulo for g in grupo)
    assert not hasattr(emissao, "desenha_quantidade_e_taxa")
    assert not hasattr(emissao, "desenha_taxa_contra_quantidade")
    assert hasattr(emissao, "desenha_taxa_contra_dv")


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
