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

## Task 3: Funding — três gráficos das abas 1.1 e 1.2

**Files:**
- Create: `src/tesouro/graficos/funding.py`
- Test: `tests/test_graficos_funding.py`

**Interfaces:**
- Consumes: `estilo.COR`, `estilo.num_br`, `estilo.eixo_anual`, `estilo.aplicar_estilo`.
- Produces:
  - `JANELAS = {"5 anos": 5, "completa": None}`
  - `dados_net(janela=None)` -> DataFrame indexado por data, colunas
    `emissao, resgate, net, mm12, acum12`, em **R$ milhões**.
  - `desenha_net(dados, fig)`
  - `dados_emissao_indexador(janela=None)` -> DataFrame indexado por data, uma
    coluna por indexador, em R$ milhões.
  - `desenha_emissao_indexador(dados, ax)`
  - `dados_emissao_anual(anos=12)` -> DataFrame indexado por ano, uma coluna por
    indexador **em percentual**, mais `total_milhoes`.
  - `desenha_emissao_anual(dados, ax, ano_parcial)`
  - `ultimo_mes_com_emissao()` -> Timestamp

**Fonte:** `funding_por_canal.csv` (`data, esfera, operacao, canal, valor_milhoes`) e
`funding_por_indexador.csv` (`data, esfera, operacao, indexador, valor_milhoes`).
`operacao` é `emissao` ou `resgate`; `esfera` é `DPMFi`, `DPFe` ou `Banco Central`.

**Decisões tomadas com a usuária que o código deve respeitar:**

- **Só `esfera == "DPMFi"`**, escolha explícita dela.
- **Sem média móvel de 3 meses.** A primeira versão tinha MM3 e MM12; ela mandou
  tirar a de 3. Fica o net do mês em barra colorida por sinal e a MM12 por cima.
- **O painel de acumulado usa `interpolate=True`** no preenchimento, senão aparecem
  falhas nos cruzamentos do zero.
- **A emissão anual é por indexador, não por papel.** Ela pediu por papel, viu a
  versão a partir dos leilões e se arrependeu: por indexador a cobertura é 100% do
  RMD contra 93% a 97% dos leilões. A versão por papel é candidata, na Task 10.
- **O total emitido no ano vai como rótulo acima da barra**, porque 100% esconde que
  2018 foram 657 bi e 2025 foram 1.841 bi.
- **O ano parcial leva asterisco** e a data de corte aparece no título.

**A armadilha que motivou o desenho atual:** a primeira versão empilhava emissão e
resgate ao longo de 236 meses, e quem desenhou **leu o próprio gráfico errado**,
achando que a linha do net seguia os resgates. Não seguia — o gráfico é que era
ilegível. Se 236 barras emparelhadas confundem quem as fez, confundem qualquer um.

- [ ] **Passo 1: escrever os testes que falham**

```python
# tests/test_graficos_funding.py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pytest

from tesouro import config
from tesouro.graficos import estilo, funding


@pytest.fixture(scope="module")
def net():
    return funding.dados_net()


def test_o_net_do_ultimo_mes_bate_com_o_medido(net):
    u = net.iloc[-1]
    assert round(u["emissao"] / 1000, 1) == 149.5
    assert round(u["resgate"] / 1000, 1) == 6.1
    assert round(u["net"] / 1000, 1) == 143.4


def test_a_mm12_e_o_acumulado_batem_com_o_medido(net):
    u = net.iloc[-1]
    assert round(u["mm12"] / 1000, 1) == 27.7
    assert round(u["acum12"] / 1000, 1) == 332.3


def test_o_net_e_emissao_menos_resgate_em_toda_linha(net):
    assert len(net) > 200
    assert (net["net"] - (net["emissao"] - net["resgate"])).abs().max() < 1e-6


def test_so_o_dpmfi_entra(net):
    bruto = pd.read_csv(config.PROCESSED_DIR / "funding_por_canal.csv")
    assert set(bruto["esfera"]) > {"DPMFi"}, "o teste so vale se houver outra esfera"
    assert round(net.iloc[-1]["net"] / 1000, 1) == 143.4


def test_a_janela_de_5_anos_corta_mas_preserva_o_ultimo_mes():
    curto = funding.dados_net(janela=5)
    longo = funding.dados_net()
    assert len(curto) < len(longo)
    assert curto.index.max() == longo.index.max()
    assert curto.index.min() >= longo.index.max() - pd.DateOffset(years=5)


def test_a_emissao_por_indexador_do_ultimo_mes_bate():
    u = funding.dados_emissao_indexador().iloc[-1]
    assert round(u["Taxa Flutuante"] / 1000, 1) == 102.6
    assert round(u["Prefixados"] / 1000, 1) == 35.5
    assert round(u["Índice de Preços"] / 1000, 1) == 11.4


def test_a_emissao_anual_em_100_bate_com_o_medido():
    d = funding.dados_emissao_anual()
    assert round(d.loc[2025, "Prefixados"], 1) == 40.3
    assert round(d.loc[2025, "Taxa Flutuante"], 1) == 41.0
    assert round(d.loc[2025, "Índice de Preços"], 1) == 18.6
    assert round(d.loc[2025, "total_milhoes"] / 1000) == 1841
    assert round(d.loc[2024, "Taxa Flutuante"], 1) == 64.9   # o ano da LFT


def test_cada_ano_da_emissao_anual_soma_100():
    d = funding.dados_emissao_anual()
    cols = [c for c in d.columns if c != "total_milhoes"]
    assert (d[cols].sum(axis=1) - 100).abs().max() < 0.01


def test_o_desenho_do_net_nao_tem_media_de_tres_meses():
    estilo.aplicar_estilo()
    fig = plt.figure(figsize=(13, 8))
    funding.desenha_net(funding.dados_net(janela=5), fig)
    rotulos = []
    for ax in fig.axes:
        rotulos += ax.get_legend_handles_labels()[1]
    plt.close(fig)
    assert any("MM12" in r for r in rotulos)
    assert not any("MM3" in r for r in rotulos), "a MM3 saiu por decisao da usuaria"
```

- [ ] **Passo 2: rodar e ver falhar**

```
$env:PYTHONPATH="src"; python -m pytest tests/test_graficos_funding.py -v
```

Esperado: FAIL com `ImportError: cannot import name 'funding'`.

- [ ] **Passo 3: escrever as funções de dado**

```python
# src/tesouro/graficos/funding.py
"""Funding do DPMFi: emissoes, resgates e o liquido, das abas 1.1 e 1.2.

Tres graficos: o net mes a mes com media movel de 12 meses e acumulado de 12 meses;
a emissao bruta por indexador; e a composicao anual da emissao em 100%.

Decisoes tomadas com a usuaria: so a esfera DPMFi; sem media movel de 3 meses; e a
emissao anual por INDEXADOR e nao por papel, porque pela aba 1.2 a cobertura e 100%
da emissao do RMD contra 93% a 97% se viesse dos leiloes.
"""

import pandas as pd

from .. import config
from . import estilo

JANELAS = {"5 anos": 5, "completa": None}

_ORDEM = ["Prefixados", "Índice de Preços", "Taxa Flutuante",
          "Câmbio", "Demais"]

_CHAVE_COR = {"Prefixados": "Prefixado",
              "Índice de Preços": "Indice Precos",
              "Taxa Flutuante": "Taxa Flutuante",
              "Câmbio": "Cambio",
              "Demais": "Demais"}


def _recorta(df, janela):
    """Ultimos 'janela' anos. janela=None devolve a serie inteira."""
    if janela is None:
        return df
    return df[df.index >= df.index.max() - pd.DateOffset(years=janela)]


def dados_net(janela=None):
    """Emissao, resgate e net do DPMFi por mes, em R$ milhoes."""
    f = pd.read_csv(config.PROCESSED_DIR / "funding_por_canal.csv",
                    parse_dates=["data"])
    d = (f[f["esfera"] == "DPMFi"]
         .groupby(["data", "operacao"])["valor_milhoes"].sum()
         .unstack())
    d["net"] = d["emissao"] - d["resgate"]
    d["mm12"] = d["net"].rolling(12).mean()
    d["acum12"] = d["net"].rolling(12).sum()
    return _recorta(d, janela)


def dados_emissao_indexador(janela=None):
    """Emissao bruta do DPMFi por indexador e por mes, em R$ milhoes."""
    f = pd.read_csv(config.PROCESSED_DIR / "funding_por_indexador.csv",
                    parse_dates=["data"])
    e = f[(f["esfera"] == "DPMFi") & (f["operacao"] == "emissao")]
    piv = e.pivot_table(index="data", columns="indexador",
                        values="valor_milhoes", aggfunc="sum").fillna(0.0)
    piv = piv.loc[:, piv.sum() > 0]
    return _recorta(piv[[c for c in _ORDEM if c in piv.columns]], janela)


def dados_emissao_anual(anos=12):
    """Composicao da emissao por indexador, ano a ano, em percentual.

    'total_milhoes' carrega o tamanho do ano: sem ele, 100% esconde que 2018 foram
    657 bi e 2025 foram 1.841 bi.
    """
    f = pd.read_csv(config.PROCESSED_DIR / "funding_por_indexador.csv",
                    parse_dates=["data"])
    e = f[(f["esfera"] == "DPMFi") & (f["operacao"] == "emissao")].copy()
    e["ano"] = e["data"].dt.year
    piv = e.pivot_table(index="ano", columns="indexador",
                        values="valor_milhoes", aggfunc="sum").fillna(0.0)
    piv = piv[piv.index >= piv.index.max() - anos + 1]
    piv = piv.loc[:, piv.sum() > 0]
    total = piv.sum(axis=1)
    saida = (piv.div(total, axis=0) * 100)[[c for c in _ORDEM if c in piv.columns]]
    saida = saida.copy()
    saida["total_milhoes"] = total
    return saida


def ultimo_mes_com_emissao():
    """Data do ultimo mes com emissao, para marcar o ano parcial."""
    f = pd.read_csv(config.PROCESSED_DIR / "funding_por_indexador.csv",
                    parse_dates=["data"])
    return f["data"].max()
```

- [ ] **Passo 4: escrever as funções de desenho**

```python
# continuacao de src/tesouro/graficos/funding.py

def desenha_net(dados, fig):
    """Dois paineis: o net do mes com a MM12, e o acumulado de 12 meses.

    Sem media movel de 3 meses, por decisao da usuaria. O preenchimento de baixo usa
    interpolate=True porque sem isso aparecem falhas nos cruzamentos do zero.
    """
    a1, a2 = fig.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": [2, 1]})

    cores = ["#2ca02c" if v >= 0 else "#d62728" for v in dados["net"]]
    a1.bar(dados.index, dados["net"] / 1000, width=18, color=cores, alpha=0.45,
           label="net do mês")
    a1.plot(dados.index, dados["mm12"] / 1000, color="#1f6feb", lw=2.8, label="MM12")
    a1.axhline(0, color="gray", lw=0.8)
    a1.set_ylabel("R$ bilhões por mês")
    a1.legend(ncol=2, frameon=False, loc="upper left")
    a1.grid(axis="y", alpha=0.25)

    for cond, cor in [(dados["acum12"] >= 0, "#2ca02c"), (dados["acum12"] < 0, "#d62728")]:
        a2.fill_between(dados.index, dados["acum12"] / 1000, 0, where=cond,
                        color=cor, alpha=0.5, interpolate=True)
    a2.plot(dados.index, dados["acum12"] / 1000, color="#444444", lw=1)
    a2.axhline(0, color="gray", lw=0.8)
    a2.set_ylabel("R$ bilhões")
    a2.set_title("Net acumulado de 12 meses", fontsize=10)
    a2.grid(axis="y", alpha=0.25)
    estilo.eixo_anual(a2)


def desenha_emissao_indexador(dados, ax):
    """Barra empilhada da emissao bruta por indexador."""
    base = 0
    for k in dados.columns:
        ax.bar(dados.index, dados[k] / 1000, bottom=base, width=18,
               color=estilo.COR[_CHAVE_COR[k]], label=k)
        base = base + dados[k] / 1000
    ax.set_ylabel("R$ bilhões emitidos")
    ax.legend(ncol=len(dados.columns), frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.08))
    ax.grid(axis="y", alpha=0.25)
    estilo.eixo_anual(ax)


def desenha_emissao_anual(dados, ax, ano_parcial):
    """Barra de 100% por ano, com o total acima e o ano parcial marcado."""
    cols = [c for c in dados.columns if c != "total_milhoes"]
    base = pd.Series(0.0, index=dados.index)
    for k in cols:
        ax.bar(dados.index, dados[k], bottom=base, width=0.72,
               color=estilo.COR[_CHAVE_COR[k]], label=k)
        for x in dados.index:
            h = dados.loc[x, k]
            if h >= 4:
                ax.text(x, base[x] + h / 2, f"{h:.0f}", ha="center", va="center",
                        fontsize=8.5, color="white", weight="bold")
        base = base + dados[k]

    for x in dados.index:
        ax.text(x, 101.5, estilo.num_br(dados.loc[x, "total_milhoes"] / 1000, 0) + " bi",
                ha="center", fontsize=8, color="#444444")

    ax.set_ylim(0, 108)
    ax.set_xticks(list(dados.index))
    ax.set_xticklabels([str(a) if a != ano_parcial else f"{a}*" for a in dados.index])
    ax.set_ylabel("% do financeiro emitido no ano")
    ax.legend(ncol=len(cols), frameon=False, loc="lower center",
              bbox_to_anchor=(0.5, -0.13))
    ax.grid(axis="y", alpha=0.20)
```

- [ ] **Passo 5: rodar e ver passar**

```
$env:PYTHONPATH="src"; python -m pytest tests/test_graficos_funding.py -v
```

Esperado: 9 passed.

- [ ] **Passo 6: confirmar que cada asserção tem dentes**

Para **cada** âncora, quebre a linha de produção que ela protege, rode, confirme a
falha, e desfaça:

- tire o filtro `esfera == "DPMFi"` — `test_so_o_dpmfi_entra` deve falhar;
- troque `rolling(12)` por `rolling(6)` — a âncora da MM12 deve falhar;
- devolva uma linha de MM3 ao desenho — o último teste deve falhar.

**Não pule este passo.** Na entrega 2 apareceram seis testes que afirmavam o
resultado em vez da intenção, e todos passavam com a implementação quebrada.

- [ ] **Passo 7: rodar a suíte inteira e commitar**

```
$env:PYTHONPATH="src"; python -m pytest -q
```

Esperado: 322 passed, 1 skipped.

```bash
git add src/tesouro/graficos/funding.py tests/test_graficos_funding.py
git commit -m "Adiciona os tres graficos de funding"
```

---

## Task 4: Estoque — composição por indexador com a banda do PAF

**Files:**
- Create: `src/tesouro/graficos/paf.py`
- Create: `src/tesouro/graficos/estoque.py`
- Modify: `src/tesouro/graficos/estilo.py` (sobe o corte de janela)
- Modify: `src/tesouro/graficos/funding.py` (usa o corte do estilo; literais viram escape)
- Test: `tests/test_graficos_estoque.py`, e mais dois testes em `tests/test_estilo.py`

**Interfaces:**
- Consumes: `valida_referencia.conferir_paf`, `valida_referencia.caminho_paf`,
  `estilo.COR`, `estilo.recorta`, `estilo.eixo_anual`, `estilo.grade_fina`.
- Produces:
  - `estilo.recorta(df, janela)` — o corte de janela, que sai do `funding.py`.
  - `paf.bandas(indicador, caminho=None)` -> DataFrame indexado por ano, colunas
    `minimo, maximo, minimo_original, maximo_original, realizado`.
  - `paf.COMPOSICAO` -> tupla dos quatro indicadores que particionam a dívida.
  - `estoque.dados_composicao(janela=None)` -> DataFrame indexado por data, uma
    coluna por indexador **em percentual da DPF**, mais `estoque_milhoes`.
  - `estoque.desenha_composicao(dados, bandas, ax)`

**Fonte:** `composicao_dpf.csv` (`data, indexador, valor_milhoes`), 307 meses de
dez/2000 a jun/2026, e `referencia/paf_bandas.csv`, 192 linhas de 2003 a 2026.

**Por que esta tarefa existe.** É o gráfico que a dona do projeto chama de retrato da
gestão: a participação de cada indexador na DPF, mês a mês, com a banda que o PAF
prometeu para cada ano desenhada por cima. E é a primeira vez que a banda aparece —
os gráficos de vencimentos (Task 6) e de prazo médio (Task 7) reusam o mesmo leitor.

**Por que a banda ganha um módulo próprio.** A spec lista um módulo por tema e não
prevê `paf.py`. É desvio consciente: **três gráficos** carregam banda, e a
alternativa é repetir em três lugares a leitura do CSV, a chamada do validador e a
resolução entre banda original e revisada. Um leitor só, testado uma vez.

**Decisões que o código deve respeitar:**

- **História completa por padrão, não 5 anos.** A queda do câmbio de **51,0% em
  set/2002 para 3,7% hoje** é o fato central da gestão da dívida brasileira, e some
  numa janela curta. A janela de 5 anos existe no botão, mas o padrão é a série
  inteira.
- **A banda vigente é a revisada quando existe**, porque é a que valia no fechamento
  do ano; a original vai em linha pontilhada por baixo, para que a mudança de meta
  fique visível em vez de desaparecer.
- **A banda é desenhada ano a ano sobre o gráfico**, não como caixa estática embaixo
  do jeito que o RMD faz.
- **O validador é pré-requisito de execução.** Se `referencia/paf_bandas.csv`
  estiver quebrado, `paf.bandas` **levanta** em vez de desenhar banda errada.

**Armadilhas medidas nesta tarefa:**

1. **Os dois CSVs escrevem o mesmo indexador com nomes diferentes.** A aba 2.1
   grava `"Índice Preços"` e a 1.2 grava `"Índice de Preços"` —
   com "de" no meio. Copiar a lista de nomes do `funding.py` produz uma coluna
   vazia e um gráfico com um indexador faltando.
2. **O `realizado` do PAF não é a nossa medida.** O gráfico desenha a **nossa**
   série, do `composicao_dpf.csv`; a coluna `realizado` do PAF só serve de
   cruzamento contra fonte independente, e é isso que o teste faz.
3. **O ano aberto não tem realizado.** 2026 tem banda e `realizado` vazio. Tratar
   `NaN` como zero desenharia a composição caindo a zero em 2026.
4. **O `funding.py` da Task 3 tem literais acentuados**, contra a restrição global de
   ASCII puro. Esta tarefa fecha isso com um teste que varre o pacote inteiro, em vez
   de conferir arquivo por arquivo à mão.

- [ ] **Passo 1: escrever os testes que falham**

```python
# tests/test_graficos_estoque.py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pytest

from tesouro.graficos import estilo, estoque, paf


# ---------------------------------------------------------------------------
# A banda do PAF
# ---------------------------------------------------------------------------

def test_a_banda_de_2026_do_prefixado_bate_com_a_planilha_do_paf():
    b = paf.bandas("prefixado_pct")
    assert b.loc[2026, "minimo"] == 21.0
    assert b.loc[2026, "maximo"] == 25.0
    # 2026 ainda nao fechou: realizado VAZIO, nunca zero -- zero seria lido como
    # "a participacao do prefixado foi a zero".
    assert pd.isna(b.loc[2026, "realizado"])


def test_a_revisao_de_2025_vira_a_banda_vigente_e_guarda_a_original():
    # O estoque de 2025 foi revisado de 8.100-8.500 para 8.500-8.800. A banda
    # vigente e a revisada, porque e a que valia no fechamento; a original vai por
    # baixo em linha pontilhada, para a mudanca de meta ficar visivel.
    b = paf.bandas("estoque_bilhoes")
    assert b.loc[2025, "minimo"] == 8500.0
    assert b.loc[2025, "maximo"] == 8800.0
    assert b.loc[2025, "minimo_original"] == 8100.0
    assert b.loc[2025, "maximo_original"] == 8500.0
    # Ano sem revisao nao tem original separada.
    assert pd.isna(b.loc[2023, "minimo_original"])


def test_os_oito_anos_revisados_estao_todos_presentes():
    # A aba 5.7 do RMD guarda so quatro revisoes; a planilha do PAF guarda oito.
    # E por isso que a fonte da banda e referencia/paf_bandas.csv e nao a 5.7.
    b = paf.bandas("prefixado_pct")
    revisados = sorted(b.index[b["minimo_original"].notna()])
    assert revisados == [2008, 2015, 2016, 2018, 2020, 2021, 2024, 2025]


def test_o_paf_falha_alto_quando_a_referencia_esta_quebrada(tmp_path):
    # Pre-requisito de execucao: banda quebrada derruba, nunca desenha errado.
    # O percentual escrito como fracao (0,21 em vez de 21) e o erro que um
    # limiar de plausibilidade nao pega -- 0,21 esta entre 0 e 100.
    ruim = tmp_path / "paf_bandas.csv"
    ruim.write_text(
        "ano,versao,indicador,minimo,maximo,realizado\n"
        "2026,original,prefixado_pct,0.21,0.25,\n",
        encoding="ascii",
    )
    with pytest.raises(ValueError) as erro:
        paf.bandas("prefixado_pct", caminho=ruim)
    assert "paf_bandas.csv" in str(erro.value)


# ---------------------------------------------------------------------------
# A composicao
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def comp():
    return estoque.dados_composicao()


def test_a_composicao_de_junho_de_2026_bate_com_o_medido(comp):
    # Conferido contra a pagina do RMD que a dona do projeto forneceu.
    u = comp.iloc[-1]
    assert round(u["Prefixado"], 1) == 21.0
    assert round(u["\u00cdndice Pre\u00e7os"], 1) == 25.9
    assert round(u["Taxa Flutuante"], 1) == 49.3
    assert round(u["C\u00e2mbio"], 1) == 3.7
    assert round(u["estoque_milhoes"] / 1000, 1) == 9268.4


def test_cada_mes_da_composicao_soma_100(comp):
    cols = [c for c in comp.columns if c != "estoque_milhoes"]
    assert len(comp) == 307
    assert (comp[cols].sum(axis=1) - 100).abs().max() < 1e-9


def test_o_cambio_cai_do_pico_de_51_para_37(comp):
    # O fato central da gestao da divida brasileira, e a razao de a serie completa
    # ser o padrao: numa janela de 5 anos ele nao aparece.
    cam = comp["C\u00e2mbio"]
    assert round(cam.max(), 1) == 51.0
    assert cam.idxmax() == pd.Timestamp("2002-09-30")
    assert round(cam.iloc[-1], 2) == 3.74


def test_o_nosso_dado_bate_com_o_realizado_que_o_paf_registra(comp):
    # Cruzamento contra fonte independente: a composicao sai da aba 2.1 pelo nosso
    # parser, e o realizado do PAF foi digitado a mao de outra fonte. De 2011 em
    # diante os dois tem de coincidir.
    #
    # Antes de 2011 divergem em ate 2,8 p.p. na taxa flutuante, e o realizado do
    # PAF soma 97,7 em 2003 em vez de 100 -- o PAF antigo media a DPF de outro
    # jeito. Documentado, nao perseguido (ver a spec, secao 10).
    for indicador, coluna in estoque.BANDA_DE.items():
        b = paf.bandas(indicador)
        for ano in range(2011, 2026):
            fecha = pd.Timestamp(f"{ano}-12-31")
            assert abs(comp.loc[fecha, coluna] - b.loc[ano, "realizado"]) < 0.01, \
                f"{indicador} em {ano}"


def test_o_desenho_traz_a_banda_de_cada_ano_visivel():
    estilo.aplicar_estilo()
    fig, ax = plt.subplots(figsize=(13, 6))
    dados = estoque.dados_composicao(janela=5)
    bandas = {k: paf.bandas(k) for k in paf.COMPOSICAO}
    estoque.desenha_composicao(dados, bandas, ax)
    faixas = list(ax.collections)
    plt.close(fig)
    # Seis anos visiveis (2021 a 2026) vezes quatro indexadores.
    assert len(faixas) == 24


def test_o_desenho_marca_a_banda_original_dos_anos_revisados():
    estilo.aplicar_estilo()
    fig, ax = plt.subplots(figsize=(13, 6))
    dados = estoque.dados_composicao()
    bandas = {k: paf.bandas(k) for k in paf.COMPOSICAO}
    estoque.desenha_composicao(dados, bandas, ax)
    finas = [l for l in ax.lines if l.get_linestyle() == ":"]
    plt.close(fig)
    # Oito anos revisados, quatro indexadores, duas linhas cada (piso e teto).
    assert len(finas) == 64
```

```python
# acrescentar em tests/test_estilo.py

def test_todo_o_pacote_de_graficos_e_ascii():
    # A restricao vale para o pacote inteiro, nao so para o estilo. Conferir
    # arquivo por arquivo a mao nao escala para dez modulos, e o byte acentuado
    # entra sem ninguem ver.
    import pathlib
    from tesouro import graficos

    pasta = pathlib.Path(graficos.__file__).parent
    arquivos = sorted(pasta.glob("*.py"))
    assert len(arquivos) >= 3
    for arquivo in arquivos:
        with open(arquivo, "rb") as f:
            try:
                f.read().decode("ascii")
            except UnicodeDecodeError as erro:
                raise AssertionError(f"{arquivo.name} tem byte nao-ASCII: {erro}")


def test_o_corte_de_janela_preserva_o_ultimo_ponto():
    import pandas as pd
    datas = pd.date_range("2015-01-31", "2026-06-30", freq="ME")
    df = pd.DataFrame({"v": range(len(datas))}, index=datas)
    assert len(estilo.recorta(df, None)) == len(df)
    curto = estilo.recorta(df, 5)
    assert curto.index.max() == df.index.max()
    assert curto.index.min() >= df.index.max() - pd.DateOffset(years=5)
```

- [ ] **Passo 2: rodar e ver falhar**

```
$env:PYTHONPATH="src"; python -m pytest tests/test_graficos_estoque.py tests/test_estilo.py -v
```

Esperado: FAIL com `ImportError: cannot import name 'paf'` nos primeiros, e
`AttributeError: module 'tesouro.graficos.estilo' has no attribute 'recorta'` no
teste de janela.

- [ ] **Passo 3: subir o corte de janela para o estilo**

Acrescente a `estilo.py`:

```python
def recorta(df, janela):
    """Ultimos 'janela' anos de um DataFrame indexado por data.

    janela=None devolve a serie inteira. Mora aqui, e nao em cada modulo de
    grafico, porque nove dos dezesseis graficos aceitam janela e a conta e a
    mesma em todos.
    """
    import pandas as pd
    if janela is None:
        return df
    return df[df.index >= df.index.max() - pd.DateOffset(years=janela)]
```

E em `funding.py`: apague o `_recorta` local, troque as três chamadas por
`estilo.recorta(...)`, e substitua os literais acentuados por escape Unicode:

| era | fica |
|---|---|
| `"Índice de Preços"` | `"\u00cdndice de Pre\u00e7os"` |
| `"Câmbio"` | `"C\u00e2mbio"` |
| `"net do mês"` | `"net do m\u00eas"` |
| `"R$ bilhões por mês"` | `"R$ bilh\u00f5es por m\u00eas"` |
| `"R$ bilhões"` | `"R$ bilh\u00f5es"` |
| `"R$ bilhões emitidos"` | `"R$ bilh\u00f5es emitidos"` |

O mesmo vale para `tests/test_graficos_funding.py`, que também tem
`"Índice de Preços"` acentuado — troque pelo escape. **O teste de ASCII varre
`src/`, não `tests/`**, mas manter os dois no mesmo padrão evita que alguém copie o
literal acentuado de volta para o código.

- [ ] **Passo 4: escrever o leitor da banda**

```python
# src/tesouro/graficos/paf.py
"""A banda do PAF, lida uma vez e desenhada por tres graficos.

O PAF define, para cada ano, um piso e um teto para seis indicadores da divida.
Este modulo devolve essa banda ja resolvida: onde houve revisao no meio do ano, a
banda VIGENTE e a revisada -- e a que valia no fechamento -- e a original fica
guardada a parte, para o desenho traca-la em linha fina por baixo.

O validador de referencia/paf_bandas.csv roda ANTES de qualquer leitura, e o erro
derruba. E decisao da spec (secao 6): banda quebrada nao vira grafico com banda
errada, que e o defeito que ninguem enxerga olhando a figura.
"""

import pandas as pd

from .. import valida_referencia

# Os quatro que particionam a divida. O estoque e o prazo medio tambem tem banda,
# mas nao sao participacao e nao entram no grafico de composicao.
COMPOSICAO = ("prefixado_pct", "indice_precos_pct",
              "taxa_flutuante_pct", "cambio_pct")

_COLUNAS = ["minimo", "maximo", "minimo_original", "maximo_original", "realizado"]


def bandas(indicador, caminho=None):
    """Banda ano a ano de um indicador, resolvida entre original e revisada.

    'minimo'/'maximo' sao a banda vigente no fechamento do ano. Nos anos revisados,
    'minimo_original'/'maximo_original' guardam a que foi substituida; nos demais
    ficam vazias. 'realizado' fica vazio no ano que ainda nao fechou -- nunca zero,
    que seria lido como "a participacao foi a zero".
    """
    if indicador not in valida_referencia.INDICADORES:
        raise ValueError(
            f"indicador '{indicador}' nao e um dos seis do PAF: "
            f"{list(valida_referencia.INDICADORES)}"
        )

    caminho = caminho or valida_referencia.caminho_paf()
    erros = valida_referencia.conferir_paf(caminho)
    if erros:
        raise ValueError(
            f"{caminho.name} esta invalido e o dashboard nao desenha banda "
            f"suspeita. {len(erros)} problema(s):\n" + "\n".join(erros)
        )

    tudo = pd.read_csv(caminho)
    d = tudo[tudo["indicador"] == indicador]
    orig = d[d["versao"] == "original"].set_index("ano").sort_index()
    rev = d[d["versao"] == "revisado"].set_index("ano").sort_index()

    saida = pd.DataFrame(index=orig.index, columns=_COLUNAS, dtype=float)
    saida["minimo"] = orig["minimo"]
    saida["maximo"] = orig["maximo"]
    saida["realizado"] = orig["realizado"]

    for ano in rev.index:
        saida.loc[ano, "minimo_original"] = orig.loc[ano, "minimo"]
        saida.loc[ano, "maximo_original"] = orig.loc[ano, "maximo"]
        saida.loc[ano, "minimo"] = rev.loc[ano, "minimo"]
        saida.loc[ano, "maximo"] = rev.loc[ano, "maximo"]

    return saida
```

- [ ] **Passo 5: escrever o gráfico da composição**

```python
# src/tesouro/graficos/estoque.py
"""Composicao da DPF por indexador, com a banda do PAF por cima.

O retrato da gestao: quanto da divida esta em cada indexador, mes a mes desde
dez/2000, contra o que o PAF prometeu para cada ano.

A serie completa e o padrao, e nao os 5 anos: o cambio sai de 51,0% em set/2002
para 3,7% hoje, e essa queda -- que e o fato central da gestao da divida brasileira
-- nao existe dentro de uma janela curta.

ARMADILHA: a aba 2.1 grava o indexador como "Indice Precos" e a aba 1.2, que
alimenta o funding.py, grava "Indice de Precos", com "de" no meio. Copiar a lista
de nomes de la deixa uma coluna vazia e um indexador fora do grafico.
"""

import pandas as pd

from .. import config
from . import estilo

JANELAS = {"5 anos": 5, "completa": None}

_ORDEM = ["Prefixado", "\u00cdndice Pre\u00e7os", "Taxa Flutuante",
          "C\u00e2mbio", "Demais"]

_CHAVE_COR = {"Prefixado": "Prefixado",
              "\u00cdndice Pre\u00e7os": "Indice Precos",
              "Taxa Flutuante": "Taxa Flutuante",
              "C\u00e2mbio": "Cambio",
              "Demais": "Demais"}

# Qual banda do PAF corresponde a qual coluna do nosso CSV.
BANDA_DE = {"prefixado_pct": "Prefixado",
            "indice_precos_pct": "\u00cdndice Pre\u00e7os",
            "taxa_flutuante_pct": "Taxa Flutuante",
            "cambio_pct": "C\u00e2mbio"}


def dados_composicao(janela=None):
    """Participacao de cada indexador na DPF, em percentual, mes a mes.

    'estoque_milhoes' viaja junto porque o percentual sozinho nao diz que a divida
    saiu de 654 bi para 9.268 bi no mesmo periodo.
    """
    c = pd.read_csv(config.PROCESSED_DIR / "composicao_dpf.csv",
                    parse_dates=["data"])
    piv = c.pivot_table(index="data", columns="indexador",
                        values="valor_milhoes", aggfunc="sum").fillna(0.0)
    total = piv.sum(axis=1)
    share = piv.div(total, axis=0) * 100
    share = share[[k for k in _ORDEM if k in share.columns]].copy()
    share["estoque_milhoes"] = total
    return estilo.recorta(share, janela)


def desenha_composicao(dados, bandas, ax):
    """Uma linha por indexador, com a banda do PAF desenhada ano a ano.

    A banda vai por cima do proprio grafico, ano a ano, e nao como caixa estatica
    embaixo do jeito que o RMD faz: assim da para ver, em cada ano, se o realizado
    ficou dentro ou fora do que foi prometido.

    Nos anos revisados a banda original aparece em linha pontilhada por baixo, para
    que a mudanca de meta nao desapareca.
    """
    visiveis = range(dados.index.min().year, dados.index.max().year + 1)

    for indicador, coluna in BANDA_DE.items():
        b = bandas[indicador]
        cor = estilo.COR[_CHAVE_COR[coluna]]
        for ano in visiveis:
            if ano not in b.index:
                continue
            inicio = pd.Timestamp(year=ano, month=1, day=1)
            fim = pd.Timestamp(year=ano, month=12, day=31)
            ax.fill_between([inicio, fim],
                            b.loc[ano, "minimo"], b.loc[ano, "maximo"],
                            color=cor, alpha=0.12, linewidth=0, zorder=1)
            if pd.notna(b.loc[ano, "minimo_original"]):
                for nivel in ("minimo_original", "maximo_original"):
                    ax.plot([inicio, fim], [b.loc[ano, nivel]] * 2,
                            color=cor, lw=0.8, ls=":", zorder=2)

    for coluna in [c for c in dados.columns if c != "estoque_milhoes"]:
        if coluna == "Demais":
            continue                     # nunca passa de 0,06% da DPF
        ax.plot(dados.index, dados[coluna], lw=2.2,
                color=estilo.COR[_CHAVE_COR[coluna]], label=coluna, zorder=3)
        ax.annotate(estilo.num_br(dados[coluna].iloc[-1], 1),
                    xy=(dados.index[-1], dados[coluna].iloc[-1]),
                    xytext=(6, 0), textcoords="offset points",
                    fontsize=9, color=estilo.COR[_CHAVE_COR[coluna]],
                    va="center", weight="bold")

    ax.set_ylabel("% da DPF")
    ax.set_ylim(0, 60)
    estilo.grade_fina(ax, 10, 5)
    estilo.eixo_anual(ax, a_cada=2)
    ax.legend(ncol=4, frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.08))
```

- [ ] **Passo 6: rodar e ver passar**

```
$env:PYTHONPATH="src"; python -m pytest tests/test_graficos_estoque.py tests/test_estilo.py -v
```

Esperado: 10 passed no arquivo do estoque e 7 no do estilo.

- [ ] **Passo 7: confirmar que cada asserção tem dentes**

Para **cada** âncora, quebre a linha de produção que ela protege, rode, confirme a
falha, e desfaça:

- apague o laço `for ano in rev.index:` do `paf.bandas` —
  `test_a_revisao_de_2025_vira_a_banda_vigente_e_guarda_a_original` deve falhar;
- troque `versao == "revisado"` por `== "original"` — o teste dos oito anos
  revisados deve falhar;
- devolva `[]` em vez de levantar quando `conferir_paf` acusa erro — o teste do
  arquivo quebrado deve falhar;
- troque `div(total, axis=0)` por `div(total.iloc[-1])` — a âncora de junho e a
  soma de 100 devem falhar;
- apague o bloco do `fill_between` — o teste das 24 bandas deve falhar;
- apague as duas linhas do `ls=":"` — o teste das 64 linhas finas deve falhar;
- **cole um byte acentuado** dentro de um comentário de `estoque.py` —
  `test_todo_o_pacote_de_graficos_e_ascii` deve falhar apontando o arquivo.

**Um caso em que a asserção não tem dentes, e fica registrado:** trocar `alpha=0.12`
por `alpha=0` no `fill_between` mantém as 24 coleções e o teste **passa**. Aquele
teste protege a *contagem* de bandas, não a visibilidade delas. Ninguém deve achar
que ele cobre mais do que cobre.

- [ ] **Passo 8: rodar a suíte inteira e commitar**

```
$env:PYTHONPATH="src"; python -m pytest -q
```

Esperado: 333 passed, 1 skipped.

```bash
git add src/tesouro/graficos/ tests/test_graficos_estoque.py tests/test_estilo.py tests/test_graficos_funding.py
git commit -m "Adiciona a composicao do estoque com a banda do PAF"
```

---
