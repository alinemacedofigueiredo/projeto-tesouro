# Entrega 5 — a simulação: quanto emitir por leilão

Data: 25/08/2026. Escrita depois de medir cada número que ela afirma.

---

## 1. A pergunta

A entrega 4 responde **"estou dentro da banda?"**. Esta responde **"o que faço para
entrar?"**.

São a mesma conversa, e por isso esta entrega **acrescenta um bloco a `paf.html`** —
o terceiro — em vez de criar uma página nova. A decisão está na spec da entrega 4,
§6.4, e não é reaberta aqui.

A projeção da entrega 4 vai numa direção: *dado o ritmo, chego onde?* Esta vai na
inversa: *dado onde quero chegar, que ritmo preciso?* É a mesma conta lida ao
contrário, e o teste que sustenta tudo é essa identidade.

---

## 2. A forma, decidida por ela em 25/08/2026

**Três tabelas independentes, uma por indexador.** Nas palavras dela: *"tabela com
total de dívida em cima e na lateral % do papel, com o miolo respondendo quanto
emitir"*.

Cada célula precisa apenas do estoque-alvo **daquele** papel, que é `total × %`.
Nenhuma tabela depende de como os outros dois se comportam — é o que torna as três
independentes sem truque.

**O custo, dito aqui porque não aparece na tela:** as três não são necessariamente
compatíveis entre si. Ler "prefixado 22% pede X" e "índice de preços 25% pede Y" e
fazer as duas coisas pode não produzir o total escolhido. Cada tabela responde a sua
pergunta isoladamente. **O rodapé diz isso.**

Três alternativas foram descartadas por ela: manter o pace dos outros, ratear a
diferença proporcionalmente, e usar a LFT como colchão. Todas fechariam a conta, e
todas custariam a legibilidade que ela quer.

### 2.1 O miolo: só o quanto, e por leilão

Decisão dela, duas escolhas separadas:

- **Só quanto emitir** — não a diferença para o ritmo atual, e não os dois juntos. O
  ritmo atual aparece uma vez, no rodapé, e a comparação é do leitor.
- **Por leilão**, e não por semana. Cada papel vai a mercado uma vez por semana e os
  dois quase coincidem, mas não exatamente: feriado e a regra do fim do ano mudam a
  contagem. Por leilão é o que o Tesouro executa, e casa com o `pace` que a página já
  usa.

### 2.2 Os eixos: a banda mais uma margem fora

Linhas: a banda do indicador **mais 1 pp para cada lado**. Colunas: total da dívida
de **9.500 a 10.500**, de 200 em 200 — a banda de estoque de 2026 é 9.700 a 10.300.

As linhas dentro da banda ficam marcadas. As de fora existem para mostrar o custo de
furar, e para o caso de o ritmo atual cair fora — que é o caso da taxa flutuante hoje.

---

## 3. A conta

Para o indexador `i`, o alvo `(total, pct)` e o horizonte `31/12`:

```
alvo        = total × pct
emissao     = alvo − estoque_hoje − juros_ate_31/12 + vencimentos_e_cupons
por_leilao  = emissao ÷ leiloes_que_faltam(i)
```

Cada termo já existe e já é testado, da entrega 4:

| termo | de onde vem |
|---|---|
| `estoque_hoje` | `rolagem.estoque_em(hoje)` — RMD rolado, com o leilão da API |
| `juros` | mesma premissa da projeção: Selic implícita para a LFT, inflação implícita mais cupom real para a NTN-B, carga fixa para o prefixado |
| `vencimentos_e_cupons` | `fluxos.pagos(hoje, 31/12)` |
| `leiloes_que_faltam` | `rolagem.leiloes_que_faltam(dias, i)`, sobre o calendário publicado mais o estimado |

**Nenhuma premissa nova.** Se a projeção da entrega 4 estiver certa, esta está; se
estiver errada, as duas erram juntas — e é isso que o teste de identidade trava.

---

## 4. O que as três tabelas dizem hoje

Medido em 26/08/2026, com 33 dias de leilão até 31/12 (10 publicados até 29/09, o
resto estimado), Selic implícita 13,76% e inflação implícita 4,70%.

As tabelas abaixo são **trechos** — mostram algumas linhas de cada uma, para o texto
caber. A tabela da página traz a banda inteira mais 1 pp de cada lado.

### 4.1 Prefixado — banda 21 a 25%, ritmo 14,43 bi/leilão

```
   %  |   9.500   9.700   9.900  10.100  10.300  10.500
  20  |     3,6     6,0     8,3    10,7    13,0    15,4
  21  |     9,2    11,7    14,1    16,6    19,1    21,6   <- banda
  22  |    14,8    17,4    20,0    22,6    25,1    27,7   <- banda
  23  |    20,4    23,1    25,8    28,5    31,2    33,9   <- banda
```

**Nenhuma das 30 células da banda é negativa.** O prefixado está a um passo: manter o
ritmo de hoje leva a 21,10% (projeção da entrega 4), e 21% de 9.900 pede 14,1 contra
os 14,43 atuais. Entrar na banda custa quase nada; subir dentro dela custa caro.

### 4.2 Índice de preços — banda 23 a 27%, ritmo 2,04 bi/leilão

```
   %  |   9.500   9.700   9.900  10.100  10.300  10.500
  22  |    -5,2    -2,5     0,3     3,0     5,8     8,5
  23  |     0,7     3,6     6,5     9,4    12,2    15,1   <- banda
  24  |     6,7     9,7    12,7    15,7    18,7    21,7   <- banda
```

Nenhuma célula da banda é negativa, mas o ritmo é baixo: 23% de 9.900 pede **6,5
bi/leilão contra 2,04 hoje** — mais de três vezes. A projeção da entrega 4 leva a
22,18%, fora por baixo, e esta tabela mostra o tamanho do esforço para reverter.

### 4.3 Taxa flutuante — banda 46 a 50%, ritmo 23,02 bi/leilão

```
   %  |   9.500   9.700   9.900  10.100  10.300  10.500
  46  |   -34,9   -29,1   -23,4   -17,6   -11,9    -6,1   <- banda
  48  |   -23,0   -17,0   -11,0    -5,0     1,0     7,0   <- banda
  50  |   -11,1    -4,9     1,4     7,6    13,9    20,1   <- banda
```

**20 das 30 células da banda são negativas — 67%.** A LFT está em 53,00% e só volta
para dentro pelo canto de baixo à direita: total alto e percentual no teto da banda.
Com a dívida em 9.900 ou menos, chegar a 48% exige **resgatar**, não emitir menos.

Isto é o achado da entrega, e a página não o dizia: para a taxa flutuante, a banda de
2026 não é alcançável só desacelerando a emissão.

---

## 5. A célula negativa

Negativo quer dizer: **nem parando de emitir você chega lá** — o estoque cresce
sozinho pelos juros, e o alvo está abaixo de onde ele vai parar.

A célula mostra **o número, com marca visual**, e não uma palavra genérica como
"impossível". A magnitude é a informação: −4,8 e −40,8 são situações diferentes, e a
segunda diz que o alvo está fora de alcance por qualquer meio ordinário.

O rodapé explica o sinal em uma frase. Sem isso, um número negativo numa tabela
chamada "quanto emitir" parece defeito.

---

## 6. Onde o ritmo atual cai

A célula mais próxima do resultado da projeção da entrega 4 fica **marcada na grade**.

É a ponte entre os dois blocos: o de cima diz onde o ano fecha se nada mudar, este
diz o que fazer diferente. Sem a marca, o leitor tem de procurar na tabela o que a
seção anterior já calculou.

Como a projeção cai entre células (prefixado 21,10%, total 9.947), a marca vai na
célula mais próxima — **arredondando cada eixo ao ponto mais próximo da sua grade,
independentemente do outro**: 21,10% vai para a linha 21, e 9.947 para a coluna
9.900. Não é a menor distância no plano, que dependeria de comparar pontos
percentuais com bilhões de reais e exigiria uma escala inventada.

Se a projeção cair fora da grade — percentual além da banda mais 1 pp, ou total fora
de 9.500 a 10.500 — **nenhuma célula é marcada**, e o rodapé diz que o ritmo atual
leva para fora da tabela. Marcar a célula da borda faria o leitor crer que o ritmo
atual cabe ali dentro.

---

## 7. O código

**`rolagem.emissao_necessaria(indexador, alvo_pct, alvo_total, hoje=None, ate=None)`**
devolve o financeiro por leilão. Fica em `rolagem.py`, ao lado de `projecao`, porque
é dado e não figura — mesma razão que pôs a rolagem fora de `graficos/` na entrega 4
(spec 4, §6.2).

**`graficos/simulacao.py`** é módulo novo, com `dados_simulacao(indexador)` e
`tabela(dados)`. Não entra em `banda.py`: aquele arquivo já tem 400 linhas e duas
tabelas, e receber três matrizes o empurraria para além do que se lê de uma vez.

**`graficos/painel_paf.py`** ganha a terceira seção recolhível, fechada por padrão.

A separação `dados_*` / `desenha_*` do projeto vale aqui: `dados_simulacao` devolve
exatamente o que vai na tela e não importa matplotlib.

---

## 8. Os testes

**O que sustenta tudo: a identidade com a projeção.** Pedir a emissão necessária para
o resultado da própria projeção tem de devolver o pace atual, para os três
indexadores. Se `emissao_necessaria` e `projecao` discordarem, uma das duas está
errada — e o teste não diz qual, mas impede que a página publique as duas.

Os demais:

1. **Monotonicidade.** Alvo maior pede emissão maior, em toda linha e toda coluna.
   Uma inversão de sinal na fórmula passaria por qualquer teste de valor isolado.
2. **A célula negativa aparece como negativa**, com a marca, e o rodapé explica o
   sinal. Travado contra o dado da taxa flutuante, onde 67% das células da banda são
   negativas hoje.
3. **A marca do ritmo atual cai na célula certa** — a mais próxima do resultado da
   projeção, e não a primeira nem a última.
4. **As linhas da banda estão marcadas**, e as de fora não.
5. **A página continua com três blocos** e cabe no limiar de 10 MB.
6. **Determinismo:** duas gerações seguidas produzem o mesmo HTML.

**O que NÃO é testado, e por quê:** a precisão da simulação não tem teste, porque não
existe verdade contra a qual medir — ninguém sabe qual emissão o Tesouro fará. O que
se testa é a consistência interna com a projeção, cuja precisão a entrega 4 já mediu
(erro médio de ±153 bi no ritmo de emissão, dez anos de backtest).

---

## 9. Fora de escopo

- **Simular prazo médio, vincendo e câmbio.** Os três não são rolados na entrega 4
  (ruling 17 e §4.6 da spec anterior), e simular o que não se rola seria inventar.
- **Otimizar.** A tabela responde "para chegar ali, quanto"; não sugere para onde ir.
  A escolha do alvo é dela.
- **Custo.** Emitir mais prefixado a 14% muda o custo da dívida, e esta tabela não
  diz nada sobre isso. É uma entrega própria, se ela quiser.
- **Fonte de dado nova.** Nenhuma. Tudo sai do que a entrega 4 já lê.
