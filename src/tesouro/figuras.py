"""Graficos do DV01: o primeiro output visual do projeto.

Backend Agg: nao abre janela e funciona em maquina sem interface grafica
(necessario no Windows da usuaria, e em qualquer execucao em servidor ou
sessao remota). O "matplotlib.use" tem que vir ANTES de "import
matplotlib.pyplot" -- depois disso o backend ja foi escolhido, e a
chamada nao tem efeito nenhum.

Convencao de sinal, mantida do resto do projeto (docs/convencoes-dv.md):
o DV de um titulo prefixado ou indexado e NEGATIVO -- o preco cai quando
a taxa sobe, entao "mais negativo" significa "mais risco" (maior perda
com uma alta de 1 bp). Os dois graficos aqui preservam esse sinal, em vez
de plotar o modulo, por duas razoes:

  (1) e o mesmo numero das tabelas e dos CSVs que a usuaria vai conferir
      ao lado do grafico -- inverter so no desenho criaria um grafico que
      nao bate com a planilha;
  (2) o grafico pontual e uma decomposicao ADITIVA (dv_base + dv_que_vence
      + decay_sobreviventes = dv_alvo), que so fecha com o sinal
      verdadeiro; usar modulo num grafico e sinal verdadeiro no outro
      seria pior do que a inconsistencia que se tenta evitar.

Como consequencia, uma linha ou barra que DESCE (fica mais negativa)
representa MAIS risco, nao menos -- o oposto da leitura intuitiva de "linha
subindo e o valor crescendo". Por isso os dois graficos trazem uma nota
explicita de rodape lembrando a convencao, em vez de confiar que quem olha
vai lembrar sozinho.

Cada figura tambem precisa dizer qual conta esta usando (ver docs/
convencoes-dv.md e a nota do modulo dv sobre pontual()):

  - grafico_dv_do_sistema: nao e nem a Conta A nem a Conta B. E o DV01
    OBSERVADO em cada fim de mes, calculado com a taxa e o VNA daquela
    data (o mesmo painel() que alimenta as duas contas) -- nao envolve
    dinheiro (nao e Conta A) e nao e uma projecao de decay a taxa parada
    (nao e Conta B). O rotulo do grafico deixa isso explicito para nao
    convidar a leitura errada.
  - grafico_pontual: Conta B, decay a taxa constante -- taxa e VNA
    congelados na data-base, sem dinheiro e sem VNA reprojetado (ver a
    docstring de dv.pontual()).
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402  (o backend precisa vir antes)

from . import calendario, config, dv  # noqa: E402

_CORES = {"LTN": "#1f4e79", "NTN-F": "#2e75b6", "NTN-B": "#c00000"}
_ORDEM_TITULOS = ("LTN", "NTN-F", "NTN-B")

_NOTA_SINAL = (
    "Negativo = mercado perde na alta de taxa (docs/convencoes-dv.md); "
    "quanto mais negativa a linha/barra, maior o risco -- nao inverta a "
    "leitura."
)


def _pasta():
    p = config.PROCESSED_DIR / "figuras"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _texto_cobertura(cobertura, data):
    """Formata a nota de cobertura a partir de um dict ja calculado (pelo
    formato de dv._cobertura). Separada de _nota_cobertura para quem ja
    tem o dict pronto -- como grafico_pontual, que reusa resumo['cobertura']
    de dv.pontual() em vez de recalcular a mesma coisa duas vezes."""
    if cobertura is None:
        return (
            f"cobertura do DV01 em {data:%d/%m/%Y}: nao foi possivel "
            f"calcular (sem estoque total medido nesta data)."
        )
    return (
        f"DV01 cobre {dv._num_br(cobertura['cobertos_pct'], 1)}% do "
        f"estoque em {data:%d/%m/%Y} (LTN, NTN-F, NTN-B); LFT "
        f"{dv._num_br(cobertura['lft_pct'], 1)}% nao tem duration de "
        f"juros por construcao, e {dv._num_br(cobertura['excluidos_pct'], 1)}% "
        f"fica fora por nao ter preco no secundario."
    )


def _nota_cobertura(cal, data):
    """Cobertura de verdade NA data pedida, via dv._cobertura -- nunca uma
    constante fixa (ver comentario acima de dv._cobertura: 46,6% e o
    numero de 30/06/2026, mas a cobertura muda mes a mes; em 2020-12-31
    ela chega a 60,4%, catorze pontos acima)."""
    return _texto_cobertura(dv._cobertura(cal, data), data)


def _serie_por_titulo(p=None):
    """DV01 do sistema por (data, titulo), a partir do painel.

    Extraida de grafico_dv_do_sistema para poder ser testada direto,
    contra os numeros de verdade, sem depender de reabrir o PNG
    rasterizado -- ver docs do modulo sobre nao afirmar so a existencia
    do arquivo.
    """
    p = dv.painel() if p is None else p
    p = p[p["dv_posicao_milhoes"].notna()]
    return (p.groupby(["data", "titulo"])["dv_posicao_milhoes"].sum()
              .unstack("titulo").sort_index())


def _figura_do_sistema():
    """Monta a figura do DV01 do sistema e devolve (fig, eixo, serie).

    Separada de grafico_dv_do_sistema para os testes poderem inspecionar
    os artistas do matplotlib (linhas, rotulos, valores) antes do
    fig.savefig/plt.close -- ler o PNG de volta nao verificaria os dados
    plotados, so a existencia do arquivo.
    """
    cal = calendario.padrao()
    serie = _serie_por_titulo()
    ultima_data = serie.index.max()

    fig, eixo = plt.subplots(figsize=(11, 5.5))
    for titulo in _ORDEM_TITULOS:
        if titulo in serie:
            eixo.plot(serie.index, serie[titulo], label=titulo,
                      color=_CORES[titulo], linewidth=1.6)
    eixo.plot(serie.index, serie.sum(axis=1, skipna=True), label="total",
              color="black", linewidth=1.0, linestyle="--")
    eixo.axhline(0, color="#999999", linewidth=0.8)
    eixo.set_title(
        "DV01 do sistema por tipo de papel -- serie observada mes a mes\n"
        "(taxa e VNA de cada data; nao e resultado em dinheiro nem "
        "projecao de decay)",
        fontsize=11,
    )
    eixo.set_ylabel("DV01 (R$ milhoes por bp)")
    eixo.legend(frameon=False, ncol=4)
    eixo.grid(alpha=0.25)
    fig.text(
        0.01, 0.01,
        f"{_nota_cobertura(cal, ultima_data)} {_NOTA_SINAL}",
        fontsize=7, color="#555555", wrap=True,
    )
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    return fig, eixo, serie


def grafico_dv_do_sistema(caminho=None):
    """DV01 do sistema por tipo de papel, ao longo do tempo.

    Nao e Conta A (nao envolve dinheiro) nem Conta B (nao e projecao de
    decay): e o DV01 tal como observado em cada fim de mes do painel, com
    a taxa e o VNA daquela data. Ver a nota do modulo.
    """
    caminho = Path(caminho) if caminho else _pasta() / "dv_do_sistema.png"
    fig, _eixo, _serie = _figura_do_sistema()
    fig.savefig(caminho, dpi=140)
    plt.close(fig)
    return caminho


def _figura_pontual(resumo):
    """Monta a figura da decomposicao pontual e devolve (fig, eixo,
    rotulos, valores) -- mesma razao de _figura_do_sistema: testar contra
    os artistas, nao contra o PNG."""
    rotulos = ["DV na base", "vence", "decay", "DV no alvo"]
    valores = [resumo["dv_base"], resumo["dv_que_vence"],
               resumo["decay_sobreviventes"], resumo["dv_alvo"]]
    cores = ["#1f4e79", "#c00000", "#ed7d31", "#2e75b6"]

    fig, eixo = plt.subplots(figsize=(8, 4.8))
    eixo.bar(rotulos, valores, color=cores)
    for i, v in enumerate(valores):
        eixo.text(i, v, dv._num_br(v, 1), ha="center",
                  va="bottom" if v >= 0 else "top", fontsize=9)
    eixo.axhline(0, color="#333333", linewidth=0.8)
    eixo.set_title(
        f"DV01: decay a taxa constante (Conta B), de "
        f"{resumo['data_base']:%d/%m/%Y} ate {resumo['data_alvo']:%d/%m/%Y}\n"
        f"taxa e VNA congelados na data-base -- sem dinheiro, sem VNA "
        f"reprojetado",
        fontsize=11,
    )
    eixo.set_ylabel("DV01 (R$ milhoes por bp)")
    eixo.grid(axis="y", alpha=0.25)
    texto_cobertura = _texto_cobertura(resumo["cobertura"], resumo["data_base"])
    fig.text(
        0.01, 0.01,
        f"{texto_cobertura} {_NOTA_SINAL}",
        fontsize=7, color="#555555", wrap=True,
    )
    fig.tight_layout(rect=(0, 0.14, 1, 1))
    return fig, eixo, rotulos, valores


def grafico_pontual(resumo, caminho):
    """Decomposicao da queda de DV entre a data-base e a data-alvo.

    Conta B da spec (ver dv.pontual()): decay a taxa constante, taxa e
    VNA congelados na data-base -- nao envolve dinheiro nem reprojecao de
    VNA. "resumo" e o dicionario devolvido por dv.pontual().
    """
    caminho = Path(caminho)
    fig, _eixo, _rotulos, _valores = _figura_pontual(resumo)
    fig.savefig(caminho, dpi=140)
    plt.close(fig)
    return caminho


def gravar_todas():
    """Grava as figuras padrao em data/processed/figuras/ (nao versionado,
    como o resto de data/processed/)."""
    caminho_sistema = grafico_dv_do_sistema()
    print(f"gravado: {caminho_sistema}")

    resumo = dv.pontual()
    caminho_pontual = grafico_pontual(resumo, _pasta() / "pontual.png")
    print(f"gravado: {caminho_pontual}")


if __name__ == "__main__":
    gravar_todas()
