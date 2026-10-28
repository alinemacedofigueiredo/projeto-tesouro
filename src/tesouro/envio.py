"""O unico lugar do projeto que manda e-mail.

SEPARADO DE PROPOSITO de quem monta (email_leilao) e de quem espera
(leilao_hoje). Montar e deterministico e tem teste; mandar e irreversivel e
sai para fora. Enquanto os tres estiverem separados, nenhum teste de formato
ou de laco consegue disparar mensagem para uma lista -- e ha teste nos outros
dois reprovando se algum deles ganhar caminho de envio proprio.

PELO OUTLOOK, E SEM SENHA NENHUMA. Decidido com ela em 28/10/2026. Ele usa a
sessao que ja esta aberta e logada na maquina: o projeto nunca ve, nunca pede
e nunca guarda credencial. E o caminho que costuma sobreviver as travas de
banco justamente por nao abrir conexao nova.

ELA USA O "NOVO OUTLOOK" PARA LER, E TEM OS DOIS INSTALADOS. O novo nao pode
ser automatizado -- nao e configuracao, e porta que a Microsoft nao
implementou. Entao este modulo fala com o CLASSICO, em segundo plano, como
motor de envio. Os dois atendem a mesma conta: a mensagem sai da caixa dela e
aparece nos Enviados dela, e a rotina de leitura nao muda. No dia em que o
banco tirar o classico da maquina, este caminho morre e sobra SMTP.

A GUARDA DO PROPRIO OUTLOOK e o que pode transformar "automatico" em
"automatico ate alguem clicar": ele tem protecao contra programa que manda
e-mail sozinho e pode abrir uma caixa pedindo autorizacao. Nao da para saber
daqui se a politica dela permite. Por isso, quando o envio e recusado, este
modulo ABRE A MENSAGEM PRONTA em vez de falhar calado -- e diz, em voz alta,
que ela precisa clicar. Ver _EXPLICA_A_GUARDA.

NAO HA MODO "MANDA DE QUALQUER JEITO". Se o Outlook nao estiver la, levanta.
Inventar um caminho alternativo em silencio seria pior que nao mandar.
"""
import datetime as dt

_SEM_OUTLOOK = (
    "nao consegui falar com o Outlook classico desta maquina.\n"
    "\n"
    "Motivo: {motivo}\n"
    "\n"
    "Tres coisas costumam explicar isto, nesta ordem:\n"
    "\n"
    "  1. o pacote pywin32 nao esta instalado    ->  pip install pywin32\n"
    "  2. so existe o NOVO Outlook nesta maquina ->  ele nao pode ser\n"
    "     automatizado; e preciso o classico instalado, mesmo que voce leia\n"
    "     no novo\n"
    "  3. o Outlook classico nao abre por politica da maquina\n"
    "\n"
    "Enquanto isso, o e-mail JA ESTA MONTADO em disco -- abra o arquivo que o\n"
    "programa imprimiu, selecione tudo, e cole numa mensagem nova."
)

_EXPLICA_A_GUARDA = (
    "O Outlook RECUSOU o envio automatico e eu ABRI A MENSAGEM PRONTA.\n"
    "Ela esta na sua tela, preenchida -- falta voce clicar em Enviar.\n"
    "\n"
    "Isto costuma ser a protecao do proprio Outlook contra programa que manda\n"
    "e-mail sozinho. Se acontecer todo dia, vale perguntar a TI se da para\n"
    "liberar o acesso programatico; sem isso, o 'automatico' precisa de voce\n"
    "na frente da maquina as 10h45."
)


class NaoMandou(Exception):
    """O e-mail NAO saiu. Nunca levantada quando ele saiu."""


# A MENSAGEM FOI ABERTA MAS NAO ENVIADA -- definida em leilao_hoje, porque
# quem precisa REAGIR a ela e o laco, e o laco nao pode importar este modulo
# (ha teste reprovando). Aqui ela e so levantada.
#
# EXCECAO E NAO AVISO, de proposito: quem chamou precisa NAO marcar o dia como
# enviado, senao a proxima rodada acha que ja foi e ninguem recebe nada.
from .leilao_hoje import FoiSoAberto  # noqa: F401


def _aplicacao():
    """O Outlook classico desta maquina, ou levanta explicando."""
    try:
        import win32com.client
    except ImportError as erro:
        raise NaoMandou(_SEM_OUTLOOK.format(motivo=erro)) from erro
    try:
        return win32com.client.Dispatch("Outlook.Application")
    except Exception as erro:            # noqa: BLE001
        raise NaoMandou(_SEM_OUTLOOK.format(motivo=erro)) from erro


def pelo_outlook(assunto, corpo, para, aplicacao=None, saida=print):
    """Manda o e-mail pelo Outlook classico. Devolve a hora em que saiu.

    'aplicacao' existe para o teste: ele passa um Outlook de mentira e exercita
    os dois caminhos -- o que envia e o que e recusado -- sem terminal, sem
    pywin32 e, principalmente, sem mandar nada.
    """
    if not para:
        raise NaoMandou("sem destinatario: nao ha para quem mandar")

    app = aplicacao or _aplicacao()
    mensagem = app.CreateItem(0)         # 0 = olMailItem
    mensagem.Subject = assunto
    mensagem.HTMLBody = corpo
    mensagem.To = "; ".join(para)

    try:
        mensagem.Send()
    except Exception as erro:            # noqa: BLE001
        # A RECUSA NAO PODE VIRAR SILENCIO NEM VIRAR SUCESSO. Abre a mensagem
        # pronta e levanta: quem chamou nao marca o dia como enviado.
        try:
            mensagem.Display()
        except Exception:                # noqa: BLE001
            raise NaoMandou(
                "o Outlook recusou enviar E recusou abrir a mensagem (%s)"
                % erro) from erro
        saida(_EXPLICA_A_GUARDA)
        raise FoiSoAberto(
            "a mensagem foi aberta e esta esperando voce clicar em Enviar "
            "(%s)" % erro) from erro

    quando = dt.datetime.now()
    saida("e-mail enviado pelo Outlook as %s" % quando.strftime("%H:%M:%S"))
    return quando


def outlook_responde():
    """Da para mandar nesta maquina? Para dizer ANTES de a manha comecar.

    Nao manda nada e nao abre janela: so pergunta se o caminho existe. Quem
    roda o modo 'hoje' as 9h30 precisa saber as 9h30, e nao as 10h45, que o
    envio nao vai funcionar.
    """
    try:
        _aplicacao()
        return True, "o Outlook classico respondeu"
    except NaoMandou as erro:
        return False, str(erro)
