# Projeto Tesouro — camada de dados, DV01 e decay

Baixa os dados públicos do Tesouro Nacional (e, para o DV01, também da
Bloomberg) e os converte em CSVs limpos para análise da Dívida Pública
Federal: estoque, funding, custo médio e prazo médio a partir do RMD e dos
leilões; e, a partir da entrega 2, o preço unitário (PU) e o resultado
mensal de LTN, NTN-F, NTN-B e LFT, além do DV01 e do decay de LTN, NTN-F e
NTN-B (a LFT não tem duration de juros por construção — ver
`docs/convencoes-dv.md`).

## Uso rápido

O projeto não instala pacote (decisão deliberada — ver
`docs/superpowers/specs/2026-08-14-camada-de-dados-design.md`, §3): toda
invocação precisa apontar `PYTHONPATH` para `src`.

    pip install -r requirements.txt

PowerShell:

    $env:PYTHONPATH="src"; python -m tesouro.pipeline --ano 2026 --mes 6

bash:

    PYTHONPATH=src python -m tesouro.pipeline --ano 2026 --mes 6

Sem acesso à internet (ver `docs/como-baixar.md`):

    $env:PYTHONPATH="src"; python -m tesouro.pipeline --sem-coleta   # PowerShell
    PYTHONPATH=src python -m tesouro.pipeline --sem-coleta           # bash

O pipeline grava vinte e dois CSVs em `data/processed/` — dezessete da
camada de dados (RMD e leilões) e cinco do DV01/decay (taxa e VNA da
Bloomberg, painel de DV por papel, decay e resultado mensal). O dicionário
de cada um está em `docs/dicionario-de-dados.md`; as convenções de sinal e
as fórmulas de cálculo estão em `docs/convencoes-dv.md`.

### O dashboard

Os vinte e um gráficos da dívida num arquivo HTML autocontido, que abre com
duplo clique e continua funcionando copiado para outra máquina ou mandado
por e-mail.

PowerShell:

    $env:PYTHONPATH="src"; python -m tesouro.graficos

bash:

    PYTHONPATH=src python -m tesouro.graficos

Grava `data/processed/dashboard.html` (7,65 MB) com quatro janelas — 12 meses,
3 anos, 5 anos e série completa — e os botões no cabeçalho que alternam entre
elas. O limiar da spec é 10 MB por página, e um teste o guarda: uma quinta
janela não cabe. Para um recorte específico, com os botões suprimidos porque só
existe uma janela:

    $env:PYTHONPATH="src"; python -m tesouro.graficos --de 2021-01-01 --ate 2026-06-30
    PYTHONPATH=src python -m tesouro.graficos --de 2021-01-01 --ate 2026-06-30

O `pipeline` já gera o dashboard no fim, depois de reescrever os CSVs; o
comando acima serve para regerar sem rodar o pipeline inteiro.

### A suíte precisa que o pipeline tenha rodado

**155 dos 451 testes leem CSVs de `data/processed/`**, que é gerado e fica fora do
git. Num clone novo, `pytest` falha nesses 155 até você rodar o pipeline uma vez:

    $env:PYTHONPATH="src"; python -m pytest -q          # 155 falhas num clone novo
    $env:PYTHONPATH="src"; python -m tesouro.pipeline --sem-coleta
    $env:PYTHONPATH="src"; python -m pytest -q          # 450 passed, 1 skipped

Não é defeito: são as âncoras de valor, que existem justamente para conferir número
real contra as páginas do RMD — um teste que não lê o dado não pegaria erro de
parser. O pipeline, por sua vez, precisa do anexo do RMD em `data/raw/rmd/`
(ver `docs/como-baixar.md`).

O teste pulado é o do PU contra o `PX_DIRTY_MID` da Bloomberg, que aguarda
autorização para puxar os arquivos de preço.

### Cálculo pontual: quanto do DV01 desaparece até uma data escolhida

Além do pipeline, há um comando específico para uma pergunta do dia a dia —
"da posição de hoje, quanto do meu DV01 some até tal data, e quanto disso é
vencimento em vez de queda de risco de mercado" — sem precisar regravar
nenhum CSV:

PowerShell:

    $env:PYTHONPATH="src"; python -m tesouro.dv --alvo 31/12/2027

bash:

    PYTHONPATH=src python -m tesouro.dv --alvo 31/12/2027

O comando usa o painel já gravado em `data/processed/dv_por_papel.csv` (rode
o pipeline pelo menos uma vez antes) e imprime a decomposição — DV na
data-base, o que vence no caminho, o decay dos sobreviventes, DV na
data-alvo — junto com a cobertura do DV01 sobre o estoque naquela data
específica. `--base DD/MM/AAAA` escolhe outra data de partida (o padrão é o
último fim de mês do painel); `--gravar` regrava os três CSVs de DV01/decay/
resultado em vez de calcular o pontual. Detalhe completo do que cada número
significa, e por que a cobertura do DV01 muda de mês a mês, em
`docs/convencoes-dv.md`.

## Como o projeto está organizado

O fluxo é sempre `fetch → data/raw/ → parse → data/processed/`. Os
coletores (`fetch_*`) baixam arquivos; os parsers (`parse_*`) leem apenas
de `data/raw/` e nunca acessam a rede. É isso que permite rodar o projeto
em ambiente fechado: basta colocar os arquivos na pasta manualmente. O
mesmo desenho vale para a Bloomberg: `fetch_bloomberg.py` fala com o
terminal (se ele existir na máquina); `parse_bloomberg.py` só lê
`data/raw/bloomberg/`. Num ambiente de banco sem `blpapi`, a exportação sai
por `BDH` para Excel e cai na mesma pasta, sem mudar nenhum código — ver
`docs/como-baixar.md`.

Arquivos em `data/raw/` nunca são modificados. Se o Tesouro republicar um
mês, entra um arquivo novo e o antigo permanece; o mesmo vale para a
Bloomberg, cuja coleta é incremental (nunca sobrescreve, só acrescenta
arquivos novos — ver `docs/convencoes-dv.md`, seção "Recuperando um
arquivo apagado à mão").

## Documentação

- `docs/fontes-de-dados.md` — de onde vem cada dado
- `docs/dicionario-de-dados.md` — o que há em cada CSV
- `docs/como-baixar.md` — download manual, para ambiente sem rede
- `docs/convencoes-dv.md` — convenções de sinal, fórmulas de PU e DV01, e as
  armadilhas medidas na Bloomberg e no RMD — confira aqui antes de qualquer
  conta que envolva sinal, taxa ou cobertura do DV01
- `docs/superpowers/specs/` — decisões de design e por quê

## Testes

    python -m pytest tests/ -v

(`tests/conftest.py` já ensina o Python a achar o código em `src/` sozinho,
então os testes não precisam de `PYTHONPATH` — ao contrário dos outros
comandos deste documento.)

Os testes em `tests/test_coerencia.py` e `tests/test_coerencia_dv.py`
cruzam tabelas independentes entre si. São os mais importantes: um parser
errado raramente quebra, ele produz números plausíveis e falsos.

A suíte roda com **1 teste pulado** (`skipped`), não uma falha: o teste que
compara o PU calculado com o preço da Bloomberg
(`test_pu_reproduz_o_preco_da_bloomberg_com_deslocamento_de_d1`) exige o
arquivo `data/raw/bloomberg/bbg_precos_*.csv`, que depende de uma consulta à
Bloomberg ainda não autorizada. Ver `docs/convencoes-dv.md`, seção
"Verificação pendente de autorização", para o comando que gera esse
arquivo.
