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


# A RESPOSTA DE CADA ENDPOINT, GUARDADA PARA A RODADA. Medido em 20/10/2026
# gravando a pagina do PAF: o endpoint 'calendario' era buscado CINCO vezes na
# mesma pagina, 6,9 s de rede. Quem pede sao a banda, a projecao e a agenda, que
# nao sabem uma da outra.
#
# NAO E SO VELOCIDADE: com uma busca so, as cinco leitoras veem o MESMO retrato
# do calendario. Antes, duas respostas podiam chegar diferentes no meio da
# gravacao -- e a pagina diria duas coisas sobre o mesmo dia.
#
# SO SUCESSO ENTRA. Falha nao e guardada: um tropeco de rede na primeira
# chamada nao pode condenar a rodada inteira, e o proximo pedido tenta de novo.
_GUARDADO = {}


def esquece():
    """Esvazia o guardado. Para teste, e para quem quer buscar de novo na mesma
    rodada."""
    _GUARDADO.clear()


def buscar(nome, timeout=TEMPO_LIMITE):
    """Os registros de um endpoint, como lista de dicionarios.

    Levanta LookupError quando o endpoint nao e um dos que este projeto usa: a lista
    e curta de proposito, e um nome novo merece uma linha em ENDPOINTS dizendo para
    que serve, e nao entrar de contrabando por string.

    DENTRO DE UMA RODADA a resposta e buscada UMA VEZ por endpoint -- ver o
    comentario de _GUARDADO. Para forcar outra busca, chame esquece().
    """
    if nome not in ENDPOINTS:
        raise LookupError(
            f"endpoint {nome!r} nao esta na lista deste projeto. Os que estao: "
            f"{sorted(ENDPOINTS)}."
        )
    if nome in _GUARDADO:
        registros, bruto = _GUARDADO[nome]
        # Copia da LISTA: quem chama nao pode encurtar ou reordenar o que o
        # proximo vai receber. Os dicionarios dentro dela sao os mesmos, e
        # ninguem neste projeto os altera (os parsers so montam DataFrame).
        return list(registros), bruto
    with _abrir(BASE + nome, timeout) as resposta:
        bruto = resposta.read()
    registros = _registros(bruto, nome)
    _GUARDADO[nome] = (registros, bruto)
    return list(registros), bruto


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


def guardado_em_disco(nome, destino=None):
    """A resposta guardada mais recente de um endpoint: (registros, data).

    Devolve (None, None) quando nao ha nenhuma.

    MAIS RECENTE PELA DATA DO NOME do arquivo, e nao pelo carimbo -- a mesma
    decisao que leitura_rmd.caminho_do_rmd tomou em 09/09/2026, e pelo mesmo
    motivo: reabrir e salvar um arquivo antigo nao pode fazer o projeto voltar
    no tempo. Nome que nao se deixa ler e IGNORADO, nao adivinhado.
    """
    destino = Path(destino) if destino else (config.RAW_DIR / PASTA)
    if not destino.is_dir():
        return None, None

    achados = []
    for caminho in destino.glob("%s-*.json" % nome):
        texto = caminho.stem[len(nome) + 1:]
        try:
            achados.append((datetime.date.fromisoformat(texto), caminho))
        except ValueError:
            continue
    if not achados:
        return None, None

    quando, caminho = max(achados)
    return _registros(caminho.read_bytes(), nome), quando


def calendario_publicado(registros=None, destino=None):
    """O calendario do Tesouro: (registros, de_onde, de_quando).

    DISCO PRIMEIRO, REDE DEPOIS -- e essa ordem e a observacao dela de
    20/10/2026: "o calendario e dado antes, nao atualiza todo dia que tem
    leilao". O comunicado do Tesouro e TRIMESTRAL. Buscar na rede a cada
    gravacao de pagina gastava rede e, com a API fora, impedia a pagina de
    sair por falta de um documento que o projeto tinha guardado.

    NAO TOCA A REDE, E NAO ESCREVE NADA. Quem busca e guarda e a fase de
    coleta do pipeline, e so ela -- esta funcao e para quem DESENHA. Foi erro
    meu na primeira versao: sem arquivo no disco ela chamava guardar(), que
    busca na rede e grava em data/raw. Os testes do agenda pegaram, e pelo
    motivo certo: eles trocam api_leiloes.buscar por uma funcao que estoura se
    alguem for a rede durante a gravacao de pagina. O README do projeto diz
    "os parsers nunca acessam a rede", e data/raw e imutavel por invariante.

    'de_onde' e "injetado", "disco" ou "ausente"; 'de_quando' e a data do
    arquivo, ou None. Quem desenha usa os dois para DIZER de quando e o
    calendario que esta mostrando.

    AUSENTE NAO E FALHA: devolve lista vazia, e com ela calendario_leiloes
    estima o periodo inteiro e a pagina diz "de calendario inteiramente
    estimado" -- caminho que ja existia e que ja se anuncia.
    """
    if registros is not None:
        return registros, "injetado", None

    do_disco, quando = guardado_em_disco("calendario", destino)
    if do_disco is not None:
        return do_disco, "disco", quando

    return [], "ausente", None


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
