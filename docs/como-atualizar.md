# Como atualizar o Projeto Tesouro

Este é o documento de operação: o que rodar quando chega dado novo, como saber
se deu certo, e o que fazer quando não dá.

Escrito em 09/09/2026.

## O atalho, para quem nao quer decorar comando

Na area de trabalho tem **Projeto Tesouro - atualizar**. Duplo clique, e ele
abre o menu.

A janela **fica aberta no fim**, de proposito: sem isso ela fecharia junto com o
programa e levaria o resultado embora -- inclusive a `ADVERTENCIA` de RMD
atrasado, que e a ultima linha impressa.

O atalho aponta para `atualizar.cmd`, que mora no projeto e vai no git. O icone
na area de trabalho e so um apontador, e por isso nao esta versionado: se o
projeto mudar de pasta, recria-se o icone e o `.cmd` continua o mesmo.

## O comando

```
cd "C:\Users\lineb\Projetos\Projeto Tesouro"
$env:PYTHONPATH="src"; python -m tesouro.pipeline
```

Sem mais nada, ele **pergunta o que você quer atualizar**:

```
O que voce quer atualizar?

  1. rmd      o RMD novo saiu (mensal) -- baixa o anexo e regrava tudo
  2. leiloes  houve leilao -- baixa os resultados e regrava PAF, emissoes e agenda
  3. paf      voce editou referencia/paf_bandas.csv -- confere e redesenha as bandas
  4. tudo     atualiza as tres fontes e regrava todas as paginas

numero (ou o nome do modo):
```

Responda o número ou o nome. Quem preferir digitar direto, sem menu:

```
$env:PYTHONPATH="src"; python -m tesouro.pipeline --modo leiloes
```

O menu só aparece quando o comando roda **sem argumento nenhum, num terminal de
verdade**. Num agendador o padrão continua sendo `tudo`, como sempre foi — um
programa que espera resposta onde não há ninguém trava calado.

## A oferta do dia, antes de sair resultado

**Desde 24/09/2026 o modo `leiloes` busca o edital sozinho.** Rodar de manhã,
depois das 10h30, já traz as pernas ofertadas — elas aparecem **hachuradas**,
que é a marca de "o resultado ainda não saiu". Quando o resultado sai, rode de
novo: o aceito substitui o teto sozinho, pela ordem dos estágios
(`ofertado` < `aceito` < `planilha`), e a barra fica sólida.

Antes disso a oferta só entrava pela planilha digitada
(`python -m tesouro.leilao_do_dia modelo`), um caminho manual que o pipeline
nunca chamava. O custo disso foi medido: em 20/08/2026 o leilão tinha seis
pernas, só as três NTN-F foram digitadas, e as três LTN — 18 milhões de títulos
contra 3,65 milhões — ficaram fora do gráfico sem que nada avisasse.

**A planilha digitada continua valendo, e continua mandando.** A taxa que você
digita vence a emprestada. O edital automático não tem taxa publicada, então o
DV usa a do leilão anterior daquele papel e marca a linha como `taxa_suposta` —
o erro medido dessa suposição é de 11 bp na mediana. Se a taxa importa no dia,
digite; se não, a barra aparece de qualquer jeito, que é melhor que não aparecer.

## Qual usar, e quanto leva

| modo | quando | o que baixa | o que regrava | tempo medido |
|---|---|---|---|---|
| `leiloes` | terça e quinta — de manhã pela oferta, de tarde pelo resultado | edital e resultados (API) | paf, emissões, agenda | **170 s** |
| `rmd` | uma vez por mês, quando sai o RMD | o anexo do mês | todas as páginas | ~171 s |
| `paf` | quando o Tesouro revisa a banda | nada | dashboard, paf e agenda | **97 s** |
| `tudo` | quando você não tem certeza | as três fontes | todas as páginas | ~191 s |

O de leilões foi medido em 17/09/2026 com coleta de verdade, e o de `paf` em
24/09/2026 (duas rodadas: 96,6 s e 98,0 s). Os outros dois são de 09/09 com
`--sem-coleta`, e subiram um pouco desde então — a página do histórico entrou no
meio.

**A agenda passou a sair no modo `paf` em 24/09/2026.** Ela e a página do PAF
leem o mesmo calendário publicado: uma projeta o fechamento do ano, a outra
mostra dia a dia o que entrou nessa conta. Regravar uma sem a outra deixava as
duas discordando na tela sem nada avisar — e a agenda é justamente onde se
confere a projeção. Foi o que acrescentou os ~28 s.

**Mas o modo `leilões` te dá um número muito antes dos 173 s:** ver a fase
rápida, logo abaixo.

## A fase rápida do modo leilões

Assim que os resultados chegam, o modo `leilões` grava a
**`emissoes-rapida.html`** — a janela de 20 leilões apenas — e avisa no log:

```
=== PAGINA RAPIDA PRONTA: ...\data\processed\emissoes-rapida.html
=== e a janela de 20 leiloes. O e-mail do dia ja pode sair;
    as demais paginas continuam sendo geradas.
```

**Isso sai em ~30 s**, contra os 170 s do modo inteiro. A partir daí o programa
segue sozinho: grava a `emissoes.html` com as cinco janelas, depois as duas
variantes, a página do PAF e a agenda.

**Arquivo próprio, desde 24/09/2026.** Até então a fase rápida escrevia na
própria `emissoes.html` e a fase 2 a substituía ~140 s depois — a versão de
1 MB durava dois minutos. Como ela vira **anexo de e-mail**, precisa continuar
existindo: 1,06 MB passa em qualquer caixa, os 7,25 MB da completa não.

**São dois arquivos, e os dois ficam.** A `emissoes-rapida.html` é a de uma
janela, leve, para anexar; a `emissoes.html` é a completa, de cinco janelas.
As duas dizem no cabeçalho de quando são.

**Antes de mandar o e-mail, confira o cabeçalho da página.** Se ele não mudou,
a atualização não atualizou e você estaria anunciando o leilão de ontem.

O projeto **não manda e-mail**. Há uma receita comentada em `pipeline.py`, junto
da fase rápida, com as três coisas que precisam ser decididas antes de ligar
isso: qual servidor SMTP, de quem para quem, e se a página vai anexada (1,05 MB)
ou como link.

**A economia de tempo é modesta, e isso está dito de propósito.** O que os modos
entregam de fato é outra coisa: não tocar na Bloomberg quando ela não é
necessária, não precisar saber qual RMD baixar para acrescentar um leilão, e não
regravar página que aquela fonte não pode ter mudado.

## As três regras que os modos seguem por desenho

**O modo `leiloes` não toca na Bloomberg.** O terminal só existe na máquina da
mesa e fica desligado quase sempre. Tentar a Bloomberg para acrescentar um
leilão ou demora ou falha, e o leilão não depende dela.

**O modo `leiloes` não regrava o dashboard.** Aquelas duas páginas saem do RMD —
estoque, prazo, custo, funding, detentores — e nenhuma delas muda por causa de
um leilão.

**O modo `paf` não baixa nada, e confere antes de desenhar.** A banda entra a
mão: você lê o informe do Tesouro e edita `referencia/paf_bandas.csv`. O modo
valida o arquivo primeiro, e **se ele não passar, nada é redesenhado** e o
comando sai com erro. Banda quebrada não vira gráfico com banda errada.

## Passo a passo de cada situação

### Ao escolher `1`, ele diz qual RMD você tem

Desde 02/10/2026, antes de perguntar qualquer coisa:

```
O RMD que o projeto tem e de julho/2026.

Se quiser um mais novo:
  1. abra   https://www.tesourotransparente.gov.br/publicacoes/relatorio-mensal-da-divida-rmd
  2. salve o anexo em   ...\dataawmd
  3. volte aqui e de Enter em branco nas duas perguntas
```

**Por que isso faltava:** o projeto usa o RMD mais recente que encontra em disco
e ficava calado sobre o que não está lá. Em 02/10/2026 ela descobriu por acaso
que estava com o de julho, e a página do PAF projetava o ano inteiro a partir de
uma base de 31/07.

**A URL e a pasta saem do código**, e não escritas na mensagem — caminho
repetido a mão é caminho que fica errado no dia em que o outro muda, e essa
mensagem existe justamente para colar no navegador e no Explorer.

**No menu, e não no fim da rodada.** A primeira versão avisava depois do
`concluido.`, e ela recusou: no fim a informação chega depois de a decisão ter
sido tomada.

### Saiu o RMD do mês

1. rode o comando e escolha `1` (rmd)
2. ele pergunta **qual RMD puxar** — responda o ano e o mês (ex.: `2026`, `8`)
   - Enter em branco nos dois segue com o anexo que já está em `data/raw/rmd/`
3. espere o `concluido.`
4. abra `data/processed/dashboard.html` e confira o cabeçalho: ele diz qual RMD
   está sendo usado

Se o download falhar, salve o anexo a mão em `data/raw/rmd/` pelo navegador e
rode de novo com Enter em branco nas duas perguntas. **Isso sempre funciona, e
não depende de arrumar certificado nenhum.**

### Por que o download falha, e o que muda no banco

Medido em 28/09/2026:

```
site do RMD   AC SERPRO AR46 OV TLS CA 2025    falha
API de leilão GeoTrust TLS RSA CA G10          funciona
```

A API funciona porque a GeoTrust já vem em qualquer máquina. O site do RMD falha
porque a cadeia do SERPRO chega **incompleta** — o navegador contorna buscando o
elo que falta, e o Python não faz isso.

**A verificação de certificado nunca é desligada.** O conserto é apontar o Python
para um pacote de certificados que tenha a cadeia:

```
$env:SSL_CERT_FILE = "C:\caminho\para\ca-bundle.crt"
```

**Isso é propriedade da máquina, e não do projeto** — não há pacote de
certificados dentro do repositório, de propósito. No banco a variável aponta para
o pacote que o TI de lá fornecer, e nada no código muda.

Duas razões para não embutir o pacote aqui, as duas medidas:

- se o banco **inspeciona o tráfego**, o certificado que o Python vê é o do
  banco, e um pacote com o SERPRO dentro não serve para nada;
- em Linux o `SSL_CERT_FILE` **substitui** o padrão em vez de somar (no Windows
  soma — testado). Um pacote só com o SERPRO derrubaria o resto do HTTPS.

Quando o download falha, a mensagem diz **quem assinou** o certificado. Se for o
órgão público, falta o elo da cadeia dele; se for a sua instituição, o tráfego
está sendo inspecionado e o pacote a apontar é o dela.

### Houve leilão

1. rode o comando e escolha `2` (leiloes)
2. em ~30 s aparece o aviso da **página rápida** — a `emissoes-rapida.html`
   com a janela de 20 leilões já está gravada, e o e-mail do dia pode sair
3. **confira o cabeçalho antes de mandar**: ele diz qual foi o último leilão
   puxado e quando liquidou
4. deixe o programa seguir; ele regrava tudo sozinho e termina com `concluido.`

As linhas que entraram pela API e ainda não estão na planilha do Tesouro
aparecem **com hachura** nos gráficos de emissão. Elas somem sozinhas quando a
planilha alcançar.

### O Tesouro revisou a banda do PAF

1. leia o informe e edite `referencia/paf_bandas.csv` a mão
   - a linha `original` fica como está; você acrescenta ou edita a `revisado`
2. rode o comando e escolha `3` (paf)
3. se o validador reclamar, **corrija o CSV** — ele diz a linha
4. confira em `paf.html` que a coluna da banda passou a dizer `revisada`, com a
   original ao lado

### Não sei o que mudou

Escolha `4` (tudo). São três minutos.

## Como saber se deu certo

**A primeira linha** diz qual modo está rodando:

```
modo: leiloes -- houve leilao -- baixa os resultados e regrava PAF, emissoes e agenda
```

**A última linha** tem de ser `concluido.` — sozinha, sem nada depois.

**Se aparecer `ATENCAO:`**, alguma perna falhou e as páginas foram regravadas
com o dado que havia. O comando sai com código diferente de zero e repete a
lista de falhas no fim, perto do `concluido`. Isso é de propósito: falha que
some no meio de um log de trezentas linhas é falha que ninguém vê.

**E toda página diz de onde veio o que ela mostra**, no alto:

```
RMD de julho/2026 (base 31/07/2026) · último leilão 08/09/2026, liquidado em 09/09/2026
```

Se esse cabeçalho não mudou depois de uma atualização, a atualização não
atualizou. Confira isso antes de acreditar no `concluido.`

## Quando dá errado

**"coleta da Bloomberg FALHOU"** — o terminal está desligado, ou o `blpapi` não
está instalado nesta máquina. As páginas saem com o dado de Bloomberg que já
estava em disco. Só atrapalha o DV01 e o decay; o resto não usa.

**"a agenda nao foi regravada"** — a API do Tesouro não respondeu. As outras
páginas estão em dia e a agenda ficou com o calendário da rodada anterior. A
agenda **é** o calendário publicado: sem ele, não sobra página.

**"o resultado do dia NAO foi buscado"** — a API não respondeu. As páginas foram
regravadas sem o leilão de hoje. Rode de novo mais tarde.

**O download da planilha histórica de leilões trava no certificado do SERPRO.**
Isso é conhecido e **não impede nada**: o leilão novo entra pela API, que
responde nesta rede. A planilha só serve para o histórico antigo, que já está em
disco.

**Nunca desligue a verificação de certificado** para contornar qualquer um
desses. Se for preciso, aponte `SSL_CERT_FILE` para o pacote de certificados da
instituição.

## O que este projeto NÃO faz sozinho

- **A banda do PAF** entra a mão. O informe do Tesouro usa uma fonte com
  codificação própria e a tabela não sai por código.
- **A Bloomberg** precisa do terminal aberto na máquina da mesa.
- **O anexo do RMD** pode precisar ser baixado pelo navegador, quando o
  certificado do site trava o download automático.
- **Nada aqui decide por você** se um número está certo. As páginas dizem de
  onde veio cada coisa justamente para você julgar.
