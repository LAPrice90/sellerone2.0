:: Operational entrypoint - do not bypass; use for all runs.
@echo off
setlocal
set "PY=C:\Users\Luke\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"
set "ROOT=%~dp0"
set "PYTHONPATH=%ROOT%;%ROOT%scripts;%PYTHONPATH%"
if not defined B_RUN_ONCE set "B_RUN_ONCE=0"
pushd "%ROOT%"
set "B_LIVE=%ROOT%out\systems\B\live"
if not exist "%B_LIVE%" mkdir "%B_LIVE%"
set "B_CYCLE_LOG_PATH=%B_LIVE%\B_cycle.log"
set "B_CYCLE_LOCK_PATH=%B_LIVE%\B_cycle.lock"
set "RUN_LOCK_PATH=%B_CYCLE_LOCK_PATH%"
if not defined B_LOCK_STALE_SECONDS set "B_LOCK_STALE_SECONDS=300"
set "B002_STATE_PATH=%B_LIVE%\B002_last_run.txt"
set "REFUND_COLLECTION_STATE_PATH=%B_LIVE%\refund_collection_last_run.txt"
set "LISTING_COLLECTION_STATE_PATH=%B_LIVE%\listing_offer_collection_last_run.txt"
:loop
echo [%date% %time%] [B_supervisor] starting B cycle
"%PY%" "%ROOT%scripts\cycles\run_B_cycle.py"
set "RC=%ERRORLEVEL%"
echo [%date% %time%] [B_supervisor] B cycle exited rc=%RC%
if /I "%B_RUN_ONCE%"=="1" (
  popd
  endlocal & exit /b %RC%
)
if "%RC%"=="0" (
  echo [%date% %time%] [B_supervisor] restart in 3s after clean exit
) else (
  echo [%date% %time%] [B_supervisor] restart in 5s after nonzero exit
)
if "%RC%"=="0" (
  timeout /t 3 /nobreak >nul
) else (
  timeout /t 5 /nobreak >nul
)
goto loop
popd
endlocal
