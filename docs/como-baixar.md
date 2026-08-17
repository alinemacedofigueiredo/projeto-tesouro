# Download manual (ambiente sem internet)

Os parsers nunca acessam a rede. Basta colocar os arquivos certos nas
pastas certas e rodar o pipeline com `--sem-coleta`:

PowerShell:

    $env:PYTHONPATH="src"; python -m tesouro.pipeline --sem-coleta

bash:

    PYTHONPATH=src python -m tesouro.pipeline --sem-coleta

## 1. Anexo do RMD

1. Acesse `tesourotransparente.gov.br`, seção Publicações → Relatório
   Mensal da Dívida, e escolha o mês desejado.
2. Baixe o **anexo** (nome parecido com `Anexo RMD_Junho_26.zip` ou já
   `.xlsx`) — não o relatório em PDF.
3. Se vier compactado, extraia o `.xlsx`.
4. Coloque o `.xlsx` em `data/raw/rmd/`.

O projeto usa o `.xlsx` mais recente da pasta (por data de modificação do
arquivo — ver `leitura_rmd.caminho_do_rmd`). Não apague os antigos: eles
preservam os retratos mensais da aba 3.4 (`cronograma_vencimentos.csv`),
que é substituída a cada execução e não tem histórico dentro do próprio
arquivo.

## 2. Histórico de leilões

1. Baixe `historico-leiloes-todos.xls` de
   `sisweb.tesouro.gov.br/apex/cosis/rleiloes/arquivos/todos/desc/historico-leiloes-todos.xls`
2. Coloque em `data/raw/leiloes/`.

### Se a biblioteca `xlrd` não estiver disponível

O arquivo de leilões é `.xls` legado (formato OLE2) e exige a biblioteca
`xlrd` para o pandas conseguir lê-lo. Se `xlrd` não estiver disponível no
ambiente de destino:

1. Abra o `.xls` no Excel.
2. Salve como `.xlsx`, na mesma pasta (`data/raw/leiloes/`).
3. Ajuste `ARQUIVO_LEILOES` em `src/tesouro/config.py` para o novo nome de
   arquivo.

O parser (`parse_leiloes.py`) lê os dois formatos sem nenhuma outra
alteração — a leitura passa por `pandas.read_excel`, que escolhe o motor
(`xlrd` ou `openpyxl`) pela extensão do arquivo.

## Depois de colocar os arquivos

Rode o pipeline sem coleta (comandos no topo deste documento) e confira a
saída: cada CSV gravado aparece com o número de linhas. Os dezessete CSVs
esperados estão listados em `docs/fontes-de-dados.md` e detalhados em
`docs/dicionario-de-dados.md`.
