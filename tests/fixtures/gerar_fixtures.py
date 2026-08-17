"""Recorta amostras pequenas dos arquivos reais para os testes.

Rode uma vez; os arquivos gerados sao versionados para que os testes nao
dependam de rede nem dos arquivos grandes em data/raw/.
"""
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
AQUI = Path(__file__).resolve().parent


def gerar_leiloes():
    origem = RAIZ / "data" / "raw" / "leiloes" / "historico-leiloes-todos.xls"
    if not origem.exists():
        sys.exit(f"arquivo nao encontrado: {origem}")

    # Tres anos que cobrem as variacoes: 2000 (colunas do Bacen em branco),
    # 2011 (taxa zerada para LFT) e 2026 (formato atual).
    abas = ["Ano 2000", "Ano 2011", "Ano 2026"]
    destino = AQUI / "leiloes_amostra.xlsx"
    with pd.ExcelWriter(destino, engine="openpyxl") as escritor:
        for aba in abas:
            bruto = pd.read_excel(origem, sheet_name=aba, header=None, nrows=20)
            bruto.to_excel(escritor, sheet_name=aba, header=False, index=False)
    print(f"gerado: {destino}")


ABAS_DA_AMOSTRA = [
    "1.1", "1.2", "2.1", "2.2", "2.4", "2.7", "2.8",
    "3.1", "3.3", "3.4", "3.7", "3.8", "3.9",
    "4.1", "4.2", "4.3", "5.7", "6.1",
]


# A aba 1.1 repete os mesmos rotulos de categoria ("Trocas Oferta Publica",
# "Tesouro Direto", "Divida Mobiliaria" ...) com a mesma indentacao debaixo
# de "EMISSOES" e de novo debaixo de "RESGATES" -- duas secoes de dados
# genuinamente distintas que o par (rotulo, data) sozinho nao diferencia.
# Cortar a amostra antes da secao RESGATES evita essa colisao; a secao de
# EMISSOES ja basta para exercitar cabecalho, hierarquia, a primeira data
# da serie e o descarte dos totais anuais intercalados nas colunas (esse
# descarte depende da linha de cabecalho, nao da quantidade de linhas de
# dado, entao continua exercitado).
_NROWS_PERSONALIZADO = {"1.1": 20}


def gerar_rmd():
    origem = RAIZ / "data" / "raw" / "rmd" / "Anexo RMD_Junho_26.xlsx"
    if not origem.exists():
        sys.exit(f"arquivo nao encontrado: {origem}")

    destino = AQUI / "rmd_amostra.xlsx"
    with pd.ExcelWriter(destino, engine="openpyxl") as escritor:
        for aba in ABAS_DA_AMOSTRA:
            # 40 linhas bastam para exercitar cabecalho, hierarquia e as
            # primeiras datas de cada aba (excecao: ver _NROWS_PERSONALIZADO
            # acima). usecols=range(30) nao e usado aqui porque estoura
            # ParserError nas abas cuja largura real de dados e menor que 30
            # (ex.: 3.1 tem so 15 colunas com dado); em vez disso le-se a
            # largura real e corta-se depois, o que da o mesmo resultado
            # (no maximo 30 colunas) sem erro.
            nrows = _NROWS_PERSONALIZADO.get(aba, 40)
            bruto = pd.read_excel(
                origem, sheet_name=aba, header=None, nrows=nrows,
            )
            bruto = bruto.iloc[:, :30]
            bruto.to_excel(escritor, sheet_name=aba, header=False, index=False)
    print(f"gerado: {destino}")


if __name__ == "__main__":
    gerar_leiloes()
    gerar_rmd()
