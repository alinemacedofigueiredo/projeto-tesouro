"""A simulacao: quanto emitir por leilao para chegar a cada alvo.

E o terceiro bloco da paf.html, e o par da projecao: aquela responde "neste
ritmo, chego onde?", esta responde "para chegar ali, que ritmo preciso?".

TRES TABELAS INDEPENDENTES, uma por indexador -- decisao dela. Cada celula
precisa so do estoque-alvo DAQUELE papel, que e total x pct, entao nenhuma
tabela depende do que os outros dois fazem. O preco disso, que o rodape diz: as
tres nao sao necessariamente compativeis entre si.

MODULO PROPRIO, e nao mais uma funcao em banda.py: aquele arquivo ja tem duas
tabelas e passou de 400 linhas, e tres matrizes o empurrariam para alem do que
se le de uma vez.
"""
import math

import pandas as pd

from . import paf
from .. import calendario_leiloes, rolagem

# Passo das colunas, em R$ bilhoes, e margem das linhas, em pontos percentuais.
PASSO_TOTAL = 200
MARGEM_PCT = 1

# O rotulo de cada tabela na tela. Sai do vocabulario dela: e "indice de
# precos", e nao "IPCA" -- o indexador do PAF inclui a NTN-C, que e IGP-M.
_ROTULO = {
    "prefixado_pct": "Prefixado",
    "indice_precos_pct": "\u00cdndice de pre\u00e7os",
    "taxa_flutuante_pct": "Taxa flutuante",
}


def eixos(chave, projetado_pct, projetado_total, ano):
    """As linhas (%) e colunas (R$ bi) da tabela daquele indicador.

    OS EIXOS NAO SAO FIXOS. Cada um e calculado para conter DUAS coisas: a banda
    do PAF daquele indicador e o ponto para onde o ritmo de hoje leva. Decisao
    dela, e ela existe por um caso concreto -- a taxa flutuante esta em 53,24%
    projetado contra uma banda de 46 a 50: com grade fixa, a tabela do unico
    indicador FORA da banda ficaria sem a marca do ritmo atual, que e o que se
    quer comparar.
    """
    b = paf.bandas(chave).loc[ano]
    lo, hi = float(b["minimo"]), float(b["maximo"])
    linhas = list(range(
        int(min(lo - MARGEM_PCT, math.floor(projetado_pct))),
        int(max(hi + MARGEM_PCT, math.ceil(projetado_pct))) + 1))

    e = paf.bandas("estoque_bilhoes").loc[ano]
    est_lo, est_hi = float(e["minimo"]), float(e["maximo"])
    colunas = list(range(
        int(min(est_lo - PASSO_TOTAL,
                math.floor(projetado_total / PASSO_TOTAL) * PASSO_TOTAL)),
        int(max(est_hi + PASSO_TOTAL,
                math.ceil(projetado_total / PASSO_TOTAL) * PASSO_TOTAL)) + 1,
        PASSO_TOTAL))
    return linhas, colunas


def dados_simulacao(chave, hoje=None, ate=None, registros=None):
    """A matriz de uma tabela: linhas em %, colunas em R$ bi, celulas em R$ bi.

    A CELULA SAI EM BILHOES, e nao nos milhoes que rolagem devolve: a tabela
    inteira e lida em bilhoes -- os eixos, o rodape e a pagina toda -- e deixar
    uma unidade diferente no miolo e o tipo de detalhe que produz erro de mil
    vezes numa leitura rapida.
    """
    indexador = rolagem.INDEXADOR_DA_CHAVE[chave]
    hoje = pd.Timestamp(hoje) if hoje is not None \
        else rolagem.leiloes()["data_liquidacao"].max()
    ate = pd.Timestamp(ate) if ate is not None \
        else pd.Timestamp(f"{hoje.year}-12-31")

    # BUSCA UMA VEZ SO. Com registros=None -- o default de producao -- cada
    # celula da grade chamava emissao_necessaria, que chamava dias_ate, que
    # buscava o calendario NA API do Tesouro de novo: umas quarenta celulas
    # vezes tres tabelas, mais de cem buscas identicas para montar UMA pagina.
    # Os testes sempre passam registros=[] e por isso nunca passaram por aqui
    # -- achado da revisao da rodada 1. Resolver aqui, uma vez, e repassar a
    # lista concreta para projecao/emissao_necessaria/dias_ate muda o CUSTO,
    # nao o resultado: e a mesma lista que cada um buscaria sozinho.
    if registros is None:
        from .. import api_leiloes
        registros, _ = api_leiloes.buscar("calendario")

    p = rolagem.projecao(ate, registros=registros, hoje=hoje)
    projetado_pct = float(p["percentual"][indexador])
    projetado_total = float(p["estoque"].sum()) / 1000

    linhas, colunas = eixos(chave, projetado_pct, projetado_total, ate.year)

    # OS TERMOS QUE NAO MUDAM POR CELULA, calculados UMA VEZ para a tabela
    # inteira. Antes, cada uma das ~42 celulas chamava emissao_necessaria, que
    # refazia estoque_em (quatro CSVs por baixo), fluxos.pagos e a contagem de
    # leiloes do zero -- so o alvo varia de celula para celula. Medido: 338 s
    # para gerar paf.html (126 chamadas, tres tabelas) contra cerca de 24 s
    # depois. A formula da celula mora so em rolagem.emissao_a_partir_dos_
    # termos -- a mesma que emissao_necessaria chama -- para nao duplicar a
    # conta aqui (ver o docstring dela sobre o defeito da premissa copiada).
    termos = rolagem.termos_da_simulacao(indexador, hoje=hoje, ate=ate,
                                         registros=registros)
    matriz = pd.DataFrame(
        [[rolagem.emissao_a_partir_dos_termos(termos, pct, total) / 1000
          for total in colunas]
         for pct in linhas],
        index=linhas, columns=colunas)

    b = paf.bandas(chave).loc[ate.year]
    matriz.attrs["chave"] = chave
    matriz.attrs["indexador"] = indexador
    matriz.attrs["rotulo"] = _ROTULO[chave]
    matriz.attrs["banda"] = (float(b["minimo"]), float(b["maximo"]))
    # CADA EIXO ARREDONDA SOZINHO, ao ponto mais proximo da sua propria grade.
    # A menor distancia no plano exigiria comparar pontos percentuais com
    # bilhoes de reais, e portanto uma escala inventada.
    matriz.attrs["marca"] = (
        min(linhas, key=lambda x: abs(x - projetado_pct)),
        min(colunas, key=lambda x: abs(x - projetado_total)))
    matriz.attrs["ritmo_atual"] = float(rolagem.pace(hoje)[indexador]) / 1000
    matriz.attrs["projetado_pct"] = projetado_pct
    matriz.attrs["projetado_total"] = projetado_total
    dias, fronteira = calendario_leiloes.dias_ate(ate, registros=registros,
                                                   hoje=hoje)
    matriz.attrs["leiloes"] = rolagem.leiloes_que_faltam(dias, indexador)
    # DE ONDE VEIO O CALENDARIO, e a PREMISSA DE JUROS -- as duas ja vem
    # calculadas dentro de 'p', porque projecao() precisa delas para o mesmo
    # alvo. Sem levar as duas para ca, o bloco irmao (banda.py, na projecao)
    # confessa a origem do calendario e declara a premissa de juros, e este
    # bloco -- recolhivel INDEPENDENTE, que da para abrir sozinho -- ficava
    # mudo nas duas. Achado da revisao: com registros=[] a secao da simulacao
    # saia byte a byte igual a com calendario publicado.
    matriz.attrs["fronteira_do_calendario"] = fronteira
    matriz.attrs["selic"] = float(p["selic"])
    matriz.attrs["inflacao"] = float(p["inflacao"])
    matriz.attrs["data_da_curva"] = p["data_da_curva"]
    matriz.attrs["hoje"] = hoje
    matriz.attrs["ate"] = ate
    return matriz


def _numero_br(valor, casas=2):
    """O numero em pt-BR. Delegado a banda._numero, para as duas tabelas da
    pagina escreverem numero do mesmo jeito."""
    from . import banda
    return banda._numero(valor, casas)


def tabela(dados):
    """Uma tabela da simulacao, em HTML.

    Quatro decisoes dela, escritas aqui:
    1. A celula negativa e so o numero em vermelho, com o sinal de menos na
       frente -- sem icone, sem hachura, sem palavra.
    2. A celula do projetado (a "marca") sai colorida, nas tres tabelas, e
       NAO perde o alinhamento numerico das outras -- ela carrega as duas
       classes, "n" e "marca".
    3. O rodape traz o ritmo atual em numero, separado da celula marcada --
       que NAO e o ritmo atual, e sim quanto emitir para cair no ponto
       arredondado da grade. As coordenadas que acompanham o VALOR da celula
       sao as DELA -- as do ponto projetado exato, que cai fora da grade,
       vem antes e separadas, so para dizer para onde o ritmo de hoje leva.
    4. O rodape tambem confessa a origem do calendario (publicado ou
       estimado) e a premissa de juros -- o mesmo padrao que o bloco irmao
       (a projecao, em banda.py) ja segue, e que este bloco, por ser
       recolhivel INDEPENDENTE, precisa repetir sozinho.
    """
    lo, hi = dados.attrs["banda"]
    marca_linha, marca_coluna = dados.attrs["marca"]
    valor_marca = dados.at[marca_linha, marca_coluna]

    cabecalho = (
        '<tr><th></th>'
        f'<th colspan="{len(dados.columns)}" class="n">Total da d\u00edvida, '
        f'R$ bi</th></tr>'
        '<tr><th>% do papel</th>'
        + "".join(f'<th class="n">{_numero_br(c, 0)}</th>'
                  for c in dados.columns)
        + "</tr>")

    linhas = []
    for pct in dados.index:
        classe_tr = ' class="na-banda"' if lo <= pct <= hi else ""
        celulas = []
        for total in dados.columns:
            v = dados.at[pct, total]
            e_marca = pct == marca_linha and total == marca_coluna
            texto = _numero_br(v)
            if v < 0:
                texto = f'<span class="negativo">{texto}</span>'
            # O negativo fica num span DENTRO do TD -- so o numero fica
            # vermelho. A marca fica na classe DO TD, JUNTO com "n" -- sem
            # "n" a unica celula que o bloco existe para apontar seria a
            # unica desalinhada da grade (achado da revisao).
            classe_td = "n marca" if e_marca else "n"
            celulas.append(f'<td class="{classe_td}">{texto}</td>')
        linhas.append(
            f'<tr{classe_tr}><th class="pct">{_numero_br(pct, 0)}%</th>'
            + "".join(celulas) + "</tr>")

    fronteira = dados.attrs.get("fronteira_do_calendario")
    origem = (f", de calend\u00e1rio publicado at\u00e9 "
              f"{fronteira:%d/%m/%Y} e estimado depois"
              if fronteira is not None
              else ", de calend\u00e1rio inteiramente estimado")

    coord_marca = (f"{_numero_br(marca_linha, 0)}% de R$ "
                   f"{_numero_br(marca_coluna, 0)} bi")

    rodape = (
        f"{dados.attrs['rotulo']}: banda de {_numero_br(lo, 0)} a "
        f"{_numero_br(hi, 0)}%, {dados.attrs['leiloes']} leil\u00e3o(\u00f5es) "
        f"at\u00e9 {dados.attrs['ate']:%d/%m/%Y}{origem}. "
        f"Premissa de juros: curva de "
        f"{dados.attrs['data_da_curva']:%d/%m/%Y} (Selic impl\u00edcita "
        f"{_numero_br(100 * dados.attrs['selic'])}% a.a., infla\u00e7\u00e3o "
        f"impl\u00edcita {_numero_br(100 * dados.attrs['inflacao'])}% a.a.). "
        f"A c\u00e9lula destacada \u00e9 a mais pr\u00f3xima do ponto para "
        f"onde o ritmo de hoje leva "
        f"({_numero_br(dados.attrs['projetado_pct'])}% de R$ "
        f"{_numero_br(dados.attrs['projetado_total'], 0)} bi). Ela responde "
        f"por <b>{coord_marca}</b>: R$ {_numero_br(valor_marca)} bi por "
        f"leil\u00e3o \u2014 e <b>n\u00e3o</b> o que se emite hoje, que \u00e9 "
        f"R$ {_numero_br(dados.attrs['ritmo_atual'])} bi por leil\u00e3o. Os "
        f"dois diferem porque a grade arredonda os dois eixos. "
        f"N\u00famero negativo quer dizer que nem parando de emitir se "
        f"chega ao alvo: faltaria resgatar. "
        f"<b>As tr\u00eas tabelas s\u00e3o independentes:</b> cada uma "
        f"responde \u00e0 sua pergunta sozinha, e fazer o que duas delas "
        f"pedem ao mesmo tempo pode n\u00e3o produzir o total escolhido.")

    ident = "simulacao-" + dados.attrs["chave"].replace("_", "-")
    return (f'<div class="simulacao" id="{ident}">'
            f"<h3>{dados.attrs['rotulo']} (R$ bi por leil\u00e3o)</h3>"
            f"<table>{cabecalho}{''.join(linhas)}</table>"
            f'<p class="rodape">{rodape}</p></div>')


_CSS = """
.simulacao { margin: 22px auto 34px; max-width: 1180px; }
.simulacao h3 { font-size: 15px; margin: 0 0 8px; }
.simulacao table { border-collapse: collapse; width: 100%; font-size: 13px; }
.simulacao th, .simulacao td { padding: 5px 9px; text-align: left;
  border-bottom: 1px solid #eee; }
.simulacao th.pct { font-weight: 600; }
.simulacao td.n, .simulacao th.n { text-align: right;
  font-variant-numeric: tabular-nums; }
.simulacao tr.na-banda { background: #f6f8fb; }
.simulacao span.negativo { color: #b03030; }
.simulacao td.marca { outline: 2px solid #2b6cb0; font-weight: 600; }
"""
