@echo off
chcp 65001 >nul
cd /d "%~dp0"

:: ======================================================
::  优先使用 Hermes Agent 虚拟环境（已预装 aiohttp）
::  兜底使用当前目录下的 .venv
::  最后尝试系统 Python
:: ======================================================

set "PYTHON="

if exist "C:\.hermes\hermes-agent\venv\Scripts\python.exe" (
    set "PYTHON=C:\.hermes\hermes-agent\venv\Scripts\python.exe"
) else if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else if exist "venv\Scripts\python.exe" (
    set "PYTHON=venv\Scripts\python.exe"
) else (
    where python >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON=python"
    ) else (
        echo [错误] 未找到可用的 Python 解释器！
        pause
        exit /b 1
    )
)

set "PORT=%~1"
if "%PORT%"=="" set "PORT=8643"

echo ====================================================
echo   Hermes Skill Market API Server
echo   Python: %PYTHON%
echo   Port:   %PORT%
echo   URL:    http://127.0.0.1:%PORT%/api/skill-market/list
echo ====================================================
echo.

%PYTHON% skill_market_api.py %PORT%

if errorlevel 1 (
    echo.
    echo [错误] 服务启动失败，请检查 Python 环境和依赖。
    echo 需要安装: pip install aiohttp pyyaml
)

pause
