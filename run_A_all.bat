:: Operational entrypoint - do not bypass; use for all runs.
@echo off
setlocal
set "PY=C:\Users\Luke\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"
set "ROOT=%~dp0"
set "PYTHONPATH=%ROOT%;%ROOT%scripts;%PYTHONPATH%"
set "A_LIVE=%ROOT%out\systems\A\live"
set "B_LIVE=%ROOT%out\systems\B\live"
set "INVENTORY_USE_API_OWNER=1"
if not exist "%A_LIVE%" mkdir "%A_LIVE%"
if not exist "%B_LIVE%" mkdir "%B_LIVE%"
set "RUN_LOCK_PATH=%A_LIVE%\run_cycle.lock"
set "B_CYCLE_LOCK_PATH=%B_LIVE%\B_cycle.lock"
"%PY%" "%ROOT%scripts\cycles\run_A_all.py"
endlocal
