# DV01, decay e resultado (entrega 2)

**Data:** 2026-08-17
**Status:** design aprovado, aguardando plano de implementação
**Depende de:** `docs/superpowers/specs/2026-08-14-camada-de-dados-design.md`
**Convenções detalhadas:** `docs/convencoes-dv.md`

---

## 1. Contexto

A camada de dados está pronta e no `master`: 17 CSVs canônicos a partir do anexo do
RMD e do histórico de leilões. Esta é a **entrega 2** do projeto: o DV01 da dívida
por papel, o decay e o resultado do estoque numa janela.

As entregas 3 (análise de leilões) e 5 (simulação contra o PAF) vão consumir a
tabela de DV por papel que este sub-projeto produz. É por isso que ela é persistida
em vez de calculada sob demanda: três implementações independentes de DV que
discordam entre si seria o pior resultado possível.

---

## 2. Escopo

**Dentro:** PU, DV01, decay e resultado para **LTN, NTN-F e NTN-B**, em cada fim de
mês do painel; recálculo do financeiro da **LFT** para projeção de composição; e um
comando de cálculo pontual até uma data-alvo escolhida.

**Fora:** NTN-C, NTN-B Principal, RendA+ e EducA+ — sem preço observável no
secundário, 2,1% do estoque. Fora também: curva de juros, rolldown, análise de
leilões, simulação contra o PAF.

**O DV01 cobre 46,5% do estoque** (LTN 14,4% + NTN-F 7,5% + NTN-B 24,7%, pelo
estoque de junho de 2026 — as parcelas arredondadas somam 46,6%, mas o total
calculado com precisão total é 46,5%; ver `docs/convencoes-dv.md`, seção
"Escopo"). Os outros 53,5% são LFT, que não tem duration de juros
por construção, e os excluídos. **Esse número aparece sempre que um total for
reportado** — sem ele, alguém soma o DV01 e supõe que mede a dívida inteira.

---

## 3. Decisões de modelagem

Todas tomadas com a mesa e verificadas onde possível. O detalhe está em
`docs/convencoes-dv.md`; aqui fica o resumo do que vincula a implementação.

- **Base de cálculo em D+0**, embora o mercado negocie em D+1. Consequência aceita:
  o PU fica cerca de 5 bp abaixo da tela, por construção.
- **Data de posição é o último dia útil do mês**, nunca o último dia corrido. São 61
  das 198 datas do painel que diferem.
- **O DV da LFT é tratado como zero.** Matematicamente ele existe e é a
  sensibilidade ao ágio; a decisão é de modelagem, e a LFT entra só pelo financeiro.
- **A truncagem faz parte do DV**, deliberadamente: o preço truncado é o negociável,
  e a diferença entre dois truncados é o que se ganha ou perde em 1 bp.
- **O motor de precificação parte do código em uso na mesa**, já revisado e validado
  (ver §7), com duas correções acordadas: mapeamento do fim de mês para o último dia
  útil, e contagem de dias úteis por índice pré-computado em vez de laço diário.
- **Convenções de sinal:** no resultado, negativo é o mercado perdendo dinheiro; no
  risco emitido, positivo é o Tesouro emitindo. As duas olham da ótica de quem
  carrega o papel.

---

## 4. As duas contas

São coisas diferentes e cada gráfico ou tabela diz qual está usando.

**Conta A — resultado realizado, de um fim de mês ao seguinte.** Quanto o DV do
mercado mudou e quanto dinheiro se ganhou ou perdeu. Precisa de taxa e VNA nas duas
datas. Para a NTN-B, parte do resultado é acumulação de inflação, não movimento de
taxa real.

O ΔDV é medido sobre o **estoque real de cada data** — inclui emissão e resgate, e
responde "quanto risco o mercado passou a carregar". O resultado em dinheiro é
medido sobre a **posição congelada no início do mês** — o papel emitido no dia 20
não deu lucro nem prejuízo a quem estava posicionado no dia 1º.

**Conta B — decay a taxa constante.** Só a queda do DV pela passagem do tempo,
mantendo a taxa fixa. Não envolve dinheiro nem VNA: é mecânico, prazo menor implica
DV menor.

---

## 5. Decay: horizontes e a separação que importa

Os horizontes fixos são **1, 5 e 21 dias úteis**, em base 252, coerentes com o resto
do cálculo e comparáveis entre meses.

O comando pontual aceita **uma data-alvo qualquer**, e os horizontes fixos são
apenas formas nomeadas de calcular essa data. Uma função só.

**Papel que vence entre a data-base e a data-alvo é reportado à parte.** O decay até
uma data distante mistura duas coisas que não se somam: papel que encurtou (vivo,
com menos DV) e papel que sumiu (venceu, DV foi a zero). Juntos, viram um número que
parece decay e é metade calendário. A saída separa:

| | |
|---|---|
| DV na data-base | total da carteira |
| (−) DV que vence no caminho | papéis com vencimento até a data-alvo |
| (−) decay dos sobreviventes | queda de DV dos que continuam vivos |
| DV na data-alvo | só os sobreviventes |

**A separação vale também para os horizontes fixos**, não só para o pontual. Em 21
dias úteis há vencimento com frequência — LTN vence em 1º de janeiro, abril, julho e
outubro; NTN-B em 15 de maio e agosto. Sem a quebra, um mês com vencimento grande
mostra decay enorme e alguém procura explicação de mercado para o que é calendário.

---

## 6. Fontes de dados

O contrato completo está em `docs/convencoes-dv.md`. Em resumo:

| dado | origem |
|---|---|
| Posição por papel | `estoque_titulos_vencimento.csv` (camada de dados, aba 2.2 do RMD) |
| Taxa | Bloomberg, `YLD_YTM_MID` em `/isin/<ISIN>@ANDE Govt`, série histórica mensal |
| VNA do IPCA | Bloomberg, campo `IDX_RATIO` com override `SETTLE_DT`, × 1000 |
| VNA da Selic | Bloomberg, campo `ACCUMULATED_SELIC`, mesmo override, × 1000 |
| Feriados | `data/raw/anbima/feriados_nacionais.xls`, oficial, 2001–2099 |

**Arquitetura idêntica à da camada de dados:** a coleta escreve em `data/raw/`, a
interpretação lê de disco, e o cálculo nunca sabe de onde o dado veio. No ambiente
do banco pode não haver `blpapi`; nesse caso a exportação sai por `BDH` para Excel e
entra na mesma pasta, sem que nada mais mude.

**A coleta da Bloomberg é incremental; o cálculo é sempre completo.** A taxa de
31/03/2015 não muda nunca mais, então repuxar é desperdício. Já o cálculo é barato
depois da otimização de dias úteis, e recalcular tudo elimina a classe inteira de
bug em que o incremento e o completo divergem. Se o Tesouro republicar um mês
antigo, ou se corrigirmos a precificação, o painel inteiro se ajusta sozinho.

**Cobertura medida:** 8.898 pontos de taxa, 185 papéis, de dezembro de 2009 a junho
de 2026. 93,9% dos pares papel-mês com estoque, e **99,23% ponderado pelo
financeiro** — os buracos são LFTs de 2010 e 2011. No último mês, 0,10% do estoque
fica sem taxa.

---

## 7. Validação já realizada

O motor de precificação foi verificado contra o `PX_DIRTY_MID` da Bloomberg em 438
pares papel-data entre 2020 e 2026, aplicando o deslocamento de liquidação D+1:

| título | comparações | resultado |
|---|---|---|
| NTN-F | 228 | exatas, todas |
| NTN-B | 210 | exatas, todas |

Diferença máxima de 0,0083 bp. Isso valida simultaneamente as fórmulas, o calendário
da Anbima, a fonte `ANDE`, o VNA e a contagem de dias úteis — antes de existir uma
linha de código de produção.

---

## 8. Tabelas canônicas

**`dv_por_papel.csv`** — o fato atômico, uma linha por papel e fim de mês:

`data, isin, titulo, vencimento, taxa_pct, vna, pu, dv_unitario, quantidade_mil,
dv_posicao_milhoes, financeiro_calculado_milhoes`

Guarda os insumos junto do resultado de propósito: quem quiser conferir um papel
abre o CSV e refaz a conta à mão. Para a LFT, `dv_unitario` fica **vazio** — não
zero. A diferença importa para quem somar.

**`decay_por_papel.csv`** — decay nos horizontes fixos, também por papel:

`data_base, horizonte, data_alvo, isin, titulo, venceu_no_caminho, dv_base, dv_alvo,
decay`

A quebra entre vencido e sobrevivente é uma coluna, não um total pré-agregado: assim
qualquer agregação escolhe se inclui ou não, sem perder informação.

**O cálculo pontual não vira tabela.** É uma pergunta, não um fato — a data-alvo é
escolha do momento, e persistir resposta de pergunta cria arquivo que ninguém sabe
se ainda vale.

---

## 9. Comando e figuras

```
python -m tesouro.dv --alvo 31/12/2026
```

Imprime o quadro com a decomposição da §5 e grava a figura. Requer `PYTHONPATH=src`,
como o resto do projeto.

**Figuras:** o DV do sistema por tipo de papel (LTN, NTN-F, NTN-B) ao longo do
tempo, e a do cálculo pontual. `matplotlib`, já na lista de bibliotecas permitidas.

---

## 10. Testes de coerência

Na ordem de quanto pegam.

**PU × quantidade contra o `financeiro` da aba 2.2.** O mais forte, e responde de
graça a pergunta que ficou aberta na spec da camada de dados: se bater, o financeiro
do Tesouro é marcação a mercado; se divergir sistematicamente, é curva. Nos dois
casos aprendemos algo, e ganhamos um cruzamento contra fonte independente.

**PU calculado contra `PX_DIRTY_MID` da Bloomberg.** Já validado em 438 pares. Vira
teste permanente — **aplicando o deslocamento de D+1**, conforme a §3 e
`docs/convencoes-dv.md`.

**VNA idêntico entre papéis do mesmo índice.** Verificado em todas as 198 datas, com
divergência exatamente zero.

**DV zero, e não nulo, para papel vencido.** Confundir os dois é como se perde risco
de vista.

**Aditividade do decay:** o decay de 21 dias úteis é próximo da soma dos 21 decays
diários. Não idêntico — a convexidade impede — mas divergência grande indica erro de
contagem de dias.

---

## 11. Armadilhas conhecidas

Descobertas ao validar o contrato de dados. Cada uma produziria número plausível e
errado.

1. **`SETTLE_DT` não serve para taxa histórica.** Ele muda a liquidação, não a data
   do mercado: devolve a taxa de hoje liquidando lá atrás. No fim de 2024 o erro é
   de 135 bp. Serve para o VNA, que é função determinística da data.
2. **A série de preço da LFT na Bloomberg usa o índice corrente.** O preço de 2020
   dividido pelo VNA de hoje dá 1,018 — e dá o mesmo em todos os anos. Inutilizável
   como referência histórica; para a LFT a nossa conta é a referência.
3. **Junção por data literal descarta um terço do painel.** A Bloomberg devolve
   29/05 onde o RMD traz 31/05. Junte por mês, ou normalize os dois lados para o
   último dia útil.
4. **`BZAC2000 Index` é CDI acumulado, não Selic.** Difere do `ACCUMULATED_SELIC` de
   forma crescente ao longo do tempo.
5. **O mercado liquida em D+1.** Ver a §3: nós calculamos em D+0 por decisão, e o
   teste contra a Bloomberg precisa aplicar o deslocamento.

---

## 12. Dependências e decisões adiadas

| Assunto | Situação |
|---|---|
| **VNA projetado no decay** | **Vira sub-projeto próprio (decidido em 18/08/2026).** A Conta B congela o VNA da data-base, o que superestima o decay da NTN-B em 24% a 48% para IPCA de 0,35% a 0,70% no mês — medido, ver `docs/convencoes-dv.md`, seção "Limitação conhecida da Conta B". A entrega 2 fica com o VNA congelado e rotulado |
| Rolldown (decay com curva) | Fora de escopo: exige curva, não a taxa do papel |
| Bandas do PAF de 2023 em diante | Não existem na aba 5.7; bloqueiam a entrega 4, não esta |
| Otimização da contagem de dias úteis | Obrigatória: hoje são 762 ms numa NTN-B 2060 |
| Anomalia `BRSTNCLF1NI0` | ISIN de LFT rotulado NTN-B na aba 2.2; 3 pares, investigar |
