@echo off
setlocal
cd /d "%~dp0"
echo Este arquivo abre o codigo-fonte pelo Python e serve apenas para desenvolvimento.
echo Para criar o executavel, use GERAR_EXECUTAVEL.bat.
echo.
if not exist ".venv\Scripts\pythonw.exe" (
    echo Ambiente nao encontrado. Execute GERAR_EXECUTAVEL.bat para criar o EXE.
    pause
    exit /b 1
)
start "Sistema SIA - desenvolvimento" .venv\Scripts\pythonw.exe run.py
