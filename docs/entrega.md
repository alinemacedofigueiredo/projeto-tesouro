# Projeto Tesouro — o que é e como rodar

Versão curta, para quem já conhece o projeto.

## O que ele faz

Pega três fontes do Tesouro — o **RMD**, os **resultados de leilão** e as
**bandas do PAF** — e produz **oito páginas HTML** autocontidas, que você abre
no navegador sem servidor nem internet.

A pergunta central é a da página `paf.html`: **onde a dívida fecha o ano, e isso
está dentro do que o PAF prometeu?**

## O comando

```
cd "C:\Users\lineb\Projetos\Projeto Tesouro"
$env:PYTHONPATH="src"; python -m tesouro.pipeline
```

Ele pergunta o que atualizar:

| | quando | tempo |
|---|---|---|
| `leiloes` | terça e quinta, depois do resultado sair | 135 s |
| `rmd` | uma vez por mês, quando sai o RMD | 171 s |
| `paf` | quando o Tesouro revisa a banda | 69 s |
| `tudo` | quando você não tem certeza | 191 s |

O passo a passo de cada situação, e o que fazer quando falha, está em
[`docs/como-atualizar.md`](como-atualizar.md).

## Como saber se deu certo

**Toda página diz no alto de onde veio o que ela mostra:**

```
RMD de julho/2026 (base 31/07/2026) · último leilão 08/09/2026, liquidado em 09/09/2026
```

**Se esse cabeçalho não mudou depois de uma atualização, a atualização não
atualizou** — confira isso antes de acreditar no `concluido.` do log. Foi assim
que dois defeitos apareceram em setembro.

## O que ele NÃO faz sozinho

- **A banda do PAF entra a mão.** Você lê o informe e edita
  `referencia/paf_bandas.csv`. O modo `paf` confere o arquivo antes de
  desenhar, e recusa se estiver quebrado.
- **A Bloomberg precisa do terminal aberto**, na máquina da mesa.
- **O anexo do RMD** pode precisar vir pelo navegador, quando o certificado do
  site trava o download automático.
- **O câmbio é segurado** no valor do último RMD — ele não passa por leilão, e
  a página marca a linha como não rolada.

## Onde as coisas ficam

```
data/processed/*.html    as oito páginas
data/processed/*.csv     os 24 CSVs que as alimentam
referencia/              o que entra a mão (bandas do PAF, detentores)
docs/como-atualizar.md   o manual de operação
```

O código e o histórico estão no GitHub, em repositório privado. Os dados não —
eles se reconstroem a partir das fontes.

## O que sustenta os números

A rolagem **reproduz os 24 meses fechados do RMD** com viés médio de −0,03% no
prefixado, −0,11% no índice de preços e −0,05% na taxa flutuante. O pior mês do
prefixado é 0,12%.

E houve um **teste fora da amostra**: a previsão de julho foi registrada antes
de o RMD sair e errou **0,099%** no total.
