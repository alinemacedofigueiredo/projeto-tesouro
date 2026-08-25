"""A distancia ate a banda do PAF, e as duas tabelas da pagina.

DENTRO DA BANDA A DISTANCIA E ZERO, e nao "a distancia ate o meio". Quem esta dentro
cumpriu o que prometeu; medir ate o centro inventaria um alvo que o PAF nao define.

Duas decisoes da dona do projeto (ver progress.md, rulings 16 e 17):

  - O ESTOQUE PROJETADO SAI COMO NUMERO, e nao como faixa. A premissa de Selic move
    a projecao em ~8 bi contra uma banda de ~600 -- 1,4%, ruido. Quem domina o erro
    e o RITMO de emissao, que errou ate +/-153 bi; essa incerteza vai no rodape da
    tabela, e nao numa faixa.

  - CAMBIO, PRAZO MEDIO e VINCENDO EM 12 MESES nao sao rolados nesta entrega (o
    cambio e a DPFe, que nao passa por leilao; os outros dois pedem o prazo papel a
    papel, trabalho da entrega 5). Cada linha nao rolada mostra a DATA do valor --
    "3,57 anos (30/06)" -- e nao um asterisco: medido, os dois andam ~25% da largura
    da banda deles em sete semanas, e o asterisco sozinho e fraco demais para isso.
"""

import pandas as pd

from .. import config, rolagem
from . import estilo, paf

# (chave da banda, rotulo, unidade). A ordem e a da tabela. A chave casa com
# valida_referencia.TODOS / paf.bandas(); o rotulo casa com o composicao_dpf.csv
# onde ha um indexador correspondente (ver _DA_COMPOSICAO).
INDICADORES = (
    ("prefixado_pct", "Prefixado", "pp"),
    ("indice_precos_pct", "\u00cdndice Pre\u00e7os", "pp"),
    ("taxa_flutuante_pct", "Taxa Flutuante", "pp"),
    ("cambio_pct", "C\u00e2mbio", "pp"),
    ("prazo_medio_anos", "Prazo m\u00e9dio", "anos"),
    ("vincendo_12m_pct", "Vincendo em 12 meses", "pp"),
    ("estoque_bilhoes", "Estoque", "R$ bi"),
)


def distancia(valor, minimo, maximo):
    """Quanto falta para entrar na banda. Zero se ja esta dentro.

    Medir ate o CENTRO da banda inventaria um alvo que o PAF nao define -- ele so
    promete um piso e um teto, e quem esta entre os dois ja cumpriu o que prometeu.
    """
    if pd.isna(valor) or pd.isna(minimo) or pd.isna(maximo):
        return float("nan")
    if valor < minimo:
        return valor - minimo
    if valor > maximo:
        return valor - maximo
    return 0.0


# O rotulo do indexador na composicao_dpf.csv, por chave de indicador. E DADO: casa
# com o CSV, acentuado -- desacentuar zeraria o filtro em silencio (ver o comentario
# junto de rolagem.INDEXADORES).
_DA_COMPOSICAO = {"prefixado_pct": "Prefixado",
                  "indice_precos_pct": "\u00cdndice Pre\u00e7os",
                  "taxa_flutuante_pct": "Taxa Flutuante",
                  "cambio_pct": "C\u00e2mbio"}


def _confere_colunas_do_denominador(colunas):
    """A guarda do denominador: o CONJUNTO tem de ser exatamente o que a rolagem
    move ou segura, nem mais (a coluna 'Demais' do CSV entraria) nem menos (um
    indexador ficaria de fora do percentual).

    ISSO E ESTRUTURAL, E NAO DE VALOR DE PROPOSITO. 'Demais' esta zerada desde
    06/2006 (medido): com o dado de hoje, somar as quatro colunas certas ou
    somar TODAS as colunas do CSV da o MESMO NUMERO, entao nenhuma comparacao de
    valor pega se alguem trocar de volta para comp.sum(axis=1). Comparar o
    CONJUNTO de colunas pega -- e continua pegando no dia em que 'Demais' deixar
    de ser zero, quando o teste de valor teria comecado a mentir sozinho.
    """
    esperado = set(rolagem.INDEXADORES) | set(rolagem.PARADOS)
    if set(colunas) != esperado:
        raise ValueError(
            "_realizado_do_rmd: o denominador tem de somar exatamente "
            f"{sorted(esperado)}, e recebeu {sorted(set(colunas))}.")


def _realizado_do_rmd():
    """O valor de cada indicador na data-base do RMD, do NOSSO dado.

    A coluna 'realizado' do referencia/paf_bandas.csv nao e usada -- paf.bandas() ja
    a descarta de proposito. Ler o realizado de uma tabela digitada a mao trocaria
    dado verificado (o parser, testado) por dado redigitado.
    """
    c = pd.read_csv(config.PROCESSED_DIR / "composicao_dpf.csv",
                    parse_dates=["data"])
    comp = c.pivot_table(index="data", columns="indexador",
                         values="valor_milhoes", aggfunc="sum").fillna(0.0)
    # O denominador e so os quatro que a rolagem move ou segura (INDEXADORES e
    # PARADOS) -- o MESMO total que rolagem.estoque_em() soma. A coluna 'Demais' do
    # CSV fica fora do denominador para o percentual de hoje e o do RMD serem
    # comparaveis contra a mesma base. _confere_colunas_do_denominador() trava
    # ISSO por ESTRUTURA -- ver o docstring dela.
    colunas = list(rolagem.INDEXADORES) + list(rolagem.PARADOS)
    _confere_colunas_do_denominador(colunas)
    total = comp[colunas].sum(axis=1)
    pct = comp[colunas].div(total, axis=0) * 100

    p = pd.read_csv(config.PROCESSED_DIR / "prazo_medio_por_titulo.csv",
                    parse_dates=["data"])
    prazo = p[(p["nivel"] == "DPF") & p["entidade"].isna()
              & p["titulo"].isna()].set_index("data")["prazo_anos"]

    v = pd.read_csv(config.PROCESSED_DIR / "vencimentos_faixa.csv",
                    parse_dates=["data"])
    fx = v[v["nivel"] == "DPF"].pivot_table(
        index="data", columns="faixa", values="valor_milhoes",
        aggfunc="sum").fillna(0.0)
    venc12 = fx["At\u00e9 12 meses"] / fx.sum(axis=1) * 100

    e = pd.read_csv(config.PROCESSED_DIR / "estoque_dpf.csv",
                    parse_dates=["data"])
    ag = e[e["entidade"].isna() & e["titulo"].isna()]
    est = ag[ag["nivel"] == "DPF em poder do publico"].set_index(
        "data")["valor_milhoes"] / 1000

    base = comp.index.max()
    saida = {chave: float(pct.loc[base, nome])
             for chave, nome in _DA_COMPOSICAO.items()}
    saida["prazo_medio_anos"] = float(prazo.loc[prazo.index.max()])
    saida["vincendo_12m_pct"] = float(venc12.loc[venc12.index.max()])
    saida["estoque_bilhoes"] = float(est.loc[est.index.max()])
    return base, saida


def _valores_de_hoje(quando):
    """Os indicadores ROLADOS ate 'quando'. Os demais vem como None.

    Cambio, prazo medio e vincendo em 12 meses NAO SAO ROLADOS nesta entrega -- ver
    o docstring do modulo. _linhas() troca o None pelo valor do RMD e marca a linha
    como nao rolada.
    """
    estoque = rolagem.estoque_em(quando)
    total = estoque.sum()
    return {"prefixado_pct": 100 * estoque["Prefixado"] / total,
            "indice_precos_pct": 100 * estoque["\u00cdndice Pre\u00e7os"] / total,
            "taxa_flutuante_pct": 100 * estoque["Taxa Flutuante"] / total,
            "cambio_pct": None,
            "prazo_medio_anos": None,
            "vincendo_12m_pct": None,
            "estoque_bilhoes": total / 1000}


def _linhas(valores, ano):
    """Uma linha por indicador, com a banda do ano e a distancia.

    O indicador ROLADO usa o valor de 'valores'. O PARADO usa o valor E A DATA do
    RMD -- 'data_base' guarda essa data para a tabela escrever "(DD/MM)" ao lado,
    em vez do asterisco que a spec original previa (ver o docstring do modulo).
    """
    base, no_rmd = _realizado_do_rmd()
    linhas = []
    for chave, rotulo, unidade in INDICADORES:
        b = paf.bandas(chave)
        if ano not in b.index:
            continue
        r = b.loc[ano]
        valor = valores.get(chave)
        rolado = valor is not None
        if not rolado:
            valor = no_rmd[chave]
        linhas.append({"indicador": rotulo, "chave": chave,
                       "no_rmd": no_rmd[chave], "hoje": valor,
                       "minimo": r["minimo"], "maximo": r["maximo"],
                       "minimo_original": r["minimo_original"],
                       "maximo_original": r["maximo_original"],
                       "distancia": distancia(valor, r["minimo"], r["maximo"]),
                       "unidade": unidade, "rolado": rolado,
                       "data_base": base})
    return pd.DataFrame(linhas)


def _ultima_liquidacao():
    """A data de liquidacao mais recente que o dado de leiloes tem."""
    l = pd.read_csv(config.PROCESSED_DIR / "leiloes.csv",
                    parse_dates=["data_liquidacao"])
    return l["data_liquidacao"].max()


def quantos_leiloes_entraram(hoje=None):
    """Quantos dias de leilao entraram na rolagem, e de que data ate que data.

    Um numero sem procedencia nao serve: quem le a tabela de hoje precisa saber se
    o "hoje" dela e de ontem ou de tres semanas atras.
    """
    base, _ = _realizado_do_rmd()
    ate = pd.Timestamp(hoje) if hoje is not None else _ultima_liquidacao()
    l = pd.read_csv(config.PROCESSED_DIR / "leiloes.csv",
                    parse_dates=["data_liquidacao"])
    entre = l[(l["data_liquidacao"] > base) & (l["data_liquidacao"] <= ate)]
    return entre["data_liquidacao"].nunique(), base, ate


def dados_hoje(hoje=None):
    """A tabela de onde estamos hoje: rolada ate a ultima liquidacao (ou 'hoje')."""
    quando = pd.Timestamp(hoje) if hoje is not None else _ultima_liquidacao()
    d = _linhas(_valores_de_hoje(quando), quando.year)
    n, de, ate = quantos_leiloes_entraram(quando)
    # A PROCEDENCIA VIAJA COM A TABELA, em attrs, para tabela() escrever o rodape
    # sozinha -- quem chama nao precisa lembrar de montar esse texto por fora.
    d.attrs["hoje"] = quando
    d.attrs["leiloes"] = n
    d.attrs["leiloes_de"] = de
    d.attrs["leiloes_ate"] = ate
    return d


def dados_projecao(ate=None, registros=None):
    """A tabela de onde a rolagem projeta o fechamento do ano.

    O ESTOQUE SAI COMO NUMERO (rolagem.projecao ja devolve um numero so, e nao uma
    faixa -- ver o docstring dela e o do modulo). 'registros' existe para os testes
    nao tocarem rede: passam registros=[] e calendario_leiloes.dias_ate usa so o
    calendario estimado.
    """
    ate = pd.Timestamp(ate) if ate is not None else pd.Timestamp(
        f"{_ultima_liquidacao().year}-12-31")
    p = rolagem.projecao(ate, registros=registros)
    valores = {"prefixado_pct": p["percentual"]["Prefixado"],
               "indice_precos_pct": p["percentual"]["\u00cdndice Pre\u00e7os"],
               "taxa_flutuante_pct": p["percentual"]["Taxa Flutuante"],
               "cambio_pct": None, "prazo_medio_anos": None,
               "vincendo_12m_pct": None,
               "estoque_bilhoes": p["estoque"].sum() / 1000}
    d = _linhas(valores, ate.year)
    d.attrs["premissa"] = p
    return d


def _numero(valor, casas=2):
    return estilo.num_br(valor, casas)


def _com_unidade(numero, unidade):
    if unidade == "R$ bi":
        return f"R$ {numero} bi"
    return f"{numero} {unidade}"


def _casas(unidade):
    return 0 if unidade == "R$ bi" else 2


def _celula(valor, unidade):
    return _com_unidade(_numero(valor, _casas(unidade)), unidade)


def _faixa(minimo, maximo, unidade):
    # A UNIDADE ENTRA UMA SO VEZ na faixa inteira, e nao em cada ponta -- "R$ 9.700
    # a 10.300 bi", e nao "9.700 a R$ 10.300 bi".
    casas = _casas(unidade)
    texto = f"{_numero(minimo, casas)} a {_numero(maximo, casas)}"
    return _com_unidade(texto, unidade)


def _rodape_automatico(dados):
    """O texto que a propria tabela sabe dizer, sem quem chama passar nada.

    A tabela de hoje diz QUANTOS LEILOES entraram e de onde ate onde; a de
    projecao diz a PREMISSA que usou (curva, Selic e inflacao implicitas) e o erro
    historico do ritmo de emissao, que e o que de fato domina a incerteza do
    estoque projetado (ver o docstring do modulo).
    """
    if "leiloes" in dados.attrs:
        n = dados.attrs["leiloes"]
        de = dados.attrs["leiloes_de"]
        ate = dados.attrs["leiloes_ate"]
        hoje = dados.attrs.get("hoje", ate)
        return (f"Hoje: {hoje:%d/%m/%Y}. {n} dia(s) de leil\u00e3o entraram na "
                f"rolagem desde a data-base do RMD ({de:%d/%m/%Y}).")
    if "premissa" in dados.attrs:
        p = dados.attrs["premissa"]
        # DE ONDE VEIO O CALENDARIO. O publicado tem precedencia sobre o
        # estimado (ver calendario_leiloes.dias_ate), e a diferenca nao e
        # cosmetica: com o calendario de 24/08/2026 sao 34 dias de leilao
        # ate 31/12, e estimando o periodo inteiro dao 36. Dois dias a mais
        # de emissao mexem no percentual projetado de cada indexador. Sem
        # esta frase, palpite e transcricao apareciam com a mesma cara.
        fronteira = p.get("fronteira_do_calendario")
        origem = (f", de calend\u00e1rio publicado at\u00e9 "
                  f"{fronteira:%d/%m/%Y} e estimado depois"
                  if fronteira is not None
                  else ", de calend\u00e1rio inteiramente estimado")
        return (
            f"Projetado para {p['ate']:%d/%m/%Y} a partir de {p['de']:%d/%m/%Y} "
            f"({p['dias_de_leilao']} dias de leil\u00e3o{origem}), "
            f"com a curva de "
            f"{p['data_da_curva']:%d/%m/%Y} (Selic impl\u00edcita "
            f"{_numero(100 * p['selic'])}% a.a., infla\u00e7\u00e3o impl\u00edcita "
            f"{_numero(100 * p['inflacao'])}% a.a.). O estoque projetado sai como "
            f"N\u00daMERO, n\u00e3o como faixa: quem domina o erro e o RITMO de "
            f"emiss\u00e3o, que errou at\u00e9 \u00b1153 bi nos ultimos fechamentos "
            f"medidos -- a premissa de Selic move a projecao em ~8 bi, ru\u00eddo "
            f"perto disso.")
    return ""


def tabela(dados, ident, rodape=""):
    """A tabela em HTML: uma linha por indicador, a nao rolada com a data do RMD.

    O rotulo da terceira coluna muda com a tabela -- "hoje" na de agora, "projetado"
    na de fechamento -- porque as duas respondem perguntas diferentes com o mesmo
    layout.
    """
    rotulo_coluna = "projetado" if "premissa" in dados.attrs else "hoje"
    cabec = ("<tr><th>indicador</th><th class='n'>no RMD</th>"
             f"<th class='n'>{rotulo_coluna}</th><th class='n'>banda</th>"
             "<th class='n'>dist\u00e2ncia</th></tr>")
    linhas = []
    for _, r in dados.iterrows():
        marca = "" if r["rolado"] else " class='parado'"
        hoje = _celula(r["hoje"], r["unidade"])
        if not r["rolado"]:
            hoje += f" ({r['data_base']:%d/%m})"
        if r["distancia"] == 0:
            dist = "dentro"
        else:
            dist = _celula(r["distancia"], r["unidade"])
        linhas.append(
            f"<tr{marca}><td>{r['indicador']}</td>"
            f"<td class='n'>{_celula(r['no_rmd'], r['unidade'])}</td>"
            f"<td class='n'>{hoje}</td>"
            f"<td class='n'>{_faixa(r['minimo'], r['maximo'], r['unidade'])}</td>"
            f"<td class='n'>{dist}</td></tr>")

    texto = " ".join(t for t in (rodape, _rodape_automatico(dados)) if t)
    return (f"<div id='{ident}'><table>{cabec}{''.join(linhas)}</table>"
            f"<p class='rodape'>{texto}</p></div>")
