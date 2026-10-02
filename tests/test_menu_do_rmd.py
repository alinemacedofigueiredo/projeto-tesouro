"""O menu do RMD: qual anexo esta carregado, e onde pegar outro.

SUBSTITUI test_atraso_do_rmd.py. Aquele cobria um aviso no FIM da rodada, que
foi a minha primeira versao e que ela recusou -- "nao quero assim". No fim, a
informacao chega depois de a decisao ter sido tomada.
"""


def test_o_menu_DIZ_qual_rmd_esta_carregado_e_onde_pegar_outro(monkeypatch):
    # PEDIDO DELA em 02/10/2026, com estas palavras: "quero que qdo eu coloque
    # 1, ele me fale, o ultimo rmd e da data XX/YYYY. se quiser um rmd novo,
    # entre no site ... e coloque o arquivo na pasta ...".
    import tesouro.pipeline as pipeline
    from tesouro import config, fetch_rmd, leitura_rmd

    linhas = []
    monkeypatch.setattr(leitura_rmd, "mes_base_carregado",
                        lambda *a, **k: (2026, 7))
    pipeline.escolher_rmd_no_menu(entrada=lambda _: "", saida=linhas.append)
    texto = "\n".join(linhas)

    # 1. QUAL ESTA CARREGADO, com mes e ano.
    assert "julho" in texto.lower()
    assert "2026" in texto
    # 2. O SITE. A URL vem do modulo que a usa, e nao escrita no teste nem na
    #    mensagem -- caminho repetido a mao e caminho que fica errado.
    assert fetch_rmd.BASE in texto
    # 3. A PASTA, caminho completo: ela vai colar no Explorer.
    assert str(config.RMD_DIR) in texto


def test_o_menu_funciona_mesmo_sem_anexo_em_disco(monkeypatch):
    # Maquina nova, pasta vazia: nao da para dizer qual esta carregado, e a
    # mensagem tem de continuar util em vez de mentir um mes.
    import tesouro.pipeline as pipeline
    from tesouro import config, fetch_rmd, leitura_rmd

    linhas = []
    monkeypatch.setattr(leitura_rmd, "mes_base_carregado", lambda *a, **k: None)
    pipeline.escolher_rmd_no_menu(entrada=lambda _: "", saida=linhas.append)
    texto = "\n".join(linhas)

    assert fetch_rmd.BASE in texto
    assert str(config.RMD_DIR) in texto
    assert "None" not in texto, "vazou o None na mensagem"


def test_a_mensagem_NAO_atrapalha_quem_sabe_o_que_quer(monkeypatch):
    # Quem digita ano e mes continua sendo atendido: a mensagem informa, e nao
    # vira mais um passo para responder.
    import tesouro.pipeline as pipeline
    from tesouro import leitura_rmd

    monkeypatch.setattr(leitura_rmd, "mes_base_carregado",
                        lambda *a, **k: (2026, 7))
    respostas = iter(["2026", "8"])
    escolha = pipeline.escolher_rmd_no_menu(
        entrada=lambda _: next(respostas), saida=lambda *a: None)
    assert escolha == (2026, 8)


def test_o_mes_carregado_sai_do_NOME_do_arquivo_em_disco():
    # Sem fingir nada: confere que a funcao le o disco de verdade e devolve algo
    # plausivel. E a mesma funcao que escolhe QUAL anexo usar -- se as duas
    # discordassem, a mensagem falaria de um e a pagina mostraria outro.
    from tesouro import leitura_rmd

    base = leitura_rmd.mes_base_carregado()
    assert base is not None, "nao achei RMD em disco"
    ano, mes = base
    assert 2000 < ano < 2100 and 1 <= mes <= 12
    assert leitura_rmd.caminho_do_rmd().name.lower().startswith("anexo rmd")
