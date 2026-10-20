"""O cache de leitura: o que ele promete, e o que ele nao pode fazer.

O risco de um cache neste projeto nao e lentidao, e SERVIR DADO VELHO. O
pipeline grava e le o mesmo CSV dentro da mesma rodada -- parse_leiloes grava
leiloes.csv e as paginas o leem depois -- entao a invalidacao e a parte que
precisa de teste, mais do que a economia.
"""
import pandas as pd
import pytest

from tesouro import leitura


@pytest.fixture(autouse=True)
def cache_limpo():
    leitura.esquece()
    yield
    leitura.esquece()


def _grava(caminho, linhas):
    caminho.write_text("a,b\n" + "\n".join(linhas) + "\n", encoding="utf-8")


def test_le_o_mesmo_que_o_pandas(tmp_path):
    alvo = tmp_path / "x.csv"
    _grava(alvo, ["1,2", "3,4"])
    pd.testing.assert_frame_equal(leitura.csv(alvo), pd.read_csv(alvo))


def test_a_segunda_leitura_NAO_REFAZ_o_parse(tmp_path, monkeypatch):
    # O teste da economia. Se o cache sair, esta conta vai para 2 e isto fica
    # vermelho -- e era essa economia que valia 30 s por pagina do PAF.
    alvo = tmp_path / "x.csv"
    _grava(alvo, ["1,2"])

    vezes = {"n": 0}
    real = pd.read_csv

    def contado(*a, **k):
        vezes["n"] += 1
        return real(*a, **k)

    monkeypatch.setattr(leitura.pd, "read_csv", contado)
    leitura.csv(alvo)
    leitura.csv(alvo)
    leitura.csv(alvo)
    assert vezes["n"] == 1, "o cache nao economizou parse nenhum"


def test_arquivo_REESCRITO_com_outro_tamanho_e_relido(tmp_path):
    alvo = tmp_path / "x.csv"
    _grava(alvo, ["1,2"])
    assert len(leitura.csv(alvo)) == 1
    _grava(alvo, ["1,2", "3,4", "5,6"])
    assert len(leitura.csv(alvo)) == 3, "serviu o quadro velho"


def test_arquivo_REESCRITO_com_o_MESMO_tamanho_e_relido(tmp_path):
    # O caso dificil, e o que de fato acontece: um CSV regravado com o mesmo
    # numero de linhas e outros valores. Aqui so o carimbo do arquivo salva, e
    # e por isso que a chave inclui st_mtime_ns.
    alvo = tmp_path / "x.csv"
    _grava(alvo, ["1,2"])
    assert int(leitura.csv(alvo)["b"].iloc[0]) == 2
    _grava(alvo, ["1,9"])
    assert int(leitura.csv(alvo)["b"].iloc[0]) == 9, \
        "mesmo tamanho, conteudo novo: o cache serviu o velho"


def test_quem_mexe_no_quadro_NAO_suja_a_proxima_leitura(tmp_path):
    # Por isso leitura.csv devolve copia. Sem ela, a segunda chamada receberia
    # a coluna que a primeira acrescentou -- e os chamadores deste projeto
    # acrescentam coluna o tempo todo (ver curva._curva, que poe "du").
    alvo = tmp_path / "x.csv"
    _grava(alvo, ["1,2"])
    primeiro = leitura.csv(alvo)
    primeiro["inventada"] = 99
    primeiro.loc[0, "a"] = -1

    segundo = leitura.csv(alvo)
    assert "inventada" not in segundo.columns
    assert int(segundo["a"].iloc[0]) == 1


def test_o_parse_dates_entra_na_chave(tmp_path):
    # Dois pedidos do MESMO arquivo com parse_dates diferente sao resultados
    # diferentes. Se a chave ignorasse o argumento, o segundo pedido receberia
    # a coluna como texto -- ou como data -- conforme quem chegou primeiro.
    alvo = tmp_path / "d.csv"
    alvo.write_text("data,v\n2026-01-31,1\n", encoding="utf-8")
    cru = leitura.csv(alvo)
    datado = leitura.csv(alvo, parse_dates=["data"])
    # O pandas desta versao le texto como str e nao como object, entao o teste
    # afirma o que importa: um NAO e data e o outro E.
    assert not str(cru["data"].dtype).startswith("datetime")
    assert str(datado["data"].dtype).startswith("datetime")


def test_argumento_que_a_chave_nao_representa_e_RECUSADO(tmp_path):
    # Melhor recusar do que cachear errado. 'nrows' muda o resultado e nao
    # entra na chave: servir o quadro inteiro a quem pediu duas linhas seria um
    # numero plausivel e errado.
    alvo = tmp_path / "x.csv"
    _grava(alvo, ["1,2", "3,4"])
    with pytest.raises(LookupError, match="nrows"):
        leitura.csv(alvo, nrows=1)


def test_o_cache_tem_teto(tmp_path):
    # Um laco que lesse arquivo gerado em serie nao pode crescer sem limite.
    for i in range(leitura._TETO + 5):
        alvo = tmp_path / ("x%d.csv" % i)
        _grava(alvo, ["%d,%d" % (i, i)])
        leitura.csv(alvo)
    assert leitura.quantos() <= leitura._TETO
