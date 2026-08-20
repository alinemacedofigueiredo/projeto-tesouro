"""Calendario de dias uteis do mercado brasileiro.

Duas responsabilidades: ler o arquivo oficial de feriados da Anbima, e
contar dias uteis em tempo constante.

A contagem por indice existe por necessidade de escala. O codigo em uso na
mesa conta dia a dia, o que custa 762 ms numa NTN-B 2060 -- e o painel tem
milhares de pares papel-data, cada um exigindo dois precos. Com o indice
acumulado, du() vira uma subtracao.

O indice nao pode mudar nenhum numero em relacao a contagem dia a dia. O
teste guarda uma implementacao ingenua como oraculo e compara as duas.
"""
import calendar as _calendar
import datetime
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from . import config


def carregar_feriados(caminho=None):
    """Le o arquivo da Anbima e devolve o conjunto de datas de feriado.

    O arquivo tem tres colunas (Data, Dia da Semana, Feriado) e termina
    com notas de rodape, que sao descartadas por nao serem data.
    """
    caminho = Path(caminho) if caminho else config.ANBIMA_DIR / config.ARQUIVO_FERIADOS
    if not caminho.exists():
        raise FileNotFoundError(
            f"calendario de feriados nao encontrado em {caminho}; baixe de "
            f"anbima.com.br/feriados/arqs/feriados_nacionais.xls e coloque "
            f"nessa pasta (veja docs/como-baixar.md)"
        )
    bruto = pd.read_excel(caminho, header=0)
    datas = pd.to_datetime(bruto["Data"], errors="coerce")
    return set(datas.dropna().dt.date)


class Calendario:
    """Conta dias uteis em tempo constante.

    `du(a, b)` reproduz exatamente a contagem dia a dia: o numero de dias
    uteis no intervalo fechado [a, b], menos um. Com a e b uteis, e o
    numero de dias uteis decorridos entre eles.

    A janela indexada nao e fixada no codigo: ela vem do proprio conjunto
    de feriados recebido, do primeiro ao ultimo ano com feriado listado.
    Fixar a janela a mao arriscaria cobrir anos em que o arquivo nao lista
    feriado nenhum -- toda data nesses anos pareceria util, mesmo sendo
    Natal ou Tiradentes, porque simplesmente nao ha dado ali. Fora da
    janela derivada, os metodos levantam erro em vez de responder errado.
    """

    def __init__(self, feriados):
        self.feriados = set(feriados)
        anos = {d.year for d in self.feriados}
        if not anos:
            raise ValueError(
                "conjunto de feriados vazio; nao da para determinar a "
                "janela do calendario"
            )
        self._inicio = date(min(anos), 1, 1)
        self._fim = date(max(anos), 12, 31)
        self._idx = {}
        n = 0
        d = self._inicio
        um_dia = timedelta(days=1)
        while d <= self._fim:
            if d.weekday() < 5 and d not in self.feriados:
                n += 1
            self._idx[d] = n          # dias uteis em [self._inicio, d], inclusive
            d += um_dia

    def _verificar_janela(self, d):
        if d < self._inicio or d > self._fim:
            raise ValueError(
                f"data {d} fora da janela do calendario carregado "
                f"({self._inicio} a {self._fim}); a janela vem da cobertura "
                f"do arquivo de feriados, entao fora dela nao ha garantia de "
                f"que os feriados estejam completos"
            )

    def eh_dia_util(self, d):
        self._verificar_janela(d)
        return d.weekday() < 5 and d not in self.feriados

    def _acumulado(self, d):
        self._verificar_janela(d)
        return self._idx[d]

    def du(self, a, b):
        if b < a:
            a, b = b, a
        # dias uteis em [a, b] = acumulado(b) - acumulado(a) + (1 se a e util)
        n = self._acumulado(b) - self._acumulado(a) + (1 if self.eh_dia_util(a) else 0)
        return n - 1

    def mover(self, d, k):
        """Anda k dias uteis a partir de d. Sempre sai da data inicial."""
        if k == 0:
            return d
        passo = 1 if k > 0 else -1
        um_dia = timedelta(days=passo)
        restante = abs(k)
        while restante:
            d += um_dia
            while not self.eh_dia_util(d):
                d += um_dia
            restante -= 1
        return d

    def ajustar_vencimento(self, d):
        """Leva a data para o dia util efetivo de pagamento.

        Reproduz o comportamento do codigo da mesa: recua um dia util e
        avanca um. Um dia util devolve ele mesmo; um feriado ou fim de
        semana devolve o primeiro dia util seguinte.
        """
        return self.mover(self.mover(d, -1), 1)

    def ultimo_dia_util_do_mes(self, d):
        ultimo = date(d.year, d.month, _calendar.monthrange(d.year, d.month)[1])
        while not self.eh_dia_util(ultimo):
            ultimo -= timedelta(days=1)
        return ultimo


_PADRAO = None


def padrao():
    """Instancia unica sobre o arquivo oficial; o indice custa a montar."""
    global _PADRAO
    if _PADRAO is None:
        _PADRAO = Calendario(carregar_feriados())
    return _PADRAO
