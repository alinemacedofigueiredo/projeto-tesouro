# Projeto Tesouro — camada de dados

Baixa os dados públicos do Tesouro Nacional e os converte em CSVs limpos
para análise da Dívida Pública Federal.

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

Os CSVs saem em `data/processed/`. O dicionário de cada um está em
`docs/dicionario-de-dados.md`.

## Como o projeto está organizado

O fluxo é sempre `fetch → data/raw/ → parse → data/processed/`. Os
coletores (`fetch_*`) baixam arquivos; os parsers (`parse_*`) leem apenas
de `data/raw/` e nunca acessam a rede. É isso que permite rodar o projeto
em ambiente fechado: basta colocar os arquivos na pasta manualmente.

Arquivos em `data/raw/` nunca são modificados. Se o Tesouro republicar um
mês, entra um arquivo novo e o antigo permanece.

## Documentação

- `docs/fontes-de-dados.md` — de onde vem cada dado
- `docs/dicionario-de-dados.md` — o que há em cada CSV
- `docs/como-baixar.md` — download manual, para ambiente sem rede
- `docs/superpowers/specs/` — decisões de design e por quê

## Testes

    python -m pytest tests/ -v

(`tests/conftest.py` já ajusta o `sys.path` para achar `src/`, então os
testes não precisam de `PYTHONPATH`.)

Os testes em `tests/test_coerencia.py` cruzam tabelas independentes entre
si. São os mais importantes: um parser errado raramente quebra, ele
produz números plausíveis e falsos.
