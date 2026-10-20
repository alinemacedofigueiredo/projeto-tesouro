"""O atalho atualizar.cmd: as tres coisas que ele nao pode perder.

Ele nao tinha teste nenhum, e carrega duas armadilhas ja medidas, escritas nos
comentarios dele. Teste de FONTE, de proposito: rodar o .cmd de verdade abre
janela do Explorer e roda o pipeline inteiro, e o que se quer travar aqui e a
forma do arquivo.
"""
import pathlib

import pytest

ATALHO = pathlib.Path(__file__).resolve().parents[1] / "atualizar.cmd"


@pytest.fixture(scope="module")
def linhas():
    assert ATALHO.exists(), "o atalho sumiu da raiz do projeto"
    return [l.rstrip() for l in ATALHO.read_text(encoding="utf-8").splitlines()]


def _sem_comentario(linhas):
    return [l for l in linhas if l.strip() and not l.strip().lower().startswith("rem")]


def test_o_codigo_de_saida_e_guardado_ANTES_de_qualquer_echo(linhas):
    # A ARMADILHA MEDIDA: no .cmd o errorlevel que sobra e o do ultimo comando,
    # e o pause devolve sempre 0. Com --modo inexistente o atalho saia com 0, e
    # quem olha codigo de saida achava que tinha dado certo. E a mesma armadilha
    # do "pytest | tail".
    uteis = _sem_comentario(linhas)
    guarda = [i for i, l in enumerate(uteis)
              if l.lower().startswith("set codigo=%errorlevel%")]
    assert len(guarda) == 1, "a captura do errorlevel sumiu ou duplicou"

    antes = uteis[:guarda[0]]
    poluentes = [l for l in antes
                 if l.lower().startswith(("echo", "pause", "start"))]
    assert not poluentes, (
        "estes comandos rodam ANTES de guardar o errorlevel e o estragam: %s"
        % poluentes)


def test_o_atalho_PARA_no_fim_para_a_janela_nao_fechar(linhas):
    # Clicando duas vezes, a janela fecharia junto com o programa e levaria o
    # resultado embora -- inclusive o 'concluido' e a lista de paginas.
    uteis = _sem_comentario(linhas)
    assert any(l.lower().startswith("pause") for l in uteis), \
        "sem pause, o duplo-clique leva o resultado embora"


def test_a_tecla_do_fim_abre_a_pasta_das_paginas(linhas):
    # PERGUNTA DELA em 20/10/2026: "como clico duas vezes nos links do cmd? nao
    # funciona isso, parece". Nao funciona -- na janela aquilo e texto. E depois
    # do pause a janela fecha, entao nao sobra onde digitar nada. A tecla que
    # ela ja aperta passa a abrir a pasta, onde o clique funciona.
    uteis = _sem_comentario(linhas)
    abre = [l for l in uteis if l.lower().startswith("start")]
    assert len(abre) == 1, "a linha que abre a pasta sumiu ou duplicou"

    # O CAMINHO E RELATIVO AO PROPRIO ARQUIVO (%~dp0), e nao cravado: o atalho
    # tem de continuar funcionando no dia em que o projeto mudar de lugar.
    assert "%~dp0" in abre[0], abre[0]
    assert "data" in abre[0] and "processed" in abre[0], abre[0]
    assert "C:\\\\Users" not in abre[0], "caminho cravado no atalho"

    # E a pasta que ele abre existe de verdade na arvore do projeto.
    assert (ATALHO.parent / "data" / "processed").is_dir()


def test_o_atalho_passa_as_bandeiras_adiante(linhas):
    # 'atualizar.cmd --modo paf' tem de chegar no pipeline. E assim que se roda
    # um modo sem passar pelo menu.
    uteis = _sem_comentario(linhas)
    chamada = [l for l in uteis if "tesouro.pipeline" in l]
    assert len(chamada) == 1, chamada
    assert "%*" in chamada[0], "as bandeiras nao chegam no pipeline"
