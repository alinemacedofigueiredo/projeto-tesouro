"""O unico modulo que manda e-mail (src/tesouro/envio.py).

NENHUM TESTE DAQUI MANDA NADA. Todos passam um Outlook de mentira, e ha um que
reprova se o modulo tentar falar com o Outlook de verdade sem receber um.

O QUE PRECISA SER DEFENDIDO aqui nao e formato, e o que acontece QUANDO DA
ERRADO -- porque so existem duas formas de errar e as duas sao caras:

  dizer que mandou sem ter mandado   -> ninguem recebe e ninguem percebe;
  mandar achando que nao mandou      -> a mesa recebe duas vezes.

A guarda do proprio Outlook contra envio programatico e o caso real: ela
RECUSA o Send e, se nada for feito, o programa acha que falhou de vez. Aqui
ele abre a mensagem pronta e LEVANTA -- para quem chamou nao marcar o dia
como enviado.
"""
import pytest

from tesouro import envio


class _Mensagem:
    def __init__(self, recusa_enviar=False, recusa_abrir=False):
        self.recusa_enviar = recusa_enviar
        self.recusa_abrir = recusa_abrir
        self.Subject = None
        self.HTMLBody = None
        self.To = None
        self.enviada = False
        self.aberta = False

    def Send(self):
        if self.recusa_enviar:
            raise OSError("a guarda do Outlook recusou o envio programatico")
        self.enviada = True

    def Display(self):
        if self.recusa_abrir:
            raise OSError("nem abrir deu")
        self.aberta = True


class _Itens:
    def __init__(self, lista):
        self._lista = lista

    @property
    def Count(self):
        return len(self._lista)

    def Item(self, i):
        return self._lista[i - 1]          # o Outlook conta de 1


class _Pasta:
    def __init__(self, lista):
        self._lista = lista

    @property
    def Items(self):
        return _Itens(self._lista)


class _Namespace:
    def __init__(self, enviados):
        self._enviados = enviados

    def GetDefaultFolder(self, qual):
        assert qual == 5, "5 e a pasta Enviados"
        return _Pasta(self._enviados)


class _Outlook:
    """Um Outlook de mentira COM PASTA DE ENVIADOS.

    A VERSAO ANTERIOR NAO TINHA, e foi por isso que oito testes passaram em
    cima do defeito de 05/11/2026: eu modelei o Send() pelo que achava que ele
    fazia -- "mandou ou levantou" -- e o resto do modulo foi construido sobre
    essa suposicao. O Send() de verdade ENFILEIRA e devolve sucesso.

    'entrega' diz o que o Outlook de verdade faria: True poe a mensagem nos
    Enviados (saiu), False deixa so na fila (nao saiu).
    """

    def __init__(self, entrega=True, **como):
        self.mensagem = _Mensagem(**como)
        self.entrega = entrega
        self.enviados = []

    def CreateItem(self, qual):
        assert qual == 0, "0 e olMailItem; outro numero e outra coisa"
        return self.mensagem

    def GetNamespace(self, qual):
        assert qual == "MAPI"
        if self.mensagem.enviada and self.entrega:
            self.enviados = [self.mensagem]
        return _Namespace(self.enviados)


def test_o_caminho_normal_preenche_e_ENVIA():
    app = _Outlook()
    quando = envio.pelo_outlook("Leilao NTN-B/LFT", "<div>corpo</div>",
                                ["mesa@banco", "chefe@banco"],
                                aplicacao=app, saida=lambda *a: None)
    m = app.mensagem
    assert m.enviada is True
    assert m.aberta is False
    assert m.Subject == "Leilao NTN-B/LFT"
    assert m.HTMLBody == "<div>corpo</div>"
    assert m.To == "mesa@banco; chefe@banco"
    assert quando is not None


def test_a_GUARDA_DO_OUTLOOK_abre_a_mensagem_e_LEVANTA():
    """O caso que pode acontecer todo dia na maquina dela.

    Abrir sem levantar seria o pior dos mundos: a mensagem fica na tela, o
    programa marca o dia como enviado, e ninguem recebe nada.
    """
    app = _Outlook(recusa_enviar=True)
    falas = []
    with pytest.raises(envio.FoiSoAberto):
        envio.pelo_outlook("Leilao", "<div/>", ["mesa@banco"],
                           aplicacao=app, saida=falas.append)
    assert app.mensagem.enviada is False
    assert app.mensagem.aberta is True, "recusou enviar e nao abriu nada"
    assert any("clicar em Enviar" in f for f in falas), falas


def test_FoiSoAberto_NAO_e_sucesso_para_quem_chamou():
    """Contrato entre os dois modulos: leilao_hoje so marca o dia como
    enviado quando 'enviar' volta SEM excecao."""
    assert issubclass(envio.FoiSoAberto, Exception)
    assert not issubclass(envio.FoiSoAberto, Warning)


def test_recusar_ENVIAR_e_ABRIR_vira_NaoMandou():
    app = _Outlook(recusa_enviar=True, recusa_abrir=True)
    with pytest.raises(envio.NaoMandou):
        envio.pelo_outlook("Leilao", "<div/>", ["mesa@banco"],
                           aplicacao=app, saida=lambda *a: None)


def test_SEM_DESTINATARIO_levanta_antes_de_tocar_no_Outlook():
    """"Esqueci de dizer para quem" nao pode virar "mandou para alguem"."""
    class _Explode:
        def CreateItem(self, _qual):
            raise AssertionError("tocou no Outlook sem destinatario")

    with pytest.raises(envio.NaoMandou):
        envio.pelo_outlook("Leilao", "<div/>", [], aplicacao=_Explode())
    with pytest.raises(envio.NaoMandou):
        envio.pelo_outlook("Leilao", "<div/>", None, aplicacao=_Explode())


def test_SEM_pywin32_a_mensagem_de_erro_ENSINA_o_que_fazer(monkeypatch):
    """Ela nao conseguiu testar o pywin32 ainda, entao esta e a mensagem que
    ela vai ver primeiro se faltar."""
    import builtins
    de_verdade = builtins.__import__

    def sem_win32(nome, *resto):
        if nome.startswith("win32com"):
            raise ImportError("No module named 'win32com'")
        return de_verdade(nome, *resto)
    monkeypatch.setattr(builtins, "__import__", sem_win32)

    with pytest.raises(envio.NaoMandou) as erro:
        envio.pelo_outlook("Leilao", "<div/>", ["mesa@banco"])
    texto = str(erro.value)
    assert "pip install pywin32" in texto
    assert "NOVO Outlook" in texto, "nao explica a armadilha do novo Outlook"
    assert "ja esta montado" in texto.lower(), (
        "nao diz o que fazer agora: o arquivo existe e da para colar a mao")


def test_outlook_responde_DIZ_NAO_sem_levantar(monkeypatch):
    """Quem roda as 9h30 precisa saber as 9h30, e nao as 10h45."""
    monkeypatch.setattr(envio, "_aplicacao",
                        lambda: (_ for _ in ()).throw(
                            envio.NaoMandou("sem Outlook aqui")))
    pode, porque = envio.outlook_responde()
    assert pode is False
    assert "sem Outlook aqui" in porque

    monkeypatch.setattr(envio, "_aplicacao", lambda: _Outlook())
    pode, porque = envio.outlook_responde()
    assert pode is True


def test_o_modulo_NAO_GUARDA_NEM_PEDE_SENHA():
    """O caminho do Outlook foi escolhido justamente por nao precisar de
    credencial. Se um dia aparecer senha aqui, isto reprova."""
    import inspect

    fonte = inspect.getsource(envio).lower()
    for proibido in ("password", "senha =", "getpass", "login(",
                     "smtp_user", "credential"):
        assert proibido not in fonte, "achei %r no modulo de envio" % proibido


# ------------------------- Send() nao envia: ENFILEIRA


def test_mensagem_que_FICA_NA_FILA_nao_passa_por_enviada():
    """O defeito de 05/11/2026, no primeiro leilao de verdade.

    Send() devolveu sucesso as 10:43:54 e a mensagem ficou VINTE E CINCO
    MINUTOS na Caixa de Saida. Ela so descobriu porque foi olhar a caixa.

    E a consequencia foi pior que a frase errada: quem chamou MARCOU O DIA
    COMO ENVIADO, e a trava do reenvio -- que existe para proteger -- passou a
    impedir o envio de uma coisa que nunca saiu.

    A PROVA E A PASTA ENVIADOS, e nao o retorno do Send().
    """
    app = _Outlook(entrega=False)        # aceita, mas nao entrega
    with pytest.raises(envio.FoiSoEnfileirado):
        envio.pelo_outlook("Leilao", "<div/>", ["mesa@banco"],
                           aplicacao=app, saida=lambda *a: None,
                           espera=1)
    assert app.mensagem.enviada is True, "nem chegou a chamar Send()"


def test_FoiSoEnfileirado_NAO_e_sucesso_para_quem_chamou():
    """Mesmo contrato de FoiSoAberto: leilao_hoje so marca o dia quando
    'enviar' volta SEM excecao."""
    assert issubclass(envio.FoiSoEnfileirado, Exception)
    assert not issubclass(envio.FoiSoEnfileirado, Warning)


def test_a_mensagem_que_APARECE_nos_enviados_passa():
    """A outra metade: sem ela, "nunca confia no Send()" passaria com um
    modulo que nunca desse envio por certo."""
    app = _Outlook(entrega=True)
    quando = envio.pelo_outlook("Leilao", "<div/>", ["mesa@banco"],
                                aplicacao=app, saida=lambda *a: None,
                                espera=1)
    assert quando is not None
    assert app.mensagem.enviada is True


def test_conferir_procura_pelo_ASSUNTO_e_nao_so_pelo_ultimo_item():
    """Outra mensagem chegando nos Enviados no meio nao pode ser confundida
    com a nossa -- ela manda e-mail o dia todo nessa caixa."""
    app = _Outlook(entrega=True)
    app.mensagem.Subject = "Leilao LTN/NTN-F . Oferta . 05/11/2026"

    class _Outra:
        Subject = "RE: almoco"

    envio.pelo_outlook("Leilao LTN/NTN-F . Oferta . 05/11/2026", "<div/>",
                       ["mesa@banco"], aplicacao=app, saida=lambda *a: None,
                       espera=1)
    # entrega=False para o duble parar de repor a nossa mensagem na pasta a
    # cada GetNamespace -- senao o cenario que eu quero montar e desfeito
    # pelo proprio dubl\u00ea antes de ser medido.
    app.entrega = False
    app.enviados = [_Outra()]
    with pytest.raises(envio.FoiSoEnfileirado):
        envio._conferir_que_saiu(app, "Leilao LTN/NTN-F . Oferta . 05/11/2026",
                                 espera=1)
