:: Operational entrypoint - do not bypass; use for all runs.
@echo off
setlocal
set "PY=C:\Users\Luke\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"
set "ROOT=%~dp0"
if not defined SELLERONE_STORAGE_MODE set "SELLERONE_STORAGE_MODE=sql_primary_csv_export"
if not defined SELLERONE_SQLITE_PATH set "SELLERONE_SQLITE_PATH=out/sql/sellerone_dev.sqlite3"
if not defined B_LAUNCHER_AUTO_DETACH set "B_LAUNCHER_AUTO_DETACH=1"
if not defined B_LAUNCHER_DETACHED set "B_LAUNCHER_DETACHED=0"
if /I "%B_LAUNCHER_AUTO_DETACH%"=="1" if /I not "%B_LAUNCHER_DETACHED%"=="1" (
  powershell -NoProfile -WindowStyle Hidden -Command "$env:B_LAUNCHER_DETACHED='1'; Start-Process -WindowStyle Hidden -FilePath 'cmd.exe' -WorkingDirectory '%ROOT%' -ArgumentList '/d','/c','call ""%~f0""'" >nul 2>&1
  if not errorlevel 1 (
    endlocal & exit /b 0
  )
)
set "PYTHONPATH=%ROOT%;%ROOT%scripts;%PYTHONPATH%"
if not defined B_RUN_ONCE set "B_RUN_ONCE=0"
pushd "%ROOT%"
set "B_LIVE=%ROOT%out\systems\B\live"
if not exist "%B_LIVE%" mkdir "%B_LIVE%"
set "B_CYCLE_LOG_PATH=%B_LIVE%\B_cycle.log"
set "B_CYCLE_LOCK_PATH=%B_LIVE%\B_cycle.lock"
set "RUN_LOCK_PATH=%B_CYCLE_LOCK_PATH%"
if not defined B_LOCK_STALE_SECONDS set "B_LOCK_STALE_SECONDS=300"
if not defined B_CYCLE_MAINTENANCE_SLEEP_SECONDS set "B_CYCLE_MAINTENANCE_SLEEP_SECONDS=5"
if not defined B_SUPERVISOR_STOP_ON_SIGINT set "B_SUPERVISOR_STOP_ON_SIGINT=0"
set "B002_STATE_PATH=%B_LIVE%\B002_last_run.txt"
set "REFUND_COLLECTION_STATE_PATH=%B_LIVE%\refund_collection_last_run.txt"
set "LISTING_COLLECTION_STATE_PATH=%B_LIVE%\listing_offer_collection_last_run.txt"
set "B_SUPERVISOR_LOCK_PATH=%B_LIVE%\B_supervisor.lock"
set "B_SUPERVISOR_LOG_PATH=%B_LIVE%\B_supervisor.log"
"%PY%" "%ROOT%scripts\cycles\run_B_supervisor.py"
set "RC=%ERRORLEVEL%"
popd
endlocal & exit /b %RC%
