:: Operational entrypoint - do not bypass; use for all runs.
@echo off
setlocal
set "PY=C:\Users\Luke\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"
set "ROOT=%~dp0"
set "E_LIVE=%ROOT%out\systems\E\live"
if not exist "%E_LIVE%" mkdir "%E_LIVE%"
set "E_RUN_LOG_PATH=%E_LIVE%\e_run_log.jsonl"
set "E_DECISION_LOG_PATH=%E_LIVE%\e_decision_log.csv"
"%PY%" "%ROOT%scripts\cycles\run_E_cycle.py"
endlocal
