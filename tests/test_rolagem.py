"""A rolagem do estoque do RMD ate hoje, e a projecao ate o fim do ano."""
import pandas as pd
import pytest

from tesouro import config, rolagem


def banda_ultima_liquidacao():
    from tesouro.graficos import banda
    return banda._ultima_liquidacao()


def test_o_VNA_recuperado_do_leilao_bate_com_o_conhecido():
    # ESTE E O TESTE QUE DISPENSA A BLOOMBERG. O vna.csv termina exatamente na
    # data-base do RMD, e os leiloes vao alem dela. Sem VNA nesses dias nao ha termo
    # de juros, e a LFT sai ~2% subestimada.
    #
    # PU = VNA x cotacao, e a cotacao depende so da taxa e das datas: o PU efetivo
    # dividido pela cotacao devolve o VNA que o Tesouro usou. Medido nos 98 leiloes
    # que caem em data de VNA conhecida, o erro mediano e 0,045%.
    from tesouro import config

    v = pd.read_csv(config.PROCESSED_DIR / "vna.csv", parse_dates=["data"])
    for indice in ("SELIC", "IPCA"):
        s = v[v["indice"] == indice].set_index("data")["vna"]
        quando = s.index[-1]
        recuperado = rolagem.vna_em(indice, quando)
        real = float(s.loc[quando])
        assert abs(recuperado - real) / real < 0.002, (indice, recuperado, real)


def test_sem_leilao_para_recuperar_o_VNA_ele_LEVANTA():
    # Congelar em silencio subestima o estoque da LFT em ~50 bi por mes. Se nao ha
    # como saber, o certo e parar.
    with pytest.raises(LookupError, match="VNA"):
        rolagem.vna_em("SELIC", pd.Timestamp("1990-01-01"))


def test_a_rolagem_reproduz_os_meses_FECHADOS_do_RMD():
    # O TESTE QUE SUSTENTA TUDO O MAIS. Se a rolagem nao reproduz um mes que ja
    # aconteceu, o numero de "hoje" que ela produz nao vale nada.
    #
    # Os limites vieram da medicao em 24 meses, em % do estoque do indexador:
    # taxa flutuante 0,07%, indice de precos 0,51%, prefixado 0,75%. O teste usa o
    # DOBRO de folga, para nao reprovar por um mes atipico.
    from tesouro import config

    c = pd.read_csv(config.PROCESSED_DIR / "composicao_dpf.csv",
                    parse_dates=["data"])
    piv = c.pivot_table(index="data", columns="indexador",
                        values="valor_milhoes", aggfunc="sum").fillna(0.0)
    # VINTE E QUATRO meses, como a spec 8 pede. Estava em 12 -- o plano encolheu
    # sem dizer por que, e a revisao da branch pegou.
    datas = list(piv.index)[-25:]

    # LIMITES MEDIDOS SOBRE OS 24, e nao herdados dos 12. O pior mes de cada
    # indexador em 25/08/2026: prefixado 0,248% (jul/2024), indice de precos
    # 0,950% (ago/2024), taxa flutuante 0,191% (set/2025). Os limites ficam
    # pouco acima disso -- os antigos (1,5% no prefixado contra 0,25% medido)
    # davam folga de seis vezes, e folga demais e teste que nao pega nada.
    LIMITE = {"Prefixado": 0.004, "\u00cdndice Pre\u00e7os": 0.011,
              "Taxa Flutuante": 0.0025}
    for t0, t1 in zip(datas[:-1], datas[1:]):
        obtido = rolagem.estoque_em(t1, de=t0)
        for ind, limite in LIMITE.items():
            real = piv.loc[t1, ind]
            erro = abs(obtido[ind] - real) / real
            assert erro < limite, (t1.date(), ind, erro, limite)


def test_a_rolagem_casa_por_LIQUIDACAO_e_nao_por_data_de_leilao():
    # 6,1% dos leiloes liquidam no mes seguinte ao do leilao. Casar pela data errada
    # poe o papel no mes errado, e erra exatamente as viradas -- que e onde o RMD
    # corta.
    from tesouro import config

    l = pd.read_csv(config.PROCESSED_DIR / "leiloes.csv",
                    parse_dates=["data_leilao", "data_liquidacao"])
    vira = l[(l["data_liquidacao"].dt.to_period("M")
              != l["data_leilao"].dt.to_period("M"))
             & (l["tipo_leilao"] == "Venda")]
    # PRE-CONDICAO DE DADO, NAO PROPRIEDADE DO CODIGO: 996 e a contagem medida
    # hoje, e o filtro acima e so tipo_leilao == "Venda" -- o total SEM filtro
    # de tipo e maior (1.196). Comparar um numero medido com filtro contra um
    # limite pensado sem filtro foi o erro que fez o limite original (1000)
    # ficar errado; o proximo leitor que remedir nao deve repetir isso.
    assert len(vira) > 900, "os leiloes que viram o mes sumiram do dado"

    r = vira.sort_values("data_liquidacao").iloc[-1]
    fim_do_mes_do_leilao = (r["data_leilao"] + pd.offsets.MonthEnd(0))
    entrou = rolagem.leiloes_liquidados(
        r["data_liquidacao"] - pd.Timedelta(days=1), r["data_liquidacao"])
    nao_entrou = rolagem.leiloes_liquidados(
        fim_do_mes_do_leilao - pd.Timedelta(days=31), fim_do_mes_do_leilao)
    assert entrou.sum() > 0
    assert r["data_liquidacao"] > fim_do_mes_do_leilao
    # O PONTO DO TESTE, que estava calculado e nunca conferido: este leilao
    # liquidou DEPOIS do fim do mes em que aconteceu, entao ele NAO pode entrar
    # na janela daquele mes. A variavel existia e ninguem olhava -- dava
    # aparencia de cobertura sem cobrir. Achado na revisao da branch.
    assert entrou.sum() != nao_entrou.sum() or entrou.sum() == 0, (
        "a janela que termina no fim do mes nao pode conter o leilao que "
        "liquidou depois dele")
    financeiro_do_leilao = abs(float(r["financeiro_milhoes"]))
    assert abs(entrou.sum()) >= financeiro_do_leilao * 0.99, (
        "a janela que contem a liquidacao tem de contar este leilao")


def test_o_CAMBIO_fica_parado_e_a_rolagem_diz_isso():
    # O indexador Cambio E a DPFe -- diferenca mediana de R$ 4,9 bi em 307 meses --
    # e a DPFe nao passa por leilao. Ele e segurado no valor do RMD, com o custo
    # medido: 5,2 bi por mes, 0,06% do estoque total.
    #
    # O que nao pode e segura-lo em SILENCIO: ele esta no denominador dos outros
    # tres percentuais.
    assert "C\u00e2mbio" in rolagem.PARADOS
    assert "C\u00e2mbio" not in rolagem.INDEXADORES


def test_o_pace_e_por_PAPEL_e_nao_por_dia_de_leilao():
    # Decisao dela. O metodo anterior media por DIA DE LEILAO contando os zeros --
    # nos dias de terca o prefixado vale zero -- e so dava certo se a mistura de
    # tercas e quintas da janela batesse com a do futuro. Batia por sorte: 10 e 10,
    # contra 18 e 18 no futuro.
    #
    # Medir sobre os leiloes DAQUELE papel nao depende de mistura, e rende numero que
    # se confere de cabeca: 1,09 bi por leilao de NTN-B, e nao 0,21 por dia.
    assert rolagem.LEILOES_DO_PACE == 10
    quando = pd.Timestamp("2026-08-17")
    p = rolagem.pace(quando)
    for ind in rolagem.INDEXADORES:
        assert p[ind] > 0, ind
    # A ordem de grandeza medida em 17/08/2026: a LFT coloca 21,91 bi por leilao, o
    # prefixado 12,32 e a NTN-B 1,09. Se essa relacao inverter, alguem trocou o
    # denominador -- que e exatamente o defeito que este metodo veio corrigir.
    #
    # ISSO SOZINHO NAO TRAVA A DECISAO: as razoes acima continuam valendo mesmo se
    # os zeros voltarem a entrar na media (revisor mediu: reverter para o metodo
    # antigo passa nos oito testes, porque a NTN-B e pequena demais para as
    # desigualdades quebrarem). O trecho abaixo calcula o pace DOS DOIS JEITOS,
    # dentro do proprio teste -- com e sem os dias em que o papel nao foi
    # ofertado -- e confere que excluir os zeros muda a resposta na direcao certa.
    assert p["\u00cdndice Pre\u00e7os"] * 5 < p["Taxa Flutuante"]
    assert p["\u00cdndice Pre\u00e7os"] * 3 < p["Prefixado"]

    l = pd.read_csv(config.PROCESSED_DIR / "leiloes.csv",
                    parse_dates=["data_leilao", "data_liquidacao"])
    l = l[l["data_liquidacao"] <= quando].copy()
    l["indexador"] = [rolagem._INDEXADOR_DO_TITULO.get(t) for t in l["titulo"]]
    l["sinal"] = [rolagem._SINAL.get(t, 0) for t in l["tipo_leilao"]]
    l = l[l["indexador"].notna()]
    l["fluxo"] = l["financeiro_milhoes"] * l["sinal"]
    por_leilao = l.pivot_table(index="data_leilao", columns="indexador",
                               values="fluxo", aggfunc="sum")
    # O METODO ANTIGO: media por DIA DE LEILAO, com fillna(0) em vez do filtro
    # dele != 0 que rolagem.pace usa -- os dias em que o papel nao foi a leilao
    # entram como zero, e nao ficam de fora.
    com_zeros = por_leilao.fillna(0.0).tail(rolagem.LEILOES_DO_PACE).mean()

    for ind in rolagem.INDEXADORES:
        # Sem os zeros e sempre estritamente maior: e a mesma soma dividida por
        # nao mais leiloes.
        assert com_zeros[ind] < p[ind], ind
    # O prefixado so vai a leilao as quintas: contar os zeros das tercas derruba
    # a media por quase a metade (medido: com zeros fica a 53% do valor sem
    # zeros). Materialmente maior, e nao so estatisticamente maior.
    assert com_zeros["Prefixado"] < 0.7 * p["Prefixado"]


def test_a_contagem_de_leiloes_futuros_e_por_PAPEL():
    # Prefixado na quinta, indexados na terca. Numa janela com 18 de cada, cada papel
    # tem 18 leiloes -- e nao os 36 dias.
    from tesouro import calendario_leiloes

    dias = calendario_leiloes.dias_estimados(pd.Timestamp("2026-08-18"),
                                             pd.Timestamp("2026-12-31"))
    assert len(dias) == 36
    for ind in rolagem.INDEXADORES:
        quantos = rolagem.leiloes_que_faltam(dias, ind)
        assert 15 <= quantos <= 20, (ind, quantos)
        assert quantos < len(dias), "contou dia de leilao, e nao leilao do papel"


def test_a_projecao_devolve_a_PREMISSA_que_usou():
    # Numero projetado sem a premissa ao lado e opiniao com cara de medida.
    #
    # ESTE TESTE E' A UNICA TESTEMUNHA da premissa de juros (ver o docstring
    # de rolagem._taxa_do_indexador). NAO troque as contas abaixo por uma
    # comparacao direta contra _taxa_do_indexador ou curva.selic_implicita/
    # curva.inflacao_implicita -- isso a tornaria tautologica (a mesma conta
    # contra ela mesma) e removeria a unica cobertura real, com a suite
    # inteira continuando verde.
    p = rolagem.projecao(pd.Timestamp("2026-12-31"), registros=[])
    assert 0.05 < p["selic"] < 0.30
    assert 0.0 < p["inflacao"] < 0.15
    assert p["dias_de_leilao"] > 0
    assert "fronteira_do_calendario" in p
    # A data da curva viaja junto: ela termina no ultimo RMD e a projecao parte da
    # ultima liquidacao, semanas depois.
    assert p["data_da_curva"] <= p["de"]

    # ANCORA DE SANIDADE que sobrevive a dado novo: os percentuais somam 100, e
    # nenhum indexador fica fora de [0, 100] -- nem negativo, nem maior que o todo.
    assert p["percentual"].sum() == pytest.approx(100.0)
    for ind in p["percentual"].index:
        assert 0 <= p["percentual"][ind] <= 100, ind

    # O UNICO TESTE DO CAMINHO REAL PRECISA DEFENDER O NUMERO QUE A PAGINA
    # PUBLICA -- ate aqui o teste so conferia a premissa ao lado (Selic, inflacao,
    # datas), e nunca p["estoque"] nem p["percentual"]. Revisor mediu: mutar
    # leiloes_que_faltam para devolver len(dias) (contar DIAS de leilao em vez de
    # LEILOES DAQUELE PAPEL) dobra a emissao projetada (635 -> 1.271 bi) e empurra
    # o total para fora de qualquer banda razoavel -- e nada aqui acusava.
    #
    # Recalcula a emissao de forma independente da chamada de projecao() -- com as
    # mesmas pecas publicas que ela usa por dentro -- e confere que bate com a
    # diferenca que a projecao de fato produziu (estoque - base + pago - juros,
    # tambem recalculados aqui e nao lidos do dict devolvido). Isto trava a fiacao
    # entre pace()/leiloes_que_faltam() e o numero publicado sem prender o teste a
    # um valor cravado que muda quando o pipeline roda de novo.
    from tesouro import calendario, calendario_leiloes, curva, fluxos

    de, ate = p["de"], p["ate"]
    dias, _ = calendario_leiloes.dias_ate(ate, registros=[], hoje=de)
    ritmo = rolagem.pace(de)
    inicial = rolagem.estoque_em(de)
    pagou = fluxos.pagos(de, ate)
    selic = curva.selic_implicita(ate, data_base=de)
    inflacao = curva.inflacao_implicita(ate, data_base=de)
    du = calendario.padrao().du(de.date(), ate.date())

    total_emissao = 0.0
    for ind in rolagem.INDEXADORES:
        base = float(inicial[ind])
        do_ind = pagou[pagou["indexador"] == ind]
        pago = do_ind["principal_milhoes"].sum() + do_ind["cupom_milhoes"].sum()
        if ind == "\u00cdndice Pre\u00e7os":
            taxa = (1 + inflacao) * 1.06 - 1
        elif ind == "Taxa Flutuante":
            taxa = selic
        else:
            # A peca PUBLICA, como selic/inflacao acima -- e nao
            # _taxa_do_indexador, que tornaria a comparacao a mesma conta
            # contra ela mesma e removeria a unica cobertura da premissa.
            taxa = rolagem.carga_do_prefixado(de)
        juros = base * ((1 + taxa) ** (du / 252) - 1)
        emissao_esperada = float(ritmo[ind]) * rolagem.leiloes_que_faltam(dias, ind)
        emissao_publicada = p["estoque"][ind] - base + pago - juros
        assert emissao_publicada == pytest.approx(emissao_esperada, rel=1e-6), ind
        total_emissao += emissao_publicada

    # A COMPARACAO ACIMA (emissao_publicada == emissao_esperada) chama
    # leiloes_que_faltam nos dois lados: qualquer mutacao nela move os dois lados
    # juntos, e a assercao continua batendo -- por isso ela nao pegava a mutacao
    # que o revisor testou (leiloes_que_faltam mutado para devolver len(dias)).
    #
    # Esta comparacao NAO chama leiloes_que_faltam. O prefixado so vai a leilao
    # as quintas, os indexados so as tercas -- cada papel usa cerca de METADE dos
    # dias de leilao da janela. A emissao projetada tem de ser bem menor do que
    # seria se todos os papeis fossem a leilao em todos os dias: o teto do metodo
    # errado (contar dias, e nao leiloes do papel) e quase o dobro. 0,7 e nao 0,5
    # porque os tres papeis nao se dividem exatamente meio a meio -- mas ainda
    # reprova a mutacao, que leva a razao a 1,0.
    teto_do_metodo_errado = sum(float(ritmo[ind]) * len(dias)
                                for ind in rolagem.INDEXADORES)
    assert total_emissao < teto_do_metodo_errado * 0.7


def test_a_projecao_no_ramo_do_BACKTEST_usa_a_data_pedida():
    # 'de_snapshot' existe para o backtest: comecar de uma data de RMD de
    # proposito, e nao da ultima liquidacao, para comparar com o dezembro que de
    # fato aconteceu. Chamava-se 'hoje' ate 25/08/2026, e o nome enganava --
    # 'hoje' em todo o resto do projeto quer dizer "role ate aqui".
    c = pd.read_csv(config.PROCESSED_DIR / "composicao_dpf.csv",
                    parse_dates=["data"])
    datas = sorted(c["data"].unique())
    hoje = pd.Timestamp(datas[-2])
    ate = pd.Timestamp(datas[-1])

    p = rolagem.projecao(ate, de_snapshot=hoje, registros=[])
    assert p["de"] == hoje
    assert p["ate"] == ate
    assert p["estoque"].sum() > 0


def test_a_projecao_no_ramo_do_BACKTEST_levanta_LookupError_diagnosavel():
    # piv.loc[partida] sem guarda levantava um KeyError cru do pandas -- nao diz
    # qual data faltou nem quais existem por perto. Troquei por um LookupError com
    # as duas informacoes.
    with pytest.raises(LookupError, match="composicao_dpf"):
        rolagem.projecao(pd.Timestamp("2026-12-31"),
                         de_snapshot=pd.Timestamp("1999-01-01"), registros=[])

# ---------------------------------------------------------------------------
# Decisao dela, 25/08/2026: "tudo que teve de leilao que ainda nao esta na
# planilha, usa o do leilao, pq ja temos inclusive o resultado. ou seja, da
# planilha ate hj usa o leilao."
# ---------------------------------------------------------------------------


def test_o_provisorio_entra_DEPOIS_de_onde_a_planilha_acaba():
    """A planilha do Tesouro atrasa ate cinco dias; a API tem o resultado hoje.

    A fronteira e a ULTIMA LIQUIDACAO da planilha. Antes dela manda a planilha,
    depois dela manda o provisorio -- assim nenhum leilao entra duas vezes, que
    e o unico jeito de esta juncao errar para MAIS.

    A PROPRIEDADE NAO E "nao ha linha repetida". A planilha ja tem 1.027 linhas
    que repetem (data, titulo, vencimento, volta) por conta propria: sao Venda e
    Compra no mesmo dia e no mesmo papel, mais linhas zeradas. Foi a primeira
    chave que escrevi, e ela acusava a planilha, nao a juncao. O que importa e
    que a juncao NAO ACRESCENTE repetido, e que tudo que ela acrescenta esteja
    depois da fronteira.
    """
    chave = ["data_leilao", "titulo", "data_vencimento", "volta", "tipo_leilao"]
    oficial = rolagem.leiloes(com_provisorio=False)
    tudo = rolagem.leiloes()

    fronteira = oficial["data_liquidacao"].max()
    assert tudo["data_liquidacao"].max() >= fronteira

    assert (tudo.duplicated(subset=chave).sum()
            == oficial.duplicated(subset=chave).sum()), (
        "a juncao acrescentou linha repetida -- algum leilao entrou pela "
        "planilha E pelo provisorio")

    # E o que entrou a mais esta TODO depois da fronteira, e e exatamente o
    # tanto que o arquivo provisorio tem dali em diante.
    caminho = config.PROCESSED_DIR / "leiloes_recentes.csv"
    if caminho.exists():
        prov = pd.read_csv(caminho, parse_dates=["data_liquidacao"])
        alem = prov[prov["data_liquidacao"] > fronteira]
        assert len(tudo) == len(oficial) + len(alem)
        if len(alem):
            entrou = tudo.tail(len(alem))
            assert (entrou["data_liquidacao"] > fronteira).all()

def test_a_rolagem_ENXERGA_o_leilao_que_a_planilha_ainda_nao_traz():
    """O ponto da decisao 3, medido no numero e nao na existencia do arquivo.

    Sem isto a tabela "onde estamos hoje" ficava ate cinco dias atrasada, dizendo
    17/08 num dia 25/08 -- honesta no rodape, mas cega para tres dias de leilao
    que ja tinham resultado publicado.
    """
    import pandas as pd

    oficial = rolagem.leiloes(com_provisorio=False)
    tudo = rolagem.leiloes()
    fronteira = oficial["data_liquidacao"].max()
    depois = tudo[tudo["data_liquidacao"] > fronteira]
    if depois.empty:
        pytest.skip("a planilha esta em dia; nao ha provisorio para somar")

    base, _ = rolagem.base_do_rmd()
    ate = tudo["data_liquidacao"].max()

    com = rolagem.leiloes_liquidados(base, ate)
    ate_a_planilha = rolagem.leiloes_liquidados(base, fronteira)

    # O que entrou a mais tem de ser EXATAMENTE o financeiro liquido do
    # provisorio -- nem mais (duplicou) nem menos (perdeu linha).
    esperado = {}
    for ind in rolagem.INDEXADORES:
        d = depois[[rolagem._INDEXADOR_DO_TITULO.get(t) == ind
                    for t in depois["titulo"]]]
        sinais = [rolagem._SINAL.get(t, 0) for t in d["tipo_leilao"]]
        esperado[ind] = float((d["financeiro_milhoes"] * sinais).sum())

    for ind in rolagem.INDEXADORES:
        assert com[ind] - ate_a_planilha[ind] == pytest.approx(
            esperado[ind], rel=1e-9), ind


# ---------------------------------------------------------------------------
# Decisao dela, 25/08/2026: "vc tem o vna do ultimo leilao. projeta tudo a
# partir da data do ultimo leilao, ai vc usa as premissas que ja estava usando"
# ---------------------------------------------------------------------------


def test_o_VNA_e_CARREGADO_da_ancora_ate_a_data_pedida():
    """A ancora e o ultimo leilao ate a data, e nao a data.

    Antes, vna_em devolvia o VNA do leilao ancora como se fosse o da data
    pedida. Em 17/08/2026 a ancora era 11/08: quatro dias uteis sem apropriar,
    R$ 12,1 bi a menos, SEMPRE para baixo. Agora carrega da ancora ate a data
    com a Selic (ou a inflacao) implicita da curva -- a mesma premissa que a
    projecao ja usava.
    """
    import pandas as pd

    from tesouro import calendario

    carrego = {}
    for indice in ("SELIC", "IPCA"):
        valor, ancora = rolagem.vna_ancorado(indice, pd.Timestamp("2026-08-17"))
        carregado = rolagem.vna_em(indice, pd.Timestamp("2026-08-17"))

        du = calendario.padrao().du(ancora.date(), pd.Timestamp("2026-08-17").date())
        if du == 0:
            assert carregado == pytest.approx(valor)
            pytest.skip(f"{indice} ancorou na propria data; sem carrego a medir")
        # Carregou para CIMA, e por um fator plausivel para poucos dias uteis.
        assert carregado > valor, indice
        assert carregado / valor - 1 < 0.01, (
            f"{indice}: carrego de {du} dias uteis nao pode passar de 1%")
        carrego[indice] = carregado / valor - 1

    # E CADA INDICE COM A SUA TAXA. So "subiu, e pouco" nao distingue Selic de
    # inflacao: sobre um dia util as duas passam nesse teste, e trocar uma pela
    # outra ficava verde (medido). A Selic implicita e ~13,8% a.a. e a inflacao
    # ~4,7%, entao o carrego da SELIC tem de ser varias vezes o do IPCA -- razao
    # que so vale se cada um estiver usando a propria premissa.
    assert carrego["SELIC"] > 2 * carrego["IPCA"], (
        f"o carrego da SELIC ({carrego['SELIC']:.5f}) devia ser bem maior que o "
        f"do IPCA ({carrego['IPCA']:.5f}); parece que os dois usam a mesma taxa")


def test_carregar_ate_a_PROPRIA_data_da_ancora_nao_muda_nada():
    """A identidade que separa "carregou certo" de "carregou qualquer coisa".

    Um teste que so olhasse "ficou maior" passaria com qualquer fator. Este fixa
    a ponta: pedir o VNA na data do proprio leilao ancora tem de devolver o VNA
    daquele leilao, sem carrego nenhum.
    """
    import pandas as pd

    for indice in ("SELIC", "IPCA"):
        _, ancora = rolagem.vna_ancorado(indice, pd.Timestamp("2026-08-17"))
        na_ancora, mesma = rolagem.vna_ancorado(indice, ancora)
        assert mesma == ancora
        assert rolagem.vna_em(indice, ancora) == pytest.approx(na_ancora)

def test_a_fronteira_BARRA_o_provisorio_que_a_planilha_ja_tem(tmp_path,
                                                              monkeypatch):
    """O corte na fronteira, exercitado com dado que o forca a agir.

    Com o arquivo de verdade esta mutacao nao aparece: o provisorio de hoje so
    tem linhas ALEM da fronteira, entao tirar o filtro nao muda nada e o teste
    fica verde contra codigo que duplicaria. Medido -- foi o que aconteceu na
    primeira rodada de mutacao.

    Aqui o provisorio leva DUAS linhas de proposito: uma copia de um leilao que
    a planilha ja tem, e uma nova depois da fronteira. So a segunda pode entrar.
    Se a fronteira parar de cortar, a primeira entra tambem e o estoque emitido
    conta o mesmo leilao duas vezes -- erro para MAIS, o pior lado numa tabela
    de conformidade.
    """
    import shutil

    oficial = rolagem.leiloes(com_provisorio=False)
    fronteira = oficial["data_liquidacao"].max()

    shutil.copy(config.PROCESSED_DIR / "leiloes.csv",
                tmp_path / "leiloes.csv")

    ja_tem = oficial[oficial["data_liquidacao"] == fronteira].iloc[[0]].copy()
    nova = ja_tem.copy()
    nova["data_liquidacao"] = fronteira + pd.Timedelta(days=1)
    nova["data_leilao"] = fronteira + pd.Timedelta(days=1)
    pd.concat([ja_tem, nova], ignore_index=True).to_csv(
        tmp_path / "leiloes_recentes.csv", index=False)

    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)

    tudo = rolagem.leiloes()
    assert len(tudo) == len(oficial) + 1, (
        "so a linha DEPOIS da fronteira pode entrar; a que a planilha ja tem "
        "nao pode ser contada de novo")
    assert tudo["data_liquidacao"].max() == fronteira + pd.Timedelta(days=1)


# ---------------------------------------------------------------------------
# Entrega 5: a emissao necessaria e a projecao lida ao contrario.
# ---------------------------------------------------------------------------


def test_emissao_necessaria_e_a_projecao_ao_contrario():
    """A IDENTIDADE QUE SUSTENTA A ENTREGA 5 INTEIRA.

    A projecao responde "neste ritmo, chego onde?". Esta funcao responde "para
    chegar ali, que ritmo preciso?". Sao a mesma conta lida ao contrario, entao
    pedir a emissao necessaria para o resultado da PROPRIA projecao tem de
    devolver o pace atual -- para os tres indexadores.

    Se as duas discordarem, uma esta errada, e este teste nao diz qual. Mas
    impede que a pagina publique as duas lado a lado dizendo coisas diferentes.

    A IDENTIDADE SOZINHA E GAMEAVEL (achado da revisao): uma funcao que ignore
    alvo_pct, alvo_total, vence e juros, e simplesmente devolva
    pace(hoje)[indexador], bate com a assercao acima por construcao -- o
    teste chama com hoje=p["de"] e compara com pace(p["de"]), entao os dois
    lados sao a mesma chamada disfarcada. Por isso este teste tambem exige que
    um alvo DESLOCADO mude a resposta, e na direcao certa: alvo maior tem de
    pedir emissao maior. So assim a identidade deixa de ser tautologica.
    """
    ate = pd.Timestamp("2026-12-31")
    p = rolagem.projecao(ate, registros=[])
    total = float(p["estoque"].sum()) / 1000
    ritmo = rolagem.pace(p["de"])

    for ind in rolagem.INDEXADORES:
        pct = float(p["percentual"][ind])
        obtido = rolagem.emissao_necessaria(ind, pct, total, hoje=p["de"],
                                            ate=ate, registros=[])
        assert obtido == pytest.approx(float(ritmo[ind]), rel=1e-6), (
            f"{ind}: a emissao necessaria para o proprio resultado da projecao "
            f"tem de ser o pace atual")

        # A PROVA DE QUE NAO E TAUTOLOGIA: pedir um alvo_pct maior, com o
        # mesmo hoje/ate/total, tem de pedir MAIS emissao. Uma funcao que
        # ignore alvo_pct (o stub acima) devolveria o mesmo numero aqui, e
        # esta assercao cairia sozinha.
        maior = rolagem.emissao_necessaria(ind, pct + 1, total, hoje=p["de"],
                                           ate=ate, registros=[])
        assert maior > obtido, (
            f"{ind}: emissao_necessaria tem de reagir ao alvo_pct, e nao so "
            f"repetir o pace atual")


def test_emissao_necessaria_cresce_com_o_alvo():
    """Monotonicidade nos dois eixos.

    Uma troca de sinal na formula -- alvo menos estoque virando estoque menos
    alvo -- daria numeros plausiveis e inverteria a leitura inteira. Nenhum
    teste de valor isolado pega isso; a ordem pega.
    """
    ate = pd.Timestamp("2026-12-31")
    hoje = banda_ultima_liquidacao()

    def pede(pct, total):
        return rolagem.emissao_necessaria("Prefixado", pct, total, hoje=hoje,
                                          ate=ate, registros=[])

    # Mesmo total, percentual maior -> emitir mais.
    assert pede(22, 9900) > pede(21, 9900)
    # Mesmo percentual, total maior -> emitir mais.
    assert pede(21, 10100) > pede(21, 9900)


def test_emissao_necessaria_fica_NEGATIVA_quando_o_alvo_esta_abaixo():
    """Negativo e resposta, e nao erro.

    O estoque cresce sozinho pelos juros. Quando o alvo esta abaixo de onde ele
    vai parar, nem parando de emitir se chega la -- e o numero diz o tamanho do
    resgate que faltaria.

    Medido em 26/08/2026: a taxa flutuante esta em 53,00% com banda de 46 a 50,
    e 20 das 30 celulas da banda dela sao negativas.
    """
    ate = pd.Timestamp("2026-12-31")
    hoje = banda_ultima_liquidacao()
    assert rolagem.emissao_necessaria("Taxa Flutuante", 46, 9700, hoje=hoje,
                                      ate=ate, registros=[]) < 0


def test_emissao_necessaria_LEVANTA_quando_nao_ha_leilao_do_papel_na_janela():
    """Caminho nunca exercitado: a guarda contra dividir por zero.

    Classe de defeito que ja mordeu este projeto duas vezes -- um 'raise' novo
    sem cobertura e divida na hora em que nasce. Pedindo 'ate' igual a 'hoje'
    nao sobra dia nenhum de leilao no meio, para nenhum dos tres indexadores;
    entao a guarda tem de levantar, nomeando o indexador e as duas datas, e
    nao dividir 'quantos' zerado em silencio.
    """
    hoje = banda_ultima_liquidacao()
    with pytest.raises(LookupError) as excinfo:
        rolagem.emissao_necessaria("Prefixado", 20, 10000, hoje=hoje,
                                   ate=hoje, registros=[])

    mensagem = str(excinfo.value)
    data = hoje.strftime("%d/%m/%Y")
    assert f"'Prefixado' entre {data} e {data}" in mensagem, (
        "a mensagem tem de nomear o indexador e as DUAS datas da janela")

# ---------------------------------------------------------------------------
# A CARGA DO PREFIXADO SAI DO CUSTO PUBLICADO, e nao de uma constante.
#
# Ate 27/08/2026 era _CARGA_DO_PREFIXADO = 0.135, calibrada contra o residuo da
# propria rolagem. O numero nem era absurdo -- bate com a taxa de EMISSAO do
# prefixado (13,68% em 12 meses) -- mas e a taxa errada: LTN e NTN-F tem juro
# TRAVADO na emissao, entao o que o ESTOQUE rende e a taxa ja contratada la
# atras, que e mais baixa. O custo do estoque publicado pelo Tesouro em
# 31/07/2026 dava 12,233% ponderado, contra os 13,5% usados.
#
# MEDIDO no backtest de 24 meses, vies medio do prefixado:
#
#     13,500% (a constante)   +0,071%   com 19 dos 24 meses para cima
#     por data, mensal        -0,058%   com  6 dos 24
#     por data, acum_12m      -0,090%   com  2 dos 24
#     12,233% fixo            -0,021%   com 10 dos 24  <- ILEGITIMO, olha o gabarito
#
# O ganho e de PROCEDENCIA e nao de precisao: o vies quase nao muda de tamanho,
# so de sinal. O que muda e a fonte deixar de ser ajustada por nos.
# ---------------------------------------------------------------------------

def test_a_carga_do_prefixado_e_o_custo_do_ESTOQUE_e_nao_o_da_EMISSAO():
    """A distincao que da sentido a esta entrega.

    Sao dois numeros publicados, diferentes, e o codigo usava o errado:

        custo do ESTOQUE   LTN 12,916%  NTN-F 11,814%   <- o que o estoque rende
        custo das EMISSOES LTN 13,628%  NTN-F 13,733%   <- o que o dinheiro NOVO custa

    Se alguem trocar a fonte para 'emissoes_12m', a carga sobe ~1,4 pp e este
    teste fica vermelho.
    """
    from tesouro import config

    c = pd.read_csv(config.PROCESSED_DIR / "custo_medio.csv", parse_dates=["data"])
    quando = c["data"].max()
    do_estoque = c[(c["data"] == quando) & (c["medida"] == "mensal")
                   & (c["nivel"] == "DPMFi")].set_index("titulo")["custo_aa_pct"]
    das_emissoes = c[(c["data"] == quando) & (c["medida"] == "emissoes_12m")
                     & (c["nivel"] == "DPMFi")].set_index("titulo")["custo_aa_pct"]

    obtida = 100 * rolagem.carga_do_prefixado(quando)

    menor = min(float(do_estoque["LTN"]), float(do_estoque["NTN-F"]))
    maior = max(float(do_estoque["LTN"]), float(do_estoque["NTN-F"]))
    assert menor <= obtida <= maior, (
        f"a carga ({obtida:.3f}%) tem de ficar entre o custo de estoque da "
        f"NTN-F e o da LTN ({menor:.3f}% a {maior:.3f}%)")

    piso_emissao = min(float(das_emissoes["LTN"]), float(das_emissoes["NTN-F"]))
    assert obtida < piso_emissao, (
        f"a carga ({obtida:.3f}%) ficou na faixa do custo de EMISSAO "
        f"(>= {piso_emissao:.3f}%) -- fonte trocada")


def test_a_carga_do_prefixado_ANDA_no_tempo():
    """Uma constante nao envelhece: ela apenas passa a estar errada em silencio.

    Era esse o defeito real do 0.135 -- nao o valor, que ate batia com a taxa
    de emissao da epoca, mas ser um numero congelado num arquivo enquanto o
    custo do estoque se move todo mes.
    """
    from tesouro import config

    c = pd.read_csv(config.PROCESSED_DIR / "custo_medio.csv", parse_dates=["data"])
    datas = sorted(c["data"].unique())[-24:]
    valores = {round(rolagem.carga_do_prefixado(d), 6) for d in datas}
    assert len(valores) > 12, (
        f"a carga so assumiu {len(valores)} valores em 24 meses; "
        f"isso e constante disfarcada")


def test_a_carga_do_prefixado_pondera_pelo_ESTOQUE_de_cada_papel():
    """LTN e NTN-F custam diferente, e a mistura importa.

    Em 31/07/2026, medida mensal: LTN 12,916% com R$ 1.133 bi, NTN-F 11,814%
    com R$ 647 bi. A media SIMPLES daria 12,365%; a ponderada da 12,516%. Sao
    0,15 pp, e sobre 1.800 bi isso e da ordem de R$ 1 bi por ano de juros.
    """
    from tesouro import config

    quando = pd.Timestamp("2026-07-31")
    c = pd.read_csv(config.PROCESSED_DIR / "custo_medio.csv", parse_dates=["data"])
    k = c[(c["data"] == quando) & (c["medida"] == "mensal")
          & (c["nivel"] == "DPMFi")].set_index("titulo")["custo_aa_pct"]
    simples = (float(k["LTN"]) + float(k["NTN-F"])) / 2

    obtida = 100 * rolagem.carga_do_prefixado(quando)
    assert abs(obtida - simples) > 0.05, (
        f"a carga ({obtida:.3f}%) ficou colada na media SIMPLES "
        f"({simples:.3f}%) -- a ponderacao pelo estoque sumiu")


def test_a_projecao_usa_a_carga_da_DATA_DE_PARTIDA():
    """A taxa que interessa e a do estoque de onde a projecao parte.

    Nao a de hoje, nem a do fim da janela: o backtest parte de datas antigas de
    proposito, e usar a carga de 2026 para projetar de 2024 seria olhar o
    futuro. curva.selic_implicita ja recusa isso, e com razao.
    """
    antiga = pd.Timestamp("2024-12-31")
    recente = pd.Timestamp("2026-07-31")
    assert (rolagem._taxa_do_indexador("Prefixado", recente, data_base=antiga)
            == pytest.approx(rolagem.carga_do_prefixado(antiga)))
    assert (rolagem._taxa_do_indexador("Prefixado", recente, data_base=recente)
            == pytest.approx(rolagem.carga_do_prefixado(recente)))

def test_a_rolagem_NAO_LE_O_MES_QUE_ESTA_TENTANDO_REPRODUZIR(tmp_path, monkeypatch):
    """A regra dela, 27/08/2026, e ela vale para toda a rolagem.

    Ao rolar de t0 para t1 nao se pode ler nada carimbado em t1: seria olhar o
    gabarito que se esta tentando prever. Um backtest que le o futuro fica lindo
    e nao diz nada -- a projecao de verdade, que nao tem gabarito, erra do mesmo
    jeito e ninguem descobre.

    JA ACONTECEU AQUI, e foi por isso que a regra apareceu. Uma das candidatas
    a carga do prefixado era a constante 12,233%, que media MELHOR que todas as
    outras (-0,021% de vies). Era o custo de julho de 2026 aplicado a 2024. Em
    2024 ninguem sabia aquele numero.

    COMO ESTE TESTE FUNCIONA: em vez de inspecionar quem le o que -- que exigiria
    saber de antemao todos os caminhos, inclusive os que ainda nao existem -- ele
    ESTRAGA o futuro e exige que nada mude. Qualquer leitura indevida move o
    resultado e o teste cai.

    ONDE ESTA A FRONTEIRA, e ela e escolha dela:

      GABARITO, nao pode ler em t1
        composicao_dpf.csv              a resposta que a rolagem tenta reproduzir
        custo_medio.csv                 a taxa a que o estoque rendeu
        estoque_titulos_vencimento.csv  a abertura do estoque por papel

      NAO E GABARITO, pode ler ate t1
        leiloes                         quanto o Tesouro de fato emitiu no mes
        vna.csv                         a inflacao e a Selic que de fato correram

    A segunda lista existe porque estoque_em() e uma RECONSTRUCAO do mes que
    passou, e nao uma previsao. Proibi-la de saber quanto foi emitido a impediria
    de reproduzir mes nenhum -- e e justamente reproduzir os meses fechados que
    sustenta todo o resto.
    """
    import shutil

    from tesouro import config

    t0, t1 = pd.Timestamp("2026-06-30"), pd.Timestamp("2026-07-31")

    esperado = rolagem.estoque_em(t1, de=t0)

    destino = tmp_path / "processed"
    destino.mkdir()
    for arquivo in config.PROCESSED_DIR.glob("*.csv"):
        shutil.copy2(arquivo, destino / arquivo.name)

    GABARITO = ("composicao_dpf.csv", "custo_medio.csv",
                "estoque_titulos_vencimento.csv")
    estragadas = 0
    for nome in GABARITO:
        caminho = destino / nome
        d = pd.read_csv(caminho, parse_dates=["data"])
        futuro = d["data"] >= t1
        estragadas += int(futuro.sum())
        for coluna in d.columns:
            # is_numeric_dtype, e nao 'dtype == object': o pandas novo usa um
            # dtype 'str' proprio, que nao e object e explode ao receber float.
            if coluna == "data" or not pd.api.types.is_numeric_dtype(d[coluna]):
                continue
            d.loc[futuro, coluna] = 999999.0
        d.to_csv(caminho, index=False)

    assert estragadas > 0, (
        "nenhuma linha de t1 foi estragada -- o teste nao provaria nada")

    monkeypatch.setattr(config, "PROCESSED_DIR", destino)
    obtido = rolagem.estoque_em(t1, de=t0)

    for ind in rolagem.INDEXADORES:
        assert float(obtido[ind]) == pytest.approx(float(esperado[ind]), abs=1e-6), (
            f"{ind}: a rolagem mudou quando o dado de {t1:%d/%m/%Y} foi "
            f"estragado -- ou seja, ela LE o mes que deveria estar prevendo")
