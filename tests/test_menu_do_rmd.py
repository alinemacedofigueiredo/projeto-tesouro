"""O menu do RMD: continuar com o que esta salvo, ou ir buscar um mais novo.

DESENHO DELA em 02/10/2026, com estas palavras: "se eu escolho 1 rmd, ai vc me
diz, o ultimo rmd que vc salvou e da data tal. quer atualizar ou continuar? se
continuar, pega esse. se clicar em atualizar, diz para pegar no site e salvar na
pasta e tem q avisar q salvou. e ai roda de novo".

A VERSAO ANTERIOR perguntava ano e mes e tentava baixar -- o que nao funciona
nesta maquina, por causa do certificado do SERPRO. Esta pergunta o que ela de
fato decide.
"""


def _menu(monkeypatch, respostas, base=(2026, 7)):
    """Roda o menu com as respostas dadas. Devolve (escolha, texto na tela)."""
    import tesouro.pipeline as pipeline
    from tesouro import leitura_rmd

    bases = base if isinstance(base, list) else [base]
    vez = {"n": 0}

    def ler_disco(*a, **k):
        # Cada leitura pode devolver uma base diferente -- e assim que o teste
        # finge "ela salvou o anexo novo entre uma pergunta e a outra".
        i = min(vez["n"], len(bases) - 1)
        vez["n"] += 1
        return bases[i]

    monkeypatch.setattr(leitura_rmd, "mes_base_carregado", ler_disco)
    linhas = []
    fila = iter(respostas)
    escolha = pipeline.escolher_rmd_no_menu(
        entrada=lambda _: next(fila), saida=linhas.append)
    return escolha, "\n".join(linhas)


def test_diz_qual_rmd_esta_salvo_e_oferece_as_duas_saidas(monkeypatch):
    escolha, texto = _menu(monkeypatch, ["c"])
    assert "julho" in texto.lower() and "2026" in texto
    # As duas saidas, nomeadas como ela as nomeou.
    assert "continuar" in texto.lower()
    assert "atualizar" in texto.lower()
    # "continuar" segue com o anexo que esta em disco.
    assert escolha is None


def test_atualizar_diz_o_SITE_e_a_PASTA_e_espera_o_aviso(monkeypatch):
    from tesouro import config, fetch_rmd

    # 'a' para atualizar, depois 's' de "salvei", e entao 'c' para seguir.
    escolha, texto = _menu(monkeypatch, ["a", "s", "c"])
    assert fetch_rmd.BASE in texto, "faltou o site"
    assert str(config.RMD_DIR) in texto, "faltou a pasta"
    assert escolha is None


def test_depois_de_salvar_ele_RELE_o_disco_e_mostra_o_mes_novo(monkeypatch):
    # O PONTO DA CONFIRMACAO: ao dizer que salvou, ela precisa VER que o arquivo
    # foi encontrado. Se mostrasse julho de novo, ela saberia na hora que salvou
    # no lugar errado -- em vez de descobrir isso na pagina, dali a uma hora.
    escolha, texto = _menu(monkeypatch, ["a", "s", "c"],
                           base=[(2026, 7), (2026, 8)])
    assert "julho" in texto.lower()
    assert "agosto" in texto.lower(), (
        "depois de salvar, o menu tem de mostrar o mes novo")
    assert escolha is None


def test_quem_NAO_salvou_segue_com_o_que_tem(monkeypatch):
    # 'a', depois 'n' de "nao salvei": nao fica preso no laco nem aborta a
    # rodada -- segue com o anexo que ja esta la.
    escolha, _ = _menu(monkeypatch, ["a", "n"])
    assert escolha is None


def test_resposta_que_nao_existe_INSISTE_em_vez_de_escolher_sozinho(monkeypatch):
    escolha, texto = _menu(monkeypatch, ["x", "sei la", "c"])
    assert escolha is None
    assert texto.lower().count("nao entendi") == 2


def test_sem_anexo_em_disco_o_menu_AINDA_serve(monkeypatch):
    from tesouro import config, fetch_rmd

    escolha, texto = _menu(monkeypatch, ["a", "n"], base=None)
    assert "None" not in texto, "vazou o None na mensagem"
    assert fetch_rmd.BASE in texto
    assert str(config.RMD_DIR) in texto
    assert escolha is None


def test_o_mes_salvo_sai_do_NOME_do_arquivo_em_disco():
    # Sem fingir nada: a funcao le o disco de verdade, e e a MESMA que escolhe
    # qual anexo usar. Se as duas discordassem, a mensagem falaria de um mes e a
    # pagina mostraria outro.
    from tesouro import leitura_rmd

    base = leitura_rmd.mes_base_carregado()
    assert base is not None, "nao achei RMD em disco"
    ano, mes = base
    assert 2000 < ano < 2100 and 1 <= mes <= 12
    assert leitura_rmd.caminho_do_rmd().name.lower().startswith("anexo rmd")


def test_ENTER_EM_BRANCO_e_continuar(monkeypatch):
    # DEFEITO MEU, achado em 06/10/2026 por um teste que TRAVOU: o menu antigo
    # aceitava Enter em branco como "segue com o que esta em disco", e o meu so
    # aceitava C ou A. Enter caia no "nao entendi" e o laco repetia para
    # sempre.
    #
    # Enter e a tecla de quem nao quer decidir nada, e aqui nao decidir nada
    # tem um significado obvio e seguro: usar o que ja esta na pasta.
    escolha, _ = _menu(monkeypatch, [""])
    assert escolha is None


def test_o_menu_NAO_PERGUNTA_PARA_SEMPRE(monkeypatch):
    # A outra metade do mesmo defeito: com resposta que nunca casa, o laco era
    # infinito. Num terminal isso irrita; em qualquer coisa automatizada,
    # pendura. O laco passou a ter fim, e o fim e a saida segura -- seguir com
    # o anexo que esta la.
    escolha, texto = _menu(monkeypatch, ["x"] * 40)
    assert escolha is None
    assert texto.lower().count("nao entendi") <= 5, (
        "insistiu demais antes de desistir")
