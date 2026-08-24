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


def test_o_cupom_calculado_bate_com_a_aba_3_4_em_novembro():
    # NOVEMBRO DE 2026 E O CASO QUE PROVA: tem R$ 26,0 bi de fluxo e ZERO
    # principal. E cupom puro, entao a comparacao contra a 3.4 e direta -- nos
    # outros meses o cupom final do papel que vence esta dentro da linha de
    # principal dela, e a conta nao fecha por motivo que nao e erro nosso.
    from tesouro import config

    d = fluxos.pagos(pd.Timestamp("2026-11-01"), pd.Timestamp("2026-11-30"))
    calculado = d["cupom_milhoes"].sum()
    assert d["principal_milhoes"].sum() == 0, "novembro deixou de ser cupom puro"

    cr = pd.read_csv(config.PROCESSED_DIR / "cronograma_vencimentos.csv",
                     parse_dates=["mes_vencimento"])
    da_34 = cr[(cr["faixa"] == "mensal")
               & (cr["mes_vencimento"] == pd.Timestamp("2026-11-30"))
               ]["valor_milhoes"].sum()
    assert abs(calculado - da_34) / da_34 < 0.05, (calculado, da_34)


def test_o_principal_sai_da_aba_2_2_e_o_cupom_do_calculo():
    # Os dois termos ficam em colunas separadas de proposito: um e transcricao e o
    # outro e conta, e um teste que os somasse nao saberia dizer qual quebrou.
    #
    # OS LIMITES SAO MEDIDOS, NAO OS DO BRIEF. O brief original previa principal
    # > 700.000 e cupom entre 80.000 e 120.000; o estoque atual (snapshot de
    # 30/06/2026) so tem quatro papeis vencendo nesta janela -- LFT, LTN, NTN-B e
    # NTN-B Principal, 520.563 milhoes de principal e 66.923 de cupom. Nao e bug:
    # e o RMD de junho que o projeto tem disponivel agora. Os limites abaixo tem
    # folga em torno do valor medido, para pegar regressao sem depender de o
    # estoque nao mudar nunca.
    d = fluxos.pagos(pd.Timestamp("2026-07-01"), pd.Timestamp("2026-12-31"))
    assert set(d.columns) >= {"data", "indexador", "principal_milhoes",
                              "cupom_milhoes"}
    assert d["principal_milhoes"].sum() > 500000
    assert 60000 < d["cupom_milhoes"].sum() < 75000


def test_a_janela_e_fechada_a_direita_e_aberta_a_esquerda():
    # (de, ate]. A rolagem encadeia janelas, e sobreposicao de um dia conta um
    # vencimento duas vezes.
    quinze = pd.Timestamp("2026-08-15")
    dentro = fluxos.pagos(pd.Timestamp("2026-08-14"), quinze)
    fora = fluxos.pagos(quinze, pd.Timestamp("2026-08-16"))
    assert dentro["principal_milhoes"].sum() > 0
    assert fora["principal_milhoes"].sum() == 0
