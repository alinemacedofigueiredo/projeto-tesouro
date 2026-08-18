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
| **Com DV01 calculado** | LTN, NTN-F, NTN-B | **46,6%** |
| Sem duration de juros | LFT (e LFT-TD1 Reserva) | 51,3% |
| Fora por decisão | NTN-C, NTN-B Principal, RendA+, EducA+ | 2,1% |

Percentuais pelo estoque de junho de 2026. Os excluídos ficaram de fora por não
terem preço observável no secundário.

**O DV01 agregado cobre 46,6% do estoque.** Esse número precisa aparecer sempre que
um total for reportado — caso contrário, alguém soma o DV01 da carteira e supõe que
ele mede a dívida inteira.
