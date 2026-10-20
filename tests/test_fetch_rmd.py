import io
import zipfile

import pytest
from tesouro import fetch_rmd

HTML = """
<html><body>
  <a href="https://thot-arquivos.tesouro.gov.br/publicacao/53999">
     Relatorio Mensal da Divida - Junho de 2026</a>
  <a href="https://thot-arquivos.tesouro.gov.br/publicacao-anexo/54001">
     Anexo RMD_Junho_26.zip</a>
  <a href="/publicacoes/outra-coisa">Outro link</a>
</body></html>
"""


def test_url_da_publicacao_monta_o_caminho_do_mes():
    url = fetch_rmd.url_da_publicacao(2026, 6)
    assert url.endswith("/relatorio-mensal-da-divida-rmd/2026/6")


def test_link_do_anexo_prefere_o_anexo_e_nao_o_relatorio():
    assert fetch_rmd.link_do_anexo(HTML).endswith("publicacao-anexo/54001")


def test_link_do_anexo_falha_com_mensagem_clara_quando_nao_ha_anexo():
    html = '<html><body><a href="/nada">nada</a></body></html>'
    with pytest.raises(LookupError, match="anexo"):
        fetch_rmd.link_do_anexo(html)


def test_url_da_publicacao_rejeita_mes_invalido():
    with pytest.raises(ValueError):
        fetch_rmd.url_da_publicacao(2026, 13)


XLSX_FALSO = b"PK\x03\x04 planilha de mentira, mas com a assinatura certa"


def _zip_com(nomes):
    """Um zip em memoria, para exercitar o ramo do anexo compactado."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for nome in nomes:
            zf.writestr(nome, XLSX_FALSO)
    return buffer.getvalue()


def _respostas(monkeypatch, *conteudos):
    """Faz _baixar_bytes devolver os conteudos dados, em ordem, sem rede."""
    fila = list(conteudos)

    def _falso(url, timeout=None):
        return fila.pop(0)

    monkeypatch.setattr(fetch_rmd, "_baixar_bytes", _falso)


def test_baixar_extrai_o_xlsx_de_dentro_do_zip(tmp_path, monkeypatch):
    """O ramo do zip e onde o nome do arquivo vem de fora do codigo."""
    _respostas(
        monkeypatch,
        HTML.encode("utf-8"),
        _zip_com(["leiame.txt", "tabelas/Anexo RMD_Junho_26.xlsx"]),
    )

    caminho = fetch_rmd.baixar(2026, 6, destino=tmp_path)

    # Fica so o nome base: o caminho interno do zip nao vira subpasta.
    assert caminho == tmp_path / "Anexo RMD_Junho_26.xlsx"
    assert caminho.read_bytes() == XLSX_FALSO


def test_baixar_falha_quando_o_zip_nao_tem_xlsx(tmp_path, monkeypatch):
    _respostas(
        monkeypatch, HTML.encode("utf-8"), _zip_com(["leiame.txt", "anexo.pdf"])
    )

    with pytest.raises(LookupError, match="nao contem .xlsx"):
        fetch_rmd.baixar(2026, 6, destino=tmp_path)

    assert not list(tmp_path.iterdir())


def test_baixar_nao_sobrescreve_o_xlsx_extraido_do_zip(tmp_path, monkeypatch):
    """A guarda do C1 tambem vale no ramo do zip.

    La o nome so e conhecido depois do download, entao a checagem tem que
    acontecer entre a extracao e a escrita -- e nao antes da rede, como no
    ramo do nome deterministico.
    """
    ja_existe = tmp_path / "Anexo RMD_Junho_26.xlsx"
    ja_existe.write_bytes(b"PK\x03\x04 o anexo original")
    _respostas(
        monkeypatch, HTML.encode("utf-8"), _zip_com(["Anexo RMD_Junho_26.xlsx"])
    )

    assert fetch_rmd.baixar(2026, 6, destino=tmp_path) == ja_existe
    assert ja_existe.read_bytes() == b"PK\x03\x04 o anexo original"


def test_baixar_recusa_pagina_de_erro_no_lugar_do_anexo(tmp_path, monkeypatch):
    """Status 200 com HTML no corpo nao pode virar um .xlsx em data/raw/."""
    _respostas(
        monkeypatch,
        HTML.encode("utf-8"),
        b"<!DOCTYPE html><html><body>erro</body></html>",
    )

    with pytest.raises(ValueError, match="pagina de erro"):
        fetch_rmd.baixar(2026, 6, destino=tmp_path)

    assert not list(tmp_path.iterdir())


def test_baixar_nao_sobrescreve_anexo_ja_existente(tmp_path, monkeypatch):
    """data/raw/ e imutavel: rodar o mesmo mes duas vezes nao pode destruir
    o primeiro download. A guarda tem que agir antes da rede.
    """
    ja_existe = tmp_path / fetch_rmd._nome_previsto(2026, 6)
    ja_existe.write_bytes(b"PK\x03\x04 o anexo original")

    def _proibido(*args, **kwargs):
        raise AssertionError("nao deveria ter acessado a rede")

    monkeypatch.setattr(fetch_rmd, "_baixar_bytes", _proibido)

    assert fetch_rmd.baixar(2026, 6, destino=tmp_path) == ja_existe
    assert ja_existe.read_bytes() == b"PK\x03\x04 o anexo original"


# ---------------------------------------------------------------------------
# A TRAVA DA REDE DO BANCO, medida em 20/10/2026 tentando o anexo de setembro:
#
#     URLError: <urlopen error [WinError 10054] Foi forcado o cancelamento de
#     uma conexao existente pelo host remoto>
#
# O tradutor so reconhecia CERTIFICATE e SSL, entao este caso vazava o erro cru
# e a pessoa recebia pilha no lugar da instrucao -- no comando que o README e o
# menu mandam rodar.
# ---------------------------------------------------------------------------

URL = "https://www.tesourotransparente.gov.br/publicacoes/x"


def test_conexao_derrubada_vira_frase_com_o_caminho_a_mao():
    import urllib.error

    erro = urllib.error.URLError(OSError(10054, "cancelamento da conexao"))
    r = fetch_rmd._traduzir_erro_de_rede(URL, erro)

    assert isinstance(r, LookupError), "o erro cru voltou a vazar"
    texto = str(r)
    assert "CAMINHO A MAO" in texto
    assert "data/raw/rmd/" in texto
    assert fetch_rmd.BASE in texto, "a frase tem de dar o endereco do site"
    # E NAO PODE MANDAR MEXER NO CERTIFICADO: conexao derrubada nao se resolve
    # com SSL_CERT_FILE, e apontar para la manda a pessoa para o lugar errado.
    assert "SSL_CERT_FILE" not in texto


def test_erro_de_certificado_continua_ganhando_a_orientacao_do_SSL():
    import urllib.error

    erro = urllib.error.URLError(
        "[SSL: CERTIFICATE_VERIFY_FAILED] unable to get local issuer")
    texto = str(fetch_rmd._traduzir_erro_de_rede(URL, erro))
    assert "SSL_CERT_FILE" in texto, "a orientacao do certificado se perdeu"
    assert "CAMINHO A MAO" in texto
    # A REGRA DELA: nunca sugerir desligar a verificacao.
    assert "desligar a verifica" not in texto.lower()


def test_o_que_NAO_e_de_rede_continua_subindo_como_esta():
    # Esconder defeito de codigo sob frase amavel e pior que o traceback: ele
    # passaria a parecer problema de rede do banco.
    erro = ValueError("defeito de verdade")
    assert fetch_rmd._traduzir_erro_de_rede(URL, erro) is erro


def test_404_diz_que_o_MES_NAO_SAIU_e_nao_culpa_a_rede():
    # Medido em 20/10/2026: a pagina de agosto responde 200 com o link do
    # anexo, e a de setembro da 404 -- o RMD de setembro nao estava publicado.
    # A rede chegou la; dizer "a conexao nao completou" seria afirmar o que o
    # programa nao sabe, e mandaria ela investigar proxy por nada.
    import urllib.error

    erro = urllib.error.HTTPError(URL, 404, "Not Found", {}, None)
    texto = str(fetch_rmd._traduzir_erro_de_rede(URL, erro))

    assert "404" in texto
    assert "ainda nao saiu" in texto
    assert "CONEXAO NAO COMPLETOU" not in texto, \
        "404 nao e falha de conexao"
    assert "proxy" not in texto, "nao mandar investigar a rede por um 404"
    # E O CAMINHO A MAO CONTINUA, porque e o que resolve quando o mes saiu.
    assert "CAMINHO A MAO" in texto


def test_outro_codigo_HTTP_diz_o_codigo_sem_inventar_a_causa():
    import urllib.error

    erro = urllib.error.HTTPError(URL, 503, "Service Unavailable", {}, None)
    texto = str(fetch_rmd._traduzir_erro_de_rede(URL, erro))
    assert "503" in texto
    assert "ainda nao saiu" not in texto, "503 nao e mes que nao saiu"
