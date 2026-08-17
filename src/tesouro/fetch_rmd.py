"""Baixa o anexo (tabelas) do Relatorio Mensal da Divida.

O link do anexo tem um identificador numerico que muda a cada publicacao,
entao nao ha URL previsivel: e preciso abrir a pagina do mes e extrair o
link de la.

Este modulo nunca e necessario para rodar os parsers. Em ambiente sem
rede, basta colocar o .xlsx em data/raw/rmd/ na mao.
"""
import io
import re
import urllib.request
import zipfile
from pathlib import Path

from . import config
from .gravacao import gravar_atomico

BASE = (
    "https://www.tesourotransparente.gov.br/publicacoes/"
    "relatorio-mensal-da-divida-rmd"
)

# O anexo mora sob /publicacao-anexo/; o relatorio em PDF, sob /publicacao/.
_PADRAO_ANEXO = re.compile(
    r'href="(https?://[^"]*publicacao-anexo/\d+[^"]*)"', re.IGNORECASE
)

_CABECALHO = {"User-Agent": "projeto-tesouro/1.0"}


def url_da_publicacao(ano, mes):
    if not 1 <= mes <= 12:
        raise ValueError(f"mes fora do intervalo 1..12: {mes}")
    return f"{BASE}/{ano}/{mes}"


def link_do_anexo(html):
    """Extrai da pagina da publicacao o link do arquivo de anexo."""
    achado = _PADRAO_ANEXO.search(html)
    if not achado:
        raise LookupError(
            "nenhum link de anexo encontrado na pagina da publicacao; "
            "o layout do site pode ter mudado, ou o anexo daquele mes "
            "ainda nao foi publicado"
        )
    return achado.group(1)


def _baixar_bytes(url, timeout=300):
    requisicao = urllib.request.Request(url, headers=_CABECALHO)
    with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:
        return resposta.read()


def baixar(ano, mes, destino=None):
    """Baixa o anexo do mes e devolve o caminho do .xlsx salvo.

    Se o anexo vier compactado, extrai a primeira planilha do zip.
    """
    destino = Path(destino) if destino else config.RMD_DIR
    destino.mkdir(parents=True, exist_ok=True)

    pagina = _baixar_bytes(url_da_publicacao(ano, mes), timeout=60)
    url = link_do_anexo(pagina.decode("utf-8", errors="ignore"))
    print(f"baixando {url}")
    conteudo = _baixar_bytes(url)

    if conteudo[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(conteudo)) as zf:
            planilhas = [n for n in zf.namelist() if n.lower().endswith(".xlsx")]
            if not planilhas:
                raise LookupError(
                    f"o anexo de {mes}/{ano} nao contem .xlsx; "
                    f"encontrado: {zf.namelist()}"
                )
            nome = planilhas[0]
            caminho = destino / Path(nome).name
            gravar_atomico(zf.read(nome), caminho)
    else:
        caminho = destino / f"Anexo RMD_{ano}_{mes:02d}.xlsx"
        gravar_atomico(conteudo, caminho)

    print(f"salvo em {caminho} ({caminho.stat().st_size / 1e6:.1f} MB)")
    return caminho


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        sys.exit("uso: python -m tesouro.fetch_rmd <ano> <mes>")
    baixar(int(sys.argv[1]), int(sys.argv[2]))
