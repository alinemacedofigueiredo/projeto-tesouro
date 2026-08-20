"""Um comando so, para rodar depois que o resultado do leilao sai.

    python -m tesouro.leilao_do_dia

Ele faz, nesta ordem:

  1. tenta a rede; se o certificado barrar, usa o arquivo que alguem salvou a mao em
     data/raw/leiloes_api/;
  1b. descobre sozinho se aquele arquivo e a OFERTA ou o RESULTADO, olhando se ha
     quantidade aceita dentro dele;
  2. traduz o arquivo para o esquema do leiloes.csv;
  3. compara com o historico e guarda so o que a planilha ainda nao tem;
  4. recalcula o DV01 incluindo o provisorio;
  5. regrava as quatro paginas de emissao.

E imprime, em cada passo, o numero que permite saber se deu certo. Um comando que
termina em silencio nao serve: quem roda isso as sete da noite precisa ver "entraram
6 linhas de 20/08/2026", e nao um prompt vazio.

QUANDO A PLANILHA ALCANCA, o provisorio some sozinho -- a comparacao e refeita a
cada rodada. Nao ha nada para limpar a mao.
"""
import sys
import traceback

from . import (fetch_leiloes_api, leilao_ofertado, leiloes_dv,
               leiloes_recentes, parse_leiloes_api)
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


def rodar(url_do_recurso=None, refazer_graficos=True):
    """O caminho inteiro. Devolve quantas linhas novas entraram."""
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

    print("4. comparando com o historico da planilha...")
    destino, entraram, ja_estavam = leiloes_recentes.gravar_recentes(tabela, estagio)
    print(f"   {entraram} nova(s), {ja_estavam} que a planilha ja tinha")
    print(f"   gravado: {destino}")

    if entraram == 0:
        print("\nNada novo. A planilha ja alcancou tudo o que o arquivo trouxe -- "
              "os graficos continuam validos como estao.")
        return 0

    print("5. recalculando o DV01, com o provisorio...")
    leiloes_dv.gravar(ate_o_estagio="ofertado")

    if refazer_graficos:
        print("6. regravando as quatro paginas de emissao...")
        for caminho_html in painel_emissoes.grava_as_quatro():
            print(f"   {caminho_html}")

    marca = ("contorno claro" if estagio == "ofertado" else "hachura")
    print(f"\nPronto. {entraram} linha(s) entraram como {estagio.upper()} -- "
          f"aparecem com {marca} nos graficos.")
    if estagio == "ofertado":
        print("Quando o resultado sair, rode de novo com o arquivo do resultado: "
              "a quantidade aceita substitui o teto sozinha.")
    else:
        print("Quando a planilha do Tesouro trouxer este leilao, a linha some "
              "sozinha.")
    return entraram


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


def main():
    try:
        rodar()
        return 0
    except FileNotFoundError as erro:
        # As duas vias falharam. A mensagem do fetch ja diz o que fazer; repeti-la
        # aqui e o ponto, porque e o unico texto que a pessoa vai ler.
        print(f"\n{erro}", file=sys.stderr)
        return 2
    except LookupError as erro:
        # O arquivo veio mas nao deu para ler. Idem: a mensagem lista as colunas
        # reais, que e o que permite consertar sem adivinhar.
        print(f"\nO arquivo chegou, mas nao consegui ler:\n\n{erro}",
              file=sys.stderr)
        return 3
    except Exception:                                    # noqa: BLE001
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
