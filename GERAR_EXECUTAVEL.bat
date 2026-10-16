@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Gerar executavel - Sistema SIA

set "PY_CMD="

echo ============================================================
echo        SISTEMA SIA - GERACAO DO EXECUTAVEL WINDOWS
echo ============================================================
echo.

echo [1/6] Localizando Python 3.11 ou superior...
where py >nul 2>&1
if not errorlevel 1 (
    py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
    if not errorlevel 1 set "PY_CMD=py -3"
)

if not defined PY_CMD (
    where python >nul 2>&1
    if not errorlevel 1 (
        python -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
        if not errorlevel 1 set "PY_CMD=python"
    )
)

if not defined PY_CMD goto :python_error

%PY_CMD% --version

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo [2/6] Criando ambiente de compilacao...
    %PY_CMD% -m venv ".venv"
    if errorlevel 1 goto :build_error
) else (
    echo.
    echo [2/6] Ambiente de compilacao ja existe.
)

echo.
echo [3/6] Instalando/atualizando dependencias...
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto :build_error
.venv\Scripts\python.exe -m pip install -e .
if errorlevel 1 goto :build_error
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
if errorlevel 1 goto :build_error

echo.
echo [4/6] Limpando compilacoes anteriores...
if exist "build" rmdir /s /q "build"
if exist "dist\RelatorioSIA" rmdir /s /q "dist\RelatorioSIA"

echo.
echo [5/6] Gerando o executavel...
.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm RelatorioSIA.spec
if errorlevel 1 goto :build_error

if not exist "dist\RelatorioSIA\RelatorioSIA.exe" goto :build_error

echo.
echo [6/6] Concluido.
echo.
echo Executavel criado em:
echo %CD%\dist\RelatorioSIA\RelatorioSIA.exe
echo.
echo IMPORTANTE: mantenha a pasta RelatorioSIA inteira.
echo Nao mova apenas o arquivo EXE, pois a pasta _internal faz parte do programa.
echo.
start "" explorer.exe /select,"%CD%\dist\RelatorioSIA\RelatorioSIA.exe"
pause
exit /b 0

:python_error
echo.
echo ERRO: Python 3.11 ou superior nao foi encontrado.
echo Instale o Python para Windows e marque "Add python.exe to PATH".
echo Depois execute este arquivo novamente.
echo.
pause
exit /b 1

:build_error
echo.
echo ============================================================
echo ERRO: nao foi possivel gerar o executavel.
echo ============================================================
echo.
echo Copie a mensagem de erro exibida acima e envie para analise.
echo.
pause
exit /b 1
