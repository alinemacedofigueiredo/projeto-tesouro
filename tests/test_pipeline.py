"""Testes do orquestrador (src/tesouro/pipeline.py).

Ate a Tarefa 10, pipeline.py nao tinha nenhum teste -- nem o invariante
"--sem-coleta nunca toca rede" (restricao dura do ambiente do banco), nem
o try/except da coleta da Bloomberg, nem a ordem/contrato das etapas que
gravam os 22 CSVs. Os tres ganham teste aqui, todos com monkeypatch nas
funcoes de gravacao/coleta reais -- rodar o pipeline de ponta a ponta de
verdade (com dado real) e feito a mao no fechamento da tarefa, nao aqui.
"""
import pathlib
import socket

import pytest

from tesouro import (
    dv, figuras, fetch_bloomberg, fetch_leiloes, fetch_rmd, parse_bloomberg,
    parse_leiloes, parse_rmd, pipeline,
)


def _sem_efeito(*args, **kwargs):
    return None


def _stub_gravacoes(monkeypatch, chamadas=None):
    """Substitui toda funcao de gravacao real por um stub sem IO.

    Se `chamadas` for uma lista, cada stub registra o proprio nome nela
    antes de devolver uma LISTA VAZIA -- usado para conferir ordem.

    Lista, e nao None: desde que o dashboard virou duas paginas, o pipeline ITERA
    o retorno de grava_o_rmd para imprimir os caminhos. Um stub que devolvesse None
    quebraria o pipeline dentro do proprio teste que mede a ordem das etapas.
    """
    alvos = [
        (parse_leiloes, "gravar"),
        (parse_rmd, "gravar_tudo"),
        (parse_bloomberg, "gravar"),
        (dv, "gravar_painel"),
        (dv, "gravar_decay"),
        (dv, "gravar_resultado"),
        (figuras, "gravar_todas"),
    ]
    # O dashboard tambem: sem este stub, SEIS dos nove testes deste arquivo geravam
    # os 37 SVGs de verdade -- 15 s cada, 91 s no arquivo -- e sobrescreviam
    # data/processed/dashboard.html a cada execucao. Pior, uma falha na geracao
    # pintava de vermelho o teste de rede, que nao tem nada com isso.
    from tesouro.graficos import dashboard
    alvos.append((dashboard, "grava_o_rmd"))
    # E o DV por leilao, que entrou com a entrega 3 e roda antes do dashboard.
    from tesouro import leiloes_dv
    alvos.append((leiloes_dv, "gravar"))
    from tesouro.graficos import painel_emissoes
    alvos.append((painel_emissoes, "grava_todas"))
    # E A PAGINA RAPIDA. Faltava aqui, e nenhum teste via: 18 testes deste
    # arquivo rodam o modo leiloes sem stub proprio, chamavam a funcao de
    # VERDADE e sobrescreviam data/processed/emissoes.html -- a pagina
    # publicada. Achado em 24/09/2026 quando ela perguntou onde via a saida da
    # fase rapida: o arquivo tinha o carimbo da ultima rodada de TESTE, e nao
    # do ultimo pipeline. Custava ~6 s por teste, alem do estrago.
    alvos.append((painel_emissoes, "grava_rapida"))
    # E a agenda, que entrou em 20/08/2026. Sem o stub ela iria a REDE buscar o
    # calendario -- e ha um teste neste arquivo que bloqueia socket de proposito.
    from tesouro.graficos import painel_agenda
    alvos.append((painel_agenda, "grava"))
    # E a pagina do PAF, que entrou em 24/08/2026. Sem o stub ela geraria as duas
    # tabelas de verdade a cada teste deste arquivo, e sobrescreveria
    # data/processed/paf.html. QUE ARGUMENTO ela recebe e assunto do teste logo
    # abaixo, que poe um stub proprio por cima deste.
    from tesouro.graficos import painel_paf
    alvos.append((painel_paf, "grava"))
    # E O RESULTADO DO DIA, que entrou no pipeline em 09/09/2026. Ele vai a
    # API do Tesouro, e o stub mora AQUI -- e nao em _stub_coletas -- porque
    # tres testes deste arquivo montam a coleta a mao e nao chamam aquele
    # auxiliar. Sem isto eles passaram a ir a rede de verdade: 5 a 6 segundos
    # cada, e a suite so passando com a API no ar. Medido ao ligar.
    from tesouro import leilao_do_dia
    alvos.append((leilao_do_dia, "rodar"))
    # E O EDITAL DO DIA, que entrou na coleta em 24/09/2026. Mesma natureza do
    # rodar -- vai a API -- e por isso mora no mesmo lugar, e nao em
    # _stub_coletas: os tres testes que montam a coleta a mao nao chamam aquele
    # auxiliar. Sem isto eles iriam a rede e gravariam leiloes_recentes.csv.
    alvos.append((leilao_do_dia, "do_edital"))

    # E A GUARDA DO CALENDARIO, que entrou na coleta em 20/10/2026. TERCEIRA
    # vez que este arquivo vive a mesma historia -- ver os dois comentarios
    # acima. Sem este stub, os tres testes que chamam pipeline.main([]) iam a
    # API e gravavam data/raw/leiloes_api/calendario-AAAA-MM-DD.json de
    # VERDADE: achado em 22/10/2026, 10.847 bytes na pasta dela, e a suite
    # passando a depender da API estar no ar. data/raw e imutavel por
    # invariante.
    #
    # ELE DEVOLVE DUPLA, e nao lista vazia como os outros: o pipeline faz
    # 'caminho, registros_cal = _api.guardar(...)', e desempacotar [] estoura.
    from tesouro import api_leiloes as _api_leiloes

    def guardar_sem_rede(nome, *args, **kwargs):
        if chamadas is not None:
            chamadas.append("tesouro.api_leiloes.guardar")
        return pathlib.Path("nao-gravado-%s.json" % nome), []

    monkeypatch.setattr(_api_leiloes, "guardar", guardar_sem_rede)

    # E O DOLAR DO DIA, que entrou na coleta em 27/10/2026. QUARTA vez que este
    # arquivo vive a mesma historia -- ver os tres comentarios acima. Sem este
    # stub os testes que chamam pipeline.main([]) iriam ao Banco Central e
    # gravariam data/raw/cambio/dolar-AAAA-MM-DD.json de VERDADE.
    #
    # ELE DEVOLVE DUPLA (caminho, registro), e o registro precisa ter 'fonte',
    # 'taxa' e 'data_da_cotacao': o pipeline imprime os tres, e um dicionario
    # vazio estouraria no KeyError em vez de no stub ausente.
    from tesouro import fetch_cambio as _fetch_cambio

    def dolar_sem_rede(*args, **kwargs):
        if chamadas is not None:
            chamadas.append("tesouro.fetch_cambio.guardar")
        return (pathlib.Path("nao-gravado-dolar.json"),
                {"fonte": "PTAX", "taxa": 5.0, "data_da_cotacao": "2026-01-01"})

    monkeypatch.setattr(_fetch_cambio, "guardar", dolar_sem_rede)

    for modulo, nome in alvos:
        def stub(*args, _nome=f"{modulo.__name__}.{nome}", **kwargs):
            if chamadas is not None:
                chamadas.append(_nome)
            # LISTA VAZIA, e nao None: o pipeline itera o retorno de
            # dashboard.grava_o_rmd para imprimir os caminhos das duas paginas, e
            # None quebraria o proprio teste que mede a ordem das etapas.
            return []
        monkeypatch.setattr(modulo, nome, stub)


# ---------------------------------------------------------------------------
# --sem-coleta nao pode tocar rede -- restricao dura do ambiente do banco
# (os parsers so leem arquivo que alguem colocou a mao em data/raw/).
# Bloqueamos socket.socket e socket.getaddrinfo (qualquer tentativa de
# rede, TCP ou resolucao de nome, levanta) e rodamos o pipeline de
# verdade com --sem-coleta -- mesmo metodo usado na revisao da Tarefa 10.
# ---------------------------------------------------------------------------

def test_sem_coleta_nunca_toca_rede(monkeypatch):
    _stub_gravacoes(monkeypatch)

    def rede_proibida(*args, **kwargs):
        raise AssertionError(
            "--sem-coleta tentou acessar a rede (socket/getaddrinfo "
            "chamado); os coletores so podem rodar quando --sem-coleta "
            "NAO e passado"
        )

    monkeypatch.setattr(socket, "socket", rede_proibida)
    monkeypatch.setattr(socket, "getaddrinfo", rede_proibida)

    codigo = pipeline.main(["--sem-coleta"])
    assert codigo == 0


def test_sem_coleta_manda_a_pagina_do_PAF_estimar_o_calendario(monkeypatch):
    """Com a rede proibida, o pipeline tem de pedir a pagina em modo offline.

    Nao basta o stub de _stub_gravacoes: ele deixa QUALQUER argumento passar, e o
    teste de rede so pega quem chama socket -- com o gravador stubado, ninguem
    chama. Entao o pipeline poderia voltar a passar `registros=None` e os dois
    testes seguiriam verdes, ate alguem rodar --sem-coleta de verdade e a pagina
    ir a rede. Este aqui olha o argumento.
    """
    from tesouro.graficos import painel_paf

    _stub_gravacoes(monkeypatch)
    recebido = {}

    def espia(*args, **kwargs):
        recebido.update(kwargs)
        return []

    monkeypatch.setattr(painel_paf, "grava", espia)

    assert pipeline.main(["--sem-coleta"]) == 0
    assert recebido.get("registros") == [], (
        "com --sem-coleta a pagina do PAF tem de receber registros=[], para "
        "estimar o calendario em vez de baixa-lo")


def test_sem_coleta_nao_importa_nenhum_coletor_no_topo_do_modulo():
    # Complementa o teste de rede com uma checagem estrutural, barata,
    # no molde de tests/test_fetch_bloomberg.py::
    # test_nao_importa_blpapi_no_topo: nenhum dos tres coletores pode
    # aparecer num import de NIVEL DE MODULO em pipeline.py -- eles so
    # podem ser importados dentro de main(), dentro do bloco "if not
    # opcoes.sem_coleta". Um import de coletor promovido ao topo do
    # modulo rodaria (e tentaria tocar rede, no caso do fetch_bloomberg,
    # abrir sessao do terminal) so por "import tesouro.pipeline", mesmo
    # com --sem-coleta.
    import ast
    import pathlib
    caminho = pathlib.Path(pipeline.__file__)
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    coletores = ("fetch_leiloes", "fetch_rmd", "fetch_bloomberg")
    for no in arvore.body:                      # so o nivel de modulo
        if isinstance(no, (ast.Import, ast.ImportFrom)):
            nomes = [a.name for a in no.names] + [getattr(no, "module", "") or ""]
            assert not any(c in n for c in coletores for n in nomes), (
                f"{no.lineno}: coletor importado no topo do modulo -- "
                f"deveria estar dentro de main(), no bloco 'if not "
                f"opcoes.sem_coleta'"
            )


# ---------------------------------------------------------------------------
# Contrato: as DEZ etapas de gravacao rodam, e nesta ordem -- e o que
# produz os 22 CSVs (17 da camada de dados + taxa_por_papel, vna,
# dv_por_papel, decay_por_papel, resultado_mensal) mais as figuras. A
# contagem exata de linhas/CSVs foi conferida a mao contra o dado real
# (ver task-10-report.md); aqui o que se trava e a fiacao -- cada etapa e
# chamada exatamente uma vez, na ordem que uma depende da anterior (dv
# le taxa_por_papel/vna, que so existem depois de parse_bloomberg.gravar;
# figuras le dv_por_papel/decay_por_papel/resultado_mensal, que so
# existem depois de dv.gravar_*; e o dashboard le os 22 CSVs, entao vem
# por ultimo).
# ---------------------------------------------------------------------------

def test_pipeline_grava_as_etapas_na_ordem_certa(monkeypatch):
    chamadas = []
    _stub_gravacoes(monkeypatch, chamadas)

    codigo = pipeline.main(["--sem-coleta"])

    assert codigo == 0
    assert chamadas == [
        "tesouro.parse_leiloes.gravar",
        "tesouro.parse_rmd.gravar_tudo",
        "tesouro.parse_bloomberg.gravar",
        "tesouro.dv.gravar_painel",
        "tesouro.dv.gravar_decay",
        "tesouro.dv.gravar_resultado",
        "tesouro.figuras.gravar_todas",
        "tesouro.leiloes_dv.gravar",
        "tesouro.graficos.dashboard.grava_o_rmd",
        "tesouro.graficos.painel_emissoes.grava_todas",
        "tesouro.graficos.painel_paf.grava",
        "tesouro.graficos.painel_agenda.grava",
    ]


# ---------------------------------------------------------------------------
# O try/except da coleta da Bloomberg: precisa distinguir "painel ja em
# dia" (RuntimeError, rotina) de falha de verdade (qualquer outra
# excecao) -- achado da revisao da Tarefa 10, em que um "except
# Exception" generico fundia os dois sob a mesma linha neutra "pulada" e
# o pipeline sempre saia com codigo 0.
# ---------------------------------------------------------------------------

def test_coleta_sem_novidade_nao_e_tratada_como_falha(monkeypatch, capsys):
    _stub_gravacoes(monkeypatch)
    monkeypatch.setattr(fetch_leiloes, "baixar", _sem_efeito)
    monkeypatch.setattr(fetch_rmd, "baixar", _sem_efeito)

    def nada_novo(*args, **kwargs):
        raise RuntimeError("nada novo a coletar: painel ja coberto")

    monkeypatch.setattr(fetch_bloomberg, "baixar", nada_novo)

    codigo = pipeline.main([])
    saida = capsys.readouterr().out

    assert codigo == 0
    # A AGULHA E O ANUNCIO, e nao a palavra: desde 02/10/2026 o
    # cabecalho da rodada tambem cita "concluido." para dizer a ela o
    # que procurar. O anuncio de sucesso e impresso com quebra de linha
    # antes; a mencao do cabecalho vem depois de uma apostrofe.
    assert "\nconcluido." in saida
    assert "ATENCAO" not in saida
    assert "nada novo a coletar" in saida


def test_coleta_com_falha_real_fica_marcada_e_derruba_o_codigo_de_saida(monkeypatch, capsys):
    _stub_gravacoes(monkeypatch)
    monkeypatch.setattr(fetch_leiloes, "baixar", _sem_efeito)
    monkeypatch.setattr(fetch_rmd, "baixar", _sem_efeito)

    def sessao_recusada(*args, **kwargs):
        raise ConnectionError("sessao do terminal Bloomberg recusada")

    monkeypatch.setattr(fetch_bloomberg, "baixar", sessao_recusada)

    codigo = pipeline.main([])
    saida = capsys.readouterr().out

    # Falha de verdade: codigo de saida diferente de zero, prefixo bem
    # visivel, e o aviso REPETIDO perto do fim do log (nao so uma linha
    # no topo que se perde antes de "leiloes"/"rmd"/etc.).
    assert codigo != 0
    assert "ATENCAO" in saida
    assert "sessao do terminal Bloomberg recusada" in saida
    # A AGULHA E O ANUNCIO, e nao a palavra: desde 02/10/2026 o
    # cabecalho da rodada tambem cita "concluido." para dizer a ela o
    # que procurar. O anuncio de sucesso e impresso com quebra de linha
    # antes; a mencao do cabecalho vem depois de uma apostrofe.
    assert "\nconcluido." not in saida
    # A ultima parte do log repete o aviso. O MARCO MUDOU em 02/10/2026: o
    # titulo "--- figuras ---" foi apagado quando as fases passaram a se
    # anunciar com hora e aquele texto virou duplicata. A linha de fase e o
    # marco agora -- e o assunto deste teste nunca foi o texto do marco, foi o
    # aviso aparecer PERTO DO FIM em vez de so no topo, onde se perde.
    marco = saida.index("desenhando as figuras do RMD")
    assert "ATENCAO" in saida[marco:]


def test_coleta_com_blpapi_ausente_tambem_conta_como_falha_real(monkeypatch, capsys):
    # Um ModuleNotFoundError (blpapi nao instalado na maquina) tem que
    # cair no MESMO ramo de falha real que ConnectionError -- e nao no
    # ramo benigno do RuntimeError, so porque as duas sao "erro".
    _stub_gravacoes(monkeypatch)
    monkeypatch.setattr(fetch_leiloes, "baixar", _sem_efeito)
    monkeypatch.setattr(fetch_rmd, "baixar", _sem_efeito)

    def sem_blpapi(*args, **kwargs):
        raise ModuleNotFoundError("No module named 'blpapi'")

    monkeypatch.setattr(fetch_bloomberg, "baixar", sem_blpapi)

    codigo = pipeline.main([])
    saida = capsys.readouterr().out

    assert codigo != 0
    assert "ATENCAO" in saida


def test_import_do_fetch_bloomberg_fica_fora_do_sem_coleta(monkeypatch):
    # --sem-coleta pula a coleta inteira, inclusive a CHAMADA de
    # fetch_bloomberg.baixar. Se o pipeline chamasse baixar() mesmo com
    # --sem-coleta, este stub levantaria e o teste falharia.
    def nao_deveria_ser_chamado(*args, **kwargs):
        raise AssertionError("fetch_bloomberg.baixar chamado com --sem-coleta")

    monkeypatch.setattr(fetch_bloomberg, "baixar", nao_deveria_ser_chamado)
    _stub_gravacoes(monkeypatch)
    codigo = pipeline.main(["--sem-coleta"])
    assert codigo == 0


def test_o_pipeline_grava_o_dashboard_depois_das_figuras(monkeypatch):
    # Os graficos leem os CSVs que as etapas anteriores acabaram de escrever:
    # gerar o dashboard antes produz um HTML com o dado do mes passado.
    from tesouro.graficos import dashboard

    chamadas = []
    _stub_gravacoes(monkeypatch, chamadas)
    def marca(*a, **k):
        chamadas.append("dashboard.grava_o_rmd")
        return []

    monkeypatch.setattr(dashboard, "grava_o_rmd", marca)

    assert pipeline.main(["--sem-coleta"]) == 0
    assert "dashboard.grava_o_rmd" in chamadas
    # O _stub_gravacoes que ja existe no arquivo registra o nome QUALIFICADO --
    # "tesouro.figuras.gravar_todas", nao "gravar_todas".
    assert (chamadas.index("dashboard.grava_o_rmd")
            > chamadas.index("tesouro.figuras.gravar_todas"))


def test_falha_do_dashboard_entra_nas_falhas_e_muda_o_codigo_de_saida(monkeypatch,
                                                                     capsys):
    # O paf.bandas levanta de proposito quando a referencia esta quebrada. Isso
    # tem de aparecer como falha real, nao sumir no meio do log.
    from tesouro.graficos import dashboard

    _stub_gravacoes(monkeypatch)

    def _explode(*args, **kwargs):
        raise ValueError("paf_bandas.csv esta invalido")

    monkeypatch.setattr(dashboard, "grava_o_rmd", _explode)

    assert pipeline.main(["--sem-coleta"]) == 1
    saida = capsys.readouterr().out
    assert "dashboard" in saida.lower()
    assert "paf_bandas.csv" in saida


# ---------------------------------------------------------------------------
# OS QUATRO MODOS DE ATUALIZACAO, pedido dela em 08/09/2026.
#
# O pipeline era tudo-ou-nada: coletava as tres fontes e regravava as sete
# paginas, ~30 minutos, mesmo para acrescentar um leilao. Os modos existem
# porque as fontes tem cadencias diferentes -- o RMD e mensal, o leilao e de
# terca e quinta, e a banda do PAF muda quando o Tesouro revisa.
#
# A PROPRIEDADE QUE MAIS IMPORTA E A DO MODO LEILOES: ele nao pode tocar na
# Bloomberg. O terminal so existe na maquina da mesa e fica desligado quase
# sempre; um pipeline que tenta a Bloomberg para acrescentar um leilao ou
# demora ou falha, e nos dois casos por nada.
# ---------------------------------------------------------------------------

def _stub_coletas(monkeypatch, chamadas):
    """Stub das tres coletas, registrando quem foi chamado."""
    from tesouro import fetch_bloomberg, fetch_leiloes, fetch_rmd

    for modulo in (fetch_leiloes, fetch_rmd, fetch_bloomberg):
        def stub(*args, _nome=modulo.__name__, **kwargs):
            chamadas.append(_nome + ".baixar")
        monkeypatch.setattr(modulo, "baixar", stub)


def _rodar(monkeypatch, argumentos):
    chamadas = []
    _stub_gravacoes(monkeypatch, chamadas)
    _stub_coletas(monkeypatch, chamadas)
    from tesouro import valida_referencia

    def valida(*args, **kwargs):
        chamadas.append("tesouro.valida_referencia.main")
        return 0
    monkeypatch.setattr(valida_referencia, "main", valida)
    codigo = pipeline.main(argumentos)
    return codigo, chamadas


def test_o_modo_LEILOES_nao_toca_na_bloomberg_nem_no_rmd(monkeypatch):
    """A propriedade de seguranca do modo, e a razao de ele existir.

    A Bloomberg so responde na maquina da mesa com o terminal aberto. Puxa-la
    para acrescentar um leilao ou demora ou falha, e o leilao nao depende dela.
    """
    codigo, chamadas = _rodar(monkeypatch, ["--modo", "leiloes"])
    assert codigo == 0
    assert "tesouro.fetch_bloomberg.baixar" not in chamadas
    assert "tesouro.fetch_rmd.baixar" not in chamadas
    assert "tesouro.parse_rmd.gravar_tudo" not in chamadas
    assert "tesouro.fetch_leiloes.baixar" in chamadas


def test_o_modo_LEILOES_regrava_so_as_paginas_que_um_leilao_muda(monkeypatch):
    """O dashboard sai do RMD e nao muda com leilao -- regrava-lo seria gastar
    a maior parte do tempo do pipeline para reescrever bytes iguais."""
    _, chamadas = _rodar(monkeypatch, ["--modo", "leiloes"])
    assert "tesouro.graficos.dashboard.grava_o_rmd" not in chamadas
    for pagina in ("tesouro.graficos.painel_paf.grava",
                   "tesouro.graficos.painel_emissoes.grava_todas",
                   "tesouro.graficos.painel_agenda.grava"):
        assert pagina in chamadas, pagina


def test_o_modo_RMD_puxa_o_rmd_e_regrava_TODAS_as_paginas(monkeypatch):
    """O RMD novo move a base de tudo -- inclusive a rolagem da pagina do PAF.

    Por isso este modo e o unico que regrava as sete paginas: nao ha pagina
    deste projeto que nao dependa do RMD por algum caminho.
    """
    _, chamadas = _rodar(monkeypatch,
                         ["--modo", "rmd", "--ano", "2026", "--mes", "8"])
    assert "tesouro.fetch_rmd.baixar" in chamadas
    assert "tesouro.fetch_leiloes.baixar" not in chamadas
    assert "tesouro.fetch_bloomberg.baixar" not in chamadas
    for pagina in ("tesouro.graficos.dashboard.grava_o_rmd",
                   "tesouro.graficos.painel_paf.grava",
                   "tesouro.graficos.painel_emissoes.grava_todas",
                   "tesouro.graficos.painel_agenda.grava"):
        assert pagina in chamadas, pagina


def test_o_modo_PAF_NAO_COLETA_NADA(monkeypatch):
    """A banda do PAF entra a mao: ela le o informe e edita o CSV.

    Nao ha nada para baixar, e o modo tem de dizer isso com o comportamento --
    zero coleta -- e nao so com um texto no manual.
    """
    _, chamadas = _rodar(monkeypatch, ["--modo", "paf"])
    assert not [c for c in chamadas if c.endswith(".baixar")], chamadas


def test_o_modo_PAF_confere_a_referencia_ANTES_de_desenhar(monkeypatch):
    """Banda quebrada nao pode virar grafico com banda errada -- e a regra da
    spec, secao 6. Aqui ela vira ordem de execucao."""
    _, chamadas = _rodar(monkeypatch, ["--modo", "paf"])
    assert "tesouro.valida_referencia.main" in chamadas
    assert (chamadas.index("tesouro.valida_referencia.main")
            < chamadas.index("tesouro.graficos.painel_paf.grava"))


def test_o_modo_PAF_para_quando_a_referencia_esta_quebrada(monkeypatch):
    """E para de verdade: nao regrava pagina nenhuma e sai com codigo 1."""
    chamadas = []
    _stub_gravacoes(monkeypatch, chamadas)
    _stub_coletas(monkeypatch, chamadas)
    from tesouro import valida_referencia

    def reprovado(*args, **kwargs):
        chamadas.append("tesouro.valida_referencia.main")
        return 1
    monkeypatch.setattr(valida_referencia, "main", reprovado)

    codigo = pipeline.main(["--modo", "paf"])
    assert codigo == 1
    assert "tesouro.graficos.painel_paf.grava" not in chamadas
    assert "tesouro.graficos.dashboard.grava_o_rmd" not in chamadas


def test_o_modo_TUDO_faz_o_que_o_pipeline_SEMPRE_fez(monkeypatch):
    """Compatibilidade: o modo 'tudo' e o pipeline antigo, etapa por etapa."""
    _, chamadas = _rodar(monkeypatch, ["--modo", "tudo"])
    # SO OS PASSOS DE GERACAO. Os de coleta saem daqui -- o assunto deste teste
    # e a ordem em que as paginas sao produzidas, e nao o que se busca antes.
    # do_edital entrou na coleta em 24/09/2026 e sai pelo mesmo motivo que rodar.
    # E a guarda do calendario entrou em 20/10/2026, pelo mesmo motivo ainda:
    # ela BUSCA, e este teste e sobre a ordem em que as paginas saem. O sufixo
    # ".guardar" e especifico -- nenhuma etapa de geracao se chama assim (elas
    # sao gravar, gravar_tudo, gravar_painel).
    COLETA = (".baixar", ".rodar", ".do_edital", ".guardar")
    geracao = [c for c in chamadas
               if not c.endswith(COLETA)
               and c != "tesouro.valida_referencia.main"]
    assert geracao == [
        "tesouro.parse_leiloes.gravar",
        "tesouro.parse_rmd.gravar_tudo",
        "tesouro.parse_bloomberg.gravar",
        "tesouro.dv.gravar_painel",
        "tesouro.dv.gravar_decay",
        "tesouro.dv.gravar_resultado",
        "tesouro.figuras.gravar_todas",
        "tesouro.leiloes_dv.gravar",
        "tesouro.graficos.dashboard.grava_o_rmd",
        "tesouro.graficos.painel_emissoes.grava_todas",
        "tesouro.graficos.painel_paf.grava",
        "tesouro.graficos.painel_agenda.grava",
    ]


def test_SEM_modo_o_pipeline_se_comporta_como_antes(monkeypatch):
    """Quem ja tem o comando na cabeca ou num agendador nao pode ser quebrado.

    'python -m tesouro.pipeline --sem-coleta' continua valendo e continua
    fazendo tudo.
    """
    _, com_modo = _rodar(monkeypatch, ["--modo", "tudo", "--sem-coleta"])
    _, sem_modo = _rodar(monkeypatch, ["--sem-coleta"])
    assert sem_modo == com_modo


def test_o_modo_LEILOES_respeita_o_sem_coleta(monkeypatch):
    """--sem-coleta continua sendo a promessa mais forte: com ele, nenhum modo
    toca a rede."""
    _, chamadas = _rodar(monkeypatch, ["--modo", "leiloes", "--sem-coleta"])
    assert not [c for c in chamadas if c.endswith(".baixar")], chamadas
    assert "tesouro.graficos.painel_paf.grava" in chamadas


def test_o_modo_RMD_NAO_baixa_nada_quando_ela_escolhe_continuar(monkeypatch):
    """O menu virou continuar/atualizar em 02/10/2026, por pedido dela.

    ANTES este teste cobrava o contrario: perguntar ano e mes e CHAMAR o
    download. Ela trocou o desenho -- "se eu escolho 1 rmd, ai vc me diz, o
    ultimo rmd que vc salvou e da data tal. quer atualizar ou continuar?" -- e
    o download saiu do menu, porque nesta maquina ele nao funciona: o site
    trava no certificado do SERPRO.

    Entao o que se cobra aqui mudou de "baixa" para "NAO baixa, e usa o que
    esta na pasta". A capacidade de baixar nao foi perdida: continua nas
    bandeiras, e o teste abaixo a cobra.
    """
    chamadas = []
    _stub_gravacoes(monkeypatch, chamadas)
    _stub_coletas(monkeypatch, chamadas)
    pedidos = []

    def baixar(ano, mes):
        pedidos.append((ano, mes))
    from tesouro import fetch_rmd
    monkeypatch.setattr(fetch_rmd, "baixar", baixar)
    monkeypatch.setattr(pipeline, "_e_interativo", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *a: "c")

    codigo = pipeline.main(["--modo", "rmd"])
    assert codigo == 0
    assert pedidos == [], "escolher continuar nao pode baixar nada"


def test_as_BANDEIRAS_continuam_baixando_o_RMD(monkeypatch):
    """A capacidade de baixar nao morreu com a troca do menu.

    Numa maquina onde o certificado nao atrapalha -- a do banco pode ser --
    --ano/--mes continua puxando o anexo, sem menu e sem ninguem do outro lado.
    Sem este teste, tirar o download do menu teria aposentado o caminho em
    silencio.
    """
    chamadas = []
    _stub_gravacoes(monkeypatch, chamadas)
    _stub_coletas(monkeypatch, chamadas)
    pedidos = []

    def baixar(ano, mes):
        pedidos.append((ano, mes))
    from tesouro import fetch_rmd
    monkeypatch.setattr(fetch_rmd, "baixar", baixar)
    # NAO interativo: e assim que um agendador chama.
    monkeypatch.setattr(pipeline, "_e_interativo", lambda: False)

    codigo = pipeline.main(["--modo", "rmd", "--ano", "2026", "--mes", "8"])
    assert codigo == 0
    assert pedidos == [(2026, 8)], pedidos


def test_o_modo_RMD_NAO_pergunta_quando_nao_ha_ninguem(monkeypatch):
    """Num agendador nao ha quem responda, e um programa que espera input ali
    trava calado. Sem terminal, o modo segue com o anexo que ja esta em disco
    -- e diz isso."""
    chamadas = []
    _stub_gravacoes(monkeypatch, chamadas)
    _stub_coletas(monkeypatch, chamadas)
    monkeypatch.setattr(pipeline, "_e_interativo", lambda: False)

    def nao_pergunte(*a, **k):
        raise AssertionError("perguntou sem ter a quem")
    monkeypatch.setattr("builtins.input", nao_pergunte)

    codigo = pipeline.main(["--modo", "rmd"])
    assert codigo == 0


def test_o_menu_aceita_o_NUMERO_e_o_NOME_do_modo():
    """Ela vai digitar um dos dois, e nenhum e mais certo que o outro."""
    for resposta, esperado in [("1", "rmd"), ("2", "leiloes"), ("3", "paf"),
                               ("4", "tudo"), ("leiloes", "leiloes"),
                               ("PAF", "paf"), ("  tudo  ", "tudo")]:
        escolhido = pipeline.escolher_modo_no_menu(
            entrada=lambda *a, _r=resposta: _r, saida=lambda *a: None)
        assert escolhido == esperado, resposta


def test_o_menu_INSISTE_em_vez_de_escolher_por_conta_propria():
    """Uma resposta que nao serve nao pode virar "tudo" em silencio: os modos
    fazem coisas bem diferentes, e o mais caro deles leva meia hora."""
    respostas = iter(["9", "banana", "", "2"])
    ditas = []
    escolhido = pipeline.escolher_modo_no_menu(
        entrada=lambda *a: next(respostas), saida=ditas.append)
    assert escolhido == "leiloes"
    assert sum("nao entendi" in d for d in ditas) == 3


def test_o_menu_do_RMD_aceita_seguir_com_o_anexo_em_disco():
    """Enter em branco e resposta valida: as vezes o anexo ja foi baixado a
    mao, e ela so quer reprocessar."""
    assert pipeline.escolher_rmd_no_menu(
        entrada=lambda *a: "", saida=lambda *a: None) is None
    respostas = iter(["2026", ""])
    assert pipeline.escolher_rmd_no_menu(
        entrada=lambda *a: next(respostas), saida=lambda *a: None) is None


def test_a_BANDEIRA_recusa_mes_impossivel(capsys):
    """13 nao e mes, e dizer isso em vez de estourar.

    ESTE TESTE MUDOU DE LUGAR em 06/10/2026, junto com a guarda. Antes o menu
    perguntava o mes e recusava 13 com "1 a 12"; o menu dela nao pergunta mais
    mes, e a guarda ficou so no --mes.

    E ali ela tinha DEGRADADO: medido, `--modo rmd --mes 13` estourava
    "ValueError: mes fora do intervalo 1..12" com traceback, depois de ja ter
    comecado a rodada. Traceback e um jeito confuso de dizer "digitei 13" --
    que e exatamente o que a versao antiga deste teste dizia.

    Agora o argparse recusa ANTES de comecar, e com o mes valido no texto.
    """
    import pytest

    with pytest.raises(SystemExit) as saiu:
        pipeline.main(["--modo", "rmd", "--ano", "2026", "--mes", "13"])
    assert saiu.value.code != 0
    erro = capsys.readouterr().err
    assert "--mes" in erro
    assert "13" in erro


def test_a_coleta_de_leiloes_PUXA_O_RESULTADO_DO_DIA_e_nao_so_a_planilha(
        monkeypatch):
    """O buraco que o modo 'leiloes' destapou em 09/09/2026.

    O pipeline chamava fetch_leiloes.baixar(), que busca a PLANILHA HISTORICA
    do Tesouro -- e essa planilha trava no certificado do SERPRO e nao
    atualiza. O leilao novo so entra por leilao_do_dia.rodar(), que vai a API e
    grava leiloes_recentes.csv, e o pipeline NUNCA chamava isso.

    Medido: rodei "--modo leiloes" em 09/09 com a API oferecendo leiloes ate
    08/09, e o pipeline disse "concluido" com a pagina ainda em 25/08. Rodada
    verde que nao atualizou nada.

    Vale para o modo 'tudo' tambem, que tinha o mesmo buraco desde sempre.
    """
    for modo in ("leiloes", "tudo"):
        chamadas = []
        _stub_gravacoes(monkeypatch, chamadas)
        _stub_coletas(monkeypatch, chamadas)
        from tesouro import leilao_do_dia

        def rodar(*args, **kwargs):
            chamadas.append("tesouro.leilao_do_dia.rodar")
        monkeypatch.setattr(leilao_do_dia, "rodar", rodar)

        pipeline.main(["--modo", modo])
        assert "tesouro.leilao_do_dia.rodar" in chamadas, modo


def test_o_resultado_do_dia_NAO_e_buscado_com_sem_coleta(monkeypatch):
    """--sem-coleta continua prometendo nao tocar a rede, e leilao_do_dia e
    rede."""
    chamadas = []
    _stub_gravacoes(monkeypatch, chamadas)
    _stub_coletas(monkeypatch, chamadas)
    from tesouro import leilao_do_dia

    def nao_deveria(*args, **kwargs):
        raise AssertionError("foi a rede com --sem-coleta")
    monkeypatch.setattr(leilao_do_dia, "rodar", nao_deveria)

    assert pipeline.main(["--modo", "leiloes", "--sem-coleta"]) == 0


def test_a_falha_do_resultado_do_dia_NAO_derruba_a_rodada(monkeypatch):
    """A API do Tesouro cai, e quando cai a planilha ainda serve.

    Mas nao pode passar em silencio: quem le o log tem de ver que o leilao de
    hoje pode estar faltando. Mesma regra da Bloomberg e da agenda.
    """
    chamadas = []
    _stub_gravacoes(monkeypatch, chamadas)
    _stub_coletas(monkeypatch, chamadas)
    from tesouro import leilao_do_dia

    def caiu(*args, **kwargs):
        raise ConnectionError("apiapex fora do ar")
    monkeypatch.setattr(leilao_do_dia, "rodar", caiu)

    codigo = pipeline.main(["--modo", "leiloes"])
    assert codigo == 1, "falha de coleta tem de mudar o codigo de saida"
    assert "tesouro.graficos.painel_paf.grava" in chamadas, (
        "as paginas continuam sendo regravadas com o dado que ha")


def test_o_pipeline_NAO_APAGA_o_dv_provisorio_que_acabou_de_gravar(monkeypatch):
    """Medido em 09/09/2026, rodando o modo leiloes de verdade:

        gravado: dv_emitido_por_leilao.csv (14398 linhas)   <- leilao_do_dia
        gravado: dv_emitido_por_leilao.csv (14338 linhas)   <- o pipeline

    Sessenta linhas a menos: exatamente as que tinham acabado de entrar.
    leilao_do_dia grava com ate_o_estagio="ofertado", que inclui o leilao de
    hoje; leiloes_dv.gravar() sozinho usa "planilha", que so tem o que o
    Tesouro ja publicou -- e a planilha trava no certificado do SERPRO.

    As paginas de emissao desenham o provisorio com HACHURA; regravar por cima
    sem ele nao quebra nada em voz alta, so faz o leilao de hoje sumir do
    grafico que existe para mostra-lo.

    O DEFEITO E MAIS VELHO QUE O MODO: quem rodasse leilao_do_dia e depois o
    pipeline ja perdia as linhas. Ligar os dois no mesmo comando tornou o caso
    deterministico, e por isso visivel.
    """
    chamadas = []
    _stub_gravacoes(monkeypatch, chamadas)
    _stub_coletas(monkeypatch, chamadas)
    from tesouro import leilao_do_dia
    monkeypatch.setattr(leilao_do_dia, "rodar",
                        lambda *a, **k: chamadas.append(
                            "tesouro.leilao_do_dia.rodar") or 60)

    pipeline.main(["--modo", "leiloes"])
    assert "tesouro.leiloes_dv.gravar" not in chamadas, (
        "o pipeline regravou por cima do DV que ja tinha o leilao de hoje")


def test_o_pipeline_REGRAVA_o_dv_no_MESMO_estagio_de_leilao_do_dia(monkeypatch):
    """O outro lado, e o que faltava para a correcao valer na rodada seguinte.

    Sem novidade, leilao_do_dia devolve zero e nao grava o DV -- entao o
    pipeline precisa grava-lo. Mas gravar com o default "planilha" apagaria de
    novo o provisorio que uma rodada ANTERIOR tinha posto la: o guard sozinho
    adiava o defeito de um dia em vez de corrigi-lo.

    "ofertado" e o estagio que leilao_do_dia usa e o default de
    leiloes_recentes.completo, que devolve so a planilha quando nao ha
    provisorio nenhum. Ou seja: e seguro sempre, e e o unico que nao perde
    linha.
    """
    chamadas = []
    _stub_gravacoes(monkeypatch, chamadas)
    _stub_coletas(monkeypatch, chamadas)
    from tesouro import leilao_do_dia, leiloes_dv
    monkeypatch.setattr(leilao_do_dia, "rodar",
                        lambda *a, **k: chamadas.append(
                            "tesouro.leilao_do_dia.rodar") or 0)
    estagios = []
    monkeypatch.setattr(leiloes_dv, "gravar",
                        lambda ate_o_estagio="planilha", **k:
                        estagios.append(ate_o_estagio))

    pipeline.main(["--modo", "leiloes"])
    assert estagios == ["ofertado"], estagios


def test_o_log_cita_TODAS_as_paginas_de_emissao(monkeypatch, capsys):
    """Pagina gravada em silencio nao da para conferir.

    A do historico entrou em 09/09/2026 e o log so citava as tres combinacoes,
    porque iterava COMBINACOES -- e ela nao esta la. O manual deste projeto
    ensina a conferir o que o log diz que gravou; sem a linha, nao ha o que
    conferir.

    LE A LISTA, e nao uma contagem: se entrar uma quarta combinacao, o teste
    exige a linha dela sozinho.
    """
    from tesouro.graficos import painel_emissoes

    chamadas = []
    _stub_gravacoes(monkeypatch, chamadas)
    _stub_coletas(monkeypatch, chamadas)
    pipeline.main(["--modo", "leiloes", "--sem-coleta"])
    saida = capsys.readouterr().out

    for _, _, arquivo, _ in painel_emissoes.COMBINACOES:
        assert arquivo in saida, arquivo
    assert painel_emissoes.ARQUIVO_HISTORICO in saida, (
        "a pagina do historico foi gravada sem aparecer no log")


# --------------------------------------------------------------------------
# A FASE RAPIDA DO MODO LEILOES, ideia dela em 17/09/2026:
#
#   "talvez possamos rodar primeiro um 'modo rapido' dos leiloes, que roda a
#    janela de 20 leiloes primeiro.. e depois chama o resto. porque ai ja e
#    possivel disparar um email rapido com a janela de 20 leiloes"
#
# MEDIDO antes de desenhar: a emissoes.html com UMA janela leva 6,1 s e sai com
# 1,05 MB; com as cinco leva ~58 s e 7,28 MB. O modo inteiro leva 203 s.
#
# MESMO ARQUIVO, e nao uma pagina nova: a fase 2 substitui a rapida pela
# completa. Quem abrir no meio pega a de uma janela, quem abrir depois pega a
# cheia, e as duas dizem no cabecalho de quando sao.
# --------------------------------------------------------------------------

def test_o_modo_LEILOES_grava_a_emissoes_DUAS_VEZES(monkeypatch):
    """Uma rapida e uma completa -- e a rapida vem primeiro, senao nao serve."""
    chamadas = []
    _stub_gravacoes(monkeypatch, chamadas)
    _stub_coletas(monkeypatch, chamadas)
    from tesouro.graficos import painel_emissoes

    def rapida(*a, **k):
        chamadas.append("tesouro.graficos.painel_emissoes.grava_rapida")
    monkeypatch.setattr(painel_emissoes, "grava_rapida", rapida)

    pipeline.main(["--modo", "leiloes"])
    rap = "tesouro.graficos.painel_emissoes.grava_rapida"
    completa = "tesouro.graficos.painel_emissoes.grava_todas"
    assert rap in chamadas, chamadas
    assert completa in chamadas, chamadas
    assert chamadas.index(rap) < chamadas.index(completa)


def test_a_fase_rapida_vem_ANTES_da_pagina_do_PAF(monkeypatch):
    """A do PAF custa 45 s dos 203. Se a rapida sair depois dela, o e-mail
    espera o que ele existe para nao esperar."""
    chamadas = []
    _stub_gravacoes(monkeypatch, chamadas)
    _stub_coletas(monkeypatch, chamadas)
    from tesouro.graficos import painel_emissoes
    monkeypatch.setattr(painel_emissoes, "grava_rapida",
                        lambda *a, **k: chamadas.append("RAPIDA"))

    pipeline.main(["--modo", "leiloes"])
    assert chamadas.index("RAPIDA") < chamadas.index(
        "tesouro.graficos.painel_paf.grava")


def test_o_modo_TUDO_nao_faz_fase_rapida(monkeypatch):
    """O 'tudo' e o modo de quem nao tem pressa. Fase rapida ali seria gerar a
    mesma pagina tres vezes."""
    chamadas = []
    _stub_gravacoes(monkeypatch, chamadas)
    _stub_coletas(monkeypatch, chamadas)
    from tesouro.graficos import painel_emissoes
    monkeypatch.setattr(painel_emissoes, "grava_rapida",
                        lambda *a, **k: chamadas.append("RAPIDA"))

    pipeline.main(["--modo", "tudo"])
    assert "RAPIDA" not in chamadas, chamadas


def test_o_log_AVISA_que_a_pagina_rapida_esta_pronta(monkeypatch, capsys):
    """O aviso E o produto desta fase: e por ele que ela sabe que pode mandar
    o e-mail. Sem linha achavel no log, a fase rapida nao serve para nada."""
    chamadas = []
    _stub_gravacoes(monkeypatch, chamadas)
    _stub_coletas(monkeypatch, chamadas)
    from tesouro.graficos import painel_emissoes
    monkeypatch.setattr(painel_emissoes, "grava_rapida",
                        lambda *a, **k: __import__("pathlib").Path("x.html"))

    pipeline.main(["--modo", "leiloes"])
    saida = capsys.readouterr().out
    assert "RAPIDA" in saida.upper(), saida[-500:]
    assert "20 leil" in saida, saida[-500:]


def test_todo_modo_que_regrava_o_PAF_tambem_regrava_a_AGENDA(monkeypatch):
    """As duas paginas leem o MESMO calendario publicado, e tem de concordar.

    A pagina do PAF usa o calendario para projetar o fechamento do ano; a agenda
    mostra dia a dia quais leiloes entraram nessa conta e quais sao inferencia
    nossa. Regravar uma sem a outra deixa as duas discordando na tela sem que
    nada avise -- e a agenda e justamente onde se confere a projecao.

    Achado em 24/09/2026: o modo 'paf' refazia a pagina do PAF e nao a agenda.
    Escrito como RELACAO e nao como lista de passos: uma lista fixa so repetiria
    a configuracao, e passaria de novo no dia em que alguem criasse um quinto
    modo com o mesmo buraco.
    """
    from tesouro import pipeline

    modos = [m for m, passos in pipeline.PASSOS_DO_MODO.items()
             if "paf" in passos]
    assert modos, "nenhum modo regrava o PAF -- o teste nao mede nada assim"

    for modo in modos:
        argumentos = ["--modo", modo]
        if modo == "rmd":
            argumentos += ["--ano", "2026", "--mes", "8"]
        _, chamadas = _rodar(monkeypatch, argumentos)
        assert "tesouro.graficos.painel_paf.grava" in chamadas, modo
        assert "tesouro.graficos.painel_agenda.grava" in chamadas, (
            f"o modo {modo!r} regrava a pagina do PAF sem regravar a agenda: "
            f"as duas leem o mesmo calendario e ficariam discordando")


def test_a_coleta_de_leiloes_PUXA_O_EDITAL_e_nao_so_o_resultado(monkeypatch):
    """O buraco que ela destapou em 24/09/2026, ao pedir o modo rapido.

    Saiu a oferta do dia, ainda sem resultado. Rodei o modo leiloes: 185 s,
    codigo 0, pagina rapida gravada -- e a oferta NAO estava nela. O dado dos
    graficos parava em 22/09, com estagios 'planilha' e 'aceito' e ZERO
    'ofertado'. A hachura que marca "resultado ainda nao saiu" nao tinha o que
    hachurar.

    O /editais tinha a oferta -- seis pernas, editais 238 e 239. So que ele era
    lido apenas por entrada_manual, um caminho MANUAL que o pipeline nunca
    chamava e que nem estava no manual.

    O caminho da planilha continua existindo e continua mandando: a taxa que ela
    digita vence a emprestada, pela ordem dos estagios. Este passo garante que a
    oferta APARECA nos dias em que ninguem digitou nada.
    """
    for modo in ("leiloes", "tudo"):
        chamadas = []
        _stub_gravacoes(monkeypatch, chamadas)
        _stub_coletas(monkeypatch, chamadas)
        from tesouro import leilao_do_dia

        monkeypatch.setattr(leilao_do_dia, "rodar",
                            lambda *a, **k: chamadas.append("rodar"))
        monkeypatch.setattr(leilao_do_dia, "do_edital",
                            lambda *a, **k: chamadas.append("do_edital"))

        pipeline.main(["--modo", modo])
        assert "do_edital" in chamadas, (
            f"o modo {modo!r} coleta leilao sem buscar o edital do dia: a "
            f"oferta nao entra, e nao ha o que hachurar")
        # A oferta vem antes do resultado, que e a ordem do dia -- e a ordem dos
        # estagios garante que o aceito substitua o ofertado, nunca o contrario.
        assert chamadas.index("do_edital") < chamadas.index("rodar"), modo


def test_o_EDITAL_tambem_NAO_e_buscado_com_sem_coleta(monkeypatch):
    """--sem-coleta promete nao tocar a rede, e o edital e rede."""
    chamadas = []
    _stub_gravacoes(monkeypatch, chamadas)
    _stub_coletas(monkeypatch, chamadas)
    from tesouro import leilao_do_dia

    def nao_deveria(*args, **kwargs):
        raise AssertionError("foi a rede com --sem-coleta")
    monkeypatch.setattr(leilao_do_dia, "do_edital", nao_deveria)
    monkeypatch.setattr(leilao_do_dia, "rodar", nao_deveria)

    pipeline.main(["--modo", "leiloes", "--sem-coleta"])


def test_a_agenda_fora_do_ar_NAO_derruba_a_rodada(monkeypatch, capsys):
    """Rede caida e rotina, e nao falha: as outras paginas seguem valendo.

    Esta e a metade que ja estava certa. Fica aqui para que o conserto da outra
    metade nao a atropele -- derrubar a rodada toda vez que a API pisca seria
    trocar um problema por outro.
    """
    chamadas = []
    _stub_gravacoes(monkeypatch, chamadas)
    _stub_coletas(monkeypatch, chamadas)
    from tesouro.graficos import painel_agenda

    def sem_rede(*a, **k):
        raise ConnectionError("a API do Tesouro nao respondeu")
    monkeypatch.setattr(painel_agenda, "grava", sem_rede)

    codigo = pipeline.main(["--modo", "leiloes"])
    saida = capsys.readouterr().out

    assert codigo == 0, "API fora do ar nao e falha do projeto"
    assert "AVISO" in saida
    # A AGULHA E O ANUNCIO, e nao a palavra: desde 02/10/2026 o
    # cabecalho da rodada tambem cita "concluido." para dizer a ela o
    # que procurar. O anuncio de sucesso e impresso com quebra de linha
    # antes; a mencao do cabecalho vem depois de uma apostrofe.
    assert "\nconcluido." in saida


def test_a_agenda_QUEBRADA_entra_nas_falhas_e_derruba_o_codigo(monkeypatch,
                                                               capsys):
    """O defeito de 24/09/2026, que ficou semanas invisivel.

    A agenda parou de ser gravada por um erro NOSSO -- 'NaTType does not
    support strftime', um vertice de LFT estreante no calendario. O bloco
    tratava isso igual a "a API nao respondeu": imprimia AVISO no meio do log,
    nao entrava em 'falhas', e a ultima linha da tela dizia 'concluido.' com
    codigo 0. A pagina ficou com o calendario velho e nada acusou.

    E o mesmo padrao que a linha 207 deste arquivo ja descrevia para a
    Bloomberg: um 'except Exception' generico fundindo rotina com falha real.
    A rodada continua -- as outras paginas valem -- mas o FIM da tela tem de
    dizer a verdade.
    """
    chamadas = []
    _stub_gravacoes(monkeypatch, chamadas)
    _stub_coletas(monkeypatch, chamadas)
    from tesouro.graficos import painel_agenda

    def defeito_nosso(*a, **k):
        raise ValueError("NaTType does not support strftime")
    monkeypatch.setattr(painel_agenda, "grava", defeito_nosso)

    codigo = pipeline.main(["--modo", "leiloes"])
    saida = capsys.readouterr().out

    assert codigo == 1, (
        "erro NOSSO na agenda saiu com codigo 0 -- indistinguivel de rodada boa")
    # As outras paginas continuam saindo: o remedio nao pode ser pior que a
    # doenca.
    assert "tesouro.graficos.painel_paf.grava" in chamadas
    # E o FIM da tela diz a verdade, que e onde ela olha.
    assert "concluido com falha" in saida
    assert "NaTType" in saida.split("concluido com falha")[-1], (
        "a falha tem de aparecer no resumo do fim, e nao so cinco linhas acima")


def test_a_rodada_DIZ_QUE_COMECOU_e_marca_cada_fase(monkeypatch, capsys):
    """Ela nao tinha como saber se estava rodando.

    PALAVRAS DELA em 02/10/2026: "como sei que esta rodando? fui checar na
    pagina paf, e nao esta atualizado, entao nao sei se esta rodando, tem que
    ter algum aviso que esta rodando, e um concluido.. onde olho?".

    O pipeline levava minutos imprimindo quase nada -- entre dois cabecalhos
    passavam 60 s de silencio, e silencio de dois minutos e indistinguivel de
    travado. Agora cada fase se anuncia com HORA e tempo decorrido.
    """
    codigo, chamadas = _rodar(monkeypatch, ["--modo", "leiloes"])
    saida = capsys.readouterr().out

    assert codigo == 0
    # COMECOU: a primeira linha util diz que comecou, com hora.
    assert "COMECOU" in saida.upper()
    # CADA FASE se anuncia. Tres que o modo leiloes certamente faz.
    for fase in ("leiloes", "paf", "agenda"):
        assert fase in saida.lower(), fase
    # E o tempo decorrido aparece, para o silencio ter tamanho visivel.
    import re

    assert re.search(r"\d+\s*s\b", saida), "nenhuma marca de tempo na saida"
    # TERMINOU, e de um jeito que nao se confunde com o meio do log.
    assert "concluido" in saida.lower()


def test_cada_fase_e_anunciada_ANTES_de_rodar_e_nao_depois(monkeypatch, capsys):
    # A ordem importa: anunciar depois de terminar deixa o silencio sem
    # explicacao justamente enquanto ele dura.
    chamadas = []
    _stub_gravacoes(monkeypatch, chamadas)
    _stub_coletas(monkeypatch, chamadas)
    from tesouro.graficos import painel_paf

    marcas = []

    def grava(*a, **k):
        marcas.append("rodou o paf")
        return []
    monkeypatch.setattr(painel_paf, "grava", grava)

    pipeline.main(["--modo", "paf"])
    saida = capsys.readouterr().out
    assert "rodou o paf" in marcas
    antes = saida.lower().index("paf")
    assert antes < saida.lower().rindex("concluido")


# ---------------------------------------------------------------------------
# FALTA DE DADO NAO SAI EM TRACEBACK -- achado em 20/10/2026 no teste do clone
# limpo. A frase do projeto ja era boa; ela chegava embrulhada em quinze linhas
# de pilha, e numa maquina nova e a primeira coisa que a pessoa ve.
# ---------------------------------------------------------------------------

def test_falta_de_arquivo_vira_FaltaDado_com_a_fase_no_texto():
    import tesouro.pipeline as pipeline

    def nao_tem():
        raise FileNotFoundError(
            "nenhum .xlsx encontrado em data/raw/rmd; baixe o anexo")

    with pytest.raises(pipeline.FaltaDado) as erro:
        pipeline._executa("lendo o RMD", nao_tem)
    # A FASE E A FRASE ORIGINAL, as duas: sem a fase ninguem sabe onde parou,
    # e sem a frase original ninguem sabe qual arquivo falta.
    assert "lendo o RMD" in str(erro.value)
    assert "data/raw/rmd" in str(erro.value)
    assert "baixe o anexo" in str(erro.value)


def test_outro_erro_qualquer_NAO_e_disfarcado_de_falta_de_dado():
    # Esconder um defeito de codigo sob uma frase amavel e pior que o
    # traceback: ele passaria a parecer instalacao incompleta.
    import tesouro.pipeline as pipeline

    def quebrado():
        raise ZeroDivisionError("defeito de verdade")

    with pytest.raises(ZeroDivisionError):
        pipeline._executa("lendo o RMD", quebrado)


def test_as_fases_de_leitura_passam_por__executa():
    # A guarda de que o conserto nao se perde: as duas fases que uma instalacao
    # nova encontra primeiro continuam embrulhadas.
    import pathlib

    fonte = (pathlib.Path(__file__).resolve().parents[1]
             / "src" / "tesouro" / "pipeline.py").read_text(encoding="utf-8")
    assert '_executa("lendo o RMD", parse_rmd.gravar_tudo)' in fonte
    assert '_executa("lendo os leiloes", parse_leiloes.gravar)' in fonte


# ---------------------------------------------------------------------------
# O FIM DA RODADA DIZ ONDE ESTAO AS PAGINAS -- pergunta dela em 20/10/2026:
# "quando diz 'concluido' ele da os links da onde estao as paginas?". Nao dava:
# os caminhos saiam espalhados pela rodada, e as quatro de emissoes saiam so
# com o nome do arquivo.
# ---------------------------------------------------------------------------

def test_o_fim_lista_as_paginas_da_BARRA_DE_NAVEGACAO(tmp_path, monkeypatch):
    # A LISTA SAI DE dashboard.PAGINAS, a mesma que monta a barra no topo das
    # paginas. Assim o fim da tela nao pode discordar da barra, e quem
    # acrescentar pagina mexe num lugar so.
    import tesouro.pipeline as pipeline
    from tesouro import config
    from tesouro.graficos import dashboard

    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)
    for arquivo, _ in dashboard.PAGINAS:
        (tmp_path / arquivo).write_text("x", encoding="utf-8")

    linhas = []
    pipeline._COMECO.clear()
    pipeline._COMECO.append(0)          # tudo foi gravado depois do comeco
    pipeline._onde_estao_as_paginas(saida=linhas.append)
    junto = "\n".join(linhas)

    assert str(tmp_path) in junto, "nao disse a pasta"
    for arquivo, rotulo in dashboard.PAGINAS:
        assert arquivo in junto, arquivo
        assert rotulo in junto, rotulo
    assert "NAO GRAVADA" not in junto
    assert "rodada anterior" not in junto


def test_pagina_que_o_modo_NAO_REGRAVOU_sai_marcada(tmp_path, monkeypatch):
    # O habito dela, nas palavras dela: "se o cabecalho nao mudou, a
    # atualizacao nao atualizou". A tela passa a responder isso sem ela abrir
    # arquivo nenhum -- e no modo 'paf' as paginas de emissao de fato nao sao
    # regravadas.
    import time

    import tesouro.pipeline as pipeline
    from tesouro import config
    from tesouro.graficos import dashboard

    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)
    for arquivo, _ in dashboard.PAGINAS:
        (tmp_path / arquivo).write_text("x", encoding="utf-8")

    velha = dashboard.PAGINAS[0][0]
    antiga = time.time() - 86400
    import os
    os.utime(tmp_path / velha, (antiga, antiga))

    linhas = []
    pipeline._COMECO.clear()
    pipeline._COMECO.append(time.time() - 60)
    pipeline._onde_estao_as_paginas(saida=linhas.append)

    da_velha = [l for l in linhas if velha in l]
    assert len(da_velha) == 1, linhas
    assert "rodada anterior" in da_velha[0], da_velha
    # E SO ELA: as outras foram gravadas nesta rodada.
    assert sum("rodada anterior" in l for l in linhas) == 1, linhas


def test_pagina_AUSENTE_sai_marcada_e_nao_em_silencio(tmp_path, monkeypatch):
    # "Nao gravada" e uma informacao; silencio nao e. Se a barra promete uma
    # pagina que nao esta no disco, quem abrir a barra vai achar link morto --
    # melhor descobrir aqui.
    import tesouro.pipeline as pipeline
    from tesouro import config
    from tesouro.graficos import dashboard

    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)
    presentes = dashboard.PAGINAS[1:]
    for arquivo, _ in presentes:
        (tmp_path / arquivo).write_text("x", encoding="utf-8")
    faltando = dashboard.PAGINAS[0][0]

    linhas = []
    pipeline._COMECO.clear()
    pipeline._COMECO.append(0)
    pipeline._onde_estao_as_paginas(saida=linhas.append)

    da_faltando = [l for l in linhas if faltando in l]
    assert len(da_faltando) == 1, linhas
    assert "NAO GRAVADA" in da_faltando[0], da_faltando


def test_a_falha_NOMEIA_a_fase_que_quebrou():
    # Medido em 20/10/2026 numa rodada de verdade: a API deu "Server Error", a
    # pagina do PAF quebrou, e a tela dizia "a geracao do dashboard FALHOU" --
    # mandando olhar justamente a pagina que tinha dado certo.
    import tesouro.pipeline as pipeline

    pipeline._ULTIMA_FASE.clear()
    pipeline._COMECO.clear()
    pipeline._COMECO.append(0)
    pipeline._fase("gravando a pagina do PAF")
    assert pipeline._ULTIMA_FASE == ["gravando a pagina do PAF"]

    # E a fase mais recente VENCE: o bloco vai do dashboard ate a agenda, e o
    # que importa e onde estava quando quebrou.
    pipeline._fase("gravando as paginas de emissao")
    assert pipeline._ULTIMA_FASE == ["gravando as paginas de emissao"]


def test_a_mensagem_de_falha_das_paginas_usa_a_fase():
    # Guarda de fonte: a mensagem tem de sair da fase guardada, e nao de uma
    # pagina cravada no texto.
    import pathlib

    fonte = (pathlib.Path(__file__).resolve().parents[1]
             / "src" / "tesouro" / "pipeline.py").read_text(encoding="utf-8")
    assert "a geracao do dashboard FALHOU" not in fonte, (
        "a mensagem voltou a nomear o dashboard para qualquer pagina")
    assert "_ULTIMA_FASE[0] if _ULTIMA_FASE" in fonte


def test_a_rotina_do_calendario_novo_esta_LIGADA_na_coleta():
    # PEDIDO DELA em 20/10/2026: "quando ter uma rotina para quando sai um
    # calendario novo?". Guarda de fonte: a comparacao tem de acontecer na
    # coleta e chegar a tela. Sem ela, o projeto volta a baixar, salvar e ficar
    # calado -- e a publicacao de um comunicado novo e o evento que mais muda a
    # projecao do fim do ano.
    import pathlib

    fonte = (pathlib.Path(__file__).resolve().parents[1]
             / "src" / "tesouro" / "pipeline.py").read_text(encoding="utf-8")

    # O GUARDADO E LIDO ANTES DE SALVAR: depois de salvar, o "anterior" seria o
    # proprio arquivo de hoje e a comparacao nunca acusaria nada.
    antes = fonte.index('guardado_em_disco("calendario")')
    salva = fonte.index('_api.guardar("calendario")')
    assert antes < salva, "le o guardado DEPOIS de salvar; nada seria acusado"

    assert "mudou_a_cobertura(antes_cal, registros_cal)" in fonte
    assert "_anuncia_calendario_novo(" in fonte


def test_o_anuncio_do_calendario_FICA_CALADO_quando_nada_mudou():
    # Aviso que sai em toda rodada deixa de ser lido, e no dia em que importar
    # ninguem ve.
    import tesouro.pipeline as pipeline

    linhas = []
    assert pipeline._anuncia_calendario_novo([], saida=linhas.append) is False
    assert linhas == []


def test_o_anuncio_do_calendario_SAI_INTEIRO_quando_mudou():
    # A prova de dentes pegou a versao inline: o teste era um grep, e trocar a
    # condicao por 'if False' o deixava verde. Agora o comportamento e afirmado.
    import tesouro.pipeline as pipeline

    linhas = []
    mudou = pipeline._anuncia_calendario_novo(
        ["LTN: esticou de 17/12/2026 para 30/03/2027",
         "NTN-B: ENCURTOU de 23/03/2027 para 29/09/2026 -- a projecao vai "
         "depender mais do estimador"],
        saida=linhas.append)
    junto = "\n".join(linhas)

    assert mudou is True
    assert "CALENDARIO NOVO" in junto
    # CADA LINHA SAI, e nao so a primeira.
    assert "LTN: esticou" in junto
    assert "NTN-B: ENCURTOU" in junto
    # E A CONSEQUENCIA, que e por que isto existe.
    assert "projecao do fim do ano" in junto


def test_a_coleta_NAO_ESCREVE_em_data_raw_durante_os_testes(monkeypatch, tmp_path):
    """A guarda da guarda: nenhuma acao de coleta pode gravar em data/raw.

    TERCEIRA VEZ que este arquivo vive a mesma historia: o resultado do dia
    (09/09/2026), o edital (24/09/2026) e a guarda do calendario (20/10/2026)
    entraram na coleta e nao foram stubadas, e os testes passaram a ir a rede e
    a escrever na pasta de ENTRADA dela. Em 22/10/2026 achei um
    calendario-2026-10-20.json de 10.847 bytes gravado por teste.

    Em vez de confiar na memoria de quem acrescenta a proxima, este teste
    OLHA A PASTA: roda o pipeline com a coleta stubada e exige que nada tenha
    sido criado em data/raw.
    """
    from tesouro import config

    # NOME, CARIMBO E TAMANHO -- e nao so o nome. A primeira versao desta
    # guarda comparava o CONJUNTO DE NOMES, e a prova de dentes mostrou o
    # buraco: tirar o stub fazia o teste reescrever o arquivo de HOJE, que ja
    # existia, e nada aparecia como novo. Reescrever arquivo de entrada e tao
    # proibido quanto criar.
    def retrato():
        return {p.relative_to(config.RAW_DIR).as_posix():
                (p.stat().st_mtime_ns, p.stat().st_size)
                for p in config.RAW_DIR.rglob("*") if p.is_file()}

    antes = retrato()

    chamadas = []
    _stub_gravacoes(monkeypatch, chamadas)
    _stub_coletas(monkeypatch, chamadas)
    pipeline.main([])

    depois = retrato()
    mexidos = sorted(set(antes) ^ set(depois))
    mexidos += sorted(k for k in set(antes) & set(depois)
                      if antes[k] != depois[k])
    assert not mexidos, (
        "a coleta mexeu em data/raw durante o teste: %s. Toda acao de coleta "
        "precisa de stub em _stub_gravacoes -- ver os comentarios do helper."
        % mexidos)
