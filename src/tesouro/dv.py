"""Painel de DV01 por papel, decay e calculo pontual.

O painel e persistido, e nao calculado sob demanda, porque as entregas 3
(analise de leiloes) e 5 (simulacao contra o PAF) vao consumi-lo. Tres
implementacoes independentes de DV que discordam entre si seria o pior
resultado possivel.

Unidades: quantidade_mil e o estoque em milhares de titulos; pu e
dv_unitario sao reais por titulo. Logo o financeiro e o DV da posicao,
em milhoes de reais, sao (valor por titulo) * quantidade_mil / 1000.

A taxa entra em PERCENTUAL nos tres CSVs de origem (13.5 = 13,5% a.a.);
a conversao para decimal (/100) acontece so aqui, uma vez, porque o
motor de precificacao (precificacao.pu/dv) exige decimal e um fator 100
errado e a classe de defeito que este projeto mais teme.

A juncao e pelo ultimo dia util do mes nos tres lados. O estoque
(estoque_titulos_vencimento.csv) traz o ultimo dia CORRIDO; taxa e VNA
(taxa_por_papel.csv, vna.csv, produzidos por parse_bloomberg) ja vem no
ultimo dia UTIL. Um merge(on="data") direto entre estoque cru e taxa
perde por volta de um terco do painel em silencio -- ver
docs/convencoes-dv.md. _posicoes normaliza o lado do estoque com
calendario.ultimo_dia_util_do_mes antes de qualquer juncao.
"""
import pandas as pd

from . import calendario, config, precificacao

TITULOS = ("LTN", "NTN-F", "NTN-B", "LFT")
_INDICE_DO_TITULO = {"NTN-B": "IPCA", "LFT": "SELIC"}

_COLUNAS = [
    "data", "isin", "titulo", "vencimento", "taxa_pct", "vna", "pu",
    "dv_unitario", "quantidade_mil", "dv_posicao_milhoes",
    "financeiro_calculado_milhoes",
]


def _ler(nome, **kw):
    caminho = config.PROCESSED_DIR / f"{nome}.csv"
    if not caminho.exists():
        raise FileNotFoundError(
            f"{caminho} nao existe. Rode a camada de dados e o parser da "
            f"Bloomberg antes: 'python -m tesouro.pipeline --sem-coleta'"
        )
    return pd.read_csv(caminho, **kw)


def _posicoes(cal):
    """Estoque do escopo, com a data ja no ultimo dia util do mes."""
    e = _ler("estoque_titulos_vencimento", parse_dates=["data", "vencimento"])
    e = e[(e["quantidade_mil"].fillna(0) > 0) & e["titulo"].isin(TITULOS)].copy()
    e["data"] = e["data"].dt.date.map(cal.ultimo_dia_util_do_mes)
    e["vencimento"] = e["vencimento"].dt.date
    return e[["data", "isin", "titulo", "vencimento", "quantidade_mil"]]


def _com_precos(cal):
    """Junta posicao, taxa e VNA, e calcula PU e DV linha a linha."""
    pos = _posicoes(cal)
    tx = _ler("taxa_por_papel", parse_dates=["data"])
    tx["data"] = tx["data"].dt.date
    vn = _ler("vna", parse_dates=["data"])
    vn["data"] = vn["data"].dt.date
    dup = vn.duplicated(subset=["data", "indice"])
    if dup.any():
        exemplos = vn.loc[dup, ["data", "indice"]].drop_duplicates().head(5).values.tolist()
        raise ValueError(
            f"vna.csv tem (data, indice) duplicado em {int(dup.sum())} linha(s), "
            f"exemplos: {exemplos}. O dicionario vna_por fica com a ultima "
            f"ocorrencia em silencio; corrija a origem antes de montar o painel."
        )
    vna_por = {(r.data, r.indice): r.vna for r in vn.itertuples(index=False)}

    df = pos.merge(tx[["data", "isin", "taxa_pct"]], on=["data", "isin"], how="left")
    df["vna"] = [
        vna_por.get((d, _INDICE_DO_TITULO[t])) if t in _INDICE_DO_TITULO else None
        for d, t in zip(df["data"], df["titulo"])
    ]

    pus, dvs = [], []
    for r in df.itertuples(index=False):
        precisa_vna = r.titulo in _INDICE_DO_TITULO
        # pd.isna(r.vna), nao "r.vna is None": df["vna"] e uma coluna
        # numerica, e uma vez que ela recebe qualquer valor float o
        # pandas converte os None ausentes em NaN -- e NaN is None e
        # False. Com "is None" aqui, uma NTN-B sem VNA passa da guarda,
        # e precificacao._truncar(NaN, 6) tanto pode devolver um PU NaN
        # silencioso quanto levantar ValueError (math.trunc de NaN), em
        # vez de a linha ser pulada como None. Ver tests/test_dv.py,
        # test_vna_ausente_pula_a_linha_em_vez_de_precificar_com_nan.
        if pd.isna(r.taxa_pct) or (precisa_vna and pd.isna(r.vna)):
            pus.append(None)
            dvs.append(None)
            continue
        taxa = r.taxa_pct / 100.0
        pus.append(precificacao.pu(cal, r.titulo, r.data, r.vencimento, taxa, r.vna))
        dvs.append(precificacao.dv(cal, r.titulo, r.data, r.vencimento, taxa, r.vna))
    df["pu"] = pus
    df["dv_unitario"] = dvs
    return df


def painel():
    """Uma linha por papel e fim de mes, com insumos e resultado."""
    cal = calendario.padrao()
    df = _com_precos(cal)
    df["financeiro_calculado_milhoes"] = df["pu"] * df["quantidade_mil"] / 1000
    df["dv_posicao_milhoes"] = df["dv_unitario"] * df["quantidade_mil"] / 1000
    return df[_COLUNAS].sort_values(["data", "titulo", "vencimento"]).reset_index(drop=True)


def gravar_painel():
    """Grava dv_por_papel.csv em data/processed/.

    Nao usa gravacao.gravar_atomico: essa funcao protege downloads brutos
    de rede contra escrita parcial e paginas de erro salvas como
    planilha. Aqui o conteudo e gerado localmente a partir de arquivos ja
    validados em data/processed/, o padrao do projeto para esse caso (ver
    parse_bloomberg.gravar) e df.to_csv direto.
    """
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df = painel()
    saida = config.PROCESSED_DIR / "dv_por_papel.csv"
    df.to_csv(saida, index=False, encoding="utf-8")
    print(f"gravado: {saida} ({len(df)} linhas)")


# ---------------------------------------------------------------------------
# Decay: Conta B da spec -- so a passagem do tempo, taxa e VNA constantes.
#
# Nao envolve dinheiro nem VNA reprojetado: e mecanico, prazo menor implica
# DV menor em modulo. A outra conta, o resultado realizado com movimento de
# taxa (Conta A), fica na Tarefa 8 e nao usa nada daqui.
#
# Convencao de sinal do decay: dv e negativo para titulo (docs/convencoes-
# dv.md). Com menos prazo o DV fica MENOS negativo, entao decay = dv_alvo -
# dv_base e POSITIVO para um sobrevivente -- o numero mede o quanto o DV
# "encolheu" em modulo. Para um papel que vence no caminho, dv_alvo e 0.0 e
# decay tambem sai positivo (a mesma formula), mas dv_alvo=0 misturado com
# o encolhimento normal e exatamente o que venceu_no_caminho existe para
# marcar -- nunca somar as duas coisas sem olhar essa coluna.
# ---------------------------------------------------------------------------

HORIZONTES = {"1du": 1, "5du": 5, "21du": 21}

_COLUNAS_DECAY = [
    "data_base", "horizonte", "data_alvo", "isin", "titulo",
    "venceu_no_caminho", "dv_base", "dv_alvo", "decay",
]


def _decay_de(cal, linhas, data_base, data_alvo, rotulo):
    """Reprecifica cada papel na data-alvo, com taxa e VNA constantes.

    Conta B da spec: so o efeito da passagem do tempo. Papel que vence no
    caminho recebe dv_alvo zero -- ele existia e deixou de existir, o que
    e informacao, nao ausencia -- e fica marcado em venceu_no_caminho para
    nao se confundir com queda de risco de um papel vivo. Para papel
    vencido, precificacao.dv nunca e chamado: o zero vem direto, sem
    reprecificar nada (ver test_venceu_no_caminho_nunca_chama_precificacao
    em tests/test_decay.py).
    """
    saida = []
    for r in linhas.itertuples(index=False):
        venceu = cal.ajustar_vencimento(r.vencimento) <= data_alvo
        if pd.isna(r.taxa_pct) or pd.isna(r.dv_unitario):
            # Sem taxa ou sem dv_unitario na base, nao ha decay medivel --
            # nao dava para medir o risco de partida, entao nao da para
            # medir a variacao, mesmo que o papel tambem tenha vencido no
            # caminho. None, nao zero -- "nao se aplica" e diferente de
            # "risco genuinamente nulo". Esta guarda vem ANTES da de
            # vencimento de proposito: um papel vencido sem dv_base
            # medido (ex.: NTN-F ja vencida no estoque, sem taxa na
            # data) nao pode virar "risco foi a zero", porque o risco de
            # partida nunca foi conhecido.
            alvo = None
        elif venceu:
            alvo = 0.0
        else:
            unitario = precificacao.dv(
                cal, r.titulo, data_alvo, r.vencimento, r.taxa_pct / 100.0, r.vna
            )
            alvo = unitario * r.quantidade_mil / 1000
        base = r.dv_posicao_milhoes
        decaimento = None if (alvo is None or pd.isna(base)) else alvo - base
        saida.append((data_base, rotulo, data_alvo, r.isin, r.titulo,
                      venceu, base, alvo, decaimento))
    return saida


def decay(horizontes=None):
    """Decay a taxa constante, por papel, nos horizontes pedidos.

    horizontes: dict rotulo -> passos em dias uteis (base 252). Default
    HORIZONTES = {"1du": 1, "5du": 5, "21du": 21}.
    """
    horizontes = horizontes or HORIZONTES
    cal = calendario.padrao()
    p = painel()
    p = p[p["titulo"] != "LFT"]           # LFT nao tem DV no projeto (None)

    linhas = []
    for data_base, grupo in p.groupby("data", sort=True):
        for rotulo, passos in horizontes.items():
            alvo = cal.mover(data_base, passos)
            linhas += _decay_de(cal, grupo, data_base, alvo, rotulo)
    return pd.DataFrame(linhas, columns=_COLUNAS_DECAY).sort_values(
        ["data_base", "horizonte", "titulo", "isin"]
    ).reset_index(drop=True)


def gravar_decay():
    """Grava decay_por_papel.csv em data/processed/.

    Mesmo padrao de gravar_painel: conteudo gerado localmente a partir de
    data/processed/ ja validado, entao df.to_csv direto, sem gravar_atomico
    (essa protege download bruto de rede, nao e o caso aqui).
    """
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df = decay()
    saida = config.PROCESSED_DIR / "decay_por_papel.csv"
    df.to_csv(saida, index=False, encoding="utf-8")
    print(f"gravado: {saida} ({len(df)} linhas)")


# ---------------------------------------------------------------------------
# Pontual: a pergunta do dia a dia -- "da posicao de hoje, quanto do meu DV
# some ate tal data". Nao e uma funcao nova: e _decay_de com uma data-alvo
# escolhida no momento, em vez de um dos tres horizontes fixos. Por isso o
# resultado NUNCA e persistido em CSV -- e uma pergunta, nao um fato: a
# data-alvo muda a cada chamada, e gravar a resposta criaria um arquivo que
# ninguem sabe se ainda vale (ver docs/convencoes-dv.md e o brief da Tarefa
# 7). O comando de linha (main, abaixo) imprime na tela e para por ai.
#
# Cobertura do DV01 sobre o estoque: NAO e uma constante fixa. 46,6% (LTN
# 14,4% + NTN-F 7,5% + NTN-B 24,7%) e o numero de junho de 2026 em
# docs/convencoes-dv.md, mas a composicao da divida muda mes a mes -- em
# 2020-12-31 a cobertura medida e 60,4%, quatorze pontos acima. Por isso
# _cobertura calcula o numero de verdade NA data_base pedida, a partir do
# financeiro_milhoes bruto de estoque_titulos_vencimento.csv (que cobre
# todo titulo, inclusive LFT e os excluidos, ao contrario do painel de
# DV que so tem LTN/NTN-F/NTN-B/LFT). Sem isso, um total impresso para
# uma data antiga vinha rotulado com a cobertura errada -- achado da
# revisao da Tarefa 7.
# ---------------------------------------------------------------------------

_TITULOS_LFT = ("LFT", "LFT-TD1 Reserva")


def _cobertura(cal, data_base):
    """Cobertura real do DV01 sobre o estoque, calculada NA data_base.

    Devolve None se nao houver estoque total medido nessa data (sem
    financeiro em nenhum titulo) -- quem chama decide o que fazer.
    """
    e = _ler("estoque_titulos_vencimento", parse_dates=["data"])
    e = e[e["quantidade_mil"].fillna(0) > 0].copy()
    e["data"] = e["data"].dt.date.map(cal.ultimo_dia_util_do_mes)
    grupo = e[e["data"] == data_base]

    total = grupo["financeiro_milhoes"].sum()
    if total == 0:
        return None

    por_titulo_pct = {
        t: 100 * grupo[grupo["titulo"] == t]["financeiro_milhoes"].sum() / total
        for t in TITULOS if t != "LFT"          # LTN, NTN-F, NTN-B, nessa ordem
    }
    lft_pct = 100 * grupo[grupo["titulo"].isin(_TITULOS_LFT)]["financeiro_milhoes"].sum() / total
    cobertos_pct = sum(por_titulo_pct.values())
    return {
        "por_titulo_pct": por_titulo_pct,
        "cobertos_pct": cobertos_pct,
        "lft_pct": lft_pct,
        "excluidos_pct": 100 - cobertos_pct - lft_pct,
    }


def _daqui_um_ano(d):
    """Mesma data, um ano depois; 29/02 sem bissexto seguinte vira 28/02."""
    from datetime import date as _date
    try:
        return _date(d.year + 1, d.month, d.day)
    except ValueError:
        return _date(d.year + 1, d.month, d.day - 1)


def _validar_no_calendario(cal, d, nome):
    """Converte o ValueError interno do calendario numa mensagem que nao
    exige conhecer _decay_de/Calendario para entender."""
    try:
        cal.eh_dia_util(d)
    except ValueError:
        # "from None" corta a cadeia: sem isso, o ValueError cru de dentro
        # de Calendario._verificar_janela aparece no traceback junto com
        # esta mensagem (via "During handling of the above exception..."),
        # exatamente o que o brief da Tarefa 7 pede para evitar.
        # cal._inicio/_fim, nao um literal "2001 a 2099": a janela vem do
        # arquivo de feriados carregado (ver Calendario no modulo
        # calendario), entao se o arquivo mudar a mensagem continua certa
        # em vez de mentir com um numero fixo desatualizado.
        raise ValueError(
            f"a {nome} ({d:%d/%m/%Y}) esta fora do calendario de dias "
            f"uteis, que cobre {cal._inicio:%d/%m/%Y} a {cal._fim:%d/%m/%Y}. "
            f"Escolha uma {nome} dentro desse intervalo."
        ) from None


def pontual(data_alvo=None, data_base=None):
    """Decompoe a queda de DV entre a data-base e uma data-alvo escolhida.

    Responde a pergunta do dia a dia: da posicao de hoje, quanto do DV
    some ate a data-alvo, e quanto disso e vencimento em vez de encurtar.
    Reusa _decay_de -- e a mesma conta dos horizontes fixos (1du/5du/21du),
    so que com uma data escolhida na hora em vez de um dos tres rotulos.

    data_base ausente: usa o ultimo fim de mes disponivel no painel.
    data_alvo ausente: usa data_base + 1 ano (o resumo devolvido marca
    isso em "alvo_padrao", para quem chama avisar o que foi assumido).

    Conta B da spec: taxa e VNA constantes, sem dinheiro e sem VNA
    reprojetado (ver o comentario acima de HORIZONTES).
    """
    cal = calendario.padrao()
    p = painel()
    p = p[p["titulo"] != "LFT"]           # LFT nao tem DV no projeto (None)

    if data_base is None:
        data_base = max(p["data"])
    _validar_no_calendario(cal, data_base, "data-base")

    alvo_padrao = data_alvo is None
    if alvo_padrao:
        data_alvo = _daqui_um_ano(data_base)
    _validar_no_calendario(cal, data_alvo, "data-alvo")

    if data_alvo <= data_base:
        raise ValueError(
            f"a data-alvo ({data_alvo:%d/%m/%Y}) precisa ser posterior a "
            f"data-base ({data_base:%d/%m/%Y})"
        )

    grupo = p[p["data"] == data_base]
    if grupo.empty:
        datas = sorted(p["data"].unique())
        raise ValueError(
            f"nao ha posicao em {data_base:%d/%m/%Y} no painel; as datas "
            f"disponiveis sao fins de mes, de {datas[0]:%d/%m/%Y} a "
            f"{datas[-1]:%d/%m/%Y}. Informe --base com uma dessas datas, "
            f"ou omita para usar a mais recente."
        )

    linhas = _decay_de(cal, grupo, data_base, data_alvo, "pontual")
    df = pd.DataFrame(linhas, columns=_COLUNAS_DECAY)

    vence = df[df["venceu_no_caminho"]]
    vive = df[~df["venceu_no_caminho"]]
    resumo = {
        "data_base": data_base,
        "data_alvo": data_alvo,
        "alvo_padrao": alvo_padrao,
        "dv_base": df["dv_base"].sum(),
        "dv_que_vence": -vence["dv_base"].sum(),
        "decay_sobreviventes": vive["decay"].sum(),
        "dv_alvo": df["dv_alvo"].sum(),
        "por_titulo": _por_titulo(df),
        "cobertura": _cobertura(cal, data_base),
    }
    return resumo


def _por_titulo(df):
    """Agrega dv_base, dv_alvo, contagem de papeis e de vencimentos por
    titulo. Extraida de pontual() para poder ser testada com um DataFrame
    sintetico pequeno -- ver test_por_titulo_agrega_as_quatro_colunas_
    corretamente, que usa ISIN duplicado de proposito porque no dado real
    cada ISIN aparece uma unica vez por (titulo, data) e por isso
    "nunique" e "count" dao o mesmo numero, escondendo essa mutacao.
    """
    return (
        df.groupby("titulo")
          .agg(dv_base=("dv_base", "sum"), dv_alvo=("dv_alvo", "sum"),
               papeis=("isin", "nunique"),
               vencendo=("venceu_no_caminho", "sum"))
          .reset_index()
    )


def _num_br(x, casas=2, forcar_sinal=False):
    """Formata em portugues: ponto de milhar, virgula decimal."""
    neg = x < 0
    texto = f"{abs(x):,.{casas}f}"
    texto = texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    if neg:
        return f"-{texto}"
    if forcar_sinal:
        return f"+{texto}"
    return texto


def _formatar(r):
    tabela = r["por_titulo"].copy()
    tabela["dv_base"] = tabela["dv_base"].map(_num_br)
    tabela["dv_alvo"] = tabela["dv_alvo"].map(_num_br)
    tabela = tabela.rename(columns={
        "titulo": "titulo", "dv_base": "dv_base_milhoes",
        "dv_alvo": "dv_alvo_milhoes", "papeis": "papeis",
        "vencendo": "vencendo_no_caminho",
    })

    # Linhas rotulo/valor com largura de rotulo calculada, nao espacos
    # contados a mao -- um quadro com rotulos de tamanhos diferentes
    # ("DV na data-base" vs "(-) decay dos sobreviventes") desalinhava a
    # virgula decimal entre as quatro linhas quando o espaco era fixo
    # (achado da revisao da Tarefa 7).
    itens = [
        ("DV na data-base", r["dv_base"], False),
        ("(-) DV que vence no caminho", r["dv_que_vence"], True),
        ("(-) decay dos sobreviventes", r["decay_sobreviventes"], True),
        ("DV na data-alvo", r["dv_alvo"], False),
    ]
    largura_rotulo = max(len(rotulo) for rotulo, _, _ in itens)
    quadro = [
        f"  {rotulo:<{largura_rotulo}}  {_num_br(valor, forcar_sinal=sinal):>14}"
        for rotulo, valor, sinal in itens
    ]

    linhas = [
        f"posicao em {r['data_base']:%d/%m/%Y}, projetada para "
        f"{r['data_alvo']:%d/%m/%Y}",
        "",
        *quadro,
        "",
        "valores em R$ milhoes por bp; negativo = mercado perde na alta de "
        "taxa. 'DV que vence' e 'decay' aparecem com sinal positivo porque "
        "somam ao DV base, que e negativo -- o efeito de ambos e deixar o "
        "DV menos negativo.",
        "",
    ]

    cobertura = r["cobertura"]
    if cobertura is None:
        linhas.append(
            "cobertura do DV01: nao foi possivel calcular para esta "
            "data-base (sem estoque total medido nela)."
        )
    else:
        cobertura_titulos = " + ".join(
            f"{t} {_num_br(pct, 1)}%"
            for t, pct in cobertura["por_titulo_pct"].items()
        )
        linhas += [
            f"cobertura do DV01 em {r['data_base']:%d/%m/%Y}: "
            f"{_num_br(cobertura['cobertos_pct'], 1)}% do estoque "
            f"({cobertura_titulos})",
            f"fora do DV01: LFT {_num_br(cobertura['lft_pct'], 1)}% (sem "
            f"duration de juros por construcao) + "
            f"{_num_br(cobertura['excluidos_pct'], 1)}% excluidos sem "
            f"preco no secundario",
        ]

    linhas += [
        "",
        tabela.to_string(index=False),
        "",
        "'papeis' conta todo ISIN do titulo presente no painel nesta "
        "data-base, inclusive os sem taxa/DV medido -- pode ser maior do "
        "que o numero de papeis que de fato compoe dv_base_milhoes.",
    ]
    return "\n".join(linhas)


def main(argumentos=None):
    import argparse
    import sys
    from datetime import datetime

    analisador = argparse.ArgumentParser(
        description=(
            "Decay do DV01 ate uma data-alvo.\n\n"
            "Exemplos de uso (o modulo nao se instala; sempre com "
            "PYTHONPATH apontando para src/):\n\n"
            "  PowerShell:\n"
            "    $env:PYTHONPATH=\"src\"; python -m tesouro.dv --alvo 31/12/2026\n\n"
            "  bash:\n"
            "    PYTHONPATH=src python -m tesouro.dv --alvo 31/12/2026"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    analisador.add_argument(
        "--alvo", default=None,
        help="data-alvo, no formato DD/MM/AAAA (ex.: 31/12/2026); se "
             "omitido, usa data-base + 1 ano",
    )
    analisador.add_argument(
        "--base", default=None,
        help="data-base, no formato DD/MM/AAAA; o padrao e o ultimo fim de "
             "mes do painel",
    )
    analisador.add_argument(
        "--figura", default=None,
        help="caminho para gravar o grafico (opcional; ver Tarefa 9)",
    )
    analisador.add_argument(
        "--gravar", action="store_true",
        help="regrava dv_por_papel.csv e decay_por_papel.csv em "
             "data/processed/ e sai, sem calcular o pontual",
    )
    opcoes = analisador.parse_args(argumentos)

    if opcoes.gravar:
        # Unica forma de linha de comando de regerar os dois CSVs -- antes
        # desta tarefa era 'python -m tesouro.dv' sem argumento nenhum.
        # A ligacao com o pipeline geral fica para a Tarefa 10; aqui so
        # devolvemos a capacidade que o proprio __main__ tinha antes de
        # virar o comando pontual.
        gravar_painel()
        gravar_decay()
        return

    def ler_data(valor, nome_opcao):
        try:
            return datetime.strptime(valor, "%d/%m/%Y").date()
        except ValueError:
            raise SystemExit(
                f"'{valor}' nao e uma data valida para {nome_opcao}. Use o "
                f"formato DD/MM/AAAA (dia/mes/ano com 4 digitos), por "
                f"exemplo 31/12/2026."
            )

    data_alvo = ler_data(opcoes.alvo, "--alvo") if opcoes.alvo else None
    data_base = ler_data(opcoes.base, "--base") if opcoes.base else None

    try:
        r = pontual(data_alvo, data_base)
    except ValueError as erro:
        raise SystemExit(str(erro))

    if r["alvo_padrao"]:
        print(
            f"nenhuma --alvo informada; usando data-base + 1 ano "
            f"({r['data_alvo']:%d/%m/%Y}). Informe --alvo DD/MM/AAAA para "
            f"escolher outra data."
        )
        print()

    print(_formatar(r))

    if opcoes.figura:
        try:
            from . import figuras
        except ImportError:
            # Nao e um erro do calculo -- o quadro acima ja saiu certo e
            # completo. Sai com codigo 0: um script que so olha o
            # resultado do calculo pontual nao deve falhar por causa de
            # um recurso opcional, ainda nao implementado (Tarefa 9),
            # sinalizado claramente no stderr.
            print(
                "\n--figura ainda nao esta disponivel (modulo "
                "tesouro.figuras nao existe nesta versao); o quadro "
                "acima ja foi impresso normalmente.",
                file=sys.stderr,
            )
            return
        figuras.grafico_pontual(r, opcoes.figura)
        print(f"\nfigura: {opcoes.figura}")


if __name__ == "__main__":
    main()
