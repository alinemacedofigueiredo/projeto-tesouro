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
