"""Caminhos do projeto.

Tudo que precisa saber onde os arquivos moram passa por aqui, para que
mudar a estrutura de pastas seja uma edicao em um lugar so.
"""
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

RAW_DIR = RAIZ / "data" / "raw"
RMD_DIR = RAW_DIR / "rmd"
LEILOES_DIR = RAW_DIR / "leiloes"
PROCESSED_DIR = RAIZ / "data" / "processed"

# Nome do arquivo unico com todo o historico de leiloes desde 2000.
ARQUIVO_LEILOES = "historico-leiloes-todos.xls"
