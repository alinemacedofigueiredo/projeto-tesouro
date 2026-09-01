# As âncoras do RMD de julho — plano de implementação

> **Para quem executa:** SUB-SKILL OBRIGATÓRIA: use `superpowers:subagent-driven-development` (recomendado) ou `superpowers:executing-plans` para implementar tarefa a tarefa. Os passos usam `- [ ]` para acompanhamento.

**Objetivo:** Devolver ao verde os 60 testes que ficaram vermelhos porque o RMD virou de junho para julho — **sem que nenhum deles vire espelho** do nosso próprio código.

**Arquitetura:** Não há código de produção nesta entrega. O trabalho é reescrever asserções, e a única coisa nova é `tests/anexo.py`: um leitor que abre o anexo do RMD **direto**, sem passar pelo nosso parser, para que o valor novo de cada âncora do tipo §3.1 venha da fonte e não de nós.

**Tech Stack:** Python 3.12, pandas, pytest. Sem dependência nova.

**Spec:** `docs/superpowers/specs/2026-08-26-ancoras-do-rmd-de-julho-design.md` — leia as seções 2, 2.1 e 3 antes da primeira tarefa. Elas explicam por que este trabalho é perigoso.

---

## Por que este plano é diferente dos outros

Em quase toda entrega, errar faz o teste ficar vermelho. **Aqui, errar faz o teste ficar verde.**

Se você rodar o teste, pegar o número que o nosso código imprimiu e escrever na asserção, ele passa. Passa hoje, passa mês que vem, passa para sempre — e não protege mais nada. Vira a afirmação de que o código produz o que o código produz.

Foram essas âncoras que acharam a coluna "Demais" zerada desde 2006, o câmbio que era a DPFe, e os 401 leilões que mudavam de lado. Se elas virarem espelho, o projeto perde a rede que pega o defeito que ele mais teme — um número plausível que não é o que diz ser — e perde **em silêncio**.

**A regra que vale em toda tarefa: o valor novo não pode sair do nosso código.**

---

## Restrições globais

- **Nada de acento LITERAL em `.py`** — `tests/**/*.py` está sob `test_todo_o_projeto_e_ascii` (`tests/test_estilo.py:89`). Onde o texto precisa sair acentuado, use escape `\uXXXX`: o fonte fica ASCII **e** o valor sai acentuado em execução. As duas coisas ao mesmo tempo, sem escolher. Isso vale também para string usada como DADO (rótulo de indexador, chave de filtro): o VALOR tem de continuar batendo com a coluna do CSV, então continua acentuado; o que muda é só como se escreve.
- **Gravar arquivo:** `caminho.write_bytes(texto.encode("utf-8"))`. O `write_text` deste ambiente trunca antes de codificar e já zerou três arquivos.
- **Determinismo:** nada de iterar `set`, nada de `pd.Timestamp.today()` dentro de teste.
- **Nada de tocar em `src/`.** Se alguma âncora só fecha mudando código de produção, **pare e relate**: isso é defeito achado, e vira decisão dela. Não é conserto silencioso dentro desta entrega (spec §5).
- **Toda âncora nova leva a procedência no comentário**, em uma linha: de onde o número veio. `# aba 2.4 do anexo de julho` ou `# coerencia: as partes somam o todo`. Sem isso a tarefa não está pronta.
- **Rodar a suíte inteira leva ~15 minutos.** Rode só os testes da sua tarefa enquanto trabalha.

---

## O inventário, medido em 01/09/2026

66 vermelhos ao todo. **6 são da revisão do PAF** e ficam de fora deste plano — a divisão foi medida revertendo `referencia/paf_bandas.csv` e rodando os mesmos vermelhos de novo. Os 60 que sobram, por arquivo:

> **A contagem subiu de 58 para 60 em 01/09/2026**, e não por causa das mudanças na rolagem: as duas novas continuaram vermelhas com a rolagem revertida. Elas se moveram quando o pipeline reprocessou o DV e o decay já com o VNA de julho da Bloomberg. As quatro mudanças do motor (juro real, carrego das emissões passadas e futuras) **não acrescentaram nenhuma falha** — medido rodando a suíte inteira depois delas.

| arquivo | quantos | tipo da spec |
|---|---|---|
| `test_graficos_candidatos.py` | 9 | §3.4 coerência |
| `test_graficos_vencimentos.py` | 8 | §3.1 anexo |
| `test_graficos_detentores.py` | 6 | §3.1 anexo |
| `test_graficos_custo.py` | 6 | §3.1 anexo |
| `test_graficos_funding.py` | 5 | §3.1 anexo |
| `test_graficos_estoque.py` | 6 | §3.1 anexo |
| `test_graficos_reserva.py` | 4 | §3.1 anexo |
| `test_graficos_prazo.py` | 3 | §3.1 anexo |
| `test_decay.py` | 3 | §3.2 data + §3.4 |
| `test_conferencia_detentores.py` | 3 | §3.3 duas fontes |
| `test_resultado.py` | 2 | §3.4 coerência |
| `test_figuras.py` | 2 | §3.2 data + §3.4 valores |
| `test_dv.py` | 1 | §3.4 coerência |
| `test_dashboard.py` | 1 | §3.2 data no lugar errado |
| `test_curva.py` | 1 | §3.1 valor medido da implicita |

A lista completa, nó a nó, está em `git show 246819e` (a spec) e sai de novo com:

```bash
PYTHONPATH=src python -m pytest -q --tb=no -rf
```

---

## Task 0: Confirmar que as três fontes estão no mesmo mês

**Cinco minutos, e é a tarefa que impede o plano de repetir o erro que a spec §2.1 documenta.**

A primeira contagem desta entrega deu **65** e estava errada: foi tirada com o VNA de julho ainda faltando. Sete daquelas falhas não eram âncora nenhuma — eram testes corretos reclamando de dado incompleto, e sumiram sozinhas quando a Bloomberg de julho entrou. Um quinto do trabalho ia ser despachado para consertar testes que não tinham nada de errado, e cada "conserto" teria reescrito uma âncora boa.

Um vermelho tirado de base incompleta não diz qual dos dois problemas ele é.

**Files:** Nenhum. É verificação.

- [ ] **Passo 1: conferir o mês de cada fonte**

```bash
PYTHONPATH=src python -c "
import pandas as pd
from tesouro import config
for nome in ('composicao_dpf.csv', 'estoque_dpf.csv'):
    d = pd.read_csv(config.PROCESSED_DIR / nome)
    print('%-32s ate %s' % (nome, d['data'].max()))
"
ls -la data/raw/rmd/ data/raw/bloomberg/ | tail -20
```

- [ ] **Passo 2: decidir**

As três — RMD, Bloomberg e leilões — têm de estar no mesmo mês (julho/2026).

**Se alguma estiver atrás, PARE.** Não comece a reescrever âncora. Relate qual fonte está atrasada e o que falta, e espere. Reescrever âncora contra base incompleta é a fábrica de espelhos da §2, só que com trabalho extra.

- [ ] **Passo 3: registrar no ledger** que as três foram conferidas e em que mês estão.

---

## Task 1: `tests/anexo.py` — o leitor que não passa por nós

Esta é a fundação das oito tarefas do tipo §3.1. Sem ela, cada uma inventaria o seu próprio jeito de ler o Excel, e a primeira que errasse contaminaria as outras.

**Files:**
- Create: `tests/anexo.py`
- Test: `tests/test_anexo.py`

**Interfaces:**
- Produz, e as tarefas seguintes consomem:
  ```
  anexo.caminho(mes="julho") -> Path      # ESCOLHE PELO NOME, nao pelo mtime
  anexo.aba(nome) -> DataFrame            # a aba crua, header=None, sem parser nosso
  ```

**Por que escolher pelo nome.** `leitura_rmd.caminho_do_rmd()` escolhe o anexo mais recente **pelo mtime do arquivo**. Este projeto vive dentro do OneDrive, que reescreve arquivo e mexe em mtime por conta própria — se ele tocar no anexo de junho, o leitor passaria a ler junho sem avisar, e as âncoras de julho seriam conferidas contra o mês errado. Aqui a escolha é pelo nome, que não muda sozinho.

- [ ] **Passo 1: escrever o teste que falha**

Em `tests/test_anexo.py`:

```python
"""O leitor do anexo, que existe para NAO passar pelo nosso parser."""
import pandas as pd
import pytest

from tesouro import config

import anexo


def test_o_anexo_e_escolhido_pelo_NOME_e_nao_pelo_mtime():
    """A escolha por mtime e fragil dentro do OneDrive.

    leitura_rmd.caminho_do_rmd() usa max(..., key=mtime). O OneDrive reescreve
    arquivo por conta propria; se tocasse no anexo de junho, o leitor passaria a
    ler junho em silencio e as ancoras de julho seriam conferidas contra o mes
    errado. Este leitor existe para conferir ancora, entao escolhe pelo nome.
    """
    assert "Julho" in anexo.caminho("julho").name
    assert "Junho" in anexo.caminho("junho").name
    assert anexo.caminho("julho") != anexo.caminho("junho")


def test_pede_mes_que_nao_existe_e_erro_claro():
    with pytest.raises(FileNotFoundError, match="marco"):
        anexo.caminho("marco")


def test_a_aba_vem_crua_e_nao_interpretada():
    """Se viesse com header, ja seria interpretacao -- e interpretacao e o que
    este modulo existe para evitar."""
    bruto = anexo.aba("2.4")
    assert isinstance(bruto, pd.DataFrame)
    assert len(bruto) > 5
    # header=None: as colunas sao inteiros, e nao rotulos ja lidos por alguem.
    assert list(bruto.columns) == list(range(len(bruto.columns)))
```

- [ ] **Passo 2: rodar e ver falhar**

```bash
PYTHONPATH=src python -m pytest tests/test_anexo.py -q
```

Esperado: `ModuleNotFoundError: No module named 'anexo'`.

- [ ] **Passo 3: implementar**

Crie `tests/anexo.py`:

```python
"""Le o anexo do RMD DIRETO, sem passar pelo parser do projeto.

Uma ancora de valor conferida contra o nosso proprio parser nao confere nada:
se o parser errar, a ancora erra junto e fica verde. Este modulo abre o .xlsx
e devolve a celula crua, para que o numero da assercao venha da FONTE.

Mora em tests/ de proposito. Nao e codigo de producao e nada em src/ o importa.
"""
from pathlib import Path

import pandas as pd

from tesouro import config


def caminho(mes="julho"):
    """O anexo daquele mes, escolhido PELO NOME.

    leitura_rmd.caminho_do_rmd() escolhe pelo mtime, que dentro do OneDrive nao
    e confiavel -- ele reescreve arquivo sozinho. Aqui a escolha nao muda por
    conta propria.
    """
    alvo = mes.strip().lower()
    for arquivo in sorted(config.RMD_DIR.glob("*.xlsx")):
        if alvo in arquivo.name.lower():
            return arquivo
    raise FileNotFoundError(
        f"nenhum anexo de {mes!r} em {config.RMD_DIR}; ha "
        f"{[p.name for p in sorted(config.RMD_DIR.glob('*.xlsx'))]}"
    )


def aba(nome, mes="julho"):
    """A aba crua: header=None, nada interpretado."""
    return pd.read_excel(caminho(mes), sheet_name=nome, header=None)
```

- [ ] **Passo 4: rodar e ver passar**

```bash
PYTHONPATH=src python -m pytest tests/test_anexo.py -q
```

Se `aba("2.4")` estourar por nome de aba, liste os nomes reais e ajuste o teste — **não o módulo**:

```bash
PYTHONPATH=src python -c "import pandas as pd, sys; sys.path.insert(0,'tests'); import anexo; print(pd.ExcelFile(anexo.caminho()).sheet_names)"
```

- [ ] **Passo 5: conferir os dentes**

Troque `if alvo in arquivo.name.lower()` por `if True` e rode: o teste do nome tem de ficar **vermelho**. Desfaça.

- [ ] **Passo 6: commit**

```bash
git add tests/anexo.py tests/test_anexo.py
git commit -m "O leitor do anexo, que confere ancora sem passar pelo nosso parser"
```

---

## Task 2: A camada 1, provada — a composição bate com o anexo

Antes de reescrever 44 âncoras contra o anexo, prove que a comparação anexo↔nosso-CSV funciona. Este é o único par já validado à mão, em 26/08/2026, e vira teste.

**Files:**
- Test: `tests/test_anexo.py` (acrescentar)

**Interfaces:**
- Consome: `anexo.aba` da Task 1

- [ ] **Passo 1: escrever o teste que falha**

```python
def test_a_composicao_do_nosso_CSV_bate_com_o_anexo():
    """CAMADA 1 da spec, secao 4: o valor vem da fonte, e nao de nos.

    Medido a mao em 26/08/2026 contra o anexo de julho, aba 2.4, em R$ milhoes:

        Prefixado         1.785,3461
        Indice Precos     2.417,3288
        Taxa Flutuante    4.747,2540
        Cambio              338,8513
        Total             9.288,7803

    Se o nosso parser passar a ler a coluna errada, este teste fica vermelho --
    e nenhuma ancora de valor do tipo 3.1 pegaria isso, porque todas elas
    comparam numero contra numero DEPOIS do parser.
    """
    import pandas as pd
    from tesouro import config

    do_anexo = {
        "Prefixado": 1785.3461,
        "Índice Preços": 2417.3288,
        "Taxa Flutuante": 4747.2540,
        "Câmbio": 338.8513,
    }
    nosso = pd.read_csv(config.PROCESSED_DIR / "composicao_dpf.csv")
    ultimo = nosso[nosso["data"] == nosso["data"].max()]
    por_indexador = ultimo.set_index("indexador")["valor_milhoes"] / 1000

    for indexador, esperado in do_anexo.items():
        obtido = float(por_indexador[indexador])
        assert obtido == pytest.approx(esperado, abs=0.001), (
            f"{indexador}: o anexo diz {esperado}, o nosso CSV diz {obtido}")

    assert float(por_indexador.sum()) == pytest.approx(9288.7803, abs=0.001)
```

- [ ] **Passo 2: rodar**

```bash
PYTHONPATH=src python -m pytest tests/test_anexo.py -q -k composicao
```

**Se falhar, PARE e relate.** Os cinco números acima foram conferidos contra o Excel à mão. Se o nosso CSV não bate com eles, isso é defeito no parser, não âncora desatualizada — e é exatamente o que este teste existe para achar. Não "conserte" mudando os números.

Se o nome da coluna ou do arquivo não bater, ajuste a leitura (não os valores) e siga.

- [ ] **Passo 3: conferir os dentes**

Mude `1785.3461` para `1785.4` e rode: vermelho. Desfaça.

- [ ] **Passo 4: commit**

```bash
git add tests/test_anexo.py
git commit -m "A composicao do nosso CSV conferida contra o anexo, e nao contra nos"
```

---

## O procedimento de cada âncora (tarefas 3 a 11)

As nove tarefas seguintes têm a **mesma forma**, mudando só o arquivo e os
números. Cada uma repete os passos por escrito, para quem receber só a sua
tarefa não depender desta seção; ela fica como visão de conjunto.

Para cada asserção vermelha do seu arquivo:

1. **Rode com `--tb=line`** para ver o obtido e o esperado:
   ```bash
   PYTHONPATH=src python -m pytest tests/<arquivo> -q --tb=line
   ```
2. **Classifique** pela spec §3: valor do anexo (§3.1), contagem/data (§3.2), duas fontes (§3.3), ou relação nossa (§3.4). A tabela do inventário diz o tipo dominante do arquivo, mas **cada asserção se classifica sozinha** — arquivo de tipo §3.1 pode ter uma linha §3.2 no meio.
3. **Se for §3.1:** pegue o valor novo do **anexo**, com `anexo.aba(...)`. Confira que o nosso CSV bate. Só então escreva na asserção.
4. **Se for §3.2:** pergunte primeiro **se a amarra devia existir**. Uma data cravada num teste que não é sobre aquela data é âncora no lugar errado; solte-a e trave a relação. Um exemplo já diagnosticado está na Task 8.
5. **Se for §3.4:** **não escreva o número novo.** Troque por conferência de coerência: as partes somam o todo, a série não tem buraco, o sinal está certo, a ordem entre os papéis se mantém. São propriedades que valem em qualquer mês — é isso que as torna melhores que um número para este grupo.
6. **Escreva a procedência** no comentário, em uma linha.
7. **Confira os dentes:** quebre a linha de produção que a asserção protege e confirme o vermelho. Desfaça. **Uma âncora que não fica vermelha quando o código quebra não protege nada, e não conta como pronta.**
8. **Rode o arquivo inteiro** e faça um commit por arquivo.

**Se em qualquer momento o valor do anexo não bater com o nosso CSV: pare e relate.** É defeito, não âncora.

---

## Task 3: `test_graficos_estoque.py` — 6 âncoras

**Files:** Modify: `tests/test_graficos_estoque.py`

Seis vermelhos, todos §3.1 (composição por indexador, o pico do câmbio, a soma 100%). São os que a Task 2 já provou serem conferíveis contra a aba 2.4 — use os mesmos números.

Atenção a `test_cada_mes_da_composicao_soma_100` e `test_a_area_de_100_por_cento_empilha_as_cinco_faixas`: se falharem por soma, é §3.4 (coerência) disfarçado de §3.1, e a asserção certa é "soma 100 em **todo** mês", sem número de mês nenhum.

- [ ] Passo 1: rodar e listar os seis
- [ ] Passo 2: classificar cada um
- [ ] Passo 3: obter os valores do anexo (Task 1)
- [ ] Passo 4: reescrever com procedência
- [ ] Passo 5: conferir os dentes de cada um
- [ ] Passo 6: `git commit -m "As ancoras do estoque, contra a aba 2.4 do anexo de julho"`

---

## Task 4: `test_graficos_vencimentos.py` — 8 âncoras

**Files:** Modify: `tests/test_graficos_vencimentos.py`

O maior grupo §3.1. Cronograma anual, o balde, os anos parciais das pontas, os sessenta meses, as faixas da DPF.

Dois avisos:

- `test_o_cronograma_mensal_tem_os_sessenta_meses` e `test_os_dois_anos_das_pontas_sao_parciais` são **§3.2**: contam janela, e a janela anda um mês a cada RMD. Pergunte se o número devia estar cravado, ou se a asserção certa é "sessenta meses **a partir da data-base**".
- `test_o_vincendo_de_hoje_esta_dentro_da_banda_de_2026` menciona banda, mas **não** é do PAF — foi medido e falha com a banda velha também. É §3.1.

- [ ] **Passo 1: listar os vermelhos deste arquivo** — `PYTHONPATH=src python -m pytest tests/<arquivo> -q --tb=line`
- [ ] **Passo 2: classificar cada asserção** pela spec §3: valor do anexo (§3.1), contagem/data (§3.2), duas fontes (§3.3), relação nossa (§3.4). O tipo do arquivo é o dominante; **cada asserção se classifica sozinha**
- [ ] **Passo 3: obter o valor novo da FONTE** — `anexo.aba(...)` da Task 1 se for §3.1; conferência de coerência se for §3.4; se for §3.2, perguntar antes se a amarra devia existir. **Nunca do nosso código**
- [ ] **Passo 4: conferir que o nosso CSV bate com o anexo.** Se não bater, **pare e relate** — é defeito, não âncora
- [ ] **Passo 5: reescrever, com a procedência no comentário**, em uma linha
- [ ] **Passo 6: conferir os dentes de cada um** — quebre a linha de produção que a asserção protege, confirme o vermelho, desfaça. Sem isso a tarefa não está pronta
- [ ] `git commit -m "As ancoras dos vencimentos, contra o anexo de julho"`

---

## Task 5: `test_graficos_custo.py` — 6 âncoras

**Files:** Modify: `tests/test_graficos_custo.py`

Custo médio, o acumulado de 12 meses, o VNA mensal e completo, a janela de 5 anos, os rótulos.

`test_a_selic_e_o_ipca_saem_do_nosso_vna` e `test_o_vna_e_mensal_e_completo` são **§3.4**: o VNA é cálculo nosso. Troque por coerência — a série não tem buraco, e o VNA cresce monotonicamente dentro de cada índice.

`test_o_custo_de_junho_de_2026_bate_com_o_medido` traz o mês no nome. Se o teste é sobre **junho**, ele pode continuar sendo, fixando a leitura naquele mês; se é sobre "o último mês", o nome mente e tem de mudar junto. Decida e diga qual foi no commit.

- [ ] **Passo 1: listar os vermelhos deste arquivo** — `PYTHONPATH=src python -m pytest tests/<arquivo> -q --tb=line`
- [ ] **Passo 2: classificar cada asserção** pela spec §3: valor do anexo (§3.1), contagem/data (§3.2), duas fontes (§3.3), relação nossa (§3.4). O tipo do arquivo é o dominante; **cada asserção se classifica sozinha**
- [ ] **Passo 3: obter o valor novo da FONTE** — `anexo.aba(...)` da Task 1 se for §3.1; conferência de coerência se for §3.4; se for §3.2, perguntar antes se a amarra devia existir. **Nunca do nosso código**
- [ ] **Passo 4: conferir que o nosso CSV bate com o anexo.** Se não bater, **pare e relate** — é defeito, não âncora
- [ ] **Passo 5: reescrever, com a procedência no comentário**, em uma linha
- [ ] **Passo 6: conferir os dentes de cada um** — quebre a linha de produção que a asserção protege, confirme o vermelho, desfaça. Sem isso a tarefa não está pronta
- [ ] `git commit -m "As ancoras do custo: valor do anexo, coerencia no VNA"`

---

## Task 6: `test_graficos_prazo.py` (3) e `test_graficos_reserva.py` (4) — 7 âncoras

**Files:** Modify: `tests/test_graficos_prazo.py`, `tests/test_graficos_reserva.py`

Juntas porque são pequenas e do mesmo tipo (§3.1, valor do anexo).

Na reserva, `test_a_folga_e_a_reserva_menos_o_prudencial` é **§3.4**: é uma identidade entre três números nossos. Ela não devia ter valor cravado nenhum — a asserção certa é a identidade, e ela vale em qualquer mês.

`test_a_versao_de_treze_meses_tem_treze_meses` é §3.2: contagem de janela.

- [ ] **Passo 1: listar os vermelhos deste arquivo** — `PYTHONPATH=src python -m pytest tests/<arquivo> -q --tb=line`
- [ ] **Passo 2: classificar cada asserção** pela spec §3: valor do anexo (§3.1), contagem/data (§3.2), duas fontes (§3.3), relação nossa (§3.4). O tipo do arquivo é o dominante; **cada asserção se classifica sozinha**
- [ ] **Passo 3: obter o valor novo da FONTE** — `anexo.aba(...)` da Task 1 se for §3.1; conferência de coerência se for §3.4; se for §3.2, perguntar antes se a amarra devia existir. **Nunca do nosso código**
- [ ] **Passo 4: conferir que o nosso CSV bate com o anexo.** Se não bater, **pare e relate** — é defeito, não âncora
- [ ] **Passo 5: reescrever, com a procedência no comentário**, em uma linha
- [ ] **Passo 6: conferir os dentes de cada um** — quebre a linha de produção que a asserção protege, confirme o vermelho, desfaça. Sem isso a tarefa não está pronta
- [ ] Dois commits, um por arquivo

---

## Task 7: `test_graficos_funding.py` (5) e `test_dashboard.py` (1) — 6 âncoras

**Files:** Modify: `tests/test_graficos_funding.py`, `tests/test_dashboard.py`

O de `test_dashboard.py` **já está diagnosticado** — economize o tempo:

`test_o_recorte_por_data_chega_nas_funcoes_de_dado` (linha ~338) crava a ponta da janela:

```python
par = (pd.Timestamp("2021-01-01"), pd.Timestamp("2026-06-30"))
cortado = funding.dados_net(par)
inteiro = funding.dados_net()
assert cortado.index.max() == inteiro.index.max()
```

O teste quer provar que **o recorte corta o começo e não o fim**. Com o dado indo até julho e o corte cravado em junho, ele falha por motivo certo: agora o recorte corta o fim também. É §3.2, âncora no lugar errado — a ponta tem de sair do próprio dado:

```python
    inteiro = funding.dados_net()
    # A ponta sai do DADO, e nao de uma data cravada: o teste e sobre o corte
    # do comeco, e cravar a ponta o fazia falhar a cada RMD por motivo nenhum.
    par = (pd.Timestamp("2021-01-01"), inteiro.index.max())
    cortado = funding.dados_net(par)
    assert cortado.index.min() >= par[0]
    assert cortado.index.max() == inteiro.index.max()
    assert len(cortado) < len(inteiro)
```

**Confira os dentes:** faça `dados_net` ignorar o início do par (usar sempre o índice inteiro) e confirme que `cortado.index.min() >= par[0]` fica vermelho. Desfaça.

Os cinco de funding são §3.1 (net do último mês, mm3, acumulado, emissão por indexador) mais um de rótulo.

- [ ] **Passo 1: listar os vermelhos deste arquivo** — `PYTHONPATH=src python -m pytest tests/<arquivo> -q --tb=line`
- [ ] **Passo 2: classificar cada asserção** pela spec §3: valor do anexo (§3.1), contagem/data (§3.2), duas fontes (§3.3), relação nossa (§3.4). O tipo do arquivo é o dominante; **cada asserção se classifica sozinha**
- [ ] **Passo 3: obter o valor novo da FONTE** — `anexo.aba(...)` da Task 1 se for §3.1; conferência de coerência se for §3.4; se for §3.2, perguntar antes se a amarra devia existir. **Nunca do nosso código**
- [ ] **Passo 4: conferir que o nosso CSV bate com o anexo.** Se não bater, **pare e relate** — é defeito, não âncora
- [ ] **Passo 5: reescrever, com a procedência no comentário**, em uma linha
- [ ] **Passo 6: conferir os dentes de cada um** — quebre a linha de produção que a asserção protege, confirme o vermelho, desfaça. Sem isso a tarefa não está pronta
- [ ] Dois commits, um por arquivo

---

## Task 8: `test_graficos_detentores.py` — 6 âncoras

**Files:** Modify: `tests/test_graficos_detentores.py`

§3.1, contra a aba de detentores do anexo. Participação, variação em reais, quebra por papel, financeiro por detentor.

**Não confunda com `test_conferencia_detentores.py`**, que é a Task 9 e tem outro problema.

- [ ] **Passo 1: listar os vermelhos deste arquivo** — `PYTHONPATH=src python -m pytest tests/<arquivo> -q --tb=line`
- [ ] **Passo 2: classificar cada asserção** pela spec §3: valor do anexo (§3.1), contagem/data (§3.2), duas fontes (§3.3), relação nossa (§3.4). O tipo do arquivo é o dominante; **cada asserção se classifica sozinha**
- [ ] **Passo 3: obter o valor novo da FONTE** — `anexo.aba(...)` da Task 1 se for §3.1; conferência de coerência se for §3.4; se for §3.2, perguntar antes se a amarra devia existir. **Nunca do nosso código**
- [ ] **Passo 4: conferir que o nosso CSV bate com o anexo.** Se não bater, **pare e relate** — é defeito, não âncora
- [ ] **Passo 5: reescrever, com a procedência no comentário**, em uma linha
- [ ] **Passo 6: conferir os dentes de cada um** — quebre a linha de produção que a asserção protege, confirme o vermelho, desfaça. Sem isso a tarefa não está pronta
- [ ] `git commit -m "As ancoras dos detentores, contra o anexo de julho"`

---

## Task 9: `test_conferencia_detentores.py` — 3 âncoras, e a única que muda de intenção

**Files:** Modify: `tests/test_conferencia_detentores.py`

Estes três comparam a **página do RMD** (HTML publicado) contra o **anexo**, para provar que as duas fontes concordam. O anexo virou julho; a página guardada é de junho. Estão comparando meses diferentes — daí a variação de 28,5 onde a tolerância é 0,15.

**Atualizar o número não resolve, e seria o pior conserto possível:** afrouxaria a tolerância até caber uma comparação entre meses diferentes, e o teste passaria a não testar nada.

**O conserto desta tarefa:** tornar explícito que é uma conferência **histórica de junho**, fixando as **duas** fontes naquele mês. O anexo de junho continua em `data/raw/rmd/`, e `anexo.aba(nome, mes="junho")` da Task 1 já sabe abri-lo.

```python
def test_a_pagina_e_o_anexo_de_JUNHO_concordam():
    """Conferencia HISTORICA, e as duas fontes ficam fixadas em junho.

    Este teste prova que a pagina do RMD e o anexo contam a mesma coisa. Ele so
    tem sentido com as duas fontes no MESMO mes -- e a pagina que guardamos e a
    de junho. Fixar o anexo em junho junto mantem a prova viva.

    Quando a pagina de julho entrar, este teste ganha o par de julho; ele nao
    deixa de valer, porque junho continua sendo verdade.
    """
```

**Isto muda o que o teste mede, e por isso é decisão dela.** Se ela preferir puxar a página de julho, é outro caminho — e esbarra no certificado do SERPRO, que hoje bloqueia o download. Faça o conserto acima, que preserva a prova e não fecha a outra porta, e **diga no commit que foi feito assim**.

- [ ] Passo 1: fixar as duas fontes em junho
- [ ] Passo 2: confirmar que a diferença volta para dentro de 0,15
- [ ] Passo 3: conferir os dentes — troque uma das duas fontes para julho e confirme o vermelho
- [ ] Passo 4: `git commit -m "A conferencia de detentores fixa as DUAS fontes em junho"`

---

## Task 10: `test_graficos_candidatos.py` (9), `test_resultado.py` (2), `test_decay.py` (3), `test_dv.py` (1) — 15 âncoras §3.4

**Files:** Modify: os quatro arquivos

O maior bloco, e o de regra mais simples: **nenhum destes números existe no anexo.** DV01, decay, resultado decomposto, candidatos — são cálculo nosso. Um valor novo aqui só pode sair do nosso código, e é exatamente a fábrica de espelhos da §2.

**Portanto: não escreva número novo neste bloco.** Troque cada âncora de valor por conferência de coerência.

Exemplos do que a coerência trava, e do que ela pega:

| em vez de | escreva | pega o quê |
|---|---|---|
| `assert round(x,1) == 8886.0` | as partes somam o todo | parcela caindo fora da soma |
| `assert len(serie) == 187` | a série vai da data-base até hoje sem buraco | mês faltando no meio |
| `assert base == date(2026,6,30)` | a base é a data-base do RMD carregado | base congelada num mês velho |
| `assert custo == -198.54` | o sinal está certo e a ordem entre os papéis se mantém | sinal trocado, papéis trocados |

Dois já diagnosticados, para você não gastar tempo:

- `test_decay.py:236` — `assert date(2026,7,31) == date(2026,6,30)`. Data cravada, §3.2 puro. A asserção certa é contra a data-base do RMD que está carregado, e não contra um dia escrito à mão.
- `test_graficos_candidatos.py:137` — `assert 188 == 187`. A série ganhou julho. Contagem que cresce um por mês: trave "um ponto por mês entre dezembro/2010 e a data-base, sem buraco", que é verdade em qualquer mês.

**O `KeyError: 'mai-26'`** que aparece neste bloco é a janela tendo andado: um rótulo de mês que saiu do recorte. Mesmo tratamento — o rótulo tem de sair da janela, não estar cravado.

- [ ] Passo 1: listar os 15 e classificar
- [ ] Passo 2: escrever a coerência de cada um
- [ ] Passo 3: **conferir os dentes de cada um** — este passo é o que separa coerência real de teste vazio. Uma asserção de coerência mal escrita ("o resultado é positivo") passa com qualquer número e é pior que a âncora que ela substituiu.
- [ ] Passo 4: quatro commits, um por arquivo

---

## Task 11: `test_figuras.py` — 2 âncoras

**Files:** Modify: `tests/test_figuras.py`

Duas, já classificadas (medido em 27/08/2026):

- **`test_figuras.py:46`** — `assert date(2026,7,31) == date(2026,6,30)`. Data cravada, §3.2 puro. Mesmo caso do `test_decay.py:236` da Task 10: a asserção certa é contra a data-base do RMD carregado, e não contra um dia escrito à mão.
- A outra compara uma lista de quatro valores contra `approx` (o obtido deu `-1468,44` contra `-1472,87` esperado). É §3.4 — cálculo nosso, sem fonte no anexo. **Não escreva o número novo**; troque por coerência.

- [ ] **Passo 1: listar os vermelhos deste arquivo** — `PYTHONPATH=src python -m pytest tests/<arquivo> -q --tb=line`
- [ ] **Passo 2: classificar cada asserção** pela spec §3: valor do anexo (§3.1), contagem/data (§3.2), duas fontes (§3.3), relação nossa (§3.4). O tipo do arquivo é o dominante; **cada asserção se classifica sozinha**
- [ ] **Passo 3: obter o valor novo da FONTE** — `anexo.aba(...)` da Task 1 se for §3.1; conferência de coerência se for §3.4; se for §3.2, perguntar antes se a amarra devia existir. **Nunca do nosso código**
- [ ] **Passo 4: conferir que o nosso CSV bate com o anexo.** Se não bater, **pare e relate** — é defeito, não âncora
- [ ] **Passo 5: reescrever, com a procedência no comentário**, em uma linha
- [ ] **Passo 6: conferir os dentes de cada um** — quebre a linha de produção que a asserção protege, confirme o vermelho, desfaça. Sem isso a tarefa não está pronta
- [ ] `git commit -m "As ancoras das figuras"`

---

## Task 12: As três provas de que a entrega não virou espelho

Esta tarefa é o motivo de todas as outras. Sem ela, não há como saber se as 58 viraram espelho — e o modo de falha desta entrega é justamente ser invisível.

**Files:** Nenhum modificado. É verificação.

- [ ] **Prova 1: a suíte inteira fica verde**

```bash
PYTHONPATH=src python -m pytest -q --tb=no -rf
```

Esperado: **6 vermelhos**, e todos da revisão do PAF (fora do escopo deste plano). Zero dos 60.

- [ ] **Prova 2: contra o RMD de junho, a suíte tem de FICAR VERMELHA**

Esta é a prova que a spec chama de final, e é a única que detecta espelho.

Se as âncoras novas passarem **nos dois meses**, elas não travam mês nenhum — viraram a afirmação de que o código produz o que o código produz, e a entrega falhou sem dizer.

**Não faça isso mexendo em data de arquivo.** `leitura_rmd.caminho_do_rmd()` escolhe pelo mtime, e conduzir a suíte por mtime dentro do OneDrive é pedir para o resultado mentir. Regenere os CSVs a partir do anexo de junho passando o caminho explícito:

```bash
PYTHONPATH=src python -c "
import sys; sys.path.insert(0, 'tests')
import anexo
print('vou reprocessar a partir de:', anexo.caminho('junho'))
"
```

Depois rode a suíte e confirme o vermelho. **Registre quantos ficaram vermelhos e quais** — esse número é o resultado da tarefa.

Ao terminar, **regenere de volta a partir de julho** e confirme com a Prova 1 de novo. Deixar a base em junho publicaria o mês errado.

- [ ] **Prova 3: o retrato**

Gere o PDF das sete páginas e compare com `data/processed/retrato-2026-08-26-rmd-junho.pdf`, guardado antes da virada.

Diferença **esperada**: um mês a mais nas séries, vencimentos que saíram, as bandas do PAF revisadas em três indicadores. Diferença **inesperada** em qualquer gráfico é defeito — relate, não conserte.

- [ ] **Passo final: commit do relatório**

Escreva o que as três provas deram em `docs/superpowers/plans/2026-08-27-ancoras-do-rmd-de-julho-resultado.md` e commite.

---

## Decisão que fica para ela, e que este plano não toma

**O critério de mtime** (`leitura_rmd.caminho_do_rmd`). Se o OneDrive tocar no anexo de junho depois do de julho, o projeto inteiro volta a junho em silêncio — sem exceção e sem aviso, publicando o mês errado. A folga medida em 26/08/2026 era de doze dias.

Este plano **contorna** o problema dentro de `tests/anexo.py`, escolhendo pelo nome. Não o conserta em `src/`, porque a spec §5 diz que defeito achado vira decisão dela. As opções, quando ela decidir: escolher pelo mês lido do nome, ou gravar o mês-base junto do CSV processado e conferir na leitura.
