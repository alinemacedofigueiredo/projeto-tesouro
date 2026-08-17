"""Escrita atomica de arquivos brutos.

Compartilhado entre os coletores: qualquer download que grava em
data/raw/ tem o mesmo risco de deixar um arquivo truncado la se o
processo morrer no meio da escrita.
"""


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
    """
    tmp = caminho.with_name(caminho.name + ".part")
    try:
        tmp.write_bytes(conteudo)
        tmp.replace(caminho)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
