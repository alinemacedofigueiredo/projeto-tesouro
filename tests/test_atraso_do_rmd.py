"""O aviso de RMD atrasado: existe RMD mais novo que o carregado?"""
import pandas as pd

from tesouro import leitura_rmd


# O RMD de base 31/07/2026 entrou em disco em 26/08/2026 -- medido no proprio
# arquivo dela. E a unica medicao que temos do atraso de publicacao, e e a base
# da regra: o anexo de base M sai ate o fim do mes M+1.
BASE_JULHO = (2026, 7)


def test_dois_meses_atras_AVISA():
    # 02/10/2026 com julho carregado: o de agosto saiu ate o fim de setembro,
    # entao ela esta atrasada e nao tem como saber olhando a pagina.
    aviso = leitura_rmd.aviso_de_atraso(BASE_JULHO, hoje=pd.Timestamp("2026-10-02"))
    assert aviso is not None
    assert "julho" in aviso.lower()
    assert "agosto" in aviso.lower()


def test_um_mes_atras_NAO_avisa():
    # 05/09/2026 com julho carregado: o de agosto PODE nao ter saido ainda -- o
    # de julho so apareceu em 26/08. Avisar aqui seria crer lobo, e um aviso que
    # aparece quando nao precisa deixa de ser lido quando precisa.
    assert leitura_rmd.aviso_de_atraso(
        BASE_JULHO, hoje=pd.Timestamp("2026-09-05")) is None


def test_no_fim_do_mes_seguinte_ainda_NAO_avisa():
    # 30/09/2026: o de agosto provavelmente saiu, mas "provavelmente" nao basta
    # para um aviso. A regra e conservadora de proposito -- so fala quando o
    # anexo faltante JA PASSOU do prazo inteiro dele.
    assert leitura_rmd.aviso_de_atraso(
        BASE_JULHO, hoje=pd.Timestamp("2026-09-30")) is None


def test_em_dia_NAO_avisa():
    assert leitura_rmd.aviso_de_atraso(
        (2026, 9), hoje=pd.Timestamp("2026-10-02")) is None


def test_virada_de_ano_conta_certo():
    # Dezembro carregado, fevereiro corrente: um mes de atraso (janeiro), nao
    # avisa. Marco: dois, avisa. A conta nao pode ser subtracao de mes solta.
    assert leitura_rmd.aviso_de_atraso(
        (2025, 12), hoje=pd.Timestamp("2026-02-10")) is None
    aviso = leitura_rmd.aviso_de_atraso(
        (2025, 12), hoje=pd.Timestamp("2026-03-10"))
    assert aviso is not None
    assert "dezembro" in aviso.lower() and "janeiro" in aviso.lower()


def test_o_aviso_DIZ_O_QUE_FAZER():
    aviso = leitura_rmd.aviso_de_atraso(BASE_JULHO,
                                        hoje=pd.Timestamp("2026-10-02"))
    assert "rmd" in aviso.lower()
    # O caminho que funciona mesmo com o certificado travado.
    assert "navegador" in aviso.lower()


def test_o_aviso_sabe_ler_o_que_esta_em_DISCO_sozinho():
    # Sem argumento, descobre o mes carregado pelo nome do arquivo -- e o que o
    # pipeline chama. So confere que nao estoura e que concorda com o disco.
    base = leitura_rmd.mes_base_carregado()
    assert base is not None, "nao achei RMD em disco para medir"
    ano, mes = base
    assert 2000 < ano < 2100 and 1 <= mes <= 12
    # O mesmo resultado passando a base a mao.
    hoje = pd.Timestamp("2026-10-02")
    assert (leitura_rmd.aviso_de_atraso(hoje=hoje)
            == leitura_rmd.aviso_de_atraso(base, hoje=hoje))


def test_o_pipeline_MOSTRA_o_aviso_no_FIM(monkeypatch, capsys):
    # NO FIM, e nao no meio. A licao da agenda em 24/09/2026: um AVISO impresso
    # cinco linhas acima do "concluido." nao e lido. Este sai depois de tudo,
    # junto da ultima linha da tela.
    #
    # E NAO derruba o codigo de saida: nao e falha do projeto, e dado que nao
    # chegou. Derrubar transformaria "falta trazer o RMD" em "a rodada quebrou".
    import tesouro.pipeline as pipeline
    from tesouro import leitura_rmd

    import test_pipeline as tp

    chamadas = []
    tp._stub_gravacoes(monkeypatch, chamadas)
    tp._stub_coletas(monkeypatch, chamadas)
    monkeypatch.setattr(leitura_rmd, "aviso_de_atraso",
                        lambda *a, **k: "ADVERTENCIA: RMD velho, faca isso")

    codigo = pipeline.main(["--modo", "leiloes"])
    saida = capsys.readouterr().out

    assert codigo == 0, "RMD atrasado nao e falha da rodada"
    assert "ADVERTENCIA: RMD velho" in saida
    depois_do_concluido = saida.rsplit("concluido.", 1)
    assert len(depois_do_concluido) == 2
    assert "ADVERTENCIA" in depois_do_concluido[1], (
        "o aviso saiu ANTES do concluido. -- e ali ninguem le")


def test_sem_atraso_o_pipeline_NAO_fala_nada(monkeypatch, capsys):
    import tesouro.pipeline as pipeline
    from tesouro import leitura_rmd

    import test_pipeline as tp

    chamadas = []
    tp._stub_gravacoes(monkeypatch, chamadas)
    tp._stub_coletas(monkeypatch, chamadas)
    monkeypatch.setattr(leitura_rmd, "aviso_de_atraso", lambda *a, **k: None)

    pipeline.main(["--modo", "leiloes"])
    assert "ADVERTENCIA" not in capsys.readouterr().out
