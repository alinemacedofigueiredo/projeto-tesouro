@echo off
rem ATALHO PARA RODAR O PROJETO SEM DECORAR COMANDO.
rem
rem Ela pediu em 02/10/2026: "quero o atalho". Antes era abrir o PowerShell,
rem entrar na pasta e colar duas linhas -- tres chances de errar antes de o
rem programa comecar.
rem
rem O .cmd mora no PROJETO, e nao na area de trabalho, porque faz parte dele e
rem vai no git. O icone na area de trabalho e so um apontador para ca, criado
rem por maquina.
rem
rem cd /d %~dp0: entra na pasta DESTE arquivo, seja onde ele estiver. Sem isto o
rem atalho so funcionaria com o caminho certo escrito aqui dentro, e quebraria
rem no dia em que o projeto mudasse de lugar -- que foi o que aconteceu com o
rem OneDrive em setembro.
cd /d "%~dp0"

set PYTHONPATH=src

echo.
echo  Projeto Tesouro
echo  ---------------
echo.

python -m tesouro.pipeline %*

rem GUARDA O CODIGO AGORA, antes de qualquer echo ou pause: no .cmd o
rem errorlevel que sobra e o do ULTIMO comando, e o pause sempre devolve 0.
rem Medido em 02/10/2026: com --modo inexistente o atalho saia com 0.
rem Para ela nao muda nada -- ela le a tela -- mas num agendador seria
rem sempre verde. E a mesma armadilha do 'pytest | tail'.
set CODIGO=%errorlevel%

rem PAUSE NO FIM, SEMPRE. Clicando duas vezes, a janela fecha junto com o
rem programa e leva o resultado com ela -- inclusive a ADVERTENCIA de RMD
rem atrasado, que e a ultima linha impressa. A conferencia do cabecalho da
rem pagina depende de ela LER o que saiu aqui.
echo.
echo  ----------------------------------------------------------------
echo   Terminou. Confira acima:
echo.
echo    - a ultima linha diz "concluido." ?
echo    - apareceu alguma ADVERTENCIA ou ATENCAO ?
echo.
echo   Depois abra data\processed\paf.html e veja se o cabecalho mudou.
echo   Se nao mudou, a atualizacao nao atualizou.
echo  ----------------------------------------------------------------
echo.
pause

exit /b %CODIGO%
