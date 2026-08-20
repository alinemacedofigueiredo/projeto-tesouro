from datetime import date

import pandas as pd
import pytest
from tesouro import calendario, parse_bloomberg

CAL = calendario.padrao()


@pytest.fixture(scope="module")
def taxas():
    return parse_bloomberg.parse_taxas()


@pytest.fixture(scope="module")
def vna():
    return parse_bloomberg.parse_vna()


# ---------------------------------------------------------------------------
# Testes da especificacao original da Tarefa 3
# ---------------------------------------------------------------------------

def test_taxas_tem_as_colunas_canonicas(taxas):
    assert list(taxas.columns) == ["data", "isin", "titulo", "vencimento", "taxa_pct"]
    assert len(taxas) > 8000


def test_taxa_fica_em_percentual(taxas):
    # Convencao do projeto: 13.5 significa 13,5%.
    prefixados = taxas[taxas["titulo"] == "LTN"]["taxa_pct"]
    assert prefixados.median() > 5
    assert prefixados.median() < 20


def test_agio_da_lft_e_pequeno_e_pode_ser_negativo(taxas):
    lft = taxas[taxas["titulo"] == "LFT"]["taxa_pct"]
    assert lft.abs().median() < 1
    assert (lft < 0).any()


def test_datas_sao_dia_util(taxas, vna):
    # Cobre a coluna inteira, nao so um recorte -- o bruto real tem 272
    # linhas de taxa em datas nao-uteis (vesperas de feriado movel que a
    # Bloomberg conta diferente da Anbima), espalhadas de 2013 a 2024, e
    # um recorte pelo inicio da serie nunca as alcancaria.
    assert all(CAL.eh_dia_util(d) for d in taxas["data"])
    assert all(CAL.eh_dia_util(d) for d in vna["data"])


def test_vna_tem_as_colunas_canonicas(vna):
    assert list(vna.columns) == ["data", "indice", "vna"]
    assert set(vna["indice"].unique()) == {"IPCA", "SELIC"}


def test_vna_da_selic_nunca_cai(vna):
    # A Selic acumula sempre; queda indica erro de leitura.
    s = vna[vna["indice"] == "SELIC"].sort_values("data")["vna"]
    assert (s.diff().dropna() >= 0).all()


def test_vna_do_ipca_cai_em_meses_de_deflacao(vna):
    i = vna[vna["indice"] == "IPCA"].sort_values("data")["vna"]
    assert (i.diff().dropna() < 0).any()


def test_vna_em_ordem_de_grandeza_de_reais(vna):
    ult = vna[vna["data"] == vna["data"].max()].set_index("indice")["vna"]
    assert 4000 < ult["IPCA"] < 6000
    assert 15000 < ult["SELIC"] < 25000


def test_nao_ha_chave_duplicada(taxas, vna):
    assert not taxas.duplicated(subset=["data", "isin"]).any()
    assert not vna.duplicated(subset=["data", "indice"]).any()


# ---------------------------------------------------------------------------
# Helpers para as fixtures sinteticas abaixo, que exercitam parse_taxas() e
# parse_vna() com caminho=tmp_path -- isolado do bruto real.
# ---------------------------------------------------------------------------

def _escrever_taxas(diretorio, nome, linhas):
    caminho = diretorio / nome
    pd.DataFrame(
        linhas, columns=["isin", "titulo", "vencimento", "data", "yld_ytm_mid"]
    ).to_csv(caminho, index=False)
    return caminho


def _escrever_vna(diretorio, nome, linhas):
    caminho = diretorio / nome
    pd.DataFrame(
        linhas,
        columns=["data", "indice", "campo", "fator", "vna", "n_papeis", "divergencia"],
    ).to_csv(caminho, index=False)
    return caminho


# ---------------------------------------------------------------------------
# C1 -- a normalizacao de data e carga viva nos dois lados, com fixture
# sintetica provando o valor exato da conversao (nao so "e dia util").
# ---------------------------------------------------------------------------

def test_normaliza_ultimo_dia_corrido_para_ultimo_dia_util(tmp_path):
    bruta = date(2023, 12, 31)  # domingo
    esperado = CAL.ultimo_dia_util_do_mes(bruta)
    assert esperado != bruta  # confirma que o mes escolhido exercita a normalizacao
    assert esperado == date(2023, 12, 29)

    _escrever_taxas(
        tmp_path,
        "bbg_taxas_ANDE_2023-12_2023-12.csv",
        [("BRSTNCLTN000", "LTN", "2024-06-01", str(bruta), 12.0)],
    )
    _escrever_vna(
        tmp_path,
        "bbg_vna_2023-12_2023-12.csv",
        [
            (str(bruta), "IPCA", "IDX_RATIO", 4.0, 4000.0, 3, 0.0),
            (str(bruta), "SELIC", "ACCUMULATED_SELIC", 15.0, 15000.0, 3, 0.0),
        ],
    )

    t = parse_bloomberg.parse_taxas(caminho=tmp_path)
    v = parse_bloomberg.parse_vna(caminho=tmp_path)

    assert set(t["data"]) == {esperado}
    assert set(v["data"]) == {esperado}


# ---------------------------------------------------------------------------
# I1 -- divergencia, n_papeis (via header) e campo<->indice conferidos.
# ---------------------------------------------------------------------------

def test_vna_com_campo_trocado_levanta_erro(tmp_path):
    _escrever_vna(
        tmp_path,
        "bbg_vna_2023-01_2023-01.csv",
        [
            # campo de SELIC atribuido ao indice IPCA
            ("2023-01-31", "IPCA", "ACCUMULATED_SELIC", 4.0, 4000.0, 3, 0.0),
            ("2023-01-31", "SELIC", "ACCUMULATED_SELIC", 15.0, 15000.0, 3, 0.0),
        ],
    )
    with pytest.raises(ValueError):
        parse_bloomberg.parse_vna(caminho=tmp_path)


def test_vna_com_divergencia_grande_levanta_erro(tmp_path):
    _escrever_vna(
        tmp_path,
        "bbg_vna_2023-01_2023-01.csv",
        [
            ("2023-01-31", "IPCA", "IDX_RATIO", 4.0, 4000.0, 3, 120.5),
            ("2023-01-31", "SELIC", "ACCUMULATED_SELIC", 15.0, 15000.0, 3, 0.0),
        ],
    )
    with pytest.raises(ValueError):
        parse_bloomberg.parse_vna(caminho=tmp_path)


# ---------------------------------------------------------------------------
# I2 -- cabecalho conferido antes de concatenar.
# ---------------------------------------------------------------------------

def test_taxas_sem_coluna_titulo_levanta_erro(tmp_path):
    caminho = tmp_path / "bbg_taxas_ANDE_2023-01_2023-01.csv"
    pd.DataFrame(
        {
            "isin": ["BRSTNCLTN000"],
            "vencimento": ["2024-01-01"],
            "data": ["2023-01-31"],
            "yld_ytm_mid": [12.0],
            # "titulo" ausente de proposito -- layout do bruto mudou
        }
    ).to_csv(caminho, index=False)

    # match confere que e a nossa checagem explicita que disparou, e nao
    # um KeyError incidental do pandas ao tentar selecionar a coluna
    # faltante mais adiante -- KeyError tambem e um LookupError, entao um
    # pytest.raises(LookupError) sem match passaria mesmo se
    # _checar_colunas fosse removida.
    with pytest.raises(LookupError, match="colunas ausentes"):
        parse_bloomberg.parse_taxas(caminho=tmp_path)


def test_vna_sem_coluna_divergencia_levanta_erro(tmp_path):
    caminho = tmp_path / "bbg_vna_2023-01_2023-01.csv"
    pd.DataFrame(
        {
            "data": ["2023-01-31"],
            "indice": ["IPCA"],
            "campo": ["IDX_RATIO"],
            "fator": [4.0],
            "vna": [4000.0],
            "n_papeis": [1],
            # "divergencia" ausente de proposito
        }
    ).to_csv(caminho, index=False)

    with pytest.raises(LookupError, match="colunas ausentes"):
        parse_bloomberg.parse_vna(caminho=tmp_path)


# ---------------------------------------------------------------------------
# I3 -- guarda de plausibilidade por titulo, frouxa por desenho.
# ---------------------------------------------------------------------------

def test_taxa_fora_da_faixa_plausivel_levanta_erro(tmp_path):
    # LFT so carrega agio/desagio (faixa +-5%); 8% e implausivel.
    _escrever_taxas(
        tmp_path,
        "bbg_taxas_ANDE_2023-01_2023-01.csv",
        [("BRSTNCLF1000", "LFT", "2024-01-01", "2023-01-31", 8.0)],
    )
    with pytest.raises(ValueError):
        parse_bloomberg.parse_taxas(caminho=tmp_path)


def test_taxa_extrema_mas_real_nao_levanta_erro(tmp_path):
    # NTN-B a -4,21% (mai/2021) e a 25,01% (jul/2022) sao extremos reais
    # da ponta curtissima -- a guarda nao pode barrar isso.
    _escrever_taxas(
        tmp_path,
        "bbg_taxas_ANDE_2023-01_2023-01.csv",
        [
            ("BRSTNCNTB001", "NTN-B", "2024-06-01", "2023-01-31", -4.21),
            ("BRSTNCNTB002", "NTN-B", "2024-06-01", "2023-01-31", 25.01),
        ],
    )
    t = parse_bloomberg.parse_taxas(caminho=tmp_path)
    assert len(t) == 2


# ---------------------------------------------------------------------------
# I4 -- VNA tem que ser identico entre datas de origem que colapsam no
# mesmo ultimo dia util; se nao for, e erro, nao "fica com o ultimo".
# ---------------------------------------------------------------------------

def test_vna_diverge_entre_ultimo_dia_util_e_corrido_levanta_erro(tmp_path):
    # Ultimo dia util de dez/2023 e 29/12 (ver teste de normalizacao
    # acima); 31/12/2023 (domingo, ultimo dia corrido) tambem cai nele.
    _escrever_vna(
        tmp_path,
        "bbg_vna_2023-12_2023-12.csv",
        [
            ("2023-12-29", "IPCA", "IDX_RATIO", 4.0, 4500.0, 3, 0.0),
            ("2023-12-31", "IPCA", "IDX_RATIO", 4.1, 4600.0, 3, 0.0),
            ("2023-12-29", "SELIC", "ACCUMULATED_SELIC", 15.0, 15000.0, 3, 0.0),
        ],
    )
    with pytest.raises(ValueError):
        parse_bloomberg.parse_vna(caminho=tmp_path)


def test_vna_igual_entre_ultimo_dia_util_e_corrido_nao_levanta_erro(tmp_path):
    _escrever_vna(
        tmp_path,
        "bbg_vna_2023-12_2023-12.csv",
        [
            ("2023-12-29", "IPCA", "IDX_RATIO", 4.0, 4500.0, 3, 0.0),
            ("2023-12-31", "IPCA", "IDX_RATIO", 4.0, 4500.0, 3, 0.0),
            ("2023-12-29", "SELIC", "ACCUMULATED_SELIC", 15.0, 15000.0, 3, 0.0),
        ],
    )
    v = parse_bloomberg.parse_vna(caminho=tmp_path)
    assert len(v[v["indice"] == "IPCA"]) == 1


# ---------------------------------------------------------------------------
# Desduplicacao "fica com a ultima ocorrencia": teeth de verdade -- dado
# que muda de valor entre duas puxadas da MESMA data de origem.
# ---------------------------------------------------------------------------

def test_taxas_desduplicacao_mantem_a_puxada_mais_recente(tmp_path):
    _escrever_taxas(
        tmp_path,
        "bbg_taxas_ANDE_2023-01_2023-01.csv",
        [("BRSTNCLTN000", "LTN", "2024-06-01", "2023-01-31", 12.0)],
    )
    _escrever_taxas(
        tmp_path,
        "bbg_taxas_ANDE_2023-02_2023-02.csv",
        [("BRSTNCLTN000", "LTN", "2024-06-01", "2023-01-31", 12.5)],
    )
    t = parse_bloomberg.parse_taxas(caminho=tmp_path)
    assert len(t) == 1
    assert t.iloc[0]["taxa_pct"] == pytest.approx(12.5)


def test_vna_desduplicacao_mantem_a_puxada_mais_recente(tmp_path):
    _escrever_vna(
        tmp_path,
        "bbg_vna_2023-01_2023-01.csv",
        [
            ("2023-01-31", "IPCA", "IDX_RATIO", 4.0, 4000.0, 3, 0.0),
            ("2023-01-31", "SELIC", "ACCUMULATED_SELIC", 15.0, 15000.0, 3, 0.0),
        ],
    )
    _escrever_vna(
        tmp_path,
        "bbg_vna_2023-02_2023-02.csv",
        [
            ("2023-01-31", "IPCA", "IDX_RATIO", 4.01, 4010.0, 3, 0.0),
            ("2023-01-31", "SELIC", "ACCUMULATED_SELIC", 15.0, 15000.0, 3, 0.0),
        ],
    )
    v = parse_bloomberg.parse_vna(caminho=tmp_path)
    ipca = v[v["indice"] == "IPCA"].iloc[0]
    assert ipca["vna"] == pytest.approx(4010.0)


def test_nome_de_arquivo_fora_do_padrao_iso_levanta_erro(tmp_path):
    # 'DD-MM-AAAA' ordena antes de 'AAAA-MM_AAAA-MM' em ordem alfabetica:
    # uma puxada nova nesse formato seria descartada pelo keep="last" em
    # favor de uma antiga, em silencio, se isso nao virasse erro.
    _escrever_taxas(
        tmp_path,
        "bbg_taxas_ANDE_01-07-2026.csv",
        [("BRSTNCLTN000", "LTN", "2027-01-01", "2026-07-31", 12.0)],
    )
    with pytest.raises(ValueError):
        parse_bloomberg.parse_taxas(caminho=tmp_path)


# ---------------------------------------------------------------------------
# Minors: taxa ausente excluida da cobertura; papel vencido excluido.
# ---------------------------------------------------------------------------

def test_taxa_ausente_e_excluida_nao_conta_como_cobertura(tmp_path):
    _escrever_taxas(
        tmp_path,
        "bbg_taxas_ANDE_2023-01_2023-01.csv",
        [
            ("BRSTNCLTN000", "LTN", "2024-06-01", "2023-01-31", None),
            ("BRSTNCLTN111", "LTN", "2024-06-01", "2023-01-31", 12.0),
        ],
    )
    t = parse_bloomberg.parse_taxas(caminho=tmp_path)
    assert len(t) == 1
    assert t.iloc[0]["isin"] == "BRSTNCLTN111"


def test_papel_vencido_e_excluido(tmp_path):
    _escrever_taxas(
        tmp_path,
        "bbg_taxas_ANDE_2023-01_2023-01.csv",
        [
            # vencimento no passado em relacao a data da cotacao
            ("BRSTNCLTN000", "LTN", "2022-01-01", "2023-01-31", 12.0),
            ("BRSTNCLTN111", "LTN", "2024-06-01", "2023-01-31", 12.5),
        ],
    )
    t = parse_bloomberg.parse_taxas(caminho=tmp_path)
    assert len(t) == 1
    assert t.iloc[0]["isin"] == "BRSTNCLTN111"
