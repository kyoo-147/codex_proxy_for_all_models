@echo off
REM Validate a provider works with the Codex Proxy.
REM Usage: validate-provider.bat [base_url]
REM Default base_url: http://127.0.0.1:8787

setlocal enabledelayedexpansion

set "BASE=%~1"
if "%BASE%"=="" set "BASE=http://127.0.0.1:8787"

set PASS=0
set FAIL=0

echo === Provider validation: %BASE% ===
echo.

REM 1. Health check
echo --- Health check ---
curl -s -o NUL -w "%%{http_code}" "%BASE%/health" > %TEMP%\health.txt
set /p HEALTH=<%TEMP%\health.txt
if "%HEALTH%"=="200" (
    echo   [PASS] /health returns 200
    set /a PASS+=1
) else (
    echo   [FAIL] /health returned %HEALTH% (expected 200)
    set /a FAIL+=1
)

REM 2. Models endpoint
echo --- Models ---
curl -s "%BASE%/v1/models" > %TEMP%\models.json
python3 -c "import json; d=json.load(open('%TEMP%\models.json')); assert len(d['models'])>0; print(d['models'][0]['slug'])" 2>NUL
if %ERRORLEVEL%==0 (
    echo   [PASS] /v1/models returns model catalog
    set /a PASS+=1
) else (
    echo   [FAIL] /v1/models failed or returned empty
    set /a FAIL+=1
)

REM 3. Basic text round-trip
echo --- Text round-trip ---
curl -s -X POST "%BASE%/v1/responses" -H "Content-Type: application/json" -d "{\"input\": \"hello\"}" > %TEMP%\text_resp.json
python3 -c "import json; d=json.load(open('%TEMP%\text_resp.json')); print(d['output'][0]['content'][0]['text'])" 2>NUL
if %ERRORLEVEL%==0 (
    echo   [PASS] Text response received
    set /a PASS+=1
) else (
    echo   [FAIL] Text response failed
    set /a FAIL+=1
)

REM 4. Tool-calling round-trip
echo --- Tool calling ---
curl -s -X POST "%BASE%/v1/responses" -H "Content-Type: application/json" -d "{\"input\": [{\"type\":\"function_call\",\"call_id\":\"call_1\",\"name\":\"shell_command\",\"arguments\":\"{\\\"cmd\\\":\\\"echo hi\\\"}\"},{\"type\":\"function_call_output\",\"call_id\":\"call_1\",\"output\":\"hi\"}]}" > %TEMP%\tool_resp.json
python3 -c "import json; d=json.load(open('%TEMP%\tool_resp.json')); assert d['output'][0]['type']=='message'; print('OK')" 2>NUL
if %ERRORLEVEL%==0 (
    echo   [PASS] Tool loop returns message response
    set /a PASS+=1
) else (
    echo   [FAIL] Tool loop failed
    set /a FAIL+=1
)

echo.
echo === Results: %PASS% passed, %FAIL% failed ===
exit /b %FAIL%
