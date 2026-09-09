"""A tabela do ritmo: qual pace estamos considerando, e onde ele chega.

Pedido dela em 08/09/2026. Ate entao o ritmo existia so no rodape de cada uma
das tres grades da simulacao, e a tabela "Onde fechamos o ano" mostrava o
RESULTADO sem dizer de que ritmo ele saiu.
"""
import pandas as pd
import pytest

from tesouro import rolagem
from tesouro.graficos import ritmo


@pytest.fixture(scope="module")
def dados():
    return ritmo.dados_ritmo(hoje=pd.Timestamp("2026-08-26"), registros=[])


def test_a_linha_do_total_NAO_SOMA_o_ritmo(dados):
    """Somar R$ bi por leilao dos tres indexadores nao produz grandeza nenhuma.

    Nao sao os mesmos leiloes: o prefixado vai a leilao num dia, a taxa
    flutuante em outro. A soma daria 39,49 bi "por leilao" em 08/09/2026, um
    numero que parece total e nao e nada -- exatamente o tipo de plausivel e
    errado que esta pagina existe para nao produzir.

    O QUE SOMA e o financeiro do periodo, que tem outro teste.
    """
    assert pd.isna(dados.at[ritmo.LINHA_TOTAL, "ritmo"]), (
        "o total nao pode somar ritmo por leilao")
    assert pd.isna(dados.at[ritmo.LINHA_TOTAL, "leiloes"]), (
        "nem contar leiloes, que sao de papeis diferentes")


def test_o_A_EMITIR_do_total_soma_as_linhas(dados):
    """Este soma, e por isso existe: e financeiro do periodo inteiro."""
    partes = dados.loc[list(rolagem.INDEXADORES), "a_emitir"].sum()
    assert dados.at[ritmo.LINHA_TOTAL, "a_emitir"] == pytest.approx(
        partes, rel=1e-9)


def test_o_A_EMITIR_de_cada_linha_e_ritmo_vezes_leiloes(dados):
    """A relacao que liga as tres primeiras colunas.

    Se alguem trocar a fonte de uma delas sem trocar as outras, a identidade
    quebra -- e ela vale em qualquer RMD.
    """
    for ind in rolagem.INDEXADORES:
        esperado = dados.at[ind, "ritmo"] * dados.at[ind, "leiloes"]
        assert dados.at[ind, "a_emitir"] == pytest.approx(esperado, rel=1e-9), (
            f"{ind}: a emitir tem de ser ritmo x leiloes")


def test_a_coluna_de_PERCENTUAL_fecha_100(dados):
    """Com o cambio dentro. Sem ele daria 96,58% e pareceria defeito.

    E a razao de o cambio ter linha: nao para mostrar ritmo, que ele nao tem,
    mas para o total fechar e o leitor ver POR QUE fecha.
    """
    partes = dados.loc[list(rolagem.INDEXADORES) + [ritmo.LINHA_CAMBIO], "pct"]
    assert partes.sum() == pytest.approx(100, abs=0.01)
    assert dados.at[ritmo.LINHA_TOTAL, "pct"] == pytest.approx(100, abs=0.01)


def test_o_CAMBIO_entra_SEM_ritmo_e_SEM_leiloes(dados):
    """O cambio nao vai a leilao. Por um numero ali seria inventar dado."""
    assert pd.isna(dados.at[ritmo.LINHA_CAMBIO, "ritmo"])
    assert pd.isna(dados.at[ritmo.LINHA_CAMBIO, "leiloes"])
    assert pd.isna(dados.at[ritmo.LINHA_CAMBIO, "a_emitir"])
    assert dados.at[ritmo.LINHA_CAMBIO, "estoque"] > 0, (
        "mas ele tem estoque, e e por isso que a linha existe")


def test_o_ESTOQUE_do_total_bate_com_a_projecao(dados):
    """A tabela nova nao pode discordar da tabela do veredito logo abaixo.

    As duas leem rolagem.projecao; se um dia uma delas passar a ler outra
    coisa, a pagina diria dois totais diferentes para o mesmo 31/12.
    """
    p = rolagem.projecao(pd.Timestamp("2026-12-31"), registros=[],
                         hoje=pd.Timestamp("2026-08-26"))
    assert dados.at[ritmo.LINHA_TOTAL, "estoque"] == pytest.approx(
        float(p["estoque"].sum()) / 1000, rel=1e-9)
    partes = dados.loc[list(rolagem.INDEXADORES) + [ritmo.LINHA_CAMBIO],
                       "estoque"].sum()
    assert dados.at[ritmo.LINHA_TOTAL, "estoque"] == pytest.approx(
        partes, rel=1e-9), "o total tem de ser a soma das linhas"


def test_o_RITMO_de_cada_linha_vem_de_rolagem_pace(dados):
    """Conferido contra a FONTE, e nao so "existe e e positivo".

    Sem isto, um ritmo copiado da propria projecao passaria -- e a tabela
    afirmaria que o pace produz a projecao usando a projecao como pace.
    """
    esperado = rolagem.pace(pd.Timestamp("2026-08-26"))
    for ind in rolagem.INDEXADORES:
        assert dados.at[ind, "ritmo"] == pytest.approx(
            float(esperado[ind]) / 1000, rel=1e-9)


def test_a_tabela_escreve_TRACO_onde_nao_ha_numero(dados):
    """Celula vazia parece dado faltando; "nan" parece defeito.

    O traco diz "isto nao se aplica", que e a verdade sobre o ritmo do cambio.
    """
    html = ritmo.tabela(dados)
    # PROCURA A CELULA, e nao a palavra solta: "financeiro" contem "nan", e a
    # primeira versao deste teste ficou vermelha por causa do proprio rodape.
    assert ">nan<" not in html.lower(), "nenhum nan pode chegar a pagina"
    assert html.count("\u2014") >= 5, (
        "cambio e total somam cinco celulas sem numero")


def test_a_tabela_traz_as_CINCO_linhas_na_ordem(dados):
    """A ordem e a da pagina inteira: prefixado, indice de precos, taxa
    flutuante -- depois o cambio, e o total por ultimo."""
    html = ritmo.tabela(dados)
    posicoes = [html.index(nome) for nome in
                list(rolagem.INDEXADORES) + [ritmo.LINHA_CAMBIO,
                                             ritmo.LINHA_TOTAL]]
    assert posicoes == sorted(posicoes), (
        "as linhas sairam fora da ordem da pagina")
