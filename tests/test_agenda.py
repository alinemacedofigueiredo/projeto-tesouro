"""A agenda de leiloes: o que o Tesouro planeja ofertar, e a pagina que a mostra.

O RISCO DESTA PAGINA E ESPECIFICO, e nao e calcular errado. E o leitor tomar por
previsao uma coisa que nao e. O calendario diz QUAIS benchmarks vao a mercado; a
quantidade so sai no edital das 10h30 do proprio dia.

Entao os testes cobrem, alem dos numeros, as MARCAS que impedem essa leitura: a
hachura da barra suposta, o aviso da taxa velha, e o texto que diz de onde vem cada
coisa.

Nao tocam a rede: rodam contra a amostra congelada em tests/fixtures/api_leiloes/.
"""
import json
import pathlib

import matplotlib
matplotlib.use("Agg")
import pandas as pd
import pytest

from tesouro import agenda, config
from tesouro.graficos import cronograma, painel_agenda

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "api_leiloes"

# O calendario congelado vai de 20/08 a 29/09/2026; um "hoje" fixo mantem o teste
# igual amanha. Data movel em teste e teste que quebra sozinho num dia qualquer.
HOJE = "2026-08-21"


@pytest.fixture(scope="module")
def registros():
    return json.loads((FIXTURES / "calendario.json").read_text(
        encoding="utf-8"))["registros"]


@pytest.fixture(scope="module")
def dados(registros):
    return agenda.proximos(registros=registros, hoje=HOJE)


# --------------------------------------------------------------------------
# Os dados
# --------------------------------------------------------------------------

def test_a_agenda_olha_so_para_a_frente(dados):
    # Leilao que ja aconteceu nao e agenda: ele esta na pagina de emissoes, com
    # numero de verdade. Mistura-los daria duas versoes do mesmo dia.
    assert len(dados) > 0
    assert (dados["data_leilao"] >= pd.Timestamp(HOJE)).all()


def test_cada_linha_da_agenda_sabe_de_que_leilao_veio_a_taxa(dados):
    # A taxa e sempre a do ULTIMO leilao daquele papel. Sem a data ao lado, nao ha
    # como julgar se ela ainda vale.
    assert dados["taxa_pct"].notna().all()
    assert dados["taxa_de_quando"].notna().all()
    assert (dados["taxa_de_quando"] < dados["data_leilao"]).all()


def test_a_taxa_velha_e_sinalizada(dados):
    # Os 11 bp de erro foram medidos com o leilao anterior em ate 45 dias. Alem
    # disso o mercado ja e outro, e o erro deixa de ser o que esta medido.
    esperado = dados["taxa_dias_de_idade"] > agenda.DIAS_ATE_A_TAXA_ENVELHECER
    assert list(dados["taxa_velha"]) == list(esperado)
    # E o calendario vai longe o bastante para haver ao menos uma.
    assert dados["taxa_velha"].any()


def test_o_dv_unitario_encurta_conforme_o_leilao_se_afasta(dados):
    # O DV01 unitario NAO e constante por papel ao longo da agenda, e nao deveria
    # ser: cada dia de leilao liquida um dia depois, entao o prazo restante encurta
    # e o DV cai em modulo. A primeira versao deste teste exigia constancia e
    # acusou o codigo por um erro que era meu.
    #
    # O que se trava aqui e o SENTIDO: leilao mais tarde, DV menor em modulo. Se
    # crescesse, a precificacao estaria errada de um jeito grosseiro.
    com_dv = dados[dados["dv_unitario"].notna()]
    assert len(com_dv) > 0
    repetidos = 0
    for benchmark, g in com_dv.groupby("benchmark"):
        if len(g) < 2:
            continue
        repetidos += 1
        valores = list(g.sort_values("data_leilao")["dv_unitario"])
        assert valores == sorted(valores, reverse=True), benchmark
    assert repetidos > 0, "a agenda precisa repetir algum benchmark"


def test_a_quantidade_nao_entra_no_dv_unitario(dados):
    # O numero mais firme da pagina e o que nao depende de quantidade. Duas linhas
    # do mesmo papel, com ofertas anteriores diferentes, no MESMO dia, teriam de dar
    # o mesmo DV -- e como o calendario nao repete papel no mesmo dia, a checagem e
    # pela formula: o DV nao muda quando a oferta muda.
    from tesouro import agenda as mod

    uma = dados[dados["dv_unitario"].notna()].iloc[[0]].copy()
    esperado = float(uma.iloc[0]["dv_unitario"])
    uma["oferta_anterior_qtd"] = uma["oferta_anterior_qtd"] * 1000
    assert mod._dv_unitario(uma)[0] == pytest.approx(esperado)


def test_o_dv_unitario_e_POSITIVO_e_cresce_com_o_vertice(dados):
    # Convencao de RISCO EMITIDO (docs/convencoes-dv.md): positivo e o Tesouro
    # emitindo. A mesma do dv_emitido_por_leilao.csv -- se as duas divergissem, o
    # numero da agenda e o do historico teriam sinais diferentes na mesma tela.
    com_dv = dados[dados["dv_unitario"].notna()].drop_duplicates("benchmark")
    assert (com_dv["dv_unitario"] > 0).all()

    # E cresce com o prazo. Se nao crescesse, a precificacao estaria errada de um
    # jeito grosseiro.
    ntnb = com_dv[com_dv["titulo"] == "NTN-B"].sort_values("vertice_anos")
    valores = list(ntnb["dv_unitario"])
    assert valores == sorted(valores)


def test_a_lft_entra_na_agenda_mas_sem_dv(dados):
    # Sem DV por DECISAO DE MODELAGEM (premissa de duration zero, entrega 2), e nao
    # por falha de calculo: ela aparece no cronograma, que e sobre o que vai a
    # mercado, e nao na conta de risco.
    from tesouro import leiloes_dv

    lft = dados[dados["titulo"] == "LFT"]
    assert len(lft) > 0
    assert lft["dv_unitario"].isna().all()

    # A DECISAO ESTA DECLARADA em SEM_DV, e e o que este teste trava. Quebrar a
    # guarda em agenda._dv_unitario NAO faz o teste falhar, e isso e um fato sobre o
    # projeto e nao um descuido: precificacao.dv ja devolve None para LFT sozinha.
    # A guarda daqui e cinto e suspensorio -- dizer isso e melhor que fingir que ela
    # protege alguma coisa.
    assert "LFT" in leiloes_dv.SEM_DV


def test_o_dv_se_repetir_e_o_produto_declarado(dados):
    # Nao e previsao, e uma multiplicacao -- e o teste diz por qual numero.
    com = dados[dados["dv_unitario"].notna()
                & dados["oferta_anterior_qtd"].notna()]
    assert len(com) > 0
    esperado = com["dv_unitario"] * com["oferta_anterior_qtd"] / 1e6
    assert com["dv_se_repetir"].round(9).equals(esperado.round(9))


def test_a_familia_da_ntnb_usa_o_vertice_do_benchmark(dados):
    # A mesma regra dos graficos de emissao, e vinda da mesma fonte: o rotulo do
    # Tesouro. Se as duas paginas classificassem diferente, a mesma NTN-B apareceria
    # como curta numa e longa na outra.
    ntnb = dados[dados["titulo"] == "NTN-B"]
    curta = ntnb[ntnb["familia"] == "NTN-B curta"]
    longa = ntnb[ntnb["familia"] == "NTN-B longa"]
    assert len(curta) > 0 and len(longa) > 0
    assert (curta["vertice_anos"] <= 5).all()
    assert (longa["vertice_anos"] > 5).all()


def test_a_liquidacao_suposta_e_o_proximo_dia_util(dados):
    # D+1 pelo calendario de feriados do projeto, e nao pela data do leilao
    # anterior: o DV varia com o prazo restante, e uma data velha o mediria no dia
    # errado.
    from tesouro import calendario

    cal = calendario.padrao()
    dia = pd.Timestamp("2026-09-03")
    assert agenda._proximo_util(cal, dia) == cal.mover(dia.date(), 1)


def test_por_dia_soma_o_dia_e_marca_a_taxa_velha(dados):
    por_dia = agenda.por_dia(dados)
    assert len(por_dia) == dados["data_leilao"].nunique()
    assert por_dia["papeis"].sum() == len(dados)
    assert por_dia["alguma_taxa_velha"].any()


# --------------------------------------------------------------------------
# O desenho
#
# Os TRES graficos anteriores -- cronograma de pontos, DV por titulo, e "DV se
# repetir a ultima oferta" -- foram recusados na revisao de 20/08/2026 e sairam
# junto com os testes deles. O que entrou responde uma pergunta que nenhuma
# outra pagina responde: ele nao conseguiu colocar, ou nao quis?
#
# E os "ultimos seis" sao seis PREGOES, e nao seis de cada papel. A versao por
# familia cobria periodos diferentes em cada bloco e nao permitia somar o dia --
# que e justamente a leitura que interessa.
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def por_dia():
    return agenda.ultimos_dias()


@pytest.fixture(scope="module")
def lft():
    return agenda.ultimos_de("LFT")


def test_os_ultimos_leiloes_sao_PREGOES_e_nao_seis_de_cada_papel(por_dia):
    # O DEFEITO QUE ISTO CONSERTA: contando por familia, o grafico mostrava vinte e
    # quatro linhas cobrindo periodos diferentes em cada bloco -- de 14/07 a 20/08 no
    # prefixado e de 14/07 a 18/08 na NTN-B -- e nao dava para somar o dia.
    assert not por_dia.empty
    assert por_dia["data_leilao"].nunique() == agenda.LEILOES_NA_COMPARACAO
    # Varias familias por leilao, e nem toda familia em todo leilao: LFT e NTN-B vao
    # a mercado num dia e o prefixado no outro.
    por_leilao = por_dia.groupby("data_leilao")["familia"].nunique()
    assert por_leilao.min() >= 2
    assert por_dia.groupby("familia")["data_leilao"].nunique().min() < len(por_leilao)


def test_quantos_atras_numera_os_leiloes_do_mais_recente(por_dia):
    ordem = por_dia.drop_duplicates("data_leilao").sort_values("quantos_atras")
    assert list(ordem["quantos_atras"]) == list(range(len(ordem)))
    # 0 e o mais recente.
    assert ordem.iloc[0]["data_leilao"] == por_dia["data_leilao"].max()


def test_o_total_do_dia_e_a_soma_das_familias(por_dia):
    # E o numero que ela pediu: quanto risco entrou no mercado naquele leilao. Com a
    # barra empilhada, nenhuma fatia sozinha o mostra.
    total = agenda.total_por_dia(por_dia)
    assert len(total) == por_dia["data_leilao"].nunique()
    for _, r in total.iterrows():
        do_dia = por_dia[por_dia["data_leilao"] == r["data_leilao"]]
        assert r["dv_aceito"] == pytest.approx(do_dia["dv_aceito"].sum())
        assert r["dv_ofertado"] == pytest.approx(do_dia["dv_ofertado"].sum())
        assert r["papeis"] == do_dia["papeis"].sum()


def test_o_aceito_nunca_passa_do_ofertado(por_dia):
    com_dv = por_dia[por_dia["dv_ofertado"] > 0]
    assert len(com_dv) > 0
    assert (com_dv["dv_aceito"] <= com_dv["dv_ofertado"] * 1.001).all()


def test_o_grafico_desenha_uma_linha_por_LEILAO(por_dia):
    import matplotlib.pyplot as plt
    from tesouro.graficos import cronograma

    fig, ax = plt.subplots()
    cronograma.desenha_ofertado_e_aceito(por_dia, ax)
    rotulos = [r.get_text() for r in ax.get_yticklabels()]
    assert len(rotulos) == por_dia["data_leilao"].nunique()
    assert len(set(rotulos)) == len(rotulos), "datas repetidas no eixo"
    plt.close(fig)


def test_a_barra_do_leilao_vem_EMPILHADA_por_papel(por_dia):
    # Sem empilhar, a soma do dia apagaria a composicao: num dia de prefixado a LTN
    # e a NTN-F somam, e saber qual das duas pesou e metade da leitura.
    import matplotlib.pyplot as plt
    from tesouro.graficos import cronograma

    fig, ax = plt.subplots()
    cronograma.desenha_ofertado_e_aceito(por_dia, ax)
    familias = [f for f in cronograma.FAMILIAS_COM_DV
                if f in set(por_dia["familia"])]
    dias = por_dia["data_leilao"].nunique()
    # Duas barras (ofertado e aceito) por familia por dia -- as vazias tambem sao
    # desenhadas, com comprimento zero, e e isso que mantem a pilha alinhada.
    assert len(ax.patches) == 2 * dias * len(familias)
    plt.close(fig)


def test_a_LFT_fica_de_fora_do_grafico_de_DV(por_dia):
    # Sem DV por decisao de modelagem: uma fatia de espessura zero dentro da pilha
    # nao se distingue de ausencia.
    from tesouro.graficos import cronograma

    assert "LFT" in set(por_dia["familia"])
    assert "LFT" not in cronograma.FAMILIAS_COM_DV


def test_o_grafico_da_LFT_usa_quantidade_e_escreve_o_financeiro(lft):
    # Ela nao tem DV, entao a comparacao e em titulos -- e o financeiro entra como
    # rotulo porque e a grandeza que se compara com o resto do projeto.
    import matplotlib.pyplot as plt
    from tesouro.graficos import cronograma

    assert len(lft) == agenda.LEILOES_DA_LFT
    fig, ax = plt.subplots()
    cronograma.desenha_quantidade_lft(lft, ax)
    assert len(ax.patches) == 2 * agenda.LEILOES_DA_LFT
    assert "t\u00edtulos" in ax.get_xlabel()
    textos = " ".join(a.get_text() for a in ax.texts)
    assert "R$" in textos and "bi" in textos
    plt.close(fig)


# --------------------------------------------------------------------------
# A pagina
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def pagina(tmp_path_factory, registros, monkeypatch_module):
    destino = tmp_path_factory.mktemp("agenda") / "agenda.html"
    return painel_agenda.grava(destino, hoje=HOJE).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def monkeypatch_module():
    from _pytest.monkeypatch import MonkeyPatch

    mp = MonkeyPatch()
    yield mp
    mp.undo()


def test_a_pagina_traz_os_dois_graficos_e_as_duas_tabelas(pagina):
    for g in painel_agenda.REGISTRO:
        assert f'id="{g.id}"' in pagina, g.id
    assert pagina.count("<section") == 2
    assert 'id="tabela-ultimos"' in pagina
    assert 'id="tabela-agenda"' in pagina


def test_a_tabela_dos_ultimos_e_RECOLHIVEL_e_vem_antes_do_calendario(pagina):
    # Ela e referencia -- "o que aconteceu" -- e nao o assunto da pagina, que e "o
    # que vem". Aberta, empurraria a agenda para baixo da dobra.
    assert '<details id="tabela-ultimos"' in pagina
    assert "<summary>" in pagina
    assert pagina.index('id="tabela-ultimos"') < pagina.index('id="tabela-agenda"')


def test_a_linha_do_LEILAO_sai_marcada_e_traz_o_total(pagina, por_dia):
    # As duas tabelas tem o mesmo formato; sem a marca elas se parecem demais, e
    # nao fica claro qual e leilao que ja aconteceu. E a linha marcada traz o TOTAL
    # do dia, que e o numero que a abertura por papel sozinha nao da.
    assert pagina.count('class="passado"') == por_dia["data_leilao"].nunique()
    assert "o leil\u00e3o todo" in pagina


def test_a_pagina_diz_que_a_quantidade_nao_esta_no_calendario(pagina):
    # O texto que impede a leitura errada da TABELA da agenda: ela e o que vem pela
    # frente, e o calendario nao traz quantidade.
    assert "n\u00e3o est\u00e1 no calend\u00e1rio" in pagina
    assert "10h30" in pagina


def test_a_tabela_dos_ultimos_separa_ofertado_de_aceito(pagina):
    # A pergunta da pagina inteira. Sem as duas colunas, so da para ver o que ele
    # colocou -- e nao o que tentou colocar.
    assert "DV01 ofertado" in pagina
    assert "DV01 aceito" in pagina
    assert "colocou" in pagina
    # E o DV por TITULO saiu da tabela da agenda: o unitario e propriedade do papel
    # e nao diz nada sobre o tamanho do leilao.
    assert "DV01 por t\u00edtulo" not in pagina


def test_a_tabela_dos_ultimos_desce_ao_nivel_de_PAPEL_E_VENCIMENTO(pagina):
    # MESMO FORMATO da tabela da agenda, de proposito: as duas respondem a mesma
    # pergunta em tempos diferentes -- o que vem e o que veio -- e ler as duas exige
    # que as colunas estejam no mesmo lugar. A versao anterior parava na familia, e
    # ai nao dava para ver que dentro de "NTN-B longa" o corte foi num vencimento so.
    detalhe = agenda.ultimos_leiloes()
    i = pagina.index('id="tabela-ultimos"')
    j = pagina.index('id="tabela-agenda"')
    so_ultimos = pagina[i:j]

    leiloes = detalhe["data_leilao"].nunique()
    # Uma linha de soma por leilao, mais uma por papel-vencimento, mais o cabecalho.
    assert so_ultimos.count("<tr") == leiloes + len(detalhe) + 1
    # E as colunas sao as mesmas da agenda, na mesma ordem.
    for coluna in ("papel", "vencimento", "taxa m\u00e9dia", "ofertou", "aceitou",
                   "DV01 ofertado", "DV01 aceito", "financeiro"):
        assert f">{coluna}<" in so_ultimos, coluna


def test_a_LFT_aparece_na_tabela_sem_DV_mas_com_financeiro(pagina):
    # Ela e mais da metade da emissao: deixa-la de fora esconderia o maior numero
    # do dia. Sem DV01 por decisao de modelagem, com quantidade e financeiro.
    detalhe = agenda.ultimos_leiloes()
    lft = detalhe[detalhe["titulo"] == "LFT"]
    assert len(lft) > 0
    assert lft["dv_aceito"].fillna(0).eq(0).all()
    assert (lft["financeiro_milhoes"] > 0).all()
    assert (lft["qtd_ofertada"] > 0).all()

    i = pagina.index('id="tabela-ultimos"')
    j = pagina.index('id="tabela-agenda"')
    assert "LFT" in pagina[i:j]


def test_a_soma_do_leilao_inclui_a_LFT_no_financeiro(pagina):
    # O DV do dia soma so quem tem DV; o financeiro soma TODOS. Se a LFT ficasse de
    # fora do financeiro, o total do dia sairia ate tres vezes menor -- em 18/08 ela
    # e 29,3 dos 34,5 bilhoes.
    detalhe = agenda.ultimos_leiloes()
    total = agenda.total_dos_leiloes(detalhe)
    for _, r in total.iterrows():
        do_dia = detalhe[detalhe["data_leilao"] == r["data_leilao"]]
        assert r["financeiro_milhoes"] == pytest.approx(
            do_dia["financeiro_milhoes"].sum())
        assert r["dv_aceito"] == pytest.approx(do_dia["dv_aceito"].sum())


def test_a_taxa_da_tabela_e_ponderada_pelo_financeiro(pagina):
    # A media simples trataria um lote de 100 milhoes e um de 10 bilhoes como
    # iguais, o que nao descreve leilao nenhum.
    detalhe = agenda.ultimos_leiloes()
    com_taxa = detalhe[detalhe["taxa_media_pct"].notna()]
    assert len(com_taxa) > 0
    # Faixa de percentual, nunca de fracao: 0,0702 no lugar de 7,02 nao levanta
    # nada, so precifica errado.
    prefixados = com_taxa[com_taxa["titulo"] != "LFT"]
    assert (prefixados["taxa_media_pct"] > 1).all()


def test_a_tabela_da_agenda_tem_uma_linha_por_papel_e_um_cabecalho_por_dia(
        pagina, dados):
    # A pagina tem DUAS tabelas agora, entao a contagem e so da agenda: uma linha
    # por papel, mais um cabecalho por dia, mais o do <thead>.
    i = pagina.index('id="tabela-agenda"')
    so_agenda = pagina[i:]
    assert so_agenda.count('<tr class="dia"') == dados["data_leilao"].nunique()
    assert so_agenda.count("<tr") == len(dados) + dados["data_leilao"].nunique() + 1


def test_a_tabela_marca_a_taxa_velha(pagina, dados):
    assert pagina.count("\u26a0") >= int(dados["taxa_velha"].sum())
    assert 'class="velha"' in pagina


def test_a_pagina_nao_tem_referencia_externa(pagina):
    import re

    externos = [m.group(1) for m in
                re.finditer(r'(?:src|href|xlink:href)\s*=\s*"([^"]*)"', pagina)
                if "://" in m.group(1)]
    assert externos == [], externos[:3]
    assert "<link" not in pagina


def test_a_barra_liga_as_paginas_irmas(pagina):
    from tesouro.graficos import dashboard

    assert 'id="paginas"' in pagina
    # Uma marca de pagina atual, e nenhuma a mais: duas confundiriam quem le.
    assert pagina.count('class="atual"') == 1
    for arquivo, _ in dashboard.PAGINAS:
        if arquivo != painel_agenda.ARQUIVO:
            assert f'href="{arquivo}"' in pagina
