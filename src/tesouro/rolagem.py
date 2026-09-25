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

import collections

import pandas as pd

from . import calendario, config, curva, leiloes_dv

# Qual papel serve para recuperar o VNA de cada indice.
_PAPEL_DO_INDICE = {"SELIC": "LFT", "IPCA": "NTN-B"}

# Quantos dias para tras aceitar um leilao como fonte do VNA.
_JANELA_DO_VNA = 15


DATAS_DO_LEILAO = ["data_leilao", "data_liquidacao", "data_vencimento"]


def leiloes(com_provisorio=True):
    """Os leiloes: a planilha do Tesouro, e o provisorio DEPOIS de onde ela acaba.

    Decisao dela, 25/08/2026: "tudo que teve de leilao que ainda nao esta na
    planilha, usa o do leilao, pq ja temos inclusive o resultado -- da planilha
    ate hj usa o leilao."

    A FRONTEIRA E A ULTIMA LIQUIDACAO DA PLANILHA, e nao a data de hoje nem o
    estagio da linha. Antes dela manda a planilha; depois dela, o provisorio da
    API. E o unico corte que nao pode contar o mesmo leilao duas vezes -- e
    contar duas vezes erra para MAIS, que numa tabela de conformidade e o erro
    que faz o Tesouro parecer mais perto do teto do que esta.

    O preco disso: se a planilha estiver COMPLETA ate a fronteira mas faltando
    uma linha anterior a ela, essa linha nao entra. Preferi perder uma linha
    velha a arriscar somar uma nova duas vezes.

    Sem o arquivo provisorio -- num clone novo, antes do primeiro
    'python -m tesouro.leilao_do_dia' -- devolve so a planilha, sem reclamar.
    """
    oficial = pd.read_csv(config.PROCESSED_DIR / "leiloes.csv",
                          parse_dates=DATAS_DO_LEILAO)
    if not com_provisorio:
        return oficial

    caminho = config.PROCESSED_DIR / "leiloes_recentes.csv"
    if not caminho.exists():
        return oficial

    novo = pd.read_csv(caminho, parse_dates=DATAS_DO_LEILAO)
    novo = novo[novo["data_liquidacao"] > oficial["data_liquidacao"].max()]
    if novo.empty:
        return oficial
    return pd.concat([oficial, novo[oficial.columns]], ignore_index=True)


def _carrega_vna(indice, valor, de, ate):
    """Carrega o VNA da ancora ate a data, com a premissa que a projecao ja usa.

    Decisao dela, 25/08/2026: "vc tem o vna do ultimo leilao. projeta tudo a
    partir da data do ultimo leilao, ai vc usa as premissas que ja estava
    usando."

    E melhor do que a alternativa que eu tinha proposto (procurar uma serie de
    Selic diaria): nao acrescenta fonte de dado, usa o mesmo numero que ja
    aparece no rodape da projecao, e sobre poucos dias uteis a diferenca entre a
    Selic implicita e a efetiva e ruido perto do vao que ela fecha.

    A data-base da curva e a DA ANCORA, e nao a de hoje: assim uma chamada
    historica pega a curva que existia entao, em vez de projetar para tras --
    que curva.selic_implicita recusa, e com razao.

    O VNA da NTN-B corre so a INFLACAO. O cupom real nao entra aqui: quem
    apropria o cupom e _apropriacao, pela razao entre os dois VNAs.
    """
    de, ate = pd.Timestamp(de), pd.Timestamp(ate)
    du = calendario.padrao().du(de.date(), ate.date())
    if du <= 0:
        return valor
    taxa = (curva.selic_implicita(ate, data_base=de) if indice == "SELIC"
            else curva.inflacao_implicita(ate, data_base=de))
    return valor * (1 + taxa) ** (du / 252)


def vna_ancorado(indice, quando):
    """O VNA do leilao ancora, E A DATA DELE.

    A ancora e o ultimo leilao do papel ate 'quando' -- quase nunca a propria
    data pedida. Quem quer o VNA NA data usa vna_em, que carrega daqui ate la.

    PU = VNA x cotacao, e a cotacao depende so da taxa e das datas -- entao o PU
    efetivo (financeiro / quantidade) dividido pela cotacao devolve o VNA que o
    Tesouro usou naquele dia.

    LEVANTA quando nao ha leilao na janela. Congelar em silencio subestima o estoque
    da LFT em cerca de 50 bilhoes por mes, e um numero errado sem aviso e pior do que
    numero nenhum.
    """
    quando = pd.Timestamp(quando)
    titulo = _PAPEL_DO_INDICE[indice]
    l = leiloes()
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
    return implicito, r["data_leilao"]


def vna_em(indice, quando):
    """O VNA do indice NA DATA: o do leilao ancora, carregado dali ate aqui.

    O VIES QUE ISTO FECHA, medido em 17/08/2026 antes da correcao: a ancora era
    11/08 para LFT e para NTN-B, e os quatro dias uteis entre uma data e outra
    nao eram apropriados -- R$ 10,6 bi de SELIC mais R$ 1,5 bi de IPCA, R$ 12,1
    bi a menos, e SEMPRE para baixo, nunca para cima.

    Achado na revisao da branch banda-do-paf (item 7). O backtest dos meses
    fechados nao pegava porque todas as datas dele caem dentro da cobertura do
    vna.csv, onde este caminho nem chega a ser chamado.
    """
    valor, ancora = vna_ancorado(indice, quando)
    return _carrega_vna(indice, valor, ancora, quando)


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

# Papeis prefixados: LTN e NTN-F nao tem VNA, e o juro deles TRAVA NA EMISSAO.
_PREFIXADOS = ("LTN", "NTN-F")


def carga_do_prefixado(quando):
    """A taxa a que o estoque prefixado de fato rende, na data.

    O QUE MUDOU EM 27/08/2026, e por que. Ate aqui isto era a constante
    _CARGA_DO_PREFIXADO = 0.135, calibrada contra o residuo da propria rolagem.
    O valor nem era absurdo: batia com a taxa de EMISSAO do prefixado, 13,68% na
    media ponderada de 12 meses. Mas e a taxa errada.

    LTN e NTN-F tem juro travado na emissao. O que o ESTOQUE rende nos proximos
    meses nao e a taxa de mercado de hoje -- e a que ja foi contratada quando
    cada papel saiu, e essa e mais baixa, porque o estoque carrega papel de
    quando o juro era menor. Sao dois numeros publicados e diferentes:

        custo do ESTOQUE    LTN 12,916%   NTN-F 11,814%    (31/07/2026, mensal)
        custo das EMISSOES  LTN 13,628%   NTN-F 13,733%

    O primeiro e o que se aplica ao estoque; o segundo, ao dinheiro novo.

    MENSAL, E NAO ACUM_12M -- decisao dela em 27/08/2026. As duas medidas estao
    no arquivo e a conta fecha entre elas: compor doze 'mensal' reproduz o
    'acum_12m' com diferenca mediana de 0,05 pp. Mas o acum_12m e media movel de
    doze meses e fica ATRASADO quando o juro anda: a carga derivada dele ia de
    11,3% ha um ano para 12,2% hoje, sempre correndo atras do mensal, que no
    mesmo periodo foi de 12,63% para 12,92%.

    Medido no backtest, vies medio do prefixado: mensal -0,058%, acum_12m
    -0,090%. A medida do mes ganha, e ganha pelo motivo certo -- e a grandeza
    que se quer (quanto o estoque rende AGORA), nao uma media que arrasta o ano.

    NOS PAPEIS DE INDICE DE PRECOS A ESCOLHA DELA FOI A OUTRA, e tambem esta
    certa: o custo mensal de uma NTN-B balanca com o IPCA do mes (7,18% num mes
    contra 10,58% no acumulado; a NTN-C chegou a -3,00%), entao ali a media de
    doze meses e que serve. Quando aquela parte for feita, usar acum_12m.

    PARA O PREFIXADO, O NUMERO RETROSPECTIVO E O CORRETO -- e a curva implicita
    e que seria errada. E o oposto da LFT, que rende Selic FUTURA e por isso le
    a curva. A NTN-B fica no meio: inflacao futura, cupom real travado.

    MEDIDO no backtest de 24 meses, vies medio do prefixado:

        13,500% (a constante)         +0,071%   19 dos 24 meses para cima
        por data, mensal              -0,058%    6 dos 24
        por data, acum_12m            -0,090%    2 dos 24
        12,233% fixo                  -0,021%   10 dos 24  <- ILEGITIMO

    O 12,233% fixo mede melhor e NAO pode ser usado: e o custo de julho de 2026
    aplicado a 2024, ou seja, olha o gabarito. O mesmo vicio do 13,5%, que
    tambem foi ajustado contra a saida da propria rolagem. Entre as opcoes
    honestas -- as que so leem o RMD anterior -- o mensal ganha.

    E O GANHO AQUI E DE PROCEDENCIA, E NAO DE PRECISAO: o vies vai de +0,071%
    para -0,058%, quase o mesmo tamanho com o sinal trocado. O que muda e a
    fonte deixar de ser um numero ajustado por nos.

    O CARREGO DA EMISSAO NAO FECHA O RESTO. Medido em 27/08/2026: o residuo do
    prefixado e de -1,535 bi/mes e o carrego que falta e 0,178 bi, ou 12% dele.
    Chegou a ser dito aqui que os dois se encontrariam perto de zero; e falso.

    E SAI DO ARQUIVO A CADA DATA, e nao de uma constante. Era esse o defeito de
    fundo do 0.135: nao o valor, mas ser um numero congelado enquanto o custo do
    estoque anda todo mes -- envelheceria em silencio, sem nada acusar.
    """
    quando = pd.Timestamp(quando)
    custo = pd.read_csv(config.PROCESSED_DIR / "custo_medio.csv",
                        parse_dates=["data"])
    custo = custo[(custo["medida"] == "mensal")
                  & (custo["nivel"] == "DPMFi")
                  & (custo["titulo"].isin(_PREFIXADOS))
                  & (custo["data"] <= quando)
                  & custo["custo_aa_pct"].notna()]
    if custo.empty:
        raise LookupError(
            f"nao ha custo do estoque prefixado ate {quando:%d/%m/%Y} em "
            f"custo_medio.csv. Congelar uma carga aqui produziria juros "
            f"plausiveis e errados; a rolagem para.")
    quando_custo = custo["data"].max()
    custo = custo[custo["data"] == quando_custo].set_index("titulo")["custo_aa_pct"]

    estoque = pd.read_csv(config.PROCESSED_DIR / "estoque_titulos_vencimento.csv",
                          parse_dates=["data"])
    estoque = estoque[(estoque["data"] <= quando)
                      & (estoque["titulo"].isin(_PREFIXADOS))]
    if estoque.empty:
        raise LookupError(
            f"nao ha estoque prefixado ate {quando:%d/%m/%Y} para ponderar a "
            f"carga entre LTN e NTN-F.")
    estoque = estoque[estoque["data"] == estoque["data"].max()]
    peso = estoque.groupby("titulo")["financeiro_milhoes"].sum()

    num = den = 0.0
    for titulo in _PREFIXADOS:
        if titulo not in custo.index or titulo not in peso.index:
            continue
        p = float(peso[titulo])
        num += p * float(custo[titulo]) / 100
        den += p
    if den <= 0:
        raise LookupError(
            f"estoque prefixado zerado em {quando:%d/%m/%Y}; sem peso nao ha "
            f"como ponderar a carga.")
    return num / den

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
    l = leiloes()
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

    VIES QUE JA FOI FECHADO -- o texto abaixo descrevia um defeito ABERTO e
    ficou para tras; corrigido em 27/08/2026. vna_em hoje CARREGA da ancora ate
    a data pedida (ver o corpo dele), por decisao dela de 25/08: "projeta tudo a
    partir da data do ultimo leilao, ai vc usa as premissas que ja estava
    usando". Com isso o vao caiu de quatro dias uteis para UM, e o carrego e
    aplicado: medido em 26/08/2026, +0,051% na Selic e +0,020% no IPCA.

    O que se media antes de fechar, e que fica de registro do tamanho:

        SELIC  0,221% sobre R$ 4.800,7 bi  ->  R$ 10,6 bi a menos
        IPCA   0,073% sobre R$ 2.111,0 bi  ->  R$  1,5 bi a menos
                                               R$ 12,1 bi, SEMPRE para baixo

    Nos percentuais isso vale ate 0,05 pp (Taxa Flutuante sai 52,81% e seria
    52,86%), o que nao inverte nenhum veredito de banda com o dado de hoje --
    mas e um vies de sentido unico, e cresce com a distancia ate a ancora.

    Corrigir exige decidir COM QUE SERIE carregar da ancora ate a data (a Selic
    diaria efetiva, e nao a implicita da curva, que e premissa e nao medida), e
    essa decisao e da dona do projeto.

    O backtest dos meses fechados NAO cobre isto: todas as datas dele sao fins de
    mes de RMD, ou seja, dentro da cobertura do vna.csv, onde este caminho nem e
    chamado.
    """
    quando = pd.Timestamp(quando)
    v = pd.read_csv(config.PROCESSED_DIR / "vna.csv", parse_dates=["data"])
    s = v[v["indice"] == indice]
    if quando <= s["data"].max():
        conhecido = s[s["data"] <= quando].sort_values("data")
        return float(conhecido.iloc[-1]["vna"])
    return vna_em(indice, quando)


# Papeis do bloco de Indice de Precos. A NTN-C entra: a taxa dela sai dos leiloes
# que a emitiram, entao e o juro real DELA -- nao depende de termos serie de
# IGP-M, que o projeto nao tem.
_INDEXADOS_A_PRECOS = ("NTN-B", "NTN-B1", "NTN-C")


def taxa_real_do_estoque(quando):
    """O juro real a que o estoque indexado a precos rende, na data.

    ELA CORRIGIU ISTO EM 27/08/2026, e a correcao desfaz um engano meu. Eu tinha
    proposto usar os 6% de CUPOM_ANUAL como taxa de apropriacao. Nas palavras
    dela: "o 6% fala sobre os cupons que serao pagos (1+6%)^(0,5)*VNA. Mas o
    papel e emitido em uma taxa negociada, entao cada papel vai pagar um juro
    real .. nao faz sentido manter 6%".

    Os 6% sao a REGRA DO CUPOM PAGO, e nao a taxa a que o estoque rende. Quem
    manda no rendimento e a taxa com que cada papel saiu do leilao.

    DE ONDE SAI. O anexo do RMD nao publica taxa de estoque -- so custo (abas
    4.1, 4.2 e 4.3). Mas cada leilao traz taxa_media_pct e cada papel vivo traz
    vencimento, entao da para casar os dois e ponderar pelo estoque. Medido em
    31/07/2026: 5,948% para a NTN-B, com 100% do estoque casado a leilao.

    ATE 'quando', NUNCA DEPOIS -- a regra dela sobre nao ler o mes que se tenta
    reproduzir. Um leilao posterior a data de partida nao existia quando a
    rolagem parte dali.

    O QUE ISTO CONSERTA. A rolagem historica subtraia o cupom da NTN-B (via
    fluxos.pagos, R$ 10,0 bi/mes) e NUNCA o apropriava: tirava sem nunca ter
    posto. Dai o estoque de Indice de Precos sair menor em 24 dos 24 meses do
    backtest, -0,568% ao mes sobre um bloco de 2,1 trilhoes.

    O QUE ISTO NAO CONSERTA, e esta escrito para ninguem procurar de novo: o
    ajuste do backtest melhora monotonicamente ate ~7% ao ano, e nem o cupom
    contratual (6,00%) nem a taxa negociada (5,948%) chegam la. Sobra da ordem
    de 0,07% ao mes sem explicacao. NAO se fecha isso subindo a taxa: seria um
    numero que nenhuma fonte sustenta, e enterraria a causa de vez.
    """
    quando = pd.Timestamp(quando)

    e = pd.read_csv(config.PROCESSED_DIR / "estoque_titulos_vencimento.csv",
                    parse_dates=["data", "vencimento"])
    e = e[(e["data"] <= quando) & (e["titulo"].isin(_INDEXADOS_A_PRECOS))]
    if e.empty:
        raise LookupError(
            f"nao ha estoque indexado a precos ate {quando:%d/%m/%Y} para "
            f"apurar a taxa real.")
    e = e[(e["data"] == e["data"].max()) & (e["financeiro_milhoes"] > 0)]

    l = leiloes()
    l = l[(l["titulo"].isin(_INDEXADOS_A_PRECOS)) & (l["tipo_leilao"] == "Venda")
          & l["taxa_media_pct"].notna() & (l["financeiro_milhoes"] > 0)
          & (l["data_leilao"] <= quando)]

    num = den = 0.0
    for r in e.itertuples(index=False):
        seus = l[(l["titulo"] == r.titulo)
                 & (l["data_vencimento"] == r.vencimento)]
        peso = seus["financeiro_milhoes"]
        if seus.empty or float(peso.sum()) <= 0:
            continue
        taxa = float((seus["taxa_media_pct"] * peso).sum() / peso.sum()) / 100
        num += float(r.financeiro_milhoes) * taxa
        den += float(r.financeiro_milhoes)

    if den <= 0:
        raise LookupError(
            f"nenhum papel indexado a precos vivo em {quando:%d/%m/%Y} pode ser "
            f"casado com o leilao que o emitiu; sem isso nao ha taxa real.")
    return num / den


def _apropriacao(indexador, base, de, ate):
    """Juros apropriados sobre o estoque no periodo."""
    if indexador == "Prefixado":
        cal = calendario.padrao()
        du = cal.du(pd.Timestamp(de).date(), pd.Timestamp(ate).date())
        return base * ((1 + carga_do_prefixado(de)) ** (du / 252) - 1)
    indice = _INDICE_DO_INDEXADOR[indexador]
    fator = (_vna_para_apropriacao(indice, ate)
             / _vna_para_apropriacao(indice, de))
    if indexador == "\u00cdndice Pre\u00e7os":
        # O VNA corrige o principal pela inflacao; o JURO REAL vem por cima, e
        # ate 27/08/2026 nao vinha de lugar nenhum -- a rolagem subtraia o cupom
        # pago e nunca o apropriava. Ver taxa_real_do_estoque.
        cal = calendario.padrao()
        du = cal.du(pd.Timestamp(de).date(), pd.Timestamp(ate).date())
        fator *= (1 + taxa_real_do_estoque(de)) ** (du / 252)
    return base * (fator - 1)


# Como cada papel carrega o dinheiro que levantou, entre a liquidacao e a data.
# NAO E A MESMA REGRA PARA OS QUATRO, e a diferenca nao e detalhe:
#
#   LTN, NTN-F   taxa_media_pct e a taxa NOMINAL, travada na emissao.
#   NTN-B        taxa_media_pct e a taxa REAL; a inflacao vem por cima.
#   LFT          taxa_media_pct e o AGIO sobre a Selic -- 0,11% nos ultimos dez
#                leiloes. Carregar uma LFT a 0,11% ao ano seria catastrofico:
#                ela rende Selic mais aquilo.
_REGRA_DE_CARREGO = {"LTN": "nominal", "NTN-F": "nominal",
                     "NTN-B": "real", "NTN-B1": "real", "NTN-C": "real",
                     "LFT": "agio"}


def _fator_de_carrego(titulo, taxa_pct, de, ate, vna=None):
    """Quanto o financeiro emitido em 'de' vale em 'ate', pela regra do papel.

    A inflacao e a Selic saem do VNA REALIZADO -- e esta funcao so serve para
    emissao que JA aconteceu. Para leilao futuro nao ha VNA, e quem carrega e a
    projecao, com as implicitas.
    """
    de, ate = pd.Timestamp(de), pd.Timestamp(ate)
    # A GUARDA E PELAS DATAS, e nao pelo du: calendario.padrao().du devolve
    # positivo mesmo com as datas invertidas, entao 'du <= 0' nunca pegava o
    # caso de liquidacao POSTERIOR a data pedida -- e ela seria carregada para
    # a frente, aumentando o estoque com dinheiro que ainda nao entrou.
    # leiloes_liquidados_carregados ja filtra por data, entao isto e defesa;
    # achado ao reforcar o teste, e nao em producao.
    if ate <= de:
        return 1.0
    du = calendario.padrao().du(de.date(), ate.date())
    if du <= 0:
        return 1.0
    regra = _REGRA_DE_CARREGO.get(titulo)
    if regra is None:
        return 1.0
    taxa = float(taxa_pct) / 100 if pd.notna(taxa_pct) else 0.0
    if regra == "nominal":
        return (1 + taxa) ** (du / 252)
    indice = "IPCA" if regra == "real" else "SELIC"
    # 'vna' existe por DESEMPENHO, e a razao esta medida: _vna_para_apropriacao
    # le o vna.csv do disco a CADA chamada, e esta funcao roda uma vez por
    # leilao da janela -- centenas de leituras por rolagem. Sem o memo, gravar
    # paf.html subiu de 24 s para 57 s. Quem chama em lote passa um resolvedor
    # que le uma vez so; o padrao continua sendo o caminho direto.
    ler = vna if vna is not None else _vna_para_apropriacao
    correcao = ler(indice, ate) / ler(indice, de)
    return correcao * (1 + taxa) ** (du / 252)


def leiloes_liquidados_carregados(de, ate):
    """Financeiro dos leiloes liquidados em (de, ate], CARREGADO ate 'ate'.

    O QUE ISTO CONSERTA. leiloes_liquidados soma o financeiro e pronto: o
    dinheiro que entrou em agosto e tratado como se tivesse chegado no ultimo
    dia da janela, sem render nada no caminho. O vies e de mao unica -- sempre
    para baixo -- e medido em 27/08/2026 valia 0,178 bi/mes no prefixado, 0,088
    no indice de precos e 0,334 na taxa flutuante.

    E DESENHO DELA, passo 3 de quatro: "adiciona emissoes ajustando o preco ate
    hj (pela taxa de cada emissao)". Aqui nao ha estimativa nenhuma -- cada
    leilao traz a sua taxa e a sua data.
    """
    l = leiloes()
    l = l[(l["data_liquidacao"] > pd.Timestamp(de))
          & (l["data_liquidacao"] <= pd.Timestamp(ate))].copy()
    l["indexador"] = [_INDEXADOR_DO_TITULO.get(t) for t in l["titulo"]]
    l["sinal"] = [_SINAL.get(t, 0) for t in l["tipo_leilao"]]
    l = l[l["indexador"].notna()]

    memo = {}

    def _vna(indice, quando):
        chave = (indice, pd.Timestamp(quando))
        if chave not in memo:
            memo[chave] = _vna_para_apropriacao(indice, quando)
        return memo[chave]

    valores = []
    for r in l.itertuples(index=False):
        fator = _fator_de_carrego(r.titulo, r.taxa_media_pct,
                                  r.data_liquidacao, ate, vna=_vna)
        valores.append(float(r.financeiro_milhoes) * r.sinal * fator)
    l = l.assign(carregado=valores)
    fluxo = l.groupby("indexador")["carregado"].sum()
    return fluxo.reindex(list(INDEXADORES)).fillna(0.0)


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
    # CARREGADO, e nao so somado: o dinheiro que entrou no meio da janela
    # rende ate o fim dela. Ver leiloes_liquidados_carregados.
    emitido = leiloes_liquidados_carregados(de, quando)
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


# Quantos dias de leilao entram na media do pace.
#
# VINTE, escolha dela: sao cerca de dez semanas e dez leiloes de cada papel. O
# backtest de dez anos NAO DISTINGUE as janelas -- 10, 20 e 60 dias de leilao e 26
# semanas caem todos na mesma faixa de erro (1,26 a 1,71 pp no prefixado) -- entao a
# escolha e por ser a unidade em que se pensa, e por lidar sozinha com semana de
# feriado e com dezembro, que tem menos leilao.
LEILOES_DO_PACE = 10

# EM QUE DIA DA SEMANA CADA PAPEL VAI A LEILAO. Regra do Tesouro, descrita pela dona
# do projeto e medida nos ultimos dois anos:
#
#     prefixado (LTN e NTN-F)   quinta-feira   91% dos 104 leiloes
#     NTN-B                     terca-feira    95% dos 101
#     LFT                       terca-feira    99% dos  98
#
# Feriado que antecipa o leilao em um dia util nao muda nada aqui: o que se conta e
# quantos leiloes DAQUELE PAPEL faltam, e nao em que dia da semana caem.
DIA_DO_PAPEL = {"Prefixado": 3, "\u00cdndice Pre\u00e7os": 1, "Taxa Flutuante": 1}


def dia_do_titulo(titulo):
    """O dia da semana em que AQUELE PAPEL vai a leilao, ou None se nao souber.

    Compoe os dois mapas acima -- titulo -> indexador -> dia. O calendario
    precisa disso para saber de QUE PAPEL e cada dia publicado: sem essa
    traducao, um papel publicado ate dezembro apaga o estimado dos outros.

    Papel desconhecido devolve None em vez de um dia qualquer. Quem chama
    decide o que fazer com a ausencia; inventar um dia aqui seria plausivel e
    errado.
    """
    return DIA_DO_PAPEL.get(_INDEXADOR_DO_TITULO.get(titulo))


def pace(quando):
    """Financeiro liquido medio por LEILAO DAQUELE PAPEL, por indexador.

    OS ZEROS NAO ENTRAM NA MEDIA. Um dia de terca em que o prefixado nao foi a leilao
    nao e um leilao de prefixado de valor zero: e um dia em que ele nao foi ofertado.
    Contar o zero fazia a media depender da mistura de tercas e quintas da janela --
    batia por sorte (10 e 10, contra 18 e 18 no futuro), e uma janela com 15 tercas e
    5 quintas subestimaria o prefixado em quase metade, sem nada acusar.

    Medido em 17/08/2026: prefixado 12,32 bi por leilao, indice de precos 1,09, taxa
    flutuante 21,91.
    """
    l = leiloes()
    l = l[l["data_liquidacao"] <= pd.Timestamp(quando)].copy()
    l["indexador"] = [_INDEXADOR_DO_TITULO.get(t) for t in l["titulo"]]
    l["sinal"] = [_SINAL.get(t, 0) for t in l["tipo_leilao"]]
    l = l[l["indexador"].notna()]
    l["fluxo"] = l["financeiro_milhoes"] * l["sinal"]

    por_leilao = l.pivot_table(index="data_leilao", columns="indexador",
                               values="fluxo", aggfunc="sum")
    saida = {}
    for ind in INDEXADORES:
        if ind not in por_leilao.columns:
            raise LookupError(f"nenhum leilao de {ind} ate {quando:%d/%m/%Y}.")
        dele = por_leilao[ind].dropna()
        dele = dele[dele != 0].tail(LEILOES_DO_PACE)
        if len(dele) < LEILOES_DO_PACE:
            raise LookupError(
                f"so ha {len(dele)} leiloes de {ind} ate {quando:%d/%m/%Y}, e o "
                f"pace pede {LEILOES_DO_PACE}.")
        saida[ind] = dele.mean()
    return pd.Series(saida)


def leiloes_que_faltam(dias, indexador):
    """Quantos dos dias de leilao levam AQUELE papel.

    O prefixado vai a leilao na quinta e os indexados na terca -- regra do Tesouro,
    medida em 91% a 99% dos ultimos dois anos. Feriado que antecipa o leilao em um
    dia util nao muda a conta: o que importa e quantos leiloes daquele papel faltam.
    """
    alvo = DIA_DO_PAPEL[indexador]
    return sum(1 for d in dias if pd.Timestamp(d).dayofweek == alvo)


def dias_do_papel(dias, indexador):
    """Os dias de leilao que levam AQUELE papel -- as datas, e nao a contagem.

    leiloes_que_faltam devolve quantos; o passo 4 precisa de QUANDO, porque
    cada leilao carrega da sua propria data ate o fim da janela.
    """
    alvo = DIA_DO_PAPEL[indexador]
    return [pd.Timestamp(d) for d in dias if pd.Timestamp(d).dayofweek == alvo]


def taxa_de_emissao_recente(indexador, quando):
    """A taxa dos MESMOS leiloes que definem o pace.

    DECISAO DELA, 27/08/2026, e o motivo e coerencia de amostra. O pace afirma
    "o Tesouro vai continuar emitindo 14,43 bi por leilao de prefixado" a partir
    dos ultimos LEILOES_DO_PACE leiloes. A companhia natural e "a taxa a que ele
    vem emitindo", tirada dos MESMOS leiloes, com os MESMOS pesos.

    Tirar o volume dos leiloes e a taxa da curva implicita juntaria duas fontes
    que podem discordar -- e elas discordam: em 26/08/2026 a LTN saia a 14,08%
    e a Selic implicita ate 31/12 era 13,69%. Quase 0,4 pp que entrariam no
    numero sem aparecer.

    O QUE ELA DEVOLVE MUDA DE SIGNIFICADO POR INDEXADOR, e quem usa tem de
    saber: nominal no prefixado, REAL no indice de precos, AGIO sobre a Selic
    na taxa flutuante. Ver _REGRA_DE_CARREGO.
    """
    quando = pd.Timestamp(quando)
    papeis = [t for t, i in _INDEXADOR_DO_TITULO.items() if i == indexador]
    l = leiloes()
    l = l[(l["titulo"].isin(papeis)) & (l["tipo_leilao"] == "Venda")
          & l["taxa_media_pct"].notna() & (l["financeiro_milhoes"] > 0)
          & (l["data_leilao"] <= quando)]
    if l.empty:
        raise LookupError(
            f"nenhum leilao de {indexador!r} ate {quando:%d/%m/%Y} para apurar "
            f"a taxa de emissao recente.")
    dias = sorted(l["data_leilao"].unique())[-LEILOES_DO_PACE:]
    l = l[l["data_leilao"].isin(dias)]
    peso = l["financeiro_milhoes"]
    return float((l["taxa_media_pct"] * peso).sum() / peso.sum()) / 100


def fatores_da_emissao_futura(indexador, dias, ate, taxa, selic, inflacao):
    """Soma dos fatores de carrego de um leilao em cada dia que ainda vem.

    Uma emissao de X por leilao vale X * soma(fatores) na data final -- e nao
    X * quantidade de leiloes, que e como era ate 27/08/2026. O dinheiro que
    entra em setembro rende ate 31/12.

    As premissas de inflacao e Selic sao as IMPLICITAS que a projecao ja usa,
    porque para leilao futuro nao ha VNA realizado. A taxa do papel vem dos
    leiloes recentes (taxa_de_emissao_recente) e se compoe com elas, seguindo a
    regra de cada papel.
    """
    cal = calendario.padrao()
    ate = pd.Timestamp(ate)
    total = 0.0
    for dia in dias_do_papel(dias, indexador):
        if dia >= ate:
            total += 1.0
            continue
        du = cal.du(dia.date(), ate.date())
        if du <= 0:
            total += 1.0
            continue
        if indexador == "Prefixado":
            fator = (1 + taxa) ** (du / 252)
        elif indexador == "\u00cdndice Pre\u00e7os":
            fator = ((1 + inflacao) * (1 + taxa)) ** (du / 252)
        else:
            fator = ((1 + selic) * (1 + taxa)) ** (du / 252)
        total += fator
    return total


def projecao(ate, de_snapshot=None, registros=None, hoje=None):
    """O estoque projetado para 'ate', com a premissa que usou ao lado.

    A PREMISSA VIAJA JUNTO de proposito: um numero projetado sem a Selic e a
    inflacao que ele usou ao lado e opiniao com cara de medida, e quem le a pagina
    nao tem como saber se a projecao mudaria com outra premissa.

    O ESTOQUE SAI COMO NUMERO, e nao como faixa. Uma faixa construida sobre um
    cenario alternativo de Selic foi cogitada e descartada: medida contra um
    cenario plausivel (Selic 2pp mais baixa), a premissa de Selic move o estoque
    em ~8 bi contra uma banda de ~600 -- 1,4%, ruido. O que de fato domina o erro
    da projecao e o pace, que erra da ordem de 150 bi; uma faixa construida sobre a
    Selic passaria a impressao de uma precisao que a projecao nao tem.
    """
    from . import calendario_leiloes, curva, fluxos

    ate = pd.Timestamp(ate)

    # A PROJECAO COMECA DE HOJE, e nao da data-base do RMD. Comecando do RMD, o
    # pace seria aplicado tambem aos dias de leilao que JA ACONTECERAM entre a
    # data-base e hoje -- trocando seis semanas de leilao medido por estimativa. E
    # os dois blocos da mesma pagina partiriam de lugares diferentes.
    #
    # 'hoje' existe para o BACKTEST, em que quem chama quer comecar numa data de
    # RMD de proposito, para comparar com o dezembro que de fato aconteceu.
    # DOIS JEITOS DE DIZER DE ONDE PARTIR, e eles nao sao o mesmo:
    #
    #   de_snapshot   parta do snapshot do RMD nesta data. E o do BACKTEST: quem
    #                 chama quer uma data de fim de mes de RMD de proposito, para
    #                 comparar com o dezembro que de fato aconteceu.
    #   hoje          role o estoque ate esta data e parta dai. E o que a pagina
    #                 usa, e o que 'hoje' quer dizer em dados_hoje e em
    #                 estoque_em.
    #
    # ATE 25/08/2026 OS DOIS SE CHAMAVAM 'hoje', e o daqui era o do snapshot.
    # Ao ligar o 'hoje' da pagina neste parametro, painel_paf.grava(hoje=X)
    # passou a levantar LookupError para qualquer X que nao fosse fim de mes de
    # RMD -- e o unico X que os testes passavam era None. Nome enganoso mais
    # caminho nunca exercitado.
    if de_snapshot is not None:
        partida = pd.Timestamp(de_snapshot)
        c = pd.read_csv(config.PROCESSED_DIR / "composicao_dpf.csv",
                        parse_dates=["data"])
        piv = c.pivot_table(index="data", columns="indexador",
                            values="valor_milhoes", aggfunc="sum").fillna(0.0)
        if partida not in piv.index:
            # 'de_snapshot' e para o BACKTEST: quem chama passa uma data de RMD de
            # proposito. piv.loc[partida] sem guarda levantava um KeyError cru
            # do pandas -- nao diz qual data faltou nem quais existem por
            # perto, e quem chama fica sem saber se digitou a data errada ou
            # se e o arquivo que nao tem aquele mes.
            vizinhas = sorted(piv.index)
            antes = [d for d in vizinhas if d <= partida][-3:]
            depois = [d for d in vizinhas if d > partida][:3]
            texto = ", ".join(d.strftime("%d/%m/%Y") for d in antes + depois)
            raise LookupError(
                f"nao ha composicao_dpf.csv na data {partida:%d/%m/%Y}. Datas "
                f"por perto: {texto}.")
        inicial = piv.loc[partida]
    else:
        partida = (pd.Timestamp(hoje) if hoje is not None
                   else leiloes()["data_liquidacao"].max())
        inicial = estoque_em(partida)

    dias, fronteira = calendario_leiloes.dias_ate(ate, registros=registros,
                                                  hoje=partida)
    quantos = len(dias)
    ritmo = pace(partida)
    pagou = fluxos.pagos(partida, ate)
    selic = curva.selic_implicita(ate, data_base=partida)
    inflacao = curva.inflacao_implicita(ate, data_base=partida)
    cal = calendario.padrao()
    du = cal.du(partida.date(), ate.date())

    projetado = {}
    for ind in INDEXADORES:
        base = float(inicial[ind])
        do_ind = pagou[pagou["indexador"] == ind]
        pago = do_ind["principal_milhoes"].sum() + do_ind["cupom_milhoes"].sum()
        # A premissa de juros vem de _taxa_do_indexador, e nao de um if/elif/else
        # duplicado aqui. Ate 25/08/2026 as duas copias existiam separadas, e a
        # afirmacao de que "nao ha premissa nova" na entrega 5 era verdadeira so
        # por coincidencia de copia -- mudar a premissa aqui e esquecer a outra
        # quebraria a identidade de emissao_necessaria em silencio (achado da
        # revisao da entrega 5).
        taxa = _taxa_do_indexador(ind, ate, data_base=partida)
        juros = base * ((1 + taxa) ** (du / 252) - 1)
        # CADA LEILAO CARREGA DA SUA DATA, e nao chega todo no ultimo dia --
        # passo 4 do desenho dela. Ver fatores_da_emissao_futura.
        fatores = fatores_da_emissao_futura(
            ind, dias, ate, taxa_de_emissao_recente(ind, partida),
            selic, inflacao)
        projetado[ind] = base + float(ritmo[ind]) * fatores - pago + juros
    for ind in PARADOS:
        projetado[ind] = float(inicial[ind])

    total = sum(projetado.values())

    return {"estoque": pd.Series(projetado),
            "percentual": pd.Series({k: 100 * v / total
                                     for k, v in projetado.items()}),
            "selic": selic,
            "inflacao": inflacao,
            # DE QUANDO E A CURVA. Ela termina no ultimo RMD e a projecao parte da
            # ultima liquidacao: sao semanas de diferenca, e apresentar premissa de
            # sete semanas atras como "de hoje" e o tipo de coisa que esta pagina
            # existe para nao fazer.
            "data_da_curva": curva.data_da_curva(partida),
            "dias_de_leilao": quantos,
            "fronteira_do_calendario": fronteira,
            "de": partida, "ate": ate}


# A chave do indicador (como banda.INDICADORES a escreve) para o nome do
# indexador (como INDEXADORES o escreve). Os dois vocabularios ja existiam
# separados; este mapa e o unico lugar que os liga.
#
# OS VALORES FICAM ACENTUADOS. Eles sao DADO -- casam com a coluna do
# composicao_dpf.csv. Desacentuar aqui faria o filtro nao casar e o termo ir a
# zero em silencio (ruling 4 da entrega 4).
INDEXADOR_DA_CHAVE = {
    "prefixado_pct": "Prefixado",
    "indice_precos_pct": "\u00cdndice Pre\u00e7os",
    "taxa_flutuante_pct": "Taxa Flutuante",
}


def _taxa_do_indexador(indexador, ate, data_base=None):
    """A premissa de juros de cada indexador, a MESMA que projecao usa.

    Nao ha premissa nova nesta entrega: se a projecao estiver certa, esta conta
    esta; se estiver errada, as duas erram juntas. E isso que o teste de
    identidade trava.

    A UNICA TESTEMUNHA desta premissa (Selic e inflacao implicitas, e a carga
    do prefixado) e' test_a_projecao_devolve_a_PREMISSA_que_usou, em
    test_rolagem.py -- ele recalcula o estoque projetado por fora, com as
    mesmas pecas publicas que projecao() usa por dentro, sem ler o resultado
    de _taxa_do_indexador direto do dict devolvido. Quem "simplificar" aquele
    teste comparando p['selic']/p['inflacao'] contra uma chamada direta a
    _taxa_do_indexador (ou a curva.selic_implicita/curva.inflacao_implicita)
    o torna tautologico -- a mesma conta contra ela mesma -- e remove a unica
    cobertura real da premissa, com a suite inteira continuando verde.
    """
    if indexador == "Taxa Flutuante":
        return curva.selic_implicita(ate, data_base=data_base)
    if indexador == "\u00cdndice Pre\u00e7os":
        return (1 + curva.inflacao_implicita(ate, data_base=data_base)) * 1.06 - 1
    # A carga do prefixado e a da DATA DE PARTIDA, e nao a de 'ate': o backtest
    # parte de datas antigas de proposito, e usar a carga de hoje para projetar
    # de 2024 seria olhar o futuro -- que curva.selic_implicita ja recusa.
    return carga_do_prefixado(data_base if data_base is not None else ate)


# Os termos de emissao_necessaria QUE NAO DEPENDEM DO ALVO -- so de indexador,
# hoje, ate e registros. 'quantos' ja vem sem cheirar problema: ver a guarda em
# termos_da_simulacao, que levanta antes de devolver um valor que dividiria por
# zero.
#
# 'hoje' e 'ate' NAO ENTRAM AQUI. emissao_a_partir_dos_termos so le partida,
# juros, vence e quantos -- quem chama termos_da_simulacao ja tem os proprios
# 'hoje'/'ate' normalizados (dados_simulacao guarda os dela nos attrs da
# matriz). Achado da revisao: a versao anterior carregava os dois campos e o
# docstring justificava por uma necessidade que o codigo nunca teve.
TermosDaSimulacao = collections.namedtuple(
    "TermosDaSimulacao",
    ["partida", "juros", "vence", "quantos", "fatores"])


def termos_da_simulacao(indexador, hoje=None, ate=None, registros=None):
    """Os termos de emissao_necessaria que NAO MUDAM com o alvo.

    Uma tabela da simulacao tem ~42 celulas, e cada uma pedia a
    emissao_necessaria inteira: estoque_em (que le quatro CSVs por baixo),
    fluxos.pagos e a contagem de leiloes refeitos do zero 42 vezes, quando so
    o alvo varia de celula para celula. Medido: gerar paf.html caiu de 338 s
    para cerca de 24 s calculando estes termos uma vez por tabela.
    """
    from . import calendario_leiloes, fluxos

    hoje = pd.Timestamp(hoje) if hoje is not None \
        else leiloes()["data_liquidacao"].max()
    ate = pd.Timestamp(ate) if ate is not None \
        else pd.Timestamp(f"{hoje.year}-12-31")

    partida = float(estoque_em(hoje)[indexador])
    dias, _ = calendario_leiloes.dias_ate(ate, registros=registros, hoje=hoje)
    quantos = leiloes_que_faltam(dias, indexador)
    if quantos <= 0:
        raise LookupError(
            f"nao ha leilao de {indexador!r} entre {hoje:%d/%m/%Y} e "
            f"{ate:%d/%m/%Y}; nao ha como dividir a emissao por leilao.")

    pagou = fluxos.pagos(hoje, ate)
    do_ind = pagou[pagou["indexador"] == indexador]
    vence = float(do_ind["principal_milhoes"].sum()
                  + do_ind["cupom_milhoes"].sum())

    cal = calendario.padrao()
    du = cal.du(hoje.date(), ate.date())
    taxa = _taxa_do_indexador(indexador, ate, data_base=hoje)
    juros = partida * ((1 + taxa) ** (du / 252) - 1)

    # A MESMA SOMA DE FATORES QUE A PROJECAO USA. A simulacao e a projecao lida
    # ao contrario; se uma carrega cada leilao da sua data e a outra divide pela
    # contagem, as duas param de bater -- e o teste de identidade que sustenta a
    # entrega 5 quebra. As premissas saem daqui, nao de uma copia.
    from . import curva as _curva
    fatores = fatores_da_emissao_futura(
        indexador, dias, ate, taxa_de_emissao_recente(indexador, hoje),
        _curva.selic_implicita(ate, data_base=hoje),
        _curva.inflacao_implicita(ate, data_base=hoje))

    return TermosDaSimulacao(partida=partida, juros=juros, vence=vence,
                             quantos=quantos, fatores=fatores)


def emissao_a_partir_dos_termos(termos, alvo_pct, alvo_total):
    """A aritmetica de UMA celula, dados os termos que a tabela inteira reusa.

    A UNICA formula de emissao_necessaria: ela tambem chama esta funcao, e nao
    duplica a conta. Este projeto ja teve um defeito exatamente desse formato
    -- a premissa de juros copiada entre projecao e emissao_necessaria -- que
    so fechou unificando numa fonte so (_taxa_do_indexador). Duplicar aqui a
    conta de 'alvo' e a divisao final repetiria o mesmo risco: uma mudanca de
    formula feita num lugar e esquecida no outro.
    """
    alvo = alvo_total * alvo_pct / 100 * 1000
    # DIVIDE PELA SOMA DOS FATORES, e nao pela contagem: se cada leilao
    # carrega da sua data (passo 4), emitir X por leilao vale
    # X * soma(fatores) no fim -- e a inversa tem de dividir pelo mesmo.
    return (alvo - termos.partida - termos.juros + termos.vence) / termos.fatores


def emissao_necessaria(indexador, alvo_pct, alvo_total, hoje=None, ate=None,
                       registros=None):
    """Quanto emitir POR LEILAO daquele papel para o alvo sair em 'ate'.

    'alvo_pct' em pontos percentuais (22 e 22%), 'alvo_total' em R$ BILHOES, e o
    retorno em R$ MILHOES por leilao -- a mesma unidade de pace(), para os dois
    poderem ser comparados sem conversao no meio do caminho.

    A conta:

        alvo       = alvo_total x alvo_pct
        emissao    = alvo - estoque_hoje - juros + vencimentos_e_cupons
        por_leilao = emissao / leiloes_que_faltam

    PODE SER NEGATIVA, e negativa e resposta: o estoque cresce sozinho pelos
    juros, e quando o alvo esta abaixo de onde ele vai parar, nem parando de
    emitir se chega la. O numero diz o tamanho do resgate que faltaria.

    Chama termos_da_simulacao e emissao_a_partir_dos_termos por dentro -- quem
    precisa da tabela inteira (dados_simulacao) chama os dois separados, uma
    vez so, em vez de pagar de novo os termos que nao mudam por celula.
    """
    termos = termos_da_simulacao(indexador, hoje=hoje, ate=ate,
                                 registros=registros)
    return emissao_a_partir_dos_termos(termos, alvo_pct, alvo_total)
