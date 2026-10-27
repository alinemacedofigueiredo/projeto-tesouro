"""O dolar dos e-mails de leilao (src/tesouro/fetch_cambio.py).

O QUE ESTES TESTES EXISTEM PARA DEFENDER e uma frase dela, de 27/10/2026:
"lembra de salvar esses numeros convertidos, pq dps o dolar muda e nao queremos
mudar a serie para tras".

O jeito de quebrar isso nao e exotico. E uma rodada repetida no dia seguinte,
quando a PTAX que faltava ja existe: sem a guarda, a taxa do leilao de ontem
seria trocada pela de hoje e a serie andaria sozinha. Por isso o teste central
daqui nao mede "gravou certo" -- mede QUE NAO REGRAVOU.

NENHUM TESTE DESTE ARQUIVO TOCA A REDE: todos trocam fetch_cambio._abrir por
uma funcao que devolve JSON de mentira, e um deles troca por uma que explode se
for chamada, que e a unica forma de provar "nao buscou".
"""
import datetime as dt
import io
import json

import pytest

from tesouro import fetch_cambio


_DIA = dt.date(2026, 10, 20)


class _Resposta(io.BytesIO):
    """O minimo que urlopen devolve e que o modulo usa: read() e with."""

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
        return False


def _ptax(dia, venda, hora="13:03:28.123"):
    return {"value": [{"cotacaoCompra": venda - 0.0006,
                       "cotacaoVenda": venda,
                       "dataHoraCotacao": "%s %s" % (dia, hora)}]}


def _rede_falsa(por_data, visitadas=None):
    """Um _abrir que responde pela data que esta na URL."""
    def abrir(url, timeout=None):
        # A data vai na URL como MM-DD-AAAA, entre aspas codificadas (%27).
        pedaco = url.split("%27")[1]
        mes, dia, ano = pedaco.split("-")
        chave = "%s-%s-%s" % (ano, mes, dia)
        if visitadas is not None:
            visitadas.append(chave)
        return _Resposta(json.dumps(por_data.get(chave, {"value": []}))
                         .encode("utf-8"))
    return abrir


def _sem_bloomberg(monkeypatch):
    """Nenhum teste daqui pode depender de ter terminal na maquina."""
    def nao(*_a, **_k):
        raise ImportError("sem blpapi nesta maquina")
    monkeypatch.setattr(fetch_cambio, "_do_bloomberg", nao)


# ---------------------------------------------------------------- a guarda


def test_a_SEGUNDA_rodada_NAO_REGRAVA_e_NAO_BUSCA(monkeypatch, tmp_path):
    """O coracao do modulo: a serie nao anda para tras.

    Primeiro grava com a PTAX de 19/10, que e o que existe as 10:45. Depois
    simula o dia seguinte, quando a PTAX de 20/10 ja saiu -- e exige que o
    arquivo continue dizendo 19/10 e que a rede nem seja consultada.
    """
    _sem_bloomberg(monkeypatch)
    monkeypatch.setattr(fetch_cambio, "_abrir",
                        _rede_falsa({"2026-10-19": _ptax("2026-10-19", 5.0564)}))
    caminho, primeiro = fetch_cambio.guardar(_DIA, destino=tmp_path)
    assert primeiro["taxa"] == 5.0564
    assert primeiro["data_da_cotacao"] == "2026-10-19"
    bytes_do_primeiro = caminho.read_bytes()

    def explode(*_a, **_k):
        raise AssertionError("buscou a rede numa rodada que ja tinha arquivo")
    monkeypatch.setattr(fetch_cambio, "_abrir", explode)

    de_novo, segundo = fetch_cambio.guardar(_DIA, destino=tmp_path)
    assert segundo["taxa"] == 5.0564
    assert segundo["data_da_cotacao"] == "2026-10-19"
    assert de_novo.read_bytes() == bytes_do_primeiro, "o arquivo foi reescrito"


def test_do_disco_NAO_TOCA_A_REDE_nem_quando_falta_arquivo(monkeypatch,
                                                           tmp_path):
    def explode(*_a, **_k):
        raise AssertionError("quem le do disco nao pode buscar")
    monkeypatch.setattr(fetch_cambio, "_abrir", explode)
    assert fetch_cambio.do_disco(_DIA, destino=tmp_path) is None


# ------------------------------------------------------------ o que grava


def test_o_arquivo_e_nomeado_pelo_DIA_DO_LEILAO_e_nao_pelo_da_cotacao(
        monkeypatch, tmp_path):
    """A pergunta e 'qual dolar aquele e-mail usou', entao o nome e do leilao."""
    _sem_bloomberg(monkeypatch)
    monkeypatch.setattr(fetch_cambio, "_abrir",
                        _rede_falsa({"2026-10-19": _ptax("2026-10-19", 5.0564)}))
    caminho, registro = fetch_cambio.guardar(_DIA, destino=tmp_path)
    assert caminho.name == "dolar-2026-10-20.json"
    assert registro["data_da_cotacao"] == "2026-10-19"
    assert registro["data_do_leilao"] == "2026-10-20"


def test_o_registro_diz_a_FONTE_e_a_HORA(monkeypatch, tmp_path):
    """Numero sem procedencia e o defeito que este projeto persegue."""
    _sem_bloomberg(monkeypatch)
    monkeypatch.setattr(fetch_cambio, "_abrir",
                        _rede_falsa({"2026-10-19": _ptax("2026-10-19", 5.0564)}))
    _caminho, registro = fetch_cambio.guardar(_DIA, destino=tmp_path)
    assert registro["fonte"] == "PTAX"
    assert registro["hora_da_cotacao"] == "13:03:28.123"
    assert "buscado_em" in registro


def test_o_que_foi_gravado_e_o_que_do_disco_devolve(monkeypatch, tmp_path):
    _sem_bloomberg(monkeypatch)
    monkeypatch.setattr(fetch_cambio, "_abrir",
                        _rede_falsa({"2026-10-19": _ptax("2026-10-19", 5.0564)}))
    _caminho, gravado = fetch_cambio.guardar(_DIA, destino=tmp_path)
    assert fetch_cambio.do_disco(_DIA, destino=tmp_path) == gravado


# ------------------------------------------------------- andar para tras


def test_as_10h45_a_PTAX_DO_DIA_nao_existe_e_ele_pega_a_VESPERA(monkeypatch,
                                                                tmp_path):
    """O caso normal, e nao a excecao: a PTAX so e fixada por volta das 13h."""
    _sem_bloomberg(monkeypatch)
    visitadas = []
    monkeypatch.setattr(
        fetch_cambio, "_abrir",
        _rede_falsa({"2026-10-19": _ptax("2026-10-19", 5.0564)}, visitadas))
    _caminho, registro = fetch_cambio.guardar(_DIA, destino=tmp_path)
    assert visitadas[0] == "2026-10-20", "nem tentou o dia do leilao"
    assert registro["data_da_cotacao"] == "2026-10-19"


def test_depois_de_FERIADO_ele_anda_mais_de_um_dia(monkeypatch, tmp_path):
    _sem_bloomberg(monkeypatch)
    visitadas = []
    monkeypatch.setattr(
        fetch_cambio, "_abrir",
        _rede_falsa({"2026-10-15": _ptax("2026-10-15", 5.0521)}, visitadas))
    _caminho, registro = fetch_cambio.guardar(_DIA, destino=tmp_path)
    assert registro["data_da_cotacao"] == "2026-10-15"
    assert visitadas == ["2026-10-20", "2026-10-19", "2026-10-18",
                         "2026-10-17", "2026-10-16", "2026-10-15"]


def test_sem_cotacao_em_dia_nenhum_ele_LEVANTA_em_vez_de_inventar(monkeypatch,
                                                                  tmp_path):
    _sem_bloomberg(monkeypatch)
    monkeypatch.setattr(fetch_cambio, "_abrir", _rede_falsa({}))
    with pytest.raises(LookupError):
        fetch_cambio.guardar(_DIA, destino=tmp_path)
    assert not list(tmp_path.glob("*.json")), "gravou arquivo sem cotacao"


# ------------------------------------------------------- BBG antes da PTAX


def test_a_BLOOMBERG_vem_PRIMEIRO_quando_responde(monkeypatch, tmp_path):
    monkeypatch.setattr(fetch_cambio, "_do_bloomberg", lambda: {
        "taxa": 5.0412, "fonte": "BBG",
        "data_da_cotacao": "2026-10-20", "hora_da_cotacao": "10:42:00"})

    def explode(*_a, **_k):
        raise AssertionError("foi na PTAX com a Bloomberg respondendo")
    monkeypatch.setattr(fetch_cambio, "_abrir", explode)

    _caminho, registro = fetch_cambio.guardar(_DIA, destino=tmp_path)
    assert registro["fonte"] == "BBG"
    assert registro["taxa"] == 5.0412
    assert registro["data_da_cotacao"] == "2026-10-20"


def test_terminal_fechado_CAI_NA_PTAX_e_registra_o_motivo(monkeypatch,
                                                          tmp_path):
    """Cair na PTAX e o combinado; cair em silencio nao e."""
    def fechado():
        raise ConnectionError("nao foi possivel falar com o terminal")
    monkeypatch.setattr(fetch_cambio, "_do_bloomberg", fechado)
    monkeypatch.setattr(fetch_cambio, "_abrir",
                        _rede_falsa({"2026-10-19": _ptax("2026-10-19", 5.0564)}))

    _caminho, registro = fetch_cambio.guardar(_DIA, destino=tmp_path)
    assert registro["fonte"] == "PTAX"
    assert "terminal" in registro["bloomberg_falhou"]


def test_com_a_PORTA_FECHADA_ele_nem_chega_a_pedir_sessao(monkeypatch):
    """A desistencia rapida, que nao e enfeite.

    MEDIDO EM 27/10/2026 nesta maquina, onde o blpapi ESTA instalado e o
    terminal NAO esta aberto -- que e exatamente o estado da maquina dela fora
    do horario: pedir a sessao custava 100 s com as opcoes de fetch_bloomberg,
    e 18 s mesmo com uma tentativa so e timeout de 2 s. A biblioteca retenta
    por baixo. Um connect de TCP responde a mesma pergunta em 0,4 s.

    O teste nao mede TEMPO, que seria instavel: mede que a decisao e tomada
    ANTES, no aperto de mao, e que o motivo chega a quem le.
    """
    monkeypatch.setattr(fetch_cambio, "_terminal_atende", lambda *a, **k: False)

    def nao_deveria(*_a, **_k):
        raise AssertionError("pediu sessao com a porta fechada")
    monkeypatch.setattr(fetch_cambio, "ESPERA_DO_TERMINAL_MS", 1)

    import builtins
    de_verdade = builtins.__import__

    def importa(nome, *resto):
        if nome == "blpapi":
            nao_deveria()
        return de_verdade(nome, *resto)
    monkeypatch.setattr(builtins, "__import__", importa)

    with pytest.raises(ConnectionError) as erro:
        fetch_cambio._do_bloomberg()
    assert "atendendo" in str(erro.value)


def test_sem_blpapi_instalado_tambem_cai_na_PTAX(monkeypatch, tmp_path):
    """O ambiente de destino e maquina sem terminal; isto nao pode estourar."""
    _sem_bloomberg(monkeypatch)
    monkeypatch.setattr(fetch_cambio, "_abrir",
                        _rede_falsa({"2026-10-19": _ptax("2026-10-19", 5.0564)}))
    _caminho, registro = fetch_cambio.guardar(_DIA, destino=tmp_path)
    assert registro["fonte"] == "PTAX"
    assert "ImportError" in registro["bloomberg_falhou"]


# ------------------------------------------------------------ certificado


def test_erro_de_certificado_traz_a_orientacao_UNICA_do_projeto(monkeypatch):
    """Nao basta "tem SSL_CERT_FILE": tem de ser A orientacao, e nao outra.

    A primeira versao deste teste procurava "desligue a verificacao" como
    frase proibida e reprovava a mensagem CERTA, que diz "NAO desligue a
    verificacao" -- o mesmo tropeco que test_certificado.py ja registra no
    proprio comentario. O conserto nao foi afrouxar o filtro: foi parar de
    escrever mensagem propria aqui e passar a chamar certificado.orientacao,
    que ja tem teste e sabe dizer quem assinou.
    """
    import ssl as _ssl
    import urllib.error

    from tesouro import certificado

    def falha_de_certificado(*_a, **_k):
        raise urllib.error.URLError(
            _ssl.SSLCertVerificationError("certificate verify failed"))

    monkeypatch.setattr(fetch_cambio.urllib.request, "urlopen",
                        falha_de_certificado)
    monkeypatch.setattr(certificado, "quem_assinou",
                        lambda *a, **k: "AC SERPRO AR46 OV TLS CA 2025")

    with pytest.raises(ConnectionError) as erro:
        fetch_cambio._abrir("https://olinda.bcb.gov.br/qualquer")

    texto = str(erro.value)
    assert "SSL_CERT_FILE" in texto
    assert "AC SERPRO AR46 OV TLS CA 2025" in texto, "nao disse quem assinou"
    assert "NAO desligue a verificacao" in texto
    for tentacao in ("verify=false", "cert_none", "insecure",
                     "_create_unverified"):
        assert tentacao not in texto.lower(), (
            "a mensagem sugere %r" % tentacao)


def test_erro_de_rede_COMUM_nao_fala_de_certificado(monkeypatch):
    """Rede fora nao e certificado, e mandar apontar SSL_CERT_FILE ali manda a
    pessoa consertar o que nao esta quebrado -- a mesma licao de test_fetch_rmd.
    """
    import urllib.error

    def sem_rede(*_a, **_k):
        raise urllib.error.URLError("conexao recusada")

    monkeypatch.setattr(fetch_cambio.urllib.request, "urlopen", sem_rede)
    with pytest.raises(ConnectionError) as erro:
        fetch_cambio._abrir("https://olinda.bcb.gov.br/qualquer")
    assert "SSL_CERT_FILE" not in str(erro.value)
