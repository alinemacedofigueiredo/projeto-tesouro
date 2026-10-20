@echo off
rem O ATALHO. Ela pediu em 02/10/2026 e, ao ver a primeira versao, disse que os
rem textos estavam "mtu ruim" -- eram tres blocos de instrucao numa janela que
rem ela ja sabia usar. Aqui ficou o minimo: o nome, e uma linha no fim.
rem
rem O QUE EXPLICA E O PROGRAMA, e nao esta janela: desde 02/10 o pipeline abre
rem dizendo que comecou e marca cada fase com hora e tempo decorrido.
rem
rem cd /d %~dp0 entra na pasta DESTE arquivo, onde ele estiver -- sem isso o
rem atalho quebraria no dia em que o projeto mudasse de lugar.
cd /d "%~dp0"
set PYTHONPATH=src

python -m tesouro.pipeline %*

rem GUARDA O CODIGO ANTES DE QUALQUER ECHO: no .cmd o errorlevel que sobra e o
rem do ultimo comando, e o pause devolve sempre 0. Medido -- com --modo
rem inexistente o atalho saia com 0. E a mesma armadilha do "pytest | tail".
set CODIGO=%errorlevel%

rem PAUSE SEMPRE. Clicando duas vezes, a janela fecharia junto com o programa e
rem levaria o resultado embora.
rem
rem E A TECLA ABRE A PASTA DAS PAGINAS. Ela perguntou em 20/10/2026 "como clico
rem duas vezes nos links do cmd?" -- nao da, aquilo e texto. E depois do pause a
rem janela fecha, entao nao sobra nem onde digitar um comando. A tecla que ela ja
rem aperta passa a levar ao lugar onde o clique funciona.
echo.
echo Aperte uma tecla para abrir a pasta das paginas.
pause >nul
start "" "%~dp0data\processed"

exit /b %CODIGO%
