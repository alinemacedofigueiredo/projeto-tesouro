"""Recorta amostras pequenas dos arquivos reais para os testes.

Rode uma vez; os arquivos gerados sao versionados para que os testes nao
dependam de rede nem dos arquivos grandes em data/raw/.
"""
import sys
from pathlib import Path

import openpyxl
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
#
# A 3.4 detalha 60 meses e, DEPOIS deles, traz as linhas de resumo: 'Em 12
# meses' ate 'Em 60 meses', a linha 'Apos 5 anos' (o balde de tudo o que
# vence adiante, 2.006,9 bi) e o 'Total'. Com o corte padrao de 40 a
# amostra para no meio dos meses e nunca alcanca o balde -- o parser que
# o procura levantaria LookupError na amostra, e um parser que o
# esquecesse passaria limpo nos testes e gravaria um CSV com 78% do
# estoque. A aba real tem 80 linhas; usa-se ela inteira.
#
# A 5.7 empilha quatro blocos verticais de PAF, cada um com layout
# proprio; o quarto comeca na linha 55, e a aba inteira tem so 69 linhas.
# Com o corte padrao de 40, a amostra parava no meio do terceiro bloco e
# nunca alcancava o quarto -- que e o unico a escrever a revisao como
# 'PAF <ano> (Revisado)' (parenteses, maiuscula) em vez de 'PAF <ano>
# revisado'. Um parser que so reconhecesse a segunda forma passaria limpo
# nos testes e perderia a revisao mais recente da planilha real em
# silencio. Usa-se a aba inteira (69 linhas) para nao depender de onde o
# quarto bloco termina.
LINHAS_POR_ABA = {
    "2.1": 60, "2.2": 290, "2.7": 150, "2.8": 400, "3.1": 840, "3.4": 80,
    "5.7": 69,
}

# A 2.1 tambem precisa de mais colunas (meses) que as demais abas: o
# rotulo 'Demais' se repete sob Tesouro Nacional (linha 19) e sob o memo
# de DPMFi no Banco Central (linha 40), mas essas duas series so comecam
# em Jan/06 (coluna 62) -- com o corte padrao de 30 colunas, as duas
# ficam sem nenhum dado na amostra e o filtro de nota de rodape (que
# descarta titulo sem valor em toda a serie) as removeria, mascarando o
# teste de colisao de rotulo em 'Demais' (ver test_estoque.py).
#
# A 4.3 precisa alcancar jan/2021 -- e a partir dai, o unico ponto onde a
# aba passa de uma coluna por mes para uma trinca de colunas mescladas
# ('Taxa media' / 'Variacao do Indexador' / 'CME'). As trincas comecam na
# coluna 122; 140 colunas cobrem jan/2021 a jun/2021 inteiras, o bastante
# para o teste que ancora num valor concreto da coluna CME (ver
# test_custo.py) -- sem essas colunas, o ramo que le a trinca nunca roda
# nos testes e pode ler a coluna errada sem que nada acuse.
#
# A 4.2 tambem precisa de mais colunas: seu primeiro mes e Dez/05, e
# precisa alcancar pelo menos o mesmo mes mais recente que a 4.3
# amostrada (jun/2021, coluna 187 de Dez/05), senao o teste que compara
# as duas medidas pela mesma data (custo do estoque vs. custo das
# emissoes) encontraria datas na 4.3 que nao existem na 4.2 amostrada.
COLUNAS_POR_ABA = {"2.1": 65, "4.2": 190, "4.3": 140}


def _preservar_formato_percentual_57(origem, destino):
    """Copia a formatacao de celula da 5.7 do arquivo real para a amostra.

    pd.read_excel devolve so o valor de cada celula, nunca a formatacao;
    e bruto.to_excel escreve um arquivo novo, sem nenhuma formatacao
    herdada. No bloco de 2021-2022 da 5.7, o parser (paf_reserva.py)
    distingue realizado em fracao de realizado em pontos percentuais
    pelo `number_format` da celula (ver `_celulas_percentuais`) -- sem
    preservar esse formato na amostra, nenhuma celula da amostra seria
    reconhecida como percentual, e o teste que ancora a conversao
    passaria sem nunca exercitar o caso real.
    """
    linhas = LINHAS_POR_ABA.get("5.7", 40)
    colunas = COLUNAS_POR_ABA.get("5.7", 30)
    livro_origem = openpyxl.load_workbook(origem, data_only=True)
    planilha_origem = livro_origem["5.7"]
    livro_destino = openpyxl.load_workbook(destino)
    planilha_destino = livro_destino["5.7"]
    for linha in range(1, linhas + 1):
        for coluna in range(1, colunas + 1):
            planilha_destino.cell(row=linha, column=coluna).number_format = (
                planilha_origem.cell(row=linha, column=coluna).number_format
            )
    livro_destino.save(destino)


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
    _preservar_formato_percentual_57(origem, destino)
    print(f"gerado: {destino}")


if __name__ == "__main__":
    gerar_leiloes()
    gerar_rmd()
