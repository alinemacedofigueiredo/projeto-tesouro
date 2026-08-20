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
# As tres aparencias, para os tres momentos: ofertado (fantasma com contorno),
# aceito (hachurado) e planilha (solido).
#
# O risco aqui nao e o grafico ficar feio. E alguem olhar um numero hoje, outro
# amanha, e nao ter como saber por que mudou.
# --------------------------------------------------------------------------

def _dia_com_os_tres_estagios():
    import pandas as pd
    idx = pd.to_datetime(["2026-08-04", "2026-08-11", "2026-08-20", "2026-08-25"])
    d = pd.DataFrame({"financeiro_milhoes": [676.0, 1571.0, 2650.0, 3100.0],
                      "dv_milhoes": [-0.48, -0.76, -1.25, -1.48],
                      "leiloes": [6, 3, 1, 1],
                      "estagio": ["planilha", "planilha", "aceito", "ofertado"]},
                     index=idx)
    d.index.name = "data_leilao"
    return d


def test_cada_estagio_ganha_a_sua_aparencia():
    d = _dia_com_os_tres_estagios()
    estagios = emissao._estagios(d)
    assert estagios == ["planilha", "planilha", "aceito", "ofertado"]

    a = emissao._aparencia(estagios, "#3d9be9")
    # A oferta e fantasma: o preenchimento quase some, mas a cor do papel fica --
    # foi por isso que a barra OCA foi abandonada, ela apagava a composicao do
    # grafico empilhado.
    assert a["color"][3][3] == emissao.OPACIDADE_DO_OFERTADO
    assert a["color"][0][3] > emissao.OPACIDADE_DO_OFERTADO
    # So o aceito e hachurado.
    assert a["hatch"] == ["", "", emissao.HACHURA_ACEITO, ""]
    # E so a oferta tem contorno grosso, que e o que a faz ler como contorno.
    assert a["linewidth"][3] > a["linewidth"][2] > a["linewidth"][0]


def test_sem_provisorio_nao_ha_marca_nenhuma():
    # Importa para a reprodutibilidade: enquanto tudo vem da planilha, o SVG tem de
    # sair identico ao que saia antes de a API existir. Passar hatch=["",""] em vez
    # de hatch=None ja muda o arquivo.
    d = _dia_com_os_tres_estagios()
    d["estagio"] = "planilha"
    assert emissao._estagios(d) is None
    assert set(emissao._aparencia(None, "#3d9be9")) == {"color"}


def test_csv_antigo_sem_a_coluna_estagio_continua_desenhando():
    # O dv_emitido_por_leilao.csv gravado antes da API nao tem a coluna. Quebrar
    # nesse caso trocaria "grafico um dia atrasado" por "grafico nenhum".
    d = _dia_com_os_tres_estagios().drop(columns=["estagio"])
    assert emissao._estagios(d) is None


def test_a_legenda_explica_so_os_estagios_presentes():
    # Listra sem legenda e enfeite. E legenda de um estagio que nao esta na tela e
    # ruido: quem olha procura a barra e nao acha.
    ambos = emissao._legenda_dos_estagios(["planilha", "aceito", "ofertado"])
    assert [e.get_label() for e in ambos] == [
        emissao._ROTULO_DO_ESTAGIO["ofertado"], emissao._ROTULO_DO_ESTAGIO["aceito"]]

    so_aceito = emissao._legenda_dos_estagios(["planilha", "aceito"])
    assert len(so_aceito) == 1
    assert "API" in so_aceito[0].get_label()

    assert emissao._legenda_dos_estagios(None) == []


def test_o_rotulo_da_oferta_diz_que_e_teto():
    # A palavra importa: sem ela, a barra mais alta do grafico parece emissao
    # recorde quando e so o anuncio. O Tesouro aceita 83,9% do que oferta.
    assert "teto" in emissao._ROTULO_DO_ESTAGIO["ofertado"]


def test_a_barra_somada_recebe_o_estagio_menos_firme():
    # Um dia de leilao soma varios papeis. Se um deles ainda e teto, o total daquele
    # dia tambem e teto -- a soma nao pode ser mais firme que a sua parte mais fraca.
    assert emissao._menos_firme(["planilha", "aceito"]) == "aceito"
    assert emissao._menos_firme(["planilha", "aceito", "ofertado"]) == "ofertado"
    assert emissao._menos_firme(["planilha", "planilha"]) == "planilha"
    assert emissao._menos_firme([]) == emissao.ESTAGIO_MAIS_FIRME


def test_o_dia_inteiro_fica_no_estagio_menos_firme_do_csv(tmp_path, monkeypatch):
    # O mesmo, mas atravessando por_dia() e o CSV de verdade -- e nao so a funcao
    # auxiliar.
    import pandas as pd
    from tesouro import config

    base = pd.read_csv(config.PROCESSED_DIR / "dv_emitido_por_leilao.csv",
                       parse_dates=["data_leilao", "data_liquidacao"])
    recorte = base[base["familia"] == "NTN-B longa"].tail(2).copy()
    recorte["data_leilao"] = pd.Timestamp("2026-08-20")
    recorte["estagio"] = ["planilha", "ofertado"]

    falso = tmp_path / "dv_emitido_por_leilao.csv"
    recorte.to_csv(falso, index=False, encoding="utf-8")
    monkeypatch.setattr(emissao.config, "PROCESSED_DIR", tmp_path)

    d = emissao.por_dia("NTN-B longa")
    assert len(d) == 1
    assert d.iloc[0]["estagio"] == "ofertado"


def test_o_aviso_do_provisorio_diz_quais_dias_e_em_que_momento(tmp_path,
                                                               monkeypatch):
    # A marca no grafico diz "esta barra e provisoria"; o aviso diz QUAL DIA e EM
    # QUE MOMENTO. Sao os dois dados que permitem conferir contra a planilha depois.
    import pandas as pd
    from tesouro import config

    pd.DataFrame({"estagio": ["planilha", "aceito", "ofertado"],
                  "data_leilao": ["2026-08-11", "2026-08-20", "2026-08-25"]}
                 ).to_csv(tmp_path / "dv_emitido_por_leilao.csv", index=False)
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)

    aviso = painel_emissoes._aviso_do_provisorio()
    assert "2026-08-20" in aviso
    assert "2026-08-25" in aviso
    assert "2026-08-11" not in aviso     # esse a planilha ja confirmou
    # E cada data com o seu momento, e nao os dois no mesmo saco: um vai mudar de
    # quantidade, o outro so de taxa.
    assert aviso.index("2026-08-25") < aviso.index("2026-08-20")
    assert "teto" in aviso


def test_o_aviso_so_mostra_o_momento_que_existe(tmp_path, monkeypatch):
    # Aviso sobre um estagio que nao esta na tela e ruido: quem le procura a barra
    # e nao acha.
    import pandas as pd
    from tesouro import config

    pd.DataFrame({"estagio": ["planilha", "aceito"],
                  "data_leilao": ["2026-08-11", "2026-08-20"]}
                 ).to_csv(tmp_path / "dv_emitido_por_leilao.csv", index=False)
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)

    aviso = painel_emissoes._aviso_do_provisorio()
    assert "hachurado" in aviso
    assert "teto" not in aviso


def test_sem_provisorio_a_pagina_nao_ganha_aviso_nenhum(tmp_path, monkeypatch):
    # Pagina de historico nao precisa de aviso sobre uma coisa que nao esta la --
    # e um aviso permanente vira ruido que ninguem le quando importar.
    import pandas as pd
    from tesouro import config

    pd.DataFrame({"estagio": ["planilha"], "data_leilao": ["2026-08-11"]}
                 ).to_csv(tmp_path / "dv_emitido_por_leilao.csv", index=False)
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)
    assert painel_emissoes._aviso_do_provisorio() == ""


def test_csv_sem_a_coluna_estagio_nao_quebra_a_pagina(tmp_path, monkeypatch):
    import pandas as pd
    from tesouro import config

    pd.DataFrame({"data_leilao": ["2026-08-11"]}
                 ).to_csv(tmp_path / "dv_emitido_por_leilao.csv", index=False)
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)
    assert painel_emissoes._aviso_do_provisorio() == ""
