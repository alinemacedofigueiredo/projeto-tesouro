# Projeto Tesouro — resumo de entrega

Para quem não acompanhou a construção.

## A pergunta que ele responde

**Onde a Dívida Pública Federal fecha o ano, e isso está dentro do que o PAF
prometeu?**

O Plano Anual de Financiamento publica bandas para a composição da dívida —
quanto pode ser prefixado, indexado a preços, flutuante e câmbio — e para o
estoque total. Ao longo do ano ninguém sabe onde vai fechar: o RMD é mensal e
olha para trás; os leilões são de terça e quinta e olham para a frente.

O projeto junta os dois: parte do último RMD, acrescenta os leilões liquidados
desde então, subtrai vencimentos e cupons pagos, apropria juros, e projeta o
ritmo atual de emissão até 31/12.

## As fontes

| fonte | o que traz | cobertura |
|---|---|---|
| **RMD** (anexo mensal) | composição, custo, prazo, vencimentos, detentores | 308 meses, desde dez/2000 |
| **Leilões** (planilha + API) | resultado de cada leilão | 19.739 linhas, desde jan/2000 |
| **Bloomberg** | taxa, VNA e preço de referência | precisa do terminal |
| **PAF** (a mão) | as bandas do ano, original e revisada | digitado do informe |

A planilha histórica de leilões trava no certificado do SERPRO; o leilão novo
entra pela **API**, que responde. **A verificação de certificado nunca é
desligada** — se for preciso, aponta-se `SSL_CERT_FILE` para o pacote da
instituição.

## O que ele produz

Oito páginas HTML **autocontidas** — sem servidor, sem internet, sem CDN. Cada
gráfico vai embutido como SVG no próprio arquivo.

| página | responde |
|---|---|
| `paf.html` | onde fechamos o ano, e o que fazer para entrar na banda |
| `dashboard.html` | estoque, prazo e custo |
| `dashboard-funding.html` | funding e detentores |
| `emissoes.html` (+2 variantes) | o que já foi emitido, por dia e por semana |
| `emissoes-historico.html` | 25 anos de emissão, por mês e por ano |
| `calendario.html` | o que vem pela frente |

## O que sustenta os números

**A rolagem reproduz os meses que já aconteceram.** Nos 24 meses fechados do
RMD, o viés médio é:

```
Prefixado        −0,032%     pior mês 0,120%
Índice de Preços −0,106%     pior mês 0,455%
Taxa Flutuante   −0,045%     pior mês 0,207%
```

**E houve um teste fora da amostra**, que é a prova mais dura: a previsão do
fechamento de julho foi registrada **antes** de o RMD sair, e errou **0,099%**
no total.

**Toda página declara a própria procedência** — qual RMD, qual o último leilão
puxado, de onde veio o calendário, e qual premissa de juros foi usada.

**A suíte tem 934 testes** e cada âncora de valor foi conferida por mutação:
quebrar a linha de produção que ela protege tem de deixá-la vermelha. Um teste
que nunca fica vermelho não protege nada.

## O que ele NÃO faz — e os tamanhos

- **A banda do PAF entra a mão.** A tabela do informe usa fonte com codificação
  própria e não sai por código.
- **O câmbio é segurado** no valor do último RMD: ele é a DPFe, não passa por
  leilão, e o movimento dele é câmbio mais emissão externa, que este projeto não
  tem. Custo medido: variação mensal mediana de R$ 5,2 bi, 0,06% do estoque. A
  página marca a linha como não rolada.
- **A NTN-C usa VNA de IPCA** por falta de série de IGP-M. Um papel vivo, 0,85%
  do estoque. Decisão consciente, com o erro medido no código.
- **O DV01 cobre pouco menos da metade da dívida.** A LFT entra por financeiro
  com DV01 zero, e ela é mais da metade do estoque. Isso aparece nomeado nas
  páginas, não em silêncio.
- **Sobra um resíduo de ~0,05% ao mês** na rolagem, sem explicação. Em cinco
  meses de projeção vale 0,06 pp na taxa flutuante — um oitavo da folga atual
  até o teto da banda. Está escrito no código.

## Como operar

```
$env:PYTHONPATH="src"; python -m tesouro.pipeline
```

Sem argumento, ele pergunta o que atualizar: **RMD**, **leilões**, **PAF** ou
**tudo**. Cada modo coleta só a fonte que se moveu e regrava só as páginas que
aquela fonte muda — de 69 a 191 segundos, conforme o caso.

O manual de operação, com o passo a passo de cada situação e o que fazer quando
falha, está em [`docs/como-atualizar.md`](como-atualizar.md).

**A verificação mais útil, e a que já pegou dois defeitos:** toda página diz no
alto de onde veio o que mostra. Se aquele cabeçalho não mudou depois de uma
atualização, a atualização não atualizou — por mais que o programa diga
`concluido.`
