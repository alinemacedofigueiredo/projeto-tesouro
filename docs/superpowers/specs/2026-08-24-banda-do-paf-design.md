# Distância até a banda do PAF (entrega 4)

**Data:** 2026-08-24
**Status:** design revisado com ela em 24/08/2026, **aguardando o sim final para o plano**
**Depende de:** a camada de dados (`2026-08-14-camada-de-dados-design.md`), a
entrega 2 (`2026-08-17-dv01-decay-design.md`) e a entrega 1
(`2026-08-18-dashboard-design.md`)
**Branch:** a criar, `banda-do-paf`, a partir de `master`

---

## 1. Contexto

O projeto tem cinco entregas. As três primeiras estão no `master`: a camada de
dados, o DV01/decay/resultado e os leilões. Esta é a **entrega 4**.

A spec da entrega 1 fixou a fronteira entre as duas em uma frase: *"o que é figura
com banda vem para cá; o que é medida de distância fica na 4"*. Quatro gráficos do
dashboard já desenham a banda do PAF por cima da série. Nenhum diz **de quanto** é a
distância, nem **onde estamos hoje** — todos param na data-base do último RMD.

Esta entrega responde duas perguntas, nesta ordem:

1. **Onde estamos hoje**, e não em 30 de junho. O RMD é mensal; entre a data-base
   dele e hoje passaram-se semanas de leilão que mudaram a composição.
2. **Onde fechamos o ano**, se o ritmo atual continuar.

A tabela de simulação — quanto emitir por semana, por papel, para fechar dentro da
banda — **fica para a entrega 5**, por decisão dela. Esta entrega entrega o ponto de
partida daquela.

### 1.1 O que foi medido antes desta spec existir

Este documento não propõe nada que não tenha sido medido. Os números abaixo saíram
do dado do próprio projeto durante a conversa de desenho, e cada um deles vira teste
na implementação.

---

## 2. Escopo

**Dentro:**

- rolagem do estoque do último RMD até a data corrente, por indexador;
- distância até a banda, para os sete indicadores do PAF, na posição corrente;
- projeção até 31/12 do ano corrente, com premissa saída da própria curva;
- a leitura histórica: com que frequência o Tesouro fecha o ano dentro da banda,
  medida contra a banda **original** e contra a **vigente**;
- uma **página nova**, `paf.html`, irmã do calendário e das emissões.

**Fora:**

- a tabela de simulação "quanto emitir por semana" (entrega 5);
- qualquer fonte de dados nova — nem Bloomberg, nem Focus, nem ANBIMA;
- a DPFe (dívida externa) na rolagem: ela não passa por leilão, e o movimento dela é
  câmbio mais emissão externa, que este projeto não tem. **Isso arrasta o indexador
  Câmbio junto** — ver §4.6;
- o Tesouro Direto na rolagem, pelo mesmo motivo (medido: resíduo pequeno, §4.4).

---

## 3. Os dois bloqueios que a camada de dados registrou

A spec da camada de dados marcou dois itens como **bloqueantes desta entrega**.
Ambos foram verificados antes de escrever este documento.

### 3.1 Bandas do PAF de 2023 em diante — RESOLVIDO

A aba 5.7 do RMD termina em 2022. O `referencia/paf_bandas.csv`, digitado à mão da
planilha do PAF e validado por `valida_referencia`, cobre **2003 a 2026** nos sete
indicadores (o vincendo em 12 meses a partir de 2016). Já é a fonte do gráfico do
total da dívida, entregue em 21/08/2026. **O bloqueio não existe mais.**

### 3.2 Datas de vigência das revisões — CONTINUA ABERTO, e vira decisão de desenho

O arquivo traz `original` e `revisado`, mas **não em que mês a revisão passou a
valer**. São oito anos com revisão: 2008, 2015, 2016, 2018, 2020, 2021, 2024, 2025.

Em vez de tratar isso como pendência, esta spec o trata como **as duas medidas que
o gráfico mostra** — porque a diferença entre elas é o achado mais interessante da
entrega.

**Medido.** Em **14 dos 54 pares** (indicador × ano com revisão), a escolha da
banda inverte o veredito. E em **14 dos 14** a inversão vai para o mesmo lado: fora
pela original, dentro pela revisada. **A revisão nunca foi contra o realizado.**

(Uma primeira contagem deu 13 de 48, usando a coluna `realizado` do arquivo de
referência. Está errada pelo critério do §6.3: o realizado tem de sair do nosso
dado. Refeita, dá 14 de 54 — e o resultado fica mais forte, não mais fraco.)

Sobre os 23 anos e os sete indicadores, com o realizado saindo do nosso dado:

| indicador | dentro da ORIGINAL | dentro da VIGENTE |
|---|---|---|
| Prefixado | 16 de 23 (70%) | 18 de 23 (78%) |
| Índice de preços | 18 de 23 (78%) | 20 de 23 (87%) |
| Taxa flutuante | 11 de 23 (48%) | 16 de 23 (70%) |
| Câmbio | 18 de 23 (78%) | 18 de 23 (78%) |
| Prazo médio | 17 de 21 (81%) | 18 de 21 (86%) |
| Vincendo em 12 meses | 8 de 10 (80%) | 9 de 10 (90%) |
| Estoque | 14 de 23 (61%) | 17 de 23 (74%) |
| **todos** | **102 de 146 (70%)** | **116 de 146 (79%)** |

**Decisão: a página mostra as duas, lado a lado, sempre.** Medir só contra a
vigente produziria um painel em que o Tesouro quase nunca erra — e isso seria
artefato da revisão, não fato sobre a gestão. Medir só contra a original ignoraria
que a banda revisada é a que estava em vigor no fechamento.

A data exata de vigência continua desconhecida e continua **não sendo necessária**,
porque a comparação é sempre do fechamento de dezembro contra as duas bandas do ano
inteiro. Se um dia a data aparecer, ela refina a leitura intra-anual; não muda esta.

---

## 4. A rolagem do estoque

### 4.1 A conta

Para cada indexador, entre a data-base do último RMD (t0) e a data corrente (t1):

```
estoque(t1) = estoque(t0)
            + leilões liquidados em (t0, t1]
            - fluxos pagos em (t0, t1]        <- principal E CUPOM
            + juros apropriados no período
```

**A data que casa é a de LIQUIDAÇÃO, e não a do leilão.** É a data em que o papel
entra no estoque, e é a que o RMD usa. Medido: a defasagem mediana é de 1 dia útil,
mas **6,1% dos leilões liquidam no mês seguinte** ao do leilão — 1.196 de 19.739, e
129 nos últimos dois anos. Casar por data de leilão erra exatamente as viradas de
mês, que é onde o RMD corta.

### 4.2 Os três termos são todos necessários — medido

Backtest em 24 meses fechados de RMD, erro médio absoluto por mês, em R$ bilhões:

| termos usados | Prefixado | Índice de preços | Taxa flutuante |
|---|---|---|---|
| só leilões | 52,7 | 32,7 | 70,7 |
| + vencimentos | 14,6 | 16,3 | 42,0 |
| + juros apropriados | 14,6 | 12,2 | **3,4** |

A apropriação de juros é o maior termo da LFT: **39,9 dos 61,7 bi de variação mensal
média são Selic correndo sobre o estoque, não emissão**. Sem esse termo a rolagem
subestima a taxa flutuante em cerca de 1,1% ao mês.

Erro típico da rolagem completa, em % do estoque do indexador:

| indexador | erro por mês |
|---|---|
| Taxa flutuante | 0,07% |
| Índice de preços | 0,51% |
| Prefixado | 0,75% |

### 4.3 O cupom entra no termo de fluxos, e é 12% dele

Correção dela, em 24/08/2026: *"lembrar que nos vencimentos tem cupons também"*.

**Medido.** Até 31/12/2026, o fluxo a pagar é de R$ 833,5 bi pela aba 3.4, contra
R$ 736,4 bi de principal pela aba 2.2. A diferença — **R$ 97,1 bilhões, 12% do
fluxo** — é cupom: 55,9 de NTN-B e 33,2 de LTN/NTN-F.

**Novembro de 2026 é o caso que prova.** Tem R$ 26,0 bi de fluxo e **zero
principal**: é cupom puro. Uma rolagem que só olhasse a 2.2 faria novembro
desaparecer.

**O cupom é CALCULADO, e não lido da 3.4.** Duas razões:

1. A 3.4 é o **retrato atual** — a camada de dados guarda só o mês corrente. Lido
   dela, o termo não teria como ser testado nos 24 meses do backtest do §4.2.
2. A 3.4 é **mensal**, e a rolagem corta em data. O cupom de NTN-B cai no dia 15, o
   de NTN-F no dia 1º: ratear pelo mês poria dentro da janela um fluxo que ainda não
   aconteceu.

A conta é `quantidade × VNA × ((1 + taxa do cupom)^0,5 − 1)`, com 6% a.a. para a
NTN-B e 10% para a NTN-F.

**ARMADILHA, e ela custou uma tentativa.** A NTN-B **não** paga em todo fevereiro,
maio, agosto e novembro: ela paga **no mês do vencimento dela e seis meses antes**.
Os vencimentos se dividem em dois grupos — 188,6 milhões de títulos vencem em maio e
267,3 em agosto — então agosto e novembro pagam a grupos diferentes. Aplicar a regra
errada dá **2,1 vezes o cupom real**.

Validado contra a 3.4 em novembro, mês em que nada vence e o número é cupom puro:
**calculado R$ 26,4 bi contra R$ 25,8 bi da 3.4, +2,4%**. Em agosto a diferença
aparente é maior porque a NTN-B 15/08/2026 vence nesse mês e o cupom final dela está
dentro da linha de principal da 3.4; descontados esses R$ 7,1 bi, sobram 30,3 contra
30,1.

A NTN-B Principal não paga cupom, e por isso não entra nesta conta.

### 4.4 O termo que falta no prefixado

LTN e NTN-F não têm VNA: carregam para o par pela taxa de emissão. O resíduo médio
do prefixado é **+12,2 bi/mês sobre ~1.900 bi, ou 0,64% ao mês** — que é uma carga
de aproximadamente 13% ao ano, e não ruído.

**A implementação acresce o prefixado pela taxa média de carregamento**, recuperada
do próprio estoque: a mesma inversão que descobriu que a aba 2.2 avalia a carteira
pelo custo de carregamento (achado de 22/08/2026, registrado no commit `84db0ca`).
O teste é o resíduo cair de 0,75% para a mesma ordem dos outros dois.

### 4.5 O que sobra depois dos termos

Tesouro Direto e emissão direta. Medido no §4.2: o resíduo final é 0,07% a 0,75% do
estoque por mês. **Não é modelado, e a página diz isso.** Modelar exigiria dado que
o projeto não tem, e o tamanho não justifica.

### 4.6 O indexador Câmbio fica parado, e isso é uma escolha medida

O indexador **Câmbio da composição é, na prática, a DPFe**: comparados os 307 meses
da série, a diferença mediana entre os dois é de **R$ 4,9 bilhões**, e hoje são
346,4 contra 347,7 bi. Tirar a DPFe da rolagem tira o câmbio junto — não há como
rolar um sem o outro.

**Ele é segurado no valor do último RMD, e a página diz isso.** O custo está medido:
a variação mensal mediana do câmbio é de **R$ 5,2 bi, ou 0,06% do estoque total**; em
dois meses, no pior decil dos casos, R$ 32,5 bi. Contra uma banda de câmbio que hoje
tem largura de pontos percentuais inteiros, é ruído.

O que **não** é aceitável é segurá-lo em silêncio: como ele entra no denominador dos
outros três percentuais, um erro nele contamina todos. Por isso a linha do câmbio na
tabela do §7.1 aparece marcada como não rolada, e não como se fosse medida de hoje.

### 4.7 O VNA depois do último RMD — e por que não precisa da Bloomberg

O `vna.csv` é mensal e termina **exatamente na data-base do RMD**. Os leilões vão
além dela. Sem VNA nesses dias não há termo de juros.

**A saída é o próprio leilão.** `PU = VNA × cotação`, e a cotação depende só da taxa
e das datas — então o PU efetivo (financeiro ÷ quantidade) dividido pela cotação
devolve o VNA que o Tesouro usou naquele dia. A função existe:
`leiloes_dv._vna_implicito`.

**Medido** nos 98 leilões cujo dia coincide com uma data de VNA conhecida:

| papel | leilões | erro mediano | máximo |
|---|---|---|---|
| LFT | 34 | 0,045% | 0,056% |
| NTN-B | 64 | 0,047% | 0,197% |

Na janela aberta hoje (30/06 a 17/08/2026) há **13 leilões de LFT e 31 de NTN-B** —
VNA de sobra. Se num período futuro faltar leilão do papel, a rolagem **falha em voz
alta** em vez de congelar em silêncio: congelar o VNA da LFT por um mês subestima o
estoque dela em ~50 bilhões.

---

## 5. A projeção até 31/12

### 5.1 A premissa sai da curva, e não de um número escolhido

Decisão dela, em 24/08/2026, entre quatro opções apresentadas.

- **Selic implícita:** interpolada na curva de LTN com cotação, pelos dias úteis até
  31/12. Em 30/06/2026: **13,76% a.a.**, acumulando 6,71% no período.
- **Inflação implícita:** breakeven entre a curva prefixada interpolada no prazo da
  NTN-B de referência e a taxa real dela. A **NTN-B de referência é a mais curta com
  cotação cujo vencimento passe de 31/12** — em 30/06/2026, a de 15/05/2027, a 218
  dias úteis. Critério explícito porque "a mais próxima" escolheria a de 15/08/2026,
  a 33 dias úteis, cuja taxa real de 11,25% é ponta de curva e não expectativa.
  Resultado: **4,70% a.a.**, 2,34% no período.

Sem fonte nova, sem número escolhido por mim, e reproduzível.

**Armadilha achada no desenho:** a LTN de vencimento mais próximo de 31/12/2026 é a
**01/01/2027, que não tem cotação** — é um dos dois papéis que só existem no Tesouro
Direto (achado de 22/08/2026). A interpolação usa as LTN com tela dos dois lados, e
a implementação **nunca** pode escolher o vencimento mais próximo sem conferir que
ele tem taxa.

### 5.2 O pace da emissão é o termo fraco, e isso vai escrito

Backtest de dez anos, projetando o segundo semestre a partir de 30/06 pela média
semanal das últimas N semanas. Erro médio absoluto em R$ bilhões, contra um
realizado médio de 237 (prefixado), 85 (índice de preços) e 216 (flutuante):

| indexador | 4 sem | 8 sem | 13 sem | 26 sem | 52 sem |
|---|---|---|---|---|---|
| Prefixado | 130,5 | 113,9 | 117,4 | **104,4** | 128,8 |
| Índice de preços | 43,1 | 54,5 | 57,7 | 48,5 | **37,3** |
| Taxa flutuante | 72,2 | 70,6 | 76,9 | **66,0** | 72,5 |

São erros de 31% a 44%, e **nenhuma janela é muito melhor que outra**.

Refeito na unidade que ela propôs — **dias de leilão** em vez de semanas — o erro da
composição projetada, em pontos percentuais:

| janela | Prefixado | Índice de preços | Taxa flutuante |
|---|---|---|---|
| 10 leilões | 1,45 | **0,46** | **1,29** |
| **20 leilões** | 1,71 | 0,58 | 1,65 |
| 60 leilões | **1,26** | 0,69 | 1,61 |
| 26 semanas | 1,35 | 0,66 | 1,53 |

**O dado não distingue as janelas.** Tudo cai na mesma faixa, e com dez anos de
backtest escolher a melhor é ajustar ao ruído.

**A escolha é 20 dias de leilão**, decisão dela, por dois motivos que não são
estatísticos: são cerca de dez semanas e **dez leilões de cada papel**, que é a
unidade em que quem acompanha o Tesouro pensa; e o dia de leilão lida sozinho com
semana de feriado e com dezembro, que tem menos leilão que os outros meses.

### 5.3 Quantos leilões faltam: o calendário estimado

Pergunta dela, e um buraco real na primeira versão desta spec, que dizia "os leilões
que faltam" sem dizer como contar.

**A fonte é híbrida, e a página diz onde uma acaba e a outra começa:**

1. **O calendário publicado pelo Tesouro**, que a API traz em `/calendario`. Ele vai
   cerca de **seis semanas** à frente — é transcrição, não inferência.
2. **Além dele, o padrão do próprio Tesouro**, descrito por ela e verificado aqui.

**As regras, e o que a medição diz de cada uma** (dias de leilão de venda distintos,
2021 em diante):

| regra | verificação |
|---|---|
| prefixado toda quinta | **94%** dos 288 dias |
| NTN-B toda terça | **97%** dos 280 dias |
| LFT toda terça | **81%** — e **18% na quinta**, que a regra não previa |
| antecipa um dia útil em feriado | **71%** dos 17 casos fora da quinta |
| duas últimas semanas do ano sem leilão | o último leilão do ano caiu entre **15 e 21 de dezembro** nos cinco anos |

**O estimador construído com essas regras acerta quase exatamente.** Dias de leilão
de 1º de setembro a 31 de dezembro:

| ano | estimado | real | erro |
|---|---|---|---|
| 2021 | 32 | 31 | +1 |
| 2022 | 32 | 31 | +1 |
| 2023 | 32 | 32 | 0 |
| 2024 | 32 | 34 | −2 |
| 2025 | 32 | 33 | −1 |

E nas **datas exatas**: 32 de 32 acertadas em 2024 e em 2025, **sem nenhum falso
positivo** — os dois e um dias que faltaram foram leilões extraordinários, que não há
como prever.

2019 e 2020 erram mais (+8 e +4) e ficam de fora da validação: são anteriores ao
padrão atual, e 2020 foi o ano da pandemia.

Para 2026, a partir de 18/08: **36 dias de leilão**, o último em **17/12**.

### 5.4 Mas o erro se cancela no percentual — e é o percentual que a banda mede

Backtest da **composição projetada de dezembro**, a partir de 30/06, com a rolagem
completa do §4 mais o pace de 26 semanas. Erro em pontos percentuais:

| indexador | erro médio | sem 2020 | largura típica da banda |
|---|---|---|---|
| Índice de preços | 0,66 pp | 0,62 pp | 4 pp |
| Prefixado | 1,35 pp | 0,77 pp | 4 pp |
| Taxa flutuante | 1,53 pp | 1,17 pp | 4 pp |

**2020 é o ano que estraga a média** — a projeção errou 6,54 pp no prefixado e 4,81
na taxa flutuante. É o ano em que o Tesouro encurtou a dívida no meio do caminho.
Isso vai escrito na página, e não numa nota de rodapé: **a projeção supõe que o pace
continua, e falha exatamente quando ele não continua** — que é quando mais se
gostaria de saber.

### 5.5 O estoque em reais sai com faixa, e não com ponto

É o único indicador em que a premissa move quase a largura da banda. Medido, só com
apropriação de juros de 30/06 a 31/12, sem emitir nem resgatar nada:

| premissa | prefixado | índice de preços | flutuante | estoque |
|---|---|---|---|---|
| Selic 15% / IPCA 4,5% | 21,09% | 25,62% | 49,77% | R$ 9.850 bi |
| Selic 13% / IPCA 4,5% | 21,18% | 25,74% | 49,55% | R$ 9.807 bi |
| Selic 15% / IPCA 6,5% | 21,04% | 25,80% | 49,66% | R$ 9.872 bi |
| congelado | 20,88% | 26,47% | 48,95% | R$ 9.339 bi |

Nos percentuais a premissa vale 0,2 pp contra bandas de 4 pp. No estoque ela vale
**R$ 511 bi contra uma banda de 600 bi de largura** (9.700 a 10.300 em 2026):
congelar joga para fora, apropriar joga para dentro.

**Decisão: o estoque é o único que sai como faixa**, entre o cenário da curva e o
cenário de Selic 2 pp abaixo. Os outros seis saem como número, porque ali a faixa
seria mais larga que a informação.

---

## 6. Decisões de arquitetura

### 6.1 Um módulo de dado, um de desenho, como todo o resto

- `src/tesouro/rolagem.py` — a rolagem do §4 e a projeção do §5. Não importa
  matplotlib. Produz um DataFrame por indexador e data.
- `src/tesouro/graficos/banda.py` — `dados_*` e `desenha_*`, no molde da entrega 1.

A separação é a mesma da spec da entrega 1, §3.1, e pelo mesmo motivo.

### 6.2 A rolagem é um módulo de `src/tesouro/`, e não de `graficos/`

Ela é dado, não figura, e a entrega 5 vai usá-la como ponto de partida da simulação.
Nascer dentro de `graficos/` a amarraria ao desenho.

### 6.3 O realizado sai do nosso dado, nunca da tabela digitada

`paf.bandas()` já descarta a coluna `realizado` do arquivo de referência de
propósito. Esta entrega segue a regra: o realizado de cada indicador vem de
`composicao_dpf.csv`, `prazo_medio_por_titulo.csv`, `vencimentos_faixa.csv` e
`estoque_dpf.csv`. Ler o realizado de uma tabela digitada seria trocar dado
verificado por dado redigitado.

### 6.4 É uma PÁGINA, e não uma seção do dashboard

A primeira versão desta spec punha tudo como um grupo novo dentro de
`dashboard.html`. **Está errado**, e a dona do projeto apontou: isto é uma página
própria, como o calendário. Três razões, e a terceira é a que decide.

**Cadência.** O dashboard muda uma vez por mês, quando sai o RMD. Esta página muda a
cada **leilão liquidado** — é essa a razão de ela existir. Enterrar uma tabela que
muda toda semana dentro de um arquivo de 4,03 MB significa reescrever 4 MB para
mudar uma linha, e 16,5 segundos de geração contra os 5,6 do calendário. O
calendário é pequeno de propósito, porque é o que se regrava sempre; esta página é
da mesma família.

**Momento de leitura.** O dashboard responde "como está a dívida", e se lê depois do
RMD. Esta responde "estou no rumo, e o que preciso fazer", e se lê na semana do
leilão. Leitor diferente, postura diferente, arquivo diferente.

**As entregas 4 e 5 são a mesma conversa.** "Estou dentro?" e "o que faço para
entrar?" são a pergunta e a resposta. Se a 5 é página — e é —, pôr a 4 no dashboard
separaria as duas metades em arquivos diferentes. A entrega 5 **acrescenta um bloco a
esta página**, e não cria outra.

**O arquivo é `paf.html`**, rótulo "contra o PAF" na barra do topo, entrando entre
`dashboard-funding.html` e `emissoes.html`. Nome de substantivo simples, como
`calendario.html` e `emissoes.html`, e não `dashboard-*`, porque ela não é uma
página do RMD.

Tamanho esperado: os sete gráficos pequenos do §7.3 mais duas tabelas devem ficar na
ordem do calendário, bem abaixo do limiar. A ser medido na implementação.

---

## 7. O que a página mostra

**Dois blocos**, cada um numa seção recolhível — o mesmo molde do calendário, que já
usa `<details>`/`<summary>`. O primeiro abre com a página. (Havia um terceiro; ver
§7.3.)

### 7.1 Onde estamos hoje

Uma tabela, sete linhas — uma por indicador. Colunas: o valor no último RMD, o valor
**hoje** (rolado), a banda do ano, e a distância até ela em pontos percentuais (ou
anos, ou R$ bilhões). Quem está dentro aparece neutro; quem está fora, marcado, com
o sinal de que lado.

A linha do **câmbio** aparece marcada como **não rolada** (§4.6), e não como medida
de hoje.

A tabela diz, em uma linha acima dela, **de quando é o "hoje"** e quantos leilões
entraram na rolagem. Sem isso, o número não tem procedência.

### 7.2 Onde fechamos o ano

A mesma tabela, com a coluna do projetado em 31/12 e a distância projetada. O
estoque sai como faixa (§5.5). Uma linha diz a Selic e a inflação implícitas usadas,
com a data da curva.

### 7.3 O histórico saiu

A primeira versão desta spec tinha um terceiro bloco: um gráfico por indicador com o
realizado de dezembro de cada ano contra as duas bandas.

**Cortado por ela em 24/08/2026, e a decisão está certa.** Aquele bloco é *análise*,
e não monitoramento — responde "quanto vale a promessa do PAF", que é uma pergunta
boa e não é a que faz alguém abrir esta página na terça de manhã. Sete gráficos para
um achado que cabe em duas linhas.

**O achado fica, como texto**, no rodapé dos dois blocos que sobraram: o Tesouro
fecha o ano dentro da banda em **70% dos casos pela banda original e 79% pela
vigente**, e em **14 de 14** inversões a revisão pôs o realizado dentro, nunca fora.
A tabela por indicador está no §3.2 deste documento, para quem quiser o detalhe.

---

## 8. Testes

Cada afirmação medida nesta spec vira um teste. Os que têm de existir:

1. **A rolagem reproduz os 24 meses fechados** dentro do erro medido no §4.2 — é o
   teste que sustenta tudo o mais.
2. **A rolagem casa por liquidação**, e não por data de leilão: um leilão que vira o
   mês entra no período certo.
3. **O VNA implícito bate** com o VNA conhecido nos dias em que os dois existem,
   dentro de 0,2%.
4. **Falta de leilão para recuperar o VNA levanta erro**, e não congela em silêncio.
5. **A interpolação da curva ignora vencimento sem cotação** — com a LTN 01/01/2027
   como caso nomeado.
6. **A distância tem o sinal certo** dos dois lados da banda, e zero dentro dela.
7. **O realizado não vem da coluna `realizado`** do arquivo de referência.
8. **A contagem de acertos** bate com a tabela do §3.2, contra as duas bandas.
9. **A projeção de composição** fica dentro do erro medido no §5.4, nos dez anos do
   backtest — com 2020 nomeado como o caso que estoura.
10. **O cupom calculado bate com a 3.4** em novembro, dentro de 3% — o mês em que
    nada vence e o número é cupom puro.
11. **A NTN-B paga no aniversário dela**, e não em todo fevereiro/maio/agosto/
    novembro: aplicar a regra errada dá 2,1 vezes o cupom real.
12. **O calendário estimado acerta os dias** de setembro a dezembro dentro de dois,
    nos anos de 2021 em diante.
13. **A página cabe no limiar** de 10 MB, como as outras.

Cada guarda é verificada quebrando a linha de produção que ela protege, como no
resto do projeto.

---

## 9. Armadilhas conhecidas

1. **Data de liquidação, não de leilão.** 6,1% dos leilões viram o mês.
2. **A LTN 01/01/2027 não tem cotação.** É o vencimento mais próximo de 31/12/2026 e
   é armadilha para quem interpolar pelo mais próximo.
3. **O VNA acaba junto com o RMD.** Sem o VNA implícito, a LFT sai ~2% subestimada
   na janela aberta.
4. **A LFT domina a apropriação.** 39,9 dos 61,7 bi/mês. Errar esse termo erra o
   indicador de maior peso na dívida.
5. **A banda revisada nunca vai contra o realizado.** 13 de 13. Mostrar só ela
   produz um painel em que o Tesouro não erra.
6. **2020 quebra a projeção**, e deve quebrar: é o ano em que a estratégia mudou.
7. **Câmbio e DPFe são a mesma coisa** — diferença mediana de R$ 4,9 bi em 307
   meses. Quem tirar uma da rolagem tira a outra, e o câmbio está no denominador dos
   outros três percentuais.
8. **A NTN-B só paga cupom no aniversário dela.** Metade do estoque vence em maio e
   metade em agosto; a regra ingênua dobra o cupom.
9. **Novembro de 2026 é cupom puro** — R$ 26,0 bi e zero principal. Quem só olhar a
   aba 2.2 faz o mês sumir.
10. **A LFT também leiloa na quinta**, em 18% dos casos. A regra "terça" cobre 81%.
11. **A NTN-B mais próxima não é a de referência.** A de 33 dias úteis tem taxa real
   de 11,25%, que é ponta de curva, não expectativa.

---

## 10. Decisões adiadas

| assunto | decisão | quando reabrir |
|---|---|---|
| Tabela de simulação "quanto emitir por semana" | Entrega 5, **como um quarto bloco desta mesma página** | Depois desta |
| DPFe na rolagem | Fora: não passa por leilão | Se houver fonte de emissão externa |
| Tesouro Direto na rolagem | Fora: resíduo medido pequeno | Se o resíduo crescer |
| Data de vigência das revisões do PAF | Não é necessária para a comparação anual | Se a leitura intra-anual for pedida |
| VNA projetado no decay da entrega 2 | Sub-projeto próprio, decisão dela em 18/08 | Independente desta |
