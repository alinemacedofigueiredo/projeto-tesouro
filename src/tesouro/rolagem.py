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

    VIES CONHECIDO, MEDIDO, E AINDA NAO CORRIGIDO (revisao da branch, item 7).
    Fora da cobertura do vna.csv o desvio nao cancela: vna_em devolve o VNA da
    ANCORA -- o ultimo leilao do papel ate 'quando' -- e ninguem carrega dali
    ate a data pedida. Em 17/08/2026 a ancora e 11/08 para LFT e para NTN-B, e
    ficam QUATRO DIAS UTEIS sem apropriar:

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
        projetado[ind] = (base + float(ritmo[ind])
                          * leiloes_que_faltam(dias, ind) - pago + juros)
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
    """
    if indexador == "Taxa Flutuante":
        return curva.selic_implicita(ate, data_base=data_base)
    if indexador == "\u00cdndice Pre\u00e7os":
        return (1 + curva.inflacao_implicita(ate, data_base=data_base)) * 1.06 - 1
    return _CARGA_DO_PREFIXADO


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

    alvo = alvo_total * alvo_pct / 100 * 1000
    return (alvo - partida - juros + vence) / quantos
