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

