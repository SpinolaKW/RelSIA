@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo [1/4] Procurando Python 3.11 ou superior...
set "SIA_PYTHON="

where py >nul 2>&1
if not errorlevel 1 (
    py -3 -c "import sys; sys.exit(0 if sys.version_info.major == 3 and sys.version_info.minor in range(11, 100) else 1)" >nul 2>&1
    if not errorlevel 1 set "SIA_PYTHON=py -3"
)
if defined SIA_PYTHON goto :python_found

where python >nul 2>&1
if not errorlevel 1 (
    python -c "import sys; sys.exit(0 if sys.version_info.major == 3 and sys.version_info.minor in range(11, 100) else 1)" >nul 2>&1
    if not errorlevel 1 set "SIA_PYTHON=python"
)
if defined SIA_PYTHON goto :python_found

where python3 >nul 2>&1
if not errorlevel 1 (
    python3 -c "import sys; sys.exit(0 if sys.version_info.major == 3 and sys.version_info.minor in range(11, 100) else 1)" >nul 2>&1
    if not errorlevel 1 set "SIA_PYTHON=python3"
)
if defined SIA_PYTHON goto :python_found

goto :python_not_found

:python_found
echo Python encontrado:
%SIA_PYTHON% --version
echo.
echo [2/4] Criando o ambiente virtual...
%SIA_PYTHON% -m venv ".venv"
if errorlevel 1 goto :venv_error
if not exist ".venv\Scripts\python.exe" goto :venv_error

echo.
echo [3/4] Atualizando o instalador de pacotes...
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto :dependencies_error

echo.
echo [4/4] Instalando o Sistema SIA e suas dependencias...
.venv\Scripts\python.exe -m pip install -e .
if errorlevel 1 goto :dependencies_error

echo.
echo Instalacao concluida. Execute run.bat para abrir o sistema.
pause
exit /b 0

:python_not_found
echo.
echo Python 3.11 ou superior nao foi encontrado neste computador.
echo.
echo Instale pelo site https://www.python.org/downloads/windows/
echo Durante a instalacao, marque a opcao "Add python.exe to PATH".
echo Depois feche esta janela e execute install.bat novamente.
pause
exit /b 1

:venv_error
echo.
echo Nao foi possivel criar o ambiente virtual .venv.
echo Verifique se a instalacao do Python inclui os componentes pip e venv.
pause
exit /b 1

:dependencies_error
echo.
echo Nao foi possivel instalar as dependencias do Sistema SIA.
echo Verifique a conexao com a internet e tente executar install.bat novamente.
pause
exit /b 1
