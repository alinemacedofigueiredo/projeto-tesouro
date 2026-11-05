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
    def grava(dia, tipo, estagio, destino=None, faltando=None):
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
#
# AS DUAS PONTAS TEM REGRAS OPOSTAS, dela, em 30/10/2026:
#
#   oferta     espera os papeis do CALENDARIO; as 10:05 manda assim mesmo,
#              avisando no corpo o que nao puxou;
#   resultado  espera os papeis que foram OFERTADOS; ao meio-dia, faltando
#              vertice, NAO manda.
#
# Oferta incompleta ainda informa o lote que ja saiu. Resultado incompleto
# mente sobre o DV01 colocado, e o numero menor nao parece errado.


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
]

_TODOS = {("NTN-B", "2029-05-15"), ("NTN-B", "2045-05-15"),
          ("LFT", "2032-12-01")}


def _relogio(monkeypatch, *horas):
    """Um relogio que anda pelas horas dadas e DEPOIS SEGUE ANDANDO.

    O "depois segue andando" nao e detalhe: a primeira versao repetia a ultima
    hora para sempre, e um laco que espera algo que nunca chega rodava
    INFINITO -- com dormir() sem efeito no teste, travou a suite. Avancando um
    minuto por volta, todo teste termina, por prazo se nao por despacho.
    """
    passos = list(horas)
    estado = {"ultima": passos[-1]}

    def agora():
        if passos:
            estado["ultima"] = passos.pop(0)
        else:
            anterior = dt.datetime.combine(_DIA, estado["ultima"])
            estado["ultima"] = (anterior + dt.timedelta(minutes=1)).time()
        return dt.datetime.combine(_DIA, estado["ultima"])
    monkeypatch.setattr(leilao_hoje, "_agora", agora)


def _mundo(monkeypatch, ofertados=None, com_resultado=None):
    """O que ja saiu, vertice a vertice, nas duas pontas."""
    monkeypatch.setattr(leilao_hoje, "papeis_que_sairam",
                        lambda *a, **k: set(ofertados or ()))
    monkeypatch.setattr(leilao_hoje, "com_resultado",
                        lambda *a, **k: set(com_resultado or ()))


def _no_calendario(monkeypatch, registros=_CALENDARIO):
    esperados = leilao_hoje.papeis_esperados(_DIA, registros)
    monkeypatch.setattr(leilao_hoje, "papeis_esperados",
                        lambda *a, **k: esperados)
    return esperados


def test_a_COMPRA_do_calendario_nao_segura_o_email_de_venda():
    """Leilao de compra existe no calendario e nao tem e-mail."""
    esperados = leilao_hoje.papeis_esperados(_DIA, _CALENDARIO)
    assert ("NTN-B", "2035-05-15") not in esperados
    assert esperados == _TODOS


def test_vertice_A_MAIS_do_que_o_calendario_previa_NAO_segura():
    """Leilao extraordinario acontece. O que segura e o que FALTA."""
    esperados = leilao_hoje.papeis_esperados(_DIA, _CALENDARIO)
    assert esperados - (esperados | {("NTN-B", "2060-08-15")}) == set()


def test_DIA_FORA_DO_CALENDARIO_termina_na_hora_sem_mandar(monkeypatch,
                                                           tmp_path):
    """Escopo que ela fechou em 30/10/2026: por enquanto, so leilao do
    calendario.

    E TERMINA NA HORA, em vez de esperar ate o meio-dia: o calendario e lido
    do disco e nao muda durante a rodada, entao esperar nao traria nada.
    """
    _sem_montar(monkeypatch, tmp_path)
    monkeypatch.setattr(leilao_hoje, "papeis_esperados", lambda *a, **k: set())
    carteiro = _Carteiro()
    voltas = []
    falas = []

    feitos = leilao_hoje.espera_e_despacha(
        _DIA, enviar=carteiro, para=["mesa@banco"], destino=tmp_path,
        saida=falas.append, dormir=lambda _s: None,
        buscar=lambda d: voltas.append(d) or {"oferta", "resultado"})

    assert feitos == []
    assert carteiro.mandados == []
    assert voltas == [], "foi buscar em dia que nem esta no calendario"
    assert any("fora do calendario" in f for f in falas), falas


# ------------------------------------------------------------- a OFERTA


def test_a_OFERTA_espera_todos_os_papeis_antes_das_10h05(monkeypatch,
                                                         tmp_path):
    _sem_montar(monkeypatch, tmp_path)
    _no_calendario(monkeypatch)
    _relogio(monkeypatch, dt.time(10, 0), dt.time(10, 1), dt.time(10, 2))
    # Falta a 2045 e o relogio nao chegou nas 10:05.
    _mundo(monkeypatch, ofertados={("NTN-B", "2029-05-15"),
                                   ("LFT", "2032-12-01")})

    carteiro = _Carteiro()
    falas = []
    feitos = leilao_hoje.espera_e_despacha(
        _DIA, enviar=carteiro, para=["mesa@banco"], destino=tmp_path,
        saida=falas.append, dormir=lambda _s: None,
        buscar=lambda _d: {"oferta"},
        prazo_do_resultado=dt.time(10, 3))

    assert feitos == [], "mandou antes de todos os papeis sairem"
    assert carteiro.mandados == []
    assert any("2045-05-15" in f for f in falas), falas


def test_a_OFERTA_sai_quando_TODOS_saem(monkeypatch, tmp_path):
    _sem_montar(monkeypatch, tmp_path)
    _no_calendario(monkeypatch)
    _relogio(monkeypatch, dt.time(10, 1))
    _mundo(monkeypatch, ofertados=_TODOS)

    carteiro = _Carteiro()
    feitos = leilao_hoje.espera_e_despacha(
        _DIA, enviar=carteiro, para=["mesa@banco"], destino=tmp_path,
        saida=lambda *a: None, dormir=lambda _s: None,
        buscar=lambda _d: {"oferta"}, prazo_do_resultado=dt.time(10, 2))
    assert feitos == ["oferta"]
    assert len(carteiro.mandados) == 1


def test_PASSADO_O_PRAZO_a_OFERTA_SAI_INCOMPLETA_avisando_no_CORPO(monkeypatch,
                                                            tmp_path):
    """A regra dela: "Se nao cumprir ate 10:05, envia o email com o que tem, e
    avisa dentro do email os papeis que voce nao conseguiu puxar".

    DENTRO e a palavra que importa. Um aviso so no log serve a quem rodou;
    quem recebe e que vai olhar o DV01 e tirar conclusao dele.
    """
    _sem_montar(monkeypatch, tmp_path)
    _no_calendario(monkeypatch)
    # DEPOIS do prazo da oferta, seja ele qual for. A primeira versao
    # cravava 10:06 contra um prazo de 10:05, e quando ela corrigiu o horario
    # para 10:35 -- o Tesouro mostra a oferta as 10:30 -- o teste virou
    # vermelho sem nada estar errado na producao. Amarra no lugar errado.
    depois = (dt.datetime.combine(_DIA, leilao_hoje.PRAZO_DA_OFERTA)
              + dt.timedelta(minutes=1)).time()
    _relogio(monkeypatch, depois)
    _mundo(monkeypatch, ofertados={("NTN-B", "2029-05-15")})

    avisados = {}

    def grava(dia, tipo, estagio, destino=None, faltando=None):
        avisados[estagio] = faltando
        alvo = tmp_path / ("email-%s.html" % estagio)
        alvo.write_text("<div/>", encoding="utf-8")
        return alvo, {"tipo": tipo, "estagio": estagio,
                      "rotulo": "NTN-B/LFT", "data_leilao": dia}
    monkeypatch.setattr(leilao_hoje.email_leilao, "grava", grava)

    carteiro = _Carteiro()
    feitos = leilao_hoje.espera_e_despacha(
        _DIA, enviar=carteiro, para=["mesa@banco"], destino=tmp_path,
        saida=lambda *a: None, dormir=lambda _s: None,
        buscar=lambda _d: {"oferta"},
        prazo_do_resultado=(dt.datetime.combine(_DIA, depois)
                            + dt.timedelta(minutes=1)).time())

    assert feitos == ["oferta"], "segurou a oferta depois do prazo"
    assert avisados["oferta"] == {("NTN-B", "2045-05-15"),
                                  ("LFT", "2032-12-01")}, (
        "nao passou a lista de faltantes para dentro do e-mail")


# ---------------------------------------------------------- o RESULTADO


def test_o_RESULTADO_espera_os_que_foram_OFERTADOS_e_nao_o_calendario(
        monkeypatch, tmp_path):
    """Desenho dela, e melhor que o meu: a oferta e a verdade DO DIA.

    Aqui o calendario previa tres vertices e o Tesouro ofertou DOIS. O
    resultado nao pode ficar esperando um terceiro que nunca foi ofertado.
    """
    _sem_montar(monkeypatch, tmp_path)
    _no_calendario(monkeypatch)
    _relogio(monkeypatch, dt.time(11, 50))
    ofertados = {("NTN-B", "2029-05-15"), ("LFT", "2032-12-01")}
    _mundo(monkeypatch, ofertados=ofertados, com_resultado=ofertados)

    carteiro = _Carteiro()
    feitos = leilao_hoje.espera_e_despacha(
        _DIA, enviar=carteiro, para=["mesa@banco"], destino=tmp_path,
        saida=lambda *a: None, dormir=lambda _s: None,
        buscar=lambda _d: {"oferta", "resultado"},
        prazo_do_resultado=dt.time(11, 51))
    assert "resultado" in feitos


def test_o_RESULTADO_INCOMPLETO_NAO_SAI_nem_depois_do_meio_dia(monkeypatch,
                                                               tmp_path):
    """A outra metade da regra, e a mais cara: faltando vertice, nao manda.

    Resultado incompleto diria um DV01 MENOR do que o colocado, e um numero
    menor nao parece errado -- nao ha aviso que conserte isso, porque quem le
    nao tem contra o que comparar.
    """
    _sem_montar(monkeypatch, tmp_path)
    _no_calendario(monkeypatch)
    _relogio(monkeypatch, dt.time(11, 50), dt.time(12, 30))
    _mundo(monkeypatch, ofertados=_TODOS,
           com_resultado={("NTN-B", "2029-05-15")})

    carteiro = _Carteiro()
    falas = []
    feitos = leilao_hoje.espera_e_despacha(
        _DIA, enviar=carteiro, para=["mesa@banco"], destino=tmp_path,
        saida=falas.append, dormir=lambda _s: None,
        buscar=lambda _d: {"oferta", "resultado"})

    assert "resultado" not in feitos
    assert not any("resultado" in m[0] for m in carteiro.mandados)
    assert any("NAO MANDEI O RESULTADO" in f for f in falas), falas
    assert any("2045-05-15" in f for f in falas), (
        "nao disse QUAL vertice faltou")


def test_depois_do_meio_dia_o_laco_TERMINA(monkeypatch, tmp_path):
    """"depois desse horario NAO precisa disparar nenhum email automatico"."""
    _sem_montar(monkeypatch, tmp_path)
    _no_calendario(monkeypatch)
    _relogio(monkeypatch, dt.time(12, 1))
    _mundo(monkeypatch, ofertados=_TODOS, com_resultado=_TODOS)

    carteiro = _Carteiro()
    voltas = []
    feitos = leilao_hoje.espera_e_despacha(
        _DIA, enviar=carteiro, para=["mesa@banco"], destino=tmp_path,
        saida=lambda *a: None, dormir=lambda _s: None,
        buscar=lambda d: voltas.append(d) or {"oferta", "resultado"})

    assert feitos == []
    assert carteiro.mandados == []
    assert voltas == [], "ainda foi buscar depois do meio-dia"


def test_REINICIAR_no_meio_da_manha_nao_remanda_a_oferta(monkeypatch,
                                                         tmp_path):
    """O caso que vai acontecer: a maquina do banco cai as 10h20."""
    _sem_montar(monkeypatch, tmp_path)
    _no_calendario(monkeypatch)
    _relogio(monkeypatch, dt.time(11, 50))
    _mundo(monkeypatch, ofertados=_TODOS, com_resultado=_TODOS)

    antes = _Carteiro()
    leilao_hoje.despacha(_DIA, "ntnb", "oferta", antes, ["mesa@banco"],
                         destino=tmp_path, saida=lambda *a: None)

    depois = _Carteiro()
    feitos = leilao_hoje.espera_e_despacha(
        _DIA, enviar=depois, para=["mesa@banco"], destino=tmp_path,
        saida=lambda *a: None, dormir=lambda _s: None,
        buscar=lambda _d: {"oferta", "resultado"},
        prazo_do_resultado=dt.time(11, 51))

    assert [m[0] for m in depois.mandados] == ["Leilao NTN-B/LFT resultado"]
    assert feitos == ["resultado"], (
        "o laco disse ter mandado a oferta que a guarda impediu")


def test_a_mensagem_SO_ABERTA_nao_derruba_a_espera_do_RESULTADO(monkeypatch,
                                                                tmp_path):
    """A guarda do Outlook pode barrar a oferta.

    Tres coisas ao mesmo tempo: o dia nao fica marcado como enviado, o laco
    NAO tenta de novo no minuto seguinte -- seriam dezenas de janelas na tela
    dela -- e o RESULTADO sai normalmente.
    """
    _sem_montar(monkeypatch, tmp_path)
    _no_calendario(monkeypatch)
    _relogio(monkeypatch, dt.time(11, 50))
    _mundo(monkeypatch, ofertados=_TODOS, com_resultado=_TODOS)

    mandados = []

    def carteiro(assunto, corpo, para):
        if "oferta" in assunto:
            raise leilao_hoje.FoiSoAberto("esperando voce clicar em Enviar")
        mandados.append(assunto)

    falas = []
    feitos = leilao_hoje.espera_e_despacha(
        _DIA, enviar=carteiro, para=["mesa@banco"], destino=tmp_path,
        saida=falas.append, dormir=lambda _s: None,
        buscar=lambda _d: {"oferta", "resultado"},
        prazo_do_resultado=dt.time(11, 51))

    assert feitos == ["resultado"], "contou como enviado o que ficou na tela"
    assert mandados == ["Leilao NTN-B/LFT resultado"]
    assert not leilao_hoje.ja_enviado(_DIA, "ntnb", "oferta", tmp_path)
    assert any("NAO FOI ENVIADO" in f for f in falas), falas


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


def test_ENQUANTO_espera_o_RESULTADO_ele_diz_quais_vertices_faltam(
        monkeypatch, tmp_path):
    """A espera precisa ser legivel ENQUANTO acontece, e nao so no fim.

    Se as 11h50 ele esta segurando porque a NTN-B 2045 nao saiu, ela precisa
    saber as 11h50 -- da para ligar para a mesa, ou decidir montar a mao. Ao
    meio-dia a informacao chega tarde: o e-mail ja nao serve.

    Esta e a mutacao que escapou na primeira prova de dentes: trocar o prazo
    do resultado pelo da oferta nao mudava NENHUM numero, so emudecia o aviso
    -- e nenhum teste ouvia.
    """
    _sem_montar(monkeypatch, tmp_path)
    _no_calendario(monkeypatch)
    _relogio(monkeypatch, dt.time(11, 50))
    _mundo(monkeypatch, ofertados=_TODOS,
           com_resultado={("NTN-B", "2029-05-15"), ("LFT", "2032-12-01")})

    falas = []
    leilao_hoje.espera_e_despacha(
        _DIA, enviar=_Carteiro(), para=["mesa@banco"], destino=tmp_path,
        saida=falas.append, dormir=lambda _s: None,
        buscar=lambda _d: {"oferta", "resultado"},
        prazo_do_resultado=dt.time(11, 55))

    esperando = [f for f in falas if f.startswith("resultado: faltam")]
    assert esperando, "nao avisou nada enquanto segurava o resultado: %s" % falas
    assert "2045-05-15" in esperando[0], esperando


def test_ENTRE_a_oferta_e_as_11h43_ele_nao_pergunta_NADA(monkeypatch,
                                                         tmp_path):
    """A janela morta, correcao dela em 05/11/2026.

    Depois que a oferta sai (~10:35) e antes de o resultado existir (11:45)
    nao ha nada para perguntar: o edital ja veio, o resultado nao existe, e o
    historico foi carregado antes do laco. Sao uns 68 minutos; antes desta
    correcao o laco perguntava 68 vezes pela mesma resposta.
    """
    _sem_montar(monkeypatch, tmp_path)
    _no_calendario(monkeypatch)
    _mundo(monkeypatch, ofertados=_TODOS, com_resultado=set())
    # CADA VOLTA DO LACO LE O RELOGIO MAIS DE UMA VEZ -- a condicao do while,
    # o 'agora' de dentro, e aqui ainda o buscar(), que anota a hora. Com uma
    # hora por volta o teste pulava a janela morta inteira: a oferta saia de
    # pendentes as 11:00 e a volta seguinte ja lia 11:50. Tres leituras por
    # hora deixam cada volta DENTRO da janela que ela deveria medir.
    _relogio(monkeypatch,
             *([dt.time(10, 40)] * 3     # acha a oferta ja despachada
               + [dt.time(10, 45)] * 3   # primeira volta na janela morta
               + [dt.time(11, 0)] * 3    # segunda volta, so sinal de vida
               + [dt.time(11, 50)] * 3))  # hora do resultado

    # A oferta ja saiu numa rodada anterior.
    leilao_hoje.despacha(_DIA, "ntnb", "oferta", _Carteiro(), ["mesa@banco"],
                         destino=tmp_path, saida=lambda *a: None)

    perguntas = []
    falas = []
    leilao_hoje.espera_e_despacha(
        _DIA, enviar=_Carteiro(), para=["mesa@banco"], destino=tmp_path,
        saida=falas.append, dormir=lambda _s: None,
        buscar=lambda d: perguntas.append(_relogio_agora()) or {"oferta"},
        prazo_do_resultado=dt.time(11, 55))

    assert perguntas, "nao perguntou nem na hora do resultado"

    # UMA PERGUNTA NA JANELA MORTA E LEGITIMA, e e a primeira: o laco so
    # descobre que a oferta ja saiu quando TENTA despachar e leva JaFoi. Dali
    # em diante ele sabe, e fica quieto.
    #
    # A primeira versao deste teste exigia ZERO perguntas antes das 11:43 e
    # ficava vermelha por causa dessa, que nao e desperdicio nenhum.
    cedo = [q for q in perguntas if q < leilao_hoje.HORA_DO_RESULTADO]
    assert len(cedo) <= 1, (
        "perguntou %d vezes na janela morta, as %s"
        % (len(cedo), [str(q) for q in cedo]))
    assert any("Nada a fazer ate" in f for f in falas), falas
    # UMA VEZ SO, e nao a cada volta da janela.
    assert sum("Nada a fazer ate" in f for f in falas) == 1


def _relogio_agora():
    return leilao_hoje._agora().time()
