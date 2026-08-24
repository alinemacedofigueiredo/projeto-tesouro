"""Os fluxos que o Tesouro paga: principal e cupom."""
import pandas as pd
import pytest

from tesouro import fluxos


def test_a_NTN_B_paga_no_ANIVERSARIO_dela_e_nao_em_todo_trimestre():
    # A ARMADILHA DESTA TAREFA, e ela custa 2,1 vezes o cupom se passar batido.
    # A NTN-B nao paga em todo fevereiro, maio, agosto e novembro: paga no mes do
    # vencimento DELA e seis meses antes. O estoque se divide -- 188,6 milhoes de
    # titulos vencem em maio e 267,3 em agosto -- entao agosto e novembro pagam a
    # grupos diferentes.
    maio = pd.Timestamp("2029-05-15")
    agosto = pd.Timestamp("2030-08-15")

    assert fluxos.paga_cupom_em("NTN-B", maio, pd.Timestamp("2026-05-15"))
    assert fluxos.paga_cupom_em("NTN-B", maio, pd.Timestamp("2026-11-15"))
    assert not fluxos.paga_cupom_em("NTN-B", maio, pd.Timestamp("2026-08-15"))
    assert not fluxos.paga_cupom_em("NTN-B", maio, pd.Timestamp("2026-02-15"))

    assert fluxos.paga_cupom_em("NTN-B", agosto, pd.Timestamp("2026-08-15"))
    assert fluxos.paga_cupom_em("NTN-B", agosto, pd.Timestamp("2026-02-15"))
    assert not fluxos.paga_cupom_em("NTN-B", agosto, pd.Timestamp("2026-05-15"))


def test_o_cupom_cai_no_DIA_certo_de_cada_papel():
    # NTN-B no dia 15, NTN-F no dia 1. A rolagem corta em data, e nao em mes:
    # ratear pelo mes poria dentro da janela um fluxo que ainda nao aconteceu.
    venc_b = pd.Timestamp("2030-08-15")
    assert fluxos.paga_cupom_em("NTN-B", venc_b, pd.Timestamp("2026-08-15"))
    assert not fluxos.paga_cupom_em("NTN-B", venc_b, pd.Timestamp("2026-08-14"))

    venc_f = pd.Timestamp("2031-01-01")
    assert fluxos.paga_cupom_em("NTN-F", venc_f, pd.Timestamp("2026-07-01"))
    assert not fluxos.paga_cupom_em("NTN-F", venc_f, pd.Timestamp("2026-07-15"))


def test_papel_sem_cupom_nunca_paga():
    # LTN e LFT nao pagam cupom. A NTN-B Principal tambem nao -- e ela e NTN-B no
    # nome, que e exatamente o jeito de errar.
    for titulo in ("LTN", "LFT", "NTN-B Principal"):
        assert not fluxos.paga_cupom_em(
            titulo, pd.Timestamp("2030-08-15"), pd.Timestamp("2026-08-15"))
