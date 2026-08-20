"""Leiloes do dia, vindos da API, ao lado do historico que vem da planilha.

O PROBLEMA. O Tesouro publica o `historico-leiloes-todos.xls` com atraso -- um dia,
as vezes mais. Quem acompanha leilao precisa do numero logo depois de o resultado
sair, e nao no dia seguinte. A API do portal de dados abertos publica antes.

A REGRA QUE ORGANIZA TUDO: a planilha e a fonte definitiva, a API e provisoria.

Dai decorre o resto do desenho:

  - `leiloes.csv` continua sendo SO a planilha. O contrato dele nao muda, e os
    testes que ja o usam continuam querendo dizer o que queriam;
  - `leiloes_recentes.csv` guarda so o que a API trouxe e a planilha ainda nao tem;
  - `completo()` devolve a uniao, com a coluna `origem` dizendo de onde veio cada
    linha. Quem consome escolhe se quer o provisorio;
  - quando a planilha finalmente traz um leilao, a linha da API para ele SOME. A
    reconciliacao e automatica e nao precisa de ninguem lembrando de limpar.

A CHAVE de um leilao e (data_leilao, data_liquidacao, titulo, data_vencimento,
tipo_leilao, volta). Medido no historico: ela e unica em 19.731 das 19.739 linhas.
As oito que sobram sao quatro pares em 12/05/2009 -- duplicata da propria planilha do
Tesouro, nao defeito nosso. Estao declaradas em DUPLICATAS_CONHECIDAS_DA_PLANILHA e
travadas por teste, para que uma duplicata NOVA seja notada em vez de virar rotina.
"""
import pandas as pd

from . import config

# O que identifica um leilao. Sem data_liquidacao a chave colide 12 vezes: em
# 29/01/2004 o mesmo papel foi leiloado com duas liquidacoes diferentes.
CHAVE = ["data_leilao", "data_liquidacao", "titulo", "data_vencimento",
         "tipo_leilao", "volta"]

# As oito linhas em que a propria planilha do Tesouro repete o registro. Declaradas
# para que o teste de unicidade possa ser exato -- um limiar frouxo ("no maximo dez
# duplicatas") deixaria a nona entrar sem ninguem ver.
DUPLICATAS_CONHECIDAS_DA_PLANILHA = 8

ARQUIVO_RECENTES = "leiloes_recentes.csv"


def carregar_base():
    """O historico que veio da planilha do Tesouro."""
    return pd.read_csv(
        config.PROCESSED_DIR / "leiloes.csv",
        parse_dates=["data_leilao", "data_liquidacao", "data_vencimento"],
    )


def carregar_recentes():
    """O que a API trouxe e a planilha ainda nao tem. Vazio se o arquivo nao existe."""
    caminho = config.PROCESSED_DIR / ARQUIVO_RECENTES
    if not caminho.exists():
        return pd.DataFrame(columns=list(carregar_base().columns) + ["origem"])
    return pd.read_csv(
        caminho, parse_dates=["data_leilao", "data_liquidacao", "data_vencimento"],
    )


def _chaves(df):
    """O conjunto de chaves de um DataFrame, com as datas normalizadas para dia.

    Normalizar importa: a planilha traz datas sem hora e a API pode trazer com, e
    duas datas que diferem so na hora sao o mesmo leilao. Sem isto, toda linha da
    API pareceria nova para sempre.
    """
    if df.empty:
        return set()
    partes = []
    for coluna in CHAVE:
        valores = df[coluna]
        if pd.api.types.is_datetime64_any_dtype(valores):
            valores = valores.dt.normalize()
        partes.append(valores.astype(str))
    return set(zip(*partes))


def novidades(candidatos, base=None):
    """Das linhas candidatas, as que a planilha ainda NAO tem.

    E aqui que a reconciliacao acontece: quando a planilha alcanca um leilao que a
    API tinha trazido, ele deixa de ser novidade e sai sozinho do arquivo recente.
    """
    base = carregar_base() if base is None else base
    if candidatos.empty:
        return candidatos
    ja_tem = _chaves(base)
    marca = [chave not in ja_tem for chave in zip(*[
        (candidatos[c].dt.normalize() if pd.api.types.is_datetime64_any_dtype(
            candidatos[c]) else candidatos[c]).astype(str)
        for c in CHAVE
    ])]
    return candidatos[pd.Series(marca, index=candidatos.index)]


def gravar_recentes(candidatos, base=None):
    """Grava leiloes_recentes.csv com o que a planilha ainda nao tem.

    Devolve (caminho, quantos_entraram, quantos_ja_estavam) -- os tres numeros que
    quem roda isso de madrugada precisa ver no log.
    """
    base = carregar_base() if base is None else base
    novos = novidades(candidatos, base).copy()
    novos["origem"] = "api"

    caminho = config.PROCESSED_DIR / ARQUIVO_RECENTES
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    novos.to_csv(caminho, index=False, encoding="utf-8")
    return caminho, len(novos), len(candidatos) - len(novos)


def completo(com_provisorio=True):
    """A planilha mais o que a API adiantou, com a coluna 'origem'.

    E o que os graficos de leilao devem ler quando quiserem o dia de hoje. Com
    com_provisorio=False devolve so a planilha, que e o numero que nao muda mais.
    """
    base = carregar_base().copy()
    base["origem"] = "planilha"
    if not com_provisorio:
        return base

    recentes = carregar_recentes()
    if recentes.empty:
        return base
    # Reconfere na hora de juntar, e nao so na hora de gravar: o recentes.csv pode
    # ter sido gravado antes de a planilha ser atualizada, e nesse intervalo ele
    # carrega linhas que ja viraram definitivas.
    recentes = novidades(recentes, base)
    return pd.concat([base, recentes], ignore_index=True)
