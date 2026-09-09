"""A distancia ate a banda do PAF, e as duas tabelas da pagina.

DENTRO DA BANDA A DISTANCIA E ZERO, e nao "a distancia ate o meio". Quem esta dentro
cumpriu o que prometeu; medir ate o centro inventaria um alvo que o PAF nao define.

Duas decisoes da dona do projeto (ver progress.md, rulings 16 e 17):

  - O ESTOQUE PROJETADO SAI COMO NUMERO, e nao como faixa. A premissa de Selic move
    a projecao em ~8 bi contra uma banda de ~600 -- 1,4%, ruido. Quem domina o erro
    e o RITMO de emissao, que errou EM MEDIA +/-153 bi em dez anos de backtest --
    metade dos anos foi pior que isso. Essa incerteza vai ESCRITA no rodape da
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


def _confere_colunas_do_denominador(do_csv):
    """A guarda do denominador, alimentada pelas colunas do CSV.

    RECEBE O DADO, E NAO A CONSTANTE. A primeira versao desta guarda recebia
    list(INDEXADORES) + list(PARADOS) e comparava contra set(INDEXADORES) |
    set(PARADOS) -- os dois lados saiam da mesma constante, entao era impossivel
    divergir e a guarda nao podia disparar. Achado na revisao da branch.

    Duas perguntas, e as duas so podem ser feitas ao CSV:

      falta alguma? Um rotulo desacentuado no parser -- "Indice Precos" em vez de
      "\u00cdndice Pre\u00e7os" -- faria a coluna sumir do denominador e o termo
      ir a ZERO EM SILENCIO. Ja aconteceu neste projeto (ruling 4).

      sobrou alguma? Um indexador novo no CSV ficaria fora do denominador sem que
      ninguem percebesse, e os percentuais somariam mais de 100. So 'Demais' pode
      ficar de fora, e de proposito: ela nao entra no que a rolagem move.

    Devolve as colunas do denominador, na ordem. Quem chama SOMA O QUE ESTA
    GUARDA DEVOLVEU -- e nao uma lista propria -- para nao haver dois lugares
    dizendo qual e o denominador.
    """
    esperado = set(rolagem.INDEXADORES) | set(rolagem.PARADOS)
    do_csv = set(do_csv)

    faltando = esperado - do_csv
    if faltando:
        raise ValueError(
            "composicao_dpf.csv nao tem a(s) coluna(s) "
            f"{sorted(faltando)}, que o denominador do PAF exige. Um rotulo "
            "trocado aqui zera o indexador em silencio.")

    intrusas = do_csv - esperado - {"Demais"}
    if intrusas:
        raise ValueError(
            f"composicao_dpf.csv tem a(s) coluna(s) {sorted(intrusas)}, que "
            "nao estao no denominador do PAF nem sao a 'Demais'. Se for "
            "indexador novo, ele precisa entrar em rolagem.INDEXADORES.")

    return list(rolagem.INDEXADORES) + list(rolagem.PARADOS)


def _percentuais(comp):
    """O percentual de cada indexador sobre o denominador do PAF.

    FUNCAO PROPRIA para poder ser testada com um 'Demais' DIFERENTE DE ZERO. No
    dado de verdade 'Demais' e zero desde 06/2006, e por isso somar as quatro
    colunas certas ou somar o CSV inteiro da o mesmo numero -- nenhum teste de
    valor contra o dado real distingue as duas coisas. Com um pivo sintetico
    distingue, e ai a diferenca aparece.
    """
    colunas = _confere_colunas_do_denominador(comp.columns)
    total = comp[colunas].sum(axis=1)
    return comp[colunas].div(total, axis=0) * 100


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
    # CSV fica fora dele para o percentual de hoje e o do RMD serem comparaveis
    # contra a mesma base. _percentuais() e quem decide isso, em um lugar so.
    pct = _percentuais(comp)

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
            # NAO PULA EM SILENCIO. paf_bandas.csv e digitado a mao e cobre
            # 2003-2026; num ano sem linha, pular deixava a tabela sair VAZIA
            # -- ou, pior, faltando so alguns indicadores -- com o rodape
            # normal por cima, publicando uma tabela de conformidade em
            # branco. Achado na revisao da branch.
            raise LookupError(
                f"paf_bandas.csv nao tem a banda de {chave!r} para {ano}. "
                "Enquanto o PAF do ano nao for digitado esta pagina nao tem "
                "o que comparar, e falhar aqui e melhor do que publicar uma "
                "tabela sem a linha.")
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
    return rolagem.leiloes()["data_liquidacao"].max()


def quantos_leiloes_entraram(hoje=None):
    """Quantos dias de leilao entraram na rolagem, e de que data ate que data.

    Um numero sem procedencia nao serve: quem le a tabela de hoje precisa saber se
    o "hoje" dela e de ontem ou de tres semanas atras.
    """
    base, _ = _realizado_do_rmd()
    ate = pd.Timestamp(hoje) if hoje is not None else _ultima_liquidacao()
    l = rolagem.leiloes()
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


def dados_projecao(ate=None, registros=None, hoje=None):
    """A tabela de onde a rolagem projeta o fechamento do ano.

    O ESTOQUE SAI COMO NUMERO (rolagem.projecao ja devolve um numero so, e nao uma
    faixa -- ver o docstring dela e o do modulo). 'registros' existe para os testes
    nao tocarem rede: passam registros=[] e calendario_leiloes.dias_ate usa so o
    calendario estimado.
    """
    # 'hoje' E O MESMO DOS DOIS BLOCOS. A pagina passa o dela para ca e para
    # dados_hoje, senao a tabela de hoje anda e a projecao fica na ultima
    # liquidacao real -- dois blocos da mesma pagina partindo de datas
    # diferentes, que e o que o ruling 1 existiu para evitar.
    referencia = pd.Timestamp(hoje) if hoje is not None else _ultima_liquidacao()
    ate = pd.Timestamp(ate) if ate is not None else pd.Timestamp(
        f"{referencia.year}-12-31")
    p = rolagem.projecao(ate, registros=registros, hoje=hoje)
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
    # AUSENTE E TRACO, e nao "nan pp". Hoje nenhuma banda vem sem numero, mas o
    # paf_bandas.csv e digitado a mao: uma celula em branco viraria "nan pp" na
    # pagina, que parece dado. Achado na revisao da branch.
    if valor is None or pd.isna(valor):
        return "\u2014"
    return _com_unidade(_numero(valor, _casas(unidade)), unidade)


def _faixa(minimo, maximo, unidade):
    # A UNIDADE ENTRA UMA SO VEZ na faixa inteira, e nao em cada ponta -- "R$ 9.700
    # a 10.300 bi", e nao "9.700 a R$ 10.300 bi".
    casas = _casas(unidade)
    texto = f"{_numero(minimo, casas)} a {_numero(maximo, casas)}"
    return _com_unidade(texto, unidade)


def _banda_da_celula(r):
    """A banda VIGENTE, e o quanto ela foi revisada quando foi.

    A coluna sempre mostrou a vigente sem dizer que era a vigente. O Tesouro
    revisa a banda no meio do ano com alguma frequencia, e o paragrafo logo
    abaixo desta tabela diz, em negrito, que em 14 de 14 casos a revisao pos o
    realizado DENTRO. Medir contra a revisada sem avisar, ao lado dessa frase,
    e o tipo de numero plausivel e errado que esta pagina existe para nao
    produzir.

    A CONTAGEM SAIU DAQUI. Dizia "em 8 dos 23 anos" e "em 2026 as duas
    coincidem" -- as duas envelheceram juntas em 26/08/2026, quando o Tesouro
    revisou 2026 e o oitavo virou nono. Quantos anos foram nao muda o que esta
    funcao faz.

    Quando as duas faixas coincidem, sai so uma. E a comparacao e de VALOR, e
    nao de existencia: o Tesouro publica linha "revisado" para os sete
    indicadores mesmo quando so alguns mudam.
    """
    vigente = _faixa(r["minimo"], r["maximo"], r["unidade"])
    original_min, original_max = r.get("minimo_original"), r.get("maximo_original")
    if (pd.isna(original_min) or pd.isna(original_max)
            or (original_min == r["minimo"] and original_max == r["maximo"])):
        return vigente
    original = _faixa(original_min, original_max, r["unidade"])
    return (f"{vigente}<br><span class='revisada'>"
            f"revisada; original {original}</span>")


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
        return (
            f"Hoje: {hoje:%d/%m/%Y}. {n} dia(s) de leil\u00e3o entraram "
            f"na rolagem desde a data-base do RMD ({de:%d/%m/%Y}). "
            "Tesouro Direto e emiss\u00e3o direta n\u00e3o entram na "
            "rolagem: o res\u00edduo medido \u00e9 de 0,07% a 0,75% do "
            "estoque do indexador por m\u00eas, o que sobre esta janela "
            "d\u00e1 algo da ordem de 0,25 pp \u2014 compare com a "
            "coluna de dist\u00e2ncia antes de concluir que um "
            "indicador furou a banda. As linhas em it\u00e1lico, com a "
            "data entre par\u00eanteses, N\u00c3O s\u00e3o roladas e "
            "mostram o valor do RMD: o c\u00e2mbio \u00e9 a d\u00edvida "
            "externa, que n\u00e3o passa por leil\u00e3o, e o prazo "
            "m\u00e9dio e o vincendo ficam para a entrega 5. O estoque "
            "n\u00e3o traz dist\u00e2ncia: a banda dele \u00e9 alvo de "
            "31/12 e o estoque cresce ao longo do ano. Em 23 anos, o de "
            "agosto caiu fora da banda de dezembro 18 vezes \u2014 e 14 "
            "dessas fecharam o ano dentro dela. "
            "O denominador desta tabela s\u00e3o os quatro indexadores que "
            "a rolagem move ou segura \u2014 prefixado, \u00edndice de "
            "pre\u00e7os, taxa flutuante e c\u00e2mbio. O gr\u00e1fico de "
            "composi\u00e7\u00e3o do dashboard divide pelo total do "
            "arquivo, que inclui a coluna <i>Demais</i>. As duas contas "
            "d\u00e3o o mesmo n\u00famero desde 06/2006, quando a "
            "<i>Demais</i> zerou; antes disso ela chegou a 0,05% do "
            "estoque.")

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
            f"{_numero(100 * p['inflacao'])}% a.a.). "
            # O QUE A PREMISSA FAZ, e nao so quanto ela vale. Pedido dela em
            # 09/09/2026. O numero ja estava aqui, solto: quem lia via uma
            # premissa sem saber sobre o que ela age. A inflacao implicita e o
            # que CORRIGE O VNA da NTN-B da data-base ate a data-alvo -- cinco
            # meses com o dado de hoje, distancia em que premissa pesa.
            f"A infla\u00e7\u00e3o impl\u00edcita \u00e9 anualizada e "
            f"corrige o <b>VNA</b> entre {p['de']:%d/%m/%Y} e "
            f"{p['ate']:%d/%m/%Y}; a Selic impl\u00edcita corrige o da LFT no "
            f"mesmo per\u00edodo. O estoque projetado sai como "
            "N\u00daMERO, e n\u00e3o como faixa: quem domina o erro \u00e9 "
            "o RITMO de emiss\u00e3o, que errou EM M\u00c9DIA \u00b1153 bi "
            "(26% da largura da banda) nos dez anos de backtest \u2014 "
            "metade dos anos foi pior que isso. A premissa de Selic move a "
            "proje\u00e7\u00e3o em ~8 bi, ru\u00eddo perto disso.")
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
        if rotulo_coluna == "hoje" and r["chave"] == "estoque_bilhoes":
            # NAO E DISTANCIA: a banda de estoque e alvo de 31/12, e o estoque
            # cresce ao longo do ano por construcao. Medido nos 23 anos de PAF,
            # o estoque de AGOSTO caiu fora da banda de dezembro em 18 deles --
            # e 14 desses 18 fecharam o ano DENTRO. Escrever "R$ -610 bi" aqui
            # convida a ler como descumprimento o que e apenas o calendario.
            # Na tabela da projecao a distancia fica, porque la os dois lados
            # sao 31/12.
            dist = "\u2014 alvo de 31/12"
        elif r["distancia"] == 0:
            dist = "dentro"
        else:
            dist = _celula(r["distancia"], r["unidade"])
        linhas.append(
            f"<tr{marca}><td>{r['indicador']}</td>"
            f"<td class='n'>{_celula(r['no_rmd'], r['unidade'])}</td>"
            f"<td class='n'>{hoje}</td>"
            f"<td class='n'>{_banda_da_celula(r)}</td>"
            f"<td class='n'>{dist}</td></tr>")

    texto = " ".join(t for t in (rodape, _rodape_automatico(dados)) if t)
    return (f"<div id='{ident}'><table>{cabec}{''.join(linhas)}</table>"
            f"<p class='rodape'>{texto}</p></div>")
