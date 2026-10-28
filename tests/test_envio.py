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


class _Outlook:
    def __init__(self, **como):
        self.mensagem = _Mensagem(**como)

    def CreateItem(self, qual):
        assert qual == 0, "0 e olMailItem; outro numero e outra coisa"
        return self.mensagem


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
