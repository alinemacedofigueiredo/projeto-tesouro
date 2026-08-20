"""Emissao anual por papel, a partir dos leiloes. Grafico CANDIDATO.

A usuaria pediu a composicao da emissao por papel, viu esta versao e preferiu a por
indexador (o grafico principal, no funding.py): pela aba 1.2 a cobertura e 100% da
emissao do RMD, e por aqui vai de 90,5% (2015) a 97,3% (2020). Este ficou
guardado, e a
cobertura de cada ano vai escrita no proprio grafico -- e a razao da recusa, e
esconde-la seria esconder o defeito.

ARMADILHA: o leiloes.csv vai alem do RMD -- tem leilao ate 13/08/2026 enquanto o
RMD para em jun/26. Sem cortar na ultima competencia do RMD, 2026 da cobertura de
120%, comparando oito meses de leilao com seis meses de emissao.
"""

import pandas as pd

from .. import config
from . import estilo

JANELAS = {"5 anos": 5, "completa": None}

ORDEM_PAPEIS = ["LFT", "LTN", "NTN-B", "NTN-F", "NTN-C", "NTN-D"]


def competencias_do_rmd():
    """Primeira e ultima competencia do RMD, e quantos meses cada ano dele tem.

    As DUAS pontas importam, e por muito tempo so a direita foi cortada. Os leiloes
    comecam em 2000 e a emissao do RMD so em nov/2006, entao 2006 saia com cobertura
    de 375% e a nota escrita DENTRO da figura anunciava "54,2% a 375,0%" na janela
    completa -- a mesma armadilha do corte da direita, do outro lado.
    """
    f = pd.read_csv(config.PROCESSED_DIR / "funding_por_indexador.csv",
                    parse_dates=["data"])
    e = f[(f["esfera"] == "DPMFi") & (f["operacao"] == "emissao")]
    meses = e.groupby(e["data"].dt.year)["data"].nunique()
    return e["data"].min(), e["data"].max(), meses


def ultima_competencia_do_rmd():
    """Ultimo mes que o RMD cobre."""
    return competencias_do_rmd()[1]


def dados_emissao_anual_papel(janela=None, anos=12):
    """Composicao da emissao por papel, ano a ano, em percentual.

    'total_milhoes' e o tamanho do ano; 'cobertura_pct' e quanto os leiloes
    representam da emissao que o RMD registra no mesmo ano.

    Tres decisoes que so aparecem no numero:

      - o corte e o agrupamento sao pela LIQUIDACAO, nao pela data do leilao. E
        assim que o RMD conta: um leilao de 30/jun liquida em julho e entra em
        julho la. Medido: agrupando pelo leilao, 2026 fecha 18,6 bi acima da aba
        1.1; pela liquidacao, 1,7 abaixo;
      - o recorte e pelas DUAS pontas da competencia do RMD;
      - 'cobertura_pct' fica VAZIA em ano que o RMD nao cobre inteiro. Comparar doze
        meses de leilao com dois de RMD da 375%, e 375% nao significa nada.

    'janela' segue o contrato dos demais: None, um numero de anos, ou o par
    (de, ate) do --de/--ate.
    """
    primeira, corte, meses_do_rmd = competencias_do_rmd()

    l = pd.read_csv(config.PROCESSED_DIR / "leiloes.csv",
                    parse_dates=["data_leilao", "data_liquidacao"])
    venda = l[(l["tipo_leilao"] == "Venda")
              & (l["data_liquidacao"] >= primeira)
              & (l["data_liquidacao"] <= corte)].copy()
    venda["ano"] = venda["data_liquidacao"].dt.year
    piv = venda.pivot_table(index="ano", columns="titulo",
                            values="financeiro_milhoes", aggfunc="sum").fillna(0.0)
    # O corte de colunas vem DEPOIS do corte de anos, e a ordem importa: a NTN-D
    # nao e emitida desde 2002 e a NTN-C desde 2006. Filtrando antes, as duas
    # sobrevivem como colunas de zero dentro da janela mostrada -- e o desenho
    # quebra procurando cor para um papel que a paleta nao tem.
    if isinstance(janela, tuple):
        de, ate = janela
        piv = piv[(piv.index >= de.year) & (piv.index <= ate.year)]
    else:
        anos = janela if isinstance(janela, int) else anos
        piv = piv[piv.index >= piv.index.max() - anos + 1]
    piv = piv.loc[:, piv.sum() > 0]

    f = pd.read_csv(config.PROCESSED_DIR / "funding_por_indexador.csv",
                    parse_dates=["data"])
    emissao = f[(f["esfera"] == "DPMFi") & (f["operacao"] == "emissao")].copy()
    emissao["ano"] = emissao["data"].dt.year
    do_rmd = emissao.groupby("ano")["valor_milhoes"].sum()

    total = piv.sum(axis=1)
    saida = (piv.div(total, axis=0) * 100)[[p for p in ORDEM_PAPEIS
                                            if p in piv.columns]].copy()
    saida["total_milhoes"] = total
    saida["cobertura_pct"] = total / do_rmd.reindex(total.index) * 100
    incompletos = meses_do_rmd.reindex(saida.index).fillna(0) < 12
    saida.loc[incompletos, "cobertura_pct"] = float("nan")
    return saida


def desenha_emissao_anual_papel(dados, ax, ano_parcial):
    """Barra de 100% por ano, com o total acima e a cobertura escrita embaixo."""
    cols = [c for c in dados.columns
            if c not in ("total_milhoes", "cobertura_pct")]
    base = pd.Series(0.0, index=dados.index)
    for papel in cols:
        ax.bar(dados.index, dados[papel], bottom=base, width=0.72,
               color=estilo.COR[papel], label=papel)
        for x in dados.index:
            altura = dados.loc[x, papel]
            if altura >= 4:
                ax.text(x, base[x] + altura / 2, f"{altura:.0f}", ha="center",
                        va="center", fontsize=8.5, color="white", weight="bold")
        base = base + dados[papel]

    for x in dados.index:
        ax.text(x, 101.5,
                estilo.num_br(dados.loc[x, "total_milhoes"] / 1000, 0) + " bi",
                ha="center", fontsize=8, color="#444444")

    fechados = dados[dados.index != ano_parcial]["cobertura_pct"]
    ax.text(0.5, -0.20,
            "cobertura dos leil\u00f5es sobre a emiss\u00e3o do RMD: "
            + estilo.num_br(fechados.min(), 1) + "% a "
            + estilo.num_br(fechados.max(), 1) + "% nos anos fechados",
            transform=ax.transAxes, ha="center", fontsize=9,
            color=estilo.COR["neutro"])

    ax.set_ylim(0, 108)
    ax.set_xticks(list(dados.index))
    ax.set_xticklabels([str(a) if a != ano_parcial else f"{a}*"
                        for a in dados.index])
    ax.set_ylabel("% do financeiro emitido no ano")
    ax.legend(ncol=len(cols), frameon=False, loc="lower center",
              bbox_to_anchor=(0.5, -0.13))
    ax.grid(axis="y", alpha=0.20)
