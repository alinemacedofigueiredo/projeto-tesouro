"""O e-mail do leilao do dia: tabela, graficos e o rascunho no Outlook.

DESENHO DELA em 25/09/2026, depois de ver o primeiro que eu fiz e dizer "ficou
muito ruim". O primeiro era texto puro com a pagina de 1 MB anexada; o modelo
que ela usa e outro -- a TELA COLADA NO CORPO.

    escrito: leilao dia XX/XX/XXXX

    se for de LTN e NTN-F:
        tabela: papel, quantidade, dv e financeiro; total de dv e financeiro
        graficos de dois eixos: LTN, NTN-F, LTN + NTN-F

    se for de LFT e NTN-B:
        a mesma tabela, lembrando que a LFT nao entra no dv, so no financeiro
        graficos de 12 meses: NTN-B ate 10 anos, acima de 10 anos, as duas
        e a LFT, so financeiro

O QUE ELA CHAMA DE "NOTIONAL" E O FINANCEIRO DO LEILAO -- perguntei, porque a
palavra nao existia no projeto e as duas leituras dao numeros bem diferentes.
Nao e quantidade vezes valor de face.

NAO ENVIA. Monta o rascunho e mostra na tela; o botao e dela. Ver montar().
"""
import io
import json
import re
import subprocess
import tempfile

import pandas as pd

from . import config
from .graficos import dashboard, emissao, estilo

# Os cid: que o corpo cita. Serve ao teste que cruza HTML contra anexos -- o
# defeito classico do e-mail com imagem embutida e o quadrado quebrado, que
# aparece quando o HTML aponta para um cid que ninguem anexou.
CIDS_NO_HTML = re.compile(r'cid:([a-z0-9_]+)')

# Os papeis de cada tipo de leilao. O Tesouro oferta prefixado na quinta e
# indexado na terca, mas quem decide aqui e O QUE VEIO no dia, e nao o dia da
# semana: leilao extraordinario tambem tem de sair certo.
_PREFIXADO = ("LTN", "NTN-F")

# A LFT NAO TEM DV01, por decisao de modelagem do projeto. Ela nao entra na
# soma do DV -- nem como zero, que se somaria calado e faria um total parcial
# parecer completo.
SEM_DV = ("LFT",)

DPI = 110


def _base(quando):
    """As linhas de VENDA daquele dia, ou LookupError."""
    quando = pd.Timestamp(quando).normalize()
    d = pd.read_csv(config.PROCESSED_DIR / "dv_emitido_por_leilao.csv",
                    parse_dates=["data_leilao"])
    d = d[(d["data_leilao"].dt.normalize() == quando)
          & (d["operacao"] == "venda")]
    if d.empty:
        raise LookupError(
            f"nao ha leilao de venda em {quando:%d/%m/%Y} no "
            f"dv_emitido_por_leilao.csv."
        )
    return d


def e_prefixado(quando):
    """O leilao do dia e de LTN e NTN-F?"""
    return bool(set(_base(quando)["titulo"]) & set(_PREFIXADO))


def e_oferta(quando):
    """O resultado deste leilao ainda nao saiu?

    Quando e oferta, a quantidade e o TETO -- historicamente sai 83,9% dele --
    e o financeiro e o DV sao derivados da taxa EMPRESTADA do leilao anterior
    daquele papel, com erro mediano de 11 bp. Sao numeros uteis e provisorios,
    e o corpo do e-mail tem de dizer isso.
    """
    return bool((_base(quando)["estagio"] == "ofertado").any())


def assunto(quando):
    return f"Leil\u00e3o dia {pd.Timestamp(quando):%d/%m/%Y}"


def tabela(quando):
    """Papel, quantidade, DV e financeiro -- uma linha por papel.

    POR PAPEL, e nao por vencimento: o e-mail e o primeiro sinal do dia, e a
    abertura por vertice esta na pagina, a um clique.

    A coluna de DV vem VAZIA na LFT, e nao zero. Zero somaria calado.
    """
    d = _base(quando)
    linhas = []
    for papel, bloco in d.groupby("titulo", sort=False):
        linhas.append({
            "papel": papel,
            "quantidade": float(bloco["quantidade"].sum()),
            "dv": (float("nan") if papel in SEM_DV
                   else float(bloco["dv_milhoes"].sum())),
            "financeiro": float(bloco["financeiro_milhoes"].sum()),
        })
    t = pd.DataFrame(linhas, columns=["papel", "quantidade", "dv",
                                      "financeiro"])
    return t.sort_values("papel").reset_index(drop=True)


def totais(t):
    """O total de DV e o de financeiro.

    O DV SOMA SO QUEM TEM DV. A LFT entra no financeiro e fica de fora do DV,
    que e a razao de a coluna dela vir vazia em vez de zero.
    """
    return {"dv": float(t["dv"].sum(skipna=True)),
            "financeiro": float(t["financeiro"].sum())}


# Os graficos de cada tipo, na ordem em que ela pediu. O recorte e a chave de
# emissao.RECORTES; a janela e a de 12 meses, que e a padrao das paginas.
_GRAFICOS_PREFIXADO = ("LTN", "NTN-F", "LTN + NTN-F")
_GRAFICOS_INDEXADO = ("NTN-B at\u00e9 10 anos", "NTN-B acima de 10 anos",
                      "NTN-B", "LFT")

# A janela de "12 meses" das paginas e o numero 1 -- um ano, como
# estilo.recorta entende. Nao e uma contagem de meses: a primeira versao disto
# passou (12, None) e o pandas tentou comparar data com inteiro.
JANELA_12_MESES = 1

ALTURA = 5.6


def graficos(quando):
    """[(nome, figura)] -- os que aquele tipo de leilao pede.

    A LFT sai por desenha_lft, que e SO FINANCEIRO: ela nao tem DV, e um eixo de
    DV vazio ao lado da barra seria um eixo que promete e nao entrega. Foi ela
    que pediu assim -- "lft 12 meses, so financeiro".

    As figuras saem das MESMAS funcoes das paginas. Se o desenho mudar la, muda
    aqui junto, e o e-mail nunca mostra uma versao velha do grafico.
    """
    # O MESMO PREPARO DAS PAGINAS. estilo.aplicar_estilo fixa o backend Agg e as
    # rcParams; sem ele o matplotlib tenta abrir janela e quebra em maquina sem
    # interface -- foi o primeiro erro desta funcao. dashboard.grava chama isto
    # antes de desenhar, e aqui nao passamos por ele.
    estilo.aplicar_estilo()

    quais = (_GRAFICOS_PREFIXADO if e_prefixado(quando)
             else _GRAFICOS_INDEXADO)
    saida = []
    for nome in quais:
        dados = emissao.por_dia(nome, JANELA_12_MESES)
        fig = dashboard._figura(ALTURA)
        if nome in SEM_DV:
            emissao.desenha_lft(dados, fig.subplots())
        else:
            emissao.desenha_dois_eixos(
                dados, fig.subplots(),
                f"{nome} \u00b7 por dia de leil\u00e3o")
        saida.append((nome, fig))
    return saida


def _png(fig):
    """O PNG da figura, e FECHA a figura.

    As figuras vem do pyplot e ficam retidas ate alguem fechar. A suite de
    25/09/2026 avisou com "More than 20 figures have been opened" -- em teste e
    barulho, mas montar() roda a cada leilao e a memoria nao volta sozinha.
    """
    import matplotlib.pyplot as plt

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def _tabela_html(t, total):
    cabeca = ("<tr><th align='left'>papel</th><th align='right'>quantidade"
              "</th><th align='right'>DV (R$ mi)</th>"
              "<th align='right'>financeiro (R$ mi)</th></tr>")
    corpo = []
    for _, r in t.iterrows():
        dv = "\u2014" if pd.isna(r["dv"]) else estilo.num_br(r["dv"], 1)
        corpo.append(
            f"<tr><td>{r['papel']}</td>"
            f"<td align='right'>{estilo.num_br(r['quantidade'], 0)}</td>"
            f"<td align='right'>{dv}</td>"
            f"<td align='right'>{estilo.num_br(r['financeiro'], 0)}</td></tr>")
    rodape = (f"<tr><td><b>total</b></td><td align='right'></td>"
              f"<td align='right'><b>{estilo.num_br(total['dv'], 1)}</b></td>"
              f"<td align='right'><b>"
              f"{estilo.num_br(total['financeiro'], 0)}</b></td></tr>")
    return ("<table cellpadding='6' style=\"border-collapse:collapse;"
            "font-family:Segoe UI,Arial,sans-serif;font-size:13px\">"
            + cabeca + "".join(corpo) + rodape + "</table>")


def corpo(quando):
    """(html, [(cid, png)]) -- o corpo com as imagens embutidas.

    IMAGEM EMBUTIDA, e nao anexo. O anexo de 1 MB foi a primeira tentativa e ela
    disse que ficou ruim: o modelo dela e a tela colada no corpo, que se le sem
    abrir nada.
    """
    t = tabela(quando)
    total = totais(t)
    partes = [f"<p style=\"font-family:Segoe UI,Arial,sans-serif\">"
              f"<b>{assunto(quando)}</b></p>",
              _tabela_html(t, total)]
    if e_oferta(quando):
        partes.append(
            "<p style=\"font-family:Segoe UI,Arial,sans-serif;font-size:12px;"
            "background:#fff4e5;border-left:3px solid #e8a33d;padding:8px\">"
            "<b>O resultado ainda n\u00e3o saiu.</b> A quantidade \u00e9 o "
            "<b>teto ofertado</b> \u2014 historicamente sai 83,9% dele \u2014 "
            "e o financeiro e o DV v\u00eam da taxa do leil\u00e3o anterior de cada "
            "papel, com erro mediano de 11 bp.</p>")
    if any(p in SEM_DV for p in t["papel"]):
        partes.append("<p style=\"font-family:Segoe UI,Arial,sans-serif;"
                      "font-size:12px;color:#555\">A LFT n\u00e3o tem DV01 "
                      "\u2014 ela entra no financeiro e fica de fora do total "
                      "de DV.</p>")

    imagens = []
    for i, (nome, fig) in enumerate(graficos(quando)):
        cid = "g%d" % i
        imagens.append((cid, _png(fig)))
        partes.append(f"<p style=\"font-family:Segoe UI,Arial,sans-serif;"
                      f"font-size:13px\"><b>{nome}</b></p>")
        partes.append(f"<img src='cid:{cid}' style='max-width:100%'>")
    return "".join(partes), imagens


def montar(quando=None, para=None):
    """Monta o rascunho no Outlook CLASSICO e mostra. NAO ENVIA.

    DUAS COISAS MEDIDAS EM 24/09/2026, e as duas custaram uma tentativa:

    - o Outlook NOVO (olk.exe) nao expoe automacao COM: CreateItem aborta com
      E_ABORT. So o classico serve.
    - mesmo no classico, New-Object falha com CO_E_SERVER_EXEC_FAILURE quando o
      Outlook nao esta aberto -- este processo nao consegue LANCAR o servidor
      COM. Por isso aqui se anexa na instancia existente, e o Outlook precisa
      estar aberto ANTES.

    NAO ENVIA de proposito. Mandar mensagem em nome dela e decisao dela.
    """
    caminhos = gravar(quando, assunto=assunto(quando), para=para)
    with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False,
                                     encoding="utf-8") as f:
        f.write(_POWERSHELL)
        script = f.name
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy",
                        "Bypass", "-File", script, str(caminhos["manifesto"])],
                       capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(
            "nao consegui montar o rascunho.\n\n%s\n%s"
            % (r.stdout.strip(), r.stderr.strip()))
    return r.stdout.strip()


def gravar(quando=None, assunto=None, para=None):
    """Grava o corpo, as imagens e o manifesto em data/processed/email/.

    SEPARADO DE montar() de proposito: isto e testavel e roda em qualquer
    maquina; aquilo depende do Outlook estar aberto. Tambem serve de saida
    manual -- da para abrir o corpo.html no navegador e copiar.
    """
    quando = pd.Timestamp(quando).normalize() if quando is not None \
        else pd.Timestamp.today().normalize()
    html, imagens = corpo(quando)
    pasta = config.PROCESSED_DIR / "email"
    pasta.mkdir(parents=True, exist_ok=True)
    escritos = []
    for cid, png in imagens:
        arquivo = pasta / f"{cid}.png"
        arquivo.write_bytes(png)
        escritos.append((cid, arquivo))
    corpo_html = pasta / "corpo.html"
    corpo_html.write_text(html, encoding="utf-8")

    # O MANIFESTO EXISTE PARA O POWERSHELL nao receber nada interpolado. A
    # primeira versao montava o roteiro com json.dumps no meio: JSON nao e
    # sintaxe de PowerShell, e os caminhos chegavam com as barras duplicadas.
    manifesto = pasta / "manifesto.json"
    manifesto.write_text(json.dumps({
        "assunto": assunto or "",
        "para": para or "",
        "html": str(corpo_html),
        "imagens": [{"cid": cid, "arquivo": str(c)} for cid, c in escritos],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"html": corpo_html, "png": escritos, "manifesto": manifesto}


# O Outlook por PowerShell, e nao por pywin32: sao cinco dependencias neste
# projeto e subir uma sexta numa maquina de banco tem processo. O PowerShell ja
# esta la.
#
# GetActiveObject, e nao New-Object: medido em 24/09/2026, com o Outlook
# fechado o New-Object falha com CO_E_SERVER_EXEC_FAILURE -- este processo nao
# consegue LANCAR o servidor COM. O Outlook CLASSICO precisa estar aberto antes.
# O Outlook novo (olk.exe) nao serve: nao expoe COM.
_POWERSHELL = """
param([Parameter(Mandatory=$true)][string]$Manifesto)
$ErrorActionPreference = "Stop"
$m = Get-Content -Raw -Encoding UTF8 $Manifesto | ConvertFrom-Json
try {
  $ol = [Runtime.InteropServices.Marshal]::GetActiveObject("Outlook.Application")
} catch {
  Write-Error "abra o Outlook CLASSICO antes -- o novo (olk.exe) nao expoe COM, e com ele fechado nao da para lancar o servidor."
  exit 1
}
$mail = $ol.CreateItem(0)
if ($m.para) { $mail.To = $m.para }
$mail.Subject = $m.assunto
foreach ($img in $m.imagens) {
  $anexo = $mail.Attachments.Add($img.arquivo)
  $anexo.PropertyAccessor.SetProperty("http://schemas.microsoft.com/mapi/proptag/0x3712001F", $img.cid)
  $anexo.PropertyAccessor.SetProperty("http://schemas.microsoft.com/mapi/proptag/0x370E001F", "image/png")
}
$mail.HTMLBody = [IO.File]::ReadAllText($m.html, [Text.Encoding]::UTF8)
$mail.Display()
Write-Output ("rascunho aberto, nao enviado -- assunto: " + $mail.Subject + " | imagens: " + $mail.Attachments.Count)
"""
