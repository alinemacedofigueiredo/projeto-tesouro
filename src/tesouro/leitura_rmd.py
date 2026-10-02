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


# OS MESES COMO O TESOURO ESCREVE no nome do anexo: "Anexo RMD_Julho_26.xlsx".
# Sem acento na chave porque a comparacao normaliza -- e porque este arquivo e
# ASCII puro, regra do projeto.
_MESES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5,
          "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10,
          "novembro": 11, "dezembro": 12}


def _sem_acento(texto):
    import unicodedata

    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn")


def mes_do_nome(nome):
    """(ano, mes) lidos do NOME do arquivo, ou None se nao der para ler.

    Aceita o ano com dois ou quatro digitos, que e como o Tesouro alterna:
    "Anexo RMD_Julho_26.xlsx" e "..._2026.xlsx" tem de dar o mesmo.
    """
    import re

    limpo = _sem_acento(nome).lower()
    mes = next((n for m, n in _MESES.items() if m in limpo), None)
    if mes is None:
        return None
    anos = re.findall(r"(?<!\d)(\d{4}|\d{2})(?!\d)", limpo)
    if not anos:
        return None
    ano = int(anos[-1])
    return (ano if ano > 100 else 2000 + ano), mes


def caminho_do_rmd(diretorio=None):
    """Devolve o anexo do RMD mais recente em data/raw/rmd/.

    MAIS RECENTE PELO MES DO NOME, e nao pela data de modificacao do arquivo.
    Decisao dela em 09/09/2026.

    O criterio antigo era `max(..., key=st_mtime)`: o carimbo que o sistema
    poe quando o arquivo foi gravado pela ultima vez -- que NAO E o mes do RMD.
    Bastava o anexo de junho ser reescrito (abrir e salvar sem querer, um
    backup restaurar, o antivirus mexer) para o carimbo dele passar na frente e
    O PROJETO INTEIRO voltar a junho. Sem excecao e sem aviso, publicando o mes
    errado com o cabecalho dizendo o certo -- porque o cabecalho tambem sai do
    arquivo lido.

    Dentro do OneDrive isso era rotina, e a folga medida em 26/08/2026 entre os
    dois carimbos era de doze dias. Fora dele virou acidente; o criterio e que
    continuava sendo o carimbo. Os testes ja escolhiam pelo nome
    (tests/anexo.py); esta e a producao alcancando o que eles ja faziam.

    FALHA EM VOZ ALTA quando nenhum nome se deixa ler: silencio aqui seria o
    pior caso, porque o projeto leria um arquivo qualquer e publicaria como se
    fosse o mes corrente.
    """
    diretorio = Path(diretorio) if diretorio else config.RMD_DIR
    candidatos = sorted(diretorio.glob("*.xlsx"))
    if not candidatos:
        raise FileNotFoundError(
            f"nenhum .xlsx encontrado em {diretorio}; baixe com "
            f"'python -m tesouro.fetch_rmd <ano> <mes>' ou coloque o "
            f"arquivo na pasta manualmente"
        )
    datados = [(mes_do_nome(p.name), p) for p in candidatos]
    datados = [(d, p) for d, p in datados if d is not None]
    if not datados:
        raise LookupError(
            f"nenhum anexo em {diretorio} tem mes reconhecivel no nome. "
            f"Esperava algo como 'Anexo RMD_Julho_26.xlsx'; achei "
            f"{[p.name for p in candidatos]}"
        )
    return max(datados, key=lambda par: par[0])[1]


# QUANTOS MESES DE ATRASO VALEM UM AVISO.
#
# MEDIDO, e e a unica medicao que temos: o anexo de base 31/07/2026 entrou em
# disco em 26/08/2026. Ou seja, o anexo de base M sai ate o fim do mes M+1.
#
# Dois, e nao um, de proposito. Em 05/09 com julho carregado o de agosto pode
# nao ter saido ainda, e um aviso que aparece quando nao precisa deixa de ser
# lido quando precisa. A regra so fala quando o prazo INTEIRO do anexo faltante
# ja passou -- entao ela nunca cre lobo, e em troca pode demorar um mes.
MESES_ATE_AVISAR = 2


def mes_base_carregado(diretorio=None):
    """(ano, mes) do RMD que o projeto esta usando, ou None.

    Sai do NOME do arquivo, pela mesma funcao que escolhe qual usar -- se as
    duas discordassem, o aviso falaria de um anexo e a pagina de outro.
    """
    try:
        caminho = caminho_do_rmd(diretorio)
    except Exception:                                    # noqa: BLE001
        return None
    return mes_do_nome(caminho.name)


def _nome_do_mes(ano, mes):
    nomes = {n: m for m, n in _MESES.items()}
    return "%s/%d" % (nomes[mes], ano)


def aviso_de_atraso(base=None, hoje=None, diretorio=None):
    """A frase que diz que existe RMD mais novo que o carregado, ou None.

    POR QUE ISTO EXISTE: o projeto usa o RMD mais recente que ENCONTRA em disco,
    e fica calado sobre o que nao esta la. Em 02/10/2026 ela descobriu, por
    acaso, que estava com o de julho -- e a pagina do PAF projetava o fechamento
    do ano a partir de uma base de 31/07, sem nada avisar.

    Nao vai a rede. O site do RMD trava no certificado do SERPRO, e um aviso que
    depende de rede que nao funciona nao avisa nada. A conta e de calendario.
    """
    import pandas as pd

    if base is None:
        base = mes_base_carregado(diretorio)
    if base is None:
        return None
    hoje = pd.Timestamp(hoje).normalize() if hoje is not None \
        else pd.Timestamp.today().normalize()

    ano, mes = base
    # Diferenca em MESES de calendario, que atravessa a virada de ano sem
    # gambiarra -- subtracao de mes solta daria -11 de dezembro para janeiro.
    atraso = (hoje.year - ano) * 12 + (hoje.month - mes)
    if atraso <= MESES_ATE_AVISAR:
        return None

    faltando = []
    for passo in range(1, atraso - MESES_ATE_AVISAR + 1):
        d = pd.Timestamp(year=ano, month=mes, day=1) + pd.DateOffset(months=passo)
        faltando.append(_nome_do_mes(d.year, d.month))

    quais = faltando[0] if len(faltando) == 1 else \
        "%s e %s" % (", ".join(faltando[:-1]), faltando[-1])
    return (
        "ADVERTENCIA: o projeto esta usando o RMD de %s, e o de %s ja deveria\n"
        "ter saido. As paginas projetam o fechamento do ano a partir dessa base.\n"
        "\n"
        "Para atualizar: salve o anexo pelo NAVEGADOR em data/raw/rmd/ e rode o\n"
        "modo rmd dando Enter em branco nas duas perguntas."
        % (_nome_do_mes(ano, mes), quais)
    )


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
