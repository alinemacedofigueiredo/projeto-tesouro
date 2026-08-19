# Dashboard da dívida (entrega 1)

**Data:** 2026-08-18
**Status:** design aprovado, aguardando plano de implementação
**Depende de:** a camada de dados (`2026-08-14-camada-de-dados-design.md`) e a
entrega 2 (`2026-08-17-dv01-decay-design.md`)
**Branch:** `dashboard`, criada de `dv01-decay`

---

## 1. Contexto

O projeto tem cinco entregas. A camada de dados está no `master` com 17 CSVs; a
entrega 2 está pronta e revisada na branch `dv01-decay`, com mais 5 CSVs e o DV01
por papel. Esta é a **entrega 1**: a camada de gráficos.

Ela é a última a ser construída e a primeira que foi pedida, e isso não é acaso —
sem dado limpo não há gráfico honesto. Os treze gráficos principais foram
desenhados como rascunho e **validados um a um** com a dona do projeto antes desta
spec existir. As decisões daquela conversa estão registradas e são a entrada deste
documento.

Vários gráficos foram construídos contra páginas do próprio RMD que ela forneceu, e
**reproduzem os números daquelas páginas exatamente**. Isso não é enfeite: é
validação contra fonte independente, feita antes de existir código de produção.

---

## 2. Escopo

**Dentro:** dezesseis gráficos, um dashboard HTML autocontido com navegação e troca
de período, e o fechamento de uma lacuna no parser de vencimentos.

**Fora:** a análise de distância numérica até a banda do PAF (entrega 4); a
decomposição do custo de emissão em taxa mais variação do indexador; a análise de
leilões (entrega 3); a simulação de trajetória (entrega 5).

**A fronteira com a entrega 4 mudou.** Originalmente toda comparação contra o PAF
era da entrega 4. Como três gráficos aprovados carregam a banda desenhada, manter a
fronteira original significaria construir gráfico pela metade agora e mexer nele
depois. Decisão: **o que é figura com banda vem para cá; o que é medida de
distância fica na 4.**

---

## 3. Decisões de arquitetura

### 3.1 Dado e desenho são funções separadas

Cada gráfico é um par:

- `dados_<nome>(...)` devolve um DataFrame com **exatamente o que vai para a tela**.
  Não importa matplotlib. É onde os testes de número vivem.
- `desenha_<nome>(dados, eixo)` desenha, e é a parte descartável.

Isso serve dois propósitos ao mesmo tempo. O primeiro é a decisão explícita da dona
do projeto: **navegação agora, interatividade se o banco deixar** — trocar o motor
de desenho no futuro não pode exigir reescrever a lógica dos gráficos.

O segundo é a qualidade dos testes. Sem a separação, o teste possível seria "a
figura tem quatro barras", que passa com qualquer implementação. Com ela, o teste é
"a composição de junho de 2026 é 21,0 / 25,9 / 49,3 / 3,7" — que é o número que
importa e o que pega defeito silencioso.

### 3.2 Um módulo por tema, não por gráfico

```
src/tesouro/graficos/
    funding.py       3 gráficos
    estoque.py       1
    detentores.py    3
    vencimentos.py   2 (+1 candidato)
    prazo.py         1
    custo.py         1 (+1 candidato)
    reserva.py       2
    leiloes.py       1 candidato
    estilo.py        cores, meses em português, número brasileiro, eixos
    dashboard.py     monta o HTML
```

Gráficos do mesmo tema leem as mesmas fontes e mudam juntos quando o RMD muda.

### 3.3 O registro é uma lista literal

O `dashboard.py` traz uma lista dizendo quais gráficos existem, em que ordem, em que
grupo, e se aceitam janela. **Sem decorador e sem descoberta automática:** quem
abrir o arquivo vê os dezesseis e entende em trinta segundos. A indireção de um
sistema de registro não se paga para dezesseis itens.

### 3.4 O que fazer com o `figuras.py` da entrega 2

A entrega 2 tem `src/tesouro/figuras.py` com os dois gráficos de DV, que não segue
este padrão. **Não é tocado nesta entrega.** Quando as branches se encontrarem, ele
deve ser absorvido pelo pacote novo — decisão explícita, registrada aqui para não
acontecer em silêncio.

---

## 4. O dashboard

### 4.1 Um arquivo autocontido

`data/processed/dashboard.html`, com os SVGs embutidos no próprio HTML. Abre com
duplo clique, sem servidor, e continua funcionando se for copiado para outra máquina
ou mandado por e-mail. Num banco isso vale mais que elegância.

**Limiar medido, não suposto.** Medido em 19/08/2026: **2,66 MB** com os 25 SVGs
embutidos, contra o limiar de 10 MB. A propriedade "um arquivo só" fica de pé, e o
teste `test_o_arquivo_cabe_no_limiar_de_dez_megabytes` trava o limiar. Se algum dia
passar, os SVGs saem para arquivos ao lado e o HTML os referencia.

### 4.2 Navegação e período

Índice lateral fixo, gráficos agrupados por tema, âncoras. HTML e CSS puros.

Botão no topo com **5 anos** e **série completa**. As duas versões ficam embutidas e
alternam com JavaScript escrito à mão. Nenhuma biblioteca nova — a lista permitida
é `pandas`, `openpyxl`, `xlrd`, `matplotlib`, `pytest`.

**Nove dos dezesseis aceitam janela** — os sete principais mais dois candidatos (o
custo de emissão e a emissão anual por papel), como a tabela da seção 5 marca. Os
outros são retrato de uma data ou têm layout fixo herdado das páginas do RMD. Total:
**25 SVGs**. (Uma versão anterior desta seção dizia sete e 23, contando só os
principais; o número certo é o da tabela, e o teste o deriva do registro.)

### 4.3 Linha de comando

```
$env:PYTHONPATH="src"; python -m tesouro.graficos
```

Sem argumento, gera as duas janelas padrão. Com `--de` e `--ate`, gera o recorte
pedido, e o botão de período some porque só existe uma janela.

Toda instrução no projeto vem em PowerShell primeiro e bash depois, seguindo
`docs/como-baixar.md`. Sintaxe bash sozinha falha na primeira linha no shell da
usuária, e isso já quebrou quatro vezes neste projeto.

### 4.4 O que acompanha cada gráfico

De qual aba do RMD ele vem, qual conta usa quando isso importa, e a cobertura
nomeada quando o total não é a dívida inteira. Fica no HTML como legenda abaixo da
figura, **não dentro do desenho** — assim o texto é selecionável e o SVG fica limpo.

---

## 5. Os dezesseis gráficos

| grupo | gráfico | fonte | janela? |
|---|---|---|---|
| Funding | net do DPMFi com MM12 e acumulado de 12m | 1.1 | sim |
| | emissão por indexador, mensal em reais | 1.2 | sim |
| | emissão anual em 100% por indexador | 1.2 | sim |
| Estoque | composição por indexador com banda do PAF | 2.1 + PAF | sim |
| Detentores | participação relativa e variação | 2.7 | não |
| | quem carrega cada papel | 2.8 | não |
| | financeiro por detentor, oito painéis | 2.8 | sim |
| Vencimentos | cronograma com o balde da cauda | 3.4 | não |
| | composição da DPF com banda do PAF | 3.1 + PAF | não |
| Prazo | prazo médio com banda do PAF | 3.7 + PAF | não |
| Custo | custo do estoque contra Selic e IPCA | 4.1/4.2 + `vna.csv` | sim |
| Reserva | treze meses, no formato do RMD | 6.1 | não |
| | cinco anos, com a folga sombreada | 6.1 | sim |
| *Candidatos* | perfil completo de vencimentos até 2084 | 2.2 | não |
| | custo de emissão contra o do estoque | 4.2/4.3 | sim |
| | emissão anual em 100% por papel | leilões | sim |

Os três candidatos foram construídos em rascunho, não são os preferidos da dona do
projeto, e ela mandou guardá-los. Ficam num grupo próprio no fim do índice: "cada um
escolhe o que olhar" vale de verdade, sem poluir a primeira leitura.

### 5.1 Decisões de desenho já tomadas, gráfico a gráfico

Cada uma destas saiu de uma rodada de crítica sobre um rascunho:

- **Funding:** sem média móvel de 3 meses; só o net do mês e a MM12. O painel de
  acumulado de 12 meses usa preenchimento contínuo nos cruzamentos do zero.
- **Emissão anual em 100%:** por **indexador**, não por papel. A versão por papel
  existe (dos leilões) mas foi recusada: por indexador a cobertura é 100% do RMD,
  contra 93% a 97% dos leilões. O total emitido vai como rótulo acima da barra, e o
  ano parcial é marcado com asterisco.
- **Composição do estoque:** história completa por padrão, não 5 anos. A queda do
  câmbio de 40% para 3,7% é o fato central da gestão da dívida brasileira e
  desaparece numa janela curta.
- **Quem carrega cada papel:** rótulo de percentual só nas fatias de 10% ou mais.
- **Financeiro por detentor:** escala própria em cada painel, porque os detentores
  diferem em ordem de grandeza; Tesouro Direto por último, por ordem de importância.
- **Cronograma:** painel anual mais o balde "Após 5 anos", mais o detalhe mensal com
  marcas em jan/abr/jul/out e divisória na virada do ano.
- **Prazo médio:** rótulos só na DPMFi e na DPFe; a DPF fica como linha de contexto.
- **Custo:** eixo do tempo em marcas anuais mantendo o dado mensal, e rótulo só no
  último ponto de cada linha.
- **Reserva:** as duas versões coexistem. A de treze meses é a linguagem do RMD, para
  apresentação; a de cinco anos diz se o número de hoje é alto ou baixo.
- **Banda do PAF:** desenhada **ano a ano sobre o próprio gráfico**, não como caixa
  estática embaixo como o RMD faz. Onde houve revisão da meta, a banda original
  aparece em linha fina por baixo.

### 5.2 O que foi construído e recusado

Registrado para ninguém reconstruir: detentores em área empilhada; heatmap de papel
contra ano de vencimento (esparso — metade das colunas vazias); sazonalidade de
funding em mês contra ano; risco por real de dívida (a linha cai por aritmética da
premissa de duration zero da LFT, não por achado de mercado, e não mede risco total
porque a dívida trocou risco de marcação por risco de rolagem); e preço da duration
(compara o custo **realizado** da LFT com a taxa **contratada** do prefixado — são
grandezas diferentes, e a comparação correta exigiria curva de juros).

---

## 6. Fontes e dependências

| dado | origem | de onde vem |
|---|---|---|
| funding, estoque, detentores, vencimentos, prazo, custo, reserva | 17 CSVs | camada de dados, `master` |
| Selic e IPCA acumulados em 12 meses | `vna.csv` | **entrega 2** |
| bandas do PAF, 2003 a 2026 | `referencia/paf_bandas.csv` | esta branch |
| banda do vincendo em 12 meses, 2003 a 2022 | `paf_metas.csv` (aba 5.7) | camada de dados |
| taxas de leilão | `leiloes.csv` | camada de dados |

**A Selic e o IPCA saem do nosso próprio VNA.** A variação de 12 meses do VNA que a
entrega 2 coleta é o índice acumulado: 14,78% e 4,81% em jun/2026. A página do RMD
busca isso no site do Bacen; nós não precisamos. É por isso que esta branch nasce de
`dv01-decay` e não do `master`.

**O validador do PAF é pré-requisito de execução.** Se `referencia/paf_bandas.csv`
estiver quebrado, o dashboard **falha** em vez de desenhar banda errada.

**A banda do vincendo em 12 meses tem duas fontes.** A aba 5.7 do RMD publica de
2003 a 2022; a tabela de bandas que a dona do projeto mantém à parte cobre 2016 a
2026, e por isso `paf_bandas.csv` ganhou um sétimo indicador, `vincendo_12m_pct`,
**opcional por ano** — só precisa entrar o que a 5.7 não alcança. Juntas, as duas não
deixam ano sem banda. Nos **sete anos em que se sobrepõem (2016 a 2022) um teste
confere que dão a mesma banda vigente** — e dão.

**A tabela da dona do projeto confirmou a nossa.** Em 19/08/2026 ela forneceu uma
foto dessa tabela, com 2016 a 2026 e as seis revisões do período. Cruzada contra o
`paf_bandas.csv`: **103 comparações, 103 iguais, zero divergências** — duas origens
independentes para os seis indicadores obrigatórios.

**E confirmou a armadilha 5 com um caso medido.** Em 2020 a aba 5.7 guarda uma linha
só, com **24%–28%** — que é a revisão de ago/20. A banda **original** era 20%–23%, e
só a tabela da dona do projeto a tem. A banda desenhada não muda, porque as duas dão
a vigente; o que a 5.7 perde é a memória de que a meta subiu no meio do ano da
pandemia.

---

## 7. A lacuna do parser que esta entrega fecha

`cronograma_vencimentos.csv` traz os 60 meses que a aba 3.4 detalha, somando
6.913,8 bi — mas **não traz o balde "Após 5 anos", de 2.006,9 bi**. Quem somar aquele
arquivo pega **78% do estoque** achando que pegou o todo.

O rascunho contornava lendo a planilha crua. Isso foi recusado, e com razão: trava o
nome do arquivo no código, duplica a interpretação das esquisitices do RMD num
segundo lugar, e quebra a propriedade que faz o projeto funcionar no banco — alguém
coloca o arquivo à mão numa pasta e o resto continua.

**Decisão: fechar a lacuna no parser.** `parse_rmd/vencimentos.py` passa a emitir o
balde, o CSV passa a somar 8.920,7 bi, e um teste trava esse total. É código já
mergeado no `master`, então a alteração vem com teste próprio.

---

## 8. Testes

**Âncoras de valor nas funções de dado.** Cada uma ganha um teste com número medido:
composição em jun/26 de 21,0 / 25,9 / 49,3 / 3,7; reserva de 1.346 contra prudencial
de 783 com índice 8,33; custo do DPF em 12,68 com Selic em 14,78 e IPCA em 4,81;
funding com net de +143,4 e MM12 de +27,7; detentores em 31,8 / 22,0 / 22,5 / 10,0 /
13,8; prazo médio de 4,01 na DPF, 3,90 na DPMFi e 6,93 na DPFe; vencimentos da DPF em
20,1 / 14,1 / 42,2 / 23,6.

**Vários já foram conferidos contra páginas do RMD** que a dona do projeto forneceu.
Onde isso vale, o teste registra a página como fonte — é cruzamento contra fonte
independente, que é o que pega defeito plausível-e-errado.

**Coerência entre gráficos que dividem fonte.** O custo aparece em dois gráficos e
tem que dar o mesmo número. As duas versões de vencimentos coexistem por decisão, e
a diferença de 16,6 bi entre elas é **travada por teste** com o valor atual, para que
mudar sem querer seja detectado; a causa fica para investigação posterior.

**Testes de desenho, mínimos mas com dentes.** A lição que custou seis rodadas na
entrega 2: uma asserção que afirma que a nota de cobertura existe precisa **falhar
quando a linha que a produz é apagada**. Cada asserção é verificada apagando a linha
que ela protege, não lendo o código.

**Reprodutibilidade.** O matplotlib gera identificadores aleatórios dentro do SVG.
Sem fixar `svg.hashsalt`, duas execuções com o mesmo dado produzem arquivos
diferentes e ninguém sabe se o dashboard mudou porque o dado mudou. Fixar é uma
linha, e sem ela o teste de reprodutibilidade é impossível.

**O HTML é testado estruturalmente:** os dezesseis presentes, os grupos presentes, as
duas janelas embutidas nos sete que aceitam janela, e **nenhuma referência externa**
— um `src` apontando para fora quebra o "abre com duplo clique em qualquer máquina".

---

## 9. Armadilhas conhecidas

Medidas durante os rascunhos. Cada uma produziria gráfico plausível e errado.

1. **A aba do cronograma é a 3.4, não a 3.1.** A 3.1 é a de faixas. Confundi as duas
   num rascunho.
2. **A 3.4 é principal a preço de curva**, e detalha só 60 meses. A diferença de 425
   bi contra a aba 2.2 **não é cupom** — foi o que eu afirmei antes de conferir.
3. **A linha do ano aberto na planilha do PAF tem treze valores em vez de dezenove**,
   porque não existe coluna de realizado e as colunas escorregam. Um leitor
   posicional lê o piso do prefixado como se fosse o estoque.
4. **"Selic" e "Taxa Flutuante" são o mesmo indicador do PAF**, renomeado em 2011.
5. **A aba 5.7 do RMD guarda uma linha por ano** e registra a banda revisada como se
   fosse a original. A planilha do PAF guarda as duas e tem oito anos revisados
   contra quatro na 5.7. As fontes concordam; a do PAF é mais rica e é a oficial.
   **Caso medido em 19/08/2026:** o vincendo em 12 meses de 2020 aparece na 5.7 como
   24%–28%, que é a revisão de ago/20; a original era 20%–23%.
6. **Barras emparelhadas de emissão e resgate ao longo de 236 meses são ilegíveis** —
   eu li o meu próprio gráfico errado.
7. **Eixo duplo não é o problema; eixo truncado é.** A versão descartada da reserva
   começava o eixo do índice em 5,7 e exagerava a variação.

---

## 10. Decisões adiadas

| assunto | situação |
|---|---|
| Diferença de 16,6 bi entre os totais da 3.4 e da 2.2 | Os dois gráficos coexistem; a diferença é travada por teste e investigada depois |
| Divergência de 12 meses dos detentores contra o slide do RMD | O nosso dado foi verificado contra a célula crua da aba 2.7 e está fiel ao anexo. A origem do número do slide é desconhecida. Documentar, não perseguir |
| Descontinuidade do Governo em 2012 na aba 2.8 | **Resolvida:** a LFT vai de ~100 para 40 e depois a zero, provavelmente mudança de regra. Dado real, não defeito |
| Decomposição do custo de emissão | Precisa das taxas de leilão cruzadas com o VNA. Trabalho próprio |
| Absorver o `figuras.py` da entrega 2 | Quando as branches se encontrarem |
| Interatividade dentro do gráfico | Se o banco liberar biblioteca. O código nasce preparado para a troca |
