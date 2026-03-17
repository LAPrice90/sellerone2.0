:: Operational entrypoint - do not bypass; use for all runs.
@echo off
setlocal
set "PY=C:\Users\Luke\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
cd /d "%ROOT%"
set "H_LIVE=%ROOT%\out\systems\H\live"
if not exist "%H_LIVE%" mkdir "%H_LIVE%"
set "H_CONTROLLED_MODE_FLAG=%ROOT%\out\locks\h_controlled_mode.active"
set "PYTHONPATH=%ROOT%;%ROOT%\scripts;%PYTHONPATH%"
if not exist "%ROOT%\out" mkdir "%ROOT%\out"
set "H_TASK_LOG=%H_LIVE%\phase1_pilot_task.log"
if not defined H_RESTART_OWNERSHIP_MODE set "H_RESTART_OWNERSHIP_MODE=launcher"
if /I "%H_RESTART_OWNERSHIP_MODE%"=="" set "H_RESTART_OWNERSHIP_MODE=launcher"
set "H_RESTART_OWNER_ROLE=active_owner"
if /I not "%H_RESTART_OWNERSHIP_MODE%"=="launcher" set "H_RESTART_OWNER_ROLE=observer"
set "H_RUN_ONCE_RAW_INPUT=%H_RUN_ONCE%"
if not defined H_RUN_ONCE_RAW_INPUT set "H_RUN_ONCE_RAW_INPUT=0"
call :normalize_flag "%H_RUN_ONCE_RAW_INPUT%" H_RUN_ONCE_REQUESTED
set "H_CONTROLLED_MODE_ACTIVE=0"
if exist "%H_CONTROLLED_MODE_FLAG%" set "H_CONTROLLED_MODE_ACTIVE=1"
set "H_RUN_ONCE_SOURCE=default_production"
if /I "%H_RUN_ONCE_REQUESTED%"=="1" set "H_RUN_ONCE_SOURCE=explicit_env"
if /I "%H_CONTROLLED_MODE_ACTIVE%"=="1" set "H_RUN_ONCE_SOURCE=controlled_mode"
set "H_EFFECTIVE_RUN_ONCE=%H_RUN_ONCE_REQUESTED%"
if /I "%H_CONTROLLED_MODE_ACTIVE%"=="1" set "H_EFFECTIVE_RUN_ONCE=1"
set "H_LAUNCHER_RESTART_ON_EXIT_RAW_INPUT=%H_LAUNCHER_RESTART_ON_EXIT%"
if not defined H_LAUNCHER_RESTART_ON_EXIT_RAW_INPUT set "H_LAUNCHER_RESTART_ON_EXIT_RAW_INPUT=1"
call :normalize_flag "%H_LAUNCHER_RESTART_ON_EXIT_RAW_INPUT%" H_RESTART_REQUESTED
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
powershell -NoProfile -Command "$ErrorActionPreference='SilentlyContinue';$selfPs=Get-CimInstance Win32_Process -Filter ('ProcessId=' + $PID) -ErrorAction SilentlyContinue;$selfPid=0;if($selfPs){$selfPid=[int]$selfPs.ParentProcessId};$line='set ""H_LAUNCHER_SELF_PID=' + $selfPid + '""';[System.IO.File]::WriteAllText('%H_LAUNCHER_SELF_PID_FILE%',$line + [Environment]::NewLine,[System.Text.Encoding]::ASCII)" >nul 2>&1
if exist "%H_LAUNCHER_SELF_PID_FILE%" call "%H_LAUNCHER_SELF_PID_FILE%"
if exist "%H_LAUNCHER_SELF_PID_FILE%" del /f /q "%H_LAUNCHER_SELF_PID_FILE%" >nul 2>&1
if not defined H_LAUNCHER_SELF_PID set "H_LAUNCHER_SELF_PID=0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\tools\h_launcher_gate.ps1" -Mode gate -Root "%ROOT%" -SelfPid %H_LAUNCHER_SELF_PID% -LockPath "%H_LAUNCHER_LOCK_FILE%" -HeartbeatPath "%H_LAUNCHER_HEARTBEAT_FILE%" -HeartbeatStaleSeconds %H_LAUNCHER_HEARTBEAT_STALE_SECONDS% > "%H_LAUNCHER_GATE_TRACE%" 2>&1
set "EARLY_GATE_RC=%ERRORLEVEL%"
if exist "%H_LAUNCHER_GATE_TRACE%" type "%H_LAUNCHER_GATE_TRACE%" >> "%H_TASK_LOG%" 2>nul
if "%EARLY_GATE_RC%"=="96" (
  echo [run_H_cycle] H launcher already active - refusing concurrent start
  echo [%date% %time%] H-cycle launcher detected active instance, exiting >> "%H_LAUNCHER_GATE_TRACE%"
  endlocal & exit /b 96
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\tools\h_launcher_gate.ps1" -Mode confirm -Root "%ROOT%" -SelfPid %H_LAUNCHER_SELF_PID% -LockPath "%H_LAUNCHER_LOCK_FILE%" -HeartbeatPath "%H_LAUNCHER_HEARTBEAT_FILE%" -HeartbeatStaleSeconds %H_LAUNCHER_HEARTBEAT_STALE_SECONDS% >> "%H_LAUNCHER_GATE_TRACE%" 2>&1
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
    powershell -NoProfile -Command "$path='%%~fL';$now=(Get-Date).ToUniversalTime();$line='';if(Test-Path $path){$line=(Get-Content $path -Raw).Trim()};$lockPid=$null;if($line -match 'pid=(\d+)'){try{$lockPid=[int]$Matches[1]}catch{$lockPid=$null}};$run='';if($line -match 'run_id=([^|\s]+)'){$run=$Matches[1].Trim()};$hb=$null;if($line -match 'heartbeat=([0-9TZ:\-\.]+)'){try{$hb=[datetime]::Parse($Matches[1]).ToUniversalTime()}catch{}};$start=$null;if($line -match 'start=([0-9TZ:\-\.]+)'){try{$start=[datetime]::Parse($Matches[1]).ToUniversalTime()}catch{}};$ts=$hb;if(-not $ts){$ts=$start};$alive=$false;if($lockPid){try{$proc=Get-Process -Id $lockPid -ErrorAction SilentlyContinue;if($proc){$alive=$true}}catch{$alive=$false}};$freshTol=[double]%H_RECONCILE_RUNTIME_STALE_SECONDS%;$holdSeconds=[double]%H_RECONCILE_HOLD_SECONDS%;$launcherFresh=$false;$launcherAge=-1.0;$launcherPath='%H_LAUNCHER_HEARTBEAT_FILE%';if(Test-Path $launcherPath){try{$hbLine=(Get-Content $launcherPath -Raw).Trim();$hbUtc='';if($hbLine -match 'utc=([0-9TZ:\-]+)'){$hbUtc=$Matches[1]};if($hbUtc){$hbTs=[datetime]::Parse($hbUtc).ToUniversalTime();$launcherAge=($now-$hbTs).TotalSeconds;$launcherFresh=($launcherAge -ge 0 -and $launcherAge -le $freshTol)}}catch{}};$runtimeFresh=$false;$runtimeAge=-1.0;$runtimePath=Join-Path '%H_LIVE%' 'H_runtime_status.json';if(Test-Path $runtimePath){try{$runtimeRaw=Get-Content $runtimePath -Raw | ConvertFrom-Json;$runtimeUtc=[string]$runtimeRaw.utc;if($runtimeUtc){$runtimeTs=[datetime]::Parse($runtimeUtc).ToUniversalTime();$runtimeAge=($now-$runtimeTs).TotalSeconds}else{$runtimeAge=($now-(Get-Item $runtimePath).LastWriteTimeUtc).TotalSeconds};$runtimeFresh=($runtimeAge -ge 0 -and $runtimeAge -le $freshTol)}catch{try{$runtimeAge=($now-(Get-Item $runtimePath).LastWriteTimeUtc).TotalSeconds;$runtimeFresh=($runtimeAge -ge 0 -and $runtimeAge -le $freshTol)}catch{}}};$runMarker='';$runMarkerPath=Join-Path '%H_LIVE%' 'H_run_in_progress.txt';if(Test-Path $runMarkerPath){$runMarker=(Get-Content $runMarkerPath -Raw).Trim()};$finalized='';$finalizedPath=Join-Path '%H_LIVE%' 'H_last_finalized_run_id.txt';if(Test-Path $finalizedPath){$finalized=(Get-Content $finalizedPath -Raw).Trim()};$mismatchReasons=@();if($lockPid -and -not $alive){$mismatchReasons+='lock_pid_dead'};if((-not $lockPid) -or ($lockPid -le 0)){$mismatchReasons+='lock_pid_missing'};if(($launcherFresh -or $runtimeFresh) -and (-not $alive)){$mismatchReasons+='fresh_runtime_evidence_present'};if($run -and $runMarker -and $run -eq $runMarker -and $finalized -ne $run){$mismatchReasons+='parent_child_marker_disagree'};$mismatch=($mismatchReasons.Count -gt 0);$age='';if($ts){$age=[math]::Round(($now-$ts).TotalSeconds,2).ToString()};$statePath=Join-Path '%H_LIVE%' ('H_reconcile_lock.' + [IO.Path]::GetFileName($path) + '.json');if($lockPid -and $alive){if(Test-Path $statePath){Remove-Item -Path $statePath -Force -ErrorAction SilentlyContinue;Write-Output ('reconcile_hold_cleared_healthy path=' + $path + ' reason=pid_alive')};Write-Output ('active_lock_detected path=' + $path + ' pid=' + $lockPid + ' run_id=' + $run);exit 96};if($mismatch){$state=$null;if(Test-Path $statePath){try{$state=Get-Content $statePath -Raw | ConvertFrom-Json}catch{$state=$null}};$stateStart=$null;if($state -and $state.started_utc){try{$stateStart=[datetime]::Parse([string]$state.started_utc).ToUniversalTime()}catch{$stateStart=$null}};if(-not $stateStart){$stateObj=@{started_utc=$now.ToString('yyyy-MM-ddTHH:mm:ssZ');path=$path;reasons=($mismatchReasons -join ',');run_id=$run;pid=$lockPid};[System.IO.File]::WriteAllText($statePath,(ConvertTo-Json $stateObj -Depth 6) + [Environment]::NewLine,[System.Text.Encoding]::ASCII);Write-Output ('reconcile_hold_enter path=' + $path + ' hold_seconds=' + $holdSeconds + ' reasons=' + ($mismatchReasons -join ',') + ' launcher_age_seconds=' + [math]::Round($launcherAge,2) + ' runtime_age_seconds=' + [math]::Round($runtimeAge,2));Write-Output ('stale_cleanup_skipped_due_to_reconcile path=' + $path + ' hold_state=enter');exit 94};$holdAge=($now-$stateStart).TotalSeconds;if($holdAge -lt $holdSeconds){$remaining=[math]::Round($holdSeconds-$holdAge,2);Write-Output ('reconcile_hold_active path=' + $path + ' age_seconds=' + [math]::Round($holdAge,2) + ' remaining_seconds=' + $remaining + ' reasons=' + ($mismatchReasons -join ','));Write-Output ('stale_cleanup_skipped_due_to_reconcile path=' + $path + ' hold_state=active');exit 94};Write-Output ('reconcile_hold_expired path=' + $path + ' age_seconds=' + [math]::Round($holdAge,2) + ' reasons=' + ($mismatchReasons -join ','));Remove-Item -Path $statePath -Force -ErrorAction SilentlyContinue;Write-Output ('stale_cleanup_allowed path=' + $path + ' reason=reconcile_expired')}else{if(Test-Path $statePath){Remove-Item -Path $statePath -Force -ErrorAction SilentlyContinue;Write-Output ('reconcile_hold_cleared_healthy path=' + $path + ' reason=evidence_healthy')};Write-Output ('stale_cleanup_allowed path=' + $path + ' reason=no_reconcile_mismatch')};$reason='missing_or_invalid_pid';if($lockPid){$reason='dead_pid'};$archiveDir='%ROOT%\out\locks\archive';New-Item -ItemType Directory -Force -Path $archiveDir | Out-Null;$stamp=(Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ');$archive=Join-Path $archiveDir ('H.lock.' + $stamp);$n=1;while(Test-Path $archive){$n=$n+1;$archive=Join-Path $archiveDir ('H.lock.' + $stamp + '.' + $n)};if(Test-Path $path){Move-Item -Path $path -Destination $archive -Force -ErrorAction SilentlyContinue};Write-Output ('stale_lock_removed path=' + $path + ' archive=' + $archive + ' pid=' + $lockPid + ' run_id=' + $run + ' reason=' + $reason + ' age_seconds=' + $age);exit 95" >> "%H_TASK_LOG%" 2>&1
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
  timeout /t 15 /nobreak >nul
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
REM H110 pilot must run out-of-process so a pilot-only control-flow exit cannot terminate the H parent before publish.
if not defined H_PHASE1_PILOT_MODE set "H_PHASE1_PILOT_MODE=subprocess"
if not defined H_PHASE1_INTEL_MODE set "H_PHASE1_INTEL_MODE=inline"
if not defined H_PHASE1_PUBLISH_MODE set "H_PHASE1_PUBLISH_MODE=inline"
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
set "H_CURRENT_RUN_FILE=%H_LIVE%\H_cycle_current_run_id.txt"
set "H_PUBLISH_RUN_FILE=%H_LIVE%\H_cycle_last_publish_run_id.txt"
set "H_COMPLETED_RUN_FILE=%H_LIVE%\H_cycle_last_completed_run_id.txt"
set "H_FINALIZED_RUN_FILE=%H_LIVE%\H_last_finalized_run_id.txt"
powershell -NoProfile -Command "$payload=('launcher_pid=%H_LAUNCHER_SELF_PID%|utc=' + (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ') + '|state=loop_ready|restart_owner=launcher_loop|owner_role=%H_RESTART_OWNER_ROLE%'); [System.IO.File]::WriteAllText('%H_LAUNCHER_HEARTBEAT_FILE%',$payload + [Environment]::NewLine,[System.Text.Encoding]::ASCII)" >nul 2>&1
echo [%date% %time%] H-cycle restart_ownership owner=launcher_loop role=%H_RESTART_OWNER_ROLE% mode=%H_RESTART_OWNERSHIP_MODE% >> "%H_TASK_LOG%"
set "H_RESTART_DRAIN_REQUESTED=0"
if exist "%MAINT_REQUEST_PATH%" (
  powershell -NoProfile -Command "$text='';try{$text=Get-Content '%MAINT_REQUEST_PATH%' -Raw}catch{};if($text -and $text -match 'requested_by=controlled_restart_gate' -and $text -match 'reason=overnight_restart_eval'){exit 11};exit 0" >nul 2>&1
  if "%ERRORLEVEL%"=="11" set "H_RESTART_DRAIN_REQUESTED=1"
)
if "%H_RESTART_DRAIN_REQUESTED%"=="1" (
  echo [%date% %time%] H-cycle launcher restart_drain requested - waiting at boundary and skipping child launch >> "%H_TASK_LOG%"
  powershell -NoProfile -Command "$now=(Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ');$payload=('H_DRAIN_READY|launcher_pid=%H_LAUNCHER_SELF_PID%|ts=' + $now + '|state=boundary_wait'); [System.IO.File]::WriteAllText('%H_DRAIN_READY_FILE%',$payload + [Environment]::NewLine,[System.Text.Encoding]::ASCII)" >nul 2>&1
  goto drain_wait
)
if exist "%H_DRAIN_READY_FILE%" del /f /q "%H_DRAIN_READY_FILE%" >nul 2>&1
set "BOUNDARY_RELEASE_RC=0"
powershell -NoProfile -Command "$live='%H_LIVE%';$runPath='%H_RUN_IN_PROGRESS_FILE%';$finalizedPath='%H_FINALIZED_RUN_FILE%';$repo=[regex]::Escape('%ROOT%');$threshold=[double]%H_PHASE1_BOUNDARY_STALE_SECONDS%;$now=(Get-Date).ToUniversalTime();$runMarker='';if(Test-Path $runPath){$runMarker=(Get-Content $runPath -Raw).Trim()};$finalized='';if(Test-Path $finalizedPath){$finalized=(Get-Content $finalizedPath -Raw).Trim()};$active=(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match $repo -and ( $_.CommandLine -like '*scripts\\cycles\\run_H_pricing_cycle.py*' -or $_.CommandLine -like '*scripts\\cycles\\run_H_pricing_cycle_guarded.py*' -or $_.CommandLine -like '*scripts\\flows\\H\\H110_run_phase1_h_pilot.py*' ) });if($active){exit 0};$released=0;$files=Get-ChildItem -Path $live -Filter 'phase1_intel_alignment.boundary.*.json' -ErrorAction SilentlyContinue | Sort-Object LastWriteTimeUtc;foreach($file in $files){$raw=$null;try{$raw=Get-Content $file.FullName -Raw | ConvertFrom-Json}catch{continue};if(-not $raw){continue};$statusNorm=[string]$raw.status;$statusNorm=$statusNorm.Trim().ToLower();if(@('stale_or_orphaned','unresolved_parent_exit') -notcontains $statusNorm){continue};$run=[string]$raw.run_id;if(-not $run){continue};if($runMarker -and $runMarker -eq $run){Write-Output ('boundary_release_skipped run_id=' + $run + ' status=' + $statusNorm + ' reason=matching_run_in_progress');continue};$updated=$file.LastWriteTimeUtc;if($raw.updated_utc){try{$updated=[datetime]::Parse([string]$raw.updated_utc).ToUniversalTime()}catch{}};$age=[math]::Round(($now-$updated).TotalSeconds,2);$releaseReason='';$releaseStatus='';if($statusNorm -eq 'stale_or_orphaned'){if($age -lt $threshold){continue};$releaseReason='launcher_gate_no_active_owner_no_matching_run_marker';$releaseStatus='released_stale_orphan'}elseif($statusNorm -eq 'unresolved_parent_exit'){$parentExitCode=[string]$raw.parent_exit_code;$finalizedMatch=($finalized -and $finalized -eq $run);$childPid=0;try{$childPid=[int]$raw.child_pid}catch{$childPid=0};$childAlive=$false;if($childPid -gt 0){try{$proc=Get-Process -Id $childPid -ErrorAction SilentlyContinue;if($proc){$childAlive=$true}}catch{}};$staleTerminalThreshold=[math]::Min($threshold,120);$staleTerminalEligible=(((-not $runMarker) -or ($runMarker -ne $run)) -and (-not $childAlive) -and ($age -ge $staleTerminalThreshold));if($finalizedMatch -or $parentExitCode -eq '0'){$releaseReason='launcher_gate_post_finalize_parent_exit_reconcile';$releaseStatus='released_post_finalize_reconcile'}elseif($staleTerminalEligible){$releaseReason='launcher_gate_stale_terminal_parent_exit_reconcile';$releaseStatus='released_stale_terminal'}else{continue}};if(-not $releaseStatus){continue};$raw.status=$releaseStatus;try{[System.IO.File]::WriteAllText($file.FullName,(ConvertTo-Json $raw -Depth 10) + [Environment]::NewLine,[System.Text.Encoding]::ASCII)}catch{continue};Write-Output ('boundary_released run_id=' + $run + ' from_status=' + $statusNorm + ' to_status=' + $releaseStatus + ' age_seconds=' + $age + ' path=' + $file.FullName + ' run_in_progress=' + $runMarker + ' finalized=' + $finalized + ' release_reason=' + $releaseReason);$released=1};if($released -eq 1){exit 95};exit 0" >> "%H_TASK_LOG%" 2>&1
set "BOUNDARY_RELEASE_RC=%ERRORLEVEL%"
if "%BOUNDARY_RELEASE_RC%"=="95" (
  echo [%date% %time%] H-cycle launcher released stale orphan boundary and continued >> "%H_TASK_LOG%"
)
set "BOUNDARY_GUARD_RC=0"
powershell -NoProfile -Command "$live='%H_LIVE%';$repo=[regex]::Escape('%ROOT%');$threshold=[double]%H_PHASE1_BOUNDARY_STALE_SECONDS%;$now=(Get-Date).ToUniversalTime();$files=Get-ChildItem -Path $live -Filter 'phase1_intel_alignment.boundary.*.json' -ErrorAction SilentlyContinue | Sort-Object LastWriteTimeUtc;foreach($file in $files){$raw=$null;try{$raw=Get-Content $file.FullName -Raw | ConvertFrom-Json}catch{continue};if(-not $raw){continue};$status=[string]($raw.status);$run=[string]($raw.run_id);$childPid=0;try{$childPid=[int]$raw.child_pid}catch{$childPid=0};$updated=$file.LastWriteTimeUtc;if($raw.updated_utc){try{$updated=[datetime]::Parse([string]$raw.updated_utc).ToUniversalTime()}catch{}};$age=[math]::Round(($now-$updated).TotalSeconds,2);$childAlive=$false;if($childPid -gt 0){try{$proc=Get-Process -Id $childPid -ErrorAction SilentlyContinue;if($proc){$childAlive=$true}}catch{}};$statusNorm=$status.Trim().ToLower();$unresolved=@('active','unresolved_parent_exit') -contains $statusNorm;if(-not $unresolved){continue};if((-not $childAlive) -and $statusNorm -ne 'stale_or_orphaned' -and $age -gt $threshold){$raw.status='stale_or_orphaned';$raw.updated_utc=$now.ToString('yyyy-MM-ddTHH:mm:ssZ');try{[System.IO.File]::WriteAllText($file.FullName,(ConvertTo-Json $raw -Depth 10) + [Environment]::NewLine,[System.Text.Encoding]::ASCII)}catch{};$statusNorm='stale_or_orphaned'};$reason='status_only';if($childAlive){$reason='child_alive'}elseif($statusNorm -eq 'unresolved_parent_exit'){$reason='parent_exited_before_resolution'}elseif($statusNorm -eq 'stale_or_orphaned'){$reason='stale_or_orphaned'};Write-Output ('active_phase1_intel_boundary_detected run_id=' + $run + ' status=' + $statusNorm + ' child_pid=' + $childPid + ' child_alive=' + ($childAlive.ToString().ToLower()) + ' age_seconds=' + $age + ' path=' + $file.FullName + ' reason=' + $reason);exit 96};exit 0" >> "%H_TASK_LOG%" 2>&1
set "BOUNDARY_GUARD_RC=%ERRORLEVEL%"
if "%BOUNDARY_GUARD_RC%"=="96" (
  echo [%date% %time%] H-cycle launcher detected unresolved phase1 intel boundary, exiting >> "%H_TASK_LOG%"
  endlocal & exit /b 96
)
if exist "%H_RUN_IN_PROGRESS_FILE%" (
  if not exist "%H_CYCLE_LOCK_PATH%" (
    if not exist "%H_ROOT_LOCK_PATH%" (
      del /f /q "%H_RUN_IN_PROGRESS_FILE%" >nul 2>&1
      echo [%date% %time%] H-cycle launcher stale_run_in_progress_removed_no_locks path="%H_RUN_IN_PROGRESS_FILE%" >> "%H_TASK_LOG%"
    )
  )
)
set "RUN_PROGRESS_RC=0"
powershell -NoProfile -Command "$runPath='%H_RUN_IN_PROGRESS_FILE%';$finPath='%H_FINALIZED_RUN_FILE%';if(-not (Test-Path $runPath)){exit 0};$run=(Get-Content $runPath -Raw).Trim();$fin='';if(Test-Path $finPath){$fin=(Get-Content $finPath -Raw).Trim()};if(-not $run -or $run -eq $fin){exit 0};$boundaryPath=Join-Path '%H_LIVE%' ('phase1_intel_alignment.boundary.' + $run + '.json');$boundaryExists=Test-Path $boundaryPath;$status='';if($boundaryExists){try{$raw=Get-Content $boundaryPath -Raw | ConvertFrom-Json;$status=[string]$raw.status}catch{$status=''}};$resultFiles=@();try{$resultFiles=Get-ChildItem -Path '%H_LIVE%' -Filter ('phase1_intel_alignment.result.' + $run + '.*.json') -ErrorAction SilentlyContinue | Sort-Object LastWriteTimeUtc -Descending}catch{$resultFiles=@()};$resultExists=($resultFiles.Count -gt 0);$resultPath='';if($resultExists){$resultPath=$resultFiles[0].FullName};$archivePath=Join-Path '%H_LIVE%' ('H_failed_run_archived.' + $run + '.json');$archiveExists=Test-Path $archivePath;$archiveValid=$false;if($archiveExists){try{$archiveRaw=Get-Content $archivePath -Raw | ConvertFrom-Json;if([string]$archiveRaw.run_id -eq $run){$archiveValid=$true}}catch{$archiveValid=$false}};$repo=[regex]::Escape('%ROOT%');$active=(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match $repo -and ( $_.CommandLine -like '*scripts\\cycles\\run_H_pricing_cycle.py*' -or $_.CommandLine -like '*scripts\\cycles\\run_H_pricing_cycle_guarded.py*' -or $_.CommandLine -like '*scripts\\flows\\H\\H110_run_phase1_h_pilot.py*' ) });if($boundaryExists -or $resultExists){if($archiveExists -and -not $archiveValid){Write-Output ('active_run_in_progress run_id=' + $run + ' finalized=' + $fin + ' reason=invalid_archive_marker archive_path=' + $archivePath + ' boundary_exists=' + ($boundaryExists.ToString().ToLower()) + ' result_exists=' + ($resultExists.ToString().ToLower()));exit 96};if($archiveValid){if($active){$pids=@($active | ForEach-Object { [string]$_.ProcessId }) -join ',';Write-Output ('active_run_in_progress run_id=' + $run + ' finalized=' + $fin + ' reason=archived_but_python_active archive_path=' + $archivePath + ' pids=' + $pids);exit 96};Remove-Item -Path $runPath -Force -ErrorAction SilentlyContinue;if(Test-Path $runPath){Write-Output ('archived_failed_run_release_failed run_id=' + $run + ' archive_path=' + $archivePath)}else{Write-Output ('archived_failed_run_released run_id=' + $run + ' finalized=' + $fin + ' archive_path=' + $archivePath + ' boundary_exists=' + ($boundaryExists.ToString().ToLower()) + ' boundary_status=' + ($status -replace '\s+','_') + ' result_exists=' + ($resultExists.ToString().ToLower()) + ' result_path=' + $resultPath)};exit 95};$reason='finalization_pending_artifacts';if(@('active','unresolved_parent_exit') -contains $status.Trim().ToLower()){$reason='unresolved_boundary'};Write-Output ('active_run_in_progress run_id=' + $run + ' finalized=' + $fin + ' reason=' + $reason + ' boundary_exists=' + ($boundaryExists.ToString().ToLower()) + ' boundary_status=' + ($status -replace '\s+','_') + ' boundary_path=' + $boundaryPath + ' result_exists=' + ($resultExists.ToString().ToLower()) + ' result_path=' + $resultPath + ' archive_exists=' + ($archiveExists.ToString().ToLower()) + ' archive_path=' + $archivePath);exit 96};$age=0.0;try{$age=((Get-Date).ToUniversalTime()-(Get-Item $runPath).LastWriteTimeUtc).TotalSeconds}catch{};if($active -or $age -le [double]%H_LOCK_STALE_SECONDS%){$pids=@($active | ForEach-Object { [string]$_.ProcessId }) -join ',';Write-Output ('active_run_in_progress run_id=' + $run + ' finalized=' + $fin + ' reason=process_or_recent_marker age_seconds=' + [math]::Round($age,2) + ' pids=' + $pids);exit 96};Remove-Item -Path $runPath -Force -ErrorAction SilentlyContinue;Write-Output ('stale_run_in_progress_removed run_id=' + $run + ' finalized=' + $fin + ' age_seconds=' + [math]::Round($age,2) + ' boundary_exists=false result_exists=false');exit 95" >> "%H_TASK_LOG%" 2>&1
set "RUN_PROGRESS_RC=%ERRORLEVEL%"
if "%RUN_PROGRESS_RC%"=="96" (
  echo [%date% %time%] H-cycle launcher detected active in-progress run, exiting >> "%H_TASK_LOG%"
  endlocal & exit /b 96
)
if "%RUN_PROGRESS_RC%"=="95" (
  echo [%date% %time%] H-cycle launcher stale_run_in_progress_removed and continued >> "%H_TASK_LOG%"
)
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
set "H_SUPERVISOR_PATH=core"
if /I "%H_USE_GUARD_WRAPPER%"=="1" set "H_SUPERVISOR_PATH=guard"
echo [%date% %time%] H-cycle supervisor path=%H_SUPERVISOR_PATH% restart_on_exit=%H_EFFECTIVE_RESTART_ON_EXIT% >> "%H_TASK_LOG%"
set "H_CHILD_START_EPOCH=0"
for /f "delims=" %%S in ('powershell -NoProfile -Command "[DateTimeOffset]::UtcNow.ToUnixTimeSeconds()" 2^>nul') do set "H_CHILD_START_EPOCH=%%S"
if /I "%H_USE_GUARD_WRAPPER%"=="1" (
  "%PY%" -u "%ROOT%\scripts\cycles\run_H_pricing_cycle_guarded.py" --phase1-pilot --phase1-config "%CFG%" --sleep-minutes 0 %EXTRA_ARGS% >> "%H_TASK_LOG%" 2>&1
) else (
  "%PY%" -u "%ROOT%\scripts\cycles\run_H_pricing_cycle.py" --phase1-pilot --phase1-config "%CFG%" --sleep-minutes 0 %EXTRA_ARGS% >> "%H_TASK_LOG%" 2>&1
)
echo [%date% %time%] H-cycle launcher postchild checkpoint=after_python >> "%H_TASK_LOG%"
set "LOOP_RC=%ERRORLEVEL%"
set "H_CHILD_END_EPOCH=%H_CHILD_START_EPOCH%"
for /f "delims=" %%S in ('powershell -NoProfile -Command "[DateTimeOffset]::UtcNow.ToUnixTimeSeconds()" 2^>nul') do set "H_CHILD_END_EPOCH=%%S"
set /a H_CHILD_RUNTIME_SECONDS=H_CHILD_END_EPOCH-H_CHILD_START_EPOCH
if %H_CHILD_RUNTIME_SECONDS% LSS 0 set "H_CHILD_RUNTIME_SECONDS=0"
echo [%date% %time%] H-cycle child exit raw_rc=%LOOP_RC% >> "%H_TASK_LOG%"

REM --- Validate publish marker against child-written run id ---
REM --- Fail-closed: rc=0 is only valid after finalizer confirms this run id ---
if "%LOOP_RC%"=="0" (
  powershell -NoProfile -Command "$cur='';$done='';if(Test-Path '%H_CURRENT_RUN_FILE%'){$cur=(Get-Content '%H_CURRENT_RUN_FILE%' -Raw).Trim()};if(Test-Path '%H_COMPLETED_RUN_FILE%'){$done=(Get-Content '%H_COMPLETED_RUN_FILE%' -Raw).Trim()};if($cur -and $done -and $cur -eq $done){Set-Content -Path '%H_FINALIZED_RUN_FILE%' -Value ($cur + [Environment]::NewLine) -Encoding Ascii;Write-Output ('finalizer_self_heal source=completed_marker current=' + $cur)}" >> "%H_TASK_LOG%"
)
echo [%date% %time%] H-cycle launcher postchild checkpoint=before_finalizer_check rc=%LOOP_RC% >> "%H_TASK_LOG%"
if "%LOOP_RC%"=="0" (
  powershell -NoProfile -Command "$cur='';$fin='';if(Test-Path '%H_CURRENT_RUN_FILE%'){$cur=(Get-Content '%H_CURRENT_RUN_FILE%' -Raw).Trim()};if(Test-Path '%H_FINALIZED_RUN_FILE%'){$fin=(Get-Content '%H_FINALIZED_RUN_FILE%' -Raw).Trim()};if(-not $cur){$decision='allow_missing_current'}elseif(-not $fin){$decision='fail_missing_finalized'}elseif($cur -ne $fin){$decision='fail_mismatch'}else{$decision='pass'};Write-Output ('finalizer_check path=%H_FINALIZED_RUN_FILE% decision=' + $decision + ' current=' + $cur + ' finalized=' + $fin);if($decision -like 'fail*'){exit 3};exit 0" >> "%H_TASK_LOG%"
  if errorlevel 3 set "LOOP_RC=3"
  if errorlevel 1 if not errorlevel 3 set "LOOP_RC=1"
)
echo [%date% %time%] H-cycle launcher postchild checkpoint=after_finalizer_check rc=%LOOP_RC% >> "%H_TASK_LOG%"

echo [%date% %time%] H-cycle launcher postchild checkpoint=before_publish_marker_check rc=%LOOP_RC% >> "%H_TASK_LOG%"
if "%LOOP_RC%"=="0" if /I "%H_STAGE_PHASE1_PUBLISH%"=="1" (
  powershell -NoProfile -Command "$timeout=15;$start=Get-Date;$matched=$false;while(((Get-Date)-$start).TotalSeconds -lt $timeout){if((Test-Path '%H_CURRENT_RUN_FILE%') -and (Test-Path '%H_PUBLISH_RUN_FILE%')){$cur=(Get-Content '%H_CURRENT_RUN_FILE%' -Raw).Trim();$pub=(Get-Content '%H_PUBLISH_RUN_FILE%' -Raw).Trim();if($cur -and $pub -and $cur -eq $pub){$matched=$true;break}};Start-Sleep -Milliseconds 500};$curExists=(Test-Path '%H_CURRENT_RUN_FILE%');$markerExists=(Test-Path '%H_PUBLISH_RUN_FILE%');$cur='';$marker='';if($curExists){$cur=(Get-Content '%H_CURRENT_RUN_FILE%' -Raw).Trim()};if($markerExists){$marker=(Get-Content '%H_PUBLISH_RUN_FILE%' -Raw).Trim()};if($matched){$decision='pass'}elseif(-not $curExists -or -not $markerExists){$decision='allow_missing'}elseif(-not $cur -or -not $marker){$decision='allow_empty'}elseif($cur -ne $marker){$decision='fail_mismatch'}else{$decision='allow_unknown'};Write-Output ('marker_check name=publish path=%H_PUBLISH_RUN_FILE% exists=' + ($markerExists.ToString().ToLower()) + ' decision=' + $decision + ' current=' + $cur + ' marker=' + $marker);if($decision -like 'fail*'){exit 97};if('%H_MARKER_CHECK_STRICT%' -eq '1' -and $decision -ne 'pass'){exit 97};exit 0" >> "%H_TASK_LOG%"
  if errorlevel 97 set "LOOP_RC=97"
  if errorlevel 1 if not errorlevel 97 set "LOOP_RC=1"
)
echo [%date% %time%] H-cycle launcher postchild checkpoint=after_publish_marker_check rc=%LOOP_RC% >> "%H_TASK_LOG%"
echo [%date% %time%] H-cycle launcher postchild checkpoint=before_completed_marker_check rc=%LOOP_RC% >> "%H_TASK_LOG%"
set "H_COMPLETED_MARKER_STRICT=%H_MARKER_CHECK_STRICT%"
if /I "%H_GATING_MODE%"=="1" set "H_COMPLETED_MARKER_STRICT=0"
if "%LOOP_RC%"=="0" (
  powershell -NoProfile -Command "$timeout=15;$start=Get-Date;$matched=$false;while(((Get-Date)-$start).TotalSeconds -lt $timeout){if((Test-Path '%H_CURRENT_RUN_FILE%') -and (Test-Path '%H_COMPLETED_RUN_FILE%')){$cur=(Get-Content '%H_CURRENT_RUN_FILE%' -Raw).Trim();$done=(Get-Content '%H_COMPLETED_RUN_FILE%' -Raw).Trim();if($cur -and $done -and $cur -eq $done){$matched=$true;break}};Start-Sleep -Milliseconds 500};$curExists=(Test-Path '%H_CURRENT_RUN_FILE%');$markerExists=(Test-Path '%H_COMPLETED_RUN_FILE%');$cur='';$marker='';if($curExists){$cur=(Get-Content '%H_CURRENT_RUN_FILE%' -Raw).Trim()};if($markerExists){$marker=(Get-Content '%H_COMPLETED_RUN_FILE%' -Raw).Trim()};if($matched){$decision='pass'}elseif(-not $curExists -or -not $markerExists){$decision='allow_missing'}elseif(-not $cur -or -not $marker){$decision='allow_empty'}elseif($cur -ne $marker){$decision='fail_mismatch'}else{$decision='allow_unknown'};Write-Output ('marker_check name=completed path=%H_COMPLETED_RUN_FILE% exists=' + ($markerExists.ToString().ToLower()) + ' decision=' + $decision + ' current=' + $cur + ' marker=' + $marker);if('%H_GATING_MODE%' -eq '1' -and $decision -ne 'pass'){Write-Output 'marker_check name=completed gating_mode_non_strict=1 action=informational_only';exit 0};if($decision -like 'fail*'){exit 97};if('%H_COMPLETED_MARKER_STRICT%' -eq '1' -and $decision -ne 'pass'){exit 97};exit 0" >> "%H_TASK_LOG%"
  if errorlevel 97 set "LOOP_RC=97"
  if errorlevel 1 if not errorlevel 97 set "LOOP_RC=1"
)
echo [%date% %time%] H-cycle launcher postchild checkpoint=after_completed_marker_check rc=%LOOP_RC% >> "%H_TASK_LOG%"
set "H_HEARTBEAT=%H_LIVE%\H_pricing_cycle.HEARTBEAT.txt"
set "H_EXIT_STATUS=%H_LIVE%\H_pricing_cycle.EXIT_STATUS.txt"
echo [%date% %time%] H-cycle launcher postchild checkpoint=before_heartbeat_check rc=%LOOP_RC% >> "%H_TASK_LOG%"
if "%LOOP_RC%"=="0" if /I "%H_USE_GUARD_WRAPPER%"=="1" (
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
powershell -NoProfile -Command "$payload=('launcher_pid=%H_LAUNCHER_SELF_PID%|utc=' + (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ') + '|state=postchild|rc=%LOOP_RC%|restart_owner=launcher_loop|owner_role=%H_RESTART_OWNER_ROLE%'); [System.IO.File]::WriteAllText('%H_LAUNCHER_HEARTBEAT_FILE%',$payload + [Environment]::NewLine,[System.Text.Encoding]::ASCII)" >nul 2>&1
set "H_INTERRUPTION_CLASS_FLAG=0"
set "H_INTERRUPTION_SIGNAL="
set "H_INTERRUPTION_EXIT_CATEGORY=none"
for /f "tokens=1,* delims==" %%A in ('powershell -NoProfile -Command "$rc=0;try{$rc=[int]('%LOOP_RC%')}catch{$rc=1};$text='';$paths=@('%H_EXIT_STATUS%','%H_HEARTBEAT%');foreach($p in $paths){if(Test-Path $p){try{$text+=[Environment]::NewLine + (Get-Content $p -Raw)}catch{}}};$textLow=$text.ToLowerInvariant();$isInterruption=$false;$signal='';$exitCategory='none';if($text -match 'signum=(SIG[A-Z0-9]+)'){$signal=[string]$Matches[1];$isInterruption=$true;$exitCategory='signal_marker'};if($textLow -match 'interruption_class=(true|1)'){$isInterruption=$true;if($exitCategory -eq 'none'){$exitCategory='runtime_marker'}};if($textLow -match 'wrapper_exit_category=([a-z0-9_\-\.]+)' -and $exitCategory -eq 'none'){$exitCategory=[string]$Matches[1]};if($textLow -match 'exit_category=([a-z0-9_\-\.]+)' -and $exitCategory -eq 'none'){$exitCategory=[string]$Matches[1]};if($rc -eq 130){$isInterruption=$true;if(-not $signal){$signal='SIGINT'};$exitCategory='keyboard_interrupt_rc130'};if(($rc -eq 3 -or $rc -eq 2) -and ($textLow -match 'external_interruption' -or $textLow -match 'signal_handler:' -or $textLow -match 'process_exit reason=keyboard_interrupt' -or $textLow -match 'parent_owner_lost')){$isInterruption=$true;if($exitCategory -eq 'none'){$exitCategory='external_interruption_evidence'}};Write-Output ('H_INTERRUPTION_CLASS_FLAG=' + ($(if($isInterruption){'1'}else{'0'})));Write-Output ('H_INTERRUPTION_SIGNAL=' + $signal);Write-Output ('H_INTERRUPTION_EXIT_CATEGORY=' + $exitCategory)"') do set "%%A=%%B"
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
  powershell -NoProfile -Command "$cur='';if(Test-Path '%H_CURRENT_RUN_FILE%'){$cur=(Get-Content '%H_CURRENT_RUN_FILE%' -Raw).Trim()};$rc='%LOOP_RC%';$archiveDir='%ROOT%\out\locks\archive';New-Item -ItemType Directory -Force -Path $archiveDir | Out-Null;$paths=@('%H_CYCLE_LOCK_PATH%','%H_ROOT_LOCK_PATH%');foreach($path in $paths){if(-not (Test-Path $path)){continue};$line=(Get-Content $path -Raw).Trim();$lockRun='';$lockPid=$null;if($line -match 'run_id=([^|\\s]+)'){$lockRun=$Matches[1].Trim()};if($line -match 'pid=(\\d+)'){try{$lockPid=[int]$Matches[1]}catch{$lockPid=$null}};if($cur -and $lockRun -and $lockRun -ne $cur){Write-Output ('lock_cleanup_skip path=' + $path + ' reason=run_id_mismatch current=' + $cur + ' lock_run_id=' + $lockRun);continue};$alive=$false;if($lockPid){try{$proc=Get-Process -Id $lockPid -ErrorAction SilentlyContinue;if($proc){$alive=$true}}catch{}};if($alive){Write-Output ('lock_cleanup_skip path=' + $path + ' reason=pid_alive pid=' + $lockPid);continue};$runPart='unknown';if($lockRun){$runPart=$lockRun}elseif($cur){$runPart=$cur};$stamp=(Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ');$archive=Join-Path $archiveDir ('H.lock.' + $stamp + '.' + $runPart + '.rc' + $rc + '.launcher');$n=1;while(Test-Path $archive){$n=$n+1;$archive=Join-Path $archiveDir ('H.lock.' + $stamp + '.' + $runPart + '.rc' + $rc + '.launcher.' + $n)};Move-Item -Path $path -Destination $archive -Force -ErrorAction SilentlyContinue;if(Test-Path $path){Remove-Item -Path $path -Force -ErrorAction SilentlyContinue};if(Test-Path $path){Write-Output ('lock_cleanup_failed path=' + $path + ' run_id=' + $runPart + ' rc=' + $rc)}else{Write-Output ('lock_cleanup_archived path=' + $path + ' archive=' + $archive + ' run_id=' + $runPart + ' rc=' + $rc)}};" >> "%H_TASK_LOG%" 2>&1
  powershell -NoProfile -Command "$repo=[regex]::Escape('%ROOT%');$runPath='%H_RUN_IN_PROGRESS_FILE%';$currentPath='%H_CURRENT_RUN_FILE%';$finPath='%H_FINALIZED_RUN_FILE%';$run='';$current='';$fin='';if(Test-Path $runPath){$run=(Get-Content $runPath -Raw).Trim()};if(Test-Path $currentPath){$current=(Get-Content $currentPath -Raw).Trim()};if(Test-Path $finPath){$fin=(Get-Content $finPath -Raw).Trim()};$boundaryPath='';$boundaryExists=$false;$status='';if($run){$boundaryPath=Join-Path '%H_LIVE%' ('phase1_intel_alignment.boundary.' + $run + '.json');$boundaryExists=Test-Path $boundaryPath};if($boundaryExists){try{$raw=Get-Content $boundaryPath -Raw | ConvertFrom-Json;$status=[string]$raw.status}catch{$status=''}};$resultFiles=@();if($run){try{$resultFiles=Get-ChildItem -Path '%H_LIVE%' -Filter ('phase1_intel_alignment.result.' + $run + '.*.json') -ErrorAction SilentlyContinue | Sort-Object LastWriteTimeUtc -Descending}catch{$resultFiles=@()}};$resultExists=($resultFiles.Count -gt 0);$resultPath='';if($resultExists){$resultPath=$resultFiles[0].FullName};$archivePath='';$archiveExists=$false;$archiveValid=$false;if($run){$archivePath=Join-Path '%H_LIVE%' ('H_failed_run_archived.' + $run + '.json');$archiveExists=Test-Path $archivePath};if($archiveExists){try{$archiveRaw=Get-Content $archivePath -Raw | ConvertFrom-Json;if([string]$archiveRaw.run_id -eq $run){$archiveValid=$true}}catch{$archiveValid=$false}};$active=(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match $repo -and ( $_.CommandLine -like '*scripts\\cycles\\run_H_pricing_cycle.py*' -or $_.CommandLine -like '*scripts\\cycles\\run_H_pricing_cycle_guarded.py*' -or $_.CommandLine -like '*scripts\\flows\\H\\H110_run_phase1_h_pilot.py*' ) });if($active){$pids=@($active | ForEach-Object { [string]$_.ProcessId }) -join ',';Write-Output ('run_in_progress_cleanup_skip reason=python_active run_id=' + $run + ' pids=' + $pids);exit 0};if(-not $run){Write-Output 'run_in_progress_cleanup_skip reason=missing_marker';exit 0};if($run -eq $fin){Write-Output ('run_in_progress_cleanup_skip reason=already_finalized run_id=' + $run + ' finalized=' + $fin);exit 0};if($current -and $run -ne $current){Write-Output ('run_in_progress_cleanup_skip reason=run_id_mismatch marker=' + $run + ' current=' + $current);exit 0};if($boundaryExists -or $resultExists){if($archiveExists -and -not $archiveValid){Write-Output ('run_in_progress_cleanup_skip reason=invalid_archive_marker run_id=' + $run + ' archive_path=' + $archivePath);exit 0};if($archiveValid){Remove-Item -Path $runPath -Force -ErrorAction SilentlyContinue;if(Test-Path $runPath){Write-Output ('run_in_progress_cleanup_failed reason=archived_failed_run_release_failed run_id=' + $run + ' archive_path=' + $archivePath)}else{Write-Output ('run_in_progress_cleanup_ok reason=archived_failed_run_released run_id=' + $run + ' finalized=' + $fin + ' archive_path=' + $archivePath + ' boundary_exists=' + ($boundaryExists.ToString().ToLower()) + ' boundary_status=' + ($status -replace '\s+','_') + ' result_exists=' + ($resultExists.ToString().ToLower()) + ' result_path=' + $resultPath)};exit 0};$reason='finalization_pending_artifacts';if(@('active','unresolved_parent_exit') -contains $status.Trim().ToLower()){$reason='unresolved_boundary'};Write-Output ('run_in_progress_cleanup_skip reason=' + $reason + ' run_id=' + $run + ' finalized=' + $fin + ' boundary_exists=' + ($boundaryExists.ToString().ToLower()) + ' boundary_status=' + ($status -replace '\s+','_') + ' boundary_path=' + $boundaryPath + ' result_exists=' + ($resultExists.ToString().ToLower()) + ' result_path=' + $resultPath + ' archive_exists=' + ($archiveExists.ToString().ToLower()) + ' archive_path=' + $archivePath);exit 0};Remove-Item -Path $runPath -Force -ErrorAction SilentlyContinue;if(Test-Path $runPath){Write-Output ('run_in_progress_cleanup_failed run_id=' + $run + ' rc=%LOOP_RC%')}else{Write-Output ('run_in_progress_cleanup_ok run_id=' + $run + ' rc=%LOOP_RC% boundary_exists=false result_exists=false')}" >> "%H_TASK_LOG%" 2>&1
)
echo [%date% %time%] H-cycle loop finished (exit %LOOP_RC%) >> "%H_TASK_LOG%"
"%PY%" -u "%ROOT%\scripts\tools\h_session_tally.py" update --rc %LOOP_RC% --run_id_file "%H_LIVE%\H_cycle_current_run_id.txt" >> "%H_TASK_LOG%" 2>&1
if not "%LOOP_RC%"=="0" (
  if /I "%H_KILL_ORPHAN_H110_ON_FAILURE%"=="1" (
    powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*H110_run_phase1_h_pilot.py*' -and $_.CommandLine -like '*SellerOne 2.0*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >> "%H_TASK_LOG%" 2>&1
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
timeout /t %SLEEP_SECONDS% /nobreak >nul
goto loop

:drain_wait
powershell -NoProfile -Command "$payload=('launcher_pid=%H_LAUNCHER_SELF_PID%|utc=' + (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ') + '|state=drain_wait|restart_owner=launcher_loop|owner_role=%H_RESTART_OWNER_ROLE%'); [System.IO.File]::WriteAllText('%H_LAUNCHER_HEARTBEAT_FILE%',$payload + [Environment]::NewLine,[System.Text.Encoding]::ASCII)" >nul 2>&1
if not exist "%MAINT_REQUEST_PATH%" (
  if exist "%H_DRAIN_READY_FILE%" del /f /q "%H_DRAIN_READY_FILE%" >nul 2>&1
  echo [%date% %time%] H-cycle launcher restart_drain cleared - resuming loop >> "%H_TASK_LOG%"
  goto loop
)
timeout /t 15 /nobreak >nul
goto drain_wait

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




