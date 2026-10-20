import csv
import io
from datetime import date

import pandas as pd
import pytest
from tesouro import fetch_bloomberg, parse_bloomberg

# O calendario e pedido SO QUANDO USADO -- ver tests/calendario_tardio.py.
# No topo do modulo ele quebrava a COLETA do pytest numa maquina sem
# data/raw/anbima/feriados_nacionais.xls, e com isso a suite inteira.
from calendario_tardio import CAL


def _fim_mes(ano, mes):
    return CAL.ultimo_dia_util_do_mes(date(ano, mes, 1))


# ---------------------------------------------------------------------------
# Testes da especificacao original da Tarefa 4 -- rodam contra o estoque de
# verdade do projeto (data/processed/estoque_titulos_vencimento.csv), sem
# tocar rede: papeis_do_estoque e datas_do_painel so leem CSV local.
# ---------------------------------------------------------------------------

def test_papeis_cobrem_apenas_o_escopo():
    p = fetch_bloomberg.papeis_do_estoque()
    assert set(p["titulo"].unique()) == {"LTN", "NTN-F", "NTN-B", "LFT"}
    assert len(p) > 150
    assert p["isin"].notna().all()


def test_papeis_trazem_a_janela_de_vida():
    p = fetch_bloomberg.papeis_do_estoque()
    assert (p["primeira"] <= p["ultima"]).all()


def test_datas_do_painel_sao_dia_util_e_fim_de_mes():
    d = fetch_bloomberg.datas_do_painel()
    assert len(d) > 190
    assert all(CAL.eh_dia_util(x) for x in d)
    assert all(CAL.ultimo_dia_util_do_mes(x) == x for x in d)
    assert d == sorted(d)


def test_nao_importa_blpapi_no_topo():
    # O modulo tem de importar em maquina sem Bloomberg. O import fica
    # dentro da funcao que faz a coleta.
    import ast
    import pathlib
    fonte = pathlib.Path("src/tesouro/fetch_bloomberg.py").read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    for no in arvore.body:                      # so o nivel de modulo
        if isinstance(no, (ast.Import, ast.ImportFrom)):
            nomes = [a.name for a in no.names] + [getattr(no, "module", "") or ""]
            assert not any("blpapi" in n for n in nomes)


# ---------------------------------------------------------------------------
# Testes de _historico/_referencia -- confirmam a REQUISICAO que as duas
# funcoes montam (nao so o retorno), com um servico/sessao falso que so
# registra o que foi pedido. E aqui que moram as duas armadilhas de maior
# custo medido do projeto (docs/convencoes-dv.md): taxa historica tem que
# usar HistoricalDataRequest, nunca SETTLE_DT (erro medido de 135 bp no
# fim de 2024); e a fonte @ANDE e obrigatoria no identificador do papel.
# Como esses testes chamam _historico/_referencia de verdade (nao
# dublados), uma mutacao nessas duas funcoes -- inclusive uma que so
# aparece na REQUISICAO, sem quebrar nenhum outro teste, porque todo
# teste de baixar() dubla as duas -- e pega aqui.
# ---------------------------------------------------------------------------

class _FakeBlpapiEvent:
    RESPONSE = "RESPONSE"


class _FakeBlpapi:
    Event = _FakeBlpapiEvent


class _FakeEvento:
    """Uma resposta sem nenhuma mensagem -- so nos interessa o pedido."""

    def __iter__(self):
        return iter(())

    def eventType(self):
        return _FakeBlpapiEvent.RESPONSE


class _FakeElemento:
    def __init__(self):
        self.valores = []

    def appendValue(self, valor):
        self.valores.append(valor)

    def appendElement(self):
        elemento = _FakeOverride()
        self.valores.append(elemento)
        return elemento


class _FakeOverride:
    def __init__(self):
        self.campos = {}

    def setElement(self, nome, valor):
        self.campos[nome] = valor


class _FakeRequest:
    def __init__(self, tipo):
        self.tipo = tipo
        self.elementos = {}
        self.sets = {}

    def getElement(self, nome):
        return self.elementos.setdefault(nome, _FakeElemento())

    def set(self, nome, valor):
        self.sets[nome] = valor


class _FakeServicoRequisicao:
    def __init__(self):
        self.requests = []

    def createRequest(self, tipo):
        req = _FakeRequest(tipo)
        self.requests.append(req)
        return req


class _FakeSessaoRequisicao:
    def __init__(self, servico):
        self._servico = servico

    def sendRequest(self, req):
        pass

    def nextEvent(self, timeout):
        return _FakeEvento()


def test_historico_usa_historicaldatarequest_com_fonte_ande_e_sem_settle_dt():
    servico = _FakeServicoRequisicao()
    sessao = _FakeSessaoRequisicao(servico)

    fetch_bloomberg._historico(
        _FakeBlpapi, sessao, servico, "BR1234567890",
        fetch_bloomberg.CAMPO_TAXA, date(2023, 1, 1), date(2023, 3, 31),
    )

    assert len(servico.requests) == 1
    req = servico.requests[0]
    assert req.tipo == "HistoricalDataRequest"
    assert req.elementos["securities"].valores == ["/isin/BR1234567890@ANDE Govt"]
    assert req.elementos["fields"].valores == [fetch_bloomberg.CAMPO_TAXA]
    assert req.sets["startDate"] == "20230101"
    assert req.sets["endDate"] == "20230331"
    assert req.sets["periodicitySelection"] == "MONTHLY"
    # A armadilha central: taxa historica NUNCA usa override de SETTLE_DT
    # -- ver docs/convencoes-dv.md (erro medido de 135 bp com ele).
    assert "overrides" not in req.elementos


def test_referencia_usa_referencedatarequest_com_settle_dt_e_fonte_ande():
    servico = _FakeServicoRequisicao()
    sessao = _FakeSessaoRequisicao(servico)

    fetch_bloomberg._referencia(
        _FakeBlpapi, sessao, servico,
        ["BR1111111111", "BR2222222222"], "IDX_RATIO", date(2023, 6, 30),
    )

    assert len(servico.requests) == 1
    req = servico.requests[0]
    assert req.tipo == "ReferenceDataRequest"
    assert req.elementos["securities"].valores == [
        "/isin/BR1111111111@ANDE Govt", "/isin/BR2222222222@ANDE Govt",
    ]
    assert req.elementos["fields"].valores == ["IDX_RATIO"]
    overrides = req.elementos["overrides"].valores
    assert len(overrides) == 1
    assert overrides[0].campos == {"fieldId": "SETTLE_DT", "value": "20230630"}


# ---------------------------------------------------------------------------
# Teste isolado de _conteudo_vna -- confere que 'divergencia' e gravada na
# MESMA unidade que 'vna' (reais, fator x 1000), nao na unidade do fator
# cru. parse_bloomberg.py documenta a tolerancia (0.5) "em reais"; sem o
# x1000 aqui, uma divergencia real de R$0,40 (bem acima da tolerancia)
# seria gravada como 0.4 e aceita calada.
# ---------------------------------------------------------------------------

def test_conteudo_vna_grava_divergencia_em_reais_nao_no_fator_cru(monkeypatch):
    m1 = _fim_mes(2023, 1)
    estoque_dois_papeis_mesmo_indice = pd.DataFrame({
        "titulo": ["LFT", "LFT"],
        "isin": ["BR0000000LF1", "BR0000000LF2"],
        "data": pd.to_datetime([m1, m1]),
    })
    monkeypatch.setattr(fetch_bloomberg, "_estoque",
                         lambda: estoque_dois_papeis_mesmo_indice)

    def _referencia_fake(blpapi, sessao, servico, isins, campo, settle):
        # dois papeis do mesmo indice discordando em 0.0004 no FATOR --
        # R$0,40 de divergencia depois do x1000, dez vezes acima da
        # tolerancia de 0.5 documentada em parse_bloomberg.py.
        return [1.874868830, 1.875268830][: len(isins)]

    monkeypatch.setattr(fetch_bloomberg, "_referencia", _referencia_fake)

    conteudo = fetch_bloomberg._conteudo_vna([m1], None, None, None)
    linhas = list(csv.DictReader(io.StringIO(conteudo.decode("utf-8"))))

    assert len(linhas) == 1
    assert linhas[0]["indice"] == "SELIC"
    assert float(linhas[0]["divergencia"]) == pytest.approx(0.4, abs=1e-6)


# ---------------------------------------------------------------------------
# Testes de baixar() -- nunca tocam rede. _sessao, _historico e _referencia
# sao substituidos por dubles; papeis_do_estoque, datas_do_painel e _estoque
# sao substituidos por um painel sintetico pequeno (3 meses, 3 papeis) para
# manter os testes rapidos e legiveis. Nenhum teste escreve em data/raw/ --
# tudo usa tmp_path.
# ---------------------------------------------------------------------------

# AS TRES DATAS DO PAINEL FALSO: ultimo dia util de jan, fev e mar de
# 2023. CRAVADAS DE PROPOSITO -- calcula-las aqui pedia o calendario de
# feriados na COLETA do pytest, e um erro de coleta aborta a suite
# inteira numa maquina sem data/raw/anbima (achado em 20/10/2026 no
# teste do clone limpo). Quem confere que sao mesmo os ultimos dias
# uteis e test_as_datas_do_painel_falso_sao_os_ultimos_dias_uteis,
# abaixo, que roda onde o calendario existe.
M1, M2, M3 = date(2023, 1, 31), date(2023, 2, 28), date(2023, 3, 31)

_PAPEIS_FAKE = pd.DataFrame([
    # ativo o periodo inteiro -- serve para testar o corte incremental
    {"isin": "BR0000000LTN", "titulo": "LTN", "vencimento": date(2024, 1, 1),
     "primeira": M1, "ultima": M3},
    # nasce so em fevereiro -- depois do cutoff usado nos testes, entao a
    # janela pedida para ele tem de ser a propria data de nascimento, nunca
    # o limite do corte incremental
    {"isin": "BR0000000NTB", "titulo": "NTN-B", "vencimento": date(2025, 1, 1),
     "primeira": M2, "ultima": M3},
    # LFT so para exercitar o campo ACCUMULATED_SELIC no vna, e para
    # confirmar que o preco NUNCA e pedido para ela (serie inutilizavel)
    {"isin": "BR0000000LFT", "titulo": "LFT", "vencimento": date(2024, 6, 1),
     "primeira": M1, "ultima": M3},
])

_DATAS_FAKE = [M1, M2, M3]

_ESTOQUE_FAKE = pd.DataFrame({
    "titulo": ["LTN", "LTN", "LTN", "NTN-B", "NTN-B", "LFT", "LFT", "LFT"],
    "isin": ["BR0000000LTN"] * 3 + ["BR0000000NTB"] * 2 + ["BR0000000LFT"] * 3,
    "data": pd.to_datetime([M1, M2, M3, M2, M3, M1, M2, M3]),
})

# Fatores distintos e nao-redondos por campo -- usados para "asserte o
# numero" no teste de ida e volta (test_baixar_grava_csv_...): se o x1000
# de _conteudo_vna for removido numa edicao futura, o vna lido de volta
# fica com o valor do FATOR (~1,8 / ~4,5) em vez do valor esperado
# (~1834 / ~4512), e a assercao de valor pega isso -- ao contrario de so
# checar presenca de linha ou o conjunto de indices.
_FATOR_POR_CAMPO = {
    "IDX_RATIO": 1.834568321,
    "ACCUMULATED_SELIC": 4.512389765,
}


class _SessaoFake:
    def getService(self, nome):
        return "servico-fake"

    def stop(self):
        pass


def _aplicar_dubles(monkeypatch, chamadas_historico=None, chamadas_referencia=None):
    """Substitui o painel e a fala com o terminal por dubles deterministicos.

    chamadas_historico/chamadas_referencia, se passadas, recebem cada
    chamada feita -- para os testes que precisam conferir QUAL janela foi
    pedida, nao so o resultado. A forma da REQUISICAO (tipo, securities,
    overrides) e testada a parte, sem dublar _historico/_referencia --
    ver a secao acima.
    """
    monkeypatch.setattr(fetch_bloomberg, "papeis_do_estoque", lambda: _PAPEIS_FAKE.copy())
    monkeypatch.setattr(fetch_bloomberg, "datas_do_painel", lambda: list(_DATAS_FAKE))
    monkeypatch.setattr(fetch_bloomberg, "_estoque", lambda: _ESTOQUE_FAKE.copy())
    monkeypatch.setattr(fetch_bloomberg, "_sessao", lambda: (None, _SessaoFake()))

    def _historico_fake(blpapi, sessao, servico, isin, campo, inicio, fim):
        if chamadas_historico is not None:
            chamadas_historico.append((isin, campo, inicio, fim))
        return [(d, 1.0) for d in _DATAS_FAKE if inicio <= d <= fim]

    def _referencia_fake(blpapi, sessao, servico, isins, campo, settle):
        if chamadas_referencia is not None:
            chamadas_referencia.append((tuple(isins), campo, settle))
        return [_FATOR_POR_CAMPO[campo]] * len(isins)

    monkeypatch.setattr(fetch_bloomberg, "_historico", _historico_fake)
    monkeypatch.setattr(fetch_bloomberg, "_referencia", _referencia_fake)


def _linhas(caminho):
    with open(caminho, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _criar_marcador(tmp_path, prefixo, de, ate):
    """Cria um arquivo vazio (so cabecalho) com o nome que _meses_cobertos
    le -- os testes de corte incremental so precisam do NOME, nunca do
    conteudo.
    """
    nome = f"{prefixo}{de:%Y-%m}_{ate:%Y-%m}.csv"
    (tmp_path / nome).write_text("cabecalho\n", encoding="utf-8")
    return tmp_path / nome


def test_baixar_primeira_coleta_pega_a_janela_inteira(tmp_path, monkeypatch):
    chamadas = []
    _aplicar_dubles(monkeypatch, chamadas_historico=chamadas)

    alvo_taxa, alvo_vna, alvo_preco = fetch_bloomberg.baixar(destino=tmp_path)

    assert alvo_taxa.name == "bbg_taxas_ANDE_2023-01_2023-03.csv"
    assert alvo_vna.name == "bbg_vna_2023-01_2023-03.csv"
    assert alvo_preco.name == "bbg_precos_ANDE_2023-01_2023-03.csv"
    assert alvo_taxa.exists() and alvo_vna.exists() and alvo_preco.exists()

    # Sem coleta anterior, cada papel e pedido desde a propria data de
    # nascimento -- nunca um corte artificial.
    janelas = {isin: (inicio, fim) for isin, campo, inicio, fim in chamadas
               if campo == fetch_bloomberg.CAMPO_TAXA}
    assert janelas["BR0000000LTN"] == (M1, M3)
    assert janelas["BR0000000NTB"] == (M2, M3)

    linhas = _linhas(alvo_taxa)
    assert {l["isin"] for l in linhas} == {"BR0000000LTN", "BR0000000NTB", "BR0000000LFT"}
    # BR0000000NTB nasce em M2: nao pode ter linha em M1.
    assert not any(l["isin"] == "BR0000000NTB" and l["data"] == str(M1) for l in linhas)

    # A LFT nunca entra no preco -- serie inutilizavel na Bloomberg.
    linhas_preco = _linhas(alvo_preco)
    assert "BR0000000LFT" not in {l["isin"] for l in linhas_preco}


def test_baixar_incremental_pede_so_o_que_falta(tmp_path, monkeypatch):
    # Uma coleta anterior ja cobriu janeiro nos tres arquivos.
    _criar_marcador(tmp_path, "bbg_taxas_ANDE_", M1, M1)
    _criar_marcador(tmp_path, "bbg_vna_", M1, M1)
    _criar_marcador(tmp_path, "bbg_precos_ANDE_", M1, M1)

    chamadas = []
    _aplicar_dubles(monkeypatch, chamadas_historico=chamadas)

    alvo_taxa, alvo_vna, alvo_preco = fetch_bloomberg.baixar(destino=tmp_path)

    # O nome do arquivo novo reflete SO o periodo pedido -- fevereiro e
    # marco -- nunca a janela inteira do estoque.
    assert alvo_taxa.name == "bbg_taxas_ANDE_2023-02_2023-03.csv"
    assert alvo_vna.name == "bbg_vna_2023-02_2023-03.csv"

    janelas = {isin: (inicio, fim) for isin, campo, inicio, fim in chamadas
               if campo == fetch_bloomberg.CAMPO_TAXA}
    # LTN ja vivia antes do corte: pedido comeca no mes mais antigo que
    # falta (fevereiro), nao na data de nascimento real (janeiro) -- e o
    # corte incremental agindo.
    assert janelas["BR0000000LTN"] == (M2, M3)
    # NTN-B nasceu depois do corte: pedido comeca na propria data de
    # nascimento (fim de fevereiro), que ja e posterior ao limite.
    assert janelas["BR0000000NTB"] == (M2, M3)

    linhas = _linhas(alvo_taxa)
    assert all(l["data"] != str(M1) for l in linhas)

    # Os arquivos de janeiro, que ja existiam, continuam exatamente como
    # estavam -- nada foi reescrito neles.
    assert (tmp_path / "bbg_taxas_ANDE_2023-01_2023-01.csv").read_text(
        encoding="utf-8"
    ) == "cabecalho\n"


def test_baixar_preenche_buraco_no_meio_da_serie(tmp_path, monkeypatch):
    """A primeira versao deste modulo so olhava o MAXIMO 'ate' de cada
    tipo de arquivo -- um buraco no meio (janeiro e marco presentes,
    fevereiro faltando) nunca era detectado, e a mensagem de erro dizia
    'nada novo', mandando mexer no RMD sem motivo. Este teste reproduz
    exatamente esse cenario.
    """
    for prefixo in ("bbg_taxas_ANDE_", "bbg_vna_", "bbg_precos_ANDE_"):
        _criar_marcador(tmp_path, prefixo, M1, M1)
        _criar_marcador(tmp_path, prefixo, M3, M3)

    chamadas_vna = []
    _aplicar_dubles(monkeypatch, chamadas_referencia=chamadas_vna)

    alvo_taxa, alvo_vna, alvo_preco = fetch_bloomberg.baixar(destino=tmp_path)

    # So fevereiro faltava -- o nome do arquivo novo reflete so ele.
    assert alvo_taxa.name == "bbg_taxas_ANDE_2023-02_2023-02.csv"
    assert alvo_vna.name == "bbg_vna_2023-02_2023-02.csv"
    assert alvo_preco.name == "bbg_precos_ANDE_2023-02_2023-02.csv"

    # O vna e pedido mes a mes (nao por intervalo): so fevereiro aparece.
    meses_pedidos = {settle for isins, campo, settle in chamadas_vna}
    assert meses_pedidos == {M2}

    linhas_vna = _linhas(alvo_vna)
    assert {l["data"] for l in linhas_vna} == {str(M2)}

    # Os arquivos de janeiro e marco, que ja existiam, continuam intactos.
    assert (tmp_path / "bbg_taxas_ANDE_2023-01_2023-01.csv").read_text(
        encoding="utf-8"
    ) == "cabecalho\n"
    assert (tmp_path / "bbg_taxas_ANDE_2023-03_2023-03.csv").read_text(
        encoding="utf-8"
    ) == "cabecalho\n"


def test_baixar_sem_novidade_leva_erro_visivel_sem_tocar_rede(tmp_path, monkeypatch):
    # Arquivos existentes ja cobrem o painel inteiro (jan a mar) nos tres
    # tipos de arquivo.
    for prefixo in ("bbg_taxas_ANDE_", "bbg_vna_", "bbg_precos_ANDE_"):
        _criar_marcador(tmp_path, prefixo, M1, M3)

    monkeypatch.setattr(fetch_bloomberg, "papeis_do_estoque", lambda: _PAPEIS_FAKE.copy())
    monkeypatch.setattr(fetch_bloomberg, "datas_do_painel", lambda: list(_DATAS_FAKE))

    def _proibido(*args, **kwargs):
        raise AssertionError("nao deveria ter aberto sessao com o terminal")

    monkeypatch.setattr(fetch_bloomberg, "_sessao", _proibido)

    with pytest.raises(RuntimeError, match="nada novo"):
        fetch_bloomberg.baixar(destino=tmp_path)

    # Nao pode ter criado nada em tmp_path alem dos 3 marcadores originais.
    assert len(list(tmp_path.iterdir())) == 3


def test_baixar_nunca_sobrescreve_arquivo_de_destino_existente(tmp_path, monkeypatch):
    # Forca a deteccao de cobertura a "nao ver nada ainda coletado",
    # mesmo com um arquivo ja fisicamente presente no caminho que o
    # proximo pedido calcularia -- simula qualquer cenario em que o nome
    # alvo colida (defesa em profundidade, independente do mecanismo que
    # descobre a cobertura existente).
    alvo = tmp_path / "bbg_taxas_ANDE_2023-01_2023-03.csv"
    alvo.write_text("SENTINELA: nao mexer\n", encoding="utf-8")

    monkeypatch.setattr(fetch_bloomberg, "_meses_cobertos",
                         lambda destino, padrao_glob, padrao_nome: set())
    monkeypatch.setattr(fetch_bloomberg, "papeis_do_estoque", lambda: _PAPEIS_FAKE.copy())
    monkeypatch.setattr(fetch_bloomberg, "datas_do_painel", lambda: list(_DATAS_FAKE))

    def _proibido(*args, **kwargs):
        raise AssertionError("nao deveria ter aberto sessao com o terminal")

    monkeypatch.setattr(fetch_bloomberg, "_sessao", _proibido)

    with pytest.raises(FileExistsError, match="ja existe"):
        fetch_bloomberg.baixar(destino=tmp_path)

    assert alvo.read_text(encoding="utf-8") == "SENTINELA: nao mexer\n"


def test_baixar_nao_cria_pasta_de_destino_quando_nao_ha_nada_a_gravar(tmp_path, monkeypatch):
    """destino.mkdir() so roda depois de confirmar que ha algo para
    gravar -- um destino digitado errado nao deixa uma pasta vazia para
    tras so por ter sido consultado.
    """
    destino = tmp_path / "nao_deveria_ser_criada"  # nem existe ainda

    monkeypatch.setattr(fetch_bloomberg, "papeis_do_estoque", lambda: _PAPEIS_FAKE.copy())
    monkeypatch.setattr(fetch_bloomberg, "datas_do_painel", lambda: [])

    def _proibido(*args, **kwargs):
        raise AssertionError("nao deveria ter aberto sessao com o terminal")

    monkeypatch.setattr(fetch_bloomberg, "_sessao", _proibido)

    with pytest.raises(RuntimeError, match="nada a coletar"):
        fetch_bloomberg.baixar(destino=destino)

    assert not destino.exists()


def test_baixar_grava_csv_que_parse_bloomberg_le_sem_alteracao(tmp_path, monkeypatch):
    """O contrato de nome, coluna E VALOR com o leitor (Tarefa 3) e o que
    importa de verdade aqui: gera com baixar() e le de volta com
    parse_bloomberg, sem tocar em parse_bloomberg.py. A assercao de valor
    do vna (nao so presenca/indice) e o que pega uma remocao do x1000 em
    _conteudo_vna -- sem ela, essa mutacao passaria pelos 9 testes
    originais sem ser notada (achado da revisao).
    """
    _aplicar_dubles(monkeypatch)

    fetch_bloomberg.baixar(destino=tmp_path)

    taxas = parse_bloomberg.parse_taxas(caminho=tmp_path)
    vna = parse_bloomberg.parse_vna(caminho=tmp_path)

    assert len(taxas) > 0
    assert set(taxas["isin"]) == {"BR0000000LTN", "BR0000000NTB", "BR0000000LFT"}
    assert len(vna) > 0
    assert set(vna["indice"]) <= {"IPCA", "SELIC"}

    ipca = vna[vna["indice"] == "IPCA"].iloc[0]
    selic = vna[vna["indice"] == "SELIC"].iloc[0]
    assert ipca["vna"] == pytest.approx(_FATOR_POR_CAMPO["IDX_RATIO"] * 1000, rel=1e-9)
    assert selic["vna"] == pytest.approx(_FATOR_POR_CAMPO["ACCUMULATED_SELIC"] * 1000, rel=1e-9)

def test_baixar_coleta_SO_O_TIPO_que_falta(tmp_path, monkeypatch):
    """O caso real de 25/08/2026: taxa e vna em disco, preco nunca coletado.

    A conta de "meses faltando" usava OU entre os tres tipos. Com o preco
    inteiramente ausente, TODOS os meses entravam -- e baixar() tentava
    regravar tambem a taxa e o vna, batendo no FileExistsError que guarda a
    imutabilidade de data/raw/.

    O invariante fez o trabalho dele: parou antes de sobrescrever. Mas o efeito
    era que nao havia como coletar so o preco, e coletar os tres de novo
    triplicaria a consulta a Bloomberg que ela autorizou.

    Agora a conta e por tipo. Aqui, so o preco e pedido.
    """
    chamadas = []
    _aplicar_dubles(monkeypatch, chamadas_historico=chamadas)

    # Taxa e vna ja cobrem o painel inteiro; preco, nada.
    _criar_marcador(tmp_path, "bbg_taxas_ANDE_", M1, M3)
    _criar_marcador(tmp_path, "bbg_vna_", M1, M3)

    alvo_taxa, alvo_vna, alvo_preco = fetch_bloomberg.baixar(destino=tmp_path)

    assert alvo_taxa is None, "a taxa ja esta coberta e nao pode ser repuxada"
    assert alvo_vna is None, "o vna ja esta coberto e nao pode ser repuxado"
    assert alvo_preco is not None and alvo_preco.exists()
    assert alvo_preco.name == "bbg_precos_ANDE_2023-01_2023-03.csv"

    # E A CONSULTA A BLOOMBERG SO PEDIU PRECO. Sem isto o teste passaria com
    # um baixar() que puxa os tres e joga dois fora -- o arquivo nao apareceria,
    # mas a consulta teria sido feita, que e o que custa.
    campos = {campo for _, campo, _, _ in chamadas}
    assert fetch_bloomberg.CAMPO_TAXA not in campos, (
        "pediu taxa a Bloomberg mesmo com o periodo ja coberto")


def test_baixar_ainda_recusa_sobrescrever_o_tipo_que_ja_existe(tmp_path,
                                                               monkeypatch):
    """A coleta por tipo nao pode ter afrouxado o invariante de data/raw/.

    Se o arquivo do tipo que falta ja existir com o nome computado -- uma
    coleta anterior interrompida, por exemplo -- baixar() continua parando em
    vez de sobrescrever.
    """
    _aplicar_dubles(monkeypatch)
    _criar_marcador(tmp_path, "bbg_taxas_ANDE_", M1, M3)
    _criar_marcador(tmp_path, "bbg_vna_", M1, M3)
    # O nome que o preco receberia, ja ocupado por um arquivo que NAO
    # reivindica cobrir o periodo (nome fora do padrao lido por
    # _meses_cobertos seria ignorado, entao usa-se o proprio nome-alvo).
    (tmp_path / "bbg_precos_ANDE_2023-01_2023-03.csv").write_text(
        "cabecalho\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="nada novo"):
        fetch_bloomberg.baixar(destino=tmp_path)


def test_as_datas_do_painel_falso_sao_os_ultimos_dias_uteis():
    # As tres datas do painel sintetico estao cravadas no topo do modulo, para
    # a coleta do pytest nao depender do calendario de feriados. Este teste e
    # quem mantem a afirmacao checada: onde o calendario existe, ele confere.
    #
    # Sem o calendario na maquina, ele falha com a frase que diz qual arquivo
    # baixar -- que e exatamente o que se quer numa instalacao nova.
    assert (M1, M2, M3) == (_fim_mes(2023, 1), _fim_mes(2023, 2),
                            _fim_mes(2023, 3))
