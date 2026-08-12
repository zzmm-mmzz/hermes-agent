@echo off
chcp 65001 >nul
title 批量启动三个项目服务

echo ====================================================
echo   批量启动项目服务
echo ====================================================
echo.

set "ROOT=%~dp0"

rem --- 1. mcp-core-indicators (端口 8100) ---
echo [1/3] 启动 mcp-core-indicators (端口 8100)...
start "core-indicators" /min cmd /c "cd /d "%ROOT%mcp-core-indicators" && python server.py"
if errorlevel 1 (
    echo   [!] 启动失败，请检查 Python 环境
) else (
    echo   [OK] 已启动
)
echo.

rem --- 2. mcp-eip-mock (端口 8200) ---
echo [2/3] 启动 mcp-eip-mock (端口 8200)...
start "eip-mock" /min cmd /c "cd /d "%ROOT%mcp-eip-mock" && python server.py"
if errorlevel 1 (
    echo   [!] 启动失败，请检查 Python 环境
) else (
    echo   [OK] 已启动
)
echo.

rem --- 3. skill-market-api (端口 8643) ---
echo [3/3] 启动 skill-market-api (端口 8643)...
start "skill-market-api" /min cmd /c "%ROOT%skill-market-api\start.bat"
echo   [OK] 已启动
echo.

echo ====================================================
echo   三个服务已全部启动！
echo.
echo   端口映射:
echo     core-indicators  http://localhost:8100
echo     eip-mock         http://localhost:8200
echo     skill-market     http://localhost:8643
echo.
echo   各服务在独立窗口中运行，关闭即可停止。
echo ====================================================

pause
