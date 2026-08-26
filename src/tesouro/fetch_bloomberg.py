"""Coleta taxa e VNA na Bloomberg.

Unico modulo do projeto que fala com o terminal, e o import de blpapi fica
DENTRO da funcao de coleta: assim o resto roda em maquina sem Bloomberg,
que e o cenario do ambiente de destino. Um teste le a arvore do modulo e
falha se blpapi aparecer num import de nivel de modulo.

Contrato de dados em docs/convencoes-dv.md. Pontos que o codigo respeita
e que nao sao obvios:

  A fonte @ANDE e obrigatoria no identificador do papel. Sem ela a taxa
  vem de outra origem; na ponta curta a diferenca chega a alguns bp.

  SETTLE_DT muda a data de LIQUIDACAO, nao a data do mercado. Serve para o
  VNA, que e funcao deterministica da data. NAO serve para taxa: usa-lo
  ali devolve a taxa de hoje liquidando na data pedida, o que no fim de
  2024 da 135 bp de erro. Taxa historica vem so de HistoricalDataRequest.

  O preco (PX_DIRTY_MID) nao entra em calculo nenhum -- serve so de
  referencia independente para conferir o motor de precificacao (ver
  docs/convencoes-dv.md sobre o deslocamento de D+1 nessa comparacao).

data/raw/ e imutavel por invariante do projeto -- ja perdemos dado assim
uma vez (fetch_rmd.baixar sobrescreveu em silencio, so descoberto na
revisao final do branch anterior, depois de catorze revisoes de tarefa).
Por isso a coleta aqui e incremental de verdade, nao so "nomeada por
periodo": cada chamada de baixar() monta, so pelo NOME dos arquivos ja
presentes no destino (formato ISO), o conjunto de meses que cada tipo de
arquivo (taxa, vna, preco) ja reivindica cobrir, e pede so os meses do
painel atual que faltam em QUALQUER um dos tres -- inclusive um buraco no
MEIO da serie (ex.: janeiro e marco presentes, fevereiro faltando), nao
so o que vem depois do mes mais recente. O arquivo novo e nomeado pelo
periodo que ele de fato cobre -- nunca a janela inteira do estoque -- e
se por algum motivo o nome computado ja existir, a funcao levanta erro em
vez de sobrescrever. gravar_atomico cuida da escrita (sem deixar arquivo
parcial), mas quem decide se pode escrever e este modulo, que confere
existencia antes de abrir sessao com o terminal.

Duas consequencias do desenho acima que vale registrar, nao esconder:
- Como HistoricalDataRequest pede um INTERVALO continuo (nao uma lista de
  meses), um papel cujo periodo pedido cobre um buraco no meio acaba
  recebendo de volta alguns meses que um dos tres arquivos ja tinha --
  redundante, nunca errado: parse_bloomberg concatena e fica com a ultima
  ocorrencia por (data, isin)/(data, indice), entao um valor repetido so
  e escrito de novo, nao duplicado no painel final. So o VNA (pedido mes
  a mes, nao por intervalo) evita essa redundancia.
- Ha uma janela de corrida pequena, e deliberadamente NAO fechada: entre
  o calculo do que falta (leitura dos nomes existentes) e a gravacao
  final (gravar_atomico dos tres arquivos, que so acontece depois que as
  tres puxadas terminam), outra chamada de baixar() rodando em paralelo
  calcularia o mesmo periodo e tentaria gravar o mesmo nome. No fluxo
  real -- uma pessoa, rodando na mao -- isso nao acontece; as duas
  chamadas calculariam o mesmo corte e pediriam o mesmo periodo de
  qualquer forma, entao o pior caso e trabalho duplicado, nunca dado
  perdido ou sobrescrito (a segunda gravacao esbarra no FileExistsError
  da primeira). Registrado aqui para quem for automatizar isto num
  agendador.
"""
import csv
import io
import re
from datetime import date
from pathlib import Path

import pandas as pd

from . import calendario, config
from .gravacao import gravar_atomico

TITULOS = ("LTN", "NTN-F", "NTN-B", "LFT")
CAMPO_TAXA = "YLD_YTM_MID"
# O preco nao entra em calculo nenhum: serve de referencia independente
# para o teste de coerencia. Ver docs/convencoes-dv.md sobre o D+1.
CAMPO_PRECO = "PX_DIRTY_MID"
CAMPO_VNA = {"NTN-B": ("IDX_RATIO", "IPCA"), "LFT": ("ACCUMULATED_SELIC", "SELIC")}
_HOST, _PORTA = "localhost", 8194

# O nome precisa ordenar cronologicamente em ordem alfabetica -- e o
# mesmo contrato que parse_bloomberg exige do leitor (ver seu docstring).
# So a fonte ANDE e escrita por este coletor, entao o padrao ja fixa isso
# em vez de aceitar qualquer fonte como parse_bloomberg faz do lado da
# leitura.
_PADRAO_ARQ_TAXA = re.compile(
    r"^bbg_taxas_ANDE_(?P<de>\d{4}-\d{2})_(?P<ate>\d{4}-\d{2})\.csv$"
)
_PADRAO_ARQ_VNA = re.compile(
    r"^bbg_vna_(?P<de>\d{4}-\d{2})_(?P<ate>\d{4}-\d{2})\.csv$"
)
_PADRAO_ARQ_PRECO = re.compile(
    r"^bbg_precos_ANDE_(?P<de>\d{4}-\d{2})_(?P<ate>\d{4}-\d{2})\.csv$"
)


def _estoque():
    caminho = config.PROCESSED_DIR / "estoque_titulos_vencimento.csv"
    if not caminho.exists():
        raise FileNotFoundError(
            f"{caminho} nao existe; rode a camada de dados antes "
            f"('python -m tesouro.pipeline --sem-coleta')"
        )
    df = pd.read_csv(caminho, parse_dates=["data", "vencimento"])
    return df[df["quantidade_mil"].fillna(0) > 0]


def papeis_do_estoque():
    """Papeis do escopo, com a janela em que tiveram estoque."""
    e = _estoque()
    e = e[e["titulo"].isin(TITULOS)]
    p = (e.groupby(["isin", "titulo", "vencimento"])["data"]
           .agg(primeira="min", ultima="max").reset_index())
    p["vencimento"] = p["vencimento"].dt.date
    p["primeira"] = p["primeira"].dt.date
    p["ultima"] = p["ultima"].dt.date
    return p.sort_values(["titulo", "vencimento"]).reset_index(drop=True)


def datas_do_painel():
    """Os fins de mes do estoque, mapeados para o ultimo dia util."""
    cal = calendario.padrao()
    e = _estoque()
    return sorted({cal.ultimo_dia_util_do_mes(d) for d in e["data"].dt.date})


def _meses_cobertos(destino, padrao_glob, padrao_nome):
    """O conjunto de (ano, mes) que arquivos existentes em destino ja
    reivindicam cobrir, olhando SO o nome -- nunca o conteudo.

    Cada arquivo casa o padrao ISO 'AAAA-MM_AAAA-MM' e reivindica cobrir
    TODOS os meses entre 'de' e 'ate', inclusive -- e assim que baixar()
    nomeia o que grava: o intervalo fechado que ele de fato pediu.

    E um CONJUNTO, nao so o maior 'ate' de cada tipo: a primeira versao
    deste modulo so olhava o mes mais recente coberto, e isso tinha dois
    problemas medidos na revisao -- (1) um buraco no MEIO da serie (ex.:
    pasta com 2023-01 e 2023-03, faltando 2023-02) nunca era detectado,
    porque o 'mais recente' (marco) escondia o buraco; e (2) quando um
    dos tres tipos de arquivo (taxa/vna/preco) ficava mais adiantado que
    os outros -- por exemplo uma coleta anterior interrompida entre
    gravar a taxa e gravar o vna -- o nome recalculado para a proxima
    coleta podia colidir exatamente com o arquivo mais adiantado que ja
    existia, travando em FileExistsError ate alguem apagar a mao. Um
    conjunto de meses, comparado tipo a tipo (ver baixar()), nao tem
    nenhum dos dois problemas: qualquer mes que falte em QUALQUER um dos
    tres tipos entra na proxima coleta, com um nome que nunca repete o de
    um arquivo existente.
    """
    cobertos = set()
    for arquivo in destino.glob(padrao_glob):
        casado = padrao_nome.match(arquivo.name)
        if not casado:
            continue
        ano, mes = int(casado.group("de")[:4]), int(casado.group("de")[5:7])
        ano_fim, mes_fim = int(casado.group("ate")[:4]), int(casado.group("ate")[5:7])
        while (ano, mes) <= (ano_fim, mes_fim):
            cobertos.add((ano, mes))
            mes += 1
            if mes > 12:
                mes, ano = 1, ano + 1
    return cobertos


def _sessao():
    import blpapi
    opcoes = blpapi.SessionOptions()
    opcoes.setServerHost(_HOST)
    opcoes.setServerPort(_PORTA)
    sessao = blpapi.Session(opcoes)
    if not sessao.start() or not sessao.openService("//blp/refdata"):
        raise ConnectionError(
            "nao foi possivel falar com o terminal Bloomberg. Confira se ele "
            "esta aberto e logado nesta maquina. Sem terminal, exporte por "
            "BDH e coloque o CSV em data/raw/bloomberg/ (docs/como-baixar.md)"
        )
    return blpapi, sessao


def _historico(blpapi, sessao, servico, isin, campo, inicio, fim):
    """Serie historica mensal de um campo, para um papel.

    Usa HistoricalDataRequest -- nunca SETTLE_DT -- porque so a serie
    historica devolve a taxa do MERCADO naquela data. Ver docstring do
    modulo e docs/convencoes-dv.md.
    """
    req = servico.createRequest("HistoricalDataRequest")
    req.getElement("securities").appendValue(f"/isin/{isin}@ANDE Govt")
    req.getElement("fields").appendValue(campo)
    req.set("startDate", inicio.strftime("%Y%m%d"))
    req.set("endDate", fim.strftime("%Y%m%d"))
    req.set("periodicitySelection", "MONTHLY")
    sessao.sendRequest(req)
    pontos = []
    while True:
        evento = sessao.nextEvent(30000)
        for msg in evento:
            if not msg.hasElement("securityData"):
                continue
            dados = msg.getElement("securityData")
            if dados.hasElement("securityError"):
                return []
            campos = dados.getElement("fieldData")
            for i in range(campos.numValues()):
                ponto = campos.getValue(i)
                if ponto.hasElement(campo):
                    # blpapi ja devolve um date aqui -- .date() sobre um
                    # date (em vez de datetime) levanta AttributeError.
                    pontos.append((
                        ponto.getElementAsDatetime("date"),
                        ponto.getElementAsFloat(campo),
                    ))
        if evento.eventType() == blpapi.Event.RESPONSE:
            return pontos


def _referencia(blpapi, sessao, servico, isins, campo, settle):
    """Valor do campo com override de SETTLE_DT, para varios papeis.

    So serve para o VNA (funcao deterministica da data de liquidacao) --
    nunca para taxa historica. Ver docstring do modulo.
    """
    req = servico.createRequest("ReferenceDataRequest")
    for isin in isins:
        req.getElement("securities").appendValue(f"/isin/{isin}@ANDE Govt")
    req.getElement("fields").appendValue(campo)
    override = req.getElement("overrides").appendElement()
    override.setElement("fieldId", "SETTLE_DT")
    override.setElement("value", settle.strftime("%Y%m%d"))
    sessao.sendRequest(req)
    valores = []
    while True:
        evento = sessao.nextEvent(30000)
        for msg in evento:
            if not msg.hasElement("securityData"):
                continue
            todos = msg.getElement("securityData")
            for i in range(todos.numValues()):
                dados = todos.getValue(i)
                if dados.hasElement("securityError"):
                    continue
                campos = dados.getElement("fieldData")
                if campos.hasElement(campo):
                    valores.append(campos.getElementAsFloat(campo))
        if evento.eventType() == blpapi.Event.RESPONSE:
            return valores


def _janela_incremental(p, limite):
    """Primeiro dia a pedir para o papel p, dado o corte incremental.

    limite e a data (util, de datas_do_painel()) do MES MAIS ANTIGO que
    falta em algum dos tres tipos de arquivo -- None se nao houver
    nenhuma coleta anterior (primeira coleta, pede a janela inteira).

    Um papel que ja estava ativo antes de limite so precisa do que vem
    dali para frente. Um papel que so passou a existir depois de limite
    usa a propria data de nascimento (p.primeira), nunca limite, porque
    pedir antes disso nao teria papel vivo para responder. Devolve None
    se o papel nao tem nada de novo a pedir (ja tinha saido de
    circulacao antes do corte).

    Como HistoricalDataRequest pede um INTERVALO continuo, um papel cujo
    periodo cobre um buraco no meio da serie (ver docstring do modulo)
    acaba recebendo de volta alguns meses que ja estavam cobertos --
    redundante, nao errado.
    """
    inicio = max(p.primeira, limite) if limite else p.primeira
    return inicio if inicio <= p.ultima else None


def _conteudo_taxas(papeis, limite, blpapi, sessao, servico):
    """Monta em memoria o CSV de taxa (YLD_YTM_MID, fonte ANDE)."""
    buffer = io.StringIO()
    escritor = csv.writer(buffer)
    escritor.writerow(["isin", "titulo", "vencimento", "data", "yld_ytm_mid"])
    for p in papeis.itertuples(index=False):
        inicio = _janela_incremental(p, limite)
        if inicio is None:
            continue
        for dt, valor in _historico(blpapi, sessao, servico, p.isin,
                                     CAMPO_TAXA, inicio, p.ultima):
            escritor.writerow([p.isin, p.titulo, p.vencimento, dt, valor])
    return buffer.getvalue().encode("utf-8")


def _conteudo_precos(papeis, limite, blpapi, sessao, servico):
    """Monta em memoria o CSV de preco (PX_DIRTY_MID) -- so referencia.

    Quem chama (baixar()) ja filtra a LFT fora de `papeis` antes de
    passar aqui: a serie de preco da LFT na Bloomberg e inutilizavel
    (expressa com o INDICE CORRENTE, nao o da epoca -- ver
    docs/convencoes-dv.md). Pedir e gravar esse preco nao quebraria nada
    tecnicamente, mas quem usasse este arquivo no teste de coerencia do
    motor de precificacao ia comparar a LFT contra um numero sem sentido
    e concluir, errado, que o motor esta errado.
    """
    buffer = io.StringIO()
    escritor = csv.writer(buffer)
    escritor.writerow(["isin", "titulo", "data", "px_dirty_mid"])
    for p in papeis.itertuples(index=False):
        inicio = _janela_incremental(p, limite)
        if inicio is None:
            continue
        for dt, valor in _historico(blpapi, sessao, servico, p.isin,
                                     CAMPO_PRECO, inicio, p.ultima):
            escritor.writerow([p.isin, p.titulo, dt, valor])
    return buffer.getvalue().encode("utf-8")


def _conteudo_vna(datas, blpapi, sessao, servico):
    """Monta em memoria o CSV de VNA (IDX_RATIO/NTN-B, ACCUMULATED_SELIC/LFT).

    'fator' e o campo cru da Bloomberg (ex.: 1.874868830); 'vna' e o
    fator x 1000, em reais (ver docs/convencoes-dv.md). 'divergencia' tem
    de estar na MESMA unidade que 'vna' -- reais, nao fator -- porque e
    contra 'vna' que parse_bloomberg.py compara a tolerancia
    (_TOLERANCIA_DIVERGENCIA = 0.5, documentada la como "em reais"). Sem
    o x1000 aqui, uma divergencia real de R$ 400 sobre um VNA de ~R$
    1.875 (21%, bem acima do que a tolerancia deveria pegar) seria
    gravada como 0.4 e passaria pela guarda calada.
    """
    e = _estoque()
    buffer = io.StringIO()
    escritor = csv.writer(buffer)
    escritor.writerow(["data", "indice", "campo", "fator", "vna",
                        "n_papeis", "divergencia"])
    for dt in datas:
        for titulo, (campo, indice) in CAMPO_VNA.items():
            vivos = e[(e["titulo"] == titulo)
                      & (e["data"].dt.year == dt.year)
                      & (e["data"].dt.month == dt.month)]["isin"].head(3).tolist()
            if not vivos:
                continue
            valores = _referencia(blpapi, sessao, servico, vivos, campo, dt)
            if not valores:
                continue
            divergencia_reais = (max(valores) - min(valores)) * 1000
            escritor.writerow([dt, indice, campo, f"{valores[0]:.9f}",
                                f"{valores[0] * 1000:.6f}", len(valores),
                                f"{divergencia_reais:.9f}"])
    return buffer.getvalue().encode("utf-8")


def baixar(destino=None):
    """Puxa a taxa e o VNA que ainda faltam e grava arquivos novos.

    Devolve (caminho_taxas, caminho_vna, caminho_precos).

    A coleta e incremental: monta, so pelo NOME dos arquivos ja
    presentes em destino (formato ISO -- o mesmo contrato que
    parse_bloomberg exige do leitor), o conjunto de meses que CADA tipo
    de arquivo (taxa, vna, preco) ja reivindica cobrir, e pede so os
    meses do painel atual que faltam em qualquer um dos tres -- ver
    _meses_cobertos() para o porque disso ser um conjunto, nao so "o mes
    mais recente". O nome do arquivo novo reflete o periodo que ele de
    fato cobre, nunca a janela inteira do estoque -- e por isso os
    arquivos se acumulam em vez de se sobrescrever.

    data/raw/ e imutavel por invariante do projeto (ver
    docs/convencoes-dv.md e o incidente do fetch_rmd.baixar que motivou
    essa regra): se o caminho calculado ja existir -- o que o corte
    incremental acima ja deveria ter evitado -- a funcao levanta erro em
    vez de sobrescrever, como defesa em profundidade.

    Se nao houver nada novo (o estoque nao tem mes do painel que falte
    em taxa, vna E preco ao mesmo tempo), levanta erro em vez de gravar
    arquivo vazio ou repetir o de sempre -- e o sinal de que a camada de
    dados (RMD) precisa ser atualizada primeiro, nao a Bloomberg. Nenhum
    diretorio e criado nesse caso nem no caso de erro de leitura do
    estoque: destino.mkdir() so roda depois de confirmar que ha alguma
    coisa para gravar ali.
    """
    destino = Path(destino) if destino else config.BLOOMBERG_DIR

    cobertos_taxa = _meses_cobertos(destino, "bbg_taxas_ANDE_*.csv", _PADRAO_ARQ_TAXA)
    cobertos_vna = _meses_cobertos(destino, "bbg_vna_*.csv", _PADRAO_ARQ_VNA)
    cobertos_preco = _meses_cobertos(destino, "bbg_precos_ANDE_*.csv", _PADRAO_ARQ_PRECO)

    datas = datas_do_painel()

    # POR TIPO, E NAO "OU" ENTRE OS TRES. Ate 25/08/2026 um mes entrava na
    # coleta se faltasse em QUALQUER um dos tres tipos, e os tres eram pedidos
    # e gravados juntos, com o mesmo nome de periodo.
    #
    # Isso quebrava no caso mais natural que existe: taxa e vna coletados em
    # 17/08/2026, preco NUNCA coletado. Todos os meses "faltavam" (por causa do
    # preco), baixar() montava o nome do periodo inteiro para os tres, e batia
    # no FileExistsError que guarda a imutabilidade de data/raw/.
    #
    # O invariante fez o trabalho dele -- parou antes de sobrescrever. Mas nao
    # havia como coletar so o preco, e recoletar os tres triplicaria a consulta
    # a Bloomberg, que e cara e que ela autoriza caso a caso.
    faltando = {
        "taxa": [d for d in datas if (d.year, d.month) not in cobertos_taxa],
        "vna": [d for d in datas if (d.year, d.month) not in cobertos_vna],
        "preco": [d for d in datas if (d.year, d.month) not in cobertos_preco],
    }
    novas_datas = sorted(set().union(*faltando.values()))

    if not novas_datas:
        if not (cobertos_taxa or cobertos_vna or cobertos_preco):
            raise RuntimeError(
                f"nada a coletar: o estoque em {config.PROCESSED_DIR} nao "
                f"tem nenhum fim de mes com posicao positiva nos titulos do "
                f"escopo {TITULOS}."
            )
        raise RuntimeError(
            f"nada novo a coletar em {destino}: os {len(datas)} mes(es) do "
            f"painel atual do estoque ja estao cobertos (taxa, vna e preco) "
            f"pelos arquivos existentes. Se esperava um mes novo, rode a "
            f"camada de dados (RMD) antes da Bloomberg."
        )

    # CADA TIPO COM O SEU PROPRIO PERIODO. O que ja esta coberto nao ganha
    # arquivo nem consulta -- alvo None quer dizer "nada a coletar deste tipo".
    def _alvo(tipo, prefixo):
        if not faltando[tipo]:
            return None
        marca = f"{faltando[tipo][0]:%Y-%m}_{faltando[tipo][-1]:%Y-%m}"
        return destino / f"{prefixo}{marca}.csv"

    alvo_taxa = _alvo("taxa", "bbg_taxas_ANDE_")
    alvo_vna = _alvo("vna", "bbg_vna_")
    alvo_preco = _alvo("preco", "bbg_precos_ANDE_")

    for tipo, alvo in (("taxa", alvo_taxa), ("vna", alvo_vna),
                       ("preco", alvo_preco)):
        if alvo is not None and alvo.exists():
            # O nome computado ja existe sem que _meses_cobertos o tenha lido
            # -- arquivo de coleta interrompida, ou nome fora do padrao ISO.
            # Continua parando: a coleta por tipo nao afrouxa a imutabilidade.
            raise FileExistsError(
                f"{alvo} ja existe; data/raw/ e imutavel por invariante do "
                f"projeto e este coletor nunca sobrescreve. Se a intencao e "
                f"recoletar esse periodo, apague ou renomeie o arquivo na "
                f"mao antes de rodar de novo."
            )

    papeis = papeis_do_estoque()

    def _papeis_de(tipo):
        """Os papeis vivos a partir do primeiro mes que falta DAQUELE tipo."""
        if not faltando[tipo]:
            return None
        return papeis[papeis["ultima"] >= faltando[tipo][0]].reset_index(
            drop=True)

    papeis_novos = _papeis_de("taxa")
    # A serie de preco da LFT na Bloomberg e inutilizavel (ver
    # docs/convencoes-dv.md e o docstring de _conteudo_precos) -- nunca
    # pedida.
    de_preco = _papeis_de("preco")
    papeis_novos_preco = (None if de_preco is None
                          else de_preco[de_preco["titulo"] != "LFT"])

    # So cria o diretorio de destino depois de confirmar que ha algo
    # para gravar ali -- um destino digitado errado (ou um estoque sem
    # mes novo) nao deixa uma pasta vazia para tras.
    destino.mkdir(parents=True, exist_ok=True)

    blpapi, sessao = _sessao()
    servico = sessao.getService("//blp/refdata")
    try:
        # SO SE PEDE O QUE FALTA. Puxar os tres e jogar dois fora nao deixaria
        # arquivo para tras, mas a consulta -- que e o que custa -- teria sido
        # feita do mesmo jeito.
        conteudo_taxa = (None if alvo_taxa is None else _conteudo_taxas(
            papeis_novos, faltando["taxa"][0], blpapi, sessao, servico))
        conteudo_vna = (None if alvo_vna is None else _conteudo_vna(
            faltando["vna"], blpapi, sessao, servico))
        conteudo_preco = (None if alvo_preco is None else _conteudo_precos(
            papeis_novos_preco, faltando["preco"][0], blpapi, sessao, servico))
    finally:
        sessao.stop()

    # So grava depois que as tres puxadas terminaram: uma falha na
    # segunda ou terceira nao pode deixar a primeira gravada sozinha em
    # data/raw/ com um periodo que os outros dois arquivos nao cobrem.
    # A janela de corrida residual (entre este ponto e a ultima
    # gravacao) esta registrada no docstring do modulo -- deliberadamente
    # nao fechada, ver ali o motivo.
    for conteudo, alvo in ((conteudo_taxa, alvo_taxa),
                           (conteudo_vna, alvo_vna),
                           (conteudo_preco, alvo_preco)):
        if alvo is None:
            continue
        gravar_atomico(conteudo, alvo)
        print(f"gravado: {alvo}")

    return alvo_taxa, alvo_vna, alvo_preco


if __name__ == "__main__":
    baixar()
