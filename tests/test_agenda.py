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
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def comparacao():
    return agenda.ofertado_e_aceito()


def test_a_comparacao_traz_os_ultimos_leiloes_de_CADA_familia(comparacao):
    # POR FAMILIA e nao por data: LFT e NTN-B vao a mercado num dia e o prefixado no
    # outro, entao um corte por data deixaria metade das familias sem linha.
    assert not comparacao.empty
    esperado = list(range(agenda.LEILOES_NA_COMPARACAO))
    for familia, g in comparacao.groupby("familia"):
        assert sorted(g["quantos_atras"]) == esperado, familia
    # E as datas do "ultimo" NAO sao todas iguais, que e o motivo da regra existir.
    ultimos = comparacao[comparacao["quantos_atras"] == 0]
    assert ultimos["data_leilao"].nunique() > 1


def test_a_comparacao_traz_quantidade_alem_do_dv(comparacao):
    # A LFT nao tem DV: a comparacao ofertado/aceito dela so existe em titulos.
    lft = comparacao[comparacao["familia"] == "LFT"]
    assert len(lft) == agenda.LEILOES_NA_COMPARACAO
    assert lft["dv_ofertado"].fillna(0).eq(0).all()
    assert (lft["qtd_ofertada"] > 0).all()
    assert (lft["qtd_aceita"] > 0).all()
    assert lft["colocado_qtd_pct"].notna().all()


def test_o_aceito_nunca_passa_do_ofertado(comparacao):
    com_dv = comparacao[comparacao["dv_ofertado"] > 0]
    assert len(com_dv) > 0
    assert (com_dv["dv_aceito"] <= com_dv["dv_ofertado"] * 1.001).all()


def test_o_grafico_desenha_duas_barras_por_LEILAO(comparacao):
    import matplotlib.pyplot as plt
    from tesouro.graficos import cronograma

    fig, ax = plt.subplots()
    cronograma.desenha_ofertado_e_aceito(comparacao, ax, quantos=6)
    familias = [f for f in cronograma.ORDEM_FAMILIAS
                if f in set(comparacao["familia"])]
    assert len(ax.patches) == 2 * 6 * len(familias)
    plt.close(fig)


def test_a_linha_pontilhada_separa_uma_familia_da_outra(comparacao):
    # Sem ela, vinte e quatro barras deitadas viram um bloco so e nao se ve onde
    # uma familia termina e a outra comeca.
    import matplotlib.pyplot as plt
    from tesouro.graficos import cronograma

    fig, ax = plt.subplots()
    cronograma.desenha_ofertado_e_aceito(comparacao, ax, quantos=6)
    familias = [f for f in cronograma.ORDEM_FAMILIAS
                if f in set(comparacao["familia"])]
    pontilhadas = [l for l in ax.get_lines() if l.get_linestyle() in (":", "dotted")]
    assert len(pontilhadas) == len(familias) - 1
    plt.close(fig)


def test_o_grafico_da_LFT_usa_quantidade_e_escreve_o_financeiro(comparacao):
    # Ela nao tem DV, entao a comparacao e em titulos -- e o financeiro entra como
    # rotulo porque e a grandeza que se compara com o resto do projeto.
    import matplotlib.pyplot as plt
    from tesouro.graficos import cronograma

    fig, ax = plt.subplots()
    cronograma.desenha_quantidade_lft(comparacao, ax, quantos=4)
    assert len(ax.patches) == 2 * 4
    assert "t\u00edtulos" in ax.get_xlabel()
    textos = " ".join(a.get_text() for a in ax.texts)
    assert "R$" in textos and "bi" in textos
    plt.close(fig)


def test_a_LFT_fica_de_fora_do_grafico_de_DV(comparacao):
    # Sem DV por decisao de modelagem: duas barras zeradas ao lado das outras se
    # leriam como "nao colocou nada", que e outra coisa.
    from tesouro.graficos import cronograma

    assert "LFT" in set(comparacao["familia"])
    assert "LFT" not in cronograma.ORDEM_FAMILIAS


def test_cada_linha_traz_a_DATA_e_o_nome_so_no_comeco_do_bloco(comparacao):
    # Vinte e quatro barras de dias diferentes pareceriam do mesmo leilao sem a
    # data. E repetir "NTN-B longa" seis vezes empilhadas e ruido: o nome marca o
    # bloco, a data identifica a linha.
    import matplotlib.pyplot as plt
    from tesouro.graficos import cronograma

    fig, ax = plt.subplots()
    cronograma.desenha_ofertado_e_aceito(comparacao, ax, quantos=6)
    rotulos = [r.get_text() for r in ax.get_yticklabels()]
    familias = [f for f in cronograma.ORDEM_FAMILIAS
                if f in set(comparacao["familia"])]
    assert len(rotulos) == 6 * len(familias)
    # Cada familia aparece UMA vez, na primeira linha do bloco dela.
    for familia in familias:
        assert sum(1 for r in rotulos if r.startswith(familia)) == 1, familia
    # E as datas sao todas diferentes dentro de um bloco.
    assert len({r.strip().split()[-1] for r in rotulos}) > 6
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


def test_a_primeira_linha_de_cada_papel_sai_marcada_como_passado(pagina, comparacao):
    # As duas tabelas tem o mesmo formato; sem a marca elas se parecem demais, e
    # nao fica claro qual e leilao que ja aconteceu.
    familias = comparacao["familia"].nunique()
    assert pagina.count('class="passado"') == familias


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


def test_a_tabela_dos_ultimos_mostra_seis_leiloes_por_papel(pagina, comparacao):
    # Uma linha por (familia, leilao), no mesmo molde da tabela da agenda.
    i = pagina.index('id="tabela-ultimos"')
    j = pagina.index('id="tabela-agenda"')
    so_ultimos = pagina[i:j]
    esperado = len(comparacao[
        comparacao["quantos_atras"] < agenda.LEILOES_NA_COMPARACAO])
    assert so_ultimos.count("<tr") == esperado + 1     # +1 do cabecalho


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
