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

        Prefixado         1.887,2278
        Indice Precos     2.157,3492
        Taxa Flutuante    4.901,0258
        Cambio              347,1316
        Total             9.292,7344

    REMEDIDO para o RMD de agosto/2026 em 07/10/2026. Os valores saem das
    CELULAS CRUAS da aba 2.4, localizando a coluna pelo cabecalho da linha 4 --
    nao pelo nosso parser, que e justamente o que este teste existe para
    conferir. Conferido na hora: o CSV concorda na casa decimal, ou seja o
    parser le a coluna certa.

    Se o nosso parser passar a ler a coluna errada, este teste fica vermelho --
    e nenhuma ancora de valor do tipo 3.1 pegaria isso, porque todas elas
    comparam numero contra numero DEPOIS do parser.
    """
    from tesouro import config

    do_anexo = {
        "Prefixado": 1887.2278,
        "\u00cdndice Pre\u00e7os": 2157.3492,
        "Taxa Flutuante": 4901.0258,
        "C\u00e2mbio": 347.1316,
    }
    nosso = pd.read_csv(config.PROCESSED_DIR / "composicao_dpf.csv")
    ultimo = nosso[nosso["data"] == nosso["data"].max()]
    por_indexador = ultimo.set_index("indexador")["valor_milhoes"] / 1000

    for indexador, esperado in do_anexo.items():
        obtido = float(por_indexador[indexador])
        assert obtido == pytest.approx(esperado, abs=0.001), (
            f"{indexador}: o anexo diz {esperado}, o nosso CSV diz {obtido}")

    assert float(por_indexador.sum()) == pytest.approx(9292.7344, abs=0.001)
