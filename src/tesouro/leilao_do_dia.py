"""Os comandos do dia de leilao.

    python -m tesouro.leilao_do_dia modelo   cria a planilha de hoje
    python -m tesouro.leilao_do_dia oferta   desenha o que voce preencheu
    python -m tesouro.leilao_do_dia          pega o RESULTADO pela API

SAO TRES MOMENTOS, e cada comando cobre um.

1. DE MANHA, quando o Tesouro anuncia a oferta. Nao ha taxa publicada, e para
   desenhar qualquer barra ela e necessaria. Quem acompanha o mercado sabe a
   taxa do momento; a suposicao automatica (a do leilao anterior) erra 11 bp na
   mediana. Entao o modelo pede a dela, e so supre o que ficar em branco.
   A barra sai como TETO: a quantidade ofertada, que historicamente cai para
   83,9% dela.

2. A TARDE, quando sai o resultado. Ai o dado e publico e vem pela API -- ou,
   se o certificado da rede barrar, pelo arquivo que alguem salvar a mao. A
   quantidade aceita substitui o teto sozinha, pela chave do leilao.

3. DIAS DEPOIS, quando o historico-leiloes-todos.xls traz o mesmo leilao. A
   linha provisoria some sozinha, e ninguem precisa lembrar de limpar.

Nenhum passo termina em silencio. Se algo der errado, a mensagem diz O QUE e O
QUE FAZER -- inclusive a linha do Excel, quando o problema esta na planilha.
"""
import sys
import traceback

import pandas as pd

from . import (api_leiloes, entrada_manual, fetch_leiloes_api,
               leilao_ofertado, leiloes_dv, leiloes_recentes,
               parse_api_leiloes, parse_leiloes_api)
from .graficos import painel_emissoes

# Quantos dias de resultado comparar com o historico a cada rodada. A API devolve
# tudo desde 2018; o que e antigo a planilha ja tem, e mandar 6.944 linhas para a
# mesclagem toda tarde e trabalho a toa. Trinta dias cobrem com folga o atraso da
# planilha, que foi de cinco dias em 20/08/2026.
DIAS_PARA_TRAS = 30


def da_planilha_preenchida(caminho=None, refazer_graficos=True):
    """O caminho da OFERTA: o que ela digitou, sem passar pela rede.

    Existe porque na hora da oferta ela sabe a taxa e eu nao. A alternativa
    automatica empresta a do leilao anterior e erra 11 bp na mediana; a dela nao
    erra, porque e a leitura do mercado naquele momento.

    A taxa que ficar em branco na planilha ainda recebe a emprestada -- assim uma
    linha sem opiniao continua desenhavel, e a marca 'taxa_suposta' diz quais foram.
    """
    print("1. lendo a planilha preenchida...")
    tabela, digitadas = entrada_manual.ler(caminho)
    print(f"   {len(tabela)} linha(s) com quantidade ofertada")
    print(f"   {digitadas} com taxa digitada por voce"
          + (f"; nas outras {len(tabela) - digitadas} eu uso a do leilao anterior"
             if digitadas < len(tabela) else ""))
    if digitadas < len(tabela):
        _avisar_sobre_a_taxa(tabela)

    return _guardar_e_desenhar(tabela, "ofertado", refazer_graficos)


def _proximo_dia_util(quando):
    """D+1 pelo calendario de verdade, feriado inclusive.

    O caminho da PLANILHA usa D+1 pulando so o fim de semana, e o comentario de
    la diz por que: "feriado ela corrige na propria planilha". Aqui nao ha
    planilha nem ninguem para corrigir -- este caminho roda sozinho dentro do
    pipeline -- entao a regra tem de estar completa no codigo.
    """
    from . import calendario

    cal = calendario.padrao()
    dia = pd.Timestamp(quando).normalize() + pd.Timedelta(days=1)
    while not cal.eh_dia_util(dia.date()):
        dia += pd.Timedelta(days=1)
    return dia


def tabela_do_edital(quando=None):
    """As pernas ofertadas hoje, no esquema do leiloes.csv, ou None.

    O /editais sai a partir das 10h30 e traz exatamente o que foi ofertado, por
    benchmark. Ate 24/09/2026 so o caminho MANUAL o lia, e o pipeline nunca
    chamava esse caminho: a oferta do dia simplesmente nao existia para os
    graficos, e a hachura do "ofertado" nao tinha o que hachurar.

    FILTRA PELO DIA. O endpoint devolve o edital vigente, que antes das 10h30
    ainda pode ser o do leilao anterior -- gravar o que vier marcaria oferta de
    ontem como de hoje.

    Sem taxa: nada foi negociado ainda. Quem empresta a do leilao anterior e
    leiloes_dv, no calculo do DV, e a marca 'taxa_suposta' diz quais foram.
    """
    quando = (pd.Timestamp(quando).normalize() if quando is not None
              else pd.Timestamp.today().normalize())
    registros, _ = api_leiloes.buscar("editais")
    if not len(registros):
        return None
    edital = parse_api_leiloes.editais(registros)
    do_dia = edital[edital["data_leilao"].dt.normalize() == quando]
    if do_dia.empty:
        return None
    # A liquidacao nao vem no edital, e o tradutor a deixa vazia de proposito --
    # ver parse_api_leiloes.editais.
    return do_dia.assign(data_liquidacao=_proximo_dia_util(quando))


def _o_que_o_calendario_diz(quando, registros=None):
    """Por que nao ha edital: nao e dia de leilao, ou ainda nao saiu?

    A FRASE ANTIGA DIZIA AS DUAS COISAS AO MESMO TEMPO. "nao ha edital para este
    dia -- nada a gravar" serve para "hoje nao tem leilao" e para "hoje tem
    leilao e o Tesouro ainda nao publicou", que sao avisos opostos: o primeiro
    manda esquecer, o segundo manda voltar mais tarde.

    MEDIDO EM 08/10/2026, e e dela o achado. Ela rodou o atalho as 10:32 numa
    quinta-feira -- dia de prefixado -- leu a frase como "hoje nao tem leilao" e
    achou estranho ver o resultado publicado depois. Os tres instantes:

        10:11   a API nao tinha edital nem resultado para 08/10
        10:32   idem -- o leilao ainda nao havia acontecido
        14:36   edital E resultado, as seis pernas (3 LTN, 3 NTN-F)

    TRES RESPOSTAS, e a terceira e a que este projeto obriga. Passada a ultima
    data que o Tesouro publicou, dizer "nao tem leilao" seria plausivel e errado
    -- e errado exatamente onde a frase soa mais segura. Ali a resposta e nao
    sei, com a data em que o calendario acaba.

    Recebe 'registros' para os testes nao tocarem a rede.
    """
    from . import api_leiloes, parse_api_leiloes

    # SEM DATA QUER DIZER HOJE. pd.Timestamp(None) e NaT, e NaT nao tem
    # .normalize() -- AttributeError em vez da frase que esta funcao existe
    # para dizer.
    #
    # SO ESTOURAVA NO DIA EM QUE NAO HA EDITAL AINDA, porque este caminho so e
    # alcancado quando tabela_do_edital devolve None. Ou seja: todo dia de
    # leilao ANTES das 10h -- exatamente a janela em que o modo 'hoje' roda.
    # Achado em 05/11/2026, as 9h47, com leilao marcado para as 10h.
    quando = (pd.Timestamp.today() if quando is None
              else pd.Timestamp(quando)).normalize()
    try:
        if registros is None:
            # DISCO PRIMEIRO -- ver api_leiloes.calendario_publicado.
            registros, _, _ = api_leiloes.calendario_publicado()
        if not len(registros):
            return ("   e o calendario do Tesouro voltou vazio, entao nao da "
                    "para dizer se hoje e dia de leilao.")
        agenda = parse_api_leiloes.calendario(registros)
    except (LookupError, OSError) as erro:
        # NAO AFIRMA NADA quando a fonte da resposta falhou. A frase sem o
        # calendario e a frase antiga, e era ela o problema.
        return ("   e o calendario do Tesouro nao pode ser consultado (%s), "
                "entao nao da para dizer se hoje e dia de leilao." % erro)

    # "HOJE" SO QUANDO E HOJE. A funcao aceita 'quando', e chamada com outra
    # data ela dizia "para hoje" de qualquer jeito -- rotulo descolado do dado,
    # que e o defeito que este projeto pegou tres vezes em 09/09/2026.
    dia = ("hoje" if quando == pd.Timestamp.today().normalize()
           else quando.strftime("%d/%m/%Y"))

    dias = agenda["data_leilao"].dt.normalize()
    do_dia = agenda[dias == quando]
    if not do_dia.empty:
        papeis = ", ".join(sorted(set(do_dia["titulo"])))
        return ("   o calendario do Tesouro traz %s para %s, e o edital ainda "
                "nao foi publicado.\n"
                "   O leilao acontece perto do meio-dia e o resultado sai de "
                "tarde -- rode de novo depois disso." % (papeis, dia))

    ultimo = dias.max()
    if quando > ultimo:
        return ("   e o calendario publicado do Tesouro termina em %s, entao "
                "nao da para dizer se %s e dia de leilao." %
                (ultimo.strftime("%d/%m/%Y"), quando.strftime("%d/%m/%Y")))
    return ("   e o calendario do Tesouro nao traz leilao para %s "
            "(ele vai ate %s)." % (dia, ultimo.strftime("%d/%m/%Y")))


def do_edital(quando=None, refazer_graficos=True):
    """O caminho da OFERTA sem digitacao: o que o Tesouro anunciou hoje.

    Nao substitui o caminho da planilha. Aquele existe porque ela sabe a taxa do
    momento e eu nao -- e a taxa digitada continua vencendo a emprestada, pela
    ordem de estagios. Este aqui garante que a oferta APARECA mesmo nos dias em
    que ninguem digitou nada, que era o buraco: em 20/08/2026 tres pernas de LTN
    ficaram fora do grafico sem que nada avisasse.
    """
    print("1. buscando o edital do dia na API do Tesouro...")
    try:
        tabela = tabela_do_edital(quando)
    except LookupError as erro:
        print("   o /editais nao respondeu no formato esperado: %s" % erro)
        return 0
    if tabela is None:
        # NAO BASTA DIZER QUE NAO HA -- ver _o_que_o_calendario_diz.
        print("   nao ha edital para este dia na API,")
        print(_o_que_o_calendario_diz(quando))
        return 0
    print("   %d perna(s) ofertada(s): %s"
          % (len(tabela), ", ".join(sorted(set(tabela["titulo"])))))
    return _guardar_e_desenhar(tabela, "ofertado", refazer_graficos)


def _guardar_e_desenhar(tabela, estagio, refazer_graficos):
    """Do dado normalizado ate as paginas gravadas. Comum aos dois caminhos."""
    print("2. comparando com o historico da planilha do Tesouro...")
    destino, entraram, na_planilha, no_provisorio = \
        leiloes_recentes.gravar_recentes(tabela, estagio)
    # CADA MOTIVO COM O SEU NOME -- ver o docstring de gravar_recentes. A frase
    # unica dizia "que a planilha ja tinha" para as duas coisas, e em 08/10/2026
    # anunciou que a planilha havia alcancado seis leiloes que ela nao tem.
    print(f"   {entraram} nova(s), {na_planilha} que a planilha do Tesouro ja "
          f"tem, {no_provisorio} que o provisorio ja cobria")
    print(f"   gravado: {destino}")

    if entraram == 0:
        if na_planilha and not no_provisorio:
            print("\nNada novo: a planilha do Tesouro ja alcancou estas linhas "
                  "-- os graficos continuam validos como estao.")
        elif no_provisorio and not na_planilha:
            print("\nNada novo: estas linhas ja estavam aqui, num estagio igual "
                  "ou mais adiantado. A planilha do Tesouro NAO as alcancou "
                  "ainda -- os graficos continuam validos como estao.")
        else:
            print("\nNada novo: parte ja esta na planilha do Tesouro, parte ja "
                  "estava aqui num estagio igual ou mais adiantado -- os "
                  "graficos continuam validos como estao.")
        return 0

    print("3. recalculando o DV01, com o provisorio...")
    leiloes_dv.gravar(ate_o_estagio="ofertado")

    if refazer_graficos:
        print("4. regravando as paginas de emissao...")
        for caminho_html in painel_emissoes.grava_todas():
            print(f"   {caminho_html}")

    # A HACHURA MARCA O OFERTADO desde 09/09/2026, e nao mais o aceito. Esta
    # linha dizia o contrario, e mensagem de log que descreve errado o grafico e
    # pior que mensagem nenhuma.
    marca = ("contorno e hachura" if estagio == "ofertado"
             else "barra solida, como o resto")
    print(f"\nPronto. {entraram} linha(s) entraram como {estagio.upper()} -- "
          f"aparecem com {marca} nos graficos.")
    if estagio == "ofertado":
        print("Quando o resultado sair, rode  python -m tesouro.leilao_do_dia  "
              "para pegar o aceito pela API: ele substitui o teto sozinho.")
    else:
        # A FRASE ANTIGA PROMETIA O QUE NAO ACONTECIA: "quando a planilha do
        # Tesouro trouxer este leilao, a linha some sozinha". Medido em
        # 08/10/2026 -- fetch_leiloes.baixar nunca rebaixava a planilha, entao
        # ela nunca trazia o leilao e a linha nunca sumia. O estado real: o
        # numero esta certo (o provisorio tem taxa e financeiro do proprio
        # Tesouro), e a linha fica.
        print("A linha fica como provisoria. Ela so sai quando a planilha do "
              "Tesouro for rebaixada -- o que NAO acontece sozinho: rode com "
              "--rebaixar-planilha quando quiser renovar.")
    return entraram


def rodar(refazer_graficos=True, dias=DIAS_PARA_TRAS):
    """O caminho do RESULTADO. Pela API do Tesouro; se ela falhar, pelo arquivo
    salvo a mao.

    A API vem PRIMEIRO desde 20/08/2026, quando se descobriu que o apiapex responde
    nesta rede -- o que o portal de dados abertos nao faz, por causa da inspecao de
    TLS. Antes disso a via principal era alguem salvar o arquivo no disco.

    'dias' limita o que se compara com o historico: /resultados devolve tudo desde
    2018, e mandar 6.944 linhas para a mesclagem toda tarde e trabalho a toa. O que
    e antigo a planilha ja tem.
    """
    print("1. buscando o resultado dos leiloes na API do Tesouro...")
    try:
        caminho, registros = api_leiloes.guardar("resultados")
        tabela = parse_api_leiloes.resultados(registros)
        print(f"   {len(registros)} leiloes, {len(tabela)} linhas com as voltas "
              f"desdobradas")
        print(f"   resposta crua guardada em {caminho.name}")
        via = "API"
    except ConnectionError as erro:
        print(f"   {erro}")
        print("\n   vou procurar arquivo salvo a mao.")
        caminho, via = fetch_leiloes_api.obter(None)
        tabela, estagio_do_arquivo = parse_leiloes_api.normalizar(caminho)
        print(f"   {caminho.name}, via {via}, estagio {estagio_do_arquivo}")
        return _guardar_e_desenhar(tabela, estagio_do_arquivo, refazer_graficos)

    if dias:
        corte = tabela["data_leilao"].max() - pd.Timedelta(days=dias)
        antes = len(tabela)
        tabela = tabela[tabela["data_leilao"] >= corte]
        print(f"   dos ultimos {dias} dias: {len(tabela)} de {antes} linhas "
              f"(o resto a planilha ja tem)")

    return _guardar_e_desenhar(tabela, "aceito", refazer_graficos)


def _avisar_sobre_a_taxa(tabela):
    """Diz de quando veio a taxa emprestada, e avisa quando ela e velha.

    A oferta nao traz taxa, e sem taxa nao ha financeiro nem DV01. A do leilao
    anterior do mesmo papel erra 11 bp na mediana -- MAS isso foi medido com o
    leilao anterior em ate 45 dias. Alem disso o mercado ja e outro, e o erro nao e
    mais o que esta medido. A linha nao e recusada; quem roda e avisado.
    """
    preenchida = leilao_ofertado.preencher(tabela)
    velhas = preenchida[preenchida["taxa_velha"]]
    sem_taxa = preenchida[preenchida["taxa_media_pct"].isna()]
    print(f"   taxa emprestada do leilao anterior de cada papel; idade mediana "
          f"{preenchida['taxa_dias_de_idade'].median():.0f} dia(s)")
    if len(velhas):
        print(f"   ATENCAO: em {len(velhas)} linha(s) a taxa tem mais de "
              f"{leilao_ofertado.DIAS_MAXIMOS_PARA_A_TAXA} dias -- o erro medido "
              f"(11 bp na mediana) nao vale para elas:")
        for _, r in velhas.iterrows():
            print(f"     {r['titulo']} {r['data_vencimento']:%d/%m/%Y}: taxa de "
                  f"{r['taxa_de_quando']:%d/%m/%Y} "
                  f"({int(r['taxa_dias_de_idade'])} dias)")
    if len(sem_taxa):
        print(f"   {len(sem_taxa)} linha(s) sem leilao anterior: entram so com "
              f"quantidade, sem financeiro e sem DV01.")


# Os tres subcomandos, e o que cada um significa no dia.
_AJUDA = """uso:
  python -m tesouro.leilao_do_dia modelo   -> cria a planilha de hoje para preencher
  python -m tesouro.leilao_do_dia oferta   -> desenha a partir do que voce preencheu
  python -m tesouro.leilao_do_dia          -> pega o RESULTADO (API ou arquivo salvo)

o dia tipico:
  de manha, quando sai o edital:  modelo, preencher no Excel, depois  oferta
  a tarde, quando sai o resultado:  (sem argumento)
  e quando o historico-leiloes-todos.xls chegar, a linha provisoria some sozinha."""


def main(argumentos=None):
    argumentos = sys.argv[1:] if argumentos is None else argumentos
    comando = (argumentos[0].lower() if argumentos else "")

    if comando in ("-h", "--help", "ajuda"):
        print(_AJUDA)
        return 0

    try:
        if comando == "modelo":
            caminho, do_edital = entrada_manual.modelo()
            print(f"planilha criada: {caminho}\n")
            if do_edital:
                print("As quantidades JA VIERAM DO EDITAL de hoje -- sao as pernas "
                      "que o Tesouro ofertou, com os numeros dele.")
                print("Confira, e apague a linha que nao quiser no grafico.")
            else:
                print("A API nao tinha edital para hoje, entao montei a planilha "
                      "pelo historico e as quantidades vieram VAZIAS.")
                print("Preencha a QUANTIDADE OFERTADA das linhas em oferta hoje, e "
                      "apague as que nao estao.")
            print("A TAXA e opcional: em branco, eu uso a do leilao anterior "
                  "daquele papel (erra 11 bp na mediana).")
            print("\nDepois:  python -m tesouro.leilao_do_dia oferta")
            return 0
        if comando == "oferta":
            da_planilha_preenchida()
            return 0
        if comando:
            print(f"nao conheco o comando {comando!r}.\n\n{_AJUDA}",
                  file=sys.stderr)
            return 4
        rodar()
        return 0
    except FileExistsError as erro:
        print(f"\n{erro}", file=sys.stderr)
        return 5
    except FileNotFoundError as erro:
        # As vias falharam. A mensagem de origem ja diz o que fazer; repeti-la aqui
        # e o ponto, porque e o unico texto que a pessoa vai ler.
        print(f"\n{erro}", file=sys.stderr)
        return 2
    except LookupError as erro:
        # O arquivo veio mas nao deu para ler. Idem: a mensagem diz a linha do
        # Excel ou lista as colunas reais, que e o que permite consertar sem
        # adivinhar.
        print(f"\nO arquivo chegou, mas nao consegui ler:\n\n{erro}",
              file=sys.stderr)
        return 3
    except Exception:                                    # noqa: BLE001
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
