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

O projeto usa o `.xlsx` mais recente da pasta **pelo mês escrito no nome**
(ver `leitura_rmd.caminho_do_rmd`) — não pela data de modificação. O
critério era o carimbo do sistema até 09/09/2026 e foi trocado porque
bastava reabrir e salvar um anexo antigo para o projeto inteiro voltar
àquele mês, sem exceção e sem aviso. Por isso o **nome do arquivo tem de
trazer o mês**, como o Tesouro o publica (`Anexo RMD_Agosto_26.xlsx`). Não apague os antigos: eles
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

## 3. Calendário de feriados da Anbima

O calendário de dias úteis (usado em toda conta de PU e DV01, não só no
RMD) vem de um arquivo separado, não do RMD nem dos leilões:

1. Baixe `feriados_nacionais.xls` de
   `anbima.com.br/feriados/arqs/feriados_nacionais.xls`.
2. Coloque em `data/raw/anbima/`.

O arquivo cobre 2001 a 2099. Não precisa ser baixado de novo a cada mês — a
Anbima não republica feriados de anos já fechados, e o arquivo já cobre
décadas à frente.

## 4. Taxa e VNA da Bloomberg (sem terminal)

O DV01, o decay e o resultado mensal (`dv_por_papel.csv`, `decay_por_papel.csv`,
`resultado_mensal.csv`) dependem de taxa e VNA por papel, que normalmente
vêm de `python -m tesouro.fetch_bloomberg` falando com um terminal Bloomberg
instalado na máquina. Num ambiente de banco sem `blpapi` nem terminal, os
mesmos dados saem por `BDH` (a função de série histórica do Excel plugin da
Bloomberg) e entram manualmente, do mesmo jeito que o RMD e os leilões.

**O nome do arquivo precisa seguir o formato ISO abaixo, à risca.** O leitor
(`parse_bloomberg.py`) concatena todos os arquivos de um tipo na ordem
alfabética do nome e, quando duas linhas descrevem a mesma data e o mesmo
papel/índice, fica com a que veio do arquivo lido por último — presumindo
que o nome ordena cronologicamente. Um nome fora do padrão (por exemplo, dia
antes do ano) faz esse "manter o mais recente" pegar o arquivo errado, **sem
erro nenhum** — a puxada nova é descartada em silêncio a favor da antiga.

### Taxa (`YLD_YTM_MID`, fonte `ANDE`)

1. No Excel com o plugin da Bloomberg, monte um `BDH` para cada papel do
   escopo (LTN, NTN-F, NTN-B, LFT), campo `YLD_YTM_MID`, identificador
   `/isin/<ISIN>@ANDE Govt` (o `@ANDE` é obrigatório — sem ele a taxa vem de
   outra fonte, ver `docs/convencoes-dv.md`), periodicidade mensal.
2. Monte um `.csv` com exatamente estas colunas, em qualquer ordem de
   linhas: `isin, titulo, vencimento, data, yld_ytm_mid`. `titulo` é o nome
   do papel (`LTN`, `NTN-F`, `NTN-B` ou `LFT`); `taxa_pct` fica com o nome
   `yld_ytm_mid` no arquivo bruto (é renomeado na leitura).
3. Nomeie o arquivo `bbg_taxas_ANDE_<AAAA-MM>_<AAAA-MM>.csv`, com o
   primeiro e o último mês que o arquivo de fato cobre (ex.:
   `bbg_taxas_ANDE_2010-01_2026-06.csv`).
4. Coloque em `data/raw/bloomberg/`.

### VNA (`IDX_RATIO` para IPCA, `ACCUMULATED_SELIC` para Selic)

1. Monte um `BDH` (ou `BDP`, para a data mais recente) com override de
   `SETTLE_DT` na data desejada — **nunca use esse override para taxa**, só
   para VNA, que é função determinística da data (ver
   `docs/convencoes-dv.md` sobre o erro de 135 bp que o override causa em
   taxa histórica). Campo `IDX_RATIO` para um papel de NTN-B, `ACCUMULATED_
   SELIC` para um papel de LFT — não use `BZAC2000 Index`, que é CDI
   acumulado, não Selic.
2. Multiplique o valor por 1.000 (o campo cru vem como fator, ex.
   `1,874868830`; o VNA em reais é `1.874,868830`).
3. Monte um `.csv` com as colunas: `data, indice, campo, fator, vna,
   n_papeis, divergencia`. `indice` é `IPCA` ou `SELIC`; `campo` é o nome do
   campo Bloomberg usado (`IDX_RATIO` ou `ACCUMULATED_SELIC`); `fator` é o
   valor cru; `vna` é o fator × 1.000; `n_papeis` é quantos papéis do índice
   você conferiu naquela data; `divergencia` é a diferença, em reais, entre
   o maior e o menor VNA implícito entre esses papéis (deve ficar perto de
   zero — o VNA é o mesmo para todo papel do índice na mesma data).
4. Nomeie o arquivo `bbg_vna_<AAAA-MM>_<AAAA-MM>.csv` e coloque em
   `data/raw/bloomberg/`.

### Preço (`PX_DIRTY_MID`, opcional — só para conferência)

Não entra em nenhum cálculo de produção; serve só para o teste que confere
o PU calculado contra o preço de mercado
(`tests/test_coerencia_dv.py::test_pu_reproduz_o_preco_da_bloomberg_com_deslocamento_de_d1`,
que pula sem este arquivo). Colunas: `isin, titulo, data, px_dirty_mid`.
Nome: `bbg_precos_ANDE_<AAAA-MM>_<AAAA-MM>.csv`, mesma pasta.

**Se você apagar um desses três arquivos por engano** e os outros dois do
mesmo período continuarem na pasta, a próxima coleta (`fetch_bloomberg.
baixar()`) para em erro pedindo para apagar o(s) irmão(s) também, um de cada
vez — pode levar duas ou três tentativas. O procedimento completo está em
`docs/convencoes-dv.md`, seção "Recuperando um arquivo apagado à mão em
`data/raw/bloomberg/`".

## Depois de colocar os arquivos

Rode o pipeline sem coleta (comandos no topo deste documento) e confira a
saída: cada CSV gravado aparece com o número de linhas. Os vinte e dois
CSVs esperados estão listados em `docs/fontes-de-dados.md` e detalhados em
`docs/dicionario-de-dados.md`.
