@echo off
REM ============================================================
REM codex-glm.bat -- Auto-start GLM Proxy + launch Codex
REM Drop in the same directory as glm_proxy.py or set PROXY_SCRIPT
REM Usage: codex-glm [codex args...]
REM ============================================================
if not defined PROXY_SCRIPT set PROXY_SCRIPT=%~dp0glm_proxy.py

REM Start proxy if not already running
curl -s http://127.0.0.1:8787/health >nul 2>&1
if errorlevel 1 (
    echo [GLM Proxy] Starting...
    start /B pythonw "%PROXY_SCRIPT%"
    for /L %%i in (1,1,10) do (
        timeout /t 1 /nobreak >nul
        curl -s http://127.0.0.1:8787/health >nul 2>&1
        if not errorlevel 1 goto :ready
    )
    echo [GLM Proxy] WARNING: may not have started in time
    :ready
    echo [GLM Proxy] Ready
)

codex %*
