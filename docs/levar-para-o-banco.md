# Levar o projeto para o banco

Este arquivo é para ser **colado inteiro** no começo da conversa com a IA que
for ajudar dentro do banco. Ele responde as perguntas que ela faria, e evita as
três ou quatro coisas que ela tenderia a fazer de errado.

---

## Cole a partir daqui

Você vai me ajudar com um projeto Python que analisa a Dívida Pública Federal
brasileira. Ele acabou de ser copiado para esta máquina, dentro da rede de um
banco. Leia este briefing antes de propor qualquer mudança.

### Não há caminho para arrumar

Esta é a primeira coisa, porque é a primeira que você vai querer mexer.

Todos os caminhos saem de um lugar só, `src/tesouro/config.py`, e ele se
localiza sozinho:

    RAIZ = Path(__file__).resolve().parents[2]

O projeto roda em **qualquer pasta, com qualquer nome, em qualquer máquina**.
Não existe caminho absoluto em `src/` nem em `tests/`. Se algo não achar um
arquivo, o problema é o arquivo faltando, não o caminho — procure o arquivo
antes de editar código.

A única exceção é um exemplo de `cd` no `docs/como-atualizar.md`, que é
documentação e aponta para a pasta da máquina antiga.

### A primeira coisa a fazer: rodar a suíte

    $env:PYTHONPATH="src"; python -m pytest -q

Eram **1120 testes passando, em 17 minutos** na última medição (05/11/2026).
Se passarem aqui, o transporte não quebrou nada e você pode confiar no resto.
Se algum falhar, me diga **qual** e o que ele afirma, antes de consertar.

Um aviso sobre medir: **não jogue o pytest num `| tail`**. O código de saída
que volta é o do `tail`, não o do pytest, e isso já me fez dar um "verde" para
uma corrida que tinha parado no meio. Redirecione para arquivo e leia o código
de saída de verdade.

### Ambiente

- **Python 3.12** (era 3.12.10 na máquina de origem).
- `pip install -r requirements.txt` — pandas, openpyxl, xlrd, matplotlib, pytest.
- `pip install -r requirements-envio.txt` — **separado de propósito**. Só o
  `pywin32`, e só para mandar e-mail. A razão está escrita lá dentro: se ele
  estivesse na lista principal, um download bloqueado pelo banco derrubaria a
  instalação inteira, e o projeto não rodaria nem para gravar as páginas, que é
  o que ele faz todo dia.

### Certificado: nunca desligue a verificação

Se uma coleta falhar com erro de certificado, **não** use `verify=False`, nem
`ssl._create_unverified_context`, nem `-k`. Essa é uma regra do projeto e existe
um teste que reprova se a mensagem de erro sequer sugerir isso.

O jeito certo é apontar o Python para o pacote de certificados da instituição:

    $env:SSL_CERT_FILE = "C:\caminho\para\ca-bundle.crt"

### Se a rede não alcançar o Tesouro

Muito provável aqui. O projeto foi desenhado para isso:

    $env:PYTHONPATH="src"; python -m tesouro.pipeline --sem-coleta

`--sem-coleta` não baixa nada e usa o que já está em `data/raw/`. As páginas
HTML e os CSV de `data/processed/` são **gerados** a partir do `raw` — se eles
não vieram no pacote, é porque devem ser refeitos aqui.

### `data/raw/` é imutável

Invariante do projeto: só a coleta escreve ali, e **arquivo nunca é reescrito**
(a primeira gravação vence). Nada mais no projeto pode escrever nessa pasta.
Se você precisar de um arquivo transformado, grave em `data/processed/`.

### E-mail de leilão

- O motor é o **Outlook clássico**. O "novo Outlook" não tem a porta COM que o
  `pywin32` usa.
- **O projeto nunca vê, pede nem guarda senha.** O caminho do Outlook foi
  escolhido exatamente por isso, e há um teste que reprova se aparecer
  `password`, `getpass` ou `credential` em `src/tesouro/envio.py`.
- **`Send()` não envia: ele enfileira.** Já custou um leilão: o `Send()`
  devolveu sucesso e a mensagem ficou 25 minutos na Caixa de Saída enquanto o
  programa dizia "enviado". A prova de que saiu é **encontrar o assunto na
  pasta Enviados**, e é assim que o código faz hoje. Não troque isso pelo
  retorno do `Send()`.
- Destinatários ficam em `referencia/destinatarios.txt`. **Sem ninguém na
  lista, ele roda em ensaio** — de propósito.

### Bloomberg

Existe `src/tesouro/fetch_bloomberg.py`, que usa o `blpapi`. **Só puxe da
Bloomberg quando a Aline disser, caso a caso, que o terminal está aberto.**
Não assuma que está, mesmo que ela tenha dito ontem.

### Regra de escrita do código

Todo arquivo `.py` em `src/` e `tests/` é **ASCII puro**. Acento vai como
escape `\uXXXX`, e só dentro de literal de string, nunca em comentário. Há um
teste que varre o projeto e reprova o contrário. Markdown pode ter acento.

### Dois defeitos conhecidos, para você não perder tempo descobrindo

1. **`src/tesouro/fetch_anbima.py` está quebrado.** A URL que ele usa
   (`anbima.com.br/informacoes/merc-sec/arqs/ms{DDMMAA}.txt`) devolve 404 em
   toda data testada, inclusive em datas antigas de controle. A home da ANBIMA
   responde, então o caminho do arquivo mudou. Nenhuma taxa foi gravada em
   `data/raw/anbima/`.
2. **O prazo de 12:00 do e-mail de resultado está calibrado contra a fonte
   errada.** O resultado sai no site do Tesouro por volta de 11:45, mas a API
   que o programa lê publica mais tarde e em hora variável — em 05/11/2026, às
   12:00:08, ela ainda não tinha o dia. O laço acertou em não mandar, mas o
   prazo precisa esticar. Decisão da Aline, não sua.

### Como eu trabalho aqui

- **Nada de número plausível.** O defeito que este projeto mais teme é um
  número ou uma frase que parece razoável e não é o que diz ser. Se você não
  mediu, diga que não mediu.
- **Teste tem dente.** Antes de dizer que um teste protege algo, quebre a linha
  de produção que ele protege e confirme que ele fica vermelho. Depois restaure
  e confira os bytes.
- Fale **português do Brasil**, usando "você".
