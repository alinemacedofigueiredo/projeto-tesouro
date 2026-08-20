"""A traducao do arquivo do dia para o esquema do leiloes.csv.

Este modulo foi escrito sem ver a resposta real da API -- a rede da maquina
intercepta TLS. O risco, entao, nao e o de sempre (calcular errado): e o de aceitar
um arquivo de formato inesperado e produzir uma tabela pela metade, que entraria no
grafico como se fosse leilao de verdade.

Os testes cobrem exatamente isso: o que ele aceita, e o que ele RECUSA em voz alta.
"""
import json

import pandas as pd
import pytest

from tesouro import parse_leiloes_api as p


# Uma linha de leilao com os nomes de coluna que o portal usa na versao "bonita"
# (com acento, espaco e maiuscula), que e a mais dificil das formas.
LINHA_DO_PORTAL = {
    "Data do Leil\u00e3o": "20/08/2026",
    "T\u00edtulo": "NTN-B",
    "Tipo Leil\u00e3o": "Venda",
    "Volta": 1,
    "Data Liquida\u00e7\u00e3o": "21/08/2026",
    "Data Vencimento": "15/08/2032",
    "Oferta Qtd": 500000,
    "Taxa M\u00e9dia": 7.1234,
    "Venda Qtd": 480000,
    "Financeiro": 2100.5,
}


def _grava_json(tmp_path, registros, embrulho="ckan"):
    caminho = tmp_path / "leiloes-2026-08-20.json"
    if embrulho == "ckan":
        conteudo = {"result": {"records": registros}}
    elif embrulho == "lista":
        conteudo = registros
    else:
        conteudo = {"records": registros}
    caminho.write_text(json.dumps(conteudo, ensure_ascii=False), encoding="utf-8")
    return caminho


def test_le_o_formato_do_ckan(tmp_path):
    tabela = p.normalizar(_grava_json(tmp_path, [LINHA_DO_PORTAL]))
    assert len(tabela) == 1
    assert tabela.iloc[0]["titulo"] == "NTN-B"


def test_le_json_de_lista_pura_e_de_records(tmp_path):
    # Nao sei qual endpoint o portal vai entregar. Os tres embrulhos plausiveis
    # precisam funcionar, senao a pessoa que salvar o arquivo a mao acerta ou erra
    # por sorte.
    for embrulho in ("ckan", "lista", "records"):
        tabela = p.normalizar(_grava_json(tmp_path, [LINHA_DO_PORTAL], embrulho))
        assert len(tabela) == 1, embrulho


def test_le_csv_e_excel(tmp_path):
    bruto = pd.DataFrame([LINHA_DO_PORTAL])

    csv = tmp_path / "leiloes.csv"
    bruto.to_csv(csv, index=False, encoding="utf-8")
    assert len(p.normalizar(csv)) == 1

    xlsx = tmp_path / "leiloes.xlsx"
    bruto.to_excel(xlsx, index=False)
    assert len(p.normalizar(xlsx)) == 1


def test_a_data_e_lida_como_brasileira(tmp_path):
    # 08/03/2026 e 8 de marco, nao 3 de agosto. Lido ao contrario, o leilao aparece
    # no mes errado do grafico e NADA levanta -- as duas leituras sao datas validas.
    linha = dict(LINHA_DO_PORTAL, **{"Data do Leil\u00e3o": "08/03/2026"})
    tabela = p.normalizar(_grava_json(tmp_path, [linha]))
    assert tabela.iloc[0]["data_leilao"] == pd.Timestamp("2026-03-08")


def test_os_numeros_viram_numero(tmp_path):
    tabela = p.normalizar(_grava_json(tmp_path, [LINHA_DO_PORTAL]))
    assert tabela.iloc[0]["financeiro_milhoes"] == pytest.approx(2100.5)
    assert tabela.iloc[0]["venda_qtd"] == 480000
    assert tabela.iloc[0]["taxa_media_pct"] == pytest.approx(7.1234)


def test_coluna_essencial_faltando_levanta_dizendo_o_que_achou(tmp_path):
    # O teste que da dentes ao modulo. Sem financeiro, a linha nao soma nada -- e o
    # grafico do dia mostraria uma barra menor sem ninguem saber por que.
    linha = {k: v for k, v in LINHA_DO_PORTAL.items() if k != "Financeiro"}
    with pytest.raises(LookupError) as erro:
        p.normalizar(_grava_json(tmp_path, [linha]))
    texto = str(erro.value)
    assert "financeiro_milhoes" in texto
    # A mensagem tem de mostrar as colunas REAIS, senao quem for consertar fica
    # adivinhando qual sinonimo acrescentar.
    assert "Data do Leil" in texto


def test_data_ilegivel_levanta_em_vez_de_virar_linha_sem_data(tmp_path):
    # Uma linha sem data nao tem chave, e sem chave a mesclagem nao consegue dizer se
    # ela ja esta na planilha. Deixa-la passar duplicaria o leilao a cada rodada.
    linha = dict(LINHA_DO_PORTAL, **{"Data do Leil\u00e3o": "sem data"})
    with pytest.raises(LookupError, match="sem data de leilao"):
        p.normalizar(_grava_json(tmp_path, [linha]))


def test_arquivo_vazio_levanta(tmp_path):
    with pytest.raises(LookupError, match="nenhuma linha"):
        p.normalizar(_grava_json(tmp_path, []))


def test_json_de_formato_desconhecido_levanta_mostrando_as_chaves(tmp_path):
    caminho = tmp_path / "estranho.json"
    caminho.write_text(json.dumps({"erro": "acesso negado"}), encoding="utf-8")
    with pytest.raises(LookupError) as erro:
        p.normalizar(caminho)
    assert "erro" in str(erro.value)


def test_extensao_desconhecida_levanta(tmp_path):
    caminho = tmp_path / "leiloes.pdf"
    caminho.write_bytes(b"%PDF")
    with pytest.raises(LookupError, match="pdf"):
        p.normalizar(caminho)


def test_a_saida_serve_de_entrada_para_a_mesclagem(tmp_path):
    # O contrato que importa: o que sai daqui tem de ter TODAS as colunas da chave,
    # senao leiloes_recentes.novidades() quebra na hora -- de madrugada, sem ninguem
    # olhando.
    from tesouro import leiloes_recentes as lr

    tabela = p.normalizar(_grava_json(tmp_path, [LINHA_DO_PORTAL]))
    assert set(lr.CHAVE) <= set(tabela.columns)

    # E a comparacao com o historico de fato roda, e diz que este leilao de 2026 e
    # novidade.
    base = lr.carregar_base()
    assert len(lr.novidades(tabela, base)) == 1
