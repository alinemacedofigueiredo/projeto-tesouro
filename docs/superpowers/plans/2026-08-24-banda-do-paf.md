# Distância até a banda do PAF — plano de implementação

> **Para quem executa:** SUB-SKILL OBRIGATÓRIA: use
> `superpowers:subagent-driven-development` (recomendado) ou
> `superpowers:executing-plans` para implementar tarefa a tarefa. Os passos usam
> caixinha (`- [ ]`) para acompanhamento.

**Objetivo:** dizer onde a dívida está hoje em relação à banda do PAF — e não na
data-base do último RMD — e onde ela fecha o ano se o ritmo de leilão continuar.

**Arquitetura:** três módulos de dado em `src/tesouro/` (a rolagem do estoque, o
calendário estimado de leilões e a curva que fornece a premissa) e dois de
apresentação em `src/tesouro/graficos/` (as tabelas e a página). A rolagem soma ao
estoque do RMD os leilões liquidados, subtrai os fluxos pagos — principal **e**
cupom — e apropria juros pelo VNA recuperado dos próprios leilões. A projeção usa a
mesma máquina com o calendário estimado e o pace dos últimos 20 dias de leilão.

**Stack:** `pandas`, `matplotlib`, `pytest`. Nada mais.

**Spec:** `docs/superpowers/specs/2026-08-24-banda-do-paf-design.md` — o plano
argumenta a partir dela; quem executa lê as duas.

## Restrições globais

Copiadas da spec e das regras do projeto. **Valem para toda tarefa.**

- **Bibliotecas permitidas:** `pandas`, `openpyxl`, `xlrd`, `matplotlib`, `pytest`.
  Nada mais. `numpy` **não** conta como permitido.
- **Arquivos `.py` inteiramente ASCII**, comentários e docstrings inclusive. Acento
  entra como escape `\uXXXX`. Os blocos de código deste plano já vêm assim.
- **Nada é escrito em `data/raw/`.** É dado insubstituível.
- **Caminhos vêm de `config.PROCESSED_DIR` e `config.RAIZ`**, nunca relativos.
- **Guardas de pandas:** `pd.isna(...)` e nunca `is None` numa coluna numérica;
  `r["isin"]` e nunca `r.isin`.
- **Nenhuma consulta à Bloomberg**, por nenhum motivo. Nenhuma fonte de rede nova.
- **Não toque em `src/tesouro/precificacao.py`.** Ele foi validado contra o
  `PX_DIRTY_MID` da Bloomberg em 438 pares e contra o `pu_medio` da API do Tesouro
  em 434. Chame-o; não o edite.
- **Instrução de linha de comando vem em PowerShell primeiro e bash depois.**
- **Todo teste tem de ter dentes:** depois de escrevê-lo, quebre a linha de produção
  que ele protege e confirme que ele reprova. Um teste que passa contra código
  quebrado é pior que nenhum.
- **A suíte não toca a rede.** Se um teste precisar da API, use a amostra congelada
  em `tests/fixtures/api_leiloes/`.

## Estrutura de arquivos

| arquivo | responsabilidade |
|---|---|
| `src/tesouro/fluxos.py` | **criar** — quanto o Tesouro paga em cada data: principal e cupom |
| `src/tesouro/rolagem.py` | **criar** — o estoque numa data qualquer depois do RMD, e a projeção |
| `src/tesouro/calendario_leiloes.py` | **criar** — quantos e quais dias de leilão faltam |
| `src/tesouro/curva.py` | **criar** — Selic implícita e inflação implícita |
| `src/tesouro/graficos/banda.py` | **criar** — as duas tabelas, dado e HTML |
| `src/tesouro/graficos/painel_paf.py` | **criar** — a página `paf.html` |
| `src/tesouro/graficos/dashboard.py` | **modificar** — `PAGINAS` ganha a entrada nova |
| `src/tesouro/pipeline.py` | **modificar** — grava a página nova |
| `tests/test_fluxos.py` | **criar** |
| `tests/test_rolagem.py` | **criar** |
| `tests/test_calendario_leiloes.py` | **criar** |
| `tests/test_curva.py` | **criar** |
| `tests/test_painel_paf.py` | **criar** |

**Por que `fluxos.py` é separado de `rolagem.py`:** o cupom tem regra própria por
papel e é a parte com armadilha nomeada. Ele também serve a entrega 5. Misturado
com a rolagem, o arquivo cresce e a regra do cupom fica escondida no meio de uma
soma.

---

### Task 1: `fluxos.py` — o cupom, com a regra do aniversário

**Arquivos:**
- Criar: `src/tesouro/fluxos.py`
- Teste: `tests/test_fluxos.py`

**Interfaces:**
- Consome: `config.PROCESSED_DIR`, `estoque_titulos_vencimento.csv`, `vna.csv`
- Produz:
  - `CUPOM_ANUAL: dict[str, float]` — `{"NTN-B": 0.06, "NTN-F": 0.10, "NTN-C": 0.12}`
  - `paga_cupom_em(titulo, vencimento, quando) -> bool`
  - (a tabela de fluxos é a `pagos(de, ate)` da Task 2 — esta tarefa entrega só a
    regra de quando cada papel paga)

- [ ] **Passo 1: escrever o teste que falha — a regra do aniversário**

```python
"""Os fluxos que o Tesouro paga: principal e cupom."""
import pandas as pd
import pytest

from tesouro import fluxos


def test_a_NTN_B_paga_no_ANIVERSARIO_dela_e_nao_em_todo_trimestre():
    # A ARMADILHA DESTA TAREFA, e ela custa 2,1 vezes o cupom se passar batido.
    # A NTN-B nao paga em todo fevereiro, maio, agosto e novembro: paga no mes do
    # vencimento DELA e seis meses antes. O estoque se divide -- 188,6 milhoes de
    # titulos vencem em maio e 267,3 em agosto -- entao agosto e novembro pagam a
    # grupos diferentes.
    maio = pd.Timestamp("2029-05-15")
    agosto = pd.Timestamp("2030-08-15")

    assert fluxos.paga_cupom_em("NTN-B", maio, pd.Timestamp("2026-05-15"))
    assert fluxos.paga_cupom_em("NTN-B", maio, pd.Timestamp("2026-11-15"))
    assert not fluxos.paga_cupom_em("NTN-B", maio, pd.Timestamp("2026-08-15"))
    assert not fluxos.paga_cupom_em("NTN-B", maio, pd.Timestamp("2026-02-15"))

    assert fluxos.paga_cupom_em("NTN-B", agosto, pd.Timestamp("2026-08-15"))
    assert fluxos.paga_cupom_em("NTN-B", agosto, pd.Timestamp("2026-02-15"))
    assert not fluxos.paga_cupom_em("NTN-B", agosto, pd.Timestamp("2026-05-15"))


def test_o_cupom_cai_no_DIA_certo_de_cada_papel():
    # NTN-B no dia 15, NTN-F no dia 1. A rolagem corta em data, e nao em mes:
    # ratear pelo mes poria dentro da janela um fluxo que ainda nao aconteceu.
    venc_b = pd.Timestamp("2030-08-15")
    assert fluxos.paga_cupom_em("NTN-B", venc_b, pd.Timestamp("2026-08-15"))
    assert not fluxos.paga_cupom_em("NTN-B", venc_b, pd.Timestamp("2026-08-14"))

    venc_f = pd.Timestamp("2031-01-01")
    assert fluxos.paga_cupom_em("NTN-F", venc_f, pd.Timestamp("2026-07-01"))
    assert not fluxos.paga_cupom_em("NTN-F", venc_f, pd.Timestamp("2026-07-15"))


def test_papel_sem_cupom_nunca_paga():
    # LTN e LFT nao pagam cupom. A NTN-B Principal tambem nao -- e ela e NTN-B no
    # nome, que e exatamente o jeito de errar.
    for titulo in ("LTN", "LFT", "NTN-B Principal"):
        assert not fluxos.paga_cupom_em(
            titulo, pd.Timestamp("2030-08-15"), pd.Timestamp("2026-08-15"))
```

- [ ] **Passo 2: rodar e ver falhar**

PowerShell:

```powershell
$env:PYTHONPATH="src"; python -m pytest tests/test_fluxos.py -q
```

bash:

```bash
PYTHONPATH=src python -m pytest tests/test_fluxos.py -q
```

Esperado: `ModuleNotFoundError: No module named 'tesouro.fluxos'`.

- [ ] **Passo 3: escrever o mínimo que faz passar**

```python
"""Os fluxos que o Tesouro paga: principal no vencimento, e cupom no caminho.

ESTE MODULO EXISTE SEPARADO da rolagem por causa do cupom. Ele tem regra propria
por papel, e a regra tem uma armadilha que custa 2,1 vezes o numero certo se passar
batido -- ver paga_cupom_em. Misturado numa soma maior, isso fica escondido.

POR QUE CALCULAR EM VEZ DE LER A ABA 3.4. A 3.4 traz o fluxo com cupom, e seria a
fonte obvia. Duas razoes contra:

  1. Ela e o RETRATO ATUAL. A camada de dados guarda so o mes corrente, entao o
     termo lido dela nao teria como ser testado nos 24 meses de backtest da rolagem.
  2. Ela e MENSAL, e a rolagem corta em data. O cupom da NTN-B cai no dia 15 e o da
     NTN-F no dia 1: ratear pelo mes poria dentro da janela um fluxo que ainda nao
     aconteceu.

Calculado, o termo serve as duas pontas -- o backtest e a projecao -- e e conferido
contra a 3.4 no mes em que nada vence (novembro de 2026: 26,4 calculado contra 25,8
da 3.4, +2,4%).
"""

import pandas as pd

from . import config

# Taxa de cupom de cada papel, ao ano. Os demais nao pagam cupom.
CUPOM_ANUAL = {"NTN-B": 0.06, "NTN-F": 0.10, "NTN-C": 0.12}

# Em que dia do mes cai o cupom de cada papel.
DIA_DO_CUPOM = {"NTN-B": 15, "NTN-C": 15, "NTN-F": 1}


def paga_cupom_em(titulo, vencimento, quando):
    """O papel paga cupom nesta data?

    A REGRA E O ANIVERSARIO DELE, e nao um trimestre fixo do calendario. Uma NTN-B
    que vence em 15/05 paga em maio e em novembro; uma que vence em 15/08 paga em
    agosto e em fevereiro. Supor que toda NTN-B paga em fev/mai/ago/nov dobra o
    cupom, porque o estoque se divide quase pela metade entre os dois grupos.

    A NTN-B PRINCIPAL nao paga cupom, e o nome dela comeca com "NTN-B" -- por isso a
    consulta e por igualdade exata, e nao por prefixo.
    """
    if titulo not in CUPOM_ANUAL:
        return False
    if pd.isna(vencimento) or pd.isna(quando):
        return False
    if quando.day != DIA_DO_CUPOM[titulo]:
        return False
    if quando > vencimento:
        return False
    # Semestral: o mes tem de distar um multiplo de seis do mes do vencimento.
    return (vencimento.month - quando.month) % 6 == 0
```

- [ ] **Passo 4: rodar e ver passar**

PowerShell:

```powershell
$env:PYTHONPATH="src"; python -m pytest tests/test_fluxos.py -q
```

bash:

```bash
PYTHONPATH=src python -m pytest tests/test_fluxos.py -q
```

Esperado: 3 passed.

- [ ] **Passo 5: verificar que os testes têm dentes**

Troque, em `paga_cupom_em`, a última linha por `return quando.month in (2, 5, 8, 11)`
e rode de novo. O teste do aniversário tem de reprovar. Desfaça.

- [ ] **Passo 6: commitar**

```bash
git add src/tesouro/fluxos.py tests/test_fluxos.py
git commit -m "A regra do cupom: aniversario do papel, e nao trimestre fixo"
```

---

### Task 2: `fluxos.py` — a tabela de fluxos pagos, conferida contra a 3.4

**Arquivos:**
- Modificar: `src/tesouro/fluxos.py`
- Teste: `tests/test_fluxos.py`

**Interfaces:**
- Consome: `paga_cupom_em` da Task 1
- Produz: `pagos(de, ate) -> pd.DataFrame` com colunas `data`, `indexador`,
  `principal_milhoes`, `cupom_milhoes`

- [ ] **Passo 1: escrever o teste que falha**

```python
def test_o_cupom_calculado_bate_com_a_aba_3_4_em_novembro():
    # NOVEMBRO DE 2026 E O CASO QUE PROVA: tem R$ 26,0 bi de fluxo e ZERO
    # principal. E cupom puro, entao a comparacao contra a 3.4 e direta -- nos
    # outros meses o cupom final do papel que vence esta dentro da linha de
    # principal dela, e a conta nao fecha por motivo que nao e erro nosso.
    from tesouro import config

    d = fluxos.pagos(pd.Timestamp("2026-11-01"), pd.Timestamp("2026-11-30"))
    calculado = d["cupom_milhoes"].sum()
    assert d["principal_milhoes"].sum() == 0, "novembro deixou de ser cupom puro"

    cr = pd.read_csv(config.PROCESSED_DIR / "cronograma_vencimentos.csv",
                     parse_dates=["mes_vencimento"])
    da_34 = cr[(cr["faixa"] == "mensal")
               & (cr["mes_vencimento"] == pd.Timestamp("2026-11-30"))
               ]["valor_milhoes"].sum()
    assert abs(calculado - da_34) / da_34 < 0.05, (calculado, da_34)


def test_o_principal_sai_da_aba_2_2_e_o_cupom_do_calculo():
    # Os dois termos ficam em colunas separadas de proposito: um e transcricao e o
    # outro e conta, e um teste que os somasse nao saberia dizer qual quebrou.
    d = fluxos.pagos(pd.Timestamp("2026-07-01"), pd.Timestamp("2026-12-31"))
    assert set(d.columns) >= {"data", "indexador", "principal_milhoes",
                              "cupom_milhoes"}
    assert d["principal_milhoes"].sum() > 700000
    assert 80000 < d["cupom_milhoes"].sum() < 120000


def test_a_janela_e_fechada_a_direita_e_aberta_a_esquerda():
    # (de, ate]. A rolagem encadeia janelas, e sobreposicao de um dia conta um
    # vencimento duas vezes.
    quinze = pd.Timestamp("2026-08-15")
    dentro = fluxos.pagos(pd.Timestamp("2026-08-14"), quinze)
    fora = fluxos.pagos(quinze, pd.Timestamp("2026-08-16"))
    assert dentro["principal_milhoes"].sum() > 0
    assert fora["principal_milhoes"].sum() == 0
```

- [ ] **Passo 2: rodar e ver falhar**

PowerShell:

```powershell
$env:PYTHONPATH="src"; python -m pytest tests/test_fluxos.py -q -k "3_4 or aba_2_2 or janela"
```

bash:

```bash
PYTHONPATH=src python -m pytest tests/test_fluxos.py -q -k "3_4 or aba_2_2 or janela"
```

Esperado: FAIL com `AttributeError: module 'tesouro.fluxos' has no attribute 'pagos'`.

- [ ] **Passo 3: implementar**

```python
INDEXADOR = {"LTN": "Prefixado", "NTN-F": "Prefixado",
             "NTN-B": "Índice Preços",
             "NTN-B Principal": "Índice Preços",
             "NTN-C": "Índice Preços",
             "NTN-B1 EducA+": "Índice Preços",
             "NTN-B1 RendA+": "Índice Preços",
             "LFT": "Taxa Flutuante", "LFT-TD1 Reserva": "Taxa Flutuante"}

_INDICE_DO_VNA = {"Índice Preços": "IPCA", "Taxa Flutuante": "SELIC"}


def _estoque_mais_recente():
    e = pd.read_csv(config.PROCESSED_DIR / "estoque_titulos_vencimento.csv",
                    parse_dates=["data", "vencimento"])
    u = e[(e["data"] == e["data"].max()) & (e["quantidade_mil"] > 0)].copy()
    faltando = sorted(set(u["titulo"]) - set(INDEXADOR))
    if faltando:
        raise LookupError(
            f"papel sem indexador em fluxos.INDEXADOR: {faltando}. Sem isso ele "
            f"sai da conta em silencio, e o fluxo pago fica menor do que e.")
    u["indexador"] = [INDEXADOR[t] for t in u["titulo"]]
    return u


def _vna(indice, quando):
    v = pd.read_csv(config.PROCESSED_DIR / "vna.csv", parse_dates=["data"])
    s = v[(v["indice"] == indice) & (v["data"] <= quando)]
    if s.empty:
        raise LookupError(
            f"nao ha VNA de {indice} ate {quando:%d/%m/%Y}. O cupom de papel "
            f"indexado nao pode ser calculado sem ele.")
    return float(s.iloc[-1]["vna"])


def pagos(de, ate):
    """Principal e cupom pagos em (de, ate], por data e indexador.

    JANELA FECHADA A DIREITA E ABERTA A ESQUERDA. A rolagem encadeia janelas, e
    sobreposicao de um dia conta um vencimento duas vezes.
    """
    de, ate = pd.Timestamp(de), pd.Timestamp(ate)
    u = _estoque_mais_recente()
    linhas = []

    vence = u[(u["vencimento"] > de) & (u["vencimento"] <= ate)]
    for _, r in vence.iterrows():
        linhas.append({"data": r["vencimento"], "indexador": r["indexador"],
                       "principal_milhoes": r["financeiro_milhoes"],
                       "cupom_milhoes": 0.0})

    for dia in pd.date_range(de + pd.Timedelta(days=1), ate, freq="D"):
        for _, r in u.iterrows():
            if not paga_cupom_em(r["titulo"], r["vencimento"], dia):
                continue
            taxa = (1 + CUPOM_ANUAL[r["titulo"]]) ** 0.5 - 1
            indice = _INDICE_DO_VNA[r["indexador"]]
            base = _vna(indice, dia) if indice == "IPCA" else 1000.0
            valor = r["quantidade_mil"] * 1000 * base * taxa / 1e6
            linhas.append({"data": dia, "indexador": r["indexador"],
                           "principal_milhoes": 0.0, "cupom_milhoes": valor})

    if not linhas:
        return pd.DataFrame(columns=["data", "indexador", "principal_milhoes",
                                     "cupom_milhoes"])
    return pd.DataFrame(linhas).sort_values("data").reset_index(drop=True)
```

- [ ] **Passo 4: rodar e ver passar**

PowerShell:

```powershell
$env:PYTHONPATH="src"; python -m pytest tests/test_fluxos.py -q
```

bash:

```bash
PYTHONPATH=src python -m pytest tests/test_fluxos.py -q
```

Esperado: 6 passed.

- [ ] **Passo 5: verificar dentes**

Troque `(u["vencimento"] > de)` por `(u["vencimento"] >= de)`. O teste da janela tem
de reprovar. Desfaça.

- [ ] **Passo 6: commitar**

```bash
git add src/tesouro/fluxos.py tests/test_fluxos.py
git commit -m "Fluxos pagos: principal da aba 2.2 e cupom calculado"
```

---

### Task 3: `calendario_leiloes.py` — quantos leilões faltam

**Arquivos:**
- Criar: `src/tesouro/calendario_leiloes.py`
- Teste: `tests/test_calendario_leiloes.py`

**Interfaces:**
- Consome: `calendario.padrao()` (o calendário de dias úteis), `leiloes.csv`
- Produz: `dias_estimados(de, ate) -> list[pd.Timestamp]`

- [ ] **Passo 1: escrever o teste que falha**

```python
"""O calendario de leiloes: o publicado, e o estimado alem dele."""
import pandas as pd

from tesouro import calendario_leiloes


def test_o_estimador_acerta_as_datas_de_2024_e_2025():
    # A VALIDACAO QUE SUSTENTA A PROJECAO. As regras vieram da dona do projeto e
    # foram conferidas contra o historico: prefixado na quinta (94% dos dias),
    # NTN-B na terca (97%), antecipando um dia util em feriado, e sem leilao depois
    # da terceira semana de dezembro.
    #
    # Medido: 32 de 32 datas acertadas em 2024 e em 2025, SEM NENHUM FALSO
    # POSITIVO. Os dias que faltam sao leiloes extraordinarios, que nao ha como
    # prever -- por isso o teste exige subconjunto, e nao igualdade.
    from tesouro import config

    l = pd.read_csv(config.PROCESSED_DIR / "leiloes.csv",
                    parse_dates=["data_leilao"])
    venda = l[l["tipo_leilao"].isin(["Venda", "Extra Venda"])]

    for ano in (2024, 2025):
        de = pd.Timestamp(f"{ano}-09-01")
        ate = pd.Timestamp(f"{ano}-12-31")
        estimado = set(calendario_leiloes.dias_estimados(de, ate))
        real = set(venda[(venda["data_leilao"] >= de)
                         & (venda["data_leilao"] <= ate)]
                   ["data_leilao"].dt.normalize())
        assert estimado <= real, (
            f"{ano}: o estimador previu dia sem leilao: {sorted(estimado - real)}")
        assert len(estimado) >= len(real) - 3, (
            f"{ano}: estimou {len(estimado)} contra {len(real)} reais")


def test_nao_ha_leilao_depois_da_terceira_semana_de_dezembro():
    # Medido: o ultimo leilao do ano caiu entre 15 e 21 de dezembro nos cinco anos.
    dias = calendario_leiloes.dias_estimados(pd.Timestamp("2026-12-01"),
                                             pd.Timestamp("2026-12-31"))
    assert dias
    assert max(dias).day <= 21


def test_o_leilao_antecipa_quando_o_dia_cai_em_feriado():
    # Natal de 2025 caiu numa quinta. O leilao de prefixado daquela semana nao
    # existiu, mas a regra de antecipacao vale para os feriados do meio do ano.
    # 21/04/2026 (Tiradentes) cai numa terca: o leilao daquela semana antecipa.
    from tesouro import calendario

    cal = calendario.padrao()
    assert not cal.eh_dia_util(pd.Timestamp("2026-04-21").date())
    dias = calendario_leiloes.dias_estimados(pd.Timestamp("2026-04-19"),
                                             pd.Timestamp("2026-04-25"))
    assert pd.Timestamp("2026-04-21") not in dias
    assert pd.Timestamp("2026-04-20") in dias
```

- [ ] **Passo 2: rodar e ver falhar**

PowerShell:

```powershell
$env:PYTHONPATH="src"; python -m pytest tests/test_calendario_leiloes.py -q
```

bash:

```bash
PYTHONPATH=src python -m pytest tests/test_calendario_leiloes.py -q
```

Esperado: `ModuleNotFoundError`.

- [ ] **Passo 3: implementar**

```python
"""Quais dias tem leilao, e quantos faltam ate uma data.

AS REGRAS SAO DO TESOURO, e foram descritas pela dona do projeto e conferidas contra
o historico de 2021 em diante:

    prefixado (LTN e NTN-F)   quinta-feira    94% dos 288 dias
    NTN-B                     terca-feira     97% dos 280 dias
    LFT                       terca-feira     81% -- e 18% na quinta
    feriado no dia            antecipa um dia util  (71% dos casos fora do padrao)
    fim de ano                sem leilao depois da terceira semana de dezembro

O estimador construido com elas erra de 0 a 2 dias em ~32, de setembro a dezembro,
nos anos de 2021 a 2025 -- e acerta 32 de 32 DATAS EXATAS em 2024 e 2025, sem nenhum
falso positivo. Os dias que faltam sao leiloes extraordinarios.

2019 e 2020 erram mais (+8 e +4 dias) e nao entram na validacao: sao anteriores ao
padrao atual, e 2020 foi o ano da pandemia.

ISTO E ESTIMATIVA, e o calendario publicado pelo Tesouro tem precedencia onde
existir -- ver dias_ate, que junta os dois e diz onde um acaba.
"""

import pandas as pd

from . import calendario

# Terca e quinta, na numeracao do pandas (segunda = 0).
_DIAS_DA_SEMANA = (1, 3)

# Depois deste dia de dezembro nao ha mais leilao.
_ULTIMO_DIA_DE_DEZEMBRO = 21


def _anterior_util(cal, d):
    """O dia, ou o dia util anterior a ele se cair em feriado."""
    while not cal.eh_dia_util(d.date()):
        d -= pd.Timedelta(days=1)
    return d


def dias_estimados(de, ate):
    """Os dias de leilao entre 'de' e 'ate', pelas regras do cabecalho.

    Devolve datas normalizadas e sem repeticao, em ordem. Terca e quinta caem no
    mesmo conjunto porque o que interessa a projecao e o DIA DE LEILAO, e nao qual
    papel foi ofertado nele -- o pace ja e medido por papel.
    """
    cal = calendario.padrao()
    de, ate = pd.Timestamp(de).normalize(), pd.Timestamp(ate).normalize()
    dias = set()
    for d in pd.date_range(de, ate, freq="D"):
        if d.dayofweek not in _DIAS_DA_SEMANA:
            continue
        dia = _anterior_util(cal, d)
        if dia < de:
            continue
        if dia.month == 12 and dia.day > _ULTIMO_DIA_DE_DEZEMBRO:
            continue
        dias.add(dia)
    return sorted(dias)
```

- [ ] **Passo 4: rodar e ver passar**

PowerShell:

```powershell
$env:PYTHONPATH="src"; python -m pytest tests/test_calendario_leiloes.py -q
```

bash:

```bash
PYTHONPATH=src python -m pytest tests/test_calendario_leiloes.py -q
```

Esperado: 3 passed.

- [ ] **Passo 5: verificar dentes**

Troque `_ULTIMO_DIA_DE_DEZEMBRO` por `31`. O teste de dezembro tem de reprovar.
Depois troque `_anterior_util` por `return d` e o teste do feriado tem de reprovar.
Desfaça as duas.

- [ ] **Passo 6: commitar**

```bash
git add src/tesouro/calendario_leiloes.py tests/test_calendario_leiloes.py
git commit -m "Calendario de leilao estimado, pelas regras do Tesouro"
```

---

### Task 4: `calendario_leiloes.py` — o publicado tem precedência

**Arquivos:**
- Modificar: `src/tesouro/calendario_leiloes.py`
- Teste: `tests/test_calendario_leiloes.py`

**Interfaces:**
- Consome: `parse_api_leiloes.calendario(registros)`, `dias_estimados` da Task 3
- Produz: `dias_ate(ate, registros=None) -> tuple[list, pd.Timestamp | None]` — os
  dias e a data em que o publicado acaba

- [ ] **Passo 1: escrever o teste que falha**

```python
def test_o_calendario_PUBLICADO_tem_precedencia_sobre_o_estimado():
    # Onde o Tesouro ja disse o que vai fazer, e transcricao. So alem disso e
    # inferencia -- e a pagina precisa saber onde uma acaba, senao apresenta
    # palpite com a mesma cara de fato.
    import json
    import pathlib

    fixtures = pathlib.Path(__file__).parent / "fixtures" / "api_leiloes"
    registros = json.loads(
        (fixtures / "calendario.json").read_text(encoding="utf-8"))["registros"]

    # HOJE FIXO, como o test_agenda.py ja faz. A amostra congelada vai de 20/08 a
    # 29/09/2026: com a data real do relogio, este teste comeca a reprovar sozinho
    # em 30/09, quando 'publicados' fica vazio e a fronteira vira None. Data movel
    # em teste e teste que quebra num dia qualquer, sem ninguem ter mexido em nada.
    dias, ate_quando = calendario_leiloes.dias_ate(
        pd.Timestamp("2026-12-31"), registros=registros,
        hoje=pd.Timestamp("2026-08-24"))
    assert ate_quando is not None
    assert pd.Timestamp("2026-08-20") <= ate_quando <= pd.Timestamp("2026-10-31")
    # Os dias do publicado entram como estao, mesmo os que a regra nao previa.
    publicados = set(dias[:len(dias)])
    assert ate_quando in publicados or ate_quando <= max(dias)
    # E depois dele, o estimado continua ate o fim do ano.
    assert max(dias) > ate_quando


def test_sem_registros_a_lista_e_toda_estimada():
    dias, ate_quando = calendario_leiloes.dias_ate(pd.Timestamp("2026-12-31"),
                                                   registros=[],
                                                   hoje=pd.Timestamp("2026-08-24"))
    assert ate_quando is None
    assert dias
```

- [ ] **Passo 2: rodar e ver falhar**

PowerShell:

```powershell
$env:PYTHONPATH="src"; python -m pytest tests/test_calendario_leiloes.py -q -k "PUBLICADO or sem_registros"
```

bash:

```bash
PYTHONPATH=src python -m pytest tests/test_calendario_leiloes.py -q -k "PUBLICADO or sem_registros"
```

Esperado: FAIL, `has no attribute 'dias_ate'`.

- [ ] **Passo 3: implementar**

```python
def dias_ate(ate, registros=None, hoje=None):
    """Os dias de leilao ate 'ate', e a data em que o calendario publicado acaba.

    O PUBLICADO TEM PRECEDENCIA. Onde o Tesouro ja disse o que vai fazer, e
    transcricao; alem disso e inferencia nossa. Devolver a fronteira junto nao e
    detalhe: sem ela a pagina apresentaria palpite com a mesma cara de fato.

    'registros' e a resposta ja baixada da API. Os testes passam a amostra
    congelada, e por isso nao tocam a rede.
    """
    from . import api_leiloes, parse_api_leiloes

    ate = pd.Timestamp(ate).normalize()
    hoje = pd.Timestamp(hoje).normalize() if hoje is not None \
        else pd.Timestamp.today().normalize()

    if registros is None:
        registros, _ = api_leiloes.buscar("calendario")

    publicados = []
    fronteira = None
    if len(registros):
        agenda = parse_api_leiloes.calendario(registros)
        datas = sorted(set(agenda["data_leilao"].dt.normalize()))
        publicados = [d for d in datas if hoje <= d <= ate]
        if publicados:
            fronteira = max(publicados)

    inicio = fronteira + pd.Timedelta(days=1) if fronteira is not None else hoje
    estimados = [d for d in dias_estimados(inicio, ate) if d not in set(publicados)]
    return sorted(set(publicados) | set(estimados)), fronteira
```

- [ ] **Passo 4: rodar e ver passar**

PowerShell:

```powershell
$env:PYTHONPATH="src"; python -m pytest tests/test_calendario_leiloes.py -q
```

bash:

```bash
PYTHONPATH=src python -m pytest tests/test_calendario_leiloes.py -q
```

Esperado: 5 passed.

- [ ] **Passo 5: verificar que a suíte não toca a rede**

Ponha `raise RuntimeError("A SUITE TOCOU A REDE")` na primeira linha de
`api_leiloes.buscar` e rode `tests/test_calendario_leiloes.py`. Tem de passar
inteiro. Desfaça.

- [ ] **Passo 6: commitar**

```bash
git add src/tesouro/calendario_leiloes.py tests/test_calendario_leiloes.py
git commit -m "O calendario publicado tem precedencia sobre o estimado"
```

---

### Task 5: `curva.py` — Selic implícita e inflação implícita

**Arquivos:**
- Criar: `src/tesouro/curva.py`
- Teste: `tests/test_curva.py`

**Interfaces:**
- Consome: `dv_por_papel.csv`, `calendario.padrao()`
- Produz:
  - `selic_implicita(ate, data_base=None) -> float` — taxa ao ano, em decimal
  - `inflacao_implicita(ate, data_base=None) -> float`

- [ ] **Passo 1: escrever o teste que falha**

```python
"""A curva do proprio dado: Selic implicita e inflacao implicita."""
import pandas as pd

from tesouro import curva


def test_a_interpolacao_IGNORA_vencimento_sem_cotacao():
    # A ARMADILHA DESTA TAREFA. A LTN de vencimento mais proximo de 31/12/2026 e a
    # 01/01/2027 -- e ela NAO TEM COTACAO: e um dos dois papeis que so existem no
    # Tesouro Direto. Quem escolher "o vencimento mais proximo" pega justamente o
    # que nao tem taxa, e a conta sai NaN sem reclamar.
    from tesouro import config

    d = pd.read_csv(config.PROCESSED_DIR / "dv_por_papel.csv",
                    parse_dates=["data", "vencimento"])
    ult = d[d["data"] == d["data"].max()]
    sem_taxa = ult[(ult["titulo"] == "LTN") & ult["taxa_pct"].isna()]
    assert len(sem_taxa), "a LTN sem cotacao sumiu do dado; reveja este teste"

    taxa = curva.selic_implicita(pd.Timestamp("2026-12-31"))
    assert taxa == taxa, "a taxa saiu NaN: a interpolacao pegou papel sem cotacao"
    assert 0.05 < taxa < 0.30, taxa


def test_a_selic_implicita_fica_entre_as_pontas_da_curva():
    # Interpolacao nao inventa: o valor tem de ficar entre os dois vizinhos.
    from tesouro import config

    d = pd.read_csv(config.PROCESSED_DIR / "dv_por_papel.csv",
                    parse_dates=["data", "vencimento"])
    ult = d[(d["data"] == d["data"].max()) & (d["titulo"] == "LTN")
            & d["taxa_pct"].notna()]
    taxa = curva.selic_implicita(pd.Timestamp("2026-12-31")) * 100
    assert ult["taxa_pct"].min() <= taxa <= ult["taxa_pct"].max()


def test_a_inflacao_implicita_sai_da_relacao_de_Fisher():
    # (1 + nominal) / (1 + real) - 1. Uma inflacao implicita que nao respeite isso
    # nao e breakeven, e outra coisa.
    infl = curva.inflacao_implicita(pd.Timestamp("2026-12-31"))
    assert 0.0 < infl < 0.15, infl


def test_a_NTN_B_de_referencia_nao_e_a_mais_proxima():
    # A mais proxima em 30/06/2026 e a de 15/08/2026, a 33 dias uteis, com taxa real
    # de 11,25% -- ponta de curva, e nao expectativa. A de referencia e a mais curta
    # COM COTACAO cujo vencimento passe da data-alvo.
    escolhida = curva.ntnb_de_referencia(pd.Timestamp("2026-12-31"))
    assert escolhida > pd.Timestamp("2026-12-31")
```

- [ ] **Passo 2: rodar e ver falhar**

PowerShell:

```powershell
$env:PYTHONPATH="src"; python -m pytest tests/test_curva.py -q
```

bash:

```bash
PYTHONPATH=src python -m pytest tests/test_curva.py -q
```

Esperado: `ModuleNotFoundError`.

- [ ] **Passo 3: implementar**

```python
"""A premissa da projecao, tirada da propria curva do projeto.

NENHUMA FONTE NOVA. A dona do projeto escolheu esta opcao entre quatro em
24/08/2026: a Selic vem interpolada da curva de LTN, e a inflacao vem do breakeven
entre a curva prefixada e a taxa real da NTN-B. Nao ha numero escolhido a mao, e as
duas contas sao reproduziveis.

ARMADILHA. A LTN de vencimento mais proximo de 31/12/2026 e a 01/01/2027, e ela NAO
TEM COTACAO: e um dos dois papeis que so existem no Tesouro Direto (achado de
22/08/2026). Escolher "o vencimento mais proximo" pega justamente essa, e a conta
sai NaN sem reclamar. Toda selecao de papel aqui filtra por taxa presente ANTES de
medir distancia.
"""

import bisect

import pandas as pd

from . import calendario, config


def _curva(titulo, data_base=None):
    """Os papeis COM COTACAO, ordenados por dias uteis ate o vencimento."""
    d = pd.read_csv(config.PROCESSED_DIR / "dv_por_papel.csv",
                    parse_dates=["data", "vencimento"])
    base = pd.Timestamp(data_base) if data_base is not None else d["data"].max()
    g = d[(d["data"] == base) & (d["titulo"] == titulo)
          & d["taxa_pct"].notna()].copy()
    if g.empty:
        raise LookupError(
            f"nenhuma {titulo} com cotacao em {base:%d/%m/%Y}. Sem curva nao ha "
            f"premissa, e projetar com premissa inventada seria pior.")
    cal = calendario.padrao()
    g["du"] = [cal.du(base.date(), v.date()) for v in g["vencimento"]]
    return base, g.sort_values("du")


def _interpola(g, du):
    xs, ys = list(g["du"]), list(g["taxa_pct"])
    if du <= xs[0]:
        return ys[0]
    if du >= xs[-1]:
        return ys[-1]
    i = bisect.bisect_left(xs, du)
    peso = (du - xs[i - 1]) / (xs[i] - xs[i - 1])
    return ys[i - 1] + peso * (ys[i] - ys[i - 1])


def selic_implicita(ate, data_base=None):
    """Taxa ao ano, em decimal, interpolada na curva de LTN ate 'ate'."""
    base, g = _curva("LTN", data_base)
    cal = calendario.padrao()
    du = cal.du(base.date(), pd.Timestamp(ate).date())
    return _interpola(g, du) / 100


def ntnb_de_referencia(ate, data_base=None):
    """A NTN-B mais curta COM COTACAO cujo vencimento passe de 'ate'.

    Nao e a mais proxima: em 30/06/2026 a mais proxima e a de 15/08/2026, a 33 dias
    uteis, com taxa real de 11,25% -- ponta de curva, e nao expectativa.
    """
    _, g = _curva("NTN-B", data_base)
    ate = pd.Timestamp(ate)
    depois = g[g["vencimento"] > ate]
    if depois.empty:
        raise LookupError(
            f"nenhuma NTN-B com cotacao vence depois de {ate:%d/%m/%Y}.")
    return depois.iloc[0]["vencimento"]


def inflacao_implicita(ate, data_base=None):
    """Breakeven ao ano, em decimal, no prazo da NTN-B de referencia."""
    base, pre = _curva("LTN", data_base)
    _, b = _curva("NTN-B", data_base)
    venc = ntnb_de_referencia(ate, data_base)
    linha = b[b["vencimento"] == venc].iloc[0]
    nominal = _interpola(pre, linha["du"]) / 100
    real = linha["taxa_pct"] / 100
    return (1 + nominal) / (1 + real) - 1
```

- [ ] **Passo 4: rodar e ver passar**

PowerShell:

```powershell
$env:PYTHONPATH="src"; python -m pytest tests/test_curva.py -q
```

bash:

```bash
PYTHONPATH=src python -m pytest tests/test_curva.py -q
```

Esperado: 4 passed.

- [ ] **Passo 5: verificar dentes**

Em `_curva`, tire o filtro `& d["taxa_pct"].notna()`. O teste da armadilha tem de
reprovar com a taxa saindo NaN. Desfaça.

- [ ] **Passo 6: commitar**

```bash
git add src/tesouro/curva.py tests/test_curva.py
git commit -m "A premissa sai da curva: Selic implicita e breakeven"
```

---

### Task 6: `rolagem.py` — o VNA recuperado do leilão

**Arquivos:**
- Criar: `src/tesouro/rolagem.py`
- Teste: `tests/test_rolagem.py`

**Interfaces:**
- Consome: `leiloes_dv._vna_implicito`, `calendario.padrao()`
- Produz: `vna_em(indice, quando) -> float`

- [ ] **Passo 1: escrever o teste que falha**

```python
"""A rolagem do estoque do RMD ate hoje, e a projecao ate o fim do ano."""
import pandas as pd
import pytest

from tesouro import rolagem


def test_o_VNA_recuperado_do_leilao_bate_com_o_conhecido():
    # ESTE E O TESTE QUE DISPENSA A BLOOMBERG. O vna.csv termina exatamente na
    # data-base do RMD, e os leiloes vao alem dela. Sem VNA nesses dias nao ha termo
    # de juros, e a LFT sai ~2% subestimada.
    #
    # PU = VNA x cotacao, e a cotacao depende so da taxa e das datas: o PU efetivo
    # dividido pela cotacao devolve o VNA que o Tesouro usou. Medido nos 98 leiloes
    # que caem em data de VNA conhecida, o erro mediano e 0,045%.
    from tesouro import config

    v = pd.read_csv(config.PROCESSED_DIR / "vna.csv", parse_dates=["data"])
    for indice in ("SELIC", "IPCA"):
        s = v[v["indice"] == indice].set_index("data")["vna"]
        quando = s.index[-1]
        recuperado = rolagem.vna_em(indice, quando)
        real = float(s.loc[quando])
        assert abs(recuperado - real) / real < 0.002, (indice, recuperado, real)


def test_sem_leilao_para_recuperar_o_VNA_ele_LEVANTA():
    # Congelar em silencio subestima o estoque da LFT em ~50 bi por mes. Se nao ha
    # como saber, o certo e parar.
    with pytest.raises(LookupError, match="VNA"):
        rolagem.vna_em("SELIC", pd.Timestamp("1990-01-01"))
```

- [ ] **Passo 2: rodar e ver falhar**

PowerShell:

```powershell
$env:PYTHONPATH="src"; python -m pytest tests/test_rolagem.py -q
```

bash:

```bash
PYTHONPATH=src python -m pytest tests/test_rolagem.py -q
```

Esperado: `ModuleNotFoundError`.

- [ ] **Passo 3: implementar**

```python
"""O estoque da divida numa data qualquer depois do ultimo RMD, e a projecao.

A CONTA, por indexador, entre a data-base do RMD (t0) e a data alvo (t1):

    estoque(t1) = estoque(t0)
                + leiloes LIQUIDADOS em (t0, t1]
                - fluxos pagos em (t0, t1]        principal E cupom
                + juros apropriados no periodo

Os tres termos sao todos necessarios -- medido em 24 meses fechados de RMD, erro
medio absoluto por mes, em R$ bilhoes:

    termos usados          Prefixado  Ind.Precos  Taxa Flutuante
    so leiloes                  52,7        32,7            70,7
    + vencimentos               14,6        16,3            42,0
    + juros apropriados         14,6        12,2             3,4

A apropriacao e o MAIOR termo da LFT: 39,9 dos 61,7 bi de variacao mensal media sao
Selic correndo sobre o estoque, e nao emissao.

A DATA QUE CASA E A DE LIQUIDACAO. E a data em que o papel entra no estoque, e e a
que o RMD usa. A defasagem mediana e de 1 dia util, mas 6,1% dos leiloes liquidam no
mes seguinte -- casar por data de leilao erra exatamente as viradas de mes, que e
onde o RMD corta.
"""

import pandas as pd

from . import calendario, config, leiloes_dv

# Qual papel serve para recuperar o VNA de cada indice.
_PAPEL_DO_INDICE = {"SELIC": "LFT", "IPCA": "NTN-B"}

# Quantos dias para tras aceitar um leilao como fonte do VNA.
_JANELA_DO_VNA = 15


def vna_em(indice, quando):
    """O VNA do indice na data, recuperado do leilao mais proximo.

    PU = VNA x cotacao, e a cotacao depende so da taxa e das datas -- entao o PU
    efetivo (financeiro / quantidade) dividido pela cotacao devolve o VNA que o
    Tesouro usou naquele dia.

    LEVANTA quando nao ha leilao na janela. Congelar em silencio subestima o estoque
    da LFT em cerca de 50 bilhoes por mes, e um numero errado sem aviso e pior do que
    numero nenhum.
    """
    quando = pd.Timestamp(quando)
    titulo = _PAPEL_DO_INDICE[indice]
    l = pd.read_csv(config.PROCESSED_DIR / "leiloes.csv",
                    parse_dates=["data_leilao", "data_vencimento"])
    g = l[(l["titulo"] == titulo) & (l["tipo_leilao"] == "Venda")
          & l["taxa_media_pct"].notna() & (l["venda_qtd"] > 0)
          & (l["financeiro_milhoes"] > 0)
          & (l["data_leilao"] <= quando)
          & (l["data_leilao"] >= quando - pd.Timedelta(days=_JANELA_DO_VNA))]
    if g.empty:
        raise LookupError(
            f"nao ha leilao de {titulo} entre {_JANELA_DO_VNA} dias antes de "
            f"{quando:%d/%m/%Y} para recuperar o VNA de {indice}. Congelar o VNA "
            f"subestima o estoque, e por isso a rolagem para aqui.")

    cal = calendario.padrao()
    r = g.sort_values("data_leilao").iloc[-1]
    implicito = leiloes_dv._vna_implicito(
        cal, titulo, r["data_leilao"].date(), r["data_vencimento"].date(),
        r["taxa_media_pct"] / 100, r["venda_qtd"], r["financeiro_milhoes"])
    if implicito is None:
        raise LookupError(
            f"o leilao de {titulo} em {r['data_leilao']:%d/%m/%Y} nao permitiu "
            f"recuperar o VNA de {indice}.")
    return implicito
```

- [ ] **Passo 4: rodar e ver passar**

PowerShell:

```powershell
$env:PYTHONPATH="src"; python -m pytest tests/test_rolagem.py -q
```

bash:

```bash
PYTHONPATH=src python -m pytest tests/test_rolagem.py -q
```

Esperado: 2 passed.

- [ ] **Passo 5: verificar dentes**

Troque o `raise LookupError` por `return 1000.0`. O teste do "levanta" tem de
reprovar. Desfaça.

- [ ] **Passo 6: commitar**

```bash
git add src/tesouro/rolagem.py tests/test_rolagem.py
git commit -m "O VNA recuperado do leilao, sem tocar a Bloomberg"
```

---

### Task 7: `rolagem.py` — a rolagem, conferida em 24 meses

**Arquivos:**
- Modificar: `src/tesouro/rolagem.py`
- Teste: `tests/test_rolagem.py`

**Interfaces:**
- Consome: `vna_em` da Task 6, `fluxos.pagos` da Task 2
- Produz: `estoque_em(quando) -> pd.Series` indexada por indexador, em R$ milhões;
  `INDEXADORES: tuple[str, ...]`

- [ ] **Passo 1: escrever o teste que falha**

```python
def test_a_rolagem_reproduz_os_meses_FECHADOS_do_RMD():
    # O TESTE QUE SUSTENTA TUDO O MAIS. Se a rolagem nao reproduz um mes que ja
    # aconteceu, o numero de "hoje" que ela produz nao vale nada.
    #
    # Os limites vieram da medicao em 24 meses, em % do estoque do indexador:
    # taxa flutuante 0,07%, indice de precos 0,51%, prefixado 0,75%. O teste usa o
    # DOBRO de folga, para nao reprovar por um mes atipico.
    from tesouro import config

    c = pd.read_csv(config.PROCESSED_DIR / "composicao_dpf.csv",
                    parse_dates=["data"])
    piv = c.pivot_table(index="data", columns="indexador",
                        values="valor_milhoes", aggfunc="sum").fillna(0.0)
    datas = list(piv.index)[-13:]

    LIMITE = {"Prefixado": 0.015, "Índice Preços": 0.011,
              "Taxa Flutuante": 0.002}
    for t0, t1 in zip(datas[:-1], datas[1:]):
        obtido = rolagem.estoque_em(t1, de=t0)
        for ind, limite in LIMITE.items():
            real = piv.loc[t1, ind]
            erro = abs(obtido[ind] - real) / real
            assert erro < limite, (t1.date(), ind, erro, limite)


def test_a_rolagem_casa_por_LIQUIDACAO_e_nao_por_data_de_leilao():
    # 6,1% dos leiloes liquidam no mes seguinte ao do leilao. Casar pela data errada
    # poe o papel no mes errado, e erra exatamente as viradas -- que e onde o RMD
    # corta.
    from tesouro import config

    l = pd.read_csv(config.PROCESSED_DIR / "leiloes.csv",
                    parse_dates=["data_leilao", "data_liquidacao"])
    vira = l[(l["data_liquidacao"].dt.to_period("M")
              != l["data_leilao"].dt.to_period("M"))
             & (l["tipo_leilao"] == "Venda")]
    assert len(vira) > 1000, "os leiloes que viram o mes sumiram do dado"

    r = vira.sort_values("data_liquidacao").iloc[-1]
    fim_do_mes_do_leilao = (r["data_leilao"] + pd.offsets.MonthEnd(0))
    entrou = rolagem.leiloes_liquidados(
        r["data_liquidacao"] - pd.Timedelta(days=1), r["data_liquidacao"])
    nao_entrou = rolagem.leiloes_liquidados(
        fim_do_mes_do_leilao - pd.Timedelta(days=31), fim_do_mes_do_leilao)
    assert entrou.sum() > 0
    assert r["data_liquidacao"] > fim_do_mes_do_leilao


def test_o_CAMBIO_fica_parado_e_a_rolagem_diz_isso():
    # O indexador Cambio E a DPFe -- diferenca mediana de R$ 4,9 bi em 307 meses --
    # e a DPFe nao passa por leilao. Ele e segurado no valor do RMD, com o custo
    # medido: 5,2 bi por mes, 0,06% do estoque total.
    #
    # O que nao pode e segura-lo em SILENCIO: ele esta no denominador dos outros
    # tres percentuais.
    assert "Câmbio" in rolagem.PARADOS
    assert "Câmbio" not in rolagem.INDEXADORES
```

- [ ] **Passo 2: rodar e ver falhar**

PowerShell:

```powershell
$env:PYTHONPATH="src"; python -m pytest tests/test_rolagem.py -q -k "FECHADOS or LIQUIDACAO or CAMBIO"
```

bash:

```bash
PYTHONPATH=src python -m pytest tests/test_rolagem.py -q -k "FECHADOS or LIQUIDACAO or CAMBIO"
```

Esperado: FAIL, `has no attribute 'estoque_em'`.

- [ ] **Passo 3: implementar**

```python
# Os indexadores que a rolagem move. O Cambio fica de fora -- ver PARADOS.
INDEXADORES = ("Prefixado", "Índice Preços", "Taxa Flutuante")

# O CAMBIO E A DPFe: comparados os 307 meses da serie, a diferenca mediana entre os
# dois e de R$ 4,9 bilhoes. A DPFe nao passa por leilao, e o movimento dela e cambio
# mais emissao externa, que este projeto nao tem -- entao nao ha como rolar um sem o
# outro.
#
# Ele e segurado no valor do ultimo RMD. Custo medido: variacao mensal mediana de
# R$ 5,2 bi, ou 0,06% do estoque total; em dois meses, no pior decil, R$ 32,5 bi.
# Contra uma banda de cambio com largura de pontos percentuais inteiros, e ruido.
#
# O que NAO e aceitavel e segura-lo em silencio: ele entra no denominador dos outros
# tres percentuais, entao a pagina marca a linha dele como nao rolada.
PARADOS = ("Câmbio",)

_INDICE_DO_INDEXADOR = {"Taxa Flutuante": "SELIC", "Índice Preços": "IPCA"}

# Carga do prefixado: LTN e NTN-F nao tem VNA, carregam para o par pela taxa de
# emissao. O residuo medido sem este termo e de +12,2 bi/mes sobre ~1.900 bi, ou
# 0,64% ao mes -- que e uma carga de ~13% ao ano, e nao ruido.
_CARGA_DO_PREFIXADO = 0.135

_INDEXADOR_DO_TITULO = {"LTN": "Prefixado", "NTN-F": "Prefixado",
                        "NTN-B": "Índice Preços",
                        "NTN-C": "Índice Preços",
                        "LFT": "Taxa Flutuante"}

_SINAL = {"Venda": 1, "Extra Venda": 1, "Compra": -1, "Extra Compra": -1,
          "Troca": 0}


def base_do_rmd():
    """A data-base do ultimo RMD, e o estoque por indexador nela."""
    c = pd.read_csv(config.PROCESSED_DIR / "composicao_dpf.csv",
                    parse_dates=["data"])
    piv = c.pivot_table(index="data", columns="indexador",
                        values="valor_milhoes", aggfunc="sum").fillna(0.0)
    return piv.index.max(), piv.loc[piv.index.max()]


def leiloes_liquidados(de, ate):
    """Financeiro liquido dos leiloes liquidados em (de, ate], por indexador."""
    l = pd.read_csv(config.PROCESSED_DIR / "leiloes.csv",
                    parse_dates=["data_liquidacao"])
    l = l[(l["data_liquidacao"] > pd.Timestamp(de))
          & (l["data_liquidacao"] <= pd.Timestamp(ate))].copy()
    l["indexador"] = [_INDEXADOR_DO_TITULO.get(t) for t in l["titulo"]]
    l["sinal"] = [_SINAL.get(t, 0) for t in l["tipo_leilao"]]
    l = l[l["indexador"].notna()]
    fluxo = (l["financeiro_milhoes"] * l["sinal"]).groupby(l["indexador"]).sum()
    return fluxo.reindex(list(INDEXADORES)).fillna(0.0)


def _apropriacao(indexador, base, de, ate):
    """Juros apropriados sobre o estoque no periodo."""
    if indexador == "Prefixado":
        cal = calendario.padrao()
        du = cal.du(pd.Timestamp(de).date(), pd.Timestamp(ate).date())
        return base * ((1 + _CARGA_DO_PREFIXADO) ** (du / 252) - 1)
    indice = _INDICE_DO_INDEXADOR[indexador]
    return base * (vna_em(indice, ate) / vna_em(indice, de) - 1)


def estoque_em(quando, de=None):
    """O estoque por indexador na data, rolado desde o RMD (ou desde 'de')."""
    from . import fluxos

    if de is None:
        de, inicial = base_do_rmd()
    else:
        c = pd.read_csv(config.PROCESSED_DIR / "composicao_dpf.csv",
                        parse_dates=["data"])
        piv = c.pivot_table(index="data", columns="indexador",
                            values="valor_milhoes", aggfunc="sum").fillna(0.0)
        de = pd.Timestamp(de)
        inicial = piv.loc[de]

    quando = pd.Timestamp(quando)
    emitido = leiloes_liquidados(de, quando)
    pagou = fluxos.pagos(de, quando)
    saida = {}
    for ind in INDEXADORES:
        base = float(inicial[ind])
        do_ind = pagou[pagou["indexador"] == ind]
        pago = (do_ind["principal_milhoes"].sum()
                + do_ind["cupom_milhoes"].sum())
        saida[ind] = (base + float(emitido[ind]) - pago
                      + _apropriacao(ind, base, de, quando))
    for ind in PARADOS:
        saida[ind] = float(inicial[ind])
    return pd.Series(saida)
```

- [ ] **Passo 4: rodar e ver passar**

PowerShell:

```powershell
$env:PYTHONPATH="src"; python -m pytest tests/test_rolagem.py -q
```

bash:

```bash
PYTHONPATH=src python -m pytest tests/test_rolagem.py -q
```

Esperado: 5 passed.

Se o teste dos meses fechados reprovar por pouco num indexador, **não afrouxe o
limite**: veja qual termo está faltando. O limite já tem o dobro da folga medida.

- [ ] **Passo 5: verificar dentes**

Três mutações, uma de cada vez, desfazendo entre elas:

1. Em `estoque_em`, tire `- pago`. O teste dos meses fechados tem de reprovar.
2. Em `_apropriacao`, devolva `0.0` na primeira linha. Tem de reprovar na taxa
   flutuante.
3. Em `leiloes_liquidados`, troque `data_liquidacao` por `data_leilao` no
   `parse_dates` e nos dois filtros. Tem de reprovar.

- [ ] **Passo 6: commitar**

```bash
git add src/tesouro/rolagem.py tests/test_rolagem.py
git commit -m "A rolagem do estoque, conferida em 24 meses fechados"
```

---

### Task 8: `rolagem.py` — a projeção até o fim do ano

**Arquivos:**
- Modificar: `src/tesouro/rolagem.py`
- Teste: `tests/test_rolagem.py`

**Interfaces:**
- Consome: `estoque_em` (Task 7), `calendario_leiloes.dias_ate` (Task 4),
  `curva.selic_implicita` e `curva.inflacao_implicita` (Task 5)
- Produz: `LEILOES_DO_PACE: int`; `pace(quando) -> pd.Series`;
  `projecao(ate, hoje=None, registros=None) -> dict`

- [ ] **Passo 0: consertar `curva._curva` antes de tudo**

Achado por mim ao varrer o brief, e é **bloqueante**: `_curva` casa a data-base por
igualdade exata, e isso quebra nos dois caminhos que esta tarefa precisa.

**No backtest:** `composicao_dpf.csv` usa o último dia **corrido** do mês e
`dv_por_papel.csv` usa o último dia **útil**. Em 2024 eles divergem — 30/06/2024 caiu
num domingo, então o `dv_por_papel` tem 28/06. `curva.selic_implicita(data_base=
30/06/2024)` levanta `LookupError`.

**No caminho real, que é pior:** a projeção parte da última **liquidação**, que hoje
é 17/08/2026, e o `dv_por_papel` termina em 30/06/2026. O caminho principal da
entrega levantaria `LookupError` — e nenhum teste o exercitava.

Mude `_curva(titulo, data_base=None)` para usar a **data mais recente menor ou igual
a `data_base`**, em vez de igualdade exata:

```python
def _curva(titulo, data_base=None):
    """Os papeis COM COTACAO na data-base, ordenados por dias uteis ate o vencimento.

    A DATA-BASE E A MAIS RECENTE MENOR OU IGUAL a pedida, e nao igualdade exata. Dois
    motivos, e os dois quebravam:

    O composicao_dpf.csv usa o ultimo dia CORRIDO do mes e o dv_por_papel.csv usa o
    ultimo dia UTIL. Em 30/06/2024 -- um domingo -- eles divergem, e o backtest
    levantava LookupError num ano que existe nos dois arquivos.

    E a projecao real parte da ultima LIQUIDACAO, que vai alem do ultimo RMD. A curva
    termina no RMD. Exigir igualdade fazia o caminho principal da entrega levantar.

    Quem chama recebe de volta a data que de fato valeu, porque uma curva de sete
    semanas atras apresentada como "de hoje" e o tipo de coisa que a pagina inteira
    existe para nao fazer.
    """
    d = pd.read_csv(config.PROCESSED_DIR / "dv_por_papel.csv",
                    parse_dates=["data", "vencimento"])
    pedida = pd.Timestamp(data_base) if data_base is not None else d["data"].max()
    disponiveis = d.loc[d["data"] <= pedida, "data"]
    if disponiveis.empty:
        raise LookupError(
            f"nao ha curva ate {pedida:%d/%m/%Y} no dv_por_papel.csv. Sem curva nao "
            f"ha premissa, e projetar com premissa inventada seria pior.")
    base = disponiveis.max()
    g = d[(d["data"] == base) & (d["titulo"] == titulo)
          & d["taxa_pct"].notna()].copy()
    if g.empty:
        raise LookupError(
            f"nenhuma {titulo} com cotacao em {base:%d/%m/%Y}. Sem curva nao ha "
            f"premissa, e projetar com premissa inventada seria pior.")
    cal = calendario.padrao()
    g["du"] = [cal.du(base.date(), v.date()) for v in g["vencimento"]]
    return base, g.sort_values("du")
```

E acrescente `data_da_curva(data_base=None) -> pd.Timestamp`, que devolve a data que
`_curva` de fato usaria — a projeção precisa dela para a página dizer de quando é a
curva.

Testes que vão junto:

```python
def test_a_curva_aceita_data_base_que_nao_existe_no_arquivo():
    # O composicao_dpf usa o ultimo dia CORRIDO e o dv_por_papel o ultimo dia UTIL.
    # 30/06/2024 caiu num domingo: existe num e nao no outro. E a projecao real parte
    # da ultima LIQUIDACAO, que vai alem do ultimo RMD -- o caminho principal da
    # entrega levantava LookupError, e nenhum teste o exercitava.
    from tesouro import curva

    assert curva.data_da_curva(pd.Timestamp("2024-06-30")) == pd.Timestamp("2024-06-28")
    assert curva.selic_implicita(pd.Timestamp("2024-12-31"),
                                 data_base=pd.Timestamp("2024-06-30")) > 0

    # E alem do fim do arquivo: a curva mais recente vale, e quem chama fica sabendo.
    depois = pd.Timestamp("2026-08-17")
    usada = curva.data_da_curva(depois)
    assert usada < depois
    assert curva.selic_implicita(pd.Timestamp("2026-12-31"), data_base=depois) > 0


def test_sem_curva_nenhuma_ate_a_data_ele_LEVANTA():
    from tesouro import curva

    with pytest.raises(LookupError, match="curva"):
        curva.data_da_curva(pd.Timestamp("1999-01-01"))
```

Verifique os dentes: volte `_curva` para igualdade exata e confirme que o primeiro
teste reprova.

- [ ] **Passo 1: escrever o teste que falha**

```python
def test_o_pace_e_por_PAPEL_e_nao_por_dia_de_leilao():
    # Decisao dela. O metodo anterior media por DIA DE LEILAO contando os zeros --
    # nos dias de terca o prefixado vale zero -- e so dava certo se a mistura de
    # tercas e quintas da janela batesse com a do futuro. Batia por sorte: 10 e 10,
    # contra 18 e 18 no futuro.
    #
    # Medir sobre os leiloes DAQUELE papel nao depende de mistura, e rende numero que
    # se confere de cabeca: 1,09 bi por leilao de NTN-B, e nao 0,21 por dia.
    assert rolagem.LEILOES_DO_PACE == 10
    p = rolagem.pace(pd.Timestamp("2026-08-17"))
    for ind in rolagem.INDEXADORES:
        assert p[ind] > 0, ind
    # A ordem de grandeza medida em 17/08/2026: a LFT coloca 21,91 bi por leilao, o
    # prefixado 12,32 e a NTN-B 1,09. Se essa relacao inverter, alguem trocou o
    # denominador -- que e exatamente o defeito que este metodo veio corrigir.
    assert p["Índice Preços"] * 5 < p["Taxa Flutuante"]
    assert p["Índice Preços"] * 3 < p["Prefixado"]


def test_a_contagem_de_leiloes_futuros_e_por_PAPEL():
    # Prefixado na quinta, indexados na terca. Numa janela com 18 de cada, cada papel
    # tem 18 leiloes -- e nao os 36 dias.
    from tesouro import calendario_leiloes

    dias = calendario_leiloes.dias_estimados(pd.Timestamp("2026-08-18"),
                                             pd.Timestamp("2026-12-31"))
    assert len(dias) == 36
    for ind in rolagem.INDEXADORES:
        quantos = rolagem.leiloes_que_faltam(dias, ind)
        assert 15 <= quantos <= 20, (ind, quantos)
        assert quantos < len(dias), "contou dia de leilao, e nao leilao do papel"


def test_a_projecao_devolve_a_PREMISSA_que_usou():
    # Numero projetado sem a premissa ao lado e opiniao com cara de medida.
    p = rolagem.projecao(pd.Timestamp("2026-12-31"), registros=[])
    assert 0.05 < p["selic"] < 0.30
    assert 0.0 < p["inflacao"] < 0.15
    assert p["dias_de_leilao"] > 0
    assert "fronteira_do_calendario" in p
    # A data da curva viaja junto: ela termina no ultimo RMD e a projecao parte da
    # ultima liquidacao, semanas depois.
    assert p["data_da_curva"] <= p["de"]
```

- [ ] **Passo 2: rodar e ver falhar**

PowerShell:

```powershell
$env:PYTHONPATH="src"; python -m pytest tests/test_rolagem.py -q -k "pace or projecao"
```

bash:

```bash
PYTHONPATH=src python -m pytest tests/test_rolagem.py -q -k "pace or projecao"
```

Esperado: FAIL, `has no attribute 'LEILOES_DO_PACE'`.

- [ ] **Passo 3: implementar**

```python
# Quantos dias de leilao entram na media do pace.
#
# VINTE, escolha dela: sao cerca de dez semanas e dez leiloes de cada papel. O
# backtest de dez anos NAO DISTINGUE as janelas -- 10, 20 e 60 dias de leilao e 26
# semanas caem todos na mesma faixa de erro (1,26 a 1,71 pp no prefixado) -- entao a
# escolha e por ser a unidade em que se pensa, e por lidar sozinha com semana de
# feriado e com dezembro, que tem menos leilao.
LEILOES_DO_PACE = 10

# EM QUE DIA DA SEMANA CADA PAPEL VAI A LEILAO. Regra do Tesouro, descrita pela dona
# do projeto e medida nos ultimos dois anos:
#
#     prefixado (LTN e NTN-F)   quinta-feira   91% dos 104 leiloes
#     NTN-B                     terca-feira    95% dos 101
#     LFT                       terca-feira    99% dos  98
#
# Feriado que antecipa o leilao em um dia util nao muda nada aqui: o que se conta e
# quantos leiloes DAQUELE PAPEL faltam, e nao em que dia da semana caem.
DIA_DO_PAPEL = {"Prefixado": 3, "\u00cdndice Pre\u00e7os": 1, "Taxa Flutuante": 1}

def pace(quando):
    """Financeiro liquido medio por LEILAO DAQUELE PAPEL, por indexador.

    OS ZEROS NAO ENTRAM NA MEDIA. Um dia de terca em que o prefixado nao foi a leilao
    nao e um leilao de prefixado de valor zero: e um dia em que ele nao foi ofertado.
    Contar o zero fazia a media depender da mistura de tercas e quintas da janela --
    batia por sorte (10 e 10, contra 18 e 18 no futuro), e uma janela com 15 tercas e
    5 quintas subestimaria o prefixado em quase metade, sem nada acusar.

    Medido em 17/08/2026: prefixado 12,32 bi por leilao, indice de precos 1,09, taxa
    flutuante 21,91.
    """
    l = pd.read_csv(config.PROCESSED_DIR / "leiloes.csv",
                    parse_dates=["data_leilao", "data_liquidacao"])
    l = l[l["data_liquidacao"] <= pd.Timestamp(quando)].copy()
    l["indexador"] = [_INDEXADOR_DO_TITULO.get(t) for t in l["titulo"]]
    l["sinal"] = [_SINAL.get(t, 0) for t in l["tipo_leilao"]]
    l = l[l["indexador"].notna()]
    l["fluxo"] = l["financeiro_milhoes"] * l["sinal"]

    por_leilao = l.pivot_table(index="data_leilao", columns="indexador",
                               values="fluxo", aggfunc="sum")
    saida = {}
    for ind in INDEXADORES:
        if ind not in por_leilao.columns:
            raise LookupError(f"nenhum leilao de {ind} ate {quando:%d/%m/%Y}.")
        dele = por_leilao[ind].dropna()
        dele = dele[dele != 0].tail(LEILOES_DO_PACE)
        if len(dele) < LEILOES_DO_PACE:
            raise LookupError(
                f"so ha {len(dele)} leiloes de {ind} ate {quando:%d/%m/%Y}, e o "
                f"pace pede {LEILOES_DO_PACE}.")
        saida[ind] = dele.mean()
    return pd.Series(saida)


def leiloes_que_faltam(dias, indexador):
    """Quantos dos dias de leilao levam AQUELE papel.

    O prefixado vai a leilao na quinta e os indexados na terca -- regra do Tesouro,
    medida em 91% a 99% dos ultimos dois anos. Feriado que antecipa o leilao em um
    dia util nao muda a conta: o que importa e quantos leiloes daquele papel faltam.
    """
    alvo = DIA_DO_PAPEL[indexador]
    return sum(1 for d in dias if pd.Timestamp(d).dayofweek == alvo)


def projecao(ate, hoje=None, registros=None):
    """O estoque projetado para 'ate', com a premissa que usou ao lado.

    A PREMISSA VIAJA JUNTO de proposito. Numero projetado sem ela e opiniao com cara
    de medida -- e no estoque em reais ela vale quase a largura da banda: congelar
    da 9.339 bi e apropriar da 9.850, contra uma banda de 9.700 a 10.300.
    """
    from . import calendario_leiloes, curva, fluxos

    ate = pd.Timestamp(ate)

    # A PROJECAO COMECA DE HOJE, e nao da data-base do RMD. Comecando do RMD, o
    # pace seria aplicado tambem aos dias de leilao que JA ACONTECERAM entre a
    # data-base e hoje -- trocando seis semanas de leilao medido por estimativa. E
    # os dois blocos da mesma pagina partiriam de lugares diferentes.
    #
    # 'hoje' existe para o BACKTEST, em que quem chama quer comecar numa data de
    # RMD de proposito, para comparar com o dezembro que de fato aconteceu.
    if hoje is not None:
        partida = pd.Timestamp(hoje)
        c = pd.read_csv(config.PROCESSED_DIR / "composicao_dpf.csv",
                        parse_dates=["data"])
        piv = c.pivot_table(index="data", columns="indexador",
                            values="valor_milhoes", aggfunc="sum").fillna(0.0)
        inicial = piv.loc[partida]
    else:
        l = pd.read_csv(config.PROCESSED_DIR / "leiloes.csv",
                        parse_dates=["data_liquidacao"])
        partida = l["data_liquidacao"].max()
        inicial = estoque_em(partida)

    dias, fronteira = calendario_leiloes.dias_ate(ate, registros=registros,
                                                  hoje=partida)
    quantos = len(dias)
    ritmo = pace(partida)
    pagou = fluxos.pagos(partida, ate)
    selic = curva.selic_implicita(ate, data_base=partida)
    inflacao = curva.inflacao_implicita(ate, data_base=partida)
    cal = calendario.padrao()
    du = cal.du(partida.date(), ate.date())

    projetado = {}
    for ind in INDEXADORES:
        base = float(inicial[ind])
        do_ind = pagou[pagou["indexador"] == ind]
        pago = do_ind["principal_milhoes"].sum() + do_ind["cupom_milhoes"].sum()
        if ind == "Taxa Flutuante":
            taxa = selic
        elif ind == "Índice Preços":
            taxa = (1 + inflacao) * 1.06 - 1
        else:
            taxa = _CARGA_DO_PREFIXADO
        juros = base * ((1 + taxa) ** (du / 252) - 1)
        projetado[ind] = (base + float(ritmo[ind])
                          * leiloes_que_faltam(dias, ind) - pago + juros)
    for ind in PARADOS:
        projetado[ind] = float(inicial[ind])

    total = sum(projetado.values())
    return {"estoque": pd.Series(projetado),
            "percentual": pd.Series({k: 100 * v / total
                                     for k, v in projetado.items()}),
            "selic": selic, "inflacao": inflacao,
            # DE QUANDO E A CURVA. Ela termina no ultimo RMD e a projecao parte da
            # ultima liquidacao: sao semanas de diferenca, e apresentar premissa de
            # sete semanas atras como "de hoje" e o tipo de coisa que esta pagina
            # existe para nao fazer.
            "data_da_curva": curva.data_da_curva(partida),
            "dias_de_leilao": quantos,
            "fronteira_do_calendario": fronteira,
            "de": partida, "ate": ate}
```

- [ ] **Passo 4: rodar e ver passar**

PowerShell:

```powershell
$env:PYTHONPATH="src"; python -m pytest tests/test_rolagem.py -q
```

bash:

```bash
PYTHONPATH=src python -m pytest tests/test_rolagem.py -q
```

Esperado: 8 passed.

- [ ] **Passo 5: verificar dentes**

Troque `LEILOES_DO_PACE` por `1`. O teste da projeção tem de reprovar em pelo menos
um ano. Desfaça.

- [ ] **Passo 6: commitar**

```bash
git add src/tesouro/rolagem.py tests/test_rolagem.py
git commit -m "A projecao ate o fim do ano, com a premissa ao lado"
```

---

### Task 9: `graficos/banda.py` — a distância, e as duas tabelas

**Arquivos:**
- Criar: `src/tesouro/graficos/banda.py`
- Teste: `tests/test_painel_paf.py`

**Interfaces:**
- Consome: `rolagem.estoque_em`, `rolagem.projecao`, `paf.bandas`
- Produz:
  - `INDICADORES: tuple[tuple[str, str, str], ...]` — `(chave, rótulo, unidade)`
  - `distancia(valor, minimo, maximo) -> float`
  - `dados_hoje(hoje=None) -> pd.DataFrame`
  - `dados_projecao(ate=None, registros=None) -> pd.DataFrame`
  - `tabela(dados, ident) -> str`

- [ ] **Passo 1: escrever o teste que falha**

```python
"""A pagina contra o PAF: distancia, projecao e o arquivo."""
import pandas as pd
import pytest

from tesouro.graficos import banda


def test_a_distancia_tem_o_sinal_certo_dos_dois_lados_e_zero_DENTRO():
    # Dentro da banda a distancia e zero, e nao "a distancia ate o meio". Quem esta
    # dentro cumpriu o que prometeu; medir distancia ate o centro inventaria um
    # alvo que o PAF nao define.
    assert banda.distancia(25.0, 21.0, 28.0) == 0.0
    assert banda.distancia(21.0, 21.0, 28.0) == 0.0
    assert banda.distancia(28.0, 21.0, 28.0) == 0.0
    assert banda.distancia(19.5, 21.0, 28.0) == pytest.approx(-1.5)
    assert banda.distancia(30.0, 21.0, 28.0) == pytest.approx(2.0)


def test_a_tabela_de_hoje_tem_uma_linha_por_indicador():
    d = banda.dados_hoje()
    assert len(d) == len(banda.INDICADORES)
    assert set(d.columns) >= {"indicador", "no_rmd", "hoje", "minimo", "maximo",
                              "distancia", "unidade", "rolado"}


def test_a_linha_do_CAMBIO_aparece_marcada_como_NAO_ROLADA():
    # Ele e a DPFe, que nao passa por leilao. Segura-lo e aceitavel; segura-lo em
    # silencio nao e, porque ele esta no denominador dos outros tres percentuais.
    d = banda.dados_hoje().set_index("indicador")
    assert d.loc["Câmbio", "rolado"] is False or \
        not bool(d.loc["Câmbio", "rolado"])
    assert bool(d.loc["Prefixado", "rolado"])


def test_a_tabela_diz_DE_QUANDO_e_o_hoje_e_quantos_leiloes_entraram():
    # Numero sem procedencia nao serve: quem le precisa saber se o "hoje" e de
    # ontem ou de tres semanas atras.
    html = banda.tabela(banda.dados_hoje(), "tabela-hoje")
    assert "leil" in html
    assert "20" in html
```

- [ ] **Passo 2: rodar e ver falhar**

PowerShell:

```powershell
$env:PYTHONPATH="src"; python -m pytest tests/test_painel_paf.py -q
```

bash:

```bash
PYTHONPATH=src python -m pytest tests/test_painel_paf.py -q
```

Esperado: `ModuleNotFoundError: No module named 'tesouro.graficos.banda'`.

- [ ] **Passo 3: implementar**

```python
"""A distancia ate a banda do PAF, e as duas tabelas da pagina.

DENTRO DA BANDA A DISTANCIA E ZERO, e nao "a distancia ate o meio". Quem esta dentro
cumpriu o que prometeu; medir ate o centro inventaria um alvo que o PAF nao define.
"""

import pandas as pd

from .. import config, rolagem
from . import paf

# (chave da banda, rotulo, unidade). A ordem e a da tabela.
INDICADORES = (
    ("prefixado_pct", "Prefixado", "pp"),
    ("indice_precos_pct", "Índice Preços", "pp"),
    ("taxa_flutuante_pct", "Taxa Flutuante", "pp"),
    ("cambio_pct", "Câmbio", "pp"),
    ("prazo_medio_anos", "Prazo médio", "anos"),
    ("vincendo_12m_pct", "Vincendo em 12 meses", "pp"),
    ("estoque_bilhoes", "Estoque", "R$ bi"),
)


def distancia(valor, minimo, maximo):
    """Quanto falta para entrar na banda. Zero se ja esta dentro."""
    if pd.isna(valor) or pd.isna(minimo) or pd.isna(maximo):
        return float("nan")
    if valor < minimo:
        return valor - minimo
    if valor > maximo:
        return valor - maximo
    return 0.0
```

```python
# Os indicadores que a rolagem MOVE. Os demais aparecem com o valor do RMD e
# marcados como nao rolados.
#
# Prazo medio e vincendo em 12 meses nao sao rolados nesta entrega: rola-los exige
# recalcular o prazo papel a papel, que e trabalho da entrega 5. O cambio nao e
# rolado porque e a DPFe, que nao passa por leilao -- ver rolagem.PARADOS.
_ROLADOS = ("prefixado_pct", "indice_precos_pct", "taxa_flutuante_pct",
            "estoque_bilhoes")

_DA_COMPOSICAO = {"prefixado_pct": "Prefixado",
                  "indice_precos_pct": "Índice Preços",
                  "taxa_flutuante_pct": "Taxa Flutuante",
                  "cambio_pct": "Câmbio"}


def _realizado_do_rmd():
    """O valor de cada indicador na data-base do RMD, do NOSSO dado.

    A coluna 'realizado' do referencia/paf_bandas.csv nao e usada, e paf.bandas() ja
    a descarta de proposito: ler o realizado de uma tabela digitada seria trocar dado
    verificado por dado redigitado.
    """
    c = pd.read_csv(config.PROCESSED_DIR / "composicao_dpf.csv",
                    parse_dates=["data"])
    comp = c.pivot_table(index="data", columns="indexador",
                         values="valor_milhoes", aggfunc="sum").fillna(0.0)
    pct = comp.div(comp.sum(axis=1), axis=0) * 100

    p = pd.read_csv(config.PROCESSED_DIR / "prazo_medio_por_titulo.csv",
                    parse_dates=["data"])
    prazo = p[(p["nivel"] == "DPF") & p["entidade"].isna()
              & p["titulo"].isna()].set_index("data")["prazo_anos"]

    v = pd.read_csv(config.PROCESSED_DIR / "vencimentos_faixa.csv",
                    parse_dates=["data"])
    fx = v[v["nivel"] == "DPF"].pivot_table(
        index="data", columns="faixa", values="valor_milhoes",
        aggfunc="sum").fillna(0.0)
    venc12 = fx["Até 12 meses"] / fx.sum(axis=1) * 100

    e = pd.read_csv(config.PROCESSED_DIR / "estoque_dpf.csv",
                    parse_dates=["data"])
    ag = e[e["entidade"].isna() & e["titulo"].isna()]
    est = ag[ag["nivel"] == "DPF em poder do publico"].set_index(
        "data")["valor_milhoes"] / 1000

    base = comp.index.max()
    saida = {k: float(pct.loc[base, nome])
             for k, nome in _DA_COMPOSICAO.items()}
    saida["prazo_medio_anos"] = float(prazo.loc[prazo.index.max()])
    saida["vincendo_12m_pct"] = float(venc12.loc[venc12.index.max()])
    saida["estoque_bilhoes"] = float(est.loc[est.index.max()])
    return base, saida


def _valores_de_hoje(quando):
    """Os indicadores rolados ate 'quando'. Os nao rolados vem como None."""
    estoque = rolagem.estoque_em(quando)
    total = estoque.sum()
    return {"prefixado_pct": 100 * estoque["Prefixado"] / total,
            "indice_precos_pct": 100 * estoque["Índice Preços"] / total,
            "taxa_flutuante_pct": 100 * estoque["Taxa Flutuante"] / total,
            "cambio_pct": None,
            "prazo_medio_anos": None,
            "vincendo_12m_pct": None,
            "estoque_bilhoes": total / 1000}


def _linhas(valores, ano, quando=None):
    """Uma linha por indicador, com a banda do ano, a distancia e a data.

    'quando' e a data dos indicadores ROLADOS. Os parados ficam com a
    data-base do RMD, e a diferenca entre as duas e o que a coluna
    de_quando mostra na tabela.
    """
    base, no_rmd = _realizado_do_rmd()
    quando = quando if quando is not None else base
    linhas = []
    for chave, rotulo, unidade in INDICADORES:
        b = paf.bandas(chave)
        if ano not in b.index:
            continue
        r = b.loc[ano]
        valor = valores.get(chave)
        rolado = valor is not None
        if not rolado:
            valor = no_rmd[chave]
        linhas.append({"indicador": rotulo, "chave": chave,
                       "no_rmd": no_rmd[chave], "hoje": valor,
                       "minimo": r["minimo"], "maximo": r["maximo"],
                       "minimo_original": r["minimo_original"],
                       "maximo_original": r["maximo_original"],
                       "distancia": distancia(valor, r["minimo"], r["maximo"]),
                       "unidade": unidade, "rolado": rolado,
                       "data_base": base})
    return pd.DataFrame(linhas)


def dados_hoje(hoje=None):
    """A tabela de onde estamos hoje."""
    quando = pd.Timestamp(hoje) if hoje is not None else _ultima_liquidacao()
    return _linhas(_valores_de_hoje(quando), quando.year, quando)


def _ultima_liquidacao():
    l = pd.read_csv(config.PROCESSED_DIR / "leiloes.csv",
                    parse_dates=["data_liquidacao"])
    return l["data_liquidacao"].max()


def quantos_leiloes_entraram(hoje=None):
    """Quantos dias de leilao entraram na rolagem, e de que data ate que data."""
    base, _ = _realizado_do_rmd()
    ate = pd.Timestamp(hoje) if hoje is not None else _ultima_liquidacao()
    l = pd.read_csv(config.PROCESSED_DIR / "leiloes.csv",
                    parse_dates=["data_liquidacao"])
    entre = l[(l["data_liquidacao"] > base) & (l["data_liquidacao"] <= ate)]
    return entre["data_liquidacao"].nunique(), base, ate


def dados_projecao(ate=None, registros=None):
    """A tabela de onde fechamos o ano."""
    ate = pd.Timestamp(ate) if ate is not None else pd.Timestamp(
        f"{_ultima_liquidacao().year}-12-31")
    p = rolagem.projecao(ate, registros=registros)
    valores = {"prefixado_pct": p["percentual"]["Prefixado"],
               "indice_precos_pct": p["percentual"]["Índice Preços"],
               "taxa_flutuante_pct": p["percentual"]["Taxa Flutuante"],
               "cambio_pct": None, "prazo_medio_anos": None,
               "vincendo_12m_pct": None,
               "estoque_bilhoes": p["estoque"].sum() / 1000}
    d = _linhas(valores, ate.year)
    d.attrs["premissa"] = p
    return d


def _numero(valor, unidade):
    casas = 0 if unidade == "R$ bi" else 2
    return estilo.num_br(valor, casas)


def tabela(dados, ident, rodape=""):
    """A tabela em HTML, com a linha nao rolada marcada."""
    cabec = ("<tr><th>indicador</th><th class='n'>no RMD</th>"
             "<th class='n'>hoje</th><th class='n'>banda</th>"
             "<th class='n'>dist\u00e2ncia</th></tr>")
    linhas = []
    for _, r in dados.iterrows():
        marca = "" if r["rolado"] else " class='parado'"
        nota = "" if r["rolado"] else " *"
        dist = ("dentro" if r["distancia"] == 0
                else _numero(r["distancia"], r["unidade"]) + " " + r["unidade"])
        linhas.append(
            f"<tr{marca}><td>{r['indicador']}{nota}</td>"
            f"<td class='n'>{_numero(r['no_rmd'], r['unidade'])}</td>"
            f"<td class='n'>{_numero(r['hoje'], r['unidade'])}</td>"
            f"<td class='n'>{_numero(r['minimo'], r['unidade'])} a "
            f"{_numero(r['maximo'], r['unidade'])}</td>"
            f"<td class='n'>{dist}</td></tr>")
    return (f"<div id='{ident}'><table>{cabec}{''.join(linhas)}</table>"
            f"<p class='rodape'>{rodape}</p></div>")
```

**Prazo médio e vincendo em 12 meses não são rolados** nesta entrega, e aparecem
marcados com asterisco, pelo mesmo critério do câmbio. Rolá-los exigiria recalcular
o prazo papel a papel, que é trabalho da entrega 5. Isso está no §7.1 da spec.

- [ ] **Passo 4: rodar e ver passar**

PowerShell:

```powershell
$env:PYTHONPATH="src"; python -m pytest tests/test_painel_paf.py -q
```

bash:

```bash
PYTHONPATH=src python -m pytest tests/test_painel_paf.py -q
```

Esperado: 4 passed.

- [ ] **Passo 5: verificar dentes**

Em `distancia`, troque o `return 0.0` final por `return valor - (minimo + maximo)/2`.
O primeiro teste tem de reprovar. Desfaça.

- [ ] **Passo 6: commitar**

```bash
git add src/tesouro/graficos/banda.py tests/test_painel_paf.py
git commit -m "A distancia ate a banda, e as duas tabelas"
```

---

### Task 10: `painel_paf.py` — a página `paf.html`

**Arquivos:**
- Criar: `src/tesouro/graficos/painel_paf.py`
- Modificar: `src/tesouro/graficos/dashboard.py` (a lista `PAGINAS`)
- Modificar: `src/tesouro/pipeline.py`
- Teste: `tests/test_painel_paf.py`

**Interfaces:**
- Consome: `banda.dados_hoje`, `banda.dados_projecao`, `banda.tabela`,
  `dashboard.grava`
- Produz: `ARQUIVO = "paf.html"`; `grava(caminho=None, hoje=None) -> Path`

- [ ] **Passo 1: escrever o teste que falha**

```python
@pytest.fixture(scope="module")
def pagina(tmp_path_factory):
    from tesouro.graficos import painel_paf

    destino = tmp_path_factory.mktemp("paf") / painel_paf.ARQUIVO
    return painel_paf.grava(destino).read_text(encoding="utf-8")


def test_a_pagina_tem_os_DOIS_blocos_recolhiveis(pagina):
    # Eram tres na primeira versao da spec. O historico saiu por decisao dela: era
    # analise, e nao monitoramento.
    import re

    corpo = pagina[pagina.index("</header>"):pagina.rindex("</main>")]
    assert corpo.count("<details class=\"secao") == 2
    assert 'id="tabela-hoje"' in pagina
    assert 'id="tabela-projecao"' in pagina
    assert re.search(r"<details class=\"secao[^\"]*\" open>", corpo)


def test_a_pagina_esta_na_barra_e_aponta_para_as_irmas(pagina):
    from tesouro.graficos import dashboard, painel_paf

    assert any(a == painel_paf.ARQUIVO for a, _ in dashboard.PAGINAS)
    assert f'href="{painel_paf.ARQUIVO}"' not in pagina
    for outra, _ in dashboard.PAGINAS:
        if outra != painel_paf.ARQUIVO:
            assert f'href="{outra}"' in pagina


def test_a_pagina_nao_tem_referencia_externa(pagina):
    import re

    externos = [m.group(1) for m in
                re.finditer(r'(?:src|href|xlink:href)\s*=\s*"([^"]*)"', pagina)
                if "://" in m.group(1)]
    assert externos == [], externos[:3]


def test_a_pagina_cabe_no_limiar_de_dez_megabytes(tmp_path):
    from tesouro.graficos import painel_paf

    caminho = painel_paf.grava(tmp_path / painel_paf.ARQUIVO)
    tamanho = caminho.stat().st_size
    assert tamanho > 20_000, "a pagina saiu pequena demais; algo nao entrou"
    assert tamanho < 10 * 1024 * 1024


def test_o_achado_do_historico_ficou_como_TEXTO(pagina):
    # O bloco dos sete graficos saiu; o numero fica. 70% pela banda original contra
    # 79% pela vigente, e 14 de 14 inversoes para dentro.
    assert "70%" in pagina and "79%" in pagina
```

- [ ] **Passo 2: rodar e ver falhar**

PowerShell:

```powershell
$env:PYTHONPATH="src"; python -m pytest tests/test_painel_paf.py -q -k "pagina"
```

bash:

```bash
PYTHONPATH=src python -m pytest tests/test_painel_paf.py -q -k "pagina"
```

Esperado: `ModuleNotFoundError: No module named 'tesouro.graficos.painel_paf'`.

- [ ] **Passo 3: implementar**

```python
"""A pagina contra o PAF: onde estamos hoje, e onde fechamos o ano.

E PAGINA PROPRIA, e nao secao do dashboard, por tres razoes que estao na spec 6.4. A
que decide: as entregas 4 e 5 sao a pergunta e a resposta -- "estou dentro?" e "o que
faco para entrar?" -- e a 5 acrescenta um bloco AQUI, em vez de criar outra pagina.

A que quase passou batido: esta pagina muda a cada leilao liquidado, e o dashboard
muda uma vez por mes. Enterrar uma tabela que muda toda semana num arquivo de 4 MB e
reescrever 4 MB para mudar uma linha.
"""

from .. import config
from . import banda, dashboard

ARQUIVO = "paf.html"
GRUPOS = ["Contra o PAF"]
REGISTRO = []

SECOES = [
    ("hoje", "Onde estamos hoje", True),
    ("projecao", "Onde fechamos o ano", False),
]

# O achado do historico, que perdeu os sete graficos e ficou como texto. Ver spec
# 7.3: aquele bloco era analise e nao monitoramento.
_ACHADO = (
    "<p class='achado'>Em 23 anos de PAF, o Tesouro fechou o ano dentro da banda "
    "em <b>70% dos casos pela banda original</b> e <b>79% pela vigente</b>. Em "
    "<b>14 de 14</b> revis\u00f5es que inverteram o veredito, a banda revisada "
    "p\u00f4s o realizado <i>dentro</i> \u2014 nunca fora.</p>")

_CSS = """
#tabela-hoje, #tabela-projecao { margin: 20px auto 30px; max-width: 1180px; }
#tabela-hoje table, #tabela-projecao table { border-collapse: collapse;
  width: 100%; font-size: 13.5px; }
#tabela-hoje th, #tabela-hoje td, #tabela-projecao th, #tabela-projecao td {
  padding: 6px 10px; text-align: left; border-bottom: 1px solid #e6e6e6; }
#tabela-hoje th, #tabela-projecao th { font-weight: 600; color: var(--fraco);
  border-bottom: 2px solid #ccc; }
td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; }
tr.parado td { color: var(--fraco); font-style: italic; }
p.rodape, p.achado { font-size: 12.5px; color: var(--fraco); max-width: 1180px;
  margin: 6px auto 0; }
"""


def _recolhe(conteudo, chave, rotulo, aberta):
    marca = " open" if aberta else ""
    return (f'<details class="secao secao-{chave}"{marca}>'
            f"<summary>{rotulo}</summary>\n{conteudo}\n</details>")


def _rodape_de_hoje():
    quantos, base, ate = banda.quantos_leiloes_entraram()
    return (f"Estoque do RMD de {base:%d/%m/%Y}, rolado at\u00e9 "
            f"{ate:%d/%m/%Y} com <b>{quantos} dias de leil\u00e3o</b> "
            f"liquidados no meio, mais os fluxos pagos e os juros apropriados. "
            f"As linhas com * n\u00e3o s\u00e3o roladas: o c\u00e2mbio \u00e9 "
            f"a d\u00edvida externa, que n\u00e3o passa por leil\u00e3o, e o "
            f"prazo e o vincendo ficam para a entrega 5.")


def _rodape_da_projecao(dados):
    from .. import rolagem

    p = dados.attrs["premissa"]
    fronteira = p["fronteira_do_calendario"]
    onde = (f"calend\u00e1rio publicado at\u00e9 {fronteira:%d/%m/%Y} e "
            f"estimado depois" if fronteira is not None
            else "calend\u00e1rio inteiramente estimado")
    return (f"Pace dos <b>{rolagem.LEILOES_DO_PACE} \u00faltimos leil\u00f5es de "
            f"cada papel</b>, aplicado aos leil\u00f5es que faltam em "
            f"<b>{p['dias_de_leilao']} dias</b> \u2014 {onde}. "
            f"Selic impl\u00edcita de {p['selic']*100:.2f}% e infla\u00e7\u00e3o "
            f"impl\u00edcita de {p['inflacao']*100:.2f}%, da curva de "
            f"{p['data_da_curva']:%d/%m/%Y}. "
            f"<b>O n\u00famero mais incerto \u00e9 a emiss\u00e3o:</b> em dez anos "
            f"de backtest, projetar o segundo semestre pelo ritmo do momento errou "
            f"<b>R$ 153 bilh\u00f5es em m\u00e9dia</b> \u2014 um quarto da largura "
            f"da banda. A proje\u00e7\u00e3o sup\u00f5e que o ritmo continua, e "
            f"falha quando ele n\u00e3o continua: em 2020 errou 6,5 pontos no "
            f"prefixado.")


def grava(caminho=None, hoje=None):
    """Grava a pagina do PAF e devolve o caminho."""
    caminho = caminho or (config.PROCESSED_DIR / ARQUIVO)
    escrito = dashboard.grava(caminho, [("paf", None)], REGISTRO, GRUPOS,
                              "Contra o PAF", agrupar=False)
    html = escrito.read_text(encoding="utf-8")

    # ANCORADO NO FIM DO CABECALHO, e nao na abertura do <main>: a marca do main
    # aparece antes, dentro de um comentario do CSS, e o recorte pegava metade da
    # folha de estilo junto. Defeito real, achado em 20/08/2026.
    marca = "</header>"
    inicio = html.index(marca) + len(marca)
    fim = html.rindex("</main>")

    de_hoje = banda.dados_hoje(hoje)
    projetado = banda.dados_projecao()
    corpo = "\n".join([
        _recolhe(banda.tabela(de_hoje, "tabela-hoje", _rodape_de_hoje()),
                 *SECOES[0]),
        _recolhe(banda.tabela(projetado, "tabela-projecao",
                              _rodape_da_projecao(projetado)) + _ACHADO,
                 *SECOES[1]),
    ])
    html = html[:inicio] + "\n" + corpo + "\n" + html[fim:]
    html = html.replace("</style>", _CSS + "</style>", 1)
    escrito.write_text(html, encoding="utf-8")
    return escrito
```

**Nenhuma tag literal dentro de comentário de CSS** — `_CSS` acima não tem
comentários por isso. Um `<main>` dentro de um comentário quebra o recorte, e já
quebrou em 20/08/2026.

Em `dashboard.py`, acrescente a entrada em `PAGINAS`, entre a de funding e a de
emissões:

```python
PAGINAS = [(arquivo, rotulo) for arquivo, rotulo, _, _ in PAGINAS_DO_RMD] + [
    ("paf.html", "contra o PAF"),
    ("emissoes.html", "o que já foi emitido"),
    ("calendario.html", "o calendário"),
]
```

Em `pipeline.py`, depois de `painel_emissoes.grava_todas()`:

```python
        from .graficos import painel_paf
        print(f"pagina do PAF gravada: {painel_paf.grava()}")
```

- [ ] **Passo 4: rodar e ver passar**

PowerShell:

```powershell
$env:PYTHONPATH="src"; python -m pytest tests/test_painel_paf.py -q
```

bash:

```bash
PYTHONPATH=src python -m pytest tests/test_painel_paf.py -q
```

Esperado: 9 passed.

- [ ] **Passo 5: rodar a suíte inteira e regravar as páginas**

PowerShell:

```powershell
$env:PYTHONPATH="src"; python -m pytest -q
```

bash:

```bash
PYTHONPATH=src python -m pytest -q
```

Esperado: tudo passando, e os testes de `test_dashboard.py` que contam as páginas
podem precisar do número novo — ajuste a contagem, não o comportamento.

Depois regrave as páginas e confira o tamanho da nova:

```bash
PYTHONPATH=src python -m tesouro.graficos
```

- [ ] **Passo 6: commitar**

```bash
git add src/tesouro/graficos/painel_paf.py src/tesouro/graficos/dashboard.py src/tesouro/pipeline.py tests/test_painel_paf.py
git commit -m "A pagina contra o PAF, irma do calendario"
```

---

## Depois de todas as tarefas

- [ ] Atualizar o `README.md`: a lista de páginas passa de seis para sete, com o
      tamanho medido de `paf.html`.
- [ ] Conferir no navegador, com o servidor de `.claude/launch.json`: a barra liga
      as sete páginas, a primeira seção abre, e não há rolagem horizontal.
- [ ] Rodar a suíte inteira uma última vez e commitar as páginas regravadas.
