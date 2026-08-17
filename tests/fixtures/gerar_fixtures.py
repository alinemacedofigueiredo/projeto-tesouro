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

# 2.1, 2.2, 2.7 e 2.8 precisam de amostra maior que as demais: 40 linhas
# nao alcancam os rodapes da 2.1 (por volta das linhas 43-46), nem as
# datas escritas como texto na 2.7/2.8 ('mar/18*', 'abr/18*'), nem, na
# 2.8, o segundo bloco de titulo (LTN comeca por volta da linha 193). Na
# 2.2, 40 linhas pegam so parte do bloco Prefixados -- sem nenhum
# subtotal, nota de rodape ou segundo bloco de indexador (Selic comeca na
# linha 117, Indices de Precos na 188); 290 alcanca os tres blocos e todo
# tipo de linha de ruido que a aba intercala entre eles.
#
# A 3.1 empilha tres blocos completos (DPF, DPMFi, DPFe) na mesma aba; o
# ultimo comeca por volta da linha 581 e so termina perto do fim real da
# aba (834 linhas). Com o corte padrao de 40, a amostra so pegaria o
# comeco do bloco DPF, e os testes que separam os tres niveis nao teriam
# como falhar mesmo se o parser misturasse tudo.
LINHAS_POR_ABA = {"2.1": 60, "2.2": 290, "2.7": 150, "2.8": 400, "3.1": 840}

# A 2.1 tambem precisa de mais colunas (meses) que as demais abas: o
# rotulo 'Demais' se repete sob Tesouro Nacional (linha 19) e sob o memo
# de DPMFi no Banco Central (linha 40), mas essas duas series so comecam
# em Jan/06 (coluna 62) -- com o corte padrao de 30 colunas, as duas
# ficam sem nenhum dado na amostra e o filtro de nota de rodape (que
# descarta titulo sem valor em toda a serie) as removeria, mascarando o
# teste de colisao de rotulo em 'Demais' (ver test_estoque.py).
#
# A 4.2 tambem precisa de mais colunas: seu primeiro mes e Dez/05, mas a
# 4.3 (emissoes) so comeca em Dez/10 e, com o corte padrao de 30 colunas,
# vai ate Abr/13 (coluna 89 de Dez/05). Com 30 colunas a 4.2 amostrada
# para em meados de 2008, antes da 4.3 sequer comecar, e o teste que
# compara as duas medidas pela mesma data (custo do estoque vs. custo das
# emissoes) nao teria nenhuma data em comum para verificar.
COLUNAS_POR_ABA = {"2.1": 65, "4.2": 95}


def gerar_rmd():
    origem = RAIZ / "data" / "raw" / "rmd" / "Anexo RMD_Junho_26.xlsx"
    if not origem.exists():
        sys.exit(f"arquivo nao encontrado: {origem}")

    destino = AQUI / "rmd_amostra.xlsx"
    with pd.ExcelWriter(destino, engine="openpyxl") as escritor:
        for aba in ABAS_DA_AMOSTRA:
            # 40 linhas bastam para exercitar cabecalho, hierarquia e as
            # primeiras datas de cada aba -- e, na 1.1, para alcancar a
            # secao RESGATES (comeca por volta da linha 20), que a Tarefa 6
            # precisa para testar a outra metade da tabela. Nao reduza
            # abaixo de 40: ler_padrao_a agora identifica cada linha por
            # linha_origem, entao os rotulos repetidos entre EMISSOES e
            # RESGATES (ex.: "Trocas Oferta Publica", "Tesouro Direto") nao
            # colidem mais, e nao ha motivo para cortar a amostra por causa
            # deles.
            #
            # usecols=range(30) nao e usado aqui porque estoura ParserError
            # nas abas cuja largura real de dados e menor que 30 (ex.: 3.1
            # tem so 15 colunas com dado); em vez disso le-se a largura real
            # e corta-se depois, o que da o mesmo resultado (no maximo 30
            # colunas) sem erro.
            linhas = LINHAS_POR_ABA.get(aba, 40)
            bruto = pd.read_excel(origem, sheet_name=aba, header=None, nrows=linhas)
            bruto = bruto.iloc[:, :COLUNAS_POR_ABA.get(aba, 30)]
            bruto.to_excel(escritor, sheet_name=aba, header=False, index=False)
    print(f"gerado: {destino}")


if __name__ == "__main__":
    gerar_leiloes()
    gerar_rmd()
