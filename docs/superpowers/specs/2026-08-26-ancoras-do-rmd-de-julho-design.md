# As âncoras de valor e o RMD novo

Data: 26/08/2026, com as contagens refeitas em 27/08 depois de medir.
Escrita depois de inventariar as falhas, uma a uma.

---

## 1. O problema

São **64 testes vermelhos**, e a contagem foi medida em 27/08/2026 rodando a
suíte inteira, não estimada. Eles têm **duas causas diferentes**, e a divisão foi
medida revertendo o CSV do PAF e rodando os mesmos 64 de novo:

| causa | quantos | volta a acontecer |
|---|---|---|
| o RMD virou de junho para julho | **58** | todo mês |
| a revisão do PAF 2026 | **6** | só quando o Tesouro revisa o PAF |

Os 6 do PAF foram lidos um a um e **nenhum é defeito**: são a banda 21-25 cravada,
"oito anos revisados" que agora são nove, e a grade da simulação testada contra a
banda velha. A regra dos eixos, por exemplo, continua certa -- a grade passou a
começar em 48 porque o piso novo é 49 e a margem é 1.

**A cadência diferente importa.** Um título de âncora que diz "oito anos revisados"
envelhece por revisão do PAF, e não por RMD -- quem reescrever as 58 mensais não vai
topar com as 6, e vice-versa.

Nenhum dos 64 é falha de lógica: são âncoras de valor — asserções que travam um número medido, como

```python
assert round(por_ano[2026], 1) == 833.5
```

833,5 era o vencimento de 2026 **medido no RMD de junho**. Em julho dá 584,1.

**As âncoras não estão erradas; estão desatualizadas.** Elas existem porque o medo
declarado deste projeto é "plausível e errado", e um teste que diz "o resultado é
positivo" passa igual mostrando 833 ou 8.330. Foram elas que acharam a coluna
"Demais" zerada desde 2006, o câmbio sendo a DPFe, e os 401 leilões que mudam de
lado conforme o critério da NTN-B.

O custo é que **cada RMD novo exige reescrevê-las**, e isso é trabalho mensal.

---

## 2. O risco desta entrega, e é o que a define

Atualizar âncora é **o trabalho onde o erro não aparece**. Se alguém roda os testes,
pega o número que o código produziu e escreve na asserção, o teste vira **espelho**:
passa a afirmar que o código produz o que o código produz. Fica verde para sempre e
não protege mais nada.

O erro seria silencioso, permanente e invisível — exatamente o oposto de escrever
código novo, onde o erro grita.

**Por isso nenhuma âncora nova pode sair do nosso próprio código.**

---

## 2.1 Não se conta falha com o dado pela metade

A primeira contagem desta entrega deu **65**, e estava errada -- tirada com o VNA de
julho ainda faltando. **Sete daquelas falhas não eram âncora nenhuma:** eram testes
corretos reclamando de dado incompleto, e sumiram sozinhas quando a Bloomberg de
julho entrou. Um quinto do trabalho que eu ia despachar para implementadores era
inventado.

Foi a pergunta dela -- *"onde faltam PUs?"* -- que desmontou a contagem. Sem ela, o
plano teria saído com sete tarefas para consertar testes que não tinham nada de
errado, e alguém teria "consertado" cada um deles reescrevendo uma âncora boa.

**A regra, então:** antes de inventariar qualquer coisa, conferir que RMD, Bloomberg
e leilões estão todos no mesmo mês. Um vermelho tirado de base incompleta não diz
qual dos dois problemas ele é, e o conserto errado -- reescrever a âncora em vez de
completar o dado -- é exatamente a fábrica de espelhos da seção 2.

Vale para o próximo mês também, e é por isso que está escrito aqui e não no ledger.

---

## 3. Os quatro tipos, inventariados

O inventário mostrou que não são todas iguais. Cada tipo pede tratamento
diferente:

### 3.1 Valor que existe no anexo do Tesouro

A maioria. Vencimentos por ano, estoque por indexador, custo médio, prazo, funding.

**Regra: o valor novo sai do Excel, lido direto, sem passar pelo nosso parser.**
Depois se confere que o nosso CSV bate com ele.

Já validado para a composição, em 26/08/2026:

```
                   Excel do Tesouro     nosso CSV
Prefixado             1.785,3461       1.785,346
Índice Preços         2.417,3288       2.417,329
Taxa Flutuante        4.747,2540       4.747,254
Câmbio                  338,8513         338,851
Total                 9.288,7803       9.288,780
```

### 3.2 Contagem ou data cravada no teste

```python
assert base == date(2026, 6, 30)          # a data-base do decay
assert len(vivas_sem_pu) == 8             # deu 57
```

Aqui a pergunta é outra: **a amarra devia existir?** Uma data cravada num teste que
não é sobre aquela data específica é âncora no lugar errado. Cada uma se decide
individualmente — atualizar, ou soltar e travar a relação.

### 3.3 Cruzamento de duas fontes que precisam ser do mesmo mês

Três testes, em `test_conferencia_detentores.py`. Eles comparam a **página do RMD**
(HTML que o Tesouro publica) contra o **anexo**, para provar que as duas fontes
concordam.

Com o anexo em julho e a página guardada em junho, eles comparam meses diferentes —
daí a variação de 28 pontos onde a tolerância é 0,15. **Atualizar o número não
resolve:** ou entra a página de julho, ou o teste vira explicitamente uma
conferência histórica de junho, com as duas fontes fixadas naquele mês.

### 3.4 Relação que nós calculamos, sem fonte externa

DV01, decay, resultado decomposto, candidatos. Não existem no anexo — são cálculo
nosso.

**Regra: conferência de coerência, não de valor.** As partes somam o todo, a série
não tem buraco, o sinal está certo, a ordem entre os papéis se mantém. São
propriedades que valem em qualquer mês, e é isso que as torna melhores que um número
para este grupo.

---

## 4. A verificação, em três camadas

Nenhuma âncora nova entra sem passar por uma delas:

**Camada 1 — contra a fonte.** Onde o valor existe no anexo, ler do Excel e conferir
o nosso CSV contra ele. Já feito para a composição (§3.1).

**Camada 2 — coerência.** Onde não há fonte, verificar relações independentes do mês.

**Camada 3 — o retrato.** No fim, gerar o PDF das sete páginas e comparar com
`data/processed/retrato-2026-08-26-rmd-junho.pdf`, guardado antes da virada.
Diferença esperada: um mês a mais, vencimentos que saíram. Diferença **inesperada**
em qualquer gráfico é defeito.

---

### 4.1 A prova final e executavel, e nao passa por mexer em data

Conferido em 26/08/2026: **o anexo de junho continua em `data/raw/rmd/`**, ao lado
do de julho. Entao "rodar a suite contra junho de novo" nao e figura de linguagem --
da para fazer.

Mas ha uma armadilha no caminho. `leitura_rmd.caminho_do_rmd()` escolhe o anexo
**pelo mtime**, e nao pelo mes no nome:

```python
return max(candidatos, key=lambda p: p.stat().st_mtime)
```

Fazer a prova mudando a data de um arquivo seria conduzir o projeto inteiro pela
data de modificacao -- e este projeto vive dentro do OneDrive, que reescreve
arquivo e mexe em mtime por conta propria. **A prova se faz passando o caminho
explicito** a `leitura_rmd.abrir(caminho=...)`, que ja aceita o argumento.

### 4.2 Um risco que esta entrega ENCONTROU e nao conserta

O criterio de mtime e fragil aqui, e o modo de falha e o pior possivel: se o
OneDrive tocar no anexo de junho depois do de julho, o projeto inteiro volta a
junho **em silencio**. Nao ha excecao, nao ha aviso -- as paginas simplesmente
passam a publicar o mes errado, e todas as ancoras de julho ficariam vermelhas
sem que ninguem soubesse por que.

Medido agora, a folga e de doze dias (julho em 26/08 14:51, junho em 14/08 16:00),
entao nao e urgente. Mas e decisao dela, e nao conserto silencioso dentro desta
entrega -- pela regra da secao 5. As opcoes, para quando ela decidir: escolher pelo
mes lido do nome do arquivo, ou gravar o mes-base junto do CSV processado e conferir.

---

## 5. O que esta entrega NÃO faz

- **Não muda o contrato de âncora do projeto.** A ideia de trocar valor por relação
  em massa foi considerada e descartada: as âncoras de valor pegaram defeito real
  aqui, e trocá-las por relações enfraqueceria a única rede que pega "plausível e
  errado".
- **Não automatiza a atualização.** Um script que reescreve âncoras a partir da saída
  do código é precisamente a fábrica de espelhos que §2 proíbe.
- **Não toca em `src/`.** Se alguma âncora só fecha mudando código de produção, isso
  é defeito achado e vira decisão dela — não conserto silencioso dentro desta
  entrega.

---

## 6. Como saber que deu certo

- as 64 voltam ao verde (58 do RMD, 6 do PAF)
- cada âncora nova tem procedência registrada: Excel, coerência, ou decisão explícita
- o retrato novo difere do antigo só onde se espera
- e a prova final: **rodar a suíte contra o RMD de junho de novo deve falhar**. Se
  passar nos dois meses, as âncoras deixaram de travar mês nenhum — viraram espelho,
  e a entrega falhou sem dizer.
