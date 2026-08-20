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

Ele cria `data/entrada/leilao_hoje.xlsx` **já montado**: papel, vencimento, data do
leilão, data de liquidação e tipo vêm preenchidos, tirados do que o Tesouro vem
leiloando. Sobram duas colunas para você:

- **Quantidade ofertada (títulos)** — obrigatória. Linha sem quantidade é linha
  apagada, e é assim que você tira do leilão os vencimentos que não estão em oferta
  hoje. Não precisa apagar linha nenhuma;
- **Taxa % a.a.** — **opcional**. Em branco, eu uso a do leilão anterior daquele
  papel, que erra 11 bp na mediana. A sua não erra, porque é a sua leitura do
  mercado naquele momento.

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

Ele tenta a rede primeiro. Se o certificado barrar — e nesta máquina ele barra — ele
procura sozinho um arquivo salvo à mão em `data/raw/leiloes_api/` (`.json`, `.csv`,
`.xls` ou `.xlsx`). Descobre sozinho se aquele arquivo é a oferta ou o resultado,
olhando se há quantidade aceita dentro dele.

**A quantidade aceita substitui o teto sozinha**, pela chave do leilão. E o que ela
digitou de manhã e o arquivo do resultado não traz — a quantidade *ofertada* — é
herdado, para que a leitura de "quanto do ofertado ele colocou" exista no mesmo dia.

### Se a rede liberar

Com o pacote de certificados da instituição, a tarde roda sozinha e dá para agendar:

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
3. **O corte entre NTN-B curta e longa.** Continua em 5 anos, provisório, esperando a
   definição do Tesouro.
