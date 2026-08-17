"""Abas 4.1, 4.2 e 4.3 -- custo medio, em % ao ano.

As tres compartilham a mesma dimensao (nivel e titulo) e diferem apenas na
medida, entao viram uma tabela unica com coluna 'medida'. Comparar o custo
das emissoes com o custo do estoque -- o grafico mais informativo da secao
-- passa a ser um filtro em vez de um join.

Custo negativo e legitimo e nao deve ser filtrado: aparece na 4.1 para a
NTN-D em 2005.

A 4.3 muda de leiaute a partir de jan/2021 (a propria aba registra isso
numa nota 'Obs'): ate dez/2020 cada mes ocupa uma coluna, igual as demais
abas; dai em diante cada mes vira um cabecalho mesclado de dois niveis --
uma celula mesclada com o rotulo do mes cobrindo tres colunas, e a linha
de baixo com os sub-rotulos dessas tres colunas ('Taxa media', 'Variacao
do Indexador', 'CME'). So a CME equivale ao valor unico de antes.

Isso quebra o detector de cabecalho generico (que para na primeira linha
com 3+ meses reconheciveis): ele para na linha do rotulo do mes mesclado,
antes de chegar a linha das tres sub-colunas, e o valor sob esse rotulo
fica vazio (a celula mesclada so tem conteudo na primeira das tres
colunas). O resultado depende do titulo: para DPMFi e NTN-B1 da NaN; para
NTN-B e LFT da a 'Taxa media' isolada, um numero plausivel e errado (ex.:
NTN-B em jan/2021 vira 2.124644 em vez de 10.519469) -- a classe de falha
mais perigosa deste projeto, porque nao acusa nada. LTN e NTN-F saem
certos por coincidencia, ja que sao prefixados e a variacao do indexador
e sempre zero neles. Por isso a 4.3 tem leitura propria:
_colunas_de_data_4_3 acha a linha das sub-colunas (a que tem uma celula
'CME') e le a trinca certa; sem 'CME' -- caso da amostra recortada antes
de jan/2021 -- cai no mesmo detector generico das outras abas.
"""
import re

import pandas as pd

from .. import config
from ..conversoes import limpar_nulo, mes_para_data, para_milhoes
from ..leitura_rmd import (
    aba,
    aplicar_papel,
    descartar_folhas_sem_dado,
    ler_padrao_a,
    ordem_dos_rotulos,
)

_ABAS = {"4.1": "mensal", "4.2": "acum_12m", "4.3": "emissoes_12m"}

_ESFERAS = {"DPF", "DPMFi", "DPFe"}

# Subgrupos da DPFe, no mesmo papel que 'Tesouro Nacional' tem na DPMFi.
_ENTIDADES = {"Dívida Mobiliária", "Dívida Contratual"}

# As abas terminam com duas formas de nota: numerada ('1  Titulos de
# renegociacao...') e prefixada ('Obs: O Tesouro Nacional...').
_PADRAO_NOTA = re.compile(r"^(?:\d+\s|obs)", re.IGNORECASE)


def _hierarquia(bruto):
    """Marca cada linha com nivel, entidade e titulo.

    A chave e linha_origem, nunca o rotulo: 'Demais' aparece duas vezes
    em cada aba -- uma sob a DPMFi e outra sob a Divida Mobiliaria -- e
    indexar por texto faria a segunda sobrescrever a primeira, jogando a
    linha da DPMFi para dentro da DPFe sem erro nenhum.
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

        if rotulo in _ESFERAS:
            nivel, entidade = rotulo, None
            papel[origem] = (nivel, None, None)
        elif rotulo in _ENTIDADES:
            entidade = rotulo
            papel[origem] = (nivel, entidade, None)
        else:
            papel[origem] = (nivel, entidade, rotulo)

    return papel


def _indentacao(texto):
    return len(texto) - len(texto.lstrip())


def _colunas_de_data_4_3(bruto):
    """Mapeia coluna -> data para a aba 4.3, nos seus dois leiautes.

    Devolve (linha_cabecalho, colunas). Ate dez/2020 o mes esta na mesma
    linha da coluna, igual as outras abas. De jan/2021 em diante o mes
    vira uma trinca 'Taxa media' / 'Variacao do Indexador' / 'CME', com o
    rotulo do mes uma linha acima; so a coluna 'CME' interessa, pelo
    mesmo papel que a coluna unica tinha antes.
    """
    linha_cme = None
    for indice in range(len(bruto)):
        linha = bruto.iloc[indice]
        if any(str(v).strip().lower() == "cme" for v in linha if not pd.isna(v)):
            linha_cme = indice
            break

    if linha_cme is None:
        # Leiaute simples do inicio ao fim -- caso da amostra, que nao
        # alcanca jan/2021: mesmo detector de cabecalho das outras abas.
        for indice in range(len(bruto)):
            linha = bruto.iloc[indice]
            reconhecidos = sum(1 for v in linha if mes_para_data(v) is not None)
            if reconhecidos >= 3:
                colunas = {
                    c: mes_para_data(v) for c, v in linha.items()
                    if mes_para_data(v) is not None
                }
                return indice, colunas
        raise LookupError("nenhuma linha de cabecalho com rotulos de mes na aba 4.3")

    linha_meses_simples = bruto.iloc[linha_cme]
    linha_super = bruto.iloc[linha_cme - 1]
    colunas = {}
    for coluna in bruto.columns:
        data = mes_para_data(linha_meses_simples[coluna])
        if data is not None:
            colunas[coluna] = data
        elif str(linha_meses_simples[coluna]).strip().lower() == "cme":
            data = mes_para_data(linha_super[coluna - 2])
            if data is not None:
                colunas[coluna] = data
    return linha_cme, colunas


def _ler_4_3(xl):
    """Le a aba 4.3 (emissoes) com o leiaute proprio dela -- ver o
    comentario do modulo e _colunas_de_data_4_3.
    """
    bruto = aba(xl, "4.3")
    linha_cabecalho, colunas = _colunas_de_data_4_3(bruto)

    registros = []
    for indice in range(linha_cabecalho + 1, len(bruto)):
        rotulo_bruto = bruto.iloc[indice, 0]
        if pd.isna(rotulo_bruto) or not str(rotulo_bruto).strip():
            continue
        rotulo_bruto = str(rotulo_bruto)
        rotulo = rotulo_bruto.strip()
        nivel = _indentacao(rotulo_bruto.replace("\xa0", " "))
        for coluna, data in colunas.items():
            valor = para_milhoes(limpar_nulo(bruto.iloc[indice, coluna]), "milhoes")
            registros.append((data, indice, rotulo, nivel, valor))

    return pd.DataFrame(
        registros,
        columns=["data", "linha_origem", "rotulo", "nivel_indentacao", "valor_milhoes"],
    )


def _ler_aba(xl, nome_da_aba):
    if nome_da_aba == "4.3":
        return _ler_4_3(xl)
    return ler_padrao_a(xl, nome_da_aba, "milhoes")


def _por_aba(xl, nome_da_aba, medida):
    bruto = _ler_aba(xl, nome_da_aba)
    papel = _hierarquia(bruto)

    df = aplicar_papel(bruto, papel, ["nivel", "entidade", "titulo"])
    # Rede estrutural contra nota de rodape, alem do _PADRAO_NOTA textual:
    # uma folha sem valor em data nenhuma nao e folha. Ver
    # descartar_folhas_sem_dado.
    df = descartar_folhas_sem_dado(df, df["titulo"].notna())
    df["medida"] = medida
    return df.rename(columns={"valor_milhoes": "custo_aa_pct"})


def parse(xl):
    partes = [_por_aba(xl, nome, medida) for nome, medida in _ABAS.items()]
    df = pd.concat(partes, ignore_index=True)
    return df[
        ["data", "medida", "nivel", "entidade", "titulo", "custo_aa_pct"]
    ].sort_values(
        ["data", "medida", "nivel", "entidade", "titulo"]
    ).reset_index(drop=True)


def gravar(xl):
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df = parse(xl)
    saida = config.PROCESSED_DIR / "custo_medio.csv"
    df.to_csv(saida, index=False, encoding="utf-8")
    print(f"gravado: {saida} ({len(df)} linhas)")
