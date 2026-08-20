"""A planilha que ela preenche na hora da oferta.

O RISCO DESTE MODULO nao e calcular errado -- ele quase nao calcula. E aceitar uma
digitacao errada em silencio. Uma taxa em fracao, uma data trocada, uma quantidade
faltando: nenhuma dessas coisas levanta erro sozinha, todas produzem um numero, e o
numero vai para o grafico com a mesma cara de um numero certo.

Os testes cobrem o que ele ACEITA e, sobretudo, o que ele RECUSA em voz alta.
"""
import datetime

import pandas as pd
import pytest

from tesouro import config, entrada_manual


@pytest.fixture(scope="module")
def base():
    return pd.read_csv(
        config.PROCESSED_DIR / "leiloes.csv",
        parse_dates=["data_leilao", "data_liquidacao", "data_vencimento"],
    )


DIA = datetime.date(2026, 8, 20)
_ROT = {nome: rotulo for nome, rotulo in entrada_manual.COLUNAS}


@pytest.fixture
def modelo(tmp_path, base):
    return entrada_manual.modelo(tmp_path / "leilao_hoje.xlsx", quando=DIA,
                                 base=base)


def _preencher(caminho, linhas):
    """Escreve linhas na planilha, no formato em que ela ficaria depois do Excel."""
    d = pd.read_excel(caminho, sheet_name=entrada_manual.ABA)
    escolhidas = []
    for titulo, quantidade, taxa in linhas:
        r = d[d[_ROT["titulo"]] == titulo].tail(1).copy()
        r[_ROT["quantidade_ofertada"]] = quantidade
        r[_ROT["taxa_pct"]] = taxa
        escolhidas.append(r)
    pd.concat(escolhidas).to_excel(caminho, sheet_name=entrada_manual.ABA,
                                   index=False)
    return caminho


# --------------------------------------------------------------------------
# O modelo
# --------------------------------------------------------------------------

def test_o_modelo_chega_com_o_trabalho_de_digitacao_feito(modelo):
    # A ideia inteira e ela digitar SO quantidade e taxa. Se o modelo viesse vazio,
    # ela teria de copiar vencimento a vencimento do edital, e o caminho manual
    # deixaria de ser mais rapido que o automatico.
    d = pd.read_excel(modelo, sheet_name=entrada_manual.ABA)
    assert len(d) > 8
    assert d[_ROT["titulo"]].notna().all()
    assert d[_ROT["data_vencimento"]].notna().all()
    assert d[_ROT["data_leilao"]].notna().all()
    # E o que ela preenche vem vazio, e nao com um exemplo dentro: um numero de
    # exemplo esquecido na planilha vira leilao inventado no grafico.
    assert d[_ROT["quantidade_ofertada"]].isna().all()
    assert d[_ROT["taxa_pct"]].isna().all()


def test_o_modelo_so_traz_vencimento_que_ainda_nao_venceu(modelo):
    d = pd.read_excel(modelo, sheet_name=entrada_manual.ABA)
    assert (pd.to_datetime(d[_ROT["data_vencimento"]]) > pd.Timestamp(DIA)).all()


def test_a_liquidacao_pula_o_fim_de_semana(base):
    # Sexta liquida na segunda. Feriado ela corrige na propria planilha -- mas fim
    # de semana e todo mes, e errar isso poe a liquidacao num dia que nao existe.
    sexta = datetime.date(2026, 8, 21)
    assert sexta.weekday() == 4
    linhas = entrada_manual.linhas_provaveis(sexta, base)
    assert linhas.iloc[0]["data_liquidacao"] == datetime.date(2026, 8, 24)


def test_o_modelo_nao_sobrescreve_planilha_ja_preenchida(modelo, base):
    # Ela pode digitar meia planilha, sair para o cafe e rodar 'modelo' de novo por
    # habito. Regravar apagaria o trabalho sem perguntar.
    with pytest.raises(FileExistsError, match="ja existe"):
        entrada_manual.modelo(modelo, quando=DIA, base=base)


# --------------------------------------------------------------------------
# A leitura
# --------------------------------------------------------------------------

def test_le_o_que_ela_preencheu(modelo):
    _preencher(modelo, [("NTN-B", 600_000, 7.02), ("LTN", 1_500_000, 14.35)])
    tabela, digitadas = entrada_manual.ler(modelo)

    assert len(tabela) == 2
    assert digitadas == 2
    assert set(tabela["titulo"]) == {"NTN-B", "LTN"}
    assert sorted(tabela["oferta_qtd"]) == [600_000, 1_500_000]
    # A quantidade aceita e o financeiro NAO sao inventados: eles nao existem ainda.
    assert tabela["venda_qtd"].isna().all()
    assert tabela["financeiro_milhoes"].isna().all()


def test_a_taxa_e_opcional_e_o_modulo_conta_quantas_vieram(modelo):
    # A linha em branco continua desenhavel, com a taxa emprestada -- e o numero de
    # digitadas e o que permite dizer no log quantas sao opiniao dela e quantas sao
    # suposicao minha.
    _preencher(modelo, [("NTN-B", 600_000, 7.02), ("LTN", 800_000, None)])
    tabela, digitadas = entrada_manual.ler(modelo)
    assert len(tabela) == 2
    assert digitadas == 1
    assert tabela["taxa_media_pct"].isna().sum() == 1


def test_linha_sem_quantidade_e_linha_apagada_e_nao_erro(modelo):
    # O modelo chega com mais vencimentos do que um leilao costuma ter, DE
    # PROPOSITO. Recusar as sobras obrigaria a apagar linha por linha.
    _preencher(modelo, [("NTN-B", 600_000, 7.02), ("LTN", None, None)])
    tabela, _ = entrada_manual.ler(modelo)
    assert len(tabela) == 1
    assert tabela.iloc[0]["titulo"] == "NTN-B"


def test_a_saida_serve_de_entrada_para_a_mesclagem(modelo):
    from tesouro import leiloes_recentes as lr

    _preencher(modelo, [("NTN-B", 600_000, 7.02)])
    tabela, _ = entrada_manual.ler(modelo)
    assert set(lr.CHAVE) <= set(tabela.columns)
    assert len(lr.novidades(tabela, lr.carregar_base())) == 1


# --------------------------------------------------------------------------
# O que ela RECUSA. Cada um destes produziria um numero se passasse.
# --------------------------------------------------------------------------

def test_taxa_em_fracao_e_recusada(modelo):
    # O erro classico deste projeto: 0,0702 no lugar de 7,02 nao levanta nada -- ele
    # precifica, e devolve um PU plausivel e completamente errado.
    _preencher(modelo, [("NTN-B", 600_000, 0.0702)])
    with pytest.raises(LookupError) as erro:
        entrada_manual.ler(modelo)
    assert "PERCENTUAL" in str(erro.value)


def test_a_lft_pode_ter_taxa_abaixo_de_um_por_cento(modelo):
    # A guarda de fracao NAO pode pegar a LFT: o agio dela sobre a Selic e mesmo
    # perto de zero, e recusa-lo tornaria o papel indigitavel.
    _preencher(modelo, [("LFT", 1_500_000, 0.1097)])
    tabela, digitadas = entrada_manual.ler(modelo)
    assert digitadas == 1
    assert tabela.iloc[0]["taxa_media_pct"] == pytest.approx(0.1097)


def test_vencimento_antes_da_liquidacao_e_recusado(modelo):
    # Data trocada vira PU negativo, que e um numero e passa despercebido.
    _preencher(modelo, [("NTN-B", 600_000, 7.02)])
    d = pd.read_excel(modelo, sheet_name=entrada_manual.ABA)
    d[_ROT["data_vencimento"]] = datetime.date(2020, 1, 1)
    d.to_excel(modelo, sheet_name=entrada_manual.ABA, index=False)

    with pytest.raises(LookupError, match="posterior"):
        entrada_manual.ler(modelo)


def test_quantidade_zero_ou_negativa_e_recusada(modelo):
    _preencher(modelo, [("NTN-B", -600_000, 7.02)])
    with pytest.raises(LookupError, match="zero ou negativa"):
        entrada_manual.ler(modelo)


def test_titulo_que_nao_sabemos_precificar_e_recusado(modelo):
    _preencher(modelo, [("NTN-B", 600_000, 7.02)])
    d = pd.read_excel(modelo, sheet_name=entrada_manual.ABA)
    d[_ROT["titulo"]] = "NTN-C"
    d.to_excel(modelo, sheet_name=entrada_manual.ABA, index=False)

    with pytest.raises(LookupError, match="precificar"):
        entrada_manual.ler(modelo)


def test_data_obrigatoria_vazia_e_recusada_dizendo_a_linha_do_excel(modelo):
    # A LINHA DO EXCEL, e nao o indice do pandas: ela vai olhar a planilha, e
    # "linha 2" so ajuda se for a linha 2 que ela ve na tela.
    _preencher(modelo, [("NTN-B", 600_000, 7.02), ("LTN", 800_000, 14.3)])
    d = pd.read_excel(modelo, sheet_name=entrada_manual.ABA)
    d.loc[d.index[1], _ROT["data_liquidacao"]] = None
    d.to_excel(modelo, sheet_name=entrada_manual.ABA, index=False)

    with pytest.raises(LookupError) as erro:
        entrada_manual.ler(modelo)
    assert "linhas 3" in str(erro.value)     # 2 linhas + cabecalho


def test_coluna_renomeada_levanta_dizendo_o_que_achou(modelo):
    _preencher(modelo, [("NTN-B", 600_000, 7.02)])
    d = pd.read_excel(modelo, sheet_name=entrada_manual.ABA)
    d = d.rename(columns={_ROT["taxa_pct"]: "taxa"})
    d.to_excel(modelo, sheet_name=entrada_manual.ABA, index=False)

    with pytest.raises(LookupError) as erro:
        entrada_manual.ler(modelo)
    assert "taxa" in str(erro.value)
    assert "Vencimento" in str(erro.value)   # mostra as colunas reais


def test_planilha_toda_vazia_levanta(modelo):
    with pytest.raises(LookupError, match="quantidade ofertada"):
        entrada_manual.ler(modelo)


def test_arquivo_que_nao_existe_diz_como_criar(tmp_path):
    with pytest.raises(FileNotFoundError) as erro:
        entrada_manual.ler(tmp_path / "nao_existe.xlsx")
    assert "modelo" in str(erro.value)
