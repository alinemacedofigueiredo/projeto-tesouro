"""Verifica as tabelas de referencia mantidas a mao, em referencia/.

Diferente de data/, que e baixado ou reconstruido, o que esta em referencia/ e
digitado por pessoas ao longo dos anos. Este modulo existe para que um erro de
digitacao falhe ALTO, com a linha e o motivo, em vez de virar um grafico com a
banda errada.

Uso:
    PowerShell:  $env:PYTHONPATH="src"; python -m tesouro.valida_referencia
    bash:        PYTHONPATH=src python -m tesouro.valida_referencia
"""

import sys

import pandas as pd

from . import config

# Os seis que TODO ano do PAF tem. A ausencia de um deles num ano e erro.
INDICADORES = (
    "estoque_bilhoes",
    "prazo_medio_anos",
    "prefixado_pct",
    "indice_precos_pct",
    "taxa_flutuante_pct",
    "cambio_pct",
)

# O setimo, que a planilha do PAF tambem publica e que entrou depois dos seis.
# E OPCIONAL por ano: a aba 5.7 do RMD ja cobre 2003 a 2022, entao aqui so
# precisam entrar os anos que a 5.7 nao alcanca. Exigi-lo em todo ano obrigaria a
# redigitar vinte anos de dado que ja temos por parser -- e o grafico usa as duas
# fontes, com teste conferindo que elas concordam onde as duas tem o ano.
OPCIONAIS = (
    "vincendo_12m_pct",
)

TODOS = INDICADORES + OPCIONAIS

VERSOES = ("original", "revisado")

# Os quatro que particionam a divida: as bandas deles somam perto de 100.
# O estoque e o prazo medio ficam de fora porque nao sao participacao.
_COMPOSICAO = (
    "prefixado_pct",
    "indice_precos_pct",
    "taxa_flutuante_pct",
    "cambio_pct",
)

_COLUNAS = ["ano", "versao", "indicador", "minimo", "maximo", "realizado"]

# Faixas de plausibilidade por indicador. Largas de proposito: pegam erro de
# digitacao (21 virando 210, ou percentual escrito como fracao) sem opinar sobre
# politica de divida.
_FAIXA = {
    "estoque_bilhoes": (100.0, 100000.0),
    "prazo_medio_anos": (1.0, 15.0),
    "prefixado_pct": (0.0, 100.0),
    "indice_precos_pct": (0.0, 100.0),
    "taxa_flutuante_pct": (0.0, 100.0),
    "cambio_pct": (0.0, 100.0),
    "vincendo_12m_pct": (0.0, 100.0),
}


def caminho_paf():
    """Caminho do CSV das bandas do PAF."""
    return config.RAIZ / "referencia" / "paf_bandas.csv"


def _erro(erros, linha, msg):
    # linha + 2: uma pelo cabecalho, outra porque o Excel conta a partir de 1
    erros.append(f"  linha {linha + 2}: {msg}")


def conferir_paf(caminho=None):
    """Devolve a lista de problemas encontrados. Lista vazia significa que passou."""
    caminho = caminho or caminho_paf()
    if not caminho.exists():
        return [f"  arquivo nao encontrado: {caminho}"]

    df = pd.read_csv(caminho)
    erros = []

    faltando = [c for c in _COLUNAS if c not in df.columns]
    if faltando:
        return [f"  colunas ausentes: {faltando}; esperadas {_COLUNAS}"]

    for i, r in df.reset_index(drop=True).iterrows():
        if r["indicador"] not in TODOS:
            _erro(erros, i, f"indicador '{r['indicador']}' nao e um dos nomes fixos: "
                            f"{list(TODOS)}")
            continue
        if r["versao"] not in VERSOES:
            _erro(erros, i, f"versao '{r['versao']}' nao e 'original' nem 'revisado'")
        if pd.isna(r["minimo"]) or pd.isna(r["maximo"]):
            _erro(erros, i, "minimo ou maximo em branco; a banda precisa dos dois")
            continue
        if r["minimo"] > r["maximo"]:
            _erro(erros, i, f"minimo {r['minimo']} maior que maximo {r['maximo']}")
        lo, hi = _FAIXA[r["indicador"]]
        for campo in ("minimo", "maximo", "realizado"):
            v = r[campo]
            if pd.notna(v) and not (lo <= float(v) <= hi):
                _erro(erros, i, f"{campo}={v} fora da faixa plausivel de "
                                f"{r['indicador']} ({lo:g} a {hi:g})")

    dup = df.duplicated(subset=["ano", "versao", "indicador"], keep=False)
    for i in df.reset_index(drop=True).index[dup]:
        r = df.reset_index(drop=True).loc[i]
        _erro(erros, i, f"chave repetida: {r['ano']}/{r['versao']}/{r['indicador']}")

    # So os obrigatorios entram nesta conta: o vincendo pode faltar num ano sem
    # que isso seja erro (ver o comentario em OPCIONAIS).
    for (ano, versao), g in df.groupby(["ano", "versao"]):
        faltam = sorted(set(INDICADORES) - set(g["indicador"]))
        if faltam:
            erros.append(f"  {ano}/{versao}: faltam os indicadores {faltam}")

    # Os quatro indexadores particionam a divida, entao os pontos medios das bandas
    # tem de somar perto de 100. E o unico teste que pega percentual escrito como
    # fracao (0,21 em vez de 21): um limiar de plausibilidade nao pega, porque 0,21
    # esta dentro de "entre 0 e 100".
    for (ano, versao), g in df.groupby(["ano", "versao"]):
        comp = g[g["indicador"].isin(_COMPOSICAO)]
        if len(comp) != len(_COMPOSICAO):
            continue                      # a falta ja foi reportada acima
        meio = ((comp["minimo"] + comp["maximo"]) / 2).sum()
        if not (90.0 <= meio <= 110.0):
            erros.append(
                f"  {ano}/{versao}: os pontos medios das quatro bandas de composicao "
                f"somam {meio:.1f}, e deveriam somar perto de 100. Confira se algum "
                f"percentual foi escrito como fracao (0,21 em vez de 21)"
            )

    # Um ano so pode ter 'revisado' se tiver 'original' -- a revisao substitui algo.
    for ano, g in df.groupby("ano"):
        versoes = set(g["versao"])
        if "revisado" in versoes and "original" not in versoes:
            erros.append(f"  {ano}: tem banda revisada sem a original correspondente")

    # O realizado, quando existe, tem de ser igual nas duas versoes do mesmo ano:
    # a meta muda, o que aconteceu nao.
    for (ano, ind), g in df.groupby(["ano", "indicador"]):
        vals = g["realizado"].dropna().unique()
        if len(vals) > 1:
            erros.append(f"  {ano}/{ind}: realizado difere entre original e revisado "
                         f"({vals}); o que aconteceu e um so")

    return erros


def main(argv=None):
    erros = conferir_paf()
    if erros:
        print(f"referencia/paf_bandas.csv: {len(erros)} problema(s)\n")
        print("\n".join(erros))
        print("\nCorrija e rode de novo. O LEIA-ME.md da pasta explica cada coluna.")
        return 1
    df = pd.read_csv(caminho_paf())
    # So os obrigatorios contam aqui: as linhas do vincendo entram sem realizado
    # de proposito (nenhum realizado deste arquivo e lido), e sem este filtro a
    # mensagem passaria a listar todo ano que tem vincendo como "ainda aberto".
    obrigatorios = df[df["indicador"].isin(INDICADORES)]
    abertos = sorted(obrigatorios[obrigatorios["realizado"].isna()]["ano"].unique())
    print(f"referencia/paf_bandas.csv: ok "
          f"({len(df)} linhas, {df['ano'].min()} a {df['ano'].max()})")
    if abertos:
        print(f"  ano(s) sem realizado, por ainda nao terem fechado: {abertos}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
