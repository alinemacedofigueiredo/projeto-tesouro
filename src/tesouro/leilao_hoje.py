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
import contextlib
import datetime as dt
import io
import json
import time

from . import api_leiloes, config, email_leilao, leilao_do_dia

# De quanto em quanto tempo perguntar. Um minuto e barato para a API do
# Tesouro e rapido o bastante: o que se perde no pior caso e um minuto.
INTERVALO = 60

# Quando desistir. Depois disso, ou nao houve leilao, ou houve e algo deu
# errado -- e nos dois casos ficar rodando em silencio nao ajuda ninguem.
# OS DOIS PRAZOS, dela, em 30/10/2026. Nao e um limite so: as duas pontas tem
# regras OPOSTAS, e e por isso que sao dois numeros e nao um.
#
#   a oferta FALHA ABERTA  -- as 10:05 ela manda com o que tem, avisando no
#     proprio corpo quais papeis nao conseguiu puxar. Oferta incompleta ainda
#     informa o lote que ja saiu;
#   o resultado FALHA FECHADO -- ao meio-dia, faltando vertice, NAO manda.
#     Resultado incompleto mente sobre o DV01 colocado, e isso nao tem aviso
#     que conserte: o numero menor parece certo.
#
# Depois do meio-dia nao sai e-mail automatico nenhum.
# 10:35 E NAO 10:05. O Tesouro mostra a oferta as 10:30 -- ela corrigiu em
# 05/11/2026, com o laco rodando e a dez minutos de disparar um e-mail de
# oferta com os seis vertices faltando, que nao serviria para nada. Eu tinha
# escrito 10:05 lendo "a oferta sai 10h" da primeira conversa, e nunca
# conferi contra o horario de verdade.
PRAZO_DA_OFERTA = dt.time(10, 35)
PRAZO_DO_RESULTADO = dt.time(12, 0)

# A PARTIR DAQUI O LACO NAO DORME, decisao dela em 05/11/2026: "a partir das
# 10:28 ela precisa rodar uma vez atras da outra, sem dormir".
#
# A oferta aparece as 10:30. Dormir um minuto ali pode custar a oferta inteira
# -- acorda 10:31, e o lote ja esta na tela de todo mundo menos na dela.
#
# A JANELA APERTADA FECHA quando a oferta e despachada, e nao as 12h: depois
# dela sobra 1h30 de espera pelo resultado, e martelar a API do Tesouro sem
# pausa por hora e meia seria abuso, nao urgencia.
HORA_DE_APERTAR = dt.time(10, 28)
INTERVALO_APERTADO = 0

# E A HORA DE COMECAR A PROCURAR O RESULTADO. O Tesouro mostra o resultado as
# 11:45; antes disso, buscar resultado e so peso.
#
# CORRECAO DELA, em 05/11/2026: eu tinha ligado a busca de resultados assim
# que a oferta era despachada, por volta das 10:35 -- uma HORA inteira
# baixando 2,3 MB por minuto para esperar algo que so sai as 11:45. Ela
# apontou: "quando o resultado sair, ele volta a baixar os resultados, certo?
# quando a oferta sair ele ja tem o resultado dos anteriores para fazer os
# graficos". Certo nas duas pontas.
#
# Os dois minutos de margem sao os mesmos da oferta (10:28 para 10:30), e dali
# ate o resultado sair o laco tambem nao dorme.
HORA_DO_RESULTADO = dt.time(11, 43)

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


class FoiSoEnfileirado(Exception):
    """O Outlook aceitou a mensagem, mas ela NAO saiu -- ficou na fila.

    MORA AQUI pelo mesmo motivo de FoiSoAberto: quem precisa reagir e o laco,
    e o laco nao pode importar o modulo de envio.

    ACHADO EM 05/11/2026, no primeiro leilao de verdade. Send() nao envia:
    ENFILEIRA, e devolve sem erro nos dois casos. O programa disse "e-mail
    enviado as 10:43:54" e a mensagem ficou vinte e cinco minutos na Caixa de
    Saida. Pior que a frase errada foi a consequencia: o dia ficou MARCADO
    como enviado, e a trava do reenvio passou a impedir o envio de uma coisa
    que nunca saiu.

    Tratada como FoiSoAberto: nao marca, nao retenta no minuto seguinte, nao
    derruba o laco. O que muda e a frase, que passa a dizer a verdade.
    """


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
             saida=print, faltando=None):
    """Monta o e-mail e manda -- ou grava, quando 'enviar' e None (ensaio).

    A MARCA SO E GRAVADA DEPOIS DE 'enviar' VOLTAR SEM ERRO. Gravar antes
    trocaria "mandei duas vezes" por "nunca mandei e achei que tinha", que e
    pior: o primeiro se percebe, o segundo nao.

    'faltando' sao os vertices que o calendario previa e que nao sairam ate o
    prazo. Eles vao DENTRO do corpo do e-mail, e nao so no log: quem recebe
    precisa saber que aquele DV01 nao e o lote inteiro. So a OFERTA chega aqui
    com vertice faltando -- o resultado incompleto nao e enviado.
    """
    if ja_enviado(dia, tipo, estagio, destino):
        raise JaFoi("o e-mail de %s de %s ja saiu hoje" % (estagio, tipo))

    caminho, d = email_leilao.grava(dia, tipo, estagio, faltando=faltando)
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


def com_resultado(dia, tipo):
    """Os vertices que ja tem RESULTADO, e nao so oferta.

    O estagio "ofertado" e exatamente o de quem ainda nao tem: a taxa dele e
    emprestada do leilao anterior. Qualquer outro estagio quer dizer que o
    Tesouro ja publicou o que aceitou.
    """
    d = email_leilao.dados(dia, tipo, estagio="oferta")
    return {(x["titulo"], x["vencimento"].isoformat()) for x in d["linhas"]
            if x["estagio"] != "ofertado"}


def falta_na_oferta(dia, tipo, registros=None):
    """Vertices que o CALENDARIO previa e que ainda nao apareceram.

    A TRAVA QUE ELA PEDIU EM 29/10/2026: "as vezes um papel demora mais que
    outro para sair a quantidade, e ai o email sai com um dv menor".

    POR VERTICE E NAO POR PAPEL -- uma NTN-B 2045 atrasada nao e coberta pela
    2029 que ja saiu, e e justamente esse o caso dela.

    SO O QUE FALTA, e nao a diferenca simetrica: vertice a MAIS do que o
    calendario previa nao segura nada.
    """
    esperados = papeis_esperados(dia, registros)
    if not esperados:
        return set()
    try:
        sairam = papeis_que_sairam(dia, tipo)
    except LookupError:
        return esperados
    return esperados - sairam


def falta_no_resultado(dia, tipo):
    """Vertices que foram OFERTADOS e ainda nao tem resultado.

    CONTRA A OFERTA, E NAO CONTRA O CALENDARIO -- desenho dela, e melhor que o
    meu: a oferta e a verdade DO DIA. Se o Tesouro ofertou cinco vertices, sao
    cinco resultados. O calendario e a previsao de semanas atras, e pode ter
    sido revisado.
    """
    try:
        ofertados = papeis_que_sairam(dia, tipo)
    except LookupError:
        return set()
    return ofertados - com_resultado(dia, tipo)


def caminho_do_email(dia, tipo, estagio):
    """Onde o e-mail montado ficou, para a mensagem poder dizer."""
    return config.PROCESSED_DIR / ("email-%s-%s-%s.html"
                                   % (tipo, estagio, dia.isoformat()))


def _agora():
    """Isolado para o teste poder trocar sem mexer no relogio da maquina."""
    return dt.datetime.now()


def espera_e_despacha(dia=None, enviar=None, para=None, intervalo=INTERVALO,
                      prazo_da_oferta=PRAZO_DA_OFERTA,
                      prazo_do_resultado=PRAZO_DO_RESULTADO, destino=None,
                      saida=print, dormir=time.sleep, buscar=None,
                      registros=None):
    """O dia de leilao: espera a oferta, manda; espera o resultado, manda.

    Devolve os estagios que foram despachados NESTA rodada.

    SO LEILAO DO CALENDARIO, por enquanto. Ela restringiu o escopo em
    30/10/2026 -- leilao fora do calendario sera desenhado depois. Sem
    previsao para o dia, isto termina NA HORA, em vez de esperar ate o
    meio-dia por algo que nao vem: o calendario e lido do disco e nao muda
    durante a rodada.

    QUEM BUSCA e QUEM MANDA sao injetaveis pelo mesmo motivo: o teste precisa
    fazer a manha passar sem rede, sem relogio e sem mandar nada.
    """
    dia = dia or dt.date.today()
    buscar = buscar or _procura_na_api
    feitos = []

    esperados = papeis_esperados(dia, registros)
    if not esperados:
        saida("o calendario salvo nao preve leilao de VENDA em %s."
              % dia.strftime("%d/%m/%Y"))
        saida("   Leilao fora do calendario ainda nao tem e-mail automatico.")
        return feitos

    saida("leilao de %s: %d vertice(s) previstos no calendario"
          % (dia.strftime("%d/%m/%Y"), len(esperados)))
    saida("   oferta ate %s (manda assim mesmo, avisando o que faltar)"
          % prazo_da_oferta.strftime("%H:%M"))
    saida("   resultado ate %s (nao manda se faltar)"
          % prazo_do_resultado.strftime("%H:%M"))
    saida("   pergunta sem parar das %s (oferta) e das %s (resultado)"
          % (HORA_DE_APERTAR.strftime("%H:%M"),
             HORA_DO_RESULTADO.strftime("%H:%M")))

    # O HISTORICO VEM UMA VEZ SO, ANTES DO LACO -- ideia dela, em 05/11/2026.
    #
    # E o que torna o laco leve: os 2,3 MB de resultados carregam o grafico e
    # a tabela dos dois leiloes anteriores, e dali em diante so falta o
    # edital, que custa quase nada. Sem isto, cada volta rebaixava o
    # historico inteiro para usar as mesmas 67 linhas de sempre.
    if buscar is _procura_na_api:
        saida("")
        saida("baixando o historico uma vez (uns 2,3 MB, poucos segundos)...")
        _procura_na_api(dia)
        saida("historico carregado; dali em diante o laco so pergunta pelo "
              "edital.")
        saida("")
    if enviar is None:
        saida("MODO ENSAIO: nada sera enviado; os e-mails sao gravados.")

    pendentes = ["oferta", "resultado"]
    ultimo_aviso = {}
    avisou_da_pausa = False
    ultimo_sinal = None

    while pendentes and _agora().time() < prazo_do_resultado:
        # A JANELA MORTA: oferta ja despachada e ainda nao sao 11:43.
        #
        # Nao ha NADA para perguntar ali -- o edital ja veio, o resultado nao
        # existe, e o historico foi carregado antes do laco. Correcao dela em
        # 05/11/2026: "aqui nessa janela nao precisa ficar fazendo nada".
        #
        # Sao uns 68 minutos; antes disto o laco perguntava o edital 68 vezes
        # pela mesma resposta.
        agora = _agora().time()
        if "oferta" not in pendentes and agora < HORA_DO_RESULTADO:
            if not avisou_da_pausa:
                saida("oferta despachada. Nada a fazer ate %s, quando o "
                      "resultado sai." % HORA_DO_RESULTADO.strftime("%H:%M"))
                avisou_da_pausa = True
            # SINAL DE VIDA a cada 15 minutos. Sao 68 minutos de silencio, e o
            # cabecalho da rodada promete "enquanto aparecer linha nova, esta
            # rodando" -- calado, ele fica identico a travado. Ela perguntou
            # "ainda esta rodando?" em 05/11/2026, as 11h25, com o programa
            # perfeitamente vivo.
            if agora.minute % 15 == 0 and agora.minute != ultimo_sinal:
                saida("   %s -- vivo, esperando as %s"
                      % (agora.strftime("%H:%M"),
                         HORA_DO_RESULTADO.strftime("%H:%M")))
                ultimo_sinal = agora.minute
            dormir(intervalo)
            continue

        # SO O EDITAL ENQUANTO A OFERTA NAO SAIU -- ver _procura_na_api.
        achado = (buscar(dia, "oferta" in pendentes)
                  if buscar is _procura_na_api else buscar(dia))
        tipo = email_leilao.tipo_do_dia(dia)

        for estagio in list(pendentes):
            if estagio not in achado or tipo is None:
                continue

            falta = (falta_na_oferta(dia, tipo, registros)
                     if estagio == "oferta" else falta_no_resultado(dia, tipo))
            no_prazo = (agora < prazo_da_oferta if estagio == "oferta"
                        else agora < prazo_do_resultado)

            if falta and no_prazo:
                if ultimo_aviso.get(estagio) != falta:
                    saida("%s: faltam %d vertice(s) -- %s"
                          % (estagio, len(falta),
                             ", ".join("%s %s" % x for x in sorted(falta))))
                    ultimo_aviso[estagio] = falta
                continue

            if falta and estagio == "resultado":
                continue          # fora do prazo o laco inteiro termina

            if falta:
                # A OFERTA FALHA ABERTA, e o aviso vai DENTRO do e-mail: quem
                # recebe precisa saber que aquele DV01 nao e o lote inteiro.
                saida("oferta: passou das %s com %d vertice(s) faltando -- "
                      "mandando assim mesmo, com aviso no corpo."
                      % (prazo_da_oferta.strftime("%H:%M"), len(falta)))

            try:
                despacha(dia, tipo, estagio, enviar, para, destino, saida,
                         faltando=falta)
            except JaFoi as erro:
                saida("nada a fazer: %s" % erro)
                pendentes.remove(estagio)
                continue
            except FoiSoAberto as erro:
                saida("ATENCAO: o e-mail de %s NAO FOI ENVIADO -- %s"
                      % (estagio, erro))
                saida("   ele esta aberto na sua tela esperando o clique.")
                pendentes.remove(estagio)
                continue
            except FoiSoEnfileirado as erro:
                saida("ATENCAO: o e-mail de %s NAO SAIU -- %s"
                      % (estagio, erro))
                saida("   ele esta montado em %s" % caminho_do_email(
                    dia, tipo, estagio))
                saida("   abra o Outlook e empurre a Caixa de Saida.")
                pendentes.remove(estagio)
                continue
            feitos.append(estagio)
            pendentes.remove(estagio)

        if pendentes:
            # SEM DORMIR NA JANELA DA OFERTA -- ver HORA_DE_APERTAR. Fora
            # dela, um minuto entre as perguntas.
            agora_ = _agora().time()
            apertado = (("oferta" in pendentes
                         and agora_ >= HORA_DE_APERTAR)
                        or ("resultado" in pendentes
                            and agora_ >= HORA_DO_RESULTADO))
            dormir(INTERVALO_APERTADO if apertado else intervalo)

    if "resultado" in pendentes:
        tipo = _tipo_ou_nada(dia)
        falta = falta_no_resultado(dia, tipo) if tipo else set()
        saida("")
        if falta:
            saida("NAO MANDEI O RESULTADO: as %s ainda faltava(m) %d "
                  "vertice(s) que foram ofertados:"
                  % (prazo_do_resultado.strftime("%H:%M"), len(falta)))
            for titulo, vencimento in sorted(falta):
                saida("   %s %s" % (titulo, vencimento))
            saida("")
            saida("Resultado incompleto diria um DV01 menor do que o colocado,")
            saida("e o numero menor nao parece errado. Monte a mao se precisar.")
        else:
            saida("o resultado nao saiu ate as %s."
                  % prazo_do_resultado.strftime("%H:%M"))
    return feitos


def _tipo_ou_nada(dia):
    try:
        return email_leilao.tipo_do_dia(dia)
    except Exception:                        # noqa: BLE001
        return None


# As falhas da ultima busca, para o laco poder contar. Lista e nao excecao
# porque a busca NAO pode derrubar a rodada: a API do Tesouro cai, e o laco
# tem de sobreviver a isso -- so nao pode fingir que esta tudo bem.
_falhas_da_busca = []


def _procura_na_api(dia, so_edital=False):
    """Quais estagios ja existem hoje, como conjunto.

    O EDITAL VEM ANTES do resultado, e os dois entram pelo mesmo caminho que o
    pipeline ja usa -- nao ha fonte nova aqui.

    'so_edital' PULA A BUSCA DE RESULTADOS, e a ideia e dela, em 05/11/2026:
    "nao e melhor vc baixar essa de resultados uma vez antes de comecar a
    procurar o edital... ai a busca do loop fica leve e rapida".

    O raciocinio dela, que eu nao tinha feito: ENQUANTO A OFERTA NAO SAIU, o
    resultado nao serve para nada -- o grafico e a tabela dos leiloes
    anteriores ja estao montados com o historico que foi baixado no comeco.
    So falta o edital.

    O QUE ISSO POUPA, medido chamada a chamada em 05/11/2026:

        editais        0 KB, 4,8 s   <- o que a oferta precisa
        resultados   2,3 MB, 5,5 s   <- o historico INTEIRO, 4.708 leiloes

    O endpoint de resultados nao filtra por data: devolve tudo desde 2018,
    sempre, para o projeto usar as 67 linhas dos ultimos 30 dias. E nao da
    para perguntar antes se mudou -- medido no mesmo dia, o servidor responde
    HEAD com Content-Length zero e nao manda Last-Modified nem ETag.
    """
    achado = set()
    _falhas_da_busca.clear()

    # A COLETA FALA BAIXO AQUI, e so aqui.
    #
    # do_edital e rodar imprimem o relatorio inteiro da coleta -- quantas
    # linhas vieram, onde foi gravado, o aviso da planilha provisoria. Isso
    # serve numa rodada de atualizacao, que acontece UMA vez. Aqui acontece a
    # cada 60 segundos, por duas horas: seriam ~130 repeticoes do mesmo bloco,
    # e o que importa -- "faltam 2 vertices", "enviado" -- fica enterrado.
    #
    # Ela viu isso rodando em 05/11/2026 e a palavra dela foi "que confuso".
    # Estava certa: a tela e a unica coisa que ela tem para saber o que o
    # programa esta fazendo enquanto espera.
    #
    # O QUE FOI ENGOLIDO NAO SE PERDE DE VERDADE: o que interessa daquelas
    # linhas e o resultado, e o resultado e o que esta funcao devolve.
    engolido = io.StringIO()
    acoes = ((leilao_do_dia.do_edital,) if so_edital
             else (leilao_do_dia.do_edital, leilao_do_dia.rodar))
    for acao in acoes:
        try:
            with contextlib.redirect_stdout(engolido):
                acao(refazer_graficos=False)
        except Exception as erro:            # noqa: BLE001
            # ENGOLIR O ERRO AQUI FAZIA O LACO ESPERAR PARA SEMPRE, CALADO.
            #
            # Aconteceu em 05/11/2026, no primeiro leilao de verdade: o edital
            # saiu as 10:30 e o laco dela nao pegou. A causa provavel fui eu
            # -- rodando diagnosticos no mesmo minuto, dois processos escrevem
            # dv_emitido_por_leilao.csv ao mesmo tempo e um perde. Mas a causa
            # importa menos que isto: COM O ERRO ENGOLIDO, a tela dizia
            # "esperando" e nada estava chegando.
            #
            # A falha continua NAO derrubando a rodada -- a API do Tesouro cai
            # e o laco tem de sobreviver. O que muda e que ela FALA.
            _falhas_da_busca.append("%s: %s" % (type(erro).__name__, erro))

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
