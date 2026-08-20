import datetime
from pathlib import Path

import pytest
from tesouro import leitura_rmd
from tesouro.parse_rmd import estoque, vencimentos

AMOSTRA = Path(__file__).parent / "fixtures" / "rmd_amostra.xlsx"


RMD_REAL = Path(__file__).parents[1] / "data" / "raw" / "rmd"


@pytest.fixture(scope="module")
def xl():
    return leitura_rmd.abrir(AMOSTRA)


@pytest.fixture(scope="module")
def xl_real():
    """O anexo completo, quando presente. Mesmo padrao de test_coerencia.py."""
    if not RMD_REAL.exists() or not list(RMD_REAL.glob("*.xlsx")):
        pytest.skip(
            "teste de integracao: exige o anexo do RMD em data/raw/rmd/ "
            "(veja docs/como-baixar.md)"
        )
    return leitura_rmd.abrir()


def test_faixa_tem_as_colunas_canonicas(xl):
    df = vencimentos.parse_por_faixa(xl)
    assert list(df.columns) == ["data", "nivel", "faixa", "valor_milhoes"]


def test_faixa_cobre_as_seis_faixas(xl):
    df = vencimentos.parse_por_faixa(xl)
    faixas = set(df["faixa"].unique())
    assert "At\u00e9 12 meses" in faixas
    assert "Acima de 5 anos" in faixas


def test_faixa_separa_os_tres_blocos_empilhados(xl):
    # A aba 3.1 traz DPF, DPMFi e DPFe um abaixo do outro, cada um com a
    # serie completa. Lidos juntos, cada data apareceria tres vezes sem
    # nada dizendo a qual serie pertence.
    df = vencimentos.parse_por_faixa(xl)
    assert set(df["nivel"].unique()) == {"DPF", "DPMFi", "DPFe"}
    assert not df.duplicated(subset=["data", "nivel", "faixa"]).any()


def test_faixa_dpf_e_maior_que_dpmfi(xl):
    # DPF = DPMFi + DPFe, entao o total tem de ser maior que a parte --
    # mas so dentro do periodo em que os tres niveis tem dado. A serie de
    # DPMFi comeca em 1999, quase sete anos antes da de DPF (N/D ate
    # 2006), entao somar o historico inteiro de cada nivel compararia
    # janelas de tamanhos diferentes e poderia inverter o resultado sem
    # que os blocos tivessem se misturado. Restringir ao periodo em que
    # DPF tem dado real elimina esse efeito.
    df = vencimentos.parse_por_faixa(xl)
    dpf = df[df["nivel"] == "DPF"]
    primeira_data_com_dado = dpf.loc[dpf["valor_milhoes"].notna(), "data"].min()
    comparavel = df[df["data"] >= primeira_data_com_dado]
    por_nivel = comparavel.groupby("nivel")["valor_milhoes"].sum()
    assert por_nivel["DPF"] > por_nivel["DPMFi"] > 0


def test_faixa_trata_nd_como_ausente(xl):
    df = vencimentos.parse_por_faixa(xl)
    assert df["valor_milhoes"].isna().any()


def test_faixa_nao_grava_o_total_derivado(xl):
    # A aba 3.1 traz 'Total' como se fosse mais uma faixa de prazo, na
    # ultima posicao de cada bloco. Se o filtro sumisse, quem somasse as
    # faixas para conferir o total contaria tudo em dobro.
    df = vencimentos.parse_por_faixa(xl)
    faixas = {f.lower() for f in df["faixa"].unique()}
    assert "total" not in faixas
    assert "part %" not in faixas


def test_a_vencer_12m_tem_indexadores(xl):
    df = vencimentos.parse_a_vencer_12m(xl)
    assert list(df.columns) == ["data", "indexador", "valor_milhoes"]
    assert "Prefixado" in set(df["indexador"].unique())


def test_a_vencer_12m_nao_grava_o_total_derivado(xl):
    df = vencimentos.parse_a_vencer_12m(xl)
    indexadores = {i.lower() for i in df["indexador"].unique()}
    assert "total" not in indexadores
    assert "part %" not in indexadores


def test_cronograma_usa_data_de_referencia_e_nao_data(xl):
    # E retrato, nao serie: carrega a data de fechamento do RMD.
    df = vencimentos.parse_cronograma(xl)
    assert list(df.columns) == [
        "data_referencia", "mes_vencimento", "grupo_titulo", "valor_milhoes",
        "faixa",
    ]
    assert df["data_referencia"].nunique() == 1
    assert df["data_referencia"].iloc[0] == datetime.date(2026, 6, 30)


def test_cronograma_olha_para_frente(xl):
    # So as linhas mensais tem mes: o balde "Apos 5 anos" agrega tudo o que vence
    # depois dos 60 meses detalhados, e por isso nasce sem mes_vencimento.
    df = vencimentos.parse_cronograma(xl)
    mensal = df[df["faixa"] == "mensal"]
    assert (mensal["mes_vencimento"] > mensal["data_referencia"]).all()


def test_cronograma_nao_grava_o_percentual_derivado(xl):
    df = vencimentos.parse_cronograma(xl)
    assert "PART %" not in set(df["grupo_titulo"].unique())


def test_cronograma_traz_o_balde_de_apos_5_anos(xl):
    # A aba 3.4 detalha 60 meses e joga o resto num balde unico. Sem ele, o CSV
    # soma 78% do estoque e quem usa nao percebe.
    #
    # Chama o PARSER, e nao le o CSV gravado: a primeira versao deste teste lia
    # data/processed/cronograma_vencimentos.csv, entao apagar o bloco do balde do
    # parser a deixava verde ate alguem rodar o pipeline -- e num clone novo ela
    # falhava com FileNotFoundError, porque data/ e ignorado pelo git.
    d = vencimentos.parse_cronograma(xl)

    detalhado = d[d["faixa"] == "mensal"]
    balde = d[d["faixa"] == "apos_5_anos"]

    assert len(balde) > 0, "o balde 'Apos 5 anos' nao foi capturado"
    assert balde["mes_vencimento"].isna().all(),         "o balde nao tem mes; ele agrega tudo depois de 5 anos"

    assert round(detalhado["valor_milhoes"].sum() / 1000, 1) == 6913.8
    assert round(balde["valor_milhoes"].sum() / 1000, 1) == 2006.9
    assert round(d["valor_milhoes"].sum() / 1000, 1) == 8920.7


def test_sem_a_linha_do_balde_o_parser_levanta(xl, monkeypatch):
    # A guarda que impede o CSV de sair com 78% do estoque em silencio. Aqui ela e
    # exercitada de verdade: sem esta assercao, apagar o LookupError nao quebra nada.
    def sem_balde(bruto, linha_cabecalho):
        raise LookupError(
            "aba 3.4: linha 'Apos 5 anos' nao encontrada. Ela existe desde que "
            "acompanhamos a aba, e sem ela o CSV soma so os 60 meses detalhados."
        )

    monkeypatch.setattr(vencimentos, "_linha_do_balde", sem_balde)
    with pytest.raises(LookupError) as erro:
        vencimentos.parse_cronograma(xl)
    assert "Apos 5 anos" in str(erro.value)


def test_duas_linhas_de_apos_5_anos_levantam(xl):
    # Se o RMD acrescentar uma linha "Apos 5 anos (Part %)" acima da de valores,
    # ler a primeira daria percentual no lugar de R$ milhoes -- numero pequeno,
    # plausivel e errado, sem nada levantar. A guarda exige rotulo unico.
    from tesouro.leitura_rmd import aba

    bruto = aba(xl, "3.4").copy()
    linha_cabecalho = vencimentos._linha_do_cabecalho(bruto)
    original = vencimentos._linha_do_balde(bruto, linha_cabecalho)

    bruto.iloc[original - 1, 0] = "Ap\u00f3s 5 anos (Part %)"
    with pytest.raises(LookupError) as erro:
        vencimentos._linha_do_balde(bruto, linha_cabecalho)
    assert "2 vezes" in str(erro.value)


def test_o_total_do_cronograma_bate_com_o_estoque_do_dpmfi(xl_real):
    # Cruzamento contra fonte independente: a aba 3.4 e a 2.7 sao interpretadas por
    # parsers diferentes e tem de dar o mesmo estoque. So faz sentido sobre o anexo
    # inteiro -- na amostra recortada a 2.7 nao vem completa.
    cr = vencimentos.parse_cronograma(xl_real)
    det = estoque.parse_detentores(xl_real)
    ultimo = det[det["data"] == det["data"].max()]["valor_milhoes"].sum()

    assert abs(cr["valor_milhoes"].sum() - ultimo) / ultimo < 0.0001
