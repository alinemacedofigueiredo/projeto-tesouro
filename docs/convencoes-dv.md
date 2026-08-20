# Convenções de DV01 e de sinal

Documento de referência para o cálculo de DV01, decay e resultado. Escrito antes
da implementação, a partir do código de precificação em uso na mesa.

---

## Antes de qualquer cálculo: confira o lado

**Esta é a primeira coisa a verificar, sempre.** O projeto usa duas convenções de
sinal diferentes, para duas medidas diferentes, e trocá-las inverte toda conclusão
sem que nenhum gráfico pareça errado.

| Medida | Convenção |
|---|---|
| **Resultado (P&L)** | Negativo é o **mercado perdendo dinheiro** |
| **Risco emitido** | Positivo é o **Tesouro emitindo**; negativo é vencimento ou recompra |

### Onde cada uma vale, na prática

| arquivo | convenção | por quê |
|---|---|---|
| `dv_painel.csv`, `dv_decay.csv` | **P&L** — `dv` negativo | medem o dinheiro de quem carrega o papel |
| `dv_emitido_por_leilao.csv` | **risco emitido** — venda positiva, recompra negativa | mede emissão |

**Isto já saiu errado uma vez.** A primeira versão de `leiloes_dv.py` deixou passar o
sinal de P&L que `precificacao.dv` devolve — correto lá, errado ali — e o resultado
foi um gráfico de emissão com **todas as barras para baixo**, que ainda exigiu inverter
o eixo do DV para ficar legível. Não levantou nada: o número estava certo em módulo, e
só o lado estava trocado. Corrigido em 20/08/2026, e a inversão do eixo saiu junto.

As duas são coerentes entre si: ambas olham da ótica de quem carrega o papel.
Emissão coloca risco no mercado (positivo); alta de taxa faz quem carrega perder
(negativo).

**No cálculo do DV**, a diferença é tomada como `PU(taxa + 1bp) − PU(taxa)`. Para
título prefixado ou indexado, isso é **negativo** — o preço cai quando a taxa sobe.
Multiplicado pela posição, dá diretamente o dinheiro perdido num choque de +1 bp,
já no sinal certo da tabela acima.

**Atenção ao DI.** No código original da mesa, o DV do DI é calculado ao contrário
(`PU(taxa) − PU(taxa + 1bp)`), portanto **positivo**. O DI está fora do escopo deste
projeto, mas se algum cálculo futuro somar carteira de títulos com futuro, os sinais
se cancelam na direção errada. Verifique antes de agregar.

---

## Como o DV de cada papel é calculado

Todos os PUs usam base **252 dias úteis** e o calendário de feriados da Anbima. A
taxa entra em decimal (`0,13` = 13% a.a.), e o choque de 1 bp é `+0,0001`.

### LTN — prefixado, sem cupom

```
PU = 1000 / (1 + taxa) ^ (du / 252)
```
Truncado em 6 casas. `du` contado da data de posição até o vencimento ajustado.

### NTN-F — prefixado, cupom semestral

Cupom de `1000 × ((1,10) ^ 0,5 − 1)` = **48,8088** por período, pago junto com o
principal de 1.000 no vencimento. As datas de cupom caem no **dia 1**, de seis em
seis meses contados de trás do vencimento. Cada fluxo é descontado pelos seus
próprios dias úteis; a soma é truncada em 6 casas.

### NTN-B — indexada ao IPCA, cupom semestral

Cupom de `100 × ((1,06) ^ 0,5 − 1)` = **2,9563** por período, sobre principal de 100
no vencimento. As datas de cupom caem no **dia 15**. A soma dos fluxos descontados é
a **cotação**, truncada em **4 casas**; o PU é `cotação / 100 × VNA`, truncado em 6.

O **VNA usado é o negociado do dia** — não o oficial nem uma projeção calculada
internamente.

### LFT — pós-fixada à Selic

```
cotação = 100 / (1 + ágio) ^ (du / 252)     (truncada em 4 casas)
PU      = cotação × VNA / 100                (truncado em 6 casas)
```

**Neste projeto o DV da LFT é tratado como zero.** É uma decisão de modelagem, não
o que o código faz: matematicamente o DV existe e é a sensibilidade ao **ágio**, não
ao nível da Selic. A LFT entra apenas pelo financeiro recalculado, para projetar
composição da dívida.

---

## A truncagem faz parte do DV, de propósito

O DV é a diferença de dois PUs **já truncados**. Isso é deliberado: o preço truncado
é o preço com que o mercado opera, e portanto é o que de fato se ganha ou se perde
quando a taxa anda 1 bp.

A consequência a conhecer é que o DV fica levemente quantizado, e o efeito é
proporcionalmente maior nos papéis mais curtos — numa NTN-B a vencer em dois meses
o degrau da truncagem chega a cerca de 1% do DV. Não é erro: é a granularidade real
do preço negociável.

---

## Liquidação: calculamos em D+0; o mercado negocia em D+1

**O mercado cota para liquidação em D+1, e nós calculamos para D+0.** É decisão
deliberada: a posição é a do fim do mês, e queremos o valor naquela data, não o
valor de liquidação do dia seguinte.

A consequência é que **o nosso PU fica sistematicamente cerca de 5 bp abaixo do
preço da tela**, num papel prefixado a 13% ao ano. Isso não é erro — é a diferença
de um dia útil de desconto. Quem comparar um PU nosso com a Bloomberg ou com a
Anbima vai encontrar essa diferença, e ela é esperada.

**Para a NTN-B a diferença tem duas partes:** o dia útil de desconto e o dia de
acumulação do VNA. O mercado usa o VNA de D+1; nós usamos o de D+0.

**Consequência para os testes:** o teste que compara o nosso PU com o preço da
Bloomberg **precisa aplicar o deslocamento de D+1** — liquidação em D+1 e, na
NTN-B, VNA em D+1 também. Sem isso o teste falha para sempre, e o risco real é
alguém "corrigir" a produção para D+1 só para o teste passar, mudando todos os
números do projeto sem perceber.

### Como esta convenção foi verificada

Comparando o PU calculado contra o `PX_DIRTY_MID` da Bloomberg, com fonte `ANDE`,
em 438 pares papel-data entre 2020 e 2026:

| título | comparações | resultado com liquidação em D+1 |
|---|---|---|
| NTN-F | 228 | exatas, todas |
| NTN-B | 210 | exatas, todas (com VNA em D+1) |

Diferença máxima de 0,0083 bp — ruído de ponto flutuante. Antes do ajuste de D+1, a
mediana era de −5 bp na LTN e na NTN-F, e de −1,95 bp na NTN-B.

Isso valida de uma vez as fórmulas de PU, o calendário da Anbima, a taxa com fonte
`ANDE`, o VNA e a contagem de dias úteis.

---

## Fontes na Bloomberg

| dado | como obter |
|---|---|
| Taxa | `YLD_YTM_MID` em `/isin/<ISIN>@ANDE Govt`, série histórica mensal |
| VNA da NTN-B | campo `IDX_RATIO`, override `SETTLE_DT` na data desejada, × 1000 |
| VNA da LFT | campo `ACCUMULATED_SELIC`, mesmo override, × 1000 |
| Preço (só para conferência) | `PX_DIRTY_MID`, série histórica mensal |

**O `@ANDE` é obrigatório.** Sem a fonte, a taxa vem de outra origem. Na maioria dos
papéis o número é idêntico, mas na ponta curtíssima diverge em alguns pontos-base.

**`SETTLE_DT` muda a data de liquidação, não a data do mercado.** Usar o override
para obter taxa histórica devolve *a taxa de hoje liquidando naquela data* — no fim
de 2024 isso dá um erro de 135 bp. O override serve para o VNA, que é função
determinística da data, e não serve para a taxa. Taxa histórica só por série
temporal.

**O VNA é por índice, não por papel.** Verificado: o valor é idêntico entre papéis
diferentes na mesma data, em todas as 198 datas do painel. Isso vira teste.

**A série histórica de preço da LFT é inutilizável.** A Bloomberg a expressa com o
índice corrente, não o da época: o preço de 2020 dividido pelo VNA de hoje dá 1,018,
e dá o mesmo valor em todos os anos de 2020 a 2026. Para a LFT, a nossa conta é a
referência, não a dela.

**A junção com o estoque é por mês, ou por último dia útil normalizado dos dois
lados — nunca por data literal.** A Bloomberg devolve 29/05 onde o estoque do RMD
traz 31/05; casar por data crua descarta um terço do painel em silêncio.

**`BZAC2000 Index` é CDI acumulado, não Selic.** É um erro fácil de cometer
porque os dois nomes soam parecidos e as séries ficam próximas por longos
períodos; a diferença cresce com o tempo. O campo certo para o VNA da LFT é
`ACCUMULATED_SELIC`, não `BZAC2000 Index`.

**O nome do arquivo salvo em `data/raw/bloomberg/` precisa seguir o formato
ISO (`AAAA-MM_AAAA-MM`), sem exceção.** `parse_bloomberg.py` lê todos os
arquivos de um tipo (taxa, VNA) e concatena na ordem alfabética do nome,
mantendo a última ocorrência de cada `(data, isin)`/`(data, índice)`
repetido — que só é a coleta mais recente se o nome ordenar
cronologicamente. Um arquivo nomeado fora do padrão (ex.: dia antes do ano)
ordena antes ou depois do que deveria, e a coleta mais nova é descartada em
favor da mais antiga, **sem erro nenhum**. É por isso que o leitor confere o
nome de cada arquivo contra um padrão fixo antes de ler qualquer um deles, e
por que a exportação manual por `BDH` (`docs/como-baixar.md`) precisa nomear
o arquivo do mesmo jeito.

---

## Calendário de dias úteis

Fonte oficial: `data/raw/anbima/feriados_nacionais.xls`, baixado de
`anbima.com.br/feriados/arqs/feriados_nacionais.xls`. Cobre **2001 a 2099**, com
1.013 feriados em dia de semana.

**O último dia do ano é dia útil.** O arquivo da Anbima não inclui 31/12, e a nota 4
do próprio arquivo explica que a listagem exclui feriados municipais, eleições e o
último dia do ano. Pela Resolução 2.596/99 não há atendimento ao público nesse dia,
mas ele conta como dia útil para o cálculo — e é assim que fazemos.

Quinta-feira santa é dia útil desde 2000, por resolução do Banco Central, e por isso
não está na lista.

**A data que a Bloomberg devolve nem sempre é dia útil pela Anbima.** No bruto
da coleta (`bbg_taxas_*.csv`), 272 das 8.898 linhas trazem uma data de origem
que a Anbima não considera dia útil, concentradas em 6 datas, todos os
próprios feriados móveis (não vésperas): **Paixão de Cristo**
(29/03/2013, 30/03/2018, 29/03/2024), **Carnaval** (28/02/2017, 28/02/2022) e
**Corpus Christi** (31/05/2018) — conferido nome a nome contra
`data/raw/anbima/feriados_nacionais.xls`. O calendário que a Bloomberg usa
para fechar o mês não é o mesmo da Anbima nesses feriados móveis. É por isso
que a normalização para o último dia útil é feita **dos dois lados** —
Bloomberg e RMD — e não só do lado do RMD, que é onde a armadilha de "último
dia corrido" já era conhecida.

O custo de pular essa normalização é medido: juntando `taxa_por_papel.csv`
com o estoque (`estoque_titulos_vencimento.csv`) pela data **literal**, sem
mapear nenhum dos dois lados para o último dia útil, sobram 6.074 pares
papel-mês dos 9.366 do painel — 64,9%, uma perda silenciosa de 35,1%. A
junção correta (os dois lados normalizados) preserva 93,89% (8.794 pares).

---

## Data de posição: sempre o último dia útil do mês

As datas do estoque (`estoque_titulos_vencimento.csv`, aba 2.2 do RMD) são **fim de
mês de calendário**, e **61 das 198 caem em fim de semana ou feriado**.

Toda conta de fim de mês usa o **último dia útil do mês**, nunca o último dia
corrido. Sem esse mapeamento, a contagem de dias úteis fica um dia curta em quase um
terço do painel — erro pequeno em cada ponto, sistemático no conjunto, e invisível.

---

## Escopo: o que o DV01 cobre

| | Papéis | Fatia do estoque |
|---|---|---|
| **Com DV01 calculado** | LTN, NTN-F, NTN-B | **46,5%** |
| Sem duration de juros | LFT (e LFT-TD1 Reserva) | 51,3% |
| Fora por decisão | NTN-C, NTN-B Principal, RendA+, EducA+ | 2,2% |

Percentuais pelo estoque de junho de 2026 (LTN 14,4% + NTN-F 7,5% + NTN-B
24,7% — a soma das três parcelas arredondadas dá 46,6%, mas o total calculado
com precisão total, sem arredondar cada parcela antes, é 46,5%; é o número
preciso que conta). Os excluídos ficaram de fora por não terem preço
observável no secundário.

**O DV01 agregado cobre 46,5% do estoque.** Esse número precisa aparecer sempre que
um total for reportado — caso contrário, alguém soma o DV01 da carteira e supõe que
ele mede a dívida inteira.

**A cobertura não é uma constante — ela é calculada NA data pedida**, porque a
composição da dívida muda mês a mês: em 30/06/2026 é 46,5%, mas em 31/12/2020
era 60,4% (catorze pontos acima, com mais LTN e menos NTN-B no estoque da
época). `dv.pontual()` recalcula a cobertura a cada chamada em vez de usar uma
constante fixa — um total antigo rotulado com a cobertura de hoje estaria
errado.

**Há uma segunda leitura de cobertura, com denominador diferente: pela nossa
marcação a mercado, não pela base do RMD.** Os 46,5% acima usam
`financeiro_milhoes` da aba 2.2 (a base "oficial" do Tesouro) tanto no
numerador (LTN+NTN-F+NTN-B) quanto no denominador (estoque inteiro). Trocando
o numerador pelo `financeiro_calculado_milhoes` da entrega 2 — nossa marcação
a mercado, ver a seção seguinte — a cobertura em 30/06/2026 cai para **43,3%**.
Os 3,3 pontos de diferença são o desconto entre a marcação na curva do RMD e
a marcação a mercado desta entrega: o financeiro da 2.2 vale um pouco mais
para NTN-F e NTN-B do que o PU calculado a partir da taxa observada. Isso
**não** afeta o cálculo do DV01 em si (`dv_unitario × quantidade_mil` nunca lê
`financeiro_milhoes`) — só muda qual dos dois denominadores uma fração de
cobertura está citando. Sempre que citar "cobertura de X%", diga contra qual
base.

---

## O financeiro da aba 2.2 é marcação na curva, não a mercado

A spec da camada de dados
(`docs/superpowers/specs/2026-08-14-camada-de-dados-design.md`, §8) deixou
essa pergunta em aberto, com a suspeita de que fosse curva. Esta entrega
responde, com evidência forte.

**O teste:** comparar a taxa que reproduz `financeiro_milhoes / quantidade_mil`
(aba 2.2) contra o PU calculado a partir da taxa de mercado real (Bloomberg,
fonte `ANDE`). Se as duas baterem, o financeiro do Tesouro é marcação a
mercado; se divergirem de forma sistemática, é marcação na curva.

- **NTN-B 15/05/2050 (`BRSTNCNTB3D4`):** a taxa implícita no financeiro do
  Tesouro fica **cravada entre 5,40% e 5,56%** nos doze anos de 2014-01 a
  2026-06 (150 observações), enquanto a taxa de mercado no mesmo período foi
  de **3,57% (jan/2020) a 7,56% (fev/2025)**. Uma curva parada não se move
  com o mercado real.
- **NTN-F 01/01/2031 (`BRSTNCNTF204`):** a taxa implícita sobe de forma
  geral, mas **não estritamente monotônica** — há quedas pontuais de poucos
  centésimos de ponto (jan→fev/2020, jan→fev/2022, out→dez/2023) —, de
  **6,99% em jan/2020 para 12,28% em jan/2026**. No mesmo par de datas o
  mercado fez **6,86% → 13,23%**, com um pico de **15,68% em dez/2024**
  pelo meio (não em jan/2025, onde a taxa já tinha recuado para 14,85%). A
  série continua até jun/2026, onde a implícita chega a 12,49% contra 14,30%
  de mercado. A curva do RMD segue uma trajetória muito mais suave do que
  o mercado real, que sobe, cai e sobe de novo.
- **O controle que fecha o argumento é a LFT.** A LFT quase não carrega cupom
  futuro para uma curva "chutar" — sobra pouco para divergir. E de fato,
  nos 2.506 pares papel-mês com taxa e VNA conhecidos: a mediana do erro
  absoluto entre o ágio implícito e o ágio de mercado é **3,1 bp**, e
  **97,1% dos pares ficam dentro de 25 bp** — a mesma ordem de grandeza do
  ruído de marcação normal, bem diferente da divergência sistemática de
  NTN-F e NTN-B. Há 24 pares acima de 100 bp, todos com o papel a 1-11 dias
  úteis do vencimento — ali o PU fica quase insensível ao ágio (`du` muito
  pequeno na fórmula da LFT), e qualquer ruído de truncagem se amplifica na
  inversão; não é sinal de erro de fórmula, é a mesma quantização da seção
  "A truncagem faz parte do DV" agindo ao contrário (implícita, não PU). Fora
  dessa janela de quase-vencimento, o controle sustenta o argumento: isso
  descarta erro de fórmula ou de unidade do nosso lado, porque o defeito não
  aparece no título de controle, só nos títulos com cupom longo para uma
  curva reprecificar.

**Consequência prática:** a cobertura do DV01 medida pela base do RMD é
46,5%; medida pela nossa marcação a mercado é 43,3% (ver a seção anterior). O
cálculo do DV01 em si não muda — `dv.painel()` usa `dv_unitario ×
quantidade_mil` e nunca lê `financeiro_milhoes` —, só o denominador de
qualquer fração de cobertura reportada contra a base do RMD.

Reprodução: `tests/test_coerencia_dv.py::test_pu_vezes_quantidade_bate_com_o_financeiro_do_tesouro`
e `test_ntnb_2050_tem_taxa_implicita_cravada_no_financeiro_do_tesouro` fazem
essa comparação linha a linha e travam as faixas acima.

---

## Convenção de sinal do decay

O decay (`decay_por_papel.csv`, gerado por `dv.decay()`) segue a mesma lógica
de sinal do DV (ver "Antes de qualquer cálculo: confira o lado", no topo
deste documento), mas o sinal do resultado surpreende quem não parar para
pensar:

**O DV de um título é negativo. Com menos prazo até o vencimento, o DV fica
MENOS negativo — então `decay = dv_alvo − dv_base` é, EM REGRA, POSITIVO
para um sobrevivente.** O número mede o quanto o risco "encolheu" em módulo
com a passagem do tempo, não uma perda. Para um papel que vence no caminho,
`dv_alvo` é `0.0` e a mesma fórmula também dá um `decay` positivo — mas essa
positividade é vencimento (calendário), não redução gradual de risco de um
papel vivo. É exatamente para não confundir os dois que existe a coluna
`venceu_no_caminho`: nunca some as duas populações sem olhá-la (ver
`docs/dicionario-de-dados.md`, seção `decay_por_papel.csv`, para o número
medido do efeito de misturar).

**"Em regra" porque há exceção, pequena e explicada pela truncagem.** Em
933 das 18.596 linhas de sobrevivente com decay medido (5,0%, todas
NTN-B), `decay` sai levemente negativo — magnitude minúscula (mediana
−0,000019, mínimo −0,2326), mas presente em 24,6% do horizonte de 1 dia
útil, 6,8% do de 5 dias e 0,4% do de 21 dias. A causa é a mesma quantização
que a seção "A truncagem faz parte do DV" já descreve: dois PUs truncados
independentemente às vezes não guardam a ordem exata que o PU cheio
guardaria, e o efeito pesa mais quanto menor o horizonte. Não é defeito da
tabela — mas quem filtrar `decay < 0` para caçar erro vai achar essas 933
linhas, e precisa saber de antemão que isso é esperado, não sinal de algo
quebrado.

Fonte: o comentário acima de `HORIZONTES`, em `src/tesouro/dv.py`, que traz os
mesmos números — se você mudar um dos dois, mude o outro.

---

## As duas contas: resultado realizado e decay a taxa constante

O projeto responde duas perguntas diferentes, com bases de posição
diferentes de propósito — cada gráfico e cada tabela deste projeto diz qual
das duas está usando, e as duas nunca devem ser somadas ou comparadas como
se fossem a mesma coisa.

**Conta A — resultado realizado, de um fim de mês ao seguinte**
(`dv.resultado_mensal()` → `resultado_mensal.csv`, e `dv.variacao_de_dv()`,
não persistida). Quanto dinheiro se ganhou ou perdeu, com taxa e VNA se
movendo de verdade entre as duas datas. Tem duas metades, com bases de
posição **diferentes** porque respondem perguntas diferentes:

- o **resultado em dinheiro** (`resultado_mensal.csv`) usa a posição
  **congelada no início do mês** — o papel emitido no dia 20 não deu lucro
  nem prejuízo a quem já carregava o título desde o dia 1º; reprecificar
  sobre o estoque final atribuiria a esse investidor um ganho que ele nunca
  teve;
- a **variação de DV** (`dv.variacao_de_dv()`) usa o **estoque real de cada
  data** — emissão e resgate fazem parte da resposta, porque a pergunta aqui
  é "quanto risco o mercado passou a carregar", não "quanto dinheiro alguém
  ganhou".

**Conta B — decay a taxa constante** (`dv.decay()`/`dv.pontual()` →
`decay_por_papel.csv`, e o comando `python -m tesouro.dv --alvo`). Só o
efeito da passagem do tempo, com taxa e VNA **congelados** na data-base:
mecânico, sem dinheiro e sem VNA reprojetado. Prazo menor implica DV menor
em módulo, e é só isso que a Conta B mede.

Confundir as duas leva a erro de interpretação, não de conta: a Conta A pode
mostrar ganho num mês em que a Conta B mostra queda de risco (ou
vice-versa), e isso é esperado — elas respondem perguntas diferentes, com
bases de posição diferentes.

### Limitação conhecida da Conta B: o VNA fica congelado, e isso é material

O decay usa o VNA da data-base também na data-alvo. Para a NTN-B isso
**superestima o decay**, e não por pouco.

O DV da NTN-B escala linearmente com o VNA (`PU = cotação × VNA / 100`),
então uma acreção de x% no VNA move o `dv_alvo` em x%. Medido a partir de
30/06/2026, no horizonte de 21 dias úteis, com decay de 15,911 milhões por
bp com o VNA congelado:

| IPCA no mês | decay de 21du | vs. VNA congelado |
|---|---|---|
| congelado (o que fazemos hoje) | 15,911 | — |
| 0,20% | 13,733 | −13,7% |
| 0,35% | 12,101 | −23,9% |
| 0,50% | 10,468 | −34,2% |
| 0,70% | 8,291 | −47,9% |

A leitura econômica: o risco da NTN-B não encolhe tão rápido quanto o efeito
de `du` sozinho sugere, porque o nocional a que ela está indexada cresce no
caminho. Num horizonte de seis meses, como o pontual até 31/12/2026, o efeito
passa de 30%.

**Por que está assim:** a spec define a Conta B como o efeito puro da
passagem do tempo, sem premissa nenhuma — e projetar o VNA exige ou uma
fonte nova (o VNA projetado da ANBIMA) ou uma premissa de inflação. A escolha
foi ficar sem premissa e **rotular**: o título da figura do pontual diz "taxa
e VNA congelados na data-base", e é isso que os números significam.

**A decisão de mudar já foi tomada** (18/08/2026, com a dona do projeto): o
VNA projetado entra num sub-projeto próprio, onde se escolhe entre puxar o
VNA projetado da ANBIMA e calcular a parte determinística (publicado o IPCA
do mês, o caminho do VNA até o dia 15 está determinado; premissa só além
disso). A LFT não é afetada no decay, porque não tem DV neste projeto.
`_decay_de` é uma função só, usada pelo `decay()` e pelo `pontual()`, então a
mudança entra num lugar; o custo está no insumo, não no código.

---

## Resultado mensal: separando a acumulação de índice da taxa real

Para os títulos indexados (NTN-B ao IPCA, LFT à Selic), o resultado em
dinheiro do mês (`resultado_milhoes`, Conta A) mistura duas coisas de
natureza diferente: o VNA sobe entre as duas datas mesmo com a taxa
(cupom real da NTN-B, ágio da LFT) parada, e essa parte é correção
monetária, não o mercado "ganhando dinheiro" com uma queda de taxa.

É por isso que existe `dv.resultado_decomposto()` (não persistida em CSV —
é análise calculada na hora, mesma regra de `variacao_de_dv()`): reprecifica
cada papel vivo em `data_fim` duas vezes, uma com o VNA de `data_ini` e outra
com o de `data_fim`, mantendo a taxa de `data_ini` fixa nas duas. A diferença
entre as duas reprecificações isola a acumulação de índice; o resíduo é
`resultado_taxa_e_carrego_milhoes`. As duas colunas somam de volta o
`resultado_milhoes` original por construção.

**Sem separar, o resultado mensal sozinho engana.** Medido nos doze meses
terminados em 30/06/2026:

- A NTN-B fechou em **+R$ 29.495,0 milhões** no total — mas isso escondia
  **+R$ 90.095,9 milhões** de acumulação de inflação (3,05× o próprio
  resultado) contra **−R$ 60.600,9 milhões** de movimento de taxa real. O
  sinal do total nem bate com o sinal da parcela que de fato veio de taxa.
  Em março de 2026 sozinho, a parcela de inflação chegou a **565% do
  resultado total do mês** de NTN-B.
- Na LFT o efeito é ainda maior, por construção (ela não tem duration de
  juros): dos **R$ 738.059,3 milhões** de resultado total do painel inteiro
  nesses doze meses, **R$ 568.716,3 milhões (77%)** são o resultado da LFT,
  e desse total quase tudo é acumulação de Selic no VNA, não ágio/deságio de
  mercado.

Reprodução: `tests/test_resultado.py` trava a decomposição linha a linha
(telescopagem exata); os números acima vêm de `dv.resultado_decomposto()`
sobre o painel real.

---

## Refazendo uma conta à mão

`dv_por_papel.csv` guarda os insumos (taxa, VNA, quantidade) junto do
resultado (PU, DV) de propósito, exatamente para isto: abrir o CSV, pegar uma
linha, e reproduzir a conta numa calculadora comum.

Exemplo real, LTN (a fórmula mais simples — sem cupom, sem VNA), linha de
`dv_por_papel.csv` em `data = 30/06/2026`, `isin = BRSTNCLTN8I0`,
`vencimento = 01/04/2027`:

```
taxa_pct = 13,7522      (13,7522% a.a.)
quantidade_mil = 127.836,253
```

1. **Dias úteis entre as duas datas** (calendário Anbima, `cal.du`):
   `du = 188`.
2. **PU** (fórmula da LTN, base 252, truncado em 6 casas). **Atenção ao
   expoente:** `188 / 252` é uma dízima (`0,746031746...`); se você digitar
   o quociente arredondado em vez de manter todas as casas da calculadora
   (ou repetir a divisão sem arredondar no meio), o resultado sai errado na
   6ª casa — arredondar para `0,746032` dá `908,347854`, não `908,347884`.
   Mantenha o expoente como fração (`188/252`), sem arredondar:

   ```
   PU = 1000 / (1 + 0,137522) ^ (188 / 252)
      = 1000 / (1,137522) ^ 0,7460317460...
      = 908,347884...   → truncado: 908,347884
   ```

3. **PU com o choque de +1 bp** (`taxa = 13,7622%`), mesmo expoente:

   ```
   PU(+1bp) = 1000 / (1,137622) ^ 0,7460317460...
            = 908,288316...  → truncado: 908,288316
   ```

4. **DV unitário** = `PU(+1bp) − PU` = `908,288316 − 908,347884` =
   **−0,059568** — negativo, como todo título prefixado (ver "Antes de
   qualquer cálculo: confira o lado", no topo).

5. **DV da posição**, em R$ milhões por bp:

   ```
   dv_posicao_milhoes = dv_unitario × quantidade_mil / 1000
                       = −0,059568 × 127.836,253 / 1000
                       = −7,614950
   ```

Os cinco números — `PU = 908,347884`, `dv_unitario = −0,059568` e
`dv_posicao_milhoes = −7,614950` — batem exatamente com a linha do CSV. Para
NTN-F e NTN-B o procedimento é o mesmo, só com um laço de fluxos de cupom
somados antes de truncar (ver "Como o DV de cada papel é calculado", acima);
para a NTN-B, multiplique a cotação truncada em 4 casas pelo VNA antes do
truncamento final em 6.

---

## Recuperando um arquivo apagado à mão em `data/raw/bloomberg/`

`data/raw/` nunca é sobrescrito nem perde dado — é uma invariante do projeto
— mas o caminho de recuperação quando alguém apaga um arquivo bruto à mão é
áspero, e vale escrever o procedimento em vez de deixar que cada pessoa
descubra sozinha.

Cada rodada de `fetch_bloomberg.baixar()` grava **três** arquivos juntos,
sempre com o mesmo período no nome (a mesma "marca"):
`bbg_taxas_ANDE_<de>_<até>.csv`, `bbg_vna_<de>_<até>.csv` e
`bbg_precos_ANDE_<de>_<até>.csv`. Se você apagar só um dos três (por
exemplo, só o de VNA) e os outros dois do
mesmo período continuarem na pasta, `baixar()` recalcula corretamente que
aquele período voltou a faltar — mas ao tentar gravar de novo, ele tenta
recriar os **três** arquivos daquele período, na mesma ordem sempre (taxa,
depois VNA, depois preço). Como os outros dois (que você não apagou) ainda
existem com aquele nome exato, a função para em `FileExistsError` no
primeiro deles que colidir — não necessariamente no que você apagou.

**O procedimento** é apagar em sequência, seguindo a mensagem de erro:

1. Rode a coleta:

   PowerShell:

       $env:PYTHONPATH="src"; python -m tesouro.fetch_bloomberg

   bash:

       PYTHONPATH=src python -m tesouro.fetch_bloomberg

2. Se der `FileExistsError` num arquivo, apague esse arquivo também (ele
   será refeito do zero, com o mesmo conteúdo de antes, porque a taxa e o
   VNA de uma data passada não mudam).
3. Rode de novo. Repita até a coleta completar sem erro — normalmente duas
   ou três rodadas, porque o irmão que colide muda a cada tentativa (taxa,
   depois VNA, depois preço, na ordem em que `baixar()` os grava).

Isso nunca sobrescreve nada e nunca perde dado — o pior custo é repetir uma
consulta à Bloomberg para um período que já estava correto. É o preço de o
projeto nunca sobrescrever `data/raw/` silenciosamente (ver o incidente
registrado no docstring de `src/tesouro/fetch_bloomberg.py` que motivou essa
regra).

---

## Verificação pendente de autorização

Duas verificações deste sub-projeto dependem de uma consulta à Bloomberg que
não foi autorizada durante a execução, e por isso ficam registradas aqui
como pendência, não como lacuna silenciosa:

- **A coleta ao vivo do coletor (`fetch_bloomberg.baixar()`) nunca foi
  executada de fato** — os testes cobrem a lógica de requisição e o corte
  incremental com um terminal Bloomberg simulado (dublê), nunca com o
  terminal de verdade.
- **O teste que compara o PU calculado com o `PX_DIRTY_MID` da Bloomberg
  pula automaticamente** (`tests/test_coerencia_dv.py::
  test_pu_reproduz_o_preco_da_bloomberg_com_deslocamento_de_d1`), com a
  mensagem explicando o motivo: falta `data/raw/bloomberg/bbg_precos_*.csv`.
  A validação de 438 pares papel-data que fundamenta a seção "Liquidação"
  acima foi feita à mão, fora deste teste — exata em todas as 228
  comparações de NTN-F e nas 210 de NTN-B, diferença máxima de 0,0083 bp,
  com o deslocamento de D+1 aplicado — mas não se reverifica sozinha
  enquanto esse arquivo não existir no repositório.

**O que rodar para habilitar as duas**, com o terminal Bloomberg disponível
e autorização explícita para a consulta:

PowerShell:

    $env:PYTHONPATH="src"; python -m tesouro.fetch_bloomberg

bash:

    PYTHONPATH=src python -m tesouro.fetch_bloomberg

Depois de confirmar que `bbg_precos_ANDE_*.csv` apareceu em
`data/raw/bloomberg/`, rode a suíte de novo — o teste que hoje pula deve
passar a rodar (e a passar).

---
