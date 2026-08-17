from tesouro.gravacao import gravar_atomico


def test_gravar_atomico_escreve_o_arquivo_final_com_o_conteudo_certo(tmp_path):
    caminho = tmp_path / "arquivo.xls"

    gravar_atomico(b"conteudo de teste", caminho)

    assert caminho.read_bytes() == b"conteudo de teste"


def test_gravar_atomico_nao_deixa_part_para_tras_depois_do_sucesso(tmp_path):
    caminho = tmp_path / "arquivo.xls"

    gravar_atomico(b"dados", caminho)

    assert not caminho.with_name(caminho.name + ".part").exists()


def test_gravar_atomico_sobrescreve_part_de_tentativa_anterior_truncada(tmp_path):
    caminho = tmp_path / "arquivo.xls"
    tmp = caminho.with_name(caminho.name + ".part")
    tmp.write_bytes(b"lixo de uma tentativa anterior que ficou pela metade")

    gravar_atomico(b"dados novos e completos", caminho)

    assert caminho.read_bytes() == b"dados novos e completos"
    assert not tmp.exists()
