# O leilão do dia, pela API

**Escrito na noite de 19-20/08/2026**, depois do pedido de ter os gráficos de leilão
logo após o resultado sair, em vez de no dia seguinte.

Este documento diz **o que já está pronto**, **o que falta**, e **exatamente o que eu
preciso para terminar** — porque o que falta depende de uma coisa que não consegui
obter daqui.

---

## O problema

O `historico-leiloes-todos.xls` é publicado pelo Tesouro com atraso: um dia, às vezes
mais. Quem acompanha leilão precisa do número quando o resultado sai.

## A regra que organiza a solução

**A planilha é a fonte definitiva; a API é provisória.**

Todo o resto decorre disso:

| arquivo | o que é |
|---|---|
| `leiloes.csv` | **só** a planilha. Contrato inalterado — os testes que já o usam continuam querendo dizer o que queriam |
| `leiloes_recentes.csv` | só o que a API trouxe e a planilha ainda **não** tem |
| `leiloes_recentes.completo()` | a união, com a coluna `origem` dizendo de onde veio cada linha |

Quando a planilha finalmente traz um leilão, a linha da API para ele **some sozinha**.
A reconciliação é automática: ninguém precisa lembrar de limpar, e é isso que impede
o mesmo leilão de entrar duas vezes no gráfico.

## O que está pronto e testado

`src/tesouro/leiloes_recentes.py` — a mesclagem, com nove testes:

- **a chave de um leilão** é `(data_leilao, data_liquidacao, titulo, data_vencimento,
  tipo_leilao, volta)`. Medido: única em 19.731 das 19.739 linhas;
- **as oito exceções** são quatro pares em 12/05/2009 — duplicata da própria planilha
  do Tesouro, não defeito nosso. Estão declaradas numa constante e travadas por teste
  com o número exato, para que uma duplicata **nova** seja notada em vez de virar
  rotina;
- **`data_liquidacao` está na chave por medição**, não por gosto: sem ela a chave
  colide 12 vezes — em 29/01/2004 o mesmo papel foi leiloado com duas liquidações;
- **hora na data não faz a linha parecer nova.** A planilha traz data sem hora e a
  API pode trazer com. Sem normalizar, toda linha da API pareceria nova para sempre e
  o arquivo recente cresceria duplicando o histórico inteiro. Conferido quebrando a
  linha que protege;
- **a reconciliação é reconferida na hora de juntar**, e não só na de gravar: o
  `leiloes_recentes.csv` pode ter sido gravado antes de a planilha ser atualizada, e
  nesse intervalo ele carrega linhas que já viraram definitivas.

`src/tesouro/fetch_leiloes_api.py` — a coleta, em duas camadas:

- `recursos_do_dataset()` pergunta ao CKAN quais recursos o dataset `ds013` tem. A URL
  não fica fixada no código, então reorganização no portal não quebra o coletor — é o
  mesmo desenho do `fetch_leiloes.py` que já existia;
- `baixar()` guarda a resposta **crua** em `data/raw/leiloes_api/`, com a data no
  nome. A API é um alvo móvel e a planilha é o registro: guardar o que ela disse, no
  dia em que disse, é o que permite reprocessar depois sem depender de a API ainda
  responder o mesmo.

---

## O que estava faltando, e foi fechado em 20/08/2026

**Faltava a tradução do que a API devolve para o esquema do `leiloes.csv`** — e eu
não conseguia ver uma resposta real, porque a rede desta máquina intercepta TLS.

A saída não foi adivinhar um formato: foi escrever um leitor **tolerante na entrada e
rigoroso na saída** (`src/tesouro/parse_leiloes_api.py`, onze testes).

- **aceita** JSON do CKAN (`result.records`), JSON de lista pura, `records`, CSV, XLS
  e XLSX;
- **mapeia** os nomes de coluna por tabela de sinônimos, ignorando acento, espaço e
  caixa — "Data do Leilão", "DATA_LEILAO" e "dataLeilao" caem no mesmo lugar;
- **lê a data como brasileira**, porque 08/03/2026 lido ao contrário põe o leilão num
  mês errado sem levantar nada — as duas leituras são datas válidas;
- **recusa em voz alta** quando falta coluna essencial, dizendo quais colunas o
  arquivo realmente tem. Nunca devolve tabela pela metade.

As três linhas protegidas foram quebradas uma a uma para confirmar que a asserção
falha.

E `fetch_leiloes_api.obter()` agora tenta **as duas vias**: a rede primeiro, o arquivo
salvo à mão depois. Só levanta quando as duas falham — e aí a mensagem diz o que
tentou e o que fazer.

**Como rodar:** `docs/leilao-do-dia-como-rodar.md`.

---

## O contexto que motivou tudo isto

### O problema de certificado, que continua de pé

**Falta a tradução do que a API devolve para o esquema do `leiloes.csv`.** Ela é
pequena — mapear nomes de coluna e converter tipos — mas escrevê-la sem ver uma
resposta real seria adivinhação, e adivinhação neste projeto vira defeito
plausível-e-errado.

Não consegui ver a resposta porque **a rede desta máquina intercepta TLS**. O Python
recusa a conexão com `CERTIFICATE_VERIFY_FAILED`: o certificado que chega é o do
proxy, e ele não conhece a autoridade que o assinou.

**A saída não é desligar a verificação.** Num código que vai para um banco, desligar
verificação de certificado é exatamente o tipo de decisão que não se toma sozinho — e
o módulo já traz a mensagem explicando a alternativa correta.

### Duas formas de destravar

**A primeira, se a infraestrutura fornecer o pacote de certificados:**

```bash
$env:SSL_CERT_FILE = "C:\caminho\para\ca-bundle.crt"
```

```bash
export SSL_CERT_FILE=/caminho/para/ca-bundle.crt
```

Com isso, `recursos_do_dataset()` roda e mostra o que o portal oferece.

**A segunda, sem depender de ninguém:** abra no navegador

```
https://www.tesourotransparente.gov.br/ckan/api/3/action/package_show?id=ds013
```

salve o JSON em `data/raw/leiloes_api/`, e me diga. Com uma resposta real em mãos eu
escrevo a tradução e fecho o circuito.

---

## O que ainda vai precisar de decisão sua

Anotado agora para não virar suposição depois:

1. **Qual recurso do portal traz o resultado do dia.** O `ds013` tem vários; o
   histórico completo é um deles. Pode haver um arquivo por ano, ou um endpoint de
   resultados recentes — só a resposta real diz.

2. **O que fazer quando a API e a planilha discordarem** sobre um leilão que as duas
   têm. Hoje a planilha vence e a linha da API é descartada, em silêncio. A
   alternativa é registrar a divergência num relatório — mais trabalho, e vale a pena
   se acontecer. Vale medir antes de decidir.

3. **Se a taxa do dia do leilão é a mesma que a da planilha.** O resultado publicado
   na hora pode ser preliminar. Se for, o DV01 calculado com ele muda quando a
   planilha chegar — e aí a coluna `origem` deixa de ser um detalhe de proveniência e
   vira aviso na tela.
