"""Leiloes do dia, vindos da API, ao lado do historico que vem da planilha.

O PROBLEMA. O Tesouro publica o `historico-leiloes-todos.xls` com atraso -- um dia,
as vezes mais. Quem acompanha leilao precisa do numero logo depois de o resultado
sair, e nao no dia seguinte. A API do portal de dados abertos publica antes.

SAO TRES MOMENTOS, e nao dois. Um leilao aparece na tela tres vezes, e a cada vez
o numero fica mais firme:

  1. OFERTADO -- o Tesouro anuncia quanto vai ofertar. Ainda nao ha taxa nem
     financeiro; o que da para desenhar e um TETO ("se aceitar tudo");
  2. ACEITO -- sai o resultado, e a quantidade ofertada e substituida pela aceita,
     que e sempre menor ou igual. A taxa agora e a de verdade;
  3. PLANILHA -- o historico-leiloes-todos.xls traz o mesmo leilao, um dia ou mais
     depois, e a linha da API deixa de ser necessaria.

A REGRA QUE ORGANIZA TUDO: o estagio mais adiantado sempre vence. Planilha sobre
aceito, aceito sobre ofertado. Nunca ao contrario -- e por isso que rodar de novo com
um arquivo antigo nao estraga o que ja estava certo.

Dai decorre o resto do desenho:

  - `leiloes.csv` continua sendo SO a planilha. O contrato dele nao muda, e os
    testes que ja o usam continuam querendo dizer o que queriam;
  - `leiloes_recentes.csv` guarda so o que a API trouxe e a planilha ainda nao tem;
  - `completo()` devolve a uniao, com a coluna `estagio` dizendo em que momento
    cada linha esta. Quem consome escolhe ate onde quer ir;
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

# Quanto mais alto, mais firme o numero. A ordem e o que decide quem sobrevive
# quando o mesmo leilao chega duas vezes -- e ela NUNCA anda para tras.
ORDEM_DOS_ESTAGIOS = {"ofertado": 0, "aceito": 1, "planilha": 2}

# O nome da coluna e "estagio" e nao "origem" de proposito: o que importa a quem le
# o grafico nao e de qual arquivo o numero veio, e sim quanto ele ainda pode mudar.
COLUNA_ESTAGIO = "estagio"


def carregar_base():
    """O historico que veio da planilha do Tesouro."""
    return pd.read_csv(
        config.PROCESSED_DIR / "leiloes.csv",
        parse_dates=["data_leilao", "data_liquidacao", "data_vencimento"],
    )


def carregar_recentes(colunas=None):
    """O que a API trouxe e a planilha ainda nao tem. Vazio se o arquivo nao existe.

    'colunas' evita ir ao disco so para descobrir o formato do vazio: quem ja tem a
    base em maos passa as colunas dela. Sem isso, a funcao lia leiloes.csv apenas
    para construir um DataFrame com zero linhas.
    """
    caminho = config.PROCESSED_DIR / ARQUIVO_RECENTES
    if not caminho.exists():
        if colunas is None:
            colunas = list(carregar_base().columns)
        return pd.DataFrame(columns=list(colunas) + [COLUNA_ESTAGIO])
    return pd.read_csv(
        caminho, parse_dates=["data_leilao", "data_liquidacao", "data_vencimento"],
    )


def _volta_normal(valores):
    """A volta reduzida ao numero: "1.a volta", "1a volta" e "1a" viram todos "1".

    TRES FONTES, TRES GRAFIAS, e o defeito que isso causou foi medido em 20/08/2026:
    a planilha do Tesouro escreve "1.\u00aa volta", a API escreve "1a volta" e a
    planilha de entrada escreve "1a". Sem normalizar, a chave do leilao nunca casa
    entre fontes -- e 57 leiloes que a planilha JA TINHA entraram como novidade,
    prontos para aparecer em dobro no grafico.

    E o pior tipo de defeito deste projeto: nao levanta, nao quebra, so dobra a
    barra. Foi pego porque o log dizia "70 novas, 0 que a planilha ja tinha", e zero
    casamentos em trinta dias de leilao nao e um numero possivel.

    O que importa e o ordinal. O resto e ortografia.
    """
    texto = valores.fillna("").astype(str).str.strip()
    numero = texto.str.extract(r"(\d)")[0]
    return numero.fillna(texto)


def _colunas_da_chave(df):
    """As colunas da chave, normalizadas. UM lugar so, de proposito.

    Antes havia duas copias desta logica -- uma em _chaves() e outra dentro de
    novidades() -- e foi entre elas que a normalizacao da volta ficou faltando de um
    lado. Duas copias de uma regra e uma regra que vai divergir.
    """
    partes = []
    for coluna in CHAVE:
        valores = df[coluna]
        if pd.api.types.is_datetime64_any_dtype(valores):
            # A planilha traz data sem hora e a API pode trazer com, e duas datas
            # que diferem so na hora sao o mesmo leilao.
            valores = valores.dt.normalize()
        elif coluna == "volta":
            valores = _volta_normal(valores)
        partes.append(valores.astype(str))
    return partes


def _chaves(df):
    """O conjunto de chaves de um DataFrame."""
    if df.empty:
        return set()
    return set(zip(*_colunas_da_chave(df)))


def novidades(candidatos, base=None):
    """Das linhas candidatas, as que a planilha ainda NAO tem.

    E aqui que a reconciliacao acontece: quando a planilha alcanca um leilao que a
    API tinha trazido, ele deixa de ser novidade e sai sozinho do arquivo recente.
    """
    base = carregar_base() if base is None else base
    if candidatos.empty:
        return candidatos
    ja_tem = _chaves(base)
    marca = [chave not in ja_tem
             for chave in zip(*_colunas_da_chave(candidatos))]
    return candidatos[pd.Series(marca, index=candidatos.index)]


def _indexa_por_chave(df):
    """O DataFrame indexado pela chave normalizada, para casar linha com linha."""
    if df.empty:
        return df.assign(_chave=pd.Series(dtype=object)).set_index("_chave")
    return df.assign(_chave=list(zip(*_colunas_da_chave(df)))).set_index("_chave")



def gravar_recentes(candidatos, estagio="aceito", base=None):
    """Acrescenta o que chegou ao leiloes_recentes.csv, sem apagar o que ja estava.

    ACRESCENTA, e nao substitui. A primeira versao substituia, e isso apagava o
    leilao de segunda quando o de terca chegava -- exatamente o caso que motiva o
    arquivo existir. Conferido por teste.

    Quando o mesmo leilao chega duas vezes, vence o ESTAGIO MAIS ADIANTADO: o aceito
    substitui o ofertado, e nunca o contrario. Assim, reprocessar um arquivo antigo
    de oferta nao desfaz um resultado ja conhecido.

    Devolve (caminho, entraram, ja_na_planilha, ja_no_provisorio).

    OS DOIS ULTIMOS ERAM UM SO, e ser um so fazia o log mentir. A conta antiga
    era 'len(candidatos) - len(entram)': um residuo que somava dois motivos
    diferentes para uma linha nao entrar, e que o chamador depois narrava como
    se fosse sempre o primeiro --

        ja_na_planilha    a planilha historica do Tesouro ja traz aquele leilao,
                          e por isso ele deixou de ser novidade (ver novidades);
        ja_no_provisorio  a planilha NAO traz, mas este arquivo ja tinha a linha
                          num estagio igual ou mais adiantado (aceito vence
                          ofertado).

    Medido em 08/10/2026 as 15:11: as seis pernas do edital chegaram depois de o
    resultado do dia estar guardado, e o programa anunciou "a planilha do
    Tesouro ja alcancou tudo". A planilha para em 13/08 e nao tinha nenhuma das
    seis.
    """
    if estagio not in ORDEM_DOS_ESTAGIOS:
        raise LookupError(
            f"estagio '{estagio}' nao existe. Os que existem: "
            f"{sorted(ORDEM_DOS_ESTAGIOS, key=ORDEM_DOS_ESTAGIOS.get)}."
        )
    base = carregar_base() if base is None else base

    chegando = novidades(candidatos, base).copy()
    chegando[COLUNA_ESTAGIO] = estagio

    guardado = carregar_recentes(colunas=base.columns)
    if not guardado.empty:
        # O que a planilha ja alcancou sai daqui tambem, e nao so na hora de juntar:
        # deixar crescer um arquivo de provisorios que ja viraram definitivos e
        # convite para alguem le-lo sem passar por completo().
        guardado = novidades(guardado, base)
    if COLUNA_ESTAGIO not in guardado.columns:
        guardado[COLUNA_ESTAGIO] = "aceito"

    antigos = _indexa_por_chave(guardado)
    novos = _indexa_por_chave(chegando)

    peso_novo = ORDEM_DOS_ESTAGIOS[estagio]
    manter = [
        chave for chave in antigos.index
        if chave not in novos.index
        or ORDEM_DOS_ESTAGIOS.get(antigos.loc[[chave], COLUNA_ESTAGIO].iloc[0], 0)
        > peso_novo
    ]
    sobrevivem = antigos.loc[antigos.index.isin(manter)]
    entram = novos.loc[~novos.index.isin(manter)]

    # O QUE O ESTAGIO NOVO NAO SABE, O ANTIGO AINDA SABE. O arquivo do resultado
    # traz a quantidade ACEITA e nao repete a ofertada; sem este preenchimento, a
    # quantidade que ela digitou de manha sumiria a tarde -- e com ela a leitura de
    # quanto do ofertado o Tesouro colocou naquele dia, que so voltaria quando a
    # planilha chegasse dias depois.
    comuns = entram.index.intersection(antigos.index)
    if len(comuns):
        entram = entram.copy()
        entram.loc[comuns] = entram.loc[comuns].fillna(
            antigos.loc[comuns].drop(columns=[COLUNA_ESTAGIO]))

    juntos = pd.concat([sobrevivem, entram]).reset_index(drop=True)
    juntos = juntos.sort_values(["data_leilao", "titulo"]).reset_index(drop=True)

    caminho = config.PROCESSED_DIR / ARQUIVO_RECENTES
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    juntos.to_csv(caminho, index=False, encoding="utf-8")
    # OS DOIS MOTIVOS, contados onde cada um e conhecido: 'chegando' ja passou
    # por novidades(), entao o que caiu ali e o que a planilha alcancou; o que
    # sobrou e nao entrou foi barrado pelo estagio.
    ja_na_planilha = len(candidatos) - len(chegando)
    return caminho, len(entram), ja_na_planilha, len(chegando) - len(entram)


def completo(ate_o_estagio="ofertado"):
    """A planilha mais o que a API adiantou, com a coluna 'estagio'.

    E o que os graficos de leilao devem ler quando quiserem o dia de hoje.

    ate_o_estagio diz ate onde aceitar o provisorio:
      "planilha" -- so o numero que nao muda mais;
      "aceito"   -- inclui o resultado do dia, ainda nao confirmado pela planilha;
      "ofertado" -- inclui tambem o teto anunciado, cuja quantidade quase certamente
                    vai cair. E o default porque a pergunta que motivou tudo isto e
                    "o que esta acontecendo hoje" -- mas quem desenha tem de marcar
                    a diferenca na tela, e marca.
    """
    if ate_o_estagio not in ORDEM_DOS_ESTAGIOS:
        raise LookupError(
            f"estagio '{ate_o_estagio}' nao existe. Os que existem: "
            f"{sorted(ORDEM_DOS_ESTAGIOS, key=ORDEM_DOS_ESTAGIOS.get)}."
        )
    base = carregar_base().copy()
    base[COLUNA_ESTAGIO] = "planilha"
    if ate_o_estagio == "planilha":
        return base

    recentes = carregar_recentes(colunas=base.columns)
    if recentes.empty:
        return base
    if COLUNA_ESTAGIO not in recentes.columns:
        recentes[COLUNA_ESTAGIO] = "aceito"
    # Reconfere na hora de juntar, e nao so na de gravar: o recentes.csv pode ter
    # sido gravado antes de a planilha ser atualizada, e nesse intervalo ele carrega
    # linhas que ja viraram definitivas.
    recentes = novidades(recentes, base)

    limite = ORDEM_DOS_ESTAGIOS[ate_o_estagio]
    recentes = recentes[
        recentes[COLUNA_ESTAGIO].map(ORDEM_DOS_ESTAGIOS).fillna(-1) >= limite
    ]
    return pd.concat([base, recentes], ignore_index=True)
