# As âncoras de valor e o RMD novo

Data: 26/08/2026. Escrita depois de inventariar as 65 falhas, uma a uma.

---

## 1. O problema

O RMD de julho entrou e **65 testes ficaram vermelhos**, em 15 arquivos. Nenhum é
falha de lógica: são âncoras de valor — asserções que travam um número medido, como

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

## 3. Os quatro tipos, inventariados

O inventário das 65 mostrou que não são todas iguais. Cada tipo pede tratamento
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

- as 65 voltam ao verde
- cada âncora nova tem procedência registrada: Excel, coerência, ou decisão explícita
- o retrato novo difere do antigo só onde se espera
- e a prova final: **rodar a suíte contra o RMD de junho de novo deve falhar**. Se
  passar nos dois meses, as âncoras deixaram de travar mês nenhum — viraram espelho,
  e a entrega falhou sem dizer.
