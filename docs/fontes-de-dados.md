# Fontes de dados

## Fluxo

```mermaid
flowchart LR
    RMD["Página do RMD<br/>tesourotransparente.gov.br"] -->|fetch_rmd| RAW1[("data/raw/rmd/<br/>Anexo RMD*.xlsx")]
    CKAN["API CKAN<br/>dataset ds013"] -->|fetch_leiloes| RAW2[("data/raw/leiloes/<br/>historico-leiloes-todos.xls")]
    ANBIMA["anbima.com.br/feriados"] -->|manual| RAW3[("data/raw/anbima/<br/>feriados_nacionais.xls")]
    BLOOMBERG["Terminal Bloomberg<br/>(ou exportação BDH)"] -->|fetch_bloomberg| RAW4[("data/raw/bloomberg/<br/>bbg_taxas_*.csv, bbg_vna_*.csv")]
    RAW1 -->|parse_rmd| CSV1[("16 CSVs canônicos<br/>data/processed/*.csv")]
    RAW2 -->|parse_leiloes| CSV2[("leiloes.csv")]
    RAW3 -->|calendario| CSV1
    RAW4 -->|parse_bloomberg| CSV3[("taxa_por_papel.csv<br/>vna.csv")]
    CSV1 -->|dv.py| CSV4[("dv_por_papel.csv<br/>decay_por_papel.csv<br/>resultado_mensal.csv")]
    CSV3 -->|dv.py| CSV4

    subgraph coleta ["coleta — precisa de rede (ou terminal Bloomberg)"]
        RMD
        CKAN
        BLOOMBERG
    end
    subgraph interpretacao ["interpretação — nunca acessa a rede"]
        RAW1
        RAW2
        RAW3
        RAW4
        CSV1
        CSV2
        CSV3
        CSV4
    end
```

A fronteira entre os dois retângulos é a decisão de arquitetura central do
projeto: à esquerda dela há rede ou terminal (`fetch_rmd.py`,
`fetch_leiloes.py`, `fetch_bloomberg.py`); à direita não (`parse_rmd/*.py`,
`parse_leiloes.py`, `parse_bloomberg.py`, `dv.py`). Em ambiente fechado,
alguém preenche `data/raw/` na mão (`docs/como-baixar.md`) e tudo à
direita funciona sem alteração de código — é o `--sem-coleta` do
`tesouro.pipeline`. O calendário da Anbima não tem coletor (`fetch_*`)
próprio — é baixado uma vez à mão, cobre 2001 a 2099, e raramente precisa
ser atualizado.

## RMD — Relatório Mensal da Dívida

Página: `tesourotransparente.gov.br/publicacoes/relatorio-mensal-da-divida-rmd/{ano}/{mes}`

O anexo com as tabelas fica num servidor de arquivos com identificador
numérico que muda a cada publicação — não há URL previsível, por isso o
coletor abre a página do mês e extrai o link de lá (`fetch_rmd.link_do_anexo`).
Se o anexo vier num `.zip`, o coletor extrai o `.xlsx` de dentro.

Quase todas as abas trazem a série histórica completa, então basta o RMD
mais recente. A exceção é a aba 3.4, que é um retrato substituído a cada
mês — ver a nota sobre `cronograma_vencimentos` no dicionário de dados.

## Leilões

API: `tesourotransparente.gov.br/ckan/api/3/action/package_show?id=ds013`

O arquivo único (`historico-leiloes-todos.xls`, ~5 MB) traz uma aba por
ano desde 2000, todas com o mesmo layout. É `.xls` legado, que exige a
biblioteca `xlrd`. Se ela não estiver disponível no ambiente de destino,
o contorno está em `docs/como-baixar.md`.

## Bloomberg — taxa e VNA para o DV01

Fonte da taxa (`YLD_YTM_MID`, fonte `ANDE`) e do VNA (`IDX_RATIO` para IPCA,
`ACCUMULATED_SELIC` para Selic) usados no cálculo de PU e DV01. Ao contrário
do RMD e dos leilões, a coleta fala com um **terminal Bloomberg** instalado
na máquina (`fetch_bloomberg.py`), não com uma API de internet aberta —
por isso o ambiente sem terminal (o caso do banco, por exemplo) usa a
exportação manual por `BDH`, descrita em `docs/como-baixar.md`.

A coleta é **incremental**: cada rodada grava só os meses que ainda faltam,
em arquivos novos — nunca sobrescreve os já gravados. É a mesma invariante
de `data/raw/` do resto do projeto, com uma consequência própria se um dos
arquivos for apagado à mão; ver `docs/convencoes-dv.md`, seção "Recuperando
um arquivo apagado à mão em `data/raw/bloomberg/`".

**Contrato de dados completo, com todas as armadilhas medidas** (`SETTLE_DT`
não serve para taxa histórica, `BZAC2000 Index` não é Selic, a série de
preço da LFT é inutilizável, o nome do arquivo precisa ordenar
cronologicamente) em `docs/convencoes-dv.md`, seção "Fontes na Bloomberg".

## Anbima — calendário de dias úteis

Fonte do calendário de feriados usado em toda conta de dias úteis do
projeto (não só do RMD): `data/raw/anbima/feriados_nacionais.xls`, baixado
uma única vez de `anbima.com.br/feriados/arqs/feriados_nacionais.xls`.
Cobre 2001 a 2099; não tem coletor automático (`fetch_*`) porque não
precisa — a Anbima não republica feriados de anos já fechados. Detalhe em
`docs/convencoes-dv.md`, seção "Calendário de dias úteis".

## Limite de cobertura: bandas do PAF

A aba 5.7 do RMD (origem de `paf_metas`) traz as bandas mínimo/máximo do
Programa Anual de Financiamento **apenas de 2003 a 2022**. O último bloco
da aba cobre 2021–2022 e o Tesouro parou de estendê-la — confirmado no
anexo de junho/2026. Quem for comparar a dívida contra a banda do PAF em
anos recentes (2023 em diante) vai precisar extrair as bandas dos PDFs do
PAF publicados a cada ano; essa extração **não está nesta camada de
dados**.

A aba registra revisões de meta nos anos de **2008, 2015, 2016 e 2021**
(coluna `versao` = `revisado` em `paf_metas.csv`), mas não traz a data em
que cada revisão foi publicada — só o ano e os novos limites. Quem
precisar da data de vigência de uma revisão terá de buscá-la em outra
fonte.

## De onde vem cada CSV

| CSV | Aba do RMD |
|---|---|
| `funding_por_canal` | 1.1 |
| `funding_por_indexador` | 1.2 |
| `estoque_dpf` | 2.1 |
| `estoque_titulos_vencimento` | 2.2 |
| `composicao_dpf` | 2.4 |
| `detentores` | 2.7 |
| `detentores_por_titulo` | 2.8 |
| `vencimentos_faixa` | 3.1 |
| `vencer_12m_indexador` | 3.3 |
| `cronograma_vencimentos` | 3.4 |
| `prazo_medio_por_titulo` | 3.7 |
| `prazo_medio_por_indexador` | 3.8 |
| `prazo_medio_emissoes` | 3.9 |
| `custo_medio` | 4.1, 4.2 e 4.3 |
| `paf_metas` | 5.7 |
| `reserva_liquidez` | 6.1 |
| `leiloes` | (dataset ds013) |

Os cinco CSVs abaixo não vêm de aba nenhuma do RMD — vêm da Bloomberg ou são
calculados a partir das tabelas acima:

| CSV | Origem |
|---|---|
| `taxa_por_papel` | Bloomberg, `YLD_YTM_MID` (fonte `ANDE`) |
| `vna` | Bloomberg, `IDX_RATIO` (IPCA) / `ACCUMULATED_SELIC` (Selic) |
| `dv_por_papel` | Calculado (`dv.painel()`) a partir de `estoque_titulos_vencimento`, `taxa_por_papel` e `vna`, com o calendário da Anbima |
| `decay_por_papel` | Calculado (`dv.decay()`) a partir de `dv_por_papel` |
| `resultado_mensal` | Calculado (`dv.resultado_mensal()`) a partir de `dv_por_papel` |

Detalhes de cada coluna, tipo e armadilha conhecida estão em
`docs/dicionario-de-dados.md`; as fórmulas de PU e DV01 e as convenções de
sinal estão em `docs/convencoes-dv.md`.
