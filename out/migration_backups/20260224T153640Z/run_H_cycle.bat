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
if not exist "%ROOT%\out" mkdir "%ROOT%\out"
set "H_TASK_LOG=%H_LIVE%\phase1_pilot_task.log"
powershell -NoProfile -Command "$active=(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'cmd.exe' -and $_.CommandLine -like '*run_H_cycle.bat*' }).Count; if ($active -gt 1) { exit 96 } else { exit 0 }" >nul 2>&1
if errorlevel 96 (
  echo [%date% %time%] H-cycle launcher detected active instance, exiting >> "%H_TASK_LOG%"
  endlocal & exit /b 96
)
set "H_CYCLE_LOCK_PATH=%H_LIVE%\H_pricing_cycle.lock"
if not defined H_LOCK_STALE_SECONDS set "H_LOCK_STALE_SECONDS=300"
set "H_PRICING_LOG_PATH=%H_LIVE%\H_pricing_cycle.log"
set "H_CYCLE_LOG_PATH=%H_LIVE%\H_cycle.log"
set "H_PRICING_STATE_PATH=%H_LIVE%\h_pricing_cycle_state.json"
set "H_HEALTH_RUN_INLINE=1"
set "H_IGNORE_SIGINT=1"
set "CFG=%ROOT%\config\pilot_sku.yaml"
if not exist "%CFG%" (
  echo [run_H_cycle] Missing config: "%CFG%"
  endlocal & exit /b 1
)
set "EXTRA_ARGS=--run-once"
if not exist "%ROOT%\out" mkdir "%ROOT%\out"
set "H_TASK_LOG=%H_LIVE%\phase1_pilot_task.log"
set "H_LAUNCHER_RESTART_ON_EXIT=1"
REM Hard-set bisect profile for scheduler runs (no external env required).
if not defined H_BISECT_FORCE_INLINE set "H_BISECT_FORCE_INLINE=0"
if not defined H_STAGE_SNAPSHOT_REFRESH set "H_STAGE_SNAPSHOT_REFRESH=1"
if not defined H_STAGE_ITEM_OFFERS set "H_STAGE_ITEM_OFFERS=1"
if not defined H_STAGE_PHASE1_PILOT set "H_STAGE_PHASE1_PILOT=1"
if not defined H_STAGE_PHASE1_INTEL set "H_STAGE_PHASE1_INTEL=1"
if not defined H_STAGE_PHASE1_PUBLISH set "H_STAGE_PHASE1_PUBLISH=1"
if not defined H_PHASE1_PILOT_MODE set "H_PHASE1_PILOT_MODE=subprocess"
if not defined H_PHASE1_INTEL_MODE set "H_PHASE1_INTEL_MODE=inline"
if not defined H_PHASE1_PUBLISH_MODE set "H_PHASE1_PUBLISH_MODE=subprocess"
if not defined H_PHASE1_OBSERVATION_PUBLISH_ENABLED set "H_PHASE1_OBSERVATION_PUBLISH_ENABLED=1"
if not defined H_SPLIT_HEALTH_MODE set "H_SPLIT_HEALTH_MODE=shadow"
if not defined H_REFRESH_MIN_SECONDS set "H_REFRESH_MIN_SECONDS=1"
if not defined H110_MAX_SKUS_PER_RUN_OVERRIDE set "H110_MAX_SKUS_PER_RUN_OVERRIDE=0"
if not defined H110_SKU_CALL_SPACING_SECONDS_OVERRIDE set "H110_SKU_CALL_SPACING_SECONDS_OVERRIDE=0.25"
if not defined SPAPI_ITEM_OFFERS_MAX_ASINS_PER_RUN set "SPAPI_ITEM_OFFERS_MAX_ASINS_PER_RUN=0"
if not defined H_GUARD_DIAGNOSTIC_MODE set "H_GUARD_DIAGNOSTIC_MODE=0"
if not defined PHASE1_LOCK_FORCE_STALE_SECONDS set "PHASE1_LOCK_FORCE_STALE_SECONDS=120"
if not defined H_USE_GUARD_WRAPPER set "H_USE_GUARD_WRAPPER=1"
set "H_GUARD_IGNORE_KEYBOARD_INTERRUPT=1"
if not defined H_PUBLISH_MARKER_WAIT_SECONDS set "H_PUBLISH_MARKER_WAIT_SECONDS=8"

:loop
echo [%date% %time%] H-cycle loop starting >> "%H_TASK_LOG%"
set "H_CYCLE_EXPECTED_RUN_ID="
for /f %%I in ('powershell -NoProfile -Command "(Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')"') do set "H_CYCLE_EXPECTED_RUN_ID=%%I"
if "%H_CYCLE_EXPECTED_RUN_ID%"=="" set "H_CYCLE_EXPECTED_RUN_ID=UNKNOWN"
echo [%date% %time%] H-cycle launcher mode H_RUN_ONCE=%H_RUN_ONCE% EXTRA_ARGS=%EXTRA_ARGS% H_BISECT_FORCE_INLINE=%H_BISECT_FORCE_INLINE% SNAPSHOT=%H_STAGE_SNAPSHOT_REFRESH% ITEM_OFFERS=%H_STAGE_ITEM_OFFERS% PILOT=%H_STAGE_PHASE1_PILOT% INTEL=%H_STAGE_PHASE1_INTEL% PUBLISH=%H_STAGE_PHASE1_PUBLISH% PUBLISH_ENABLED=%H_PHASE1_OBSERVATION_PUBLISH_ENABLED% PILOT_MODE=%H_PHASE1_PILOT_MODE% INTEL_MODE=%H_PHASE1_INTEL_MODE% PUBLISH_MODE=%H_PHASE1_PUBLISH_MODE% OFFERS_MAX_ASINS=%SPAPI_ITEM_OFFERS_MAX_ASINS_PER_RUN% USE_GUARD=%H_USE_GUARD_WRAPPER% GUARD_DIAG=%H_GUARD_DIAGNOSTIC_MODE% H_HEALTH_RUN_INLINE=%H_HEALTH_RUN_INLINE% >> "%H_TASK_LOG%"
echo [%date% %time%] H-cycle launcher expected_run_id=%H_CYCLE_EXPECTED_RUN_ID% >> "%H_TASK_LOG%"
set "PYTHONUNBUFFERED=1"
set "H_SUPERVISOR_PATH=core"
if /I "%H_USE_GUARD_WRAPPER%"=="1" set "H_SUPERVISOR_PATH=guard"
echo [%date% %time%] H-cycle supervisor path=%H_SUPERVISOR_PATH% restart_on_exit=%H_LAUNCHER_RESTART_ON_EXIT% >> "%H_TASK_LOG%"
if /I "%H_USE_GUARD_WRAPPER%"=="1" (
  "%PY%" -u "%ROOT%\scripts\cycles\run_H_pricing_cycle_guarded.py" --phase1-pilot --phase1-config "%CFG%" --sleep-minutes 0 %EXTRA_ARGS% >> "%H_TASK_LOG%" 2>&1
) else (
  "%PY%" -u "%ROOT%\scripts\cycles\run_H_pricing_cycle.py" --phase1-pilot --phase1-config "%CFG%" --sleep-minutes 0 %EXTRA_ARGS% >> "%H_TASK_LOG%" 2>&1
)
echo [%date% %time%] H-cycle launcher postchild checkpoint=after_python >> "%H_TASK_LOG%"
set "RC=%errorlevel%"
echo [%date% %time%] H-cycle child exit raw_rc=%RC% >> "%H_TASK_LOG%"
set "H_CYCLE_RUN_MARKER=%H_LIVE%\H_cycle_current_run_id.txt"
set "H_PUBLISH_RUN_MARKER=%H_LIVE%\H_cycle_last_publish_run_id.txt"
echo [%date% %time%] H-cycle launcher postchild checkpoint=before_publish_marker_check rc=%RC% >> "%H_TASK_LOG%"
if "%RC%"=="0" if /I "%H_STAGE_PHASE1_PUBLISH%"=="1" if not "%H_CYCLE_EXPECTED_RUN_ID%"=="" (
  powershell -NoProfile -Command "$cur='%H_CYCLE_EXPECTED_RUN_ID%';$marker='%H_PUBLISH_RUN_MARKER%';$max=[int]('%H_PUBLISH_MARKER_WAIT_SECONDS%');$ok=$false;$pub='';for($i=0;$i -lt $max;$i++){if(Test-Path $marker){$pub=(Get-Content $marker -TotalCount 1).Trim();if($pub -eq $cur){$ok=$true;break}};Start-Sleep -Seconds 1};if($ok){exit 0};if(Test-Path $marker){$pub=(Get-Content $marker -TotalCount 1).Trim()};Add-Content -Path '%H_TASK_LOG%' -Value ('publish_marker_missing run_id='+$cur+' last_publish_run_id='+$pub+' wait_s='+$max);exit 97" >nul 2>&1
  if errorlevel 97 set "RC=97"
)
echo [%date% %time%] H-cycle launcher postchild checkpoint=after_publish_marker_check rc=%RC% >> "%H_TASK_LOG%"
set "H_HEARTBEAT=%H_LIVE%\H_pricing_cycle.HEARTBEAT.txt"
set "H_EXIT_STATUS=%H_LIVE%\H_pricing_cycle.EXIT_STATUS.txt"
echo [%date% %time%] H-cycle launcher postchild checkpoint=before_heartbeat_check rc=%RC% >> "%H_TASK_LOG%"
if "%RC%"=="0" if /I "%H_USE_GUARD_WRAPPER%"=="1" (
  findstr /C:"EXIT_OK" /C:"SYSTEMEXIT" /C:"EXIT_CRASH" /C:"OS_EXIT" /C:"SIGNAL" "%H_HEARTBEAT%" >nul 2>&1
  if errorlevel 1 (
    findstr /C:"EXIT_OK" /C:"SYSTEMEXIT" /C:"EXIT_CRASH" /C:"OS_EXIT" /C:"SIGNAL" "%H_EXIT_STATUS%" >nul 2>&1
    if errorlevel 1 (
      set "RC=98"
      echo [%date% %time%] H-cycle launcher detected missing heartbeat/exit-status marker - forcing exit 98 >> "%H_TASK_LOG%"
      if exist "%H_HEARTBEAT%" (
        echo heartbeat_tail_begin >> "%H_TASK_LOG%"
        type "%H_HEARTBEAT%" >> "%H_TASK_LOG%"
        echo heartbeat_tail_end >> "%H_TASK_LOG%"
      ) else (
        echo heartbeat_missing_file >> "%H_TASK_LOG%"
      )
      if exist "%H_EXIT_STATUS%" (
        echo exit_status_tail_begin >> "%H_TASK_LOG%"
        type "%H_EXIT_STATUS%" >> "%H_TASK_LOG%"
        echo exit_status_tail_end >> "%H_TASK_LOG%"
      ) else (
        echo exit_status_missing_file >> "%H_TASK_LOG%"
      )
    )
  )
)
echo [%date% %time%] H-cycle launcher postchild checkpoint=after_heartbeat_check rc=%RC% >> "%H_TASK_LOG%"
echo [%date% %time%] H-cycle loop finished (exit %RC%) >> "%H_TASK_LOG%"
if not "%RC%"=="0" (
  powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*H110_run_phase1_h_pilot.py*' -and $_.CommandLine -like '*SellerOne 2.0*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >> "%H_TASK_LOG%" 2>&1
)
if /I "%H_RUN_ONCE%"=="1" (
  endlocal & exit /b %RC%
)
if /I not "%H_LAUNCHER_RESTART_ON_EXIT%"=="1" echo [%date% %time%] H-cycle launcher override forcing restart (H_LAUNCHER_RESTART_ON_EXIT=%H_LAUNCHER_RESTART_ON_EXIT%, exit %RC%) >> "%H_TASK_LOG%"
echo [%date% %time%] H-cycle launcher restart in 10s (last exit %RC%) >> "%H_TASK_LOG%"
timeout /t 10 /nobreak >nul
goto loop
