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
echo.
pause

exit /b %CODIGO%
