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
# paginas -- perto de trinta minutos -- mesmo para acrescentar um leilao. Os
# modos existem porque as fontes tem CADENCIAS DIFERENTES: o RMD e mensal, o
# leilao e de terca e quinta, e a banda do PAF muda quando o Tesouro revisa,
# sem aviso e sem periodicidade.
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
                "emissoes", "paf", "agenda"),
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
    "tudo": "atualiza as tres fontes e regrava as sete paginas",
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

    if "leiloes_dv" in passos:
        print("\n--- dv por leilao ---")
        from . import leiloes_dv
        leiloes_dv.gravar()

    print("\n--- dashboard ---")
    try:
        from .graficos import dashboard
        if "dashboard" in passos:
            # DUAS paginas desde 21/08/2026, por tamanho -- ver PAGINAS_DO_RMD.
            for caminho in dashboard.grava_o_rmd():
                print(f"dashboard gravado em {caminho}")
        from .graficos import painel_emissoes
        if "emissoes" in passos:
            painel_emissoes.grava_todas()
        # Os nomes saem da tabela de combinacoes, e nao do retorno da funcao: o
        # pipeline nao precisa do valor de volta para dizer o que gravou, e
        # depender dele acoplaria o log ao formato do retorno.
        if "emissoes" in passos:
            for _, _, arquivo, rotulo in painel_emissoes.COMBINACOES:
                print(f"pagina de emissoes gravada: {arquivo} ({rotulo})")

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
