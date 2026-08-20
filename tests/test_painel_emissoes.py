"""As quatro paginas de emissao, uma por combinacao de compra e segunda volta."""
import re

import matplotlib
matplotlib.use("Agg")
import pytest

from tesouro.graficos import emissao, painel_emissoes


def test_sao_quatro_combinacoes_e_cada_uma_tem_arquivo_proprio():
    assert len(painel_emissoes.COMBINACOES) == 4
    combos = {(c, v) for c, v, _, _ in painel_emissoes.COMBINACOES}
    assert combos == {(False, True), (False, False), (True, True), (True, False)}
    arquivos = [a for _, _, a, _ in painel_emissoes.COMBINACOES]
    assert len(set(arquivos)) == 4
    # A combinacao padrao e a que fica com o nome curto: e a que se abre primeiro.
    assert painel_emissoes.COMBINACOES[0][2] == "emissoes.html"


def test_as_quatro_combinacoes_dao_numeros_diferentes():
    # Se duas dessem o mesmo numero, uma delas seria pagina a toa. Medido no ultimo
    # ano: a segunda volta responde por ~90 bi de financeiro e a compra por ~49.
    totais = {}
    for com_compra in (False, True):
        for com_2a in (True, False):
            d = emissao.por_semana(janela=1, com_compra=com_compra,
                                   com_segunda_volta=com_2a)
            totais[(com_compra, com_2a)] = round(
                d["financeiro_milhoes"].sum() / 1000, 1)

    assert len(set(totais.values())) == 4, totais
    # Tirar a segunda volta reduz; incluir compra tambem reduz, porque ela entra
    # com sinal negativo.
    assert totais[(False, False)] < totais[(False, True)]
    assert totais[(True, True)] < totais[(False, True)]


def test_o_registro_muda_com_a_combinacao():
    # A nota de rodape de cada grafico diz qual recorte a pagina mostra. Se ela nao
    # mudasse, as quatro paginas seriam indistinguiveis para quem le.
    so_venda = painel_emissoes.registro(com_compra=False, com_2a=True)
    com_compra = painel_emissoes.registro(com_compra=True, com_2a=True)
    assert len(so_venda) == len(com_compra) == 13
    assert "S\u00f3 venda" in so_venda[0].nota
    assert "compra" in com_compra[0].nota
    assert so_venda[0].nota != com_compra[0].nota


@pytest.fixture(scope="module")
def pagina(tmp_path_factory):
    destino = tmp_path_factory.mktemp("emissoes") / "emissoes.html"
    caminho = painel_emissoes.grava(destino, com_compra=False, com_2a=True)
    return caminho.read_text(encoding="utf-8")


def test_a_pagina_traz_os_treze_graficos_e_os_tres_grupos(pagina):
    for g in painel_emissoes.registro():
        assert f'id="{g.id}"' in pagina, g.id
    for grupo in painel_emissoes.GRUPOS:
        assert grupo in pagina
    assert pagina.count("<section") == 13


def test_a_barra_liga_as_quatro_paginas(pagina):
    # Sem a barra, quem abre uma nao sabe que as outras existem. Os links sao
    # relativos, entao continuam funcionando com duplo clique e sem servidor.
    assert 'id="combinacoes"' in pagina
    assert pagina.count('class="atual"') == 1
    for _, _, arquivo, _ in painel_emissoes.COMBINACOES[1:]:
        assert f'href="{arquivo}"' in pagina


def test_a_pagina_nao_tem_referencia_externa(pagina):
    # Mesma propriedade do dashboard, e conferida do mesmo jeito: o que importa e
    # src= e href= apontando para fora, e nao a palavra "http" solta.
    #
    # Procurar "http://" cru acusa duas coisas que nao buscam nada: o xmlns do SVG
    # e os dois URIs de metadado RDF que o matplotlib escreve (purl.org e
    # matplotlib.org). Sao texto dentro do arquivo, nao requisicao.
    assert not re.search(r'(?:src|href)\s*=\s*"(?!#)[^"]*//', pagina)
    assert "<link" not in pagina
    assert not re.search(r"<script[^>]+src=", pagina)
    # E os links entre as quatro paginas sao RELATIVOS, que e o que os faz
    # funcionar com duplo clique.
    for _, _, arquivo, _ in painel_emissoes.COMBINACOES[1:]:
        assert f'href="{arquivo}"' in pagina


# --------------------------------------------------------------------------
# A marca do provisorio: leilao que veio da API e a planilha ainda nao confirmou.
#
# O risco aqui nao e o grafico ficar feio. E alguem olhar um numero hoje, outro
# amanha, e nao ter como saber por que mudou.
# --------------------------------------------------------------------------

def _dia_com_provisorio():
    import pandas as pd
    idx = pd.to_datetime(["2026-08-04", "2026-08-11", "2026-08-20"])
    d = pd.DataFrame({"financeiro_milhoes": [676.0, 1571.0, 2650.0],
                      "dv_milhoes": [-0.48, -0.76, -1.25],
                      "leiloes": [6, 3, 1],
                      "provisorio": [False, False, True]}, index=idx)
    d.index.name = "data_leilao"
    return d


def test_a_barra_provisoria_sai_hachurada_e_as_outras_nao():
    d = _dia_com_provisorio()
    hachuras = emissao._hachura(d)
    assert hachuras == ["", "", emissao.HACHURA_PROVISORIO]


def test_sem_provisorio_nao_ha_hachura_nenhuma():
    # Importa para a reprodutibilidade: enquanto tudo vem da planilha, o SVG tem de
    # sair identico ao que saia antes de a API existir.
    d = _dia_com_provisorio()
    d["provisorio"] = False
    assert emissao._hachura(d) is None


def test_csv_antigo_sem_a_coluna_origem_continua_desenhando():
    # O dv_emitido_por_leilao.csv gravado antes da API nao tem a coluna. Quebrar
    # nesse caso trocaria "grafico um dia atrasado" por "grafico nenhum".
    d = _dia_com_provisorio().drop(columns=["provisorio"])
    assert emissao._hachura(d) is None


def test_a_hachura_ganha_entrada_de_legenda():
    # Listra sem legenda e enfeite: quem olha nao tem como saber o que ela quer
    # dizer. Este teste existe porque a primeira versao tinha a listra e nao tinha
    # a legenda.
    extras = emissao._legenda_do_provisorio([emissao.HACHURA_PROVISORIO])
    assert len(extras) == 1
    assert "API" in extras[0].get_label()
    assert emissao._legenda_do_provisorio(None) == []


def test_o_dia_inteiro_fica_marcado_se_qualquer_linha_dele_veio_da_api(tmp_path,
                                                                      monkeypatch):
    # Um dia de leilao soma varios papeis. Se um deles e provisorio, a barra somada
    # daquele dia ja depende de um numero que pode mudar -- marcar so "parte" da
    # barra nao existe.
    import pandas as pd
    from tesouro import config

    base = pd.read_csv(config.PROCESSED_DIR / "dv_emitido_por_leilao.csv",
                       parse_dates=["data_leilao", "data_liquidacao"])
    recorte = base[base["familia"] == "NTN-B longa"].tail(2).copy()
    recorte["data_leilao"] = pd.Timestamp("2026-08-20")
    recorte["origem"] = ["planilha", "api"]

    falso = tmp_path / "dv_emitido_por_leilao.csv"
    recorte.to_csv(falso, index=False, encoding="utf-8")
    monkeypatch.setattr(emissao.config, "PROCESSED_DIR", tmp_path)

    d = emissao.por_dia("NTN-B longa")
    assert len(d) == 1
    assert bool(d.iloc[0]["provisorio"]) is True


def test_o_aviso_do_provisorio_diz_quais_dias(tmp_path, monkeypatch):
    # A hachura diz "esta barra e provisoria"; o aviso diz QUAL DIA. E a data que
    # permite conferir contra a planilha quando ela sair.
    import pandas as pd
    from tesouro import config

    pd.DataFrame({"origem": ["planilha", "api", "api"],
                  "data_leilao": ["2026-08-11", "2026-08-20", "2026-08-20"]}
                 ).to_csv(tmp_path / "dv_emitido_por_leilao.csv", index=False)
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)

    aviso = painel_emissoes._aviso_do_provisorio()
    assert "2026-08-20" in aviso
    assert "2026-08-11" not in aviso     # esse a planilha ja confirmou
    assert "1 dia(s)" in aviso


def test_sem_provisorio_a_pagina_nao_ganha_aviso_nenhum(tmp_path, monkeypatch):
    # Pagina de historico nao precisa de aviso sobre uma coisa que nao esta la --
    # e um aviso permanente vira ruido que ninguem le quando importar.
    import pandas as pd
    from tesouro import config

    pd.DataFrame({"origem": ["planilha"], "data_leilao": ["2026-08-11"]}
                 ).to_csv(tmp_path / "dv_emitido_por_leilao.csv", index=False)
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)
    assert painel_emissoes._aviso_do_provisorio() == ""


def test_csv_sem_a_coluna_origem_nao_quebra_a_pagina(tmp_path, monkeypatch):
    import pandas as pd
    from tesouro import config

    pd.DataFrame({"data_leilao": ["2026-08-11"]}
                 ).to_csv(tmp_path / "dv_emitido_por_leilao.csv", index=False)
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)
    assert painel_emissoes._aviso_do_provisorio() == ""
