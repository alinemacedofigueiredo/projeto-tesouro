"""DV01 emitido em cada leilao -- a camada de dado da entrega 3.

O RMD conta emissao em REAIS. Este modulo conta em RISCO: quanto de DV01 o Tesouro
colocou no mercado em cada leilao, que e outra pergunta e tem outra resposta. Emitir
10 bilhoes de LTN de seis meses e emitir 10 bilhoes de NTN-B 2060 sao a mesma linha
na aba 1.1 e coisas incomparaveis aqui.

Este arquivo CALCULA; a camada de graficos so desenha o que ele grava. E a mesma
divisao das entregas anteriores, e ela existe para que trocar o motor de desenho nao
mexa em conta nenhuma.

CONVENCOES, todas com consequencia no numero:

  - a taxa do CSV esta em PERCENTUAL e precificacao.pu espera FRACAO. Passar o valor
    direto nao levanta erro: devolve PU de 84,75 onde o certo e 4.490, e DV zerado.
    Medido em 19/08/2026 (ver docs/leiloes-o-que-o-dado-permite.md);
  - o DV e precificado na data de LIQUIDACAO, que e quando a posicao passa a existir,
    e reportado na data do LEILAO, que e quando a decisao foi tomada;
  - compra entra com sinal NEGATIVO, em financeiro e em DV: recompra tira risco do
    mercado, e somar com emissao daria o liquido, que e o que interessa;
  - a LFT nao tem DV por decisao de modelagem da entrega 2 (premissa de duration
    zero). A linha dela fica, com financeiro e DV vazio -- vazio e nao zero, porque
    zero seria uma afirmacao sobre o risco dela;
  - as colunas do Banco Central (venda_bacen_qtd, financeiro_bacen_milhoes) NAO
    entram: nao sao emissao do Tesouro;
  - o calendario comeca em 2001, entao os leiloes de 2000 ficam de fora. Sao 52
    semanas, e a exclusao e contada, nao silenciosa.

O VNA DA NTN-B NAO PRECISA SER APROXIMADO -- ele sai do proprio dado do leilao.

O caminho obvio seria usar o vna.csv, que tem uma observacao por mes enquanto os
leiloes sao semanais. Medido, esse caminho erra o PU em 0,15% na mediana e 0,66% no
percentil 95 para a NTN-B, e 0,30%/0,90% para a LFT -- a assinatura do VNA do
fechamento sendo usado no meio do mes.

Mas o PU e EXATAMENTE linear no VNA: PU = VNA x cotacao, e a cotacao depende so da
taxa e das datas. Como o Tesouro publica o financeiro e a quantidade de cada leilao,
o VNA daquele dia se recupera por divisao:

    cotacao = pu(..., vna=1)
    vna_do_dia = (financeiro x 1e6 / quantidade) / cotacao

Isso e o VNA que ELE usou para liquidar, na data exata, sem interpolar nem projetar
IPCA. O vna.csv continua entrando como conferencia: os dois tem de ficar dentro da
acumulacao do mes, e um desvio grande denuncia dado errado em vez de virar DV torto.
"""
import pandas as pd

from . import (calendario, config, leilao_ofertado, leiloes_recentes,
               precificacao)
from .leiloes_recentes import COLUNA_ESTAGIO as ESTAGIO

# O TESOURO CLASSIFICA CADA LEILAO PELO VERTICE, e essa classificacao esta no dado:
# a coluna 'referencia' do leiloes.csv traz "NTN-B 5 anos", "NTN-B 40 anos" e assim
# por diante, e a API de leiloes traz o mesmo no campo 'benchmark'.
#
# A FRONTEIRA FICOU EM 5 ANOS, E AGORA E MEDIDA NO VERTICE E NAO NO PRAZO. Decidido
# em 20/08/2026, depois de a API publicar a tabela de benchmarks vigentes: curta sao
# os vertices de 3 e 5 anos, longa e de 7 para cima.
#
# A DIFERENCA NAO E COSMETICA. Classificar pelo prazo calculado e classificar pelo
# vertice publicado discordam em 401 dos 4.110 leiloes de NTN-B -- 9,8% -- e todos
# pelo mesmo motivo: sao papeis que o proprio Tesouro chama de "NTN-B 5 anos" e que,
# no comeco da vigencia do benchmark, ainda tinham mais anos a correr do que o
# rotulo dizia. Pelo prazo caiam na faixa de cima; pelo rotulo dele, nao.
#
# ONDE A LINHA CAI E DECISAO DELA. Foi 5 anos de 25/08/2026 a 25/09/2026, e
# passou a 10 -- "quero que a NTN-B de dez anos entre na curta". O Tesouro
# publica os vertices 3, 4, 5, 7, 10, 15, 20, 25, 30, 35 e 40 e NUNCA diz quais
# sao curtos; a fronteira e nossa.
#
# Medido no financeiro emitido em NTN-B, com o corte em 10:
#     ate 10 anos   R$ 1.925 bi      acima de 10   R$ 518 bi      78,8% / 21,2%
# Com o corte em 5 era 53,6% / 46,4%: o vertice de 10 anos sozinho move 25 pp.
#
# Mudar a fronteira e trocar esta constante; nao exige recalcular o vertice,
# porque o dado gravado ja o carrega -- mas EXIGE regravar o CSV, porque a
# familia e gravada nele.
CORTE_NTNB_ANOS = 10

# Os nomes das duas faixas. Sao VALOR DE DADO -- vao gravados no CSV e sao chave
# dos recortes dos graficos -- e nao rotulo de tela, por isso moram aqui e nao
# em cada pagina.
FAMILIA_NTNB_CURTA = "NTN-B at\u00e9 10 anos"
FAMILIA_NTNB_LONGA = "NTN-B acima de 10 anos"

# Os vertices que o Tesouro oferta. Usados para enquadrar o leilao que veio sem
# rotulo: a coluna 'referencia' so esta preenchida em 1.548 dos 4.476 leiloes de
# NTN-B, e so a partir de 2014.
VERTICES = (3, 5, 7, 10, 15, 20, 25, 30, 35, 40)

# A precificacao do projeto cobre estes quatro. NTN-C e NTN-D existem no historico
# (186 e 55 leiloes) e ficam de fora com motivo declarado, em vez de sumirem.
PAPEIS_PRECIFICADOS = ("LTN", "NTN-F", "NTN-B", "LFT")

# Sem formula de DV: a LFT por decisao de modelagem, as outras por nao terem
# precificacao no projeto.
SEM_DV = ("LFT",)

_PRIMEIRO_ANO_DO_CALENDARIO = 2001


def _vna_ate(vna, indice, quando):
    """Ultimo VNA do indice ate a data. None se nao houver."""
    serie = vna[(vna["indice"] == indice) & (vna["data"] <= quando)]
    if serie.empty:
        return None, None
    linha = serie.iloc[-1]
    return float(linha["vna"]), linha["data"]


def dv_por_leilao(ate_o_estagio="planilha"):
    """Uma linha por leilao-papel-volta, com o DV unitario e o DV total.

    Devolve tambem as linhas sem DV (LFT), porque o financeiro delas entra nos
    graficos. Quem quiser so o que tem risco filtra por dv_milhoes.notna().

    ate_o_estagio diz quanto do provisorio entra: "planilha" (so o definitivo, que e
    o default e mantem o contrato antigo deste CSV), "aceito" (mais o resultado do
    dia) ou "ofertado" (mais o teto anunciado).

    A coluna 'estagio' sai sempre. Ela nao e detalhe de proveniencia -- e o quanto
    aquele numero ainda pode mudar:

      ofertado -- a quantidade e TETO e vai cair; a taxa e emprestada do leilao
                  anterior. Historicamente o Tesouro aceita 83,9% do que oferta;
      aceito   -- a quantidade e final, mas a taxa publicada na hora pode ser
                  preliminar;
      planilha -- nao muda mais.

    Quem desenha usa essa coluna para dar tres aparencias diferentes a barra.
    """
    cal = calendario.padrao()

    if ate_o_estagio == "planilha":
        l = pd.read_csv(
            config.PROCESSED_DIR / "leiloes.csv",
            parse_dates=["data_leilao", "data_liquidacao", "data_vencimento"],
        )
    else:
        l = leiloes_recentes.completo(ate_o_estagio=ate_o_estagio)
    if ESTAGIO not in l.columns:
        l[ESTAGIO] = "planilha"

    # As linhas de oferta chegam sem taxa e sem financeiro; leilao_ofertado.preencher
    # completa as duas, e marca que completou. Feito AQUI, e nao la na coleta, para
    # que a suposicao seja refeita com o historico de hoje toda vez que este CSV for
    # regravado -- e nao congelada no dia em que o arquivo foi baixado.
    de_oferta = l[ESTAGIO] == "ofertado"
    l["taxa_suposta"] = False
    if de_oferta.any():
        preenchidas = leilao_ofertado.preencher(l[de_oferta], base=l[~de_oferta])
        l = pd.concat([l[~de_oferta], preenchidas], ignore_index=True)
        # A marca precisa CHEGAR AO CSV: sem ela, a pagina nao consegue dizer se a
        # taxa daquela barra foi digitada por quem sabe o mercado ou emprestada do
        # leilao anterior. E a diferenca entre 0 e 11 bp de erro.
        l["taxa_suposta"] = l["taxa_suposta"].fillna(False).astype(bool)
    vna = pd.read_csv(config.PROCESSED_DIR / "vna.csv", parse_dates=["data"])

    # Venda e Compra, e as versoes extraordinarias das duas. Troca fica de fora: ela
    # substitui um papel por outro e o liquido dela nao e emissao nem resgate.
    operacoes = {"Venda": "venda", "Extra Venda": "venda",
                 "Compra": "compra", "Extra Compra": "compra"}
    d = l[l["tipo_leilao"].isin(operacoes)].copy()
    d["operacao"] = d["tipo_leilao"].map(operacoes)

    d = d[d["titulo"].isin(PAPEIS_PRECIFICADOS)]
    d = d[d["data_liquidacao"].dt.year >= _PRIMEIRO_ANO_DO_CALENDARIO]
    d = d[d["financeiro_milhoes"].notna() & (d["financeiro_milhoes"] > 0)]

    sinal = d["operacao"].map({"venda": 1.0, "compra": -1.0})
    d["financeiro_milhoes"] = d["financeiro_milhoes"] * sinal
    d["quantidade"] = d["venda_qtd"] * sinal

    unitarios, vnas, mensais = [], [], []
    for _, r in d.iterrows():
        if r["titulo"] in SEM_DV:
            unitarios.append(None)
            vnas.append(None)
            mensais.append(None)
            continue

        taxa = r["taxa_media_pct"] / 100.0
        d0 = r["data_liquidacao"].date()
        venc = r["data_vencimento"].date()

        vna_do_dia, do_mes = None, None
        if r["titulo"] == "NTN-B":
            do_mes, _ = _vna_ate(vna, "IPCA", r["data_liquidacao"])
            vna_do_dia = _vna_implicito(cal, r["titulo"], d0, venc, taxa,
                                        r["quantidade"], r["financeiro_milhoes"])
            if vna_do_dia is None:
                vna_do_dia = do_mes
            if vna_do_dia is None:
                unitarios.append(None)
                vnas.append(None)
                mensais.append(do_mes)
                continue

        # A taxa vai como FRACAO. Ver a nota do modulo: o percentual direto devolve
        # numero plausivel e errado, sem levantar.
        unitarios.append(precificacao.dv(cal, r["titulo"], d0, venc, taxa,
                                         vna_do_dia))
        vnas.append(vna_do_dia)
        mensais.append(do_mes)

    # O SINAL AQUI E O DE RISCO EMITIDO, e nao o de P&L. Conferido contra
    # docs/convencoes-dv.md, que ja dizia: "Risco emitido -- positivo e o Tesouro
    # emitindo; negativo e vencimento ou recompra".
    #
    # precificacao.dv devolve NEGATIVO, que e a convencao de P&L: o dinheiro que
    # quem carrega o papel perde num choque de +1 bp. Correta la, errada aqui --
    # esta tabela mede EMISSAO, e emissao positiva e emissao.
    #
    # A primeira versao deste modulo deixou o sinal de P&L passar, e o resultado foi
    # um grafico de emissao com todas as barras para baixo, que exigiu inverter o
    # eixo do DV para ficar legivel. Invertido o sinal na origem, a inversao do eixo
    # deixou de ser necessaria.
    d["dv_unitario"] = [None if u is None else abs(u) for u in unitarios]
    d["vna_usado"] = vnas
    d["vna_do_mes"] = mensais

    # O DV do lote, em R$ milhoes por ponto-base.
    #
    # A quantidade do CSV esta em TITULOS, nao em milhares -- conferido contra o
    # proprio financeiro do Tesouro: qtd x PU da exatamente financeiro_milhoes x 1e6
    # em todo leilao (razao 1,0000). Com a escala errada o DV saia mil vezes maior, e
    # mil vezes maior ainda parece numero, so que grande demais.
    # quantidade ja carrega o sinal da operacao (venda +, compra -), entao o
    # produto sai positivo na venda e negativo na recompra, que e a convencao.
    d["dv_milhoes"] = d["dv_unitario"] * d["quantidade"] / 1e6

    # O DV QUE ELE TENTOU COLOCAR, e nao o que colocou. A oferta e o teto do dia, e
    # comparar os dois responde uma pergunta que o aceito sozinho nao responde: ele
    # nao conseguiu colocar, ou nao quis? Medido: aceita 83,9% da quantidade
    # ofertada no agregado, e de 62,5% a 88,0% conforme o papel.
    d["oferta_qtd"] = d["oferta_qtd"] * sinal
    d["dv_ofertado_milhoes"] = d["dv_unitario"] * d["oferta_qtd"] / 1e6

    d["prazo_anos"] = ((d["data_vencimento"] - d["data_leilao"]).dt.days / 365.25)
    d["vertice_anos"] = [
        _vertice(titulo, referencia, prazo)
        for titulo, referencia, prazo
        in zip(d["titulo"], d["referencia"], d["prazo_anos"])
    ]
    d["familia"] = [
        _familia(t, p, v) for t, p, v
        in zip(d["titulo"], d["prazo_anos"], d["vertice_anos"])
    ]

    colunas = [ESTAGIO, "taxa_suposta",
               "data_leilao", "data_liquidacao", "titulo", "familia", "operacao",
               "volta", "data_vencimento", "prazo_anos", "vertice_anos",
               "quantidade", "oferta_qtd", "financeiro_milhoes",
               "taxa_media_pct",
               "taxa_corte_pct", "dv_unitario", "dv_milhoes",
               "dv_ofertado_milhoes", "vna_usado",
               "vna_do_mes"]
    return d[colunas].sort_values(["data_leilao", "titulo",
                                   "data_vencimento"]).reset_index(drop=True)


def _vertice(titulo, referencia, prazo_anos):
    """O vertice do Tesouro para aquele leilao, em anos.

    Vem do rotulo dele quando existe -- "NTN-B 40 anos" -> 40. Quando nao existe, e
    o vertice mais proximo do prazo real, que e o mesmo enquadramento que ele faz.
    Guardar os dois criterios numa coluna so seria esconder que um e transcricao e o
    outro e inferencia; por isso o dado gravado tambem carrega prazo_anos.
    """
    import re

    if isinstance(referencia, str):
        achado = re.search(r"(\d+)\s*anos?", referencia)
        if achado:
            return int(achado.group(1))
    if titulo == "LFT" or pd.isna(prazo_anos):
        return None
    return min(VERTICES, key=lambda v: abs(v - prazo_anos))


def _vna_implicito(cal, titulo, d0, vencimento, taxa, quantidade, financeiro):
    """O VNA que o Tesouro usou naquele leilao, recuperado do financeiro dele.

    PU = VNA x cotacao, e a cotacao depende so da taxa e das datas -- entao basta
    dividir o PU efetivo (financeiro / quantidade) pela cotacao. Devolve None quando
    faltam quantidade ou financeiro, e quem chama cai no VNA mensal.
    """
    if not quantidade or pd.isna(quantidade) or pd.isna(financeiro):
        return None
    cotacao = precificacao.pu(cal, titulo, d0, vencimento, taxa, 1.0)
    if not cotacao:
        return None
    pu_efetivo = abs(financeiro) * 1e6 / abs(quantidade)
    return pu_efetivo / cotacao


def _familia(titulo, prazo_anos, vertice_anos=None):
    """A NTN-B se parte em duas faixas pelo vertice; os demais sao eles mesmos.

    A FRONTEIRA E MEDIDA NO VERTICE, e nao no prazo. Um papel que o Tesouro chama de
    "NTN-B 10 anos" fica na faixa de baixo durante toda a vigencia do benchmark,
    mesmo nos meses em que ainda faltam mais de dez anos para vencer -- e o mesmo
    papel, e trocar de faixa no meio da vigencia produziria um degrau no grafico
    que nao aconteceu no mundo.

    Sem vertice -- leilao antigo, sem rotulo e sem prazo -- cai no prazo, que e a
    melhor aproximacao disponivel. Que dos dois criterios valeu fica registrado no
    CSV, que carrega prazo_anos e vertice_anos lado a lado.
    """
    if titulo != "NTN-B":
        return titulo
    medida = vertice_anos if not pd.isna(vertice_anos) else prazo_anos
    if pd.isna(medida):
        return FAMILIA_NTNB_LONGA
    return (FAMILIA_NTNB_CURTA if medida <= CORTE_NTNB_ANOS
            else FAMILIA_NTNB_LONGA)


def gravar(ate_o_estagio="planilha"):
    """Grava dv_emitido_por_leilao.csv em data/processed/.

    Mesmo padrao de dv.gravar_painel: conteudo gerado localmente a partir de
    data/processed/ ja validado, entao df.to_csv direto.
    """
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df = dv_por_leilao(ate_o_estagio)
    saida = config.PROCESSED_DIR / "dv_emitido_por_leilao.csv"
    df.to_csv(saida, index=False, encoding="utf-8")
    print(f"gravado: {saida} ({len(df)} linhas)")
    return saida
