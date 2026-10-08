"""O leilao antes de acontecer.

Duas coisas precisam ser supostas para desenhar a barra da oferta, e elas custam
MUITO diferente. Os testes travam as duas medicoes e o desenho que decorre delas.

O risco deste modulo e especifico: ele produz numeros que PARECEM observados. Um
financeiro calculado e um financeiro; um DV01 calculado e um DV01. Se as marcas de
"isto foi suposto" sumirem, o teto vira emissao sem que ninguem note.
"""
import pandas as pd
import pytest

from tesouro import config, leilao_ofertado


@pytest.fixture(scope="module")
def base():
    return pd.read_csv(
        config.PROCESSED_DIR / "leiloes.csv",
        parse_dates=["data_leilao", "data_liquidacao", "data_vencimento"],
    )


@pytest.fixture(scope="module")
def oferta(base):
    """Uma oferta de tres papeis cujos vencimentos existem no historico."""
    recentes = base[(base["venda_qtd"].fillna(0) > 0)
                    & base["taxa_media_pct"].notna()]
    linhas = []
    for titulo in ("LTN", "NTN-F", "NTN-B"):
        g = recentes[recentes["titulo"] == titulo]
        if g.empty:
            continue
        r = g.sort_values("data_leilao").iloc[-1]
        linhas.append({
            "data_leilao": pd.Timestamp("2026-08-20"),
            "data_liquidacao": pd.Timestamp("2026-08-21"),
            "titulo": titulo,
            "tipo_leilao": "Venda",
            "data_vencimento": r["data_vencimento"],
            "oferta_qtd": 1_000_000,
            "taxa_media_pct": None,
        })
    return pd.DataFrame(linhas)


# --------------------------------------------------------------------------
# A medicao que justifica o desenho. Se o dado mudar e a suposicao piorar,
# alguem precisa ver -- por isso os numeros estao travados, e nao so comentados.
# --------------------------------------------------------------------------

def test_a_taxa_do_leilao_anterior_erra_pouco(base):
    # 11,0 bp na mediana e 36,7 no p90, medidos desde 2015, so 1a volta, so leiloes
    # COM aceite e com o anterior em ate 45 dias.
    d = base[base["tipo_leilao"].isin(["Venda", "Extra Venda"])].copy()
    d = d[d["titulo"].isin(leilao_ofertado.PAPEIS_PRECIFICADOS)]
    d = d[d["data_leilao"] >= "2015-01-01"]
    d = d[~d["volta"].fillna("").astype(str).str.startswith("2")]
    # Leilao sem aceite grava taxa 0,00 na planilha, que nao e taxa nenhuma --
    # incluir esses punha uma cauda de 1.500 bp na medicao.
    d = d[d["venda_qtd"].fillna(0) > 0]
    d = d[d["taxa_media_pct"].notna()].sort_values("data_leilao")

    d["anterior"] = d.groupby(
        ["titulo", "data_vencimento"])["taxa_media_pct"].shift(1)
    d["dias"] = (d["data_leilao"] - d.groupby(
        ["titulo", "data_vencimento"])["data_leilao"].shift(1)).dt.days
    f = d[d["anterior"].notna()
          & (d["dias"] > 0)
          & (d["dias"] <= leilao_ofertado.DIAS_MAXIMOS_PARA_A_TAXA)]
    erro = (f["taxa_media_pct"] - f["anterior"]).abs() * 100

    assert len(f) > 4000
    assert erro.median() == pytest.approx(
        leilao_ofertado.ERRO_DA_TAXA_MEDIANA_BP, abs=1.0)
    assert erro.quantile(0.90) == pytest.approx(
        leilao_ofertado.ERRO_DA_TAXA_P90_BP, abs=3.0)


def test_o_tesouro_nao_aceita_tudo_o_que_oferta(base):
    # A medicao que obriga a barra da oferta a ser um TETO. Se ele aceitasse tudo,
    # ofertado e aceito seriam a mesma coisa e nao haveria dois momentos.
    d = base[base["tipo_leilao"].isin(["Venda", "Extra Venda"])]
    d = d[d["titulo"].isin(leilao_ofertado.PAPEIS_PRECIFICADOS)]
    d = d[(d["data_leilao"] >= "2015-01-01") & (d["oferta_qtd"].fillna(0) > 0)]

    razao = d["venda_qtd"].fillna(0).sum() / d["oferta_qtd"].sum()
    assert razao == pytest.approx(leilao_ofertado.RAZAO_ACEITO_SOBRE_OFERTADO,
                                  abs=0.01)
    # E ela varia MUITO por papel -- e por isso que aplicar a media para "corrigir"
    # a barra trocaria um numero honesto por uma aposta.
    por_papel = d.groupby("titulo").apply(
        lambda g: g["venda_qtd"].fillna(0).sum() / g["oferta_qtd"].sum(),
        include_groups=False)
    assert por_papel.max() - por_papel.min() > 0.20


# --------------------------------------------------------------------------
# O preenchimento
# --------------------------------------------------------------------------

def test_a_taxa_vem_do_leilao_anterior_e_fica_marcada(oferta, base):
    d = leilao_ofertado.preencher(oferta, base=base)
    assert d["taxa_media_pct"].notna().all()
    assert d["taxa_suposta"].all()
    assert d["taxa_de_quando"].notna().all()


def test_o_financeiro_e_calculado_e_fica_marcado(oferta, base):
    # Um financeiro calculado E um financeiro: sem a marca, ninguem distingue do
    # que o Tesouro publicou.
    d = leilao_ofertado.preencher(oferta, base=base)
    assert d["financeiro_milhoes"].notna().all()
    assert (d["financeiro_milhoes"] > 0).all()
    assert d["financeiro_calculado"].all()


def test_a_quantidade_da_barra_e_a_ofertada(oferta, base):
    d = leilao_ofertado.preencher(oferta, base=base)
    assert (d["venda_qtd"] == d["oferta_qtd"]).all()


def test_taxa_ja_existente_nao_e_sobrescrita(oferta, base):
    # Se o arquivo trouxer taxa indicativa, ela vence a emprestada -- e a marca diz
    # que aquela linha nao foi suposta.
    com_taxa = oferta.copy()
    com_taxa.loc[com_taxa.index[0], "taxa_media_pct"] = 9.99
    d = leilao_ofertado.preencher(com_taxa, base=base)
    assert d.iloc[0]["taxa_media_pct"] == 9.99
    assert not d.iloc[0]["taxa_suposta"]


def test_papel_sem_leilao_anterior_entra_sem_taxa_e_sem_financeiro(base):
    # Inventar uma taxa para um vencimento que nunca foi leiloado seria o defeito
    # plausivel-e-errado de sempre. A linha entra so com quantidade.
    nova = pd.DataFrame([{
        "data_leilao": pd.Timestamp("2026-08-20"),
        "data_liquidacao": pd.Timestamp("2026-08-21"),
        "titulo": "NTN-B", "tipo_leilao": "Venda",
        "data_vencimento": pd.Timestamp("2099-05-15"),
        "oferta_qtd": 500_000, "taxa_media_pct": None,
    }])
    d = leilao_ofertado.preencher(nova, base=base)
    assert pd.isna(d.iloc[0]["taxa_media_pct"])
    assert pd.isna(d.iloc[0]["financeiro_milhoes"])
    assert not d.iloc[0]["financeiro_calculado"]


def test_taxa_velha_e_sinalizada(base):
    # Os 11 bp foram medidos com o anterior em ate 45 dias. Alem disso o mercado ja
    # e outro e o erro nao e mais o que esta medido -- a linha nao e recusada, mas
    # quem roda tem de ser avisado.
    antigo = base[(base["titulo"] == "NTN-B") & (base["venda_qtd"].fillna(0) > 0)
                  & base["taxa_media_pct"].notna()]
    r = antigo.sort_values("data_leilao").iloc[-1]
    daqui_a_um_ano = pd.DataFrame([{
        "data_leilao": r["data_leilao"] + pd.Timedelta(days=400),
        "data_liquidacao": r["data_leilao"] + pd.Timedelta(days=401),
        "titulo": "NTN-B", "tipo_leilao": "Venda",
        "data_vencimento": r["data_vencimento"],
        "oferta_qtd": 500_000, "taxa_media_pct": None,
    }])
    d = leilao_ofertado.preencher(daqui_a_um_ano, base=base)
    assert d.iloc[0]["taxa_dias_de_idade"] > leilao_ofertado.DIAS_MAXIMOS_PARA_A_TAXA
    assert bool(d.iloc[0]["taxa_velha"]) is True


def test_taxa_de_referencia_ignora_leilao_sem_aceite(base):
    # Leilao SEM ACEITE grava taxa 0,00 na planilha, e esse zero nao e taxa. Nos
    # prefixados e na NTN-B, emprestar esse zero precificaria o titulo pelo valor de
    # face -- um PU plausivel e completamente errado.
    ultimas = leilao_ofertado.taxas_de_referencia(base)
    prefixados = ultimas.loc[["LTN", "NTN-F", "NTN-B"]]
    assert (prefixados["taxa_media_pct"] != 0).all()

    # NA LFT, PORTANTO, ZERO E LEGITIMO -- e por isso o filtro e por venda_qtd e nao
    # por taxa. A "taxa" da LFT e agio sobre a Selic: zero quer dizer vendida ao
    # par, PU igual ao VNA. Sao 18 vencimentos com essa marca, todos LFT, todos com
    # quantidade e financeiro de verdade. Filtrar por taxa != 0 os jogaria fora.
    zeradas = ultimas[ultimas["taxa_media_pct"] == 0]
    assert set(zeradas.index.get_level_values("titulo")) == {"LFT"}

    # E a tabela so tem os papeis que o projeto sabe precificar: a NTN-D tinha um
    # zero seu, e emprestar taxa dela nao serviria para nada.
    assert set(ultimas.index.get_level_values("titulo")) == set(
        leilao_ofertado.PAPEIS_PRECIFICADOS)


# ---------------------------------------------------------------------------
# POR QUE NAO HA EDITAL: nao e dia de leilao, ou ainda nao saiu?
#
# ELA RODOU O ATALHO EM 08/10/2026 as 10:32 -- quinta-feira, dia de prefixado --
# e leu "nao ha edital para este dia" como "hoje nao tem leilao". O leilao
# aconteceu perto do meio-dia e o resultado saiu de tarde: as 14:36 a API tinha
# as seis pernas. O programa estava certo; a frase, nao.
# ---------------------------------------------------------------------------

def _agenda_falsa(datas_e_titulos):
    """Registros do /calendario como a API os devolve, sem tocar a rede."""
    return [{"DATA_LEILAO": data, "TITULO": titulo,
             "VENCIMENTO": "2030-01-01", "TIPO_LEILAO": "Venda"}
            for data, titulo in datas_e_titulos]


def test_dia_de_leilao_sem_edital_diz_QUE_AINDA_NAO_SAIU():
    # O caso dela. O calendario do Tesouro traz prefixado para hoje, e o edital
    # nao esta la: a resposta nao e "nao tem leilao", e "ainda nao saiu".
    from tesouro import leilao_do_dia

    frase = leilao_do_dia._o_que_o_calendario_diz(
        "2026-10-08", registros=_agenda_falsa([("2026-10-08", "LTN"),
                                               ("2026-10-08", "NTN-F"),
                                               ("2026-10-13", "NTN-B")]))
    assert "ainda nao" in frase, frase
    # E DIZ DE QUE PAPEL E O DIA -- sem isso ela nao sabe o que esperar.
    assert "LTN" in frase and "NTN-F" in frase, frase
    # E nao pode dizer o contrario na mesma frase.
    assert "nao traz leilao" not in frase, frase


def test_dia_SEM_leilao_no_calendario_diz_que_nao_e_dia():
    # Sexta-feira, dentro da janela publicada: o calendario de fato nao traz
    # leilao. Aqui "nao tem leilao hoje" e a resposta certa.
    from tesouro import leilao_do_dia

    frase = leilao_do_dia._o_que_o_calendario_diz(
        "2026-10-09", registros=_agenda_falsa([("2026-10-08", "LTN"),
                                               ("2026-10-13", "NTN-B")]))
    assert "nao traz leilao" in frase, frase
    assert "ainda nao" not in frase, frase


def test_ALEM_do_calendario_publicado_a_resposta_e_NAO_SEI():
    # A TERCEIRA RESPOSTA, e a que este projeto obriga. Passada a ultima data
    # que o Tesouro publicou, dizer "nao tem leilao" seria plausivel e errado --
    # e errado justamente onde a frase soa mais segura.
    from tesouro import leilao_do_dia

    frase = leilao_do_dia._o_que_o_calendario_diz(
        "2026-12-30", registros=_agenda_falsa([("2026-10-08", "LTN"),
                                               ("2026-10-13", "NTN-B")]))
    assert "13/10/2026" in frase, frase
    assert "nao da para dizer" in frase, frase
    # NAO PODE AFIRMAR NENHUM DOS DOIS LADOS.
    assert "nao traz leilao" not in frase and "ainda nao" not in frase, frase


def test_sem_calendario_nenhum_a_frase_NAO_INVENTA():
    # A API pode responder vazio. A frase tem de dizer que nao sabe, e nao cair
    # no ramo de "nao e dia de leilao" por o calendario estar vazio.
    from tesouro import leilao_do_dia

    frase = leilao_do_dia._o_que_o_calendario_diz("2026-10-08", registros=[])
    assert "nao traz leilao" not in frase, frase
    assert "ainda nao" not in frase, frase
    assert "calend" in frase, frase


def test_do_edital_sem_edital_IMPRIME_a_explicacao(monkeypatch, capsys):
    # A ligacao entre as duas pontas: a frase do calendario tem de chegar a
    # tela. Antes saia so "nada a gravar", e era isso que ela lia.
    from tesouro import leilao_do_dia

    monkeypatch.setattr(leilao_do_dia, "tabela_do_edital",
                        lambda quando=None: None)
    monkeypatch.setattr(
        leilao_do_dia, "_o_que_o_calendario_diz",
        lambda quando, registros=None: "A FRASE DO CALENDARIO")
    assert leilao_do_dia.do_edital(quando="2026-10-08") == 0
    assert "A FRASE DO CALENDARIO" in capsys.readouterr().out


def test_a_frase_diz_HOJE_so_quando_e_hoje():
    # Rotulo descolado do dado: a funcao aceita 'quando', e dizia "para hoje"
    # para qualquer data. Em producao nao erraria -- do_edital chama com hoje --
    # mas e a mesma classe de defeito que o projeto pegou tres vezes.
    import pandas as pd

    from tesouro import leilao_do_dia

    registros = _agenda_falsa([("2026-10-08", "LTN"), ("2026-10-13", "NTN-B")])
    hoje = pd.Timestamp.today().normalize()

    outro_dia = leilao_do_dia._o_que_o_calendario_diz("2026-10-13",
                                                      registros=registros)
    if hoje != pd.Timestamp("2026-10-13"):
        assert "13/10/2026" in outro_dia, outro_dia
        assert "para hoje" not in outro_dia, outro_dia

    # E com a data de hoje de verdade a palavra volta -- sem isso o conserto
    # teria trocado uma frase natural por uma data em toda rodada normal.
    agenda_de_hoje = _agenda_falsa([(hoje.strftime("%Y-%m-%d"), "LTN")])
    frase = leilao_do_dia._o_que_o_calendario_diz(hoje, registros=agenda_de_hoje)
    assert "para hoje" in frase, frase
