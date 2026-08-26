# Entrega 5 — a simulação de emissão: plano de implementação

> **Para quem executa:** SUB-SKILL OBRIGATÓRIA: use `superpowers:subagent-driven-development` (recomendado) ou `superpowers:executing-plans` para implementar tarefa a tarefa. Os passos usam `- [ ]` para acompanhamento.

**Objetivo:** Um terceiro bloco na `paf.html` com três tabelas — uma por indexador — que respondem "quanto emitir por leilão, daqui até 31/12, para a dívida fechar em tal total com tal percentual neste papel".

**Arquitetura:** A conta é a projeção da entrega 4 invertida, e não usa nenhuma premissa nova. `rolagem.emissao_necessaria()` faz a conta (é dado, fica fora de `graficos/`); `graficos/simulacao.py` monta a tabela; `graficos/painel_paf.py` acrescenta a seção.

**Tech Stack:** Python 3.12, pandas, HTML gerado em string. Sem dependência nova.

**Spec:** `docs/superpowers/specs/2026-08-25-simulacao-de-emissao-design.md`

## Restrições globais

- **Nada de acento em código-fonte, comentário ou docstring.** Texto que vai para a tela usa escape `\uXXXX`. **NÃO desacentue strings usadas como dado** — rótulo de indexador desacentuado vira filtro que não casa e o termo vai a zero em silêncio (ruling 4 da entrega 4).
- **Gravar arquivo:** `caminho.write_bytes(texto.encode("utf-8"))`. `write_text` deste ambiente trunca antes de codificar e já zerou três arquivos.
- **Testes com dentes:** antes de dar um teste por pronto, quebre a linha que ele protege e confirme o vermelho.
- **Determinismo:** nada de iterar `set`, nada de `pd.Timestamp.today()` em teste.
- **Limiar de 10 MB por página**, guardado por teste.
- **Separação dado/desenho:** `dados_*()` devolve exatamente o que vai na tela e não importa matplotlib.

## Interfaces que já existem (conferidas em 25/08/2026)

```
rolagem.INDEXADORES        = ("Prefixado", "Índice Preços", "Taxa Flutuante")
rolagem.PARADOS            = ("Câmbio",)
rolagem._CARGA_DO_PREFIXADO = 0.135
rolagem.pace(quando)                    -> Series por indexador, em R$ milhões/leilão
rolagem.leiloes_que_faltam(dias, indexador) -> int
rolagem.estoque_em(quando, de=None)     -> Series por indexador, em R$ milhões
rolagem.projecao(ate, de_snapshot=None, registros=None, hoje=None) -> dict
    chaves: estoque, percentual, selic, inflacao, data_da_curva,
            dias_de_leilao, fronteira_do_calendario, de, ate
fluxos.pagos(de, ate)      -> frame com indexador, principal_milhoes, cupom_milhoes
curva.selic_implicita(ate, data_base=None)     -> decimal ao ano
curva.inflacao_implicita(ate, data_base=None)  -> decimal ao ano
calendario_leiloes.dias_ate(ate, registros=None, hoje=None) -> (lista, fronteira)
calendario.padrao().du(de_date, ate_date)      -> int
graficos.paf.bandas(indicador)  -> frame indexado por ano; colunas minimo, maximo,
                                   minimo_original, maximo_original
graficos.banda.INDICADORES      -> tuplas (chave, rotulo, unidade)
graficos.banda._numero(valor, casas=2)  -> texto em pt-BR
graficos.banda._ultima_liquidacao()     -> Timestamp
painel_paf.SECOES, painel_paf._recolhe(conteudo, chave, rotulo, aberta)
painel_paf.grava(caminho=None, hoje=None, registros=None)
```

**As chaves de `banda.INDICADORES` que interessam:** `prefixado_pct`, `indice_precos_pct`, `taxa_flutuante_pct`. O mapa chave→indexador NÃO existe ainda e é criado na Task 1.

---

## Task 1: `rolagem.emissao_necessaria` — a conta

**Arquivos:**
- Modificar: `src/tesouro/rolagem.py`
- Teste: `tests/test_rolagem.py`

**Interfaces:**
- Consome: `estoque_em`, `leiloes_que_faltam`, `fluxos.pagos`, `curva.selic_implicita`, `curva.inflacao_implicita`, `calendario.padrao`, `calendario_leiloes.dias_ate`
- Produz:
  ```
  INDEXADOR_DA_CHAVE = {"prefixado_pct": "Prefixado",
                        "indice_precos_pct": "Índice Preços",
                        "taxa_flutuante_pct": "Taxa Flutuante"}
  emissao_necessaria(indexador, alvo_pct, alvo_total, hoje=None, ate=None,
                     registros=None) -> float
      devolve R$ MILHÕES por leilão (mesma unidade de pace()), podendo ser negativo
  ```

- [ ] **Passo 1: escrever o teste que falha**

```python
def test_emissao_necessaria_e_a_projecao_ao_contrario():
    """A IDENTIDADE QUE SUSTENTA A ENTREGA 5 INTEIRA.

    A projecao responde "neste ritmo, chego onde?". Esta funcao responde "para
    chegar ali, que ritmo preciso?". Sao a mesma conta lida ao contrario, entao
    pedir a emissao necessaria para o resultado da PROPRIA projecao tem de
    devolver o pace atual -- para os tres indexadores.

    Se as duas discordarem, uma esta errada, e este teste nao diz qual. Mas
    impede que a pagina publique as duas lado a lado dizendo coisas diferentes.
    """
    ate = pd.Timestamp("2026-12-31")
    p = rolagem.projecao(ate, registros=[])
    total = float(p["estoque"].sum()) / 1000
    ritmo = rolagem.pace(p["de"])

    for ind in rolagem.INDEXADORES:
        pct = float(p["percentual"][ind])
        obtido = rolagem.emissao_necessaria(ind, pct, total, hoje=p["de"],
                                            ate=ate, registros=[])
        assert obtido == pytest.approx(float(ritmo[ind]), rel=1e-6), (
            f"{ind}: a emissao necessaria para o proprio resultado da projecao "
            f"tem de ser o pace atual")


def test_emissao_necessaria_cresce_com_o_alvo():
    """Monotonicidade nos dois eixos.

    Uma troca de sinal na formula -- alvo menos estoque virando estoque menos
    alvo -- daria numeros plausiveis e inverteria a leitura inteira. Nenhum
    teste de valor isolado pega isso; a ordem pega.
    """
    ate = pd.Timestamp("2026-12-31")
    hoje = banda_ultima_liquidacao()

    def pede(pct, total):
        return rolagem.emissao_necessaria("Prefixado", pct, total, hoje=hoje,
                                          ate=ate, registros=[])

    # Mesmo total, percentual maior -> emitir mais.
    assert pede(22, 9900) > pede(21, 9900)
    # Mesmo percentual, total maior -> emitir mais.
    assert pede(21, 10100) > pede(21, 9900)


def test_emissao_necessaria_fica_NEGATIVA_quando_o_alvo_esta_abaixo():
    """Negativo e resposta, e nao erro.

    O estoque cresce sozinho pelos juros. Quando o alvo esta abaixo de onde ele
    vai parar, nem parando de emitir se chega la -- e o numero diz o tamanho do
    resgate que faltaria.

    Medido em 26/08/2026: a taxa flutuante esta em 53,00% com banda de 46 a 50,
    e 20 das 30 celulas da banda dela sao negativas.
    """
    ate = pd.Timestamp("2026-12-31")
    hoje = banda_ultima_liquidacao()
    assert rolagem.emissao_necessaria("Taxa Flutuante", 46, 9700, hoje=hoje,
                                      ate=ate, registros=[]) < 0
```

Acrescente no topo do arquivo de teste, se ainda não houver:

```python
def banda_ultima_liquidacao():
    from tesouro.graficos import banda
    return banda._ultima_liquidacao()
```

- [ ] **Passo 2: rodar e ver falhar**

```bash
PYTHONPATH=src python -m pytest tests/test_rolagem.py -q -k "emissao_necessaria"
```

Esperado: `AttributeError: module 'tesouro.rolagem' has no attribute 'emissao_necessaria'`.

- [ ] **Passo 3: implementar**

Em `src/tesouro/rolagem.py`, depois de `projecao`:

```python
# A chave do indicador (como banda.INDICADORES a escreve) para o nome do
# indexador (como INDEXADORES o escreve). Os dois vocabularios ja existiam
# separados; este mapa e o unico lugar que os liga.
#
# OS VALORES FICAM ACENTUADOS. Eles sao DADO -- casam com a coluna do
# composicao_dpf.csv. Desacentuar aqui faria o filtro nao casar e o termo ir a
# zero em silencio (ruling 4 da entrega 4).
INDEXADOR_DA_CHAVE = {
    "prefixado_pct": "Prefixado",
    "indice_precos_pct": "Índice Preços",
    "taxa_flutuante_pct": "Taxa Flutuante",
}


def _taxa_do_indexador(indexador, ate, data_base=None):
    """A premissa de juros de cada indexador, a MESMA que projecao usa.

    Nao ha premissa nova nesta entrega: se a projecao estiver certa, esta conta
    esta; se estiver errada, as duas erram juntas. E isso que o teste de
    identidade trava.
    """
    if indexador == "Taxa Flutuante":
        return curva.selic_implicita(ate, data_base=data_base)
    if indexador == "Índice Preços":
        return (1 + curva.inflacao_implicita(ate, data_base=data_base)) * 1.06 - 1
    return _CARGA_DO_PREFIXADO


def emissao_necessaria(indexador, alvo_pct, alvo_total, hoje=None, ate=None,
                       registros=None):
    """Quanto emitir POR LEILAO daquele papel para o alvo sair em 'ate'.

    'alvo_pct' em pontos percentuais (22 e 22%), 'alvo_total' em R$ BILHOES, e o
    retorno em R$ MILHOES por leilao -- a mesma unidade de pace(), para os dois
    poderem ser comparados sem conversao no meio do caminho.

    A conta:

        alvo       = alvo_total x alvo_pct
        emissao    = alvo - estoque_hoje - juros + vencimentos_e_cupons
        por_leilao = emissao / leiloes_que_faltam

    PODE SER NEGATIVA, e negativa e resposta: o estoque cresce sozinho pelos
    juros, e quando o alvo esta abaixo de onde ele vai parar, nem parando de
    emitir se chega la. O numero diz o tamanho do resgate que faltaria.
    """
    from . import fluxos

    hoje = pd.Timestamp(hoje) if hoje is not None \
        else leiloes()["data_liquidacao"].max()
    ate = pd.Timestamp(ate) if ate is not None \
        else pd.Timestamp(f"{hoje.year}-12-31")

    partida = float(estoque_em(hoje)[indexador])
    dias, _ = calendario_leiloes.dias_ate(ate, registros=registros, hoje=hoje)
    quantos = leiloes_que_faltam(dias, indexador)
    if quantos <= 0:
        raise LookupError(
            f"nao ha leilao de {indexador!r} entre {hoje:%d/%m/%Y} e "
            f"{ate:%d/%m/%Y}; nao ha como dividir a emissao por leilao.")

    pagou = fluxos.pagos(hoje, ate)
    do_ind = pagou[pagou["indexador"] == indexador]
    vence = float(do_ind["principal_milhoes"].sum()
                  + do_ind["cupom_milhoes"].sum())

    cal = calendario.padrao()
    du = cal.du(hoje.date(), ate.date())
    taxa = _taxa_do_indexador(indexador, ate, data_base=hoje)
    juros = partida * ((1 + taxa) ** (du / 252) - 1)

    alvo = alvo_total * alvo_pct / 100 * 1000
    return (alvo - partida - juros + vence) / quantos
```

- [ ] **Passo 4: rodar e ver passar**

```bash
PYTHONPATH=src python -m pytest tests/test_rolagem.py -q -k "emissao_necessaria"
```

Esperado: 3 passed.

**Se o teste de identidade falhar**, o erro provável está na premissa de juros: `projecao` usa `curva.selic_implicita(ate, data_base=partida)` e a fórmula do índice de preços é `(1 + inflacao) * 1.06 - 1`. Compare linha a linha com o corpo de `projecao` antes de mexer na fórmula nova.

- [ ] **Passo 5: conferir os dentes**

Quebre cada linha de propósito e confirme o vermelho:

| mutação | teste que deve pegar |
|---|---|
| `alvo - partida` vira `partida - alvo` | monotonicidade |
| `+ vence` vira `- vence` | identidade |
| `_taxa_do_indexador` devolve sempre `_CARGA_DO_PREFIXADO` | identidade |
| `/ quantos` vira `/ len(dias)` | identidade |

- [ ] **Passo 6: commitar**

```bash
git add src/tesouro/rolagem.py tests/test_rolagem.py
git commit -m "A conta da simulacao: a projecao lida ao contrario"
```

---

## Task 2: os eixos que contêm sempre a banda e o projetado

**Arquivos:**
- Criar: `src/tesouro/graficos/simulacao.py`
- Teste: `tests/test_simulacao.py`

**Interfaces:**
- Consome: `rolagem.projecao`, `rolagem.INDEXADOR_DA_CHAVE`, `paf.bandas`
- Produz:
  ```
  PASSO_TOTAL = 200
  MARGEM_PCT = 1
  eixos(chave, projetado_pct, projetado_total, ano) -> (linhas, colunas)
      linhas: lista de int, pontos percentuais
      colunas: lista de int, R$ bilhoes
  ```

- [ ] **Passo 1: escrever o teste que falha**

```python
"""A simulacao: quanto emitir por leilao para chegar a cada alvo."""
import pandas as pd
import pytest

from tesouro import rolagem
from tesouro.graficos import simulacao


def test_os_eixos_contem_a_BANDA_inteira():
    # Decisao dela: "garante sempre que o projetado com o pace de hj esta dentro
    # da banda apresentada, e o intervalo da paf tbm".
    linhas, colunas = simulacao.eixos("prefixado_pct", 21.10, 9947, 2026)
    assert min(linhas) <= 21 and max(linhas) >= 25, "a banda 21-25 tem de caber"
    assert min(colunas) <= 9700 and max(colunas) >= 10300, (
        "a banda de estoque 9.700-10.300 tem de caber")


def test_os_eixos_contem_o_PROJETADO_mesmo_longe_da_banda():
    """O caso da taxa flutuante: banda 46-50, projetado 53,24%.

    A versao anterior da spec fixava a grade e nao marcava nada quando o
    projetado caia fora -- deixando justamente a tabela do indicador FORA da
    banda, que e a mais interessante, sem a marca do ritmo atual.
    """
    linhas, _ = simulacao.eixos("taxa_flutuante_pct", 53.24, 9947, 2026)
    assert max(linhas) >= 54, f"53,24% tem de caber; linhas foram {linhas}"
    assert min(linhas) <= 45, "a banda 46-50 continua tendo de caber"


def test_os_eixos_tem_passo_regular():
    linhas, colunas = simulacao.eixos("prefixado_pct", 21.10, 9947, 2026)
    assert all(b - a == 1 for a, b in zip(linhas, linhas[1:]))
    assert all(b - a == simulacao.PASSO_TOTAL
               for a, b in zip(colunas, colunas[1:]))
```

- [ ] **Passo 2: rodar e ver falhar**

```bash
PYTHONPATH=src python -m pytest tests/test_simulacao.py -q
```

Esperado: `ModuleNotFoundError: No module named 'tesouro.graficos.simulacao'`.

- [ ] **Passo 3: implementar**

```python
"""A simulacao: quanto emitir por leilao para chegar a cada alvo.

E o terceiro bloco da paf.html, e o par da projecao: aquela responde "neste
ritmo, chego onde?", esta responde "para chegar ali, que ritmo preciso?".

TRES TABELAS INDEPENDENTES, uma por indexador -- decisao dela. Cada celula
precisa so do estoque-alvo DAQUELE papel, que e total x pct, entao nenhuma
tabela depende do que os outros dois fazem. O preco disso, que o rodape diz: as
tres nao sao necessariamente compativeis entre si.

MODULO PROPRIO, e nao mais uma funcao em banda.py: aquele arquivo ja tem duas
tabelas e passou de 400 linhas, e tres matrizes o empurrariam para alem do que
se le de uma vez.
"""
import math

import pandas as pd

from .. import rolagem
from . import paf

# Passo das colunas, em R$ bilhoes, e margem das linhas, em pontos percentuais.
PASSO_TOTAL = 200
MARGEM_PCT = 1


def eixos(chave, projetado_pct, projetado_total, ano):
    """As linhas (%) e colunas (R$ bi) da tabela daquele indicador.

    OS EIXOS NAO SAO FIXOS. Cada um e calculado para conter DUAS coisas: a banda
    do PAF daquele indicador e o ponto para onde o ritmo de hoje leva. Decisao
    dela, e ela existe por um caso concreto -- a taxa flutuante esta em 53,24%
    projetado contra uma banda de 46 a 50: com grade fixa, a tabela do unico
    indicador FORA da banda ficaria sem a marca do ritmo atual, que e o que se
    quer comparar.
    """
    b = paf.bandas(chave).loc[ano]
    lo, hi = float(b["minimo"]), float(b["maximo"])
    linhas = list(range(
        int(min(lo - MARGEM_PCT, math.floor(projetado_pct))),
        int(max(hi + MARGEM_PCT, math.ceil(projetado_pct))) + 1))

    e = paf.bandas("estoque_bilhoes").loc[ano]
    est_lo, est_hi = float(e["minimo"]), float(e["maximo"])
    colunas = list(range(
        int(min(est_lo - PASSO_TOTAL,
                math.floor(projetado_total / PASSO_TOTAL) * PASSO_TOTAL)),
        int(max(est_hi + PASSO_TOTAL,
                math.ceil(projetado_total / PASSO_TOTAL) * PASSO_TOTAL)) + 1,
        PASSO_TOTAL))
    return linhas, colunas
```

- [ ] **Passo 4: rodar e ver passar**

```bash
PYTHONPATH=src python -m pytest tests/test_simulacao.py -q
```

Esperado: 3 passed.

- [ ] **Passo 5: conferir os dentes**

| mutação | teste que deve pegar |
|---|---|
| `min(lo - MARGEM_PCT, floor(proj))` vira `lo - MARGEM_PCT` | contém o projetado |
| `max(hi + MARGEM_PCT, ceil(proj))` vira `hi + MARGEM_PCT` | contém o projetado |
| `PASSO_TOTAL` vira 100 no `range` | passo regular |

- [ ] **Passo 6: commitar**

```bash
git add src/tesouro/graficos/simulacao.py tests/test_simulacao.py
git commit -m "Os eixos da simulacao contem sempre a banda e o projetado"
```

---

## Task 3: `dados_simulacao` — a matriz de uma tabela

**Arquivos:**
- Modificar: `src/tesouro/graficos/simulacao.py`
- Teste: `tests/test_simulacao.py`

**Interfaces:**
- Consome: `eixos`, `rolagem.emissao_necessaria`, `rolagem.projecao`, `rolagem.pace`
- Produz:
  ```
  dados_simulacao(chave, hoje=None, ate=None, registros=None) -> DataFrame
      indice = linhas (%), colunas = totais (R$ bi), valores = R$ BILHOES/leilao
      .attrs: chave, indexador, rotulo, banda (min, max), marca (linha, coluna),
              ritmo_atual (R$ bi/leilao), projetado_pct, projetado_total,
              leiloes, hoje, ate
  ```

- [ ] **Passo 1: escrever o teste que falha**

```python
def test_dados_simulacao_tem_a_forma_dos_eixos():
    d = simulacao.dados_simulacao("prefixado_pct", registros=[])
    linhas, colunas = simulacao.eixos(
        "prefixado_pct", d.attrs["projetado_pct"],
        d.attrs["projetado_total"], d.attrs["ate"].year)
    assert list(d.index) == linhas
    assert list(d.columns) == colunas


def test_a_marca_cai_na_celula_do_projetado():
    """Arredondando CADA EIXO ao ponto mais proximo da sua grade,
    independentemente do outro -- e nao a menor distancia no plano, que
    exigiria comparar pontos percentuais com bilhoes de reais.
    """
    d = simulacao.dados_simulacao("prefixado_pct", registros=[])
    linha, coluna = d.attrs["marca"]
    assert abs(linha - d.attrs["projetado_pct"]) <= 0.5
    assert abs(coluna - d.attrs["projetado_total"]) <= simulacao.PASSO_TOTAL / 2
    assert linha in d.index and coluna in d.columns


def test_a_celula_marcada_NAO_e_o_ritmo_atual():
    """A armadilha desta pagina, medida em 26/08/2026.

    A celula marcada mostra quanto emitir para cair no ponto ARREDONDADO da
    grade -- nao o que se emite hoje. No indice de precos a celula marcada da
    0,3 contra um ritmo de 2,04: SETE VEZES. Quem ler a marca como "o que
    emitimos hoje" sai com um numero muito errado, sem que nenhuma conta esteja
    errada.

    Este teste nao exige que os dois sejam diferentes -- eles podem coincidir
    por sorte. Exige que os dois ESTEJAM DISPONIVEIS separadamente, para a
    tabela poder mostrar cada um no seu lugar.
    """
    d = simulacao.dados_simulacao("indice_precos_pct", registros=[])
    linha, coluna = d.attrs["marca"]
    assert "ritmo_atual" in d.attrs
    assert d.attrs["ritmo_atual"] > 0
    # A celula existe e e um numero -- nao um NaN nem o proprio ritmo copiado.
    assert pd.notna(d.at[linha, coluna])


def test_a_matriz_cresce_nos_dois_eixos():
    d = simulacao.dados_simulacao("prefixado_pct", registros=[])
    for coluna in d.columns:
        serie = d[coluna]
        assert serie.is_monotonic_increasing, f"coluna {coluna}"
    for linha in d.index:
        assert d.loc[linha].is_monotonic_increasing, f"linha {linha}"
```

- [ ] **Passo 2: rodar e ver falhar**

```bash
PYTHONPATH=src python -m pytest tests/test_simulacao.py -q -k "dados_simulacao or marca or matriz"
```

Esperado: `AttributeError: module ... has no attribute 'dados_simulacao'`.

- [ ] **Passo 3: implementar**

```python
def dados_simulacao(chave, hoje=None, ate=None, registros=None):
    """A matriz de uma tabela: linhas em %, colunas em R$ bi, celulas em R$ bi.

    A CELULA SAI EM BILHOES, e nao nos milhoes que rolagem devolve: a tabela
    inteira e lida em bilhoes -- os eixos, o rodape e a pagina toda -- e deixar
    uma unidade diferente no miolo e o tipo de detalhe que produz erro de mil
    vezes numa leitura rapida.
    """
    indexador = rolagem.INDEXADOR_DA_CHAVE[chave]
    hoje = pd.Timestamp(hoje) if hoje is not None \
        else rolagem.leiloes()["data_liquidacao"].max()
    ate = pd.Timestamp(ate) if ate is not None \
        else pd.Timestamp(f"{hoje.year}-12-31")

    p = rolagem.projecao(ate, registros=registros, hoje=hoje)
    projetado_pct = float(p["percentual"][indexador])
    projetado_total = float(p["estoque"].sum()) / 1000

    linhas, colunas = eixos(chave, projetado_pct, projetado_total, ate.year)
    matriz = pd.DataFrame(
        [[rolagem.emissao_necessaria(indexador, pct, total, hoje=hoje,
                                     ate=ate, registros=registros) / 1000
          for total in colunas]
         for pct in linhas],
        index=linhas, columns=colunas)

    b = paf.bandas(chave).loc[ate.year]
    matriz.attrs["chave"] = chave
    matriz.attrs["indexador"] = indexador
    matriz.attrs["rotulo"] = _ROTULO[chave]
    matriz.attrs["banda"] = (float(b["minimo"]), float(b["maximo"]))
    # CADA EIXO ARREDONDA SOZINHO, ao ponto mais proximo da sua propria grade.
    # A menor distancia no plano exigiria comparar pontos percentuais com
    # bilhoes de reais, e portanto uma escala inventada.
    matriz.attrs["marca"] = (
        min(linhas, key=lambda x: abs(x - projetado_pct)),
        min(colunas, key=lambda x: abs(x - projetado_total)))
    matriz.attrs["ritmo_atual"] = float(rolagem.pace(hoje)[indexador]) / 1000
    matriz.attrs["projetado_pct"] = projetado_pct
    matriz.attrs["projetado_total"] = projetado_total
    dias, _ = calendario_leiloes.dias_ate(ate, registros=registros, hoje=hoje)
    matriz.attrs["leiloes"] = rolagem.leiloes_que_faltam(dias, indexador)
    matriz.attrs["hoje"] = hoje
    matriz.attrs["ate"] = ate
    return matriz
```

Acrescente no topo do módulo, junto das outras constantes:

```python
from .. import calendario_leiloes

# O rotulo de cada tabela na tela. Sai do vocabulario dela: e "indice de
# precos", e nao "IPCA" -- o indexador do PAF inclui a NTN-C, que e IGP-M.
_ROTULO = {
    "prefixado_pct": "Prefixado",
    "indice_precos_pct": "Índice de preços",
    "taxa_flutuante_pct": "Taxa flutuante",
}
```

- [ ] **Passo 4: rodar e ver passar**

```bash
PYTHONPATH=src python -m pytest tests/test_simulacao.py -q
```

Esperado: 7 passed. (Leva ~1 min: a matriz chama `emissao_necessaria` uma vez por célula.)

- [ ] **Passo 5: conferir os dentes**

| mutação | teste que deve pegar |
|---|---|
| `/ 1000` sai da célula | monotonicidade continua passando — **este é o furo**; ver abaixo |
| `min(linhas, key=...)` vira `linhas[0]` | a marca cai na célula do projetado |
| `matriz.attrs["ritmo_atual"]` recebe o valor da célula marcada | a célula marcada não é o ritmo |

**O furo da unidade é real e precisa de um teste próprio.** Acrescente:

```python
def test_a_celula_sai_em_BILHOES_como_o_resto_da_tabela():
    """rolagem.emissao_necessaria devolve MILHOES; a tabela le bilhoes.

    Sem esta conferencia, esquecer a divisao daria numeros mil vezes maiores --
    e a monotonicidade, que e o outro teste da matriz, continuaria passando,
    porque escalar tudo por mil nao muda a ordem.
    """
    d = simulacao.dados_simulacao("prefixado_pct", registros=[])
    linha, coluna = d.attrs["marca"]
    em_milhoes = rolagem.emissao_necessaria(
        d.attrs["indexador"], linha, coluna,
        hoje=d.attrs["hoje"], ate=d.attrs["ate"], registros=[])
    assert d.at[linha, coluna] == pytest.approx(em_milhoes / 1000, rel=1e-9)
    # E a ordem de grandeza bate com o ritmo, que tambem esta em bilhoes.
    assert abs(d.at[linha, coluna]) < 100, (
        "celula em bilhoes nao passa de dois digitos com o dado de hoje")
```

- [ ] **Passo 6: commitar**

```bash
git add src/tesouro/graficos/simulacao.py tests/test_simulacao.py
git commit -m "A matriz de cada tabela da simulacao"
```

---

## Task 4: a tabela em HTML

**Arquivos:**
- Modificar: `src/tesouro/graficos/simulacao.py`
- Teste: `tests/test_simulacao.py`

**Interfaces:**
- Consome: `dados_simulacao`, `banda._numero`
- Produz: `tabela(dados) -> str` (HTML), `_CSS` (str)

- [ ] **Passo 1: escrever o teste que falha**

```python
def test_a_tabela_marca_a_celula_do_projetado():
    d = simulacao.dados_simulacao("prefixado_pct", registros=[])
    html = simulacao.tabela(d)
    assert html.count('class="marca"') == 1, (
        "exatamente uma celula e a do projetado")


def test_a_tabela_pinta_o_negativo_de_vermelho_com_o_sinal():
    """Decisao dela: so o numero em vermelho, com o menos na frente.

    Sem icone, sem hachura, sem palavra. A magnitude e a informacao.
    """
    d = simulacao.dados_simulacao("taxa_flutuante_pct", registros=[])
    html = simulacao.tabela(d)
    negativas = (d < 0).sum().sum()
    assert negativas > 0, "a taxa flutuante tem de ter celula negativa hoje"
    assert html.count('class="negativo"') == negativas
    assert "-" in html
    # E nada de palavra no lugar do numero.
    assert "impossivel" not in html.lower()


def test_o_rodape_avisa_que_as_TRES_TABELAS_sao_independentes():
    """Spec 2: o custo da escolha dela precisa estar escrito.

    Tres tabelas independentes e a forma mais legivel, e ela escolheu sabendo
    do preco: elas nao sao necessariamente compativeis entre si. Ler "prefixado
    22% pede X" e "indice de precos 25% pede Y" e fazer as duas coisas pode nao
    dar o total escolhido.

    Isso nao aparece em nenhum numero da tela -- so no texto. Se sair do texto,
    some.
    """
    d = simulacao.dados_simulacao("prefixado_pct", registros=[])
    html = simulacao.tabela(d)
    assert "independentes" in html
    assert "total escolhido" in html


def test_a_tabela_marca_as_linhas_da_BANDA():
    d = simulacao.dados_simulacao("prefixado_pct", registros=[])
    html = simulacao.tabela(d)
    lo, hi = d.attrs["banda"]
    dentro = [x for x in d.index if lo <= x <= hi]
    assert html.count('class="na-banda"') == len(dentro)


def test_o_rodape_separa_o_RITMO_ATUAL_da_celula_marcada():
    """A armadilha de §6.1 da spec, travada no texto.

    A celula marcada nao e o ritmo atual, e no indice de precos a diferenca e de
    sete vezes. O rodape tem de trazer o ritmo em numero, separado, com essas
    palavras -- senao a pagina mente sem errar uma conta.
    """
    d = simulacao.dados_simulacao("indice_precos_pct", registros=[])
    html = simulacao.tabela(d)
    assert "ritmo de hoje" in html
    assert simulacao._numero_br(d.attrs["ritmo_atual"]) in html
    assert "para cá leva" in html or "leva o ritmo" in html
```

- [ ] **Passo 2: rodar e ver falhar**

```bash
PYTHONPATH=src python -m pytest tests/test_simulacao.py -q -k "tabela or rodape"
```

Esperado: `AttributeError: ... has no attribute 'tabela'`.

- [ ] **Passo 3: implementar**

```python
def _numero_br(valor, casas=2):
    """O numero em pt-BR. Delegado a banda._numero, para as duas tabelas da
    pagina escreverem numero do mesmo jeito."""
    from . import banda
    return banda._numero(valor, casas)


def tabela(dados):
    """Uma tabela da simulacao, em HTML."""
    lo, hi = dados.attrs["banda"]
    marca_linha, marca_coluna = dados.attrs["marca"]

    cabecalho = ("<tr><th>% do papel</th>"
                 + "".join(f"<th class='n'>{_numero_br(c, 0)}</th>"
                           for c in dados.columns)
                 + "</tr>")

    linhas = []
    for pct in dados.index:
        classe = " class='na-banda'" if lo <= pct <= hi else ""
        celulas = []
        for total in dados.columns:
            v = dados.at[pct, total]
            classes = []
            if v < 0:
                classes.append("negativo")
            if pct == marca_linha and total == marca_coluna:
                classes.append("marca")
            atributo = f" class='n {' '.join(classes)}'" if classes \
                else " class='n'"
            celulas.append(f"<td{atributo}>{_numero_br(v)}</td>")
        linhas.append(f"<tr{classe}><th class='pct'>{_numero_br(pct, 0)}%</th>"
                      + "".join(celulas) + "</tr>")

    rodape = (
        f"{dados.attrs['rotulo']}: banda de {_numero_br(lo, 0)} a "
        f"{_numero_br(hi, 0)}%, {dados.attrs['leiloes']} leilão(oes) até "
        f"{dados.attrs['ate']:%d/%m/%Y}. "
        f"A célula destacada é <b>para cá leva o ritmo de hoje</b> "
        f"({_numero_br(dados.attrs['projetado_pct'])}% de R$ "
        f"{_numero_br(dados.attrs['projetado_total'], 0)} bi) — e "
        f"<b>não</b> o que se emite hoje, que é de R$ "
        f"{_numero_br(dados.attrs['ritmo_atual'])} bi por leilão. Os dois "
        f"diferem porque a grade arredonda os dois eixos. "
        f"Número <span class='negativo'>negativo</span> quer dizer que nem "
        f"parando de emitir se chega ao alvo: faltaria resgatar. "
        f"<b>As três tabelas são independentes:</b> cada uma responde à sua "
        f"pergunta sozinha, e fazer o que duas delas pedem ao mesmo tempo pode "
        f"não produzir o total escolhido.")

    ident = "simulacao-" + dados.attrs["chave"].replace("_", "-")
    return (f"<div class='simulacao' id='{ident}'>"
            f"<h3>{dados.attrs['rotulo']}</h3>"
            f"<table>{cabecalho}{''.join(linhas)}</table>"
            f"<p class='rodape'>{rodape}</p></div>")


_CSS = """
.simulacao { margin: 22px auto 34px; max-width: 1180px; }
.simulacao h3 { font-size: 15px; margin: 0 0 8px; }
.simulacao table { border-collapse: collapse; width: 100%; font-size: 13px; }
.simulacao th, .simulacao td { padding: 5px 9px; text-align: left;
  border-bottom: 1px solid #eee; }
.simulacao th.pct { font-weight: 600; }
.simulacao td.n, .simulacao th.n { text-align: right;
  font-variant-numeric: tabular-nums; }
.simulacao tr.na-banda { background: #f6f8fb; }
.simulacao td.negativo, .simulacao span.negativo { color: #b03030; }
.simulacao td.marca { outline: 2px solid #2b6cb0; font-weight: 600; }
"""
```

**Nenhuma tag literal dentro de comentário de CSS** — `_CSS` acima não tem comentários por isso. Um `<main>` dentro de comentário quebrou o recorte da página em 20/08/2026.

- [ ] **Passo 4: rodar e ver passar**

```bash
PYTHONPATH=src python -m pytest tests/test_simulacao.py -q
```

Esperado: 13 passed.

- [ ] **Passo 5: conferir os dentes**

| mutação | teste que deve pegar |
|---|---|
| a classe `marca` nunca é aplicada | marca a célula do projetado |
| `if v < 0` vira `if False` | pinta o negativo |
| o rodapé perde o `ritmo_atual` | rodapé separa o ritmo |
| `lo <= pct <= hi` vira `True` | marca as linhas da banda |

- [ ] **Passo 6: commitar**

```bash
git add src/tesouro/graficos/simulacao.py tests/test_simulacao.py
git commit -m "A tabela da simulacao em HTML"
```

---

## Task 5: a terceira seção da página

**Arquivos:**
- Modificar: `src/tesouro/graficos/painel_paf.py`
- Teste: `tests/test_painel_paf.py`

**Interfaces:**
- Consome: `simulacao.dados_simulacao`, `simulacao.tabela`, `simulacao._CSS`
- Produz: a página com três blocos

- [ ] **Passo 1: escrever o teste que falha**

```python
def test_a_pagina_tem_TRES_blocos_recolhiveis(pagina):
    corpo = pagina[pagina.index("</header>"):pagina.rindex("</main>")]
    assert corpo.count('<details class="secao') == 3


def test_o_bloco_da_simulacao_tem_as_TRES_tabelas(pagina):
    for chave in ("prefixado-pct", "indice-precos-pct", "taxa-flutuante-pct"):
        assert f'id="simulacao-{chave}"' in pagina, chave


def test_a_pagina_e_reprodutivel_entre_processos(tmp_path):
    """Spec 8, teste 6. Duas geracoes, o mesmo HTML.

    Ja quebrou neste projeto: iterar um `set` de ISINs produzia ordem diferente
    a cada processo (PYTHONHASHSEED), e os SVGs saiam diferentes sem nada ter
    mudado no dado. A simulacao itera INDEXADOR_DA_CHAVE, que e dict -- ordem de
    insercao, estavel -- mas isso e propriedade que se perde sem aviso.

    EM DOIS PROCESSOS, e nao duas chamadas no mesmo: o embaralhamento por
    hash so muda entre processos.
    """
    import subprocess
    import sys

    codigo = (
        "from tesouro.graficos import painel_paf;"
        "import hashlib, pathlib;"
        "c = painel_paf.grava(pathlib.Path(r'%s') / 'p.html', registros=[]);"
        "print(hashlib.sha256(c.read_bytes()).hexdigest())")

    saidas = []
    for k in range(2):
        destino = tmp_path / str(k)
        destino.mkdir()
        r = subprocess.run([sys.executable, "-c", codigo % destino],
                           capture_output=True, text=True,
                           env={**os.environ, "PYTHONPATH": "src"})
        assert r.returncode == 0, r.stderr[-600:]
        saidas.append(r.stdout.strip())

    assert saidas[0] == saidas[1], "a pagina saiu diferente em dois processos"


def test_a_pagina_continua_cabendo_no_limiar(tmp_path):
    from tesouro.graficos import painel_paf

    caminho = painel_paf.grava(tmp_path / painel_paf.ARQUIVO, registros=[])
    tamanho = caminho.stat().st_size
    assert tamanho > 20_000, "a pagina com tres blocos nao pode encolher"
    assert tamanho < 10 * 1024 * 1024
```

Se `os` ainda nao estiver importado no topo de `tests/test_painel_paf.py`,
acrescente `import os`.

- [ ] **Passo 2: rodar e ver falhar**

```bash
PYTHONPATH=src python -m pytest tests/test_painel_paf.py -q -k "TRES_blocos or TRES_tabelas"
```

Esperado: `assert 2 == 3`.

- [ ] **Passo 3: implementar**

Em `painel_paf.py`, acrescente à lista `SECOES`:

```python
SECOES = [
    ("hoje", "Onde estamos hoje", True),
    ("projecao", "Onde fechamos o ano", False),
    ("simulacao", "O que fazer para chegar lá", False),
]
```

No corpo de `grava`, depois do bloco da projeção:

```python
        _recolhe(_as_tres_tabelas(hoje, registros), *SECOES[2]),
```

E a função, antes de `grava`:

```python
def _as_tres_tabelas(hoje, registros):
    """As tres tabelas da simulacao, uma por indexador, em ordem.

    A ORDEM E A DE rolagem.INDEXADOR_DA_CHAVE, que e a mesma de
    banda.INDICADORES -- a pagina inteira le prefixado, indice de precos e taxa
    flutuante nessa ordem, e trocar aqui faria o leitor procurar.
    """
    from . import simulacao

    return "\n".join(
        simulacao.tabela(simulacao.dados_simulacao(chave, hoje=hoje,
                                                   registros=registros))
        for chave in rolagem.INDEXADOR_DA_CHAVE)
```

Acrescente o import de `rolagem` no topo, se não houver, e o CSS:

```python
    html = html.replace("</style>", _CSS + simulacao._CSS + "</style>", 1)
```

- [ ] **Passo 4: rodar e ver passar**

```bash
PYTHONPATH=src python -m pytest tests/test_painel_paf.py -q
```

Esperado: tudo passando. **O teste `test_a_pagina_tem_os_DOIS_blocos_recolhiveis` vai falhar** — ele afirma dois blocos e agora são três. Atualize a contagem e o nome dele; é ajuste de contagem, não de comportamento.

- [ ] **Passo 5: rodar a suíte inteira e regravar**

```bash
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -c "from tesouro.graficos import painel_paf; print(painel_paf.grava())"
```

**Abra a página no navegador antes de dar por pronta.** Foi assim que apareceram a frase emendada e a frase colada — nenhum teste as pegou.

- [ ] **Passo 6: commitar**

```bash
git add src/tesouro/graficos/painel_paf.py tests/test_painel_paf.py
git commit -m "A simulacao entra como terceiro bloco da pagina do PAF"
```

---

## Depois de todas as tarefas

- [ ] Atualizar o `README.md`: a `paf.html` passa a ter três blocos, e o tamanho medido muda.
- [ ] Conferir no navegador: as três tabelas, a célula marcada visível, os negativos em vermelho, e sem rolagem horizontal.
- [ ] Rodar a suíte inteira uma última vez e commitar as páginas regravadas.
