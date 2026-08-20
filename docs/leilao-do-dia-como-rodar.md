# O leilão do dia: como rodar hoje

Um comando. Depois que o resultado do leilão sair:

```bash
python -m tesouro.leilao_do_dia
```

Ele tenta a rede primeiro. Se o certificado barrar — e nesta máquina ele barra —
ele procura sozinho um arquivo salvo à mão. Você não precisa escolher entre as duas
vias: ele escolhe.

---

## As duas vias

### Via 1 — a rede, com o pacote de certificados

Se a área de infraestrutura te der o `ca-bundle.crt` da instituição:

```bash
$env:SSL_CERT_FILE = "C:\caminho\para\ca-bundle.crt"
```

```bash
export SSL_CERT_FILE=/caminho/para/ca-bundle.crt
```

Depois disso o comando roda inteiro sozinho, e dá para agendar.

**Não desligue a verificação de certificado.** Num código que vai para um banco,
isso não é uma decisão de tomar sozinha — e a via 2 resolve hoje, sem precisar dela.

### Via 2 — o arquivo salvo à mão

Funciona hoje, sem depender de ninguém:

1. abra no navegador o endereço do leilão no portal do Tesouro;
2. salve o arquivo em

   ```
   data/raw/leiloes_api/
   ```

   Pode ser `.json`, `.csv`, `.xls` ou `.xlsx` — o leitor aceita os quatro, e
   reconhece os nomes de coluna com acento, sem acento, com espaço ou em maiúscula;
3. rode o comando.

É a mesma pasta em que a via 1 grava. O resto do caminho não sabe a diferença.

---

## O que ele imprime

```
1. procurando o recurso no portal...
   a rede nao respondeu: a conexao ... falhou na verificacao do certificado.
   vou procurar arquivo salvo a mao.
2. obtendo o arquivo...
   leiloes-2026-08-20.json, via salvo a mao
3. traduzindo para o esquema do leiloes.csv...
   3 linha(s), de 20/08/2026 a 20/08/2026
4. comparando com o historico da planilha...
   3 nova(s), 0 que a planilha ja tinha
5. recalculando o DV01, com o provisorio...
6. regravando as quatro paginas de emissao...
```

Nenhum passo termina em silêncio. Se algo der errado, a mensagem diz **o quê** e **o
que fazer** — inclusive listando os nomes de coluna que o arquivo realmente tem,
quando for um formato que eu não previ.

---

## A marca do provisório

O leilão que veio da API aparece **hachurado** nos gráficos, com esta entrada na
legenda:

> ▨ leilão do dia (API) · muda quando a planilha sair

**É hachura, e não cor, de propósito.** No gráfico empilhado a cor já significa
papel; roubar uma cor para significar proveniência criaria duas leituras para o mesmo
sinal.

E a marca existe por um motivo que não é estético: **a taxa publicada na hora pode
ser preliminar.** Se for, o DV01 que sai hoje muda quando a planilha chegar. Sem a
marca, você olha um número hoje e outro amanhã sem explicação.

Um dia inteiro fica marcado se **qualquer** papel daquele dia veio da API — a barra
somada já depende de um número que pode mudar.

## E quando a planilha chega

**Some sozinho.** A comparação com o histórico é refeita a cada rodada: no dia em que
o `historico-leiloes-todos.xls` traz aquele leilão, a linha provisória deixa de ser
novidade e sai. Não há nada para limpar à mão, e é isso que impede o mesmo leilão de
entrar duas vezes no gráfico.

---

## O que ainda depende de você

1. **Qual endereço do portal traz o resultado do dia.** O comando lista todos os
   recursos do `ds013` quando consegue falar com a rede. Pela via 2, é você quem
   escolhe o que salvar — e aí saberemos qual é.

2. **Se a taxa do dia bate com a da planilha.** Vale medir no primeiro leilão que
   passar pelas duas: se bater sempre, a hachura vira só proveniência; se não bater,
   ela é aviso.

3. **O corte entre NTN-B curta e longa.** Continua em 5 anos, provisório, esperando a
   definição do Tesouro.
