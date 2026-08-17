"""Conversoes de entrada: data, unidade, nulo e escala percentual.

O anexo do RMD e o arquivo de leiloes usam convencoes diferentes entre si
e ate entre abas do mesmo arquivo. Todas as normalizacoes ficam aqui para
que cada parser nao reinvente (e erre) a sua.
"""
import calendar
import datetime
import math
import re

MESES = {
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
}

_PADRAO_MES = re.compile(r"^([a-z]{3})/(\d{2})$")

_MARCADORES_NULOS = {"", "-", "n/d", "nd", "n.d.", "..."}


def _fim_do_mes(ano: int, mes: int) -> datetime.date:
    return datetime.date(ano, mes, calendar.monthrange(ano, mes)[1])


def mes_para_data(texto):
    """Converte 'Jan/10' no ultimo dia daquele mes.

    Devolve None para qualquer coisa que nao seja um rotulo de mes --
    inclusive os totais anuais ('2007') que a aba 1.1 intercala entre os
    meses e que nao podem entrar na serie.
    """
    if texto is None:
        return None
    limpo = str(texto).strip().lower()
    achado = _PADRAO_MES.match(limpo)
    if not achado:
        return None
    abreviacao, ano_curto = achado.groups()
    if abreviacao not in MESES:
        return None
    ano = int(ano_curto)
    ano += 1900 if ano >= 90 else 2000
    return _fim_do_mes(ano, MESES[abreviacao])


def normalizar_data(valor):
    """Leva uma data ja reconhecida pelo pandas para o fim do mes."""
    if valor is None:
        return None
    # pd.NaT (sentinela do pandas para data ausente numa coluna datetime64)
    # e a unica coisa, alem de NaN, para a qual "valor != valor" e
    # verdadeiro -- e o jeito de reconhece-lo sem importar pandas aqui.
    # Essa checagem tem que vir antes do isinstance abaixo: pd.NaT passa em
    # isinstance(valor, datetime.datetime) por compatibilidade do pandas,
    # entao cairia no proximo bloco, valor.date() devolveria outro NaT, e
    # calendar.monthrange(ano, nan) quebraria mais adiante com
    # IllegalMonthError em vez de devolver None. Nao remova esta linha.
    if valor != valor:
        return None
    if isinstance(valor, datetime.datetime):
        valor = valor.date()
    if not isinstance(valor, datetime.date):
        return None
    return _fim_do_mes(valor.year, valor.month)


def limpar_nulo(valor):
    """Devolve float, ou None quando o valor representa ausencia.

    Zero e negativo sao valores legitimos e passam intactos: custo negativo
    aparece de verdade na aba 4.1 (NTN-D em 2005).
    """
    if valor is None:
        return None
    if isinstance(valor, str):
        limpo = valor.strip()
        if limpo.lower() in _MARCADORES_NULOS:
            return None
        # O ponto so e separador de milhar quando ha uma virgula decimal
        # na string ('1.234,56'). Sem essa condicao, '3.75' -- que e um
        # decimal com ponto, e o que uma celula de valor com marcador de
        # nota de rodape produz depois de re-tipada como texto -- viraria
        # 375.0, um erro de cem vezes que nao levanta excecao nenhuma.
        if "," in limpo:
            limpo = limpo.replace(".", "").replace(",", ".")
        try:
            return float(limpo)
        except ValueError:
            return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    if math.isnan(numero):
        return None
    return numero


def para_milhoes(valor, unidade_origem):
    """Converte para R$ milhoes, a unica unidade monetaria do projeto."""
    fatores = {"milhoes": 1.0, "bilhoes": 1_000.0, "reais": 1e-6}
    if unidade_origem not in fatores:
        raise ValueError(
            f"unidade desconhecida: {unidade_origem!r}; "
            f"esperado um de {sorted(fatores)}"
        )
    if valor is None:
        return None
    return valor * fatores[unidade_origem]


def fracao_para_percentual(valor):
    """0.07828 vira 7.828. O arquivo de leiloes grava taxa como fracao."""
    if valor is None:
        return None
    return valor * 100.0


def data_da_celula(valor):
    """Le a data de uma celula, nas varias formas que o anexo usa.

    O pandas entrega quase todas as datas como datetime, mas algumas
    celulas trazem o mes como texto ('Jan/10'), e outras trazem texto com
    marcador de nota de rodape ('mar/18*') -- os meses que o Tesouro
    retificou. As tres formas significam a mesma coisa, e quem le a
    planilha nao deveria precisar saber disso.
    """
    data = normalizar_data(valor)
    if data is not None:
        return data
    if not isinstance(valor, str):
        return None
    return mes_para_data(valor.strip().rstrip("*").strip())
