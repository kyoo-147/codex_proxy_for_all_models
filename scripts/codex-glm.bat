@echo off
REM ============================================================
REM codex-glm.bat v2 — Auto-start GLM Proxy + launch Codex
REM 
REM Features:
REM   - Auto-detects Python (python > python3 > py -3)
REM   - Auto-detects proxy script location
REM   - Waits up to 10s for proxy to be ready
REM   - Passes all args through to Codex
REM
REM Drop in the same directory as glm_proxy.py or set PROXY_SCRIPT
REM Usage: codex-glm [codex args...]
REM ============================================================
setlocal enabledelayedexpansion

REM -- Auto-detect proxy script path
if not defined PROXY_SCRIPT set "PROXY_SCRIPT=%~dp0glm_proxy.py"

REM -- Auto-detect Python executable
set "PYTHON="
for %%p in (python python3) do (
    2>nul %%p --version >nul && set "PYTHON=%%p"
    if defined PYTHON goto :python_found
)
echo [GLM Proxy] ERROR: Python not found in PATH
exit /b 1

:python_found

REM -- Check if proxy is already running
curl -s http://127.0.0.1:8787/health >nul 2>&1
if errorlevel 1 goto :start_proxy
goto :run_codex

:start_proxy
echo [GLM Proxy] Starting (v5.2 crash-resistant)...
start /B "" "%PYTHON%" "%PROXY_SCRIPT%" >nul 2>&1

REM -- Wait up to 10 seconds for proxy to become ready
for /L %%i in (1,1,10) do (
    timeout /t 1 /nobreak >nul
    curl -s http://127.0.0.1:8787/health >nul 2>&1
    if not errorlevel 1 (
        echo [GLM Proxy] Ready
        goto :run_codex
    )
)
echo [GLM Proxy] WARNING: Not responding after 10s, proceeding anyway...
goto :run_codex

:run_codex
REM -- Set debug log if not already set (for proxy crash diagnostics)
if not defined GLM_PROXY_DEBUG set "GLM_PROXY_DEBUG=%USERPROFILE%\.codex\proxy_debug.log"

codex %*

endlocal
