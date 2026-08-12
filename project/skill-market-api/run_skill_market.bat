@echo off
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else if exist "venv\Scripts\python.exe" (
    set "PYTHON=venv\Scripts\python.exe"
) else (
    echo [ERROR] No .venv or venv found. Run: python -m venv .venv
    pause
    exit /b 1
)

set "PORT=%~1"
if "%PORT%"=="" set "PORT=8643"

echo ========================================================
echo   Hermes Skill Market API Server
echo   Python: %PYTHON%
echo   Port:    %PORT%
echo   URL:     http://127.0.0.1:%PORT%/api/skill-market/list
echo ========================================================
echo.

"%PYTHON%" skill_market_api.py %PORT%

pause
