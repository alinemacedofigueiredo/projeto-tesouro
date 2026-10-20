"""O calendario de dias uteis pedido SO quando usado.

POR QUE ISTO EXISTE, medido em 20/10/2026 no clone limpo: cinco arquivos de
teste faziam `CAL = calendario.padrao()` no topo do modulo. Isso le
data/raw/anbima/feriados_nacionais.xls, que nao vem no repositorio -- e um erro
na COLETA do pytest aborta a rodada inteira. Numa maquina nova, `pytest` dava
"Interrupted: 5 errors during collection" e NENHUM teste rodava, nem os que nao
precisam de dado.

Este objeto repassa qualquer atributo para o calendario de verdade, carregado na
primeira vez que alguem o usa. A frase que diz qual arquivo falta continua
aparecendo igual -- so que no teste que precisa dele, e nao na coleta.
"""
from tesouro import calendario


class _Tardio:
    """Repassa tudo para calendario.padrao(), carregado na primeira chamada."""

    __slots__ = ()

    def __getattr__(self, nome):
        return getattr(calendario.padrao(), nome)

    def __repr__(self):                                  # pragma: no cover
        return "<calendario tardio>"


CAL = _Tardio()
