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
