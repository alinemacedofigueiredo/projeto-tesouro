"""O modo "leilao hoje": fica esperando, monta o e-mail, e manda.

COMO ELA DESCREVEU em 27/10/2026: "rodo antes do horario. ai ele vai ficar
procurando o leilao, qdo encontrar, vai disparar o email para os emails
escolhidos. e dps ele vai procurar o resultado e tambem mandar o email
automatico".

Sao DUAS ESPERAS seguidas no mesmo dia:

    ~10h00   sai o edital      -> e-mail da OFERTA
     10h45   sai o resultado   -> e-mail do RESULTADO

ESTE MODULO NAO SABE MANDAR E-MAIL, e isso e de proposito. Ele recebe uma
funcao 'enviar' e chama. Sem ela -- o padrao -- grava o arquivo e diz onde
ficou, que e o modo ensaio. Assim todo teste daqui roda sem nenhum caminho de
envio existir, e nao ha como um teste de laco disparar mensagem para uma
lista por engano.

A GUARDA CONTRA MANDAR DUAS VEZES e um arquivo por (dia, tipo, estagio) em
data/raw/emails_enviados/. Mesma doutrina do dolar e do calendario: a primeira
gravacao vence. O laco pode ser reiniciado no meio da manha -- vai acontecer,
porque a maquina dela e do banco e cai -- e reiniciar nao pode remandar o que
ja saiu. Um e-mail repetido para a mesa inteira nao tem como voltar atras.

POR QUE PERGUNTAR E NAO ESPERAR UM HORARIO: o edital nao tem hora fixa, e o
resultado de 10:45 as vezes sai 10:52. Dormir ate as 10:46 e torcer e pior do
que perguntar de minuto em minuto; e barato -- uma chamada de API por volta.
"""
import datetime as dt
import json
import time

from . import api_leiloes, config, email_leilao, leilao_do_dia

# De quanto em quanto tempo perguntar. Um minuto e barato para a API do
# Tesouro e rapido o bastante: o que se perde no pior caso e um minuto.
INTERVALO = 60

# Quando desistir. Depois disso, ou nao houve leilao, ou houve e algo deu
# errado -- e nos dois casos ficar rodando em silencio nao ajuda ninguem.
LIMITE = dt.time(14, 0)

PASTA_DOS_ENVIADOS = config.RAW_DIR / "emails_enviados"

# A LISTA DE QUEM RECEBE, editada a mao. Fica em referencia/ junto do
# paf_bandas.csv -- e entrada dela, e nao dado coletado.
#
# ARQUIVO E NAO BANDEIRA porque o caminho de verdade dela e o duplo-clique no
# atalho: pelo menu nao da para digitar uma lista de e-mails. Sem arquivo e
# sem --para, o modo roda em ENSAIO, que e a falha segura -- "esqueci de
# configurar" nao pode virar "mandou para a lista errada".
ARQUIVO_DOS_DESTINATARIOS = config.RAIZ / "referencia" / "destinatarios.txt"


def destinatarios(caminho=None):
    """Quem recebe, lido do arquivo. Lista vazia quando nao ha arquivo.

    Uma linha por endereco; linha em branco e linha comecando com '#' sao
    ignoradas, para a lista poder ter comentario e poder ter alguem comentado
    temporariamente sem apagar o endereco.
    """
    alvo = caminho or ARQUIVO_DOS_DESTINATARIOS
    if not alvo.exists():
        return []
    linhas = alvo.read_text(encoding="utf-8").splitlines()
    return [x.strip() for x in linhas
            if x.strip() and not x.strip().startswith("#")]


class JaFoi(Exception):
    """Aquele e-mail ja saiu hoje. Nao e erro: e a guarda funcionando."""


class FoiSoAberto(Exception):
    """A mensagem foi aberta pronta na tela, mas NAO foi enviada.

    MORA AQUI, e nao em envio.py, porque quem precisa REAGIR a ela e o laco --
    e o laco nao pode importar o modulo de envio (ha teste reprovando isso).
    envio.py levanta esta; aqui ela e tratada.

    O tratamento tem de acertar tres coisas ao mesmo tempo, e so uma e obvia:
      nao marcar o dia como enviado -- ninguem recebeu ainda;
      nao tentar de novo no minuto seguinte -- seriam sessenta janelas
        abertas na tela dela ate as 14h;
      nao derrubar o laco -- a oferta parada esperando clique nao pode
        impedir o e-mail do RESULTADO de sair as 10:45.
    """


def marca_de_envio(dia, tipo, estagio, destino=None):
    pasta = destino or PASTA_DOS_ENVIADOS
    return pasta / ("%s-%s-%s.json" % (dia.isoformat(), tipo, estagio))


def ja_enviado(dia, tipo, estagio, destino=None):
    return marca_de_envio(dia, tipo, estagio, destino).exists()


def _marca(dia, tipo, estagio, para, assunto, destino=None):
    alvo = marca_de_envio(dia, tipo, estagio, destino)
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_bytes(json.dumps({
        "data_leilao": dia.isoformat(),
        "tipo": tipo,
        "estagio": estagio,
        "para": list(para or []),
        "assunto": assunto,
        "enviado_em": dt.datetime.now().isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=2).encode("utf-8"))
    return alvo


def despacha(dia, tipo, estagio, enviar=None, para=None, destino=None,
             saida=print):
    """Monta o e-mail e manda -- ou grava, quando 'enviar' e None (ensaio).

    A MARCA SO E GRAVADA DEPOIS DE 'enviar' VOLTAR SEM ERRO. Gravar antes
    trocaria "mandei duas vezes" por "nunca mandei e achei que tinha", que e
    pior: o primeiro se percebe, o segundo nao.
    """
    if ja_enviado(dia, tipo, estagio, destino):
        raise JaFoi("o e-mail de %s de %s ja saiu hoje" % (estagio, tipo))

    caminho, d = email_leilao.grava(dia, tipo, estagio)
    assunto = email_leilao.assunto(d)

    if enviar is None:
        saida("ENSAIO: nada foi enviado.")
        saida("   assunto: %s" % assunto)
        saida("   arquivo: %s" % caminho)
        return caminho, None

    corpo = caminho.read_text(encoding="utf-8")
    enviar(assunto=assunto, corpo=corpo, para=para)
    marca = _marca(dia, tipo, estagio, para, assunto, destino)
    saida("enviado: %s" % assunto)
    saida("   para: %s" % ", ".join(para or []))
    return caminho, marca


def papeis_esperados(dia, registros=None):
    """Os vertices que o CALENDARIO diz que saem naquele dia, como conjunto de
    (titulo, vencimento). Vazio quando o calendario nao fala daquele dia.

    SO VENDA: os e-mails sao de leilao de venda. Os de compra existem no
    calendario (quatro, em 27/10/2026) e nao tem e-mail.

    NAO TOCA A REDE -- calendario_publicado le do disco.
    """
    if registros is None:
        registros, _de_onde, _de_quando = api_leiloes.calendario_publicado()
    alvo = dia.isoformat()
    return {(r["TITULO"], r["VENCIMENTO"][:10])
            for r in registros or []
            if str(r.get("DATA_LEILAO", ""))[:10] == alvo
            and str(r.get("TIPO_LEILAO", "")).lower().startswith("venda")}


def papeis_que_sairam(dia, tipo):
    """Os vertices que JA aparecem no dado de hoje, como o mesmo conjunto."""
    d = email_leilao.dados(dia, tipo, estagio="oferta")
    return {(x["titulo"], x["vencimento"].isoformat()) for x in d["linhas"]}


def o_que_falta(dia, tipo, registros=None):
    """Os vertices esperados que ainda NAO sairam.

    A TRAVA QUE ELA PEDIU EM 29/10/2026, com as palavras dela: "as vezes um
    papel demora mais que outro para sair a quantidade, e ai o email sai com
    um dv menor".

    E o defeito mais perigoso que este projeto ja teve candidato a cometer: o
    e-mail sai com DV01 MENOR e parece inteiramente correto. Ninguem confere
    um numero que nao destoa. Por isso a comparacao e por VERTICE e nao por
    papel -- uma NTN-B 2045 que atrasou nao e coberta pela 2029 que ja saiu.

    CALENDARIO CALADO SOBRE O DIA devolve conjunto vazio, que quer dizer "nao
    da para conferir" e NAO "esta tudo la". Quem chama distingue os dois: ver
    espera_e_despacha.
    """
    esperados = papeis_esperados(dia, registros)
    if not esperados:
        return set()
    try:
        sairam = papeis_que_sairam(dia, tipo)
    except LookupError:
        return esperados
    # SO O QUE FALTA, e nao a diferenca simetrica: vertice a MAIS do que o
    # calendario previa nao segura o e-mail. Leilao extraordinario acontece --
    # os de compra de 26 e 27/10/2026 nao estavam no comunicado trimestral.
    return esperados - sairam


def _agora():
    """Isolado para o teste poder trocar sem mexer no relogio da maquina."""
    return dt.datetime.now()


def espera_e_despacha(dia=None, enviar=None, para=None, intervalo=INTERVALO,
                      limite=LIMITE, destino=None, saida=print,
                      dormir=time.sleep, buscar=None, mesmo_incompleto=False):
    """O laco do dia: espera a oferta, manda; espera o resultado, manda.

    Devolve o que foi despachado, como lista de estagios.

    QUEM BUSCA E INJETAVEL ('buscar') pelo mesmo motivo de 'enviar': o teste
    precisa fazer o dia passar sem rede e sem relogio.
    """
    dia = dia or dt.date.today()
    buscar = buscar or _procura_na_api
    feitos = []

    # COMECA COM OS DOIS PENDENTES, e quem decide "ja saiu" e a guarda de
    # despacha(), que sabe o tipo. Tentei filtrar aqui e precisava do tipo
    # ANTES de haver leilao -- que as 9h30 e justamente o que nao existe.
    pendentes = ["oferta", "resultado"]
    # So para nao repetir a mesma lista de faltantes a cada minuto ate as 14h.
    ultima_falta = None
    avisei_sem_calendario = False

    saida("esperando o leilao de %s (ate as %s, olhando a cada %ds)"
          % (dia.strftime("%d/%m/%Y"), limite.strftime("%H:%M"), intervalo))
    if enviar is None:
        saida("MODO ENSAIO: nada sera enviado; os e-mails sao gravados.")

    while pendentes and _agora().time() < limite:
        achado = buscar(dia)
        tipo = email_leilao.tipo_do_dia(dia)

        # A TRAVA DOS PAPEIS INCOMPLETOS. Com um vertice faltando, o e-mail
        # sairia com DV01 menor e sem nada parecendo errado -- ver o_que_falta.
        # Segura os DOIS estagios: na oferta falta lote, no resultado falta
        # risco colocado.
        # CALENDARIO CALADO SOBRE O DIA NAO E "ESTA TUDO LA" -- e "nao da para
        # conferir". Acontece em leilao extraordinario e quando o comunicado
        # trimestral ja passou do fim. A trava dela nao vale ali, e dizer isso
        # em voz alta e o minimo: ela pediu uma GARANTIA, e neste caso nao ha.
        if tipo and not avisei_sem_calendario and not papeis_esperados(dia):
            saida("AVISO: o calendario salvo nao fala de %s, entao NAO DA "
                  "PARA CONFERIR se todos os papeis sairam." % dia.strftime(
                      "%d/%m/%Y"))
            saida("   Vou despachar pelo que estiver no dado. Confira o DV01 "
                  "contra o que voce esperava.")
            avisei_sem_calendario = True

        falta = o_que_falta(dia, tipo) if tipo else set()
        if falta and not mesmo_incompleto:
            if falta != ultima_falta:
                saida("esperando %d vertice(s) que o calendario previa: %s"
                      % (len(falta), ", ".join("%s %s" % x
                                               for x in sorted(falta))))
                ultima_falta = falta
            dormir(intervalo)
            continue

        for estagio in list(pendentes):
            if estagio not in achado or tipo is None:
                continue
            try:
                despacha(dia, tipo, estagio, enviar, para, destino, saida)
            except JaFoi as erro:
                # SAI DA FILA MAS NAO ENTRA EM 'feitos'. A versao anterior
                # contava como feito, e o laco dizia ter mandado um e-mail que
                # a guarda tinha acabado de impedir -- a mensagem afirmando o
                # que nao sabe, de novo.
                saida("nada a fazer: %s" % erro)
                pendentes.remove(estagio)
                continue
            except FoiSoAberto as erro:
                saida("ATENCAO: o e-mail de %s NAO FOI ENVIADO -- %s"
                      % (estagio, erro))
                saida("   ele esta aberto na sua tela esperando o clique.")
                saida("   sigo esperando o resto do dia normalmente.")
                pendentes.remove(estagio)
                continue
            feitos.append(estagio)
            pendentes.remove(estagio)
        if pendentes:
            dormir(intervalo)

    if pendentes:
        saida("parei as %s com %s por sair." % (limite.strftime("%H:%M"),
                                                " e ".join(pendentes)))
        tipo = _tipo_ou_nada(dia)
        falta = o_que_falta(dia, tipo) if tipo else set()
        if falta:
            # NOMEAR O QUE FALTOU, e nao so dizer que faltou. Um vertice
            # cancelado -- aconteceu em 29/10/2026, o leilao inteiro caiu --
            # e indistinguivel de um que atrasou, e so ela sabe qual e qual.
            saida("")
            saida("NAO MANDEI porque o calendario previa vertice(s) que nao "
                  "sairam:")
            for titulo, vencimento in sorted(falta):
                saida("   %s %s" % (titulo, vencimento))
            saida("")
            saida("Se eles foram CANCELADOS, o e-mail esta certo sem eles --")
            saida("rode de novo com --mesmo-incompleto para mandar assim.")
        else:
            saida("Se houve leilao e o e-mail nao saiu, rode de novo ou "
                  "monte a mao.")
    return feitos


def _tipo_ou_nada(dia):
    try:
        return email_leilao.tipo_do_dia(dia)
    except Exception:                        # noqa: BLE001
        return None


def _procura_na_api(dia):
    """Quais estagios ja existem hoje, como conjunto.

    O EDITAL VEM ANTES do resultado, e os dois entram pelo mesmo caminho que o
    pipeline ja usa -- nao ha fonte nova aqui.
    """
    achado = set()
    try:
        leilao_do_dia.do_edital(refazer_graficos=False)
    except Exception:                        # noqa: BLE001
        pass
    try:
        leilao_do_dia.rodar(refazer_graficos=False)
    except Exception:                        # noqa: BLE001
        pass

    tipo = _tipo_ou_nada(dia)
    if tipo is None:
        return achado
    try:
        d = email_leilao.dados(dia, tipo, estagio="oferta")
    except LookupError:
        return achado
    achado.add("oferta")
    if any(not x["taxa_suposta"] for x in d["linhas"]):
        # Taxa de verdade em alguma linha quer dizer que o resultado chegou.
        achado.add("resultado")
    return achado
