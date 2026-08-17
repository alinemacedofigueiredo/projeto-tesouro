"""Abas 5.7 (metas do PAF) e 6.1 (reserva de liquidez).

A 5.7 e a aba mais irregular do anexo: blocos empilhados verticalmente,
cada um cobrindo um intervalo de anos com layout proprio. A estrutura de
cada bloco e sempre a mesma -- uma linha 'Indicadores' com, alternando,
o ano realizado e o rotulo 'PAF <ano>' (as vezes uma versao revisada), e
logo abaixo 'Minimo'/'Maximo' sob cada bloco de PAF.

Os nomes dos indicadores mudam ao longo do tempo ('Selic' vira 'Taxa
Flutuante' em 2011); nao sao normalizados aqui, para nao apagar a
diferenca que existe na fonte. A analise decide como trata-los.

A aba nao traz a data de publicacao das revisoes: a vigencia de cada
banda vira de um arquivo de referencia produzido em trabalho separado.
"""
import re

import pandas as pd

from .. import config
from ..conversoes import data_da_celula, limpar_nulo, para_milhoes
from ..leitura_rmd import aba

# O rotulo revisado nao e escrito do mesmo jeito em todos os blocos: a
# maioria usa 'PAF <ano> revisado' (minusculo, sem parenteses), mas o
# ultimo bloco da aba real usa 'PAF <ano> (Revisado)' -- com parenteses e
# maiuscula. As duas formas precisam casar, ou a revisao mais recente
# desaparece em silencio.
_PADRAO_PAF = re.compile(r"^PAF\s+(\d{4})\s*\(?(revisado)?\)?$", re.IGNORECASE)

# O ano realizado, na linha 'Indicadores', nem sempre chega como inteiro:
# quando a coluna mistura texto ('Indicadores') e numero, o pandas guarda
# os numeros dessa coluna como float, entao o primeiro ano de cada bloco
# aparece como '2003.0', nao '2003'. Sem aceitar o '.0' final, esse ano
# nunca e reconhecido como coluna de realizado, e o realizado do primeiro
# ano de cada um dos quatro blocos fica faltando.
_PADRAO_ANO = re.compile(r"^\d{4}(\.0+)?$")


def _blocos(bruto):
    """Devolve os indices das linhas que iniciam cada bloco da aba 5.7."""
    inicios = []
    for indice in range(len(bruto)):
        primeira = bruto.iloc[indice, 0]
        if not pd.isna(primeira) and str(primeira).strip() == "Indicadores":
            inicios.append(indice)
    if not inicios:
        raise LookupError("aba 5.7: nenhuma linha 'Indicadores' encontrada")
    return inicios


def _colunas_do_bloco(bruto, linha_indicadores):
    """Mapeia cada bloco 'PAF <ano>' para suas colunas de minimo e maximo.

    Devolve lista de (ano, versao, coluna_realizado, coluna_min, coluna_max).
    coluna_min e a propria coluna onde 'PAF <ano>' aparece -- 'Minimo' e
    'Maximo' ficam na linha seguinte, nas colunas coluna_min e
    coluna_min + 1.
    """
    achados = []
    ultimo_realizado = None
    for coluna in range(1, len(bruto.columns)):
        celula = bruto.iloc[linha_indicadores, coluna]
        if pd.isna(celula):
            continue
        texto = str(celula).strip()

        achado = _PADRAO_PAF.match(texto)
        if achado:
            ano = int(achado.group(1))
            versao = "revisado" if achado.group(2) else "original"
            achados.append((ano, versao, ultimo_realizado, coluna, coluna + 1))
            continue

        if _PADRAO_ANO.match(texto):
            ultimo_realizado = coluna

    return achados


def parse_paf(xl):
    """Aba 5.7 -- bandas de minimo/maximo do PAF, por ano e indicador.

    'versao' distingue a meta original da revisao publicada no mesmo ano
    (nem todo ano tem revisao). O nome do indicador nao e normalizado --
    ver a nota do modulo.
    """
    bruto = aba(xl, "5.7")

    registros = []
    inicios = _blocos(bruto)
    for ordem, linha_indicadores in enumerate(inicios):
        fim = inicios[ordem + 1] if ordem + 1 < len(inicios) else len(bruto)
        blocos = _colunas_do_bloco(bruto, linha_indicadores)

        for indice in range(linha_indicadores + 2, fim):
            rotulo = bruto.iloc[indice, 0]
            if pd.isna(rotulo) or not str(rotulo).strip():
                continue
            indicador = str(rotulo).strip()
            if indicador in {"Indicadores", "Mínimo", "Máximo"}:
                continue

            for ano, versao, col_real, col_min, col_max in blocos:
                minimo = limpar_nulo(bruto.iloc[indice, col_min])
                maximo = (
                    limpar_nulo(bruto.iloc[indice, col_max])
                    if col_max < len(bruto.columns) else None
                )
                realizado = (
                    limpar_nulo(bruto.iloc[indice, col_real])
                    if col_real is not None else None
                )
                if minimo is None and maximo is None and realizado is None:
                    # Descarta linhas-cabecalho de secao (ex.:
                    # 'Participacao no Estoque da DPF (%)'), que tem so a
                    # primeira celula preenchida e nenhum valor em nenhum
                    # bloco -- nao um indicador de verdade.
                    continue
                registros.append(
                    (ano, versao, indicador, minimo, maximo, realizado)
                )

    return pd.DataFrame(
        registros,
        columns=["ano", "versao", "indicador", "minimo", "maximo", "realizado"],
    ).sort_values(["ano", "versao", "indicador"]).reset_index(drop=True)


def parse_reserva(xl):
    """Aba 6.1 -- reserva de liquidez.

    As duas primeiras colunas sao R$ bilhoes; a terceira e um indice em
    meses e nao pode ser convertida.
    """
    bruto = aba(xl, "6.1")

    registros = []
    for indice in range(len(bruto)):
        # data_da_celula, e nao normalizar_data: se um mes futuro vier
        # escrito como texto (ja acontece nas abas 2.7 e 2.8), ele entra
        # em vez de desaparecer da serie em silencio.
        data = data_da_celula(bruto.iloc[indice, 0])
        if data is None:
            continue
        reserva = para_milhoes(limpar_nulo(bruto.iloc[indice, 1]), "bilhoes")
        prudencial = para_milhoes(limpar_nulo(bruto.iloc[indice, 2]), "bilhoes")
        indice_meses = limpar_nulo(bruto.iloc[indice, 3])
        registros.append((data, reserva, prudencial, indice_meses))

    return pd.DataFrame(
        registros,
        columns=["data", "reserva_milhoes", "valor_prudencial_milhoes",
                 "indice_liquidez_meses"],
    ).sort_values("data").reset_index(drop=True)


def gravar(xl):
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    for nome, df in (
        ("paf_metas", parse_paf(xl)),
        ("reserva_liquidez", parse_reserva(xl)),
    ):
        saida = config.PROCESSED_DIR / f"{nome}.csv"
        df.to_csv(saida, index=False, encoding="utf-8")
        print(f"gravado: {saida} ({len(df)} linhas)")
