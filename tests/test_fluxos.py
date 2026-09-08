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
    # A JANELA COMECA NA DATA-BASE DO RMD (30/06/2026), NAO EM 01/07. Comecar em
    # 01/07 exclui os proprios vencimentos daquele dia -- 215,8 bi de LTN e
    # NTN-F, mais o cupom de NTN-F do mesmo dia -- porque a janela e (de, ate] e
    # 01/07 nao e posterior a 01/07. E o uso real (a rolagem encadeia a partir da
    # data-base) que fixa esses limites: 736.381 milhoes de principal e 100.179
    # de cupom, medidos com a janela certa.
    d = fluxos.pagos(pd.Timestamp("2026-06-30"), pd.Timestamp("2026-12-31"))
    assert set(d.columns) >= {"data", "indexador", "principal_milhoes",
                              "cupom_milhoes"}
    assert d["principal_milhoes"].sum() > 700000
    assert 80000 < d["cupom_milhoes"].sum() < 120000


def test_o_cupom_da_NTN_F_nao_estoura_porque_ela_e_prefixada():
    # A NTN-F paga cupom em 01/01 e 01/07 e nao tem VNA -- e prefixada, paga
    # sobre a face de 1.000. _INDICE_DO_VNA so tem entrada para papel indexado
    # (Indice Precos, Taxa Flutuante); buscar "Prefixado" nele com [] e KeyError,
    # e estoura em qualquer janela que contenha 01/01 ou 01/07. A janela do
    # teste anterior comeca em 01/07 e por isso nunca pegava esse dia -- (de,
    # ate] exclui o proprio 01/07 quando de == 01/07. Aqui a janela comeca antes
    # e cobre o dia.
    d = fluxos.pagos(pd.Timestamp("2026-06-30"), pd.Timestamp("2026-07-02"))
    cupom_prefixado = d[(d["data"] == pd.Timestamp("2026-07-01"))
                        & (d["indexador"] == "Prefixado")]["cupom_milhoes"]
    assert cupom_prefixado.sum() > 0


def test_os_rotulos_de_INDEXADOR_batem_com_o_composicao_dpf():
    # INDEXADOR NAO E ROTULO LIVRE, E DADO: a rolagem filtra
    # pagou[pagou["indexador"] == "..."] contra os mesmos valores que
    # composicao_dpf.csv usa. Se o rotulo aqui nao bater byte a byte com o do
    # CSV (por exemplo por causa da regra ASCII do arquivo-fonte, que exige
    # escapar o acento), o filtro nao acha nada e o termo de fluxo pago vira
    # zero em silencio -- sem excecao, sem teste que capture, so um numero
    # errado la na frente.
    from tesouro import config

    c = pd.read_csv(config.PROCESSED_DIR / "composicao_dpf.csv")
    do_csv = set(c["indexador"].unique())
    assert set(fluxos.INDEXADOR.values()) <= do_csv


def test_a_janela_e_fechada_a_direita_e_aberta_a_esquerda():
    # (de, ate]. A rolagem encadeia janelas, e sobreposicao de um dia conta um
    # vencimento duas vezes.
    quinze = pd.Timestamp("2026-08-15")
    dentro = fluxos.pagos(pd.Timestamp("2026-08-14"), quinze)
    fora = fluxos.pagos(quinze, pd.Timestamp("2026-08-16"))
    assert dentro["principal_milhoes"].sum() > 0
    assert fora["principal_milhoes"].sum() == 0


def test_a_ntn_c_paga_cupom_no_dia_1_e_nao_no_15():
    """O dia do cupom da NTN-C tem de bater com o dia do VENCIMENTO dela.

    ESTA E UMA RELACAO, E NAO UM VALOR MEDIDO: ela le os vencimentos de NTN-C do
    estoque corrente e exige que DIA_DO_CUPOM concorde com eles. Vale em
    qualquer RMD, e passa a valer sozinha se um dia o Tesouro emitir uma NTN-C
    com outro vencimento.

    O QUE ELA PEGA e o defeito que existia ate 08/09/2026, e que nao era cupom
    faltando: com 15 no lugar de 1, a regra do mes continuava batendo e o
    pagamento saia em 15/01/2027 em vez de 01/01/2027. Duas semanas de atraso,
    R$ 3 a 4 bi no mes errado, soma anual intacta -- o tipo de erro que a soma
    esconde.
    """
    import pandas as pd

    from tesouro import config

    estoque = pd.read_csv(config.PROCESSED_DIR / "estoque_titulos_vencimento.csv")
    ntnc = estoque[estoque["titulo"] == "NTN-C"]
    assert not ntnc.empty, "a NTN-C sumiu do estoque, e nao do teste"

    dias = {pd.Timestamp(v).day for v in ntnc["vencimento"].dropna().unique()}
    assert dias == {fluxos.DIA_DO_CUPOM["NTN-C"]}, (
        "os vencimentos de NTN-C caem nos dias %s, e DIA_DO_CUPOM diz %s"
        % (sorted(dias), fluxos.DIA_DO_CUPOM["NTN-C"]))


def test_o_cupom_da_ntn_c_2031_cai_em_01_01_e_nao_em_15_01():
    """O caso concreto do unico papel vivo, escrito por extenso.

    A relacao acima morre se a NTN-C sair do estoque; esta fica, e diz que
    janeiro e julho de 2027 pagam no dia 1.
    """
    import pandas as pd

    venc = pd.Timestamp("2031-01-01")
    assert fluxos.paga_cupom_em("NTN-C", venc, pd.Timestamp("2027-01-01"))
    assert fluxos.paga_cupom_em("NTN-C", venc, pd.Timestamp("2027-07-01"))
    assert not fluxos.paga_cupom_em("NTN-C", venc, pd.Timestamp("2027-01-15"))
    assert not fluxos.paga_cupom_em("NTN-C", venc, pd.Timestamp("2027-04-01"))
