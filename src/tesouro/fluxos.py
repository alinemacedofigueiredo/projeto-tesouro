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


# Indexador de cada papel, na nomenclatura de _INDICE_DO_VNA -- e nao a coluna
# "indexador" do estoque, que usa outros nomes (p.ex. "Selic" em vez de
# "Taxa Flutuante"). Todo papel com quantidade > 0 no estoque mais recente tem
# de aparecer aqui, ou ele sai da conta em silencio.
#
# OS VALORES SAO DADO, NAO ROTULO LIVRE: tem de bater byte a byte com a coluna
# "indexador" de composicao_dpf.csv, que a rolagem da Task 7 usa para filtrar.
# Por isso o acento entra por escape \uXXXX -- o arquivo continua ASCII puro
# (regra do projeto), mas a string em tempo de execucao e "Indice Precos"
# acentuado, igual ao CSV. Ver
# test_os_rotulos_de_INDEXADOR_batem_com_o_composicao_dpf em test_fluxos.py.
INDEXADOR = {"LTN": "Prefixado", "NTN-F": "Prefixado",
             "NTN-B": "\u00cdndice Pre\u00e7os",
             "NTN-B Principal": "\u00cdndice Pre\u00e7os",
             "NTN-C": "\u00cdndice Pre\u00e7os",
             "NTN-B1 EducA+": "\u00cdndice Pre\u00e7os",
             "NTN-B1 RendA+": "\u00cdndice Pre\u00e7os",
             "LFT": "Taxa Flutuante", "LFT-TD1 Reserva": "Taxa Flutuante"}

# A NTN-C E IGP-M, E ENTRA AQUI COM O VNA DE IPCA. Isto e uma APROXIMACAO
# CONHECIDA, e o comentario anterior media o erro errado -- fica registrado aqui
# para ninguem repetir a conta.
#
# Este mapa e por INDEXADOR, e a NTN-C cai em "Indice Precos" junto com a NTN-B,
# entao o VNA dela sai da serie de IPCA. Nao ha serie de IGP-M neste projeto:
# em 27/08/2026, a NTN-C nao aparece nas taxas nem nos precos da Bloomberg, e a
# pasta da ANBIMA so tem feriados.
#
# O QUE SE SUBSTITUI E O NIVEL, E NAO A VARIACAO -- e ai esta o problema. Os dois
# VNAs partem de julho/2000, mas com 26 anos de inflacoes acumuladas diferentes,
# entao nao sao o mesmo numero. Medido em 31/07/2026:
#
#     VNA de IPCA                              4.740,66
#     PU implicito da NTN-C (financeiro/qtd)    7.065,30
#
# O PU ainda embute a cotacao, entao o VNA verdadeiro esta abaixo de 7.065 -- mas
# acima de 4.740. A base do cupom sai subestimada em algo entre um quarto e a
# metade. Nao da para cravar sem o VNA de IGP-M, que o projeto nao tem.
#
# O COMENTARIO ANTERIOR dizia "1 pp de divergencia entre IGP-M e IPCA move R$ 0,8
# bi, 0,04% do bloco". Essa conta vale para um modelo DIFERENTE deste, sugerido
# por ela em 27/08/2026: ancorar no VNA de IGP-M verdadeiro e carregar pela
# VARIACAO do IPCA --
#
#     vna_igpm(hoje) = vna_igpm(julho) * vna_ipca(hoje) / vna_ipca(julho)
#
# Naquele modelo o erro e so a divergencia de variacao na janela, e e mesmo
# pequeno. Neste, e a diferenca de nivel. Implementar o modelo dela depende de
# obter um unico numero, o VNA de IGP-M na data-base, que hoje nao temos.
#
# O TAMANHO DA POSICAO, para calibrar quanto isso merece: um unico papel vivo, a
# NTN-C 2031, com R$ 78,0 bi em 31/07/2026 -- 0,85% do estoque. O cupom sai a
# R$ 3,05 bi por pagamento com o VNA de IPCA; com a base correta, algo perto de
# R$ 4 a 4,5 bi. Sao dois pagamentos por ano, em janeiro e julho.
#
# NAO AFETA A PROJECAO CORRENTE: a janela vai de 31/07 a 31/12 e nao contem
# nenhum cupom de NTN-C. O primeiro afetado e o de janeiro de 2027.
#
# Se um dia alguem precisar do valor CONTABIL de uma NTN-C, esta substituicao
# nao serve de jeito nenhum.
_INDICE_DO_VNA = {"\u00cdndice Pre\u00e7os": "IPCA", "Taxa Flutuante": "SELIC"}


def _estoque_em(de):
    """O estoque de titulos e vencimentos no snapshot vigente em 'de'.

    NAO PODE SER SEMPRE O SNAPSHOT MAIS RECENTE. pagos() e chamado pelo backtest
    da rolagem em janelas do passado, e um titulo que ja venceu antes de hoje ja
    saiu do snapshot mais recente -- o vencimento dele desapareceria da conta em
    silencio, e exatamente nos meses de maior resgate (medido: R$115-341 bi de
    LTN/LFT sumindo em cada virada de trimestre). O snapshot certo para saber o
    que PODE vencer ou pagar cupom dentro da janela e o vigente no INICIO dela.
    """
    e = pd.read_csv(config.PROCESSED_DIR / "estoque_titulos_vencimento.csv",
                    parse_dates=["data", "vencimento"])
    disponiveis = e[e["data"] <= pd.Timestamp(de)]
    if disponiveis.empty:
        raise LookupError(
            f"nao ha snapshot de estoque_titulos_vencimento.csv ate "
            f"{pd.Timestamp(de):%d/%m/%Y}.")
    u = e[(e["data"] == disponiveis["data"].max())
          & (e["quantidade_mil"] > 0)].copy()
    faltando = sorted(set(u["titulo"]) - set(INDEXADOR))
    if faltando:
        raise LookupError(
            f"papel sem indexador em fluxos.INDEXADOR: {faltando}. Sem isso ele "
            f"sai da conta em silencio, e o fluxo pago fica menor do que e.")
    u["indexador"] = [INDEXADOR[t] for t in u["titulo"]]
    return u


def _vna(indice, quando):
    v = pd.read_csv(config.PROCESSED_DIR / "vna.csv", parse_dates=["data"])
    s = v[(v["indice"] == indice) & (v["data"] <= quando)]
    if s.empty:
        raise LookupError(
            f"nao ha VNA de {indice} ate {quando:%d/%m/%Y}. O cupom de papel "
            f"indexado nao pode ser calculado sem ele.")
    return float(s.iloc[-1]["vna"])


def pagos(de, ate):
    """Principal e cupom pagos em (de, ate], por data e indexador.

    JANELA FECHADA A DIREITA E ABERTA A ESQUERDA. A rolagem encadeia janelas, e
    sobreposicao de um dia conta um vencimento duas vezes.
    """
    de, ate = pd.Timestamp(de), pd.Timestamp(ate)
    u = _estoque_em(de)
    linhas = []

    vence = u[(u["vencimento"] > de) & (u["vencimento"] <= ate)]
    for _, r in vence.iterrows():
        linhas.append({"data": r["vencimento"], "indexador": r["indexador"],
                       "principal_milhoes": r["financeiro_milhoes"],
                       "cupom_milhoes": 0.0})

    for dia in pd.date_range(de + pd.Timedelta(days=1), ate, freq="D"):
        for _, r in u.iterrows():
            if not paga_cupom_em(r["titulo"], r["vencimento"], dia):
                continue
            taxa = (1 + CUPOM_ANUAL[r["titulo"]]) ** 0.5 - 1
            # .get() e nao []: papel Prefixado (NTN-F) nao tem entrada em
            # _INDICE_DO_VNA porque nao tem VNA -- ele paga cupom sobre a face
            # de 1.000, sem chamar _vna. Com [] isso e um KeyError toda vez que
            # a janela pega 01/01 ou 01/07, os dias de cupom da NTN-F.
            indice = _INDICE_DO_VNA.get(r["indexador"])
            base = _vna(indice, dia) if indice == "IPCA" else 1000.0
            valor = r["quantidade_mil"] * 1000 * base * taxa / 1e6
            linhas.append({"data": dia, "indexador": r["indexador"],
                           "principal_milhoes": 0.0, "cupom_milhoes": valor})

    if not linhas:
        return pd.DataFrame(columns=["data", "indexador", "principal_milhoes",
                                     "cupom_milhoes"])
    return pd.DataFrame(linhas).sort_values("data").reset_index(drop=True)
