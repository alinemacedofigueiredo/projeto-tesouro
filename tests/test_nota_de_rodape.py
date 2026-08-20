"""A defesa estrutural contra nota de rodape, nos quatro parsers padrao A.

Cada uma das abas 1.1/1.2, 2.1, 3.7/3.8 e 4.1/4.2/4.3 termina com notas em
linhas soltas, e cada aba as redige de um jeito diferente ('OBS:' na 1.1,
'Obs:'/'Obs 2:' na 1.2, 'Obs.1:' na 2.1, numeradas na 3.7/3.8/4.x). Os
filtros textuais de cada parser sao a primeira linha de defesa; a rede e
descartar_folhas_sem_dado: uma folha sem valor em nenhuma data nao e folha.

Os testes abaixo usam um rotulo de nota que nenhum dos filtros textuais
reconhece -- nao comeca com digito nem com 'obs' -- justamente para provar
que a defesa que sobra e a estrutural, e que ela existe nos quatro modulos.
"""
import datetime

import pandas as pd
from tesouro.parse_rmd import custo, estoque, funding, prazo

# Nao casa com nenhum dos filtros textuais dos quatro parsers.
NOTA = "Ver a nota metodologica publicada junto com o relatorio"

DATAS = (datetime.date(2020, 1, 31), datetime.date(2020, 2, 29))


def _quadro(linhas):
    """Monta um DataFrame no formato que ler_padrao_a devolve.

    `linhas` e uma sequencia de (rotulo, valores), um valor por data de
    DATAS. O indice da linha vira linha_origem, como na planilha.
    """
    registros = []
    for origem, (rotulo, valores) in enumerate(linhas):
        for data, valor in zip(DATAS, valores):
            registros.append((data, origem, rotulo, valor))
    return pd.DataFrame(
        registros,
        columns=["data", "linha_origem", "rotulo", "valor_milhoes"],
    )


def test_estoque_descarta_nota_sem_valor_e_preserva_cabecalho(monkeypatch):
    """Aba 2.1: a nota sai, o cabecalho sem valor proprio fica.

    'Tesouro Nacional' tambem nao tem valor em coluna de mes nenhuma, mas e
    entidade, nao folha -- confundir os dois casos apagaria hierarquia.
    """
    quadro = _quadro([
        ("DPF EM PODER DO P\u00daBLICO", [100.0, 110.0]),
        ("Tesouro Nacional", [None, None]),
        ("LTN", [50.0, 55.0]),
        (NOTA, [None, None]),
    ])
    monkeypatch.setattr(estoque, "ler_padrao_a", lambda *a, **k: quadro)

    df = estoque.parse_dpf(None)

    assert NOTA not in set(df["titulo"].dropna())
    assert "LTN" in set(df["titulo"].dropna())
    assert "Tesouro Nacional" in set(df["entidade"].dropna())


def test_prazo_descarta_nota_sem_valor(monkeypatch):
    quadro = _quadro([
        ("DPF", [4.0, 4.1]),
        ("LTN", [2.0, 2.1]),
        (NOTA, [None, None]),
    ])
    monkeypatch.setattr(prazo, "ler_padrao_a", lambda *a, **k: quadro)

    df = prazo.parse_por_titulo(None)

    assert NOTA not in set(df["titulo"].dropna())
    assert "LTN" in set(df["titulo"].dropna())
    assert "DPF" in set(df["nivel"].dropna())


def test_custo_descarta_nota_sem_valor(monkeypatch):
    quadro = _quadro([
        ("DPMFi", [10.0, 10.5]),
        ("LTN", [9.0, 9.5]),
        (NOTA, [None, None]),
    ])
    monkeypatch.setattr(custo, "_ler_aba", lambda *a, **k: quadro)

    df = custo.parse(None)

    assert NOTA not in set(df["titulo"].dropna())
    assert "LTN" in set(df["titulo"].dropna())


def test_funding_descarta_nota_sem_valor(monkeypatch):
    """Aba 1.1/1.2: sem o `break` de 'EMISSAO LIQUIDA' a nota chega aqui.

    Na 1.2 nao existe esse `break`, e o prefixo 'Obs' era a defesa unica --
    sensivel a caixa, ainda por cima. Uma nota sem valor nao pode virar
    canal nem indexador.
    """
    quadro = _quadro([
        ("EMISS\u00d5ES", [None, None]),
        ("I - DPMFi", [None, None]),
        ("Oferta P\u00fablica", [30.0, 31.0]),
        (NOTA, [None, None]),
    ])
    monkeypatch.setattr(funding, "ler_padrao_a", lambda *a, **k: quadro)

    df = funding.parse_por_canal(None)

    assert NOTA not in set(df["canal"])
    assert "Oferta P\u00fablica" in set(df["canal"])


def test_funding_ignora_nota_em_caixa_alta(monkeypatch):
    """A 1.1 escreve 'OBS:' em maiuscula; o filtro textual precisa cobrir."""
    quadro = _quadro([
        ("RESGATES", [None, None]),
        ("III - DPMFi", [None, None]),
        ("Tesouro Direto", [7.0, 8.0]),
        ("OBS: o Tesouro Nacional passou a divulgar", [None, None]),
    ])
    monkeypatch.setattr(funding, "ler_padrao_a", lambda *a, **k: quadro)

    df = funding.parse_por_canal(None)

    assert set(df["canal"]) == {"Tesouro Direto"}
