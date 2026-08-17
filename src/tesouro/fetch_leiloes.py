"""Baixa o historico completo de leiloes da DPMFi.

A URL vem da API do CKAN, nao fixada no codigo: se o Tesouro reorganizar
os arquivos, a API acompanha e o coletor continua funcionando.

Este modulo nunca e necessario para rodar os parsers. Em ambiente sem
rede, basta colocar o arquivo em data/raw/leiloes/ na mao.
"""
import json
import urllib.request
from pathlib import Path

from . import config
from .gravacao import gravar_atomico

API_CKAN = (
    "https://www.tesourotransparente.gov.br/ckan/api/3/action/"
    "package_show?id=ds013"
)

_NOME_DO_RECURSO = "historico-leiloes-todos"


def url_do_historico(resposta_ckan):
    """Extrai a URL do arquivo unico com todo o historico desde 2000."""
    recursos = resposta_ckan.get("result", {}).get("resources", [])
    for recurso in recursos:
        url = recurso.get("url", "")
        if _NOME_DO_RECURSO in url:
            return url
    raise LookupError(
        f"nenhum recurso contendo {_NOME_DO_RECURSO!r} foi encontrado na "
        f"resposta do CKAN; o dataset ds013 pode ter sido reorganizado"
    )


def baixar(destino=None):
    """Baixa o historico e devolve o caminho do arquivo salvo."""
    destino = Path(destino) if destino else config.LEILOES_DIR
    destino.mkdir(parents=True, exist_ok=True)
    caminho = destino / config.ARQUIVO_LEILOES

    if caminho.exists():
        print(f"ja existe, nada a fazer: {caminho}")
        return caminho

    with urllib.request.urlopen(API_CKAN, timeout=60) as resposta:
        dados = json.loads(resposta.read().decode("utf-8"))

    url = url_do_historico(dados)
    print(f"baixando {url}")
    with urllib.request.urlopen(url, timeout=300) as resposta:
        conteudo = resposta.read()
    gravar_atomico(conteudo, caminho)

    print(f"salvo em {caminho} ({caminho.stat().st_size / 1e6:.1f} MB)")
    return caminho


if __name__ == "__main__":
    baixar()
