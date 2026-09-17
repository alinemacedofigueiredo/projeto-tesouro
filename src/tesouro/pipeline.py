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
    "paf": ("valida_paf", "dashboard", "paf"),
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


def escolher_rmd_no_menu(entrada=None, saida=print):
    """Qual RMD puxar -- pedido dela, com estas palavras: "quando a pessoa
    decidir atualizar o rmd tem q ter a opcao, qual rmd vc quer puxar?".

    Devolve (ano, mes), ou None para "segue com o que ja esta em disco". Sem
    isto, escolher "atualizar o RMD" no menu nao baixava nada -- o pipeline
    imprimia que estava usando o anexo ja presente e seguia, que e a ultima
    coisa que quem escolheu aquele item espera.
    """
    # RESOLVE input() AQUI DENTRO, e nao como valor padrao do parametro. Um
    # padrao 'entrada=input' captura o builtin NA DEFINICAO do modulo, e
    # substitui-lo depois nao muda nada -- o teste que finge o teclado passava
    # a nao ter efeito, e a funcao ficava esperando um Enter que ninguem daria.
    entrada = entrada or input
    saida("Qual RMD voce quer puxar?")
    saida("  (Enter em branco segue com o anexo que ja esta em "
          "data/raw/rmd/)")
    ano = entrada("ano  (ex.: 2026): ").strip()
    if not ano:
        return None
    mes = entrada("mes  (1 a 12): ").strip()
    if not mes:
        return None
    try:
        ano, mes = int(ano), int(mes)
    except ValueError:
        saida("ano ou mes nao e numero; seguindo com o anexo em disco.")
        return None
    if not 1 <= mes <= 12:
        saida("mes fora de 1 a 12; seguindo com o anexo em disco.")
        return None
    return ano, mes


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
        escolha = entrada("numero (ou o nome do modo): ").strip().lower()
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


def main(argumentos=None):
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument(
        "--sem-coleta", action="store_true",
        help="nao baixa nada; usa os arquivos ja presentes em data/raw/",
    )
    analisador.add_argument("--ano", type=int, help="ano do RMD a baixar")
    analisador.add_argument("--mes", type=int, help="mes do RMD a baixar")
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
        from . import valida_referencia
        print("\n--- conferindo referencia/paf_bandas.csv ---")
        if valida_referencia.main([]) != 0:
            print("\nATENCAO: a referencia do PAF nao passou. Nada foi "
                  "redesenhado -- corrija o CSV e rode de novo.")
            return 1

    if not opcoes.sem_coleta:
        if "coleta_leiloes" in passos:
            from . import fetch_leiloes
            fetch_leiloes.baixar()
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
        print("\n--- leiloes ---")
        parse_leiloes.gravar()
    if "parse_rmd" in passos:
        print("\n--- rmd ---")
        parse_rmd.gravar_tudo()

    if "parse_bloomberg" in passos:
        print("\n--- bloomberg ---")
        from . import parse_bloomberg
        parse_bloomberg.gravar()

    if "dv" in passos:
        print("\n--- dv01 e decay ---")
        from . import dv as _dv
        _dv.gravar_painel()
        _dv.gravar_decay()
        _dv.gravar_resultado()

    if "figuras" in passos:
        print("\n--- figuras ---")
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

    print("\n--- dashboard ---")
    try:
        from .graficos import dashboard
        if "dashboard" in passos:
            # DUAS paginas desde 21/08/2026, por tamanho -- ver PAGINAS_DO_RMD.
            for caminho in dashboard.grava_o_rmd():
                print(f"dashboard gravado em {caminho}")
        from .graficos import painel_emissoes
        # A FASE RAPIDA VEM PRIMEIRO, e antes da pagina do PAF. Ver
        # painel_emissoes.grava_rapida: uma janela em 6 s contra 58 das cinco,
        # e a do PAF custa 45 s dos 203 do modo. O aviso abaixo E O PRODUTO
        # desta fase -- e por ele que ela sabe que o e-mail do dia pode sair.
        #
        # ----------------------------------------------------------------
        # RECEITA DO E-MAIL, NAO E CODIGO. Nao rode isto como esta.
        #
        # O projeto NAO manda e-mail, e ligar isto depende de decisoes dela que
        # ainda nao foram tomadas:
        #
        #   1. qual servidor SMTP do banco, e se ele exige autenticacao;
        #   2. de que endereco sai e para quem vai;
        #   3. se a pagina vai ANEXADA (1,05 MB) ou como LINK para a pasta de
        #      rede -- anexo de 1 MB por leilao enche caixa postal.
        #
        # O esqueleto, para quando essas tres estiverem respondidas:
        #
        #   import smtplib
        #   from email.message import EmailMessage
        #   msg = EmailMessage()
        #   msg["Subject"] = f"Leilao de {hoje:%d/%m} -- emissoes"
        #   msg["From"], msg["To"] = REMETENTE, DESTINATARIOS
        #   msg.set_content("A pagina esta em " + str(rapida))
        #   with smtplib.SMTP(SERVIDOR) as smtp:
        #       smtp.send_message(msg)
        #
        # DUAS ADVERTENCIAS que valem mais que o esqueleto:
        #
        #   - manda-se e-mail DEPOIS de conferir que a pagina saiu certa. O
        #     cabecalho dela diz qual foi o ultimo leilao; se ele nao mudou, a
        #     atualizacao nao atualizou e o e-mail estaria anunciando o dado de
        #     ontem.
        #   - falha de e-mail NAO pode derrubar o pipeline. Ela entra em
        #     'falhas', como a Bloomberg e a agenda, e as paginas seguem sendo
        #     gravadas.
        # ----------------------------------------------------------------
        if "emissoes_rapida" in passos:
            rapida = painel_emissoes.grava_rapida()
            print()
            print("=== PAGINA RAPIDA PRONTA: %s" % rapida)
            print("=== e a janela de 20 leiloes. O e-mail do dia ja pode "
                  "sair; as demais paginas continuam sendo geradas.")
            print()
        if "emissoes" in passos:
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
        except Exception as erro_da_agenda:      # noqa: BLE001
            print(f"AVISO: a agenda nao foi regravada ({erro_da_agenda}).")
            print("       As demais paginas estao em dia; a agenda ficou com o "
                  "calendario da rodada anterior.")
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
    sys.exit(main())
