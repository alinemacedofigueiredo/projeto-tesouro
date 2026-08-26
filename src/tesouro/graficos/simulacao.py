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

from . import paf
from .. import calendario_leiloes, rolagem

# Passo das colunas, em R$ bilhoes, e margem das linhas, em pontos percentuais.
PASSO_TOTAL = 200
MARGEM_PCT = 1

# O rotulo de cada tabela na tela. Sai do vocabulario dela: e "indice de
# precos", e nao "IPCA" -- o indexador do PAF inclui a NTN-C, que e IGP-M.
_ROTULO = {
    "prefixado_pct": "Prefixado",
    "indice_precos_pct": "\u00cdndice de pre\u00e7os",
    "taxa_flutuante_pct": "Taxa flutuante",
}


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
