"""A orientacao de certificado: a mesma em todo caminho, e com quem assinou."""
import pytest

from tesouro import certificado


def test_a_orientacao_manda_apontar_o_SSL_CERT_FILE():
    t = certificado.orientacao("www.tesourotransparente.gov.br")
    assert "SSL_CERT_FILE" in t
    # Os dois jeitos, porque a maquina do banco pode nao ser a dela.
    assert "PowerShell" in t and "bash" in t


def test_a_orientacao_NUNCA_manda_desligar_a_verificacao():
    # REGRA DELA, que vale em todo o projeto: a verificacao de certificado nao
    # se desliga. Uma mensagem de erro e o lugar mais tentador para sugerir
    # isso, porque e o momento em que quem le esta com pressa -- por isso a
    # regra tem teste, e nao so comentario.
    t = certificado.orientacao("qualquer.host", quem="AC de teste")
    baixo = t.lower()

    # OS INTERRUPTORES, que nao tem leitura ambigua: se qualquer um destes
    # aparece numa mensagem de erro, alguem vai copiar e colar.
    for tentacao in ("verify=false", "cert_none", "verify_mode", "insecure",
                     "check_hostname = false", "ssl._create_unverified"):
        assert tentacao not in baixo, f"a mensagem sugere {tentacao!r}"

    # E A INSTRUCAO EXPLICITA. A primeira versao deste teste procurava a frase
    # "desligue a verifica" solta e reprovava a mensagem CERTA, que diz "NAO
    # desligue a verificacao" -- o filtro pegava o pedaco dentro da negacao.
    assert "NAO desligue a verificacao" in t


def test_a_orientacao_DIZ_QUEM_ASSINOU_quando_da_para_saber():
    # A razao de existir: no banco, saber se quem assinou e o SERPRO ou o proxy
    # da casa muda o conserto. Sem essa linha, os dois casos dao a mesma
    # mensagem e quem le nao tem como distinguir.
    t = certificado.orientacao("host", quem="AC SERPRO AR46 OV TLS CA 2025")
    assert "AC SERPRO AR46 OV TLS CA 2025" in t


def test_sem_saber_quem_assinou_a_orientacao_AINDA_serve():
    # O aperto de mao pode falhar antes de entregar o certificado -- rede fora,
    # porta fechada. A mensagem continua util, e nao mente dizendo um emissor.
    t = certificado.orientacao("host", quem=None)
    assert "SSL_CERT_FILE" in t
    assert "None" not in t, "vazou o None na mensagem"


def test_quem_assinou_devolve_None_quando_nao_da_para_falar_com_o_host():
    # Host que nao existe: nao levanta, devolve None. Quem chama esta JA no
    # caminho de erro, e uma excecao aqui esconderia a falha de verdade.
    assert certificado.quem_assinou("host.que.nao.existe.invalido", timeout=3) is None


def test_o_RMD_explica_o_erro_de_certificado_em_vez_de_vazar_traceback(monkeypatch):
    # Ate 28/09/2026 o caminho do RMD estourava URLError cru. A orientacao sobre
    # SSL_CERT_FILE existia no api_leiloes e no fetch_leiloes_api, e faltava
    # justamente onde ela foi tentar baixar o anexo do mes.
    import urllib.error

    from tesouro import fetch_rmd

    def falha_de_certificado(*a, **k):
        raise urllib.error.URLError(
            "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")

    monkeypatch.setattr(fetch_rmd, "_baixar_bytes", falha_de_certificado)
    monkeypatch.setattr(certificado, "quem_assinou",
                        lambda *a, **k: "AC SERPRO AR46 OV TLS CA 2025")

    with pytest.raises(LookupError) as erro:
        fetch_rmd.baixar(2026, 9, destino=None)
    texto = str(erro.value)
    assert "SSL_CERT_FILE" in texto
    assert "AC SERPRO" in texto
    # E diz o que fazer AGORA, sem depender de arrumar o certificado.
    assert "navegador" in texto.lower()


def test_o_nome_do_emissor_nao_carrega_o_byte_do_campo_seguinte():
    # MEDIDO em 28/09/2026 contra o certificado real do tesourotransparente: a
    # leitura grosseira do DER devolvia "AC SERPRO AR46 OV TLS CA 20250" -- um
    # digito a mais, que e o byte de tamanho do campo seguinte entrando no nome.
    #
    # Um digito nao muda o uso (saber se e o SERPRO ou o proxy da casa), mas o
    # nome vai numa mensagem que ela pode colar para o TI do banco, e ali um
    # nome QUASE certo nao bate com o que o navegador mostra.
    assert certificado._limpar_nome("AC SERPRO AR46 OV TLS CA 20250") == (
        "AC SERPRO AR46 OV TLS CA 2025")
    # Ano de quatro digitos sozinho fica intacto.
    assert certificado._limpar_nome("AC SERPRO AR46 OV TLS CA 2025") == (
        "AC SERPRO AR46 OV TLS CA 2025")
    # E nome sem ano no fim nao e tocado.
    assert certificado._limpar_nome("GlobalSign Root CA") == "GlobalSign Root CA"
