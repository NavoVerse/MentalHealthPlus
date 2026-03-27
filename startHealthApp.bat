@echo off
setlocal

cd /d "%~dp0"

set "APP_URL=http://127.0.0.1:8000"
set "PYTHONW_EXE="

for %%I in (pythonw.exe) do set "PYTHONW_EXE=%%~$PATH:I"

if defined PYTHONW_EXE (
    start "" "%PYTHONW_EXE%" backend\main.py
) else (
    start "" python backend\main.py
)

timeout /t 8 /nobreak >nul
start "" "%APP_URL%"

endlocal
