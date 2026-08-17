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
