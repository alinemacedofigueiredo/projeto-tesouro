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

# A lista dos arquivos que podem ter byte acentuado. VAZIA, e assim deve ficar.
#
# Ela nasceu com dezesseis nomes -- os que vieram das entregas anteriores e ja
# estavam acentuados quando esta branch comecou. Foram todos escapados em 19/08/2026,
# depois do merge, quando deixaram de ser "codigo de outra entrega" e passaram a ser
# o projeto. A lista fica aqui, vazia, porque e ela que faz o teste falhar de dois
# lados: acentuar um arquivo novo quebra, e quitar um da lista sem tirar da lista
# tambem quebra.
_DIVIDA_NAO_ASCII = set()


def test_todo_o_projeto_e_ascii():
    # A restricao vale para o projeto inteiro, nao so para o pacote de graficos --
    # o varredor antigo olhava so src/tesouro/graficos/, e foi por isso que dois
    # testes novos entraram acentuados sem nada acusar.
    from tesouro import config

    arquivos = sorted(config.RAIZ.glob("src/**/*.py")) +         sorted(config.RAIZ.glob("tests/**/*.py"))
    assert len(arquivos) >= 30, f"so {len(arquivos)} arquivos; a varredura encolheu"

    acentuados = set()
    for arquivo in arquivos:
        if any(b > 127 for b in arquivo.read_bytes()):
            acentuados.add(arquivo.relative_to(config.RAIZ).as_posix())

    novos = sorted(acentuados - _DIVIDA_NAO_ASCII)
    assert not novos, (
        f"byte nao-ASCII em arquivo que esta branch controla: {novos}. "
        f"Texto que o usuario le vai por escape Unicode."
    )
    # E a divida so pode encolher: quando alguem limpar um dos dezesseis, este
    # teste avisa para tirar da lista.
    quitados = sorted(_DIVIDA_NAO_ASCII - acentuados)
    assert not quitados, f"ja estao ASCII e podem sair de _DIVIDA_NAO_ASCII: {quitados}"


def test_o_corte_de_janela_preserva_o_ultimo_ponto():
    import pandas as pd
    datas = pd.date_range("2015-01-31", "2026-06-30", freq="ME")
    df = pd.DataFrame({"v": range(len(datas))}, index=datas)
    assert len(estilo.recorta(df, None)) == len(df)
    curto = estilo.recorta(df, 5)
    assert curto.index.max() == df.index.max()
    assert curto.index.min() >= df.index.max() - pd.DateOffset(years=5)


def test_o_eixo_do_tempo_acompanha_o_TAMANHO_da_janela():
    # Com 'a_cada' fixo, a janela de 12 meses -- que entrou no dashboard em
    # 21/08/2026 -- saia com UM rotulo, o unico ano que ela atravessa. O grafico
    # ficava sem eixo do tempo. Visto na figura, e nao no codigo.
    import pandas as pd

    def quantos(anos, a_cada=2):
        fim = pd.Timestamp("2026-06-30")
        idx = pd.date_range(fim - pd.DateOffset(years=anos), fim, freq="ME")
        fig, ax = plt.subplots()
        ax.plot(idx, range(len(idx)))
        estilo.eixo_anual(ax, a_cada=a_cada)
        fig.canvas.draw()
        rotulos = [t.get_text() for t in ax.get_xticklabels() if t.get_text()]
        plt.close(fig)
        return rotulos

    doze = quantos(1)
    assert len(doze) >= 4, f"janela de 12 meses com {len(doze)} rotulos: {doze}"
    # E em mes/ano, que e o que distingue um ponto do outro dentro de um ano.
    assert any("/" in r for r in doze), doze

    tres = quantos(3)
    assert len(tres) >= 3, tres

    # Na serie longa nada muda: continua ano a ano, com o passo pedido.
    longa = quantos(25)
    assert len(longa) >= 10
    assert all(r.isdigit() and len(r) == 4 for r in longa), longa
