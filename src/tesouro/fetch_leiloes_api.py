"""Busca os leiloes do dia na API do portal de dados abertos do Tesouro.

Segue o mesmo desenho do fetch_leiloes: a URL vem da API do CKAN e nao esta fixada
no codigo, entao reorganizacao de arquivo no portal nao quebra o coletor.

DUAS CAMADAS, de proposito:

  - `baixar()` guarda a resposta CRUA em data/raw/leiloes_api/, com a data no nome.
    A API e um alvo movel; a planilha e o registro. Guardar o que ela disse, no dia
    em que disse, e o que torna o pipeline reproduzivel depois -- e o que permite
    reprocessar sem depender de a API ainda responder o mesmo;
  - `normalizar()` traduz o que foi guardado para o esquema do leiloes.csv, e nao
    toca na rede. Da para desenvolver e testar sem conexao nenhuma.

Este modulo NUNCA e necessario para rodar os parsers. Sem rede, o pipeline continua
funcionando com a planilha -- e os graficos de leilao ficam com o dado de ontem, que
e exatamente o que eles tinham antes de este arquivo existir.

CERTIFICADO. Numa rede que inspeciona TLS -- e a de um banco inspeciona -- o Python
recusa a conexao com CERTIFICATE_VERIFY_FAILED, porque nao conhece a autoridade que
assinou o certificado do proxy. A saida NAO e desligar a verificacao: e apontar o
Python para o pacote de certificados da instituicao, com a variavel SSL_CERT_FILE.
A mensagem de erro deste modulo diz isso, porque o traceback cru do ssl nao diz.
"""
import datetime
import json
import ssl
import urllib.error
import urllib.request
from pathlib import Path

from . import config
from .gravacao import gravar_atomico

API_CKAN = (
    "https://www.tesourotransparente.gov.br/ckan/api/3/action/"
    "package_show?id=ds013"
)

# O diretorio das respostas cruas. Fica em data/raw/ porque e material coletado, e
# vale a mesma regra do resto de raw: nada aqui e reescrito nem apagado.
PASTA = "leiloes_api"

_ERRO_DE_CERTIFICADO = (
    "a conexao com o portal do Tesouro falhou na verificacao do certificado.\n"
    "\n"
    "Numa rede que inspeciona TLS (a de um banco inspeciona), o certificado que\n"
    "chega e o do proxy, e o Python nao conhece a autoridade que o assinou.\n"
    "\n"
    "NAO desligue a verificacao. Aponte o Python para o pacote de certificados da\n"
    "instituicao:\n"
    "\n"
    '    PowerShell:  $env:SSL_CERT_FILE = "C:\\caminho\\para\\ca-bundle.crt"\n'
    "    bash:        export SSL_CERT_FILE=/caminho/para/ca-bundle.crt\n"
    "\n"
    "O arquivo costuma vir da equipe de infraestrutura. Sem ele, este coletor nao\n"
    "roda -- e o pipeline continua funcionando com a planilha, um dia atrasado."
)


def _abrir(url, timeout=45):
    """urlopen com a mensagem de certificado traduzida."""
    try:
        return urllib.request.urlopen(url, timeout=timeout)
    except urllib.error.URLError as erro:
        if isinstance(getattr(erro, "reason", None), ssl.SSLCertVerificationError):
            raise ConnectionError(_ERRO_DE_CERTIFICADO) from erro
        raise


def recursos_do_dataset(url=API_CKAN):
    """A lista de recursos do dataset ds013, como o CKAN os descreve.

    Devolve dicionarios com pelo menos 'name', 'url', 'format' e 'last_modified'.
    Serve para descobrir QUAL recurso traz o resultado do dia -- coisa que so da
    para saber olhando a resposta real, e por isso esta funcao existe separada.
    """
    with _abrir(url) as resposta:
        dados = json.load(resposta)
    recursos = dados.get("result", {}).get("resources", [])
    if not recursos:
        raise LookupError(
            f"o dataset em {url} nao listou recurso nenhum; ele pode ter sido "
            f"reorganizado ou renomeado no portal"
        )
    return recursos


def baixar(url_do_recurso, destino=None, quando=None):
    """Guarda a resposta crua de um recurso, com a data no nome.

    Nao interpreta nada: o que chega vai para o disco como veio. Devolve o caminho.
    """
    quando = quando or datetime.date.today()
    destino = Path(destino) if destino else (config.RAW_DIR / PASTA)
    destino.mkdir(parents=True, exist_ok=True)

    sufixo = url_do_recurso.rsplit(".", 1)[-1].lower()
    if sufixo not in ("json", "csv", "xls", "xlsx"):
        sufixo = "json"
    caminho = destino / f"leiloes-{quando.isoformat()}.{sufixo}"

    with _abrir(url_do_recurso) as resposta:
        conteudo = resposta.read()
    gravar_atomico(conteudo, caminho)
    return caminho
