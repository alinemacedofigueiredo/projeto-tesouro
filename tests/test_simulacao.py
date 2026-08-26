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
    """O caso da taxa flutuante: banda 46-50, projetado 53,24%.

    A versao anterior da spec fixava a grade e nao marcava nada quando o
    projetado caia fora -- deixando justamente a tabela do indicador FORA da
    banda, que e a mais interessante, sem a marca do ritmo atual.
    """
    linhas, _ = simulacao.eixos("taxa_flutuante_pct", 53.24, 9947, 2026)
    assert max(linhas) >= 54, f"53,24% tem de caber; linhas foram {linhas}"
    assert min(linhas) <= 45, "a banda 46-50 continua tendo de caber"


def test_os_eixos_tem_passo_regular():
    linhas, colunas = simulacao.eixos("prefixado_pct", 21.10, 9947, 2026)
    assert all(b - a == 1 for a, b in zip(linhas, linhas[1:]))
    assert all(b - a == simulacao.PASSO_TOTAL
               for a, b in zip(colunas, colunas[1:]))


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
    """Arredondando CADA EIXO ao ponto mais proximo da sua grade,
    independentemente do outro -- e nao a menor distancia no plano, que
    exigiria comparar pontos percentuais com bilhoes de reais.
    """
    d = simulacao.dados_simulacao("prefixado_pct", registros=[])
    linha, coluna = d.attrs["marca"]
    assert abs(linha - d.attrs["projetado_pct"]) <= 0.5
    assert abs(coluna - d.attrs["projetado_total"]) <= simulacao.PASSO_TOTAL / 2
    assert linha in d.index and coluna in d.columns


def test_a_celula_marcada_NAO_e_o_ritmo_atual():
    """A armadilha desta pagina, medida em 26/08/2026.

    A celula marcada mostra quanto emitir para cair no ponto ARREDONDADO da
    grade -- nao o que se emite hoje. No indice de precos a celula marcada da
    0,3 contra um ritmo de 2,04: SETE VEZES. Quem ler a marca como "o que
    emitimos hoje" sai com um numero muito errado, sem que nenhuma conta esteja
    errada.

    Este teste nao exige que os dois sejam diferentes -- eles podem coincidir
    por sorte. Exige que os dois ESTEJAM DISPONIVEIS separadamente, para a
    tabela poder mostrar cada um no seu lugar.
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


def test_busca_calendario_uma_unica_vez_por_pagina(monkeypatch):
    """A corre\u00e7\u00e3o resolveu registros UMA VEZ no topo e repassou.

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
    d = simulacao.dados_simulacao("prefixado_pct", registros=[])
    html = simulacao.tabela(d)
    assert html.count('class="marca"') == 1, (
        "exatamente uma celula e a do projetado")


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
    assert "para c\u00e1 leva" in html or "leva o ritmo" in html
