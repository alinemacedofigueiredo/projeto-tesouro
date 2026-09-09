"""A simulacao: quanto emitir por leilao para chegar a cada alvo."""
import pandas as pd
import pytest

from tesouro import api_leiloes, calendario_leiloes, rolagem
from tesouro.graficos import paf, simulacao


def test_os_eixos_contem_a_BANDA_inteira():
    # Decisao dela: "garante sempre que o projetado com o pace de hj esta dentro
    # da banda apresentada, e o intervalo da paf tbm".
    linhas, colunas = simulacao.eixos("prefixado_pct", 21.10, 9947, 2026)
    assert min(linhas) <= 21 and max(linhas) >= 25, "a banda 21-25 tem de caber"
    assert min(colunas) <= 9700 and max(colunas) >= 10300, (
        "a banda de estoque 9.700-10.300 tem de caber")


def test_os_eixos_contem_o_PROJETADO_mesmo_longe_da_banda():
    """O caso da taxa flutuante: banda 49-53 (revisada), projetado 53,24%.

    A versao anterior da spec fixava a grade e nao marcava nada quando o
    projetado caia fora -- deixando justamente a tabela do indicador FORA da
    banda, que e a mais interessante, sem a marca do ritmo atual.

    A BANDA VEM DO CSV, e nao do numero cravado que estava aqui: dizia 46-50 e
    ficou vermelho quando o Tesouro revisou para 49-53 em 26/08/2026. O que o
    teste protege e a grade CONTER a banda e o projetado, e nao qual banda e.
    """
    lo, hi = 49.0, 53.0
    b = paf.bandas("taxa_flutuante_pct").loc[2026]
    assert (float(b["minimo"]), float(b["maximo"])) == (lo, hi), (
        "a banda de 2026 mudou no CSV; confira a revisao antes de mexer aqui")
    linhas, _ = simulacao.eixos("taxa_flutuante_pct", 53.24, 9947, 2026)
    assert max(linhas) >= 54, f"53,24% tem de caber; linhas foram {linhas}"
    assert min(linhas) <= lo - 1, f"a banda {lo:.0f}-{hi:.0f} tem de caber"


def test_os_eixos_tem_passo_regular_FORA_do_ponto_de_hoje():
    """A grade continua regular; o ponto de hoje e a unica excecao.

    Ate 08/09/2026 este teste exigia passo regular em TODA a grade. Deixou de
    ser verdade por decisao dela: o ponto exato do ritmo de hoje entra como
    linha e coluna proprias, e portanto quebra o passo em UM lugar. O teste
    passa a dizer isso -- tirado o ponto, o resto anda de 1 em 1 e de
    PASSO_TOTAL em PASSO_TOTAL.
    """
    linhas, colunas = simulacao.eixos("prefixado_pct", 21.10, 9947, 2026)
    grade_l = [x for x in linhas if x != 21.10]
    grade_c = [x for x in colunas if x != 9947]
    assert all(b - a == 1 for a, b in zip(grade_l, grade_l[1:])), grade_l
    assert all(b - a == simulacao.PASSO_TOTAL
               for a, b in zip(grade_c, grade_c[1:])), grade_c


def test_a_linha_e_a_coluna_de_hoje_entram_ORDENADAS():
    """No lugar delas na grade, e nao no fim.

    Uma linha de 21,10% depois da de 25% faria o leitor procurar. O teste pega
    tanto o ponto ausente quanto o ponto anexado fora de ordem.
    """
    linhas, colunas = simulacao.eixos("prefixado_pct", 21.10, 9947, 2026)
    assert 21.10 in linhas, linhas
    assert 9947 in colunas, colunas
    assert linhas == sorted(linhas), linhas
    assert colunas == sorted(colunas), colunas


def test_o_ponto_de_hoje_NAO_DUPLICA_a_linha_quando_cai_em_cima_da_grade():
    """Caso sintetico: o ritmo leva a um valor redondo.

    Nenhum indicador de hoje projeta exatamente 22% de R$ 9.900 bi, mas nada
    impede -- e uma linha repetida sairia como duas linhas iguais na pagina,
    que parece defeito de dado.
    """
    linhas, colunas = simulacao.eixos("prefixado_pct", 22.0, 9900, 2026)
    assert linhas.count(22.0) == 1, linhas
    assert colunas.count(9900.0) == 1, colunas


def test_os_eixos_contem_PROJETADO_abaixo_da_banda():
    """Caso sintetico: projetado bem abaixo da banda.

    Nenhum indicador real de hoje projeta tao abaixo da sua banda. Por isso
    usamos valores sinteticos em vez de esperar que o dado real produza este
    ramo -- deixar essa logica sem teste e descobrir que falha quando importar e
    ja for tarde.

    Banda prefixado 21-25, projetado sintetico 18,5. O piso da grade com margem
    e 21 - 1 = 20. O floor do projetado e 18. O min(20, 18) deve ser 18, e as
    linhas devem comecar ali.
    """
    linhas, _ = simulacao.eixos("prefixado_pct", 18.5, 9947, 2026)
    assert min(linhas) <= 18, f"18,5% tem de caber; linhas foram {linhas}"
    assert max(linhas) >= 21, "a banda 21-25 continua tendo de caber"


def test_os_eixos_contem_TOTAL_abaixo_da_banda():
    """Caso sintetico: total bem abaixo da banda de estoque.

    Nenhum cenario de hoje projeta o total de estoque tao abaixo da sua banda.
    Por isso usamos valores sinteticos em vez de esperar que o dado real produza
    este ramo -- deixar essa logica sem teste e descobrir que falha quando
    importar e ja for tarde.

    Banda de estoque 9.700-10.300 bilhoes, total sintetico 8000. O piso da grade
    com margem e 9700 - 200 = 9500. O floor(8000/200)*200 = 8000. O
    min(9500, 8000) deve ser 8000, e as colunas devem comecar ali.
    """
    _, colunas = simulacao.eixos("prefixado_pct", 21.10, 8000, 2026)
    assert min(colunas) <= 8000, f"8000 tem de caber; colunas foram {colunas}"
    assert max(colunas) >= 9700, "a banda 9.700-10.300 continua tendo de caber"


def test_os_eixos_contem_TOTAL_acima_da_banda():
    """Caso sintetico: total bem acima da banda de estoque.

    Nenhum cenario de hoje projeta o total de estoque tao acima da sua banda.
    Por isso usamos valores sinteticos em vez de esperar que o dado real produza
    este ramo -- deixar essa logica sem teste e descobrir que falha quando
    importar e ja for tarde.

    Banda de estoque 9.700-10.300 bilhoes, total sintetico 12100. O teto da
    grade com margem e 10300 + 200 = 10500. O ceil(12100/200)*200 = 12200. O
    max(10500, 12200) deve ser 12200, e as colunas devem chegar ali.
    """
    _, colunas = simulacao.eixos("prefixado_pct", 21.10, 12100, 2026)
    assert max(colunas) >= 12100, f"12100 tem de caber; colunas foram {colunas}"
    assert min(colunas) <= 10300, "a banda 9.700-10.300 continua tendo de caber"


def test_dados_simulacao_tem_a_forma_dos_eixos():
    d = simulacao.dados_simulacao("prefixado_pct", registros=[])
    linhas, colunas = simulacao.eixos(
        "prefixado_pct", d.attrs["projetado_pct"],
        d.attrs["projetado_total"], d.attrs["ate"].year)
    assert list(d.index) == linhas
    assert list(d.columns) == colunas


def test_a_marca_cai_na_celula_do_projetado():
    """A marca E o ponto projetado, e a distancia ate ele e zero.

    Ate 08/09/2026 a marca era o vizinho mais proximo da grade, e este teste
    tolerava meio ponto percentual e meio passo de total. As tolerancias
    ficaram: elas continuam pegando marca posta na celula errada, e agora com
    folga de sobra, porque o ponto exato entrou na grade e a distancia caiu a
    zero. Some com isso a pergunta de qual eixo arredondar primeiro, que nao
    tinha resposta boa.
    """
    d = simulacao.dados_simulacao("prefixado_pct", registros=[])
    linha, coluna = d.attrs["marca"]
    assert abs(linha - d.attrs["projetado_pct"]) <= 0.5
    assert abs(coluna - d.attrs["projetado_total"]) <= simulacao.PASSO_TOTAL / 2
    assert linha in d.index and coluna in d.columns


def test_o_ritmo_atual_vem_da_FONTE_e_nao_da_celula():
    """O nome antigo era "a celula marcada NAO e o ritmo atual", e envelheceu.

    Ele descrevia a armadilha de 26/08/2026: com a grade so em passos
    inteiros, a celula marcada mostrava quanto emitir para cair no ponto
    ARREDONDADO, e no indice de precos dava 0,3 contra um ritmo de 2,04. Desde
    08/09 o ponto exato entrou na grade e os dois passaram a coincidir -- ver
    test_a_celula_marcada_E_o_ritmo_de_hoje.

    O CORPO NUNCA FOI SOBRE ISSO, e por isso nao quebrou: ele ja dizia, no
    proprio docstring, que os dois podiam coincidir. O que ele exige e que
    ritmo_atual venha de rolagem.pace, e nao de uma copia da celula -- se
    virasse alias, a coincidencia acima seria tautologia e nao afirmacao.
    """
    d = simulacao.dados_simulacao("indice_precos_pct", registros=[])
    linha, coluna = d.attrs["marca"]
    assert "ritmo_atual" in d.attrs
    assert d.attrs["ritmo_atual"] > 0
    # A celula existe e e um numero -- nao um NaN nem o proprio ritmo copiado.
    assert pd.notna(d.at[linha, coluna])
    # ritmo_atual vem de rolagem.pace, e nao da celula marcada -- conferido
    # contra a FONTE, e nao so "existe e e positivo", que passaria mesmo se
    # ritmo_atual fosse um alias silencioso da celula marcada.
    esperado = float(rolagem.pace(d.attrs["hoje"])[d.attrs["indexador"]]) / 1000
    assert d.attrs["ritmo_atual"] == pytest.approx(esperado, rel=1e-9)


def test_a_matriz_cresce_nos_dois_eixos(tabelas):
    """CRESCE, e nao 'nao decresce'.

    is_monotonic_increasing do pandas aceita [5,5,5,5] como crescente. O
    revisor congelou 'total' no primeiro valor do laco interno -- a matriz
    inteira fica constante por coluna -- e as duas metades deste teste
    passavam do jeito antigo. Crescimento ESTRITO e' diff() > 0.
    """
    d = tabelas["prefixado_pct"]
    for coluna in d.columns:
        assert (d[coluna].diff().dropna() > 0).all(), f"coluna {coluna}"
    for linha in d.index:
        assert (d.loc[linha].diff().dropna() > 0).all(), f"linha {linha}"


def test_a_celula_sai_em_BILHOES_como_o_resto_da_tabela():
    """rolagem.emissao_necessaria devolve MILHOES; a tabela le bilhoes.

    Sem esta conferencia, esquecer a divisao daria numeros mil vezes maiores --
    e a monotonicidade, que e o outro teste da matriz, continuaria passando,
    porque escalar tudo por mil nao muda a ordem.
    """
    d = simulacao.dados_simulacao("prefixado_pct", registros=[])
    linha, coluna = d.attrs["marca"]
    em_milhoes = rolagem.emissao_necessaria(
        d.attrs["indexador"], linha, coluna,
        hoje=d.attrs["hoje"], ate=d.attrs["ate"], registros=[])
    assert d.at[linha, coluna] == pytest.approx(em_milhoes / 1000, rel=1e-9)
    # E a ordem de grandeza bate com o ritmo, que tambem esta em bilhoes.
    assert abs(d.at[linha, coluna]) < 100, (
        "celula em bilhoes nao passa de dois digitos com o dado de hoje")


@pytest.fixture(scope="module")
def tabelas():
    """As tres tabelas, uma vez cada, para os testes de ancora abaixo.

    Montar as tres tabelas nao faz sentido tres vezes por atributo conferido
    quando os tres papeis cabem numa unica rodada, reaproveitada por teste --
    mesmo depois de dados_simulacao ter parado de chamar emissao_necessaria
    por celula (ver termos_da_simulacao em rolagem.py).
    """
    return {chave: simulacao.dados_simulacao(chave, registros=[])
            for chave in ("prefixado_pct", "indice_precos_pct",
                          "taxa_flutuante_pct")}


def test_dados_simulacao_bate_CELULA_A_CELULA_com_emissao_necessaria(tabelas):
    """A TRAVA desta otimizacao: os numeros nao podem mudar.

    dados_simulacao agora calcula os termos que nao dependem do alvo (estoque
    de hoje, juros ate 'ate', vencimentos e a contagem de leiloes) UMA VEZ por
    tabela, e reusa nas ~42 celulas -- em vez de chamar emissao_necessaria do
    zero em cada uma. emissao_necessaria continua existindo com a MESMA
    assinatura, e por baixo refaz esses termos sozinha, celula a celula --
    exatamente o caminho caro de antes da otimizacao.

    Comparar as duas, para TODAS as celulas das TRES tabelas, prova que
    reusar os termos nao mudou nenhum numero: se dados_simulacao vazasse um
    termo de uma tabela para outra, ou parasse de repassar 'hoje'/'ate'
    corretamente, alguma celula divergiria aqui. A igualdade e EXATA -- as
    duas contas fazem os MESMOS floats na MESMA ordem de operacoes -- e nao
    aproximada, porque uma tolerancia esconderia justamente o tipo de desvio
    minusculo que uma reordenacao de operacoes de ponto flutuante produziria.
    """
    for chave, d in tabelas.items():
        indexador = d.attrs["indexador"]
        hoje, ate = d.attrs["hoje"], d.attrs["ate"]
        for pct in d.index:
            for total in d.columns:
                esperado = rolagem.emissao_necessaria(
                    indexador, pct, total, hoje=hoje, ate=ate,
                    registros=[]) / 1000
                assert d.at[pct, total] == esperado, (chave, pct, total)


def test_o_indexador_bate_com_a_chave_pedida(tabelas):
    """O vinculo chave -> indexador, ancorado em valor concreto.

    Achado da revisao da rodada 1: o revisor forcou 'indexador' a ser sempre
    "Prefixado" e chamou dados_simulacao("indice_precos_pct", ...). Saiu uma
    tabela inteira com os numeros do prefixado, rotulada "indice de precos"
    -- porque rotulo e banda sao indexados por CHAVE e nao por indexador, e
    nada conferia que os dois concordam. Os cinco testes daquela rodada
    passaram todos.

    Comparar contra rolagem.INDEXADOR_DA_CHAVE seria tautologico: e' a mesma
    linha que dados_simulacao roda por dentro. Por isso os valores abaixo sao
    literais, escritos a mao -- feito para os TRES indexadores, nao so um.
    """
    esperado = {
        "prefixado_pct": "Prefixado",
        "indice_precos_pct": "\u00cdndice Pre\u00e7os",
        "taxa_flutuante_pct": "Taxa Flutuante",
    }
    for chave, indexador in esperado.items():
        assert tabelas[chave].attrs["indexador"] == indexador, chave


def test_a_chave_e_o_rotulo_batem_com_o_pedido(tabelas):
    """attrs['chave'] e attrs['rotulo'], contra o que foi PEDIDO.

    Nao contra o dicionario interno de simulacao (_ROTULO): se ele estivesse
    errado, ler dele para afirmar e' o mesmo bug se confirmando sozinho. Os
    valores abaixo sao literais.
    """
    esperado = {
        "prefixado_pct": "Prefixado",
        "indice_precos_pct": "\u00cdndice de pre\u00e7os",
        "taxa_flutuante_pct": "Taxa flutuante",
    }
    for chave, rotulo in esperado.items():
        assert tabelas[chave].attrs["chave"] == chave
        assert tabelas[chave].attrs["rotulo"] == rotulo, chave


def test_a_banda_bate_com_paf_bandas(tabelas):
    """A banda de cada tabela, conferida contra paf.bandas -- por fora.

    Uma banda com minimo e maximo invertidos, ou lida do ano errado, nao muda
    nenhuma celula da matriz: sem esta conferencia passaria batida.
    """
    for chave, d in tabelas.items():
        b = paf.bandas(chave).loc[d.attrs["ate"].year]
        assert d.attrs["banda"] == (float(b["minimo"]), float(b["maximo"])), chave


def test_os_leiloes_batem_com_leiloes_que_faltam(tabelas):
    """attrs['leiloes'], recontado por fora com o mesmo par (dias, indexador).

    A Task 4 usa este numero na contagem do rodape. Um leiloes_que_faltam
    chamado com o indexador errado, ou com um recorte de dias diferente do
    que a tabela usou, muda este numero sem mudar nenhuma celula da matriz.
    """
    for chave, d in tabelas.items():
        dias, _ = calendario_leiloes.dias_ate(
            d.attrs["ate"], registros=[], hoje=d.attrs["hoje"])
        esperado = rolagem.leiloes_que_faltam(dias, d.attrs["indexador"])
        assert d.attrs["leiloes"] == esperado, chave


def test_busca_calendario_uma_unica_vez_por_TABELA(monkeypatch):
    """A corre\u00e7\u00e3o resolveu registros UMA VEZ por chamada de dados_simulacao
    e repassou -- e' isso, e s\u00f3 isso, que este teste trava.

    NOME ANTERIOR PROMETIA MAIS DO QUE ENTREGAVA (achado da revis\u00e3o): dizia
    "por_pagina", mas s\u00f3 chama dados_simulacao UMA vez -- uma TABELA, e n\u00e3o
    a p\u00e1gina inteira. Medido: painel_paf.grava(registros=None) faz QUATRO
    buscas por p\u00e1gina -- uma de banda.dados_projecao (o bloco da proje\u00e7\u00e3o)
    e uma por TABELA da simula\u00e7\u00e3o (tr\u00eas: prefixado, \u00edndice de pre\u00e7os,
    taxa flutuante), porque cada tabela resolve o calend\u00e1rio por conta
    pr\u00f3pria dentro de dados_simulacao. Quatro e' \u00f3timo -- eram cem+ antes
    desta otimiza\u00e7\u00e3o -- mas n\u00e3o e' UMA, e um teste chamado "_por_pagina"
    que s\u00f3 exercita uma tabela n\u00e3o prova a p\u00e1gina inteira.

    dados_simulacao com registros=None e' o caminho de produ\u00e7\u00e3o. Antes,
    cada c\u00e9lula chamava emissao_necessaria -> dias_ate -> buscar("calendario")
    na API do Tesouro. Com ~40 c\u00e9lulas x 3 tabelas, eram cem+ buscas
    id\u00eanticas para uma p\u00e1gina.

    A corre\u00e7\u00e3o mudou o CUSTO, n\u00e3o o resultado: a mesma lista que cada
    um buscaria sozinho. Logo nenhum teste de VALOR a protege. Sem este teste
    de contagem, um refactor futuro volta a buscar por c\u00e9lula em sil\u00eancio.
    """
    chamadas = []

    def mock_buscar(nome, timeout=None):
        chamadas.append(nome)
        return [], b""

    monkeypatch.setattr(api_leiloes, "buscar", mock_buscar)
    simulacao.dados_simulacao("prefixado_pct")
    assert len(chamadas) <= 1, (
        f"registros=None deve buscar no m\u00e1ximo uma vez; "
        f"foram {len(chamadas)} chamadas")


def test_a_tabela_marca_a_celula_do_projetado():
    """I3: a celula marcada nao pode perder o alinhamento numerico.

    'class=\"n\"' e' quem carrega text-align:right e tabular-nums; a unica
    celula que o bloco existe para apontar nao pode ser a unica desalinhada
    da grade. A marca tem de vir JUNTO com 'n', nao no lugar dela.
    """
    d = simulacao.dados_simulacao("prefixado_pct", registros=[])
    html = simulacao.tabela(d)
    assert html.count('class="n marca"') == 1, (
        "exatamente uma celula, alinhada E marcada, e' a do projetado")
    # Nenhuma celula leva 'marca' sozinha, sem o alinhamento numerico -- essa
    # grafia so aparece dentro de 'class=\"n marca\"', contada acima.
    assert html.count('class="marca"') == 0


def test_a_tabela_pinta_o_negativo_de_vermelho_com_o_sinal():
    """Decisao dela: so o numero em vermelho, com o menos na frente.

    Sem icone, sem hachura, sem palavra. A magnitude e a informacao.
    """
    d = simulacao.dados_simulacao("taxa_flutuante_pct", registros=[])
    html = simulacao.tabela(d)
    negativas = (d < 0).sum().sum()
    assert negativas > 0, "a taxa flutuante tem de ter celula negativa hoje"
    assert html.count('class="negativo"') == negativas
    assert "-" in html
    # E nada de palavra no lugar do numero.
    assert "impossivel" not in html.lower()


def test_o_rodape_avisa_que_as_TRES_TABELAS_sao_independentes():
    """Spec 2: o custo da escolha dela precisa estar escrito.

    Tres tabelas independentes e a forma mais legivel, e ela escolheu sabendo
    do preco: elas nao sao necessariamente compativeis entre si. Ler "prefixado
    22% pede X" e "indice de precos 25% pede Y" e fazer as duas coisas pode nao
    dar o total escolhido.

    Isso nao aparece em nenhum numero da tela -- so no texto. Se sair do texto,
    some.
    """
    d = simulacao.dados_simulacao("prefixado_pct", registros=[])
    html = simulacao.tabela(d)
    assert "independentes" in html
    assert "total escolhido" in html


def test_a_tabela_marca_as_linhas_da_BANDA():
    d = simulacao.dados_simulacao("prefixado_pct", registros=[])
    html = simulacao.tabela(d)
    lo, hi = d.attrs["banda"]
    dentro = [x for x in d.index if lo <= x <= hi]
    assert html.count('class="na-banda"') == len(dentro)


def test_o_rodape_separa_o_RITMO_ATUAL_da_celula_marcada():
    """A armadilha de \u00a76.1 da spec, travada no texto.

    A celula marcada nao e o ritmo atual, e no indice de precos a diferenca e de
    sete vezes. O rodape tem de trazer o ritmo em numero, separado, com essas
    palavras -- senao a pagina mente sem errar uma conta.
    """
    d = simulacao.dados_simulacao("indice_precos_pct", registros=[])
    html = simulacao.tabela(d)
    assert "ritmo de hoje" in html
    assert simulacao._numero_br(d.attrs["ritmo_atual"]) in html


def test_o_rodape_amarra_o_VALOR_da_celula_as_COORDENADAS_DELA(tabelas):
    """C1, achado da revisao: o rodape amarrava o valor da celula as
    coordenadas ERRADAS.

    Medido: a celula estava em 22% de R$ 9.900 bi e valia 0,30, mas o texto
    dizia "...(22,18% de R$ 9.947 bi) -- e nao o que se emite hoje, que e de
    R$ 2,04 bi..." -- lido ao pe da letra, afirmava que 0,30 e' "22,18% de
    9.947", que e' falso: aquele parentese descreve o PONTO PROJETADO exato,
    que cai fora da grade, e nao a celula destacada.

    DESDE 08/09/2026 OS DOIS PARES DE COORDENADAS VIRARAM UM SO: o ponto
    exato entrou na grade, entao a celula marcada esta EM (projetado_pct,
    projetado_total) e nao mais no vizinho arredondado. O defeito que este
    teste guarda nao sumiu com isso -- so deixou de ter duas coordenadas para
    confundir. O que ele exige continua sendo: o valor que o rodape anuncia
    tem de estar junto das coordenadas a que o rodape o atribui.

    A JANELA E DENTRO DO RODAPE, e nao no HTML inteiro: a tabela acima repete
    esses mesmos numeros nos rotulos, e procurar solto bateria por acidente.
    """
    for chave, d in tabelas.items():
        html = simulacao.tabela(d)
        rodape = html[html.index('<p class="rodape">'):]
        marca_linha, marca_coluna = d.attrs["marca"]
        valor = simulacao._numero_br(d.at[marca_linha, marca_coluna])

        coord = (f"{simulacao._numero_br(d.attrs['projetado_pct'])}% de R$ "
                 f"{simulacao._numero_br(d.attrs['projetado_total'], 0)} bi")
        assert coord in rodape, (
            f"{chave}: as coordenadas do ponto de hoje tem de aparecer no "
            f"rodape")

        pos = rodape.index(coord)
        assert valor in rodape[pos:pos + 220], (
            f"{chave}: o valor da celula ({valor}) tem de estar junto das "
            f"coordenadas dela ({coord}), e nao solto no rodape")


def test_o_rodape_declara_a_PREMISSA_de_juros():
    """I1: toda celula usa uma taxa de juros (Selic implicita, inflacao
    implicita + cupom real, ou a carga do prefixado) -- rolagem.py trava a
    regra: numero projetado sem a premissa ao lado e opiniao com cara de
    medida. O bloco irmao (a projecao) ja declara a dele; este bloco, por
    ser recolhivel INDEPENDENTE -- da para abrir so a simulacao -- tinha de
    declarar a dele tambem.
    """
    d = simulacao.dados_simulacao("taxa_flutuante_pct", registros=[])
    html = simulacao.tabela(d)
    assert "selic" in d.attrs and "inflacao" in d.attrs
    assert "data_da_curva" in d.attrs
    assert simulacao._numero_br(100 * d.attrs["selic"]) in html
    assert simulacao._numero_br(100 * d.attrs["inflacao"]) in html
    assert f"{d.attrs['data_da_curva']:%d/%m/%Y}" in html


def test_o_rodape_diz_se_o_CALENDARIO_e_publicado_ou_estimado():
    """C2, achado da revisao: com o calendario vazio (tudo estimado) a
    secao da simulacao saia byte a byte identica a com calendario publicado
    -- enquanto o bloco irmao (a projecao), na mesma pagina, confessa "de
    calendario publicado ate DD/MM" ou "inteiramente estimado". Regressao do
    proprio padrao da pagina: o bloco irmao confessa, este nao confessava.
    """
    d = simulacao.dados_simulacao("prefixado_pct", registros=[])
    assert d.attrs["fronteira_do_calendario"] is None, (
        "com registros=[] nao ha calendario publicado")
    html = simulacao.tabela(d)
    rodape = html[html.index('class="rodape"'):]
    assert "estimado" in rodape


def test_a_celula_marcada_E_o_ritmo_de_hoje():
    """A identidade que a linha e a coluna exatas criam.

    Com a grade so em passos inteiros, a celula marcada era a mais PROXIMA do
    ponto projetado, e nao ele -- e a diferenca chegava a 63% no indice de
    precos (4,87 contra 2,04 bi por leilao, medido em 08/09/2026). Com o ponto
    exato dentro da grade, a celula marcada passa a responder pelo ritmo de
    hoje, e a tabela se explica sozinha.

    NAO E TAUTOLOGIA: o valor da celula vem de emissao_a_partir_dos_termos, que
    INVERTE a conta -- dado o alvo, quanto emitir. O ritmo vem de rolagem.pace,
    que le os ultimos leiloes. Que os dois coincidam e afirmacao sobre o motor,
    e quebrar a inversao deixa este teste vermelho.
    """
    hoje = pd.Timestamp("2026-08-26")
    for chave in rolagem.INDEXADOR_DA_CHAVE:
        d = simulacao.dados_simulacao(chave, hoje=hoje, registros=[])
        linha, coluna = d.attrs["marca"]
        assert d.at[linha, coluna] == pytest.approx(
            d.attrs["ritmo_atual"], abs=0.01), (
            "%s: a celula marcada da %.3f e o ritmo de hoje e %.3f"
            % (chave, d.at[linha, coluna], d.attrs["ritmo_atual"]))


def test_a_linha_de_hoje_sai_com_DUAS_CASAS_e_as_da_grade_com_zero():
    """22,52% nao pode virar 23% no rotulo.

    A linha existe justamente porque 22,52 e 23 pedem emissoes muito
    diferentes; escreve-la arredondada desfaria o motivo de ela existir.

    ROTULO DERIVADO, e nao numero cravado: o teste monta o rotulo esperado a
    partir da propria marca, entao ele nao envelhece a cada RMD -- so quebra se
    a formatacao mudar.
    """
    d = simulacao.dados_simulacao("indice_precos_pct",
                                  hoje=pd.Timestamp("2026-08-26"),
                                  registros=[])
    html = simulacao.tabela(d)
    exato = d.attrs["marca"][0]
    assert f">{simulacao._numero_br(exato, 2)}%<" in html, (
        "a linha de hoje tem de sair com duas casas")
    outra = next(x for x in d.index if x != exato)
    assert f">{simulacao._numero_br(outra, 0)}%<" in html, (
        "as linhas da grade continuam sem casa decimal")


def test_a_linha_e_a_coluna_de_hoje_ficam_MARCADAS_na_tabela():
    """Quem le tem de ver que aquelas duas nao sao da grade regular."""
    d = simulacao.dados_simulacao("indice_precos_pct",
                                  hoje=pd.Timestamp("2026-08-26"),
                                  registros=[])
    html = simulacao.tabela(d)
    assert 'class="pct hoje"' in html, "a linha de hoje precisa da marca"
    assert 'class="n hoje"' in html, "a coluna de hoje precisa da marca"


def test_o_rodape_NAO_diz_MAIS_que_a_celula_difere_do_ritmo():
    """A ressalva do arredondamento morreu com a linha exata.

    Enquanto a celula marcada era a vizinha da grade, o rodape precisava
    avisar que ela NAO era o que se emite hoje. Agora ela e -- e manter o aviso
    seria a pagina desmentindo a propria tabela.
    """
    d = simulacao.dados_simulacao("indice_precos_pct",
                                  hoje=pd.Timestamp("2026-08-26"),
                                  registros=[])
    html = simulacao.tabela(d)
    assert "a grade arredonda" not in html, (
        "a ressalva do arredondamento nao vale mais")
