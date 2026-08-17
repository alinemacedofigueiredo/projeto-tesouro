"""Escrita atomica de arquivos brutos.

Compartilhado entre os coletores: qualquer download que grava em
data/raw/ tem o mesmo risco de deixar um arquivo truncado la se o
processo morrer no meio da escrita, e o mesmo risco de gravar uma pagina
de erro como se fosse planilha.
"""

# Bytes iniciais de cada formato. 'PK' e o cabecalho do zip, que e o que
# um .xlsx e por dentro; D0CF11E0 e o do OLE2, do .xls legado (o arquivo
# de leiloes).
_ASSINATURAS = {
    ".xlsx": (b"PK",),
    ".xlsm": (b"PK",),
    ".zip": (b"PK",),
    ".xls": (b"\xd0\xcf\x11\xe0",),
}


def conferir_assinatura(conteudo, caminho):
    """Falha se o conteudo nao for a planilha que a extensao promete.

    Existe porque o site do Tesouro devolve pagina de erro em HTML com
    status 200. Sem esta checagem, o HTML e gravado como .xls ou .xlsx, e
    a guarda de idempotencia dos coletores passa a responder 'ja existe,
    nada a fazer' em toda execucao seguinte: o arquivo ruim fica
    permanente, e sair dele exige apagar a mao um arquivo de um diretorio
    que o projeto declara imutavel -- no ambiente de destino, sem quem
    construiu isto por perto.

    A checagem e por bytes magicos, nao por tamanho: uma pagina de erro
    pode ser grande. Extensao fora de _ASSINATURAS passa sem conferencia,
    para nao impedir que outro coletor grave outro formato por aqui.
    """
    esperadas = _ASSINATURAS.get(caminho.suffix.lower())
    if esperadas is None:
        return
    if any(conteudo.startswith(assinatura) for assinatura in esperadas):
        return
    raise ValueError(
        f"o conteudo baixado nao parece um {caminho.suffix} valido: "
        f"{len(conteudo)} bytes comecando com {conteudo[:16]!r}. "
        f"Provavelmente e uma pagina de erro devolvida com status 200. "
        f"Nada foi gravado em {caminho}."
    )


def gravar_atomico(conteudo, caminho):
    """Grava bytes em caminho sem nunca deixar um arquivo parcial no nome
    definitivo.

    O download e feito em duas etapas de proposito: primeiro escreve tudo
    num arquivo temporario '.part' ao lado do destino, so depois troca de
    nome com Path.replace (atomico no mesmo sistema de arquivos). Se o
    processo for interrompido no meio da escrita, sobra no maximo um '.part'
    solto; o arquivo final so existe se estiver completo, entao a checagem
    de idempotencia dos coletores (`if caminho.exists(): ...`, presente em
    fetch_leiloes.baixar e em fetch_rmd.baixar) nunca aceita um arquivo
    truncado como "ja existe". Nao troque isso por um write_bytes direto
    no destino.

    Atencao: o Path.replace substitui o destino sem avisar. Quem chama e
    responsavel por checar existencia antes -- data/raw/ e imutavel por
    invariante do projeto.

    A assinatura do conteudo e conferida antes de qualquer escrita: um
    arquivo ruim que chegue ao nome definitivo se torna permanente, porque
    a guarda de idempotencia dos coletores passa a aceita-lo.
    """
    conferir_assinatura(conteudo, caminho)

    tmp = caminho.with_name(caminho.name + ".part")
    try:
        tmp.write_bytes(conteudo)
        tmp.replace(caminho)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
