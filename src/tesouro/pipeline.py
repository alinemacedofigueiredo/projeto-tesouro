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

    if not opcoes.sem_coleta:
        from . import fetch_leiloes, fetch_rmd
        fetch_leiloes.baixar()
        if opcoes.ano and opcoes.mes:
            fetch_rmd.baixar(opcoes.ano, opcoes.mes)
        else:
            print("sem --ano/--mes: usando o RMD ja presente em data/raw/rmd/")

    print("\n--- leiloes ---")
    parse_leiloes.gravar()
    print("\n--- rmd ---")
    parse_rmd.gravar_tudo()
    print("\nconcluido.")


if __name__ == "__main__":
    sys.exit(main())
