@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Ambiente nao encontrado. Execute install.bat primeiro.
    pause
    exit /b 1
)

echo [1/3] Executando testes automatizados...
.venv\Scripts\python.exe -m unittest discover -s tests -v
if errorlevel 1 goto :error

set "SIA_VALIDATE_DIR=%TEMP%\SistemaSIA_validate_%RANDOM%_%RANDOM%"
mkdir "%SIA_VALIDATE_DIR%"
if errorlevel 1 goto :error
set "SIA_DATA_DIR=%SIA_VALIDATE_DIR%\data"

echo.
echo [2/3] Validando inicializacao e banco em area temporaria...
.venv\Scripts\python.exe run.py --self-test
if errorlevel 1 goto :error_with_cleanup

echo.
echo [3/3] Validando telas e permissoes dos dois perfis...
.venv\Scripts\python.exe run.py --ui-smoke-test
if errorlevel 1 goto :error_with_cleanup

call :cleanup
echo.
echo Validacao automatica concluida com sucesso.
echo Consulte VALIDACAO_WINDOWS.md para a conferencia visual final.
pause
exit /b 0

:error_with_cleanup
call :cleanup

:error
echo.
echo Falha na validacao. Consulte a mensagem acima e data\logs.
pause
exit /b 1

:cleanup
set "SIA_DATA_DIR="
if defined SIA_VALIDATE_DIR if exist "%SIA_VALIDATE_DIR%" rmdir /s /q "%SIA_VALIDATE_DIR%"
set "SIA_VALIDATE_DIR="
exit /b 0
