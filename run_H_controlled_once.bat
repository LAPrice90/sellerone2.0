@echo off
setlocal
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
call "%ROOT%\run_H_set_controlled_mode.bat" >nul 2>&1

set "H_RUN_ONCE=1"
set "H_USE_GUARD_WRAPPER=1"
set "H_PHASE1_PILOT_MODE=subprocess"
set "H_PHASE1_INTEL_MODE=inline"
set "H_PHASE1_PUBLISH_MODE=subprocess"
set "H_STAGE_SNAPSHOT_REFRESH=1"
set "H_STAGE_ITEM_OFFERS=1"
set "H_STAGE_PHASE1_PILOT=1"
set "H_STAGE_PHASE1_INTEL=1"
set "H_STAGE_PHASE1_PUBLISH=1"

call "%ROOT%\run_H_cycle.bat"
set "RC=%ERRORLEVEL%"
echo [H_controlled] run_once_rc=%RC%
endlocal & exit /b %RC%
