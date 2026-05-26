@echo off
setlocal
cd /d "%~dp0"

set "SELLERONE_UI_URL=http://localhost:8501/?page=price_list_queue"

powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if errorlevel 1 (
    start "SellerOne Operator UI" /min cmd /d /c call "%~dp0run_O_operator_ui.bat"
    timeout /t 5 /nobreak >nul
)

start "" "%SELLERONE_UI_URL%"
