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

# Os dezesseis arquivos que ja tinham byte acentuado quando esta branch nasceu, e
# que vieram das entregas anteriores. Sao DIVIDA CONHECIDA, nao excecao permitida:
# ficam listados um a um para que a lista so possa encolher, e para que ninguem
# acrescente o dezessetimo sem editar esta constante e explicar por que.
#
# A alternativa -- varrer so src/tesouro/graficos/ -- esconderia a divida em vez de
# registra-la, e foi ela que deixou dois testes novos entrarem acentuados.
_DIVIDA_NAO_ASCII = {
    "src/tesouro/parse_rmd/custo.py",
    "src/tesouro/parse_rmd/estoque.py",
    "src/tesouro/parse_rmd/estoque_vencimento.py",
    "src/tesouro/parse_rmd/funding.py",
    "src/tesouro/parse_rmd/paf_reserva.py",
    "src/tesouro/parse_rmd/prazo.py",
    "tests/test_custo.py",
    "tests/test_estoque.py",
    "tests/test_estoque_vencimento.py",
    "tests/test_funding.py",
    "tests/test_leitura_rmd.py",
    "tests/test_nota_de_rodape.py",
    "tests/test_paf_reserva.py",
    "tests/test_parse_leiloes.py",
    "tests/test_prazo.py",
    "tests/test_vencimentos.py",
}


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
