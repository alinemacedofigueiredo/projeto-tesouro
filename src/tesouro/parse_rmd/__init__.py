"""Parsers das abas do anexo do RMD, um modulo por grupo de abas."""
from .. import leitura_rmd
from . import custo, estoque, estoque_vencimento, funding, paf_reserva, prazo, vencimentos


def gravar_tudo(caminho=None):
    """Roda todos os parsers do RMD e grava os CSVs canonicos."""
    xl = leitura_rmd.abrir(caminho)
    for modulo in (funding, estoque, estoque_vencimento, vencimentos,
                   prazo, custo, paf_reserva):
        modulo.gravar(xl)
