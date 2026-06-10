@echo off
setlocal
cd /d "%~dp0"

set "SELLERONE_TASK_BOARD_PORT=8503"
set "SELLERONE_TASK_BOARD_URL=http://localhost:%SELLERONE_TASK_BOARD_PORT%"

powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Get-NetTCPConnection -LocalPort %SELLERONE_TASK_BOARD_PORT% -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if errorlevel 1 (
    start "SellerOne Manager Task Board" /min cmd /d /c "cd /d ""%~dp0"" && python -m streamlit run sellerone_manager\task_board_ui.py --server.port %SELLERONE_TASK_BOARD_PORT% --server.address localhost"
    timeout /t 5 /nobreak >nul
)

start "" "%SELLERONE_TASK_BOARD_URL%"
