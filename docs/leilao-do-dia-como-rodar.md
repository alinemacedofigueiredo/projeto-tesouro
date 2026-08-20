# O dia de leilão: como rodar

São **três momentos**, e um leilão aparece na tela três vezes. A cada vez o número
fica mais firme, e a barra fica mais sólida.

| momento | comando | a barra | o que ainda pode mudar |
|---|---|---|---|
| **manhã**, sai o edital | `modelo` → preencher → `oferta` | contorno claro | a quantidade (é um **teto**) e a taxa |
| **tarde**, sai o resultado | `python -m tesouro.leilao_do_dia` | hachurada | só a taxa, se a publicada na hora for preliminar |
| **dias depois**, chega a planilha | nada — some sozinho | sólida | nada |

---

## De manhã

```bash
python -m tesouro.leilao_do_dia modelo
```

Ele busca o **edital do dia** na API do Tesouro — que sai a partir das 10h30 — e cria
`data/entrada/leilao_hoje.xlsx` com as pernas certas e **as quantidades já
preenchidas**. Sobra conferir e, se quiser, digitar a taxa.

**Isso não é conforto, é correção.** No primeiro dia de uso, com a planilha montada
pelo histórico, o leilão de 20/08/2026 tinha **seis** pernas — três LTN e três NTN-F
— e só as três NTN-F foram lançadas. As três LTN, 18 milhões de títulos contra 3,65
milhões de NTN-F, ficaram de fora sem que nada avisasse.

Quando a API não responde ou ainda não há edital, ele cai no palpite tirado do
histórico e as quantidades vêm vazias — e o comando diz qual dos dois foi.

As duas colunas que são suas:

- **Quantidade ofertada (títulos)** — já vem do edital. Linha sem quantidade é linha
  apagada, e é assim que você tira do gráfico o que não quiser;
- **Taxa % a.a.** — **opcional**. Em branco, eu uso a do leilão anterior daquele
  papel, que erra 11 bp na mediana.

Depois:

```bash
python -m tesouro.leilao_do_dia oferta
```

Ele diz quantas taxas vieram de você e quantas ele teve de emprestar — e, quando
empresta, de quando é a taxa que emprestou.

### O que ele recusa, e por quê

Cada um destes produziria um número se passasse, e o número iria para o gráfico com
a mesma cara de um número certo:

- **taxa em fração** — `0,0702` no lugar de `7,02`. Não levanta erro sozinho: ele
  precifica, e devolve um PU plausível e completamente errado. *(A LFT escapa da
  guarda: o ágio dela sobre a Selic é mesmo perto de zero.)*
- **vencimento antes da liquidação** — data trocada vira PU negativo;
- **quantidade zero ou negativa**;
- **título que não sabemos precificar**;
- **data obrigatória vazia**.

Em todos, a mensagem diz **a linha do Excel** — a que você vê na tela, não o índice
interno.

E o `modelo` **não sobrescreve** uma planilha já preenchida: se você digitou metade e
rodou de novo por hábito, ele para em vez de apagar o seu trabalho.

## De tarde

```bash
python -m tesouro.leilao_do_dia
```

Ele busca `/resultados` na API do Tesouro. Se ela não responder, procura sozinho um
arquivo salvo à mão em `data/raw/leiloes_api/` (`.json`, `.csv`, `.xls` ou `.xlsx`) e
descobre pelo conteúdo se é a oferta ou o resultado.

**A API funciona nesta rede.** Testado em 20/08/2026: `apiapex.tesouro.gov.br`
responde do mesmo Python que recusa `tesourotransparente.gov.br` por certificado. O
arquivo salvo à mão deixou de ser a via principal e virou o plano B que sempre
deveria ter sido.

**A quantidade aceita substitui o teto sozinha**, pela chave do leilão. E o que ela
digitou de manhã e o arquivo do resultado não traz — a quantidade *ofertada* — é
herdado, para que a leitura de "quanto do ofertado ele colocou" exista no mesmo dia.

### Se algum dia a API cair

Com o pacote de certificados da instituição, o portal antigo também volta a funcionar:

```bash
$env:SSL_CERT_FILE = "C:\caminho\para\ca-bundle.crt"
```

```bash
export SSL_CERT_FILE=/caminho/para/ca-bundle.crt
```

**Não desligue a verificação de certificado.** Num código que vai para um banco, isso
não é uma decisão de tomar sozinha — e o arquivo salvo à mão resolve hoje.

## Dias depois

Nada a fazer. Quando o `historico-leiloes-todos.xls` traz o leilão, a linha
provisória **some sozinha** — a comparação é refeita a cada rodada. É isso que impede
o mesmo leilão de entrar duas vezes no gráfico.

---

## Por que a barra da oferta é um teto

**O Tesouro não aceita tudo o que oferta.** Medido em 9.801 linhas de leilão desde
2015:

| | |
|---|---|
| aceitou **tudo** o que ofertou | 42,6% das linhas |
| aceitou **zero** | 19,5% |
| no agregado, aceito/ofertado | **83,9%** |

E desigualmente por papel: **88,0%** em LTN, 83,4% em NTN-F, 66,7% em LFT, **62,5%**
em NTN-B.

Por isso a barra da manhã responde *"quanto no máximo entra hoje"*, e não *"quanto vai
entrar"*. **Não aplico os 83,9% para "corrigi-la"**: seria trocar um número honesto e
declarado por um inventado que parece medido — e a variação de 62,5% a 88,0% mostra
que a razão média não descreve leilão nenhum.

## Por que a taxa emprestada custa pouco

A do leilão anterior do mesmo papel-vencimento (até 45 dias, só 1ª volta, só leilões
com aceite) erra:

| | taxa | efeito no DV01 do lote |
|---|---|---|
| mediana | 11,0 bp | 0,55% |
| p90 | 36,7 bp | 2,1% |
| p99 | 87,4 bp | 6,8% |

O DV01 quase não se move com a taxa. **A quantidade é a suposição cara; a taxa,
não.** E é justamente por isso que a coluna de taxa é opcional e a de quantidade não.

Quando a taxa emprestada tem **mais de 45 dias**, o comando avisa linha por linha: o
erro medido acima não vale para ela, porque além desse prazo o mercado já é outro.

---

## As janelas

São **curtas**, porque leilão se move em semanas e não em anos. Em "5 anos" cabem
250 barras de três pixels, e a barra de hoje some no meio delas.

| janela | pontos (NTN-B por dia) | começa em |
|---|---|---|
| 20 leilões | 20 | mar/2026 |
| no ano | 31 | jan/2026 |
| **12 meses** (a que abre) | 51 | ago/2025 |
| desde o ano anterior | 82 | jan/2025 |
| 5 anos | 249 | ago/2021 |

**O contador é 20 e não 50, por medição.** O Tesouro leiloa quase toda semana, então
50 pregões são ~50 semanas e a janela colapsa sobre "12 meses" — medi 50 contra 51
pontos, com um dia de diferença no início. Duas janelas iguais é uma janela à toa.

Nos dois gráficos **por semana**, "20 leilões" conta pontos do gráfico, e ali um
ponto é uma semana — são as últimas 20 semanas. Está dito na nota daqueles dois.

## O que foi cortado, e por quê

A primeira versão oferecia todas as opções e não decidia nenhuma: 13 gráficos × 5
janelas × 4 páginas = **260 SVGs**. Agora são **11 × 5 × 3 = 165**, e cada página
fica em **4,9 MB** em vez de 9,67.

- **a janela "completa"** — custava 5,9 MB dos 9,67, **61% do arquivo**, para
  desenhar 702 barras de um pixel. A série longa fica no dashboard do RMD;
- **a opção A de quantidade × taxa** — repetia o idioma de dois eixos que já
  aparece sete vezes. Sobrou a dispersão, que responde uma pergunta que nenhum outro
  gráfico responde;
- **a quarta página** — "venda e compra, só 1ª volta".

## O que ainda depende de você

1. **Qual endereço do portal traz o resultado do dia.** O comando lista todos os
   recursos do `ds013` quando consegue falar com a rede.
2. **Se a taxa publicada na hora bate com a da planilha.** Vale medir no primeiro
   leilão que passar pelos três momentos: se bater sempre, a hachura vira só
   proveniência; se não bater, ela é aviso.
3. ~~O corte entre NTN-B curta e longa.~~ **Decidido em 20/08/2026**, quando a API
   publicou a tabela de benchmarks: curta são os vértices de **3 e 5 anos**, longa é
   de 7 para cima — e a fronteira passou a ser medida no **vértice publicado**, e não
   no prazo calculado.

   A diferença não é cosmética: **401 leilões de NTN-B (9,8%) trocam de faixa**, todos
   papeis que o Tesouro chama de "NTN-B 5 anos" e que, no começo da vigência,
   ainda tinham entre 5,00 e 6,42 anos a correr. No financeiro emitido desde 2010 a
   curta vai de **34,3% para 53,0%**.


---

## A API de leilões, e o que ela permitiu conferir

O endereço é `https://apiapex.tesouro.gov.br/aria/v1/api-leiloes-pub/custom/`. Os
endpoints que este projeto usa:

| endpoint | o que dá | tamanho em 20/08/2026 |
|---|---|---|
| `editais` | a oferta do dia, por benchmark, a partir das 10h30 | 6 registros |
| `resultados` | resultado por leilão, desde 04/01/2018 | 4.598 registros |
| `benchmarks` | o vértice de cada vencimento, com vigência | 18 |
| `calendario` | o que o Tesouro planeja ofertar, ~40 dias à frente | 60 |
| `dealers` | instituições habilitadas, com período | 216 |
| `portarias`, `comunicados` | a oferta pela portaria; título e link | 6, 42 |

`resultado_homologacao` é **byte a byte igual** a `resultados` — mesmo conteúdo em dois
nomes. `dealers_periodo` estourou o tempo limite; ficou de fora até se saber se é
lentidão permanente.

### O que foi conferido antes de confiar

**Contra a planilha do Tesouro** — 6.275 leilões cruzados por (data, título,
vencimento, tipo, volta), nas duas voltas: quantidade aceita, financeiro e oferta
batem em **todos**, com **zero** divergências acima de 0,1%.

**A coerência interna do próprio dado** — `pu_medio` × `quantidade_aceita` reproduz
`financeiro_aceito` com razão 1,000000 nas 454 linhas que trazem PU.

**A precificação do projeto contra o PU publicado** — 434 pares, erro **máximo de
0,0005%**. Nos 251 de LTN e NTN-F a checagem é limpa; em NTN-B e LFT o VNA foi
recuperado do próprio PU deles, então ali se valida a cotação e não o VNA. É a
primeira validação da precificação contra fonte pública, sem Bloomberg.

### Três armadilhas deste payload

1. **`financeiro_aceito` vem em REAIS**, e o resto do projeto trabalha em milhões;
2. **a segunda volta vem em COLUNAS** da mesma linha, enquanto a planilha usa linhas
   separadas — somá-las duplicaria o leilão;
3. **o Bacen vem em colunas próprias** e não está somado no aceito.

E uma quarta, que quase passou: **três fontes escrevem a volta de três jeitos** — a
planilha `1.ª volta`, a API `1a volta`, a planilha de entrada `1a`. Sem normalizar, a
chave do leilão nunca casa e **57 leilões que a planilha já tinha entraram como
novidade**, prontos para aparecer em dobro no gráfico. Não levantou erro nenhum; foi
pego porque o log dizia "70 novas, 0 que a planilha já tinha", e zero casamentos em
trinta dias de leilão não é um número possível.


---

## A página da agenda

`data/processed/agenda.html` — o que o Tesouro **planeja** ofertar, até onde ele
publicou. Regravada pelo `pipeline`, e sozinha por

```bash
python -c "from tesouro.graficos import painel_agenda; painel_agenda.grava()"
```

Três gráficos, na ordem **do mais firme para o mais suposto**:

1. **O cronograma** — só fatos publicados. O vértice fica no eixo vertical para
   mostrar a **cobertura da curva** de cada dia: um dia com 3, 7 e 15 anos faz com o
   prazo médio da dívida algo diferente de um com 5 e 30, e num gráfico por papel os
   dois pareceriam iguais;
2. **O DV01 por título** — calculado da última taxa, mas **sem quantidade nenhuma
   dentro**. É o número mais firme da página, e responde qual dos papeis agendados
   carrega risco: um NTN-B 35 anos carrega **mais de cem vezes** o DV01 de uma LTN de
   6 meses, título a título;
3. **O DV01 do dia, se ele repetir a última oferta** — hachurado inteiro, porque
   **não é previsão**.

E uma **tabela** com tudo, papel a papel, agrupada por dia — para conferir e copiar.

### O que a página não é

**O calendário não traz quantidade.** Ela sai no edital, a partir das 10h30 do
próprio dia. O que aparece na página é o que ele ofertou da **vez passada** daquele
papel — e ele muda de tamanho de leilão para leilão (aceita tudo em 42,6% das linhas,
zero em 19,5%).

A **taxa** de cada papel é a do último leilão dele, e o ⚠ marca as que passaram de
45 dias — fora da faixa em que o erro de 11 bp foi medido.

### O ritmo que ela revela

Os dias alternam: **prefixado** (três LTN + três NTN-F, DV01 de −2,4 a −3,0 milhões
por p.b.) e **LFT + NTN-B** (quatro papeis, −0,65 a −1,65). Os dias de pré carregam
duas a quatro vezes o risco dos outros.

### As cinco páginas

Uma barra no topo liga todas, com links relativos — funcionam com duplo clique, sem
servidor:

`dashboard.html` · `emissoes.html` (mais dois recortes) · `agenda.html`

A barra passou a ser montada num lugar só (`dashboard.grava`) em 20/08/2026: antes
cada painel tinha a sua cópia da lista, e o `dashboard.html` — que não é montado por
painel nenhum — ficava sem saída para os outros.
