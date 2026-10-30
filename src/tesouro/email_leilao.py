"""O e-mail de leilao: os numeros e o HTML, sem mandar nada.

ESTE MODULO NAO ENVIA. Ele monta. Quem manda e outro, e a separacao e de
proposito: montar e deterministico e tem teste; mandar e irreversivel e sai
para fora. Misturar os dois faria com que todo teste do formato corresse o
risco de disparar e-mail para uma lista.

A FORMATACAO FOI FECHADA COM ELA em 27/10/2026, rascunho a rascunho, e as
decisoes que nao se deduzem do codigo estao aqui para nao serem desfeitas por
engano:

  SO 1a VOLTA, em tabela e em grafico. Foi o que fez os numeros baterem com a
    imagem que ela mandou -- com a 2a volta, a NTN-B de 20/10 daria 8,285 bi
    em vez dos 7,855 que o relatorio dela diz. E as 10:45, quando o e-mail
    sai, a 2a volta ainda nem aconteceu.

  DV01 EM R$ MILHOES, com virgula. Ela corrigiu isto: "2,906" na imagem dela e
    milhoes, nao mil. O eixo dos graficos continua em R$ mil por decisao
    anterior e medida (em milhoes as etiquetas de alguns recortes caem todas
    em 0,00); ela viu a diferenca de escala e disse que nao incomoda.

  OFERTADO E ACEITO LADO A LADO, nas duas tabelas. No dia em que sai tudo as
    duas colunas ficam iguais, e isso E a informacao.

  QUANTIDADE EM MILHARES DE TITULOS, como no calendario, e A LINHA DE TOTAL
    SOMA. O % do total e o FINANCEIRO (14,333 de 17,849), e nao a razao das
    quantidades, que daria 91,8%: um titulo de NTN-B valia R$ 4.817 e um de
    LFT R$ 19.986 naquele dia.

  NADA DE TEXTO LONGO embaixo das tabelas -- ela mandou tirar. Embaixo da
    primeira fica so o dolar usado.

  OS DOIS LEILOES ANTERIORES no formato da tabela do calendario, sem
    comparacao nenhuma, com a linha do dia inteiro antes das linhas do papel.

A LFT NAO TEM DV01 por decisao de modelagem da entrega 2, e a celula fica
VAZIA e nao zero: zero seria uma afirmacao sobre o risco dela.
"""
import base64
import datetime as dt
import io

import pandas as pd

from . import agenda as dados_agenda
from . import config, fetch_cambio
from .graficos import dashboard, emissao, estilo

# Quantos leiloes a janela dos graficos mostra, e de quantos e a reta da media.
JANELA = 50

# Quantos leiloes anteriores do mesmo tipo entram na tabela do fim.
ANTERIORES = 2

TIPOS = {
    "ntnb": {
        "rotulo": "NTN-B/LFT",
        "papeis": ("NTN-B", "LFT"),
        # (recorte de emissao.RECORTES, legenda da figura)
        "graficos": (
            ("NTN-B", "NTN-B \u00b7 por dia de leil\u00e3o"),
            ("NTN-B at\u00e9 10 anos", "NTN-B at\u00e9 10 anos"),
            ("NTN-B acima de 10 anos", "NTN-B acima de 10 anos"),
            ("LFT", "LFT \u00b7 s\u00f3 financeiro"),
        ),
    },
    "pre": {
        "rotulo": "LTN/NTN-F",
        "papeis": ("LTN", "NTN-F"),
        "graficos": (
            ("LTN", "LTN \u00b7 por dia de leil\u00e3o"),
            ("NTN-F", "NTN-F \u00b7 por dia de leil\u00e3o"),
            ("LTN + NTN-F", "LTN + NTN-F \u00b7 aberto por papel"),
        ),
    },
}

ESTAGIOS = ("oferta", "resultado")


def tipo_do_dia(data_leilao, base=None):
    """Qual dos dois modelos aquele dia pede, ou None se nao houve leilao.

    O DIA DECIDE, e nao o calendario: um leilao extraordinario -- como os de
    compra de 26 e 27/10/2026 -- nao esta no comunicado trimestral e mesmo
    assim aconteceu.
    """
    d = dados_agenda.ultimos_leiloes(
        60, base=base, com_ofertado=True) if base is None else base
    do_dia = d[d["data_leilao"] == pd.Timestamp(data_leilao)]
    if do_dia.empty:
        return None
    papeis = set(do_dia["titulo"])
    for nome, tipo in TIPOS.items():
        if papeis & set(tipo["papeis"]):
            return nome
    return None


def dados(data_leilao, tipo, estagio="resultado", base=None):
    """Tudo o que o e-mail mostra, ja em numero -- sem uma linha de HTML.

    Separado da montagem de proposito: o teste do NUMERO nao precisa ler
    marcacao, e o teste do FORMATO nao precisa recalcular nada.
    """
    if tipo not in TIPOS:
        raise LookupError("tipo %r nao existe; os que existem: %s"
                          % (tipo, sorted(TIPOS)))
    if estagio not in ESTAGIOS:
        raise LookupError("estagio %r nao existe; os que existem: %s"
                          % (estagio, list(ESTAGIOS)))

    papeis = TIPOS[tipo]["papeis"]
    d = dados_agenda.ultimos_leiloes(
        60, base=base, com_ofertado=(estagio == "oferta"))
    d = d[d["titulo"].isin(papeis)]

    dia = pd.Timestamp(data_leilao)
    do_dia = d[d["data_leilao"] == dia]
    if do_dia.empty:
        raise LookupError(
            "nao ha leilao de %s em %s nos dados; o ultimo e %s"
            % (TIPOS[tipo]["rotulo"], dia.date(),
               d["data_leilao"].max().date() if not d.empty else "nenhum"))

    dolar = fetch_cambio.do_disco(dia.date())
    linhas = [_linha(r, dolar) for _, r in
              do_dia.sort_values(["titulo", "data_vencimento"]).iterrows()]

    return {
        "data_leilao": dia.date(),
        "tipo": tipo,
        "rotulo": TIPOS[tipo]["rotulo"],
        "estagio": estagio,
        "linhas": linhas,
        "total": _total(linhas),
        "dolar": dolar,
        "taxa_suposta": any(x["taxa_suposta"] for x in linhas),
        "anteriores": _anteriores(d, dia),
    }


def _num(valor):
    """float, ou None quando o dado nao existe -- nunca 0,0 por omissao."""
    if valor is None or pd.isna(valor):
        return None
    return float(valor)


def _linha(r, dolar):
    dv_aceito = _num(r.get("dv_aceito"))
    dv_ofertado = _num(r.get("dv_ofertado"))
    fin_aceito = _num(r.get("financeiro_milhoes"))
    fin_ofertado = _num(r.get("financeiro_ofertado_milhoes"))
    return {
        "titulo": r["titulo"],
        "vencimento": r["data_vencimento"].date(),
        "qtd_ofertada": _num(r.get("qtd_ofertada")),
        "qtd_aceita": _num(r.get("qtd_aceita")),
        "pct_aceito": _divide(fin_aceito, fin_ofertado),
        "financeiro_ofertado": fin_ofertado,
        "financeiro_aceito": fin_aceito,
        "taxa": _num(r.get("taxa_media_pct")),
        "dv_ofertado": dv_ofertado,
        "dv_aceito": dv_aceito,
        "dv_aceito_usd": _em_dolar(dv_aceito, dolar),
        "taxa_suposta": bool(r.get("taxa_suposta", False)),
        # O ESTAGIO VIAJA JUNTO porque o laco precisa saber, vertice a
        # vertice, QUAL JA TEM RESULTADO: o e-mail do resultado so sai quando
        # todos os que foram OFERTADOS tiverem saido, e "ofertado" e
        # exatamente o estagio de quem ainda nao tem.
        "estagio": r.get("estagio") or "",
        "colocado": _colocado(r),
    }


def _divide(a, b):
    if a is None or not b:
        return None
    return a / b


def _em_dolar(valor, dolar):
    """O DV01 em USD, ou None quando nao ha dolar guardado daquele dia.

    None E NAO ZERO, e nao a cotacao de hoje: converter um leilao antigo pelo
    dolar de agora e exatamente o que a guarda de fetch_cambio existe para
    impedir. Sem arquivo daquele dia, a coluna fica vazia e o e-mail diz.
    """
    if valor is None or not dolar:
        return None
    return valor / dolar["taxa"]


def _colocado(r):
    """A fracao colocada, pela REGRA DO CALENDARIO: DV quando ha, quantidade
    quando nao ha (LFT). E a mesma de painel_agenda._fracao, e ela fica igual
    de proposito -- as duas tabelas sao lidas lado a lado."""
    valor = _num(r.get("colocado_pct"))
    if valor is None:
        valor = _num(r.get("colocado_qtd_pct"))
    return valor


def _total(linhas):
    def soma(chave):
        valores = [x[chave] for x in linhas if x[chave] is not None]
        return sum(valores) if valores else None

    fin_of, fin_ac = soma("financeiro_ofertado"), soma("financeiro_aceito")
    dv_of, dv_ac = soma("dv_ofertado"), soma("dv_aceito")
    return {
        # A QUANTIDADE SOMA, como no calendario. O % ao lado dela e o
        # FINANCEIRO, e nao a razao das quantidades: ver o cabecalho.
        "qtd_ofertada": soma("qtd_ofertada"),
        "qtd_aceita": soma("qtd_aceita"),
        "pct_aceito": _divide(fin_ac, fin_of),
        "financeiro_ofertado": fin_of,
        "financeiro_aceito": fin_ac,
        "dv_ofertado": dv_of,
        "dv_aceito": dv_ac,
        "dv_aceito_usd": soma("dv_aceito_usd"),
        "pct_dv": _divide(dv_ac, dv_of),
    }


def _anteriores(d, dia, quantos=ANTERIORES):
    """Os N leiloes anteriores do mesmo tipo, no formato do calendario."""
    dias = sorted(x for x in d["data_leilao"].unique() if x < dia)[-quantos:]
    saida = []
    for anterior in reversed(dias):
        g = d[d["data_leilao"] == anterior]
        linhas = [_linha(r, None) for _, r in
                  g.sort_values(["titulo", "data_vencimento"]).iterrows()]
        total = _total(linhas)
        total["colocado"] = (total["pct_dv"] if total["pct_dv"] is not None
                             else _divide(total["qtd_aceita"],
                                          total["qtd_ofertada"]))
        saida.append({"data": pd.Timestamp(anterior).date(),
                      "linhas": linhas, "total": total})
    return saida


# ----------------------------------------------------------------- graficos


def graficos(tipo, estagio="resultado"):
    """Os PNG de cada grafico do modelo, como (legenda, bytes).

    SO 1a VOLTA e COM A RETA DA MEDIA -- as duas decisoes dela. A LFT nao
    recebe a reta: ela nao tem DV01, e o grafico dela ja traz a media MOVEL de
    3 meses, que e outra coisa e tem outro traco.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    janela = estilo.Ultimos(JANELA)
    saida = []
    for recorte, legenda in TIPOS[tipo]["graficos"]:
        fig = dashboard._figura(5.8 if "+" in recorte else 5.6)
        ax = fig.subplots()
        if recorte == "LFT":
            emissao.desenha_lft(emissao.por_dia(recorte, janela, False, False),
                                ax)
        elif "+" in recorte:
            emissao.desenha_dois_eixos_empilhado(
                emissao.por_dia_por_familia(recorte, janela, False, False),
                ax, legenda, media=True)
        else:
            emissao.desenha_dois_eixos(
                emissao.por_dia(recorte, janela, False, False), ax, legenda,
                media=True)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
        plt.close(fig)
        saida.append((legenda, buf.getvalue()))
    return saida


# --------------------------------------------------------------------- HTML
#
# ESTILO EMBUTIDO EM CADA ELEMENTO, e tabela em vez de grid. Nao e desleixo: o
# Outlook desenha HTML com o motor do Word, que ignora folha de estilo e nao
# conhece flex nem grid. O rascunho que ela aprovou usa CSS moderno porque
# nasceu para o navegador; aqui a mesma aparencia tem de sair de atributo em
# atributo, senao a mensagem chega como texto corrido na caixa de quem le.

_FONTE = ("font-family:Segoe UI,Calibri,Arial,sans-serif;"
          "font-size:14px;color:#16191d")
_MONO = "font-family:Consolas,Courier New,monospace"
_LINHA = "#d6dae0"
_REALCE = "#9a3324"
_FRACO = "#5d6673"


def _th(texto, alinha="right"):
    return ('<th style="%s;font-size:10.5px;text-transform:uppercase;'
            'letter-spacing:.06em;color:%s;font-weight:600;text-align:%s;'
            'padding:6px 9px;border-bottom:1.5px solid #16191d">%s</th>'
            % (_FONTE, _FRACO, alinha, texto))


def _td(texto, alinha="right", mono=True, extra=""):
    return ('<td style="%s;%s;text-align:%s;padding:6px 9px;'
            'border-bottom:1px solid %s;white-space:nowrap;%s">%s</td>'
            % (_FONTE, _MONO if mono else "", alinha, _LINHA, extra, texto))


def _pct(valor, baixo=0.95):
    """A fracao em %, vermelha quando NAO saiu quase tudo -- igual ao
    calendario, onde a cor marca o dia em que o Tesouro segurou lote."""
    if valor is None:
        return "&mdash;", ""
    cor = "" if valor > baixo else "color:%s;font-weight:600" % _REALCE
    return estilo.num_br(valor * 100, 0) + "%", cor


def _mil(valor):
    """Quantidade em milhares de titulos, como no calendario."""
    if valor is None:
        return "&mdash;"
    return estilo.num_br(valor / 1000, 0) + " mil"


def _mm(valor, casas=3):
    """DV01 em R$ milhoes. VAZIO e nao zero quando nao ha DV (LFT)."""
    if valor is None or valor == 0:
        return "&mdash;"
    return estilo.num_br(valor, casas)


def _bi(valor, casas=3):
    if valor is None:
        return "&mdash;"
    return estilo.num_br(valor / 1000, casas)


def _taxa(valor):
    if valor is None:
        return "&mdash;"
    return estilo.num_br(valor, 4) + "%"


def assunto(d):
    """A linha de assunto. Ela diz O QUE e DE QUANDO, nesta ordem, porque numa
    caixa cheia o que se le primeiro e o comeco."""
    qual = "Oferta" if d["estagio"] == "oferta" else "Resultado"
    return "Leil\u00e3o %s \u00b7 %s \u00b7 %s" % (
        d["rotulo"], qual, d["data_leilao"].strftime("%d/%m/%Y"))


def _quadros(d):
    """Os tres numeros do topo. Na oferta nao ha aceito, entao sao outros."""
    t = d["total"]
    if d["estagio"] == "oferta":
        itens = [
            ("Financeiro ofertado", _bi(t["financeiro_ofertado"], 2),
             "R$ bi"),
            ("DV01 ofertado", _mm(t["dv_ofertado"]), "R$ mm por ponto-base"),
            ("Resultado", "10:45", "ainda nao saiu"),
        ]
    else:
        pct, _cor = _pct(t["pct_dv"])
        pct_fin, _c2 = _pct(t["pct_aceito"])
        itens = [
            ("Financeiro aceito", _bi(t["financeiro_aceito"], 2),
             "R$ bi, de %s ofertados" % _bi(t["financeiro_ofertado"], 2)),
            # UM "%" SO, e nao dois: estes rotulos sao ARGUMENTO da formatacao
            # la embaixo, nao o formato. Com "%%" o sinal dobrado chegava
            # inteiro na tela -- "%% DV aceito".
            ("% DV aceito", pct,
             "R$ %s de %s mm/bp" % (_mm(t["dv_aceito"]),
                                    _mm(t["dv_ofertado"]))),
            ("% financeiro aceito", pct_fin, d["rotulo"].replace("/", " + ")),
        ]

    celulas = []
    for rotulo, valor, nota in itens:
        celulas.append(
            '<td style="%s;padding:10px 14px;border:1px solid %s;width:33%%;'
            'vertical-align:top">'
            '<div style="font-size:10.5px;text-transform:uppercase;'
            'letter-spacing:.07em;color:%s">%s</div>'
            '<div style="%s;font-size:21px;font-weight:600;padding:2px 0">'
            '%s</div>'
            '<div style="font-size:12px;color:%s">%s</div></td>'
            % (_FONTE, _LINHA, _FRACO, rotulo, _MONO, valor, _FRACO, nota))
    return ('<table cellpadding="0" cellspacing="0" border="0" '
            'style="width:100%%;border-collapse:collapse"><tr>%s</tr></table>'
            % "".join(celulas))


def _tabela_do_dia(d):
    """A tabela principal. Na OFERTA as colunas de aceito nem existem -- e nao
    ficam zeradas: zero se le como "nao colocou nada" quando o certo e "ainda
    nao aconteceu"."""
    oferta = d["estagio"] == "oferta"
    if oferta:
        cabecalho = [("Papel", "left"), ("Vencimento", "left"),
                     ("Qtd ofertada", "right"),
                     ("Oferta<br>R$ bi", "right"),
                     ("Taxa de refer\u00eancia", "right"),
                     ("DV01 ofertado<br>R$ mm/bp", "right")]
    else:
        cabecalho = [("Papel", "left"), ("Vencimento", "left"),
                     ("Qtd ofertada", "right"), ("Qtd aceita", "right"),
                     ("% aceito", "right"),
                     ("Oferta<br>R$ bi", "right"), ("Aceito<br>R$ bi", "right"),
                     ("Taxa aceita", "right"),
                     ("DV01 ofert.<br>R$ mm/bp", "right"),
                     ("DV01 aceito<br>R$ mm/bp", "right"),
                     ("DV01 aceito<br>US$ mm/bp", "right")]

    corpo = []
    for x in d["linhas"] + [_linha_de_total(d)]:
        total = x.get("_total", False)
        borda = ("border-top:1.5px solid #16191d;border-bottom:none;"
                 "font-weight:600" if total else "")
        celulas = [_td(x["titulo"], "left", mono=False, extra=borda),
                   _td("" if total else x["vencimento"].strftime("%d/%m/%Y"),
                       "left", mono=False, extra=borda),
                   _td(_mil(x["qtd_ofertada"]), extra=borda)]
        if oferta:
            celulas += [_td(_bi(x["financeiro_ofertado"]), extra=borda),
                        _td(_taxa(x["taxa"]), extra=borda),
                        _td(_mm(x["dv_ofertado"]), extra=borda)]
        else:
            texto, cor = _pct(x["pct_aceito"])
            celulas += [_td(_mil(x["qtd_aceita"]), extra=borda),
                        _td(texto, extra=borda + ";" + cor),
                        _td(_bi(x["financeiro_ofertado"]), extra=borda),
                        _td(_bi(x["financeiro_aceito"]), extra=borda),
                        _td(_taxa(None if total else x["taxa"]), extra=borda),
                        _td(_mm(x["dv_ofertado"]), extra=borda),
                        _td(_mm(x["dv_aceito"]), extra=borda),
                        _td(_mm(x["dv_aceito_usd"]), extra=borda)]
        corpo.append("<tr>%s</tr>" % "".join(celulas))

    return ('<table cellpadding="0" cellspacing="0" border="0" '
            'style="width:100%%;border-collapse:collapse">'
            "<tr>%s</tr>%s</table>"
            % ("".join(_th(t, a) for t, a in cabecalho), "".join(corpo)))


def _linha_de_total(d):
    t = dict(d["total"])
    t["titulo"] = "Total"
    t["vencimento"] = None
    t["taxa"] = None
    t["_total"] = True
    return t


def _tabela_dos_anteriores(d):
    """Os dois anteriores no FORMATO DO CALENDARIO -- linha do dia inteiro, e
    depois papel a papel. Mesmo formato de proposito: ela le as duas lado a
    lado, e "colocou" aqui segue a regra de la (DV quando ha, quantidade
    quando nao ha)."""
    if not d["anteriores"]:
        return ""
    cabecalho = [("Papel", "left"), ("Vencimento", "left"),
                 ("Taxa m\u00e9dia", "right"), ("Ofertou", "right"),
                 ("Aceitou", "right"),
                 ("DV01 ofertado<br>R$ mm/bp", "right"),
                 ("DV01 aceito<br>R$ mm/bp", "right"),
                 ("Colocou", "right"), ("Financeiro", "right")]
    corpo = []
    for leilao in d["anteriores"]:
        t = leilao["total"]
        texto, cor = _pct(t["colocado"])
        fundo = "background:#f2f3f5;font-weight:600"
        corpo.append(
            "<tr>%s%s%s%s%s%s%s%s</tr>" % (
                ('<td colspan="2" style="%s;padding:6px 9px;%s;'
                 'border-bottom:1px solid %s"><b>%s</b> \u00b7 o leil\u00e3o '
                 'todo</td>'
                 % (_FONTE, fundo, _LINHA,
                    leilao["data"].strftime("%d/%m/%Y"))),
                _td("&mdash;", extra=fundo),
                _td(_mil(t["qtd_ofertada"]), extra=fundo),
                _td(_mil(t["qtd_aceita"]), extra=fundo),
                _td(_mm(t["dv_ofertado"]), extra=fundo),
                _td(_mm(t["dv_aceito"]), extra=fundo),
                _td(texto, extra=fundo + ";" + cor),
                _td(_bi(t["financeiro_aceito"], 2) + " bi", extra=fundo)))
        for x in leilao["linhas"]:
            texto, cor = _pct(x["colocado"])
            corpo.append("<tr>%s</tr>" % "".join([
                _td(x["titulo"], "left", mono=False),
                _td(x["vencimento"].strftime("%d/%m/%Y"), "left", mono=False),
                _td(_taxa(x["taxa"])),
                _td(_mil(x["qtd_ofertada"])),
                _td(_mil(x["qtd_aceita"])),
                _td(_mm(x["dv_ofertado"])),
                _td(_mm(x["dv_aceito"])),
                _td(texto, extra=cor),
                _td(_bi(x["financeiro_aceito"], 2) + " bi")]))

    return ('<table cellpadding="0" cellspacing="0" border="0" '
            'style="width:100%%;border-collapse:collapse">'
            "<tr>%s</tr>%s</table>"
            % ("".join(_th(t, a) for t, a in cabecalho), "".join(corpo)))


def _rodape_do_dolar(d):
    """A unica linha embaixo da primeira tabela -- ela mandou tirar o resto.

    QUANDO NAO HA DOLAR GUARDADO a linha DIZ ISSO, em vez de sumir: uma coluna
    de USD vazia sem explicacao e pior que a ausencia dela.
    """
    dolar = d["dolar"]
    if not dolar:
        return ('D\u00f3lar: <b>n\u00e3o guardado para este dia</b> \u2014 a '
                'coluna em US$ fica vazia.')
    de_quando = dolar.get("data_da_cotacao") or "?"
    try:
        de_quando = dt.date.fromisoformat(de_quando).strftime("%d/%m")
    except (TypeError, ValueError):
        pass
    return "D\u00f3lar: <b>%s de %s = %s</b>." % (
        dolar.get("fonte", "?"), de_quando,
        estilo.num_br(dolar["taxa"], 4))


def _nota_da_taxa_suposta(d):
    """Na OFERTA a taxa nao existe ainda, e o numero que aparece e calculado
    por outra. Isso TEM de estar escrito: um DV01 suposto que nao se anuncia e
    o 'plausivel e errado' deste projeto."""
    if not d["taxa_suposta"]:
        return ""
    return ('<p style="%s;font-size:12px;color:%s;margin:10px 0 0">'
            'A taxa \u00e9 de refer\u00eancia, e n\u00e3o do leil\u00e3o: ele '
            'ainda n\u00e3o aconteceu. O financeiro e o DV01 acima s\u00e3o '
            'calculados por ela, ent\u00e3o s\u00e3o <b>estimativa</b> \u2014 '
            'medido, a taxa do leil\u00e3o anterior erra 11,0 bp na mediana, '
            'o que move o DV01 do lote em 0,55%%.</p>' % (_FONTE, _FRACO))


def _aviso_do_que_faltou(faltando):
    """O bloco que diz, DENTRO do e-mail, quais vertices nao foram puxados.

    REGRA DELA, de 30/10/2026: a oferta sai as 10:05 mesmo incompleta, "e
    avisa dentro do email os papeis que voce nao conseguiu puxar a
    quantidade". DENTRO e a palavra que importa -- um aviso so no log serve a
    quem rodou, e quem recebe e que vai olhar o DV01 e tirar conclusao dele.

    FICA ANTES DA TABELA, e nao depois: depois seria lido tarde demais, por
    quem ja formou opiniao sobre o numero.

    Cor forte e sem meio-termo. Este e o unico lugar do e-mail onde o projeto
    admite que o numero ao lado esta incompleto, e um aviso discreto aqui
    seria pior que nenhum.
    """
    if not faltando:
        return ""
    linhas = "".join(
        "<li style=\"padding:1px 0\">%s &middot; vencimento %s</li>"
        % (titulo, dt.date.fromisoformat(vencimento).strftime("%d/%m/%Y"))
        for titulo, vencimento in sorted(faltando))
    return (
        '<div style="%s;border:1px solid %s;border-left:4px solid %s;'
        'background:#fdf6f4;padding:12px 15px;margin:0 0 18px">'
        '<div style="font-weight:600;color:%s">Faltam %d papel(is) nesta '
        'mensagem</div>'
        '<div style="font-size:13px;padding:4px 0 6px">N\u00e3o consegui puxar '
        'a quantidade ofertada destes v\u00e9rtices at\u00e9 o hor\u00e1rio de envio. '
        '<b>O financeiro e o DV01 abaixo n\u00e3o incluem eles</b>, ent\u00e3o o lote '
        'total do leil\u00e3o \u00e9 maior do que o que aparece aqui.</div>'
        '<ul style="margin:0;padding-left:20px;font-size:13px">%s</ul></div>'
        % (_FONTE, _REALCE, _REALCE, _REALCE, len(faltando), linhas))


def _titulo(texto):
    return ('<h2 style="%s;font-size:16px;font-weight:600;margin:26px 0 10px">'
            "%s</h2>" % (_FONTE, texto))


def html(d, figuras=None, faltando=None):
    """O corpo do e-mail, em HTML, a partir do que dados() devolveu.

    'figuras' sao os PNG ja prontos; None gera na hora. Separado para o teste
    do texto nao pagar o desenho de quatro graficos.
    """
    if figuras is None:
        figuras = graficos(d["tipo"], d["estagio"])

    imagens = []
    for legenda, png in figuras:
        imagens.append(
            '<div style="margin:0 0 18px">'
            '<img src="data:image/png;base64,%s" alt="%s" '
            'style="display:block;width:100%%;max-width:900px;'
            'border:1px solid %s"/>'
            '<div style="%s;font-size:12px;color:%s;padding-top:5px">%s</div>'
            "</div>"
            % (base64.b64encode(png).decode("ascii"), legenda, _LINHA,
               _FONTE, _FRACO, legenda))

    qual = ("Resultado por v\u00e9rtice" if d["estagio"] == "resultado"
            else "Oferta por v\u00e9rtice")
    partes = [
        '<div style="%s;max-width:920px">' % _FONTE,
        # O ASSUNTO REPETIDO NO CORPO, pedido dela em 28/10/2026 ao ver o
        # primeiro e-mail de verdade. Parece redundante com a linha de
        # assunto, e nao e: o corpo viaja sozinho. Encaminhado, colado num
        # chat, ou aberto do arquivo em data/processed, o assunto nao vem
        # junto -- e ai nao ha como saber de que leilao se trata.
        '<div style="%s;font-size:19px;font-weight:600;padding:0 0 14px">'
        "%s</div>" % (_FONTE, assunto(d)),
        # O AVISO VEM ANTES DE QUALQUER NUMERO, inclusive dos quadros do
        # topo. Depois deles seria lido por quem ja formou opiniao sobre o
        # DV01 -- e e exatamente sobre o DV01 que ele avisa.
        _aviso_do_que_faltou(faltando),
        _quadros(d),
        _titulo(qual),
        _tabela_do_dia(d),
        '<p style="%s;font-size:12px;color:%s;margin:8px 0 0">%s</p>'
        % (_FONTE, _FRACO, _rodape_do_dolar(d)),
        _nota_da_taxa_suposta(d),
        _titulo("\u00daltimos %d leil\u00f5es \u00b7 s\u00f3 1a volta" % JANELA),
        "".join(imagens),
    ]
    anteriores = _tabela_dos_anteriores(d)
    if anteriores:
        partes += [_titulo("Os dois leil\u00f5es anteriores"), anteriores]
    partes.append("</div>")
    return "\n".join(partes)


def grava(data_leilao, tipo=None, estagio="resultado", destino=None,
          faltando=None):
    """Monta e grava o e-mail como arquivo. NAO MANDA NADA.

    O arquivo serve a dois caminhos: e o que o modo --ensaio produz em vez de
    enviar, e e o que ela abre para conferir antes de soltar o primeiro.
    """
    tipo = tipo or tipo_do_dia(data_leilao)
    if tipo is None:
        raise LookupError("nao houve leilao em %s" % data_leilao)
    d = dados(data_leilao, tipo, estagio)
    corpo = html(d, faltando=faltando)
    pasta = destino or config.PROCESSED_DIR
    pasta.mkdir(parents=True, exist_ok=True)
    alvo = pasta / ("email-%s-%s-%s.html"
                    % (tipo, estagio, data_leilao.isoformat()))
    pagina = ("<!doctype html><html><head><meta charset=\"utf-8\">"
              "<title>%s</title></head><body style=\"margin:18px\">"
              "%s</body></html>" % (assunto(d), corpo))
    alvo.write_bytes(pagina.encode("utf-8"))
    return alvo, d
