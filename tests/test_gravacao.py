import pytest
from tesouro.gravacao import conferir_assinatura, gravar_atomico

# Bytes iniciais de um .xls legado (OLE2) e de um .xlsx (zip).
XLS = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"resto do arquivo"
XLSX = b"PK\x03\x04" + b"resto do arquivo"

# O que o site do Tesouro devolve quando algo da errado -- com status 200.
HTML_DE_ERRO = b"<!DOCTYPE html><html><body>Servico indisponivel</body></html>"


def test_gravar_atomico_escreve_o_arquivo_final_com_o_conteudo_certo(tmp_path):
    caminho = tmp_path / "arquivo.xls"

    gravar_atomico(XLS, caminho)

    assert caminho.read_bytes() == XLS


def test_gravar_atomico_nao_deixa_part_para_tras_depois_do_sucesso(tmp_path):
    caminho = tmp_path / "arquivo.xls"

    gravar_atomico(XLS, caminho)

    assert not caminho.with_name(caminho.name + ".part").exists()


def test_gravar_atomico_sobrescreve_part_de_tentativa_anterior_truncada(tmp_path):
    caminho = tmp_path / "arquivo.xls"
    tmp = caminho.with_name(caminho.name + ".part")
    tmp.write_bytes(b"lixo de uma tentativa anterior que ficou pela metade")

    gravar_atomico(XLS + b" completo", caminho)

    assert caminho.read_bytes() == XLS + b" completo"
    assert not tmp.exists()


def test_gravar_atomico_recusa_pagina_de_erro_no_lugar_de_xls(tmp_path):
    """Pagina de erro HTML com status 200 nao pode virar um .xls.

    Se virar, a guarda de idempotencia dos coletores responde 'ja existe,
    nada a fazer' para sempre e o arquivo ruim fica permanente.
    """
    caminho = tmp_path / "historico-leiloes-todos.xls"

    with pytest.raises(ValueError, match="pagina de erro"):
        gravar_atomico(HTML_DE_ERRO, caminho)

    assert not caminho.exists()
    assert not caminho.with_name(caminho.name + ".part").exists()


def test_gravar_atomico_recusa_pagina_de_erro_no_lugar_de_xlsx(tmp_path):
    caminho = tmp_path / "Anexo RMD_2026_06.xlsx"

    with pytest.raises(ValueError, match="pagina de erro"):
        gravar_atomico(HTML_DE_ERRO, caminho)

    assert not caminho.exists()


def test_gravar_atomico_nao_destroi_arquivo_bom_ao_recusar(tmp_path):
    """A recusa vem antes de qualquer escrita, inclusive do .part."""
    caminho = tmp_path / "arquivo.xls"
    caminho.write_bytes(XLS)

    with pytest.raises(ValueError):
        gravar_atomico(HTML_DE_ERRO, caminho)

    assert caminho.read_bytes() == XLS


def test_gravar_atomico_recusa_xls_legado_gravado_como_xlsx(tmp_path):
    # Formatos trocados: um .xls legado nao e um .xlsx, e vice-versa.
    with pytest.raises(ValueError):
        gravar_atomico(XLS, tmp_path / "planilha.xlsx")
    with pytest.raises(ValueError):
        gravar_atomico(XLSX, tmp_path / "planilha.xls")


def test_conferir_assinatura_ignora_extensao_desconhecida(tmp_path):
    # Nao e papel desta funcao impedir que outro coletor grave outro
    # formato por aqui.
    conferir_assinatura(b"qualquer coisa", tmp_path / "referencia.csv")
