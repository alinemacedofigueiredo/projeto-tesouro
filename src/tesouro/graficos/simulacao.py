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
