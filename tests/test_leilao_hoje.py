"""O laco do "leilao hoje" (src/tesouro/leilao_hoje.py).

NENHUM TESTE DAQUI PODE MANDAR E-MAIL, e nao basta nao chamar: ha teste que
reprova se o modulo ganhar qualquer caminho de envio proprio. Quem manda e
injetado, e nos testes e sempre uma lista que anota.

O QUE ESTES TESTES DEFENDEM:

  mandar duas vezes e IRREVERSIVEL. O laco vai ser reiniciado no meio da
    manha -- a maquina e do banco e cai -- e reiniciar nao pode remandar o
    que ja saiu para a mesa inteira;
  a marca so e gravada DEPOIS que o envio volta sem erro. Gravar antes
    trocaria "mandei duas vezes" por "nunca mandei e achei que tinha";
  o modo ensaio e o PADRAO: sem funcao de envio, grava e diz onde ficou;
  o laco nao diz ter mandado o que a guarda impediu.

O relogio e o sono sao injetados: o teste faz o dia passar sem esperar.
"""
import datetime as dt

import pytest

from tesouro import leilao_hoje


_DIA = dt.date(2026, 10, 20)


class _Carteiro:
    """Um envio de mentira que anota em vez de mandar."""

    def __init__(self, explode=False):
        self.mandados = []
        self.explode = explode

    def __call__(self, assunto, corpo, para):
        if self.explode:
            raise ConnectionError("o Outlook nao respondeu")
        self.mandados.append((assunto, para, len(corpo)))


def _as_dez_da_manha(monkeypatch):
    """O relogio parado as 10h.

    SEM ISTO O TESTE DEPENDE DA HORA EM QUE RODA: o laco para as 14h, entao a
    suite passaria de manha e falharia a tarde. Aconteceu comigo na primeira
    rodada deste arquivo, as 18h.
    """
    monkeypatch.setattr(leilao_hoje, "_agora",
                        lambda: dt.datetime(2026, 10, 20, 10, 0))


def _sem_montar(monkeypatch, tmp_path):
    """Troca a montagem do e-mail por uma que nao desenha quatro graficos."""
    def grava(dia, tipo, estagio, destino=None):
        alvo = tmp_path / ("email-%s-%s.html" % (tipo, estagio))
        alvo.write_text("<div>corpo de mentira</div>", encoding="utf-8")
        return alvo, {"tipo": tipo, "estagio": estagio, "rotulo": "NTN-B/LFT",
                      "data_leilao": dia}
    monkeypatch.setattr(leilao_hoje.email_leilao, "grava", grava)
    monkeypatch.setattr(leilao_hoje.email_leilao, "assunto",
                        lambda d: "Leilao %s %s" % (d["rotulo"], d["estagio"]))
    monkeypatch.setattr(leilao_hoje.email_leilao, "tipo_do_dia",
                        lambda *a, **k: "ntnb")


# --------------------------------------------------- a guarda do reenvio


def test_a_SEGUNDA_chamada_NAO_REMANDA(monkeypatch, tmp_path):
    _sem_montar(monkeypatch, tmp_path)
    carteiro = _Carteiro()

    leilao_hoje.despacha(_DIA, "ntnb", "resultado", carteiro,
                         ["mesa@banco"], destino=tmp_path, saida=lambda *a: None)
    assert len(carteiro.mandados) == 1

    with pytest.raises(leilao_hoje.JaFoi):
        leilao_hoje.despacha(_DIA, "ntnb", "resultado", carteiro,
                             ["mesa@banco"], destino=tmp_path,
                             saida=lambda *a: None)
    assert len(carteiro.mandados) == 1, "mandou de novo"


def test_a_marca_so_e_gravada_DEPOIS_que_o_envio_da_certo(monkeypatch,
                                                          tmp_path):
    """Se o Outlook recusar, o e-mail NAO pode ficar marcado como enviado --
    senao a proxima rodada acha que ja foi e ninguem recebe nada."""
    _sem_montar(monkeypatch, tmp_path)
    quebrado = _Carteiro(explode=True)

    with pytest.raises(ConnectionError):
        leilao_hoje.despacha(_DIA, "ntnb", "resultado", quebrado,
                             ["mesa@banco"], destino=tmp_path,
                             saida=lambda *a: None)
    assert not leilao_hoje.ja_enviado(_DIA, "ntnb", "resultado", tmp_path)

    # E a tentativa seguinte manda de verdade.
    bom = _Carteiro()
    leilao_hoje.despacha(_DIA, "ntnb", "resultado", bom, ["mesa@banco"],
                         destino=tmp_path, saida=lambda *a: None)
    assert len(bom.mandados) == 1


def test_a_OFERTA_e_o_RESULTADO_tem_marcas_SEPARADAS(monkeypatch, tmp_path):
    """Mandar a oferta nao pode bloquear o resultado do mesmo dia."""
    _sem_montar(monkeypatch, tmp_path)
    carteiro = _Carteiro()
    for estagio in ("oferta", "resultado"):
        leilao_hoje.despacha(_DIA, "ntnb", estagio, carteiro, ["mesa@banco"],
                             destino=tmp_path, saida=lambda *a: None)
    assert len(carteiro.mandados) == 2
    assert leilao_hoje.ja_enviado(_DIA, "ntnb", "oferta", tmp_path)
    assert leilao_hoje.ja_enviado(_DIA, "ntnb", "resultado", tmp_path)
    assert not leilao_hoje.ja_enviado(dt.date(2026, 10, 22), "ntnb", "oferta",
                                      tmp_path)


# ------------------------------------------------------------- o ensaio


def test_SEM_funcao_de_envio_o_padrao_e_ENSAIO(monkeypatch, tmp_path):
    """Grava e diz onde ficou. E nao deixa marca: ensaio nao gasta o dia."""
    _sem_montar(monkeypatch, tmp_path)
    falas = []
    caminho, marca = leilao_hoje.despacha(
        _DIA, "ntnb", "resultado", None, ["mesa@banco"], destino=tmp_path,
        saida=falas.append)
    assert marca is None
    assert caminho.exists()
    assert any("ENSAIO" in f for f in falas)
    assert not leilao_hoje.ja_enviado(_DIA, "ntnb", "resultado", tmp_path), (
        "o ensaio marcou como enviado e vai bloquear o envio de verdade")


# --------------------------------------------------------------- o laco


def test_o_laco_espera_a_OFERTA_e_depois_o_RESULTADO(monkeypatch, tmp_path):
    """A manha inteira em tres voltas, sem relogio e sem rede."""
    _sem_montar(monkeypatch, tmp_path)
    _as_dez_da_manha(monkeypatch)
    carteiro = _Carteiro()

    # QUANTOS E-MAILS JA TINHAM SAIDO NO INICIO DE CADA VOLTA. E isto que
    # separa "esperou a hora" de "mandou tudo de uma vez" -- sem esta conta, o
    # teste passava igual com a espera removida da producao, e a mutacao
    # sobreviveu na primeira prova de dentes.
    saidos_por_volta = []

    def buscar(dia):
        saidos_por_volta.append(len(carteiro.mandados))
        if len(saidos_por_volta) == 1:
            return set()                       # 9h40: nada ainda
        if len(saidos_por_volta) == 2:
            return {"oferta"}                  # 10h: saiu o edital
        return {"oferta", "resultado"}          # 10h45: saiu o resultado

    feitos = leilao_hoje.espera_e_despacha(
        _DIA, enviar=carteiro, para=["mesa@banco"], destino=tmp_path,
        saida=lambda *a: None, dormir=lambda _s: None, buscar=buscar)

    assert feitos == ["oferta", "resultado"]
    assert [m[0] for m in carteiro.mandados] == [
        "Leilao NTN-B/LFT oferta", "Leilao NTN-B/LFT resultado"]
    assert saidos_por_volta == [0, 0, 1], (
        "o laco nao esperou cada estagio aparecer: %s" % saidos_por_volta)


def test_REINICIAR_no_meio_da_manha_nao_remanda_a_oferta(monkeypatch,
                                                         tmp_path):
    """O caso que vai acontecer: a maquina do banco cai as 10h20."""
    _sem_montar(monkeypatch, tmp_path)
    _as_dez_da_manha(monkeypatch)
    antes = _Carteiro()
    leilao_hoje.despacha(_DIA, "ntnb", "oferta", antes, ["mesa@banco"],
                         destino=tmp_path, saida=lambda *a: None)

    depois = _Carteiro()
    feitos = leilao_hoje.espera_e_despacha(
        _DIA, enviar=depois, para=["mesa@banco"], destino=tmp_path,
        saida=lambda *a: None, dormir=lambda _s: None,
        buscar=lambda _d: {"oferta", "resultado"})

    assert [m[0] for m in depois.mandados] == ["Leilao NTN-B/LFT resultado"]
    assert feitos == ["resultado"], (
        "o laco disse ter mandado a oferta que a guarda impediu")


def test_DIA_SEM_LEILAO_termina_no_limite_sem_mandar_nada(monkeypatch,
                                                          tmp_path):
    _sem_montar(monkeypatch, tmp_path)
    monkeypatch.setattr(leilao_hoje.email_leilao, "tipo_do_dia",
                        lambda *a, **k: None)
    carteiro = _Carteiro()
    voltas = []

    def relogio():
        voltas.append(1)
        hora = 9 if len(voltas) < 4 else 15
        return dt.datetime(2026, 10, 25, hora, 0)
    monkeypatch.setattr(leilao_hoje, "_agora", relogio)

    falas = []
    feitos = leilao_hoje.espera_e_despacha(
        dt.date(2026, 10, 25), enviar=carteiro, para=["mesa@banco"],
        destino=tmp_path, saida=falas.append, dormir=lambda _s: None,
        buscar=lambda _d: set())

    assert feitos == []
    assert carteiro.mandados == []
    assert any("parei" in f for f in falas), falas


# ------------------------------------------------- a trava contra enviar


def test_o_LACO_NAO_TEM_caminho_de_envio_proprio():
    """Quem manda e injetado. Enquanto for assim, nenhum teste de laco pode
    disparar e-mail para uma lista por engano."""
    import ast
    import inspect

    arvore = ast.parse(inspect.getsource(leilao_hoje))
    importados = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            importados.update(a.name.split(".")[0] for a in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            importados.add(no.module.split(".")[0])
    for proibido in ("smtplib", "win32com", "email"):
        assert proibido not in importados, (
            "o laco importou %r -- envio mora em outro lugar" % proibido)


def test_a_mensagem_SO_ABERTA_nao_derruba_a_espera_do_RESULTADO(monkeypatch,
                                                                tmp_path):
    """A guarda do Outlook pode barrar a oferta das 10h.

    Tres coisas tem de acontecer ao mesmo tempo, e so uma e obvia: o dia nao
    fica marcado como enviado, o laco NAO tenta de novo no minuto seguinte --
    seriam sessenta janelas abertas na tela dela -- e o e-mail do RESULTADO
    sai normalmente as 10:45.
    """
    _sem_montar(monkeypatch, tmp_path)
    _as_dez_da_manha(monkeypatch)

    mandados = []

    def carteiro(assunto, corpo, para):
        if "oferta" in assunto:
            raise leilao_hoje.FoiSoAberto("esperando voce clicar em Enviar")
        mandados.append(assunto)

    falas = []
    feitos = leilao_hoje.espera_e_despacha(
        _DIA, enviar=carteiro, para=["mesa@banco"], destino=tmp_path,
        saida=falas.append, dormir=lambda _s: None,
        buscar=lambda _d: {"oferta", "resultado"})

    assert feitos == ["resultado"], "contou como enviado o que ficou na tela"
    assert mandados == ["Leilao NTN-B/LFT resultado"]
    assert not leilao_hoje.ja_enviado(_DIA, "ntnb", "oferta", tmp_path), (
        "marcou como enviada uma mensagem que esta aberta esperando clique")
    assert any("NAO FOI ENVIADO" in f for f in falas), falas


# ------------------------------------------------------ quem recebe


def test_a_lista_IGNORA_comentario_e_linha_em_branco(tmp_path):
    alvo = tmp_path / "destinatarios.txt"
    alvo.write_text("# a mesa\nmesa@banco\n\n#   fulano@banco (de ferias)\n"
                    "  chefe@banco  \n", encoding="utf-8")
    assert leilao_hoje.destinatarios(alvo) == ["mesa@banco", "chefe@banco"]


def test_SEM_ARQUIVO_a_lista_e_vazia_e_nao_levanta(tmp_path):
    """Lista vazia leva a ENSAIO la em cima, que e a falha segura."""
    assert leilao_hoje.destinatarios(tmp_path / "nao-existe.txt") == []


def test_todo_endereco_do_arquivo_do_projeto_E_UM_ENDERECO():
    """Um endereco torto so apareceria as 10h45, na hora do envio.

    O teste nasceu dizendo "o arquivo comeca sem ninguem" -- e deixou de valer
    em 28/10/2026, quando ela pos o proprio endereco para o primeiro teste de
    verdade. O que continua valendo, e que custa caro quando quebra, e a
    FORMA: o Outlook recusa a mensagem inteira por causa de uma linha torta, e
    isso acontece no minuto em que nao da para consertar.
    """
    lista = leilao_hoje.destinatarios()
    for endereco in lista:
        assert endereco.count("@") == 1, endereco
        usuario, dominio = endereco.split("@")
        assert usuario, "endereco sem nome antes do @: %r" % endereco
        assert "." in dominio, "dominio sem ponto: %r" % endereco
        assert " " not in endereco, "espaco no meio: %r" % endereco


# ------------------------------------ a trava dos papeis incompletos


_CALENDARIO = [
    {"DATA_LEILAO": "2026-10-20", "TIPO_LEILAO": "Venda",
     "TITULO": "NTN-B", "VENCIMENTO": "2029-05-15"},
    {"DATA_LEILAO": "2026-10-20", "TIPO_LEILAO": "Venda",
     "TITULO": "NTN-B", "VENCIMENTO": "2045-05-15"},
    {"DATA_LEILAO": "2026-10-20", "TIPO_LEILAO": "Venda",
     "TITULO": "LFT", "VENCIMENTO": "2032-12-01"},
    # Um de COMPRA no mesmo dia: nao tem e-mail e nao pode segurar nada.
    {"DATA_LEILAO": "2026-10-20", "TIPO_LEILAO": "Compra",
     "TITULO": "NTN-B", "VENCIMENTO": "2035-05-15"},
    {"DATA_LEILAO": "2026-10-22", "TIPO_LEILAO": "Venda",
     "TITULO": "LTN", "VENCIMENTO": "2028-01-01"},
]


def _espera(monkeypatch):
    """Fixa os esperados do calendario de mentira.

    O CONJUNTO E CALCULADO ANTES do monkeypatch: um lambda que chamasse
    leilao_hoje.papeis_esperados chamaria a si mesmo, porque a essa altura ele
    JA E o atributo trocado. RecursionError, e nao erro de logica -- levei uma
    rodada para ver.
    """
    esperados = leilao_hoje.papeis_esperados(_DIA, _CALENDARIO)
    monkeypatch.setattr(leilao_hoje, "papeis_esperados",
                        lambda *a, **k: esperados)
    return esperados


def _so_saiu(monkeypatch, vertices):
    """O que o dado de hoje ja tem, como (titulo, vencimento)."""
    monkeypatch.setattr(leilao_hoje, "papeis_que_sairam",
                        lambda *a, **k: set(vertices))


def test_a_COMPRA_do_calendario_nao_segura_o_email_de_venda(monkeypatch):
    """Leilao de compra existe no calendario e nao tem e-mail."""
    esperados = leilao_hoje.papeis_esperados(_DIA, _CALENDARIO)
    assert ("NTN-B", "2035-05-15") not in esperados
    assert len(esperados) == 3


def test_FALTANDO_UM_VERTICE_ele_NAO_MANDA(monkeypatch, tmp_path):
    """O defeito que ela descreveu em 29/10/2026: "as vezes um papel demora
    mais que outro para sair a quantidade, e ai o email sai com um dv menor".

    O e-mail sairia com DV01 menor e SEM PARECER ERRADO. E por isso que a
    comparacao e por vertice: a NTN-B 2045 atrasada nao e coberta pela 2029
    que ja saiu.
    """
    _sem_montar(monkeypatch, tmp_path)
    _as_dez_da_manha(monkeypatch)
    _espera(monkeypatch)
    _so_saiu(monkeypatch, [("NTN-B", "2029-05-15"),
                           ("LFT", "2032-12-01")])      # falta a 2045

    carteiro = _Carteiro()
    falas = []
    voltas = []

    def relogio():
        voltas.append(1)
        return dt.datetime(2026, 10, 20, 10 if len(voltas) < 4 else 15, 0)
    monkeypatch.setattr(leilao_hoje, "_agora", relogio)

    feitos = leilao_hoje.espera_e_despacha(
        _DIA, enviar=carteiro, para=["mesa@banco"], destino=tmp_path,
        saida=falas.append, dormir=lambda _s: None,
        buscar=lambda _d: {"oferta", "resultado"})

    assert feitos == [], "mandou com vertice faltando"
    assert carteiro.mandados == []
    assert any("2045-05-15" in f for f in falas), (
        "nao disse QUAL vertice faltou: %s" % falas)
    assert any("mesmo-incompleto" in f for f in falas), (
        "nao ofereceu a saida para o caso de cancelamento")


def test_COM_TODOS_os_vertices_ele_manda(monkeypatch, tmp_path):
    """A outra metade: sem esta, "nao mandou" passaria com a trava travada
    para sempre."""
    _sem_montar(monkeypatch, tmp_path)
    _as_dez_da_manha(monkeypatch)
    _espera(monkeypatch)
    _so_saiu(monkeypatch, [("NTN-B", "2029-05-15"), ("NTN-B", "2045-05-15"),
                           ("LFT", "2032-12-01")])

    carteiro = _Carteiro()
    feitos = leilao_hoje.espera_e_despacha(
        _DIA, enviar=carteiro, para=["mesa@banco"], destino=tmp_path,
        saida=lambda *a: None, dormir=lambda _s: None,
        buscar=lambda _d: {"oferta", "resultado"})
    assert feitos == ["oferta", "resultado"]
    assert len(carteiro.mandados) == 2


def test_vertice_A_MAIS_do_que_o_calendario_previa_NAO_segura(monkeypatch):
    """Leilao extraordinario acontece -- os de compra de 26 e 27/10/2026 nao
    estavam no comunicado trimestral. O que segura e o que FALTA."""
    esperados = leilao_hoje.papeis_esperados(_DIA, _CALENDARIO)
    sairam = esperados | {("NTN-B", "2060-08-15")}
    assert esperados - sairam == set()


def test_CALENDARIO_CALADO_sobre_o_dia_avisa_que_nao_da_para_conferir(
        monkeypatch, tmp_path):
    """Nao e "esta tudo la", e "nao da para conferir".

    Ela pediu uma GARANTIA. Num dia que o calendario nao cobre nao ha
    garantia, e dizer isso em voz alta e o minimo -- calar seria afirmar o
    que nao se sabe.
    """
    _sem_montar(monkeypatch, tmp_path)
    _as_dez_da_manha(monkeypatch)
    monkeypatch.setattr(leilao_hoje, "papeis_esperados", lambda *a, **k: set())

    carteiro = _Carteiro()
    falas = []
    feitos = leilao_hoje.espera_e_despacha(
        _DIA, enviar=carteiro, para=["mesa@banco"], destino=tmp_path,
        saida=falas.append, dormir=lambda _s: None,
        buscar=lambda _d: {"oferta", "resultado"})

    assert feitos == ["oferta", "resultado"], "parou de mandar por precaucao"
    assert any("NAO DA PARA CONFERIR" in f for f in falas), falas
    # UMA VEZ SO, e nao a cada volta ate as 14h.
    assert sum("NAO DA PARA CONFERIR" in f for f in falas) == 1


def test_mesmo_incompleto_FORCA_o_envio(monkeypatch, tmp_path):
    """Para o dia em que o vertice foi CANCELADO -- aconteceu em 29/10/2026,
    o leilao inteiro caiu. Cancelado e atrasado sao indistinguiveis daqui, e
    so ela sabe qual e qual."""
    _sem_montar(monkeypatch, tmp_path)
    _as_dez_da_manha(monkeypatch)
    _espera(monkeypatch)
    _so_saiu(monkeypatch, [("NTN-B", "2029-05-15")])

    carteiro = _Carteiro()
    feitos = leilao_hoje.espera_e_despacha(
        _DIA, enviar=carteiro, para=["mesa@banco"], destino=tmp_path,
        saida=lambda *a: None, dormir=lambda _s: None,
        buscar=lambda _d: {"oferta", "resultado"}, mesmo_incompleto=True)
    assert feitos == ["oferta", "resultado"]
