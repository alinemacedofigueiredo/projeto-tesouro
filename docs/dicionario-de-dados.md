# Dicionário de dados

Um CSV por seção, dezessete no total, gerados por `python -m tesouro.pipeline`
em `data/processed/`. As colunas abaixo foram conferidas contra o código dos
parsers (`src/tesouro/parse_rmd/*.py`, `src/tesouro/parse_leiloes.py`) e
contra os CSVs gerados — não contra a especificação original, que foi escrita
antes da implementação e ficou desatualizada em alguns pontos.

Convenções gerais (ver também `docs/superpowers/specs/2026-08-14-camada-de-dados-design.md`,
§6):

- Formato longo: uma linha por combinação de data e dimensões, nunca uma
  coluna por mês.
- Unidade monetária única: R$ milhões (`*_milhoes`), mesmo quando a aba de
  origem publica em bilhões.
- Percentuais são gravados como percentual (`12.5` = 12,5%), nunca fração —
  exceto onde anotado.
- Ausência de dado é célula vazia, nunca zero. Zero é valor legítimo.
- `data` é sempre o último dia do mês de referência (`AAAA-MM-DD`).
- Nada derivado é gravado: totais, percentuais e médias calculáveis a partir
  de outras linhas não entram no CSV.

---

### `funding_por_canal.csv`

Emissões e resgates da DPF por canal de colocação, mês a mês. Origem: aba 1.1.

| Coluna | Tipo | Descrição |
|---|---|---|
| `data` | data | Último dia do mês |
| `esfera` | texto | `DPMFi`, `DPFe` ou `Banco Central` |
| `operacao` | texto | `emissao` ou `resgate` |
| `canal` | texto | Canal de colocação (Oferta Pública, Tesouro Direto, Trocas Oferta Pública, Cancelamentos, Compras, Vencimentos, NBC-E, Dívida Mobiliária, Dívida Contratual, Emissão Direta com/sem Financeiro, Transferência de Carteira, Pagamento de Dividendos…) |
| `valor_milhoes` | número | R$ milhões |

**Atenção:** `esfera` faz parte da chave porque rótulos se repetem entre
seções — "Trocas Oferta Pública" e "Tesouro Direto" existem tanto do lado de
emissão quanto do lado de resgate, e a aba numera as esferas com algarismo
romano crescente (`I - DPMFi`, `II - DPFe` sob emissões; `III - DPMFi`,
`IV - DPFe` sob resgates). Totais derivados (linhas a partir de "Emissão
Líquida") não entram na tabela.

---

### `funding_por_indexador.csv`

Emissões e resgates da DPF por indexador, mês a mês. Origem: aba 1.2.

| Coluna | Tipo | Descrição |
|---|---|---|
| `data` | data | Último dia do mês |
| `esfera` | texto | `DPMFi` ou `DPFe` |
| `operacao` | texto | `emissao` ou `resgate` |
| `indexador` | texto | Indexador na DPMFi (Prefixado, Taxa Flutuante, Índice de Preços, Câmbio, Demais); moeda na DPFe (Dólar, Euro, Real, Demais) |
| `valor_milhoes` | número | R$ milhões |

**Atenção:** `esfera` entra na chave porque "Demais" existe nas duas esferas
com valores diferentes — sem a esfera na chave, uma sobrescreveria a outra.

---

### `estoque_dpf.csv`

Estoque da Dívida Pública Federal, por nível, entidade e título, mês a mês.
Origem: aba 2.1.

| Coluna | Tipo | Descrição |
|---|---|---|
| `data` | data | Último dia do mês |
| `nivel` | texto | `DPF em poder do publico`, `DPMFi`, `DPFe` ou `DPMFi em poder do Banco Central` (memorando) |
| `entidade` | texto | `Tesouro Nacional` / `Banco Central` (sob DPMFi) ou `Dívida Mobiliária` / `Dívida Contratual` (sob DPFe); vazio nas linhas de nível |
| `titulo` | texto | Nome do título; **vazio** nas linhas que são subtotal de nível ou de entidade |
| `valor_milhoes` | número | R$ milhões |

**Atenção:** a tabela guarda a hierarquia inteira, não só as folhas — linhas
com `titulo` vazio são subtotais de `nivel`/`entidade` e trazem valor
próprio. Para somar só os títulos, filtre `titulo.notna()`; somar tudo sem
filtrar conta cada subtotal em cima dos títulos que ele já soma.

Os títulos aqui são **agregados**: `NTN-B` inclui `NTN-B Principal`, `LFT`
inclui `LFT-TD1 Reserva`, `NTN-B1` inclui `EducA+` e `RendA+` (ver
`estoque_titulos_vencimento.csv`, que traz esses mesmos títulos
desagregados). Reconciliar as duas tabelas exige somar os sub-títulos da 2.2
por título-pai; a soma bate com a 2.1 na casa de ruído de ponto flutuante, e
`tests/test_coerencia.py::test_estoque_por_vencimento_bate_com_estoque_por_titulo`
garante isso contra o RMD real.

---

### `estoque_titulos_vencimento.csv`

Estoque de cada papel da DPMFi, por vencimento, mês a mês. Origem: aba 2.2.

| Coluna | Tipo | Descrição |
|---|---|---|
| `data` | data | Último dia do mês de referência |
| `indexador` | texto | Bloco da planilha (Prefixados, Selic, Índice de Preços…) |
| `titulo` | texto | LTN, LFT, NTN-B, NTN-F, NTN-C, LFT-TD1 Reserva, NTN-B Principal, NTN-B1 EducA+, NTN-B1 RendA+… |
| `vencimento` | data | Vencimento do papel |
| `isin` | texto | Código ISIN |
| `quantidade_mil` | número | Milhares de títulos (posição) |
| `financeiro_milhoes` | número | R$ milhões |

**Atenção:** `quantidade_mil` é o campo que sustenta o cálculo de DV01 — é a
posição em título. Não está confirmado se `financeiro_milhoes` é marcação a
mercado ou na curva (a suspeita é curva); por isso ele serve de conferência,
não de fonte de preço. Os títulos aqui aparecem **desagregados** em relação
a `estoque_dpf.csv` — ver a nota daquela tabela.

---

### `composicao_dpf.csv`

Composição percentual da DPF por indexador, mês a mês (só o valor em
R$ milhões é gravado; o percentual publicado ao lado é derivado e descartado).
Origem: aba 2.4.

| Coluna | Tipo | Descrição |
|---|---|---|
| `data` | data | Último dia do mês |
| `indexador` | texto | Prefixado, Taxa Flutuante, Índice Preços, Câmbio, Demais |
| `valor_milhoes` | número | R$ milhões |

---

### `detentores.csv`

Estoque da DPMFi por classe de detentor, mês a mês. Origem: aba 2.7.

| Coluna | Tipo | Descrição |
|---|---|---|
| `data` | data | Último dia do mês |
| `detentor` | texto | Instituições Financeiras, Fundos de Investimento, Previdência, Não-residentes, Governo, Seguradoras, Outros, Tesouro Direto (os rótulos vêm com o número de nota de rodapé colado, ex.: `Instituições Financeiras 1`) |
| `valor_milhoes` | número | R$ milhões |

A coluna `Total` da aba (soma dos demais detentores) é derivada e não entra
na tabela.

---

### `detentores_por_titulo.csv`

Participação dos detentores, aberta por título, mês a mês. Origem: aba 2.8.

| Coluna | Tipo | Descrição |
|---|---|---|
| `data` | data | Último dia do mês |
| `detentor` | texto | Fundos, Governo, Inst. Financeiras, Não-residente, Outros, Previdência, Seguradoras, Tesouro Direto |
| `titulo` | texto | `LFT`, `LTN`, `NTN-B`, `NTN-F`, `OUTROS` |
| `valor_milhoes` | número | R$ milhões |

**Atenção:** dois meses por bloco de título trazem a data em texto com
asterisco na planilha original (ex.: `mar/18*`), marcando meses retificados
pelo Tesouro; o parser reconhece essa forma e a data entra normalmente. A
coluna `Total` de cada bloco é derivada e não entra na tabela.

---

### `vencimentos_faixa.csv`

Perfil de vencimento por faixa de prazo, nos três níveis, mês a mês. Origem:
aba 3.1.

| Coluna | Tipo | Descrição |
|---|---|---|
| `data` | data | Último dia do mês |
| `nivel` | texto | `DPF`, `DPMFi` ou `DPFe` |
| `faixa` | texto | Até 12 meses, De 1 a 2 anos, De 2 a 3 anos, De 3 a 4 anos, De 4 a 5 anos, Acima de 5 anos |
| `valor_milhoes` | número | R$ milhões |

A aba publica os três níveis como blocos empilhados independentes; a série
de `DPF` começa em nov/2006, mais tarde que `DPMFi` (que cobre desde 1999).
`tests/test_coerencia.py::test_dpmfi_mais_dpfe_fecha_a_dpf_por_faixa` garante
que `DPMFi + DPFe == DPF`, faixa a faixa, onde os três coexistem.

---

### `vencer_12m_indexador.csv`

Títulos a vencer nos próximos 12 meses, por indexador, mês a mês. Origem:
aba 3.3.

| Coluna | Tipo | Descrição |
|---|---|---|
| `data` | data | Último dia do mês |
| `indexador` | texto | Prefixado, Taxa Flutuante, Índices de preços, Câmbio, Demais |
| `valor_milhoes` | número | R$ milhões |

---

### `cronograma_vencimentos.csv`

Cronograma de vencimentos futuros da DPMFi. Origem: aba 3.4.

| Coluna | Tipo | Descrição |
|---|---|---|
| `data_referencia` | data | Data de fechamento do retrato (carimbo "Fechamento de DD/MM/AAAA" da aba) |
| `mes_vencimento` | data | Último dia do mês de vencimento futuro |
| `grupo_titulo` | texto | LFT, LTN / NTN-F, NTN-B, NTN-C, Demais |
| `valor_milhoes` | número | R$ milhões — **inclui juros**, não é só principal |

**Atenção — esta é a única tabela de retrato do projeto, não série
histórica.** Todas as outras dezesseis tabelas acumulam o histórico
completo, mês a mês; esta olha para frente a partir de `data_referencia` e é
substituída inteira a cada mês. Como os arquivos brutos em `data/raw/` nunca
são apagados, rodar o pipeline em meses sucessivos acumula um retrato por
mês (identificados por `data_referencia` distintos) mesmo a tabela sendo, a
cada execução, reconstruída do zero a partir do RMD mais recente.

---

### `prazo_medio_por_titulo.csv`

Prazo médio da dívida, em anos, por nível/entidade/título, mês a mês.
Origem: aba 3.7.

| Coluna | Tipo | Descrição |
|---|---|---|
| `data` | data | Último dia do mês |
| `nivel` | texto | `DPF`, `DPMFi` ou `DPFe` |
| `entidade` | texto | `Tesouro Nacional` / `Banco Central` (DPMFi) ou `Dívida Mobiliária` / `Dívida Contratual` (DPFe); vazio nas linhas de nível |
| `titulo` | texto | Nome do título; vazio nas linhas de nível/entidade (que carregam o prazo médio agregado) |
| `prazo_anos` | número | Prazo médio em anos |

A linha com `nivel = "DPF"` e `titulo` vazio traz o prazo médio agregado que
a análise compara contra a banda do PAF.

---

### `prazo_medio_por_indexador.csv`

Prazo médio da dívida, em anos, por indexador (DPMFi) ou instrumento (DPFe),
mês a mês. Origem: aba 3.8.

| Coluna | Tipo | Descrição |
|---|---|---|
| `data` | data | Último dia do mês |
| `nivel` | texto | `DPF`, `DPMFi` ou `DPFe` |
| `entidade` | texto | `Dívida Mobiliária` / `Dívida Contratual` sob DPFe; **sempre vazio nas linhas de `DPMFi`** |
| `categoria` | texto | Indexador (Prefixados, Taxa Flutuante, Índice de Preços, Câmbio, Demais) ou instrumento |
| `prazo_anos` | número | Prazo médio em anos |

**Atenção:** `entidade` é vazia em todas as linhas de nível `DPMFi`. Isso é
estrutural, não dado faltando — a aba 3.8 abre direto por indexador dentro
da DPMFi, sem o agrupamento por `Tesouro Nacional`/`Banco Central` que a
aba 3.7 tem. Só a DPFe tem subgrupo (`entidade`) nesta tabela.

---

### `prazo_medio_emissoes.csv`

Prazo médio das emissões da DPMFi em ofertas públicas, por indexador, mês a
mês. Origem: aba 3.9.

| Coluna | Tipo | Descrição |
|---|---|---|
| `data` | data | Último dia do mês |
| `indexador` | texto | Prefixado, Taxa Flutuante, Índice de Preços, Câmbio, Demais |
| `prazo_anos` | número | Prazo médio em anos |

---

### `custo_medio.csv`

Custo médio da dívida, em % a.a., por medida/nível/entidade/título, mês a
mês. Origem: abas 4.1, 4.2 e 4.3, consolidadas numa tabela porque
compartilham as mesmas dimensões e diferem só na medida.

| Coluna | Tipo | Descrição |
|---|---|---|
| `data` | data | Último dia do mês |
| `medida` | texto | `mensal` (aba 4.1), `acum_12m` (aba 4.2) ou `emissoes_12m` (aba 4.3) |
| `nivel` | texto | `DPF`, `DPMFi` ou `DPFe` |
| `entidade` | texto | `Dívida Mobiliária` / `Dívida Contratual` sob DPFe; vazio sob DPMFi |
| `titulo` | texto | Nome do título; vazio nas linhas de nível/entidade |
| `custo_aa_pct` | número | % ao ano — **pode ser negativo** (ex.: NTN-D em 2005), o que é legítimo e não é filtrado |

**Atenção:** a aba 4.3 muda de leiaute a partir de jan/2021 (cabeçalho de
mês mesclado em três sub-colunas: Taxa média, Variação do Indexador, CME).
O parser lê especificamente a sub-coluna `CME`, que equivale ao valor único
usado antes de 2021; comparar `medida = "emissoes_12m"` antes e depois dessa
data compara a mesma grandeza.

---

### `paf_metas.csv`

Bandas mínimo/máximo do Programa Anual de Financiamento (PAF), por ano e
indicador, com o realizado do próprio ano quando disponível. Origem: aba 5.7.

| Coluna | Tipo | Descrição |
|---|---|---|
| `ano` | inteiro | Ano de referência da meta (2003–2022) |
| `versao` | texto | `original` ou `revisado` — nem todo ano tem revisão |
| `indicador` | texto | Nome do indicador, **não normalizado** (ver abaixo) |
| `minimo` | número | Limite inferior da banda |
| `maximo` | número | Limite superior da banda |
| `realizado` | número | Valor realizado no ano, quando publicado na mesma aba |

**Atenção — cobertura limitada a 2003–2022.** O Tesouro parou de estender
esta aba; bandas de 2023 em diante não existem nesta fonte e precisam vir
dos PDFs do PAF (fora desta camada de dados). Ver `docs/fontes-de-dados.md`.

**Atenção — nomes de indicador mudam ao longo do tempo, de propósito não
normalizados.** `Selic` aparece de 2003 a 2010 e `Taxa Flutuante` de 2011 em
diante — é o mesmo indicador com nome diferente por período, não dois
indicadores distintos. `Demais` só existe até 2010; a meta mudou de
conceito, e normalizar o nome esconderia esse fato. Quem for comparar séries
ao longo do tempo precisa tratar essa mudança de rótulo explicitamente.

**Atenção — conversão de escala em 2021/2022.** Nesses dois anos, o
`realizado` dos indicadores percentuais (`% Vincendo em 12 meses`,
`Prefixado`, `Índice de Preços`, `Taxa Flutuante`, `Câmbio`) vinha na
planilha do Tesouro como fração (ex. `0.21`), enquanto `minimo`/`maximo` da
mesma linha vinham em pontos percentuais (ex. `21.0`). O parser converte o
`realizado` para pontos percentuais nesses casos, detectando pela
formatação de percentual da célula na planilha (não pelo valor) — não
"corrija" essa conversão de novo achando que é um bug.

A coluna `versao` vale `revisado` nas linhas em que a meta foi republicada:
isso acontece nos anos de **2008, 2015, 2016 e 2021**. A aba não traz a data
de publicação da revisão, só o ano — a vigência exata teria de vir de outra
fonte.

---

### `reserva_liquidez.csv`

Reserva de liquidez do Tesouro, mês a mês. Origem: aba 6.1.

| Coluna | Tipo | Descrição |
|---|---|---|
| `data` | data | Último dia do mês |
| `reserva_milhoes` | número | R$ milhões |
| `valor_prudencial_milhoes` | número | R$ milhões |
| `indice_liquidez_meses` | número | Índice em **meses** de despesa coberta — não é valor monetário e não passa pela conversão de unidade |

---

### `leiloes.csv`

Histórico completo de leilões da DPMFi desde 2000, uma linha por
título/data/volta. Origem: dataset CKAN `ds013`
(`historico-leiloes-todos.xls`), não o RMD.

| Coluna | Tipo | Descrição |
|---|---|---|
| `data_leilao` | data | Data do leilão |
| `titulo` | texto | LTN, LFT, NTN-B, NTN-F, NTN-C, NTN-B Principal… |
| `tipo_leilao` | texto | Venda, Compra, Troca… |
| `volta` | texto | `1.ª volta` ou `2.ª volta` |
| `data_liquidacao` | data | Data de liquidação financeira |
| `data_vencimento` | data | Vencimento do papel leiloado |
| `oferta_qtd` | número | Quantidade ofertada |
| `taxa_media_pct` | número | Taxa média, em % a.a. (convertida de fração — ver abaixo) |
| `taxa_corte_pct` | número | Taxa de corte, em % a.a. |
| `venda_qtd` | número | Quantidade vendida ao mercado |
| `financeiro_milhoes` | número | R$ milhões vendidos ao mercado |
| `venda_bacen_qtd` | número | Quantidade vendida ao Banco Central (vazio, não zero, nos primeiros anos) |
| `financeiro_bacen_milhoes` | número | R$ milhões vendidos ao Banco Central |
| `referencia` | texto | Vértice de *benchmark* (ex. `LFT 6 anos`) |

**Atenção:** o arquivo de origem grava taxa como **fração** (`0.07828` =
7,828% a.a.), convenção oposta à do RMD; o parser converte para pontos
percentuais na entrada. `financeiro_milhoes` e `financeiro_bacen_milhoes`
vêm em reais no arquivo original e são convertidos para milhões, como em
todo o resto do projeto. Para LFT, a taxa registrada é o ágio/deságio sobre
a Selic, não uma taxa absoluta — comparar essa coluna entre LFT e outros
títulos compara grandezas diferentes. Cada leilão pode ter `1.ª volta` e
`2.ª volta` em linhas distintas; o total emitido é a soma das duas.

---

## Verificação

Os dezessete nomes abaixo devem bater exatamente com os `.csv` presentes em
`data/processed/` após rodar o pipeline:

```
composicao_dpf, cronograma_vencimentos, custo_medio, detentores,
detentores_por_titulo, estoque_dpf, estoque_titulos_vencimento,
funding_por_canal, funding_por_indexador, leiloes, paf_metas,
prazo_medio_emissoes, prazo_medio_por_indexador, prazo_medio_por_titulo,
reserva_liquidez, vencer_12m_indexador, vencimentos_faixa
```
