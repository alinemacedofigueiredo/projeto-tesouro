"""A rotina de quando sai calendario novo: a cobertura POR PAPEL e anunciada.

PEDIDO DELA em 20/10/2026: "vc nao pode deixar o calendario ja salvo. e quando
ter uma rotina para quando sai um calendario novo? ate porque, meio de dezembro
teremos o calendario ate marco, ai vc tera mais dados para fazer estimativas de
2027".

O projeto baixava, salvava e ficava calado. A publicacao de um comunicado novo
e o evento mais importante para a projecao -- dezenas de dias passam de
"estimado" para "publicado" de uma vez -- e passava em silencio.

O PRECO JA FOI PAGO: em 23/09/2026 o Tesouro publicava o prefixado ate 17/12 e
a terca de LFT/NTN-B so ate 29/09; a fronteira global escondeu a diferenca e as
11 tercas de 06/10 a 15/12 sumiram da projecao -- R$ 279 bi no estoque de 31/12.
"""
from tesouro import calendario_leiloes as cal


def _reg(pares):
    return [{"DATA_LEILAO": data, "TITULO": titulo,
             "VENCIMENTO": "2030-01-01", "TIPO_LEILAO": "Venda"}
            for data, titulo in pares]


def test_a_cobertura_e_POR_PAPEL_e_nao_global():
    # O calendario do Tesouro fica completo papel a papel. Uma cobertura global
    # diria "ate 17/12" e esconderia que a terca para em 29/09 -- que foi
    # exatamente o defeito de 279 bi.
    c = cal.cobertura_por_papel(_reg([
        ("2026-12-17", "LTN"), ("2026-10-01", "LTN"),
        ("2026-09-29", "NTN-B"), ("2026-09-29", "LFT")]))
    assert set(c) == {"LTN", "NTN-B", "LFT"}
    assert c["LTN"].strftime("%d/%m/%Y") == "17/12/2026"
    assert c["NTN-B"].strftime("%d/%m/%Y") == "29/09/2026"


def test_sem_registros_a_cobertura_e_VAZIA_e_nao_estoura():
    # Calendario ausente e caminho normal: a pagina estima o periodo inteiro e
    # diz que estimou.
    assert cal.cobertura_por_papel([]) == {}
    assert cal.cobertura_por_papel(None) == {}


def test_nada_mudou_NAO_DIZ_NADA():
    # A rodada normal tem de ser silenciosa: aviso que sai todo dia deixa de
    # ser lido, e no dia em que importar ninguem ve.
    antes = _reg([("2026-12-17", "LTN")])
    assert cal.mudou_a_cobertura(antes, antes) == []


def test_o_calendario_que_ESTICA_e_anunciado_com_as_duas_datas():
    # O caso dela: meados de dezembro, o Tesouro publica o 1o trimestre de 2027.
    antes = _reg([("2026-12-17", "LTN"), ("2026-09-29", "NTN-B")])
    depois = _reg([("2027-03-30", "LTN"), ("2027-03-23", "NTN-B")])
    linhas = cal.mudou_a_cobertura(antes, depois)

    assert len(linhas) == 2, linhas
    juntas = " | ".join(linhas)
    # AS DUAS DATAS, e nao so a nova: "esticou" sem o de-onde nao diz quanto.
    assert "17/12/2026" in juntas and "30/03/2027" in juntas, juntas
    assert "29/09/2026" in juntas and "23/03/2027" in juntas, juntas
    assert "esticou" in juntas


def test_o_calendario_que_ENCURTA_e_anunciado_ALTO():
    # "O mais recente vence" e a regra certa -- o Tesouro pode ter revisado --
    # mas um calendario novo que cobre MENOS piora a projecao, e isso nao pode
    # passar em silencio. E o aviso tem de dizer o que acontece em consequencia.
    antes = _reg([("2027-03-30", "LTN")])
    depois = _reg([("2026-12-17", "LTN")])
    linhas = cal.mudou_a_cobertura(antes, depois)

    assert len(linhas) == 1, linhas
    assert "ENCURTOU" in linhas[0], linhas[0]
    assert "estimador" in linhas[0], \
        "o aviso nao diz a consequencia de encurtar"


def test_papel_que_ENTRA_e_papel_que_SAI_aparecem():
    antes = _reg([("2026-12-17", "LTN")])
    depois = _reg([("2026-12-17", "LTN"), ("2026-12-15", "LFT")])
    assert any("LFT" in l and "entrou" in l
               for l in cal.mudou_a_cobertura(antes, depois))
    assert any("LFT" in l and "saiu" in l
               for l in cal.mudou_a_cobertura(depois, antes))


def test_a_primeira_coleta_da_vida_anuncia_tudo_como_NOVO(tmp_path):
    # Sem calendario guardado, 'antes' e None: todo papel e novidade. Nao pode
    # estourar, e nao pode ficar calado.
    depois = _reg([("2026-12-17", "LTN"), ("2026-12-15", "LFT")])
    linhas = cal.mudou_a_cobertura(None, depois)
    assert len(linhas) == 2, linhas
    assert all("entrou no calendario" in l for l in linhas), linhas
