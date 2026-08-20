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


def _guardar_e_desenhar(tabela, estagio, refazer_graficos):
    """Do dado normalizado ate as paginas gravadas. Comum aos dois caminhos."""
    print("2. comparando com o historico da planilha do Tesouro...")
    destino, entraram, ja_estavam = leiloes_recentes.gravar_recentes(tabela, estagio)
    print(f"   {entraram} nova(s), {ja_estavam} que a planilha ja tinha")
    print(f"   gravado: {destino}")

    if entraram == 0:
        print("\nNada novo. A planilha do Tesouro ja alcancou tudo -- os graficos "
              "continuam validos como estao.")
        return 0

    print("3. recalculando o DV01, com o provisorio...")
    leiloes_dv.gravar(ate_o_estagio="ofertado")

    if refazer_graficos:
        print("4. regravando as paginas de emissao...")
        for caminho_html in painel_emissoes.grava_todas():
            print(f"   {caminho_html}")

    marca = "contorno claro" if estagio == "ofertado" else "hachura"
    print(f"\nPronto. {entraram} linha(s) entraram como {estagio.upper()} -- "
          f"aparecem com {marca} nos graficos.")
    if estagio == "ofertado":
        print("Quando o resultado sair, rode  python -m tesouro.leilao_do_dia  "
              "para pegar o aceito pela API: ele substitui o teto sozinho.")
    else:
        print("Quando a planilha do Tesouro trouxer este leilao, a linha some "
              "sozinha.")
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
