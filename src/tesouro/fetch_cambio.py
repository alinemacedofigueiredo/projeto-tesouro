"""Coleta do dolar que converte o DV01 dos e-mails de leilao para USD.

A REGRA QUE MANDA NESTE MODULO, pedida por ela em 27/10/2026: a serie
convertida NAO PODE MUDAR PARA TRAS. O dolar de hoje nao e o de amanha, e um
e-mail ja enviado disse um numero -- recalcular o passado com a cotacao de
agora reescreveria o que foi dito.

O risco nao e teorico nem distante. Ele mora numa rodada comum:

    10:45 de 20/10   a PTAX de 20/10 ainda nao foi fixada (sai ~13h), entao o
                     leilao de 20/10 e gravado com a cotacao de 19/10;
    qualquer hora
    de 21/10         a rodada roda de novo. A PTAX de 20/10 agora existe.

Uma implementacao ingenua trocaria a taxa do leilao de ontem, e a serie andaria
sozinha. Por isso: A PRIMEIRA GRAVACAO VENCE. Se ja existe arquivo para aquele
dia de leilao, ele e devolvido como esta e NAO SE TOCA A REDE. E a mesma
doutrina que data/raw ja tem -- ver o cabecalho de fetch_bloomberg.py, que
registra uma perda de dado por sobrescrita silenciosa.

O ARQUIVO E NOMEADO PELO DIA DO LEILAO, e nao pelo dia da cotacao. A pergunta
que ele responde e "qual dolar aquele e-mail usou", e a resposta tem de ficar
pregada no leilao. A data da cotacao vai DENTRO do arquivo, porque ela e outra
coisa e quase sempre e o dia anterior.

A HIERARQUIA DE FONTE, tambem decidida por ela: Bloomberg quando o terminal
estiver aberto, PTAX de venda quando nao estiver -- mesmo sendo de outro dia.
Aqui a Bloomberg e tentada e qualquer tropeco cai na PTAX, o que resolve dois
ambientes com um caminho so: na maquina dela com o terminal ligado vem BBG, e
em maquina sem blpapi a importacao falha e vem PTAX. Como em fetch_bloomberg,
o import de blpapi fica DENTRO da funcao: o resto do projeto roda sem terminal,
que e o cenario do ambiente de destino.

O ROTULO VIAJA COM O NUMERO. Todo registro diz a fonte, a data e a hora da
cotacao, porque "USD 578 mil" sem dizer por qual dolar e a mesma familia de
defeito que este projeto persegue: plausivel, e sem como conferir.
"""
import datetime as dt
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request

from . import config, gravacao

TEMPO_LIMITE = 30

# Quantos dias uteis para tras aceitamos procurar uma cotacao. Cinco cobre um
# feriado prolongado; alem disso o silencio e mais honesto que um numero velho.
DIAS_PARA_TRAS = 7

# O ticker de cambio do terminal. NAO estava no projeto ate hoje: a Bloomberg
# daqui so trazia taxa, VNA e preco de papel.
TICKER = "USDBRL Curncy"

# PTAX de fechamento do Banco Central, com data E hora da fixacao. A serie 1 do
# SGS da o mesmo numero (conferido em 27/10/2026 para 20/10: 5,0140 nas duas),
# mas sem a hora -- e a hora e o que diz se a cotacao e de hoje ou de ontem.
_PTAX = ("https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
         "CotacaoDolarDia(dataCotacao=@dataCotacao)"
         "?@dataCotacao=%27{data}%27&$format=json")

_HOST = "olinda.bcb.gov.br"

_ERRO_DE_REDE = (
    "nao consegui buscar o dolar no Banco Central ({url}).\n"
    "\n"
    "Motivo: {motivo}\n"
    "\n"
    "Sem dolar, o e-mail de leilao sai sem a coluna em USD -- o resto do\n"
    "pipeline nao depende disto."
)


def pasta(destino=None):
    return config.CAMBIO_DIR if destino is None else destino


def caminho_do_dia(data_do_leilao, destino=None):
    return pasta(destino) / ("dolar-%s.json" % data_do_leilao.isoformat())


def do_disco(data_do_leilao, destino=None):
    """O registro ja gravado para aquele dia de leilao, ou None.

    Nao toca a rede, nunca. Quem desenha e quem manda e-mail passam por aqui.
    """
    alvo = caminho_do_dia(data_do_leilao, destino)
    if not alvo.exists():
        return None
    return json.loads(alvo.read_bytes().decode("utf-8"))


def guardar(data_do_leilao=None, destino=None):
    """Grava o dolar daquele dia de leilao e devolve (caminho, registro).

    A PRIMEIRA GRAVACAO VENCE: com o arquivo no lugar, devolve o que esta la e
    nao busca nada. E o que impede a serie de andar para tras numa rodada
    repetida -- ver o cabecalho do modulo.
    """
    data_do_leilao = data_do_leilao or dt.date.today()
    alvo = caminho_do_dia(data_do_leilao, destino)
    ja = do_disco(data_do_leilao, destino)
    if ja is not None:
        return alvo, ja

    registro = _cotacao(data_do_leilao)
    registro["data_do_leilao"] = data_do_leilao.isoformat()
    registro["buscado_em"] = dt.datetime.now().isoformat(timespec="seconds")

    alvo.parent.mkdir(parents=True, exist_ok=True)
    corpo = json.dumps(registro, ensure_ascii=False, indent=2,
                       sort_keys=True).encode("utf-8")
    gravacao.gravar_atomico(corpo, alvo)
    return alvo, registro


def _cotacao(data_do_leilao):
    """Bloomberg primeiro; qualquer tropeco cai na PTAX."""
    try:
        return _do_bloomberg()
    except Exception as erro:              # noqa: BLE001
        # DE PROPOSITO LARGO: terminal fechado, blpapi ausente, sessao caida e
        # resposta vazia sao quatro excecoes diferentes e UMA decisao -- usar a
        # PTAX. O motivo nao se perde: vai dentro do registro.
        motivo = "%s: %s" % (type(erro).__name__, erro)
    registro = _da_ptax(data_do_leilao)
    registro["bloomberg_falhou"] = motivo
    return registro


# Quanto esperar o terminal antes de desistir e ir para a PTAX.
#
# MEDIDO EM 27/10/2026, e a medicao e a razao de este numero existir: nesta
# maquina o blpapi ESTA INSTALADO e o terminal NAO esta aberto. Com as opcoes
# padrao de fetch_bloomberg._sessao(), cada tentativa levava TRES conexoes de
# ~20 s antes de desistir -- 100 s de espera numa rodada diaria, so para no fim
# usar a PTAX. A coleta historica pode insistir, porque roda uma vez; esta roda
# todo dia e tem uma segunda fonte esperando.
#
# POR ISSO A SESSAO AQUI E PROPRIA, e nao a de fetch_bloomberg: aquela serve a
# puxada grande, onde insistir e o certo. Mudar la mudaria o comportamento de
# quem nao pediu.
ESPERA_DO_TERMINAL_MS = 2000


def _terminal_atende(espera=0.4):
    """A porta do terminal esta aberta? Um aperto de mao de TCP, nada mais.

    POR QUE ANTES DO blpapi: com a porta fechada, so pedir a sessao custava
    18 s mesmo com setConnectTimeout(2 s) e uma tentativa so -- medido em
    27/10/2026. A biblioteca tem retentativa propria por baixo que as opcoes
    nao desligam. Um connect de 0,4 s responde a mesma pergunta.

    Isto NAO substitui o tratamento de erro: a porta pode estar aberta e a
    sessao falhar assim mesmo, e ai o caminho de sempre pega. Serve so para o
    caso comum -- terminal fechado -- nao custar a rodada inteira.
    """
    import socket

    from . import fetch_bloomberg

    try:
        with socket.create_connection(
                (fetch_bloomberg._HOST, fetch_bloomberg._PORTA), espera):
            return True
    except OSError:
        return False


def _do_bloomberg():
    """O dolar do terminal, ou levanta rapido.

    'rapido' nao e detalhe: com o terminal fechado este caminho SEMPRE falha, e
    e o caminho padrao em toda rodada. Ver _terminal_atende.
    """
    if not _terminal_atende():
        raise ConnectionError(
            "o terminal Bloomberg nao esta atendendo nesta maquina; "
            "usando a PTAX")

    import blpapi

    from . import fetch_bloomberg

    # O blpapi escreve WARN e ERROR de conexao direto no stderr. Numa rodada em
    # que a queda e ESPERADA -- terminal fechado, PTAX assumindo -- isso enche a
    # tela de traco vermelho que nao e problema nenhum.
    try:
        blpapi.Logger.registerCallback(lambda *a, **k: None,
                                       blpapi.Logger.SEVERITY_OFF)
    except Exception:                        # noqa: BLE001
        pass                                 # versao de blpapi sem isso

    opcoes = blpapi.SessionOptions()
    opcoes.setServerHost(fetch_bloomberg._HOST)
    opcoes.setServerPort(fetch_bloomberg._PORTA)
    opcoes.setConnectTimeout(ESPERA_DO_TERMINAL_MS)
    opcoes.setNumStartAttempts(1)
    sessao = blpapi.Session(opcoes)
    if not sessao.start() or not sessao.openService("//blp/refdata"):
        raise ConnectionError(
            "o terminal Bloomberg nao respondeu em %d ms; usando a PTAX"
            % ESPERA_DO_TERMINAL_MS)
    try:
        servico = sessao.getService("//blp/refdata")
        pedido = servico.createRequest("ReferenceDataRequest")
        pedido.getElement("securities").appendValue(TICKER)
        for campo in ("PX_LAST", "LAST_UPDATE_DT", "LAST_UPDATE"):
            pedido.getElement("fields").appendValue(campo)
        sessao.sendRequest(pedido)
        valores = {}
        while True:
            evento = sessao.nextEvent(30000)
            for msg in evento:
                if not msg.hasElement("securityData"):
                    continue
                for dados in msg.getElement("securityData").values():
                    if dados.hasElement("securityError"):
                        raise ConnectionError(
                            "a Bloomberg nao reconheceu %r" % TICKER)
                    campos = dados.getElement("fieldData")
                    for campo in ("PX_LAST", "LAST_UPDATE_DT", "LAST_UPDATE"):
                        if campos.hasElement(campo):
                            valores[campo] = campos.getElementAsString(campo)
            if evento.eventType() == blpapi.Event.RESPONSE:
                break
    finally:
        sessao.stop()

    if "PX_LAST" not in valores:
        raise ConnectionError("a Bloomberg respondeu sem PX_LAST para %r"
                              % TICKER)
    return {
        "taxa": float(valores["PX_LAST"]),
        "fonte": "BBG",
        "data_da_cotacao": valores.get("LAST_UPDATE_DT"),
        "hora_da_cotacao": valores.get("LAST_UPDATE"),
    }


def _da_ptax(data_do_leilao, dias_para_tras=DIAS_PARA_TRAS):
    """A ultima PTAX de venda disponivel, andando para tras a partir do dia.

    ANDAR PARA TRAS E O NORMAL, e nao a excecao: o e-mail do resultado sai as
    10:45 e a PTAX do dia so e fixada por volta das 13h. Em dia util comum a
    resposta e a vespera; depois de feriado, mais atras.
    """
    erro_guardado = None
    for atras in range(dias_para_tras + 1):
        dia = data_do_leilao - dt.timedelta(days=atras)
        url = _PTAX.format(data=urllib.parse.quote(dia.strftime("%m-%d-%Y")))
        try:
            with _abrir(url) as resposta:
                bruto = resposta.read()
        except ConnectionError as erro:
            erro_guardado = erro
            continue
        linhas = json.loads(bruto).get("value") or []
        if not linhas:
            continue           # fim de semana, feriado, ou ainda nao fixada
        linha = linhas[-1]
        carimbo = linha.get("dataHoraCotacao", "")
        return {
            "taxa": float(linha["cotacaoVenda"]),
            "fonte": "PTAX",
            "data_da_cotacao": dia.isoformat(),
            "hora_da_cotacao": carimbo.split(" ")[-1] if " " in carimbo else None,
        }
    if erro_guardado is not None:
        raise erro_guardado
    raise LookupError(
        "o Banco Central nao tem PTAX em nenhum dos %d dias ate %s"
        % (dias_para_tras, data_do_leilao.isoformat()))


def _abrir(url, timeout=TEMPO_LIMITE):
    """urlopen com a mensagem traduzida para quem nao le traceback de ssl.

    A ORIENTACAO DE CERTIFICADO VEM DE certificado.orientacao, e nao daqui: ela
    e a mesma em todo caminho do projeto e sabe dizer QUEM ASSINOU, que no
    banco e o que distingue "falta um elo do orgao publico" de "o trafego esta
    sendo inspecionado". Escrever outra mensagem aqui daria duas versoes da
    mesma instrucao, e a segunda envelheceria calada.
    """
    try:
        return urllib.request.urlopen(url, timeout=timeout)
    except urllib.error.URLError as erro:
        motivo = getattr(erro, "reason", erro)
        texto = _ERRO_DE_REDE.format(url=url, motivo=motivo)
        if isinstance(motivo, ssl.SSLCertVerificationError):
            from . import certificado
            texto = certificado.orientacao(_HOST) + "\n\n" + texto
        raise ConnectionError(texto) from erro
