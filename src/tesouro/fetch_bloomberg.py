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
periodo": cada chamada de baixar() olha o que ja existe no destino,
descobre ate que mes ja foi coletado (pelo NOME dos arquivos existentes,
formato ISO) e pede so o que vem depois. O arquivo novo e nomeado pelo
periodo que ele de fato cobre -- nunca a janela inteira do estoque -- e
se por algum motivo o nome computado ja existir, a funcao levanta erro em
vez de sobrescrever. gravar_atomico cuida da escrita (sem deixar arquivo
parcial), mas quem decide se pode escrever e este modulo, que confere
existencia antes de abrir sessao com o terminal.
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


def _primeiro_dia_apos(d):
    """O primeiro dia do mes seguinte ao mes de d."""
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def _cobertura_atual(destino):
    """O ultimo mes (AAAA-MM, como date do dia 1) ja coberto por arquivos
    existentes em destino, olhando SO o nome -- nunca o conteudo.

    Confere os dois padroes (taxa e vna) e fica com o mais RESTRITIVO
    (o minimo dos dois), nao o mais recente: se por algum motivo um dos
    dois ficou para tras numa puxada anterior (por exemplo, ela foi
    interrompida entre gravar a taxa e gravar o vna), o corte incremental
    tem que continuar pedindo o que falta para o mais atrasado dos dois,
    em vez de assumir que os dois avancaram juntos.
    """
    melhores = []
    for padrao_glob, padrao_nome in (
        ("bbg_taxas_ANDE_*.csv", _PADRAO_ARQ_TAXA),
        ("bbg_vna_*.csv", _PADRAO_ARQ_VNA),
    ):
        melhor = None
        for arquivo in destino.glob(padrao_glob):
            casado = padrao_nome.match(arquivo.name)
            if not casado:
                continue
            ate = casado.group("ate")
            d = date(int(ate[:4]), int(ate[5:7]), 1)
            if melhor is None or d > melhor:
                melhor = d
        if melhor is not None:
            melhores.append(melhor)
    if not melhores:
        return None
    return min(melhores)


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

    limite, se dado, e o primeiro dia a pedir para um papel que ja
    estava ativo antes dele. Um papel que so passou a existir depois de
    limite usa a propria data de nascimento (p.primeira), nunca limite,
    porque pedir antes disso nao teria papel vivo para responder.
    Devolve None se o papel nao tem nada de novo a pedir (ja tinha
    saido de circulacao antes do corte).
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
    """Monta em memoria o CSV de preco (PX_DIRTY_MID) -- so referencia."""
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
            escritor.writerow([dt, indice, campo, f"{valores[0]:.9f}",
                                f"{valores[0] * 1000:.6f}", len(valores),
                                f"{max(valores) - min(valores):.9f}"])
    return buffer.getvalue().encode("utf-8")


def baixar(destino=None):
    """Puxa a taxa e o VNA que ainda faltam e grava arquivos novos.

    Devolve (caminho_taxas, caminho_vna, caminho_precos).

    A coleta e incremental: olha o que ja existe em destino (pelo NOME
    dos arquivos, formato ISO -- o mesmo contrato que parse_bloomberg
    exige do leitor) para descobrir o ultimo mes ja coberto, e pede so a
    partir do mes seguinte. O nome do arquivo novo reflete o periodo que
    ele de fato cobre, nunca a janela inteira do estoque -- e por isso os
    arquivos se acumulam em vez de se sobrescrever.

    data/raw/ e imutavel por invariante do projeto (ver
    docs/convencoes-dv.md e o incidente do fetch_rmd.baixar que motivou
    essa regra): se o caminho calculado ja existir -- o que o corte
    incremental acima ja deveria ter evitado -- a funcao levanta erro em
    vez de sobrescrever, como defesa em profundidade.

    Se nao houver nada novo (o estoque nao tem mes fechado mais recente
    do que o que ja foi coletado), levanta erro em vez de gravar arquivo
    vazio ou repetir o de sempre -- e o sinal de que a camada de dados
    (RMD) precisa ser atualizada primeiro, nao a Bloomberg.
    """
    destino = Path(destino) if destino else config.BLOOMBERG_DIR
    destino.mkdir(parents=True, exist_ok=True)

    cutoff = _cobertura_atual(destino)
    datas = datas_do_painel()
    limite = _primeiro_dia_apos(cutoff) if cutoff is not None else None
    novas_datas = [d for d in datas if limite is None or d >= limite]

    if not novas_datas:
        if cutoff is None:
            raise RuntimeError(
                f"nada a coletar: o estoque em {config.PROCESSED_DIR} nao "
                f"tem nenhum fim de mes com posicao positiva nos titulos do "
                f"escopo {TITULOS}."
            )
        raise RuntimeError(
            f"nada novo a coletar em {destino}: os arquivos ja existentes "
            f"cobrem ate {cutoff:%Y-%m}, e o estoque atual nao tem mes "
            f"fechado mais recente do que isso. Se esperava um mes novo, "
            f"rode a camada de dados (RMD) antes da Bloomberg."
        )

    marca = f"{novas_datas[0]:%Y-%m}_{novas_datas[-1]:%Y-%m}"
    alvo_taxa = destino / f"bbg_taxas_ANDE_{marca}.csv"
    alvo_vna = destino / f"bbg_vna_{marca}.csv"
    alvo_preco = destino / f"bbg_precos_ANDE_{marca}.csv"
    for alvo in (alvo_taxa, alvo_vna, alvo_preco):
        if alvo.exists():
            raise FileExistsError(
                f"{alvo} ja existe; data/raw/ e imutavel por invariante do "
                f"projeto e este coletor nunca sobrescreve. Se a intencao e "
                f"recoletar esse periodo, apague ou renomeie o arquivo na "
                f"mao antes de rodar de novo."
            )

    papeis = papeis_do_estoque()
    papeis_novos = (papeis[papeis["ultima"] >= limite].reset_index(drop=True)
                     if limite is not None else papeis)

    blpapi, sessao = _sessao()
    servico = sessao.getService("//blp/refdata")
    try:
        conteudo_taxa = _conteudo_taxas(papeis_novos, limite, blpapi, sessao, servico)
        conteudo_vna = _conteudo_vna(novas_datas, blpapi, sessao, servico)
        conteudo_preco = _conteudo_precos(papeis_novos, limite, blpapi, sessao, servico)
    finally:
        sessao.stop()

    # So grava depois que as tres puxadas terminaram: uma falha na
    # segunda ou terceira nao pode deixar a primeira gravada sozinha em
    # data/raw/ com um periodo que os outros dois arquivos nao cobrem.
    gravar_atomico(conteudo_taxa, alvo_taxa)
    print(f"gravado: {alvo_taxa}")
    gravar_atomico(conteudo_vna, alvo_vna)
    print(f"gravado: {alvo_vna}")
    gravar_atomico(conteudo_preco, alvo_preco)
    print(f"gravado: {alvo_preco}")

    return alvo_taxa, alvo_vna, alvo_preco


if __name__ == "__main__":
    baixar()
