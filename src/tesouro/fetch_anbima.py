"""A taxa de fechamento de cada papel, da ANBIMA, para o e-mail da OFERTA.

POR QUE ISTO EXISTE, numa frase dela em 28/10/2026: "pode pegar o preco do dia
anterior?". O e-mail da oferta sai as ~10h, quando ainda nao ha taxa de leilao
-- entao o financeiro e o DV01 ofertados precisam de ALGUM preco, e ate hoje o
projeto usava a taxa do ULTIMO LEILAO daquele papel. Medido, essa erra 11,0 bp
na mediana e 36,7 no p90, e move o DV01 do lote em 0,55% / 2,1%. O fechamento
de ontem e de ontem.

A ANBIMA publica, de graca e sem credencial, a taxa indicativa e o PU de todo
titulo publico, todo dia util. E a referencia do mercado brasileiro para
exatamente esta pergunta, e o banco deixa chegar la (conferido em 28/10/2026).

DUAS LIMITACOES MEDIDAS, as duas com consequencia no codigo:

  SO UMA JANELA CURTA FICA NO AR. Pedi 16, 20, 22, 23 e 26/10 num mesmo dia:
  so o 26 respondeu, os outros deram 404. Serve para "ontem", que e o que a
  oferta precisa -- NAO e fonte de historico, e nao adianta tentar backfill.

  O ARQUIVO DE ONTEM PODE AINDA NAO TER SUBIDO. Em 28/10 o mais novo
  disponivel era o de 26. Por isso aqui tambem se anda para tras, como no
  dolar, e o registro diz DE QUANDO e a taxa que voltou.

O ARQUIVO E GUARDADO EM data/raw/anbima/, um por data, E NUNCA REESCRITO --
mesma doutrina do dolar e do calendario. Aqui ela vale por um motivo a mais: a
taxa indicativa de um dia e revisada pela propria ANBIMA em alguns casos, e um
e-mail que ja saiu usou a versao que estava no ar naquela hora.

O FORMATO, medido no arquivo de 26/10/2026: latin-1, campos separados por '@',
numero com virgula decimal. A primeira linha e o nome da ANBIMA, a segunda e o
cabecalho, e dali em diante uma linha por (titulo, vencimento). As colunas que
interessam:

    0  Titulo             LTN, NTN-F, NTN-B, LFT, NTN-C
    1  Data Referencia    AAAAMMDD
    4  Data Vencimento    AAAAMMDD   <- AAAAMMDD, e nao DDMMAAAA; eu errei
                                        isto na primeira leitura e nao casou
                                        nada
    7  Tx. Indicativas    o numero que queremos
    8  PU
"""
import datetime as dt
import json
import ssl
import urllib.error
import urllib.request

from . import config, gravacao

TEMPO_LIMITE = 30

# Quantos dias para tras aceitar. Cinco cobre um feriado prolongado; alem
# disso a taxa ja e de outro mercado e o silencio diz mais.
DIAS_PARA_TRAS = 7

_URL = "https://www.anbima.com.br/informacoes/merc-sec/arqs/ms%s.txt"
_HOST = "www.anbima.com.br"

PAPEIS = ("LTN", "NTN-F", "NTN-B", "LFT", "NTN-C")

_ERRO_DE_REDE = (
    "nao consegui buscar a taxa de fechamento na ANBIMA ({url}).\n"
    "\n"
    "Motivo: {motivo}\n"
    "\n"
    "O e-mail da oferta ainda sai: sem isto ele cai na taxa do ultimo leilao\n"
    "daquele papel, e diz que e isso que esta usando."
)


def pasta(destino=None):
    return config.ANBIMA_DIR if destino is None else destino


def caminho_do_dia(data, destino=None):
    return pasta(destino) / ("taxas-%s.json" % data.isoformat())


def do_disco(data, destino=None):
    """O que foi guardado para aquela data, ou None. Nao toca a rede."""
    alvo = caminho_do_dia(data, destino)
    if not alvo.exists():
        return None
    return json.loads(alvo.read_bytes().decode("utf-8"))


def guardar(ate=None, destino=None, dias_para_tras=DIAS_PARA_TRAS):
    """A ultima taxa de fechamento disponivel ate aquela data.

    Devolve (caminho, registro). O registro traz a data a que as taxas se
    referem -- que quase nunca e 'ate', porque o arquivo do dia anterior pode
    nao ter subido ainda.

    A PRIMEIRA GRAVACAO VENCE, por data de REFERENCIA: se o arquivo daquele
    pregao ja esta em disco, ele volta como esta e a rede nao e tocada.
    """
    ate = ate or dt.date.today()
    erro_guardado = None

    for atras in range(dias_para_tras + 1):
        dia = ate - dt.timedelta(days=atras)
        ja = do_disco(dia, destino)
        if ja is not None:
            return caminho_do_dia(dia, destino), ja

        try:
            bruto = _baixar(dia)
        except LookupError:
            continue               # fim de semana, feriado, ou ainda nao subiu
        except ConnectionError as erro:
            erro_guardado = erro
            continue

        registro = {
            "data_de_referencia": dia.isoformat(),
            "baixado_em": dt.datetime.now().isoformat(timespec="seconds"),
            "taxas": _ler(bruto, dia),
        }
        alvo = caminho_do_dia(dia, destino)
        alvo.parent.mkdir(parents=True, exist_ok=True)
        gravacao.gravar_atomico(
            json.dumps(registro, ensure_ascii=False, indent=2,
                       sort_keys=True).encode("utf-8"), alvo)
        return alvo, registro

    if erro_guardado is not None:
        raise erro_guardado
    raise LookupError(
        "a ANBIMA nao tem fechamento em nenhum dos %d dias ate %s"
        % (dias_para_tras, ate.isoformat()))


def _baixar(dia):
    url = _URL % dia.strftime("%d%m%y")
    try:
        with _abrir(url) as resposta:
            return resposta.read()
    except urllib.error.HTTPError as erro:
        if erro.code == 404:
            raise LookupError("sem arquivo para %s" % dia.isoformat()) from erro
        raise ConnectionError(
            _ERRO_DE_REDE.format(url=url, motivo="HTTP %s" % erro.code)) from erro


def _ler(bruto, dia):
    """As taxas do arquivo, como lista de dicionarios.

    LINHA QUE NAO ENTENDO E PULADA, e nao vira zero: a ANBIMA poe cabecalho,
    nome da entidade e, em alguns dias, aviso no meio do arquivo. Um parser
    que insistisse em ler tudo transformaria texto em numero.
    """
    texto = bruto.decode("latin-1")
    saida = []
    for linha in texto.splitlines():
        campos = linha.split("@")
        if len(campos) < 9 or campos[0] not in PAPEIS:
            continue
        try:
            vencimento = dt.datetime.strptime(campos[4], "%Y%m%d").date()
            taxa = float(campos[7].replace(".", "").replace(",", "."))
            pu = float(campos[8].replace(".", "").replace(",", "."))
        except (ValueError, IndexError):
            continue
        saida.append({
            "titulo": campos[0],
            "vencimento": vencimento.isoformat(),
            "taxa_indicativa_pct": taxa,
            "pu": pu,
        })
    if not saida:
        raise LookupError(
            "o arquivo da ANBIMA de %s veio sem nenhuma linha que eu "
            "entenda -- o formato pode ter mudado" % dia.isoformat())
    return saida


def _abrir(url, timeout=TEMPO_LIMITE):
    """urlopen com a mensagem traduzida para quem nao le traceback de ssl.

    O HTTPError PASSA DIRETO, de proposito: 404 aqui quer dizer "aquele dia
    nao tem arquivo", que e rotina e nao falha de rede. Quem chama distingue.
    """
    try:
        return urllib.request.urlopen(url, timeout=timeout)
    except urllib.error.HTTPError:
        raise
    except urllib.error.URLError as erro:
        motivo = getattr(erro, "reason", erro)
        texto = _ERRO_DE_REDE.format(url=url, motivo=motivo)
        if isinstance(motivo, ssl.SSLCertVerificationError):
            from . import certificado
            texto = certificado.orientacao(_HOST) + "\n\n" + texto
        raise ConnectionError(texto) from erro
