"""A mesclagem entre a planilha (definitiva) e a API (provisoria).

O risco deste modulo nao e calcular errado -- ele nao calcula nada. E duplicar
leilao, ou perder leilao, ou deixar um provisorio no lugar de um definitivo. Os
testes cobrem os tres.
"""
import pandas as pd
import pytest

from tesouro import leiloes_recentes as lr


@pytest.fixture(scope="module")
def base():
    return lr.carregar_base()


def test_a_chave_e_quase_unica_e_as_excecoes_estao_declaradas(base):
    # Sem data_liquidacao a chave colide 12 vezes (29/01/2004 tem o mesmo papel com
    # duas liquidacoes). Com ela, sobram oito -- quatro pares em 12/05/2009, que sao
    # duplicata da propria planilha do Tesouro.
    #
    # O numero e exato de proposito: um limiar frouxo deixaria a nona entrar sem
    # ninguem ver, e uma duplicata nova significa que a planilha mudou de forma.
    duplicadas = base.duplicated(subset=lr.CHAVE, keep=False).sum()
    assert duplicadas == lr.DUPLICATAS_CONHECIDAS_DA_PLANILHA

    repetidas = base[base.duplicated(subset=lr.CHAVE, keep=False)]
    assert set(repetidas["data_leilao"].dt.date.astype(str)) == {"2009-05-12"}


def test_sem_data_liquidacao_a_chave_colide_mais(base):
    # Justifica a coluna estar na chave, em vez de estar por gosto.
    sem = [c for c in lr.CHAVE if c != "data_liquidacao"]
    assert base.duplicated(subset=sem, keep=False).sum() > lr.DUPLICATAS_CONHECIDAS_DA_PLANILHA


def test_linha_que_a_planilha_ja_tem_nao_e_novidade(base):
    ja_existe = base.iloc[-3:].copy()
    assert len(lr.novidades(ja_existe, base)) == 0


def test_linha_que_a_planilha_nao_tem_e_novidade(base):
    nova = base.iloc[-1:].copy()
    nova["data_leilao"] = pd.Timestamp("2026-09-15")
    nova["data_liquidacao"] = pd.Timestamp("2026-09-16")
    achadas = lr.novidades(nova, base)
    assert len(achadas) == 1
    assert achadas.iloc[0]["data_leilao"] == pd.Timestamp("2026-09-15")


def test_a_hora_na_data_nao_faz_a_linha_parecer_nova(base):
    # A planilha traz data sem hora; a API pode trazer com. Se a comparacao fosse
    # literal, TODA linha da API pareceria nova para sempre e o arquivo recente
    # cresceria duplicando o historico inteiro.
    ja_existe = base.iloc[-1:].copy()
    ja_existe["data_leilao"] = ja_existe["data_leilao"] + pd.Timedelta(hours=14)
    ja_existe["data_liquidacao"] = ja_existe["data_liquidacao"] + pd.Timedelta(hours=9)
    assert len(lr.novidades(ja_existe, base)) == 0


def test_a_reconciliacao_e_automatica(base):
    # O caso que motiva o desenho: a API adiantou um leilao, e dias depois a
    # planilha o traz. A linha provisoria tem de SUMIR sozinha, sem ninguem lembrar
    # de limpar -- senao o mesmo leilao entra duas vezes no grafico.
    adiantado = base.iloc[-1:].copy()
    adiantado[lr.COLUNA_ESTAGIO] = "aceito"

    # Antes: a planilha ainda nao tinha (simulada sem aquela linha).
    planilha_antiga = base.iloc[:-1]
    assert len(lr.novidades(adiantado, planilha_antiga)) == 1

    # Depois: a planilha alcancou.
    assert len(lr.novidades(adiantado, base)) == 0


def test_completo_marca_o_estagio_de_cada_linha(base, monkeypatch, tmp_path):
    # Quem consome precisa poder distinguir os tres momentos -- e o default e
    # incluir todos, porque a pergunta que motivou tudo isso e "o que esta
    # acontecendo hoje".
    adiantado = base.iloc[-1:].copy()
    adiantado["data_leilao"] = pd.Timestamp("2026-09-15")
    adiantado["data_liquidacao"] = pd.Timestamp("2026-09-16")
    adiantado[lr.COLUNA_ESTAGIO] = "aceito"

    monkeypatch.setattr(lr, "carregar_recentes", lambda **_: adiantado)

    com = lr.completo("aceito")
    sem = lr.completo("planilha")

    assert len(com) == len(sem) + 1
    assert set(com[lr.COLUNA_ESTAGIO]) == {"planilha", "aceito"}
    assert set(sem[lr.COLUNA_ESTAGIO]) == {"planilha"}


def test_completo_filtra_pelo_estagio_pedido(base, monkeypatch):
    # Quem quiser so o que ja aconteceu pede "aceito", e o teto anunciado fica de
    # fora. Sem esse filtro, um grafico de emissao realizada mostraria o que ainda
    # nao foi emitido.
    teto = base.iloc[-1:].copy()
    teto["data_leilao"] = pd.Timestamp("2026-09-15")
    teto["data_liquidacao"] = pd.Timestamp("2026-09-16")
    teto[lr.COLUNA_ESTAGIO] = "ofertado"
    monkeypatch.setattr(lr, "carregar_recentes", lambda **_: teto)

    assert len(lr.completo("ofertado")) == len(base) + 1
    assert len(lr.completo("aceito")) == len(base)
    assert len(lr.completo("planilha")) == len(base)


def test_estagio_que_nao_existe_levanta(base):
    with pytest.raises(LookupError, match="nao existe"):
        lr.completo("chutado")


def test_completo_descarta_provisorio_que_ja_virou_definitivo(base, monkeypatch):
    # O recentes.csv pode ter sido gravado ANTES de a planilha ser atualizada. Na
    # hora de juntar, a conferencia e refeita -- senao o intervalo entre uma coisa e
    # outra produz linha dobrada.
    ja_definitivo = base.iloc[-2:].copy()
    ja_definitivo[lr.COLUNA_ESTAGIO] = "aceito"
    monkeypatch.setattr(lr, "carregar_recentes", lambda **_: ja_definitivo)

    assert len(lr.completo("aceito")) == len(base)


def test_gravar_recentes_conta_o_que_entrou_e_o_que_ja_estava(base, monkeypatch,
                                                              tmp_path):
    from tesouro import config

    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)

    nova = base.iloc[-1:].copy()
    nova["data_leilao"] = pd.Timestamp("2026-09-15")
    nova["data_liquidacao"] = pd.Timestamp("2026-09-16")
    candidatos = pd.concat([base.iloc[-2:], nova], ignore_index=True)

    caminho, entraram, ja_estavam, _ = lr.gravar_recentes(
        candidatos, "aceito", base)
    assert entraram == 1
    assert ja_estavam == 2
    assert caminho.exists()

    gravado = pd.read_csv(caminho)
    assert list(gravado[lr.COLUNA_ESTAGIO]) == ["aceito"]


# --------------------------------------------------------------------------
# Os tres momentos. Um leilao aparece na tela tres vezes, e a cada vez o numero
# fica mais firme: ofertado -> aceito -> planilha.
# --------------------------------------------------------------------------

def _leilao(base, dia, ofertada, aceita=None):
    r = base.iloc[-1:].copy()
    r["data_leilao"] = pd.Timestamp(dia)
    r["data_liquidacao"] = pd.Timestamp(dia) + pd.Timedelta(days=1)
    r["oferta_qtd"] = ofertada
    r["venda_qtd"] = aceita
    return r


def test_rodar_de_novo_nao_apaga_o_leilao_da_vez_anterior(base, monkeypatch,
                                                          tmp_path):
    # O DEFEITO QUE ISTO PROTEGE: a primeira versao regravava o arquivo inteiro a
    # cada rodada, entao o leilao de terca apagava o de segunda -- exatamente o caso
    # que motiva o arquivo existir. Medido antes de consertar: sobrava 1 linha onde
    # deviam sobrar 2.
    from tesouro import config
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)

    lr.gravar_recentes(_leilao(base, "2026-09-14", 1_000_000), "aceito", base)
    lr.gravar_recentes(_leilao(base, "2026-09-15", 1_500_000), "aceito", base)

    guardado = lr.carregar_recentes()
    assert len(guardado) == 2
    assert set(guardado["data_leilao"].dt.date.astype(str)) == {
        "2026-09-14", "2026-09-15"}


def test_o_aceito_substitui_o_ofertado_do_mesmo_leilao(base, monkeypatch,
                                                       tmp_path):
    # De manha o teto, a tarde o resultado. E a mesma chave, entao a linha e UMA --
    # duas seriam o mesmo leilao contado duas vezes no grafico.
    from tesouro import config
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)

    lr.gravar_recentes(_leilao(base, "2026-09-15", 1_000_000), "ofertado", base)
    lr.gravar_recentes(_leilao(base, "2026-09-15", 1_000_000, 620_000), "aceito",
                       base)

    guardado = lr.carregar_recentes()
    assert len(guardado) == 1
    assert guardado.iloc[0][lr.COLUNA_ESTAGIO] == "aceito"
    assert guardado.iloc[0]["venda_qtd"] == 620_000


def test_o_ofertado_nao_desfaz_um_aceito_ja_conhecido(base, monkeypatch, tmp_path):
    # Reprocessar por engano o arquivo da oferta NAO pode devolver a barra ao teto:
    # o estagio so anda para a frente. Sem esta regra, rodar duas vezes na ordem
    # errada trocaria um numero final por uma estimativa.
    from tesouro import config
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)

    lr.gravar_recentes(_leilao(base, "2026-09-15", 1_000_000, 620_000), "aceito",
                       base)
    lr.gravar_recentes(_leilao(base, "2026-09-15", 1_000_000), "ofertado", base)

    guardado = lr.carregar_recentes()
    assert len(guardado) == 1
    assert guardado.iloc[0][lr.COLUNA_ESTAGIO] == "aceito"
    assert guardado.iloc[0]["venda_qtd"] == 620_000


def test_estagio_desconhecido_ao_gravar_levanta(base, monkeypatch, tmp_path):
    from tesouro import config
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)
    with pytest.raises(LookupError, match="nao existe"):
        lr.gravar_recentes(_leilao(base, "2026-09-15", 1), "chutado", base)


def test_o_estagio_novo_herda_o_que_ele_nao_sabe(base, monkeypatch, tmp_path):
    # O ARQUIVO DO RESULTADO traz a quantidade ACEITA e nao repete a ofertada. Sem
    # herdar, a quantidade que ela digitou de manha sumiria a tarde -- e com ela a
    # leitura de quanto do ofertado o Tesouro colocou naquele dia, que so voltaria
    # dias depois, quando a planilha chegasse.
    from tesouro import config
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)

    manha = _leilao(base, "2026-09-15", 1_000_000)
    manha["taxa_media_pct"] = 7.02
    lr.gravar_recentes(manha, "ofertado", base)

    tarde = _leilao(base, "2026-09-15", None, 620_000)
    tarde["taxa_media_pct"] = 7.06
    lr.gravar_recentes(tarde, "aceito", base)

    g = lr.carregar_recentes()
    assert len(g) == 1
    assert g.iloc[0]["oferta_qtd"] == 1_000_000    # herdado da manha
    assert g.iloc[0]["venda_qtd"] == 620_000       # do resultado
    # E o que o estagio novo SABE vence: a taxa do resultado, e nao a da manha.
    assert g.iloc[0]["taxa_media_pct"] == 7.06


# --------------------------------------------------------------------------
# TRES FONTES, TRES GRAFIAS DA VOLTA.
#
# O defeito que isto protege foi medido em 20/08/2026, no primeiro dia em que a
# API entrou no fluxo: a chave nunca casava entre fontes, e 57 leiloes que a
# planilha JA TINHA entraram como novidade -- prontos para aparecer em dobro.
#
# Nao levantou, nao quebrou. Foi pego porque o log dizia "70 novas, 0 que a
# planilha ja tinha", e zero casamentos em trinta dias de leilao nao e um
# numero possivel.
# --------------------------------------------------------------------------

def test_as_tres_grafias_da_volta_viram_o_mesmo_numero():
    grafias = pd.Series(["1.\u00aa volta", "1a volta", "1a", "1\u00aa volta",
                         "2.\u00aa volta", "2a volta", "2a"])
    assert list(lr._volta_normal(grafias)) == ["1", "1", "1", "1", "2", "2", "2"]


def test_a_planilha_e_a_api_casam_apesar_da_grafia(base):
    # O caso concreto: a MESMA linha, escrita como cada fonte a escreve.
    #
    # A linha e escolhida por ser de PRIMEIRA volta, e nao por ser a ultima: a
    # ultima linha da planilha e uma segunda volta, e reescreve-la como "1a" faria
    # dela outro leilao de verdade -- foi assim que a primeira versao deste teste
    # falhou, acusando o codigo por um erro que era meu.
    de_primeira = base[base["volta"].fillna("").astype(str).str.startswith("1")]
    assert len(de_primeira) > 0
    original = de_primeira.iloc[-1:].copy()

    for grafia in ("1a volta", "1a", "1\u00aa volta", "1.a volta"):
        outra_fonte = original.copy()
        outra_fonte["volta"] = grafia
        assert len(lr.novidades(outra_fonte, base)) == 0, grafia

    # E a de segunda volta, escrita de qualquer jeito, continua casando com a de
    # segunda volta -- e nao com a de primeira.
    de_segunda = base[base["volta"].fillna("").astype(str).str.startswith("2")]
    segunda = de_segunda.iloc[-1:].copy()
    segunda["volta"] = "2a volta"
    assert len(lr.novidades(segunda, base)) == 0

    virou_primeira = de_segunda.iloc[-1:].copy()
    virou_primeira["volta"] = "1a volta"
    assert len(lr.novidades(virou_primeira, base)) == 1


def test_a_primeira_e_a_segunda_volta_continuam_sendo_leiloes_DIFERENTES():
    # A normalizacao nao pode ir longe demais: se "1a" e "2a" casassem, a segunda
    # volta sumiria da mesclagem -- e ela responde por parte do risco emitido.
    assert list(lr._volta_normal(pd.Series(["1a volta", "2a volta"]))) == ["1", "2"]


def test_volta_vazia_nao_vira_a_mesma_coisa_que_volta_1(base):
    # Um leilao sem volta declarada nao e a primeira volta: e ausencia de dado, e
    # colapsar os dois esconderia linha.
    assert list(lr._volta_normal(pd.Series([None, "", "1a"]))) == ["", "", "1"]


def test_a_chave_e_montada_num_lugar_so(base):
    # Havia DUAS copias da montagem da chave -- uma em _chaves() e outra dentro de
    # novidades() -- e foi entre elas que a normalizacao da volta ficou faltando de
    # um lado. Este teste amarra as duas ao mesmo resultado.
    amostra = base.iloc[-5:]
    das_colunas = set(zip(*lr._colunas_da_chave(amostra)))
    assert das_colunas == lr._chaves(amostra)
    indexado = lr._indexa_por_chave(amostra)
    assert set(indexado.index) == das_colunas


# ---------------------------------------------------------------------------
# OS DOIS MOTIVOS DE UMA LINHA NAO ENTRAR, contados separados desde 08/10/2026.
# A conta antiga era um residuo unico, e o log a narrava sempre como "a planilha
# do Tesouro ja tinha" -- inclusive quando a planilha nao tinha nada.
# ---------------------------------------------------------------------------

def test_a_contagem_separa_a_planilha_do_proprio_provisorio(base, monkeypatch,
                                                            tmp_path):
    monkeypatch.setattr(lr.config, "PROCESSED_DIR", tmp_path)

    # Um leilao que a planilha NAO tem, gravado primeiro como aceito.
    novo = _leilao(base, "2026-09-15", 1_000_000, 620_000)
    _, entraram, na_planilha, no_provisorio = lr.gravar_recentes(
        novo, "aceito", base)
    assert (entraram, na_planilha, no_provisorio) == (1, 0, 0)

    # O MESMO leilao chegando como OFERTADO depois: nao entra, e o motivo e o
    # provisorio -- nao a planilha. E esta a linha que fazia o log mentir.
    _, entraram, na_planilha, no_provisorio = lr.gravar_recentes(
        _leilao(base, "2026-09-15", 1_000_000), "ofertado", base)
    assert entraram == 0
    assert no_provisorio == 1, "o motivo foi o estagio, e tem de ser contado aqui"
    assert na_planilha == 0, "a planilha nao tem este leilao; nao pode levar o credito"


def test_a_contagem_credita_a_planilha_quando_e_dela(base, monkeypatch, tmp_path):
    # O outro lado: uma linha que a planilha JA tem conta como da planilha.
    monkeypatch.setattr(lr.config, "PROCESSED_DIR", tmp_path)
    da_planilha = base.head(1).copy()
    _, entraram, na_planilha, no_provisorio = lr.gravar_recentes(
        da_planilha, "aceito", base)
    assert (entraram, na_planilha, no_provisorio) == (0, 1, 0)
