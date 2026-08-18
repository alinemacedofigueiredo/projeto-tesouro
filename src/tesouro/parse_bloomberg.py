"""Converte os brutos da Bloomberg nas tabelas canonicas.

A coleta e incremental por desenho: cada puxada grava um arquivo novo em
data/raw/bloomberg/ e nada e sobrescrito -- data/raw/ e imutavel por
invariante do projeto. Por isso o parser le TODOS os arquivos de cada
tipo, concatena, e em caso de repeticao fica com a ultima ocorrencia --
que e a puxada mais recente. Isso so funciona se o NOME do arquivo
ordenar cronologicamente em ordem alfabetica (formato ISO, AAAA-MM); um
nome fora desse padrao faz o "manter a ultima ocorrencia" ficar com o
arquivo errado, sem erro nenhum -- por isso o nome de cada arquivo lido e
conferido contra um padrao antes de qualquer leitura.

As duas fontes trazem a data em convencoes diferentes: a de taxas em
geral ja vem no ultimo dia util do mes (e o que a periodicidade mensal da
Bloomberg devolve via HistoricalDataRequest), mas nao sempre -- o bruto
atual tem 272 linhas em 6 datas que sao ultimo dia CORRIDO, nao util
(29/03/2013, 28/02/2017, 30/03/2018, 31/05/2018, 28/02/2022 e 29/03/2024
-- todas vesperas de feriado movel, Sexta-feira Santa ou Carnaval, que a
Bloomberg parece contar diferente da Anbima). A de VNA vem no ultimo dia
corrido, porque foi assim que o override de SETTLE_DT foi pedido.
Verificado durante o design que o VNA e identico nos dois dias, porque
nao acumula em dia nao util -- e essa premissa e conferida em tempo de
leitura, nao so assumida (ver parse_vna). As duas fontes sao normalizadas
para o ultimo dia util, que e a chave de juncao do projeto -- ver
docs/convencoes-dv.md: casar por data crua descarta cerca de um terco do
painel em silencio, porque a Bloomberg pode devolver 29/05 onde o RMD
traz 31/05.

Atencao para quem for juntar com o estoque: taxa_por_papel.csv e vna.csv
(este modulo) gravam a coluna 'data' no ultimo dia UTIL do mes.
estoque_titulos_vencimento.csv (parse_rmd/estoque_vencimento.py) grava a
mesma coluna 'data' no ultimo dia CORRIDO. Um merge(on="data") ingenuo
entre os dois perde cerca de 33,7% do painel -- normalize o lado do
estoque com calendario.ultimo_dia_util_do_mes antes de juntar.

Este modulo nunca toca a rede. Ele so le o que a coleta ja deixou em
data/raw/bloomberg/ e nunca escreve em data/raw/ -- so em
data/processed/.
"""
import re
from pathlib import Path

import pandas as pd

from . import calendario, config

# O nome do arquivo precisa ordenar cronologicamente em ordem alfabetica,
# porque _ler_todos concatena na ordem do glob e resolve repeticao com
# "fica com a ultima ocorrencia". So o formato ISO (AAAA-MM) garante isso:
# um nome como 'bbg_taxas_ANDE_01-07-2026.csv' (dia antes do ano) ordena
# antes de 'bbg_taxas_ANDE_2010-01_2026-06.csv', e uma puxada nova acaba
# descartada em favor de uma antiga, em silencio.
_PADRAO_NOME_TAXAS = re.compile(r"^bbg_taxas_[A-Za-z0-9]+_\d{4}-\d{2}_\d{4}-\d{2}\.csv$")
_PADRAO_NOME_VNA = re.compile(r"^bbg_vna_\d{4}-\d{2}_\d{4}-\d{2}\.csv$")

_COLUNAS_TAXAS = ["isin", "titulo", "vencimento", "data", "yld_ytm_mid"]
_COLUNAS_VNA = ["data", "indice", "campo", "fator", "vna", "n_papeis", "divergencia"]

# Cada indice vem de um campo Bloomberg fixo -- ver docs/convencoes-dv.md.
# Uma troca de rotulo entregaria o VNA de um indice como se fosse do
# outro, e o preco de toda NTN-B (ou toda LFT) do mes erraria por inteiro.
_CAMPO_POR_INDICE = {"IPCA": "IDX_RATIO", "SELIC": "ACCUMULATED_SELIC"}

# Tolerancia sobre a coluna 'divergencia' do bruto de VNA: a diferenca
# entre o VNA reportado e o VNA implicito nos papeis individuais do
# indice, em reais. Hoje e 0,0 em todas as 396 linhas; qualquer valor
# apreciavel indica que o VNA nao bateu entre os papeis do mesmo indice
# na coleta. Nota: em 16 das 198 datas de IPCA ha um so papel
# (n_papeis == 1), e a divergencia fica trivialmente zero ali -- isso nao
# e evidencia de nada, so a ausencia de um segundo papel para comparar.
_TOLERANCIA_DIVERGENCIA = 0.5

# Faixa de taxa plausivel por titulo, em percentual. Frouxa de proposito:
# a ponta curtissima do painel tem extremos que sao mercado de verdade,
# nao erro -- NTN-B a -4,21% em mai/2021 (45 dias para vencer, Selic a
# 2%) e a 25,01% em jul/2022 (17 dias para vencer). A LFT e a excecao:
# ela carrega agio/desagio, nao taxa, e fica sempre perto de zero.
_LIMITES_TAXA_PCT = {
    "LFT": (-5.0, 5.0),
    "LTN": (-10.0, 60.0),
    "NTN-F": (-10.0, 60.0),
    "NTN-B": (-10.0, 60.0),
}


def _checar_colunas(df, colunas_esperadas, nome_arquivo):
    """Levanta erro se o arquivo nao trouxer todas as colunas esperadas.

    Sem isso, pd.concat entre um arquivo com o layout antigo e outro com
    uma coluna a menos preenche a coluna ausente com NaN em silencio --
    um 'titulo' NaN, por exemplo, nao casa com nenhum mapa de indexador
    na Tarefa 5, e uma NTN-B acabaria precificada como prefixada. Mesmo
    padrao de parse_rmd/paf_reserva.py (aba 6.1).
    """
    faltantes = [c for c in colunas_esperadas if c not in df.columns]
    if faltantes:
        raise LookupError(
            f"{nome_arquivo}: colunas ausentes {faltantes}; esperado "
            f"{colunas_esperadas}, achou {list(df.columns)}. O layout do "
            f"bruto pode ter mudado."
        )


def _ler_todos(padrao_glob, padrao_nome, colunas_esperadas, caminho=None):
    """Le e concatena todos os arquivos que casam com o padrao de nome.

    caminho, se dado, substitui o diretorio padrao (config.BLOOMBERG_DIR)
    -- usado pelos testes para apontar para uma pasta com fixtures.

    Cada arquivo encontrado precisa (1) ter o nome no formato ISO
    esperado -- a ordem de leitura depende disso, ver o comentario de
    _PADRAO_NOME_* -- e (2) trazer todas as colunas esperadas. As duas
    checagens levantam erro em vez de seguir em frente com dado ruim.
    """
    diretorio = Path(caminho) if caminho else config.BLOOMBERG_DIR
    arquivos = sorted(diretorio.glob(padrao_glob))
    if not arquivos:
        raise FileNotFoundError(
            f"nenhum arquivo {padrao_glob!r} em {diretorio}; rode a coleta "
            f"com 'python -m tesouro.fetch_bloomberg' ou coloque a "
            f"exportacao do BDH nessa pasta (veja docs/convencoes-dv.md)"
        )
    for arquivo in arquivos:
        if not padrao_nome.match(arquivo.name):
            raise ValueError(
                f"{arquivo.name}: nome fora do padrao esperado "
                f"({padrao_nome.pattern}). A leitura concatena os arquivos "
                f"na ordem alfabetica do nome e mantem a ultima ocorrencia "
                f"de cada chave repetida -- um nome fora do formato ISO "
                f"(ex.: dia antes do ano) ordena errado e faz o dado novo "
                f"ser descartado em favor do antigo, em silencio."
            )
    print(f"parse_bloomberg: lendo, em ordem: {[a.name for a in arquivos]}")
    quadros = []
    for arquivo in arquivos:
        df = pd.read_csv(arquivo)
        _checar_colunas(df, colunas_esperadas, arquivo.name)
        quadros.append(df)
    return pd.concat(quadros, ignore_index=True)


def _checar_plausibilidade_taxas(df):
    """Levanta erro se alguma taxa estiver fora da faixa plausivel do titulo.

    Guarda frouxa, so para erro grosseiro (unidade errada por um fator
    grande, titulo trocado) -- ver _LIMITES_TAXA_PCT sobre por que a
    faixa e larga.
    """
    for titulo, (minimo, maximo) in _LIMITES_TAXA_PCT.items():
        fatia = df[df["titulo"] == titulo]
        fora = fatia[(fatia["taxa_pct"] < minimo) | (fatia["taxa_pct"] > maximo)]
        if not fora.empty:
            raise ValueError(
                f"{len(fora)} taxa(s) de {titulo} fora da faixa plausivel "
                f"[{minimo}, {maximo}]%: "
                f"{fora[['data', 'isin', 'taxa_pct']].head(5).to_dict('records')}"
            )


def parse_taxas(caminho=None):
    """Taxa indicativa Anbima por papel e fim de mes, em percentual.

    A taxa vem de HistoricalDataRequest (YLD_YTM_MID, fonte ANDE), nao de
    SETTLE_DT -- ver docs/convencoes-dv.md sobre por que o override de
    liquidacao nao serve para taxa historica. Fica em percentual (13.5
    significa 13,5%), a mesma convencao que o resto do projeto usa para
    taxa antes de entrar em decimal no calculo do PU.

    Ha agio/desagio negativo na LFT (ex.: -0.0039): e esperado, nao e
    erro.

    Tres filtros silenciosos de proposito -- cada um reportado por
    print, nunca por excecao, porque representam ausencia legitima de
    dado, nao erro de leitura:
    - taxa ausente (NaN): sem isso, a chave (data, isin) contaria como
      'coberta' na medicao de cobertura do painel sem taxa nenhuma.
    - papel ja vencido na data da cotacao (vencimento <= data): e uma
      cotacao residual sem sentido para precificar, e calendario.du
      inverte a ordem dos argumentos quando vencimento < data, devolvendo
      um numero de dias uteis positivo como se o papel ainda estivesse
      vivo -- silenciosamente errado se chegar ao motor de precificacao.
    """
    cal = calendario.padrao()
    df = _ler_todos("bbg_taxas_*.csv", _PADRAO_NOME_TAXAS, _COLUNAS_TAXAS, caminho)
    df = df.rename(columns={"yld_ytm_mid": "taxa_pct"})
    df["data_bruta"] = pd.to_datetime(df["data"]).dt.date
    df["vencimento"] = pd.to_datetime(df["vencimento"]).dt.date

    # Resolve repeticao da MESMA data de origem (duas puxadas cobrindo o
    # mesmo mes) antes de normalizar -- fica com o arquivo lido por
    # ultimo, que e o mais recente.
    df = df.drop_duplicates(subset=["data_bruta", "isin"], keep="last")

    df["data"] = df["data_bruta"].map(cal.ultimo_dia_util_do_mes)
    df = df.drop(columns=["data_bruta"])

    antes = len(df)
    df = df[df["taxa_pct"].notna()]
    if len(df) < antes:
        print(f"parse_taxas: {antes - len(df)} linha(s) com taxa ausente descartada(s)")

    antes = len(df)
    df = df[df["vencimento"] > df["data"]]
    if len(df) < antes:
        print(f"parse_taxas: {antes - len(df)} linha(s) de papel ja vencido descartada(s)")

    _checar_plausibilidade_taxas(df)

    # Segunda desduplicacao: duas datas de origem diferentes podem cair
    # no mesmo ultimo dia util normalizado (ex.: 29/05 util e 31/05
    # corrido, se algum dia aparecerem os dois). Mantem a ultima
    # ocorrencia pela mesma logica -- aqui nao ha premissa de igualdade
    # documentada como no VNA, entao nao ha erro, so a resolucao padrao.
    df = df.drop_duplicates(subset=["data", "isin"], keep="last")
    return df[["data", "isin", "titulo", "vencimento", "taxa_pct"]].sort_values(
        ["data", "titulo", "isin"]
    ).reset_index(drop=True)


def parse_vna(caminho=None):
    """VNA por indice e fim de mes, em reais.

    O VNA e por indice, nao por papel: verificado que o valor e identico
    entre papeis diferentes na mesma data, em todas as datas do painel --
    ver docs/convencoes-dv.md. Duas checagens defendem essa premissa em
    tempo de leitura, nao so em tempo de design:

    - campo Bloomberg (IDX_RATIO / ACCUMULATED_SELIC) precisa bater com o
      indice (IPCA / SELIC); uma troca de rotulo entregaria o VNA errado
      travestido do indice certo.
    - a coluna 'divergencia' do bruto (diferenca entre o VNA reportado e
      o implicito nos papeis do indice) precisa ficar dentro da
      tolerancia; acima dela, o VNA nao bateu entre os papeis na coleta.

    A normalizacao de data (ultimo dia corrido -> ultimo dia util) e
    conferida contra a mesma premissa: se duas datas de origem diferentes
    (ex.: 29/05 util e 31/05 corrido) colapsarem no mesmo ultimo dia util
    com VNA DIFERENTE, isso quebra o que o docstring afirma -- o VNA nao
    acumula em dia nao util -- e vira erro, nunca resolucao silenciosa
    por 'ultima ocorrencia'. Repeticao da MESMA data de origem (puxadas
    incrementais cobrindo o mesmo mes) continua resolvida por ultima
    ocorrencia, antes dessa checagem.
    """
    cal = calendario.padrao()
    df = _ler_todos("bbg_vna_*.csv", _PADRAO_NOME_VNA, _COLUNAS_VNA, caminho)
    df["data_bruta"] = pd.to_datetime(df["data"]).dt.date

    esperado = df["indice"].map(_CAMPO_POR_INDICE)
    trocado = df["campo"] != esperado
    if trocado.any():
        raise ValueError(
            f"{trocado.sum()} linha(s) com campo Bloomberg que nao bate "
            f"com o indice esperado ({_CAMPO_POR_INDICE}): "
            f"{df.loc[trocado, ['data_bruta', 'indice', 'campo']].head(5).to_dict('records')}"
        )

    ruim_divergencia = df["divergencia"].abs() > _TOLERANCIA_DIVERGENCIA
    if ruim_divergencia.any():
        raise ValueError(
            f"{ruim_divergencia.sum()} linha(s) com divergencia acima de "
            f"{_TOLERANCIA_DIVERGENCIA}: o VNA nao bateu entre os papeis "
            f"do mesmo indice/data na coleta -- "
            f"{df.loc[ruim_divergencia, ['data_bruta', 'indice', 'divergencia']].head(5).to_dict('records')}"
        )

    # Resolve repeticao da MESMA data de origem antes de normalizar --
    # fica com o arquivo lido por ultimo (mais recente).
    df = df.drop_duplicates(subset=["data_bruta", "indice"], keep="last")

    df["data"] = df["data_bruta"].map(cal.ultimo_dia_util_do_mes)

    conflito = df.groupby(["data", "indice"])["vna"].nunique()
    ruins = conflito[conflito > 1]
    if not ruins.empty:
        raise ValueError(
            f"VNA diverge entre datas de origem diferentes que caem no "
            f"mesmo ultimo dia util, em {len(ruins)} par(es) (data, "
            f"indice): {ruins.index.tolist()[:5]}. O VNA nao deveria "
            f"variar entre o ultimo dia util e o ultimo dia corrido do "
            f"mes -- ver docs/convencoes-dv.md."
        )

    df = df.drop_duplicates(subset=["data", "indice"], keep="last")
    return df[["data", "indice", "vna"]].sort_values(
        ["data", "indice"]
    ).reset_index(drop=True)


def gravar():
    """Grava as duas tabelas canonicas em data/processed/.

    Nao usa gravar_atomico: essa funcao existe para proteger downloads
    brutos de rede contra escrita parcial e paginas de erro salvas como
    planilha. Aqui o conteudo e gerado localmente a partir de arquivos ja
    validados em data/raw/, e o padrao do projeto para esse caso (ver
    src/tesouro/parse_rmd/) e df.to_csv direto em data/processed/.
    """
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    for nome, df in (("taxa_por_papel", parse_taxas()), ("vna", parse_vna())):
        saida = config.PROCESSED_DIR / f"{nome}.csv"
        df.to_csv(saida, index=False, encoding="utf-8")
        print(f"gravado: {saida} ({len(df)} linhas)")


if __name__ == "__main__":
    gravar()
