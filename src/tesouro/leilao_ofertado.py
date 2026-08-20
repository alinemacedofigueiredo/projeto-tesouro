"""O leilao antes de acontecer: quantidade ofertada, sem taxa e sem financeiro.

O PROBLEMA. No momento da oferta o Tesouro anuncia QUANTO vai ofertar de cada papel,
e mais nada. Nao ha taxa, e sem taxa nao ha PU, e sem PU nao ha financeiro nem DV01 --
que sao as duas moedas em que os graficos de emissao contam.

Duas coisas precisam ser supostas para desenhar qualquer barra, e elas custam MUITO
DIFERENTE. Medido no historico desde 2015:

  A TAXA e barata. Usar a do leilao anterior do mesmo papel-vencimento (ate 45 dias,
  so 1a volta, so leiloes com aceite) erra 11,0 bp na mediana, 36,7 bp no p90 e
  87,4 bp no p99. E o que 25 bp de erro de taxa fazem no DV01 do lote e pouco:
  mediana 0,55%, p90 2,1%, p99 6,8%. O DV01 quase nao se move com a taxa.

  A QUANTIDADE e cara. O Tesouro NAO aceita tudo o que oferta: em 9.801 linhas de
  leilao desde 2015, ele aceitou tudo em 42,6% e aceitou ZERO em 19,5%. No agregado
  aceita 83,9% da quantidade ofertada -- e desigualmente por papel: 88,0% em LTN,
  83,4% em NTN-F, 66,7% em LFT, 62,5% em NTN-B.

DAI A DECISAO DE DESENHO: a barra da oferta e um TETO, e nao uma previsao. Ela
responde "quanto no MAXIMO entra hoje, se ele aceitar tudo aproximadamente ao preco
de ontem" -- e nao "quanto vai entrar". Por isso ela aparece so com contorno, vazia
por dentro, e a legenda diz "teto".

NAO aplicamos os 83,9% para "corrigir" a barra. Seria trocar um numero honesto e
declarado (o teto) por um numero inventado que parece medido -- e o desvio por papel,
de 62,5% a 88,0%, mostra que a razao media nao descreve leilao nenhum. O teto e
verdade sobre o que foi anunciado; a razao media e uma aposta.
"""
import pandas as pd

from . import calendario, config, precificacao

# Ate quantos dias atras vale procurar a taxa do leilao anterior. Alem disso o
# mercado ja e outro -- e foi com esse corte que os numeros do cabecalho foram
# medidos.
DIAS_MAXIMOS_PARA_A_TAXA = 45

# Os erros medidos, guardados aqui para que o teste possa trava-los. Se o dado mudar
# e a suposicao piorar, alguem precisa ver.
ERRO_DA_TAXA_MEDIANA_BP = 11.0
ERRO_DA_TAXA_P90_BP = 36.7
RAZAO_ACEITO_SOBRE_OFERTADO = 0.839

PAPEIS_PRECIFICADOS = ("LTN", "NTN-F", "NTN-B", "LFT")


def taxas_de_referencia(base=None):
    """A ultima taxa observada em leilao, por (titulo, data_vencimento).

    E a taxa que o proprio Tesouro praticou naquele papel da ultima vez -- nao uma
    taxa de mercado, que este projeto nao tem fonte para ler.

    O FILTRO E POR QUANTIDADE ACEITA, e nao por taxa diferente de zero, e a
    diferenca importa. Quando nada e aceito a planilha grava taxa 0,00, e comparar
    contra isso e comparar contra ausencia de dado -- era a cauda de 1.500 bp da
    medicao. MAS na LFT o zero e legitimo: a "taxa" dela e agio sobre a Selic, e
    zero quer dizer vendida ao par, com PU igual ao VNA. Sao 18 vencimentos assim,
    todos com quantidade e financeiro de verdade. Filtrar por taxa != 0 os jogaria
    fora sem motivo.
    """
    if base is None:
        base = pd.read_csv(
            config.PROCESSED_DIR / "leiloes.csv",
            parse_dates=["data_leilao", "data_liquidacao", "data_vencimento"],
        )
    d = base[base["tipo_leilao"].isin(["Venda", "Extra Venda"])]
    # So os papeis que este projeto sabe precificar. Emprestar a taxa de uma NTN-D
    # nao serviria para nada -- preencher() a descartaria adiante de qualquer jeito
    # -- e ela traria os proprios zeros para a tabela, confundindo quem a olhar.
    d = d[d["titulo"].isin(PAPEIS_PRECIFICADOS)]
    d = d[d["taxa_media_pct"].notna()]
    d = d[d["venda_qtd"].fillna(0) > 0]
    d = d.sort_values("data_leilao")
    ultima = d.groupby(["titulo", "data_vencimento"]).agg(
        taxa_media_pct=("taxa_media_pct", "last"),
        data_leilao=("data_leilao", "last"),
    )
    return ultima


def preencher(ofertados, base=None, cal=None):
    """Completa as linhas de oferta com taxa suposta e financeiro calculado.

    Devolve a tabela com tres colunas a mais, e elas existem para que ninguem
    confunda o suposto com o observado:

      taxa_suposta      -- True quando a taxa veio do leilao anterior;
      taxa_de_quando    -- a data daquele leilao anterior;
      financeiro_calculado -- True quando o financeiro saiu de qtd x PU, e nao do
                              Tesouro.

    A quantidade da oferta vai para 'venda_qtd' de proposito: dali para a frente o
    resto do caminho trata a linha como qualquer outra, e a diferenca fica registrada
    no estagio e nestas tres colunas. Chamar de venda_qtd o que e teto seria mentira
    se o estagio nao acompanhasse -- e ele acompanha.
    """
    cal = cal or calendario.padrao()
    ultima = taxas_de_referencia(base)
    saida = ofertados.copy()

    taxas, quandos, supostas = [], [], []
    for _, r in saida.iterrows():
        chave = (r["titulo"], r["data_vencimento"])
        if pd.notna(r.get("taxa_media_pct")):
            taxas.append(r["taxa_media_pct"])
            quandos.append(pd.NaT)
            supostas.append(False)
        elif chave in ultima.index:
            linha = ultima.loc[chave]
            taxas.append(float(linha["taxa_media_pct"]))
            quandos.append(linha["data_leilao"])
            supostas.append(True)
        else:
            # Papel novo, sem leilao anterior. Sem taxa nao ha PU: a linha fica sem
            # financeiro e sem DV, e o grafico mostra so a quantidade. Inventar uma
            # taxa aqui seria o defeito plausivel-e-errado de sempre.
            taxas.append(None)
            quandos.append(pd.NaT)
            supostas.append(True)

    saida["taxa_media_pct"] = taxas
    saida["taxa_de_quando"] = quandos
    saida["taxa_suposta"] = supostas

    # A idade da taxa emprestada. Os erros do cabecalho foram medidos com a taxa do
    # leilao anterior em ATE 45 dias; alem disso o mercado ja e outro e o erro nao
    # e mais o que esta medido aqui. A linha nao e recusada -- teto com taxa velha
    # ainda diz mais que barra nenhuma -- mas quem roda precisa ser avisado.
    saida["taxa_dias_de_idade"] = (
        saida["data_leilao"] - saida["taxa_de_quando"]).dt.days
    saida["taxa_velha"] = (
        saida["taxa_dias_de_idade"] > DIAS_MAXIMOS_PARA_A_TAXA).fillna(False)

    # A quantidade ofertada e o teto do que pode ser emitido hoje.
    saida["venda_qtd"] = saida["oferta_qtd"]

    # Uma leitura so do vna.csv, e nao uma por linha.
    vna = pd.read_csv(config.PROCESSED_DIR / "vna.csv", parse_dates=["data"])

    financeiros, calculados = [], []
    for _, r in saida.iterrows():
        if (pd.isna(r["taxa_media_pct"]) or pd.isna(r["venda_qtd"])
                or r["titulo"] not in PAPEIS_PRECIFICADOS):
            financeiros.append(None)
            calculados.append(False)
            continue
        try:
            preco = precificacao.pu(cal, r["titulo"],
                                    r["data_liquidacao"].date(),
                                    r["data_vencimento"].date(),
                                    r["taxa_media_pct"] / 100.0,
                                    _vna_do_mes(vna, r))
        except Exception:                                # noqa: BLE001
            financeiros.append(None)
            calculados.append(False)
            continue
        financeiros.append(preco * r["venda_qtd"] / 1e6)
        calculados.append(True)

    saida["financeiro_milhoes"] = financeiros
    saida["financeiro_calculado"] = calculados
    return saida


def _vna_do_mes(vna, r):
    """O VNA do mes para NTN-B e LFT; None para os prefixados.

    No estagio da oferta NAO da para recuperar o VNA exato: a recuperacao divide o
    financeiro publicado pela cotacao, e financeiro publicado e justamente o que
    ainda nao existe. Fica o VNA do mes, cujo erro medido e de 0,156% na mediana --
    pequeno perto do que a suposicao de quantidade ja custa.
    """
    if r["titulo"] not in ("NTN-B", "LFT"):
        return None
    indice = "IPCA" if r["titulo"] == "NTN-B" else "SELIC"
    d = vna[(vna["indice"] == indice) & (vna["data"] <= r["data_liquidacao"])]
    if d.empty:
        return None
    return float(d.sort_values("data").iloc[-1]["vna"])
