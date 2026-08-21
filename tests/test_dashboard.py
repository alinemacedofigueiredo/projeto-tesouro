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


@pytest.fixture(scope="module")
def pagina_gravada(tmp_path_factory):
    """O HTML como o arquivo fica no disco.

    monta() nao injeta a barra de paginas -- quem faz isso e grava(), porque a
    lista de irmas depende do NOME do arquivo. Testar o cabecalho exige passar
    pelo caminho de verdade.
    """
    destino = tmp_path_factory.mktemp("dash") / "dashboard.html"
    return dashboard.grava(destino).read_text(encoding="utf-8")


def test_o_registro_tem_os_vinte_e_oito_graficos():
    # Eram dezesseis; entraram em 19/08/2026 as quatro quebras por papel, recolhidas
    # atras de uma setinha, e a composicao empilhada em 100%. Em 20/08 entrou o
    # estoque em titulos por vencimento, um grafico por papel -- quatro, porque
    # a NTN-C tem um vencimento so.
    assert len(dashboard.REGISTRO) == 28
    ids = [g.id for g in dashboard.REGISTRO]
    assert len(set(ids)) == 28, "id repetido no registro"
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
    assert len(com_janela) == 17
    assert len(com_variante) == 1

    # O NUMERO DE JANELAS SAI DA CONSTANTE, e nao de um "2" cravado. Ele foi 2 ate
    # 20/08/2026 e virou 4 no dia seguinte, e o teste continuou passando porque
    # contava o registro e nao o arquivo -- afirmava uma coisa e media outra.
    quantas = len(dashboard.JANELAS)
    total = sum((quantas if g.janela else 1) * (2 if g.variantes else 1)
                for g in dashboard.REGISTRO)
    # Os quatro de estoque em titulos entraram SEM janela: e o retrato de uma data,
    # e dizer "5 anos" neles seria atributo que mente.
    sem_janela = len(dashboard.REGISTRO) - len(com_janela)
    assert total == quantas * len(com_janela) + sem_janela + quantas


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
    #
    # SAO DOIS NIVEIS DE SETINHA desde 20/08/2026: as secoes recolhidas uma a uma
    # (as quebras por papel) e os GRUPOS inteiros. Contar "<summary>" solto somaria
    # os dois e nao diria nada -- a contagem e por classe.
    assert html.count('class="recolhida"') == 5
    for gid in ("emissao_papel", "detentores_lft", "detentores_ntnb",
                "detentores_ltn", "detentores_ntnf"):
        assert f'<section id="{gid}" class="recolhida">' in html
        assert f'data-grafico="{gid}"' in html

    # Um <details> por grupo, mais os cinco de dentro.
    assert html.count('class="grupo-secao"') == len(dashboard.GRUPOS)
    assert html.count("</details>") == len(dashboard.GRUPOS) + 5


def test_cada_grupo_vira_uma_secao_recolhivel(html):
    # O pedido: setinha para abrir cada grupo. Com os sete abertos, o dashboard tem
    # oito metros de rolagem e quem chega nao ve onde as coisas estao.
    import re

    achados = re.findall(r'data-grupo="([^"]+)"( open)?>\s*<summary>([^<]*)</summary>',
                         html)
    assert [a[0] for a in achados] == dashboard.GRUPOS
    # O rotulo da setinha e o nome do grupo.
    assert [a[2] for a in achados] == dashboard.GRUPOS
    # SO O PRIMEIRO ABRE.
    abertos = [a[0] for a in achados if a[1]]
    assert abertos == [dashboard.GRUPOS[0]]


def test_cada_grafico_fica_dentro_do_grupo_dele(html):
    # Se um grafico caisse fora da secao do grupo, o indice levaria a ele e a
    # setinha do grupo nao o mostraria -- ficaria invisivel de um jeito que nada
    # acusa.
    import re

    for grupo in dashboard.GRUPOS:
        i = html.index(f'data-grupo="{grupo}"')
        fim = html.index("</details>\n<details", i) if f'data-grupo="{grupo}"' \
            != f'data-grupo="{dashboard.GRUPOS[-1]}"' else html.index("</main>")
        trecho = html[i:fim]
        for g in dashboard.REGISTRO:
            if g.grupo == grupo:
                assert f'id="{g.id}"' in trecho, (grupo, g.id)


def test_o_indice_abre_o_grupo_fechado(html):
    # COM O GRUPO FECHADO, clicar num link do indice levava a uma secao invisivel.
    # abreSeApontada() passou a abrir tambem os <details> ANCESTRAIS do alvo.
    assert "acima.tagName === 'DETAILS'" in html
    assert "secao.scrollIntoView()" in html
    # E o indice continua apontando para todos os graficos, inclusive os de grupo
    # fechado.
    for g in dashboard.REGISTRO:
        assert f'href="#{g.id}"' in html


def test_o_html_traz_todos_os_titulos_e_todos_os_grupos(html):
    for g in dashboard.REGISTRO:
        assert g.titulo in html, f"faltou o titulo de {g.id}"
        assert f'id="{g.id}"' in html, f"faltou a ancora de {g.id}"
    for grupo in dashboard.GRUPOS:
        assert grupo in html


def test_os_graficos_com_janela_trazem_TODAS_as_versoes_embutidas(html):
    # Eram duas janelas ate 20/08/2026; entraram "12 meses" e "3 anos" em 21/08.
    # A conta sai do numero de recortes, e nao de um dois cravado -- senao
    # acrescentar uma janela quebra o teste sem que nada esteja errado.
    quantas = len(dashboard.JANELAS)
    for g in dashboard.REGISTRO:
        marcas = html.count(f'data-grafico="{g.id}" data-janela=')
        esperado = (quantas if g.janela else 1) * (2 if g.variantes else 1)
        assert marcas == esperado, f"{g.id} tem {marcas} versoes, esperava {esperado}"


def test_a_caixa_da_dpfe_traz_todas_as_combinacoes(html):
    # Dois eixos de troca no mesmo grafico: janela e variante (com / sem DPFe).
    # Todas vao embutidas, como as janelas ja iam.
    janelas = [nome for nome, _ in dashboard.JANELAS]
    assert (html.count('data-grafico="custo_estoque" data-janela=')
            == len(janelas) * 2)
    for janela in janelas:
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
    # O do total tambem: a divida sai de 654 bi para 9.268, e isso nao existe
    # dentro de uma janela de cinco anos.
    assert porid["estoque_total"].padrao == "completa"
    # E os demais que aceitam janela abrem em 5 anos.
    # O DV01 tambem: a serie so comeca em 2010 e o que se ve nela e a divida
    # triplicando de risco -- numa janela de cinco anos isso nao existe.
    assert porid["dv_do_estoque"].padrao == "completa"
    na_completa = {"estoque_composicao", "estoque_composicao_100",
                   "estoque_total", "dv_do_estoque"}
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


def test_CADA_UMA_das_paginas_cabe_no_limiar_de_dez_megabytes(tmp_path):
    # Limiar medido, nao suposto (ver a spec, secao 4.1).
    #
    # ELE VALE POR PAGINA, e e por isso que o dashboard virou duas: com os 28
    # graficos juntos o arquivo chegou a 9,62 MB e sobravam 0,38 -- o proximo
    # grafico com quatro janelas nao caberia. Se uma das duas estourar de novo, o
    # caminho e o mesmo: dividir por assunto, e nao cortar janela.
    escritos = dashboard.grava_o_rmd(destino=tmp_path)
    assert len(escritos) == len(dashboard.PAGINAS_DO_RMD)
    for caminho in escritos:
        tamanho = caminho.stat().st_size
        assert tamanho > 100_000, (
            f"{caminho.name} saiu pequeno demais; algum grafico nao entrou")
        assert tamanho < 10 * 1024 * 1024, (
            f"{caminho.name} passou de 10 MB ({tamanho / 1024 / 1024:.1f} MB). "
            f"A spec manda trocar os SVGs embutidos por arquivos ao lado, ou "
            f"dividir a pagina de novo.")


def test_TODO_GRAFICO_esta_em_EXATAMENTE_UMA_pagina():
    # O jeito de perder um grafico numa divisao e este: renomear um grupo, ou criar
    # um novo, e esquecer de listar. Ele some do arquivo e nada quebra -- o registro
    # continua com 28 e os testes de contagem passam.
    de_pagina = {}
    for arquivo, _, grupos, _ in dashboard.PAGINAS_DO_RMD:
        for g in dashboard.REGISTRO:
            if g.grupo in grupos:
                de_pagina.setdefault(g.id, []).append(arquivo)

    orfaos = [g.id for g in dashboard.REGISTRO if g.id not in de_pagina]
    assert not orfaos, f"graficos fora das duas paginas: {orfaos}"
    repetidos = {i: p for i, p in de_pagina.items() if len(p) > 1}
    assert not repetidos, f"graficos em mais de uma pagina: {repetidos}"
    assert len(de_pagina) == len(dashboard.REGISTRO)


def test_TODO_GRUPO_esta_em_EXATAMENTE_UMA_pagina():
    listados = [grupo for _, _, grupos, _ in dashboard.PAGINAS_DO_RMD
                for grupo in grupos]
    assert sorted(listados) == sorted(dashboard.GRUPOS), (
        sorted(listados), sorted(dashboard.GRUPOS))
    assert len(listados) == len(set(listados)), "grupo em duas paginas"


def test_a_ordem_de_GRUPOS_e_a_ordem_das_paginas():
    # O corpo e o indice saem na ordem da lista de grupos de cada pagina. Se GRUPOS
    # discordar de PAGINAS_DO_RMD, a segunda pagina abre com os grupos embaralhados
    # em relacao ao registro -- e o teste do registro continua passando.
    esperado = [grupo for _, _, grupos, _ in dashboard.PAGINAS_DO_RMD
                for grupo in grupos]
    assert esperado == dashboard.GRUPOS


def test_as_duas_paginas_do_RMD_apontam_UMA_PARA_A_OUTRA(tmp_path):
    # Dividir sem ligar as duas e esconder metade do dashboard: quem abre por duplo
    # clique nao tem como saber que a outra existe.
    escritos = {c.name: c.read_text(encoding="utf-8")
                for c in dashboard.grava_o_rmd(destino=tmp_path)}
    assert set(escritos) == {a for a, _, _, _ in dashboard.PAGINAS_DO_RMD}

    for arquivo, rotulo, _, titulo in dashboard.PAGINAS_DO_RMD:
        html = escritos[arquivo]
        # A propria pagina aparece como texto, e nao como link para si mesma.
        assert f'href="{arquivo}"' not in html, arquivo
        assert rotulo in html
        assert f"<title>{titulo}</title>" in html
        # E as outras tres, como link relativo -- que e o que funciona sem servidor.
        for outra, _ in dashboard.PAGINAS:
            if outra != arquivo:
                assert f'href="{outra}"' in html, (arquivo, outra)


def test_a_pagina_do_estoque_leva_o_estoque_e_a_outra_leva_o_funding():
    # A divisao e POR ASSUNTO, e nao por tamanho. Se um dia alguem mover um grupo
    # para equilibrar megabytes, este teste diz que a conta nao e essa.
    primeira, segunda = dashboard.PAGINAS_DO_RMD
    assert primeira[0] == "dashboard.html", (
        "a pagina de entrada mudou de nome; ela e a que abre por duplo clique")
    assert "Estoque" in primeira[2] and "Custo" in primeira[2]
    assert "Funding" in segunda[2] and "Detentores" in segunda[2]
    assert "Funding" not in primeira[2]



# --------------------------------------------------------------------------
# O CABECALHO.
#
# O defeito que estes testes protegem foi visto na tela e nao no codigo: a
# barra de paginas ficava FORA do <main>, irma do indice fixo de 250px, e
# como nao tinha margem era desenhada por baixo dele. As duas coisas se
# entrelacavam no alto da pagina.
#
# E havia duas faixas grudadas no topo competindo pelo mesmo lugar -- a de
# paginas e a de janelas -- o que fazia o alto da tela parecer travado.
# --------------------------------------------------------------------------

def test_ha_UM_cabecalho_so_e_ele_fica_dentro_do_conteudo(pagina_gravada):
    # Dentro do <main>: e o que lhe da a margem de 250px e o tira de baixo do
    # indice fixo. Fora dele, a barra escorregava para debaixo da lateral.
    assert pagina_gravada.count('<header id="topo">') == 1
    inicio_main = pagina_gravada.index("\n<main>")
    assert pagina_gravada.index('<header id="topo">') > inicio_main
    assert pagina_gravada.index('<header id="topo">') < pagina_gravada.index("</main>")


def test_as_duas_faixas_moram_dentro_do_cabecalho(pagina_gravada):
    inicio = pagina_gravada.index('<header id="topo">')
    fim = pagina_gravada.index("</header>")
    cabecalho = pagina_gravada[inicio:fim]
    assert 'id="paginas"' in cabecalho
    assert 'id="troca-periodo"' in cabecalho
    # E nenhuma delas aparece FORA dele.
    assert pagina_gravada.count('id="paginas"') == 1
    assert pagina_gravada.count('id="troca-periodo"') == 1


def test_o_cabecalho_gruda_no_topo_e_e_opaco(pagina_gravada):
    # Opaco porque o grafico passa por tras dele ao rolar; grudado porque o
    # seletor de janela tem de estar a mao em qualquer altura da pagina.
    assert "#topo { position: sticky; top: 0;" in pagina_gravada
    assert "background: var(--fundo);" in pagina_gravada


def test_as_duas_faixas_ficam_na_MESMA_LINHA(pagina_gravada):
    # Empilhadas, o cabecalho tinha 86px e comia um decimo da tela o tempo todo --
    # e um cabecalho fixo que ocupa tanto parece travado. Lado a lado cai para ~52.
    inicio = pagina_gravada.index("#topo { position: sticky")
    regra = pagina_gravada[inicio:pagina_gravada.index("}", inicio)]
    assert "display: flex" in regra
    assert "justify-content: space-between" in regra
    # E volta a empilhar em tela estreita, que e quando o espaco justifica.
    assert "flex-wrap: wrap" in regra


def test_nenhum_comentario_do_css_contem_TAG_literal(pagina_gravada):
    # O DEFEITO QUE ISTO PEGA: o CSS vai inteiro para dentro do HTML, e um
    # comentario que escreva "<main>" faz quem procurar essa marca no arquivo
    # achar o comentario primeiro. Foi o que quebrou o recorte da pagina do
    # calendario, que ancorava nessa marca -- metade da folha de estilo foi parar
    # dentro de uma secao recolhivel.
    import re

    estilo_ = pagina_gravada[pagina_gravada.index("<style>"):pagina_gravada.index("</style>")]
    for comentario in re.findall(r"/\*.*?\*/", estilo_, flags=re.S):
        for tag in ("<main>", "<nav>", "<header", "<section", "<details"):
            assert tag not in comentario, (tag, comentario[:80])


def test_o_conteudo_nao_estoura_a_largura(pagina_gravada):
    # Rolagem horizontal fazia o cabecalho grudado ficar preso a uma largura maior
    # que a tela, e ai ele parecia travado ao rolar de lado.
    assert "section > div { max-width: 100%; overflow-x: auto; }" in pagina_gravada


def test_nenhuma_legenda_tem_ACENTO_SEGUIDO_DE_DIGITO():
    # O RASTRO DE UM ESCAPE MAL FEITO. Os .py deste projeto sao ASCII por regra, e
    # os acentos entram como uXXXX escapado. Um script de edicao que troca "@e" por
    # o escape de e-agudo transforma "@e9" no e-agudo seguido do algarismo NOVE.
    # Nada quebra: o arquivo continua ASCII, os testes passam, e a pagina publica
    # "a LFT e9 54,3% do estoque".
    #
    # Aconteceu doze vezes em 21/08/2026, em duas legendas, e foi para o ar. So se
    # ve lendo o texto renderizado -- que e o que este teste faz.
    import re

    suspeitos = []
    for g in dashboard.REGISTRO:
        for campo in (g.titulo, g.nota, g.fonte):
            for m in re.finditer(".{0,20}[\u00c0-\u00ff][0-9].{0,20}", campo):
                suspeitos.append(g.id + ": ..." + m.group(0) + "...")
    assert not suspeitos, (
        "acento colado num algarismo, quase certamente escape mal feito:"
        + chr(10) + chr(10).join(suspeitos))
