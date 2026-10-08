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


def baixar(destino=None, forcar=False):
    """Baixa o historico e devolve o caminho do arquivo salvo.

    BAIXA UMA VEZ E PARA, por desenho: a planilha tem dezenas de megabytes e o
    que ela traz de novo a cada mes o provisorio da API ja cobre (ver
    rolagem.leiloes, que mescla os dois pela ultima liquidacao da planilha).

    MAS ISSO TEM UM PRECO QUE FICOU ESCONDIDO, achado em 08/10/2026: como ela
    nunca era rebaixada, leiloes.csv ficou parado em 13/08 e o conjunto
    provisorio so crescia -- e o programa ainda PROMETIA ao operador que a linha
    provisoria "some sozinha quando a planilha trouxer este leilao". Nao sumia,
    porque a planilha nao vinha. A promessa saiu (ver leilao_do_dia) e aqui ficou
    a porta: 'forcar', ou --rebaixar-planilha no pipeline.

    'forcar' SOBRESCREVE um arquivo de data/raw, que e imutavel por invariante
    do projeto -- por isso e explicito, e nunca o padrao.
    """
    destino = Path(destino) if destino else config.LEILOES_DIR
    destino.mkdir(parents=True, exist_ok=True)
    caminho = destino / config.ARQUIVO_LEILOES

    if caminho.exists() and not forcar:
        print(f"ja existe, e fica: {caminho}")
        print("   Ela NAO e rebaixada sozinha. O provisorio da API cobre o que "
              "falta; para renovar a planilha, rode com --rebaixar-planilha.")
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
