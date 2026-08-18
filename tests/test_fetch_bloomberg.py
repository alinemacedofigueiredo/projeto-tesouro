import csv
from datetime import date

import pandas as pd
import pytest
from tesouro import calendario, fetch_bloomberg, parse_bloomberg

CAL = calendario.padrao()


def _fim_mes(ano, mes):
    return CAL.ultimo_dia_util_do_mes(date(ano, mes, 1))


# ---------------------------------------------------------------------------
# Testes da especificacao original da Tarefa 4 -- rodam contra o estoque de
# verdade do projeto (data/processed/estoque_titulos_vencimento.csv), sem
# tocar rede: papeis_do_estoque e datas_do_painel so leem CSV local.
# ---------------------------------------------------------------------------

def test_papeis_cobrem_apenas_o_escopo():
    p = fetch_bloomberg.papeis_do_estoque()
    assert set(p["titulo"].unique()) == {"LTN", "NTN-F", "NTN-B", "LFT"}
    assert len(p) > 150
    assert p["isin"].notna().all()


def test_papeis_trazem_a_janela_de_vida():
    p = fetch_bloomberg.papeis_do_estoque()
    assert (p["primeira"] <= p["ultima"]).all()


def test_datas_do_painel_sao_dia_util_e_fim_de_mes():
    d = fetch_bloomberg.datas_do_painel()
    assert len(d) > 190
    assert all(CAL.eh_dia_util(x) for x in d)
    assert all(CAL.ultimo_dia_util_do_mes(x) == x for x in d)
    assert d == sorted(d)


def test_nao_importa_blpapi_no_topo():
    # O modulo tem de importar em maquina sem Bloomberg. O import fica
    # dentro da funcao que faz a coleta.
    import ast
    import pathlib
    fonte = pathlib.Path("src/tesouro/fetch_bloomberg.py").read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    for no in arvore.body:                      # so o nivel de modulo
        if isinstance(no, (ast.Import, ast.ImportFrom)):
            nomes = [a.name for a in no.names] + [getattr(no, "module", "") or ""]
            assert not any("blpapi" in n for n in nomes)


# ---------------------------------------------------------------------------
# Testes de baixar() -- nunca tocam rede. _sessao, _historico e _referencia
# sao substituidos por dubles; papeis_do_estoque, datas_do_painel e _estoque
# sao substituidos por um painel sintetico pequeno (3 meses, 3 papeis) para
# manter os testes rapidos e legiveis. Nenhum teste escreve em data/raw/ --
# tudo usa tmp_path.
# ---------------------------------------------------------------------------

M1, M2, M3 = _fim_mes(2023, 1), _fim_mes(2023, 2), _fim_mes(2023, 3)

_PAPEIS_FAKE = pd.DataFrame([
    # ativo o periodo inteiro -- serve para testar o corte incremental
    {"isin": "BR0000000LTN", "titulo": "LTN", "vencimento": date(2024, 1, 1),
     "primeira": M1, "ultima": M3},
    # nasce so em fevereiro -- depois do cutoff usado nos testes, entao a
    # janela pedida para ele tem de ser a propria data de nascimento, nunca
    # o limite do corte incremental
    {"isin": "BR0000000NTB", "titulo": "NTN-B", "vencimento": date(2025, 1, 1),
     "primeira": M2, "ultima": M3},
    # LFT so para exercitar o campo ACCUMULATED_SELIC no vna
    {"isin": "BR0000000LFT", "titulo": "LFT", "vencimento": date(2024, 6, 1),
     "primeira": M1, "ultima": M3},
])

_DATAS_FAKE = [M1, M2, M3]

_ESTOQUE_FAKE = pd.DataFrame({
    "titulo": ["LTN", "LTN", "LTN", "NTN-B", "NTN-B", "LFT", "LFT", "LFT"],
    "isin": ["BR0000000LTN"] * 3 + ["BR0000000NTB"] * 2 + ["BR0000000LFT"] * 3,
    "data": pd.to_datetime([M1, M2, M3, M2, M3, M1, M2, M3]),
})


class _SessaoFake:
    def getService(self, nome):
        return "servico-fake"

    def stop(self):
        pass


def _aplicar_dubles(monkeypatch, chamadas_historico=None, chamadas_referencia=None):
    """Substitui o painel e a fala com o terminal por dubles deterministicos.

    chamadas_historico/chamadas_referencia, se passadas, recebem cada
    chamada feita -- para os testes que precisam conferir QUAL janela foi
    pedida, nao so o resultado.
    """
    monkeypatch.setattr(fetch_bloomberg, "papeis_do_estoque", lambda: _PAPEIS_FAKE.copy())
    monkeypatch.setattr(fetch_bloomberg, "datas_do_painel", lambda: list(_DATAS_FAKE))
    monkeypatch.setattr(fetch_bloomberg, "_estoque", lambda: _ESTOQUE_FAKE.copy())
    monkeypatch.setattr(fetch_bloomberg, "_sessao", lambda: (None, _SessaoFake()))

    def _historico_fake(blpapi, sessao, servico, isin, campo, inicio, fim):
        if chamadas_historico is not None:
            chamadas_historico.append((isin, campo, inicio, fim))
        return [(d, 1.0) for d in _DATAS_FAKE if inicio <= d <= fim]

    def _referencia_fake(blpapi, sessao, servico, isins, campo, settle):
        if chamadas_referencia is not None:
            chamadas_referencia.append((tuple(isins), campo, settle))
        return [1000.0] * len(isins)

    monkeypatch.setattr(fetch_bloomberg, "_historico", _historico_fake)
    monkeypatch.setattr(fetch_bloomberg, "_referencia", _referencia_fake)


def _linhas(caminho):
    with open(caminho, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_baixar_primeira_coleta_pega_a_janela_inteira(tmp_path, monkeypatch):
    chamadas = []
    _aplicar_dubles(monkeypatch, chamadas_historico=chamadas)

    alvo_taxa, alvo_vna, alvo_preco = fetch_bloomberg.baixar(destino=tmp_path)

    assert alvo_taxa.name == "bbg_taxas_ANDE_2023-01_2023-03.csv"
    assert alvo_vna.name == "bbg_vna_2023-01_2023-03.csv"
    assert alvo_preco.name == "bbg_precos_ANDE_2023-01_2023-03.csv"
    assert alvo_taxa.exists() and alvo_vna.exists() and alvo_preco.exists()

    # Sem coleta anterior, cada papel e pedido desde a propria data de
    # nascimento -- nunca um corte artificial.
    janelas = {isin: (inicio, fim) for isin, campo, inicio, fim in chamadas
               if campo == fetch_bloomberg.CAMPO_TAXA}
    assert janelas["BR0000000LTN"] == (M1, M3)
    assert janelas["BR0000000NTB"] == (M2, M3)

    linhas = _linhas(alvo_taxa)
    assert {l["isin"] for l in linhas} == {"BR0000000LTN", "BR0000000NTB", "BR0000000LFT"}
    # BR0000000NTB nasce em M2: nao pode ter linha em M1.
    assert not any(l["isin"] == "BR0000000NTB" and l["data"] == str(M1) for l in linhas)


def test_baixar_incremental_pede_so_o_que_falta(tmp_path, monkeypatch):
    # Uma coleta anterior ja cobriu janeiro.
    (tmp_path / "bbg_taxas_ANDE_2023-01_2023-01.csv").write_text(
        "isin,titulo,vencimento,data,yld_ytm_mid\n", encoding="utf-8"
    )
    (tmp_path / "bbg_vna_2023-01_2023-01.csv").write_text(
        "data,indice,campo,fator,vna,n_papeis,divergencia\n", encoding="utf-8"
    )

    chamadas = []
    _aplicar_dubles(monkeypatch, chamadas_historico=chamadas)

    alvo_taxa, alvo_vna, alvo_preco = fetch_bloomberg.baixar(destino=tmp_path)

    # O nome do arquivo novo reflete SO o periodo pedido -- fevereiro e
    # marco -- nunca a janela inteira do estoque.
    assert alvo_taxa.name == "bbg_taxas_ANDE_2023-02_2023-03.csv"
    assert alvo_vna.name == "bbg_vna_2023-02_2023-03.csv"

    janelas = {isin: (inicio, fim) for isin, campo, inicio, fim in chamadas
               if campo == fetch_bloomberg.CAMPO_TAXA}
    limite = date(2023, 2, 1)  # primeiro dia apos o mes coberto (janeiro)
    # LTN ja vivia antes do corte: pedido comeca no limite (1/fev), nao na
    # data de nascimento real (fim de janeiro) -- e o corte incremental
    # agindo.
    assert janelas["BR0000000LTN"] == (limite, M3)
    # NTN-B nasceu depois do corte: pedido comeca na propria data de
    # nascimento (fim de fevereiro), que ja e posterior ao limite.
    assert janelas["BR0000000NTB"] == (M2, M3)

    linhas = _linhas(alvo_taxa)
    assert all(l["data"] != str(M1) for l in linhas)

    # O arquivo de janeiro, que ja existia, continua exatamente como
    # estava -- nada foi reescrito nele.
    assert (tmp_path / "bbg_taxas_ANDE_2023-01_2023-01.csv").read_text(
        encoding="utf-8"
    ) == "isin,titulo,vencimento,data,yld_ytm_mid\n"


def test_baixar_sem_novidade_leva_erro_visivel_sem_tocar_rede(tmp_path, monkeypatch):
    # Arquivos existentes ja cobrem o painel inteiro (jan a mar).
    (tmp_path / "bbg_taxas_ANDE_2023-01_2023-03.csv").write_text(
        "isin,titulo,vencimento,data,yld_ytm_mid\n", encoding="utf-8"
    )
    (tmp_path / "bbg_vna_2023-01_2023-03.csv").write_text(
        "data,indice,campo,fator,vna,n_papeis,divergencia\n", encoding="utf-8"
    )

    monkeypatch.setattr(fetch_bloomberg, "papeis_do_estoque", lambda: _PAPEIS_FAKE.copy())
    monkeypatch.setattr(fetch_bloomberg, "datas_do_painel", lambda: list(_DATAS_FAKE))

    def _proibido(*args, **kwargs):
        raise AssertionError("nao deveria ter aberto sessao com o terminal")

    monkeypatch.setattr(fetch_bloomberg, "_sessao", _proibido)

    with pytest.raises(RuntimeError, match="nada novo"):
        fetch_bloomberg.baixar(destino=tmp_path)


def test_baixar_nunca_sobrescreve_arquivo_de_destino_existente(tmp_path, monkeypatch):
    # Forca o corte incremental a "nao ver nada ainda coletado" (cutoff
    # None), mesmo com um arquivo ja fisicamente presente no caminho que
    # o proximo pedido calcularia -- simula qualquer cenario em que o nome
    # alvo colida (defesa em profundidade, independente do mecanismo que
    # descobre a cobertura existente).
    alvo = tmp_path / "bbg_taxas_ANDE_2023-01_2023-03.csv"
    alvo.write_text("SENTINELA: nao mexer\n", encoding="utf-8")

    monkeypatch.setattr(fetch_bloomberg, "_cobertura_atual", lambda destino: None)
    monkeypatch.setattr(fetch_bloomberg, "papeis_do_estoque", lambda: _PAPEIS_FAKE.copy())
    monkeypatch.setattr(fetch_bloomberg, "datas_do_painel", lambda: list(_DATAS_FAKE))

    def _proibido(*args, **kwargs):
        raise AssertionError("nao deveria ter aberto sessao com o terminal")

    monkeypatch.setattr(fetch_bloomberg, "_sessao", _proibido)

    with pytest.raises(FileExistsError, match="ja existe"):
        fetch_bloomberg.baixar(destino=tmp_path)

    assert alvo.read_text(encoding="utf-8") == "SENTINELA: nao mexer\n"


def test_baixar_grava_csv_que_parse_bloomberg_le_sem_alteracao(tmp_path, monkeypatch):
    """O contrato de nome e de coluna com o leitor (Tarefa 3) e o que
    importa de verdade aqui: gera com baixar() e le de volta com
    parse_bloomberg, sem tocar em parse_bloomberg.py.
    """
    _aplicar_dubles(monkeypatch)

    fetch_bloomberg.baixar(destino=tmp_path)

    taxas = parse_bloomberg.parse_taxas(caminho=tmp_path)
    vna = parse_bloomberg.parse_vna(caminho=tmp_path)

    assert len(taxas) > 0
    assert set(taxas["isin"]) == {"BR0000000LTN", "BR0000000NTB", "BR0000000LFT"}
    assert len(vna) > 0
    assert set(vna["indice"]) <= {"IPCA", "SELIC"}
