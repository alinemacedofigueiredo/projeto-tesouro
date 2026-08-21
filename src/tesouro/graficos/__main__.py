"""Gera o dashboard da divida.

    PowerShell:  $env:PYTHONPATH="src"; python -m tesouro.graficos
    bash:        PYTHONPATH=src python -m tesouro.graficos

Sem argumento, grava as DUAS paginas do dashboard -- dashboard.html, com estoque,
prazo e custo, e dashboard-funding.html, com funding e detentores -- cada uma com
as quatro janelas (12 meses, 3 anos, 5 anos e serie completa) e os botoes que
alternam entre elas. Uma barra no alto liga as duas.

Com --saida, grava UMA pagina so, com todos os graficos, no caminho pedido. Serve
para inspecionar; nao e o formato publicado, e pode estourar o limiar de 10 MB.

Com --de e --ate, grava o recorte pedido, e o botao some porque so existe uma
janela. Os dois andam juntos: um sem o outro e erro, nao recorte pela metade.
"""

import argparse
import sys

import pandas as pd

from . import dashboard


def _data(texto, campo, erros):
    """Converte AAAA-MM-DD, acumulando o erro em vez de levantar.

    O formato vai EXPLICITO: pd.Timestamp("01/01/2021") aceita e devolve 1 de
    janeiro, entao a data em formato brasileiro passaria batido e o recorte sairia
    de um lugar que ninguem pediu.
    """
    try:
        return pd.to_datetime(texto, format="%Y-%m-%d")
    except (ValueError, TypeError):
        erros.append(f"{campo}: '{texto}' nao e uma data no formato AAAA-MM-DD")
        return None


def main(argumentos=None):
    analisador = argparse.ArgumentParser(
        prog="python -m tesouro.graficos", description=__doc__)
    analisador.add_argument("--de", help="inicio do recorte, AAAA-MM-DD")
    analisador.add_argument("--ate", help="fim do recorte, AAAA-MM-DD")
    analisador.add_argument("--saida", help="caminho do HTML a gravar")
    opcoes = analisador.parse_args(argumentos)

    erros = []
    if bool(opcoes.de) != bool(opcoes.ate):
        falta = "--ate" if opcoes.de else "--de"
        erros.append(f"{falta} tambem e necessario: o recorte precisa dos dois "
                     f"extremos, senao nao da para saber onde ele termina")

    recortes = None
    if opcoes.de and opcoes.ate:
        de = _data(opcoes.de, "--de", erros)
        ate = _data(opcoes.ate, "--ate", erros)
        if de is not None and ate is not None:
            if ate < de:
                erros.append(f"--ate ({opcoes.ate}) e anterior a --de "
                             f"({opcoes.de})")
            else:
                recortes = [(f"{opcoes.de} a {opcoes.ate}", (de, ate))]

    if erros:
        for erro in erros:
            print(f"erro: {erro}", file=sys.stderr)
        return 2

    from pathlib import Path
    if opcoes.saida:
        # Caminho explicito quer dizer UM arquivo: nao ha como espalhar duas
        # paginas num nome so, e inventar "-funding" no meio do nome que a pessoa
        # deu seria escrever onde nao foi pedido.
        gravado = dashboard.grava(Path(opcoes.saida), recortes)
        print(f"dashboard gravado em {gravado}")
        return 0

    for gravado in dashboard.grava_o_rmd(recortes):
        print(f"dashboard gravado em {gravado}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
