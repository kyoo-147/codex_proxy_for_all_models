@echo off
REM ============================================================
REM codex-glm.bat — Auto-start GLM Proxy + launch Codex
REM ============================================================
REM Drop this in your PATH alongside glm_proxy.py
REM Usage: codex-glm [codex args...]
REM ============================================================

REM Start proxy if not already running
curl -s http://127.0.0.1:8787/health >nul 2>&1
if errorlevel 1 (
    echo [GLM Proxy] Starting...
    start /B pythonw "%~dp0glm_proxy.py"
    REM Wait for proxy to be ready
    for /L %%i in (1,1,10) do (
        timeout /t 1 /nobreak >nul
        curl -s http://127.0.0.1:8787/health >nul 2>&1
        if not errorlevel 1 goto :proxy_ready
    )
    echo [GLM Proxy] WARNING: Proxy may not have started in time
    :proxy_ready
    echo [GLM Proxy] Ready
)

REM Launch Codex with all passed arguments
codex %*
