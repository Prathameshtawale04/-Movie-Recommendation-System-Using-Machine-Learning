@echo off
REM ==============================================================================
REM MovieFlix - Windows Fast Launch Script
REM ==============================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo   Starting MovieFlix - Intelligent Movie Recommendation System
echo ============================================================
echo.

REM Determine Python interpreter: prioritize .venv, fallback to system python
set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
)

REM Verify .env exists
if not exist ".env" (
    echo [*] Creating .env from .env.example...
    copy .env.example .env >nul
)

REM Quick dependency check
%PYTHON_EXE% -c "import flask, pandas, sklearn" >nul 2>&1
if errorlevel 1 (
    echo [*] Installing dependencies, please wait...
    %PYTHON_EXE% -m pip install -r requirements.txt
)

REM Determine Port from .env (default 5000)
set "PORT=5000"
for /f "tokens=1,2 delims==" %%A in (.env) do (
    if "%%A"=="FLASK_PORT" set "PORT=%%B"
)
set "PORT=%PORT: =%"

echo [*] Server is starting on http://127.0.0.1:%PORT%
echo [*] Press CTRL+C in this console to stop the server.
echo.

REM Open browser automatically in 2 seconds
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:%PORT%"

REM Start Flask
%PYTHON_EXE% app.py

pause
