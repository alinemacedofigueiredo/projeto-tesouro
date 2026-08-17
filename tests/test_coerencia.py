"""Testes que cruzam tabelas diferentes.

Cada aba do RMD e publicada de forma independente, entao concordancia
entre elas e evidencia forte de que os parsers estao certos -- e
discordancia denuncia erro que nenhum teste unitario pegaria.
"""
from pathlib import Path

import pandas as pd
import pytest
from tesouro import leitura_rmd
from tesouro.parse_rmd import estoque, estoque_vencimento, vencimentos

AMOSTRA = Path(__file__).parent / "fixtures" / "rmd_amostra.xlsx"
RMD_REAL = Path(__file__).parents[1] / "data" / "raw" / "rmd"


@pytest.fixture(scope="module")
def xl():
    return leitura_rmd.abrir(AMOSTRA)


@pytest.fixture(scope="module")
def xl_real():
    """O anexo completo do RMD, quando presente em data/raw/rmd/.

    Alguns cruzamentos so fazem sentido sobre a serie inteira; na amostra
    recortada eles passariam em verde sem verificar nada, que e pior do
    que nao existir.
    """
    if not RMD_REAL.exists() or not list(RMD_REAL.glob("*.xlsx")):
        pytest.skip(
            "teste de integracao: exige o anexo do RMD em data/raw/rmd/ "
            "(veja docs/como-baixar.md)"
        )
    return leitura_rmd.abrir()


def _nivel_agregado(xl, nivel):
    """A linha de total de um nivel da aba 2.1 (sem entidade nem titulo)."""
    df = estoque.parse_dpf(xl)
    linhas = df[
        (df["nivel"] == nivel)
        & df["entidade"].isna()
        & df["titulo"].isna()
    ]
    return linhas.set_index("data")["valor_milhoes"]


def test_composicao_soma_a_dpf_em_poder_do_publico(xl):
    """Soma dos indexadores da 2.4 contra a linha de total da aba 2.1.

    Cruzamento entre abas independentes, e mais forte do que conferir a
    coluna 'Total' da propria 2.4: se o filtro que descarta o derivado em
    parse_composicao parar de casar (o Tesouro renomear 'Total' para
    'Total DPF', por exemplo), o total entra como se fosse indexador e a
    soma dobra. Uma assercao de positividade continuaria verde nesse caso
    -- soma dobrada tambem e positiva -- e composicao_dpf e exatamente a
    serie que a analise compara contra a banda do PAF.
    """
    soma = estoque.parse_composicao(xl).groupby("data")["valor_milhoes"].sum()
    total = _nivel_agregado(xl, "DPF em poder do publico")

    par = pd.DataFrame({"soma": soma, "total": total}).dropna()
    assert len(par) > 10, (
        f"apenas {len(par)} datas em comum entre 2.4 e 2.1; uma das duas "
        f"abas foi lida com as datas erradas"
    )

    relativo = (par["soma"] - par["total"]).abs() / par["total"].abs()
    # Folga de 1e-4: as duas abas arredondam por conta propria. Verificado
    # contra o arquivo real (307 datas, maior desvio 2,5e-5) e contra a
    # amostra (34 datas, 3,1e-16).
    piores = relativo[relativo > 1e-4]
    assert piores.empty, (
        f"{len(piores)} datas em que a soma dos indexadores da 2.4 nao "
        f"fecha com a DPF em poder do publico da 2.1; pior desvio "
        f"relativo {relativo.max():.2e} em {relativo.idxmax()}"
    )


def test_detentores_somam_a_dpmfi(xl_real):
    """Soma dos detentores da 2.7 contra a linha de DPMFi da aba 2.1.

    Roda contra o RMD real: na amostra recortada a 2.7 e a 2.1 nao tem
    nenhuma data em comum, e o teste passaria em verde sem comparar nada
    -- exatamente o defeito que este cruzamento existe para evitar.
    """
    soma = estoque.parse_detentores(xl_real).groupby("data")["valor_milhoes"].sum()
    total = _nivel_agregado(xl_real, "DPMFi")

    par = pd.DataFrame({"soma": soma, "total": total}).dropna()
    assert len(par) > 10, (
        f"apenas {len(par)} datas em comum entre 2.7 e 2.1 no arquivo "
        f"real; uma das duas abas foi lida com as datas erradas"
    )

    relativo = (par["soma"] - par["total"]).abs() / par["total"].abs()
    # Verificado contra o arquivo real: 234 datas, maior desvio 2,0e-6.
    piores = relativo[relativo > 1e-4]
    assert piores.empty, (
        f"{len(piores)} datas em que a soma dos detentores da 2.7 nao "
        f"fecha com a DPMFi da 2.1; pior desvio relativo "
        f"{relativo.max():.2e} em {relativo.idxmax()}"
    )


def test_dpmfi_mais_dpfe_fecha_a_dpf_por_faixa(xl):
    """DPF = DPMFi + DPFe, faixa por faixa, mes a mes.

    A aba 3.1 publica os tres niveis em blocos separados e independentes,
    entao a identidade so fecha se os tres tiverem sido lidos do bloco
    certo. E o cruzamento mais forte que esta aba permite: se os blocos
    tivessem se misturado, ou se um deles tivesse sido lido com as
    colunas deslocadas, a soma nao bateria.
    """
    df = vencimentos.parse_por_faixa(xl)

    # pivot (nao pivot_table): cada (data, faixa, nivel) tem no maximo uma
    # linha, entao nao ha nada a agregar. pivot_table com aggfunc='sum'
    # devolveria 0.0 nos meses em que um nivel inteiro esta ausente (soma
    # de um grupo vazio/todo-NaN e 0.0 em pandas, nao NaN), e o dropna
    # abaixo deixaria de descartar esses meses -- fechando a conta contra
    # um zero disfarcado em vez de contra dado ausente de verdade.
    largo = df.pivot(index=["data", "faixa"], columns="nivel", values="valor_milhoes")
    for coluna in ("DPF", "DPMFi", "DPFe"):
        assert coluna in largo.columns, f"nivel {coluna} ausente"

    # So onde os tres existem: a DPF comeca em Nov/2006 e a DPMFi em 1999.
    completo = largo.dropna(subset=["DPF", "DPMFi", "DPFe"])
    assert len(completo) > 0

    soma = completo["DPMFi"] + completo["DPFe"]
    diferenca = (completo["DPF"] - soma).abs()
    # Folga de 1 por mil: a planilha arredonda os tres blocos por conta.
    tolerancia = completo["DPF"].abs() * 0.001 + 1.0
    piores = diferenca[diferenca > tolerancia]
    assert piores.empty, (
        f"{len(piores)} combinacoes (data, faixa) em que DPMFi + DPFe nao "
        f"fecha a DPF; pior caso: {diferenca.max():.1f}"
    )


def test_estoque_por_vencimento_bate_com_estoque_por_titulo(xl_real):
    """Soma da 2.2 por titulo contra as linhas de titulo da 2.1.

    Esta e a principal defesa do projeto: a 2.2 e a aba mais dificil de
    ler e alimenta o calculo de DV01 inteiro. A 2.1 e independente dela.

    Roda contra o RMD real, nao contra a amostra: no recorte de 30
    colunas a 2.1 cobre Dez/00 em diante e a 2.2 comeca em Jan/10, sem
    nenhum mes em comum -- e a 2.2 fica so com parte do bloco de
    prefixados, entao a soma por titulo nao fecharia de qualquer forma.
    E teste de integracao; pula com mensagem clara se o arquivo faltar.
    """
    detalhe = estoque_vencimento.parse(xl_real)
    # A 2.2 cobre o estoque total da DPMFi (2.1, nivel 'DPMFi'), nao o
    # subconjunto 'em poder do publico' nem o memorando 'DPMFi em poder
    # do Banco Central' que a 2.1 tambem publica com os mesmos titulos
    # (ex.: LFT aparece nos dois). Sem restringir o nivel, set_index
    # abaixo colide as duas linhas de LFT e a comparacao fica ambigua.
    agregado = estoque.parse_dpf(xl_real)
    agregado = agregado[agregado["nivel"] == "DPMFi"]

    datas_comuns = sorted(
        set(detalhe["data"]) & set(agregado["data"])
    )
    assert datas_comuns, (
        "as abas 2.1 e 2.2 do RMD real deveriam ter meses em comum; "
        "se nao tem, um dos dois parsers leu as datas errado"
    )

    data = datas_comuns[-1]
    linhas_agregado = agregado[
        (agregado["data"] == data) & agregado["titulo"].notna()
    ].set_index("titulo")["valor_milhoes"]

    # A 2.1 e mais grossa que a 2.2: 'NTN-B' na 2.1 e a soma de 'NTN-B' e
    # 'NTN-B Principal' na 2.2; 'NTN-B1' na 2.1 e a soma de 'NTN-B1 EducA+'
    # e 'NTN-B1 RendA+' na 2.2; 'LFT' na 2.1 inclui 'LFT-TD1 Reserva' na
    # 2.2. Confirmado contra o arquivo real: a soma dos sub-titulos da 2.2
    # bate com o titulo agregado da 2.1 na casa de 1e-8% (ruido de ponto
    # flutuante), nao os ~4% que apareciam comparando 'NTN-B' contra
    # 'NTN-B' cru -- a 2.2 simplesmente detalha o que a 2.1 agrupa, e as
    # duas abas concordam exatamente uma vez que o agrupamento e desfeito.
    # Sem isso, o teste compara duas definicoes diferentes de 'NTN-B' e
    # acusa divergencia onde nao ha nenhuma.
    titulos_agregado = set(linhas_agregado.index)

    def _titulo_pai(titulo_detalhe):
        candidatos = [
            t for t in titulos_agregado
            if titulo_detalhe == t or titulo_detalhe.startswith(t)
        ]
        return max(candidatos, key=len) if candidatos else titulo_detalhe

    bloco = detalhe[detalhe["data"] == data].copy()
    bloco["titulo_pai"] = bloco["titulo"].map(_titulo_pai)
    soma_detalhe = bloco.groupby("titulo_pai")["financeiro_milhoes"].sum()

    titulos = set(soma_detalhe.index) & set(linhas_agregado.index)
    if not titulos:
        pytest.skip("a amostra nao tem titulos em comum entre as abas")

    for titulo in titulos:
        esperado = linhas_agregado[titulo]
        obtido = soma_detalhe[titulo]
        if pd.isna(esperado) or esperado == 0:
            continue
        # 2% de folga: a 2.2 cobre 'os principais titulos', nao todos.
        assert abs(obtido - esperado) / esperado < 0.02, (
            f"{titulo} em {data}: 2.2 soma {obtido:.0f}, "
            f"2.1 diz {esperado:.0f}"
        )


def test_series_nao_tem_mes_faltando_no_meio(xl):
    """Buraco no meio da serie indica linha ou coluna perdida na leitura."""
    df = estoque.parse_composicao(xl)
    datas = sorted(df["data"].unique())
    if len(datas) < 3:
        pytest.skip("amostra curta demais para checar continuidade")
    periodos = pd.PeriodIndex(pd.to_datetime(datas), freq="M")
    esperado = pd.period_range(periodos.min(), periodos.max(), freq="M")
    faltando = set(esperado) - set(periodos)
    assert not faltando, f"meses ausentes: {sorted(str(p) for p in faltando)}"
