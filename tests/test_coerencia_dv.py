"""Cruzamentos entre fontes independentes, para o DV01, decay e resultado.

Testes unitarios verificam que a funcao faz o que o autor achou que ela
fazia. Estes verificam contra numeros que outra pessoa publicou (a aba
2.2 do RMD, a Bloomberg) ou contra uma segunda conta feita por um caminho
diferente dentro do proprio projeto. A camada de dados deste sub-projeto
acumulou nove defeitos silenciosos que nenhum teste unitario pegou -- o
que pegou foi exatamente este tipo de cruzamento.
"""
from datetime import date

import pandas as pd
import pytest
from tesouro import calendario, config, dv, precificacao


@pytest.fixture(scope="module")
def p():
    return dv.painel()


@pytest.fixture(scope="module")
def cal():
    return calendario.padrao()


# ---------------------------------------------------------------------------
# 1. PU x quantidade contra o financeiro publicado na aba 2.2 do RMD.
#
# O mais forte dos cruzamentos, porque a aba 2.2 e uma fonte publicada de
# forma inteiramente independente do motor de precificacao. Responde a
# pergunta que ficou em aberto na spec da camada de dados: o financeiro do
# RMD e marcacao NA CURVA, nao a mercado.
#
# LFT e LTN servem de controle: sao os dois titulos em que o PU nao carrega
# cupom futuro (LFT e pos-fixada; LTN e prefixada sem cupom), entao pouco
# resta para a curva "chutar" -- e de fato os dois batem com o financeiro
# do Tesouro dentro de poucos bp. NTN-F e NTN-B tem cupom semestral, e sao
# exatamente os dois que divergem de forma sistematica e na mesma direcao
# (positiva) -- a assinatura de uma curva diferente da nossa marcacao a
# mercado, nao um erro de formula ou de unidade (que apareceria tambem no
# controle).
# ---------------------------------------------------------------------------

def test_pu_vezes_quantidade_bate_com_o_financeiro_do_tesouro(p):
    """LFT/LTN batem quase exato (controle); NTN-F/NTN-B divergem sistema-
    ticamente -- essa e a evidencia de marcacao na curva no financeiro da
    aba 2.2.

    Faixas medidas nesta sessao (mediana do erro relativo
    financeiro_calculado/financeiro_tesouro - 1):
      LFT    -0,02%  (controle)
      LTN    +0,01%  (controle)
      NTN-F  +0,36%  (diverge)
      NTN-B  +1,95%  (diverge mais -- cupom mais longo, mais peso de curva)
    """
    e = pd.read_csv(config.PROCESSED_DIR / "estoque_titulos_vencimento.csv",
                     parse_dates=["data"])
    cal = calendario.padrao()
    e["data"] = e["data"].dt.date.map(cal.ultimo_dia_util_do_mes)
    j = p.merge(e[["data", "isin", "financeiro_milhoes"]], on=["data", "isin"],
                how="inner")
    j = j[j["financeiro_calculado_milhoes"].notna()
          & (j["financeiro_milhoes"] > 0)]
    # Sanidade de tamanho: se a juncao colapsasse (rotulo repetido, chave
    # errada), sobraria uma fracao minuscula do painel e as medianas abaixo
    # ficariam vazias ou sem sentido, sem erro nenhum.
    assert len(j) > 5000

    j = j.copy()
    j["erro_rel"] = (j["financeiro_calculado_milhoes"] / j["financeiro_milhoes"]) - 1
    mediana = j.groupby("titulo")["erro_rel"].median()
    assert set(mediana.index) == {"LFT", "LTN", "NTN-F", "NTN-B"}

    # Controle: sem cupom futuro para a curva "chutar", o erro tem que
    # ficar perto de zero. Se um dia LFT ou LTN sairem dessa banda, o
    # problema esta na NOSSA formula ou unidade -- nao mexa na tolerancia
    # sem investigar antes.
    for titulo in ("LFT", "LTN"):
        assert abs(mediana[titulo]) < 0.0025, (
            f"{titulo} (controle, sem cupom futuro) diverge do financeiro "
            f"do Tesouro em {mediana[titulo]:.2%} na mediana -- deveria "
            f"ficar perto de zero. Investigue erro de formula/unidade "
            f"antes de mexer aqui."
        )

    # Achado: NTN-F e NTN-B divergem de forma sistematica e POSITIVA, e bem
    # maior que o controle -- marcacao na curva, nao erro de calculo. Se a
    # divergencia sumir ou trocar de sinal, o RMD pode ter mudado de
    # convencao de marcacao; avise a usuaria antes de comemorar.
    assert 0.001 < mediana["NTN-F"] < 0.01, (
        f"NTN-F: mediana do erro relativo e {mediana['NTN-F']:.2%}, fora "
        f"da faixa que evidenciava marcacao na curva (achado da Tarefa 10)"
    )
    assert 0.01 < mediana["NTN-B"] < 0.04, (
        f"NTN-B: mediana do erro relativo e {mediana['NTN-B']:.2%}, fora "
        f"da faixa que evidenciava marcacao na curva (achado da Tarefa 10)"
    )


def test_ntnb_2050_tem_taxa_implicita_cravada_no_financeiro_do_tesouro(p, cal):
    """Evidencia mais direta da marcacao na curva: a taxa que reproduz o
    financeiro/quantidade da NTN-B 15/05/2050 (BRSTNCNTB3D4) fica presa
    entre ~5,3% e ~5,7% por mais de uma decada, enquanto a taxa de
    mercado (marcada a mercado, coluna taxa_pct) varia livremente de
    menos de 4% a mais de 7% no mesmo periodo. Uma curva que nao se move
    com o mercado real e a assinatura de marcacao NA CURVA.

    A taxa implicita e obtida por bissecao sobre precificacao.pu_ntnb --
    nao ha solver de yield no motor de precificacao (nem precisa: o
    projeto so precifica PU a partir de taxa, nunca o inverso).
    """
    ISIN = "BRSTNCNTB3D4"
    e = pd.read_csv(config.PROCESSED_DIR / "estoque_titulos_vencimento.csv",
                     parse_dates=["data"])
    e["data"] = e["data"].dt.date.map(cal.ultimo_dia_util_do_mes)

    linhas = p[(p["isin"] == ISIN) & p["vna"].notna() & p["taxa_pct"].notna()]
    j = linhas.merge(e[["data", "isin", "financeiro_milhoes"]], on=["data", "isin"])
    j = j[j["financeiro_milhoes"] > 0].sort_values("data")
    assert len(j) > 100, "amostra pequena demais para o cruzamento valer"

    def taxa_implicita_pct(row):
        alvo = row["financeiro_milhoes"] / row["quantidade_mil"] * 1000
        lo, hi = -0.10, 0.60
        for _ in range(60):
            mid = (lo + hi) / 2
            pu_mid = precificacao.pu_ntnb(cal, row["data"], row["vencimento"], mid, row["vna"])
            if pu_mid > alvo:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2 * 100

    j = j.copy()
    j["taxa_implicita_pct"] = j.apply(taxa_implicita_pct, axis=1)

    # O mercado real se mexeu bastante -- senao o cruzamento nao provaria
    # nada (uma curva parada bateria com um mercado tambem parado).
    assert j["taxa_pct"].min() < 4.0 and j["taxa_pct"].max() > 7.0, (
        f"mercado variou de {j['taxa_pct'].min():.2f}% a "
        f"{j['taxa_pct'].max():.2f}%; esperava uma banda mais larga para "
        f"o cruzamento fazer sentido"
    )

    # A implicita fica cravada nos ultimos ~12 anos da serie, mesmo com o
    # mercado variando livremente no periodo.
    recentes = j[j["data"] >= date(2014, 1, 1)]
    assert len(recentes) > 100
    assert recentes["taxa_implicita_pct"].min() > 5.2, (
        "taxa implicita da NTN-B 2050 caiu abaixo de 5,2% nos ultimos "
        "anos -- a marcacao na curva pode ter mudado; investigue antes "
        "de relaxar este piso"
    )
    assert recentes["taxa_implicita_pct"].max() < 5.7, (
        "taxa implicita da NTN-B 2050 subiu acima de 5,7% nos ultimos "
        "anos -- a marcacao na curva pode ter mudado; investigue antes "
        "de relaxar este teto"
    )


# ---------------------------------------------------------------------------
# 2. PU calculado contra o PX_DIRTY_MID da Bloomberg, com deslocamento D+1.
#
# Ja validado a mao em 438 pares papel-data (docs/convencoes-dv.md). Este
# teste so pode rodar com bbg_precos_*.csv em disco, e a usuaria exige
# autorizar cada consulta a Bloomberg caso a caso -- ela NAO autorizou
# esta. O teste pula com mensagem explicita em vez de tentar buscar o
# arquivo.
# ---------------------------------------------------------------------------

def test_pu_reproduz_o_preco_da_bloomberg_com_deslocamento_de_d1(cal):
    """A Bloomberg cota para liquidacao em D+1; a producao calcula em D+0
    por decisao (docs/convencoes-dv.md). Este teste aplica o deslocamento
    -- liquidacao em D+1 e, na NTN-B, VNA em D+1 tambem.

    Se este teste falhar, o erro provavel esta AQUI, nao na producao:
    releia docs/convencoes-dv.md antes de tocar em precificacao.py.
    """
    precos_arquivos = sorted(config.BLOOMBERG_DIR.glob("bbg_precos_*.csv"))
    if not precos_arquivos:
        pytest.skip(
            "sem bbg_precos_*.csv em data/raw/bloomberg/: este teste cruza "
            "o PU calculado contra o PX_DIRTY_MID da Bloomberg (fonte "
            "ANDE), e a usuaria exige autorizar cada consulta a Bloomberg "
            "caso a caso -- consulta ainda nao autorizada. Peca a ela para "
            "autorizar e rodar a coleta de precos, e colocar o(s) "
            "arquivo(s) 'bbg_precos_*.csv' em data/raw/bloomberg/ antes de "
            "habilitar este teste."
        )

    taxas_arquivos = sorted(config.BLOOMBERG_DIR.glob("bbg_taxas_*.csv"))
    bruto = pd.concat(
        [pd.read_csv(a, parse_dates=["data", "vencimento"]) for a in taxas_arquivos],
        ignore_index=True,
    )
    bruto["data"] = bruto["data"].dt.date
    bruto["vencimento"] = bruto["vencimento"].dt.date

    vna = pd.read_csv(config.PROCESSED_DIR / "vna.csv", parse_dates=["data"])
    vna["data"] = vna["data"].dt.date
    vna_ipca_por_data = {
        r.data: r.vna for r in vna[vna["indice"] == "IPCA"].itertuples(index=False)
    }

    px = pd.concat(
        [pd.read_csv(a, parse_dates=["data"]) for a in precos_arquivos],
        ignore_index=True,
    )
    px["data"] = px["data"].dt.date

    j = bruto.merge(px[["data", "isin", "px_dirty_mid"]], on=["data", "isin"])
    j = j[j["titulo"].isin(["NTN-F", "LTN", "NTN-B"])]
    assert len(j) > 50, "amostra pequena demais para o cruzamento valer"

    erros = []
    for r in j.itertuples(index=False):
        d1 = cal.mover(r.data, 1)
        venc, taxa = r.vencimento, r.yld_ytm_mid / 100
        if r.titulo == "NTN-F":
            calc = precificacao.pu_ntnf(cal, d1, venc, taxa)
        elif r.titulo == "LTN":
            calc = precificacao.pu_ltn(cal, d1, venc, taxa)
        else:
            vna_d1 = vna_ipca_por_data.get(d1)
            if vna_d1 is None:
                continue
            calc = precificacao.pu_ntnb(cal, d1, venc, taxa, vna_d1)
        erros.append((calc - r.px_dirty_mid) / r.px_dirty_mid * 1e4)

    assert len(erros) > 50, "amostra pos-filtro pequena demais para valer"
    mediana = pd.Series(erros).median()
    assert abs(mediana) < 0.5, (
        f"PU calculado difere do preco da Bloomberg em {mediana:.3f} bp na "
        f"mediana; com o deslocamento de D+1 isso deveria ser perto de "
        f"zero. Releia docs/convencoes-dv.md antes de mexer na producao."
    )


# ---------------------------------------------------------------------------
# 3. VNA identico entre papeis do mesmo indice, na mesma data.
#
# Verificado na coleta (parse_bloomberg.parse_vna): divergencia exatamente
# zero. Cuidado documentado em docs/convencoes-dv.md: em 16 das 198 datas
# de IPCA da colheita bruta ha um so papel, e divergencia zero ali nao
# prova nada. O painel do projeto (agrupado por NTN-B/LFT, nao pelo
# universo IPCA/SELIC inteiro da colheita) sempre tem 2+ ISINs por data --
# confirmamos isso ANTES de exigir VNA unico, para a comparacao nao ser
# vacua sem que ninguem perceba.
# ---------------------------------------------------------------------------

def test_vna_e_o_mesmo_entre_papeis_do_indice(p):
    for titulo in ("NTN-B", "LFT"):
        sub = p[(p["titulo"] == titulo) & p["vna"].notna()]
        por_data = sub.groupby("data")
        n_papeis = por_data["isin"].nunique()
        assert (n_papeis >= 2).all(), (
            f"{titulo} tem data com um so papel no painel; a comparacao de "
            f"VNA ficaria vacua nela (ver docs/convencoes-dv.md sobre as "
            f"16 datas de IPCA com um so papel na colheita bruta)"
        )
        n_vna = por_data["vna"].nunique()
        assert (n_vna == 1).all(), f"{titulo} tem VNA divergente entre papeis na mesma data"


# ---------------------------------------------------------------------------
# 4. DV zero (nao nulo) para papel vencido -- a distincao entre "nao se
# aplica" (None, caso da LFT) e "risco genuinamente nulo" (0.0, papel
# vencido COM taxa conhecida) ja esta travada linha a linha em
# tests/test_dv.py (test_papel_vencido_com_taxa_fica_com_dv_zero_e_nao_none)
# e tests/test_decay.py
# (test_papel_vencido_tem_dv_alvo_zero_quando_o_risco_de_partida_era_conhecido),
# os dois com dado sintetico porque o caso "vencido com taxa conhecida" nao
# ocorre no dado real hoje.
#
# A primeira versao deste teste presumia que papel vencido nunca aparece
# no painel -- premissa falsa: o dado real tem UM caso de estoque
# residual apos o vencimento (BRSTNCNTF071, NTN-F, vencimento 2014-01-01,
# ainda com quantidade_mil > 0 em 2014-01-31). Rodar contra o dado real
# revelou o erro antes que ele virasse uma trava incorreta. O que o dado
# real tem para oferecer e o caso complementar: SEM taxa na data, pu e dv
# ficam vazios (None) -- "nao se aplica" porque o risco de partida nunca
# foi conhecido -- e nao 0.0.
# ---------------------------------------------------------------------------

def test_papel_vencido_residual_sem_taxa_fica_com_dv_vazio_nao_zero(p):
    vencidos = p[p["vencimento"] < p["data"]]
    assert len(vencidos) == 1, (
        f"{len(vencidos)} papel(is) vencido(s) com estoque residual no "
        f"painel; esperava exatamente 1 (BRSTNCNTF071 em 2014-01-31). Se "
        f"esse numero mudou, confira se o caso novo tem taxa conhecida -- "
        f"nesse caso o dv dele deveria ser 0.0, nao vazio -- antes de so "
        f"atualizar esta contagem."
    )
    linha = vencidos.iloc[0]
    assert linha["isin"] == "BRSTNCNTF071"
    assert pd.isna(linha["taxa_pct"])
    assert pd.isna(linha["pu"])
    assert pd.isna(linha["dv_unitario"])


# ---------------------------------------------------------------------------
# 5. Aditividade do decay -- ja travada na Tarefa 6 por identidade
# telescopica exata (tests/test_decay.py,
# test_cada_horizonte_bate_com_a_soma_dos_passos_diarios_equivalentes),
# que e MAIS FORTE do que a comparacao aproximada original: a identidade
# telescopica pega um off-by-one de contagem de dias uteis com folga de
# 760 mil vezes a tolerancia, enquanto a banda de convexidade real (13,6%
# medida no historico) seria larga demais para pegar o mesmo defeito. Nao
# ha nada a acrescentar aqui sem duplicar o que ja existe.
#
# O que se acrescenta e um cruzamento diferente: um horizonte fixo do
# decay (21du) bate com uma reprecificacao direta e independente via
# precificacao.dv, para uma linha real do painel -- pega o erro mais
# grosseiro possivel (horizonte mapeado para o numero errado de dias),
# que um teste de forma nao pegaria porque o resultado continua com a
# cara certa.
# ---------------------------------------------------------------------------

def test_horizonte_de_21du_bate_com_o_recalculo_direto(cal):
    d = dv.decay()
    painel = dv.painel().set_index(["data", "isin"])
    linha = d[(d["horizonte"] == "21du") & d["dv_alvo"].notna()
              & ~d["venceu_no_caminho"]].iloc[0]
    base = painel.loc[(linha["data_base"], linha["isin"])]

    assert cal.du(linha["data_base"], linha["data_alvo"]) == 21

    esperado = precificacao.dv(
        cal, linha["titulo"], linha["data_alvo"], base["vencimento"],
        base["taxa_pct"] / 100, base["vna"],
    ) * base["quantidade_mil"] / 1000
    assert abs(esperado - linha["dv_alvo"]) < 1e-9


# ---------------------------------------------------------------------------
# 6. Invariante das 8 linhas vivas sem pu_fim conhecido.
#
# resultado_mensal() marca "venceu_no_periodo" quando o papel vence entre
# as duas datas, e so ai pu_fim fica vazio por desenho. Ha, porem, 8
# linhas que NAO venceram e mesmo assim ficam sem pu_fim -- o ISIN some
# do painel do mes seguinte sem ter vencido (dado de origem da epoca, nao
# defeito do parser). A usuaria decidiu, no fim da branch, nao mudar o
# schema para distinguir esse caso de "nao se aplica"; este teste existe
# para que a contagem nao cresca em silencio.
# ---------------------------------------------------------------------------

def test_linhas_vivas_sem_pu_fim_sao_exatamente_oito():
    r = dv.resultado_mensal()
    orfas = r[r["pu_ini"].notna() & r["pu_fim"].isna() & ~r["venceu_no_periodo"]]
    assert len(orfas) == 8, (
        f"{len(orfas)} linha(s) viva(s) sem pu_fim, esperava exatamente 8 "
        f"(achado registrado na Tarefa 10); investigue antes de atualizar "
        f"este numero"
    )

    financeiro_milhoes = (orfas["pu_ini"] * orfas["quantidade_mil_ini"] / 1000).sum()
    assert financeiro_milhoes == pytest.approx(291954.8, rel=0.001)

    assert orfas["data_fim"].min() >= date(2010, 2, 1)
    assert orfas["data_fim"].max() <= date(2011, 8, 31)

    ultimo_mes = r["data_fim"].max()
    doze_meses_atras = date(ultimo_mes.year - 1, ultimo_mes.month, ultimo_mes.day)
    assert (orfas["data_fim"] < doze_meses_atras).all(), (
        "alguma das 8 linhas orfas caiu nos ultimos doze meses do painel "
        "-- isso seria uma ausencia recente, nao um problema historico"
    )
