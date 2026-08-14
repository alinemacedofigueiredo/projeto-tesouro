# Camada de dados — Tesouro Nacional (sub-projeto A)

**Data:** 2026-08-14
**Status:** design aprovado, aguardando plano de implementação

---

## 1. Contexto

Este documento especifica a **camada de dados** de um projeto maior de análise
da Dívida Pública Federal. O projeto completo tem cinco entregas:

1. Dashboard de análise da dívida (funding, estoque, rolagem e custo)
2. DV01 da dívida por papel, decay e P&L do estoque numa janela
3. Análise dos leilões: risco emitido, financeiro e DV por leilão e por papel
4. Análise contra o PAF: composição, prazo médio e total contra a banda vigente
5. Simulação de trajetória contra o PAF e sensibilidade de quanto emitir por leilão

Nenhuma delas funciona sem dados confiáveis e estruturados. Este sub-projeto
entrega só isso: os dados do Tesouro, baixados e convertidos em tabelas limpas.
As análises 1–5 são sub-projetos posteriores, cada um com sua própria spec.

### Restrições que moldaram o desenho

- **O projeto será levado para um banco**, com ambiente mais restrito de rede e
  de bibliotecas. Confirmado que lá há Python com pandas.
- **Outras pessoas vão alterar o projeto** ao longo do tempo. Documentação e
  rastreabilidade até a fonte são requisitos, não enfeite.
- **O output inicial pode ser um PDF**; o dashboard fica para o final.

---

## 2. Escopo

**Dentro:** baixar e estruturar 18 abas do anexo do Relatório Mensal da Dívida
(RMD) e o histórico de leilões da Dívida Pública Mobiliária Federal Interna.

**Fora:** qualquer cálculo analítico (DV01, decay, P&L, simulação), gráficos,
dashboard, preço diário de mercado, calendário futuro de leilões.

---

## 3. Decisão de arquitetura: coleta e interpretação separadas

O fluxo é sempre:

```
fetch → data/raw/ → parse → data/processed/
```

`fetch_*.py` baixa e grava arquivos originais. `parse_*.py` lê **apenas** de
`data/raw/` e produz CSVs. Nenhum parser conhece a internet; nenhum coletor
interpreta conteúdo.

**Por que assim:** no ambiente do banco, ninguém executa o `fetch`. Uma pessoa
baixa os arquivos manualmente e os coloca em `data/raw/`, e os parsers funcionam
sem alteração nenhuma. A "troca de fonte" é literalmente não rodar um script.

Foram consideradas e descartadas duas alternativas: uma interface `DataSource`
plugável (indireção que todo mantenedor futuro teria que entender, para um ganho
que ainda não existe) e uma configuração declarativa em YAML (as fontes são
heterogêneas demais — um zip com Excel multi-aba versus um XLS anual — e o YAML
viraria só uma capa sobre código específico de cada uma).

Se um dia a fonte passar a ser um banco de dados interno da instituição, ela
entra como um terceiro script que popula `data/raw/`, sem retrabalho.

### Imutabilidade dos brutos

Arquivos em `data/raw/` nunca são modificados nem removidos. Se o Tesouro
republicar um mês, entra um arquivo novo e o antigo permanece. Isso dá
auditoria, permite reprocessar o passado, e faz o histórico das tabelas de
retrato (ver §6) se acumular sozinho.

---

## 4. Estrutura de pastas

```
Projeto Tesouro/
├── data/
│   ├── raw/               # originais, intocados (nao versionados)
│   │   ├── rmd/
│   │   └── leiloes/
│   └── processed/         # CSVs canonicos (nao versionados)
├── src/tesouro/
│   ├── fetch_rmd.py
│   ├── fetch_leiloes.py
│   ├── parse_rmd.py
│   └── parse_leiloes.py
├── docs/
│   ├── fontes-de-dados.md
│   ├── dicionario-de-dados.md
│   └── como-baixar.md
└── tests/
```

Os dados ficam fora do controle de versão: os brutos são baixáveis do Tesouro e
os processados são reconstruíveis pelos parsers.

---

## 5. Fontes

### 5.1 Relatório Mensal da Dívida (RMD)

Publicado mensalmente em
`tesourotransparente.gov.br/publicacoes/relatorio-mensal-da-divida-rmd/{ano}/{mes}`.

O anexo com as tabelas vem num `.zip` hospedado num servidor de arquivos com
**ID numérico imprevisível**, que muda a cada publicação. Não é possível montar
a URL do arquivo diretamente: o coletor precisa abrir a página da publicação e
extrair de lá o link do anexo.

Quase todas as abas contêm a **série histórica completa**, então basta o RMD
mais recente — não é preciso baixar edições passadas.

### 5.2 Histórico de leilões

Dataset `ds013` no portal de dados abertos, acessível pela API CKAN:

```
tesourotransparente.gov.br/ckan/api/3/action/package_show?id=ds013
```

A resposta lista os recursos: um arquivo com todo o histórico desde 2000 e
arquivos anuais (2000–2024) em XLS/XLSX. As URLs vêm da API, não são fixadas
no código.

### 5.3 Fontes descartadas

- **PAF como fonte separada:** as bandas históricas estão dentro do RMD
  (aba 5.7). Não é preciso ler os PDFs do PAF.
- **Dataset `metas-paf` do CKAN:** apesar do nome, refere-se ao Programa de
  Reestruturação e Ajuste Fiscal de estados e do Distrito Federal. Não tem
  relação com as bandas da Dívida Pública Federal.
- **Calendário de leilões:** só existe como portaria em PDF. Necessário apenas
  para a entrega 5 (simulação), portanto fora deste sub-projeto.

---

## 6. Convenções das tabelas canônicas

**Formato longo, nunca largo.** As abas do RMD têm meses como colunas, ganhando
uma coluna nova a cada publicação. Um CSV nesse formato quebraria todo código
consumidor todo mês. Em formato longo (`data`, dimensões, `valor`), um mês novo
é apenas mais uma linha.

**Unidade única: R$ milhões.** O arquivo mistura unidades entre abas — 1.1 e 3.4
em `R$ Milhões`, 2.4 e 6.1 em `R$ Bilhões`. Somar duas sem perceber produz erro
de mil vezes que não gera exceção nenhuma. A conversão acontece na entrada.
Percentuais são gravados como percentual (`12.5` = 12,5%), não como fração.

**Nada derivado é gravado.** Médias móveis, acumulados, participações, spreads e
composições percentuais são calculados em funções testáveis, nunca persistidos.
O CSV guarda somente o que veio do Tesouro.

**Ausente é nulo, nunca zero.** O arquivo usa convenções diferentes em abas
diferentes: `N/D` na 3.1, `-` na 3.9, células vazias em várias. Todas viram
campo vazio no CSV. Zero é um valor legítimo e distinto.

**Datas normalizadas para `AAAA-MM-DD`,** sempre no último dia do mês de
referência. A origem varia: número de série do Excel em umas abas (2.4, 3.1),
texto `Jan/10` em outras (1.1, 2.2).

**Séries versus retratos.** Quase todas as abas são séries históricas que
crescem. A 3.4 é um retrato: olha para frente a partir da data de fechamento e
é substituída a cada mês. Tabelas de retrato levam `data_referencia` em vez de
`data`. Decidido coletar apenas o retrato atual; como os brutos são imutáveis,
o histórico se acumula naturalmente a cada execução mensal.

---

## 7. Tabelas canônicas

Dezessete CSVs em `data/processed/`.

| CSV | Origem | Colunas |
|---|---|---|
| `funding_por_canal` | 1.1 | data, esfera, operacao, canal, valor_milhoes |
| `funding_por_indexador` | 1.2 | data, operacao, indexador, valor_milhoes |
| `estoque_dpf` | 2.1 | data, nivel, entidade, titulo, valor_milhoes |
| `estoque_titulos_vencimento` | 2.2 | data, indexador, titulo, vencimento, isin, quantidade_mil, financeiro_milhoes |
| `composicao_dpf` | 2.4 | data, indexador, valor_milhoes |
| `detentores` | 2.7 | data, detentor, valor_milhoes |
| `detentores_por_titulo` | 2.8 | data, detentor, titulo, valor_milhoes |
| `vencimentos_faixa` | 3.1 | data, faixa, valor_milhoes |
| `vencer_12m_indexador` | 3.3 | data, indexador, valor_milhoes |
| `cronograma_vencimentos` | 3.4 | **data_referencia**, mes_vencimento, grupo_titulo, valor_milhoes |
| `prazo_medio_por_titulo` | 3.7 | data, nivel, entidade, titulo, prazo_anos |
| `prazo_medio_por_indexador` | 3.8 | data, nivel, categoria, prazo_anos |
| `prazo_medio_emissoes` | 3.9 | data, indexador, prazo_anos |
| `custo_medio` | 4.1 + 4.2 + 4.3 | data, medida, nivel, titulo, custo_aa_pct |
| `paf_metas` | 5.7 | ano, versao, indicador, minimo, maximo, realizado |
| `reserva_liquidez` | 6.1 | data, reserva_milhoes, valor_prudencial_milhoes, indice_liquidez_meses |
| `leiloes` | CKAN ds013 | definido na implementação, após inspeção do arquivo |

### Critério de consolidação

Duas abas viram uma tabela só quando compartilham as **mesmas dimensões** e
diferem apenas na **medida**.

As três abas de custo passam: 4.1, 4.2 e 4.3 são todas indexadas por nível e
título, mudando só o que medem. Viram uma coluna `medida` com os valores
`mensal`, `acum_12m` e `emissoes_12m`. Comparar custo de emissão contra custo
de estoque — o gráfico mais informativo da seção 4 — passa a ser um filtro em
vez de um join.

As três abas de prazo médio reprovam: a 3.7 abre por título, a 3.8 por indexador
(na DPMFi) e por instrumento (na DPFe), a 3.9 por indexador sobre emissões.
Uni-las exigiria uma coluna polimórfica — que significa "título" numas linhas e
"indexador" noutras — e um agrupamento acidental somaria grandezas
incomparáveis sem gerar erro.

---

## 8. Armadilhas conhecidas do anexo

Levantadas na inspeção do RMD de junho/2026. Cada uma precisa de tratamento
explícito e de um teste.

1. **A aba 1.1 mistura colunas mensais com totais anuais** na mesma linha de
   cabeçalho (`Jan/07 ... Dez/07`, depois `2007`). As colunas anuais precisam
   ser identificadas e descartadas, ou o total do ano entra como se fosse mês.
2. **A aba 5.7 são blocos empilhados verticalmente**, cada um cobrindo um
   intervalo de anos com layout próprio.
3. **Nomes de indicador mudam ao longo do tempo** na 5.7: `Selic` (2003–2010)
   vira `Taxa Flutuante` (2011 em diante); `Demais` desaparece após 2010.
4. **Revisões do PAF aparecem como colunas extras** (`PAF 2008 revisado`,
   `PAF 2015 revisado`, `PAF 2016 revisado`), mas **a aba não traz a data de
   publicação da revisão**. Como cada banda vale até a publicação seguinte, essa
   data precisa vir de fora — é o único ponto de entrada manual do projeto.
5. **A aba 4.3 parece mudar de layout a partir de Jan/21**, com um segundo nível
   de cabeçalho ausente no trecho antigo. Confirmar na implementação.
6. **Custo negativo é legítimo** (NTN-D em 2005, na 4.1) e não deve ser tratado
   como erro de leitura.
7. **Abas são descontinuadas** (3.5 em junho/2025, 5.6 em junho/2025). Continuam
   listadas no índice sem existirem como aba. O parser deve tolerar ausência de
   aba esperada com mensagem clara, não com exceção obscura.
8. **A 2.2 agrupa títulos em blocos por indexador**, com cabeçalhos de seção no
   meio da planilha, e usa duas colunas por mês (quantidade e financeiro).

### Questão em aberto

O campo `Financeiro` da aba 2.2 precisa ser confirmado como **preço de mercado
ou preço de curva**, consultando a metodologia do Tesouro. A entrega 2 deriva o
preço unitário desse campo para extrair a taxa implícita; se for preço de curva,
a taxa não é de mercado e o DV01 sai enviesado. Resolver antes de iniciar a
entrega 2 — não bloqueia esta camada de dados.

---

## 9. Testes

Os testes relevantes não são de execução, são de **coerência entre abas** — é
onde um parser errado se esconde, produzindo números plausíveis e falsos.

1. **2.2 contra 2.1:** a soma do financeiro da 2.2 por título tem que bater com
   as linhas de título da 2.1 no mesmo mês. É a principal defesa da aba mais
   complicada do arquivo, e ela alimenta o DV01 inteiro.
2. **3.1 contra 3.3:** o percentual a vencer em 12 meses tem que ser consistente
   entre as duas abas.
3. **Composição fecha em 100%:** as participações da 2.4 somam o total.
4. **Continuidade:** nenhuma série pode ter mês faltando no meio.
5. **Unidades:** verificação de ordem de grandeza por tabela, para pegar erro de
   mil vezes.

Os *fixtures* são recortes pequenos do arquivo real, versionados junto ao
código, para que os testes não dependam de rede.

---

## 10. Documentação a produzir

- **`fontes-de-dados.md`** — mapa das fontes: o que existe, onde, em que formato,
  e o caminho de cada uma até cada CSV. Inclui a representação visual do fluxo.
- **`dicionario-de-dados.md`** — uma entrada por CSV: colunas, tipos, unidades,
  aba de origem e armadilhas conhecidas.
- **`como-baixar.md`** — passo a passo do download manual, para ambientes sem
  acesso de rede.

---

## 11. Decisões adiadas

| Assunto | Decisão | Quando revisitar |
|---|---|---|
| Granularidade diária de preços | Fora de escopo; a análise fica mensal | Se a entrega 2 exigir janela intradiária |
| Histórico de retratos da 3.4 | Só o retrato atual | Se surgir necessidade de backtest do perfil |
| Abas 5.1, 5.2, 5.3 (mercado secundário) | Fora | Se a análise de leilões pedir contexto de liquidez |
| Calendário de leilões | Fora | Necessário para a entrega 5 |
| Aba 5.4 (exposição com mercado aberto) | Descartada | — |
