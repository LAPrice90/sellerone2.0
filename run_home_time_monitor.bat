@echo off
setlocal

set "PY=C:\Users\Luke\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
cd /d "%ROOT%"

set "SCRIPT=%ROOT%\scripts\tools\home_time_monitor.py"
if not exist "%SCRIPT%" (
  echo [home_time_monitor] missing monitor script: "%SCRIPT%"
  endlocal & exit /b 1
)

if not defined HOME_TIME_H_TASK_NAME set "HOME_TIME_H_TASK_NAME=AMZ H Cycle"
if not defined HOME_TIME_ALLOW_SAFE_ARCHIVE set "HOME_TIME_ALLOW_SAFE_ARCHIVE=1"
if not defined HOME_TIME_ALLOW_SAFE_BOOTSTRAP set "HOME_TIME_ALLOW_SAFE_BOOTSTRAP=1"
if not defined HOME_TIME_MONITOR_CONTINUOUS set "HOME_TIME_MONITOR_CONTINUOUS=1"
if not defined HOME_TIME_MONITOR_INTERVAL_SECONDS set "HOME_TIME_MONITOR_INTERVAL_SECONDS=30"
if not defined HOME_TIME_MONITOR_IDLE_INTERVAL_SECONDS set "HOME_TIME_MONITOR_IDLE_INTERVAL_SECONDS=60"

set "ARGS=--interval-seconds %HOME_TIME_MONITOR_INTERVAL_SECONDS% --idle-interval-seconds %HOME_TIME_MONITOR_IDLE_INTERVAL_SECONDS%"
if /I "%HOME_TIME_ALLOW_SAFE_ARCHIVE%"=="1" set "ARGS=%ARGS% --allow-safe-archive"
if /I "%HOME_TIME_ALLOW_SAFE_BOOTSTRAP%"=="1" set "ARGS=%ARGS% --allow-safe-bootstrap"
if /I "%HOME_TIME_MONITOR_CONTINUOUS%"=="1" (
  set "ARGS=%ARGS% --continuous"
) else (
  set "ARGS=%ARGS% --once"
)

"%PY%" -u "%SCRIPT%" %ARGS%
set "RC=%ERRORLEVEL%"
echo [home_time_monitor] exit rc=%RC%

endlocal & exit /b %RC%
