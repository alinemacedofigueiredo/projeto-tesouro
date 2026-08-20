"""Gr\u00e1ficos do DV01: o primeiro output visual do projeto.

Backend Agg: n\u00e3o abre janela e funciona em m\u00e1quina sem interface
gr\u00e1fica (necess\u00e1rio no Windows da usu\u00e1ria, e em qualquer
execu\u00e7\u00e3o em servidor ou sess\u00e3o remota). O "matplotlib.use"
tem que vir ANTES de "import matplotlib.pyplot" -- depois disso o backend
j\u00e1 foi escolhido, e a chamada n\u00e3o tem efeito nenhum.

Conven\u00e7\u00e3o de sinal, mantida do resto do projeto
(docs/convencoes-dv.md): o DV de um t\u00edtulo prefixado ou indexado
\u00e9 NEGATIVO -- o pre\u00e7o cai quando a taxa sobe, ent\u00e3o "mais
negativo" significa "mais risco" (maior perda com uma alta de 1 bp). Os
dois gr\u00e1ficos aqui preservam esse sinal, em vez de plotar o
m\u00f3dulo, por duas raz\u00f5es:

  (1) \u00e9 o mesmo n\u00famero das tabelas e dos CSVs que a usu\u00e1ria
      vai conferir ao lado do gr\u00e1fico -- inverter s\u00f3 no desenho
      criaria um gr\u00e1fico que n\u00e3o bate com a planilha;
  (2) o gr\u00e1fico pontual \u00e9 uma decomposi\u00e7\u00e3o ADITIVA
      (dv_base + dv_que_vence + decay_sobreviventes = dv_alvo), que s\u00f3
      fecha com o sinal verdadeiro; usar m\u00f3dulo num gr\u00e1fico e
      sinal verdadeiro no outro seria pior do que a inconsist\u00eancia
      que se tenta evitar.

Como consequ\u00eancia, uma linha ou barra que DESCE (fica mais negativa)
representa MAIS risco, n\u00e3o menos -- o oposto da leitura intuitiva de
"linha subindo \u00e9 o valor crescendo". Por isso os dois gr\u00e1ficos
trazem uma nota expl\u00edcita de rodap\u00e9 lembrando a
conven\u00e7\u00e3o, em vez de confiar que quem olha vai lembrar sozinho.

Cada figura tamb\u00e9m precisa dizer qual conta est\u00e1 usando (ver
docs/convencoes-dv.md e a nota do m\u00f3dulo dv sobre pontual()):

  - grafico_dv_do_sistema: n\u00e3o \u00e9 nem a Conta A nem a Conta B.
    \u00c9 o DV01 OBSERVADO em cada fim de m\u00eas, calculado com a taxa
    e o VNA daquela data (o mesmo painel() que alimenta as duas contas)
    -- n\u00e3o envolve dinheiro (n\u00e3o \u00e9 Conta A) e n\u00e3o
    \u00e9 uma proje\u00e7\u00e3o de decay a taxa parada (n\u00e3o \u00e9
    Conta B). O r\u00f3tulo do gr\u00e1fico deixa isso expl\u00edcito
    para n\u00e3o convidar a leitura errada.
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
    "quanto mais negativa a linha/barra, maior o risco -- n\u00e3o "
    "inverta a leitura."
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
            f"cobertura do DV01 em {data:%d/%m/%Y}: n\u00e3o foi "
            f"poss\u00edvel calcular (sem estoque total medido nesta "
            f"data)."
        )
    return (
        f"DV01 cobre {dv._num_br(cobertura['cobertos_pct'], 1)}% do "
        f"estoque em {data:%d/%m/%Y} (LTN, NTN-F, NTN-B); LFT "
        f"{dv._num_br(cobertura['lft_pct'], 1)}% n\u00e3o tem duration "
        f"de juros por constru\u00e7\u00e3o, e "
        f"{dv._num_br(cobertura['excluidos_pct'], 1)}% fica fora por "
        f"n\u00e3o ter pre\u00e7o no secund\u00e1rio."
    )


def _nota_cobertura(cal, data):
    """Cobertura de verdade NA data pedida, via dv._cobertura -- nunca uma
    constante fixa (ver comentario acima de dv._cobertura: 46,5% e o
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
        "DV01 do sistema por tipo de papel -- s\u00e9rie observada "
        "m\u00eas a m\u00eas\n(taxa e VNA de cada data; n\u00e3o \u00e9 "
        "resultado em dinheiro nem proje\u00e7\u00e3o de decay)",
        fontsize=11,
    )
    eixo.set_ylabel("DV01 (R$ milh\u00f5es por bp)")
    eixo.legend(frameon=False, ncol=4)
    eixo.grid(alpha=0.25)
    texto_cobertura = _nota_cobertura(cal, ultima_data)
    fig.text(
        0.01, 0.01,
        f"{texto_cobertura} {_NOTA_SINAL}",
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
    os artistas, nao contra o PNG.

    Desenhada como cascata (bridge chart), nao como quatro barras soltas
    partindo do zero -- achado da revisao da Tarefa 9 (item 2): dv_base e
    dv_alvo sao ~50x maiores em modulo que dv_que_vence e
    decay_sobreviventes, e quatro barras do zero deixavam os dois termos
    do meio quase invisiveis, sem comunicar que
    dv_base + dv_que_vence + decay_sobreviventes = dv_alvo. Aqui "DV na
    base" e "DV no alvo" sao barras cheias (do zero, sao totais); "vence"
    e "decay" flutuam, cada uma comecando onde a anterior termina -- o
    padrao bridge para decomposicao aditiva. bar(height=...) continua
    recebendo o delta de cada termo (nao o topo acumulado), entao
    b.get_height() bate com valores igual antes -- so o "bottom" de cada
    barra mudou.
    """
    rotulos = ["DV na base", "vence", "decay", "DV no alvo"]
    valores = [resumo["dv_base"], resumo["dv_que_vence"],
               resumo["decay_sobreviventes"], resumo["dv_alvo"]]
    cores = ["#1f4e79", "#c00000", "#ed7d31", "#2e75b6"]
    forcar_sinal = [False, True, True, False]

    pes = [0, valores[0], valores[0] + valores[1], 0]
    topos = [pe + v for pe, v in zip(pes, valores)]

    fig, eixo = plt.subplots(figsize=(8, 4.8))
    eixo.bar(rotulos, valores, bottom=pes, color=cores)

    # Conectores pontilhados entre o topo de uma barra e o pe da proxima,
    # para deixar a cascata visivel mesmo com os termos do meio pequenos.
    for i in range(len(rotulos) - 1):
        eixo.plot([i + 0.4, i + 1 - 0.4], [topos[i], topos[i]],
                  color="#999999", linewidth=0.8, linestyle=":")

    for i, (topo, v, sinal) in enumerate(zip(topos, valores, forcar_sinal)):
        eixo.text(i, topo, dv._num_br(v, 1, forcar_sinal=sinal),
                  ha="center", va="bottom" if v >= 0 else "top", fontsize=9)
    eixo.axhline(0, color="#333333", linewidth=0.8)
    eixo.set_title(
        f"DV01: decay a taxa constante (Conta B), de "
        f"{resumo['data_base']:%d/%m/%Y} at\u00e9 "
        f"{resumo['data_alvo']:%d/%m/%Y}\ntaxa e VNA congelados na "
        f"data-base -- sem dinheiro, sem VNA reprojetado",
        fontsize=11,
    )
    eixo.set_ylabel("DV01 (R$ milh\u00f5es por bp)")
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
