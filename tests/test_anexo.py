"""O leitor do anexo, que existe para NAO passar pelo nosso parser."""
import pandas as pd
import pytest

import anexo


def test_o_anexo_e_escolhido_pelo_NOME_e_nao_pelo_mtime():
    """A escolha por mtime e fragil dentro do OneDrive.

    leitura_rmd.caminho_do_rmd() usa max(..., key=mtime). O OneDrive reescreve
    arquivo por conta propria; se tocasse no anexo de junho, o leitor passaria a
    ler junho em silencio e as ancoras de julho seriam conferidas contra o mes
    errado. Este leitor existe para conferir ancora, entao escolhe pelo nome.
    """
    assert "Julho" in anexo.caminho("julho").name
    assert "Junho" in anexo.caminho("junho").name
    assert anexo.caminho("julho") != anexo.caminho("junho")


def test_pede_mes_que_nao_existe_e_erro_claro():
    with pytest.raises(FileNotFoundError, match="marco"):
        anexo.caminho("marco")


def test_a_aba_vem_crua_e_nao_interpretada():
    """Se viesse com header, ja seria interpretacao -- e interpretacao e o que
    este modulo existe para evitar."""
    bruto = anexo.aba("2.4")
    assert isinstance(bruto, pd.DataFrame)
    assert len(bruto) > 5
    # header=None: as colunas sao inteiros, e nao rotulos ja lidos por alguem.
    assert list(bruto.columns) == list(range(len(bruto.columns)))


def test_a_composicao_do_nosso_CSV_bate_com_o_anexo():
    """CAMADA 1 da spec, secao 4: o valor vem da fonte, e nao de nos.

    Medido a mao em 26/08/2026 contra o anexo de julho, aba 2.4, em R$ bilhoes:

        Prefixado         1.785,3461
        Indice Precos     2.417,3288
        Taxa Flutuante    4.747,2540
        Cambio              338,8513
        Total             9.288,7803

    Se o nosso parser passar a ler a coluna errada, este teste fica vermelho --
    e nenhuma ancora de valor do tipo 3.1 pegaria isso, porque todas elas
    comparam numero contra numero DEPOIS do parser.
    """
    from tesouro import config

    do_anexo = {
        "Prefixado": 1785.3461,
        "\u00cdndice Pre\u00e7os": 2417.3288,
        "Taxa Flutuante": 4747.2540,
        "C\u00e2mbio": 338.8513,
    }
    nosso = pd.read_csv(config.PROCESSED_DIR / "composicao_dpf.csv")
    ultimo = nosso[nosso["data"] == nosso["data"].max()]
    por_indexador = ultimo.set_index("indexador")["valor_milhoes"] / 1000

    for indexador, esperado in do_anexo.items():
        obtido = float(por_indexador[indexador])
        assert obtido == pytest.approx(esperado, abs=0.001), (
            f"{indexador}: o anexo diz {esperado}, o nosso CSV diz {obtido}")

    assert float(por_indexador.sum()) == pytest.approx(9288.7803, abs=0.001)
