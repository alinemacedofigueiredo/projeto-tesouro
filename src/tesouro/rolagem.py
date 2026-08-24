"""O estoque da divida numa data qualquer depois do ultimo RMD, e a projecao.

A CONTA, por indexador, entre a data-base do RMD (t0) e a data alvo (t1):

    estoque(t1) = estoque(t0)
                + leiloes LIQUIDADOS em (t0, t1]
                - fluxos pagos em (t0, t1]        principal E cupom
                + juros apropriados no periodo

Os tres termos sao todos necessarios -- medido em 24 meses fechados de RMD, erro
medio absoluto por mes, em R$ bilhoes:

    termos usados          Prefixado  Ind.Precos  Taxa Flutuante
    so leiloes                  52,7        32,7            70,7
    + vencimentos               14,6        16,3            42,0
    + juros apropriados         14,6        12,2             3,4

A apropriacao e o MAIOR termo da LFT: 39,9 dos 61,7 bi de variacao mensal media sao
Selic correndo sobre o estoque, e nao emissao.

A DATA QUE CASA E A DE LIQUIDACAO. E a data em que o papel entra no estoque, e e a
que o RMD usa. A defasagem mediana e de 1 dia util, mas 6,1% dos leiloes liquidam no
mes seguinte -- casar por data de leilao erra exatamente as viradas de mes, que e
onde o RMD corta.
"""

import pandas as pd

from . import calendario, config, leiloes_dv

# Qual papel serve para recuperar o VNA de cada indice.
_PAPEL_DO_INDICE = {"SELIC": "LFT", "IPCA": "NTN-B"}

# Quantos dias para tras aceitar um leilao como fonte do VNA.
_JANELA_DO_VNA = 15


def vna_em(indice, quando):
    """O VNA do indice na data, recuperado do leilao mais proximo.

    PU = VNA x cotacao, e a cotacao depende so da taxa e das datas -- entao o PU
    efetivo (financeiro / quantidade) dividido pela cotacao devolve o VNA que o
    Tesouro usou naquele dia.

    LEVANTA quando nao ha leilao na janela. Congelar em silencio subestima o estoque
    da LFT em cerca de 50 bilhoes por mes, e um numero errado sem aviso e pior do que
    numero nenhum.
    """
    quando = pd.Timestamp(quando)
    titulo = _PAPEL_DO_INDICE[indice]
    l = pd.read_csv(config.PROCESSED_DIR / "leiloes.csv",
                    parse_dates=["data_leilao", "data_vencimento"])
    g = l[(l["titulo"] == titulo) & (l["tipo_leilao"] == "Venda")
          & l["taxa_media_pct"].notna() & (l["venda_qtd"] > 0)
          & (l["financeiro_milhoes"] > 0)
          & (l["data_leilao"] <= quando)
          & (l["data_leilao"] >= quando - pd.Timedelta(days=_JANELA_DO_VNA))]
    if g.empty:
        raise LookupError(
            f"nao ha leilao de {titulo} entre {_JANELA_DO_VNA} dias antes de "
            f"{quando:%d/%m/%Y} para recuperar o VNA de {indice}. Congelar o VNA "
            f"subestima o estoque, e por isso a rolagem para aqui.")

    cal = calendario.padrao()
    r = g.sort_values("data_leilao").iloc[-1]
    implicito = leiloes_dv._vna_implicito(
        cal, titulo, r["data_leilao"].date(), r["data_vencimento"].date(),
        r["taxa_media_pct"] / 100, r["venda_qtd"], r["financeiro_milhoes"])
    if implicito is None:
        raise LookupError(
            f"o leilao de {titulo} em {r['data_leilao']:%d/%m/%Y} nao permitiu "
            f"recuperar o VNA de {indice}.")
    return implicito


# Os indexadores que a rolagem move. O Cambio fica de fora -- ver PARADOS.
INDEXADORES = ("Prefixado", "\u00cdndice Pre\u00e7os", "Taxa Flutuante")

# O CAMBIO E A DPFe: comparados os 307 meses da serie, a diferenca mediana entre os
# dois e de R$ 4,9 bilhoes. A DPFe nao passa por leilao, e o movimento dela e cambio
# mais emissao externa, que este projeto nao tem -- entao nao ha como rolar um sem o
# outro.
#
# Ele e segurado no valor do ultimo RMD. Custo medido: variacao mensal mediana de
# R$ 5,2 bi, ou 0,06% do estoque total; em dois meses, no pior decil, R$ 32,5 bi.
# Contra uma banda de cambio com largura de pontos percentuais inteiros, e ruido.
#
# O que NAO e aceitavel e segura-lo em silencio: ele entra no denominador dos outros
# tres percentuais, entao a pagina marca a linha dele como nao rolada.
PARADOS = ("C\u00e2mbio",)

_INDICE_DO_INDEXADOR = {"Taxa Flutuante": "SELIC",
                        "\u00cdndice Pre\u00e7os": "IPCA"}

# Carga do prefixado: LTN e NTN-F nao tem VNA, carregam para o par pela taxa de
# emissao. O residuo medido sem este termo e de +12,2 bi/mes sobre ~1.900 bi, ou
# 0,64% ao mes -- que e uma carga de ~13% ao ano, e nao ruido.
_CARGA_DO_PREFIXADO = 0.135

_INDEXADOR_DO_TITULO = {"LTN": "Prefixado", "NTN-F": "Prefixado",
                        "NTN-B": "\u00cdndice Pre\u00e7os",
                        "NTN-C": "\u00cdndice Pre\u00e7os",
                        "LFT": "Taxa Flutuante"}

_SINAL = {"Venda": 1, "Extra Venda": 1, "Compra": -1, "Extra Compra": -1,
          "Troca": 0}


def base_do_rmd():
    """A data-base do ultimo RMD, e o estoque por indexador nela."""
    c = pd.read_csv(config.PROCESSED_DIR / "composicao_dpf.csv",
                    parse_dates=["data"])
    piv = c.pivot_table(index="data", columns="indexador",
                        values="valor_milhoes", aggfunc="sum").fillna(0.0)
    return piv.index.max(), piv.loc[piv.index.max()]


def leiloes_liquidados(de, ate):
    """Financeiro liquido dos leiloes liquidados em (de, ate], por indexador."""
    l = pd.read_csv(config.PROCESSED_DIR / "leiloes.csv",
                    parse_dates=["data_liquidacao"])
    l = l[(l["data_liquidacao"] > pd.Timestamp(de))
          & (l["data_liquidacao"] <= pd.Timestamp(ate))].copy()
    l["indexador"] = [_INDEXADOR_DO_TITULO.get(t) for t in l["titulo"]]
    l["sinal"] = [_SINAL.get(t, 0) for t in l["tipo_leilao"]]
    l = l[l["indexador"].notna()]
    fluxo = (l["financeiro_milhoes"] * l["sinal"]).groupby(l["indexador"]).sum()
    return fluxo.reindex(list(INDEXADORES)).fillna(0.0)


def _vna_para_apropriacao(indice, quando):
    """O VNA na data, preferindo o vna.csv (exato) ao leilao (vna_em).

    vna_em ANCORA no leilao mais proximo, ate 15 dias antes de 'quando' -- nao
    NA data pedida. Esse desvio muda mes a mes (0 a 15 dias em cada ponta),
    entao a razao vna_em(ate)/vna_em(de) embute um erro de contagem de dias que
    NAO cancela entre as duas pontas. Medido no backtest: usar vna_em onde o
    vna.csv ja tem o valor exato levava a Taxa Flutuante a errar ate 0,39% num
    unico mes -- acima da banda de 0,2%; trocando pelo valor exato, o pior mes
    cai para 0,19%.
    vna_em so e necessario ALEM do vna.csv, que termina na data-base do RMD
    (ver o docstring dele) -- e e exatamente ali, e so ali, que ele deve ser
    chamado.
    """
    quando = pd.Timestamp(quando)
    v = pd.read_csv(config.PROCESSED_DIR / "vna.csv", parse_dates=["data"])
    s = v[v["indice"] == indice]
    if quando <= s["data"].max():
        conhecido = s[s["data"] <= quando].sort_values("data")
        return float(conhecido.iloc[-1]["vna"])
    return vna_em(indice, quando)


def _apropriacao(indexador, base, de, ate):
    """Juros apropriados sobre o estoque no periodo."""
    if indexador == "Prefixado":
        cal = calendario.padrao()
        du = cal.du(pd.Timestamp(de).date(), pd.Timestamp(ate).date())
        return base * ((1 + _CARGA_DO_PREFIXADO) ** (du / 252) - 1)
    indice = _INDICE_DO_INDEXADOR[indexador]
    return base * (_vna_para_apropriacao(indice, ate)
                   / _vna_para_apropriacao(indice, de) - 1)


def estoque_em(quando, de=None):
    """O estoque por indexador na data, rolado desde o RMD (ou desde 'de')."""
    from . import fluxos

    if de is None:
        de, inicial = base_do_rmd()
    else:
        c = pd.read_csv(config.PROCESSED_DIR / "composicao_dpf.csv",
                        parse_dates=["data"])
        piv = c.pivot_table(index="data", columns="indexador",
                            values="valor_milhoes", aggfunc="sum").fillna(0.0)
        de = pd.Timestamp(de)
        inicial = piv.loc[de]

    quando = pd.Timestamp(quando)
    emitido = leiloes_liquidados(de, quando)
    pagou = fluxos.pagos(de, quando)
    saida = {}
    for ind in INDEXADORES:
        base = float(inicial[ind])
        do_ind = pagou[pagou["indexador"] == ind]
        pago = (do_ind["principal_milhoes"].sum()
                + do_ind["cupom_milhoes"].sum())
        saida[ind] = (base + float(emitido[ind]) - pago
                      + _apropriacao(ind, base, de, quando))
    for ind in PARADOS:
        saida[ind] = float(inicial[ind])
    return pd.Series(saida)
