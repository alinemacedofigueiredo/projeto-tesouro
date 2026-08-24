"""A premissa da projecao, tirada da propria curva do projeto.

NENHUMA FONTE NOVA. A dona do projeto escolheu esta opcao entre quatro em
24/08/2026: a Selic vem interpolada da curva de LTN, e a inflacao vem do breakeven
entre a curva prefixada e a taxa real da NTN-B. Nao ha numero escolhido a mao, e as
duas contas sao reproduziveis.

ARMADILHA. A LTN de vencimento mais proximo de 31/12/2026 e a 01/01/2027, e ela NAO
TEM COTACAO: e um dos dois papeis que so existem no Tesouro Direto (achado de
22/08/2026). Escolher "o vencimento mais proximo" pega justamente essa, e a conta
sai NaN sem reclamar. Toda selecao de papel aqui filtra por taxa presente ANTES de
medir distancia.
"""

import bisect

import pandas as pd

from . import calendario, config


def _curva(titulo, data_base=None):
    """Os papeis COM COTACAO, ordenados por dias uteis ate o vencimento."""
    d = pd.read_csv(config.PROCESSED_DIR / "dv_por_papel.csv",
                    parse_dates=["data", "vencimento"])
    base = pd.Timestamp(data_base) if data_base is not None else d["data"].max()
    g = d[(d["data"] == base) & (d["titulo"] == titulo)
          & d["taxa_pct"].notna()].copy()
    if g.empty:
        raise LookupError(
            f"nenhuma {titulo} com cotacao em {base:%d/%m/%Y}. Sem curva nao ha "
            f"premissa, e projetar com premissa inventada seria pior.")
    cal = calendario.padrao()
    g["du"] = [cal.du(base.date(), v.date()) for v in g["vencimento"]]
    return base, g.sort_values("du")


def _interpola(g, du):
    xs, ys = list(g["du"]), list(g["taxa_pct"])
    if du <= xs[0]:
        return ys[0]
    if du >= xs[-1]:
        return ys[-1]
    i = bisect.bisect_left(xs, du)
    peso = (du - xs[i - 1]) / (xs[i] - xs[i - 1])
    return ys[i - 1] + peso * (ys[i] - ys[i - 1])


def _checar_ordem(base, ate):
    # calendario.du() e simetrico: du(base, ate) com ate antes de base devolve a
    # mesma distancia positiva que ate depois de base, entao _interpola pegaria a
    # ponta errada da curva sem reclamar. A premissa e sempre para a frente da
    # data-base, entao barra aqui em vez de deixar a conta sair errada em silencio.
    if ate < base:
        raise ValueError(
            f"'ate' ({ate:%d/%m/%Y}) e anterior a data-base ({base:%d/%m/%Y}); "
            f"a curva projeta para a frente, nao para tras.")


def selic_implicita(ate, data_base=None):
    """Taxa ao ano, em decimal, interpolada na curva de LTN ate 'ate'."""
    base, g = _curva("LTN", data_base)
    ate = pd.Timestamp(ate)
    _checar_ordem(base, ate)
    cal = calendario.padrao()
    du = cal.du(base.date(), ate.date())
    return _interpola(g, du) / 100


def ntnb_de_referencia(ate, data_base=None):
    """A NTN-B mais curta COM COTACAO cujo vencimento passe de 'ate'.

    Nao e a mais proxima: em 30/06/2026 a mais proxima e a de 15/08/2026, a 33 dias
    uteis, com taxa real de 11,25% -- ponta de curva, e nao expectativa.
    """
    base, g = _curva("NTN-B", data_base)
    ate = pd.Timestamp(ate)
    _checar_ordem(base, ate)
    depois = g[g["vencimento"] > ate]
    if depois.empty:
        raise LookupError(
            f"nenhuma NTN-B com cotacao vence depois de {ate:%d/%m/%Y}.")
    return depois.iloc[0]["vencimento"]


def inflacao_implicita(ate, data_base=None):
    """Breakeven ao ano, em decimal, no prazo da NTN-B de referencia."""
    base, pre = _curva("LTN", data_base)
    _, b = _curva("NTN-B", data_base)
    ate = pd.Timestamp(ate)
    _checar_ordem(base, ate)
    venc = ntnb_de_referencia(ate, data_base)
    linha = b[b["vencimento"] == venc].iloc[0]
    nominal = _interpola(pre, linha["du"]) / 100
    real = linha["taxa_pct"] / 100
    return (1 + nominal) / (1 + real) - 1
