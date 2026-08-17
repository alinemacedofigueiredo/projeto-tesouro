import pytest
from tesouro import fetch_rmd

HTML = """
<html><body>
  <a href="https://thot-arquivos.tesouro.gov.br/publicacao/53999">
     Relatorio Mensal da Divida - Junho de 2026</a>
  <a href="https://thot-arquivos.tesouro.gov.br/publicacao-anexo/54001">
     Anexo RMD_Junho_26.zip</a>
  <a href="/publicacoes/outra-coisa">Outro link</a>
</body></html>
"""


def test_url_da_publicacao_monta_o_caminho_do_mes():
    url = fetch_rmd.url_da_publicacao(2026, 6)
    assert url.endswith("/relatorio-mensal-da-divida-rmd/2026/6")


def test_link_do_anexo_prefere_o_anexo_e_nao_o_relatorio():
    assert fetch_rmd.link_do_anexo(HTML).endswith("publicacao-anexo/54001")


def test_link_do_anexo_falha_com_mensagem_clara_quando_nao_ha_anexo():
    html = '<html><body><a href="/nada">nada</a></body></html>'
    with pytest.raises(LookupError, match="anexo"):
        fetch_rmd.link_do_anexo(html)


def test_url_da_publicacao_rejeita_mes_invalido():
    with pytest.raises(ValueError):
        fetch_rmd.url_da_publicacao(2026, 13)
