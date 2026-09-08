"""Le o anexo do RMD DIRETO, sem passar pelo parser do projeto.

Uma ancora de valor conferida contra o nosso proprio parser nao confere nada:
se o parser errar, a ancora erra junto e fica verde. Este modulo abre o .xlsx
e devolve a celula crua, para que o numero da assercao venha da FONTE.

Mora em tests/ de proposito. Nao e codigo de producao e nada em src/ o importa.
"""
from pathlib import Path

import pandas as pd

from tesouro import config


def caminho(mes="julho"):
    """O anexo daquele mes, escolhido PELO NOME.

    leitura_rmd.caminho_do_rmd() escolhe pelo mtime, que dentro do OneDrive nao
    e confiavel -- ele reescreve arquivo sozinho. Aqui a escolha nao muda por
    conta propria.
    """
    alvo = mes.strip().lower()
    for arquivo in sorted(config.RMD_DIR.glob("*.xlsx")):
        if alvo in arquivo.name.lower():
            return arquivo
    raise FileNotFoundError(
        f"nenhum anexo de {mes!r} em {config.RMD_DIR}; ha "
        f"{[p.name for p in sorted(config.RMD_DIR.glob('*.xlsx'))]}"
    )


def aba(nome, mes="julho"):
    """A aba crua: header=None, nada interpretado."""
    return pd.read_excel(caminho(mes), sheet_name=nome, header=None)
