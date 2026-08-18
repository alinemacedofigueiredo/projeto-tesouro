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
        # com internet.
        from . import fetch_bloomberg
        try:
            fetch_bloomberg.baixar()
        except Exception as erro:               # noqa: BLE001
            print(f"coleta da Bloomberg pulada: {erro}")

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

    print("\nconcluido.")


if __name__ == "__main__":
    sys.exit(main())
