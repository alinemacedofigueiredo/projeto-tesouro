"""Executa a camada de dados de ponta a ponta.

A coleta e opcional por desenho: em ambiente sem rede, coloque os
arquivos em data/raw/ manualmente e rode com --sem-coleta.

Este modulo nao instala pacote: invoque com PYTHONPATH=src, por exemplo
'PYTHONPATH=src python -m tesouro.pipeline --sem-coleta' (bash) ou
'$env:PYTHONPATH="src"; python -m tesouro.pipeline --sem-coleta'
(PowerShell).
"""
import argparse
import sys

from . import parse_leiloes, parse_rmd

# OS QUATRO MODOS DE ATUALIZACAO, pedido dela em 08/09/2026.
#
# O pipeline era tudo-ou-nada: coletava as tres fontes e regravava as sete
# paginas, mesmo para acrescentar um leilao. Os modos existem porque as fontes
# tem CADENCIAS DIFERENTES: o RMD e mensal, o leilao e de terca e quinta, e a
# banda do PAF muda quando o Tesouro revisa, sem aviso e sem periodicidade.
#
# QUANTO CADA UM LEVA, medido em 09/09/2026 (os tres primeiros com
# --sem-coleta, o de leiloes com coleta de verdade):
#
#     paf       69 s
#     leiloes  135 s
#     rmd      171 s
#     tudo     191 s
#
# A ECONOMIA DE TEMPO E MODESTA, e dizer outra coisa seria vender o que estes
# modos nao entregam: eu tinha escrito aqui "perto de trinta minutos" sem ter
# medido -- trinta minutos e a SUITE DE TESTES, nao o pipeline.
#
# O que os modos entregam de fato: nao tocar na Bloomberg quando ela nao e
# necessaria (o terminal fica desligado quase sempre, e a tentativa ou demora
# ou falha); nao ter de saber qual RMD baixar para acrescentar um leilao; e
# nao regravar pagina que aquela fonte nao pode ter mudado.
#
# CADA MODO E O CONJUNTO DE PASSOS QUE AQUELA FONTE MOVE, e a lista abaixo e a
# unica fonte da verdade sobre isso -- os testes leem daqui, e cada regra tem
# teste proprio em tests/test_pipeline.py.
#
# As tres regras que nao sao obvias:
#
#   1. LEILOES NAO TOCA A BLOOMBERG. O terminal so existe na maquina da mesa e
#      fica desligado quase sempre; tentar a Bloomberg para acrescentar um
#      leilao ou demora ou falha, e o leilao nao depende dela.
#   2. LEILOES NAO REGRAVA O DASHBOARD. Aquelas duas paginas saem do RMD --
#      estoque, prazo, custo, funding, detentores -- e sao a maior parte do
#      tempo do pipeline. Regrava-las por um leilao e reescrever bytes iguais.
#   3. RMD REGRAVA TUDO. Nao ha pagina deste projeto que nao dependa do RMD
#      por algum caminho: ate a do PAF parte do estoque dele para rolar.
PASSOS_DO_MODO = {
    "rmd": ("coleta_rmd", "parse_rmd", "dv", "figuras",
            "dashboard", "emissoes", "paf", "agenda"),
    "leiloes": ("coleta_leiloes", "parse_leiloes", "leiloes_dv",
                "emissoes_rapida", "emissoes", "paf", "agenda"),
    # A banda do PAF entra A MAO: ela le o informe do Tesouro e edita
    # referencia/paf_bandas.csv. Nao ha o que baixar. O que ha e conferir o
    # arquivo ANTES de desenhar, porque banda quebrada nao pode virar grafico
    # com banda errada (spec, secao 6).
    # A AGENDA VAI JUNTO com a pagina do PAF. As duas leem o mesmo
    # calendario publicado: a do PAF para projetar o fechamento do ano,
    # a agenda para mostrar dia a dia o que entrou nessa conta e o que e
    # inferencia nossa. Ate 24/09/2026 este modo regravava uma sem a
    # outra, e as duas podiam ficar discordando na tela -- justamente na
    # pagina onde se confere a projecao.
    "paf": ("valida_paf", "dashboard", "paf", "agenda"),
    "tudo": ("coleta_leiloes", "coleta_rmd", "coleta_bloomberg",
             "parse_leiloes", "parse_rmd", "parse_bloomberg", "dv", "figuras",
             "leiloes_dv", "dashboard", "emissoes", "paf", "agenda"),
}

_EXPLICACAO = {
    "rmd": "o RMD novo saiu (mensal) -- baixa o anexo e regrava tudo",
    "leiloes": "houve leilao -- baixa os resultados e regrava PAF, "
               "emissoes e agenda",
    "paf": "voce editou referencia/paf_bandas.csv -- confere e redesenha "
           "as bandas",
    "tudo": "atualiza as tres fontes e regrava todas as paginas",
}


def _e_interativo():
    """Ha alguem do outro lado para responder?

    FUNCAO PROPRIA, e nao a condicao escrita em linha, por duas razoes: os
    dois lugares que perguntam usam a MESMA definicao, e o teste consegue
    fixar as duas de uma vez.
    """
    return sys.stdin is not None and sys.stdin.isatty()


# Quantas vezes o menu repete a pergunta antes de desistir e seguir com o que
# esta em disco. Cinco e generoso para quem erra a tecla e curto o bastante para
# nao parecer travado.
TENTATIVAS_NO_MENU = 5


def _nome_do_rmd_salvo():
    """"julho/2026", ou None se nao ha nenhum anexo na pasta."""
    from . import leitura_rmd

    base = leitura_rmd.mes_base_carregado()
    if base is None:
        return None
    return leitura_rmd._nome_do_mes(*base)


def _onde_pegar_o_rmd(saida):
    """O site e a pasta, para ela colar no navegador e no Explorer.

    OS DOIS SAEM DO CODIGO que os usa -- fetch_rmd.BASE e config.RMD_DIR -- e
    nao escritos aqui. Caminho repetido a mao fica errado no dia em que o outro
    muda.
    """
    from . import config, fetch_rmd

    saida("")
    saida("  1. abra o site:")
    saida("       %s" % fetch_rmd.BASE)
    saida("  2. baixe o ANEXO do mes e salve nesta pasta:")
    saida("       %s" % config.RMD_DIR)
    saida("")


def escolher_rmd_no_menu(entrada=None, saida=print):
    """Continuar com o RMD salvo, ou ir buscar um mais novo.

    DESENHO DELA em 02/10/2026: "se eu escolho 1 rmd, ai vc me diz, o ultimo rmd
    que vc salvou e da data tal. quer atualizar ou continuar? se continuar, pega
    esse. se clicar em atualizar, diz para pegar no site e salvar na pasta e tem
    q avisar q salvou. e ai roda de novo".

    Devolve sempre None -- "use o anexo que esta na pasta". A versao anterior
    perguntava ano e mes e tentava BAIXAR, o que nao funciona nesta maquina: o
    site trava no certificado do SERPRO. Baixar continua possivel pelas
    bandeiras --ano/--mes, na maquina onde funcionar.

    DEPOIS DO "salvei", RELE O DISCO e mostra o mes de novo. E ali que ela
    descobre se o arquivo foi para o lugar certo -- em vez de descobrir na
    pagina, uma hora depois.
    """
    entrada = entrada or input          # ver o comentario em escolher_modo_no_menu

    # O LACO TEM FIM, e o fim e a saida segura. Sem este limite, resposta que
    # nunca casa repetia a pergunta para sempre: num terminal isso irrita, mas
    # em qualquer coisa automatizada pendura -- um teste ficou 43 minutos preso
    # aqui em 06/10/2026, e foi assim que o defeito apareceu.
    for _ in range(TENTATIVAS_NO_MENU):
        nome = _nome_do_rmd_salvo()
        saida("")
        if nome is None:
            saida("Nao ha nenhum RMD salvo na pasta ainda.")
        else:
            saida("O ultimo RMD que voce salvou e de %s." % nome)
        saida("")
        saida("  C. continuar  -- usa esse mesmo")
        saida("  A. atualizar  -- pegar um mais novo no site")
        saida("")

        try:
            escolha = entrada("C ou A (Enter = continuar): ").strip().lower()
        except EOFError:
            # MESMO DESTINO DO ENTER VAZIO -- continuar com o anexo salvo. Ver
            # o comentario do EOFError em escolher_modo_no_menu.
            saida("")
            saida("nao ha entrada para responder (entrada fechada) -- "
                  "continuando com o anexo que esta na pasta.")
            return None

        # ENTER E CONTINUAR. E a tecla de quem nao quer decidir nada, e aqui
        # nao decidir nada tem significado obvio e seguro: usar o anexo que ja
        # esta na pasta. O menu antigo fazia isso, e eu havia tirado sem
        # perceber.
        if escolha in ("", "c", "continuar", "1"):
            return None

        if escolha in ("a", "atualizar", "2"):
            _onde_pegar_o_rmd(saida)
            try:
                pronto = entrada("Salvou? S para seguir, N para desistir: ")
            except EOFError:
                saida("")
                saida("nao ha entrada para responder (entrada fechada) -- "
                      "continuando com o anexo que esta na pasta.")
                return None
            if pronto.strip().lower() in ("n", "nao", "no"):
                saida("")
                saida("Seguindo com o RMD que ja esta na pasta.")
                return None
            # Qualquer outra resposta conta como "salvei": o laco volta ao topo,
            # LE O DISCO DE NOVO e mostra o mes encontrado. Exigir um "S" exato
            # seria pedir precisao de quem acabou de fazer a parte chata.
            continue

        saida("nao entendi '%s' -- responda C para continuar ou A para "
              "atualizar." % escolha)

    saida("")
    saida("Seguindo com o RMD que ja esta na pasta.")
    return None


_COMECO = []


def _fase(nome):
    """Anuncia uma fase com HORA e tempo decorrido desde o comeco.

    ANTES de rodar, e nao depois: anunciar no fim deixa o silencio sem
    explicacao justamente enquanto ele dura.

    A hora absoluta serve para comparar com o relogio -- andou nos ultimos
    minutos? O decorrido serve para saber se o silencio de agora e normal: na
    rodada anterior a mesma fase levou o mesmo tanto.
    """
    import time

    desde = int(time.time() - _COMECO[0]) if _COMECO else 0
    print("[%s] +%4ds  %s" % (time.strftime("%H:%M:%S"), desde, nome))


def _comecou(modo):
    """O cabecalho que diz que comecou, e onde olhar.

    PALAVRAS DELA: "como sei que esta rodando? fui checar na pagina paf, e nao
    esta atualizado, entao nao sei se esta rodando". As paginas sao o ULTIMO
    passo -- olhar para elas no meio da rodada nao diz nada, e e preciso dizer
    isso antes de ela ir olhar.
    """
    import time

    _COMECO.clear()
    _COMECO.append(time.time())
    print("")
    print("=" * 66)
    print(" COMECOU as %s  --  modo %s" % (time.strftime("%H:%M:%S"), modo))
    print("")
    print(" Cada linha abaixo e uma fase, com a hora e o tempo decorrido.")
    print(" Enquanto aparecer linha nova, esta rodando.")
    print(" As paginas sao o ULTIMO passo: so mudam quando sair 'concluido.'")
    print("=" * 66)


def escolher_modo_no_menu(entrada=None, saida=print):
    """O menu numerado, para quem nao quer decorar bandeira.

    Aparece so quando o pipeline e chamado SEM argumento nenhum e com terminal
    de verdade. Em teste e em agendador nao aparece: la o modo vem por
    --modo, e um programa que espera input onde nao ha ninguem trava calado.
    """
    entrada = entrada or input          # ver o comentario em escolher_rmd_no_menu
    ordem = ["rmd", "leiloes", "paf", "tudo"]
    saida("O que voce quer atualizar?")
    saida("")
    for i, modo in enumerate(ordem, 1):
        saida("  %d. %-8s %s" % (i, modo, _EXPLICACAO[modo]))
    saida("")
    while True:
        # ENTRADA FECHADA NAO E ERRO DE OPERADOR, e ausencia de operador.
        # Medido em 08/10/2026 rodando o atalho com a entrada redirecionada:
        # dez linhas de traceback (EOFError) onde cabia uma frase. No
        # duplo-clique nao acontece; no Agendador de Tarefas, acontece sempre.
        # O destino e o MESMO padrao que main() usa quando nao ha terminal --
        # 'tudo' -- para a resposta nao depender de por onde se entrou.
        try:
            escolha = entrada("numero (ou o nome do modo): ").strip().lower()
        except EOFError:
            saida("")
            saida("nao ha entrada para responder (entrada fechada) -- seguindo "
                  "em 'tudo', que e o padrao de quem chama sem bandeira.")
            return "tudo"
        if escolha in _EXPLICACAO:
            return escolha
        if escolha.isdigit() and 1 <= int(escolha) <= len(ordem):
            return ordem[int(escolha) - 1]
        saida("nao entendi '%s' -- responda 1 a %d, ou o nome do modo."
              % (escolha, len(ordem)))


class _PulaAgenda(Exception):
    """A agenda nao entra neste modo -- nao e falha, e desvio de fluxo.

    Sai por excecao porque o bloco da agenda ja vive dentro de um try que
    existe para outra coisa: sem isto, o 'if' teria de envolver o try inteiro
    e o except de baixo mudaria de alcance.
    """


class FaltaDado(Exception):
    """Falta um arquivo de entrada -- nao e defeito, e instalacao incompleta.

    EXISTE PARA A MENSAGEM NAO VIR EM TRACEBACK. Medido em 20/10/2026 no teste
    do clone limpo: a frase do projeto ja era boa ("nenhum .xlsx encontrado em
    ...; baixe com ... ou coloque o arquivo na pasta manualmente"), mas chegava
    embrulhada em quinze linhas de pilha, e numa maquina nova e a primeira
    coisa que a pessoa ve. Traceback e um jeito confuso de dizer "falta o
    anexo" -- a mesma armadilha do "--mes 13" e do menu com a entrada fechada.
    """


def _executa(fase, funcao):
    """Roda uma fase, e converte "falta arquivo" em FaltaDado.

    SO FileNotFoundError VIRA FRASE. Qualquer outra excecao continua subindo
    com a pilha inteira: defeito de codigo tem de aparecer como defeito, e
    esconder um sob uma frase amavel seria pior do que o traceback.
    """
    try:
        return funcao()
    except FileNotFoundError as erro:
        raise FaltaDado("%s: %s" % (fase, erro)) from erro


def main(argumentos=None):
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument(
        "--sem-coleta", action="store_true",
        help="nao baixa nada; usa os arquivos ja presentes em data/raw/",
    )
    # SOBRESCREVE UM ARQUIVO DE data/raw, que e imutavel por invariante -- por
    # isso e bandeira explicita e nunca o padrao. Ver fetch_leiloes.baixar.
    analisador.add_argument(
        "--rebaixar-planilha", action="store_true",
        help="rebaixa a planilha historica do Tesouro, sobrescrevendo a salva",
    )
    analisador.add_argument("--ano", type=int, help="ano do RMD a baixar")
    # choices, e nao validacao la dentro: o argparse recusa ANTES de a
    # rodada comecar, e diz o valor recusado. Medido em 06/10/2026 --
    # "--mes 13" estourava ValueError com traceback DEPOIS de imprimir
    # que a rodada tinha comecado, e traceback e um jeito confuso de
    # dizer "digitei 13".
    analisador.add_argument("--mes", type=int, choices=range(1, 13),
                            metavar="1..12",
                            help="mes do RMD a baixar")
    analisador.add_argument(
        "--modo", choices=sorted(PASSOS_DO_MODO),
        help="o que atualizar; sem isto, faz tudo (ou pergunta, no terminal)",
    )
    opcoes = analisador.parse_args(argumentos)

    # SEM --modo O PADRAO E 'tudo', e nao o menu: quem ja tem o comando num
    # agendador ou na cabeca nao pode ser quebrado, e um programa que espera
    # input onde nao ha ninguem trava calado. O menu so aparece com terminal
    # de verdade e sem argumento nenhum.
    modo = opcoes.modo
    if modo is None:
        interativo = (argumentos is None and len(sys.argv) == 1
                      and _e_interativo())
        modo = escolher_modo_no_menu() if interativo else "tudo"
    passos = PASSOS_DO_MODO[modo]
    print("modo: %s -- %s" % (modo, _EXPLICACAO[modo]))
    _comecou(modo)

    if opcoes.sem_coleta and (opcoes.ano or opcoes.mes):
        # Combinacao plausivel: o README ensina as duas formas em blocos
        # vizinhos. Sem o aviso, o operador fica achando que escolheu o mes,
        # quando na verdade o pipeline usou o .xlsx mais recente da pasta.
        print(
            "aviso: --ano/--mes sao ignorados com --sem-coleta; o pipeline "
            "usa o RMD mais recente ja presente em data/raw/rmd/"
        )

    # Falhas reais da coleta (nao o caso benigno "painel ja em dia")
    # ficam acumuladas aqui, para aparecer de novo perto de "concluido." em
    # vez de se perder cinco linhas acima no topo do log, e para o
    # pipeline sair com codigo diferente de zero quando alguma perna foi
    # pulada por falha de verdade -- achado da revisao da Tarefa 10: um
    # "except Exception" generico fundia "nada novo para coletar" (rotina)
    # com blpapi ausente/sessao recusada/arquivo corrompido/estoque ausente
    # (falha real) sob a mesma linha neutra "pulada", e o pipeline seguia,
    # regravava os 22 CSVs com dado velho e saia com codigo 0 nos dois
    # casos -- indistinguivel para quem le o log ou agenda o job.
    falhas = []

    # Quantas linhas de leilao entraram pela API nesta rodada. Zero tambem
    # quer dizer "nao coletei", e nos dois casos o DV por leilao precisa ser
    # regravado aqui -- ver o guard mais abaixo.
    entraram_leiloes = 0

    # A CONFERENCIA DA REFERENCIA VEM ANTES DE TUDO, e derruba a rodada: banda
    # quebrada nao pode virar grafico com banda errada. So o modo 'paf' passa
    # por aqui, porque so ele existe por causa de uma edicao a mao.
    if "valida_paf" in passos:
        _fase("conferindo a banda do PAF")
        from . import valida_referencia
        if valida_referencia.main([]) != 0:
            print("\nATENCAO: a referencia do PAF nao passou. Nada foi "
                  "redesenhado -- corrija o CSV e rode de novo.")
            return 1

    if not opcoes.sem_coleta:
        if "coleta_leiloes" in passos:
            _fase("baixando os leiloes")
            from . import fetch_leiloes
            fetch_leiloes.baixar(forcar=opcoes.rebaixar_planilha)
            # E O RESULTADO DO DIA, PELA API -- sem isto a coleta de leiloes
            # nao coleta leilao nenhum.
            #
            # fetch_leiloes.baixar() busca a PLANILHA HISTORICA do Tesouro, que
            # trava no certificado do SERPRO e nao atualiza: ela imprime "ja
            # existe, nada a fazer" e segue. O leilao novo entra por
            # leilao_do_dia.rodar(), que vai a API e grava
            # leiloes_recentes.csv -- o arquivo que rolagem.leiloes() junta a
            # planilha para cobrir da fronteira dela ate hoje.
            #
            # O PIPELINE NUNCA CHAMOU ISSO. Medido em 09/09/2026: rodei o modo
            # leiloes com a API oferecendo leiloes ate 08/09 e a rodada saiu
            # verde, dizendo "concluido", com a pagina ainda em 25/08. O modo
            # 'tudo' tinha o mesmo buraco desde sempre.
            #
            # refazer_graficos=False: quem redesenha e o pipeline, logo
            # abaixo, e fazer duas vezes so gastaria o dobro do tempo.
            from . import leilao_do_dia

            # E O EDITAL DO DIA, ANTES DO RESULTADO. Ela pediu o modo rapido em
            # 24/09/2026, com a oferta ja anunciada e sem resultado: a rodada
            # saiu verde em 185 s e a oferta NAO estava na pagina. O dado dos
            # graficos parava em 22/09, com zero linhas 'ofertado' -- a hachura
            # que marca "resultado ainda nao saiu" nao tinha o que hachurar.
            #
            # O /editais tinha a oferta o tempo todo. So que quem o lia era
            # entrada_manual, um caminho MANUAL que o pipeline nunca chamava.
            #
            # A ORDEM E A DO DIA: oferta de manha, resultado a tarde. E a ordem
            # dos estagios (ofertado < aceito < planilha) garante que o aceito
            # substitua o teto sozinho quando o resultado chegar na mesma
            # rodada.
            try:
                leilao_do_dia.do_edital(refazer_graficos=False)
            except Exception as erro:           # noqa: BLE001
                print("AVISO: nao consegui buscar o edital do dia (%s)." % erro)
                print("       O resultado ainda e buscado abaixo; o que se "
                      "perde e a barra da oferta antes de ele sair.")

            try:
                entraram_leiloes = (
                    leilao_do_dia.rodar(refazer_graficos=False) or 0)
            except Exception as erro:           # noqa: BLE001
                # A API cai, e quando cai a planilha ainda serve. Mas em voz
                # alta: sem isto, "concluido" significaria "as paginas foram
                # regravadas sem o leilao de hoje" sem nada acusar.
                mensagem = ("o resultado do dia NAO foi buscado, seguindo com "
                            f"os leiloes ja em disco: {erro}")
                print(f"ATENCAO: {mensagem}")
                falhas.append(mensagem)
        if "coleta_rmd" in passos:
            _fase("baixando o anexo do RMD")
            from . import fetch_rmd
            ano, mes = opcoes.ano, opcoes.mes
            # SE NINGUEM DISSE QUAL, PERGUNTA -- mas so quando ha a quem. Num
            # agendador nao ha, e um programa que espera input ali trava
            # calado; la o comportamento antigo vale, e diz que vale.
            if not (ano and mes) and _e_interativo():
                escolhido = escolher_rmd_no_menu()
                if escolhido:
                    ano, mes = escolhido
            if ano and mes:
                fetch_rmd.baixar(ano, mes)
            else:
                print("sem --ano/--mes: usando o RMD ja presente em "
                      "data/raw/rmd/")

        # A coleta da Bloomberg nao derruba o pipeline quando o terminal
        # (Bloomberg Terminal/API local) nao esta disponivel: ela avisa e
        # segue com o que ja estiver em disco. Mesmo principio de
        # --sem-coleta, aplicado a uma fonte que pode faltar mesmo com rede
        # -- o terminal so existe na maquina da mesa, nao em toda maquina
        # com internet. O import de fetch_bloomberg abaixo fica FORA do
        # try de proposito -- so o import esta seguro sem terminal, porque
        # "import blpapi" mora dentro de fetch_bloomberg._sessao(), nunca
        # no topo do modulo (travado por
        # tests/test_fetch_bloomberg.py::test_nao_importa_blpapi_no_topo);
        # o que precisa do try/except e a CHAMADA a baixar(), nao o import.
    if not opcoes.sem_coleta and "coleta_bloomberg" in passos:
        from . import fetch_bloomberg
        try:
            fetch_bloomberg.baixar()
        except RuntimeError as erro:
            # fetch_bloomberg.baixar so levanta RuntimeError nos dois casos
            # "nada a coletar"/"nada novo a coletar": o painel do estoque
            # ja esta coberto pelos arquivos existentes. Isso e rotina, nao
            # falha -- nao entra em "falhas".
            print(f"coleta da Bloomberg: {erro}")
        except Exception as erro:               # noqa: BLE001
            # Qualquer outra excecao (blpapi ausente, sessao recusada,
            # arquivo corrompido, estoque ausente etc.) e falha de
            # verdade: prefixo bem visivel, porque o pipeline vai seguir e
            # regravar os CSVs com o dado ja presente em disco -- isso
            # nunca pode parecer rotina.
            mensagem = f"coleta da Bloomberg FALHOU, seguindo com dado velho: {erro}"
            print(f"ATENCAO: {mensagem}")
            falhas.append(mensagem)

    if "parse_leiloes" in passos:
        _fase("lendo os leiloes")
        _executa("lendo os leiloes", parse_leiloes.gravar)
    if "parse_rmd" in passos:
        _fase("lendo o RMD")
        _executa("lendo o RMD", parse_rmd.gravar_tudo)

    if "parse_bloomberg" in passos:
        print("\n--- bloomberg ---")
        from . import parse_bloomberg
        parse_bloomberg.gravar()

    if "dv" in passos:
        _fase("calculando o DV01")
        print("\n--- dv01 e decay ---")
        from . import dv as _dv
        _dv.gravar_painel()
        _dv.gravar_decay()
        _dv.gravar_resultado()

    if "figuras" in passos:
        _fase("desenhando as figuras do RMD")
        from . import figuras
        figuras.gravar_todas()

    # SO REGRAVA O DV POR LEILAO SE leilao_do_dia NAO TIVER ACABADO DE
    # GRAVA-LO. Ele grava com ate_o_estagio="ofertado", que inclui o leilao de
    # hoje; leiloes_dv.gravar() sozinho usa "planilha", que so tem o que o
    # Tesouro ja publicou -- e a planilha trava no certificado do SERPRO.
    #
    # Medido em 09/09/2026, no primeiro modo leiloes de verdade: 14.398 linhas
    # gravadas por leilao_do_dia e 14.338 regravadas logo em seguida. Sessenta
    # a menos, exatamente as que tinham acabado de entrar. As paginas de
    # emissao desenham o provisorio com HACHURA, entao o efeito era o leilao de
    # hoje sumir do grafico que existe para mostra-lo -- sem erro e sem aviso.
    #
    # O DEFEITO E MAIS VELHO QUE OS MODOS: quem rodasse leilao_do_dia e depois
    # o pipeline ja perdia as linhas. Ligar os dois no mesmo comando so tornou
    # o caso deterministico, e portanto visivel.
    if "leiloes_dv" in passos and not entraram_leiloes:
        print("\n--- dv por leilao ---")
        from . import leiloes_dv
        # "ofertado", E NAO O DEFAULT "planilha": e o estagio que leilao_do_dia
        # usa, e o default de leiloes_recentes.completo, que devolve so a
        # planilha quando nao ha provisorio nenhum. Seguro sempre, e o unico
        # que nao perde linha.
        #
        # Sem isto o guard acima so adiava o defeito um dia: na rodada
        # seguinte leilao_do_dia diria "nada novo", devolveria zero, e esta
        # linha apagaria com "planilha" o provisorio que a rodada de ontem
        # tinha posto la.
        leiloes_dv.gravar(ate_o_estagio="ofertado")

    try:
        from .graficos import dashboard
        if "dashboard" in passos:
            _fase("gravando o dashboard")
            # DUAS paginas desde 21/08/2026, por tamanho -- ver PAGINAS_DO_RMD.
            for caminho in dashboard.grava_o_rmd():
                print(f"dashboard gravado em {caminho}")
        from .graficos import painel_emissoes
        # A FASE RAPIDA VEM PRIMEIRO, e antes da pagina do PAF. Ver
        # painel_emissoes.grava_rapida: uma janela em 6 s contra 58 das cinco,
        # e a do PAF custa 45 s dos 203 do modo. O aviso abaixo E O PRODUTO
        # desta fase -- e por ele que ela sabe que o e-mail do dia pode sair.
        if "emissoes_rapida" in passos:
            rapida = painel_emissoes.grava_rapida()
            print()
            print("=== PAGINA RAPIDA PRONTA: %s" % rapida)
            print("=== e a janela de 20 leiloes. O e-mail do dia ja pode "
                  "sair; as demais paginas continuam sendo geradas.")
            print()
        if "emissoes" in passos:
            _fase("gravando as paginas de emissao")
            painel_emissoes.grava_todas()
        # Os nomes saem das tabelas do painel, e nao do retorno da funcao: o
        # pipeline nao precisa do valor de volta para dizer o que gravou, e
        # depender dele acoplaria o log ao formato do retorno.
        #
        # A DO HISTORICO ENTRA AQUI TAMBEM. Ela e gravada por grava_todas desde
        # 09/09/2026 e o log nao a citava, porque so iterava COMBINACOES --
        # entao ela era escrita em silencio. O manual deste projeto ensina a
        # conferir o que o log diz que gravou; pagina que nao aparece no log
        # nao da para conferir.
        if "emissoes" in passos:
            for _, _, arquivo, rotulo in painel_emissoes.COMBINACOES:
                print(f"pagina de emissoes gravada: {arquivo} ({rotulo})")
            print(f"pagina de emissoes gravada: "
                  f"{painel_emissoes.ARQUIVO_HISTORICO} "
                  f"({painel_emissoes.ROTULO_HISTORICO})")

        from .graficos import painel_paf
        # LISTA VAZIA COM --sem-coleta, e nao None: com None a pagina iria a
        # rede buscar o calendario publicado, e --sem-coleta promete nao ir.
        # A vazia faz `dias_ate` estimar o calendario inteiro, e o rodape da
        # projecao passa a dizer "calendario inteiramente estimado" -- a
        # pagina sai mais fraca, mas sai DIZENDO que esta mais fraca.
        #
        # Diferente da agenda logo abaixo, que some quando a rede falha:
        # aquela pagina E o calendario publicado, e sem ele nao sobra pagina.
        # Esta aqui sobrevive, porque a projecao so precisa de QUANTOS dias
        # de leilao faltam, e isso a estimativa sabe dar.
        registros_do_calendario = [] if opcoes.sem_coleta else None
        if "paf" in passos:
            _fase("gravando a pagina do PAF")
            print("pagina do PAF gravada: "
                  f"{painel_paf.grava(registros=registros_do_calendario)}")

        # A AGENDA DEPENDE DA REDE, e o pipeline nao. Se a API nao responder, a
        # pagina do que VEM PELA FRENTE deixa de ser regravada e as outras seguem
        # -- a alternativa seria derrubar o dashboard inteiro por causa de um
        # calendario, que e a parte menos essencial do que se gera aqui.
        from .graficos import painel_agenda
        try:
            if "agenda" not in passos:
                raise _PulaAgenda
            caminho = painel_agenda.grava()
            print(f"agenda gravada em {caminho}")
        except _PulaAgenda:
            pass
        except (ConnectionError, TimeoutError) as erro_da_agenda:
            # REDE FORA E ROTINA. api_leiloes traduz URLError em ConnectionError
            # de proposito, e e so este caso que a rodada tolera em silencio:
            # amanha a API responde e a pagina volta sozinha.
            print(f"AVISO: a agenda nao foi regravada ({erro_da_agenda}).")
            print("       As demais paginas estao em dia; a agenda ficou com o "
                  "calendario da rodada anterior.")
        except Exception as erro_da_agenda:      # noqa: BLE001
            # QUALQUER OUTRA COISA E DEFEITO, e defeito tem de aparecer no FIM.
            #
            # Ate 24/09/2026 este bloco era um 'except Exception' so, e tratava
            # "a API nao respondeu" igual a "o nosso codigo quebrou". A agenda
            # parou de ser gravada por um erro nosso -- um vertice de LFT
            # estreante no calendario do 4o trimestre, 'NaTType does not support
            # strftime' -- e a rodada saiu com codigo 0 e 'concluido.' na ultima
            # linha. A pagina ficou com o calendario velho por rodadas, e nada
            # acusou.
            #
            # E o mesmo padrao que o comentario de 'falhas', la em cima, ja
            # descrevia para a Bloomberg: um except generico fundindo rotina com
            # falha real sob a mesma linha neutra.
            #
            # A rodada CONTINUA -- as outras paginas valem, e derrubar tudo por
            # causa do calendario seria pior. O que muda e o fim da tela.
            mensagem = f"a agenda NAO foi regravada: {erro_da_agenda}"
            print(f"ATENCAO: {mensagem}")
            print("       As demais paginas estao em dia; a agenda ficou com o "
                  "calendario da rodada anterior.")
            falhas.append(mensagem)
    except Exception as erro:               # noqa: BLE001
        # O paf.bandas levanta de proposito quando referencia/paf_bandas.csv esta
        # quebrado -- decisao da spec, secao 6: banda quebrada nao vira grafico
        # com banda errada. Aqui isso vira falha visivel e codigo de saida 1, do
        # mesmo jeito que a coleta da Bloomberg, em vez de sumir no meio do log.
        mensagem = f"a geracao do dashboard FALHOU: {erro}"
        print(f"ATENCAO: {mensagem}")
        falhas.append(mensagem)


    if falhas:
        print(
            "\nATENCAO: concluido com falha(s) -- os CSVs acima podem "
            "refletir dado desatualizado:"
        )
        for falha in falhas:
            print(f"  - {falha}")
        return 1

    print("\nconcluido.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (FaltaDado, FileNotFoundError) as erro:
        # SEM TRACEBACK, e com codigo 1. Ver o docstring de FaltaDado.
        #
        # AS DUAS JUNTAS: _executa cobre as fases de leitura, que e onde uma
        # instalacao nova para primeiro, mas DV, figuras e paginas tambem leem
        # CSV. Neste codigo FileNotFoundError quer dizer sempre a mesma coisa,
        # e as mensagens nomeiam o arquivo e onde consegui-lo.
        print()
        print("=" * 66)
        print(" FALTA UM ARQUIVO DE ENTRADA -- a rodada parou aqui.")
        print("=" * 66)
        print()
        print(" %s" % erro)
        print()
        print(" O que colocar em cada pasta esta em docs/como-baixar.md.")
        print()
        sys.exit(1)
