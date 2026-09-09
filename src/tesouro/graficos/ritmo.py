"""A tabela do ritmo: qual pace estamos considerando, e onde ele chega.

E o cabecalho do bloco "Onde fechamos o ano". Aquela tabela responde ONDE
chegamos; esta diz DE QUE RITMO aquilo saiu -- que ate 08/09/2026 so existia
escondido no rodape de cada uma das tres grades da simulacao.

MODULO PROPRIO, e nao mais uma funcao em banda.py, pelo mesmo motivo que a
simulacao virou modulo na entrega passada: aquele arquivo ja esta em 438 linhas
com duas tabelas.

DUAS DECISOES DE HONESTIDADE MORAM AQUI, as duas na linha do total:

1. O RITMO NAO SOMA. 14,43 + 2,04 + 23,02 = 39,49 nao e grandeza nenhuma --
   nao sao os mesmos leiloes, porque cada papel vai a leilao no seu dia. A
   celula fica com travessao. O que soma e o financeiro do periodo (ritmo x
   leiloes), que tem coluna propria.

2. O CAMBIO TEM LINHA, com travessao no ritmo. Ele nao vai a leilao, entao nao
   tem pace; mas sem ele a coluna de percentual fecharia em 96,58% e pareceria
   defeito. Com ele o leitor ve POR QUE fecha em 100.
"""
import pandas as pd

from .. import calendario_leiloes, rolagem
from . import estilo

LINHA_CAMBIO = "C\u00e2mbio"
LINHA_TOTAL = "Total"

# Rotulo e casas decimais de cada coluna, na ordem em que saem na tela.
_COLUNAS = [
    ("ritmo", "Ritmo, R$ bi/leil\u00e3o", 2),
    ("leiloes", "Leil\u00f5es que faltam", 0),
    ("a_emitir", "A emitir at\u00e9 o fim do ano, R$ bi", 1),
    ("pct", "% em 31/12", 2),
    ("estoque", "Estoque em 31/12, R$ bi", 1),
]

_VAZIO = "\u2014"


def dados_ritmo(hoje=None, ate=None, registros=None):
    """As cinco linhas da tabela: tres indexadores, o cambio e o total.

    'registros' e a resposta ja baixada do calendario, como no resto da pagina:
    passar uma lista vazia e o modo offline dos testes, e nao degradacao
    silenciosa -- o rodape passa a dizer que o calendario foi estimado.
    """
    hoje = pd.Timestamp(hoje) if hoje is not None \
        else rolagem.leiloes()["data_liquidacao"].max()
    ate = pd.Timestamp(ate) if ate is not None \
        else pd.Timestamp(f"{hoje.year}-12-31")
    if registros is None:
        from .. import api_leiloes
        registros, _ = api_leiloes.buscar("calendario")

    p = rolagem.projecao(ate, registros=registros, hoje=hoje)
    ritmos = rolagem.pace(hoje)
    dias, fronteira = calendario_leiloes.dias_ate(ate, registros=registros,
                                                  hoje=hoje)
    total = float(p["estoque"].sum()) / 1000

    linhas = {}
    for ind in rolagem.INDEXADORES:
        r = float(ritmos[ind]) / 1000
        quantos = rolagem.leiloes_que_faltam(dias, ind)
        linhas[ind] = {"ritmo": r, "leiloes": float(quantos),
                       "a_emitir": r * quantos,
                       "pct": float(p["percentual"][ind]),
                       "estoque": float(p["estoque"][ind]) / 1000}

    # O CAMBIO SAI DA PROJECAO, e nao de total menos os tres. A subtracao
    # daria o mesmo numero hoje e passaria a mentir no dia em que aparecesse um
    # quarto indexador -- ele entraria no cambio sem nada acusar. Lido direto,
    # um quarto indexador faz o total parar de bater com a soma das linhas, e o
    # teste do estoque fica vermelho.
    cambio = float(p["estoque"][LINHA_CAMBIO]) / 1000
    linhas[LINHA_CAMBIO] = {"ritmo": float("nan"), "leiloes": float("nan"),
                            "a_emitir": float("nan"),
                            "pct": 100 * cambio / total, "estoque": cambio}

    linhas[LINHA_TOTAL] = {
        "ritmo": float("nan"), "leiloes": float("nan"),
        "a_emitir": sum(linhas[i]["a_emitir"] for i in rolagem.INDEXADORES),
        "pct": 100.0, "estoque": total}

    ordem = list(rolagem.INDEXADORES) + [LINHA_CAMBIO, LINHA_TOTAL]
    d = pd.DataFrame.from_dict(linhas, orient="index").loc[ordem]
    d.attrs["hoje"] = hoje
    d.attrs["ate"] = ate
    d.attrs["fronteira_do_calendario"] = fronteira
    d.attrs["leiloes_do_pace"] = rolagem.LEILOES_DO_PACE
    return d


def _celula(valor, casas):
    if pd.isna(valor):
        return _VAZIO
    return estilo.num_br(valor, casas)


def tabela(dados):
    """A tabela do ritmo, em HTML."""
    cabecalho = ('<tr><th></th>'
                 + "".join(f'<th class="n">{rotulo}</th>'
                           for _, rotulo, _ in _COLUNAS)
                 + "</tr>")

    corpo = []
    for nome in dados.index:
        classe = ' class="total"' if nome == LINHA_TOTAL else ""
        celulas = "".join(f'<td class="n">{_celula(dados.at[nome, col], casas)}'
                          f"</td>" for col, _, casas in _COLUNAS)
        corpo.append(f'<tr{classe}><th>{nome}</th>{celulas}</tr>')

    fronteira = dados.attrs.get("fronteira_do_calendario")
    origem = (f"calend\u00e1rio publicado at\u00e9 "
              f"{fronteira:%d/%m/%Y} e estimado depois"
              if fronteira is not None else "calend\u00e1rio inteiramente "
              "estimado")

    rodape = (
        f"O ritmo \u00e9 o financeiro l\u00edquido m\u00e9dio dos "
        f"\u00faltimos {dados.attrs['leiloes_do_pace']} leil\u00f5es de cada "
        f"papel, at\u00e9 {dados.attrs['hoje']:%d/%m/%Y} \u2014 mantido at\u00e9 "
        f"{dados.attrs['ate']:%d/%m/%Y}, com {origem}. "
        f"<b>O total n\u00e3o soma o ritmo:</b> os tr\u00eas papeis v\u00e3o a "
        f"leil\u00e3o em dias diferentes, ent\u00e3o somar R$ por leil\u00e3o "
        f"n\u00e3o produz grandeza nenhuma. O que soma \u00e9 o financeiro do "
        f"per\u00edodo, na coluna do meio. "
        f"<b>O c\u00e2mbio n\u00e3o vai a leil\u00e3o</b>, e por isso entra sem "
        f"ritmo \u2014 ele est\u00e1 aqui para a coluna de percentual fechar "
        f"em 100.")

    return ('<div class="ritmo" id="tabela-ritmo">'
            "<h3>O ritmo considerado</h3>"
            f"<table>{cabecalho}{''.join(corpo)}</table>"
            f'<p class="rodape">{rodape}</p></div>')


_CSS = """
.ritmo { margin: 20px auto 26px; max-width: 1180px; }
.ritmo h3 { font-size: 15px; margin: 0 0 8px; }
.ritmo table { border-collapse: collapse; width: 100%; font-size: 13.5px; }
.ritmo th, .ritmo td { padding: 6px 10px; text-align: left;
  border-bottom: 1px solid #e6e6e6; }
.ritmo td.n, .ritmo th.n { text-align: right;
  font-variant-numeric: tabular-nums; }
.ritmo tr.total th, .ritmo tr.total td { font-weight: 600;
  border-top: 2px solid #ccc; }
"""
