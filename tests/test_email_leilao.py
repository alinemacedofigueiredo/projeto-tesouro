"""O e-mail do leilao do dia: a tabela, e quais graficos vao em cada tipo."""
import pandas as pd
import pytest

from tesouro import email_leilao


PREFIXADO = pd.Timestamp("2026-09-24")     # LTN e NTN-F
INDEXADO = pd.Timestamp("2026-09-22")      # LFT e NTN-B


def test_o_assunto_diz_a_data_do_leilao():
    assert "24/09/2026" in email_leilao.assunto(PREFIXADO)


def test_a_tabela_do_prefixado_traz_papel_quantidade_dv_e_financeiro():
    t = email_leilao.tabela(PREFIXADO)
    assert list(t.columns) == ["papel", "quantidade", "dv", "financeiro"]
    assert sorted(t["papel"]) == ["LTN", "NTN-F"]
    assert (t["dv"] > 0).all(), "prefixado tem DV"
    assert (t["financeiro"] > 0).all()


def test_a_LFT_entra_no_financeiro_e_NAO_no_dv():
    # Decisao de modelagem do projeto: a LFT nao tem DV01. Ela pediu que a
    # tabela lembrasse disso em vez de mostrar um zero, que se somaria calado.
    t = email_leilao.tabela(INDEXADO)
    lft = t[t["papel"] == "LFT"]
    assert len(lft) == 1
    assert lft["dv"].isna().all(), "a LFT nao pode ter DV nem zero"
    assert (lft["financeiro"] > 0).all()


def test_o_total_do_dv_ignora_a_LFT_e_o_do_financeiro_nao():
    # O erro que esta linha evita: somar a LFT no DV como se fosse zero faz o
    # total parecer completo quando ele e parcial.
    t = email_leilao.tabela(INDEXADO)
    total = email_leilao.totais(t)

    com_dv = t[t["dv"].notna()]
    assert total["dv"] == pytest.approx(com_dv["dv"].sum())
    assert total["financeiro"] == pytest.approx(t["financeiro"].sum())
    assert total["financeiro"] > com_dv["financeiro"].sum(), (
        "o financeiro total tem de incluir a LFT")


def test_o_prefixado_leva_os_tres_graficos_de_dois_eixos():
    nomes = [n for n, _ in email_leilao.graficos(PREFIXADO)]
    assert nomes == ["LTN", "NTN-F", "LTN + NTN-F"]


def test_o_indexado_leva_as_duas_faixas_a_soma_e_a_LFT():
    nomes = [n for n, _ in email_leilao.graficos(INDEXADO)]
    assert nomes == ["NTN-B at\u00e9 10 anos", "NTN-B acima de 10 anos",
                     "NTN-B", "LFT"]


def test_os_graficos_saem_como_figura_desenhavel():
    # Um por tipo basta: o que se prova aqui e que da para salvar PNG, que e o
    # que vai colado no corpo.
    for quando in (PREFIXADO, INDEXADO):
        nome, fig = email_leilao.graficos(quando)[0]
        assert hasattr(fig, "savefig"), nome


def test_o_corpo_referencia_TODAS_as_imagens_que_anexa():
    # A falha classica do e-mail com imagem embutida: o HTML aponta para um cid
    # que nao foi anexado, e o leitor ve o quadrado quebrado. Aqui os dois lados
    # sao conferidos um contra o outro.
    html, imagens = email_leilao.corpo(PREFIXADO)
    for cid, _ in imagens:
        assert ('cid:' + cid) in html, f"{cid} anexado e nao referenciado"
    citados = set(email_leilao.CIDS_NO_HTML.findall(html))
    assert citados == {cid for cid, _ in imagens}, (
        "o HTML cita cid que nao foi anexado")


def test_o_corpo_mostra_a_tabela_com_os_numeros():
    html, _ = email_leilao.corpo(PREFIXADO)
    t = email_leilao.tabela(PREFIXADO)
    assert "LTN" in html and "NTN-F" in html
    # O financeiro de cada papel, formatado como a pagina formata.
    from tesouro.graficos import estilo
    for v in t["financeiro"]:
        assert estilo.num_br(v, 0) in html


def test_dia_sem_leilao_diz_isso_em_vez_de_inventar_tabela():
    vazio = pd.Timestamp("2026-09-23")     # quarta, nao ha leilao
    with pytest.raises(LookupError, match="leil"):
        email_leilao.tabela(vazio)


def test_o_corpo_AVISA_quando_os_numeros_sao_de_oferta():
    # 24/09/2026 e uma OFERTA: o resultado nao saiu. O financeiro e o DV sao
    # derivados da taxa emprestada do leilao anterior daquele papel -- erro
    # mediano de 11 bp -- e a quantidade e o TETO ofertado, que historicamente
    # cai para 83,9% dele.
    #
    # Mostrar esses numeros com a mesma cara dos definitivos e exatamente o modo
    # de falha que este projeto chama de plausivel e errado.
    html, _ = email_leilao.corpo(PREFIXADO)
    assert email_leilao.e_oferta(PREFIXADO)
    assert "teto" in html.lower()
    assert "resultado" in html.lower()


def test_o_corpo_NAO_avisa_quando_o_resultado_ja_saiu():
    # O aviso tem de sumir sozinho quando o dado vira definitivo, senao vira
    # ruido que ninguem le -- e no dia em que importar, ninguem ve.
    html, _ = email_leilao.corpo(INDEXADO)
    assert not email_leilao.e_oferta(INDEXADO)
    assert "teto" not in html.lower()


def test_o_corpo_NAO_deixa_figura_aberta():
    # A suite de 25/09/2026 avisou: "More than 20 figures have been opened".
    # As figuras saem do pyplot e ficam retidas ate alguem fechar -- em teste e
    # barulho, mas montar() roda a cada leilao e a memoria nao volta sozinha.
    #
    # Fecha ANTES de medir, senao o teste mede o lixo dos testes anteriores em
    # vez do que esta funcao deixou.
    import matplotlib.pyplot as plt

    plt.close("all")
    email_leilao.corpo(PREFIXADO)
    assert plt.get_fignums() == [], (
        f"sobraram {len(plt.get_fignums())} figuras abertas depois do corpo")
