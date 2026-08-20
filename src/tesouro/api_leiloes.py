"""A API de leiloes do Tesouro (apiapex), que e melhor que tudo o que veio antes.

DESCOBERTA DE 20/08/2026. O projeto vinha tentando o portal de dados abertos (CKAN,
em tesourotransparente.gov.br) e batendo em CERTIFICATE_VERIFY_FAILED, porque a rede
desta maquina inspeciona TLS. O apiapex e outro host, e ELE RESPONDE -- conferido do
mesmo Python, na mesma rede, no mesmo minuto em que o CKAN falhava.

Isso muda o desenho: o caminho automatico volta a existir, e o arquivo salvo a mao
deixa de ser a via principal para virar o plano B que sempre deveria ter sido.

O QUE CADA ENDPOINT DA, medido em 20/08/2026:

  editais       6 registros    a oferta do DIA, por benchmark, a partir das 10h30
  calendario   60 registros    o que o Tesouro PLANEJA ofertar, ate ~40 dias a frente
  benchmarks   18 registros    o vertice de cada vencimento, com vigencia
  resultados 4598 registros    resultado por leilao desde 04/01/2018
  dealers     216 registros    instituicoes habilitadas, com periodo
  comunicados  42 registros    titulo e link
  portarias     6 registros    como editais, pela portaria

resultado_homologacao e BYTE A BYTE IGUAL a resultados -- mesmo conteudo em dois
nomes. Fica de fora para nao dar a impressao de serem duas fontes.

dealers_periodo estourou o tempo limite nas tentativas de 20/08/2026. Fica de fora
ate se saber se e lentidao permanente.

O QUE FOI CONFERIDO ANTES DE CONFIAR:

  contra a planilha do Tesouro -- 3.912 leiloes cruzados por (data, titulo,
  vencimento), primeira volta, venda: quantidade aceita, financeiro e oferta batem
  em TODOS, com zero divergencias acima de 0,1%;

  a coerencia interna do proprio dado -- pu_medio x quantidade_aceita reproduz
  financeiro_aceito com razao 1,000000 nas 454 linhas que trazem PU;

  e a nossa precificacao contra o pu_medio publicado: 434 pares, erro maximo de
  0,0005%. Nos 251 de LTN e NTN-F a checagem e limpa; em NTN-B e LFT o VNA foi
  recuperado do proprio PU deles, entao ali se valida a cotacao e nao o VNA.

DUAS ARMADILHAS DE UNIDADE, e as duas ja morderam projetos parecidos:

  financeiro_aceito vem em REAIS, e o resto do projeto trabalha em MILHOES;
  a segunda volta vem em COLUNAS da mesma linha (oferta_segunda_volta,
  quantidade_aceita_segunda_volta, ...), enquanto a planilha usa LINHAS separadas.
  Somar as duas coisas sem reparar duplicaria o leilao.

Este modulo NAO desliga verificacao de certificado, e nao precisa: o apiapex passa.
"""
import datetime
import json
import ssl
import urllib.error
import urllib.request
from pathlib import Path

from . import config
from .gravacao import gravar_atomico

BASE = "https://apiapex.tesouro.gov.br/aria/v1/api-leiloes-pub/custom/"

# Os endpoints que este projeto usa, e o que cada um serve. Os que existem no portal
# e nao estao aqui foram deixados de fora com motivo, na docstring do modulo.
ENDPOINTS = {
    "editais": "a oferta do dia, por benchmark",
    "calendario": "o que o Tesouro planeja ofertar",
    "benchmarks": "o vertice de cada vencimento, com vigencia",
    "resultados": "resultado por leilao, desde 2018",
    "dealers": "instituicoes habilitadas, com periodo",
    "portarias": "a oferta do dia, pela portaria",
    "comunicados": "titulo e link dos comunicados",
}

PASTA = "leiloes_api"

TEMPO_LIMITE = 45

_ERRO_DE_REDE = (
    "nao consegui falar com a API de leiloes do Tesouro ({url}).\n"
    "\n"
    "Motivo: {motivo}\n"
    "\n"
    "O pipeline NAO depende disto: sem a API, os graficos continuam com o que a\n"
    "planilha historico-leiloes-todos.xls ja trouxe -- um a cinco dias atrasado.\n"
    "\n"
    "Se for erro de certificado, NAO desligue a verificacao. Aponte o Python para o\n"
    "pacote de certificados da instituicao:\n"
    "\n"
    '    PowerShell:  $env:SSL_CERT_FILE = "C:\\caminho\\para\\ca-bundle.crt"\n'
    "    bash:        export SSL_CERT_FILE=/caminho/para/ca-bundle.crt"
)


def _abrir(url, timeout=TEMPO_LIMITE):
    """urlopen com a mensagem traduzida para quem nao le traceback de ssl."""
    try:
        return urllib.request.urlopen(url, timeout=timeout)
    except urllib.error.URLError as erro:
        motivo = getattr(erro, "reason", erro)
        if isinstance(motivo, ssl.SSLCertVerificationError):
            motivo = f"verificacao de certificado falhou ({motivo})"
        raise ConnectionError(
            _ERRO_DE_REDE.format(url=url, motivo=motivo)) from erro


def buscar(nome, timeout=TEMPO_LIMITE):
    """Os registros de um endpoint, como lista de dicionarios.

    Levanta LookupError quando o endpoint nao e um dos que este projeto usa: a lista
    e curta de proposito, e um nome novo merece uma linha em ENDPOINTS dizendo para
    que serve, e nao entrar de contrabando por string.
    """
    if nome not in ENDPOINTS:
        raise LookupError(
            f"endpoint {nome!r} nao esta na lista deste projeto. Os que estao: "
            f"{sorted(ENDPOINTS)}."
        )
    with _abrir(BASE + nome, timeout) as resposta:
        bruto = resposta.read()
    return _registros(bruto, nome), bruto


def _registros(bruto, nome):
    """A lista de registros de dentro do envelope do apiapex."""
    dados = json.loads(bruto)
    if isinstance(dados, list):
        return dados
    registros = dados.get("registros")
    if registros is None:
        raise LookupError(
            f"a resposta de {nome} nao trouxe 'registros'. As chaves que ela tem: "
            f"{sorted(dados)}. O formato do portal pode ter mudado."
        )
    # 'status' vem "ok" quando deu certo. Nao confio so nele -- a lista vazia e o
    # sinal que importa -- mas um status diferente merece aparecer.
    estado = dados.get("status")
    if estado not in (None, "ok"):
        raise LookupError(f"{nome} respondeu status {estado!r}.")
    return registros


def guardar(nome, quando=None, destino=None, timeout=TEMPO_LIMITE):
    """Busca e guarda a resposta CRUA, com a data no nome. Devolve (caminho, registros).

    A resposta crua vai para o disco porque a API e um alvo movel: o que ela disse
    hoje e o unico registro do que ela disse hoje. Sem isso, reprocessar depende de
    ela ainda responder o mesmo, e ai o pipeline deixa de ser reproduzivel.
    """
    quando = quando or datetime.date.today()
    destino = Path(destino) if destino else (config.RAW_DIR / PASTA)
    destino.mkdir(parents=True, exist_ok=True)

    registros, bruto = buscar(nome, timeout)
    caminho = destino / f"{nome}-{quando.isoformat()}.json"
    gravar_atomico(bruto, caminho)
    return caminho, registros
