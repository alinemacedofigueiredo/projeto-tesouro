"""Camada de graficos do projeto: uma funcao de dado e uma de desenho por grafico.

A separacao existe por dois motivos. O primeiro e decisao de projeto: o motor de
desenho pode mudar (ver a spec, secao 3.1), e trocar matplotlib por outra coisa nao
pode exigir reescrever a logica dos graficos. O segundo e teste: com a separacao, o
teste afirma "a composicao de junho de 2026 e 21,0 / 25,9 / 49,3 / 3,7" em vez de
"a figura tem quatro barras", que passa com qualquer implementacao.
"""
