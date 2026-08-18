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
