@echo off
setlocal

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
cd /d "%ROOT%"

if not defined HOME_TIME_MONITOR_RESTART_DELAY_SECONDS set "HOME_TIME_MONITOR_RESTART_DELAY_SECONDS=15"

:monitor_loop
call "%ROOT%\run_home_time_monitor.bat"
set "RC=%ERRORLEVEL%"
echo [home_time_supervisor] monitor exited rc=%RC% at %DATE% %TIME%
timeout /t %HOME_TIME_MONITOR_RESTART_DELAY_SECONDS% /nobreak >nul
goto monitor_loop
