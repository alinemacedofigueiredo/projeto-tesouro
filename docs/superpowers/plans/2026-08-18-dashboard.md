# Dashboard da dívida — plano de implementação

> **Para trabalhadores agênticos:** SUB-SKILL OBRIGATÓRIA: use
> superpowers:subagent-driven-development (recomendado) ou
> superpowers:executing-plans para implementar tarefa a tarefa. Os passos usam
> caixinha (`- [ ]`) para acompanhamento.

**Objetivo:** um dashboard HTML autocontido com dezesseis gráficos da dívida
pública federal, gerado a partir dos CSVs que as entregas anteriores produziram.

**Arquitetura:** cada gráfico é um par de funções — uma que devolve um DataFrame
com exatamente o que vai para a tela, e outra que desenha. A primeira não conhece
matplotlib e é onde os testes de número vivem; a segunda é a parte descartável se o
motor de desenho mudar. Um módulo por tema, um registro literal no montador do
HTML.

**Tecnologias:** `pandas`, `matplotlib`, `pytest`. Nada além disso.

**Spec:** `docs/superpowers/specs/2026-08-18-dashboard-design.md`

## Restrições globais

Copiadas da spec. Valem para toda tarefa deste plano.

- **Bibliotecas permitidas: `pandas`, `openpyxl`, `xlrd`, `matplotlib`, `pytest`.**
  Nada mais. `numpy` **não** conta como permitido mesmo funcionando — o pandas o
  arrasta, mas ele não está declarado, e a lista existe porque este projeto vai para
  um banco com travas de biblioteca.
- **Arquivos `.py` inteiramente ASCII**, comentários e docstrings inclusive. Texto
  que o usuário lê (rótulo de gráfico, título) leva acento por **escape Unicode**
  (`"conven\u00e7\u00f5es"`), que é byte ASCII no disco e renderiza acentuado.
- **Nada é escrito em `data/raw/`.** É dado insubstituível; um coletor de entrega
  anterior já destruiu snapshots ali em silêncio.
- **Caminhos vêm de `config.PROCESSED_DIR` e `config.RAIZ`**, nunca relativos ao
  diretório de trabalho.
- **Guardas de pandas:** `pd.isna(...)` e nunca `is None` numa coluna numérica;
  `r["isin"]` e nunca `r.isin`, que resolve para o método `Series.isin`.
- **Instrução de linha de comando vem em PowerShell primeiro e bash depois**,
  seguindo `docs/como-baixar.md:6-12`. Sintaxe bash sozinha falha na primeira linha
  no shell da usuária, e isso já quebrou quatro vezes neste projeto.
- **Não toque em `src/tesouro/precificacao.py`.** É port validado contra o
  `PX_DIRTY_MID` da Bloomberg em 438 pares papel-data.
- **Não toque em `src/tesouro/figuras.py`.** É da entrega 2 e será absorvido depois,
  por decisão explícita registrada na spec.
- **Nenhuma consulta à Bloomberg**, por nenhum motivo. A usuária exige autorizar
  cada uma, caso a caso.

## Ambiente

- Python: `C:\Users\lineb\AppData\Local\Programs\Python\Python312\python.exe` (o
  comando `python` pode cair no atalho da Microsoft Store).
- `pytest` exige `PYTHONPATH=src`.
- Caminhos com espaço precisam ser citados.
- A suíte tem **306 testes passando e 1 pulado** no início deste plano. O pulado é o
  teste do PU contra o `PX_DIRTY_MID`, que aguarda autorização da usuária para puxar
  `bbg_precos_*.csv`. Nenhum pode regredir.

## Estrutura de arquivos

| arquivo | responsabilidade |
|---|---|
| `src/tesouro/graficos/__init__.py` | pacote |
| `src/tesouro/graficos/estilo.py` | cores, meses em português, número brasileiro, helpers de eixo, `svg.hashsalt` |
| `src/tesouro/graficos/funding.py` | 3 gráficos da aba 1.1 e 1.2 |
| `src/tesouro/graficos/estoque.py` | composição por indexador com banda do PAF |
| `src/tesouro/graficos/detentores.py` | 3 gráficos das abas 2.7 e 2.8 |
| `src/tesouro/graficos/vencimentos.py` | cronograma, faixas da DPF, perfil completo |
| `src/tesouro/graficos/prazo.py` | prazo médio com banda |
| `src/tesouro/graficos/custo.py` | custo contra índices, custo de emissão |
| `src/tesouro/graficos/reserva.py` | duas versões da reserva |
| `src/tesouro/graficos/leiloes.py` | emissão anual por papel (candidato) |
| `src/tesouro/graficos/dashboard.py` | registro dos gráficos e montagem do HTML |
| `src/tesouro/parse_rmd/vencimentos.py` | **modificar:** emitir o balde "Após 5 anos" |
| `src/tesouro/pipeline.py` | **modificar:** gerar o dashboard |

---

## Task 1: Fundação — estilo, ASCII e reprodutibilidade

**Files:**
- Create: `src/tesouro/graficos/__init__.py`
- Create: `src/tesouro/graficos/estilo.py`
- Test: `tests/test_estilo.py`

**Interfaces:**
- Consumes: nada.
- Produces: `MES`, `MES_LONGO`, `COR`, `num_br(v, casas=1)`, `rotulo_mes(d)`,
  `aplicar_estilo()`, `eixo_anual(ax, a_cada=1)`, `grade_fina(ax, maior, menor)`.

**Por que esta tarefa existe.** Três coisas que, se não forem resolvidas agora,
aparecem espalhadas por dezesseis gráficos: o mês em português (o matplotlib usa a
locale do sistema e sai "may" em vez de "mai"), o número no formato brasileiro, e a
reprodutibilidade do SVG.

**A armadilha da reprodutibilidade:** o matplotlib gera identificadores aleatórios
dentro do SVG. Sem fixar `svg.hashsalt`, duas execuções com o mesmo dado produzem
arquivos diferentes, e ninguém consegue saber se o dashboard mudou porque o dado
mudou. É uma linha, e sem ela o teste de reprodutibilidade da Task 11 é impossível.

- [ ] **Passo 1: escrever o teste que falha**

```python
# tests/test_estilo.py
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytest

from tesouro.graficos import estilo


def test_mes_sai_em_portugues():
    from datetime import date
    assert estilo.rotulo_mes(date(2026, 5, 31)) == "mai/26"
    assert estilo.rotulo_mes(date(2026, 12, 31)) == "dez/26"
    assert estilo.MES_LONGO[6] == "Junho"


def test_numero_sai_no_formato_brasileiro():
    assert estilo.num_br(1472.87, 2) == "1.472,87"
    assert estilo.num_br(-302.3, 1) == "-302,3"
    assert estilo.num_br(8904, 0) == "8.904"
    assert estilo.num_br(0.5, 1) == "0,5"


def test_o_svg_e_reprodutivel():
    # Sem svg.hashsalt fixo, o matplotlib sorteia ids e dois desenhos iguais
    # produzem arquivos diferentes. Sem isto, nenhum teste de reprodutibilidade
    # do dashboard e possivel.
    estilo.aplicar_estilo()

    def desenha():
        buf = io.StringIO()
        fig, ax = plt.subplots()
        ax.plot([1, 2, 3], [4, 5, 6])
        fig.savefig(buf, format="svg")
        plt.close(fig)
        return buf.getvalue()

    assert desenha() == desenha()


def test_o_modulo_e_ascii_puro():
    # Rotulo acentuado vai por escape Unicode, nao por byte acentuado.
    caminho = estilo.__file__
    with open(caminho, "rb") as f:
        f.read().decode("ascii")


def test_as_cores_cobrem_os_indexadores_e_os_papeis():
    for chave in ("Prefixado", "Indice Precos", "Taxa Flutuante", "Cambio"):
        assert chave in estilo.COR
    for chave in ("LTN", "NTN-F", "NTN-B", "LFT"):
        assert chave in estilo.COR
```

- [ ] **Passo 2: rodar e ver falhar**

```
$env:PYTHONPATH="src"; python -m pytest tests/test_estilo.py -v
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'tesouro.graficos'`.

- [ ] **Passo 3: criar o pacote**

```python
# src/tesouro/graficos/__init__.py
"""Camada de graficos do projeto: uma funcao de dado e uma de desenho por grafico.

A separacao existe por dois motivos. O primeiro e decisao de projeto: o motor de
desenho pode mudar (ver a spec, secao 3.1), e trocar matplotlib por outra coisa nao
pode exigir reescrever a logica dos graficos. O segundo e teste: com a separacao, o
teste afirma "a composicao de junho de 2026 e 21,0 / 25,9 / 49,3 / 3,7" em vez de
"a figura tem quatro barras", que passa com qualquer implementacao.
"""
```

- [ ] **Passo 4: escrever o estilo**

```python
# src/tesouro/graficos/estilo.py
"""Cores, formato de numero e de data, e reprodutibilidade do SVG.

Tudo que se repetiria em dezesseis graficos mora aqui. Em especial tres coisas que
o matplotlib nao da de graca: mes em portugues (a locale do sistema devolve "may"),
numero no formato brasileiro, e SVG reprodutivel.
"""

import matplotlib

MES = {1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun",
       7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez"}

MES_LONGO = {1: "Janeiro", 2: "Fevereiro", 3: "Mar\u00e7o", 4: "Abril",
             5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
             9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"}

# Paleta unica do projeto. Os indexadores seguem as cores que a usuaria aprovou nos
# rascunhos; os papeis usam a mesma familia para o mesmo indexador (LTN e NTN-F em
# azul porque sao prefixados, NTN-B em roxo, LFT em cinza).
COR = {
    # indexadores
    "Prefixado": "#1f6feb",
    "Indice Precos": "#ff7f0e",
    "Taxa Flutuante": "#2ca02c",
    "Cambio": "#d62728",
    "Demais": "#9467bd",
    # papeis
    "LTN": "#2f5597",
    "NTN-F": "#8faadc",
    "NTN-B": "#674ea7",
    "LFT": "#7f7f7f",
    "NTN-C": "#8c564b",
    "Outros": "#c9c9c9",
    # detentores, na paleta das paginas do RMD
    "Inst. Financeiras": "#1f3864",
    "Fundos": "#3d9be9",
    "Previdencia": "#a6a6a6",
    "Nao-residente": "#ed7d31",
    "Demais Grupos": "#70ad47",
    # elementos
    "banda": "#c00000",
    "neutro": "#666666",
}


def aplicar_estilo():
    """Fixa os parametros globais do matplotlib. Chamar antes de desenhar.

    O svg.hashsalt e o que torna o SVG reprodutivel: sem ele o matplotlib sorteia
    os identificadores internos e dois desenhos identicos geram arquivos
    diferentes, tornando impossivel saber se o dashboard mudou porque o dado mudou.
    """
    matplotlib.use("Agg")
    matplotlib.rcParams["svg.hashsalt"] = "tesouro"
    matplotlib.rcParams["figure.dpi"] = 110
    matplotlib.rcParams["axes.grid"] = False
    matplotlib.rcParams["font.size"] = 10


def num_br(valor, casas=1):
    """Numero no formato brasileiro: ponto de milhar, virgula decimal."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def rotulo_mes(d):
    """'mai/26' a partir de uma data."""
    return f"{MES[d.month]}/{d.year % 100:02d}"


def eixo_anual(ax, a_cada=1):
    """Marca o eixo do tempo por ano, mantendo o dado mensal.

    A pagina do RMD usa ~170 rotulos mensais e ninguem le. Marca anual com dado
    mensal e legivel e nao perde resolucao.
    """
    import matplotlib.dates as mdates
    ax.xaxis.set_major_locator(mdates.YearLocator(a_cada))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    if a_cada > 1:
        ax.xaxis.set_minor_locator(mdates.YearLocator())


def grade_fina(ax, maior, menor, eixo="y"):
    """Grade com linha cheia a cada 'maior' e linha fraca a cada 'menor'."""
    from matplotlib.ticker import MultipleLocator
    alvo = ax.yaxis if eixo == "y" else ax.xaxis
    alvo.set_major_locator(MultipleLocator(maior))
    alvo.set_minor_locator(MultipleLocator(menor))
    ax.grid(axis=eixo, which="major", alpha=0.30)
    ax.grid(axis=eixo, which="minor", alpha=0.12)
```

- [ ] **Passo 5: rodar e ver passar**

```
$env:PYTHONPATH="src"; python -m pytest tests/test_estilo.py -v
```

Esperado: 5 passed.

- [ ] **Passo 6: rodar a suíte inteira**

```
$env:PYTHONPATH="src"; python -m pytest -q
```

Esperado: 311 passed, 1 skipped.

- [ ] **Passo 7: commit**

```bash
git add src/tesouro/graficos/ tests/test_estilo.py
git commit -m "Adiciona a fundacao da camada de graficos"
```

---

## Task 2: Fechar a lacuna do balde "Após 5 anos"

**Files:**
- Modify: `src/tesouro/parse_rmd/vencimentos.py`
- Test: `tests/test_vencimentos.py`

**Interfaces:**
- Consumes: nada da camada de gráficos.
- Produces: `cronograma_vencimentos.csv` passa a somar **8.920,7 bi** em vez de
  6.913,8, com uma linha por grupo cujo `mes_vencimento` fica **vazio** e uma coluna
  nova `faixa` com o valor `apos_5_anos`.

**Por que esta tarefa existe, e por que ela vem cedo.** A aba 3.4 detalha 60 meses
(6.913,8 bi) e joga todo o resto num balde único, "Após 5 anos", de **2.006,9 bi**.
O nosso parser captura só os 60 meses. Quem somar `cronograma_vencimentos.csv` hoje
pega **78% do estoque** achando que pegou o todo — e isso é defeito independente de
qualquer gráfico.

Ler a planilha crua no gráfico foi recusado: trava o nome do arquivo no código,
duplica a interpretação das esquisitices do RMD, e quebra a propriedade que faz o
projeto funcionar no banco.

**Como a aba é estruturada.** Linhas 7 a 66 são os 60 meses. Depois vêm linhas de
resumo acumulado ("Em 12 meses", "Em 24 meses", ... "Em 60 meses"), a linha
**"Após 5 anos"**, e a linha "Total". O parser atual para nos 60 meses.

- [ ] **Passo 1: escrever o teste que falha**

```python
# acrescentar em tests/test_vencimentos.py

def test_cronograma_traz_o_balde_de_apos_5_anos():
    # A aba 3.4 detalha 60 meses e joga o resto num balde unico. Sem ele, o CSV
    # soma 78% do estoque e quem usa nao percebe.
    import pandas as pd
    from tesouro import config

    d = pd.read_csv(config.PROCESSED_DIR / "cronograma_vencimentos.csv")

    detalhado = d[d["faixa"] == "mensal"]
    balde = d[d["faixa"] == "apos_5_anos"]

    assert len(balde) > 0, "o balde 'Apos 5 anos' nao foi capturado"
    assert balde["mes_vencimento"].isna().all(), \
        "o balde nao tem mes; ele agrega tudo depois de 5 anos"

    assert round(detalhado["valor_milhoes"].sum() / 1000, 1) == 6913.8
    assert round(balde["valor_milhoes"].sum() / 1000, 1) == 2006.9
    assert round(d["valor_milhoes"].sum() / 1000, 1) == 8920.7


def test_o_total_do_cronograma_bate_com_o_estoque_do_dpmfi():
    # Cruzamento contra fonte independente: a aba 3.4 e a 2.7 sao interpretadas
    # por parsers diferentes e tem de dar o mesmo estoque.
    import pandas as pd
    from tesouro import config

    cr = pd.read_csv(config.PROCESSED_DIR / "cronograma_vencimentos.csv")
    det = pd.read_csv(config.PROCESSED_DIR / "detentores.csv", parse_dates=["data"])
    ultimo = det[det["data"] == det["data"].max()]["valor_milhoes"].sum()

    assert abs(cr["valor_milhoes"].sum() - ultimo) / ultimo < 0.0001
```

- [ ] **Passo 2: rodar e ver falhar**

```
$env:PYTHONPATH="src"; python -m pytest tests/test_vencimentos.py -k balde -v
```

Esperado: FAIL com `KeyError: 'faixa'` — a coluna ainda não existe.

- [ ] **Passo 3: ler a aba crua para confirmar as posições**

Antes de mexer no parser, confirme onde o balde está. Rode:

```
$env:PYTHONPATH="src"; python -c "import pandas as pd; d = pd.ExcelFile(r'data/raw/rmd/Anexo RMD_Junho_26.xlsx').parse('3.4', header=None); [print(i, [str(c)[:22] for c in d.iloc[i].tolist() if str(c) != 'nan']) for i in range(66, 76)]"
```

Esperado: por volta da linha 73 aparece `['Ap\u00f3s 5 anos', ...]` com os valores por
grupo, e na 74 `['Total', ...]`. **Não confie no número da linha:** localize pelo
rótulo, porque a planilha muda de tamanho conforme o mês.

- [ ] **Passo 4: alterar o parser**

Em `parse_cronograma`, depois de montar as linhas mensais, localize a linha cujo
rótulo da primeira coluna, sem acento e em minúsculas, comece com `apos 5 anos` e
emita uma linha por grupo. Acrescente a coluna `faixa` a **todas** as linhas.

```python
def _sem_acento(texto):
    """Compara rotulo do RMD sem depender de acentuacao."""
    import unicodedata
    normal = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in normal if not unicodedata.combining(c)).strip().lower()


def parse_cronograma(xl):
    """Aba 3.4 -- cronograma de vencimentos da DPMFi (retrato).

    A aba detalha 60 meses e joga tudo o que vence depois num balde unico, "Apos 5
    anos". As duas coisas entram no CSV, separadas pela coluna 'faixa': sem o balde
    o arquivo soma 78% do estoque, e quem somar nao percebe.
    """
    bruto = aba(xl, "3.4")
    # ... (o codigo existente que monta as linhas mensais permanece,
    #      acrescentando faixa="mensal" a cada linha)

    linhas = []
    for ...:                       # laco existente dos 60 meses
        linhas.append({
            "data_referencia": referencia,
            "mes_vencimento": mes,
            "grupo_titulo": grupo,
            "valor_milhoes": valor,
            "faixa": "mensal",
        })

    # O balde. Localizado pelo rotulo, nunca pela posicao: a planilha muda de
    # tamanho conforme o mes.
    linha_balde = None
    for i in range(len(bruto)):
        if _sem_acento(bruto.iloc[i, 0]).startswith("apos 5 anos"):
            linha_balde = i
            break
    if linha_balde is None:
        raise LookupError(
            "aba 3.4: linha 'Apos 5 anos' nao encontrada. Ela existe desde que "
            "acompanhamos a aba, e sem ela o CSV soma so os 60 meses detalhados, "
            "cerca de 78% do estoque. Confira se o layout da aba mudou."
        )

    for coluna, grupo in enumerate(GRUPOS, start=1):
        valor = bruto.iloc[linha_balde, coluna]
        if pd.notna(valor):
            linhas.append({
                "data_referencia": referencia,
                "mes_vencimento": None,
                "grupo_titulo": grupo,
                "valor_milhoes": float(valor),
                "faixa": "apos_5_anos",
            })

    return pd.DataFrame(linhas)
```

**Atenção:** `GRUPOS` deve ser a lista de nomes de coluna já usada pelo laço mensal,
na mesma ordem — `["LTN / NTN-F", "LFT", "NTN-B", "NTN-C", "Demais"]`. Se o laço
existente usa outra estrutura, reutilize a dele em vez de criar uma nova.

- [ ] **Passo 5: regerar o CSV e rodar o teste**

```
$env:PYTHONPATH="src"; python -m tesouro.pipeline --sem-coleta
$env:PYTHONPATH="src"; python -m pytest tests/test_vencimentos.py -v
```

Esperado: PASS, com o CSV somando 8.920,7 bi.

- [ ] **Passo 6: confirmar que o erro é visível se o rótulo sumir**

Troque temporariamente `"apos 5 anos"` por `"apos 6 anos"` no parser, rode o
pipeline, e confirme que ele **falha com a mensagem explicativa** em vez de gerar um
CSV incompleto em silêncio. Desfaça a alteração.

- [ ] **Passo 7: rodar a suíte inteira**

```
$env:PYTHONPATH="src"; python -m pytest -q
```

Esperado: 313 passed, 1 skipped.

- [ ] **Passo 8: commit**

```bash
git add src/tesouro/parse_rmd/vencimentos.py tests/test_vencimentos.py
git commit -m "Acrescenta o balde 'Apos 5 anos' ao cronograma de vencimentos"
```

---
