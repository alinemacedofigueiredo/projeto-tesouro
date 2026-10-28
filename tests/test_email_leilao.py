"""O construtor do e-mail de leilao (src/tesouro/email_leilao.py).

O QUE ESTES TESTES DEFENDEM sao as decisoes que ela tomou rascunho a rascunho
em 27/10/2026, e que nao se deduzem do codigo -- qualquer uma delas desfeita
por engano produz um e-mail que PARECE certo e diz outra coisa:

  so 1a volta, que foi o que fez os numeros baterem com o relatorio dela;
  o % do total e o FINANCEIRO, e nao a razao das quantidades;
  a LFT sai com DV01 VAZIO, e nao zero;
  sem dolar guardado a coluna fica vazia -- nunca convertida pela cotacao de
    hoje, que e justamente o que a trava do fetch_cambio existe para impedir.

E DEFENDEM UMA COISA QUE NAO E DE FORMATO: este modulo NAO MANDA E-MAIL.
Montar e deterministico; mandar e irreversivel e sai para fora. Ha teste que
reprova se o modulo ganhar qualquer caminho de envio.
"""
import datetime as dt

import pandas as pd
import pytest

from tesouro import email_leilao


_DIA_NTNB = dt.date(2026, 10, 20)
_DIA_PRE = dt.date(2026, 10, 22)


# ------------------------------------------------- a ancora do mundo real
#
# 7,855 bi NAO E UM NUMERO QUE ESTE PROJETO INVENTOU: e o que o relatorio que
# ela mandou diz que o Tesouro colocou de NTN-B em 20/10/2026. Foi batendo
# contra ele que a regra "so 1a volta" apareceu -- com a 2a volta somada da
# 8,285, e nada fecha.


def test_o_leilao_de_20_10_bate_com_o_RELATORIO_DELA():
    d = email_leilao.dados(_DIA_NTNB, "ntnb")
    ntnb = [x for x in d["linhas"] if x["titulo"] == "NTN-B"]
    aceito_bi = sum(x["financeiro_aceito"] for x in ntnb) / 1000
    assert aceito_bi == pytest.approx(7.855, abs=0.001)

    lft = [x for x in d["linhas"] if x["titulo"] == "LFT"]
    assert sum(x["financeiro_aceito"] for x in lft) / 1000 == pytest.approx(
        6.478, abs=0.001)
    assert d["total"]["financeiro_aceito"] / 1000 == pytest.approx(
        14.333, abs=0.001)
    assert d["total"]["pct_aceito"] == pytest.approx(0.803, abs=0.001)


def test_a_2a_VOLTA_fica_de_fora_e_isso_MUDA_o_numero():
    """Sem esta diferenca, o teste de cima passaria com qualquer filtro.

    Se um dia a 2a volta entrar, o numero vai para 8,285 e o de cima fica
    vermelho -- este aqui garante que os dois valores sao mesmo diferentes, e
    que o primeiro nao esta passando por acaso.
    """
    from tesouro import config

    cru = pd.read_csv(config.PROCESSED_DIR / "dv_emitido_por_leilao.csv",
                      parse_dates=["data_leilao"])
    do_dia = cru[(cru["data_leilao"] == pd.Timestamp(_DIA_NTNB)) &
                 (cru["titulo"] == "NTN-B") &
                 (cru["operacao"] == "venda")]
    com_as_duas = do_dia["financeiro_milhoes"].sum() / 1000
    assert com_as_duas == pytest.approx(8.285, abs=0.001)
    assert com_as_duas != pytest.approx(7.855, abs=0.001)


# --------------------------------------------------------- o total e o %


def _base_de_mentira(linhas):
    """Uma base ja filtrada, no formato que ultimos_leiloes aceita."""
    d = pd.DataFrame(linhas)
    d["data_leilao"] = pd.to_datetime(d["data_leilao"])
    d["data_vencimento"] = pd.to_datetime(d["data_vencimento"])
    return d


_DOIS_PAPEIS = [
    # Precos MUITO diferentes de proposito: um titulo a 5.000 e outro a 20.000,
    # como NTN-B e LFT de verdade. E o que faz a razao das quantidades divergir
    # da razao do financeiro.
    {"data_leilao": "2026-10-20", "titulo": "NTN-B", "familia": "NTN-B",
     "data_vencimento": "2033-05-15", "dv_milhoes": 1.0,
     "dv_ofertado_milhoes": 1.0, "quantidade": 1000.0, "oferta_qtd": 1000.0,
     "financeiro_milhoes": 5.0, "taxa_media_pct": 6.0, "estagio": "aceito",
     "taxa_suposta": False},
    {"data_leilao": "2026-10-20", "titulo": "LFT", "familia": "LFT",
     "data_vencimento": "2032-12-01", "dv_milhoes": float("nan"),
     "dv_ofertado_milhoes": float("nan"), "quantidade": 500.0,
     "oferta_qtd": 1000.0, "financeiro_milhoes": 10.0, "taxa_media_pct": 0.11,
     "estagio": "aceito", "taxa_suposta": False},
]


def test_o_PERCENTUAL_DO_TOTAL_e_o_financeiro_e_nao_a_razao_das_quantidades():
    """A armadilha que ela e eu discutimos em 27/10/2026.

    Nos dados daqui a razao das QUANTIDADES da 75% e a do FINANCEIRO da 60%.
    Os dois numeros sao plausiveis e so um responde "quanto do leilao saiu".

    A CONTA, para quem vier conferir: a NTN-B ofertou 1.000 titulos a 0,005
    (5,0 / 1.000) e colocou tudo; a LFT ofertou 1.000 a 0,02 (10,0 / 500) e
    colocou metade. Financeiro ofertado 5,0 + 20,0 = 25,0; aceito 5,0 + 10,0 =
    15,0. Quantidade 1.500 de 2.000.
    """
    d = email_leilao.dados("2026-10-20", "ntnb",
                           base=_base_de_mentira(_DOIS_PAPEIS))
    t = d["total"]
    assert t["qtd_ofertada"] == 2000.0 and t["qtd_aceita"] == 1500.0
    razao_das_quantidades = t["qtd_aceita"] / t["qtd_ofertada"]
    assert razao_das_quantidades == pytest.approx(0.75)
    assert t["financeiro_ofertado"] == pytest.approx(25.0)
    assert t["pct_aceito"] == pytest.approx(0.60), (
        "o percentual do total deixou de ser o financeiro")
    assert t["pct_aceito"] != pytest.approx(razao_das_quantidades)


def test_a_LFT_sai_com_DV01_VAZIO_e_nao_zero():
    """Zero seria uma afirmacao sobre o risco dela; vazio diz que nao ha."""
    d = email_leilao.dados("2026-10-20", "ntnb",
                           base=_base_de_mentira(_DOIS_PAPEIS))
    lft = [x for x in d["linhas"] if x["titulo"] == "LFT"][0]
    assert lft["dv_aceito"] is None
    assert lft["dv_ofertado"] is None
    assert email_leilao._mm(lft["dv_aceito"]) == "&mdash;"
    # E o total das NTN-B nao herda um zero da LFT.
    assert d["total"]["dv_aceito"] == pytest.approx(1.0)


# ------------------------------------------------------------- o dolar


def test_SEM_DOLAR_guardado_a_coluna_fica_vazia_e_o_rodape_DIZ(monkeypatch):
    """Nunca converter pela cotacao de hoje -- e a trava do fetch_cambio.

    A coluna vazia sozinha seria ambigua; por isso o rodape precisa dizer.
    """
    monkeypatch.setattr(email_leilao.fetch_cambio, "do_disco",
                        lambda *a, **k: None)
    d = email_leilao.dados("2026-10-20", "ntnb",
                           base=_base_de_mentira(_DOIS_PAPEIS))
    assert all(x["dv_aceito_usd"] is None for x in d["linhas"])
    rodape = email_leilao._rodape_do_dolar(d)
    assert "guardado" in rodape


def test_COM_DOLAR_guardado_ele_converte_pela_taxa_DAQUELE_DIA(monkeypatch):
    monkeypatch.setattr(
        email_leilao.fetch_cambio, "do_disco",
        lambda *a, **k: {"taxa": 5.0, "fonte": "PTAX",
                         "data_da_cotacao": "2026-10-19"})
    d = email_leilao.dados("2026-10-20", "ntnb",
                           base=_base_de_mentira(_DOIS_PAPEIS))
    ntnb = [x for x in d["linhas"] if x["titulo"] == "NTN-B"][0]
    assert ntnb["dv_aceito_usd"] == pytest.approx(1.0 / 5.0)
    rodape = email_leilao._rodape_do_dolar(d)
    assert "PTAX" in rodape and "19/10" in rodape, rodape


# ------------------------------------------------- qual modelo, e os dois


def test_tipo_do_dia_separa_os_DOIS_MODELOS():
    assert email_leilao.tipo_do_dia(_DIA_NTNB) == "ntnb"
    assert email_leilao.tipo_do_dia(_DIA_PRE) == "pre"
    assert email_leilao.tipo_do_dia(dt.date(2026, 10, 25)) is None


def test_os_anteriores_sao_do_MESMO_TIPO_e_nao_quaisquer_dois():
    """O e-mail de NTN-B nao pode mostrar o leilao de prefixado da quinta."""
    d = email_leilao.dados(_DIA_NTNB, "ntnb")
    assert [a["data"] for a in d["anteriores"]] == [dt.date(2026, 10, 13),
                                                    dt.date(2026, 10, 6)]
    for anterior in d["anteriores"]:
        papeis = {x["titulo"] for x in anterior["linhas"]}
        assert papeis <= {"NTN-B", "LFT"}, papeis

    p = email_leilao.dados(_DIA_PRE, "pre")
    for anterior in p["anteriores"]:
        papeis = {x["titulo"] for x in anterior["linhas"]}
        assert papeis <= {"LTN", "NTN-F"}, papeis


def test_pedir_um_dia_SEM_LEILAO_levanta_em_vez_de_montar_vazio():
    with pytest.raises(LookupError):
        email_leilao.dados(dt.date(2026, 10, 25), "ntnb")


def test_tipo_ou_estagio_que_nao_existe_levanta():
    with pytest.raises(LookupError):
        email_leilao.dados(_DIA_NTNB, "ntnc")
    with pytest.raises(LookupError):
        email_leilao.dados(_DIA_NTNB, "ntnb", estagio="talvez")


# --------------------------------------------------------------- o HTML


def test_o_HTML_sai_com_ESTILO_EMBUTIDO_porque_o_Outlook_ignora_folha():
    """Sem isto a mensagem chega como texto corrido na caixa de quem le."""
    d = email_leilao.dados("2026-10-20", "ntnb",
                           base=_base_de_mentira(_DOIS_PAPEIS))
    corpo = email_leilao.html(d, figuras=[])
    assert "<style" not in corpo.lower(), "folha de estilo nao sobrevive"
    assert corpo.count("style=") > 20
    for moderno in ("display:flex", "display:grid", "grid-template"):
        assert moderno not in corpo, "o motor do Word nao conhece %s" % moderno


def test_o_assunto_diz_O_QUE_e_DE_QUANDO():
    d = email_leilao.dados(_DIA_NTNB, "ntnb")
    assunto = email_leilao.assunto(d)
    assert "NTN-B/LFT" in assunto
    assert "20/10/2026" in assunto
    assert "Resultado" in assunto


def test_os_rotulos_de_percentual_saem_com_UM_sinal_so():
    """Eles sao ARGUMENTO da formatacao, e nao o formato: com '%%' o sinal
    dobrado chegava inteiro na tela. Achado na primeira geracao de verdade."""
    d = email_leilao.dados("2026-10-20", "ntnb",
                           base=_base_de_mentira(_DOIS_PAPEIS))
    corpo = email_leilao.html(d, figuras=[])
    assert "%%" not in corpo


# ------------------------------------------------- a trava contra enviar


def test_o_MODULO_QUE_MONTA_NAO_TEM_CAMINHO_DE_ENVIO():
    """Montar tem teste; mandar e irreversivel e sai para fora.

    Enquanto os dois estiverem separados, nenhum teste de formato corre o
    risco de disparar e-mail para uma lista. Se alguem juntar, isto reprova.
    """
    import ast
    import inspect

    fonte = inspect.getsource(email_leilao)
    arvore = ast.parse(fonte)

    importados = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            importados.update(a.name.split(".")[0] for a in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            importados.add(no.module.split(".")[0])
    for proibido in ("smtplib", "win32com", "email", "ssl", "socket"):
        assert proibido not in importados, (
            "o modulo que MONTA importou %r -- envio mora em outro lugar"
            % proibido)

    chamadas = {no.func.attr for no in ast.walk(arvore)
                if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)}
    for proibido in ("send", "sendmail", "Send", "send_message"):
        assert proibido not in chamadas, "achei chamada de envio: %s" % proibido


# ------------------------------------------------------------- a OFERTA


_OFERTA = [dict(x, estagio="ofertado", taxa_suposta=True)
           for x in _DOIS_PAPEIS]


def test_na_OFERTA_as_colunas_de_aceito_NAO_EXISTEM():
    """Nao e que fiquem zeradas: nao existem.

    Zero ao lado de uma oferta cheia se le como "nao colocou nada" quando o
    certo e "ainda nao aconteceu" -- e a mesma razao pela qual agenda.
    _leiloes_realizados exclui o estagio ofertado por padrao.
    """
    d = email_leilao.dados("2026-10-20", "ntnb", estagio="oferta",
                           base=_base_de_mentira(_OFERTA))
    corpo = email_leilao.html(d, figuras=[])
    assert "Qtd ofertada" in corpo
    assert "Qtd aceita" not in corpo
    assert "DV01 aceito" not in corpo
    assert "% aceito" not in corpo
    assert "Taxa aceita" not in corpo
    assert "Oferta" in email_leilao.assunto(d)
    # E o que DEVE estar la, senao "nao achei as colunas de aceito" passaria
    # num e-mail vazio.
    assert "DV01 ofertado" in corpo
    assert "Taxa de refer\u00eancia" in corpo


def test_na_OFERTA_o_e_mail_AVISA_que_a_taxa_e_suposta():
    """Um DV01 calculado por taxa emprestada que nao se anuncia e o
    'plausivel e errado' deste projeto. O aviso traz o erro MEDIDO."""
    d = email_leilao.dados("2026-10-20", "ntnb", estagio="oferta",
                           base=_base_de_mentira(_OFERTA))
    assert d["taxa_suposta"] is True
    nota = email_leilao._nota_da_taxa_suposta(d)
    assert "estimativa" in nota
    assert "11,0 bp" in nota, "o aviso perdeu o erro medido"
    assert nota in email_leilao.html(d, figuras=[])


def test_no_RESULTADO_o_aviso_da_taxa_suposta_NAO_aparece():
    """Ele existe para a oferta; no resultado a taxa e a do proprio leilao, e
    repetir o aviso faria duvidar de um numero observado."""
    d = email_leilao.dados("2026-10-20", "ntnb",
                           base=_base_de_mentira(_DOIS_PAPEIS))
    assert d["taxa_suposta"] is False
    assert email_leilao._nota_da_taxa_suposta(d) == ""


def test_o_CORPO_comeca_dizendo_de_que_leilao_se_trata():
    """Pedido dela em 28/10/2026, ao ver o primeiro e-mail de verdade.

    Parece redundante com a linha de assunto, e nao e: o corpo VIAJA SOZINHO.
    Encaminhado, colado num chat, ou aberto do arquivo em data/processed, o
    assunto nao vem junto -- e ai um e-mail de 20/10 e um de 22/10 sao
    indistinguiveis, que e o pior tipo de parecido.
    """
    d = email_leilao.dados(_DIA_NTNB, "ntnb")
    corpo = email_leilao.html(d, figuras=[])
    assunto = email_leilao.assunto(d)

    assert assunto in corpo, "o corpo nao diz de que leilao e"
    # E NO COMECO, nao perdido no meio: antes do primeiro numero da pagina.
    assert corpo.index(assunto) < corpo.index("Financeiro aceito"), (
        "o titulo nao esta no comeco do corpo")

    # E muda com o leilao -- senao "esta la" passaria com texto fixo.
    outro = email_leilao.dados(_DIA_PRE, "pre")
    assert email_leilao.assunto(outro) in email_leilao.html(outro, figuras=[])
    assert assunto not in email_leilao.html(outro, figuras=[])
