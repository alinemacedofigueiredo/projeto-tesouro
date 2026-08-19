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
    antes de devolver None -- usado para conferir ordem.
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
    for modulo, nome in alvos:
        def stub(*args, _nome=f"{modulo.__name__}.{nome}", **kwargs):
            if chamadas is not None:
                chamadas.append(_nome)
            return None
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
# Contrato: as sete etapas de gravacao rodam, e nesta ordem -- e o que
# produz os 22 CSVs (17 da camada de dados + taxa_por_papel, vna,
# dv_por_papel, decay_por_papel, resultado_mensal) mais as figuras. A
# contagem exata de linhas/CSVs foi conferida a mao contra o dado real
# (ver task-10-report.md); aqui o que se trava e a fiacao -- cada etapa e
# chamada exatamente uma vez, na ordem que uma depende da anterior (dv
# le taxa_por_papel/vna, que so existem depois de parse_bloomberg.gravar;
# figuras le dv_por_papel/decay_por_papel/resultado_mensal, que so
# existem depois de dv.gravar_*).
# ---------------------------------------------------------------------------

def test_pipeline_grava_as_sete_etapas_na_ordem_certa(monkeypatch):
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
    monkeypatch.setattr(dashboard, "grava",
                        lambda *a, **k: chamadas.append("dashboard.grava"))

    assert pipeline.main(["--sem-coleta"]) == 0
    assert "dashboard.grava" in chamadas
    # O _stub_gravacoes que ja existe no arquivo registra o nome QUALIFICADO --
    # "tesouro.figuras.gravar_todas", nao "gravar_todas".
    assert (chamadas.index("dashboard.grava")
            > chamadas.index("tesouro.figuras.gravar_todas"))


def test_falha_do_dashboard_entra_nas_falhas_e_muda_o_codigo_de_saida(monkeypatch,
                                                                     capsys):
    # O paf.bandas levanta de proposito quando a referencia esta quebrada. Isso
    # tem de aparecer como falha real, nao sumir no meio do log.
    from tesouro.graficos import dashboard

    _stub_gravacoes(monkeypatch)

    def _explode(*args, **kwargs):
        raise ValueError("paf_bandas.csv esta invalido")

    monkeypatch.setattr(dashboard, "grava", _explode)

    assert pipeline.main(["--sem-coleta"]) == 1
    saida = capsys.readouterr().out
    assert "dashboard" in saida.lower()
    assert "paf_bandas.csv" in saida
