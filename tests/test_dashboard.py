import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pytest

from tesouro.graficos import custo, dashboard, estilo


@pytest.fixture(scope="module")
def html():
    return dashboard.monta()


def test_o_registro_tem_os_dezesseis_graficos():
    assert len(dashboard.REGISTRO) == 16
    ids = [g.id for g in dashboard.REGISTRO]
    assert len(set(ids)) == 16, "id repetido no registro"
    for g in dashboard.REGISTRO:
        assert g.grupo in dashboard.GRUPOS, f"grupo desconhecido em {g.id}"
        assert g.titulo and g.fonte, f"{g.id} sem titulo ou sem fonte"


def test_os_grupos_saem_na_ordem_com_os_candidatos_por_ultimo():
    assert dashboard.GRUPOS[-1] == "Candidatos"
    grupos_usados = [g.grupo for g in dashboard.REGISTRO]
    # Os tres candidatos ficam juntos no fim: "cada um escolhe o que olhar" vale
    # de verdade, sem poluir a primeira leitura.
    assert grupos_usados[-3:] == ["Candidatos"] * 3


def test_nove_graficos_aceitam_janela_e_saem_vinte_e_cinco_svgs():
    # A spec diz "sete dos dezesseis" e "23 SVGs", mas a tabela da secao 5 marca
    # nove -- os sete principais mais dois candidatos. A contagem certa e a da
    # tabela, e este teste a deriva do registro em vez de fixar o numero.
    com_janela = [g for g in dashboard.REGISTRO if g.janela]
    assert len(com_janela) == 9
    total = len(dashboard.REGISTRO) + len(com_janela)
    assert total == 25


def test_o_html_traz_todos_os_titulos_e_todos_os_grupos(html):
    for g in dashboard.REGISTRO:
        assert g.titulo in html, f"faltou o titulo de {g.id}"
        assert f'id="{g.id}"' in html, f"faltou a ancora de {g.id}"
    for grupo in dashboard.GRUPOS:
        assert grupo in html


def test_os_graficos_com_janela_trazem_as_duas_versoes_embutidas(html):
    for g in dashboard.REGISTRO:
        marcas = html.count(f'data-grafico="{g.id}" data-janela=')
        esperado = (2 if g.janela else 1) * (2 if g.variantes else 1)
        assert marcas == esperado, f"{g.id} tem {marcas} versoes, esperava {esperado}"


def test_a_caixa_da_dpfe_traz_as_quatro_combinacoes(html):
    # Dois eixos de troca no mesmo grafico: janela (5 anos / completa) e variante
    # (com / sem DPFe). As quatro vao embutidas, como as duas janelas ja iam.
    assert html.count('data-grafico="custo_estoque" data-janela=') == 4
    for janela in ("5 anos", "completa"):
        for variante in ("False", "True"):
            marca = (f'data-grafico="custo_estoque" data-janela="{janela}" '
                     f'data-variante="{variante}"')
            assert marca in html, marca
    # E a caixa existe, com o rotulo que o registro declara.
    assert 'input type="checkbox" class="variante"' in html
    assert "incluir a DPFe" in html
    assert "trocaVariante(&#x27;custo_estoque&#x27;)" in html or         "trocaVariante('custo_estoque')" in html


def test_so_o_custo_tem_caixa_de_variante(html):
    # Uma caixa e um grafico so. Se aparecer outra sem alguem decidir, este teste
    # avisa -- interatividade e a coisa que mais cresce sozinha.
    assert html.count('input type="checkbox"') == 1
    com_variante = [g.id for g in dashboard.REGISTRO if g.variantes]
    assert com_variante == ["custo_estoque"]


def test_o_eixo_do_custo_muda_quando_a_dpfe_entra():
    # A razao de a caixa existir: a DPFe vai de -16,0% a +62,6% e as outras duas
    # vivem entre 10% e 14%. Se o eixo nao mudasse, ou a DPFe sairia cortada ou as
    # outras quatro virariam um tapete no meio do grafico.
    estilo.aplicar_estilo()
    limites = {}
    for com_dpfe in (False, True):
        fig, ax = plt.subplots(figsize=(13, 6))
        custo.desenha_custo(custo.dados_custo(com_dpfe=com_dpfe), ax)
        limites[com_dpfe] = ax.get_ylim()
        plt.close(fig)

    assert limites[False][0] > limites[True][0], "o piso tem de descer"
    assert limites[True][1] > limites[False][1], "o teto tem de subir"
    assert limites[True][0] < -16.0 <= limites[False][0]
    assert limites[True][1] > 62.6


def test_a_composicao_do_estoque_abre_na_serie_completa():
    porid = {g.id: g for g in dashboard.REGISTRO}
    assert porid["estoque_composicao"].padrao == "completa"
    # E os demais que aceitam janela abrem em 5 anos.
    outros = [g for g in dashboard.REGISTRO
              if g.janela and g.id != "estoque_composicao"]
    assert all(g.padrao == "5 anos" for g in outros)


def test_o_html_nao_tem_nenhuma_referencia_externa(html):
    # Um src apontando para fora quebra o "abre com duplo clique em qualquer
    # maquina", que e a propriedade que faz este arquivo servir num banco.
    #
    # Nao da para procurar "http://" cru: todo SVG do matplotlib declara
    # xmlns="http://www.w3.org/2000/svg", que e nome de espaco e nao busca nada
    # na rede. O que importa e src= e href= apontando para fora.
    assert not re.search(r'(?:src|href)\s*=\s*"(?!#)[^"]*//', html)
    assert "<link" not in html
    assert not re.search(r"<script[^>]+src=", html)
    # E o prologo XML do matplotlib nao pode vazar para dentro do HTML.
    assert "<?xml" not in html
    assert "<!DOCTYPE svg" not in html


def test_toda_referencia_interna_do_svg_resolve_para_um_id_unico(html):
    # url(#p1a2b) e resolvido pelo navegador para o PRIMEIRO id daquele nome no
    # documento inteiro. Com 25 SVGs juntos, o recorte de um grafico pode passar a
    # valer para outro.
    referencias = set(re.findall(r"url\(#([^)]+)\)", html))
    assert referencias, "nenhuma referencia interna; o teste perdeu sentido"
    ids = re.findall(r'id="([^"]+)"', html)
    for referencia in referencias:
        assert ids.count(referencia) == 1, \
            f"o id '{referencia}' aparece {ids.count(referencia)} vezes"


def test_o_html_e_reprodutivel():
    # Sem o svg.hashsalt fixo da Task 1, duas montagens do mesmo dado geram
    # arquivos diferentes e ninguem sabe se o dashboard mudou porque o dado mudou.
    assert dashboard.monta() == dashboard.monta()


def test_cada_figura_leva_a_legenda_com_a_aba_de_origem(html):
    for g in dashboard.REGISTRO:
        assert g.fonte in html, f"faltou a fonte de {g.id}"
    # A legenda e HTML, nao texto dentro do desenho: selecionavel e fora do SVG.
    assert html.count('class="legenda"') == len(dashboard.REGISTRO)


def test_o_botao_de_periodo_some_quando_ha_uma_janela_so():
    um_so = dashboard.monta(recortes=[("2021-01-01 a 2026-06-30",
                                       (pd.Timestamp("2021-01-01"),
                                        pd.Timestamp("2026-06-30")))])
    assert 'id="troca-periodo"' not in um_so
    assert 'id="troca-periodo"' in dashboard.monta()


def test_o_recorte_por_data_chega_nas_funcoes_de_dado():
    from tesouro.graficos import funding
    par = (pd.Timestamp("2021-01-01"), pd.Timestamp("2026-06-30"))
    cortado = funding.dados_net(par)
    inteiro = funding.dados_net()
    assert cortado.index.min() >= par[0]
    assert cortado.index.max() == inteiro.index.max()
    assert len(cortado) < len(inteiro)


def test_o_arquivo_cabe_no_limiar_de_dez_megabytes(tmp_path):
    # Limiar medido, nao suposto (ver a spec, secao 4.1). Se estourar, os SVGs
    # saem para arquivos ao lado e a spec registra a troca.
    caminho = dashboard.grava(tmp_path / "dashboard.html")
    tamanho = caminho.stat().st_size
    assert tamanho > 100_000, "arquivo pequeno demais; algum grafico nao entrou"
    assert tamanho < 10 * 1024 * 1024, (
        f"o dashboard passou de 10 MB ({tamanho / 1024 / 1024:.1f} MB). A spec "
        f"manda trocar os SVGs embutidos por arquivos ao lado e registrar a troca."
    )
