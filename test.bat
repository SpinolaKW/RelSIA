@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Ambiente nao encontrado. Execute install.bat primeiro.
    pause
    exit /b 1
)

.venv\Scripts\python.exe -m unittest discover -s tests -v
pause
