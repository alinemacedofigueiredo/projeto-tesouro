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


def test_papel_vencido_nao_paga_mesmo_no_mes_certo():
    # A GUARDA SIMETRICA A DO ANIVERSARIO: cair no mes certo (multiplo de 6) nao
    # basta se "quando" e POSTERIOR ao vencimento -- o papel ja foi resgatado.
    # Uma NTN-B que venceu em 15/08/2026 nao paga em 15/02/2027, ainda que
    # fevereiro diste seis meses de agosto.
    venc = pd.Timestamp("2026-08-15")
    assert not fluxos.paga_cupom_em("NTN-B", venc, pd.Timestamp("2027-02-15"))


def test_vencimento_ausente_nao_paga():
    # pd.NaT chega quando o titulo nao tem vencimento conhecido no estoque (e o
    # que "parse_dates" produz para celula vazia -- nunca None, entao None nao e
    # entrada real desta funcao e nao teria dado dentes de verdade). A guarda de
    # "pd.isna(...)" e REDUNDANTE POR CONSTRUCAO aqui: com NaT, tanto
    # "quando.day != DIA_DO_CUPOM[titulo]" quanto "(NaT.month - quando.month) % 6
    # == 0" ja devolvem False sozinhas, porque NaT.month e nan e nan nunca fecha
    # o modulo 6. A guarda fica mesmo assim, por ser o idioma do projeto (guardas
    # de pandas usam pd.isna, nao a semantica acidental de NaN) -- um leitor
    # futuro nao deveria precisar saber que "nan % 6 == 0" e False para confiar
    # na funcao. ESTE TESTE NAO TEM DENTES E NAO PODE TER: tirar a guarda nao o
    # faz reprovar. Registrado aqui para nao fingir uma cobertura que nao existe.
    assert not fluxos.paga_cupom_em(
        "NTN-B", pd.NaT, pd.Timestamp("2026-08-15"))
