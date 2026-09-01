@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Python environment not found. Set it up once with:
    echo   py -3.13 -m venv .venv
    echo   .venv\Scripts\pip install -e .
    pause
    exit /b 1
)

.venv\Scripts\python.exe -m yfphonecam %*
pause
