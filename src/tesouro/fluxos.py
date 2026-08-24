"""Os fluxos que o Tesouro paga: principal no vencimento, e cupom no caminho.

ESTE MODULO EXISTE SEPARADO da rolagem por causa do cupom. Ele tem regra propria
por papel, e a regra tem uma armadilha que custa 2,1 vezes o numero certo se passar
batido -- ver paga_cupom_em. Misturado numa soma maior, isso fica escondido.

POR QUE CALCULAR EM VEZ DE LER A ABA 3.4. A 3.4 traz o fluxo com cupom, e seria a
fonte obvia. Duas razoes contra:

  1. Ela e o RETRATO ATUAL. A camada de dados guarda so o mes corrente, entao o
     termo lido dela nao teria como ser testado nos 24 meses de backtest da rolagem.
  2. Ela e MENSAL, e a rolagem corta em data. O cupom da NTN-B cai no dia 15 e o da
     NTN-F no dia 1: ratear pelo mes poria dentro da janela um fluxo que ainda nao
     aconteceu.

Calculado, o termo serve as duas pontas -- o backtest e a projecao -- e e conferido
contra a 3.4 no mes em que nada vence (novembro de 2026: 26,4 calculado contra 25,8
da 3.4, +2,4%).
"""

import pandas as pd

from . import config

# Taxa de cupom de cada papel, ao ano. Os demais nao pagam cupom.
CUPOM_ANUAL = {"NTN-B": 0.06, "NTN-F": 0.10, "NTN-C": 0.12}

# Em que dia do mes cai o cupom de cada papel.
DIA_DO_CUPOM = {"NTN-B": 15, "NTN-C": 15, "NTN-F": 1}


def paga_cupom_em(titulo, vencimento, quando):
    """O papel paga cupom nesta data?

    A REGRA E O ANIVERSARIO DELE, e nao um trimestre fixo do calendario. Uma NTN-B
    que vence em 15/05 paga em maio e em novembro; uma que vence em 15/08 paga em
    agosto e em fevereiro. Supor que toda NTN-B paga em fev/mai/ago/nov dobra o
    cupom, porque o estoque se divide quase pela metade entre os dois grupos.

    A NTN-B PRINCIPAL nao paga cupom, e o nome dela comeca com "NTN-B" -- por isso a
    consulta e por igualdade exata, e nao por prefixo.
    """
    if titulo not in CUPOM_ANUAL:
        return False
    if pd.isna(vencimento) or pd.isna(quando):
        return False
    if quando.day != DIA_DO_CUPOM[titulo]:
        return False
    if quando > vencimento:
        return False
    # Semestral: o mes tem de distar um multiplo de seis do mes do vencimento.
    return (vencimento.month - quando.month) % 6 == 0
