"""Leitores genericos para as abas do anexo do RMD.

As dezoito abas usadas caem em dois formatos:

  Padrao A -- meses nas colunas, rotulos nas linhas (1.1, 1.2, 2.1, 3.7,
  3.8, 4.1, 4.2, 4.3). A hierarquia sai de `linha_origem` mais conjuntos
  de rotulo conhecidos, resolvidos por uma maquina de estados em cada
  parser -- NAO da indentacao do rotulo, que nao e hierarquica: na 3.7
  'Tesouro Nacional' tem recuo 0 e a 'DPMFi' que o contem tem 3; na 4.1
  'Clube de Paris' tem 8 e as irmas dele 5; na 1.2 tudo tem 0.

  Padrao B -- meses nas linhas, categorias nas colunas (2.4, 2.7, 2.8,
  3.1, 3.3, 3.9, 6.1). Cada categoria costuma ocupar duas colunas, valor
  e percentual; so o valor e lido, porque percentual e derivado.

As abas 2.2, 3.4 e 5.7 nao seguem nenhum dos dois e tem parser proprio.
"""
from pathlib import Path

import pandas as pd

from . import config
from .conversoes import data_da_celula, limpar_nulo, mes_para_data, para_milhoes


def caminho_do_rmd(diretorio=None):
    """Devolve o .xlsx de RMD mais recente disponivel em data/raw/rmd/."""
    diretorio = Path(diretorio) if diretorio else config.RMD_DIR
    candidatos = sorted(diretorio.glob("*.xlsx"))
    if not candidatos:
        raise FileNotFoundError(
            f"nenhum .xlsx encontrado em {diretorio}; baixe com "
            f"'python -m tesouro.fetch_rmd <ano> <mes>' ou coloque o "
            f"arquivo na pasta manualmente"
        )
    return max(candidatos, key=lambda p: p.stat().st_mtime)


def abrir(caminho=None):
    caminho = Path(caminho) if caminho else caminho_do_rmd()
    xl = pd.ExcelFile(caminho)
    # pd.ExcelFile nao expoe o caminho de origem publicamente (so o
    # atributo privado _io); alguns parsers precisam reabrir o arquivo
    # com openpyxl para ler metadado que o pandas descarta (formatacao de
    # celula, no caso da aba 5.7 -- ver paf_reserva.py). Gravar aqui evita
    # que cada parser dependa do atributo privado do pandas.
    xl.caminho = caminho
    return xl


def aba(xl, nome):
    """Le uma aba pelo nome, falhando de forma legivel se ela nao existir.

    O Tesouro descontinua abas de tempos em tempos (a 3.5 e a 5.6 sairam
    em junho de 2025) e continua listando-as no indice do anexo. Quando
    isso acontecer com uma aba que usamos, quem for investigar precisa
    ler qual sumiu -- nao um KeyError cru do pandas.

    Todos os parsers passam por aqui, inclusive os das abas especiais.
    """
    if nome not in xl.sheet_names:
        raise LookupError(
            f"aba {nome!r} nao existe neste anexo do RMD. "
            f"Ela pode ter sido descontinuada -- confira o indice do "
            f"arquivo. Abas presentes: {', '.join(xl.sheet_names)}"
        )
    return xl.parse(sheet_name=nome, header=None)


def _linha_do_cabecalho_de_meses(bruto):
    """Acha a linha cujo conteudo sao rotulos de mes ('Nov/06').

    A posicao varia entre abas -- a 4.3 tem um nivel de cabecalho a mais
    que as demais -- entao e detectada, nao fixada.
    """
    for indice, linha in bruto.iterrows():
        reconhecidos = sum(1 for v in linha if mes_para_data(v) is not None)
        if reconhecidos >= 3:
            return indice
    raise LookupError("nenhuma linha de cabecalho com rotulos de mes")


def ordem_dos_rotulos(bruto):
    """Os rotulos de uma aba padrao A, um por linha, na ordem da planilha.

    Devolve um DataFrame com `linha_origem` e `rotulo`. E a entrada das
    maquinas de estado que resolvem hierarquia nos parsers: elas percorrem
    os rotulos na ordem em que aparecem e vao carregando o nivel corrente.

    A chave e linha_origem, nunca o texto do rotulo. Rotulos se repetem
    entre secoes ('Demais' aparece quatro vezes na 1.2, tres na 2.1) e
    indexar por texto faria a ultima ocorrencia sobrescrever as anteriores,
    espalhando o papel errado por todas as linhas com aquele texto --
    plausivel e errado, sem levantar excecao.
    """
    return (
        bruto.drop_duplicates(subset=["linha_origem"])
        .sort_values("linha_origem")[["linha_origem", "rotulo"]]
    )


def aplicar_papel(bruto, papel, colunas):
    """Anexa ao DataFrame as colunas de papel resolvidas por linha_origem.

    `papel` mapeia linha_origem -> tupla com um valor por nome de
    `colunas`, na mesma ordem. As linhas cuja origem nao esta em `papel`
    saem do resultado -- e assim que cada parser descarta o que a sua
    maquina de estados rejeitou (nota de rodape, total derivado).
    """
    resultado = bruto[bruto["linha_origem"].isin(papel)].copy()
    for posicao, nome in enumerate(colunas):
        resultado[nome] = [papel[o][posicao] for o in resultado["linha_origem"]]
    return resultado


def descartar_folhas_sem_dado(df, eh_folha, coluna_valor="valor_milhoes"):
    """Remove as linhas de folha que nao tem valor em nenhuma data.

    Esta e a defesa estrutural contra nota de rodape, e vale para as
    quatro abas padrao A que resolvem hierarquia (1.1/1.2, 2.1, 3.7/3.8,
    4.1/4.2/4.3). O fim dessas abas traz notas em linhas soltas: chamadas
    de nota numeradas ('1 Titulos de renegociacao...'), 'OBS:' na 1.1,
    'Obs:'/'Obs 2:' na 1.2, 'Obs.1:' na 2.1. Cada aba redige do seu jeito
    e a caixa varia, entao filtrar por prefixo de texto e um palpite: na
    1.2 nao existe o `break` de 'EMISSAO LIQUIDA' para conter a nota, e o
    dia em que o Tesouro escrever 'OBS:' ali duas frases longas viram
    valores de indexador.

    O criterio aqui nao depende da redacao: uma folha e uma folha porque
    tem valor em alguma data. Nota de rodape nao tem valor em coluna de
    mes nenhuma. Os filtros textuais de cada parser continuam sendo a
    primeira linha de defesa; este e a rede.

    So as linhas marcadas como folha por `eh_folha` (mascara booleana
    alinhada a `df`) entram na checagem. Um cabecalho legitimo ('Tesouro
    Nacional', 'DPMFi') tambem nao tem valor proprio e precisa ficar.
    """
    folhas = df[eh_folha]
    if folhas.empty:
        return df
    tem_dado = (
        folhas.groupby("linha_origem")[coluna_valor]
        .apply(lambda s: s.notna().any())
    )
    origens_vazias = set(tem_dado[~tem_dado].index)
    if not origens_vazias:
        return df
    return df[~df["linha_origem"].isin(origens_vazias)]


def _colunas_de_data(bruto, linha_cabecalho):
    """{coluna: data} para as colunas cujo cabecalho e um mes de verdade.

    Descarta os totais anuais que a aba 1.1 intercala entre os meses.
    """
    datas = {}
    for coluna in bruto.columns:
        data = mes_para_data(bruto.iloc[linha_cabecalho, coluna])
        if data is not None:
            datas[coluna] = data
    return datas


def ler_padrao_a(xl, nome_da_aba, unidade, colunas=None):
    """Le uma aba com meses nas colunas e rotulos nas linhas.

    Devolve tambem `linha_origem` -- o indice da linha na planilha lida.
    O rotulo sozinho nao e uma chave confiavel: abas como a 1.1 repetem o
    mesmo texto (ex.: "Trocas Oferta Publica", "Tesouro Direto") sob
    secoes diferentes (emissao e resgate). linha_origem e a unica chave
    estavel para quem for reconstruir a hierarquia ou separar secoes
    repetidas -- a indentacao do rotulo nao serve, porque nao e
    hierarquica (ver a nota do modulo).

    `colunas` aceita um mapa coluna->data pre-calculado, na forma
    `(linha_cabecalho, {coluna: data})`. Serve a aba 4.3, cujo cabecalho
    ganha um segundo nivel a partir de jan/2021 e nao e reconhecido pelo
    detector generico -- ver parse_rmd/custo.py. O padrao None detecta o
    cabecalho como nas demais abas.
    """
    bruto = aba(xl, nome_da_aba)
    if colunas is None:
        linha_cabecalho = _linha_do_cabecalho_de_meses(bruto)
        datas = _colunas_de_data(bruto, linha_cabecalho)
    else:
        linha_cabecalho, datas = colunas

    registros = []
    for indice in range(linha_cabecalho + 1, len(bruto)):
        rotulo_bruto = bruto.iloc[indice, 0]
        if pd.isna(rotulo_bruto) or not str(rotulo_bruto).strip():
            continue
        rotulo = str(rotulo_bruto).strip()
        for coluna, data in datas.items():
            valor = para_milhoes(limpar_nulo(bruto.iloc[indice, coluna]), unidade)
            registros.append((data, indice, rotulo, valor))

    return pd.DataFrame(
        registros,
        columns=["data", "linha_origem", "rotulo", "valor_milhoes"],
    )


def ler_padrao_b(xl, nome_da_aba, linha_cabecalho, unidade, colunas_por_categoria=2,
                  linha_final=None):
    """Le uma aba com meses nas linhas e categorias nas colunas.

    Assume que a coluna 0 traz a data e que cada categoria ocupa
    `colunas_por_categoria` colunas a partir da coluna 1, sendo a primeira
    delas o valor. As demais (tipicamente o percentual) sao ignoradas, por
    serem derivadas.

    `linha_final` limita a leitura a [linha_cabecalho, linha_final) -- usado
    pela aba 3.1, que empilha tres blocos (DPF, DPMFi, DPFe) na mesma aba;
    sem o limite, o bloco seguinte vazaria para dentro do anterior. O
    padrao None preserva o comportamento de ler ate o fim da aba.
    """
    bruto = aba(xl, nome_da_aba)
    fim = len(bruto) if linha_final is None else linha_final

    categorias = {}
    coluna = 1
    while coluna < len(bruto.columns):
        nome = bruto.iloc[linha_cabecalho, coluna]
        if not pd.isna(nome) and str(nome).strip():
            categorias[coluna] = str(nome).strip()
        coluna += colunas_por_categoria

    registros = []
    for indice in range(linha_cabecalho + 1, fim):
        data = data_da_celula(bruto.iloc[indice, 0])
        if data is None:
            continue
        for coluna, categoria in categorias.items():
            valor = para_milhoes(limpar_nulo(bruto.iloc[indice, coluna]), unidade)
            registros.append((data, categoria, valor))

    return pd.DataFrame(registros, columns=["data", "categoria", "valor_milhoes"])
