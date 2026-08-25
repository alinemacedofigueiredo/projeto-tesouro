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


def main(argumentos=None):
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument(
        "--sem-coleta", action="store_true",
        help="nao baixa nada; usa os arquivos ja presentes em data/raw/",
    )
    analisador.add_argument("--ano", type=int, help="ano do RMD a baixar")
    analisador.add_argument("--mes", type=int, help="mes do RMD a baixar")
    opcoes = analisador.parse_args(argumentos)

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

    if not opcoes.sem_coleta:
        from . import fetch_leiloes, fetch_rmd
        fetch_leiloes.baixar()
        if opcoes.ano and opcoes.mes:
            fetch_rmd.baixar(opcoes.ano, opcoes.mes)
        else:
            print("sem --ano/--mes: usando o RMD ja presente em data/raw/rmd/")

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

    print("\n--- leiloes ---")
    parse_leiloes.gravar()
    print("\n--- rmd ---")
    parse_rmd.gravar_tudo()

    print("\n--- bloomberg ---")
    from . import parse_bloomberg
    parse_bloomberg.gravar()

    print("\n--- dv01 e decay ---")
    from . import dv as _dv
    _dv.gravar_painel()
    _dv.gravar_decay()
    _dv.gravar_resultado()

    print("\n--- figuras ---")
    from . import figuras
    figuras.gravar_todas()

    print("\n--- dv por leilao ---")
    from . import leiloes_dv
    leiloes_dv.gravar()

    print("\n--- dashboard ---")
    try:
        from .graficos import dashboard
        # DUAS paginas desde 21/08/2026, por tamanho -- ver PAGINAS_DO_RMD.
        for caminho in dashboard.grava_o_rmd():
            print(f"dashboard gravado em {caminho}")
        from .graficos import painel_emissoes
        painel_emissoes.grava_todas()
        # Os nomes saem da tabela de combinacoes, e nao do retorno da funcao: o
        # pipeline nao precisa do valor de volta para dizer o que gravou, e
        # depender dele acoplaria o log ao formato do retorno.
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
        print("pagina do PAF gravada: "
              f"{painel_paf.grava(registros=registros_do_calendario)}")

        # A AGENDA DEPENDE DA REDE, e o pipeline nao. Se a API nao responder, a
        # pagina do que VEM PELA FRENTE deixa de ser regravada e as outras seguem
        # -- a alternativa seria derrubar o dashboard inteiro por causa de um
        # calendario, que e a parte menos essencial do que se gera aqui.
        from .graficos import painel_agenda
        try:
            caminho = painel_agenda.grava()
            print(f"agenda gravada em {caminho}")
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
