from datetime import date

import pandas as pd
import pytest
from tesouro import calendario, config, dv, precificacao

CAL = calendario.padrao()


@pytest.fixture(scope="module")
def p():
    return dv.painel()


# ---------------------------------------------------------------------------
# Testes da especificacao original da Tarefa 5
# ---------------------------------------------------------------------------

def test_colunas_canonicas(p):
    assert list(p.columns) == [
        "data", "isin", "titulo", "vencimento", "taxa_pct", "vna", "pu",
        "dv_unitario", "quantidade_mil", "dv_posicao_milhoes",
        "financeiro_calculado_milhoes",
    ]


def test_cobre_o_escopo_e_so_ele(p):
    assert set(p["titulo"].unique()) == {"LTN", "NTN-F", "NTN-B", "LFT"}


def test_sem_chave_duplicada(p):
    assert not p.duplicated(subset=["data", "isin"]).any()


def test_datas_sao_ultimo_dia_util(p):
    assert all(CAL.ultimo_dia_util_do_mes(d) == d for d in p["data"].unique())


def test_dv_da_lft_e_vazio_e_o_financeiro_nao(p):
    lft = p[(p["titulo"] == "LFT") & p["pu"].notna()]
    assert len(lft) > 1000
    assert lft["dv_unitario"].isna().all()
    assert lft["financeiro_calculado_milhoes"].notna().all()


def test_dv_dos_titulos_e_negativo(p):
    tit = p[p["titulo"].isin(["LTN", "NTN-F", "NTN-B"]) & p["dv_unitario"].notna()]
    assert (tit["dv_unitario"] < 0).all()
    assert (tit["dv_posicao_milhoes"] < 0).all()


def test_papel_sem_taxa_fica_com_preco_vazio_e_posicao_preenchida(p):
    sem = p[p["taxa_pct"].isna()]
    assert len(sem) > 0
    assert sem["pu"].isna().all()
    assert sem["quantidade_mil"].notna().all()


def test_ordem_de_grandeza_do_financeiro(p):
    # A DPMFi no ultimo mes esta na casa de trilhoes de reais.
    ult = p[p["data"] == p["data"].max()]
    total = ult["financeiro_calculado_milhoes"].sum() / 1e6
    assert 5 < total < 15


def test_dv_total_do_sistema_e_plausivel(p):
    # Somando os titulos, o DV do sistema fica na casa de bilhoes de reais
    # por bp -- negativo, pela convencao.
    ult = p[(p["data"] == p["data"].max()) & p["dv_posicao_milhoes"].notna()]
    total = ult["dv_posicao_milhoes"].sum()
    assert -20000 < total < -500


# ---------------------------------------------------------------------------
# Helpers para as fixtures sinteticas abaixo, isoladas do dado real via
# monkeypatch de config.PROCESSED_DIR -- mesmo padrao de test_parse_bloomberg.
# ---------------------------------------------------------------------------

def _escrever_estoque(diretorio, linhas):
    pd.DataFrame(
        linhas,
        columns=["data", "indexador", "titulo", "vencimento", "isin", "quantidade_mil"],
    ).to_csv(diretorio / "estoque_titulos_vencimento.csv", index=False)


def _escrever_taxas(diretorio, linhas):
    pd.DataFrame(
        linhas, columns=["data", "isin", "titulo", "vencimento", "taxa_pct"],
    ).to_csv(diretorio / "taxa_por_papel.csv", index=False)


def _escrever_vna(diretorio, linhas):
    pd.DataFrame(
        linhas, columns=["data", "indice", "vna"],
    ).to_csv(diretorio / "vna.csv", index=False)


# ---------------------------------------------------------------------------
# Regressao do defeito conhecido do brief: "r.vna is None" em vez de
# "pd.isna(r.vna)". df["vna"] e uma coluna numerica; assim que ela recebe
# qualquer valor float, o pandas converte os None ausentes em NaN, e
# "NaN is None" e False. Com "is None" na guarda, uma NTN-B com taxa mas
# sem VNA passaria pela guarda e cairia em precificacao.pu com vna=NaN --
# que ou devolve PU NaN em silencio ou levanta ValueError dentro de
# _truncar (math.trunc de NaN), em vez de a linha ser pulada como None.
# ---------------------------------------------------------------------------

def test_vna_ausente_pula_a_linha_em_vez_de_precificar_com_nan(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)
    d1 = date(2023, 6, 30)  # sexta-feira, dia util -- nao exercita a normalizacao
    d2 = date(2023, 7, 31)  # segunda-feira, dia util

    # Duas NTN-B: a primeira tem VNA de IPCA na data, a segunda nao. As
    # duas linhas sao necessarias -- com uma so, a coluna "vna" do
    # DataFrame teria um unico valor None e ficaria dtype object (None de
    # verdade), o que mascara o defeito. Com as duas, a coluna mistura um
    # float valido com um ausente e o pandas promove tudo a float64,
    # convertendo o ausente em NaN -- e "NaN is None" e False, exatamente
    # o cenario que o defeito do brief (r.vna is None) deixa passar.
    _escrever_estoque(tmp_path, [
        (str(d1), "IPCA", "NTN-B", "2030-05-15", "ISINB1", 100.0),
        (str(d2), "IPCA", "NTN-B", "2030-05-15", "ISINB1", 100.0),
    ])
    _escrever_taxas(tmp_path, [
        (str(d1), "ISINB1", "NTN-B", "2030-05-15", 7.0),
        (str(d2), "ISINB1", "NTN-B", "2030-05-15", 7.1),
    ])
    # IPCA presente em d1, ausente em d2 -- so d2 fica sem VNA.
    _escrever_vna(tmp_path, [(str(d1), "IPCA", 4200.0)])

    painel = dv.painel().set_index("data")
    assert pd.notna(painel.loc[d1, "vna"])
    assert pd.notna(painel.loc[d1, "pu"])

    linha2 = painel.loc[d2]
    assert pd.notna(linha2["taxa_pct"])
    assert pd.isna(linha2["vna"])
    assert pd.isna(linha2["pu"])
    assert pd.isna(linha2["dv_unitario"])
    assert pd.isna(linha2["financeiro_calculado_milhoes"])


# ---------------------------------------------------------------------------
# A taxa dos CSVs de origem esta em percentual; a conversao para decimal
# (/100) tem que acontecer exatamente uma vez, dentro de dv.py. Ancora um
# valor exato para que um fator 100 errado (ex.: esquecer o /100 e mandar
# 10.0 direto para o motor) nao passe despercebido.
# ---------------------------------------------------------------------------

def test_taxa_pct_converte_de_percentual_para_decimal_uma_vez(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)
    d0 = date(2026, 6, 30)
    venc = CAL.mover(d0, 252)

    _escrever_estoque(tmp_path, [(str(d0), "Prefixados", "LTN", str(venc), "ISINL1", 50.0)])
    _escrever_taxas(tmp_path, [(str(d0), "ISINL1", "LTN", str(venc), 10.0)])  # 10.0 = 10%
    _escrever_vna(tmp_path, [(str(d0), "SELIC", 15000.0)])  # LTN nao usa, so evita CSV vazio

    linha = dv.painel().iloc[0]
    # Mesma ancora aritmetica exata de test_precificacao: 1000 / 1,10 =
    # 909,090909... Se taxa_pct fosse usada crua (10.0 em vez de 0.10), o
    # PU sairia negativo ou zero, muito longe deste valor.
    assert linha["pu"] == pytest.approx(909.090909, abs=1e-6)
    assert linha["pu"] == precificacao.pu_ltn(CAL, d0, venc, 0.10)


# ---------------------------------------------------------------------------
# Papel vencido (estoque remanescente apos o vencimento, caso raro mas real
# -- ver BRSTNCNTF071/NTN-F 2014-01-01 no dado de producao) tem DV 0.0, nao
# None: "nao se aplica" (LFT) e "risco de taxa genuinamente nulo" (vencido)
# sao coisas diferentes, e somar None quebra enquanto somar 0.0 esta certo.
# ---------------------------------------------------------------------------

def test_papel_vencido_com_taxa_fica_com_dv_zero_e_nao_none(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)
    d0 = date(2026, 6, 30)
    venc_passado = date(2020, 1, 1)

    _escrever_estoque(tmp_path, [(str(d0), "Prefixados", "LTN", str(venc_passado), "ISINL2", 10.0)])
    _escrever_taxas(tmp_path, [(str(d0), "ISINL2", "LTN", str(venc_passado), 13.0)])
    _escrever_vna(tmp_path, [(str(d0), "SELIC", 15000.0)])  # LTN nao usa, so evita CSV vazio

    linha = dv.painel().iloc[0]
    assert linha["pu"] == 0.0
    assert linha["dv_unitario"] == 0.0
    assert not pd.isna(linha["dv_unitario"])
    assert linha["dv_posicao_milhoes"] == 0.0


# ---------------------------------------------------------------------------
# A armadilha da juncao (medida na Tarefa 3): estoque_titulos_vencimento.csv
# grava o ultimo dia CORRIDO do mes; taxa_por_papel.csv e vna.csv, ja no
# ultimo dia UTIL. Sem normalizar o lado do estoque em _posicoes, a chave
# de juncao nao bate nos meses em que os dois divergem, e a taxa de uma
# posicao real fica silenciosamente vazia. Fixture sintetica com um mes em
# que o ultimo dia corrido (domingo) e o ultimo dia util sao datas
# diferentes, provando que a normalizacao e o que permite casar os dois.
# ---------------------------------------------------------------------------

def test_normalizacao_do_estoque_permite_casar_com_taxa_e_vna(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)
    corrido = date(2023, 12, 31)  # domingo
    util = CAL.ultimo_dia_util_do_mes(corrido)
    assert util != corrido
    assert util == date(2023, 12, 29)

    _escrever_estoque(tmp_path, [(str(corrido), "Prefixados", "LTN", "2028-01-01", "ISINL3", 20.0)])
    _escrever_taxas(tmp_path, [(str(util), "ISINL3", "LTN", "2028-01-01", 11.5)])
    _escrever_vna(tmp_path, [(str(util), "SELIC", 15000.0)])  # LTN nao usa, so evita CSV vazio

    linha = dv.painel().iloc[0]
    assert linha["data"] == util
    assert pd.notna(linha["taxa_pct"])
    assert linha["taxa_pct"] == 11.5
    assert pd.notna(linha["pu"])
