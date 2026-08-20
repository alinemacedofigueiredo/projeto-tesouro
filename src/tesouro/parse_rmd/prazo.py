"""Abas 3.7, 3.8 e 3.9 -- prazo medio, em anos.

Ficam em tres tabelas separadas porque as dimensoes sao diferentes: a 3.7
abre por titulo, a 3.8 por indexador (DPMFi) e por instrumento (DPFe), e a
3.9 por indexador sobre emissoes. Uma tabela unica precisaria de uma coluna
que significa 'titulo' em umas linhas e 'indexador' em outras, e um
agrupamento acidental somaria grandezas incomparaveis sem gerar erro.

Os valores sao anos: a unidade 'milhoes' passada aos leitores genericos
tem fator 1 e nao altera nada.
"""
import re

from .. import config
from ..leitura_rmd import (
    aplicar_papel,
    descartar_folhas_sem_dado,
    ler_padrao_a,
    ler_padrao_b,
    ordem_dos_rotulos,
)

_ESFERAS = {"DPMFi", "DPFe"}

# 'Divida Mobiliaria' e 'Divida Contratual' sao subgrupos da DPFe, no
# mesmo papel que 'Tesouro Nacional' e 'Banco Central' tem na DPMFi.
_ENTIDADES = {
    "Tesouro Nacional",
    "Banco Central",
    "D\u00edvida Mobili\u00e1ria",
    "D\u00edvida Contratual",
}

# Nota de rodape numerada: '1 Titulos de renegociacao anteriores ao...'
_PADRAO_NOTA = re.compile(r"^\d+\s")


def _hierarquia(bruto):
    """Marca cada linha com nivel, entidade e folha.

    A chave e linha_origem, nunca o rotulo. 'Demais' aparece duas vezes
    nas abas 3.7 e 3.8 -- uma sob o Tesouro Nacional, outra sob a Divida
    Mobiliaria -- e indexar por texto faria a segunda sobrescrever a
    primeira, jogando a linha da DPMFi para dentro da DPFe sem erro
    nenhum.

    As linhas de nivel e de entidade sao preservadas com folha None:
    carregam o prazo medio agregado, e o prazo medio da DPF e exatamente
    o numero que a analise compara com a banda do PAF.
    """
    ordem = ordem_dos_rotulos(bruto)

    papel = {}
    nivel = None
    entidade = None

    for _, linha in ordem.iterrows():
        rotulo = str(linha["rotulo"]).strip()
        origem = linha["linha_origem"]

        if _PADRAO_NOTA.match(rotulo):
            continue  # nota de rodape

        if rotulo.upper() == "DPF":
            nivel, entidade = "DPF", None
            papel[origem] = (nivel, None, None)
        elif rotulo in _ESFERAS:
            nivel, entidade = rotulo, None
            papel[origem] = (nivel, None, None)
        elif rotulo in _ENTIDADES:
            entidade = rotulo
            papel[origem] = (nivel, entidade, None)
        else:
            papel[origem] = (nivel, entidade, rotulo)

    return papel


def _anotar(bruto, nome_da_folha):
    papel = _hierarquia(bruto)
    df = aplicar_papel(bruto, papel, ["nivel", "entidade", nome_da_folha])
    # Rede estrutural contra nota de rodape: _PADRAO_NOTA cobre a forma
    # numerada, mas nao 'Obs'/'OBS'. Uma folha sem valor em data nenhuma
    # nao e folha -- ver descartar_folhas_sem_dado.
    df = descartar_folhas_sem_dado(df, df[nome_da_folha].notna())
    return df.rename(columns={"valor_milhoes": "prazo_anos"})


def parse_por_titulo(xl):
    """Aba 3.7 -- prazo medio da DPF, por titulo."""
    df = _anotar(ler_padrao_a(xl, "3.7", "milhoes"), "titulo")
    return df[
        ["data", "nivel", "entidade", "titulo", "prazo_anos"]
    ].sort_values(["data", "nivel", "entidade", "titulo"]).reset_index(drop=True)


def parse_por_indexador(xl):
    """Aba 3.8 -- prazo medio da DPF, por indexador (e instrumento na DPFe).

    A coluna `entidade` existe pelo mesmo motivo da 3.7: 'Demais' aparece
    sob a DPMFi e sob a Divida Mobiliaria da DPFe, e sem o subgrupo na
    chave as duas linhas ficam indistinguiveis.
    """
    df = _anotar(ler_padrao_a(xl, "3.8", "milhoes"), "categoria")
    return df[
        ["data", "nivel", "entidade", "categoria", "prazo_anos"]
    ].sort_values(
        ["data", "nivel", "entidade", "categoria"]
    ).reset_index(drop=True)


def parse_emissoes(xl):
    """Aba 3.9 -- prazo medio das emissoes da DPMFi em ofertas publicas."""
    df = ler_padrao_b(xl, "3.9", linha_cabecalho=4, unidade="milhoes",
                      colunas_por_categoria=1)
    df = df[df["categoria"].str.lower() != "total"]
    df = df.rename(columns={"categoria": "indexador",
                            "valor_milhoes": "prazo_anos"})
    return df[["data", "indexador", "prazo_anos"]].reset_index(drop=True)


def gravar(xl):
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    for nome, df in (
        ("prazo_medio_por_titulo", parse_por_titulo(xl)),
        ("prazo_medio_por_indexador", parse_por_indexador(xl)),
        ("prazo_medio_emissoes", parse_emissoes(xl)),
    ):
        saida = config.PROCESSED_DIR / f"{nome}.csv"
        df.to_csv(saida, index=False, encoding="utf-8")
        print(f"gravado: {saida} ({len(df)} linhas)")
