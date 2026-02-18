@echo off
setlocal
set "PY=C:\Users\Luke\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"
set "ROOT=%~dp0"
set "CFG=%ROOT%config\pilot_sku.yaml"
if not exist "%CFG%" (
  echo [run_H_cycle] Missing config: "%CFG%"
  endlocal & exit /b 1
)
set "EXTRA_ARGS="
if /I "%H_RUN_ONCE%"=="1" set "EXTRA_ARGS=--run-once"
if not exist "%ROOT%out" mkdir "%ROOT%out"

:loop
echo [%date% %time%] H-cycle loop starting >> "%ROOT%out\phase1_pilot_task.log"
"%PY%" "%ROOT%scripts\run_H_pricing_cycle.py" --phase1-pilot --phase1-config "%CFG%" --sleep-minutes 0 %EXTRA_ARGS% >> "%ROOT%out\phase1_pilot_task.log" 2>&1
set "RC=%errorlevel%"
echo [%date% %time%] H-cycle loop finished (exit %RC%) >> "%ROOT%out\phase1_pilot_task.log"
if /I "%H_RUN_ONCE%"=="1" (
  endlocal & exit /b %RC%
)
echo [%date% %time%] H-cycle launcher restart in 10s (last exit %RC%) >> "%ROOT%out\phase1_pilot_task.log"
timeout /t 10 /nobreak >nul
goto loop
