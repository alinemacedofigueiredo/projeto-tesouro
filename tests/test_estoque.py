import datetime
from pathlib import Path

import pytest
from tesouro import leitura_rmd
from tesouro.parse_rmd import estoque

AMOSTRA = Path(__file__).parent / "fixtures" / "rmd_amostra.xlsx"


@pytest.fixture(scope="module")
def xl():
    return leitura_rmd.abrir(AMOSTRA)


def test_estoque_dpf_tem_as_colunas_canonicas(xl):
    df = estoque.parse_dpf(xl)
    assert list(df.columns) == [
        "data", "nivel", "entidade", "titulo", "valor_milhoes"
    ]


def test_estoque_dpf_marca_a_linha_em_poder_do_publico(xl):
    # E a linha que o PAF bandeia; precisa ser distinguivel das demais.
    df = estoque.parse_dpf(xl)
    assert (df["nivel"] == "DPF em poder do publico").any()


def test_estoque_dpf_separa_tesouro_de_banco_central(xl):
    df = estoque.parse_dpf(xl)
    entidades = set(df["entidade"].dropna().unique())
    assert "Tesouro Nacional" in entidades
    assert "Banco Central" in entidades


def test_estoque_dpf_converte_bilhoes_para_milhoes(xl):
    df = estoque.parse_dpf(xl)
    publico = df[
        (df["nivel"] == "DPF em poder do publico")
        & (df["data"] == datetime.date(2000, 12, 31))
    ]
    # 653,559 bilhoes = 653.559 milhoes
    assert publico["valor_milhoes"].iloc[0] == pytest.approx(653559.07, abs=1.0)


def test_composicao_tem_os_indexadores(xl):
    df = estoque.parse_composicao(xl)
    assert list(df.columns) == ["data", "indexador", "valor_milhoes"]
    assert {"Prefixado", "Taxa Flutuante", "C\u00e2mbio"} <= set(df["indexador"])


def test_composicao_nao_grava_o_percentual_derivado(xl):
    df = estoque.parse_composicao(xl)
    # Se o percentual tivesse vazado, haveria valores menores que 1.
    assert (df["valor_milhoes"].dropna() > 1.0).all()


def test_detentores_tem_as_colunas_canonicas(xl):
    df = estoque.parse_detentores(xl)
    assert list(df.columns) == ["data", "detentor", "valor_milhoes"]
    assert len(df) > 0


def test_detentores_por_titulo_preserva_o_bloco_do_titulo(xl):
    df = estoque.parse_detentores_por_titulo(xl)
    assert list(df.columns) == ["data", "detentor", "titulo", "valor_milhoes"]
    assert "LFT" in set(df["titulo"].unique())


def test_detentores_por_titulo_atravessa_mais_de_um_bloco(xl):
    # Os blocos ficam a ~189 linhas um do outro. Se a deteccao de bloco
    # falhar, so o primeiro titulo aparece -- e o teste acima passaria
    # mesmo assim.
    df = estoque.parse_detentores_por_titulo(xl)
    assert {"LFT", "LTN"} <= set(df["titulo"].unique())


def test_detentores_por_titulo_nao_perde_os_meses_retificados(xl):
    # 'mar/18*' e 'abr/18*' vem como texto no meio do bloco. Tratados como
    # rotulo de titulo, zerariam os detentores e as ~100 linhas seguintes
    # do bloco sumiriam sem erro nenhum.
    df = estoque.parse_detentores_por_titulo(xl)
    do_lft = df[df["titulo"] == "LFT"]
    assert datetime.date(2018, 3, 31) in set(do_lft["data"])
    assert datetime.date(2018, 4, 30) in set(do_lft["data"])
    # e o bloco continua depois deles
    assert (do_lft["data"] > datetime.date(2018, 4, 30)).any()


def test_detentores_por_titulo_ignora_o_rodape_de_asterisco(xl):
    # A ultima linha da aba comeca com '*' e explica a retificacao.
    df = estoque.parse_detentores_por_titulo(xl)
    assert not any(str(t).startswith("*") for t in df["titulo"].unique())


# Regressao dos consertos que o implementador anterior encontrou sozinho,
# revisando contra o arquivo real (nenhum tinha teste antes desta tarefa).


def test_estoque_dpf_resolve_demais_por_linha_nao_por_rotulo(xl):
    # 'Demais' se repete tres vezes na aba 2.1: sob Tesouro Nacional, sob
    # Divida Mobiliaria (DPFe) e sob o memo de DPMFi no Banco Central. Se
    # a hierarquia fosse indexada pelo texto do rotulo (drop_duplicates
    # por 'rotulo'), as tres colapsariam na primeira encontrada e as
    # outras duas herdariam o papel dela -- plausivel e errado, sem erro
    # nenhum.
    df = estoque.parse_dpf(xl)
    demais = df[df["titulo"] == "Demais"]

    combinacoes = demais[["nivel", "entidade"]].drop_duplicates()
    assert len(combinacoes) == 3

    chaves = set(demais[["data", "nivel", "entidade", "titulo"]].apply(tuple, axis=1))
    assert len(chaves) == len(demais)


def test_estoque_dpf_nao_grava_nota_de_rodape_como_titulo(xl):
    # O fim da aba 2.1 traz notas de rodape em linhas soltas, sem valor em
    # nenhuma coluna de mes. Sem o filtro, elas caem no mesmo ramo que um
    # titulo de verdade e ficam gravadas com valor_milhoes nulo em toda a
    # serie -- o traco que distingue nota de rodape de titulo legitimo.
    df = estoque.parse_dpf(xl)
    por_titulo = df[df["titulo"].notna()].groupby(
        ["nivel", "entidade", "titulo"], dropna=False
    )["valor_milhoes"]
    sem_dado_algum = por_titulo.apply(lambda serie: serie.isna().all())
    assert not sem_dado_algum.any()


def test_estoque_dpf_tem_nivel_dpmfi_no_banco_central(xl):
    # Depois do bloco de DPFe, a aba 2.1 tem uma quinta secao memorando a
    # composicao por titulo do que o Banco Central detem de DPMFi. Sem
    # reconhecer o cabecalho dela, essas linhas sao absorvidas (erradas)
    # pelo nivel DPFe, que estava ativo por ultimo.
    df = estoque.parse_dpf(xl)
    bloco = df[df["nivel"] == "DPMFi em poder do Banco Central"]
    assert len(bloco) > 0
    assert bloco["valor_milhoes"].notna().any()


def test_detentores_e_detentores_por_titulo_nao_gravam_a_coluna_total(xl):
    # 2.7 e 2.8 trazem uma coluna 'Total', soma dos demais detentores da
    # mesma linha -- derivada, e o projeto proibe gravar derivado.
    detentores = estoque.parse_detentores(xl)
    assert "Total" not in set(detentores["detentor"].unique())

    por_titulo = estoque.parse_detentores_por_titulo(xl)
    assert "Total" not in set(por_titulo["detentor"].unique())


def test_estoque_dpf_divida_mobiliaria_e_contratual_sao_entidade(xl):
    # 'Divida Mobiliaria' e 'Divida Contratual' sao cabecalhos de subgrupo
    # dentro de DPFe: a celula deles traz o subtotal exato da soma dos
    # titulos logo abaixo. Gravados como titulo (folha), um consumidor
    # que agrupe por nivel e some valor_milhoes sobre titulo.notna()
    # conta a divida externa em dobro.
    df = estoque.parse_dpf(xl)

    entidades = set(df["entidade"].dropna().unique())
    assert "D\u00edvida Mobili\u00e1ria" in entidades
    assert "D\u00edvida Contratual" in entidades

    titulos = set(df["titulo"].dropna().unique())
    assert "D\u00edvida Mobili\u00e1ria" not in titulos
    assert "D\u00edvida Contratual" not in titulos

    # A soma dos titulos de cada entidade bate com o valor que estava no
    # cabecalho na planilha -- prova de que nada foi perdido nem somado
    # em dobro pela mudanca.
    data = datetime.date(2000, 12, 31)
    for entidade in ("D\u00edvida Mobili\u00e1ria", "D\u00edvida Contratual"):
        bloco = df[(df["data"] == data) & (df["entidade"] == entidade)]
        marcador = bloco[bloco["titulo"].isna()]["valor_milhoes"].iloc[0]
        soma_filhos = bloco[bloco["titulo"].notna()]["valor_milhoes"].sum()
        assert soma_filhos == pytest.approx(marcador, abs=0.01)
