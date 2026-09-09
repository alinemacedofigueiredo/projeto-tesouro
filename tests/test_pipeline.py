"""Testes do orquestrador (src/tesouro/pipeline.py).

Ate a Tarefa 10, pipeline.py nao tinha nenhum teste -- nem o invariante
"--sem-coleta nunca toca rede" (restricao dura do ambiente do banco), nem
o try/except da coleta da Bloomberg, nem a ordem/contrato das etapas que
gravam os 22 CSVs. Os tres ganham teste aqui, todos com monkeypatch nas
funcoes de gravacao/coleta reais -- rodar o pipeline de ponta a ponta de
verdade (com dado real) e feito a mao no fechamento da tarefa, nao aqui.
"""
import socket

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
    assert "concluido." in saida
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
    assert "concluido." not in saida
    # A ultima parte do log (apos as etapas de gravacao) repete o aviso.
    indice_figuras = saida.index("--- figuras ---")
    assert "ATENCAO" in saida[indice_figuras:]


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
    geracao = [c for c in chamadas
               if not c.endswith((".baixar", ".rodar"))
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


def test_o_modo_RMD_PERGUNTA_qual_mes_quando_ninguem_diz(monkeypatch):
    """Pedido dela, com estas palavras: "quando a pessoa decidir atualizar o
    rmd tem q ter a opcao, qual rmd vc quer puxar?".

    Sem isto o modo rmd caia no comportamento antigo -- imprimia "usando o RMD
    ja presente em data/raw/rmd/" e nao baixava nada. Quem escolheu "atualizar
    o RMD" num menu nao espera que nada seja baixado.
    """
    respostas = iter(["2026", "8"])
    chamadas = []
    _stub_gravacoes(monkeypatch, chamadas)
    _stub_coletas(monkeypatch, chamadas)
    pedidos = []

    def baixar(ano, mes):
        pedidos.append((ano, mes))
        chamadas.append("tesouro.fetch_rmd.baixar")
    from tesouro import fetch_rmd
    monkeypatch.setattr(fetch_rmd, "baixar", baixar)
    monkeypatch.setattr(pipeline, "_e_interativo", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *a: next(respostas))

    codigo = pipeline.main(["--modo", "rmd"])
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


def test_o_menu_do_RMD_RECUSA_mes_impossivel():
    """13 nao e mes. Sem esta guarda o pedido ia para o site do Tesouro e
    voltava com erro de rede, que e um jeito confuso de dizer "digitei 13"."""
    respostas = iter(["2026", "13"])
    ditas = []
    assert pipeline.escolher_rmd_no_menu(
        entrada=lambda *a: next(respostas), saida=ditas.append) is None
    assert any("1 a 12" in d for d in ditas), ditas


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
