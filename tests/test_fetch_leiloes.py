import pytest
from tesouro import fetch_leiloes

RESPOSTA_CKAN = {
    "success": True,
    "result": {
        "resources": [
            {"name": "Metadados", "format": "PDF",
             "url": "https://exemplo/metadados.pdf"},
            {"name": "Todos os resultados dos leiloes da DPMFi", "format": "XLS",
             "url": "https://sisweb.tesouro.gov.br/apex/cosis/rleiloes/"
                    "arquivos/todos/desc/historico-leiloes-todos.xls"},
            {"name": "2024", "format": "XLS",
             "url": "https://sisweb.tesouro.gov.br/apex/cosis/rleiloes/"
                    "arquivos/unico/desc/historico-leiloes-2024.xlsx"},
        ]
    },
}


def test_url_do_historico_escolhe_o_arquivo_completo():
    url = fetch_leiloes.url_do_historico(RESPOSTA_CKAN)
    assert url.endswith("historico-leiloes-todos.xls")


def test_url_do_historico_falha_com_mensagem_clara_se_o_recurso_sumir():
    resposta = {"success": True, "result": {"resources": [
        {"name": "Metadados", "format": "PDF", "url": "https://exemplo/m.pdf"},
    ]}}
    with pytest.raises(LookupError, match="historico-leiloes-todos"):
        fetch_leiloes.url_do_historico(resposta)


def test_gravar_atomico_escreve_o_arquivo_final_com_o_conteudo_certo(tmp_path):
    caminho = tmp_path / "arquivo.xls"

    fetch_leiloes._gravar_atomico(b"conteudo de teste", caminho)

    assert caminho.read_bytes() == b"conteudo de teste"


def test_gravar_atomico_nao_deixa_part_para_tras_depois_do_sucesso(tmp_path):
    caminho = tmp_path / "arquivo.xls"

    fetch_leiloes._gravar_atomico(b"dados", caminho)

    assert not caminho.with_name(caminho.name + ".part").exists()


def test_gravar_atomico_sobrescreve_part_de_tentativa_anterior_truncada(tmp_path):
    caminho = tmp_path / "arquivo.xls"
    tmp = caminho.with_name(caminho.name + ".part")
    tmp.write_bytes(b"lixo de uma tentativa anterior que ficou pela metade")

    fetch_leiloes._gravar_atomico(b"dados novos e completos", caminho)

    assert caminho.read_bytes() == b"dados novos e completos"
    assert not tmp.exists()
