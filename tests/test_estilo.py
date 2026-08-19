import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytest

from tesouro.graficos import estilo


def test_mes_sai_em_portugues():
    from datetime import date
    assert estilo.rotulo_mes(date(2026, 5, 31)) == "mai/26"
    assert estilo.rotulo_mes(date(2026, 12, 31)) == "dez/26"
    assert estilo.MES_LONGO[6] == "Junho"


def test_numero_sai_no_formato_brasileiro():
    assert estilo.num_br(1472.87, 2) == "1.472,87"
    assert estilo.num_br(-302.3, 1) == "-302,3"
    assert estilo.num_br(8904, 0) == "8.904"
    assert estilo.num_br(0.5, 1) == "0,5"


def test_o_svg_e_reprodutivel():
    # Sem svg.hashsalt fixo, o matplotlib sorteia ids e dois desenhos iguais
    # produzem arquivos diferentes. Sem isto, nenhum teste de reprodutibilidade
    # do dashboard e possivel.
    estilo.aplicar_estilo()

    def desenha():
        buf = io.StringIO()
        fig, ax = plt.subplots()
        ax.plot([1, 2, 3], [4, 5, 6])
        estilo.salvar_svg(fig, buf)
        plt.close(fig)
        return buf.getvalue()

    assert desenha() == desenha()


def test_o_savefig_cru_nao_e_reprodutivel_e_por_isso_o_helper_existe():
    # O hashsalt sozinho nao basta: o matplotlib escreve a data de criacao em
    # <dc:date> com precisao de microssegundo. Este teste guarda o motivo de
    # salvar_svg existir -- se um dia o matplotlib parar de escrever a data, ele
    # falha e alguem descobre que o helper virou desnecessario.
    estilo.aplicar_estilo()

    def desenha(com_helper):
        buf = io.StringIO()
        fig, ax = plt.subplots()
        ax.plot([1, 2, 3], [4, 5, 6])
        if com_helper:
            estilo.salvar_svg(fig, buf)
        else:
            fig.savefig(buf, format="svg", bbox_inches="tight")
        plt.close(fig)
        return buf.getvalue()

    cru = desenha(False)
    assert "<dc:date>" in cru
    assert "<dc:date>" not in desenha(True)


def test_o_modulo_e_ascii_puro():
    # Rotulo acentuado vai por escape Unicode, nao por byte acentuado.
    caminho = estilo.__file__
    with open(caminho, "rb") as f:
        f.read().decode("ascii")


def test_as_cores_cobrem_os_indexadores_e_os_papeis():
    for chave in ("Prefixado", "Indice Precos", "Taxa Flutuante", "Cambio"):
        assert chave in estilo.COR
    for chave in ("LTN", "NTN-F", "NTN-B", "LFT"):
        assert chave in estilo.COR


def test_todo_o_pacote_de_graficos_e_ascii():
    # A restricao vale para o pacote inteiro, nao so para o estilo. Conferir
    # arquivo por arquivo a mao nao escala para dez modulos, e o byte acentuado
    # entra sem ninguem ver.
    import pathlib
    from tesouro import graficos

    pasta = pathlib.Path(graficos.__file__).parent
    arquivos = sorted(pasta.glob("*.py"))
    assert len(arquivos) >= 3
    for arquivo in arquivos:
        with open(arquivo, "rb") as f:
            try:
                f.read().decode("ascii")
            except UnicodeDecodeError as erro:
                raise AssertionError(f"{arquivo.name} tem byte nao-ASCII: {erro}")


def test_o_corte_de_janela_preserva_o_ultimo_ponto():
    import pandas as pd
    datas = pd.date_range("2015-01-31", "2026-06-30", freq="ME")
    df = pd.DataFrame({"v": range(len(datas))}, index=datas)
    assert len(estilo.recorta(df, None)) == len(df)
    curto = estilo.recorta(df, 5)
    assert curto.index.max() == df.index.max()
    assert curto.index.min() >= df.index.max() - pd.DateOffset(years=5)
