# Dicionário de dados

Vinte e dois CSVs, gerados por `python -m tesouro.pipeline` em
`data/processed/`. Dezessete vêm do anexo do RMD e do histórico de leilões
(camada de dados, `src/tesouro/parse_rmd/*.py` e
`src/tesouro/parse_leiloes.py`); cinco vêm do sub-projeto de DV01 e decay
(`taxa_por_papel`, `vna`, `dv_por_papel`, `decay_por_papel`,
`resultado_mensal` — produzidos por `src/tesouro/parse_bloomberg.py` e
`src/tesouro/dv.py`, documentados na sua própria seção mais abaixo). As
colunas abaixo foram conferidas contra o código e contra os CSVs gerados —
não contra a especificação original, que foi escrita antes da implementação
e ficou desatualizada em alguns pontos.

As convenções de sinal e as fórmulas de cálculo do PU e do DV01 estão em
`docs/convencoes-dv.md`, não repetidas aqui — confira lá antes de qualquer
conta que envolva sinal ou taxa.

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
| `canal` | texto | Canal de colocação — treze valores: Cancelamentos, Compras, Dívida Contratual, Dívida Mobiliária, Emissão Direta com Financeiro, Emissão Direta sem Financeiro, NBC-E, Oferta Pública, Pagamento de Dividendos, Tesouro Direto, Transferência de Carteira, Trocas Oferta Pública, Vencimentos (alguns rótulos vêm com número de nota de rodapé colado na planilha original, ex.: `Pagamento de Dividendos4`) |
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
| `indexador` | texto | Indexador na DPMFi (`Prefixado`/`Prefixados`, `Taxa Flutuante`, `Índice de Preços`, `Câmbio`, `Demais`); moeda na DPFe (`Dólar`, `Euro`, `Real`, `Demais`) |
| `valor_milhoes` | número | R$ milhões |

**Atenção:** `esfera` entra na chave porque "Demais" existe nas duas esferas
com valores diferentes — sem a esfera na chave, uma sobrescreveria a outra.

**Atenção — grafia não normalizada:** sob `DPMFi`, a aba 1.2 escreve o
indexador como `Prefixados` (plural) na seção de emissões e `Prefixado`
(singular) na de resgates — mesmo indexador, duas grafias, não
normalizadas de propósito (mesma política aplicada a `Selic`/`Taxa
Flutuante` em `paf_metas.csv`). Quem filtrar só por `indexador ==
"Prefixado"` recebe apenas os resgates e conclui, errado, que o Tesouro
nunca emitiu prefixado — é preciso tratar as duas grafias como o mesmo
indexador.

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
| `indexador` | texto | Bloco da planilha: `Prefixados`, `Selic`, `Índices de Preços` (plural) |
| `titulo` | texto | LTN, LFT, NTN-B, NTN-F, NTN-C, LFT-TD1 Reserva, NTN-B Principal, NTN-B1 EducA+, NTN-B1 RendA+… |
| `vencimento` | data | Vencimento do papel |
| `isin` | texto | Código ISIN |
| `quantidade_mil` | número | Milhares de títulos (posição) |
| `financeiro_milhoes` | número | R$ milhões |

**Atenção:** `quantidade_mil` é o campo que sustenta o cálculo de DV01 — é a
posição em título, em **milhares** de títulos, porque é assim que a aba 2.2
publica (`Quantidade (mil)`). A quantidade de `leiloes.csv` está em unidades
de título: juntar as duas exige um fator de mil (ver a nota daquela tabela).
**`financeiro_milhoes` é marcação NA CURVA, não a mercado** — confirmado no
sub-projeto de DV01 (ver `docs/convencoes-dv.md` e
`tests/test_coerencia_dv.py`): a taxa que reproduz
`financeiro_milhoes / quantidade_mil` fica presa numa faixa estreita por anos
a fio (ex.: a NTN-B 2050 entre 5,40% e 5,56% nos doze anos de 2014 a 2026,
com o mercado variando de 3,57% a 7,56% no mesmo período), enquanto a LFT —
que quase não tem cupom futuro para uma curva "chutar" — bate com o ágio de
mercado com mediana de erro de 3,1 bp (97,1% dos pares dentro de 25 bp). Por
isso `financeiro_milhoes` serve de conferência (é o que
`tests/test_coerencia_dv.py` usa para o cruzamento de coerência contra o PU
calculado — não a própria tabela `dv_por_papel.csv`, que nem tem esta coluna
e nunca a lê), não de fonte de preço: quem precisar de PU ou de marcação a
mercado usa `dv_por_papel.csv`, não esta coluna. Os títulos aqui aparecem
**desagregados** em relação a `estoque_dpf.csv` — ver a nota daquela tabela.

**Atenção — só linhas observadas são gravadas.** A aba lista todo papel
contra todo mês, e a maioria dessas combinações não existe: o papel foi
emitido depois, ou já venceu. Linha com `quantidade_mil` **e**
`financeiro_milhoes` ambos ausentes é **não-observação**, não dado faltando, e
não é gravada — no RMD de junho/2026 isso descarta 25.236 das 47.124
combinações e deixa 21.888 linhas. Como consequência, a tabela **não** é um
painel balanceado: não conte com uma linha por (papel, mês).

**Atenção — para papel já vencido, zero e vazio se misturam de forma
arbitrária, e zero ali não é posição zerada.** Depois do vencimento a aba
traz, no mesmo bloco, umas linhas com `0.0` nas duas colunas e outras com
célula vazia, sem padrão que se possa aproveitar — é assim na fonte. As linhas
de `0.0` **são preservadas** (a regra do projeto é que zero é valor legítimo,
nunca ausência: 10.682 linhas do arquivo estão nessa condição), mas quem
filtrar por `quantidade_mil > 0` para achar a carteira viva de um mês não deve
interpretar esses zeros como posição efetivamente zerada de um papel vivo —
compare `vencimento` contra `data` para separar os dois casos.

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

**Atenção — o horizonte é truncado em 60 meses.** A aba 3.4 publica apenas os
cinco anos seguintes à `data_referencia`: no RMD de junho/2026 são os 60 meses
de Jul/2026 a Jun/2031, somando R$ 6,9 trilhões. Isso **não** é o cronograma
completo da dívida — `estoque_titulos_vencimento.csv` (aba 2.2) tem papel
vencendo até 2084. Quem calcular *decay*, necessidade de rolagem ou duração a
partir desta tabela perde tudo o que vence depois do quinto ano sem receber
aviso nenhum; para o horizonte inteiro é preciso usar a 2.2.

---

### `prazo_medio_por_titulo.csv`

Prazo médio da dívida, em anos, por nível/entidade/título, mês a mês.
Origem: aba 3.7.

| Coluna | Tipo | Descrição |
|---|---|---|
| `data` | data | Último dia do mês |
| `nivel` | texto | `DPF`, `DPMFi` ou `DPFe` |
| `entidade` | texto | `Tesouro Nacional` / `Banco Central` (DPMFi) ou `Dívida Mobiliária` / `Dívida Contratual` (DPFe); vazio nas linhas de nível |
| `titulo` | texto | Dezoito valores — os dezessete de `custo_medio.csv`, incluindo `NTN - D` **com espaços**, mais `NBC-E`; vazio nas linhas de nível/entidade (que carregam o prazo médio agregado) |
| `prazo_anos` | número | Prazo médio em anos — a família RendA+/EducA+ (`NTN-B1`) chega a **28,7 anos**, legitimamente |

A linha com `nivel = "DPF"` e `titulo` vazio traz o prazo médio agregado que
a análise compara contra a banda do PAF.

**Atenção:** como em `estoque_dpf.csv`, a tabela guarda a hierarquia
inteira, não só as folhas — 1.659 das 6.162 linhas têm `titulo` vazio e são
o prazo médio agregado de um `nivel`/`entidade`, não um título individual.
Para trabalhar só com títulos, filtre `titulo.notna()`; agrupar sem
filtrar mistura a agregação com as folhas que a compõem.

---

### `prazo_medio_por_indexador.csv`

Prazo médio da dívida, em anos, por indexador (DPMFi) ou instrumento (DPFe),
mês a mês. Origem: aba 3.8.

| Coluna | Tipo | Descrição |
|---|---|---|
| `data` | data | Último dia do mês |
| `nivel` | texto | `DPF`, `DPMFi` ou `DPFe` |
| `entidade` | texto | `Dívida Mobiliária` / `Dívida Contratual` sob DPFe; **sempre vazio nas linhas de `DPMFi`** |
| `categoria` | texto | Indexador (Prefixados, Taxa Flutuante, Índice de Preços, Câmbio, Demais) ou instrumento; **vazio** nas linhas de nível/entidade que carregam o prazo médio agregado |
| `prazo_anos` | número | Prazo médio em anos |

**Atenção:** `entidade` é vazia em todas as linhas de nível `DPMFi`. Isso é
estrutural, não dado faltando — a aba 3.8 abre direto por indexador dentro
da DPMFi, sem o agrupamento por `Tesouro Nacional`/`Banco Central` que a
aba 3.7 tem. Só a DPFe tem subgrupo (`entidade`) nesta tabela.

**Atenção — subtotal, mesma armadilha de `estoque_dpf.csv`:** 1.267 das
5.742 linhas têm `categoria` vazia com `prazo_anos` preenchido — são o
prazo médio agregado de um `nivel`/`entidade`, não um indexador
individual (mais 328 linhas com `categoria` e `prazo_anos` ambos vazios,
sem risco de contagem dupla por não terem valor). Filtre
`categoria.notna()` antes de agrupar por indexador, ou o agregado entra
somado em cima das categorias que ele já resume.

---

### `prazo_medio_emissoes.csv`

Prazo médio das emissões da DPMFi em ofertas públicas, por indexador, mês a
mês. Origem: aba 3.9.

| Coluna | Tipo | Descrição |
|---|---|---|
| `data` | data | Último dia do mês |
| `indexador` | texto | Exatamente quatro valores, 319 linhas cada: `Prefixado`, `Taxa Flutuante`, `Índice de Preços`, `NBCE / NTN-D` |
| `prazo_anos` | número | Prazo médio em anos |

**Atenção:** `Câmbio` e `Demais` **não aparecem** nesta tabela (aparecem em
outras, como `funding_por_indexador.csv` e `composicao_dpf.csv` — não
assuma o mesmo conjunto de indexadores em todas as tabelas do projeto).
`NBCE / NTN-D` é um indexador de verdade aqui, um quarto das 1.276 linhas.

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
| `titulo` | texto | Dezessete valores: `LFT`, `LTN`, `NTN-B`, `NTN-B1`, `NTN-C`, `NTN-F`, `NTN - D` (**com espaços**), `TDA`, `Dívida Securitizada`, `NBC-E`, `Reestruturada 1`, `Demais`, `Global USD`, `Global BRL`, `Euro`, `Organismos Multilaterais`, `Credores Privados/ Ag. Gov.`, `Clube de Paris`; vazio nas linhas de nível/entidade |
| `custo_aa_pct` | número | % ao ano — **pode ser negativo** (ex.: NTN-D em 2005), o que é legítimo e não é filtrado |

**Atenção — grafia não normalizada, e `NTN - D` é o caso que morde.** A mesma
dimensão é escrita de formas diferentes em abas diferentes, e o projeto
preserva a grafia da fonte de propósito (mesma política de
`Selic`/`Taxa Flutuante` em `paf_metas.csv` e de `Prefixado`/`Prefixados` em
`funding_por_indexador.csv`). As variantes que existem hoje:

| dimensão | grafias | onde |
|---|---|---|
| NTN-D | `NTN - D` (com espaços) | `custo_medio`, `prazo_medio_por_titulo` (abas 4.1, 3.7) |
| | `NTN-D` | `leiloes`, `estoque_dpf` |
| | `NBCE / NTN-D` | `prazo_medio_emissoes` (aba 3.9) |
| Índice(s) de preços | `Índice Preços` | `composicao_dpf` (aba 2.4) |
| | `Índice de Preços` | `funding_por_indexador`, `prazo_medio_por_indexador`, `prazo_medio_emissoes`, `paf_metas` (1.2, 3.8, 3.9, 5.7) |
| | `Índices de preços` | `vencer_12m_indexador` (aba 3.3) |
| | `Índices de Preços` | `estoque_titulos_vencimento` (aba 2.2) |
| Credores privados | `Credores Privados/ Ag. Gov.` (com espaço) | `custo_medio`, `prazo_medio_por_titulo`, `prazo_medio_por_indexador` |
| | `Credores Privados/Ag. Gov.` (sem espaço) | `estoque_dpf` |
| Reestruturada | `Reestruturada 1` (dígito de nota) | `custo_medio`, `prazo_medio_por_titulo`, `prazo_medio_por_indexador` |
| | `Reestruturada ¹` (expoente) | `estoque_dpf` |
| Euro | `Euro` | `custo_medio`, `prazo_medio_por_titulo`, `estoque_dpf` |
| | `Euros` | `prazo_medio_por_indexador` |

Um `join` de `custo_medio.titulo` com `leiloes.titulo` perde a NTN-D em
silêncio, porque nenhum dos dois lados avisa que a chave não casou. Normalize
no ponto de uso — no `merge`, não no CSV.

**Atenção:** a aba 4.3 muda de leiaute a partir de jan/2021 (cabeçalho de
mês mesclado em três sub-colunas: Taxa média, Variação do Indexador, CME).
O parser lê especificamente a sub-coluna `CME`, que equivale ao valor único
usado antes de 2021; comparar `medida = "emissoes_12m"` antes e depois dessa
data compara a mesma grandeza.

**Atenção — subtotal, mesma armadilha de `estoque_dpf.csv`:** 2.712 das
12.737 linhas têm `titulo` vazio — são o custo médio agregado de um
`nivel`/`entidade`, não de um título individual. Filtre `titulo.notna()`
antes de agrupar por título, ou o agregado entra somado em cima dos
títulos que ele já resume.

---

### `paf_metas.csv`

Bandas mínimo/máximo do Programa Anual de Financiamento (PAF), por ano e
indicador, com o realizado do próprio ano quando disponível. Origem: aba 5.7.

| Coluna | Tipo | Descrição |
|---|---|---|
| `ano` | inteiro | Ano de referência da meta (2003–2022) |
| `versao` | texto | `original` ou `revisado` — nem todo ano tem revisão |
| `indicador` | texto | Nome do indicador, **não normalizado** (ver abaixo) |
| `unidade` | texto | Unidade de `minimo`/`maximo`/`realizado` nesta linha: `R$ bilhoes`, `anos` ou `percentual` (ver abaixo) |
| `minimo` | número | Limite inferior da banda — **na unidade indicada por `unidade`** |
| `maximo` | número | Limite superior da banda — **na unidade indicada por `unidade`** |
| `realizado` | número | Valor realizado no ano, quando publicado na mesma aba — **na unidade indicada por `unidade`** |

**Atenção — esta é a única tabela do projeto que mistura unidades nas mesmas
colunas, e é por isso que a coluna `unidade` existe.** A aba 5.7 publica
todos os indicadores lado a lado, e `minimo`/`maximo`/`realizado` significam
coisas diferentes conforme a linha:

| `unidade` | indicadores | ordem de grandeza |
|---|---|---|
| `R$ bilhoes` | `Estoque da DPF em Mercado (R$ Bilhões)` | 940 a 6.400 |
| `anos` | `Prazo Médio da DPF (anos)` | 2,9 a 4,7 |
| `percentual` | `% Vincendo em 12 meses`, `Prefixado`, `Índice de Preços`, `Selic`, `Taxa Flutuante`, `Câmbio`, `Demais` | 0 a 47 |

A banda de estoque é a **única** grandeza monetária do projeto que **não**
está em R$ milhões: fica em R$ bilhões, como o próprio nome do indicador diz,
porque converter faria o rótulo mentir. Comparar essa banda (casa de 5.600)
contra `estoque_dpf.csv` (5.613.655) sem multiplicar por mil erra por três
ordens de grandeza — e essa é exatamente a comparação que a análise da banda
do PAF faz. A `unidade` sai do nome do indicador (`_unidade_do_indicador` em
`parse_rmd/paf_reserva.py`), não de uma heurística sobre o valor.

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
| `reserva_milhoes` | número | R$ milhões — saldo da reserva de liquidez no mês |
| `valor_prudencial_milhoes` | número | R$ milhões — o **"Valor Prudencial (3 meses)"** da aba: o colchão equivalente a três meses de vencimentos, não um estoque acumulado (ver abaixo) |
| `indice_liquidez_meses` | número | Índice em **meses** de despesa coberta — não é valor monetário e não passa pela conversão de unidade |

**Atenção — o qualificador "(3 meses)" explica os saltos.** O cabeçalho da aba
6.1 chama a segunda coluna de `Valor Prudencial (3 meses)`: ela é recalculada
a cada mês sobre a janela dos três meses seguintes, então acompanha a
concentração de vencimentos à frente e se move em degraus grandes. No RMD de
junho/2026 a série vai de 167 para 303, 587 e 783 R$ bilhões em um único
trimestre (mar–jun/2026). Isso não é erro de leitura nem mudança de unidade; é
a janela de três meses passando por um pico de vencimentos.

**Atenção — `indice_liquidez_meses` é o único derivado que o projeto
persiste, e isso é deliberado.** A convenção geral do projeto é não gravar
nada derivado, mas este índice **não é reconstruível** a partir das outras
duas colunas: `reserva_milhoes / valor_prudencial_milhoes` dá 0,35 onde o
índice publicado é 1,71 — o denominador que o Tesouro usa é a despesa
projetada do período, que a aba não publica. Descartá-lo perderia informação
que não volta. Não "corrija" isto recalculando a razão das outras duas
colunas.

---

### `leiloes.csv`

Histórico completo de leilões da DPMFi desde 2000, uma linha por
título/data/volta. Origem: dataset CKAN `ds013`
(`historico-leiloes-todos.xls`), não o RMD.

| Coluna | Tipo | Descrição |
|---|---|---|
| `data_leilao` | data | Data do leilão |
| `titulo` | texto | Exatamente seis valores: `LFT`, `LTN`, `NTN-B`, `NTN-C`, `NTN-D`, `NTN-F` |
| `tipo_leilao` | texto | Venda, Compra, Troca… |
| `volta` | texto | `1.ª volta` ou `2.ª volta` |
| `data_liquidacao` | data | Data de liquidação financeira |
| `data_vencimento` | data | Vencimento do papel leiloado |
| `oferta_qtd` | número | Quantidade ofertada, em **unidades de título** (não milhares — ver abaixo) |
| `taxa_media_pct` | número | Taxa média, em % a.a. (convertida de fração — ver abaixo) |
| `taxa_corte_pct` | número | Taxa de corte, em % a.a. |
| `venda_qtd` | número | Quantidade vendida ao mercado, em **unidades de título** |
| `financeiro_milhoes` | número | R$ milhões vendidos ao mercado |
| `venda_bacen_qtd` | número | Quantidade vendida ao Banco Central, em **unidades de título** (vazio, não zero, nos primeiros anos) |
| `financeiro_bacen_milhoes` | número | R$ milhões vendidos ao Banco Central |
| `referencia` | texto | Vértice de *benchmark* (ex. `LFT 6 anos`) |

**Atenção — unidade de quantidade incompatível com `estoque_titulos_vencimento.csv`,
por um fator de mil.** Aqui `oferta_qtd`, `venda_qtd` e `venda_bacen_qtd` estão
em **unidades de título**; lá `quantidade_mil` está em **milhares de títulos**,
porque é assim que a aba 2.2 publica (`Quantidade (mil)`). Conferência: um
leilão de 1.178.700 LFT com `financeiro_milhoes = 22.989` dá R$ 19,5 mil por
título, que é o preço unitário de uma LFT — se a coluna estivesse em milhares,
o preço sairia mil vezes menor. Juntar as duas tabelas (comparar emissão em
leilão com o estoque do papel) exige dividir a quantidade dos leilões por
1.000, ou multiplicar a do estoque.

**Atenção — os títulos aqui são exatamente seis**, conferidos por
`value_counts()` sobre o CSV gerado: `LTN` (6.968), `NTN-B` (5.577), `NTN-F`
(3.964), `LFT` (2.874), `NTN-C` (301) e `NTN-D` (55). `NTN-B Principal`
**nunca aparece** nesta tabela (aparece em `estoque_titulos_vencimento.csv`),
e `NTN-D` só existe aqui e em `estoque_dpf.csv` com essa grafia — ver a nota
de grafia em `custo_medio.csv`.

**Atenção:** o arquivo de origem grava taxa como **fração** (`0.07828` =
7,828% a.a.), convenção oposta à do RMD; o parser converte para pontos
percentuais na entrada. `financeiro_milhoes` e `financeiro_bacen_milhoes`
vêm em reais no arquivo original e são convertidos para milhões, como em
todo o resto do projeto. Para LFT, a taxa registrada é o ágio/deságio sobre
a Selic, não uma taxa absoluta — comparar essa coluna entre LFT e outros
títulos compara grandezas diferentes. Cada leilão pode ter `1.ª volta` e
`2.ª volta` em linhas distintas; o total emitido é a soma das duas.

---

## DV01, decay e resultado (sub-projeto de entrega 2)

As cinco tabelas abaixo não vêm do RMD nem dos leilões: `taxa_por_papel` e
`vna` vêm da Bloomberg (`src/tesouro/parse_bloomberg.py`); `dv_por_papel`,
`decay_por_papel` e `resultado_mensal` são calculadas a partir delas e do
estoque (`src/tesouro/dv.py`). Todas em formato longo, mesma convenção do
resto do projeto. Contagens de linha e `value_counts()` abaixo conferidos
contra os CSVs reais em `data/processed/` (painel de 30/06/2026, 9.366
linhas em `dv_por_papel.csv`).

### `taxa_por_papel.csv`

Taxa indicativa de mercado (Anbima, fonte `ANDE`) por papel e fim de mês.
Origem: Bloomberg, campo `YLD_YTM_MID`. 8.836 linhas.

| Coluna | Tipo | Descrição |
|---|---|---|
| `data` | data | Último dia **útil** do mês — não o último dia corrido (ver `docs/convencoes-dv.md`, seção "Calendário de dias úteis") |
| `isin` | texto | Código ISIN |
| `titulo` | texto | `LTN` (2.169), `NTN-F` (1.200), `NTN-B` (2.945), `LFT` (2.522) |
| `vencimento` | data | Vencimento do papel |
| `taxa_pct` | número | % ao ano (`13.5` = 13,5% a.a.); pode ser negativa (a LFT já teve deságio negativo -- mínimo de -0,0903%, em 935 das 2.522 linhas de LFT; o mínimo de todo o arquivo, -4,2102%, é da NTN-B, não da LFT) |

**Atenção — `data` é o último dia ÚTIL, `estoque_titulos_vencimento.csv`
traz o último dia CORRIDO.** Juntar as duas tabelas por data literal (sem
normalizar um dos dois lados com `calendario.ultimo_dia_util_do_mes`) perde
35,1% do painel em silêncio: dos 9.366 pares papel-mês do painel de DV01,
uma junção por data crua preserva só 6.074 (64,9%), contra 8.794 (93,89%) da
junção correta. `src/tesouro/dv.py` normaliza o lado do estoque antes de
juntar; qualquer código novo que ler este CSV junto com o estoque precisa
fazer o mesmo.

**Atenção — para a LFT, `taxa_pct` é ágio/deságio sobre a Selic, não uma
taxa absoluta** (mesma convenção de `leiloes.csv`); comparar esse número
entre LFT e os demais títulos compara grandezas diferentes.

**Atenção — a Bloomberg às vezes cota num dia que a Anbima não considera
útil.** Em 272 das 8.898 linhas do bruto (antes da normalização acima), a
data de origem cai num feriado móvel pela Anbima: Paixão de Cristo (2013,
2018, 2024), Carnaval (2017, 2022) ou Corpus Christi (2018) — a Bloomberg
parece fechar esses feriados diferente da Anbima. É por isso que a
normalização para o último dia útil é feita nos dois lados (Bloomberg e
RMD), não só do lado do RMD.

### `vna.csv`

Valor Nominal Atualizado por índice e fim de mês, em reais. Origem:
Bloomberg, campo `IDX_RATIO` (IPCA) ou `ACCUMULATED_SELIC` (Selic), × 1000,
com override `SETTLE_DT` na data desejada. 396 linhas.

| Coluna | Tipo | Descrição |
|---|---|---|
| `data` | data | Último dia útil do mês |
| `indice` | texto | `IPCA` (198) ou `SELIC` (198) |
| `vna` | número | R$ por unidade de VNA |

**Atenção — o VNA é por índice, não por papel.** Verificado: idêntico entre
todos os papéis do mesmo índice na mesma data, nas 198 datas do painel (ver
`docs/convencoes-dv.md`). Uma NTN-B e outra do mesmo mês sempre usam a mesma
linha deste CSV.

**Atenção — `SETTLE_DT` não serve para taxa histórica, só para VNA.** Ver
`docs/convencoes-dv.md`, seção "Fontes na Bloomberg", para o porquê (erro de
135 bp medido se usado para taxa).

### `dv_por_papel.csv`

O fato atômico do sub-projeto: uma linha por papel e fim de mês, com os
insumos (taxa, VNA, PU) junto do resultado (DV01), de propósito — quem
quiser conferir um papel abre este CSV e refaz a conta à mão (ver exemplo em
`docs/convencoes-dv.md`, seção "Refazendo uma conta à mão"). Gerado por
`dv.painel()`. 9.366 linhas.

| Coluna | Tipo | Descrição |
|---|---|---|
| `data` | data | Último dia útil do mês |
| `isin` | texto | Código ISIN |
| `titulo` | texto | `LTN` (2.499), `NTN-F` (1.203), `NTN-B` (3.003), `LFT` (2.661) |
| `vencimento` | data | Vencimento do papel |
| `taxa_pct` | número | % ao ano, de `taxa_por_papel.csv`; vazia onde a Bloomberg não cobre o par papel-mês |
| `vna` | número | R$, de `vna.csv`; sempre vazio para LTN e NTN-F (não são indexados, não usam VNA) |
| `pu` | número | Preço unitário calculado (não é o `financeiro_milhoes` do RMD — ver abaixo) |
| `dv_unitario` | número | R$ por título, variação do PU para +1 bp; **vazio para LFT, não zero** — é decisão de modelagem (a LFT não tem duration de juros por construção), e a diferença importa para quem somar: `0` entraria numa soma como "risco nulo medido", `NaN`/vazio corretamente some da soma |
| `quantidade_mil` | número | Milhares de títulos (posição), sempre preenchida quando a linha existe |
| `dv_posicao_milhoes` | número | R$ milhões por bp = `dv_unitario × quantidade_mil / 1000`; vazio onde `dv_unitario` é vazio |
| `financeiro_calculado_milhoes` | número | R$ milhões = `pu × quantidade_mil / 1000` — **nossa marcação a mercado**, calculada a partir da taxa; não confundir com `financeiro_milhoes` de `estoque_titulos_vencimento.csv`, que é marcação NA CURVA (ver a nota daquela tabela e `docs/convencoes-dv.md`) |

**Atenção — 572 linhas (6,1% do painel) ficam sem taxa** e por isso sem
`pu`/`dv_unitario`/`financeiro_calculado_milhoes` (vazios, não zero);
`quantidade_mil` continua preenchida (a posição existiu, só falta a taxa
para precificá-la). A composição é heterogênea, não "quase toda LFT de
2010-2011" como se poderia supor de memória: `LTN` (335 linhas, de 2010 a
2026 — incluindo 38 em 2010-2011, mas sem nenhuma em 2012 nem 2014, e a
maioria depois de 2015), `LFT` (155, **integralmente** em 2010-2011),
`NTN-B` (73, a maioria em 2010) e `NTN-F` (9). Confira sempre com
`value_counts()` contra o CSV real antes de descrever a composição de um
subconjunto — é esse tipo de suposição não conferida que já causou erro
factual neste dicionário (duas vezes: uma vez achando que era "quase toda
LFT", outra vez descrevendo a janela da LTN errada ao corrigir a primeira).

**Atenção — a cobertura do DV01 não é uma constante, e precisa acompanhar
qualquer total.** 46,5% do estoque (pela base do RMD) em 30/06/2026; 60,4%
em 31/12/2020 — a composição da dívida muda mês a mês. Os fora de escopo são
LFT (sem duration de juros por construção — `dv_unitario` vazio) e ~2,2%
excluídos sem preço no secundário (NTN-C, NTN-B Principal, RendA+, EducA+).
Ver `docs/convencoes-dv.md`, seção "Escopo".

### `decay_por_papel.csv`

Decay do DV01 a taxa e VNA constantes (Conta B — mecânico, sem dinheiro),
nos horizontes fixos de 1, 5 e 21 dias úteis, por papel. Gerado por
`dv.decay()`. 20.115 linhas.

| Coluna | Tipo | Descrição |
|---|---|---|
| `data_base` | data | Data de partida (fim de mês do painel) |
| `horizonte` | texto | `1du` (6.705), `5du` (6.705) ou `21du` (6.705) |
| `data_alvo` | data | `data_base` mais o número de dias úteis do horizonte |
| `isin` | texto | Código ISIN |
| `titulo` | texto | `LTN` (7.497), `NTN-F` (3.609), `NTN-B` (9.009) — sem LFT, que não tem DV no projeto |
| `venceu_no_caminho` | booleano | `True` (286 linhas) se o papel vence entre `data_base` e `data_alvo`; `False` (19.829) caso contrário |
| `dv_base` | número | R$ milhões por bp na `data_base` (mesmo valor de `dv_posicao_milhoes` em `dv_por_papel.csv`) |
| `dv_alvo` | número | R$ milhões por bp reprecificado em `data_alvo`, com a MESMA taxa e VNA da base; `0.0` se `venceu_no_caminho` E havia `dv_base` conhecido; fica vazio nas 18 (de 286) linhas vencidas em que o risco de partida já não era conhecido -- o risco existiu e foi a zero, não é ausência, mas só quando dava para medi-lo antes |
| `decay` | número | `dv_alvo − dv_base`; **em regra** positivo para um sobrevivente (o DV fica menos negativo — "encolheu" em módulo) e sempre positivo para quem venceu no caminho (mesma fórmula, com `dv_alvo = 0`) — ver a exceção abaixo |

**Atenção — nunca some `decay` sem olhar `venceu_no_caminho`.** Um papel
que venceu contribui um `decay` positivo do tamanho do `dv_base` inteiro —
isso é calendário (o papel sumiu), não a passagem do tempo encolhendo um
risco vivo. Somar as duas populações juntas produz um número que parece
decay de mercado e é, na verdade, metade vencimento. Filtre por
`venceu_no_caminho` antes de agregar, ou mantenha as duas somas separadas.

**Atenção — `decay` sai levemente negativo em 933 das 18.596 linhas de
sobrevivente com decay medido (5,0%, todas NTN-B)** — não é a exceção rara
que "em regra" sugere sozinho: chega a 24,6% do horizonte de 1 dia útil
(722 de 2.930), 6,8% do de 5 dias (199 de 2.930) e 0,4% do de 21 dias (12
de 2.912). A magnitude é minúscula (mediana −0,000019, mínimo −0,2326) e a
causa é a mesma quantização de "A truncagem faz parte do DV"
(`docs/convencoes-dv.md`): dois PUs truncados independentemente às vezes
não guardam a ordem que o PU cheio guardaria. Não é defeito da tabela, mas
quem filtrar `decay < 0` caçando erro vai achar essas linhas.

**Atenção:** 1.251 linhas ficam com `dv_base`/`dv_alvo`/`decay` vazios —
papéis sem taxa ou sem `dv_unitario` já na base, para os quais não havia
risco de partida conhecido para medir a variação (não é o mesmo caso de
`venceu_no_caminho`, que pressupõe risco de partida conhecido).

**Atenção — o PU usado aqui é calculado em D+0**, e por isso fica cerca de
5 bp abaixo do preço da tela, que cota D+1. Não é erro; ver
`docs/convencoes-dv.md`, seção "Liquidação".

### `resultado_mensal.csv`

Resultado em dinheiro, mês a mês, sobre a posição CONGELADA no início do
período (Conta A — o papel emitido no dia 20 não deu lucro nem prejuízo a
quem carregava desde o dia 1º). Inclui a LFT (tem PU real, mesmo sem
duration de juros). Gerado por `dv.resultado_mensal()`. 9.314 linhas.

| Coluna | Tipo | Descrição |
|---|---|---|
| `data_ini` | data | Início do período (fim de mês) |
| `data_fim` | data | Fim do período (fim do mês seguinte) |
| `isin` | texto | Código ISIN |
| `titulo` | texto | `LTN` (2.485), `NTN-F` (1.197), `NTN-B` (2.988), `LFT` (2.644) |
| `venceu_no_periodo` | booleano | `True` (144 linhas) se o papel vence entre `data_ini` e `data_fim` |
| `quantidade_mil_ini` | número | Posição em `data_ini` — a MESMA usada para o resultado em `data_fim`, mesmo que o estoque real tenha mudado |
| `pu_ini` | número | PU em `data_ini` |
| `pu_fim` | número | PU em `data_fim`; **vazio quando `venceu_no_periodo`, de propósito** — não sabemos a que preço o dinheiro foi reinvestido, e arbitrar uma hipótese aqui embutiria decisão de análise na camada de dados |
| `resultado_milhoes` | número | R$ milhões = `(pu_fim − pu_ini) × quantidade_mil_ini / 1000`; vazio onde `pu_ini` ou `pu_fim` são vazios |

**Atenção — 8 linhas vivas (não vencidas) ficam com `pu_fim` vazio mesmo
assim**, sem nada na tabela que as distinga de "não se aplica": o ISIN some
do painel do mês seguinte sem ter vencido (dado de origem da época — RMD de
2010/2011 —, não defeito do parser). Somam R$ 291.954,8 milhões de posição
(`pu_ini × quantidade_mil_ini`), todas com `data_fim` entre 2010-02 e
2011-08 (nenhuma nos últimos doze meses do painel). Quem somar
`resultado_milhoes` de um mês antigo nessa janela precisa saber que o total
está incompleto ali — a contagem exata de 8 está travada em
`tests/test_coerencia_dv.py::test_linhas_vivas_sem_pu_fim_sao_exatamente_oito`.

**Atenção — para a NTN-B e a LFT, `resultado_milhoes` mistura acumulação de
índice (IPCA/Selic) com movimento de taxa real**, e a parcela de índice pode
superar o total (ou ter o sinal oposto). A função `dv.resultado_decomposto()`
(não persistida — ver `docs/convencoes-dv.md`, seção "Resultado mensal:
separando a acumulação de índice") separa as duas.

## `dashboard.html` — a camada de gráficos

Não é CSV e não é dado: é a saída visual, gerada a partir dos CSVs acima
por `python -m tesouro.graficos` (ou pelo `pipeline`, que o chama no fim).

| o que é | um arquivo HTML autocontido, com os 25 SVGs embutidos |
|---|---|
| onde fica | `data/processed/dashboard.html` |
| tamanho | 2,7 MB, contra o limiar de 10 MB que a spec fixou |
| de onde vem | dezesseis gráficos, cada um lendo os CSVs desta tabela, mais `referencia/paf_bandas.csv` |
| pode apagar? | **Sim.** É derivado: o pipeline regenera. |

Os dezesseis gráficos, o que cada um lê e as decisões de desenho estão em
`docs/superpowers/specs/2026-08-18-dashboard-design.md`. As **funções de
dado** de cada gráfico (`dados_*`) devolvem exatamente o que vai para a
tela e não conhecem matplotlib — é onde os testes de número vivem.

**Nove dos dezesseis aceitam janela** (5 anos e série completa), e por isso
são 25 SVGs e não 16. A composição do estoque abre na série completa: a
queda do câmbio de 51,0% em set/2002 para 3,7% não existe numa janela de
cinco anos.

## Verificação

Os vinte e dois nomes abaixo devem bater exatamente com os `.csv` presentes
em `data/processed/` após rodar o pipeline:

```
composicao_dpf, cronograma_vencimentos, custo_medio, decay_por_papel,
detentores, detentores_por_titulo, dv_por_papel, estoque_dpf,
estoque_titulos_vencimento, funding_por_canal, funding_por_indexador,
leiloes, paf_metas, prazo_medio_emissoes, prazo_medio_por_indexador,
prazo_medio_por_titulo, reserva_liquidez, resultado_mensal, taxa_por_papel,
vencer_12m_indexador, vencimentos_faixa, vna
```
