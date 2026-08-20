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

from . import (entrada_manual, fetch_leiloes_api, leilao_ofertado,
               leiloes_dv, leiloes_recentes, parse_leiloes_api)
from .graficos import painel_emissoes

# Formatos que valem a pena tentar, do mais facil de ler para o menos.
_PREFERENCIA = ("json", "csv", "xlsx", "xls")


def escolher_recurso(recursos):
    """Qual dos recursos do dataset baixar.

    Nao adivinha pelo nome: ordena por formato preferido e, dentro do formato, pelo
    mais recentemente modificado. Se o portal reorganizar, isto continua achando
    alguma coisa -- e o log mostra a lista inteira para conferencia.
    """
    def peso(r):
        formato = str(r.get("format", "")).lower().strip(". ")
        ordem = _PREFERENCIA.index(formato) if formato in _PREFERENCIA else 99
        return (ordem, str(r.get("last_modified") or ""))

    candidatos = sorted(recursos, key=peso)
    return candidatos[0] if candidatos else None


def _linha_do_recurso(r):
    return (f"  - {r.get('name')!r} [{r.get('format')}] "
            f"modificado em {r.get('last_modified')}")


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
        print("4. regravando as quatro paginas de emissao...")
        for caminho_html in painel_emissoes.grava_as_quatro():
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


def rodar(url_do_recurso=None, refazer_graficos=True):
    """O caminho do RESULTADO: pela rede, ou pelo arquivo salvo a mao."""
    if url_do_recurso is None:
        print("1. procurando o recurso no portal...")
        try:
            recursos = fetch_leiloes_api.recursos_do_dataset()
            print(f"   o dataset tem {len(recursos)} recurso(s):")
            for r in recursos:
                print(_linha_do_recurso(r))
            escolhido = escolher_recurso(recursos)
            url_do_recurso = escolhido.get("url") if escolhido else None
            print(f"   escolhido: {escolhido.get('name')!r}" if escolhido
                  else "   nenhum recurso utilizavel")
        except Exception as erro:                        # noqa: BLE001
            print(f"   a rede nao respondeu: {erro}")
            print("   vou procurar arquivo salvo a mao.")

    print("2. obtendo o arquivo...")
    caminho, via = fetch_leiloes_api.obter(url_do_recurso)
    print(f"   {caminho.name}, via {via}")

    print("3. traduzindo para o esquema do leiloes.csv...")
    tabela, estagio = parse_leiloes_api.normalizar(caminho)
    print(f"   {len(tabela)} linha(s), de "
          f"{tabela['data_leilao'].min():%d/%m/%Y} a "
          f"{tabela['data_leilao'].max():%d/%m/%Y}")
    print(f"   estagio detectado: {estagio.upper()}"
          + ("  (o resultado ja saiu)" if estagio == "aceito"
             else "  (so o teto anunciado; a quantidade ainda vai cair)"))

    if estagio == "ofertado":
        _avisar_sobre_a_taxa(tabela)

    return _guardar_e_desenhar(tabela, estagio, refazer_graficos)


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
            caminho = entrada_manual.modelo()
            print(f"planilha criada: {caminho}\n")
            print("Preencha a QUANTIDADE OFERTADA das linhas que estao em oferta "
                  "hoje, e apague as que nao estao.")
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
