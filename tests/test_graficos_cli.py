"""A linha de comando do dashboard.

Os testes gravam sempre em tmp_path: nenhum deles escreve em data/processed/, e
muito menos em data/raw/, que e dado insubstituivel.
"""
import matplotlib
matplotlib.use("Agg")
import pytest

from tesouro.graficos import __main__ as cli


def test_sem_argumento_gera_as_duas_janelas(tmp_path):
    saida = tmp_path / "dashboard.html"
    assert cli.main(["--saida", str(saida)]) == 0
    html = saida.read_text(encoding="utf-8")
    assert 'id="troca-periodo"' in html
    assert 'data-janela="5 anos"' in html
    assert 'data-janela="completa"' in html


def test_com_de_e_ate_gera_uma_janela_so_e_sem_botao(tmp_path):
    saida = tmp_path / "recorte.html"
    codigo = cli.main(["--de", "2021-01-01", "--ate", "2026-06-30",
                       "--saida", str(saida)])
    assert codigo == 0
    html = saida.read_text(encoding="utf-8")
    assert 'id="troca-periodo"' not in html
    assert 'data-janela="completa"' not in html
    # O recorte pedido vira o nome da janela, e aparece no atributo do bloco.
    assert 'data-janela="2021-01-01 a 2026-06-30"' in html


def test_de_sem_ate_falha_com_mensagem(tmp_path, capsys):
    codigo = cli.main(["--de", "2021-01-01", "--saida", str(tmp_path / "x.html")])
    assert codigo == 2
    assert "--ate" in capsys.readouterr().err
    assert not (tmp_path / "x.html").exists(), "nao pode gravar arquivo pela metade"


def test_data_invalida_falha_alto(tmp_path, capsys):
    codigo = cli.main(["--de", "01/01/2021", "--ate", "2026-06-30",
                       "--saida", str(tmp_path / "x.html")])
    assert codigo == 2
    erro = capsys.readouterr().err
    assert "AAAA-MM-DD" in erro
    assert not (tmp_path / "x.html").exists()


def test_ate_antes_de_de_falha(tmp_path, capsys):
    codigo = cli.main(["--de", "2026-01-01", "--ate", "2021-01-01",
                       "--saida", str(tmp_path / "x.html")])
    assert codigo == 2
    assert "anterior" in capsys.readouterr().err.lower()


def test_a_documentacao_ensina_powershell_antes_de_bash():
    # Sintaxe bash sozinha falha na primeira linha no shell da usuaria, e isso ja
    # quebrou quatro vezes neste projeto.
    from tesouro import config

    texto = (config.RAIZ / "README.md").read_text(encoding="utf-8")
    assert "python -m tesouro.graficos" in texto
    assert "dashboard.html" in texto

    pedaco = texto[texto.index("python -m tesouro.graficos") - 400:]
    posicao_ps = pedaco.index("$env:PYTHONPATH")
    posicao_bash = pedaco.index("PYTHONPATH=src python -m tesouro.graficos")
    assert posicao_ps < posicao_bash, "o bloco do bash veio antes do PowerShell"
