# Leilões: o que o dado permite

**Medido em 19/08/2026, antes de qualquer desenho.** Não é spec nem plano — é o
levantamento do que existe em `leiloes.csv` e do que dá para calcular com ele, para
que a conversa sobre a entrega 3 comece de evidência e não de suposição.

Foi assim que a entrega 1 saiu boa: as armadilhas foram medidas antes de existir
código de produção.

---

## O arquivo

19.739 linhas, de **04/01/2000 a 13/08/2026**. Uma linha por leilão-papel-volta.

| tipo de leilão | linhas |
|---|---|
| Venda | 16.959 |
| Compra | 1.505 |
| Troca | 598 |
| Extra Compra | 348 |
| Extra Venda | 329 |

Só a **Venda** é emissão. As demais são recompra, troca de papel ou operação
extraordinária — e a distinção importa: a Venda sozinha reproduz **exatamente** o
canal "Oferta Pública" da aba 1.1 do RMD, ano a ano, de 2016 a 2025 (conferido em
`test_os_leiloes_de_venda_reproduzem_a_oferta_publica_da_aba_11`).

### Por papel, só Venda

| papel | leilões | financeiro |
|---|---|---|
| LTN | 6.473 | 7.143 bi |
| LFT | 2.473 | 6.383 bi |
| NTN-B | 4.476 | 2.477 bi |
| NTN-F | 3.296 | 1.238 bi |
| NTN-C | 186 | 27 bi |
| NTN-D | 55 | 47 bi |

As colunas que um cálculo de DV precisaria — taxa média, taxa de corte, quantidade
vendida, vencimento, liquidação, financeiro — estão **100% preenchidas** nas 16.959
linhas de Venda. Só `oferta_qtd` tem buraco, e é pequeno: 1,4%.

---

## O gráfico de DV emitido semanal: é viável, com três fronteiras

A dona do projeto pediu, em 19/08/2026, um gráfico de **DV emitido por semana** para
NTN-F, NTN-B e LTN. Dá para fazer, e as fronteiras são estas.

### 1. A LFT fica de fora, e isso já estava decidido

`precificacao.dv` devolve `None` para LFT — decisão de modelagem da entrega 2, com a
premissa de duration zero. O pedido dela cobre exatamente os três papéis que o
modelo precifica. Não há conflito a resolver.

### 2. O calendário começa em 2001

`calendario.padrao()` levanta `ValueError` para datas anteriores a 01/01/2001 — a
janela vem da cobertura do arquivo de feriados da Anbima. Os leilões de 2000
(52 semanas) ficam fora, e a mensagem é explícita, não silenciosa.

### 3. A NTN-B precisa de VNA, e o nosso VNA é mensal

| | |
|---|---|
| LTN e NTN-F | não precisam de VNA — **9.769 leilões** alcançáveis |
| NTN-B | 4.476 leilões, mas só **3.592 com VNA** (o `vna.csv` começa em jan/2010) |

E o `vna.csv` tem **uma observação por mês** — 198 datas em 199 meses. Os leilões são
semanais: nos últimos doze meses houve NTN-B em 54 semanas distintas.

**Quanto custa usar o VNA de fim de mês num leilão do meio do mês:** o VNA da NTN-B
anda em média **0,47% ao mês** (máximo medido 1,54%, em mar/2015). Como o DV escala
com o VNA, o erro fica em torno de **0,25% em média e 0,77% no pior caso**.

Isso é decisão de modelagem da entrega 3, não desta nota. As saídas conhecidas são
três: aceitar o erro e declará-lo; interpolar o VNA entre fechamentos; ou computar o
VNA pro rata a partir do IPCA, que é o que o Tesouro faz. A terceira é a correta e a
mais cara.

---

## Uma armadilha de unidade, medida

`taxa_media_pct` e `taxa_corte_pct` estão em **percentual** (`8.115` para 8,115%).
`precificacao.pu` e `precificacao.dv` esperam a taxa em **fração** (`0.08115`).

Passar o valor do CSV direto **não levanta erro** — devolve número:

| taxa passada | PU da NTN-B | DV |
|---|---|---|
| `8.115` (como está no CSV) | 84,75 | **0,000000** |
| `0.08115` (fração) | 4.490,15 | −1,127200 |

O VNA de referência naquela data era 4.716 — o PU correto tem de ficar perto disso.
Os 84,75 são plausíveis para quem não conhece a ordem de grandeza, e o DV zerado
passa por "papel sem risco".

É o defeito que este projeto chama de **plausível e errado**, e ele mora na fronteira
entre dois módulos que nunca conversaram: o parser dos leilões e o de precificação.
Qualquer código da entrega 3 que cruze os dois precisa de teste de âncora com o
número certo — não de revisão de código.

---

## Um gráfico que o dado não sustenta

A dispersão entre **taxa de corte e taxa média** é candidata natural a "cauda do
leilão" — mede se houve demanda concentrada no limite.

Medido nas 3.592 NTN-B desde 2010: a diferença é **zero em praticamente todos os
leilões**, com máximo de 1,8 bp. Um gráfico de cauda seria uma linha reta em zero.

Fica registrado para ninguém construir.

---

## O que foi feito depois deste levantamento, em 19-20/08/2026

**O VNA não precisou ser aproximado.** O PU da NTN-B é exatamente linear no VNA
(`PU = VNA × cotação`, e a cotação depende só da taxa e das datas). Como o Tesouro
publica o financeiro e a quantidade de cada leilão, o VNA daquele dia se recupera por
divisão — é o VNA que **ele** usou para liquidar, na data exata, sem interpolar nem
projetar IPCA.

Medido: o VNA recuperado difere do de fim de mês em 0,16% na mediana e 0,66% no
percentil 95 — exatamente o tamanho do erro que o VNA mensal produzia no preço, o que
confirma que era ele a fonte. A correção é material: o DV da NTN-B acima de 10 anos vai de
−1.142,9 para −1.225,7.

**A precificação foi validada contra o Tesouro, 5.600 vezes.** Para LTN e NTN-F, que
não dependem de VNA nenhum, `quantidade × PU` reproduz o financeiro publicado com
mediana de erro **0,0000%** e máximo de 0,13%. É o teste mais forte do módulo, e ele
não afirma nenhum número escolhido por nós.

**A escala da quantidade estava errada e o cruzamento pegou.** `venda_qtd` está em
títulos, não em milhares — com a escala errada o DV saía mil vezes maior, e mil vezes
maior ainda parece número, só que grande demais.

## O que ainda não foi medido

- **demanda**: `oferta_qtd` contra `venda_qtd` — quanto foi ofertado e quanto saiu.
  É a pergunta que os leilões respondem e o RMD não;
- **concentração por vencimento**: quais pontos da curva o Tesouro emitiu em cada
  período;
- **`venda_bacen_qtd` e `financeiro_bacen_milhoes`**: colunas separadas, ainda não
  investigadas — são operações do Banco Central e provavelmente não entram em
  emissão do Tesouro, mas isso precisa ser conferido e não suposto;
- **1.ª e 2.ª volta**: a coluna `volta` existe e não foi analisada.
