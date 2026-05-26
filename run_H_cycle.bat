:: Operational entrypoint - do not bypass; use for all runs.
@echo off
setlocal
set "PY=C:\Users\Luke\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
cd /d "%ROOT%"
if not defined SELLERONE_STORAGE_MODE set "SELLERONE_STORAGE_MODE=sql_primary_csv_export"
if not defined SELLERONE_SQLITE_PATH set "SELLERONE_SQLITE_PATH=out/sql/sellerone_dev.sqlite3"
set "H_LIVE=%ROOT%\out\systems\H\live"
if not exist "%H_LIVE%" mkdir "%H_LIVE%"
set "H_CONTROLLED_MODE_FLAG=%ROOT%\out\locks\h_controlled_mode.active"
set "PYTHONPATH=%ROOT%;%ROOT%\scripts;%PYTHONPATH%"
if not exist "%ROOT%\out" mkdir "%ROOT%\out"
set "H_TASK_LOG=%H_LIVE%\phase1_pilot_task.log"
if not defined H_TASK_LOG_ROTATE_MAX_MB set "H_TASK_LOG_ROTATE_MAX_MB=32"
if not defined H_TASK_LOG_ROTATE_MAX_FILES set "H_TASK_LOG_ROTATE_MAX_FILES=6"
if not defined H_TASK_LOG_RETENTION_DAYS set "H_TASK_LOG_RETENTION_DAYS=14"
if not defined H_TASK_LOG_FAMILY_MAX_MB set "H_TASK_LOG_FAMILY_MAX_MB=48"
call :rotate_h_task_log
if errorlevel 1 (
  echo [%date% %time%] H-cycle startup rotate_h_task_log failed rc=%ERRORLEVEL% >> "%H_TASK_LOG%"
  echo [run_H_cycle] startup rotate_h_task_log failed rc=%ERRORLEVEL%
  endlocal & exit /b 97
)
REM Default to detached hidden launcher ownership to avoid visible console loops.
REM Attached mode remains opt-in via H_LAUNCHER_AUTO_DETACH=0.
if not defined H_LAUNCHER_AUTO_DETACH set "H_LAUNCHER_AUTO_DETACH=1"
if not defined H_LAUNCHER_DETACHED set "H_LAUNCHER_DETACHED=0"
if /I "%H_LAUNCHER_AUTO_DETACH%"=="1" if /I not "%H_LAUNCHER_DETACHED%"=="1" (
  echo [%date% %time%] H-cycle launcher bootstrap auto_detach request=1 >> "%H_TASK_LOG%"
  powershell -NoProfile -WindowStyle Hidden -Command "$env:H_LAUNCHER_DETACHED='1'; Start-Process -WindowStyle Hidden -FilePath 'cmd.exe' -WorkingDirectory '%ROOT%' -ArgumentList '/d','/c','call ""%~f0""'" >nul 2>&1
  if not errorlevel 1 (
    echo [%date% %time%] H-cycle launcher bootstrap auto_detach started child_launcher=1 parent_exit=clean >> "%H_TASK_LOG%"
    echo [run_H_cycle] detached launcher started (child owns loop)
    endlocal & exit /b 0
  )
  echo [%date% %time%] H-cycle launcher bootstrap auto_detach failed action=continue_inline >> "%H_TASK_LOG%"
)
if not defined H_RESTART_OWNERSHIP_MODE set "H_RESTART_OWNERSHIP_MODE=launcher"
if /I "%H_RESTART_OWNERSHIP_MODE%"=="" set "H_RESTART_OWNERSHIP_MODE=launcher"
set "H_RESTART_OWNER_ROLE=active_owner"
if /I not "%H_RESTART_OWNERSHIP_MODE%"=="launcher" set "H_RESTART_OWNER_ROLE=observer"
set "H_RUN_ONCE_RAW_INPUT=%H_RUN_ONCE%"
if not defined H_RUN_ONCE_RAW_INPUT set "H_RUN_ONCE_RAW_INPUT=0"
set "H_RUN_ONCE_RAW_INPUT=%H_RUN_ONCE_RAW_INPUT:"=%"
set "H_RUN_ONCE_RAW_INPUT=%H_RUN_ONCE_RAW_INPUT: =%"
set "H_RUN_ONCE_REQUESTED=0"
if /I "%H_RUN_ONCE_RAW_INPUT%"=="1" set "H_RUN_ONCE_REQUESTED=1"
set "H_CONTROLLED_MODE_ACTIVE=0"
if exist "%H_CONTROLLED_MODE_FLAG%" set "H_CONTROLLED_MODE_ACTIVE=1"
set "H_RUN_ONCE_SOURCE=default_production"
if /I "%H_RUN_ONCE_REQUESTED%"=="1" set "H_RUN_ONCE_SOURCE=explicit_env"
if /I "%H_CONTROLLED_MODE_ACTIVE%"=="1" set "H_RUN_ONCE_SOURCE=controlled_mode"
set "H_EFFECTIVE_RUN_ONCE=%H_RUN_ONCE_REQUESTED%"
if /I "%H_CONTROLLED_MODE_ACTIVE%"=="1" set "H_EFFECTIVE_RUN_ONCE=1"
if not defined H_ONESHOT_RECOVERY_RETRY_LIMIT set "H_ONESHOT_RECOVERY_RETRY_LIMIT=0"
if not defined H_ONESHOT_RECOVERY_RETRY_DELAY_SECONDS set "H_ONESHOT_RECOVERY_RETRY_DELAY_SECONDS=15"
if not defined H_ONESHOT_RECOVERY_RETRY_COUNT set "H_ONESHOT_RECOVERY_RETRY_COUNT=0"
set "H_LAUNCHER_RESTART_ON_EXIT_RAW_INPUT=%H_LAUNCHER_RESTART_ON_EXIT%"
if not defined H_LAUNCHER_RESTART_ON_EXIT_RAW_INPUT set "H_LAUNCHER_RESTART_ON_EXIT_RAW_INPUT=1"
set "H_LAUNCHER_RESTART_ON_EXIT_RAW_INPUT=%H_LAUNCHER_RESTART_ON_EXIT_RAW_INPUT:"=%"
set "H_LAUNCHER_RESTART_ON_EXIT_RAW_INPUT=%H_LAUNCHER_RESTART_ON_EXIT_RAW_INPUT: =%"
set "H_RESTART_REQUESTED=0"
if /I "%H_LAUNCHER_RESTART_ON_EXIT_RAW_INPUT%"=="1" set "H_RESTART_REQUESTED=1"
set "H_EFFECTIVE_RESTART_ON_EXIT=%H_RESTART_REQUESTED%"
if /I "%H_EFFECTIVE_RUN_ONCE%"=="1" set "H_EFFECTIVE_RESTART_ON_EXIT=0"
set "H_RUN_ONCE=%H_EFFECTIVE_RUN_ONCE%"
set "H_LAUNCHER_RESTART_ON_EXIT=%H_EFFECTIVE_RESTART_ON_EXIT%"
set "H_LAUNCHER_LOCK_FILE=%H_LIVE%\H_launcher.lock"
set "H_LAUNCHER_HEARTBEAT_FILE=%H_LIVE%\H_launcher.heartbeat"
if not defined H_LAUNCHER_HEARTBEAT_STALE_SECONDS set "H_LAUNCHER_HEARTBEAT_STALE_SECONDS=420"
if not defined H_KILL_ORPHAN_H110_ON_FAILURE set "H_KILL_ORPHAN_H110_ON_FAILURE=0"
set "H_LAUNCHER_SELF_PID="
set "H_LAUNCHER_SELF_PID_FILE=%H_LIVE%\H_launcher_self_pid.%RANDOM%.%RANDOM%.%RANDOM%.tmp.cmd"
set "H_LAUNCHER_GATE_TRACE=%H_LIVE%\H_launcher_gate_trace.%RANDOM%.%RANDOM%.%RANDOM%.log"
if exist "%H_LAUNCHER_SELF_PID_FILE%" del /f /q "%H_LAUNCHER_SELF_PID_FILE%" >nul 2>&1
if exist "%H_LAUNCHER_GATE_TRACE%" del /f /q "%H_LAUNCHER_GATE_TRACE%" >nul 2>&1
powershell -NoProfile -WindowStyle Hidden -Command "$ErrorActionPreference='SilentlyContinue';$selfPs=Get-CimInstance Win32_Process -Filter ('ProcessId=' + $PID) -ErrorAction SilentlyContinue;$selfPid=0;if($selfPs){$selfPid=[int]$selfPs.ParentProcessId};$line='set ""H_LAUNCHER_SELF_PID=' + $selfPid + '""';[System.IO.File]::WriteAllText('%H_LAUNCHER_SELF_PID_FILE%',$line + [Environment]::NewLine,[System.Text.Encoding]::ASCII)" >nul 2>&1
if exist "%H_LAUNCHER_SELF_PID_FILE%" call "%H_LAUNCHER_SELF_PID_FILE%"
if exist "%H_LAUNCHER_SELF_PID_FILE%" del /f /q "%H_LAUNCHER_SELF_PID_FILE%" >nul 2>&1
if not defined H_LAUNCHER_SELF_PID set "H_LAUNCHER_SELF_PID=0"
powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%ROOT%\scripts\tools\h_launcher_gate.ps1" -Mode gate -Root "%ROOT%" -SelfPid %H_LAUNCHER_SELF_PID% -LockPath "%H_LAUNCHER_LOCK_FILE%" -HeartbeatPath "%H_LAUNCHER_HEARTBEAT_FILE%" -HeartbeatStaleSeconds %H_LAUNCHER_HEARTBEAT_STALE_SECONDS% > "%H_LAUNCHER_GATE_TRACE%" 2>&1
set "EARLY_GATE_RC=%ERRORLEVEL%"
if exist "%H_LAUNCHER_GATE_TRACE%" type "%H_LAUNCHER_GATE_TRACE%" >> "%H_TASK_LOG%" 2>nul
if "%EARLY_GATE_RC%"=="96" (
  echo [run_H_cycle] H launcher already active - refusing concurrent start
  echo [%date% %time%] H-cycle launcher detected active instance, exiting >> "%H_LAUNCHER_GATE_TRACE%"
  endlocal & exit /b 96
)
powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%ROOT%\scripts\tools\h_launcher_gate.ps1" -Mode confirm -Root "%ROOT%" -SelfPid %H_LAUNCHER_SELF_PID% -LockPath "%H_LAUNCHER_LOCK_FILE%" -HeartbeatPath "%H_LAUNCHER_HEARTBEAT_FILE%" -HeartbeatStaleSeconds %H_LAUNCHER_HEARTBEAT_STALE_SECONDS% >> "%H_LAUNCHER_GATE_TRACE%" 2>&1
set "EARLY_CONFIRM_RC=%ERRORLEVEL%"
if exist "%H_LAUNCHER_GATE_TRACE%" type "%H_LAUNCHER_GATE_TRACE%" >> "%H_TASK_LOG%" 2>nul
if "%EARLY_CONFIRM_RC%"=="96" (
  echo [run_H_cycle] H launcher already active - refusing concurrent start
  echo [%date% %time%] H-cycle launcher detected active instance, exiting >> "%H_LAUNCHER_GATE_TRACE%"
  endlocal & exit /b 96
)
if not defined H_LOCK_STALE_SECONDS set "H_LOCK_STALE_SECONDS=300"
if not defined H_RECONCILE_HOLD_SECONDS set "H_RECONCILE_HOLD_SECONDS=90"
if not defined H_RECONCILE_RUNTIME_STALE_SECONDS set "H_RECONCILE_RUNTIME_STALE_SECONDS=180"
set "H_CYCLE_LOCK_PATH=%H_LIVE%\H_pricing_cycle.lock"
set "H_ROOT_LOCK_PATH=%ROOT%\out\H_pricing_cycle.lock"
:startup_lock_check
set "H_STARTUP_RECONCILE_HOLD=0"
for %%L in ("%H_CYCLE_LOCK_PATH%" "%H_ROOT_LOCK_PATH%") do (
  if exist "%%~fL" (
    powershell -NoProfile -WindowStyle Hidden -Command "$path='%%~fL';$now=(Get-Date).ToUniversalTime();$line='';if(Test-Path $path){$line=(Get-Content $path -Raw).Trim()};$lockPid=$null;if($line -match 'pid=(\d+)'){try{$lockPid=[int]$Matches[1]}catch{$lockPid=$null}};$run='';if($line -match 'run_id=([^|\s]+)'){$run=$Matches[1].Trim()};$hb=$null;if($line -match 'heartbeat=([0-9TZ:\-\.]+)'){try{$hb=[datetime]::Parse($Matches[1]).ToUniversalTime()}catch{}};$start=$null;if($line -match 'start=([0-9TZ:\-\.]+)'){try{$start=[datetime]::Parse($Matches[1]).ToUniversalTime()}catch{}};$ts=$hb;if(-not $ts){$ts=$start};$alive=$false;if($lockPid){try{$proc=Get-Process -Id $lockPid -ErrorAction SilentlyContinue;if($proc){$alive=$true}}catch{$alive=$false}};$freshTol=[double]%H_RECONCILE_RUNTIME_STALE_SECONDS%;$holdSeconds=[double]%H_RECONCILE_HOLD_SECONDS%;$launcherFresh=$false;$launcherAge=-1.0;$launcherPath='%H_LAUNCHER_HEARTBEAT_FILE%';if(Test-Path $launcherPath){try{$hbLine=(Get-Content $launcherPath -Raw).Trim();$hbUtc='';if($hbLine -match 'utc=([0-9TZ:\-]+)'){$hbUtc=$Matches[1]};if($hbUtc){$hbTs=[datetime]::Parse($hbUtc).ToUniversalTime();$launcherAge=($now-$hbTs).TotalSeconds;$launcherFresh=($launcherAge -ge 0 -and $launcherAge -le $freshTol)}}catch{}};$runtimeFresh=$false;$runtimeAge=-1.0;$runtimePath=Join-Path '%H_LIVE%' 'H_runtime_status.json';if(Test-Path $runtimePath){try{$runtimeRaw=Get-Content $runtimePath -Raw | ConvertFrom-Json;$runtimeUtc=[string]$runtimeRaw.utc;if($runtimeUtc){$runtimeTs=[datetime]::Parse($runtimeUtc).ToUniversalTime();$runtimeAge=($now-$runtimeTs).TotalSeconds}else{$runtimeAge=($now-(Get-Item $runtimePath).LastWriteTimeUtc).TotalSeconds};$runtimeFresh=($runtimeAge -ge 0 -and $runtimeAge -le $freshTol)}catch{try{$runtimeAge=($now-(Get-Item $runtimePath).LastWriteTimeUtc).TotalSeconds;$runtimeFresh=($runtimeAge -ge 0 -and $runtimeAge -le $freshTol)}catch{}}};$runMarker='';$runMarkerPath=Join-Path '%H_LIVE%' 'H_run_in_progress.txt';if(Test-Path $runMarkerPath){$runMarker=(Get-Content $runMarkerPath -Raw).Trim()};$finalized='';$finalizedPath=Join-Path '%H_LIVE%' 'H_last_finalized_run_id.txt';if(Test-Path $finalizedPath){$finalized=(Get-Content $finalizedPath -Raw).Trim()};$mismatchReasons=@();if($lockPid -and -not $alive){$mismatchReasons+='lock_pid_dead'};if((-not $lockPid) -or ($lockPid -le 0)){$mismatchReasons+='lock_pid_missing'};if(($launcherFresh -or $runtimeFresh) -and (-not $alive)){$mismatchReasons+='fresh_runtime_evidence_present'};if($run -and $runMarker -and $run -eq $runMarker -and $finalized -ne $run){$mismatchReasons+='parent_child_marker_disagree'};$mismatch=($mismatchReasons.Count -gt 0);$age='';if($ts){$age=[math]::Round(($now-$ts).TotalSeconds,2).ToString()};$statePath=Join-Path '%H_LIVE%' ('H_reconcile_lock.' + [IO.Path]::GetFileName($path) + '.json');if($lockPid -and $alive){if(Test-Path $statePath){Remove-Item -Path $statePath -Force -ErrorAction SilentlyContinue;Write-Output ('reconcile_hold_cleared_healthy path=' + $path + ' reason=pid_alive')};Write-Output ('active_lock_detected path=' + $path + ' pid=' + $lockPid + ' run_id=' + $run);exit 96};if($mismatch){$state=$null;if(Test-Path $statePath){try{$state=Get-Content $statePath -Raw | ConvertFrom-Json}catch{$state=$null}};$stateStart=$null;if($state -and $state.started_utc){try{$stateStart=[datetime]::Parse([string]$state.started_utc).ToUniversalTime()}catch{$stateStart=$null}};if(-not $stateStart){$stateObj=@{started_utc=$now.ToString('yyyy-MM-ddTHH:mm:ssZ');path=$path;reasons=($mismatchReasons -join ',');run_id=$run;pid=$lockPid};[System.IO.File]::WriteAllText($statePath,(ConvertTo-Json $stateObj -Depth 6) + [Environment]::NewLine,[System.Text.Encoding]::ASCII);Write-Output ('reconcile_hold_enter path=' + $path + ' hold_seconds=' + $holdSeconds + ' reasons=' + ($mismatchReasons -join ',') + ' launcher_age_seconds=' + [math]::Round($launcherAge,2) + ' runtime_age_seconds=' + [math]::Round($runtimeAge,2));Write-Output ('stale_cleanup_skipped_due_to_reconcile path=' + $path + ' hold_state=enter');exit 94};$holdAge=($now-$stateStart).TotalSeconds;if($holdAge -lt $holdSeconds){$remaining=[math]::Round($holdSeconds-$holdAge,2);Write-Output ('reconcile_hold_active path=' + $path + ' age_seconds=' + [math]::Round($holdAge,2) + ' remaining_seconds=' + $remaining + ' reasons=' + ($mismatchReasons -join ','));Write-Output ('stale_cleanup_skipped_due_to_reconcile path=' + $path + ' hold_state=active');exit 94};Write-Output ('reconcile_hold_expired path=' + $path + ' age_seconds=' + [math]::Round($holdAge,2) + ' reasons=' + ($mismatchReasons -join ','));Remove-Item -Path $statePath -Force -ErrorAction SilentlyContinue;Write-Output ('stale_cleanup_allowed path=' + $path + ' reason=reconcile_expired')}else{if(Test-Path $statePath){Remove-Item -Path $statePath -Force -ErrorAction SilentlyContinue;Write-Output ('reconcile_hold_cleared_healthy path=' + $path + ' reason=evidence_healthy')};Write-Output ('stale_cleanup_allowed path=' + $path + ' reason=no_reconcile_mismatch')};$reason='missing_or_invalid_pid';if($lockPid){$reason='dead_pid'};$archiveDir='%ROOT%\out\locks\archive';New-Item -ItemType Directory -Force -Path $archiveDir | Out-Null;$stamp=(Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ');$archive=Join-Path $archiveDir ('H.lock.' + $stamp);$n=1;while(Test-Path $archive){$n=$n+1;$archive=Join-Path $archiveDir ('H.lock.' + $stamp + '.' + $n)};if(Test-Path $path){Move-Item -Path $path -Destination $archive -Force -ErrorAction SilentlyContinue};Write-Output ('stale_lock_removed path=' + $path + ' archive=' + $archive + ' pid=' + $lockPid + ' run_id=' + $run + ' reason=' + $reason + ' age_seconds=' + $age);exit 95" >> "%H_TASK_LOG%" 2>&1
    set "LOCK_CHECK_RC=%ERRORLEVEL%"
    if "%LOCK_CHECK_RC%"=="96" (
      echo [%date% %time%] H-cycle launcher detected active lock holder path=%%~fL, exiting >> "%H_TASK_LOG%"
      endlocal & exit /b 96
    )
    if "%LOCK_CHECK_RC%"=="94" (
      set "H_STARTUP_RECONCILE_HOLD=1"
      echo [%date% %time%] H-cycle launcher stale_cleanup_skipped_due_to_reconcile path=%%~fL >> "%H_TASK_LOG%"
    )
    if "%LOCK_CHECK_RC%"=="95" (
      echo [%date% %time%] H-cycle launcher stale_lock_removed path=%%~fL and continued >> "%H_TASK_LOG%"
    )
  )
)
if /I "%H_STARTUP_RECONCILE_HOLD%"=="1" (
  echo [%date% %time%] H-cycle launcher reconcile_hold_active startup_wait_seconds=15 >> "%H_TASK_LOG%"
  timeout /t 15 /nobreak >nul 2>&1
  goto startup_lock_check
)
set "H_PRICING_LOG_PATH=%H_LIVE%\H_pricing_cycle.log"
set "H_CYCLE_LOG_PATH=%H_LIVE%\H_cycle.log"
set "H_PRICING_STATE_PATH=%H_LIVE%\h_pricing_cycle_state.json"
set "H_RUN_IN_PROGRESS_FILE=%H_LIVE%\H_run_in_progress.txt"
set "H_FINALIZED_RUN_FILE=%H_LIVE%\H_last_finalized_run_id.txt"
set "MAINT_REQUEST_PATH=%ROOT%\out\locks\maintenance.requested"
set "MAINT_READY_PATH=%ROOT%\out\locks\maintenance.ready"
set "MAINT_ACTIVE_PATH=%ROOT%\out\locks\maintenance.active"
set "H_DRAIN_READY_FILE=%H_LIVE%\H_restart_drain.ready"
if not defined H_PHASE1_BOUNDARY_STALE_SECONDS set "H_PHASE1_BOUNDARY_STALE_SECONDS=900"
if not defined H_CORE_STARTUP_RECONCILE_ENABLE set "H_CORE_STARTUP_RECONCILE_ENABLE=1"
if not defined H_LAUNCHER_STARTUP_RECONCILE_ENABLE set "H_LAUNCHER_STARTUP_RECONCILE_ENABLE=%H_CORE_STARTUP_RECONCILE_ENABLE%"
if not defined H_HEALTH_RUN_INLINE set "H_HEALTH_RUN_INLINE=0"
if not defined H_EXIT_ON_WARN set "H_EXIT_ON_WARN=0"
set "H_IGNORE_SIGINT=1"
set "CFG=%ROOT%\config\pilot_sku.yaml"
if not exist "%CFG%" (
  echo [run_H_cycle] Missing config: "%CFG%"
  endlocal & exit /b 1
)
set "EXTRA_ARGS="
if /I "%H_EFFECTIVE_RUN_ONCE%"=="1" set "EXTRA_ARGS=--run-once"
if not exist "%ROOT%\out" mkdir "%ROOT%\out"
set "H_TASK_LOG=%H_LIVE%\phase1_pilot_task.log"
REM Production default: keep H running continuously after each clean child exit.
REM One-shot behavior is maintenance-only and must be explicitly requested.
REM Hard-set bisect profile for scheduler runs (no external env required).
if not defined H_BISECT_FORCE_INLINE set "H_BISECT_FORCE_INLINE=0"
if not defined H_STAGE_SNAPSHOT_REFRESH set "H_STAGE_SNAPSHOT_REFRESH=1"
if not defined H_STAGE_ITEM_OFFERS set "H_STAGE_ITEM_OFFERS=1"
if not defined H_STAGE_PHASE1_PILOT set "H_STAGE_PHASE1_PILOT=1"
if not defined H_STAGE_PHASE1_INTEL set "H_STAGE_PHASE1_INTEL=1"
if not defined H_STAGE_PHASE1_PUBLISH set "H_STAGE_PHASE1_PUBLISH=1"
if not defined H_ALLOW_NO_PUBLISH_TERMINAL_OK set "H_ALLOW_NO_PUBLISH_TERMINAL_OK=0"
REM H110 pilot must run out-of-process so a pilot-only control-flow exit cannot terminate the H parent before publish.
if not defined H_PHASE1_PILOT_MODE set "H_PHASE1_PILOT_MODE=subprocess"
if not defined H_PHASE1_INTEL_MODE set "H_PHASE1_INTEL_MODE=inline"
if not defined H_PHASE1_PUBLISH_MODE set "H_PHASE1_PUBLISH_MODE=inline"
if not defined H_SNAPSHOT_WORKER_MODE set "H_SNAPSHOT_WORKER_MODE=0"
if not defined H_PHASE1_OBSERVATION_PUBLISH_ENABLED set "H_PHASE1_OBSERVATION_PUBLISH_ENABLED=1"
if not defined H_SPLIT_HEALTH_MODE set "H_SPLIT_HEALTH_MODE=shadow"
if not defined H_PHASE_ENGINE_ENABLED set "H_PHASE_ENGINE_ENABLED=1"
if not defined H_PHASE_ENGINE_BEHAVIOR set "H_PHASE_ENGINE_BEHAVIOR=1"
if not defined H_PHASE_ENGINE_LIVE_WRITES set "H_PHASE_ENGINE_LIVE_WRITES=1"
if not defined H_PHASE_ENGINE_SHADOW set "H_PHASE_ENGINE_SHADOW=1"
if not defined H_PHASE_ENGINE_COHORT_FILE set "H_PHASE_ENGINE_COHORT_FILE=%ROOT%\config\phase_engine_cohort.csv"
if not defined H_PHASE_ENGINE_EXCLUDE_FILE set "H_PHASE_ENGINE_EXCLUDE_FILE=%ROOT%\config\phase_engine_exclusions.csv"
if not defined H_STRATEGY_GO_LIVE_UTC set "H_STRATEGY_GO_LIVE_UTC=2026-03-04T14:05:00Z"
if not defined H_REFRESH_MIN_SECONDS set "H_REFRESH_MIN_SECONDS=1"
if not defined H110_MAX_SKUS_PER_RUN_OVERRIDE set "H110_MAX_SKUS_PER_RUN_OVERRIDE=0"
if not defined H110_SKU_CALL_SPACING_SECONDS_OVERRIDE set "H110_SKU_CALL_SPACING_SECONDS_OVERRIDE=1.50"
if not defined SPAPI_ITEM_OFFERS_MAX_ASINS_PER_RUN set "SPAPI_ITEM_OFFERS_MAX_ASINS_PER_RUN=15"
if not defined H_GUARD_DIAGNOSTIC_MODE set "H_GUARD_DIAGNOSTIC_MODE=0"
if not defined PHASE1_LOCK_FORCE_STALE_SECONDS set "PHASE1_LOCK_FORCE_STALE_SECONDS=120"
if not defined H_USE_GUARD_WRAPPER set "H_USE_GUARD_WRAPPER=1"
set "H_USE_GUARD_WRAPPER_RAW=%H_USE_GUARD_WRAPPER%"
set "H_USE_GUARD_WRAPPER_RAW=%H_USE_GUARD_WRAPPER_RAW:"=%"
set "H_USE_GUARD_WRAPPER_RAW=%H_USE_GUARD_WRAPPER_RAW: =%"
set "H_USE_GUARD_WRAPPER=0"
if /I "%H_USE_GUARD_WRAPPER_RAW%"=="1" set "H_USE_GUARD_WRAPPER=1"
if /I "%H_USE_GUARD_WRAPPER_RAW%"=="true" set "H_USE_GUARD_WRAPPER=1"
if /I "%H_USE_GUARD_WRAPPER_RAW%"=="yes" set "H_USE_GUARD_WRAPPER=1"
if /I "%H_USE_GUARD_WRAPPER_RAW%"=="on" set "H_USE_GUARD_WRAPPER=1"
if not defined H_SHORT_FAILURE_SECONDS set "H_SHORT_FAILURE_SECONDS=180"
if not defined H_SHORT_FAILURE_WINDOW_SECONDS set "H_SHORT_FAILURE_WINDOW_SECONDS=300"
if not defined H_HEALTHY_RESET_MIN_SECONDS set "H_HEALTHY_RESET_MIN_SECONDS=240"
if not defined H_MAX_COOLDOWN_TIER set "H_MAX_COOLDOWN_TIER=4"
if not defined H_SHORT_FAILURE_STREAK set "H_SHORT_FAILURE_STREAK=0"
if not defined H_LAST_SHORT_FAILURE_EPOCH set "H_LAST_SHORT_FAILURE_EPOCH=0"
if not defined H_INTERRUPTION_RECOVERY_SECONDS set "H_INTERRUPTION_RECOVERY_SECONDS=30"
if not defined H_LAST_INTERRUPTION_CLASS set "H_LAST_INTERRUPTION_CLASS=0"
set "H_PHASE1_RUNTIME_FLOOR_SNAPSHOT_ENABLED=1"
set "H_GUARD_IGNORE_KEYBOARD_INTERRUPT=1"
if not defined H_PUBLISH_MARKER_WAIT_SECONDS set "H_PUBLISH_MARKER_WAIT_SECONDS=8"
if not defined H_MARKER_CHECK_STRICT set "H_MARKER_CHECK_STRICT=0"
if not defined H_GATING_MODE set "H_GATING_MODE=0"
if defined H_TASK_SKIP_STAGE_ARGS set "EXTRA_ARGS=%EXTRA_ARGS% %H_TASK_SKIP_STAGE_ARGS%"
"%PY%" -u "%ROOT%\scripts\tools\h_session_tally.py" init >> "%H_TASK_LOG%" 2>&1

:loop
call :rotate_h_task_log
set "H_CURRENT_RUN_FILE=%H_LIVE%\H_cycle_current_run_id.txt"
set "H_PUBLISH_RUN_FILE=%H_LIVE%\H_cycle_last_publish_run_id.txt"
set "H_COMPLETED_RUN_FILE=%H_LIVE%\H_cycle_last_completed_run_id.txt"
set "H_FINALIZED_RUN_FILE=%H_LIVE%\H_last_finalized_run_id.txt"
set "H_RUN_STATE_FILE=%H_LIVE%\H_run_state.json"
powershell -NoProfile -WindowStyle Hidden -Command "$payload=('launcher_pid=%H_LAUNCHER_SELF_PID%|utc=' + (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ') + '|state=loop_ready|restart_owner=launcher_loop|owner_role=%H_RESTART_OWNER_ROLE%'); [System.IO.File]::WriteAllText('%H_LAUNCHER_HEARTBEAT_FILE%',$payload + [Environment]::NewLine,[System.Text.Encoding]::ASCII)" >nul 2>&1
echo [%date% %time%] H-cycle restart_ownership owner=launcher_loop role=%H_RESTART_OWNER_ROLE% mode=%H_RESTART_OWNERSHIP_MODE% >> "%H_TASK_LOG%"
set "H_RESTART_DRAIN_REQUESTED=0"
if exist "%MAINT_REQUEST_PATH%" (
  powershell -NoProfile -WindowStyle Hidden -Command "$text='';try{$text=Get-Content '%MAINT_REQUEST_PATH%' -Raw}catch{};if($text -and $text -match 'requested_by=controlled_restart_gate' -and $text -match 'reason=overnight_restart_eval'){exit 11};exit 0" >nul 2>&1
  if "%ERRORLEVEL%"=="11" set "H_RESTART_DRAIN_REQUESTED=1"
)
if "%H_RESTART_DRAIN_REQUESTED%"=="1" (
  echo [%date% %time%] H-cycle launcher restart_drain requested - waiting at boundary and skipping child launch >> "%H_TASK_LOG%"
  powershell -NoProfile -WindowStyle Hidden -Command "$now=(Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ');$payload=('H_DRAIN_READY|launcher_pid=%H_LAUNCHER_SELF_PID%|ts=' + $now + '|state=boundary_wait'); [System.IO.File]::WriteAllText('%H_DRAIN_READY_FILE%',$payload + [Environment]::NewLine,[System.Text.Encoding]::ASCII)" >nul 2>&1
  goto drain_wait
)
if exist "%H_DRAIN_READY_FILE%" del /f /q "%H_DRAIN_READY_FILE%" >nul 2>&1
set "BOUNDARY_GUARD_RC=0"
powershell -NoProfile -WindowStyle Hidden -Command "$live='%H_LIVE%';$repo=[regex]::Escape('%ROOT%');$files=Get-ChildItem -Path $live -Filter 'phase1_intel_alignment.boundary.*.json' -ErrorAction SilentlyContinue | Sort-Object LastWriteTimeUtc;foreach($file in $files){$raw=$null;try{$raw=Get-Content $file.FullName -Raw | ConvertFrom-Json}catch{continue};if(-not $raw){continue};$statusNorm=([string]$raw.status).Trim().ToLower();if(@('active','unresolved_parent_exit','stale_or_orphaned') -notcontains $statusNorm){continue};$run=[string]$raw.run_id;$childPid=0;try{$childPid=[int]$raw.child_pid}catch{$childPid=0};$childAlive=$false;if($childPid -gt 0){try{$proc=Get-Process -Id $childPid -ErrorAction SilentlyContinue;if($proc){$childAlive=$true}}catch{}};Write-Output ('active_phase1_intel_boundary_detected run_id=' + $run + ' status=' + $statusNorm + ' child_pid=' + $childPid + ' child_alive=' + ($childAlive.ToString().ToLower()) + ' path=' + $file.FullName + ' reason=fail_closed_no_status_mutation');exit 96};exit 0" >> "%H_TASK_LOG%" 2>&1
set "BOUNDARY_GUARD_RC=%ERRORLEVEL%"
if "%BOUNDARY_GUARD_RC%"=="96" (
  echo [%date% %time%] H-cycle launcher detected unresolved phase1 intel boundary mode=no_reconciliation exiting >> "%H_TASK_LOG%"
  endlocal & exit /b 96
)
set "RUN_PROGRESS_RC=0"
powershell -NoProfile -WindowStyle Hidden -Command "$runPath='%H_RUN_IN_PROGRESS_FILE%';$finPath='%H_FINALIZED_RUN_FILE%';if(-not (Test-Path $runPath)){exit 0};$run=(Get-Content $runPath -Raw).Trim();$fin='';if(Test-Path $finPath){$fin=(Get-Content $finPath -Raw).Trim()};if(-not $run -or $run -eq $fin){exit 0};$repo=[regex]::Escape('%ROOT%');$active=(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match $repo -and ( $_.CommandLine -like '*scripts\\cycles\\run_H_pricing_cycle.py*' -or $_.CommandLine -like '*scripts\\cycles\\run_H_pricing_cycle_guarded.py*' -or $_.CommandLine -like '*scripts\\flows\\H\\H110_run_phase1_h_pilot.py*' ) });$pids=@($active | ForEach-Object { [string]$_.ProcessId }) -join ',';if($pids){Write-Output ('active_run_in_progress run_id=' + $run + ' finalized=' + $fin + ' reason=duplicate_live_owner_detected pids=' + $pids);exit 96};Write-Output ('stale_run_in_progress_observed run_id=' + $run + ' finalized=' + $fin + ' reason=no_live_owner_continue_to_core_reconcile pids=none');exit 0" >> "%H_TASK_LOG%" 2>&1
set "RUN_PROGRESS_RC=%ERRORLEVEL%"
if "%RUN_PROGRESS_RC%"=="96" (
  echo [%date% %time%] H-cycle launcher detected duplicate live owner for in-progress marker mode=fail_closed exiting >> "%H_TASK_LOG%"
  endlocal & exit /b 96
)
echo [%date% %time%] H-cycle launcher startup_reconcile core_enabled=%H_CORE_STARTUP_RECONCILE_ENABLE% legacy_enabled=%H_LAUNCHER_STARTUP_RECONCILE_ENABLE% policy=core_owned_hard_proof >> "%H_TASK_LOG%"
echo [%date% %time%] H-cycle loop starting >> "%H_TASK_LOG%"
if /I "%H_GATING_MODE%"=="1" (
  echo [%date% %time%] H_GATING_MODE=1: marker strictness disabled; completed markers may not advance in partial runs >> "%H_TASK_LOG%"
)
echo [%date% %time%] H-cycle launcher cwd=%CD% py=%PY% cfg=%CFG% >> "%H_TASK_LOG%"
set "H_LAUNCH_MODE=continuous_production"
if /I "%H_CONTROLLED_MODE_ACTIVE%"=="1" set "H_LAUNCH_MODE=controlled_one_shot"
if /I not "%H_CONTROLLED_MODE_ACTIVE%"=="1" if /I "%H_EFFECTIVE_RUN_ONCE%"=="1" set "H_LAUNCH_MODE=one_shot_explicit"
echo [%date% %time%] H-cycle launcher mode raw_run_once=%H_RUN_ONCE_RAW_INPUT% requested_run_once=%H_RUN_ONCE_REQUESTED% effective_run_once=%H_EFFECTIVE_RUN_ONCE% run_once_source=%H_RUN_ONCE_SOURCE% raw_restart_on_exit=%H_LAUNCHER_RESTART_ON_EXIT_RAW_INPUT% requested_restart_on_exit=%H_RESTART_REQUESTED% effective_restart_on_exit=%H_EFFECTIVE_RESTART_ON_EXIT% launch_mode=%H_LAUNCH_MODE% controlled_mode_active=%H_CONTROLLED_MODE_ACTIVE% EXTRA_ARGS=%EXTRA_ARGS% H_BISECT_FORCE_INLINE=%H_BISECT_FORCE_INLINE% SNAPSHOT=%H_STAGE_SNAPSHOT_REFRESH% ITEM_OFFERS=%H_STAGE_ITEM_OFFERS% PILOT=%H_STAGE_PHASE1_PILOT% INTEL=%H_STAGE_PHASE1_INTEL% PUBLISH=%H_STAGE_PHASE1_PUBLISH% PUBLISH_ENABLED=%H_PHASE1_OBSERVATION_PUBLISH_ENABLED% PILOT_MODE=%H_PHASE1_PILOT_MODE% INTEL_MODE=%H_PHASE1_INTEL_MODE% PUBLISH_MODE=%H_PHASE1_PUBLISH_MODE% FLOOR_SNAPSHOT=%H_PHASE1_RUNTIME_FLOOR_SNAPSHOT_ENABLED% OFFERS_MAX_ASINS=%SPAPI_ITEM_OFFERS_MAX_ASINS_PER_RUN% USE_GUARD=%H_USE_GUARD_WRAPPER% GUARD_DIAG=%H_GUARD_DIAGNOSTIC_MODE% H_HEALTH_RUN_INLINE=%H_HEALTH_RUN_INLINE% >> "%H_TASK_LOG%"
echo [%date% %time%] H-cycle launcher policy launch_mode=%H_LAUNCH_MODE% restart_on_exit=%H_EFFECTIVE_RESTART_ON_EXIT% controlled_mode_active=%H_CONTROLLED_MODE_ACTIVE% run_once=%H_EFFECTIVE_RUN_ONCE% >> "%H_TASK_LOG%"
echo [%date% %time%] H-cycle launcher policy H_EXIT_ON_WARN=%H_EXIT_ON_WARN% >> "%H_TASK_LOG%"
set "PYTHONUNBUFFERED=1"
if /I "%H_CONTROLLED_MODE_ACTIVE%"=="1" if /I not "%H_USE_GUARD_WRAPPER%"=="1" if /I not "%H_CONTROLLED_ALLOW_CORE%"=="1" (
  set "H_USE_GUARD_WRAPPER=1"
  echo [%date% %time%] H-cycle launcher controlled_mode_guard_override forced_guard=1 raw=%H_USE_GUARD_WRAPPER_RAW% >> "%H_TASK_LOG%"
)
set "H_ALLOW_DIRECT_WORKER_START_RAW=%H_ALLOW_DIRECT_WORKER_START%"
if not defined H_ALLOW_DIRECT_WORKER_START_RAW set "H_ALLOW_DIRECT_WORKER_START_RAW=0"
set "H_ALLOW_DIRECT_WORKER_START_RAW=%H_ALLOW_DIRECT_WORKER_START_RAW:"=%"
set "H_ALLOW_DIRECT_WORKER_START_RAW=%H_ALLOW_DIRECT_WORKER_START_RAW: =%"
set "H_ALLOW_DIRECT_WORKER_START=0"
if /I "%H_ALLOW_DIRECT_WORKER_START_RAW%"=="1" set "H_ALLOW_DIRECT_WORKER_START=1"
if /I "%H_ALLOW_DIRECT_WORKER_START_RAW%"=="true" set "H_ALLOW_DIRECT_WORKER_START=1"
if /I "%H_ALLOW_DIRECT_WORKER_START_RAW%"=="yes" set "H_ALLOW_DIRECT_WORKER_START=1"
if /I "%H_ALLOW_DIRECT_WORKER_START_RAW%"=="on" set "H_ALLOW_DIRECT_WORKER_START=1"
set "H_SUPERVISOR_PATH=core"
if /I "%H_USE_GUARD_WRAPPER%"=="1" set "H_SUPERVISOR_PATH=guard"
echo [%date% %time%] H-cycle supervisor path=%H_SUPERVISOR_PATH% restart_on_exit=%H_EFFECTIVE_RESTART_ON_EXIT% >> "%H_TASK_LOG%"
set "H_CHILD_START_EPOCH=0"
for /f "delims=" %%S in ('powershell -NoProfile -WindowStyle Hidden -Command "[DateTimeOffset]::UtcNow.ToUnixTimeSeconds()" 2^>nul') do set "H_CHILD_START_EPOCH=%%S"
set "LOOP_RC="
set "H_LAUNCH_EXEC_PATH=blocked"
if /I "%H_SUPERVISOR_PATH%"=="guard" set "H_LAUNCH_EXEC_PATH=guard"
if /I not "%H_SUPERVISOR_PATH%"=="guard" if /I "%H_ALLOW_DIRECT_WORKER_START%"=="1" set "H_LAUNCH_EXEC_PATH=direct"
echo [%date% %time%] H-cycle launch dispatch path=%H_LAUNCH_EXEC_PATH% use_guard=%H_USE_GUARD_WRAPPER% allow_direct=%H_ALLOW_DIRECT_WORKER_START% >> "%H_TASK_LOG%"
if /I "%H_LAUNCH_EXEC_PATH%"=="guard" goto h_launch_guard
if /I "%H_LAUNCH_EXEC_PATH%"=="direct" goto h_launch_direct
goto h_launch_blocked

:h_launch_guard
"%PY%" -u "%ROOT%\scripts\cycles\run_H_pricing_cycle_guarded.py" --phase1-pilot --phase1-config "%CFG%" --sleep-minutes 0 %EXTRA_ARGS% >> "%H_TASK_LOG%" 2>&1
set "LOOP_RC=%ERRORLEVEL%"
goto h_launch_done

:h_launch_direct
echo [%date% %time%] H-cycle launcher direct_core_override allowed=1 (manual override) >> "%H_TASK_LOG%"
"%PY%" -u "%ROOT%\scripts\cycles\run_H_pricing_cycle.py" --phase1-pilot --phase1-config "%CFG%" --sleep-minutes 0 %EXTRA_ARGS% >> "%H_TASK_LOG%" 2>&1
set "LOOP_RC=%ERRORLEVEL%"
goto h_launch_done

:h_launch_blocked
echo [%date% %time%] H-cycle launcher direct_core_blocked use_guard_wrapper=0 allow_direct=0 >> "%H_TASK_LOG%"
set "LOOP_RC=98"
goto h_launch_done

:h_launch_done
echo [%date% %time%] H-cycle launcher postchild checkpoint=after_python >> "%H_TASK_LOG%"
if not defined LOOP_RC set "LOOP_RC=%ERRORLEVEL%"
set "H_HEARTBEAT=%H_LIVE%\H_pricing_cycle.HEARTBEAT.txt"
set "H_EXIT_STATUS=%H_LIVE%\H_pricing_cycle.EXIT_STATUS.txt"
if "%LOOP_RC%"=="0" if /I "%H_SUPERVISOR_PATH%"=="guard" if exist "%H_EXIT_STATUS%" (
  findstr /C:"NO_PUBLISH_TERMINAL_OK" "%H_EXIT_STATUS%" >nul 2>&1
  if not errorlevel 1 (
    echo [%date% %time%] H-cycle launcher NO_PUBLISH_TERMINAL_OK blocked reason=terminal_success_requires_same_run_publish_proof >> "%H_TASK_LOG%"
    set "LOOP_RC=97"
  )
)
set "H_CHILD_END_EPOCH=%H_CHILD_START_EPOCH%"
for /f "delims=" %%S in ('powershell -NoProfile -WindowStyle Hidden -Command "[DateTimeOffset]::UtcNow.ToUnixTimeSeconds()" 2^>nul') do set "H_CHILD_END_EPOCH=%%S"
set /a H_CHILD_RUNTIME_SECONDS=H_CHILD_END_EPOCH-H_CHILD_START_EPOCH
if %H_CHILD_RUNTIME_SECONDS% LSS 0 set "H_CHILD_RUNTIME_SECONDS=0"
echo [%date% %time%] H-cycle child exit raw_rc=%LOOP_RC% >> "%H_TASK_LOG%"

REM --- Validate publish marker against child-written run id ---
REM --- Fail-closed: launcher must not self-heal finalized markers ---
if "%LOOP_RC%"=="0" (
  echo [%date% %time%] H-cycle launcher finalizer_self_heal disabled policy=core_owned_terminal_truth >> "%H_TASK_LOG%"
)
echo [%date% %time%] H-cycle launcher postchild checkpoint=before_finalizer_check rc=%LOOP_RC% >> "%H_TASK_LOG%"
if "%LOOP_RC%"=="0" (
  powershell -NoProfile -WindowStyle Hidden -Command "$cur='';$fin='';$decision='';$source='';$runStateUsable=$false;$rsRun='';$rsState='';$rsPublish='';if(Test-Path '%H_CURRENT_RUN_FILE%'){$cur=(Get-Content '%H_CURRENT_RUN_FILE%' -Raw).Trim()};if(Test-Path '%H_FINALIZED_RUN_FILE%'){$fin=(Get-Content '%H_FINALIZED_RUN_FILE%' -Raw).Trim()};if($cur -and (Test-Path '%H_RUN_STATE_FILE%')){try{$rs=Get-Content '%H_RUN_STATE_FILE%' -Raw | ConvertFrom-Json;$rsRun=[string]$rs.run_id;$rsState=([string]$rs.state).Trim().ToLowerInvariant();$rsPublish=([string]$rs.publish_status).Trim().ToLowerInvariant();if($rsRun -and $rsState){$runStateUsable=$true}}catch{Write-Output ('lifecycle_source name=finalizer source=marker_fallback reason=run_state_unreadable path=%H_RUN_STATE_FILE% error=' + $_.Exception.GetType().Name)}};if(-not $cur){$decision='allow_missing_current';$source='current_marker'}elseif($runStateUsable){$source='h_run_state_json';if($rsRun -ne $cur){$decision='fail_run_state_run_mismatch'}elseif($rsState -eq 'finalized'){$decision='pass_run_state'}elseif($rsState -eq 'publish_done' -and $fin -and $fin -eq $cur){$decision='pass_finalized_marker_after_publish_done'}elseif($rsState -eq 'failed'){$decision='fail_run_state_failed'}else{$decision='fail_run_state_not_finalized'}}else{$source='marker_fallback';if(-not $fin){$decision='fail_missing_finalized'}elseif($cur -ne $fin){$decision='fail_mismatch'}else{$decision='pass_marker'}};Write-Output ('finalizer_check source=' + $source + ' decision=' + $decision + ' current=' + $cur + ' finalized=' + $fin + ' run_state_path=%H_RUN_STATE_FILE% run_state_run_id=' + $rsRun + ' run_state_state=' + $rsState + ' run_state_publish_status=' + $rsPublish);if($decision -like 'fail*'){exit 3};exit 0" >> "%H_TASK_LOG%"
  if errorlevel 3 set "LOOP_RC=3"
  if errorlevel 1 if not errorlevel 3 set "LOOP_RC=1"
)
echo [%date% %time%] H-cycle launcher postchild checkpoint=after_finalizer_check rc=%LOOP_RC% >> "%H_TASK_LOG%"

echo [%date% %time%] H-cycle launcher postchild checkpoint=before_publish_marker_check rc=%LOOP_RC% >> "%H_TASK_LOG%"
if "%LOOP_RC%"=="0" if /I "%H_STAGE_PHASE1_PUBLISH%"=="1" (
  powershell -NoProfile -WindowStyle Hidden -Command "$timeout=15;$start=Get-Date;$matched=$false;while(((Get-Date)-$start).TotalSeconds -lt $timeout){if((Test-Path '%H_CURRENT_RUN_FILE%') -and (Test-Path '%H_PUBLISH_RUN_FILE%')){$cur=(Get-Content '%H_CURRENT_RUN_FILE%' -Raw).Trim();$pub=(Get-Content '%H_PUBLISH_RUN_FILE%' -Raw).Trim();if($cur -and $pub -and $cur -eq $pub){$matched=$true;break}};Start-Sleep -Milliseconds 500};$curExists=(Test-Path '%H_CURRENT_RUN_FILE%');$markerExists=(Test-Path '%H_PUBLISH_RUN_FILE%');$cur='';$marker='';$markerDecision='';if($curExists){$cur=(Get-Content '%H_CURRENT_RUN_FILE%' -Raw).Trim()};if($markerExists){$marker=(Get-Content '%H_PUBLISH_RUN_FILE%' -Raw).Trim()};if($matched){$markerDecision='pass'}elseif(-not $curExists -or -not $markerExists){$markerDecision='allow_missing'}elseif(-not $cur -or -not $marker){$markerDecision='allow_empty'}elseif($cur -ne $marker){$markerDecision='fail_mismatch'}else{$markerDecision='allow_unknown'};$decision=$markerDecision;$source='marker_fallback';$rsRun='';$rsState='';$rsPublish='';if($cur -and (Test-Path '%H_RUN_STATE_FILE%')){try{$rs=Get-Content '%H_RUN_STATE_FILE%' -Raw | ConvertFrom-Json;$rsRun=[string]$rs.run_id;$rsState=([string]$rs.state).Trim().ToLowerInvariant();$rsPublish=([string]$rs.publish_status).Trim().ToLowerInvariant();if($rsRun -and $rsState){$source='h_run_state_json';if($rsRun -ne $cur){$decision='fail_run_state_run_mismatch'}elseif($rsState -eq 'failed'){$decision='fail_run_state_failed'}elseif(@('publish_done','finalized') -contains $rsState){$decision='pass_run_state'}else{$decision='fail_run_state_not_published'}}}catch{Write-Output ('lifecycle_source name=publish source=marker_fallback reason=run_state_unreadable path=%H_RUN_STATE_FILE% error=' + $_.Exception.GetType().Name)}};Write-Output ('lifecycle_check name=publish source=' + $source + ' decision=' + $decision + ' marker_decision=' + $markerDecision + ' current=' + $cur + ' marker=' + $marker + ' run_state_path=%H_RUN_STATE_FILE% run_state_run_id=' + $rsRun + ' run_state_state=' + $rsState + ' run_state_publish_status=' + $rsPublish);if($decision -like 'fail*'){exit 97};if('%H_MARKER_CHECK_STRICT%' -eq '1' -and $decision -notlike 'pass*'){exit 97};exit 0" >> "%H_TASK_LOG%"
  if errorlevel 97 set "LOOP_RC=97"
  if errorlevel 1 if not errorlevel 97 set "LOOP_RC=1"
)
echo [%date% %time%] H-cycle launcher postchild checkpoint=after_publish_marker_check rc=%LOOP_RC% >> "%H_TASK_LOG%"
echo [%date% %time%] H-cycle launcher postchild checkpoint=before_completed_marker_check rc=%LOOP_RC% >> "%H_TASK_LOG%"
set "H_COMPLETED_MARKER_STRICT=%H_MARKER_CHECK_STRICT%"
if /I "%H_GATING_MODE%"=="1" set "H_COMPLETED_MARKER_STRICT=0"
if "%LOOP_RC%"=="0" (
  powershell -NoProfile -WindowStyle Hidden -Command "$timeout=15;$start=Get-Date;$matched=$false;while(((Get-Date)-$start).TotalSeconds -lt $timeout){if((Test-Path '%H_CURRENT_RUN_FILE%') -and (Test-Path '%H_COMPLETED_RUN_FILE%')){$cur=(Get-Content '%H_CURRENT_RUN_FILE%' -Raw).Trim();$done=(Get-Content '%H_COMPLETED_RUN_FILE%' -Raw).Trim();if($cur -and $done -and $cur -eq $done){$matched=$true;break}};Start-Sleep -Milliseconds 500};$curExists=(Test-Path '%H_CURRENT_RUN_FILE%');$markerExists=(Test-Path '%H_COMPLETED_RUN_FILE%');$cur='';$marker='';$markerDecision='';if($curExists){$cur=(Get-Content '%H_CURRENT_RUN_FILE%' -Raw).Trim()};if($markerExists){$marker=(Get-Content '%H_COMPLETED_RUN_FILE%' -Raw).Trim()};if($matched){$markerDecision='pass'}elseif(-not $curExists -or -not $markerExists){$markerDecision='allow_missing'}elseif(-not $cur -or -not $marker){$markerDecision='allow_empty'}elseif($cur -ne $marker){$markerDecision='fail_mismatch'}else{$markerDecision='allow_unknown'};$decision=$markerDecision;$source='marker_fallback';$rsRun='';$rsState='';$rsPublish='';if($cur -and (Test-Path '%H_RUN_STATE_FILE%')){try{$rs=Get-Content '%H_RUN_STATE_FILE%' -Raw | ConvertFrom-Json;$rsRun=[string]$rs.run_id;$rsState=([string]$rs.state).Trim().ToLowerInvariant();$rsPublish=([string]$rs.publish_status).Trim().ToLowerInvariant();if($rsRun -and $rsState){$source='h_run_state_json';if($rsRun -ne $cur){$decision='fail_run_state_run_mismatch'}elseif($rsState -eq 'finalized'){$decision='pass_run_state'}elseif($rsState -eq 'failed'){$decision='fail_run_state_failed'}else{$decision='fail_run_state_not_finalized'}}}catch{Write-Output ('lifecycle_source name=completed source=marker_fallback reason=run_state_unreadable path=%H_RUN_STATE_FILE% error=' + $_.Exception.GetType().Name)}};Write-Output ('lifecycle_check name=completed source=' + $source + ' decision=' + $decision + ' marker_decision=' + $markerDecision + ' current=' + $cur + ' marker=' + $marker + ' run_state_path=%H_RUN_STATE_FILE% run_state_run_id=' + $rsRun + ' run_state_state=' + $rsState + ' run_state_publish_status=' + $rsPublish);if('%H_GATING_MODE%' -eq '1' -and $decision -notlike 'pass*'){Write-Output 'lifecycle_check name=completed gating_mode_non_strict=1 action=informational_only';exit 0};if($decision -like 'fail*'){exit 97};if('%H_COMPLETED_MARKER_STRICT%' -eq '1' -and $decision -notlike 'pass*'){exit 97};exit 0" >> "%H_TASK_LOG%"
  if errorlevel 97 set "LOOP_RC=97"
  if errorlevel 1 if not errorlevel 97 set "LOOP_RC=1"
)
echo [%date% %time%] H-cycle launcher postchild checkpoint=after_completed_marker_check rc=%LOOP_RC% >> "%H_TASK_LOG%"
echo [%date% %time%] H-cycle launcher postchild checkpoint=before_heartbeat_check rc=%LOOP_RC% >> "%H_TASK_LOG%"
if "%LOOP_RC%"=="0" if /I "%H_SUPERVISOR_PATH%"=="guard" (
  findstr /C:"EXIT_OK" /C:"SYSTEMEXIT" /C:"EXIT_CRASH" /C:"OS_EXIT" /C:"SIGNAL" "%H_HEARTBEAT%" >nul 2>&1
  if errorlevel 1 (
    findstr /C:"EXIT_OK" /C:"SYSTEMEXIT" /C:"EXIT_CRASH" /C:"OS_EXIT" /C:"SIGNAL" "%H_EXIT_STATUS%" >nul 2>&1
    if errorlevel 1 (
      set "LOOP_RC=98"
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
echo [%date% %time%] H-cycle launcher postchild checkpoint=after_heartbeat_check rc=%LOOP_RC% >> "%H_TASK_LOG%"
powershell -NoProfile -WindowStyle Hidden -Command "$payload=('launcher_pid=%H_LAUNCHER_SELF_PID%|utc=' + (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ') + '|state=postchild|rc=%LOOP_RC%|restart_owner=launcher_loop|owner_role=%H_RESTART_OWNER_ROLE%'); [System.IO.File]::WriteAllText('%H_LAUNCHER_HEARTBEAT_FILE%',$payload + [Environment]::NewLine,[System.Text.Encoding]::ASCII)" >nul 2>&1
set "H_INTERRUPTION_CLASS_FLAG=0"
set "H_INTERRUPTION_SIGNAL="
set "H_INTERRUPTION_EXIT_CATEGORY=none"
for /f "tokens=1,* delims==" %%A in ('powershell -NoProfile -WindowStyle Hidden -Command "$rc=0;try{$rc=[int]('%LOOP_RC%')}catch{$rc=1};$text='';$paths=@('%H_EXIT_STATUS%','%H_HEARTBEAT%');foreach($p in $paths){if(Test-Path $p){try{$text+=[Environment]::NewLine + (Get-Content $p -Raw)}catch{}}};$textLow=$text.ToLowerInvariant();$isInterruption=$false;$signal='';$exitCategory='none';if($text -match 'signum=(SIG[A-Z0-9]+)'){$signal=[string]$Matches[1];$isInterruption=$true;$exitCategory='signal_marker'};if($textLow -match 'interruption_class=(true|1)'){$isInterruption=$true;if($exitCategory -eq 'none'){$exitCategory='runtime_marker'}};if($textLow -match 'wrapper_exit_category=([a-z0-9_\-\.]+)' -and $exitCategory -eq 'none'){$exitCategory=[string]$Matches[1]};if($textLow -match 'exit_category=([a-z0-9_\-\.]+)' -and $exitCategory -eq 'none'){$exitCategory=[string]$Matches[1]};if($rc -eq 130){$isInterruption=$true;if(-not $signal){$signal='SIGINT'};$exitCategory='keyboard_interrupt_rc130'};if(($rc -eq 3 -or $rc -eq 2) -and ($textLow -match 'external_interruption' -or $textLow -match 'signal_handler:' -or $textLow -match 'process_exit reason=keyboard_interrupt' -or $textLow -match 'parent_owner_lost')){$isInterruption=$true;if($exitCategory -eq 'none'){$exitCategory='external_interruption_evidence'}};Write-Output ('H_INTERRUPTION_CLASS_FLAG=' + ($(if($isInterruption){'1'}else{'0'})));Write-Output ('H_INTERRUPTION_SIGNAL=' + $signal);Write-Output ('H_INTERRUPTION_EXIT_CATEGORY=' + $exitCategory)"') do set "%%A=%%B"
echo [%date% %time%] H-cycle interruption_evidence_written class=%H_INTERRUPTION_CLASS_FLAG% signal=%H_INTERRUPTION_SIGNAL% exit_category=%H_INTERRUPTION_EXIT_CATEGORY% rc=%LOOP_RC% >> "%H_TASK_LOG%"
if "%H_INTERRUPTION_CLASS_FLAG%"=="1" if not "%H_LAST_INTERRUPTION_CLASS%"=="1" (
  echo [%date% %time%] H-cycle interruption_class_detected signal=%H_INTERRUPTION_SIGNAL% exit_category=%H_INTERRUPTION_EXIT_CATEGORY% rc=%LOOP_RC% >> "%H_TASK_LOG%"
)
if not "%H_INTERRUPTION_CLASS_FLAG%"=="1" if "%H_LAST_INTERRUPTION_CLASS%"=="1" (
  echo [%date% %time%] H-cycle interruption_class_cleared rc=%LOOP_RC% >> "%H_TASK_LOG%"
)
set "H_LAST_INTERRUPTION_CLASS=%H_INTERRUPTION_CLASS_FLAG%"
if "%LOOP_RC%"=="" (
  set "LOOP_RC=1"
  echo [%date% %time%] H-cycle launcher normalized blank rc to 1 >> "%H_TASK_LOG%"
)
if not "%LOOP_RC%"=="0" (
  powershell -NoProfile -WindowStyle Hidden -Command "$cur='';if(Test-Path '%H_CURRENT_RUN_FILE%'){$cur=(Get-Content '%H_CURRENT_RUN_FILE%' -Raw).Trim()};$rc='%LOOP_RC%';$archiveDir='%ROOT%\out\locks\archive';New-Item -ItemType Directory -Force -Path $archiveDir | Out-Null;$paths=@('%H_CYCLE_LOCK_PATH%','%H_ROOT_LOCK_PATH%');foreach($path in $paths){if(-not (Test-Path $path)){continue};$line=(Get-Content $path -Raw).Trim();$lockRun='';$lockPid=$null;if($line -match 'run_id=([^|\\s]+)'){$lockRun=$Matches[1].Trim()};if($line -match 'pid=(\\d+)'){try{$lockPid=[int]$Matches[1]}catch{$lockPid=$null}};if($cur -and $lockRun -and $lockRun -ne $cur){Write-Output ('lock_cleanup_skip path=' + $path + ' reason=run_id_mismatch current=' + $cur + ' lock_run_id=' + $lockRun);continue};$alive=$false;if($lockPid){try{$proc=Get-Process -Id $lockPid -ErrorAction SilentlyContinue;if($proc){$alive=$true}}catch{}};if($alive){Write-Output ('lock_cleanup_skip path=' + $path + ' reason=pid_alive pid=' + $lockPid);continue};$runPart='unknown';if($lockRun){$runPart=$lockRun}elseif($cur){$runPart=$cur};$stamp=(Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ');$archive=Join-Path $archiveDir ('H.lock.' + $stamp + '.' + $runPart + '.rc' + $rc + '.launcher');$n=1;while(Test-Path $archive){$n=$n+1;$archive=Join-Path $archiveDir ('H.lock.' + $stamp + '.' + $runPart + '.rc' + $rc + '.launcher.' + $n)};Move-Item -Path $path -Destination $archive -Force -ErrorAction SilentlyContinue;if(Test-Path $path){Remove-Item -Path $path -Force -ErrorAction SilentlyContinue};if(Test-Path $path){Write-Output ('lock_cleanup_failed path=' + $path + ' run_id=' + $runPart + ' rc=' + $rc)}else{Write-Output ('lock_cleanup_archived path=' + $path + ' archive=' + $archive + ' run_id=' + $runPart + ' rc=' + $rc)}};" >> "%H_TASK_LOG%" 2>&1
  powershell -NoProfile -WindowStyle Hidden -Command "$runPath='%H_RUN_IN_PROGRESS_FILE%';$currentPath='%H_CURRENT_RUN_FILE%';$finPath='%H_FINALIZED_RUN_FILE%';$run='';$current='';$fin='';if(Test-Path $runPath){$run=(Get-Content $runPath -Raw).Trim()};if(Test-Path $currentPath){$current=(Get-Content $currentPath -Raw).Trim()};if(Test-Path $finPath){$fin=(Get-Content $finPath -Raw).Trim()};if(-not $run){Write-Output 'run_in_progress_cleanup_skip reason=missing_marker mode=core_owned_truth_no_launcher_mutation';exit 0};if($run -eq $fin){Write-Output ('run_in_progress_cleanup_skip reason=already_finalized run_id=' + $run + ' finalized=' + $fin + ' mode=core_owned_truth_no_launcher_mutation');exit 0};if($current -and $run -ne $current){Write-Output ('run_in_progress_cleanup_skip reason=run_id_mismatch marker=' + $run + ' current=' + $current + ' mode=core_owned_truth_no_launcher_mutation');exit 0};Write-Output ('run_in_progress_cleanup_skip reason=core_owned_truth_no_launcher_mutation run_id=' + $run + ' finalized=' + $fin + ' rc=%LOOP_RC%')" >> "%H_TASK_LOG%" 2>&1
)
echo [%date% %time%] H-cycle loop finished (exit %LOOP_RC%) >> "%H_TASK_LOG%"
"%PY%" -u "%ROOT%\scripts\tools\h_session_tally.py" update --rc %LOOP_RC% --run_id_file "%H_LIVE%\H_cycle_current_run_id.txt" >> "%H_TASK_LOG%" 2>&1
if not "%LOOP_RC%"=="0" (
  if /I "%H_KILL_ORPHAN_H110_ON_FAILURE%"=="1" (
    powershell -NoProfile -WindowStyle Hidden -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*H110_run_phase1_h_pilot.py*' -and $_.CommandLine -like '*SellerOne 2.0*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >> "%H_TASK_LOG%" 2>&1
    echo [%date% %time%] H-cycle launcher orphan_h110_cleanup executed rc=%LOOP_RC% >> "%H_TASK_LOG%"
  ) else (
    echo [%date% %time%] H-cycle launcher orphan_h110_cleanup skipped rc=%LOOP_RC% policy=opt_in env_H_KILL_ORPHAN_H110_ON_FAILURE=%H_KILL_ORPHAN_H110_ON_FAILURE% >> "%H_TASK_LOG%"
  )
)
set "H_RUN_CLASS=normal"
set "H_SHORT_FAILURE_FLAG=0"
set /a H_SHORT_FAILURE_GAP_SECONDS=H_CHILD_END_EPOCH-H_LAST_SHORT_FAILURE_EPOCH
if "%H_INTERRUPTION_CLASS_FLAG%"=="1" (
  set "H_RUN_CLASS=interruption_class"
) else (
  if not "%LOOP_RC%"=="0" (
    if %H_CHILD_RUNTIME_SECONDS% LEQ %H_SHORT_FAILURE_SECONDS% (
      set "H_RUN_CLASS=short_failure"
      set "H_SHORT_FAILURE_FLAG=1"
    ) else (
      set "H_RUN_CLASS=normal_failure"
    )
  ) else (
    if %H_CHILD_RUNTIME_SECONDS% GEQ %H_HEALTHY_RESET_MIN_SECONDS% (
      set "H_RUN_CLASS=healthy_run"
    ) else (
      set "H_RUN_CLASS=short_success"
    )
  )
)
if "%H_INTERRUPTION_CLASS_FLAG%"=="1" (
  if %H_SHORT_FAILURE_STREAK% GTR 0 set /a H_SHORT_FAILURE_STREAK-=1
  set "H_LAST_SHORT_FAILURE_EPOCH=0"
) else (
  if "%H_SHORT_FAILURE_FLAG%"=="1" (
    if %H_LAST_SHORT_FAILURE_EPOCH% EQU 0 (
      set "H_SHORT_FAILURE_STREAK=1"
    ) else (
      if %H_SHORT_FAILURE_GAP_SECONDS% LEQ %H_SHORT_FAILURE_WINDOW_SECONDS% (
        set /a H_SHORT_FAILURE_STREAK+=1
      ) else (
        set "H_SHORT_FAILURE_STREAK=1"
      )
    )
    set /a H_LAST_SHORT_FAILURE_EPOCH=H_CHILD_END_EPOCH
  ) else (
    if "%LOOP_RC%"=="0" (
      if %H_CHILD_RUNTIME_SECONDS% GEQ %H_HEALTHY_RESET_MIN_SECONDS% (
        if %H_SHORT_FAILURE_STREAK% GTR 0 (
          echo [%date% %time%] H-cycle cooldown reset after healthy run runtime_seconds=%H_CHILD_RUNTIME_SECONDS% prior_short_failure_streak=%H_SHORT_FAILURE_STREAK% >> "%H_TASK_LOG%"
        )
        set "H_SHORT_FAILURE_STREAK=0"
        set "H_LAST_SHORT_FAILURE_EPOCH=0"
      ) else (
        if %H_SHORT_FAILURE_STREAK% GTR 0 set /a H_SHORT_FAILURE_STREAK-=1
      )
    ) else (
      if %H_SHORT_FAILURE_STREAK% GTR 0 set /a H_SHORT_FAILURE_STREAK-=1
    )
  )
)
if %H_SHORT_FAILURE_STREAK% LSS 0 set "H_SHORT_FAILURE_STREAK=0"
set "H_COOLDOWN_TIER=0"
if %H_SHORT_FAILURE_STREAK% GTR 1 set /a H_COOLDOWN_TIER=H_SHORT_FAILURE_STREAK-1
if %H_COOLDOWN_TIER% GTR %H_MAX_COOLDOWN_TIER% set /a H_COOLDOWN_TIER=H_MAX_COOLDOWN_TIER
set "H_COOLDOWN_SECONDS=10"
if %H_COOLDOWN_TIER% EQU 1 set "H_COOLDOWN_SECONDS=20"
if %H_COOLDOWN_TIER% EQU 2 set "H_COOLDOWN_SECONDS=45"
if %H_COOLDOWN_TIER% EQU 3 set "H_COOLDOWN_SECONDS=90"
if %H_COOLDOWN_TIER% GEQ 4 set "H_COOLDOWN_SECONDS=180"
if "%H_INTERRUPTION_CLASS_FLAG%"=="1" if %H_INTERRUPTION_RECOVERY_SECONDS% GTR %H_COOLDOWN_SECONDS% set "H_COOLDOWN_SECONDS=%H_INTERRUPTION_RECOVERY_SECONDS%"
if "%H_INTERRUPTION_CLASS_FLAG%"=="1" echo [%date% %time%] H-cycle interruption_recovery_delay seconds=%H_COOLDOWN_SECONDS% signal=%H_INTERRUPTION_SIGNAL% exit_category=%H_INTERRUPTION_EXIT_CATEGORY% >> "%H_TASK_LOG%"
echo [%date% %time%] H-cycle run_classification class=%H_RUN_CLASS% rc=%LOOP_RC% runtime_seconds=%H_CHILD_RUNTIME_SECONDS% short_failure_threshold_seconds=%H_SHORT_FAILURE_SECONDS% short_failure_streak=%H_SHORT_FAILURE_STREAK% cooldown_tier=%H_COOLDOWN_TIER% interruption_class=%H_INTERRUPTION_CLASS_FLAG% interruption_signal=%H_INTERRUPTION_SIGNAL% interruption_exit_category=%H_INTERRUPTION_EXIT_CATEGORY% >> "%H_TASK_LOG%"
set "H_ONESHOT_RECOVERY_RETRY_REASON="
if /I "%H_EFFECTIVE_RUN_ONCE%"=="1" if "%LOOP_RC%"=="3" if "%H_INTERRUPTION_CLASS_FLAG%"=="0" if /I not "%H_CONTROLLED_MODE_ACTIVE%"=="1" (
  if %H_ONESHOT_RECOVERY_RETRY_LIMIT% GTR 0 if %H_ONESHOT_RECOVERY_RETRY_COUNT% LSS %H_ONESHOT_RECOVERY_RETRY_LIMIT% (
    set "H_ONESHOT_RECOVERY_RETRY_REASON=rc3_fail_closed"
    goto oneshot_recovery_retry
  )
)
if /I "%H_EFFECTIVE_RUN_ONCE%"=="1" if "%LOOP_RC%"=="3" if "%H_INTERRUPTION_CLASS_FLAG%"=="0" if /I "%H_CONTROLLED_MODE_ACTIVE%"=="1" (
  echo [%date% %time%] H-cycle launcher one_shot_recovery_retry skipped reason=controlled_mode_single_attempt rc=%LOOP_RC% >> "%H_TASK_LOG%"
)
if /I "%H_EFFECTIVE_RUN_ONCE%"=="1" (
  echo [%date% %time%] H-cycle launcher explicit one_shot exit rc=%LOOP_RC% launch_mode=%H_LAUNCH_MODE% >> "%H_TASK_LOG%"
  endlocal & exit /b %LOOP_RC%
)
if /I not "%H_EFFECTIVE_RESTART_ON_EXIT%"=="1" (
  echo [%date% %time%] H-cycle launcher explicit one_shot exit rc=%LOOP_RC% launch_mode=%H_LAUNCH_MODE% restart_on_exit=%H_EFFECTIVE_RESTART_ON_EXIT% >> "%H_TASK_LOG%"
  endlocal & exit /b %LOOP_RC%
)
set "SLEEP_SECONDS=10"
if "%LOOP_RC%"=="1" if exist "%H_CYCLE_LOCK_PATH%" (
  set "SLEEP_SECONDS=15"
  for /f "delims=" %%S in ('"%PY%" -u "%ROOT%\scripts\tools\h_lock_sleep.py" --lock-path "%H_CYCLE_LOCK_PATH%" 2^>nul') do set "SLEEP_SECONDS=%%S"
)
set "H_BASE_SLEEP_SECONDS=%SLEEP_SECONDS%"
if %H_COOLDOWN_SECONDS% GTR %SLEEP_SECONDS% set "SLEEP_SECONDS=%H_COOLDOWN_SECONDS%"
echo [%date% %time%] H-cycle cooldown_decision class=%H_RUN_CLASS% tier=%H_COOLDOWN_TIER% base_delay_seconds=%H_BASE_SLEEP_SECONDS% cooldown_delay_seconds=%H_COOLDOWN_SECONDS% next_relaunch_delay_seconds=%SLEEP_SECONDS% short_failure_streak=%H_SHORT_FAILURE_STREAK% >> "%H_TASK_LOG%"
echo [%date% %time%] H-cycle launcher continuous relaunch in %SLEEP_SECONDS%s (last exit %LOOP_RC% launch_mode=%H_LAUNCH_MODE%) >> "%H_TASK_LOG%"
timeout /t %SLEEP_SECONDS% /nobreak >nul 2>&1
goto loop

:drain_wait
powershell -NoProfile -WindowStyle Hidden -Command "$payload=('launcher_pid=%H_LAUNCHER_SELF_PID%|utc=' + (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ') + '|state=drain_wait|restart_owner=launcher_loop|owner_role=%H_RESTART_OWNER_ROLE%'); [System.IO.File]::WriteAllText('%H_LAUNCHER_HEARTBEAT_FILE%',$payload + [Environment]::NewLine,[System.Text.Encoding]::ASCII)" >nul 2>&1
if not exist "%MAINT_REQUEST_PATH%" (
  if exist "%H_DRAIN_READY_FILE%" del /f /q "%H_DRAIN_READY_FILE%" >nul 2>&1
  echo [%date% %time%] H-cycle launcher restart_drain cleared - resuming loop >> "%H_TASK_LOG%"
  goto loop
)
timeout /t 15 /nobreak >nul 2>&1
goto drain_wait

:oneshot_recovery_retry
set /a H_ONESHOT_RECOVERY_RETRY_COUNT+=1
echo [%date% %time%] H-cycle launcher one_shot_recovery_retry scheduled reason=%H_ONESHOT_RECOVERY_RETRY_REASON% retry_count=%H_ONESHOT_RECOVERY_RETRY_COUNT% retry_limit=%H_ONESHOT_RECOVERY_RETRY_LIMIT% delay_seconds=%H_ONESHOT_RECOVERY_RETRY_DELAY_SECONDS% rc=%LOOP_RC% >> "%H_TASK_LOG%"
powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds ([int]([double]('%H_ONESHOT_RECOVERY_RETRY_DELAY_SECONDS%')))" >nul 2>&1
goto loop

:rotate_h_task_log
setlocal
if not defined H_TASK_LOG (
  endlocal & exit /b 0
)
if not exist "%H_TASK_LOG%" (
  endlocal & exit /b 0
)
powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%ROOT%\scripts\tools\h_rotate_task_log.ps1" -Path "%H_TASK_LOG%" -RotateMaxMb "%H_TASK_LOG_ROTATE_MAX_MB%" -RotateMaxFiles "%H_TASK_LOG_ROTATE_MAX_FILES%" -RetentionDays "%H_TASK_LOG_RETENTION_DAYS%" -FamilyMaxMb "%H_TASK_LOG_FAMILY_MAX_MB%"
set "ROTATE_RC=%ERRORLEVEL%"
if not "%ROTATE_RC%"=="0" (
  endlocal & exit /b %ROTATE_RC%
)
endlocal & exit /b 0

:normalize_flag
setlocal
set "FLAG_RAW=%~1"
if not defined FLAG_RAW set "FLAG_RAW=0"
setlocal EnableDelayedExpansion
set "FLAG_TRIMMED=!FLAG_RAW!"
set "FLAG_TRIMMED=!FLAG_TRIMMED:"=!"
:normalize_trim_leading
if defined FLAG_TRIMMED if "!FLAG_TRIMMED:~0,1!"==" " (
  set "FLAG_TRIMMED=!FLAG_TRIMMED:~1!"
  goto normalize_trim_leading
)
:normalize_trim_trailing
if defined FLAG_TRIMMED if "!FLAG_TRIMMED:~-1!"==" " (
  set "FLAG_TRIMMED=!FLAG_TRIMMED:~0,-1!"
  goto normalize_trim_trailing
)
if not defined FLAG_TRIMMED set "FLAG_TRIMMED=0"
if /I "!FLAG_TRIMMED!"=="1" (
  set "FLAG_NORMALIZED=1"
) else (
  set "FLAG_NORMALIZED=0"
)
endlocal & endlocal & set "%~2=%FLAG_NORMALIZED%"
exit /b 0





