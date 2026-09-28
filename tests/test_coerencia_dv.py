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
      LFT    -0,0221%  (controle)
      LTN    +0,0092%  (controle)
      NTN-F  +0,3613%  (diverge)
      NTN-B  +1,9518%  (diverge mais -- cupom mais longo, mais peso de curva)
    """
    e = pd.read_csv(config.PROCESSED_DIR / "estoque_titulos_vencimento.csv",
                     parse_dates=["data"])
    cal = calendario.padrao()
    e["data"] = e["data"].dt.date.map(cal.ultimo_dia_util_do_mes)
    j = p.merge(e[["data", "isin", "financeiro_milhoes"]], on=["data", "isin"],
                how="inner")
    j = j[j["financeiro_calculado_milhoes"].notna()
          & (j["financeiro_milhoes"] > 0)]
    # Sanidade de tamanho, ANCORADA no tamanho do painel, nao numa
    # constante solta: achado da revisao -- ">5000" passava intacto com a
    # juncao feita por DATA LITERAL (sem normalizar para o ultimo dia
    # util), que perde 30,9% do painel (6.074 de 9.366) exatamente pela
    # armadilha que docs/convencoes-dv.md:154-156 manda vigiar. A juncao
    # correta preserva 93,89% do painel (8.794 de 9.366, o mesmo numerador
    # de test_cobertura_de_taxa_bate_com_a_medida_no_estoque, abaixo) --
    # 0.93 deixa uma margem de ~1% sem abrir espaco para a juncao quebrada.
    assert len(j) >= 0.93 * len(p), (
        f"juncao produziu {len(j)} pares de {len(p)} no painel "
        f"({100 * len(j) / len(p):.1f}%) -- esperava pelo menos 93%; "
        f"confira se a normalizacao para o ultimo dia util (nao a data "
        f"literal) foi aplicada nos dois lados antes do merge"
    )

    j = j.copy()
    j["erro_rel"] = (j["financeiro_calculado_milhoes"] / j["financeiro_milhoes"]) - 1
    mediana = j.groupby("titulo")["erro_rel"].median()
    assert set(mediana.index) == {"LFT", "LTN", "NTN-F", "NTN-B"}

    # Controle: sem cupom futuro para a curva "chutar", o erro tem que
    # ficar perto de zero -- e "perto" aqui e apertado, nao frouxo: um
    # erro de 0,24% no controle passaria calado e vale, em 30/06/2026,
    # cerca de R$ 3,0 bilhoes no livro de LTN e R$ 11,0 bilhoes no de LFT
    # (achado da revisao). Os limiares abaixo (6 bp para LFT, 3 bp para
    # LTN) deixam ~2,7x e ~3,3x de folga sobre a mediana medida -- a
    # mesma ordem de folga das faixas de NTN-F/NTN-B logo abaixo, nao as
    # 11x/27x de folga que a primeira versao deste teste deixava passar.
    limites_controle = {"LFT": 0.0006, "LTN": 0.0003}
    for titulo, limite in limites_controle.items():
        assert abs(mediana[titulo]) < limite, (
            f"{titulo} (controle, sem cupom futuro) diverge do financeiro "
            f"do Tesouro em {mediana[titulo]:.4%} na mediana -- deveria "
            f"ficar bem perto de zero. Investigue erro de formula/unidade "
            f"antes de mexer aqui; um erro de fracao de percentual aqui "
            f"vale bilhoes de reais no livro."
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
            "Este teste cruza o PU calculado contra o PX_DIRTY_MID da "
            "Bloomberg (fonte ANDE), e falta data/raw/bloomberg/"
            "bbg_precos_*.csv. Voce exige autorizar cada consulta a "
            "Bloomberg caso a caso, e esta consulta ainda nao foi "
            "autorizada -- este teste nao a fez sozinho. Para habilitar: "
            "autorize a coleta de precos e rode (com o terminal Bloomberg "
            "disponivel)\n\n"
            "  PowerShell:\n"
            '    $env:PYTHONPATH="src"; python -m tesouro.fetch_bloomberg\n\n'
            "  bash:\n"
            "    PYTHONPATH=src python -m tesouro.fetch_bloomberg\n\n"
            "e confirme que o(s) arquivo(s) 'bbg_precos_*.csv' apareceram "
            "em data/raw/bloomberg/ antes de rodar este teste de novo."
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

    # Por titulo, nao um balaio so: docs/convencoes-dv.md:120-121 registra
    # as medianas pre-D+1 POR TITULO (-5 bp em LTN/NTN-F, -1,95 bp em
    # NTN-B). Se so a perna de VNA da NTN-B regredisse para D+0, a metade
    # da amostra (NTN-B e 210 dos 438 pares) ficaria em -1,95 bp e a outra
    # metade perto de zero -- a mediana AGRUPADA aterrissaria perto de
    # zero e passaria, escondendo a regressao. Separado por titulo, isso
    # nao acontece.
    erros_por_titulo = {"NTN-F": [], "LTN": [], "NTN-B": []}
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
        erro_bp = (calc - r.px_dirty_mid) / r.px_dirty_mid * 1e4
        erros_por_titulo[r.titulo].append(erro_bp)

    # Limiar apertado: a validacao a mao de docs/convencoes-dv.md documenta
    # diferenca MAXIMA de 0,0083 bp (ruido de ponto flutuante) nos 438
    # pares, com D+1 aplicado. 0,05 bp deixa ~6x de folga sobre esse maximo
    # -- nao as 60x que um limiar de 0,5 bp deixaria passar.
    # A NTN-B NAO DA PARA CONFERIR AQUI, e isto e achado e nao contorno.
    #
    # Este teste rodou pela primeira vez em 25/08/2026, quando a coleta de
    # preco passou a ser possivel. LTN e NTN-F passaram. A NTN-B saiu com ZERO
    # pares, e a causa e do proprio teste: ele desloca a data para D+1 -- a
    # Bloomberg cota para liquidacao em D+1 -- e busca o VNA nessa data nova.
    # As duas series de VNA que este projeto tem, vna.csv e bbg_vna, sao
    # MENSAIS, em fim de mes. D+1 de um fim de mes e dia 1o do mes seguinte,
    # que nao esta em nenhuma das duas. O `continue` la em cima descarta todas
    # as linhas de NTN-B.
    #
    # Foi escrito no escuro e nunca executado, supondo uma serie DIARIA de VNA
    # que nao existe aqui.
    #
    # DECISAO DELA, ainda pendente, entre:
    #   (a) o teste apropriar o VNA de fim de mes ate D+1 pro rata -- poe um
    #       pedaco da conta DENTRO do teste, e o enfraquece como testemunha
    #       independente;
    #   (b) a NTN-B sair desta comparacao e ficar conferida so contra a API do
    #       Tesouro, onde ja esta com erro maximo de 0,0005% em 434 pares.
    #
    # Ate ela decidir, o que DA para conferir fica conferido: LTN e NTN-F
    # seguem travadas contra a Bloomberg, com o mesmo limiar apertado. Deixar o
    # teste inteiro vermelho treinaria a ignorar vermelho, e apagar o teste
    # perderia a validacao que funciona.
    sem_amostra = [t for t, e in erros_por_titulo.items() if len(e) == 0]
    if sem_amostra:
        assert sem_amostra == ["NTN-B"], (
            f"so a NTN-B e conhecidamente inconferivel aqui (falta VNA em "
            f"D+1); ficaram sem amostra: {sem_amostra}")
        erros_por_titulo = {t: e for t, e in erros_por_titulo.items() if e}

    for titulo, erros in erros_por_titulo.items():
        assert len(erros) > 20, (
            f"{titulo}: amostra pos-filtro pequena demais para valer "
            f"({len(erros)} pares)"
        )
        mediana = pd.Series(erros).median()
        assert abs(mediana) < 0.05, (
            f"{titulo}: PU calculado difere do preco da Bloomberg em "
            f"{mediana:.4f} bp na mediana; com o deslocamento de D+1 isso "
            f"deveria ser perto de zero (maximo documentado: 0,0083 bp). "
            f"Releia docs/convencoes-dv.md antes de mexer na producao."
        )


# ---------------------------------------------------------------------------
# 3. VNA identico entre papeis do mesmo indice, na colheita bruta.
#
# ACHADO DA REVISAO: a primeira versao deste teste rodava contra
# dv.painel(), agrupando por (titulo, data) e conferindo
# groupby("data")["vna"].nunique() == 1. Isso e estruturalmente
# infalsificavel -- dv.py:73-79 monta um dict `vna_por` chaveado por
# (data, indice), SEM ISIN, e atribui o mesmo valor a todo papel do
# titulo naquela data por CONSTRUCAO. O teste so podia dar 1, mutacao
# nenhuma o derruba (confirmado: a troca de _INDICE_DO_TITULO que quebra
# tres outros testes deste arquivo nao move este teste em nada).
#
# O cruzamento de verdade -- papeis cotados de forma INDEPENDENTE pela
# Bloomberg discordando entre si -- mora no arquivo BRUTO da colheita
# (bbg_vna_*.csv), nas colunas n_papeis/divergencia, ANTES do dict de
# dv.py colapsar tudo. Esse cruzamento ja e aplicado em tempo de escrita
# por parse_bloomberg.parse_vna (_TOLERANCIA_DIVERGENCIA) e testado com
# fixture sintetica em tests/test_parse_bloomberg.py -- o que falta, e o
# que este teste cobre, e a mesma verificacao contra o arquivo bruto REAL
# inteiro (nao uma fixture pequena), que e o dado que efetivamente
# alimenta o painel.
# ---------------------------------------------------------------------------

def test_vna_nao_diverge_entre_papeis_na_colheita_bruta():
    """Em 16 das 198 datas de IPCA a colheita bruta so tem 1 papel
    (docs/convencoes-dv.md) -- divergencia zero ali e vacua, e por isso
    essas datas sao excluidas antes de exigir divergencia baixa. As datas
    de SELIC sempre tem 3 ou mais papeis no dado real (nenhuma vacua).
    """
    arquivos = sorted(config.BLOOMBERG_DIR.glob("bbg_vna_*.csv"))
    assert arquivos, "sem bbg_vna_*.csv em data/raw/bloomberg/"
    bruto = pd.concat([pd.read_csv(a) for a in arquivos], ignore_index=True)

    contagem_vacua_esperada = {"IPCA": 16, "SELIC": 0}
    for indice, esperado in contagem_vacua_esperada.items():
        sub = bruto[bruto["indice"] == indice]
        assert len(sub) > 100

        vacuas = (sub["n_papeis"] == 1).sum()
        assert vacuas == esperado, (
            f"{indice}: {vacuas} data(s) com um so papel na colheita "
            f"bruta, esperava exatamente {esperado}. Se esse numero "
            f"mudou, confira antes de so atualizar a constante."
        )

        nao_vacuo = sub[sub["n_papeis"] >= 2]
        assert len(nao_vacuo) > 100, (
            f"{indice}: poucas datas com 2+ papeis para o cruzamento valer"
        )

        # 0,5 real, o mesmo limiar de parse_bloomberg._TOLERANCIA_
        # DIVERGENCIA -- escrito aqui como literal, e nao importado do
        # modulo sob teste, para que uma mudanca de tolerancia na
        # producao nao arraste esta trava junto sem ninguem perceber.
        piores = nao_vacuo[nao_vacuo["divergencia"].abs() > 0.5]
        assert piores.empty, (
            f"{indice}: {len(piores)} data(s) com 2+ papeis onde o VNA "
            f"reportado diverge do implicito nos papeis em mais de "
            f"R$0,50 -- "
            f"{piores[['data', 'n_papeis', 'divergencia']].head(5).to_dict('records')}"
        )


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
    # As 8 linhas ja estao confinadas a uma janela de 2010-02 a 2011-08
    # pelas duas assercoes acima; a ultima data do painel real (2026-06)
    # torna qualquer checagem adicional de "ultimos doze meses" estrita-
    # mente implicada por essa janela (nunca pode falhar) -- removida na
    # revisao por ser assercao morta, e porque a forma original
    # (date(ano - 1, mes, dia)) levantava ValueError sempre que a ultima
    # data do painel caisse em 29 de fevereiro.


# ---------------------------------------------------------------------------
# 7. Cobertura de taxa: fracao dos pares papel-mes do estoque do RMD que
# tem taxa da Bloomberg casada, e a mesma fracao ponderada pelo
# financeiro. Numerador (taxa, Bloomberg) e denominador (estoque, RMD)
# vem de fontes independentes -- e o mesmo cruzamento cuja juncao quebrada
# (por data literal, sem normalizar para o ultimo dia util) faz o teste 1
# perder um terco do painel em silencio (o numerador de ambos e o mesmo
# 8.794). Este teste torna essa fracao um numero visivel e ancorado.
# ---------------------------------------------------------------------------

def test_cobertura_de_taxa_bate_com_a_medida_no_estoque(p):
    """dv.painel() e o estoque em escopo (LTN/NTN-F/NTN-B/LFT com
    quantidade_mil > 0) juntado a ESQUERDA com a taxa -- toda linha do
    painel existe no estoque do RMD, e taxa_pct so esta presente onde a
    Bloomberg casou. A fracao com taxa e a cobertura simples (pares
    papel-mes); ponderada pelo financeiro BRUTO do RMD (nao o
    financeiro_calculado_milhoes, que ja exige taxa por construcao) da a
    cobertura ponderada.

    Se a normalizacao de data quebrar de um dos dois lados (o estoque
    traz o ultimo dia CORRIDO do mes, taxa/vna trazem o ultimo dia UTIL --
    ver docs/convencoes-dv.md), a cobertura simples cai para 0,00%: nenhum
    (data, isin) do estoque casaria mais com nenhum (data, isin) da taxa.
    """
    cobertura_simples = 100 * p["taxa_pct"].notna().sum() / len(p)
    assert cobertura_simples == pytest.approx(93.89, abs=0.1), (
        f"cobertura de taxa (pares papel-mes) e {cobertura_simples:.2f}%, "
        f"esperava ~93,89%. Se caiu para perto de zero, a juncao de data "
        f"entre taxa_por_papel.csv e estoque_titulos_vencimento.csv "
        f"provavelmente parou de normalizar para o ultimo dia util de um "
        f"dos dois lados."
    )

    cal = calendario.padrao()
    e = pd.read_csv(config.PROCESSED_DIR / "estoque_titulos_vencimento.csv",
                     parse_dates=["data"])
    e["data"] = e["data"].dt.date.map(cal.ultimo_dia_util_do_mes)
    e = e[(e["quantidade_mil"].fillna(0) > 0) & e["titulo"].isin(dv.TITULOS)]

    j = p.merge(e[["data", "isin", "financeiro_milhoes"]], on=["data", "isin"],
                how="left")
    assert len(j) == len(p)  # o painel INTEIRO tem que casar com o estoque

    peso_total = j["financeiro_milhoes"].sum()
    peso_com_taxa = j.loc[j["taxa_pct"].notna(), "financeiro_milhoes"].sum()
    cobertura_ponderada = 100 * peso_com_taxa / peso_total
    assert cobertura_ponderada == pytest.approx(99.23, abs=0.1), (
        f"cobertura de taxa ponderada pelo financeiro e "
        f"{cobertura_ponderada:.2f}%, esperava ~99,23%"
    )


# --------------------------------------------------------------------------
# NTN-B ate 10 anos e longa: a fronteira e medida no VERTICE do Tesouro, e nao no
# prazo calculado. Decidido em 20/08/2026, quando a API publicou a tabela de
# benchmarks vigentes.
# --------------------------------------------------------------------------

def test_a_familia_da_ntnb_vem_do_vertice_e_nao_do_prazo():
    # O CASO QUE MOTIVA A REGRA: um papel que o Tesouro chama de "NTN-B 10 anos"
    # e que, no comeco da vigencia do benchmark, ainda tem mais de 10 anos a
    # correr. Pelo prazo ele cairia na faixa de cima; pelo rotulo dele, nao --
    # e trocar de faixa no meio da vigencia produziria um degrau no grafico que
    # nao aconteceu no mundo.
    #
    # LE A CONSTANTE, e nao escreve o numero. Em 25/09/2026 ela mudou o corte de
    # 5 para 10 anos e estas assercoes ficaram vermelhas sem ter nada a ver com
    # o assunto delas -- amarra no lugar errado. Assim o proximo corte e mesmo
    # uma linha so.
    from tesouro import leiloes_dv

    corte = leiloes_dv.CORTE_NTNB_ANOS
    dentro = leiloes_dv.FAMILIA_NTNB_CURTA
    fora = leiloes_dv.FAMILIA_NTNB_LONGA

    # O vertice manda, mesmo quando o prazo discorda: prazo acima do corte,
    # vertice no corte.
    assert leiloes_dv._familia("NTN-B", corte + 1.4, corte) == dentro
    # E discordando para o outro lado: prazo abaixo, vertice acima.
    assert leiloes_dv._familia("NTN-B", corte - 0.1, corte + 5) == fora
    # A fronteira e INCLUSIVA: o vertice que o Tesouro chama de N anos, com o
    # corte em N, fica na faixa de baixo.
    assert leiloes_dv._familia("NTN-B", float(corte), float(corte)) == dentro


def test_sem_vertice_a_familia_cai_no_prazo():
    # Leilao antigo, sem rotulo publicado. O prazo e a melhor aproximacao
    # disponivel, e qual dos dois criterios valeu fica no CSV, que carrega os dois.
    from tesouro import leiloes_dv

    assert leiloes_dv._familia("NTN-B", 4.0, None) == "NTN-B at\u00e9 10 anos"
    assert leiloes_dv._familia("NTN-B", 12.0, None) == "NTN-B acima de 10 anos"


def test_os_demais_papeis_nao_se_partem():
    from tesouro import leiloes_dv

    for titulo in ("LTN", "NTN-F", "LFT"):
        assert leiloes_dv._familia(titulo, 6.4, 5.0) == titulo


def test_a_troca_de_criterio_move_volume_de_verdade():
    # A DIFERENCA NAO E COSMETICA, e este teste trava o tamanho dela: classificar
    # pelo vertice em vez do prazo move ~10% dos leiloes de NTN-B de faixa, todos
    # com vertice 5 e prazo acima de 5 anos. Se este numero cair para zero, alguem
    # desfez a regra sem querer.
    import pandas as pd
    from tesouro import config

    d = pd.read_csv(config.PROCESSED_DIR / "dv_emitido_por_leilao.csv")
    b = d[d["titulo"] == "NTN-B"]
    por_prazo = b["prazo_anos"] <= 5
    por_vertice = b["vertice_anos"].fillna(99) <= 5
    mudam = (por_prazo != por_vertice).sum()

    assert mudam > 300, "a classificacao pelo vertice deixou de mudar alguma coisa"
    # E todas mudam no mesmo sentido: vertice 5, prazo acima de 5.
    diferentes = b[por_prazo != por_vertice]
    assert (diferentes["vertice_anos"] == 5).all()
    assert (diferentes["prazo_anos"] > 5).all()
