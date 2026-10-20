"""Baixa o anexo (tabelas) do Relatorio Mensal da Divida.

O link do anexo tem um identificador numerico que muda a cada publicacao,
entao nao ha URL previsivel: e preciso abrir a pagina do mes e extrair o
link de la.

Este modulo nunca e necessario para rodar os parsers. Em ambiente sem
rede, basta colocar o .xlsx em data/raw/rmd/ na mao.
"""
import io
import re
import urllib.error
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


def _traduzir_erro_de_rede(url, erro):
    """URLError crua vira mensagem que diz o que fazer, ou segue como estava.

    ATE 28/09/2026 ESTE CAMINHO VAZAVA O TRACEBACK. A orientacao sobre
    SSL_CERT_FILE existia no api_leiloes e no fetch_leiloes_api, e faltava
    justamente aqui -- onde ela foi tentar baixar o anexo do mes e recebeu
    "CERTIFICATE_VERIFY_FAILED" sem nenhuma pista do que fazer.

    Medido no mesmo dia: quem assina o tesourotransparente.gov.br e a "AC SERPRO
    AR46 OV TLS CA 2025", e a cadeia chega incompleta. O navegador contorna
    buscando o elo que falta; o Python nao faz isso.

    E EM 20/10/2026 FALTAVA O OUTRO CASO, o da rede do banco: o site derruba a
    conexao ("[WinError 10054]"), e isso nao casa com CERTIFICATE nem com SSL,
    entao o URLError cru voltava a vazar pilha. Qualquer falha de rede agora
    devolve a frase; so a orientacao do SSL_CERT_FILE fica restrita ao caso de
    certificado, porque mandar mexer nele quem teve a conexao derrubada e
    apontar o lugar errado.

    O QUE NAO E DE REDE CONTINUA SUBINDO como esta: defeito de codigo tem de
    aparecer como defeito.
    """
    from urllib.error import HTTPError, URLError
    from urllib.parse import urlsplit

    from . import certificado

    texto = str(erro)
    de_certificado = "CERTIFICATE" in texto.upper() or "SSL" in texto.upper()
    # A TRAVA DO BANCO NAO E ERRO DE CERTIFICADO. Medido em 20/10/2026 na
    # maquina dela: o tesourotransparente derruba a conexao -- "[WinError
    # 10054] Foi forcado o cancelamento de uma conexao existente pelo host
    # remoto" -- e isso nao casa com CERTIFICATE nem com SSL. Antes desta
    # linha, esse caso vazava o URLError cru e a pessoa recebia uma pilha no
    # lugar da instrucao. O caminho a mao resolve os dois iguais.
    de_rede = isinstance(erro, (URLError, OSError, TimeoutError))
    if not de_certificado and not de_rede:
        return erro
    host = urlsplit(url).hostname or url
    # TRES CAUSAS, TRES FRASES. Medido em 20/10/2026: a primeira versao deste
    # conserto punha HTTPError no balde de "a rede nao deixou a conexao
    # completar", e isso e falso -- a rede deixou, o servidor respondeu, e para
    # o RMD de setembro a resposta foi 404 porque ele nao estava publicado.
    # Mandar investigar proxy nesse caso e afirmar o que o programa nao sabe.
    if de_certificado:
        especifica = certificado.orientacao(host) + "\n\n"
    elif isinstance(erro, HTTPError):
        if erro.code == 404:
            especifica = (
                "O SITE RESPONDEU 404: nao ha publicacao nesse endereco.\n"
                "Quase sempre quer dizer que o RMD daquele mes ainda nao saiu "
                "-- o\nTesouro publica com algumas semanas de atraso. Se o mes "
                "ja saiu no\nsite, entao o padrao do endereco mudou e o "
                "projeto precisa de ajuste.\n\n")
        else:
            especifica = (
                "O SITE RESPONDEU %s. A rede chegou la; a resposta nao foi a "
                "esperada.\n\n" % erro.code)
    else:
        especifica = (
            "A CONEXAO NAO COMPLETOU ate o %s.\nNao ha o que ajustar no "
            "projeto: pode ser bloqueio de saida, proxy\nou inspecao de TLS "
            "da sua rede.\n\n" % host)
    return LookupError(
        "nao consegui baixar o anexo do RMD.\n\n"
        "%s\n\n"
        "%s"
        "O CAMINHO A MAO FUNCIONA e nao depende de nada disto:\n"
        "  1. abra NO NAVEGADOR %s\n"
        "  2. baixe o ANEXO do mes (nao o PDF) e salve em data/raw/rmd/\n"
        "  3. rode de novo sem --ano/--mes -- ele usa o que esta na pasta."
        % (texto, especifica, BASE)
    )


def _nome_previsto(ano, mes):
    return f"Anexo RMD_{ano}_{mes:02d}.xlsx"


def baixar(ano, mes, destino=None):
    """Baixa o anexo do mes e devolve o caminho do .xlsx salvo.

    Se o anexo vier compactado, extrai a primeira planilha do zip.

    Nunca sobrescreve um arquivo que ja exista em data/raw/: essa pasta e
    imutavel por invariante do projeto, e os arquivos antigos sao o unico
    lugar onde ficam os retratos mensais da aba 3.4. Como gravar_atomico
    termina num Path.replace (substitui sem avisar) e o nome do arquivo e
    deterministico, rodar o mesmo mes duas vezes destruiria o primeiro
    download -- e imprimiria 'salvo em ...' como se tudo tivesse dado
    certo. A guarda e a mesma de fetch_leiloes.baixar.
    """
    destino = Path(destino) if destino else config.RMD_DIR
    destino.mkdir(parents=True, exist_ok=True)

    # Curto-circuito antes de qualquer requisicao, quando o nome do arquivo
    # ja e conhecido. No caminho do zip o nome vem de dentro do arquivo,
    # entao la a guarda so pode agir depois do download (abaixo).
    previsto = destino / _nome_previsto(ano, mes)
    if previsto.exists():
        print(f"ja existe, nada a fazer: {previsto}")
        return previsto

    alvo = url_da_publicacao(ano, mes)
    try:
        pagina = _baixar_bytes(alvo, timeout=60)
        url = link_do_anexo(pagina.decode("utf-8", errors="ignore"))
        print(f"baixando {url}")
        conteudo = _baixar_bytes(url)
    except urllib.error.URLError as erro:
        raise _traduzir_erro_de_rede(alvo, erro) from erro

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
            if caminho.exists():
                print(f"ja existe, nada a fazer: {caminho}")
                return caminho
            gravar_atomico(zf.read(nome), caminho)
    else:
        caminho = previsto
        gravar_atomico(conteudo, caminho)

    print(f"salvo em {caminho} ({caminho.stat().st_size / 1e6:.1f} MB)")
    return caminho


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        sys.exit("uso: python -m tesouro.fetch_rmd <ano> <mes>")
    try:
        baixar(int(sys.argv[1]), int(sys.argv[2]))
    except LookupError as erro:
        # SEM TRACEBACK. _traduzir_erro_de_rede ja devolve a frase inteira,
        # com o caminho a mao; embrulha-la em pilha era desperdicar o trabalho
        # dela. Medido em 20/10/2026 na maquina dela.
        print()
        print(erro)
        print()
        sys.exit(1)
