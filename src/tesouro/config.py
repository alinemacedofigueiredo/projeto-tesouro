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

ANBIMA_DIR = RAW_DIR / "anbima"
BLOOMBERG_DIR = RAW_DIR / "bloomberg"

# Um arquivo por DIA DE LEILAO com o dolar que aquele e-mail usou. Nomeado pelo
# dia do leilao e nunca reescrito -- ver fetch_cambio.py.
CAMBIO_DIR = RAW_DIR / "cambio"

# Nome do arquivo unico com todo o historico de leiloes desde 2000.
ARQUIVO_LEILOES = "historico-leiloes-todos.xls"

# Calendario oficial de feriados, baixado de
# anbima.com.br/feriados/arqs/feriados_nacionais.xls
ARQUIVO_FERIADOS = "feriados_nacionais.xls"
