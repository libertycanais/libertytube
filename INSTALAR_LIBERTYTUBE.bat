@echo off
setlocal enabledelayedexpansion
chcp 65001 > nul
title Instalador do LibertyTube 1.0
cd /d "%~dp0"

echo.
echo   ==========================================================
echo                  L I B E R T Y T U B E   1 . 0
echo   ==========================================================
echo.

rem Procura a pasta com os arquivos do app. Ela fica ao lado deste
rem arquivo; se o usuario tiver movido o .bat, tenta uma acima tambem.
set "SISTEMA=%~dp0sistema"
if not exist "!SISTEMA!\instalador.ps1" (
    if exist "%~dp0..\sistema\instalador.ps1" set "SISTEMA=%~dp0..\sistema"
)

if not exist "!SISTEMA!\instalador.ps1" (
    echo   [ATENCAO] Nao encontrei os arquivos do LibertyTube ao lado deste
    echo   instalador. Isso acontece por um destes dois motivos:
    echo.
    echo     1^) Voce clicou no instalador DE DENTRO do arquivo ZIP.
    echo        O Windows mostra o ZIP como se fosse uma pasta, mas os
    echo        arquivos ainda nao foram extraidos de verdade.
    echo.
    echo     2^) Voce extraiu so este arquivo, em vez da pasta inteira.
    echo.
    echo   COMO RESOLVER:
    echo     1. Clique com o botao DIREITO no pacote do LibertyTube
    echo     2. Escolha "Extrair Tudo..." e confirme
    echo     3. Abra a pasta LibertyTube que apareceu
    echo     4. Clique de novo neste INSTALAR_LIBERTYTUBE.bat
    echo.
    echo   MAIS FACIL AINDA: use o instalador de arquivo unico
    echo   ^(INSTALAR_LIBERTYTUBE.bat^) - com ele nao precisa extrair nada.
    echo.
    pause
    exit /b 1
)

echo   Tudo certo, abrindo o instalador...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "!SISTEMA!\instalador.ps1" %*
set "CODIGO=%errorlevel%"
if not "%CODIGO%"=="0" pause
exit /b %CODIGO%
