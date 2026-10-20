"""O calendario publicado e ENTRADA, lida do disco -- nao busca de cada pagina.

OBSERVACAO DELA em 20/10/2026: "o calendario e dado antes, nao atualiza todo dia
que tem leilao. vc so precisa calcular que o leilao de hj foi feito e vc ja tem
o resultado. mas os leiloes futuros, nao precisa atualizar calendario".

O projeto fazia o contrario: buscava /calendario na rede a cada gravacao de
pagina e jogava a resposta fora -- so /resultados ia para o disco. Naquela
tarde a API respondeu "Server Error" e a pagina do PAF deixou de ser gravada,
por falta de um documento TRIMESTRAL que o projeto tinha na mao uma hora antes.
E isso contradizia o README: "os parsers nunca acessam a rede".
"""
import datetime
import json

from tesouro import api_leiloes


def _registros(datas_e_titulos):
    return [{"DATA_LEILAO": data, "TITULO": titulo,
             "VENCIMENTO": "2030-01-01", "TIPO_LEILAO": "Venda"}
            for data, titulo in datas_e_titulos]


def _grava(pasta, nome, quando, registros):
    alvo = pasta / ("%s-%s.json" % (nome, quando))
    alvo.write_text(json.dumps(registros), encoding="utf-8")
    return alvo


def test_sem_arquivo_nenhum_nao_inventa(tmp_path):
    assert api_leiloes.guardado_em_disco("calendario", tmp_path) == (None, None)


def test_le_o_arquivo_MAIS_RECENTE_PELO_NOME(tmp_path):
    # PELO NOME E NAO PELO CARIMBO -- a mesma decisao que o anexo do RMD tomou
    # em 09/09/2026, e pelo mesmo motivo: reabrir e salvar um arquivo antigo
    # nao pode fazer o projeto voltar no tempo.
    _grava(tmp_path, "calendario", "2026-10-20",
           _registros([("2026-10-22", "LTN")]))
    velho = _grava(tmp_path, "calendario", "2026-09-01",
                   _registros([("2026-09-03", "NTN-B")]))

    # O VELHO FICA COM O CARIMBO MAIS NOVO, de proposito.
    import os
    agora = datetime.datetime.now().timestamp()
    os.utime(velho, (agora + 10, agora + 10))

    registros, quando = api_leiloes.guardado_em_disco("calendario", tmp_path)
    assert quando == datetime.date(2026, 10, 20), \
        "escolheu pelo carimbo do arquivo, e nao pela data do nome"
    assert registros[0]["TITULO"] == "LTN"


def test_nome_que_nao_se_deixa_ler_e_IGNORADO_e_nao_adivinhado(tmp_path):
    _grava(tmp_path, "calendario", "2026-10-20",
           _registros([("2026-10-22", "LTN")]))
    (tmp_path / "calendario-sei-la.json").write_text("[]", encoding="utf-8")
    registros, quando = api_leiloes.guardado_em_disco("calendario", tmp_path)
    assert quando == datetime.date(2026, 10, 20)
    assert len(registros) == 1


def test_com_arquivo_no_disco_NAO_VAI_A_REDE(tmp_path, monkeypatch):
    # O ponto da entrega: a pagina deixa de depender da rede para um documento
    # trimestral. Se a API estiver fora, a pagina sai igual.
    _grava(tmp_path, "calendario", "2026-10-20",
           _registros([("2026-10-22", "LTN")]))

    def nao_pode(*a, **k):
        raise AssertionError("foi a rede tendo o calendario no disco")

    monkeypatch.setattr(api_leiloes, "_abrir", nao_pode)
    registros, de_onde, quando = api_leiloes.calendario_publicado(
        destino=tmp_path)
    assert de_onde == "disco"
    assert quando == datetime.date(2026, 10, 20)
    assert registros[0]["TITULO"] == "LTN"


def test_SEM_arquivo_NAO_vai_a_rede_e_NAO_escreve(tmp_path, monkeypatch):
    # ERRO DE DESENHO MEU, corrigido em 20/10/2026: a primeira versao buscava
    # na rede e GRAVAVA em data/raw quando nao havia arquivo. Quem desenha
    # pagina nao faz nenhuma das duas -- o README promete "os parsers nunca
    # acessam a rede", e data/raw e imutavel por invariante, escrito pela
    # coleta. Os testes do agenda pegaram isso, pelo motivo certo.
    #
    # E a prova de que doeu: uma resposta falsa de teste chegou a ser gravada
    # como calendario-2026-10-20.json de ZERO bytes no data/raw dela, e
    # derrubou dezessete testes na rodada seguinte.
    def nao_pode(*a, **k):
        raise AssertionError("foi a rede sem ter arquivo; devia so desistir")

    monkeypatch.setattr(api_leiloes, "_abrir", nao_pode)
    registros, de_onde, quando = api_leiloes.calendario_publicado(
        destino=tmp_path)

    assert registros == []
    assert de_onde == "ausente"
    assert quando is None
    # E NAO ESCREVEU NADA: data/raw e entrada, nao saida.
    assert list(tmp_path.glob("*.json")) == []


def test_registros_INJETADOS_passam_direto(tmp_path, monkeypatch):
    # Os testes do projeto injetam a amostra congelada. Esse caminho nao pode
    # nem ler disco nem tocar rede.
    def nao_pode(*a, **k):
        raise AssertionError("tocou disco ou rede com registros injetados")

    monkeypatch.setattr(api_leiloes, "_abrir", nao_pode)
    monkeypatch.setattr(api_leiloes, "guardado_em_disco", nao_pode)
    meus = _registros([("2026-12-01", "LFT")])
    registros, de_onde, quando = api_leiloes.calendario_publicado(meus)
    assert registros is meus
    assert de_onde == "injetado"
    assert quando is None


def test_a_pagina_DIZ_de_quando_e_o_calendario():
    # Sem a data do arquivo, "publicado ate 17/12" nao distingue um calendario
    # de hoje de um de tres meses atras -- e agora ele vem do disco.
    import pandas as pd

    from tesouro.graficos import banda

    dados = pd.DataFrame({"indicador": ["Prefixado"], "hoje": [20.0]})
    dados.attrs["premissa"] = {
        "ate": pd.Timestamp("2026-12-31"),
        "de": pd.Timestamp("2026-10-20"),
        "dias_de_leilao": 20,
        "fronteira_do_calendario": pd.Timestamp("2026-12-17"),
        "calendario_baixado_em": datetime.date(2026, 10, 20),
        "data_da_curva": pd.Timestamp("2026-08-31"),
        "selic": 0.13, "inflacao": 0.05,
    }
    # SEM pytest.skip: teste que se pula nao protege nada, e este projeto
    # ja trocou um por isso. Se a funcao mudar de nome, que fique VERMELHO.
    frase = banda._rodape_automatico(dados)
    assert "17/12/2026" in frase, frase
    assert "20/10/2026" in frase, (
        "a frase nao diz de quando e o calendario: %s" % frase)
