"""Preco unitario e DV01 dos titulos publicos federais.

Portado do codigo em uso na mesa, validado contra o PX_DIRTY_MID da
Bloomberg em 438 pares papel-data entre 2020 e 2026 -- exato em todas as
comparacoes de NTN-F e NTN-B. Ver docs/convencoes-dv.md.

A taxa entra em DECIMAL (0.135 = 13,5%); quem chama converte.

Tres convencoes que parecem detalhe e nao sao:

  A truncagem esta dentro do DV de proposito. O PU truncado e o preco
  negociavel, entao a diferenca entre dois truncados e o que de fato se
  ganha ou perde quando a taxa anda 1 bp. Nao "melhore" isso calculando o
  DV com PUs cheios.

  O sinal e PU(taxa + 1bp) - PU(taxa), negativo para titulo. Multiplicado
  pela posicao, da direto o dinheiro perdido num choque de alta.

  A LFT devolve None no DV, nao zero: e decisao de modelagem do projeto,
  e "nao se aplica" precisa ser distinguivel de "risco nulo medido".
"""
import math

_UM_BP = 0.0001

# Cupom semestral: 1000 * ((1,10)^0,5 - 1) = 48,8088 na NTN-F;
# 100 * ((1,06)^0,5 - 1) = 2,9563 na NTN-B, sobre principal de 100.
_CUPOM_NTNF = 1000 * ((1.10 ** 0.5) - 1)
_CUPOM_NTNB = 100 * ((1.06 ** 0.5) - 1)


def _truncar(x, casas):
    fator = 10 ** casas
    return math.trunc(x * fator) / fator


def _meses_antes(d, meses):
    """Recua `meses` no calendario, sem estourar o fim do mes."""
    import calendar as _c
    from datetime import date as _date
    m = d.month - 1 - meses
    ano = d.year + m // 12
    m = m % 12 + 1
    return _date(ano, m, min(d.day, _c.monthrange(ano, m)[1]))


def pu_ltn(cal, d0, vencimento, taxa):
    """Prefixado sem cupom: 1000 descontado ate o vencimento."""
    venc = cal.ajustar_vencimento(vencimento)
    if d0 >= venc:
        return 0.0
    return _truncar(1000 / ((1 + taxa) ** (cal.du(d0, venc) / 252)), 6)


def pu_lft(cal, d0, vencimento, taxa, vna):
    """Pos-fixada: cotacao sobre o agio, aplicada ao VNA da Selic."""
    venc = cal.ajustar_vencimento(vencimento)
    if d0 >= venc:
        return 0.0
    cotacao = _truncar(100 / ((1 + taxa) ** (cal.du(d0, venc) / 252)), 4)
    return _truncar(cotacao * vna / 100, 6)


def pu_ntnf(cal, d0, vencimento, taxa):
    """Prefixado com cupom semestral. Os cupons caem no dia 1."""
    from datetime import date as _date
    venc = cal.ajustar_vencimento(vencimento)
    cupom = venc
    soma = 0.0
    while cupom > d0:
        principal = 1000 if cupom == venc else 0
        fluxo = round(_CUPOM_NTNF + principal, 5)
        soma += fluxo / ((1 + taxa) ** (cal.du(d0, cupom) / 252))
        anterior = _meses_antes(cupom, 6)
        cupom = cal.ajustar_vencimento(_date(anterior.year, anterior.month, 1))
    return _truncar(soma, 6)


def pu_ntnb(cal, d0, vencimento, taxa, vna):
    """Indexada ao IPCA, cupom semestral. Os cupons caem no dia 15.

    A cotacao e truncada em 4 casas antes de multiplicar pelo VNA, e o
    resultado em 6 -- e a convencao do mercado, nao um arredondamento
    nosso.
    """
    from datetime import date as _date
    venc = cal.ajustar_vencimento(vencimento)
    cupom = venc
    cotacao = 0.0
    while cupom > d0:
        principal = 100 if cupom == venc else 0
        fluxo = round(_CUPOM_NTNB + principal, 6)
        cotacao += fluxo / ((1 + taxa) ** (cal.du(d0, cupom) / 252))
        anterior = _meses_antes(cupom, 6)
        cupom = cal.ajustar_vencimento(_date(anterior.year, anterior.month, 15))
    return _truncar(_truncar(cotacao, 4) / 100 * vna, 6)


_INDEXADOS = {"NTN-B", "LFT"}


def pu(cal, titulo, d0, vencimento, taxa, vna=None):
    """Despacha para a formula do titulo. Taxa em decimal."""
    if titulo in _INDEXADOS and vna is None:
        raise ValueError(f"{titulo} exige VNA e nenhum foi informado")
    if titulo == "LTN":
        return pu_ltn(cal, d0, vencimento, taxa)
    if titulo == "NTN-F":
        return pu_ntnf(cal, d0, vencimento, taxa)
    if titulo == "NTN-B":
        return pu_ntnb(cal, d0, vencimento, taxa, vna)
    if titulo == "LFT":
        return pu_lft(cal, d0, vencimento, taxa, vna)
    raise ValueError(
        f"titulo sem formula de precificacao: {titulo!r}. "
        f"O escopo do projeto e LTN, NTN-F, NTN-B e LFT."
    )


def dv(cal, titulo, d0, vencimento, taxa, vna=None):
    """Variacao do PU para +1 bp na taxa. Negativo para titulo.

    Devolve None para LFT: por decisao de modelagem ela nao entra no
    DV01 do projeto, e None mantem isso distinguivel de zero.
    """
    if titulo == "LFT":
        return None
    return (pu(cal, titulo, d0, vencimento, taxa + _UM_BP, vna)
            - pu(cal, titulo, d0, vencimento, taxa, vna))
