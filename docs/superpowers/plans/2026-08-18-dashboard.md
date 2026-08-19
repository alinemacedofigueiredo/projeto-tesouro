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
- **Ao gravar `.py` por script, use `newline="
"` explícito** e construa o escape
  Unicode em tempo de execução (`chr(92) + "u%04x" % ord(c)`). Sem o primeiro, o
  Windows traduz `
` para `

` e a leitura seguinte dobra todas as linhas em
  branco; sem o segundo, a camada que grava interpreta o `ç` de volta para o
  byte acentuado. **As duas coisas aconteceram** ao executar as tarefas 1 a 5. O
  caminho seguro é gerar os arquivos a partir dos blocos deste plano, que é o que
  `scratchpad/gera_do_plano.py` faz.
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
  `aplicar_estilo()`, `salvar_svg(fig, destino)`, `eixo_anual(ax, a_cada=1)`,
  `grade_fina(ax, maior, menor)`.

**Por que esta tarefa existe.** Três coisas que, se não forem resolvidas agora,
aparecem espalhadas por dezesseis gráficos: o mês em português (o matplotlib usa a
locale do sistema e sai "may" em vez de "mai"), o número no formato brasileiro, e a
reprodutibilidade do SVG.

**A armadilha da reprodutibilidade tem duas metades, e a segunda só apareceu ao
executar.** A primeira é conhecida: o matplotlib gera identificadores aleatórios
dentro do SVG, e `svg.hashsalt` os fixa. A segunda é invisível — mesmo com o salt
fixo, ele escreve a **data de criação** em `<dc:date>` com precisão de
microssegundo, e dois desenhos do mesmo dado diferem naquela linha, no meio do
cabeçalho RDF. Sai passando `metadata={"Date": None}` no `savefig`.

Por isso o `savefig` não fica solto: existe `estilo.salvar_svg`, que é o único lugar
do projeto que chama `savefig` para SVG. Reprodutibilidade vira propriedade de uma
função, e não convenção que dez chamadas precisam lembrar.

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
        estilo.salvar_svg(fig, buf)
        plt.close(fig)
        return buf.getvalue()

    assert desenha() == desenha()


def test_o_savefig_cru_nao_e_reprodutivel_e_por_isso_o_helper_existe():
    # O hashsalt sozinho nao basta: o matplotlib escreve a data de criacao em
    # <dc:date> com precisao de microssegundo. Este teste guarda o motivo de
    # salvar_svg existir -- se um dia o matplotlib parar de escrever a data, ele
    # falha e alguem descobre que o helper virou desnecessario.
    estilo.aplicar_estilo()

    def desenha(com_helper):
        buf = io.StringIO()
        fig, ax = plt.subplots()
        ax.plot([1, 2, 3], [4, 5, 6])
        if com_helper:
            estilo.salvar_svg(fig, buf)
        else:
            fig.savefig(buf, format="svg", bbox_inches="tight")
        plt.close(fig)
        return buf.getvalue()

    cru = desenha(False)
    assert "<dc:date>" in cru
    assert "<dc:date>" not in desenha(True)


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


def salvar_svg(figura, destino, bbox_inches="tight"):
    """Grava a figura em SVG de forma REPRODUTIVEL.

    Duas coisas fazem o SVG do matplotlib mudar entre execucoes com o mesmo dado.
    A primeira sao os identificadores internos, que o svg.hashsalt de
    aplicar_estilo() fixa. A segunda e a data de criacao, que ele escreve em
    <dc:date> com precisao de microssegundo -- e essa so sai passando
    metadata={"Date": None} no savefig.

    O helper existe porque a segunda parte e invisivel: com o hashsalt fixo e sem
    isto, dois desenhos do mesmo dado diferem em UMA linha, no meio do cabecalho
    RDF, e quem comparar dois dashboards vai achar que o dado mudou. Aqui
    reprodutibilidade e propriedade de uma funcao, nao convencao que todo mundo
    precisa lembrar em cada savefig.
    """
    figura.savefig(destino, format="svg", bbox_inches=bbox_inches,
                   metadata={"Date": None})


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

- [ ] **Passo 5: rodar, ver falhar de novo, e entender por que**

O teste de ASCII e o de reprodutibilidade ainda falham, e cada um por um motivo:

- **`test_o_modulo_e_ascii_puro`:** os meses por extenso tem acento. Troque por
  escape Unicode. Cuidado: escrever `\u00e7` a mao num editor que
  interpreta escapes grava o byte acentuado de volta. Confira com
  `python -c "open('src/tesouro/graficos/estilo.py','rb').read().decode('ascii')"`.
- **`test_o_svg_e_reprodutivel`:** e a segunda metade da armadilha. Rode o diff
  entre dois desenhos e confirme que a unica linha diferente e o `<dc:date>` --
  e so entao escreva o `salvar_svg`. Ver com o proprio olho qual linha muda vale
  mais do que aceitar a explicacao pronta.

- [ ] **Passo 6: rodar e ver passar**

```
$env:PYTHONPATH="src"; python -m pytest tests/test_estilo.py -v
```

Esperado: 6 passed.

- [ ] **Passo 7: rodar a suíte inteira**

```
$env:PYTHONPATH="src"; python -m pytest -q
```

Esperado: 312 passed, 1 skipped.

- [ ] **Passo 8: commit**

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
**"Após 5 anos"** (linha 73 no anexo de jun/26), e a linha "Total". O parser atual
para nos 60 meses.

**A amostra de teste também para antes.** `tests/fixtures/rmd_amostra.xlsx` corta a
aba em 40 linhas, então o balde não está lá — e sem esticar a amostra o teste falha
por motivo errado. É o Passo 3b.

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

- [ ] **Passo 3b: esticar a amostra de teste ate o balde**

Os testes do parser rodam contra `tests/fixtures/rmd_amostra.xlsx`, nao contra o
anexo real. O gerador corta a aba 3.4 em **40 linhas** e o balde esta na **73**: sem
esticar, o parser novo levanta `LookupError` na amostra e o teste falha por motivo
errado.

Em `tests/fixtures/gerar_fixtures.py`, acrescente `"3.4": 80` a `LINHAS_POR_ABA`,
com o comentario explicando por que — no mesmo lugar em que a 2.1, a 3.1 e a 5.7 ja
explicam os cortes delas. Depois regere:

```
python tests/fixtures/gerar_fixtures.py
```

- [ ] **Passo 3c: acertar os dois testes que ja existiam**

Dois testes do arquivo falam do formato antigo e passam a falhar:

- `test_cronograma_usa_data_de_referencia_e_nao_data` afirma as **quatro** colunas;
  passa a afirmar cinco, com `faixa`;
- `test_cronograma_olha_para_frente` compara `mes_vencimento` com a data de
  referencia, e o balde nasce **sem mes**. Filtre por `faixa == "mensal"`, com o
  comentario dizendo por que o balde fica de fora.

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

Esperado: 314 passed, 1 skipped.

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

Esperado: 323 passed, 1 skipped.

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
    `minimo, maximo, minimo_original, maximo_original`.
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
2. **Da planilha do PAF sai a banda, e só.** A coluna `realizado` daquele arquivo
   **não é lida por nada** — decisão da dona do projeto. O que aconteceu sai do
   `composicao_dpf.csv`, que o nosso parser produz e os testes já cobrem; ler o
   realizado de uma tabela digitada à mão seria trocar dado verificado por dado
   redigitado, para desenhar o mesmo ponto.
3. **O `funding.py` da Task 3 tem literais acentuados**, contra a restrição global de
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
    # Da planilha do PAF sai a banda, e so: o que aconteceu vem do nosso dado.
    assert "realizado" not in b.columns


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

Da planilha sai a BANDA, e so: a coluna 'realizado' nao e devolvida, porque o que
aconteceu ja esta no nosso proprio dado.

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

_COLUNAS = ["minimo", "maximo", "minimo_original", "maximo_original"]


def bandas(indicador, caminho=None):
    """Banda ano a ano de um indicador, resolvida entre original e revisada.

    'minimo'/'maximo' sao a banda vigente no fechamento do ano. Nos anos revisados,
    'minimo_original'/'maximo_original' guardam a que foi substituida; nos demais
    ficam vazias.

    A coluna 'realizado' do arquivo NAO e devolvida. O que aconteceu sai do nosso
    proprio dado, que o parser produz e os testes cobrem; ler o realizado de uma
    tabela digitada a mao seria trocar dado verificado por dado redigitado.
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

Esperado: 9 passed no arquivo do estoque e 8 no do estilo.

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

**Dois casos em que a asserção não tem dentes, e ficam registrados:**

- trocar `alpha=0.12` por `alpha=0` no `fill_between` mantém as 24 coleções e o teste
  **passa**. Aquele teste protege a *contagem* de bandas, não a visibilidade delas;
- trocar `div(total, axis=0)` por `div(total.iloc[-1])` **não** faz a âncora de junho
  falhar — dividir pelo total do último mês dá o mesmo resultado *no último mês*. Quem
  pega é `test_cada_mes_da_composicao_soma_100`, que olha os 307. Medido ao executar:
  a âncora sozinha não cobre o erro que ela parece cobrir.

- [ ] **Passo 8: rodar a suíte inteira e commitar**

```
$env:PYTHONPATH="src"; python -m pytest -q
```

Esperado: 334 passed, 1 skipped.

```bash
git add src/tesouro/graficos/ tests/test_graficos_estoque.py tests/test_estilo.py tests/test_graficos_funding.py
git commit -m "Adiciona a composicao do estoque com a banda do PAF"
```

---

## Task 5: Detentores — três gráficos das abas 2.7 e 2.8

**Files:**
- Create: `src/tesouro/graficos/detentores.py`
- Modify: `src/tesouro/graficos/estilo.py` (quatro cores novas de detentor)
- Test: `tests/test_graficos_detentores.py`

**Interfaces:**
- Consumes: `estilo.COR`, `estilo.num_br`, `estilo.recorta`, `estilo.eixo_anual`.
- Produces:
  - `JANELAS = {"5 anos": 5, "completa": None}`
  - `dados_participacao()` -> DataFrame indexado pelos **cinco grupos**, colunas
    `hoje_pct, ha12m_pct, var_pp, valor_milhoes`.
  - `desenha_participacao(dados, fig)`
  - `dados_por_papel()` -> DataFrame indexado por título, uma coluna por detentor,
    **em percentual do papel**.
  - `desenha_por_papel(dados, fig)`
  - `dados_financeiro(janela=None)` -> DataFrame indexado por data, uma coluna por
    detentor, em R$ milhões.
  - `ordem_paineis(dados)` -> lista dos oito detentores na ordem dos painéis.
  - `desenha_financeiro(dados, fig)`

**Fonte:** `detentores.csv` (`data, detentor, valor_milhoes`), aba 2.7, 234 meses de
jan/2007 a jun/2026; e `detentores_por_titulo.csv` (`data, detentor, titulo,
valor_milhoes`), aba 2.8, 185 meses de fev/2011 a jun/2026.

**Por que esta tarefa existe.** São os três gráficos de "quem tem a dívida". O
primeiro responde quanto cada grupo carrega e para onde a participação está indo; o
segundo, quem compra cada papel; o terceiro, o tamanho de cada detentor em reais, que
é o que separa "caiu a participação" de "vendeu".

**Decisões tomadas com a usuária que o código deve respeitar:**

- **A participação agrupa os oito detentores da 2.7 em cinco.** Instituições
  Financeiras, Fundos, Previdência e Não-residentes ficam separados; Tesouro Direto,
  Governo, Seguradoras e Outros viram **Demais Grupos**, que soma 13,8%.
- **Rótulo de percentual só nas fatias de 10% ou mais** no gráfico de quem carrega
  cada papel. Abaixo disso o número não cabe e vira sujeira.
- **Escala própria em cada painel** do financeiro por detentor: eles diferem em ordem
  de grandeza (2.833 bi das Instituições Financeiras contra 246 bi do Governo), e uma
  escala comum achata sete dos oito.
- **Tesouro Direto por último**, por ordem de importância, mesmo tendo mais
  financeiro que o Governo.
- **A divergência de 12 meses contra o slide do RMD fica documentada, não
  perseguida.** O nosso dado foi verificado contra a célula crua da aba 2.7 e está
  fiel ao anexo; a origem do número do slide é desconhecida.

**Armadilhas medidas nesta tarefa:**

1. **Os nomes da 2.7 carregam o número da nota de rodapé.** O CSV grava
   `"Instituições Financeiras 1"`, `"Previdência 3"`,
   `"Não-residentes 4"`. Casar por igualdade com o nome limpo não encontra nada,
   e o rótulo do gráfico sai com o dígito pendurado.
2. **As duas abas usam nomes diferentes para o mesmo detentor.** A 2.7 escreve
   `"Não-residentes 4"` e a 2.8 escreve `"Não-residente"`, no singular e sem
   nota. Não dá para cruzar as duas por nome, e nenhum dos dois gráficos deve tentar.
3. **As duas séries não começam juntas:** a 2.7 em jan/2007, a 2.8 em fev/2011.
   Colocar as duas no mesmo eixo sugere um buraco de quatro anos que não existe.
4. **`"Outros"` já é chave de cor de papel.** A paleta é um dicionário só, e o
   detentor "Outros" sobrescreveria o cinza dos papéis se entrasse com o mesmo nome.
   Ele entra como `"Outros Detentores"`, e o mapa `_CHAVE_COR` resolve.
5. **A descontinuidade do Governo em 2012 é dado real**, não defeito: a LFT em poder
   do Governo vai de ~100 bi para 40 e depois a zero, provavelmente mudança de regra.
   Já foi investigada. Não "consertar" com interpolação.

- [ ] **Passo 1: escrever os testes que falham**

```python
# tests/test_graficos_detentores.py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pytest

from tesouro.graficos import detentores, estilo


# ---------------------------------------------------------------------------
# Aba 2.7: participacao relativa e variacao
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def part():
    return detentores.dados_participacao()


def test_a_participacao_de_junho_de_2026_bate_com_o_medido(part):
    # Conferido contra a pagina do RMD que a dona do projeto forneceu.
    assert round(part.loc["Inst. Financeiras", "hoje_pct"], 1) == 31.8
    assert round(part.loc["Fundos", "hoje_pct"], 1) == 22.0
    assert round(part.loc["Previd\u00eancia", "hoje_pct"], 1) == 22.5
    assert round(part.loc["N\u00e3o-residentes", "hoje_pct"], 1) == 10.0
    assert round(part.loc["Demais Grupos", "hoje_pct"], 1) == 13.8
    assert round(part["valor_milhoes"].sum() / 1000, 1) == 8920.7


def test_os_cinco_grupos_somam_100(part):
    assert len(part) == 5
    assert abs(part["hoje_pct"].sum() - 100) < 1e-9
    assert abs(part["ha12m_pct"].sum() - 100) < 1e-9


def test_a_variacao_de_12_meses_bate_com_o_medido(part):
    # Em pontos percentuais, contra jun/2025. A Previdencia perdeu 0,57 p.p. e as
    # Instituicoes Financeiras ganharam 0,46 -- o movimento do ano.
    assert round(part.loc["Previd\u00eancia", "var_pp"], 2) == -0.57
    assert round(part.loc["Inst. Financeiras", "var_pp"], 2) == 0.46
    assert round(part.loc["Fundos", "var_pp"], 2) == -0.14
    assert round(part.loc["N\u00e3o-residentes", "var_pp"], 2) == 0.11
    assert round(part.loc["Demais Grupos", "var_pp"], 2) == 0.13
    # A variacao e redistribuicao: a soma fecha em zero.
    assert abs(part["var_pp"].sum()) < 1e-9


def test_o_rotulo_perde_o_numero_da_nota_de_rodape(part):
    # O CSV grava "Instituicoes Financeiras 1", com o numero da nota do RMD colado
    # no nome. Nenhum indice pode carregar digito.
    for nome in part.index:
        assert not nome[-1].isdigit(), f"'{nome}' ainda tem o numero da nota"


# ---------------------------------------------------------------------------
# Aba 2.8: quem carrega cada papel
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def papel():
    return detentores.dados_por_papel()


def test_quem_carrega_cada_papel_bate_com_o_medido(papel):
    # Os quatro fatos que o grafico existe para mostrar: a LFT e de banco e fundo,
    # a NTN-B e da previdencia, e o estrangeiro esta na ponta prefixada.
    assert round(papel.loc["LFT", "Inst. Financeiras"], 1) == 36.5
    assert round(papel.loc["LFT", "Fundos"], 1) == 33.0
    assert round(papel.loc["NTN-B", "Previd\u00eancia"], 1) == 44.9
    assert round(papel.loc["NTN-F", "N\u00e3o-residente"], 1) == 41.8
    assert round(papel.loc["LTN", "N\u00e3o-residente"], 1) == 26.4


def test_cada_papel_soma_100_entre_os_detentores(papel):
    assert sorted(papel.index) == ["LFT", "LTN", "NTN-B", "NTN-F", "OUTROS"]
    assert (papel.sum(axis=1) - 100).abs().max() < 1e-9


# ---------------------------------------------------------------------------
# Aba 2.8: financeiro por detentor, oito paineis
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def fin():
    return detentores.dados_financeiro()


def test_o_financeiro_por_detentor_bate_com_o_medido(fin):
    u = fin.iloc[-1]
    assert round(u["Inst. Financeiras"] / 1000, 1) == 2833.5
    assert round(u["Previd\u00eancia"] / 1000, 1) == 2008.8
    assert round(u["Fundos"] / 1000, 1) == 1962.6
    assert round(u["Tesouro Direto"] / 1000, 1) == 262.5
    assert round(u.sum() / 1000, 1) == 8920.7
    # A 2.8 comeca em fev/2011, quatro anos depois da 2.7. As duas series nao sao
    # a mesma coisa e nao vao para o mesmo eixo.
    assert fin.index.min() == pd.Timestamp("2011-02-28")


def test_o_tesouro_direto_fica_por_ultimo_nos_paineis(fin):
    ordem = detentores.ordem_paineis(fin)
    assert len(ordem) == 8
    assert ordem[-1] == "Tesouro Direto"
    assert ordem[0] == "Inst. Financeiras"
    # Ordem de tamanho, com o Tesouro Direto forcado para o fim mesmo tendo mais
    # financeiro que o Governo (262,5 bi contra 245,5).
    assert ordem[-2] == "Governo"


def test_cada_painel_tem_escala_propria(fin):
    estilo.aplicar_estilo()
    fig = plt.figure(figsize=(13, 9))
    detentores.desenha_financeiro(detentores.dados_financeiro(janela=5), fig)
    topos = [round(ax.get_ylim()[1]) for ax in fig.axes]
    plt.close(fig)
    assert len(topos) == 8
    # Escala comum achataria sete dos oito: o maior detentor tem onze vezes o
    # menor. Se todos os topos forem iguais, a escala virou comum sem ninguem ver.
    assert len(set(topos)) >= 6


def test_o_rotulo_de_percentual_so_aparece_nas_fatias_de_10_ou_mais(papel):
    estilo.aplicar_estilo()
    fig = plt.figure(figsize=(13, 7))
    detentores.desenha_por_papel(papel, fig)
    escritos = []
    for ax in fig.axes:
        for t in ax.texts:
            texto = t.get_text().replace("%", "").replace(",", ".")
            try:
                escritos.append(float(texto))
            except ValueError:
                pass                      # titulo do painel, nao rotulo de fatia
    plt.close(fig)
    assert escritos, "nenhum rotulo de percentual foi desenhado"
    assert min(escritos) >= 10.0
    # E as fatias grandes tem de estar todas la: cinco papeis, e cada um tem pelo
    # menos duas fatias de 10% ou mais.
    assert len(escritos) == sum((papel >= 10).sum())


def test_a_paleta_cobre_os_oito_detentores_da_28(fin):
    for detentor in fin.columns:
        chave = detentores.CHAVE_COR[detentor]
        assert chave in estilo.COR, f"sem cor para '{detentor}'"
    # "Outros" ja e chave de cor de papel: o detentor entra com nome proprio para
    # nao sobrescrever o cinza dos papeis.
    assert detentores.CHAVE_COR["Outros"] == "Outros Detentores"
    assert estilo.COR["Outros Detentores"] != estilo.COR["Outros"]
```

- [ ] **Passo 2: rodar e ver falhar**

```
$env:PYTHONPATH="src"; python -m pytest tests/test_graficos_detentores.py -v
```

Esperado: FAIL com `ImportError: cannot import name 'detentores'`.

- [ ] **Passo 3: acrescentar as quatro cores**

Em `estilo.py`, no bloco de detentores:

```python
    # detentores, na paleta das paginas do RMD
    "Inst. Financeiras": "#1f3864",
    "Fundos": "#3d9be9",
    "Previdencia": "#a6a6a6",
    "Nao-residente": "#ed7d31",
    "Demais Grupos": "#70ad47",
    # os quatro que a aba 2.8 abre e a 2.7 agrupa em "Demais Grupos".
    # "Outros Detentores" tem nome proprio porque "Outros" ja e a chave do
    # cinza dos papeis, e a paleta e um dicionario so.
    "Governo": "#8c6d31",
    "Seguradoras": "#b07aa1",
    "Tesouro Direto": "#e15759",
    "Outros Detentores": "#bab0ac",
```

- [ ] **Passo 4: escrever as funções de dado**

```python
# src/tesouro/graficos/detentores.py
"""Quem carrega a divida: as abas 2.7 e 2.8.

Tres graficos. A participacao relativa de cada grupo e o quanto ela mudou em doze
meses (2.7); quem compra cada papel (2.8); e o financeiro de cada detentor ao longo
do tempo, em oito paineis (2.8).

As duas abas NAO se cruzam por nome. A 2.7 grava "Nao-residentes 4", com o numero da
nota de rodape colado; a 2.8 grava "Nao-residente", singular e sem nota. Alem disso
a 2.7 comeca em jan/2007 e a 2.8 em fev/2011. Sao duas fontes vizinhas, nao a mesma.

A divergencia de 12 meses contra o slide do RMD e conhecida: o nosso dado foi
conferido contra a celula crua da aba 2.7 e esta fiel ao anexo, e a origem do numero
do slide e desconhecida. Documentada, nao perseguida (ver a spec, secao 10).
"""

import re

import pandas as pd

from .. import config
from . import estilo

JANELAS = {"5 anos": 5, "completa": None}

# Aba 2.7, agrupada em cinco: os quatro grandes, e o resto junto.
ORDEM_GRUPOS = ["Inst. Financeiras", "Fundos", "Previd\u00eancia",
                "N\u00e3o-residentes", "Demais Grupos"]

_GRUPO_DE = {"Institui\u00e7\u00f5es Financeiras": "Inst. Financeiras",
             "Fundos de Investimento": "Fundos",
             "Previd\u00eancia": "Previd\u00eancia",
             "N\u00e3o-residentes": "N\u00e3o-residentes"}

# Do rotulo que aparece na tela para a chave da paleta, que e ASCII.
CHAVE_COR = {"Inst. Financeiras": "Inst. Financeiras",
             "Fundos": "Fundos",
             "Previd\u00eancia": "Previdencia",
             "N\u00e3o-residentes": "Nao-residente",
             "N\u00e3o-residente": "Nao-residente",
             "Demais Grupos": "Demais Grupos",
             "Governo": "Governo",
             "Seguradoras": "Seguradoras",
             "Tesouro Direto": "Tesouro Direto",
             "Outros": "Outros Detentores"}


def _sem_nota(nome):
    """'Instituicoes Financeiras 1' -> 'Instituicoes Financeiras'.

    A aba 2.7 cola o numero da nota de rodape no nome do detentor. Sem tirar, o
    rotulo do grafico sai com o digito e nenhum agrupamento por nome funciona.
    """
    return re.sub(r"\s*\d+$", "", str(nome)).strip()


def dados_participacao():
    """Participacao dos cinco grupos hoje e ha doze meses, e a variacao em p.p."""
    d = pd.read_csv(config.PROCESSED_DIR / "detentores.csv", parse_dates=["data"])
    d["grupo"] = [_GRUPO_DE.get(_sem_nota(n), "Demais Grupos") for n in d["detentor"]]

    piv = d.pivot_table(index="data", columns="grupo",
                        values="valor_milhoes", aggfunc="sum").fillna(0.0)
    share = piv.div(piv.sum(axis=1), axis=0) * 100

    hoje = share.index.max()
    ha12m = hoje - pd.DateOffset(months=12)
    if ha12m not in share.index:
        raise LookupError(
            f"detentores.csv nao tem o mes de {ha12m.date()}, doze meses antes do "
            f"ultimo ({hoje.date()}). A variacao de 12 meses e o segundo painel do "
            f"grafico e nao pode ser calculada contra um mes vizinho em silencio."
        )

    saida = pd.DataFrame(index=ORDEM_GRUPOS)
    saida["hoje_pct"] = share.loc[hoje]
    saida["ha12m_pct"] = share.loc[ha12m]
    saida["var_pp"] = saida["hoje_pct"] - saida["ha12m_pct"]
    saida["valor_milhoes"] = piv.loc[hoje]
    return saida


def dados_por_papel():
    """Participacao de cada detentor dentro de cada papel, em percentual."""
    d = pd.read_csv(config.PROCESSED_DIR / "detentores_por_titulo.csv",
                    parse_dates=["data"])
    u = d[d["data"] == d["data"].max()]
    piv = u.pivot_table(index="titulo", columns="detentor",
                        values="valor_milhoes", aggfunc="sum").fillna(0.0)
    return piv.div(piv.sum(axis=1), axis=0) * 100


def dados_financeiro(janela=None):
    """Financeiro de cada detentor por mes, em R$ milhoes."""
    d = pd.read_csv(config.PROCESSED_DIR / "detentores_por_titulo.csv",
                    parse_dates=["data"])
    piv = d.pivot_table(index="data", columns="detentor",
                        values="valor_milhoes", aggfunc="sum").fillna(0.0)
    return estilo.recorta(piv, janela)


def ordem_paineis(dados):
    """Os oito detentores por tamanho, com o Tesouro Direto forcado para o fim.

    Ordem de importancia, decisao da usuaria: o Tesouro Direto e o menor em
    relevancia para a gestao mesmo tendo mais financeiro que o Governo.
    """
    ultimo = dados.iloc[-1].drop("Tesouro Direto").sort_values(ascending=False)
    return list(ultimo.index) + ["Tesouro Direto"]
```

- [ ] **Passo 5: escrever as funções de desenho**

```python
# continuacao de src/tesouro/graficos/detentores.py

def desenha_participacao(dados, fig):
    """Dois paineis: a participacao de hoje, e a variacao em doze meses."""
    a1, a2 = fig.subplots(1, 2, gridspec_kw={"width_ratios": [2, 1]})

    y = range(len(dados))
    a1.barh(list(y), dados["hoje_pct"],
            color=[estilo.COR[CHAVE_COR[g]] for g in dados.index])
    for i, (g, v) in enumerate(dados["hoje_pct"].items()):
        a1.text(v + 0.4, i, estilo.num_br(v, 1) + "%", va="center", fontsize=9.5)
    a1.set_yticks(list(y))
    a1.set_yticklabels(list(dados.index))
    a1.invert_yaxis()
    a1.set_xlim(0, max(dados["hoje_pct"]) * 1.18)
    a1.set_xlabel("% do estoque em poder do p\u00fablico")
    a1.grid(axis="x", alpha=0.20)

    cores = ["#2ca02c" if v >= 0 else "#d62728" for v in dados["var_pp"]]
    a2.barh(list(y), dados["var_pp"], color=cores, alpha=0.85)
    for i, v in enumerate(dados["var_pp"]):
        desloca = 0.02 if v >= 0 else -0.02
        a2.text(v + desloca, i, estilo.num_br(v, 2), va="center",
                ha="left" if v >= 0 else "right", fontsize=9)
    a2.set_yticks(list(y))
    a2.set_yticklabels([])
    a2.invert_yaxis()
    a2.axvline(0, color="gray", lw=0.8)
    a2.set_xlabel("varia\u00e7\u00e3o em 12 meses (p.p.)")
    a2.grid(axis="x", alpha=0.20)


def desenha_por_papel(dados, fig):
    """Uma rosca por papel, com rotulo so nas fatias de 10% ou mais.

    Abaixo de 10% o numero nao cabe dentro da fatia e vira sujeira -- decisao da
    usuaria depois de ver a versao com todos os rotulos.
    """
    eixos = fig.subplots(1, len(dados.index))
    for ax, papel in zip(eixos, dados.index):
        linha = dados.loc[papel]
        linha = linha[linha > 0]
        ax.pie(linha, startangle=90, counterclock=False,
               colors=[estilo.COR[CHAVE_COR[d]] for d in linha.index],
               wedgeprops={"width": 0.42, "edgecolor": "white", "linewidth": 0.8},
               labels=None,
               autopct=lambda p: estilo.num_br(p, 1) if p >= 10 else "",
               pctdistance=0.79, textprops={"fontsize": 8.5})
        ax.set_title(papel, fontsize=11, weight="bold")

    marcas = [plt_patch(estilo.COR[CHAVE_COR[d]], d) for d in dados.columns]
    fig.legend(handles=marcas, ncol=4, frameon=False, loc="lower center")


def plt_patch(cor, rotulo):
    """Retangulo colorido para a legenda comum das cinco roscas."""
    from matplotlib.patches import Patch
    return Patch(facecolor=cor, label=rotulo)


def desenha_financeiro(dados, fig):
    """Oito paineis, cada um com escala propria.

    Escala comum achataria sete dos oito: as Instituicoes Financeiras tem
    onze vezes o financeiro do Governo. O preco e que os paineis nao sao
    comparaveis entre si a olho, e por isso cada um leva o valor do ultimo mes
    escrito.
    """
    eixos = fig.subplots(2, 4, sharex=True)
    for ax, detentor in zip(eixos.ravel(), ordem_paineis(dados)):
        serie = dados[detentor] / 1000
        cor = estilo.COR[CHAVE_COR[detentor]]
        ax.fill_between(serie.index, serie, 0, color=cor, alpha=0.30)
        ax.plot(serie.index, serie, color=cor, lw=1.8)
        ax.set_title(detentor, fontsize=10, weight="bold")
        ax.set_ylim(0, serie.max() * 1.22)
        ax.text(0.03, 0.90, estilo.num_br(serie.iloc[-1], 0) + " bi",
                transform=ax.transAxes, fontsize=9.5, color=cor, weight="bold")
        ax.grid(axis="y", alpha=0.20)
        estilo.eixo_anual(ax, a_cada=3)
```

- [ ] **Passo 6: rodar e ver passar**

```
$env:PYTHONPATH="src"; python -m pytest tests/test_graficos_detentores.py -v
```

Esperado: 11 passed.

- [ ] **Passo 7: confirmar que cada asserção tem dentes**

Para **cada** âncora, quebre a linha de produção que ela protege, rode, confirme a
falha, e desfaça:

- apague o `_sem_nota` do `dados_participacao` (use `n` cru) — a âncora de junho e o
  teste do rótulo devem falhar, porque tudo cai em "Demais Grupos";
- troque `DateOffset(months=12)` por `months=11` — a âncora da variação deve falhar;
- troque `div(piv.sum(axis=1), axis=0)` por `div(piv.sum().sum())` em
  `dados_por_papel` — a soma de 100 por papel deve falhar;
- apague o `.drop("Tesouro Direto")` do `ordem_paineis` — o teste da ordem deve
  falhar;
- troque `ax.set_ylim(0, serie.max() * 1.22)` por um topo fixo igual em todos —
  `test_cada_painel_tem_escala_propria` deve falhar;
- troque `if p >= 10 else ""` por `if p >= 0 else ""` — o teste do rótulo de 10%
  deve falhar;
- aponte `CHAVE_COR["Outros"]` para `"Outros"` — o último teste deve falhar.

- [ ] **Passo 8: rodar a suíte inteira e commitar**

```
$env:PYTHONPATH="src"; python -m pytest -q
```

Esperado: 345 passed, 1 skipped.

```bash
git add src/tesouro/graficos/ tests/test_graficos_detentores.py
git commit -m "Adiciona os tres graficos de detentores"
```

---

## Task 6: Vencimentos — cronograma com o balde, e as faixas da DPF com banda

**Files:**
- Create: `src/tesouro/graficos/vencimentos.py`
- Test: `tests/test_graficos_vencimentos.py`

**Interfaces:**
- Consumes: `estilo.COR`, `estilo.num_br`, `estilo.rotulo_mes`, `estilo.MES`.
- Produces:
  - `dados_cronograma_anual()` -> DataFrame indexado por ano, com a linha extra
    `"Após 5 anos"`, uma coluna por grupo de título, em R$ milhões.
  - `dados_cronograma_mensal()` -> DataFrame indexado por mês (os 60), uma coluna
    por grupo, em R$ milhões.
  - `ANOS_PARCIAIS` -> tupla dos dois anos das pontas, que têm seis meses.
  - `desenha_cronograma(anual, mensal, fig)`
  - `dados_faixas()` -> DataFrame indexado por data, quatro faixas em percentual.
  - `banda_vincendo_12m()` -> DataFrame indexado por ano, colunas
    `minimo, maximo, realizado`, de 2003 a **2022**.
  - `desenha_faixas(dados, banda, fig)`

**Fonte:** `cronograma_vencimentos.csv` **depois da Task 2** (com o balde e a coluna
`faixa`), somando 8.920,7 bi; `vencimentos_faixa.csv` filtrado em `nivel == "DPF"`,
246 meses de jan/2006 a jun/2026; e `paf_metas.csv`, da aba 5.7, para a banda.

**Por que esta tarefa existe.** São os dois gráficos de "quando isso vence". O
cronograma é a foto de curto prazo, mês a mês pelos próximos cinco anos mais o balde
de tudo que vem depois; as faixas são a série histórica de quanto da dívida está
vencendo em cada horizonte, com a banda que o PAF prometeu para o vincendo em doze
meses.

**Decisões tomadas com a usuária que o código deve respeitar:**

- **O cronograma tem painel anual mais o balde "Após 5 anos"**, e embaixo o detalhe
  mensal com marcas em jan/abr/jul/out e divisória na virada do ano.
- **A composição da DPF por faixa agrupa em quatro:** até 12 meses, de 1 a 2 anos,
  **de 2 a 5 anos** (soma de três faixas do CSV) e acima de 5 anos.
- **A banda vai num painel próprio, embaixo**, sobre a linha do vincendo em 12 meses.
  Desenhar a banda por cima de uma área empilhada de 100% deixaria as duas ilegíveis.

**Armadilhas medidas nesta tarefa:**

1. **Os dois anos das pontas têm seis meses, não doze.** A aba 3.4 detalha de jul/26
   a jun/31, então a barra de 2026 (833,5 bi) é jul–dez e a de 2031 (636,5 bi) é
   jan–jun. Compará-las com 2027 (1.771,9 bi) sem dizer isso é ler o gráfico errado —
   e é o que a própria página do RMD convida a fazer. Vão com asterisco e com a nota
   escrita.
2. **A aba do cronograma é a 3.4, não a 3.1.** A 3.1 é a de faixas, que alimenta o
   outro gráfico desta mesma tarefa. Já confundi as duas num rascunho.
3. **A banda de vincendo em 12 meses acaba em 2022.** A aba 5.7 do anexo de jun/26
   tem quatro blocos e o último termina em "PAF 2022"; não é o nosso parser parando
   cedo. O `referencia/paf_bandas.csv`, que vai até 2026, **não tem este indicador** —
   ele guarda seis, e vincendo não é um deles. Então a banda é desenhada até 2022 e a
   legenda diz isso. Silenciar seria pior: o leitor entende ausência de banda como
   ausência de meta.
4. **A série de faixas da DPF começa em nov/2006, não em 1999 nem em jan/2006.** O
   `vencimentos_faixa.csv` tem DPMFi desde dez/1999; o bloco DPF tem 246 meses a
   partir de jan/2006, mas os **dez primeiros vêm zerados** — a série só começa em
   nov/2006, a mesma data em que a do prazo médio começa. Filtrar por nível depois de
   calcular o percentual mistura os dois níveis; não descartar os dez meses zerados
   faz a divisão dar 0/0 e abre a área empilhada com um buraco.
5. **A diferença de 16,6 bi contra a aba 2.2** é conhecida e travada por teste na
   Task 10, onde o outro gráfico de vencimentos nasce. Não é para conciliar aqui.

- [ ] **Passo 1: escrever os testes que falham**

```python
# tests/test_graficos_vencimentos.py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pytest

from tesouro.graficos import estilo, vencimentos


# ---------------------------------------------------------------------------
# Aba 3.4: o cronograma
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def anual():
    return vencimentos.dados_cronograma_anual()


def test_o_cronograma_anual_bate_com_o_medido(anual):
    por_ano = anual.sum(axis=1) / 1000
    assert round(por_ano[2026], 1) == 833.5
    assert round(por_ano[2027], 1) == 1771.9
    assert round(por_ano[2028], 1) == 1133.2
    assert round(por_ano[2029], 1) == 1315.6
    assert round(por_ano[2030], 1) == 1223.2
    assert round(por_ano[2031], 1) == 636.5


def test_o_balde_entra_no_cronograma_e_o_total_fecha(anual):
    # Sem o balde da Task 2 o grafico mostraria 78% do estoque como se fosse tudo.
    por_ano = anual.sum(axis=1) / 1000
    assert round(por_ano["Ap\u00f3s 5 anos"], 1) == 2006.9
    assert round(por_ano.sum(), 1) == 8920.7


def test_os_dois_anos_das_pontas_sao_parciais(anual):
    # A aba 3.4 detalha jul/26 a jun/31: 2026 e jul-dez e 2031 e jan-jun. Comparar
    # 833,5 com 1.771,9 sem saber disso e ler o grafico errado.
    assert vencimentos.ANOS_PARCIAIS == (2026, 2031)
    mensal = vencimentos.dados_cronograma_mensal()
    meses = mensal.index.to_series().dt.year.value_counts()
    assert meses[2026] == 6
    assert meses[2031] == 6
    assert meses[2027] == 12


def test_o_cronograma_mensal_tem_os_sessenta_meses():
    m = vencimentos.dados_cronograma_mensal()
    total = m.sum(axis=1) / 1000
    assert len(m) == 60
    assert m.index.min() == pd.Timestamp("2026-07-31")
    assert m.index.max() == pd.Timestamp("2031-06-30")
    assert round(total.max(), 1) == 562.8
    assert total.idxmax() == pd.Timestamp("2027-03-31")
    assert round(total[pd.Timestamp("2026-07-31")], 1) == 256.0
    # O balde NAO entra no detalhe mensal: ele nao tem mes.
    assert round(total.sum(), 1) == 6913.8


# ---------------------------------------------------------------------------
# Aba 3.1: as faixas da DPF, com a banda
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def faixas():
    return vencimentos.dados_faixas()


def test_as_faixas_da_dpf_batem_com_o_medido(faixas):
    u = faixas.iloc[-1]
    assert round(u["At\u00e9 12 meses"], 1) == 20.1
    assert round(u["De 1 a 2 anos"], 1) == 14.1
    assert round(u["De 2 a 5 anos"], 1) == 42.2
    assert round(u["Acima de 5 anos"], 1) == 23.6


def test_cada_mes_das_faixas_soma_100(faixas):
    assert len(faixas.columns) == 4
    assert (faixas.sum(axis=1) - 100).abs().max() < 1e-9
    # O bloco DPF da aba 3.1 tem 246 meses, mas os dez primeiros (jan a out/2006)
    # vem ZERADOS -- a serie so comeca de fato em nov/2006, a mesma data em que a
    # do prazo medio comeca. Mantidos, eles viram dez meses somando zero por cento,
    # e a area empilhada abre com um buraco que parece dado faltando.
    assert faixas.index.min() == pd.Timestamp("2006-11-30")
    assert len(faixas) == 236


def test_a_banda_de_vincendo_em_12_meses_para_em_2022():
    # Nao e o parser parando cedo: a aba 5.7 do anexo de jun/26 tem quatro blocos e
    # o ultimo termina em "PAF 2022". E o paf_bandas.csv, que vai ate 2026, guarda
    # seis indicadores e vincendo nao e um deles.
    b = vencimentos.banda_vincendo_12m()
    assert b.index.min() == 2003
    assert b.index.max() == 2022
    assert b.loc[2022, "minimo"] == 19.0
    assert b.loc[2022, "maximo"] == 23.0


def test_o_realizado_do_vincendo_bate_com_o_nosso_dado(faixas):
    # Cruzamento contra fonte independente: a faixa sai da aba 3.1 pelo nosso
    # parser e o realizado sai da 5.7, que e outra aba e outro parser. A tolerancia
    # de 0,05 e o arredondamento com que o proprio RMD imprime o realizado.
    #
    # Este realizado E lido, diferente do de referencia/paf_bandas.csv: ele vem de
    # uma aba do RMD, por parser, e nao de tabela digitada a mao. O cruzamento
    # confere dois parsers nossos um contra o outro, que e o que pega defeito.
    b = vencimentos.banda_vincendo_12m()
    for ano in range(2011, 2023):
        nosso = faixas.loc[pd.Timestamp(f"{ano}-12-31"), "At\u00e9 12 meses"]
        assert abs(nosso - b.loc[ano, "realizado"]) < 0.05, f"vincendo em {ano}"


# ---------------------------------------------------------------------------
# Desenho
# ---------------------------------------------------------------------------

def test_o_desenho_marca_os_dois_anos_parciais():
    estilo.aplicar_estilo()
    fig = plt.figure(figsize=(13, 9))
    vencimentos.desenha_cronograma(vencimentos.dados_cronograma_anual(),
                                   vencimentos.dados_cronograma_mensal(), fig)
    rotulos = [t.get_text() for ax in fig.axes for t in ax.get_xticklabels()]
    plt.close(fig)
    assert "2026*" in rotulos and "2031*" in rotulos
    assert "2027" in rotulos and "2027*" not in rotulos


def test_o_desenho_do_mensal_divide_a_virada_do_ano():
    estilo.aplicar_estilo()
    fig = plt.figure(figsize=(13, 9))
    vencimentos.desenha_cronograma(vencimentos.dados_cronograma_anual(),
                                   vencimentos.dados_cronograma_mensal(), fig)
    # Quatro viradas de ano dentro dos 60 meses: 26/27, 27/28, 28/29, 29/30, 30/31.
    divisorias = [l for ax in fig.axes for l in ax.lines
                  if l.get_linestyle() == "--"]
    plt.close(fig)
    assert len(divisorias) == 5


def test_a_banda_nao_e_desenhada_onde_nao_existe():
    # Depois de 2022 nao ha banda. Um retangulo esticado ate 2026 inventaria meta.
    estilo.aplicar_estilo()
    fig = plt.figure(figsize=(13, 8))
    vencimentos.desenha_faixas(vencimentos.dados_faixas(),
                               vencimentos.banda_vincendo_12m(), fig)
    # So o painel de baixo: o stackplot do de cima tambem cria colecoes, uma por
    # faixa, e contar as duas coisas juntas mede outra coisa.
    faixas_desenhadas = list(fig.axes[1].collections)
    de_cima = list(fig.axes[0].collections)
    plt.close(fig)
    assert len(de_cima) == 4, "as quatro faixas da area empilhada"
    # Uma banda por ano, de 2006 (inicio da nossa serie) a 2022 (fim da banda).
    assert len(faixas_desenhadas) == 17
```

- [ ] **Passo 2: rodar e ver falhar**

```
$env:PYTHONPATH="src"; python -m pytest tests/test_graficos_vencimentos.py -v
```

Esperado: FAIL com `ImportError: cannot import name 'vencimentos'`.

**Se falhar com `KeyError: 'faixa'`,** a Task 2 não foi executada nesta cópia do
repositório. Volte e execute-a: o cronograma sem o balde some com 2.006,9 bi.

- [ ] **Passo 3: escrever as funções de dado**

```python
# src/tesouro/graficos/vencimentos.py
"""Quando a divida vence: as abas 3.4 (cronograma) e 3.1 (faixas).

Dois graficos. O cronograma e a foto de curto prazo -- os 60 meses que a 3.4
detalha, mais o balde "Apos 5 anos" que a Task 2 acrescentou ao parser. As faixas
sao a serie historica de quanto da DPF vence em cada horizonte, com a banda que o
PAF prometeu para o vincendo em doze meses.

ARMADILHA 1: os dois anos das pontas tem SEIS meses. A 3.4 detalha de jul/26 a
jun/31, entao a barra de 2026 e jul-dez e a de 2031 e jan-jun. Comparar 833,5 bi com
os 1.771,9 de 2027 sem saber disso e ler o grafico errado.

ARMADILHA 2: a aba do cronograma e a 3.4; a 3.1 e a de faixas. As duas falam de
vencimento e ja foram confundidas num rascunho.

ARMADILHA 3: a banda de vincendo em 12 meses acaba em 2022, porque a aba 5.7 do
anexo de jun/26 termina em "PAF 2022" -- e o referencia/paf_bandas.csv, que alcanca
2026, guarda seis indicadores e vincendo nao e um deles.
"""

import pandas as pd

from .. import config
from . import estilo

# Os dois anos das pontas do cronograma, que tem seis meses cada.
ANOS_PARCIAIS = (2026, 2031)

_ORDEM_GRUPOS = ["LFT", "LTN / NTN-F", "NTN-B", "NTN-C", "Demais"]

_CHAVE_COR = {"LFT": "LFT", "LTN / NTN-F": "LTN", "NTN-B": "NTN-B",
              "NTN-C": "NTN-C", "Demais": "Outros"}

# As tres faixas do meio viram uma so: "De 2 a 5 anos".
_DE_2_A_5 = ["De 2 a 3 anos", "De 3 a 4 anos", "De 4 a 5 anos"]

ORDEM_FAIXAS = ["At\u00e9 12 meses", "De 1 a 2 anos",
                "De 2 a 5 anos", "Acima de 5 anos"]

_COR_FAIXA = {"At\u00e9 12 meses": "#c00000",
              "De 1 a 2 anos": "#ed7d31",
              "De 2 a 5 anos": "#3d9be9",
              "Acima de 5 anos": "#1f3864"}


def _cronograma():
    d = pd.read_csv(config.PROCESSED_DIR / "cronograma_vencimentos.csv",
                    parse_dates=["data_referencia", "mes_vencimento"])
    if "faixa" not in d.columns:
        raise LookupError(
            "cronograma_vencimentos.csv nao tem a coluna 'faixa'. Ela vem da "
            "Task 2, que acrescentou o balde 'Apos 5 anos' ao parser; sem ela o "
            "grafico mostra 6.913,8 bi -- 78% do estoque -- como se fosse o todo."
        )
    return d


def dados_cronograma_anual():
    """Vencimentos por ano, mais a linha do balde, em R$ milhoes.

    O indice mistura inteiro (os anos) e texto (o balde) de proposito: o balde nao
    tem ano, e dar um a ele -- 2032, digamos -- seria inventar dado. Quem desenha
    trata a ultima posicao como categoria.
    """
    d = _cronograma()
    mensal = d[d["faixa"] == "mensal"].copy()
    mensal["ano"] = mensal["mes_vencimento"].dt.year
    piv = mensal.pivot_table(index="ano", columns="grupo_titulo",
                             values="valor_milhoes", aggfunc="sum").fillna(0.0)

    balde = (d[d["faixa"] == "apos_5_anos"]
             .groupby("grupo_titulo")["valor_milhoes"].sum())
    piv.loc["Ap\u00f3s 5 anos"] = balde

    return piv.fillna(0.0)[[g for g in _ORDEM_GRUPOS if g in piv.columns]]


def dados_cronograma_mensal():
    """Os 60 meses detalhados, em R$ milhoes. O balde nao entra: ele nao tem mes."""
    d = _cronograma()
    mensal = d[d["faixa"] == "mensal"]
    piv = mensal.pivot_table(index="mes_vencimento", columns="grupo_titulo",
                             values="valor_milhoes", aggfunc="sum").fillna(0.0)
    return piv[[g for g in _ORDEM_GRUPOS if g in piv.columns]]


def dados_faixas():
    """Composicao da DPF por horizonte de vencimento, em percentual.

    Quatro faixas: as tres do meio do CSV (2-3, 3-4 e 4-5 anos) viram uma so, porque
    a leitura util e "vence logo, vence em breve, vence no medio, vence longe".
    """
    v = pd.read_csv(config.PROCESSED_DIR / "vencimentos_faixa.csv",
                    parse_dates=["data"])
    dpf = v[v["nivel"] == "DPF"]
    piv = dpf.pivot_table(index="data", columns="faixa",
                          values="valor_milhoes", aggfunc="sum").fillna(0.0)
    piv["De 2 a 5 anos"] = piv[_DE_2_A_5].sum(axis=1)
    piv = piv[ORDEM_FAIXAS]

    # Os dez primeiros meses do bloco DPF (jan a out/2006) vem zerados: a serie so
    # comeca em nov/2006. Sem tirar, a divisao pelo total da 0/0 e a area empilhada
    # abre com dez meses somando zero por cento -- que se le como dado faltando.
    piv = piv[piv.sum(axis=1) > 0]

    return piv.div(piv.sum(axis=1), axis=0) * 100


def banda_vincendo_12m():
    """Banda do PAF para o vincendo em 12 meses, de 2003 a 2022.

    Vem da aba 5.7 (paf_metas.csv) e nao do referencia/paf_bandas.csv, que guarda
    seis indicadores e nao inclui este. Onde ha revisao, vale a revisada -- a que
    estava em vigor no fechamento -- pelo mesmo criterio do modulo paf.
    """
    m = pd.read_csv(config.PROCESSED_DIR / "paf_metas.csv")
    d = m[m["indicador"] == "% Vincendo em 12 meses"]
    orig = d[d["versao"] == "original"].set_index("ano").sort_index()
    rev = d[d["versao"] == "revisado"].set_index("ano").sort_index()

    saida = orig[["minimo", "maximo", "realizado"]].copy()
    for ano in rev.index:
        saida.loc[ano, "minimo"] = rev.loc[ano, "minimo"]
        saida.loc[ano, "maximo"] = rev.loc[ano, "maximo"]
    return saida
```

- [ ] **Passo 4: escrever as funções de desenho**

```python
# continuacao de src/tesouro/graficos/vencimentos.py

def desenha_cronograma(anual, mensal, fig):
    """Painel anual com o balde, e o detalhe mensal embaixo.

    Os dois anos das pontas levam asterisco porque tem seis meses; sem a marca, a
    barra de 2026 parece um ano fraco em vez de meio ano.
    """
    a1, a2 = fig.subplots(2, 1, gridspec_kw={"height_ratios": [1, 1]})

    posicoes = range(len(anual))
    base = pd.Series(0.0, index=anual.index)
    for grupo in anual.columns:
        a1.bar(list(posicoes), anual[grupo] / 1000, bottom=base / 1000, width=0.7,
               color=estilo.COR[_CHAVE_COR[grupo]], label=grupo)
        base = base + anual[grupo]
    for x, total in zip(posicoes, base / 1000):
        a1.text(x, total + 40, estilo.num_br(total, 0), ha="center", fontsize=9)

    a1.set_xticks(list(posicoes))
    a1.set_xticklabels([f"{r}*" if r in ANOS_PARCIAIS else str(r)
                        for r in anual.index])
    a1.set_ylabel("R$ bilh\u00f5es")
    a1.set_title("* 2026 \u00e9 jul\u2013dez e 2031 \u00e9 jan\u2013jun: a aba 3.4 detalha "
                 "60 meses a partir da data-base", fontsize=9, loc="left",
                 color=estilo.COR["neutro"])
    a1.legend(ncol=len(anual.columns), frameon=False, loc="upper right")
    a1.grid(axis="y", alpha=0.25)

    base = pd.Series(0.0, index=mensal.index)
    for grupo in mensal.columns:
        a2.bar(mensal.index, mensal[grupo] / 1000, bottom=base / 1000, width=22,
               color=estilo.COR[_CHAVE_COR[grupo]])
        base = base + mensal[grupo]

    for ano in range(mensal.index.min().year + 1, mensal.index.max().year + 1):
        a2.axvline(pd.Timestamp(year=ano, month=1, day=1), color="gray",
                   lw=0.8, ls="--")

    marcas = [d for d in mensal.index if d.month in (1, 4, 7, 10)]
    a2.set_xticks(marcas)
    a2.set_xticklabels([estilo.rotulo_mes(d) for d in marcas], fontsize=8)
    a2.set_ylabel("R$ bilh\u00f5es por m\u00eas")
    a2.grid(axis="y", alpha=0.25)


def desenha_faixas(dados, banda, fig):
    """Area empilhada de 100% em cima, e o vincendo em 12 meses com a banda embaixo.

    A banda vai no painel de baixo, sozinha: por cima da area de 100% ela e a area
    disputariam o mesmo espaco e nenhuma das duas seria legivel.

    Onde nao ha banda -- de 2023 em diante -- nada e desenhado. Esticar o ultimo
    retangulo ate hoje inventaria uma meta que o PAF nao publicou nesta aba.
    """
    a1, a2 = fig.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": [2, 1]})

    a1.stackplot(dados.index, [dados[f] for f in ORDEM_FAIXAS],
                 labels=ORDEM_FAIXAS,
                 colors=[_COR_FAIXA[f] for f in ORDEM_FAIXAS], alpha=0.9)
    a1.set_ylim(0, 100)
    a1.set_ylabel("% da DPF")
    a1.legend(ncol=4, frameon=False, loc="lower center")

    curto = dados["At\u00e9 12 meses"]
    for ano in range(dados.index.min().year, dados.index.max().year + 1):
        if ano not in banda.index:
            continue
        a2.fill_between([pd.Timestamp(year=ano, month=1, day=1),
                         pd.Timestamp(year=ano, month=12, day=31)],
                        banda.loc[ano, "minimo"], banda.loc[ano, "maximo"],
                        color=estilo.COR["banda"], alpha=0.15, linewidth=0)
    a2.plot(curto.index, curto, color=_COR_FAIXA["At\u00e9 12 meses"], lw=2.2)
    a2.annotate(estilo.num_br(curto.iloc[-1], 1),
                xy=(curto.index[-1], curto.iloc[-1]), xytext=(6, 0),
                textcoords="offset points", fontsize=9, weight="bold",
                color=_COR_FAIXA["At\u00e9 12 meses"], va="center")
    a2.set_ylabel("% vincendo em 12 meses")
    a2.set_title("banda do PAF publicada na aba 5.7 at\u00e9 2022", fontsize=9,
                 loc="left", color=estilo.COR["neutro"])
    estilo.grade_fina(a2, 10, 5)
    estilo.eixo_anual(a2, a_cada=2)
```

- [ ] **Passo 5: rodar e ver passar**

```
$env:PYTHONPATH="src"; python -m pytest tests/test_graficos_vencimentos.py -v
```

Esperado: 11 passed.

- [ ] **Passo 6: confirmar que cada asserção tem dentes**

Para **cada** âncora, quebre a linha de produção que ela protege, rode, confirme a
falha, e desfaça:

- tire o `piv = piv[piv.sum(axis=1) > 0]` — a soma de 100 deve falhar nos dez meses
  zerados de 2006;
- apague a linha `piv.loc["Após 5 anos"] = balde` — o teste do balde deve falhar e o
  total cair para 6.913,8;
- deixe o balde entrar no `dados_cronograma_mensal` (tire o filtro
  `faixa == "mensal"`) — **o teste continua passando**, e isso foi medido. O
  `pivot_table(index="mes_vencimento")` descarta em silêncio as linhas com índice
  vazio, e o balde nasce sem mês: o pandas já faz o trabalho do filtro. O filtro
  fica como declaração de intenção, mas quem lê deve saber que aquela asserção
  protege o **total** de 6.913,8, não o filtro;
- troque `ANOS_PARCIAIS = (2026, 2031)` por `()` — o teste do asterisco deve falhar;
- tire o `if ano not in banda.index: continue` do desenho — o teste das 17 faixas
  deve falhar, porque passaria a desenhar até 2026;
- tire o filtro `nivel == "DPF"` do `dados_faixas` — a âncora de junho e o começo em
  2006 devem falhar;
- troque `_DE_2_A_5` por só `["De 2 a 3 anos"]` — a âncora de 42,2 deve falhar e a
  soma de 100 também;
- troque `range(min.year + 1, max.year + 1)` por `range(min.year, max.year + 1)` na
  divisória — o teste das cinco divisórias deve falhar com seis.

- [ ] **Passo 7: rodar a suíte inteira e commitar**

```
$env:PYTHONPATH="src"; python -m pytest -q
```

Esperado: 356 passed, 1 skipped.

```bash
git add src/tesouro/graficos/vencimentos.py tests/test_graficos_vencimentos.py
git commit -m "Adiciona o cronograma de vencimentos e as faixas da DPF"
```

---

## Task 7: Prazo médio, com a banda do PAF

**Files:**
- Create: `src/tesouro/graficos/prazo.py`
- Test: `tests/test_graficos_prazo.py`

**Interfaces:**
- Consumes: `paf.bandas`, `estilo.COR`, `estilo.num_br`, `estilo.eixo_anual`,
  `estilo.grade_fina`.
- Produces:
  - `dados_prazo()` -> DataFrame indexado por data, colunas `DPF, DPMFi, DPFe`,
    em anos.
  - `COM_ROTULO` -> tupla dos dois níveis que levam rótulo no fim da linha.
  - `desenha_prazo(dados, banda, ax)`

**Fonte:** `prazo_medio_por_titulo.csv`, filtrado nas linhas agregadas (`entidade` e
`titulo` vazios), 237 observações de dez/2005 a jun/2026; e a banda
`prazo_medio_anos` de `referencia/paf_bandas.csv`.

**Por que esta tarefa existe.** O prazo médio é o indicador que a banda do PAF
persegue com mais atenção, e é o mais fácil de ler errado: 4,01 anos parece pouco até
você ver que a DPFe está em 6,93 e a DPMFi em 3,90, e que o número da DPF é a média
das duas ponderada por um estoque que é 96% doméstico.

**Decisões tomadas com a usuária que o código deve respeitar:**

- **Rótulo só na DPMFi e na DPFe; a DPF fica como linha de contexto**, mais fina.
  São os dois números que ela usa; o da DPF é a consequência aritmética dos dois.
- **A banda é do prazo médio da DPF** — que é justamente a linha de contexto. Por
  isso a legenda diz de quem é a banda, em vez de deixar o leitor supor que ela vale
  para a linha mais grossa.

**Armadilhas medidas nesta tarefa:**

1. **As linhas agregadas são as que têm `entidade` e `titulo` vazios.** Filtrar só
   por `nivel == "DPF"` pega também as linhas por título e por entidade, e a média
   sai errada sem nenhum sinal.
2. **A série não é mensal no começo.** Vai de dez/2005 direto para nov/2006 e só
   depois fica mensal — 237 observações em vinte anos e meio, não 247. Qualquer conta
   que suponha espaçamento constante (média móvel por número de linhas, variação em
   "12 posições") erra os dois primeiros anos.
3. **Da planilha do PAF vem só a banda.** O `realizado` que aquele arquivo guarda
   não é lido aqui nem em nenhum outro gráfico: a linha desenhada é a nossa série,
   da aba 3.7. Isso não é detalhe de implementação — ao escrever esta tarefa
   descobrimos que o `realizado` de 2025 naquele arquivo está com o valor de 2024
   repetido (`4.048869` contra os `4.003076` que a aba 3.7 dá). Como nada o lê, o
   erro não vira gráfico errado. Fica registrado para quem for mexer no arquivo.

- [ ] **Passo 1: escrever os testes que falham**

```python
# tests/test_graficos_prazo.py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pytest

from tesouro.graficos import estilo, paf, prazo


@pytest.fixture(scope="module")
def dados():
    return prazo.dados_prazo()


def test_o_prazo_de_junho_de_2026_bate_com_o_medido(dados):
    u = dados.iloc[-1]
    assert round(u["DPF"], 2) == 4.01
    assert round(u["DPMFi"], 2) == 3.90
    assert round(u["DPFe"], 2) == 6.93


def test_as_tres_series_vem_das_linhas_agregadas(dados):
    # As linhas agregadas sao as que tem entidade e titulo vazios. Filtrar so por
    # nivel traz tambem as linhas por titulo, e a media sai errada em silencio.
    assert list(dados.columns) == ["DPF", "DPMFi", "DPFe"]
    assert dados.notna().all().all()
    assert len(dados) == 237
    assert dados.index.min() == pd.Timestamp("2005-12-31")
    # A serie NAO e mensal no comeco: de dez/2005 ela pula para nov/2006.
    assert dados.index[1] == pd.Timestamp("2006-11-30")


def test_a_dpf_fica_sempre_entre_a_dpmfi_e_a_dpfe(dados):
    # Verdade estrutural: a DPF e a media ponderada das duas. Se um mes sair do
    # sanduiche, o filtro pegou linha que nao devia.
    assert (dados["DPMFi"] <= dados["DPF"]).all()
    assert (dados["DPF"] <= dados["DPFe"]).all()


def test_a_banda_do_prazo_medio_bate_com_o_paf():
    b = paf.bandas("prazo_medio_anos")
    assert b.loc[2026, "minimo"] == 3.8
    assert b.loc[2026, "maximo"] == 4.2
    # A linha desenhada e a NOSSA serie; da planilha vem so a banda.
    assert "realizado" not in b.columns


def test_so_a_dpmfi_e_a_dpfe_levam_rotulo(dados):
    estilo.aplicar_estilo()
    fig, ax = plt.subplots(figsize=(13, 6))
    prazo.desenha_prazo(dados, paf.bandas("prazo_medio_anos"), ax)
    rotulados = [a.get_text() for a in ax.texts]
    plt.close(fig)
    assert prazo.COM_ROTULO == ("DPMFi", "DPFe")
    # Os dois valores de junho, e nada mais: 3,90 e 6,93.
    assert sorted(rotulados) == ["3,90", "6,93"]


def test_a_dpf_e_a_linha_de_contexto(dados):
    estilo.aplicar_estilo()
    fig, ax = plt.subplots(figsize=(13, 6))
    prazo.desenha_prazo(dados, paf.bandas("prazo_medio_anos"), ax)
    largura = {l.get_label(): l.get_linewidth() for l in ax.lines}
    plt.close(fig)
    assert largura["DPF"] < largura["DPMFi"]
    assert largura["DPF"] < largura["DPFe"]


def test_a_banda_e_desenhada_ano_a_ano(dados):
    estilo.aplicar_estilo()
    fig, ax = plt.subplots(figsize=(13, 6))
    prazo.desenha_prazo(dados, paf.bandas("prazo_medio_anos"), ax)
    faixas = list(ax.collections)
    plt.close(fig)
    # De 2005 (inicio da serie) a 2026: o paf_bandas.csv cobre 2003 a 2026 com os
    # seis indicadores em todos os anos, entao sao 22 faixas.
    assert len(faixas) == 22


def test_nenhuma_serie_fica_fora_do_eixo(dados):
    # Eixo truncado e a armadilha 7 da spec. Aqui ela apareceria como a DPFe
    # saindo pela borda de cima sem ninguem notar.
    estilo.aplicar_estilo()
    fig, ax = plt.subplots(figsize=(13, 6))
    prazo.desenha_prazo(dados, paf.bandas("prazo_medio_anos"), ax)
    baixo, alto = ax.get_ylim()
    plt.close(fig)
    assert baixo <= dados.min().min()
    assert alto >= dados.max().max()
```

- [ ] **Passo 2: rodar e ver falhar**

```
$env:PYTHONPATH="src"; python -m pytest tests/test_graficos_prazo.py -v
```

Esperado: FAIL com `ImportError: cannot import name 'prazo'`.

- [ ] **Passo 3: escrever a função de dado**

```python
# src/tesouro/graficos/prazo.py
"""Prazo medio da divida, por nivel, com a banda do PAF.

Tres linhas: DPF, DPMFi e DPFe. A DPF e a media ponderada das outras duas, e por
isso fica sempre entre elas -- se algum mes sair do sanduiche, o filtro pegou linha
que nao devia.

ARMADILHA 1: as linhas agregadas do CSV sao as que tem 'entidade' E 'titulo'
vazios. Filtrar so por nivel traz tambem uma linha por titulo (LTN, NTN-B, ...) e
uma por entidade, e a media sai errada sem nenhum sinal.

ARMADILHA 2: a serie nao e mensal no comeco -- vai de dez/2005 direto para nov/2006.
Sao 237 observacoes em vinte anos e meio, nao 247. Conta que suponha espacamento
constante erra os dois primeiros anos.
"""

import pandas as pd

from .. import config
from . import estilo

NIVEIS = ["DPF", "DPMFi", "DPFe"]

# So estes dois levam rotulo no fim da linha: sao os numeros que a usuaria usa. O
# da DPF e consequencia aritmetica dos dois, e fica como contexto.
COM_ROTULO = ("DPMFi", "DPFe")

_COR = {"DPF": estilo.COR["neutro"],
        "DPMFi": "#1f6feb",
        "DPFe": "#ed7d31"}


def dados_prazo():
    """Prazo medio em anos, por nivel e por data."""
    p = pd.read_csv(config.PROCESSED_DIR / "prazo_medio_por_titulo.csv",
                    parse_dates=["data"])
    agregado = p[p["entidade"].isna() & p["titulo"].isna()]
    piv = agregado.pivot_table(index="data", columns="nivel",
                               values="prazo_anos", aggfunc="sum")
    return piv[NIVEIS].dropna(how="all")


def desenha_prazo(dados, banda, ax):
    """As tres linhas, com a banda do PAF da DPF desenhada ano a ano.

    A banda e do prazo medio da DPF -- que e justamente a linha de contexto, a mais
    fina. A legenda diz isso em vez de deixar o leitor supor que ela vale para a
    linha mais grossa.
    """
    for ano in range(dados.index.min().year, dados.index.max().year + 1):
        if ano not in banda.index:
            continue
        inicio = pd.Timestamp(year=ano, month=1, day=1)
        fim = pd.Timestamp(year=ano, month=12, day=31)
        ax.fill_between([inicio, fim], banda.loc[ano, "minimo"],
                        banda.loc[ano, "maximo"], color=estilo.COR["banda"],
                        alpha=0.13, linewidth=0, zorder=1)
        if pd.notna(banda.loc[ano, "minimo_original"]):
            for nivel in ("minimo_original", "maximo_original"):
                ax.plot([inicio, fim], [banda.loc[ano, nivel]] * 2,
                        color=estilo.COR["banda"], lw=0.8, ls=":", zorder=2)

    for nivel in NIVEIS:
        grossura = 2.6 if nivel in COM_ROTULO else 1.3
        ax.plot(dados.index, dados[nivel], color=_COR[nivel], lw=grossura,
                label=nivel, zorder=3)
        if nivel in COM_ROTULO:
            ax.annotate(estilo.num_br(dados[nivel].iloc[-1], 2),
                        xy=(dados.index[-1], dados[nivel].iloc[-1]),
                        xytext=(6, 0), textcoords="offset points",
                        fontsize=9.5, weight="bold", color=_COR[nivel],
                        va="center")

    ax.set_ylabel("anos")
    ax.set_ylim(0, max(8.0, dados.max().max() * 1.08))
    estilo.grade_fina(ax, 1, 0.5)
    estilo.eixo_anual(ax, a_cada=2)
    ax.legend(ncol=3, frameon=False, loc="upper left",
              title="banda: meta do PAF para o prazo m\u00e9dio da DPF")
```

- [ ] **Passo 4: rodar e ver passar**

```
$env:PYTHONPATH="src"; python -m pytest tests/test_graficos_prazo.py -v
```

Esperado: 8 passed.

- [ ] **Passo 5: confirmar que cada asserção tem dentes**

Para **cada** âncora, quebre a linha de produção que ela protege, rode, confirme a
falha, e desfaça:

- tire o `p["titulo"].isna()` do filtro — **nada falha**, e isso foi medido: no
  `prazo_medio_por_titulo.csv` de hoje não existe uma única linha com `entidade`
  vazia e `titulo` preenchido, então `entidade.isna()` sozinho já seleciona as 711
  linhas agregadas. O segundo filtro é defesa contra um layout que ainda não
  apareceu, não uma condição que o dado atual exercite. Fica, e quem lê deve saber
  que nenhum teste o protege;
- troque `COM_ROTULO` por `("DPF",)` — o teste dos rótulos deve falhar;
- iguale as duas grossuras (`grossura = 2.6` sempre) — o teste da linha de contexto
  deve falhar;
- o `if ano not in banda.index: continue` **não tem como ser exercitado aqui**: o
  `paf_bandas.csv` cobre 2003 a 2026 e a série vai de 2005 a 2026, então todo ano
  visível tem banda. A guarda existe para o dia em que a série passar do fim da
  planilha. Quem quiser vê-la funcionando, olhe a Task 6, onde a banda acaba em 2022
  e o teste pega;
- troque `ax.set_ylim(0, ...)` por `ax.set_ylim(0, 4.5)` — o teste do eixo deve
  falhar, porque a DPFe em 6,93 sai pela borda;
- devolva a coluna `realizado` no `paf.bandas` — os dois testes que afirmam
  `"realizado" not in b.columns` (este e o da Task 4) devem falhar. É o que impede
  que a planilha digitada volte a alimentar gráfico sem ninguém decidir isso.

- [ ] **Passo 6: rodar a suíte inteira e commitar**

```
$env:PYTHONPATH="src"; python -m pytest -q
```

Esperado: 364 passed, 1 skipped.

```bash
git add src/tesouro/graficos/prazo.py tests/test_graficos_prazo.py
git commit -m "Adiciona o prazo medio com a banda do PAF"
```

---

## Task 8: Custo do estoque contra a Selic e o IPCA

**Files:**
- Create: `src/tesouro/graficos/custo.py`
- Test: `tests/test_graficos_custo.py`

**Interfaces:**
- Consumes: `estilo.COR`, `estilo.num_br`, `estilo.recorta`, `estilo.eixo_anual`.
- Produces:
  - `JANELAS = {"5 anos": 5, "completa": None}`
  - `variacao_12m_do_vna()` -> DataFrame indexado por data, colunas `SELIC, IPCA`,
    em percentual acumulado em 12 meses.
  - `dados_custo(janela=None)` -> DataFrame indexado por data, colunas
    `DPF, DPMFi, SELIC, IPCA`, em % ao ano.
  - `desenha_custo(dados, ax)`

**Fonte:** `custo_medio.csv`, medida `acum_12m`, linhas agregadas de `DPF` e `DPMFi`,
247 observações de dez/2005 a jun/2026; e `vna.csv`, 198 meses de jan/2010 a jun/2026,
que vem da **entrega 2**.

**Por que esta tarefa existe.** É o gráfico que responde "a dívida está cara?". O
custo do estoque sozinho não responde: 12,68% ao ano é caro ou barato dependendo de
onde estavam a Selic e a inflação. As três linhas juntas mostram que o custo acompanha
a Selic com atraso, porque metade da dívida é LFT e a outra metade foi contratada no
passado.

**A Selic e o IPCA saem do nosso próprio VNA.** A variação de 12 meses do VNA **é** o
índice acumulado: 14,78% e 4,81% em jun/2026. A página do RMD busca isso no site do
Bacen; nós não precisamos, e é por isso que esta branch nasceu de `dv01-decay`.

**Decisões tomadas com a usuária que o código deve respeitar:**

- **Eixo do tempo em marcas anuais, mantendo o dado mensal.** A página do RMD usa
  cerca de 170 rótulos mensais e ninguém lê.
- **Rótulo só no último ponto de cada linha.** Quatro números na borda direita, e
  nada escrito no meio do gráfico.

**Armadilhas medidas nesta tarefa:**

1. **O `custo_medio.csv` tem três medidas na mesma coluna.** `mensal`, `acum_12m` e
   `emissoes_12m`. Este gráfico é o **`acum_12m`**. Pegar `mensal` dá 13,64 para a
   DPF em vez de 12,68 — número plausível, gráfico errado, e nada acusa.
2. **As linhas agregadas são as que têm `entidade` e `titulo` vazios**, a mesma
   armadilha da Task 7. Sem os dois filtros entram as linhas por título.
3. **O VNA é do último dia útil e o custo é do último dia do mês.** O VNA de maio/26
   é 29/05 e o custo é 31/05. **Só 137 das 198 datas do VNA coincidem** com as do
   custo: juntar por data exata perde 61 meses e desenha uma linha picotada que
   parece dado faltando. A junção é por **competência** (ano e mês), não por data.
4. **A variação de 12 meses precisa da série mensal completa.** `shift(12)` conta
   posições, não meses: com um buraco, ele compara contra 13 ou 14 meses atrás sem
   avisar. O VNA tem os 198 meses sem falha, e o teste trava isso.
5. **A Selic e o IPCA só começam em jan/2011** — doze meses depois do início do VNA —
   enquanto o custo começa em dez/2005. Os cinco primeiros anos ficam **vazios**, não
   zerados: zero seria lido como "a Selic foi a zero".

- [ ] **Passo 1: escrever os testes que falham**

```python
# tests/test_graficos_custo.py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pytest

from tesouro import config
from tesouro.graficos import custo, estilo


@pytest.fixture(scope="module")
def dados():
    return custo.dados_custo()


def test_o_custo_de_junho_de_2026_bate_com_o_medido(dados):
    u = dados.iloc[-1]
    assert round(u["DPF"], 2) == 12.68
    assert round(u["DPMFi"], 2) == 13.19


def test_a_selic_e_o_ipca_saem_do_nosso_vna(dados):
    # A variacao de 12 meses do VNA E o indice acumulado. A pagina do RMD busca
    # isso no site do Bacen; nos temos em casa desde a entrega 2.
    u = dados.iloc[-1]
    assert round(u["SELIC"], 2) == 14.78
    assert round(u["IPCA"], 2) == 4.81


def test_a_medida_e_o_acumulado_de_12_meses_e_nao_o_mensal(dados):
    # A medida 'mensal' da 13,64 para a DPF em junho: plausivel, e errado.
    bruto = pd.read_csv(config.PROCESSED_DIR / "custo_medio.csv",
                        parse_dates=["data"])
    mensal = bruto[(bruto["medida"] == "mensal") & (bruto["nivel"] == "DPF")
                   & bruto["entidade"].isna() & bruto["titulo"].isna()]
    valor_mensal = mensal.set_index("data")["custo_aa_pct"].iloc[-1]
    assert round(valor_mensal, 2) == 13.64          # existe, e nao e o nosso
    assert round(dados.iloc[-1]["DPF"], 2) == 12.68


def test_o_vna_e_mensal_e_completo():
    # shift(12) conta posicoes, nao meses: com um buraco na serie a variacao de 12
    # meses compara contra 13 ou 14 meses atras sem avisar.
    v = pd.read_csv(config.PROCESSED_DIR / "vna.csv", parse_dates=["data"])
    meses = v["data"].dt.to_period("M").drop_duplicates().sort_values()
    esperado = pd.period_range(meses.min(), meses.max(), freq="M")
    assert len(meses) == 198
    assert list(meses) == list(esperado), "o VNA tem mes faltando"


def test_a_juncao_e_por_competencia_e_nao_por_data(dados):
    # O VNA e do ultimo dia util e o custo e do ultimo dia do mes: so 137 das 198
    # datas coincidem. Juntar por data exata perde 61 meses.
    v = pd.read_csv(config.PROCESSED_DIR / "vna.csv", parse_dates=["data"])
    coincidem = set(v["data"]) & set(dados.index)
    assert len(coincidem) < 150, "as datas coincidem demais; o teste perdeu sentido"
    # Ainda assim nenhum mes de 2011 em diante fica sem Selic.
    de_2011 = dados[dados.index >= "2011-01-01"]
    assert de_2011["SELIC"].notna().all()
    assert len(de_2011) >= 180


def test_os_indices_ficam_vazios_antes_de_2011_e_nunca_zerados(dados):
    antes = dados[dados.index < "2011-01-01"]
    assert len(antes) > 50
    assert antes["SELIC"].isna().all()
    assert antes["IPCA"].isna().all()
    # Zero seria lido como "a Selic foi a zero".
    assert not (antes["SELIC"] == 0).any()
    # O custo, esse, existe desde dez/2005.
    assert antes["DPF"].notna().all()


def test_a_janela_de_5_anos_corta_mas_preserva_o_ultimo_mes():
    curto = custo.dados_custo(janela=5)
    longo = custo.dados_custo()
    assert len(curto) < len(longo)
    assert curto.index.max() == longo.index.max()
    assert curto.index.min() >= longo.index.max() - pd.DateOffset(years=5)
    assert round(curto.iloc[-1]["DPF"], 2) == 12.68


def test_so_o_ultimo_ponto_de_cada_linha_leva_rotulo(dados):
    estilo.aplicar_estilo()
    fig, ax = plt.subplots(figsize=(13, 6))
    custo.desenha_custo(dados, ax)
    escritos = sorted(a.get_text() for a in ax.texts)
    plt.close(fig)
    # Quatro linhas, quatro numeros, todos na borda direita.
    assert escritos == ["12,68", "13,19", "14,78", "4,81"]
```

- [ ] **Passo 2: rodar e ver falhar**

```
$env:PYTHONPATH="src"; python -m pytest tests/test_graficos_custo.py -v
```

Esperado: FAIL com `ImportError: cannot import name 'custo'`.

- [ ] **Passo 3: escrever as funções de dado**

```python
# src/tesouro/graficos/custo.py
"""Custo do estoque da divida contra a Selic e o IPCA.

O custo sozinho nao responde se a divida esta cara: 12,68% ao ano e caro ou barato
conforme onde estao a Selic e a inflacao. As tres linhas juntas mostram o custo
acompanhando a Selic com atraso, porque metade da divida e LFT e a outra metade foi
contratada no passado.

A SELIC E O IPCA SAEM DO NOSSO PROPRIO VNA. A variacao de 12 meses do VNA e o
indice acumulado -- 14,78% e 4,81% em jun/2026. A pagina do RMD busca isso no site
do Bacen; nos nao precisamos, e e por isso que esta branch nasceu de dv01-decay.

ARMADILHA 1: o custo_medio.csv tem tres medidas na mesma coluna. Este grafico e o
'acum_12m'. O 'mensal' da 13,64 para a DPF em junho, numero plausivel e errado.

ARMADILHA 2: o VNA e do ultimo dia util e o custo e do ultimo dia do mes -- so 137
das 198 datas coincidem. A juncao e por competencia (ano e mes), nunca por data.

ARMADILHA 3: shift(12) conta posicoes, nao meses. Com um buraco na serie do VNA a
variacao compara contra 13 meses atras em silencio, e por isso a completude do VNA
e travada por teste.
"""

import pandas as pd

from .. import config
from . import estilo

JANELAS = {"5 anos": 5, "completa": None}

NIVEIS = ["DPF", "DPMFi"]
INDICES = ["SELIC", "IPCA"]

_COR = {"DPF": "#1f3864",
        "DPMFi": "#3d9be9",
        "SELIC": "#2ca02c",
        "IPCA": "#ed7d31"}

_ROTULO = {"DPF": "custo da DPF",
           "DPMFi": "custo da DPMFi",
           "SELIC": "Selic acumulada em 12m",
           "IPCA": "IPCA acumulado em 12m"}


def variacao_12m_do_vna():
    """Selic e IPCA acumulados em 12 meses, a partir do VNA da entrega 2.

    O VNA e um indice acumulado: a razao entre o de hoje e o de doze meses atras,
    menos um, E a variacao do periodo. Nao ha nada a buscar no Bacen.
    """
    v = pd.read_csv(config.PROCESSED_DIR / "vna.csv", parse_dates=["data"])
    piv = v.pivot_table(index="data", columns="indice", values="vna")
    piv.index = piv.index.to_period("M")

    esperado = pd.period_range(piv.index.min(), piv.index.max(), freq="M")
    if list(piv.index) != list(esperado):
        faltam = sorted(set(esperado) - set(piv.index))
        raise LookupError(
            f"vna.csv tem {len(faltam)} mes(es) faltando ({faltam[:3]}...). A "
            f"variacao de 12 meses usa shift(12), que conta POSICOES: com buraco "
            f"na serie ela compara contra 13 ou 14 meses atras sem avisar."
        )

    return (piv / piv.shift(12) - 1) * 100


def dados_custo(janela=None):
    """Custo acumulado em 12 meses da DPF e da DPMFi, com a Selic e o IPCA.

    A juncao com o VNA e por competencia: o VNA e do ultimo dia util e o custo e do
    ultimo dia do mes, e so 137 das 198 datas coincidem.
    """
    c = pd.read_csv(config.PROCESSED_DIR / "custo_medio.csv", parse_dates=["data"])
    agregado = c[(c["medida"] == "acum_12m")
                 & c["entidade"].isna() & c["titulo"].isna()
                 & c["nivel"].isin(NIVEIS)]
    saida = agregado.pivot_table(index="data", columns="nivel",
                                 values="custo_aa_pct")[NIVEIS]

    indices = variacao_12m_do_vna()
    competencia = saida.index.to_period("M")
    for indice in INDICES:
        saida[indice] = indices[indice].reindex(competencia).to_numpy()

    return estilo.recorta(saida, janela)


def desenha_custo(dados, ax):
    """Quatro linhas, com o numero escrito so no ultimo ponto de cada uma.

    O eixo do tempo e anual e o dado continua mensal: a pagina do RMD usa cerca de
    170 rotulos mensais e ninguem le.
    """
    for coluna in NIVEIS + INDICES:
        serie = dados[coluna].dropna()
        largura = 2.6 if coluna in NIVEIS else 1.6
        estilo_linha = "-" if coluna in NIVEIS else "--"
        ax.plot(serie.index, serie, color=_COR[coluna], lw=largura,
                ls=estilo_linha, label=_ROTULO[coluna])
        ax.annotate(estilo.num_br(serie.iloc[-1], 2),
                    xy=(serie.index[-1], serie.iloc[-1]), xytext=(6, 0),
                    textcoords="offset points", fontsize=9.5, weight="bold",
                    color=_COR[coluna], va="center")

    ax.axhline(0, color="gray", lw=0.8)
    ax.set_ylabel("% ao ano")
    estilo.grade_fina(ax, 5, 2.5)
    estilo.eixo_anual(ax, a_cada=2)
    ax.legend(ncol=4, frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.08))
```

- [ ] **Passo 4: rodar e ver passar**

```
$env:PYTHONPATH="src"; python -m pytest tests/test_graficos_custo.py -v
```

Esperado: 8 passed.

- [ ] **Passo 5: confirmar que cada asserção tem dentes**

Para **cada** âncora, quebre a linha de produção que ela protege, rode, confirme a
falha, e desfaça:

- troque `medida == "acum_12m"` por `== "mensal"` — a âncora de 12,68 deve falhar
  com 13,64, que é o número plausível-e-errado que motivou o teste;
- tire o `c["titulo"].isna()` do filtro — a âncora deve falhar;
- troque a junção por competência por junção por data (`saida[indice] =
  indices[indice]` direto, com o índice de data) — `test_a_juncao_e_por_competencia`
  deve falhar, porque 61 meses ficam sem Selic;
- troque `shift(12)` por `shift(11)` — a âncora de 14,78 deve falhar;
- **apague uma linha do meio do `vna.csv`** (num arquivo temporário, nunca no
  repositório) e rode: `variacao_12m_do_vna` deve **levantar** com a mensagem
  explicativa, em vez de devolver número errado. Restaure o arquivo;
- preencha os índices com `fillna(0)` — `test_os_indices_ficam_vazios_antes_de_2011`
  deve falhar;
- escreva o rótulo em todos os pontos (tire o `.iloc[-1]`) — o teste dos quatro
  rótulos deve falhar.

- [ ] **Passo 6: rodar a suíte inteira e commitar**

```
$env:PYTHONPATH="src"; python -m pytest -q
```

Esperado: 372 passed, 1 skipped.

```bash
git add src/tesouro/graficos/custo.py tests/test_graficos_custo.py
git commit -m "Adiciona o custo do estoque contra a Selic e o IPCA"
```

---

## Task 9: Reserva de liquidez — as duas versões

**Files:**
- Create: `src/tesouro/graficos/reserva.py`
- Test: `tests/test_graficos_reserva.py`

**Interfaces:**
- Consumes: `estilo.COR`, `estilo.num_br`, `estilo.rotulo_mes`, `estilo.recorta`,
  `estilo.eixo_anual`.
- Produces:
  - `JANELAS = {"5 anos": 5, "completa": None}`
  - `dados_reserva(janela=None)` -> DataFrame indexado por data, colunas
    `reserva, prudencial, folga` em R$ milhões e `indice` em meses.
  - `dados_treze_meses()` -> os últimos treze meses, mesmas colunas.
  - `desenha_treze_meses(dados, ax)`
  - `desenha_reserva(dados, ax)`

**Fonte:** `reserva_liquidez.csv` (`data, reserva_milhoes,
valor_prudencial_milhoes, indice_liquidez_meses`), aba 6.1, 138 meses de jan/2015 a
jun/2026.

**Por que esta tarefa existe, e por que são dois gráficos.** A reserva de liquidez é
o colchão que paga os vencimentos sem depender de emitir. O RMD a mostra em treze
meses, e essa é a linguagem que a mesa e a diretoria já conhecem — serve para
apresentação. Mas treze meses não dizem se 8,33 é alto ou baixo; cinco anos dizem. As
duas versões **coexistem por decisão da usuária**, e não são redundância: uma é para
mostrar, a outra é para saber.

**Decisões tomadas com a usuária que o código deve respeitar:**

- **A de treze meses segue o formato do RMD:** barra da reserva, barra do valor
  prudencial, e o índice de liquidez em linha no eixo da direita.
- **A de cinco anos sombreia a folga** entre a reserva e o valor prudencial, que é o
  que sobra depois de honrar o colchão mínimo.
- **Eixo duplo é permitido; eixo truncado não é.** A versão descartada começava o
  eixo do índice em 5,7 e transformava uma variação de 2,6 meses num despencar. É a
  armadilha 7 da spec, e o teste a trava.

**Armadilhas medidas nesta tarefa:**

1. **A folga é negativa nos dois primeiros meses da série.** Em jan/2015 a reserva
   era 133,5 bi **menor** que o valor prudencial, e em fev/2015, 129,3 bi menor. Um
   `fill_between` sem `where` e sem `interpolate=True` pinta esses dois meses como se
   fossem folga positiva. O gráfico fica bonito e mente exatamente onde a informação
   importa.
2. **O valor prudencial oscila muito mês a mês** — 782,8 bi em jun/26 contra 166,9 em
   mar/26. Não é erro de leitura: é a conta do próprio RMD. Não suavizar.
3. **A série começa em jan/2015**, treze anos depois do resto do dashboard. Na janela
   "completa" ela tem 138 meses enquanto a composição tem 307; alinhar os eixos entre
   gráficos diferentes não faz sentido aqui.

- [ ] **Passo 1: escrever os testes que falham**

```python
# tests/test_graficos_reserva.py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pytest

from tesouro.graficos import estilo, reserva


@pytest.fixture(scope="module")
def dados():
    return reserva.dados_reserva()


def test_a_reserva_de_junho_de_2026_bate_com_o_medido(dados):
    # Conferido contra a pagina do RMD que a dona do projeto forneceu.
    u = dados.iloc[-1]
    assert round(u["reserva"] / 1000) == 1346
    assert round(u["prudencial"] / 1000) == 783
    assert round(u["indice"], 2) == 8.33


def test_a_folga_e_a_reserva_menos_o_prudencial(dados):
    assert round(dados.iloc[-1]["folga"] / 1000, 1) == 563.0
    diferenca = dados["folga"] - (dados["reserva"] - dados["prudencial"])
    assert diferenca.abs().max() < 1e-6


def test_a_folga_e_negativa_nos_dois_primeiros_meses(dados):
    # Em jan e fev/2015 a reserva ficou ABAIXO do valor prudencial. E o unico
    # trecho da serie em que isso acontece, e e onde o desenho pode mentir.
    negativos = dados[dados["folga"] < 0]
    assert list(negativos.index) == [pd.Timestamp("2015-01-31"),
                                     pd.Timestamp("2015-02-28")]
    assert round(negativos.iloc[0]["folga"] / 1000, 1) == -133.5


def test_a_versao_de_treze_meses_tem_treze_meses():
    t = reserva.dados_treze_meses()
    assert len(t) == 13
    assert t.index.min() == pd.Timestamp("2025-06-30")
    assert t.index.max() == pd.Timestamp("2026-06-30")
    assert round(t["indice"].min(), 2) == 5.69
    assert round(t["indice"].max(), 2) == 9.33


def test_a_janela_de_cinco_anos_bate_com_o_medido():
    c = reserva.dados_reserva(janela=5)
    assert len(c) == 61
    assert round(c["indice"].min(), 2) == 5.69
    assert round(c["indice"].max(), 2) == 10.59
    assert round(c["reserva"].min() / 1000, 1) == 743.9
    assert round(c["reserva"].max() / 1000, 1) == 1345.8


def test_as_duas_versoes_dizem_o_mesmo_no_mes_comum(dados):
    # Coerencia entre graficos que dividem fonte: o mesmo mes tem de dar o mesmo
    # numero nos dois.
    t = reserva.dados_treze_meses()
    for coluna in ("reserva", "prudencial", "indice"):
        assert abs(t.iloc[-1][coluna] - dados.iloc[-1][coluna]) < 1e-9


def test_o_eixo_do_indice_comeca_em_zero(dados):
    # Armadilha 7 da spec: a versao descartada comecava o eixo do indice em 5,7 e
    # transformava 2,6 meses de variacao num despencar. Eixo duplo pode; eixo
    # truncado nao.
    estilo.aplicar_estilo()
    for desenha, entrada in ((reserva.desenha_treze_meses,
                              reserva.dados_treze_meses()),
                             (reserva.desenha_reserva,
                              reserva.dados_reserva(janela=5))):
        fig, ax = plt.subplots(figsize=(13, 6))
        desenha(entrada, ax)
        direito = [a for a in fig.axes if a is not ax]
        limites = [a.get_ylim() for a in [ax] + direito]
        plt.close(fig)
        for baixo, _ in limites:
            assert baixo == 0, f"{desenha.__name__} truncou um eixo em {baixo}"


def test_a_folga_negativa_nao_e_pintada_como_folga(dados):
    # Sem where= e interpolate=True, os dois meses de 2015 aparecem sombreados do
    # mesmo jeito que os 136 de folga positiva.
    estilo.aplicar_estilo()
    fig, ax = plt.subplots(figsize=(13, 6))
    reserva.desenha_reserva(dados, ax)
    areas = [c for c in ax.collections]
    plt.close(fig)
    # Duas areas: a folga positiva e o deficit. Uma so significa que o sinal se
    # perdeu no caminho.
    assert len(areas) == 2
```

- [ ] **Passo 2: rodar e ver falhar**

```
$env:PYTHONPATH="src"; python -m pytest tests/test_graficos_reserva.py -v
```

Esperado: FAIL com `ImportError: cannot import name 'reserva'`.

- [ ] **Passo 3: escrever as funções de dado**

```python
# src/tesouro/graficos/reserva.py
"""Reserva de liquidez, aba 6.1, em duas versoes que coexistem.

A de treze meses e a linguagem do RMD -- e o formato que a mesa e a diretoria ja
conhecem, e serve para apresentar. A de cinco anos responde a pergunta que treze
meses nao respondem: 8,33 e alto ou baixo? As duas ficam, por decisao da usuaria.

ARMADILHA: a folga (reserva menos valor prudencial) e NEGATIVA em jan e fev/2015 --
133,5 e 129,3 bi abaixo do colchao minimo. Sao os dois unicos meses da serie em que
isso acontece, e um fill_between sem where= e sem interpolate=True pinta os dois
como se fossem folga positiva. O grafico fica bonito e mente exatamente onde a
informacao importa.

Eixo duplo e permitido aqui; eixo truncado nao. A versao descartada comecava o eixo
do indice em 5,7 e transformava 2,6 meses de variacao num despencar.
"""

import pandas as pd

from .. import config
from . import estilo

JANELAS = {"5 anos": 5, "completa": None}

_COR_RESERVA = "#1f3864"
_COR_PRUDENCIAL = "#a6a6a6"
_COR_INDICE = "#ed7d31"


def dados_reserva(janela=None):
    """Reserva, valor prudencial, folga e indice de liquidez, mes a mes."""
    r = pd.read_csv(config.PROCESSED_DIR / "reserva_liquidez.csv",
                    parse_dates=["data"]).set_index("data").sort_index()
    saida = pd.DataFrame(index=r.index)
    saida["reserva"] = r["reserva_milhoes"]
    saida["prudencial"] = r["valor_prudencial_milhoes"]
    saida["folga"] = saida["reserva"] - saida["prudencial"]
    saida["indice"] = r["indice_liquidez_meses"]
    return estilo.recorta(saida, janela)


def dados_treze_meses():
    """Os ultimos treze meses, que e o recorte que a pagina do RMD usa."""
    return dados_reserva().tail(13)


def desenha_treze_meses(dados, ax):
    """O formato do RMD: duas barras por mes e o indice em linha a direita."""
    posicoes = range(len(dados))
    largura = 0.38
    ax.bar([p - largura / 2 for p in posicoes], dados["reserva"] / 1000,
           width=largura, color=_COR_RESERVA, label="reserva de liquidez")
    ax.bar([p + largura / 2 for p in posicoes], dados["prudencial"] / 1000,
           width=largura, color=_COR_PRUDENCIAL, label="valor prudencial")

    ax.set_xticks(list(posicoes))
    ax.set_xticklabels([estilo.rotulo_mes(d) for d in dados.index], fontsize=9)
    ax.set_ylabel("R$ bilh\u00f5es")
    ax.set_ylim(0, dados["reserva"].max() / 1000 * 1.25)
    ax.grid(axis="y", alpha=0.25)

    direita = ax.twinx()
    direita.plot(list(posicoes), dados["indice"], color=_COR_INDICE, lw=2.4,
                 marker="o", ms=4, label="\u00edndice de liquidez")
    direita.set_ylabel("meses de vencimento cobertos")
    # Comeca em zero SEMPRE: comecar no minimo da serie exagera a variacao.
    direita.set_ylim(0, dados["indice"].max() * 1.35)

    marcas, rotulos = ax.get_legend_handles_labels()
    m2, r2 = direita.get_legend_handles_labels()
    ax.legend(marcas + m2, rotulos + r2, ncol=3, frameon=False,
              loc="upper center", bbox_to_anchor=(0.5, -0.10))


def desenha_reserva(dados, ax):
    """A serie longa, com a folga sombreada e o indice a direita.

    O sombreado usa where= com interpolate=True: sem isso os dois meses de 2015 em
    que a reserva ficou ABAIXO do prudencial aparecem pintados como folga.
    """
    ax.plot(dados.index, dados["reserva"] / 1000, color=_COR_RESERVA, lw=2.4,
            label="reserva de liquidez")
    ax.plot(dados.index, dados["prudencial"] / 1000, color=_COR_PRUDENCIAL,
            lw=1.6, label="valor prudencial")

    ax.fill_between(dados.index, dados["reserva"] / 1000,
                    dados["prudencial"] / 1000,
                    where=dados["folga"] >= 0, interpolate=True,
                    color=_COR_RESERVA, alpha=0.18, label="folga")
    ax.fill_between(dados.index, dados["reserva"] / 1000,
                    dados["prudencial"] / 1000,
                    where=dados["folga"] < 0, interpolate=True,
                    color="#d62728", alpha=0.30, label="abaixo do prudencial")

    ax.set_ylabel("R$ bilh\u00f5es")
    ax.set_ylim(0, dados["reserva"].max() / 1000 * 1.20)
    ax.grid(axis="y", alpha=0.25)
    estilo.eixo_anual(ax)

    direita = ax.twinx()
    direita.plot(dados.index, dados["indice"], color=_COR_INDICE, lw=1.8, ls="--",
                 label="\u00edndice de liquidez")
    direita.set_ylabel("meses de vencimento cobertos")
    direita.set_ylim(0, dados["indice"].max() * 1.30)
    direita.annotate(estilo.num_br(dados["indice"].iloc[-1], 2),
                     xy=(dados.index[-1], dados["indice"].iloc[-1]),
                     xytext=(6, 0), textcoords="offset points", fontsize=9.5,
                     weight="bold", color=_COR_INDICE, va="center")

    marcas, rotulos = ax.get_legend_handles_labels()
    m2, r2 = direita.get_legend_handles_labels()
    ax.legend(marcas + m2, rotulos + r2, ncol=5, frameon=False,
              loc="upper center", bbox_to_anchor=(0.5, -0.08))
```

- [ ] **Passo 4: rodar e ver passar**

```
$env:PYTHONPATH="src"; python -m pytest tests/test_graficos_reserva.py -v
```

Esperado: 8 passed.

- [ ] **Passo 5: confirmar que cada asserção tem dentes**

Para **cada** âncora, quebre a linha de produção que ela protege, rode, confirme a
falha, e desfaça:

- troque `saida["reserva"] - saida["prudencial"]` por `saida["reserva"]` — o teste
  da folga e o dos dois meses negativos devem falhar;
- troque `.tail(13)` por `.tail(12)` — o teste dos treze meses deve falhar;
- troque `direita.set_ylim(0, ...)` por `set_ylim(dados["indice"].min(), ...)` **nos
  dois desenhos** — `test_o_eixo_do_indice_comeca_em_zero` deve falhar em cada um.
  Rode as duas vezes: um desenho de cada vez, para confirmar que o teste pega os
  dois e não só o primeiro;
- apague o segundo `fill_between` (o do déficit) — o teste das duas áreas deve
  falhar;
- tire o `where=` do primeiro `fill_between` — o teste das duas áreas continua
  passando (ainda há duas coleções) mas o desenho volta a mentir. **Este é o caso
  que o teste não pega**, e por isso o passo seguinte existe.

- [ ] **Passo 6: olhar os dois meses de 2015 com o olho**

O teste conta áreas; ele não sabe qual cor cobre qual mês. Gere a figura da janela
completa e confira que jan e fev/2015 aparecem em **vermelho**, não em azul:

```
$env:PYTHONPATH="src"; python -c "import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt; from tesouro.graficos import estilo, reserva; estilo.aplicar_estilo(); fig, ax = plt.subplots(figsize=(13, 6)); reserva.desenha_reserva(reserva.dados_reserva(), ax); fig.savefig('reserva_conferencia.svg')"
```

Abra `reserva_conferencia.svg`, confirme, e **apague o arquivo**. Ele não entra no
repositório: o dashboard é quem grava figura, e num lugar só.

- [ ] **Passo 7: rodar a suíte inteira e commitar**

```
$env:PYTHONPATH="src"; python -m pytest -q
```

Esperado: 380 passed, 1 skipped.

```bash
git add src/tesouro/graficos/reserva.py tests/test_graficos_reserva.py
git commit -m "Adiciona as duas versoes da reserva de liquidez"
```

---

## Task 10: Os três candidatos

**Files:**
- Modify: `src/tesouro/graficos/vencimentos.py` (perfil completo até 2084)
- Modify: `src/tesouro/graficos/custo.py` (custo de emissão contra o do estoque)
- Create: `src/tesouro/graficos/leiloes.py` (emissão anual por papel)
- Test: `tests/test_graficos_candidatos.py`

**Interfaces:**
- Produces:
  - `vencimentos.dados_perfil_completo()` -> DataFrame indexado por ano de
    vencimento, uma coluna por família de título, em R$ milhões.
  - `vencimentos.desenha_perfil_completo(dados, ax)`
  - `custo.dados_custo_emissao(janela=None)` -> DataFrame indexado por data, colunas
    `emissao, estoque`, em % ao ano.
  - `custo.desenha_custo_emissao(dados, ax)`
  - `leiloes.dados_emissao_anual_papel(anos=12)` -> DataFrame indexado por ano, uma
    coluna por papel **em percentual**, mais `total_milhoes` e `cobertura_pct`.
  - `leiloes.desenha_emissao_anual_papel(dados, ax, ano_parcial)`

**Fonte:** `estoque_titulos_vencimento.csv` (aba 2.2), `custo_medio.csv` medida
`emissoes_12m` (abas 4.2/4.3), e `leiloes.csv` cruzado com `funding_por_indexador.csv`
para a cobertura.

**Por que esta tarefa existe.** Os três foram construídos em rascunho, **não são os
preferidos da dona do projeto, e ela mandou guardá-los**. Ficam num grupo próprio no
fim do índice: "cada um escolhe o que olhar" vale de verdade, sem poluir a primeira
leitura. Guardar custa pouco; reconstruir depois custa a conversa toda de novo.

**Decisões tomadas com a usuária que o código deve respeitar:**

- **O perfil completo agrupa em seis famílias**, e mantém a NTN-B1 separada da NTN-B.
  Sem isso a cauda desaparece: **tudo que vence depois de 2060 é NTN-B1 RendA+**, e o
  último ano, 2084, são 6,5 bi só dela.
- **O custo de emissão anda com o do estoque no mesmo gráfico.** Sozinho ele não diz
  nada; contra o estoque mostra que o Tesouro está emitindo a 14,20% enquanto carrega
  a 13,19% — a dívida vai ficar mais cara sem que nada mude.
- **A emissão anual por papel foi recusada como gráfico principal** e vive aqui, com
  a cobertura escrita ao lado. É a razão da recusa, e tem que estar visível.

**Armadilhas medidas nesta tarefa:**

1. **O `leiloes.csv` vai além do RMD.** Ele tem leilões até **13/08/2026** e o RMD
   para em jun/26. Sem cortar na última competência do RMD, a cobertura de 2026 dá
   **120%** — o gráfico compara oito meses de leilão contra seis de RMD e parece que
   os leilões emitiram mais do que a emissão total.
2. **A cobertura não é 100% e é por isso que este gráfico é candidato.** Na janela
   de doze anos ela vai de **90,5% (2015) a 97,3% (2020)**; a emissão por indexador
   da aba 1.2 cobre 100%. É a diferença que fez a usuária preferir o gráfico
   principal. A spec fala em "93% a 97%" porque mediu de 2017 em diante — a janela
   maior alcança 2015, que é o pior ano.
5. **A NTN-D e a NTN-C morrem antes da janela.** A NTN-D não é emitida desde 2002 e
   a NTN-C desde 2006. Se o corte de colunas vier antes do corte de anos, as duas
   sobrevivem como colunas de zero e o desenho quebra procurando cor para elas.
3. **A diferença de 16,6 bi entre a 2.2 e a 3.4 continua sem explicação.** O perfil
   soma 8.904,1 bi e o cronograma 8.920,7. Os dois gráficos coexistem por decisão, e
   a diferença é **travada por teste com o valor atual**, para que mudar sem querer
   seja detectado. A causa fica para investigação posterior — não tente conciliar
   aqui.
4. **Linhas com financeiro zero enchem o eixo.** A aba 2.2 traz papéis já vencidos
   com quantidade e financeiro zerados, e o ano deles é o do vencimento passado: sem
   filtrar, o eixo do perfil começa em 2010 com quatorze anos vazios.

- [ ] **Passo 1: escrever os testes que falham**

```python
# tests/test_graficos_candidatos.py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pytest

from tesouro import config
from tesouro.graficos import custo, estilo, leiloes, vencimentos


# ---------------------------------------------------------------------------
# Candidato 1: perfil completo de vencimentos, ate 2084
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def perfil():
    return vencimentos.dados_perfil_completo()


def test_o_perfil_completo_vai_ate_2084(perfil):
    assert perfil.index.min() == 2026
    assert perfil.index.max() == 2084
    # Anos ja vencidos entram no CSV com financeiro zero; sem filtrar, o eixo
    # comecaria em 2010 com quatorze anos vazios.
    assert len(perfil) == 34


def test_a_diferenca_de_166_bi_contra_o_cronograma_esta_travada(perfil):
    # Os dois graficos de vencimento coexistem por decisao. A diferenca e travada
    # com o valor de hoje para que mudar sem querer seja detectado; a causa fica
    # para investigacao posterior (ver a spec, secao 10).
    total_perfil = perfil.sum().sum() / 1000
    cronograma = vencimentos.dados_cronograma_anual().sum().sum() / 1000
    assert round(total_perfil, 1) == 8904.1
    assert round(cronograma, 1) == 8920.7
    assert round(cronograma - total_perfil, 1) == 16.6


def test_a_cauda_longa_e_toda_indexada_a_precos(perfil):
    # Depois de 2040 nao ha mais LFT, LTN nem NTN-F: so indice de precos. E o
    # motivo de a NTN-B1 ficar separada da NTN-B -- o ultimo ano da divida,
    # 2084, sao 6,5 bi de RendA+ e mais nada.
    tarde = perfil[perfil.index > 2040]
    for familia in ("LFT", "LTN", "NTN-F"):
        assert tarde[familia].sum() == 0
    assert round(perfil.loc[2084, "NTN-B1"] / 1000, 1) == 6.5
    assert round(perfil.loc[2084].sum() / 1000, 1) == 6.5


# ---------------------------------------------------------------------------
# Candidato 2: custo de emissao contra o do estoque
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def emissao():
    return custo.dados_custo_emissao()


def test_o_custo_de_emissao_bate_com_o_medido(emissao):
    u = emissao.iloc[-1]
    assert round(u["emissao"], 2) == 14.20
    assert round(u["estoque"], 2) == 13.19
    # O fato que o grafico existe para mostrar: emite-se mais caro do que se
    # carrega, entao a divida encarece sem que nada mude.
    assert u["emissao"] > u["estoque"]


def test_o_custo_de_emissao_comeca_em_dezembro_de_2010(emissao):
    assert emissao.index.min() == pd.Timestamp("2010-12-31")
    assert len(emissao) == 187


def test_o_custo_do_estoque_e_o_mesmo_nos_dois_graficos():
    # Coerencia entre graficos que dividem fonte: o custo da DPMFi aparece no
    # grafico principal e neste, e tem de dar o mesmo numero.
    principal = custo.dados_custo().iloc[-1]["DPMFi"]
    candidato = custo.dados_custo_emissao().iloc[-1]["estoque"]
    assert abs(principal - candidato) < 1e-9


# ---------------------------------------------------------------------------
# Candidato 3: emissao anual por papel, dos leiloes
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def anual():
    return leiloes.dados_emissao_anual_papel()


def test_a_emissao_anual_por_papel_bate_com_o_medido(anual):
    assert round(anual.loc[2025, "LFT"], 1) == 39.6
    assert round(anual.loc[2025, "LTN"], 1) == 33.1
    assert round(anual.loc[2025, "NTN-B"], 1) == 18.1
    assert round(anual.loc[2025, "NTN-F"], 1) == 9.2
    assert round(anual.loc[2024, "LFT"], 1) == 65.1     # o ano da LFT


def test_cada_ano_da_emissao_por_papel_soma_100(anual):
    cols = [c for c in anual.columns
            if c not in ("total_milhoes", "cobertura_pct")]
    assert (anual[cols].sum(axis=1) - 100).abs().max() < 0.01


def test_os_leiloes_sao_cortados_na_ultima_competencia_do_rmd(anual):
    # O leiloes.csv vai ate 13/08/2026 e o RMD para em jun/26. Sem cortar, a
    # cobertura de 2026 da 120% -- oito meses de leilao contra seis de RMD.
    bruto = pd.read_csv(config.PROCESSED_DIR / "leiloes.csv",
                        parse_dates=["data_leilao"])
    assert bruto["data_leilao"].max() > pd.Timestamp("2026-06-30"), \
        "o teste so vale se o CSV de leiloes for alem do RMD"
    assert round(anual.loc[2026, "total_milhoes"] / 1000, 1) == 842.6
    assert anual.loc[2026, "cobertura_pct"] < 100


def test_a_cobertura_dos_anos_fechados_fica_entre_90_e_98(anual):
    # A razao de este grafico ser candidato: a aba 1.2 cobre 100% da emissao e os
    # leiloes nao. Na janela de 12 anos a cobertura vai de 90,5% (2015) a 97,3%
    # (2020) -- a spec fala em "93% a 97%" porque mediu de 2017 em diante.
    fechados = anual[anual.index < 2026]["cobertura_pct"]
    assert round(fechados.min(), 1) == 90.5
    assert round(fechados.max(), 1) == 97.3
    assert round(fechados.loc[2024], 1) == 93.0
    # E nenhum papel entra no desenho sem cor: a NTN-D e a NTN-C sairiam como
    # coluna de zero se o corte de colunas viesse antes do corte de anos.
    from tesouro.graficos import estilo
    for papel in anual.columns:
        if papel not in ("total_milhoes", "cobertura_pct"):
            assert papel in estilo.COR, f"sem cor para {papel}"


def test_a_nota_de_cobertura_aparece_no_desenho(anual):
    # A licao que custou seis rodadas na entrega 2: esta assercao precisa FALHAR
    # quando a linha que escreve a nota e apagada. Ver o Passo 6.
    estilo.aplicar_estilo()
    fig, ax = plt.subplots(figsize=(13, 6))
    leiloes.desenha_emissao_anual_papel(anual, ax, ano_parcial=2026)
    textos = " ".join(t.get_text() for t in ax.texts)
    plt.close(fig)
    assert "cobertura" in textos.lower()
    assert "93" in textos or "97" in textos
```

- [ ] **Passo 2: rodar e ver falhar**

```
$env:PYTHONPATH="src"; python -m pytest tests/test_graficos_candidatos.py -v
```

Esperado: FAIL com `ImportError: cannot import name 'leiloes'`.

- [ ] **Passo 3: o perfil completo, em `vencimentos.py`**

```python
# acrescentar em src/tesouro/graficos/vencimentos.py

# A aba 2.2 traz nove nomes de titulo. Eles viram seis familias, e a NTN-B1 fica
# SEPARADA da NTN-B de proposito: tudo que vence depois de 2060 e NTN-B1 RendA+, e
# juntar as duas apagaria a cauda inteira do grafico.
_FAMILIA = {"LFT": "LFT",
            "LFT-TD1 Reserva": "LFT",
            "LTN": "LTN",
            "NTN-B": "NTN-B",
            "NTN-B Principal": "NTN-B",
            "NTN-B1 EducA+": "NTN-B1",
            "NTN-B1 RendA+": "NTN-B1",
            "NTN-C": "NTN-C",
            "NTN-F": "NTN-F"}

ORDEM_FAMILIAS = ["LFT", "LTN", "NTN-F", "NTN-B", "NTN-B1", "NTN-C"]

_COR_FAMILIA = {"LFT": "LFT", "LTN": "LTN", "NTN-F": "NTN-F",
                "NTN-B": "NTN-B", "NTN-B1": "NTN-C", "NTN-C": "Outros"}


def dados_perfil_completo():
    """Vencimentos por ano ate 2084, por familia de titulo, em R$ milhoes.

    Vem da aba 2.2, papel a papel -- diferente do cronograma, que vem da 3.4 e para
    em 60 meses. Os dois nao fecham: 8.904,1 aqui contra 8.920,7 la, 16,6 bi de
    diferenca cuja causa esta em aberto e travada por teste.

    ARMADILHA: papeis ja vencidos ficam no CSV com financeiro zero e ano de
    vencimento no passado. Sem filtrar, o eixo comeca em 2010 com quatorze anos
    vazios.
    """
    e = pd.read_csv(config.PROCESSED_DIR / "estoque_titulos_vencimento.csv",
                    parse_dates=["data", "vencimento"])
    u = e[(e["data"] == e["data"].max()) & (e["financeiro_milhoes"] > 0)].copy()
    u["ano"] = u["vencimento"].dt.year
    u["familia"] = [_FAMILIA[t] for t in u["titulo"]]

    piv = u.pivot_table(index="ano", columns="familia",
                        values="financeiro_milhoes", aggfunc="sum").fillna(0.0)
    for familia in ORDEM_FAMILIAS:
        if familia not in piv.columns:
            piv[familia] = 0.0
    return piv[ORDEM_FAMILIAS]


def desenha_perfil_completo(dados, ax):
    """Barras empilhadas por ano, do proximo ao ultimo.

    O eixo do tempo e categorico e nao continuo: entre 2060 e 2084 ha quatro anos
    com divida e vinte sem, e um eixo continuo gastaria metade da largura com
    espaco vazio.
    """
    posicoes = range(len(dados))
    base = pd.Series(0.0, index=dados.index)
    for familia in dados.columns:
        ax.bar(list(posicoes), dados[familia] / 1000, bottom=base / 1000,
               width=0.78, color=estilo.COR[_COR_FAMILIA[familia]], label=familia)
        base = base + dados[familia]

    ax.set_xticks(list(posicoes))
    ax.set_xticklabels([str(a) for a in dados.index], rotation=90, fontsize=8)
    ax.set_ylabel("R$ bilh\u00f5es a vencer")
    ax.legend(ncol=6, frameon=False, loc="upper right")
    ax.grid(axis="y", alpha=0.25)
```

- [ ] **Passo 4: o custo de emissão, em `custo.py`**

```python
# acrescentar em src/tesouro/graficos/custo.py

def dados_custo_emissao(janela=None):
    """Custo das emissoes dos ultimos 12 meses contra o custo do estoque, DPMFi.

    O custo de emissao sozinho nao diz nada; contra o do estoque mostra a direcao:
    em jun/26 o Tesouro emite a 14,20% e carrega a 13,19%, entao a divida encarece
    sem que nenhuma decisao nova seja tomada.

    A serie de emissoes comeca em dez/2010, cinco anos depois da do estoque, e por
    isso este grafico e mais curto que o principal.
    """
    c = pd.read_csv(config.PROCESSED_DIR / "custo_medio.csv", parse_dates=["data"])
    agregado = c[(c["nivel"] == "DPMFi")
                 & c["entidade"].isna() & c["titulo"].isna()]
    piv = agregado.pivot_table(index="data", columns="medida",
                               values="custo_aa_pct")

    saida = pd.DataFrame(index=piv.index)
    saida["emissao"] = piv["emissoes_12m"]
    saida["estoque"] = piv["acum_12m"]
    saida = saida.dropna(subset=["emissao"])
    return estilo.recorta(saida, janela)


def desenha_custo_emissao(dados, ax):
    """As duas linhas, com a diferenca sombreada entre elas."""
    ax.plot(dados.index, dados["emissao"], color="#c00000", lw=2.4,
            label="custo das emiss\u00f5es em 12m")
    ax.plot(dados.index, dados["estoque"], color="#1f3864", lw=2.4,
            label="custo do estoque em 12m")
    ax.fill_between(dados.index, dados["emissao"], dados["estoque"],
                    where=dados["emissao"] >= dados["estoque"], interpolate=True,
                    color="#c00000", alpha=0.14)
    ax.fill_between(dados.index, dados["emissao"], dados["estoque"],
                    where=dados["emissao"] < dados["estoque"], interpolate=True,
                    color="#1f3864", alpha=0.14)

    for coluna, cor in (("emissao", "#c00000"), ("estoque", "#1f3864")):
        ax.annotate(estilo.num_br(dados[coluna].iloc[-1], 2),
                    xy=(dados.index[-1], dados[coluna].iloc[-1]), xytext=(6, 0),
                    textcoords="offset points", fontsize=9.5, weight="bold",
                    color=cor, va="center")

    ax.set_ylabel("% ao ano")
    estilo.grade_fina(ax, 2, 1)
    estilo.eixo_anual(ax, a_cada=2)
    ax.legend(ncol=2, frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.08))
```

- [ ] **Passo 5: a emissão anual por papel, em `leiloes.py`**

```python
# src/tesouro/graficos/leiloes.py
"""Emissao anual por papel, a partir dos leiloes. Grafico CANDIDATO.

A usuaria pediu a composicao da emissao por papel, viu esta versao e preferiu a por
indexador (o grafico principal, no funding.py): pela aba 1.2 a cobertura e 100% da
emissao do RMD, e por aqui vai de 90,5% (2015) a 97,3% (2020). Este ficou
guardado, e a
cobertura de cada ano vai escrita no proprio grafico -- e a razao da recusa, e
esconde-la seria esconder o defeito.

ARMADILHA: o leiloes.csv vai alem do RMD -- tem leilao ate 13/08/2026 enquanto o
RMD para em jun/26. Sem cortar na ultima competencia do RMD, 2026 da cobertura de
120%, comparando oito meses de leilao com seis meses de emissao.
"""

import pandas as pd

from .. import config
from . import estilo

JANELAS = {"5 anos": 5, "completa": None}

ORDEM_PAPEIS = ["LFT", "LTN", "NTN-B", "NTN-F", "NTN-C", "NTN-D"]


def ultima_competencia_do_rmd():
    """Ultimo mes que o RMD cobre. E onde os leiloes tem de ser cortados."""
    f = pd.read_csv(config.PROCESSED_DIR / "funding_por_indexador.csv",
                    parse_dates=["data"])
    return f["data"].max()


def dados_emissao_anual_papel(anos=12):
    """Composicao da emissao por papel, ano a ano, em percentual.

    'total_milhoes' e o tamanho do ano; 'cobertura_pct' e quanto os leiloes
    representam da emissao que o RMD registra no mesmo ano -- o numero que fez a
    usuaria preferir o grafico por indexador.
    """
    corte = ultima_competencia_do_rmd()

    l = pd.read_csv(config.PROCESSED_DIR / "leiloes.csv",
                    parse_dates=["data_leilao"])
    venda = l[(l["tipo_leilao"] == "Venda") & (l["data_leilao"] <= corte)].copy()
    venda["ano"] = venda["data_leilao"].dt.year
    piv = venda.pivot_table(index="ano", columns="titulo",
                            values="financeiro_milhoes", aggfunc="sum").fillna(0.0)
    # O corte de colunas vem DEPOIS do corte de anos, e a ordem importa: a NTN-D
    # nao e emitida desde 2002 e a NTN-C desde 2006. Filtrando antes, as duas
    # sobrevivem como colunas de zero dentro da janela mostrada -- e o desenho
    # quebra procurando cor para um papel que a paleta nao tem.
    piv = piv[piv.index >= piv.index.max() - anos + 1]
    piv = piv.loc[:, piv.sum() > 0]

    f = pd.read_csv(config.PROCESSED_DIR / "funding_por_indexador.csv",
                    parse_dates=["data"])
    emissao = f[(f["esfera"] == "DPMFi") & (f["operacao"] == "emissao")].copy()
    emissao["ano"] = emissao["data"].dt.year
    do_rmd = emissao.groupby("ano")["valor_milhoes"].sum()

    total = piv.sum(axis=1)
    saida = (piv.div(total, axis=0) * 100)[[p for p in ORDEM_PAPEIS
                                            if p in piv.columns]].copy()
    saida["total_milhoes"] = total
    saida["cobertura_pct"] = total / do_rmd.reindex(total.index) * 100
    return saida


def desenha_emissao_anual_papel(dados, ax, ano_parcial):
    """Barra de 100% por ano, com o total acima e a cobertura escrita embaixo."""
    cols = [c for c in dados.columns
            if c not in ("total_milhoes", "cobertura_pct")]
    base = pd.Series(0.0, index=dados.index)
    for papel in cols:
        ax.bar(dados.index, dados[papel], bottom=base, width=0.72,
               color=estilo.COR[papel], label=papel)
        for x in dados.index:
            altura = dados.loc[x, papel]
            if altura >= 4:
                ax.text(x, base[x] + altura / 2, f"{altura:.0f}", ha="center",
                        va="center", fontsize=8.5, color="white", weight="bold")
        base = base + dados[papel]

    for x in dados.index:
        ax.text(x, 101.5,
                estilo.num_br(dados.loc[x, "total_milhoes"] / 1000, 0) + " bi",
                ha="center", fontsize=8, color="#444444")

    fechados = dados[dados.index != ano_parcial]["cobertura_pct"]
    ax.text(0.5, -0.20,
            "cobertura dos leil\u00f5es sobre a emiss\u00e3o do RMD: "
            + estilo.num_br(fechados.min(), 1) + "% a "
            + estilo.num_br(fechados.max(), 1) + "% nos anos fechados",
            transform=ax.transAxes, ha="center", fontsize=9,
            color=estilo.COR["neutro"])

    ax.set_ylim(0, 108)
    ax.set_xticks(list(dados.index))
    ax.set_xticklabels([str(a) if a != ano_parcial else f"{a}*"
                        for a in dados.index])
    ax.set_ylabel("% do financeiro emitido no ano")
    ax.legend(ncol=len(cols), frameon=False, loc="lower center",
              bbox_to_anchor=(0.5, -0.13))
    ax.grid(axis="y", alpha=0.20)
```

- [ ] **Passo 6: rodar e ver passar**

```
$env:PYTHONPATH="src"; python -m pytest tests/test_graficos_candidatos.py -v
```

Esperado: 11 passed.

- [ ] **Passo 7: confirmar que cada asserção tem dentes**

Para **cada** âncora, quebre a linha de produção que ela protege, rode, confirme a
falha, e desfaça:

- tire o `financeiro_milhoes > 0` do perfil — o teste dos 34 anos deve falhar;
- junte a NTN-B1 na NTN-B no `_FAMILIA` — o teste da cauda deve falhar;
- troque `medida` `emissoes_12m` por `mensal` no custo de emissão — a âncora de
  14,20 deve falhar;
- troque `piv["acum_12m"]` por `piv["mensal"]` — o teste de coerência entre os dois
  gráficos deve falhar. **É o teste mais importante desta tarefa:** ele é o que
  garante que o mesmo número não apareça diferente em dois lugares do dashboard;
- tire o `data_leilao <= corte` — o teste do corte deve falhar, com 2026 passando de
  100% de cobertura;
- **apague a linha do `ax.text` da cobertura** e rode
  `test_a_nota_de_cobertura_aparece_no_desenho`. Ela **tem** que falhar. Se passar, a
  asserção está afirmando o resultado em vez da intenção, e é exatamente o defeito
  que custou seis rodadas na entrega 2. Restaure.

- [ ] **Passo 8: rodar a suíte inteira e commitar**

```
$env:PYTHONPATH="src"; python -m pytest -q
```

Esperado: 391 passed, 1 skipped.

```bash
git add src/tesouro/graficos/ tests/test_graficos_candidatos.py
git commit -m "Adiciona os tres graficos candidatos"
```

---

## Task 11: O dashboard — registro, montagem do HTML e reprodutibilidade

**Files:**
- Create: `src/tesouro/graficos/dashboard.py`
- Modify: `src/tesouro/graficos/estilo.py` (`recorta` passa a aceitar par de datas)
- Test: `tests/test_dashboard.py`

**Interfaces:**
- Consumes: todos os módulos de gráfico.
- Produces:
  - `Grafico` -> namedtuple `id grupo titulo fonte nota janela padrao figura`
  - `REGISTRO` -> **lista literal** com os dezesseis
  - `GRUPOS` -> ordem dos grupos no índice
  - `JANELAS = (("5 anos", 5), ("completa", None))`
  - `svg_de(figura)` -> str, o SVG pronto para embutir
  - `monta(recortes=None)` -> str, o HTML inteiro
  - `grava(caminho=None, recortes=None)` -> Path

**Por que o registro é uma lista literal.** Sem decorador e sem descoberta
automática: quem abrir o arquivo vê os dezesseis, em ordem, com grupo e fonte, e
entende em trinta segundos. A indireção de um sistema de registro não se paga para
dezesseis itens — e um decorador espalharia por dez arquivos a informação que
interessa junta.

**Uma divergência da spec, resolvida aqui.** A spec diz "sete dos dezesseis aceitam
janela" e "23 SVGs", mas a tabela da seção 5 marca **nove** com "sim": os sete
principais mais dois candidatos (custo de emissão e emissão anual por papel). Nove
dão **25 SVGs**. A contagem certa é a da tabela; o texto contou só os principais. O
teste **deriva o número do registro** em vez de fixá-lo, para que a próxima mudança
não precise de nenhuma aritmética à mão.

**Decisões que o código deve respeitar:**

- **Um arquivo autocontido.** `data/processed/dashboard.html`, com os SVGs dentro.
  Abre com duplo clique, sem servidor, e continua funcionando copiado para outra
  máquina ou mandado por e-mail. Num banco isso vale mais que elegância.
- **O limiar de 10 MB é medido, não suposto.** Se o arquivo passar disso, os SVGs
  saem para arquivos ao lado e a spec registra que "um arquivo só" foi trocado por
  tamanho utilizável. O Passo 6 mede.
- **Cada gráfico abre na janela que a usuária escolheu para ele.** A composição do
  estoque abre na série completa — a queda do câmbio de 51% para 3,7% é o fato
  central e não existe em cinco anos. Os outros abrem em 5 anos. O botão do topo
  força todos para a mesma janela quando alguém clica.
- **A legenda fica abaixo da figura, em HTML**, e não dentro do desenho: assim o
  texto é selecionável e o SVG fica limpo.
- **Nenhuma biblioteca nova.** HTML e CSS puros, JavaScript escrito à mão.

**Armadilhas medidas nesta tarefa:**

1. **O SVG do matplotlib começa com prólogo XML e DOCTYPE.** Embutir isso no meio de
   um HTML é inválido. Tudo antes do primeiro `<svg` sai fora.
2. **Referências internas do SVG colidem entre figuras.** Um `<clipPath id="p1a2b">`
   é resolvido pelo navegador para o **primeiro** id daquele nome no documento
   inteiro. Vinte e cinco SVGs no mesmo HTML, e o recorte de um gráfico pode passar a
   valer para outro. Os ids do matplotlib são derivados do conteúdo (é o que o
   `svg.hashsalt` da Task 1 fixa), então na prática não colidem — mas isso é
   propriedade que se perde em silêncio, e o teste a trava.
3. **Reprodutibilidade só existe com o `svg.hashsalt` fixo.** Sem ele, montar duas
   vezes o mesmo dado gera arquivos diferentes e ninguém sabe se o dashboard mudou
   porque o dado mudou. É a razão de a Task 1 existir.
4. **`--de/--ate` não é uma janela em anos.** Em vez de mudar a assinatura de dez
   funções de dado, `estilo.recorta` passa a aceitar também um par `(de, ate)` — e
   como toda função de dado já chama `estilo.recorta`, o recorte por data chega em
   todas de graça.

- [ ] **Passo 1: escrever os testes que falham**

```python
# tests/test_dashboard.py
import re

import matplotlib
matplotlib.use("Agg")
import pandas as pd
import pytest

from tesouro.graficos import dashboard


@pytest.fixture(scope="module")
def html():
    return dashboard.monta()


def test_o_registro_tem_os_dezesseis_graficos():
    assert len(dashboard.REGISTRO) == 16
    ids = [g.id for g in dashboard.REGISTRO]
    assert len(set(ids)) == 16, "id repetido no registro"
    for g in dashboard.REGISTRO:
        assert g.grupo in dashboard.GRUPOS, f"grupo desconhecido em {g.id}"
        assert g.titulo and g.fonte, f"{g.id} sem titulo ou sem fonte"


def test_os_grupos_saem_na_ordem_com_os_candidatos_por_ultimo():
    assert dashboard.GRUPOS[-1] == "Candidatos"
    grupos_usados = [g.grupo for g in dashboard.REGISTRO]
    # Os tres candidatos ficam juntos no fim: "cada um escolhe o que olhar" vale
    # de verdade, sem poluir a primeira leitura.
    assert grupos_usados[-3:] == ["Candidatos"] * 3


def test_nove_graficos_aceitam_janela_e_saem_vinte_e_cinco_svgs():
    # A spec diz "sete dos dezesseis" e "23 SVGs", mas a tabela da secao 5 marca
    # nove -- os sete principais mais dois candidatos. A contagem certa e a da
    # tabela, e este teste a deriva do registro em vez de fixar o numero.
    com_janela = [g for g in dashboard.REGISTRO if g.janela]
    assert len(com_janela) == 9
    total = len(dashboard.REGISTRO) + len(com_janela)
    assert total == 25


def test_o_html_traz_todos_os_titulos_e_todos_os_grupos(html):
    for g in dashboard.REGISTRO:
        assert g.titulo in html, f"faltou o titulo de {g.id}"
        assert f'id="{g.id}"' in html, f"faltou a ancora de {g.id}"
    for grupo in dashboard.GRUPOS:
        assert grupo in html


def test_os_graficos_com_janela_trazem_as_duas_versoes_embutidas(html):
    for g in dashboard.REGISTRO:
        marcas = html.count(f'data-grafico="{g.id}" data-janela=')
        assert marcas == (2 if g.janela else 1), f"{g.id} tem {marcas} versoes"


def test_a_composicao_do_estoque_abre_na_serie_completa():
    porid = {g.id: g for g in dashboard.REGISTRO}
    assert porid["estoque_composicao"].padrao == "completa"
    # E os demais que aceitam janela abrem em 5 anos.
    outros = [g for g in dashboard.REGISTRO
              if g.janela and g.id != "estoque_composicao"]
    assert all(g.padrao == "5 anos" for g in outros)


def test_o_html_nao_tem_nenhuma_referencia_externa(html):
    # Um src apontando para fora quebra o "abre com duplo clique em qualquer
    # maquina", que e a propriedade que faz este arquivo servir num banco.
    #
    # Nao da para procurar "http://" cru: todo SVG do matplotlib declara
    # xmlns="http://www.w3.org/2000/svg", que e nome de espaco e nao busca nada
    # na rede. O que importa e src= e href= apontando para fora.
    assert not re.search(r'(?:src|href)\s*=\s*"(?!#)[^"]*//', html)
    assert "<link" not in html
    assert not re.search(r"<script[^>]+src=", html)
    # E o prologo XML do matplotlib nao pode vazar para dentro do HTML.
    assert "<?xml" not in html
    assert "<!DOCTYPE svg" not in html


def test_toda_referencia_interna_do_svg_resolve_para_um_id_unico(html):
    # url(#p1a2b) e resolvido pelo navegador para o PRIMEIRO id daquele nome no
    # documento inteiro. Com 25 SVGs juntos, o recorte de um grafico pode passar a
    # valer para outro.
    referencias = set(re.findall(r"url\(#([^)]+)\)", html))
    assert referencias, "nenhuma referencia interna; o teste perdeu sentido"
    ids = re.findall(r'id="([^"]+)"', html)
    for referencia in referencias:
        assert ids.count(referencia) == 1, \
            f"o id '{referencia}' aparece {ids.count(referencia)} vezes"


def test_o_html_e_reprodutivel():
    # Sem o svg.hashsalt fixo da Task 1, duas montagens do mesmo dado geram
    # arquivos diferentes e ninguem sabe se o dashboard mudou porque o dado mudou.
    assert dashboard.monta() == dashboard.monta()


def test_cada_figura_leva_a_legenda_com_a_aba_de_origem(html):
    for g in dashboard.REGISTRO:
        assert g.fonte in html, f"faltou a fonte de {g.id}"
    # A legenda e HTML, nao texto dentro do desenho: selecionavel e fora do SVG.
    assert html.count('class="legenda"') == len(dashboard.REGISTRO)


def test_o_botao_de_periodo_some_quando_ha_uma_janela_so():
    um_so = dashboard.monta(recortes=[("2021-01-01 a 2026-06-30",
                                       (pd.Timestamp("2021-01-01"),
                                        pd.Timestamp("2026-06-30")))])
    assert 'id="troca-periodo"' not in um_so
    assert 'id="troca-periodo"' in dashboard.monta()


def test_o_recorte_por_data_chega_nas_funcoes_de_dado():
    from tesouro.graficos import funding
    par = (pd.Timestamp("2021-01-01"), pd.Timestamp("2026-06-30"))
    cortado = funding.dados_net(par)
    inteiro = funding.dados_net()
    assert cortado.index.min() >= par[0]
    assert cortado.index.max() == inteiro.index.max()
    assert len(cortado) < len(inteiro)


def test_o_arquivo_cabe_no_limiar_de_dez_megabytes(tmp_path):
    # Limiar medido, nao suposto (ver a spec, secao 4.1). Se estourar, os SVGs
    # saem para arquivos ao lado e a spec registra a troca.
    caminho = dashboard.grava(tmp_path / "dashboard.html")
    tamanho = caminho.stat().st_size
    assert tamanho > 100_000, "arquivo pequeno demais; algum grafico nao entrou"
    assert tamanho < 10 * 1024 * 1024, (
        f"o dashboard passou de 10 MB ({tamanho / 1024 / 1024:.1f} MB). A spec "
        f"manda trocar os SVGs embutidos por arquivos ao lado e registrar a troca."
    )
```

- [ ] **Passo 2: rodar e ver falhar**

```
$env:PYTHONPATH="src"; python -m pytest tests/test_dashboard.py -v
```

Esperado: FAIL com `ImportError: cannot import name 'dashboard'`.

- [ ] **Passo 3: o recorte por par de datas, em `estilo.py`**

Troque `recorta` pela versão que aceita as duas formas:

```python
def recorta(df, janela):
    """Recorte de um DataFrame indexado por data.

    'janela' vem em tres formas:
      None                       -> a serie inteira
      um numero de anos          -> os ultimos N anos
      um par (de, ate)           -> o intervalo pedido na linha de comando

    A terceira existe para que --de/--ate chegue as dez funcoes de dado sem mudar
    a assinatura de nenhuma delas: todas ja chamam esta funcao.
    """
    import pandas as pd
    if janela is None:
        return df
    if isinstance(janela, tuple):
        de, ate = janela
        return df[(df.index >= de) & (df.index <= ate)]
    return df[df.index >= df.index.max() - pd.DateOffset(years=janela)]
```

- [ ] **Passo 4: o registro**

```python
# src/tesouro/graficos/dashboard.py
"""O registro dos dezesseis graficos e a montagem do HTML.

O registro e uma LISTA LITERAL, sem decorador e sem descoberta automatica: quem
abre este arquivo ve os dezesseis, em ordem, com grupo e fonte, e entende em trinta
segundos. A indirecao de um sistema de registro nao se paga para dezesseis itens, e
um decorador espalharia por dez arquivos a informacao que interessa junta.

O HTML e autocontido: os SVGs vao dentro dele. Abre com duplo clique, sem servidor,
e continua funcionando copiado para outra maquina ou mandado por e-mail -- num banco
isso vale mais que elegancia. O limiar de 10 MB e medido por teste; se estourar, os
SVGs saem para arquivos ao lado.

Nove dos dezesseis aceitam janela, entao sao 25 SVGs. (A spec diz sete e 23 no
texto, mas a tabela da secao 5 marca nove; a tabela e que esta certa.)
"""

import collections
import io
import re

import matplotlib.pyplot as plt

from .. import config
from . import (custo, detentores, estilo, estoque, funding, leiloes, paf,
               prazo, reserva, vencimentos)

Grafico = collections.namedtuple(
    "Grafico", "id grupo titulo fonte nota janela padrao figura")

GRUPOS = ["Funding", "Estoque", "Detentores", "Vencimentos", "Prazo", "Custo",
          "Reserva", "Candidatos"]

JANELAS = (("5 anos", 5), ("completa", None))


def _figura(altura=6.2):
    fig = plt.figure(figsize=(13, altura))
    return fig


def _fig_net(janela):
    fig = _figura(8.0)
    funding.desenha_net(funding.dados_net(janela), fig)
    return fig


def _fig_emissao_indexador(janela):
    fig = _figura()
    funding.desenha_emissao_indexador(funding.dados_emissao_indexador(janela),
                                      fig.subplots())
    return fig


def _fig_emissao_anual(janela):
    # Este grafico conta ANOS, nao recorta datas: a janela de 5 anos vira cinco
    # barras, e a completa vira a serie inteira.
    anos = janela if isinstance(janela, int) else 100
    dados = funding.dados_emissao_anual(anos=anos)
    fig = _figura()
    funding.desenha_emissao_anual(dados, fig.subplots(),
                                 funding.ultimo_mes_com_emissao().year)
    return fig


def _fig_composicao(janela):
    fig = _figura(6.8)
    bandas = {k: paf.bandas(k) for k in paf.COMPOSICAO}
    estoque.desenha_composicao(estoque.dados_composicao(janela), bandas,
                               fig.subplots())
    return fig


def _fig_participacao(janela):
    fig = _figura(5.0)
    detentores.desenha_participacao(detentores.dados_participacao(), fig)
    return fig


def _fig_por_papel(janela):
    fig = _figura(4.6)
    detentores.desenha_por_papel(detentores.dados_por_papel(), fig)
    return fig


def _fig_financeiro_detentor(janela):
    fig = _figura(8.6)
    detentores.desenha_financeiro(detentores.dados_financeiro(janela), fig)
    return fig


def _fig_cronograma(janela):
    fig = _figura(9.0)
    vencimentos.desenha_cronograma(vencimentos.dados_cronograma_anual(),
                                   vencimentos.dados_cronograma_mensal(), fig)
    return fig


def _fig_faixas(janela):
    fig = _figura(8.0)
    vencimentos.desenha_faixas(vencimentos.dados_faixas(),
                               vencimentos.banda_vincendo_12m(), fig)
    return fig


def _fig_prazo(janela):
    fig = _figura()
    prazo.desenha_prazo(prazo.dados_prazo(), paf.bandas("prazo_medio_anos"),
                        fig.subplots())
    return fig


def _fig_custo(janela):
    fig = _figura()
    custo.desenha_custo(custo.dados_custo(janela), fig.subplots())
    return fig


def _fig_reserva_13m(janela):
    fig = _figura(5.4)
    reserva.desenha_treze_meses(reserva.dados_treze_meses(), fig.subplots())
    return fig


def _fig_reserva(janela):
    fig = _figura()
    reserva.desenha_reserva(reserva.dados_reserva(janela), fig.subplots())
    return fig


def _fig_perfil_completo(janela):
    fig = _figura(6.6)
    vencimentos.desenha_perfil_completo(vencimentos.dados_perfil_completo(),
                                        fig.subplots())
    return fig


def _fig_custo_emissao(janela):
    fig = _figura()
    custo.desenha_custo_emissao(custo.dados_custo_emissao(janela),
                                fig.subplots())
    return fig


def _fig_emissao_papel(janela):
    anos = janela if isinstance(janela, int) else 100
    dados = leiloes.dados_emissao_anual_papel(anos=anos)
    fig = _figura()
    leiloes.desenha_emissao_anual_papel(
        dados, fig.subplots(), leiloes.ultima_competencia_do_rmd().year)
    return fig


REGISTRO = [
    Grafico("funding_net", "Funding",
            "Net do DPMFi, com m\u00e9dia m\u00f3vel e acumulado de 12 meses",
            "aba 1.1",
            "Emiss\u00e3o menos resgate do DPMFi, m\u00eas a m\u00eas. Sem m\u00e9dia de 3 meses, "
            "por decis\u00e3o de quem l\u00ea. Cobre 100% do DPMFi.",
            True, "5 anos", _fig_net),
    Grafico("funding_indexador", "Funding",
            "Emiss\u00e3o do DPMFi por indexador, mensal",
            "aba 1.2",
            "Emiss\u00e3o bruta, em reais do m\u00eas. Cobre 100% da emiss\u00e3o do DPMFi.",
            True, "5 anos", _fig_emissao_indexador),
    Grafico("funding_anual", "Funding",
            "Composi\u00e7\u00e3o anual da emiss\u00e3o, em 100%",
            "aba 1.2",
            "Por indexador, e n\u00e3o por papel: pela aba 1.2 a cobertura \u00e9 100% da "
            "emiss\u00e3o, contra 93% a 97% se viesse dos leil\u00f5es. O ano ainda aberto "
            "leva asterisco.",
            True, "5 anos", _fig_emissao_anual),
    Grafico("estoque_composicao", "Estoque",
            "Composi\u00e7\u00e3o da DPF por indexador, com a banda do PAF",
            "aba 2.1 e referencia/paf_bandas.csv",
            "Participa\u00e7\u00e3o de cada indexador na DPF. A banda \u00e9 a meta do PAF, ano "
            "a ano; onde houve revis\u00e3o, a banda original aparece pontilhada. "
            "Abre na s\u00e9rie completa: o c\u00e2mbio sai de 51,0% em set/2002 para 3,7%.",
            True, "completa", _fig_composicao),
    Grafico("detentores_participacao", "Detentores",
            "Participa\u00e7\u00e3o por grupo, e a varia\u00e7\u00e3o em 12 meses",
            "aba 2.7",
            "Os oito detentores da aba agrupados em cinco. A varia\u00e7\u00e3o \u00e9 contra o "
            "mesmo m\u00eas do ano anterior, em pontos percentuais.",
            False, None, _fig_participacao),
    Grafico("detentores_papel", "Detentores",
            "Quem carrega cada papel",
            "aba 2.8",
            "Participa\u00e7\u00e3o de cada detentor dentro de cada papel, no \u00faltimo m\u00eas. "
            "R\u00f3tulo s\u00f3 nas fatias de 10% ou mais.",
            False, None, _fig_por_papel),
    Grafico("detentores_financeiro", "Detentores",
            "Financeiro por detentor, oito pain\u00e9is",
            "aba 2.8",
            "Cada painel tem escala pr\u00f3pria: os detentores diferem em ordem de "
            "grandeza. S\u00e9rie come\u00e7a em fev/2011, n\u00e3o em jan/2007 como a 2.7.",
            True, "5 anos", _fig_financeiro_detentor),
    Grafico("vencimentos_cronograma", "Vencimentos",
            "Cronograma de vencimentos, com o balde da cauda",
            "aba 3.4",
            "Os 60 meses que a aba detalha (6.913,8 bi) mais o balde 'Ap\u00f3s 5 "
            "anos' (2.006,9 bi). 2026 \u00e9 jul\u2013dez e 2031 \u00e9 jan\u2013jun.",
            False, None, _fig_cronograma),
    Grafico("vencimentos_faixas", "Vencimentos",
            "Composi\u00e7\u00e3o da DPF por horizonte, com a banda do PAF",
            "aba 3.1 e aba 5.7",
            "A banda do vincendo em 12 meses \u00e9 publicada na aba 5.7 at\u00e9 2022; "
            "depois disso n\u00e3o h\u00e1 banda, e nada \u00e9 desenhado.",
            False, None, _fig_faixas),
    Grafico("prazo_medio", "Prazo",
            "Prazo m\u00e9dio por n\u00edvel, com a banda do PAF",
            "aba 3.7 e referencia/paf_bandas.csv",
            "R\u00f3tulo na DPMFi e na DPFe; a DPF \u00e9 linha de contexto. A banda \u00e9 a "
            "meta do PAF para o prazo m\u00e9dio da DPF.",
            False, None, _fig_prazo),
    Grafico("custo_estoque", "Custo",
            "Custo do estoque contra a Selic e o IPCA",
            "abas 4.1 e 4.2, e vna.csv",
            "Custo acumulado em 12 meses. A Selic e o IPCA saem da varia\u00e7\u00e3o de 12 "
            "meses do nosso pr\u00f3prio VNA, e come\u00e7am em jan/2011.",
            True, "5 anos", _fig_custo),
    Grafico("reserva_13m", "Reserva",
            "Reserva de liquidez, treze meses",
            "aba 6.1",
            "O formato da p\u00e1gina do RMD, para apresenta\u00e7\u00e3o. O eixo do \u00edndice "
            "come\u00e7a em zero.",
            False, None, _fig_reserva_13m),
    Grafico("reserva_serie", "Reserva",
            "Reserva de liquidez, s\u00e9rie longa com a folga",
            "aba 6.1",
            "A folga \u00e9 a reserva menos o valor prudencial. Em jan e fev/2015 ela "
            "foi negativa, e esses dois meses aparecem em vermelho.",
            True, "5 anos", _fig_reserva),
    Grafico("perfil_completo", "Candidatos",
            "Perfil completo de vencimentos, at\u00e9 2084",
            "aba 2.2",
            "Papel a papel, diferente do cronograma, que vem da 3.4. Os dois n\u00e3o "
            "fecham: 8.904,1 bi aqui contra 8.920,7 l\u00e1, e a causa dos 16,6 bi de "
            "diferen\u00e7a est\u00e1 em aberto.",
            False, None, _fig_perfil_completo),
    Grafico("custo_emissao", "Candidatos",
            "Custo de emiss\u00e3o contra o custo do estoque",
            "abas 4.2 e 4.3",
            "DPMFi. Emite-se a 14,20% e carrega-se a 13,19%: a d\u00edvida encarece "
            "sem que nenhuma decis\u00e3o nova seja tomada.",
            True, "5 anos", _fig_custo_emissao),
    Grafico("emissao_papel", "Candidatos",
            "Composi\u00e7\u00e3o anual da emiss\u00e3o por papel, dos leil\u00f5es",
            "leiloes.csv",
            "Recusado como gr\u00e1fico principal: os leil\u00f5es cobrem de 90,5% a 97,3% "
            "da emiss\u00e3o que o RMD registra, contra 100% da aba 1.2.",
            True, "5 anos", _fig_emissao_papel),
]
```

- [ ] **Passo 5: a montagem do HTML**

```python
# continuacao de src/tesouro/graficos/dashboard.py

_CSS = """
:root { --tinta: #1a1a1a; --fraco: #666; --linha: #e3e3e3; --fundo: #fff; }
* { box-sizing: border-box; }
body { margin: 0; font-family: Segoe UI, Arial, sans-serif; color: var(--tinta);
       background: var(--fundo); }
#indice { position: fixed; top: 0; left: 0; width: 250px; height: 100vh;
          overflow-y: auto; border-right: 1px solid var(--linha);
          padding: 18px 14px; font-size: 13.5px; }
#indice h1 { font-size: 15px; margin: 0 0 4px; }
#indice .data { color: var(--fraco); font-size: 12px; margin-bottom: 14px; }
#indice .grupo { font-weight: 600; margin: 12px 0 4px; font-size: 12px;
                 text-transform: uppercase; letter-spacing: .04em;
                 color: var(--fraco); }
#indice a { display: block; color: var(--tinta); text-decoration: none;
            padding: 3px 0 3px 8px; border-left: 2px solid transparent; }
#indice a:hover { border-left-color: var(--tinta); }
main { margin-left: 250px; padding: 22px 30px 60px; max-width: 1180px; }
#troca-periodo { position: sticky; top: 0; background: var(--fundo);
                 padding: 10px 0; border-bottom: 1px solid var(--linha);
                 z-index: 5; }
#troca-periodo button { font: inherit; padding: 5px 14px; margin-right: 6px;
                        border: 1px solid var(--linha); background: #fff;
                        cursor: pointer; border-radius: 3px; }
#troca-periodo button.ativo { background: var(--tinta); color: #fff;
                              border-color: var(--tinta); }
section { margin: 34px 0 0; padding-top: 6px; }
section h2 { font-size: 17px; margin: 0 0 2px; }
.legenda { color: var(--fraco); font-size: 12.5px; margin: 6px 0 0;
           max-width: 900px; line-height: 1.45; }
.fonte { color: var(--fraco); font-size: 12px; margin: 2px 0 10px; }
svg { max-width: 100%; height: auto; }
"""

_JS = """
function trocaPeriodo(janela) {
  document.querySelectorAll('[data-grafico]').forEach(function (bloco) {
    var alvo = bloco.parentElement.querySelector('[data-janela="' + janela + '"]');
    if (alvo) { bloco.style.display = (bloco === alvo) ? '' : 'none'; }
  });
  document.querySelectorAll('#troca-periodo button').forEach(function (b) {
    b.classList.toggle('ativo', b.dataset.janela === janela);
  });
}
"""


def svg_de(figura):
    """SVG pronto para embutir: sem prologo XML e sem DOCTYPE.

    O matplotlib escreve '<?xml ...?>' e '<!DOCTYPE svg ...>' antes do '<svg'.
    Embutir isso no meio de um HTML e invalido, entao tudo antes do primeiro
    '<svg' sai fora.

    A gravacao passa por estilo.salvar_svg, que e o unico lugar do projeto que
    chama savefig para SVG: e la que a data de criacao e suprimida, sem o que o
    teste de reprodutibilidade do dashboard nao passa.
    """
    buffer = io.StringIO()
    estilo.salvar_svg(figura, buffer)
    plt.close(figura)
    bruto = buffer.getvalue()
    return bruto[bruto.index("<svg"):]


def _bloco(grafico, recortes):
    """Uma secao: titulo, as versoes do SVG, a fonte e a legenda."""
    partes = [f'<section id="{grafico.id}">',
              f"  <h2>{grafico.titulo}</h2>"]

    usados = recortes if grafico.janela else recortes[:1]
    for nome, janela in usados:
        visivel = "" if (nome == grafico.padrao or len(usados) == 1) \
            else ' style="display:none"'
        svg = svg_de(grafico.figura(janela))
        partes.append(f'  <div data-grafico="{grafico.id}" '
                      f'data-janela="{nome}"{visivel}>{svg}</div>')

    partes.append(f'  <p class="fonte">Fonte: {grafico.fonte}</p>')
    partes.append(f'  <p class="legenda">{grafico.nota}</p>')
    partes.append("</section>")
    return "\n".join(partes)


def _indice():
    linhas = ['<nav id="indice">', "  <h1>D\u00edvida P\u00fablica Federal</h1>"]
    for grupo in GRUPOS:
        do_grupo = [g for g in REGISTRO if g.grupo == grupo]
        if not do_grupo:
            continue
        linhas.append(f'  <div class="grupo">{grupo}</div>')
        for g in do_grupo:
            linhas.append(f'  <a href="#{g.id}">{g.titulo}</a>')
    linhas.append("</nav>")
    return "\n".join(linhas)


def monta(recortes=None):
    """O HTML inteiro, com os SVGs embutidos.

    'recortes' e uma lista de pares (nome, janela). Com um par so, o botao de
    periodo nao aparece -- e o caso do --de/--ate na linha de comando.
    """
    estilo.aplicar_estilo()
    recortes = list(recortes) if recortes else list(JANELAS)

    botoes = ""
    if len(recortes) > 1:
        marcas = "".join(
            f'<button data-janela="{nome}" onclick="trocaPeriodo(\'{nome}\')">'
            f"{nome}</button>" for nome, _ in recortes)
        botoes = f'<div id="troca-periodo">{marcas}</div>'

    corpo = "\n".join(_bloco(g, recortes) for g in REGISTRO)

    return (
        "<!doctype html>\n<html lang=\"pt-br\">\n<head>\n"
        '<meta charset="utf-8">\n'
        "<title>D\u00edvida P\u00fablica Federal</title>\n"
        f"<style>{_CSS}</style>\n</head>\n<body>\n"
        f"{_indice()}\n<main>\n{botoes}\n{corpo}\n</main>\n"
        f"<script>{_JS}</script>\n</body>\n</html>\n"
    )


def grava(caminho=None, recortes=None):
    """Grava o dashboard e devolve o caminho."""
    caminho = caminho or (config.PROCESSED_DIR / "dashboard.html")
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(monta(recortes), encoding="utf-8")
    return caminho
```

- [ ] **Passo 6: rodar, ver passar, e medir o tamanho**

```
$env:PYTHONPATH="src"; python -m pytest tests/test_dashboard.py -v
```

Esperado: 13 passed.

Agora **meça** — o limiar de 10 MB da spec é medido, não suposto:

```
$env:PYTHONPATH="src"; python -c "from tesouro.graficos import dashboard; c = dashboard.grava(); print(c, round(c.stat().st_size / 1024 / 1024, 2), 'MB')"
```

**Registre o número na spec**, na seção 4.1, no lugar de "o tamanho do arquivo é
desconhecido". Se passar de 10 MB, o teste já falhou no passo anterior e a decisão
registrada na spec entra em vigor: os SVGs saem para arquivos ao lado, o HTML os
referencia, e a spec anota que "um arquivo só" foi trocado por tamanho utilizável.

- [ ] **Passo 7: abrir o arquivo e olhar**

Nenhum teste desta tarefa olha para o desenho. Abra o HTML no navegador e confira,
uma vez, com o olho:

- o índice lateral rola e as âncoras saltam para o gráfico certo;
- o botão troca os nove gráficos que aceitam janela, e **não** mexe nos sete que não
  aceitam;
- a composição do estoque abre na série completa, e os outros em 5 anos;
- nenhum gráfico aparece cortado ou com legenda por cima do desenho.

- [ ] **Passo 8: confirmar que cada asserção tem dentes**

Para **cada** âncora, quebre a linha de produção que ela protege, rode, confirme a
falha, e desfaça:

- apague uma entrada do `REGISTRO` — os testes dos dezesseis, dos títulos e das
  legendas devem falhar;
- troque `janela=True` por `False` em qualquer entrada — o teste dos 25 SVGs e o das
  duas versões devem falhar;
- troque `padrao="completa"` da composição por `"5 anos"` — o teste do padrão deve
  falhar;
- devolva `bruto` inteiro no `svg_de` (sem cortar o prólogo) — o teste de
  referências externas deve falhar nas duas últimas asserções, porque o `<?xml` e o
  `<!DOCTYPE svg` passam a aparecer no meio do HTML;
- acrescente `<link rel="stylesheet" href="https://exemplo/x.css">` ao `monta` — o
  teste de referências externas deve falhar;
- comente a linha `matplotlib.rcParams["svg.hashsalt"]` do `estilo.aplicar_estilo` —
  `test_o_html_e_reprodutivel` deve falhar. **É a prova de que a Task 1 existe por um
  motivo.**

- [ ] **Passo 9: rodar a suíte inteira e commitar**

```
$env:PYTHONPATH="src"; python -m pytest -q
```

Esperado: 404 passed, 1 skipped.

```bash
git add src/tesouro/graficos/ tests/test_dashboard.py
git commit -m "Adiciona o registro dos graficos e a montagem do dashboard"
```

---

## Task 12: Linha de comando, pipeline e documentação

**Files:**
- Create: `src/tesouro/graficos/__main__.py`
- Modify: `src/tesouro/pipeline.py`
- Modify: `README.md`
- Modify: `docs/dicionario-de-dados.md`
- Test: `tests/test_graficos_cli.py`, e mais um teste em `tests/test_pipeline.py`

**Interfaces:**
- Produces:
  - `python -m tesouro.graficos` — gera as duas janelas padrão.
  - `--de AAAA-MM-DD --ate AAAA-MM-DD` — gera um recorte só, e o botão de período
    some porque só existe uma janela.
  - `--saida CAMINHO` — grava em outro lugar (usado pelos testes).
  - `main(argumentos=None)` -> int, o código de saída.
  - `pipeline.main` passa a gerar o dashboard depois das figuras.

**Por que esta tarefa existe.** Até aqui o dashboard só existe para quem sabe
importar um módulo Python. Esta tarefa é a que o entrega: um comando, uma linha no
pipeline, e a documentação que diz onde o arquivo aparece.

**Decisões que o código deve respeitar:**

- **Instrução em PowerShell primeiro e bash depois**, seguindo
  `docs/como-baixar.md:6-12`. Sintaxe bash sozinha falha na primeira linha no shell
  da usuária, e **isso já quebrou quatro vezes neste projeto**.
- **`--de` e `--ate` andam juntos.** Um sem o outro é erro com mensagem, não um
  recorte pela metade.
- **Nada é escrito em `data/raw/`.** É dado insubstituível, e um coletor de entrega
  anterior já destruiu snapshots ali em silêncio.

**Armadilhas medidas nesta tarefa:**

1. **O `pipeline.py` só grava o dashboard depois de `figuras.gravar_todas()`.** Os
   gráficos leem os CSVs que as etapas anteriores acabaram de escrever; gerar o
   dashboard antes produz um HTML com o dado do mês passado, e nada acusa.
2. **A falha do dashboard não pode derrubar o pipeline em silêncio nem passar
   despercebida.** O `paf.bandas` levanta de propósito quando a referência está
   quebrada (Task 4). Isso tem de aparecer como falha real na lista de `falhas` que
   o pipeline já mantém, do mesmo jeito que a coleta da Bloomberg — e fazer o
   pipeline sair com código diferente de zero.
3. **O `README.md` diz "vinte e dois CSVs"** e a Task 2 não muda esse número, mas o
   dashboard é saída nova e precisa aparecer. Sem isso, quem seguir o README não
   descobre que o arquivo existe.

- [ ] **Passo 1: escrever os testes que falham**

```python
# tests/test_graficos_cli.py
"""A linha de comando do dashboard.

Os testes gravam sempre em tmp_path: nenhum deles escreve em data/processed/, e
muito menos em data/raw/, que e dado insubstituivel.
"""
import matplotlib
matplotlib.use("Agg")
import pytest

from tesouro.graficos import __main__ as cli


def test_sem_argumento_gera_as_duas_janelas(tmp_path):
    saida = tmp_path / "dashboard.html"
    assert cli.main(["--saida", str(saida)]) == 0
    html = saida.read_text(encoding="utf-8")
    assert 'id="troca-periodo"' in html
    assert 'data-janela="5 anos"' in html
    assert 'data-janela="completa"' in html


def test_com_de_e_ate_gera_uma_janela_so_e_sem_botao(tmp_path):
    saida = tmp_path / "recorte.html"
    codigo = cli.main(["--de", "2021-01-01", "--ate", "2026-06-30",
                       "--saida", str(saida)])
    assert codigo == 0
    html = saida.read_text(encoding="utf-8")
    assert 'id="troca-periodo"' not in html
    assert 'data-janela="completa"' not in html
    # O recorte pedido vira o nome da janela, e aparece no atributo do bloco.
    assert 'data-janela="2021-01-01 a 2026-06-30"' in html


def test_de_sem_ate_falha_com_mensagem(tmp_path, capsys):
    codigo = cli.main(["--de", "2021-01-01", "--saida", str(tmp_path / "x.html")])
    assert codigo == 2
    assert "--ate" in capsys.readouterr().err
    assert not (tmp_path / "x.html").exists(), "nao pode gravar arquivo pela metade"


def test_data_invalida_falha_alto(tmp_path, capsys):
    codigo = cli.main(["--de", "01/01/2021", "--ate", "2026-06-30",
                       "--saida", str(tmp_path / "x.html")])
    assert codigo == 2
    erro = capsys.readouterr().err
    assert "AAAA-MM-DD" in erro
    assert not (tmp_path / "x.html").exists()


def test_ate_antes_de_de_falha(tmp_path, capsys):
    codigo = cli.main(["--de", "2026-01-01", "--ate", "2021-01-01",
                       "--saida", str(tmp_path / "x.html")])
    assert codigo == 2
    assert "anterior" in capsys.readouterr().err.lower()


def test_a_documentacao_ensina_powershell_antes_de_bash():
    # Sintaxe bash sozinha falha na primeira linha no shell da usuaria, e isso ja
    # quebrou quatro vezes neste projeto.
    from tesouro import config

    texto = (config.RAIZ / "README.md").read_text(encoding="utf-8")
    assert "python -m tesouro.graficos" in texto
    assert "dashboard.html" in texto

    pedaco = texto[texto.index("python -m tesouro.graficos") - 400:]
    posicao_ps = pedaco.index("$env:PYTHONPATH")
    posicao_bash = pedaco.index("PYTHONPATH=src python -m tesouro.graficos")
    assert posicao_ps < posicao_bash, "o bloco do bash veio antes do PowerShell"
```

```python
# acrescentar em tests/test_pipeline.py

def test_o_pipeline_grava_o_dashboard_depois_das_figuras(monkeypatch):
    # Os graficos leem os CSVs que as etapas anteriores acabaram de escrever:
    # gerar o dashboard antes produz um HTML com o dado do mes passado.
    from tesouro.graficos import dashboard

    chamadas = []
    _stub_gravacoes(monkeypatch, chamadas)
    monkeypatch.setattr(dashboard, "grava",
                        lambda *a, **k: chamadas.append("dashboard.grava"))

    assert pipeline.main(["--sem-coleta"]) == 0
    assert "dashboard.grava" in chamadas
    assert chamadas.index("dashboard.grava") > chamadas.index("gravar_todas")


def test_falha_do_dashboard_entra_nas_falhas_e_muda_o_codigo_de_saida(monkeypatch,
                                                                     capsys):
    # O paf.bandas levanta de proposito quando a referencia esta quebrada. Isso
    # tem de aparecer como falha real, nao sumir no meio do log.
    from tesouro.graficos import dashboard

    _stub_gravacoes(monkeypatch)

    def _explode(*args, **kwargs):
        raise ValueError("paf_bandas.csv esta invalido")

    monkeypatch.setattr(dashboard, "grava", _explode)

    assert pipeline.main(["--sem-coleta"]) == 1
    saida = capsys.readouterr().out
    assert "dashboard" in saida.lower()
    assert "paf_bandas.csv" in saida
```

- [ ] **Passo 2: rodar e ver falhar**

```
$env:PYTHONPATH="src"; python -m pytest tests/test_graficos_cli.py tests/test_pipeline.py -v
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'tesouro.graficos.__main__'`.

- [ ] **Passo 3: escrever a linha de comando**

```python
# src/tesouro/graficos/__main__.py
"""Gera o dashboard da divida.

    PowerShell:  $env:PYTHONPATH="src"; python -m tesouro.graficos
    bash:        PYTHONPATH=src python -m tesouro.graficos

Sem argumento, grava data/processed/dashboard.html com as duas janelas -- 5 anos e
serie completa -- e o botao que alterna entre elas.

Com --de e --ate, grava o recorte pedido, e o botao some porque so existe uma
janela. Os dois andam juntos: um sem o outro e erro, nao recorte pela metade.
"""

import argparse
import sys

import pandas as pd

from . import dashboard


def _data(texto, campo, erros):
    """Converte AAAA-MM-DD, acumulando o erro em vez de levantar.

    O formato vai EXPLICITO: pd.Timestamp("01/01/2021") aceita e devolve 1 de
    janeiro, entao a data em formato brasileiro passaria batido e o recorte sairia
    de um lugar que ninguem pediu.
    """
    try:
        return pd.to_datetime(texto, format="%Y-%m-%d")
    except (ValueError, TypeError):
        erros.append(f"{campo}: '{texto}' nao e uma data no formato AAAA-MM-DD")
        return None


def main(argumentos=None):
    analisador = argparse.ArgumentParser(
        prog="python -m tesouro.graficos", description=__doc__)
    analisador.add_argument("--de", help="inicio do recorte, AAAA-MM-DD")
    analisador.add_argument("--ate", help="fim do recorte, AAAA-MM-DD")
    analisador.add_argument("--saida", help="caminho do HTML a gravar")
    opcoes = analisador.parse_args(argumentos)

    erros = []
    if bool(opcoes.de) != bool(opcoes.ate):
        falta = "--ate" if opcoes.de else "--de"
        erros.append(f"{falta} tambem e necessario: o recorte precisa dos dois "
                     f"extremos, senao nao da para saber onde ele termina")

    recortes = None
    if opcoes.de and opcoes.ate:
        de = _data(opcoes.de, "--de", erros)
        ate = _data(opcoes.ate, "--ate", erros)
        if de is not None and ate is not None:
            if ate < de:
                erros.append(f"--ate ({opcoes.ate}) e anterior a --de "
                             f"({opcoes.de})")
            else:
                recortes = [(f"{opcoes.de} a {opcoes.ate}", (de, ate))]

    if erros:
        for erro in erros:
            print(f"erro: {erro}", file=sys.stderr)
        return 2

    from pathlib import Path
    caminho = Path(opcoes.saida) if opcoes.saida else None
    gravado = dashboard.grava(caminho, recortes)
    print(f"dashboard gravado em {gravado}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Passo 4: pendurar no pipeline**

Em `src/tesouro/pipeline.py`, **depois** do bloco das figuras:

```python
    print("\n--- dashboard ---")
    try:
        from .graficos import dashboard
        caminho = dashboard.grava()
        print(f"dashboard gravado em {caminho}")
    except Exception as erro:               # noqa: BLE001
        # O paf.bandas levanta de proposito quando referencia/paf_bandas.csv esta
        # quebrado -- decisao da spec, secao 6: banda quebrada nao vira grafico
        # com banda errada. Aqui isso vira falha visivel e codigo de saida 1, do
        # mesmo jeito que a coleta da Bloomberg, em vez de sumir no meio do log.
        mensagem = f"a geracao do dashboard FALHOU: {erro}"
        print(f"ATENCAO: {mensagem}")
        falhas.append(mensagem)
```

- [ ] **Passo 5: documentar**

No `README.md`, logo depois do parágrafo que fala dos vinte e dois CSVs:

```markdown
### O dashboard

Os dezesseis gráficos da dívida num arquivo HTML autocontido, que abre com duplo
clique e continua funcionando copiado para outra máquina ou mandado por e-mail.

PowerShell:

    $env:PYTHONPATH="src"; python -m tesouro.graficos

bash:

    PYTHONPATH=src python -m tesouro.graficos

Grava `data/processed/dashboard.html` com duas janelas — 5 anos e série completa —
e um botão no topo que alterna entre elas. Para um recorte específico, com o botão
suprimido porque só existe uma janela:

    $env:PYTHONPATH="src"; python -m tesouro.graficos --de 2021-01-01 --ate 2026-06-30
    PYTHONPATH=src python -m tesouro.graficos --de 2021-01-01 --ate 2026-06-30

O `pipeline` já gera o dashboard no fim, depois de reescrever os CSVs; o comando
acima serve para regerar sem rodar o pipeline inteiro.
```

E em `docs/dicionario-de-dados.md`, uma entrada para `dashboard.html`: o que é, de
quais CSVs sai, e a observação de que ele é **derivado** — apagar não perde nada,
porque o pipeline regenera.

- [ ] **Passo 6: rodar e ver passar**

```
$env:PYTHONPATH="src"; python -m pytest tests/test_graficos_cli.py tests/test_pipeline.py -v
```

Esperado: 6 passed no arquivo da linha de comando, e o de pipeline com os dois
novos passando junto com os que já existiam.

- [ ] **Passo 7: confirmar que cada asserção tem dentes**

Para **cada** âncora, quebre a linha de produção que ela protege, rode, confirme a
falha, e desfaça:

- troque `!=` por `and` na conferência de `--de`/`--ate` — o teste do `--de` sozinho
  deve falhar;
- devolva `0` em vez de `2` quando há erros — três testes devem falhar;
- grave o arquivo **antes** de conferir os erros — os testes que verificam
  `not exists()` devem falhar. É o que impede um HTML pela metade em disco;
- mova a geração do dashboard para **antes** de `figuras.gravar_todas()` no pipeline
  — `test_o_pipeline_grava_o_dashboard_depois_das_figuras` deve falhar;
- troque o `except` do pipeline por um `pass` silencioso — o teste do código de
  saída deve falhar;
- **inverta os dois blocos no README**, pondo o bash antes do PowerShell — o teste
  da documentação deve falhar. Esse teste existe porque a ordem já foi trocada
  quatro vezes neste projeto, sempre por distração.

- [ ] **Passo 8: rodar tudo de ponta a ponta, de verdade**

Os testes usam stub nas gravações. Uma vez, à mão, rode o pipeline inteiro sem rede
e confirme que o dashboard sai com o dado de hoje:

```
$env:PYTHONPATH="src"; python -m tesouro.pipeline --sem-coleta
```

Esperado: termina com `concluido.`, sem nenhuma linha `ATENCAO:`, e
`data/processed/dashboard.html` com a data de modificação de agora.

Abra o arquivo e confirme, com o olho, que a composição de jun/2026 mostra
**21,0 / 25,9 / 49,3 / 3,7** — o mesmo número do teste, agora na tela.

- [ ] **Passo 9: rodar a suíte inteira e commitar**

```
$env:PYTHONPATH="src"; python -m pytest -q
```

Esperado: 412 passed, 1 skipped.

```bash
git add src/tesouro/ tests/ README.md docs/dicionario-de-dados.md
git commit -m "Adiciona a linha de comando do dashboard e o pendura no pipeline"
```

---

## Fechamento da entrega

Depois da Task 12, antes de considerar a entrega pronta:

- [ ] **Rodar a suíte inteira uma última vez** e confirmar **412 passed, 1
  skipped**. O pulado é o teste do PU contra o `PX_DIRTY_MID`, que aguarda
  autorização para puxar `bbg_precos_*.csv` — ele estava pulado antes desta entrega
  e continua.
- [ ] **Registrar na spec o tamanho medido do `dashboard.html`** (seção 4.1), no
  lugar de "o tamanho do arquivo é desconhecido".
- [ ] **Corrigir a seção 4.2 da spec**: são **nove** gráficos com janela e **25**
  SVGs, não sete e 23 (ver a Task 11).
- [ ] **Usar `superpowers:requesting-code-review`** sobre a branch inteira antes de
  falar em merge. As entregas anteriores mostraram que a revisão de branch encontra
  o que a revisão tarefa a tarefa não encontra.
- [ ] **Não mergear sem a dona do projeto pedir.** As branches `dv01-decay` e
  `dashboard` ficam separadas até ela decidir — decisão dela, registrada.

**O que fica explicitamente para depois, e não é esquecimento:**

| assunto | onde está registrado |
|---|---|
| Absorver o `figuras.py` da entrega 2 no pacote novo | spec, seção 3.4 |
| A causa dos 16,6 bi entre a aba 3.4 e a 2.2 | spec, seção 10; travado por teste na Task 10 |
| A divergência de 12 meses dos detentores contra o slide | spec, seção 10 |
| O `realizado` de 2025 errado em `referencia/paf_bandas.csv` | Task 7, armadilha 3; não é lido por nada |
| Decomposição do custo de emissão em taxa mais indexador | spec, seção 2 (fora do escopo) |
| Interatividade dentro do gráfico | spec, seção 10; o código já nasce separado para a troca |
