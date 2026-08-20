import collections
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pytest

from tesouro import config
from tesouro.graficos import custo, dashboard, estilo


@pytest.fixture(scope="module")
def html():
    return dashboard.monta()


def test_o_registro_tem_os_vinte_e_um_graficos():
    # Eram dezesseis; entraram em 19/08/2026 as quatro quebras por papel, recolhidas
    # atras de uma setinha, e a composicao empilhada em 100%.
    assert len(dashboard.REGISTRO) == 21
    ids = [g.id for g in dashboard.REGISTRO]
    assert len(set(ids)) == 21, "id repetido no registro"
    for g in dashboard.REGISTRO:
        assert g.grupo in dashboard.GRUPOS, f"grupo desconhecido em {g.id}"
        assert g.titulo and g.fonte, f"{g.id} sem titulo ou sem fonte"


def test_cada_grupo_aparece_uma_vez_so_no_corpo():
    # O corpo do HTML sai na ordem do REGISTRO, e o indice sai agrupado. Se as duas
    # ordens divergirem, o leitor clica em "Perfil de vencimentos" no grupo
    # Vencimentos e cai depois da Reserva. Foi o que aconteceu ao promover os
    # candidatos para os grupos deles em 19/08/2026.
    vistos = []
    for g in dashboard.REGISTRO:
        if not vistos or vistos[-1] != g.grupo:
            assert g.grupo not in vistos,                 f"o grupo {g.grupo} aparece em dois trechos do registro"
            vistos.append(g.grupo)
    assert vistos == dashboard.GRUPOS


def test_nao_ha_mais_grupo_de_candidatos():
    # Os tres candidatos entraram nos grupos a que pertencem em 19/08/2026. Guardar
    # grafico bom num apendice chamado "candidato" e uma forma de nunca decidir.
    assert "Candidatos" not in dashboard.GRUPOS
    porid = {g.id: g for g in dashboard.REGISTRO}
    assert porid["perfil_completo"].grupo == "Vencimentos"
    assert porid["custo_emissao"].grupo == "Custo"
    assert porid["emissao_papel"].grupo == "Funding"
    assert all(g.grupo != "Candidatos" for g in dashboard.REGISTRO)


def test_a_contagem_de_svgs_sai_do_registro():
    # Cada grafico rende uma versao, mais uma por janela, vezes duas se tiver
    # variante. A conta e derivada do registro de proposito: fixar o numero faria o
    # teste passar depois de alguem esquecer de gravar uma versao.
    com_janela = [g for g in dashboard.REGISTRO if g.janela]
    com_variante = [g for g in dashboard.REGISTRO if g.variantes]
    assert len(com_janela) == 14
    assert len(com_variante) == 1

    total = sum((2 if g.janela else 1) * (2 if g.variantes else 1)
                for g in dashboard.REGISTRO)
    assert total == 37


def test_as_quatro_quebras_por_papel_ficam_recolhidas():
    # Sao quatro graficos densos que respondem a mesma pergunta do quinto. Abertos,
    # empurram metade do dashboard para baixo da dobra.
    recolhidos = [g.id for g in dashboard.REGISTRO if g.recolhido]
    assert recolhidos == ["emissao_papel", "detentores_lft", "detentores_ntnb",
                          "detentores_ltn", "detentores_ntnf"]
    # A emissao por papel tambem: tem a MESMA FORMA do grafico anterior, e o que ela
    # acrescenta e a quebra do prefixado em LTN e NTN-F. Aberta, o leitor ve dois
    # graficos iguais seguidos e nao entende por que.
    porid = {g.id: g for g in dashboard.REGISTRO}
    assert porid["emissao_papel"].grupo == "Funding"


def test_a_setinha_e_html_puro_e_o_conteudo_fica_no_arquivo(html):
    # <details>/<summary> sem uma linha de JavaScript. O SVG continua no arquivo
    # mesmo fechado: quem procura com Ctrl+F acha, e quem imprime leva tudo.
    assert html.count("<details>") == 5
    assert html.count("<summary>") == 5
    for gid in ("emissao_papel", "detentores_lft", "detentores_ntnb",
                "detentores_ltn", "detentores_ntnf"):
        assert f'<section id="{gid}" class="recolhida">' in html
        assert f'data-grafico="{gid}"' in html


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


def test_os_dois_graficos_de_composicao_abrem_na_serie_completa():
    # Os dois contam a queda do cambio, e ela nao existe numa janela de cinco anos.
    porid = {g.id: g for g in dashboard.REGISTRO}
    assert porid["estoque_composicao"].padrao == "completa"
    assert porid["estoque_composicao_100"].padrao == "completa"
    # E os demais que aceitam janela abrem em 5 anos.
    na_completa = {"estoque_composicao", "estoque_composicao_100"}
    outros = [g for g in dashboard.REGISTRO if g.janela and g.id not in na_completa]
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
    # As DUAS familias de referencia, e nao so url(): as url() sao ~111 (recortes)
    # e as href="#" sao ~2.100 (os <use> de glifo que o matplotlib emite com
    # svg.fonttype='path'). A versao anterior olhava so as url(), entao apagar a
    # regex de href do _prefixa_ids deixava o teste VERDE com o texto de 36 dos 37
    # SVGs pendurado em id inexistente. Medido na revisao de 19/08/2026.
    referencias = set(re.findall(r"url\(#([^)]+)\)", html))
    referencias |= set(re.findall(r'(?:xlink:href|href)="#([^"]+)"', html))
    assert len(referencias) > 1000, \
        f"so {len(referencias)} referencias; o teste perdeu de vista as de glifo"

    contagem = collections.Counter(re.findall(r'id="([^"]+)"', html))
    for referencia in referencias:
        assert contagem[referencia] == 1, \
            f"o id '{referencia}' aparece {contagem[referencia]} vezes"


def test_o_html_e_reprodutivel():
    # Sem o svg.hashsalt fixo da Task 1, duas montagens do mesmo dado geram
    # arquivos diferentes e ninguem sabe se o dashboard mudou porque o dado mudou.
    assert dashboard.monta() == dashboard.monta()


def test_o_html_e_reprodutivel_entre_processos(tmp_path):
    # O teste acima compara duas montagens no MESMO processo, onde a semente de hash
    # e a mesma -- e por isso ele passava contra uma implementacao quebrada:
    # funding._rotula_extremos percorria um SET de Timestamp, cuja ordem de iteracao
    # depende do PYTHONHASHSEED. Duas execucoes do comando davam MD5 diferente com
    # as MESMAS 149.169 linhas, so trocadas de lugar. Medido em 19/08/2026.
    #
    # Este roda em dois subprocessos com sementes diferentes, que e o unico jeito de
    # a propriedade ser afirmada de verdade.
    #
    # O filho grava em ARQUIVO com utf-8 explicito, e nao no stdout: o dashboard tem
    # o sinal de menos tipografico (U+2212) que o matplotlib escreve nos eixos, e o
    # stdout do Windows sai em cp1252 -- o filho morria com UnicodeEncodeError e o
    # teste falhava por motivo nenhum.
    import os
    import subprocess
    import sys

    saidas = []
    for semente in ("0", "12345"):
        destino = tmp_path / f"dash_{semente}.html"
        codigo = (
            "import pathlib; from tesouro.graficos import dashboard; "
            f"pathlib.Path(r'{destino}').write_text(dashboard.monta(), "
            "encoding='utf-8')"
        )
        ambiente = dict(os.environ, PYTHONPATH="src", PYTHONHASHSEED=semente)
        r = subprocess.run([sys.executable, "-c", codigo], capture_output=True,
                           text=True, env=ambiente, cwd=str(config.RAIZ))
        assert r.returncode == 0, r.stderr[-800:]
        saidas.append(destino.read_text(encoding="utf-8"))

    assert saidas[0] == saidas[1], (
        "o HTML mudou entre processos com PYTHONHASHSEED diferente: alguma ordem de "
        "iteracao depende do hash. Procure set ou dict de objeto nao-str sendo "
        "percorrido para desenhar."
    )


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
