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


# ---------------------------------------------------------------------------
# A PLANILHA NAO REBAIXA SOZINHA, e a mensagem precisa dizer isso.
#
# Medido em 08/10/2026: baixar() imprimia "ja existe, nada a fazer" e voltava --
# baixa UMA vez e nunca mais. Com isso leiloes.csv ficou parado em 13/08 e a
# linha provisoria da API nao "some sozinha", como o programa prometia.
# ---------------------------------------------------------------------------

class _RespostaFalsa:
    def __init__(self, conteudo):
        self._conteudo = conteudo

    def read(self):
        return self._conteudo

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_a_planilha_que_ja_existe_FICA_e_a_mensagem_diz_como_renovar(
        tmp_path, capsys):
    from tesouro import config

    alvo = tmp_path / config.ARQUIVO_LEILOES
    alvo.write_bytes(b"planilha velha")
    assert fetch_leiloes.baixar(tmp_path) == alvo
    assert alvo.read_bytes() == b"planilha velha", "nao podia reescrever"
    saida = capsys.readouterr().out
    # A MENSAGEM TEM DE ENSINAR A RENOVAR. Sem isso o operador fica esperando
    # que a planilha ande sozinha, que e o que aconteceu.
    assert "--rebaixar-planilha" in saida, saida


# Bytes magicos de um .xls de verdade. PRECISAM ser estes: gravar_atomico
# confere a assinatura antes de gravar, porque o site do Tesouro devolve pagina
# de erro em HTML com status 200 -- ver gravacao.conferir_assinatura. A primeira
# versao deste teste usou b"planilha nova" e a guarda a recusou, o que e a
# guarda fazendo exatamente o trabalho dela.
_XLS = b"\xd0\xcf\x11\xe0"


def test_com_forcar_ela_REBAIXA(tmp_path, monkeypatch):
    # A porta de saida existe e funciona, sem tocar a rede.
    import json

    from tesouro import config

    alvo = tmp_path / config.ARQUIVO_LEILOES
    alvo.write_bytes(_XLS + b"velha")

    def urlopen_falso(url, timeout=0):
        if url == fetch_leiloes.API_CKAN:
            return _RespostaFalsa(json.dumps(RESPOSTA_CKAN).encode("utf-8"))
        return _RespostaFalsa(_XLS + b"nova")

    monkeypatch.setattr(fetch_leiloes.urllib.request, "urlopen", urlopen_falso)
    assert fetch_leiloes.baixar(tmp_path, forcar=True) == alvo
    assert alvo.read_bytes() == _XLS + b"nova"


def test_SEM_forcar_ela_nao_toca_a_rede(tmp_path, monkeypatch):
    # A guarda de idempotencia e o que faz a planilha nao ser rebaixada: com o
    # arquivo no lugar, nem o catalogo e consultado. Se um dia alguem tirar o
    # 'and not forcar' do lugar errado, este teste cai.
    from tesouro import config

    alvo = tmp_path / config.ARQUIVO_LEILOES
    alvo.write_bytes(_XLS + b"velha")

    def nao_pode(url, timeout=0):
        raise AssertionError("baixar() tocou a rede com o arquivo ja no lugar")

    monkeypatch.setattr(fetch_leiloes.urllib.request, "urlopen", nao_pode)
    assert fetch_leiloes.baixar(tmp_path) == alvo
