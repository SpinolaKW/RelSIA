@echo off
setlocal
set "SERVIDOR=\\SERVIDOR\Sistema_SIA\RelatorioSIA"
set "LOCAL=%LOCALAPPDATA%\Sistema_SIA\App"

if not exist "%SERVIDOR%\RelatorioSIA.exe" (
    echo Nao foi possivel localizar o Sistema SIA no servidor.
    echo Caminho: %SERVIDOR%
    pause
    exit /b 1
)

if not exist "%LOCAL%" mkdir "%LOCAL%"
robocopy "%SERVIDOR%" "%LOCAL%" /MIR /FFT /R:1 /W:1 /NFL /NDL /NJH /NJS >nul

start "" "%LOCAL%\RelatorioSIA.exe"
exit /b 0
