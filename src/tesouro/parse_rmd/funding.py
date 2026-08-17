"""Abas 1.1 e 1.2 -- emissoes e resgates da DPF.

Ambas sao padrao A em R$ milhoes, e ambas tem a mesma forma: uma linha de
operacao em caixa alta (EMISSOES / RESGATES), uma linha de esfera abaixo
dela (DPMFi / DPFe), e as linhas de detalhe em seguida -- canal na 1.1,
indexador na 1.2.

Tres armadilhas moldaram este parser:

1. A aba 1.1 nomeia as esferas com numeral romano crescente ao longo da
   planilha: 'I - DPMFi' e 'II - DPFe' sob emissoes, mas 'III - DPMFi' e
   'IV - DPFe' sob resgates. Reconhecer so as duas primeiras descartaria
   todos os resgates sem erro nenhum.

2. Rotulos se repetem entre secoes: 'Trocas Oferta Publica' e 'Tesouro
   Direto' existem dos dois lados na 1.1; 'Demais' aparece quatro vezes
   na 1.2 (DPMFi e DPFe, emissao e resgate). Por isso a hierarquia e
   indexada por linha_origem, nunca pelo texto do rotulo, e por isso a
   esfera faz parte da chave das duas tabelas.

3. A indentacao nao serve de guia aqui: na 1.2 todos os rotulos estao com
   recuo zero, inclusive os de esfera. Quem decide o papel de cada linha
   e o formato do rotulo, na ordem em que aparece.

As linhas a partir de 'EMISSAO LIQUIDA' sao totais derivados (I - III e
II - IV) e ficam de fora, como tudo que e derivado neste projeto.
"""
import re

from .. import config
from ..leitura_rmd import (
    aplicar_papel,
    descartar_folhas_sem_dado,
    ler_padrao_a,
    ordem_dos_rotulos,
)

_OPERACOES = {"EMISSÕES": "emissao", "RESGATES": "resgate"}

# Aceita 'DPMFi' puro (aba 1.2) e com numeral romano (aba 1.1).
_PADRAO_ESFERA = re.compile(r"^(?:(?:I{1,3}|IV)\s*-\s*)?(DPMFi|DPFe)$")

# A carteira do Banco Central aparece na 1.1 no mesmo nivel de uma esfera.
_ESFERA_BACEN = "Banco Central"

_INICIO_DOS_DERIVADOS = "EMISSÃO LÍQUIDA"


def _anotar_hierarquia(df):
    """Marca cada linha com a sua operacao, esfera e se e linha de detalhe.

    Percorre os rotulos na ordem da planilha e vai carregando o estado.
    A chave e linha_origem: indexar por rotulo faria a secao de resgate
    sobrescrever a de emissao, e a tabela sairia inteira com a mesma
    operacao -- plausivel e errada, sem levantar excecao.
    """
    ordem = ordem_dos_rotulos(df)

    papel = {}
    operacao = None
    esfera = None

    for _, linha in ordem.iterrows():
        rotulo = str(linha["rotulo"]).strip()
        origem = linha["linha_origem"]

        if _INICIO_DOS_DERIVADOS in rotulo.upper():
            break  # dai para baixo e total calculado, nao dado

        if rotulo.upper().startswith("OBS"):
            continue  # nota de rodape ('Obs:' na 1.2, 'OBS:' na 1.1)

        if rotulo in _OPERACOES:
            operacao = _OPERACOES[rotulo]
            esfera = None
            papel[origem] = (operacao, None, False)
            continue

        achado = _PADRAO_ESFERA.match(rotulo)
        if achado:
            esfera = achado.group(1)
            papel[origem] = (operacao, esfera, False)
            continue

        if rotulo == _ESFERA_BACEN:
            esfera = _ESFERA_BACEN
            papel[origem] = (operacao, esfera, False)
            continue

        papel[origem] = (operacao, esfera, True)

    resultado = aplicar_papel(df, papel, ["operacao", "esfera", "eh_detalhe"])
    # Rede estrutural contra nota de rodape. Os filtros textuais acima sao
    # a primeira linha, mas dependem de como o Tesouro redige: na 1.1 as
    # notas caem depois do `break` de 'EMISSAO LIQUIDA' e na 1.2 nao ha
    # `break` nenhum, entao ali o prefixo 'OBS' era a defesa unica. Uma
    # folha sem valor em data nenhuma nao e folha -- ver
    # descartar_folhas_sem_dado.
    return descartar_folhas_sem_dado(resultado, resultado["eh_detalhe"])


def _detalhe(bruto):
    anotado = _anotar_hierarquia(bruto)
    return anotado[
        anotado["eh_detalhe"]
        & anotado["esfera"].notna()
        & anotado["operacao"].notna()
    ].copy()


def parse_por_canal(xl):
    """Aba 1.1 -- emissoes e resgates por canal de colocacao."""
    detalhe = _detalhe(ler_padrao_a(xl, "1.1", "milhoes"))
    detalhe = detalhe.rename(columns={"rotulo": "canal"})
    return detalhe[
        ["data", "esfera", "operacao", "canal", "valor_milhoes"]
    ].sort_values(["data", "operacao", "esfera", "canal"]).reset_index(drop=True)


def parse_por_indexador(xl):
    """Aba 1.2 -- emissoes e resgates por indexador.

    A esfera entra na chave: na DPFe o detalhe e moeda (Dolar, Euro,
    Real), nao indexador, e 'Demais' existe nas duas esferas com valores
    diferentes.
    """
    detalhe = _detalhe(ler_padrao_a(xl, "1.2", "milhoes"))
    detalhe = detalhe.rename(columns={"rotulo": "indexador"})
    return detalhe[
        ["data", "esfera", "operacao", "indexador", "valor_milhoes"]
    ].sort_values(
        ["data", "operacao", "esfera", "indexador"]
    ).reset_index(drop=True)


def gravar(xl):
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    for nome, df in (
        ("funding_por_canal", parse_por_canal(xl)),
        ("funding_por_indexador", parse_por_indexador(xl)),
    ):
        saida = config.PROCESSED_DIR / f"{nome}.csv"
        df.to_csv(saida, index=False, encoding="utf-8")
        print(f"gravado: {saida} ({len(df)} linhas)")
