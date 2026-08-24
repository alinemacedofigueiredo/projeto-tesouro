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
