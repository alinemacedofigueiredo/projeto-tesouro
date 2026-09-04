# As 60 âncoras do RMD de julho — resultado das três provas

Data: 04/09/2026. Branch `ancoras-do-rmd-de-julho`.

As três provas da Task 12 rodaram. **As três passam**, e duas delas acharam
coisa que o acompanhamento tarefa a tarefa não tinha pegado.

---

## Prova 1 — a suíte inteira

```
843 testes: 836 passam, 7 falham
```

Eram 6 esperadas (as da revisão do PAF, fora do escopo deste plano). **A sétima
foi o achado da prova.**

`test_curva.py::test_inflacao_implicita_bate_o_valor_medido` não estava em
tarefa nenhuma. Quando a contagem subiu de 58 para 60, eu atualizei o inventário
do plano e **não revisei se as tarefas cobriam o inventário novo** — as Tasks 3
a 11 já estavam escritas, e nenhuma cobria `test_curva.py`.

O mecanismo importa mais que o caso: a falha não foi de execução, foi de não
reconferir uma lista depois de mudá-la. Quem pegou foi a prova, contando.

E aquela âncora trazia um problema próprio, que aparece na Prova 2.

---

## Prova 2 — contra o RMD de junho, tem de ficar vermelha

É a única que detecta espelho. Se as âncoras novas passassem nos dois meses,
elas não travariam mês nenhum.

Feita **sem tocar em data de arquivo** — trocando o leitor, não o `mtime`, que
dentro do OneDrive não é confiável. Reprocessa junho, roda os quinze arquivos da
entrega, reprocessa julho de volta.

```
53 vermelhos de 246 testes coletados
```

Separando as 60 âncoras:

| | quantas | leitura |
|---|---|---|
| caíram contra junho | 50 | as de valor. Travam o mês, como devem |
| passaram | 10 | as que viraram relação. Valem em qualquer mês, como devem |
| passou e não devia | 1 | a âncora da Selic implícita |

**As dez que passam têm nome e motivo**, e nenhuma é espelho: a soma fechar em
100 (duas), a série mensal sem buraco (três), os dois anos das pontas derivados
do mês-base, a forma da tabela de detentores, a igualdade papel a papel entre as
abas 2.2 e 3.4, o custo de emissão começando em dez/2010, e a identidade entre o
`dv_base` do decay e o painel.

**A exceção é o achado desta prova.** `test_selic_implicita_bate_o_valor_medido`
passou contra junho. Não é espelho — o valor sai da curva, não de uma rodada do
teste. Mas a tolerância é de 0,1 pp e a Selic implícita andou **0,075 pp** de
junho para julho: ela passa com qualquer um dos dois meses. **Não trava mês
nenhum.**

Chamar aquilo de âncora seria mentir sobre o que ela protege. O que ela pega é
curva lida na escala errada ou vértice trocado — outra coisa, e útil. Isso
passou a estar escrito no próprio teste.

**Apertar a tolerância até distinguir o mês foi considerado e descartado:** o
limiar teria de sair de 0,1 pp para menos de 0,075, escolhido para caber entre
dois meses que por acaso andaram pouco. Seria número ajustado contra o próprio
dado — o vício que esta entrega inteira remove.

A da inflação implícita, ao lado, trava o mês: lá o movimento foi de 0,49 pp,
cinco vezes a tolerância, e ela cai contra junho.

---

## Prova 3 — o retrato

`retrato-2026-09-04-pos-ancoras.pdf` contra
`retrato-2026-09-01-rolagem-corrigida.pdf`. 75 páginas cada, comparadas bloco a
bloco.

```
71 dos 76 blocos idênticos
 5 com diferença
```

**A diferença esperada apareceu:** a nota do gráfico de variação do DV passou de
"197 dos 197 meses" para "198 dos 198". É a única coisa que esta entrega mudou
em código de produção que produz texto na página.

**As outras quatro têm causa medida, e não é a entrega.** O calendário publicado
pelo Tesouro mudou entre 01/09 e 04/09: a projeção partia de **32 dias de
leilão** até 31/12 e passou a partir de **30**. Isso cascateia para a tabela do
PAF, a simulação e a agenda.

Duas hipóteses foram descartadas medindo, antes de aceitar essa:

- **leilões novos?** Não. A última liquidação segue 26/08 nos dois retratos.
- **a entrega mexeu em algo que produz número?** Não. A branch tocou quatro
  arquivos em `src/`, e três são só comentário ou docstring. O único que gera
  texto na página é a nota.

---

## Dois erros meus na própria verificação, que valem registro

**Contei 53 vermelhos e reportei antes de saber quais eram.** O número sozinho
não distingue "as âncoras travam o mês" de "algumas viraram espelho" — só a
lista distingue. Refiz.

**E procurei "197 dos 197" no PDF inteiro com os espaços removidos**, o que
colou fragmentos de lugares diferentes e me fez achar que a frase antiga tinha
sobrevivido. Era a capa do próprio retrato, que cita as duas formas ao explicar
a mudança. Conferido por bloco, cada uma está onde deve.

Os dois são a mesma espécie: medir com um instrumento que eu não tinha
calibrado, e ler o resultado como se fosse o fenômeno.
