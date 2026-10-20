"""Leitura de CSV com cache, invalidado pelo CONTEUDO do arquivo.

POR QUE ISTO EXISTE, medido em 20/10/2026 gravando a pagina do PAF:

    a pagina do PAF: 52,4 s   --   31,7 s dentro de pandas.read_csv

    dv_por_papel.csv        547 leituras   12,1 s
    leiloes.csv             270 leituras   15,5 s
    leiloes_recentes.csv    270 leituras    1,3 s
    vna.csv                 298 leituras    0,8 s

Sessenta por cento do tempo era reler o MESMO arquivo. rolagem.leiloes() era
chamado 270 vezes e relia dois CSVs em cada uma; curva._curva e
curva.data_da_curva reliam o dv_por_papel.csv inteiro, com conversao de data,
a cada chamada.

A CHAVE E O CONTEUDO, E NAO O CARIMBO DO ARQUIVO -- e isto foi medido, nao
suposto. A primeira versao usava (caminho, st_mtime_ns, tamanho), e o teste
test_arquivo_REESCRITO_com_o_MESMO_tamanho_e_relido ficou VERMELHO: no Windows
duas gravacoes seguidas do mesmo tamanho saem com o mesmo st_mtime_ns -- o
formato do carimbo tem unidade de 100 ns, mas o relogio que o preenche e muito
mais grosso. O cache servia o quadro velho.

Isso nao e hipotetico aqui: o pipeline grava e le o mesmo CSV dentro da mesma
rodada (parse_leiloes grava leiloes.csv e as paginas o leem depois), e
leiloes_recentes regrava o provisorio entre duas leituras.

O PRECO DO HASH, medido no mesmo dia -- ele le os bytes, que e o barato; o que
custa e o parse:

    leiloes.csv                     2,35 MB   hash  9,8 ms   parse 45,1 ms
    dv_por_papel.csv                1,15 MB   hash  2,6 ms   parse 20,3 ms
    estoque_titulos_vencimento.csv  1,62 MB   hash  4,7 ms   parse 51,9 ms
    vna.csv                         0,01 MB   hash  0,3 ms   parse  1,7 ms

Entre cinco e onze vezes mais barato. Sobra quase todo o ganho, e a correcao
deixa de depender de alguem lembrar de invalidar o cache ao gravar.

DEVOLVE COPIA. Quem chama costuma mexer no quadro que recebe (curva._curva
acrescenta a coluna "du"), e servir o mesmo objeto duas vezes faria a segunda
chamada receber o que a primeira sujou.
"""
import hashlib

import pandas as pd

_CACHE = {}

# Teto do cache, em numero de quadros. Os CSVs do projeto cabem todos em poucos
# megabytes, e um processo le no maximo duas dezenas de arquivos diferentes --
# o teto existe para um laco que lesse arquivo gerado em serie nao crescer sem
# limite, e nao por aperto de memoria.
_TETO = 64

# Argumentos que mudam o resultado e que a chave nao representa. Melhor recusar
# do que cachear errado: servir o arquivo inteiro a quem pediu duas linhas e um
# numero plausivel e errado.
_NAO_COBERTOS = ("converters", "chunksize", "iterator", "skiprows", "nrows",
                 "usecols", "names", "header")


def _chave(bytes_do_arquivo, kwargs):
    partes = []
    for nome in sorted(kwargs):
        valor = kwargs[nome]
        partes.append((nome, tuple(valor) if isinstance(valor, list) else valor))
    return (len(bytes_do_arquivo),
            hashlib.blake2b(bytes_do_arquivo, digest_size=16).digest(),
            tuple(partes))


def csv(caminho, **kwargs):
    """pandas.read_csv, servido do cache quando o conteudo e o mesmo.

    A assinatura e a de read_csv para os argumentos que este projeto usa --
    parse_dates, dtype, sep. Os de _NAO_COBERTOS sao recusados.
    """
    maus = [nome for nome in _NAO_COBERTOS if nome in kwargs]
    if maus:
        raise LookupError(
            "leitura.csv nao cobre %s: esses argumentos mudam o resultado de "
            "um jeito que a chave do cache nao representa. Chame "
            "pandas.read_csv direto." % maus)

    with open(caminho, "rb") as arquivo:
        cru = arquivo.read()
    chave = _chave(cru, kwargs)
    quadro = _CACHE.get(chave)
    if quadro is None:
        import io

        # O PARSE SAI DOS BYTES QUE JA FORAM LIDOS, e nao de uma segunda
        # abertura do arquivo: se alguem regravar o arquivo entre a leitura dos
        # bytes e o parse, o quadro ficaria guardado sob a chave do conteudo
        # ANTIGO. Ler duas vezes seria a propria armadilha que este cache
        # existe para nao ter.
        quadro = pd.read_csv(io.BytesIO(cru), **kwargs)
        if len(_CACHE) >= _TETO:
            _CACHE.clear()
        _CACHE[chave] = quadro
    return quadro.copy()


def esquece():
    """Esvazia o cache. Para teste, e para quem mexe no disco por fora."""
    _CACHE.clear()


def quantos():
    """Quantos quadros estao no cache agora. Para teste."""
    return len(_CACHE)
