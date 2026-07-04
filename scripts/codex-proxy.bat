@echo off
setlocal enabledelayedexpansion

if not defined PROXY_SCRIPT set "PROXY_SCRIPT=%~dp0..\glm_proxy.py"

set "PYTHON="
for %%p in (python python3) do (
    2>nul %%p --version >nul && set "PYTHON=%%p"
    if defined PYTHON goto :python_found
)
echo [Codex Proxy] ERROR: Python not found in PATH
exit /b 1

:python_found
curl -s http://127.0.0.1:8787/health >nul 2>&1
if errorlevel 1 goto :start_proxy
goto :run_codex

:start_proxy
echo [Codex Proxy] Starting...
start /B "" "%PYTHON%" "%PROXY_SCRIPT%" >nul 2>&1
for /L %%i in (1,1,10) do (
    timeout /t 1 /nobreak >nul
    curl -s http://127.0.0.1:8787/health >nul 2>&1
    if not errorlevel 1 (
        echo [Codex Proxy] Ready
        goto :run_codex
    )
)
echo [Codex Proxy] WARNING: Not responding after 10s, proceeding anyway...

:run_codex
if not defined CODEX_PROXY_DEBUG_LOG set "CODEX_PROXY_DEBUG_LOG=%USERPROFILE%\.codex\proxy_debug.log"
codex %*
endlocal
