"""A orientacao de certificado, igual em todo caminho, e com quem assinou.

POR QUE ISTO EXISTE, e por que fora do codigo de download: o conserto de um erro
de certificado e PROPRIEDADE DA MAQUINA, e nao do projeto. O Python ja le a
variavel SSL_CERT_FILE sozinho, sem uma linha nossa -- entao aqui nao ha pacote
de certificados nem caminho fixo. Ha so a mensagem que diz o que fazer.

A PERGUNTA DELA em 28/09/2026, que desenhou este modulo: "isso nao vai dar
problema pra rodar no banco depois?". Ia dar, do jeito que eu tinha proposto --
embutir um pacote com a cadeia do SERPRO no repositorio. No banco isso falha de
duas formas:

  1. se o banco inspeciona o trafego, o certificado que o Python ve E DO BANCO,
     e um pacote com o SERPRO dentro nao serve para nada;
  2. em Linux o SSL_CERT_FILE SUBSTITUI o padrao em vez de somar (medido: no
     Windows soma, e a apiapex continuou verificando com um pacote de um
     certificado irrelevante). Um pacote so com o SERPRO derrubaria o resto do
     HTTPS.

Por isso a unica coisa que este modulo faz e EXPLICAR. Quem aponta a variavel e
a maquina, aqui ou no banco.

E DIZ QUEM ASSINOU. Sem essa linha, "erro de certificado" do SERPRO e "erro de
certificado" do proxy da casa dao a mesma mensagem, e sao conserto diferente.
"""
import socket
import ssl

TEMPO_LIMITE = 20

# NAO DESLIGA A VERIFICACAO, e isso tem teste. Mensagem de erro e o lugar mais
# tentador para sugerir o atalho, porque e o momento em que quem le esta com
# pressa -- e um "verify=False" posto ali sobrevive por anos.
_COMO_APONTAR = (
    "NAO desligue a verificacao. Aponte o Python para o pacote de\n"
    "certificados da instituicao:\n"
    "\n"
    '    PowerShell:  $env:SSL_CERT_FILE = "C:\\caminho\\para\\ca-bundle.crt"\n'
    "    bash:        export SSL_CERT_FILE=/caminho/para/ca-bundle.crt"
)


def quem_assinou(host, timeout=TEMPO_LIMITE):
    """O nome de quem emitiu o certificado do host, ou None.

    SEM VERIFICAR, de proposito: quem chama esta JA no caminho de erro, e o que
    se quer saber e justamente qual certificado chegou -- inclusive o que nao
    passou na verificacao. Isto nao abre conexao de dado nem baixa nada; e um
    aperto de mao para ler o cartao de visita.

    Devolve None em vez de levantar. Uma excecao aqui esconderia a falha de
    verdade, que e a de quem chamou.
    """
    contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    contexto.check_hostname = False
    contexto.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((host, 443), timeout=timeout) as cru:
            with contexto.wrap_socket(cru, server_hostname=host) as seguro:
                bruto = seguro.getpeercert(binary_form=True)
    except Exception:                                    # noqa: BLE001
        return None
    return _emissor(bruto)


def _emissor(der):
    """O nome mais longo que parece de autoridade, dentro do certificado bruto.

    LEITURA GROSSEIRA, e de proposito: decodificar ASN.1 a mao para pegar um
    nome que vai numa mensagem de erro seria muito codigo para pouco ganho, e
    trazer uma biblioteca de criptografia seria uma sexta dependencia. O nome do
    emissor aparece como texto legivel no DER, e e o unico uso disto.
    """
    import re

    texto = der.decode("latin-1")
    candidatos = re.findall(r"[ -~]{8,}", texto)
    autoridades = [c.strip() for c in candidatos
                   if re.search(r"\b(CA|AC)\b", c)]
    if not autoridades:
        return None
    return _limpar_nome(max(autoridades, key=len))


def _limpar_nome(nome):
    """Tira o byte do campo seguinte que vaza no fim do nome.

    A leitura do DER e por texto legivel, entao o comprimento do proximo campo
    entra como um digito colado no fim. Medido contra o certificado real do
    tesourotransparente.gov.br: saia "AC SERPRO AR46 OV TLS CA 20250", com um
    zero a mais.

    O CORTE E ESTREITO de proposito: so um digito, e so quando ha exatamente
    cinco seguidos no fim. Um nome que terminasse em cinco digitos de verdade
    seria estragado por isto -- e por isso o corte nao e "tira digito do fim".
    """
    import re

    return re.sub(r"(?<!\d)(\d{4})\d$", lambda m: m.group(1), nome.strip())


def orientacao(host, quem=None):
    """O texto que explica o erro de certificado daquele host.

    'quem' evita a rede quando quem chama ja sabe -- e e o que o teste passa.
    """
    if quem is None:
        quem = quem_assinou(host)
    linhas = [f"O certificado de {host} nao passou na verificacao."]
    if quem:
        linhas.append(f"Quem assinou: {quem}")
        linhas.append(
            "Se esse nome for do orgao publico, falta um elo da cadeia dele. Se\n"
            "for da sua instituicao, o trafego esta sendo inspecionado e o\n"
            "pacote a apontar e o dela."
        )
    linhas.append(_COMO_APONTAR)
    return "\n\n".join(linhas)
