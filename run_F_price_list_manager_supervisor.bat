:: Operational entrypoint - Task Scheduler should own this supervisor, not FPM130 directly.
@echo off
setlocal

set "PY=C:\Users\Luke\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
cd /d "%ROOT%"

if not defined SELLERONE_STORAGE_MODE set "SELLERONE_STORAGE_MODE=sql_primary_csv_export"
if not defined SELLERONE_SQLITE_PATH set "SELLERONE_SQLITE_PATH=out/sql/sellerone_dev.sqlite3"
set "PYTHONPATH=%ROOT%;%ROOT%\scripts;%PYTHONPATH%"

set "FPM_LIVE=%ROOT%\out\systems\F\price_list_manager\live"
if not exist "%FPM_LIVE%" mkdir "%FPM_LIVE%"
set "FPM_LIVE_LOG=%FPM_LIVE%\live_cycle.log"

if not defined FPM_SUPERVISOR_AUTO_DETACH set "FPM_SUPERVISOR_AUTO_DETACH=1"
if not defined FPM_SUPERVISOR_DETACHED set "FPM_SUPERVISOR_DETACHED=0"
if /I "%FPM_SUPERVISOR_AUTO_DETACH%"=="1" if /I not "%FPM_SUPERVISOR_DETACHED%"=="1" (
  echo [%date% %time%] FPM supervisor bootstrap auto_detach request=1 >> "%FPM_LIVE_LOG%"
  powershell -NoProfile -WindowStyle Hidden -Command "$env:FPM_SUPERVISOR_DETACHED='1'; Start-Process -WindowStyle Hidden -FilePath 'cmd.exe' -WorkingDirectory '%ROOT%' -ArgumentList '/d','/c','call ""%~f0""'" >nul 2>&1
  if not errorlevel 1 (
    echo [%date% %time%] FPM supervisor bootstrap auto_detach started child_launcher=1 parent_exit=clean >> "%FPM_LIVE_LOG%"
    echo [run_F_price_list_manager_supervisor] detached supervisor started
    endlocal & exit /b 0
  )
  echo [%date% %time%] FPM supervisor bootstrap auto_detach failed action=continue_inline >> "%FPM_LIVE_LOG%"
)

if not defined FPM_LIVE_CHUNK_ROWS set "FPM_LIVE_CHUNK_ROWS=25"
if not defined FPM_LIVE_SLEEP_SECONDS set "FPM_LIVE_SLEEP_SECONDS=10"
if not defined FPM_LIVE_APPLY_NEXT set "FPM_LIVE_APPLY_NEXT=1"
if not defined FPM_LIVE_AUTO_APPROVE_NEXT set "FPM_LIVE_AUTO_APPROVE_NEXT=1"
if not defined FPM_LIVE_REFRESH_BEFORE_SELECT set "FPM_LIVE_REFRESH_BEFORE_SELECT=1"
if not defined FPM_SUPERVISOR_STALE_SECONDS set "FPM_SUPERVISOR_STALE_SECONDS=900"
if not defined FPM_SUPERVISOR_CHECK_SECONDS set "FPM_SUPERVISOR_CHECK_SECONDS=30"

set "ARGS=--chunk-rows %FPM_LIVE_CHUNK_ROWS% --sleep-seconds %FPM_LIVE_SLEEP_SECONDS% --stale-seconds %FPM_SUPERVISOR_STALE_SECONDS% --check-seconds %FPM_SUPERVISOR_CHECK_SECONDS%"
if /I "%FPM_LIVE_APPLY_NEXT%"=="0" set "ARGS=%ARGS% --no-apply-next"
if /I "%FPM_LIVE_AUTO_APPROVE_NEXT%"=="0" set "ARGS=%ARGS% --no-auto-approve-next"
if /I "%FPM_LIVE_REFRESH_BEFORE_SELECT%"=="0" set "ARGS=%ARGS% --skip-refresh-before-select"

echo [%date% %time%] FPM supervisor starting args=%ARGS% >> "%FPM_LIVE_LOG%"
"%PY%" -u "%ROOT%\scripts\flows\F\price_list_manager\FPM170_supervise_live_cycle.py" %ARGS% >> "%FPM_LIVE_LOG%" 2>&1
set "RC=%ERRORLEVEL%"
echo [%date% %time%] FPM supervisor exited rc=%RC% >> "%FPM_LIVE_LOG%"

endlocal & exit /b %RC%
