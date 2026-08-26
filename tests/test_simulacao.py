"""A simulacao: quanto emitir por leilao para chegar a cada alvo."""
import pandas as pd
import pytest

from tesouro import rolagem
from tesouro.graficos import simulacao


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


def test_a_matriz_cresce_nos_dois_eixos():
    d = simulacao.dados_simulacao("prefixado_pct", registros=[])
    for coluna in d.columns:
        serie = d[coluna]
        assert serie.is_monotonic_increasing, f"coluna {coluna}"
    for linha in d.index:
        assert d.loc[linha].is_monotonic_increasing, f"linha {linha}"


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
