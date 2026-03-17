:: Operational entrypoint - do not bypass; use for all runs.
@echo off
setlocal
set "PY=C:\Users\Luke\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "H_LIVE=%ROOT%\out\systems\H\live"
if not exist "%H_LIVE%" mkdir "%H_LIVE%"
if not defined H_RUN_ONCE set "H_RUN_ONCE=0"
set "PYTHONPATH=%ROOT%;%ROOT%\scripts;%PYTHONPATH%"
set "H_CYCLE_LOCK_PATH=%H_LIVE%\H_pricing_cycle.lock"
if not defined H_LOCK_STALE_SECONDS set "H_LOCK_STALE_SECONDS=300"
set "H_PRICING_LOG_PATH=%H_LIVE%\H_pricing_cycle.log"
set "H_CYCLE_LOG_PATH=%H_LIVE%\H_cycle.log"
set "H_PRICING_STATE_PATH=%H_LIVE%\h_pricing_cycle_state.json"
set "H_HEALTH_RUN_INLINE=1"
set "CFG=%ROOT%\config\pilot_sku.yaml"
if not exist "%CFG%" (
  echo [run_H_cycle] Missing config: "%CFG%"
  endlocal & exit /b 1
)
set "EXTRA_ARGS="
if /I "%H_RUN_ONCE%"=="1" set "EXTRA_ARGS=--run-once"
if not exist "%ROOT%\out" mkdir "%ROOT%\out"
set "H_TASK_LOG=%H_LIVE%\phase1_pilot_task.log"
set "H_LAUNCHER_RESTART_ON_EXIT=1"
REM Hard-set bisect profile for scheduler runs (no external env required).
set "H_BISECT_FORCE_INLINE=0"
set "H_STAGE_SNAPSHOT_REFRESH=1"
set "H_STAGE_ITEM_OFFERS=1"
set "H_STAGE_PHASE1_PILOT=1"
set "H_STAGE_PHASE1_INTEL=1"
set "H_STAGE_PHASE1_PUBLISH=1"
set "H_PHASE1_PILOT_MODE=inline"
set "H_PHASE1_INTEL_MODE=inline"
set "H_PHASE1_PUBLISH_MODE=inline"
set "H_PHASE1_OBSERVATION_PUBLISH_ENABLED=1"
set "H_SPLIT_HEALTH_MODE=shadow"
set "H_REFRESH_MIN_SECONDS=1"
set "H110_MAX_SKUS_PER_RUN_OVERRIDE=20"
set "H110_SKU_CALL_SPACING_SECONDS_OVERRIDE=0.25"
set "SPAPI_ITEM_OFFERS_MAX_ASINS_PER_RUN=6"
if not defined H_GUARD_DIAGNOSTIC_MODE set "H_GUARD_DIAGNOSTIC_MODE=0"
if not defined PHASE1_LOCK_FORCE_STALE_SECONDS set "PHASE1_LOCK_FORCE_STALE_SECONDS=120"
if not defined H_USE_GUARD_WRAPPER set "H_USE_GUARD_WRAPPER=0"

:loop
echo [%date% %time%] H-cycle loop starting >> "%H_TASK_LOG%"
echo [%date% %time%] H-cycle launcher mode H_RUN_ONCE=%H_RUN_ONCE% EXTRA_ARGS=%EXTRA_ARGS% H_BISECT_FORCE_INLINE=%H_BISECT_FORCE_INLINE% SNAPSHOT=%H_STAGE_SNAPSHOT_REFRESH% ITEM_OFFERS=%H_STAGE_ITEM_OFFERS% PILOT=%H_STAGE_PHASE1_PILOT% INTEL=%H_STAGE_PHASE1_INTEL% PUBLISH=%H_STAGE_PHASE1_PUBLISH% PILOT_MODE=%H_PHASE1_PILOT_MODE% INTEL_MODE=%H_PHASE1_INTEL_MODE% PUBLISH_MODE=%H_PHASE1_PUBLISH_MODE% OFFERS_MAX_ASINS=%SPAPI_ITEM_OFFERS_MAX_ASINS_PER_RUN% USE_GUARD=%H_USE_GUARD_WRAPPER% GUARD_DIAG=%H_GUARD_DIAGNOSTIC_MODE% >> "%H_TASK_LOG%"
set "PYTHONUNBUFFERED=1"
if /I "%H_USE_GUARD_WRAPPER%"=="1" (
  "%PY%" -u "%ROOT%\scripts\cycles\run_H_pricing_cycle_guarded.py" --phase1-pilot --phase1-config "%CFG%" --sleep-minutes 0 %EXTRA_ARGS% >> "%H_TASK_LOG%" 2>&1
) else (
  "%PY%" -u "%ROOT%\scripts\cycles\run_H_pricing_cycle.py" --phase1-pilot --phase1-config "%CFG%" --sleep-minutes 0 %EXTRA_ARGS% >> "%H_TASK_LOG%" 2>&1
)
set "RC=%errorlevel%"
set "H_HEARTBEAT=%H_LIVE%\H_pricing_cycle.HEARTBEAT.txt"
if "%RC%"=="0" if /I "%H_USE_GUARD_WRAPPER%"=="1" (
  findstr /C:"EXIT_OK" /C:"SYSTEMEXIT" /C:"EXIT_CRASH" /C:"OS_EXIT" /C:"SIGNAL" "%H_HEARTBEAT%" >nul 2>&1
  if errorlevel 1 (
    set "RC=98"
    echo [%date% %time%] H-cycle launcher detected missing heartbeat exit marker - forcing exit 98 >> "%H_TASK_LOG%"
  )
)
echo [%date% %time%] H-cycle loop finished (exit %RC%) >> "%H_TASK_LOG%"
for %%L in ("%H_LIVE%\H_pricing_cycle.lock" "%ROOT%\out\H_pricing_cycle.lock") do (
  if exist "%%~fL" del /q "%%~fL" >nul 2>&1
)
if /I "%H_RUN_ONCE%"=="1" (
  endlocal & exit /b %RC%
)
if /I not "%H_LAUNCHER_RESTART_ON_EXIT%"=="1" (
  echo [%date% %time%] H-cycle launcher stop on child exit (H_LAUNCHER_RESTART_ON_EXIT=%H_LAUNCHER_RESTART_ON_EXIT%, exit %RC%) >> "%H_TASK_LOG%"
  endlocal & exit /b %RC%
)
echo [%date% %time%] H-cycle launcher restart in 10s (last exit %RC%) >> "%H_TASK_LOG%"
timeout /t 10 /nobreak >nul
goto loop
