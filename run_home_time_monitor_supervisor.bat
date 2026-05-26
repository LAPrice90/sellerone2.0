@echo off
setlocal

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
cd /d "%ROOT%"

if not defined HOME_TIME_MONITOR_RESTART_DELAY_SECONDS set "HOME_TIME_MONITOR_RESTART_DELAY_SECONDS=15"
if not defined HOME_TIME_MONITOR_SUPERVISOR_DETACHED set "HOME_TIME_MONITOR_SUPERVISOR_DETACHED=0"
if /I not "%HOME_TIME_MONITOR_SUPERVISOR_DETACHED%"=="1" (
  powershell -NoProfile -WindowStyle Hidden -Command "$env:HOME_TIME_MONITOR_SUPERVISOR_DETACHED='1'; Start-Process -WindowStyle Hidden -FilePath 'cmd.exe' -WorkingDirectory '%ROOT%' -ArgumentList '/d','/c','call ""%~f0""'" >nul 2>&1
  if not errorlevel 1 (
    endlocal & exit /b 0
  )
)

:monitor_loop
call "%ROOT%\run_home_time_monitor.bat"
set "RC=%ERRORLEVEL%"
echo [home_time_supervisor] monitor exited rc=%RC% at %DATE% %TIME%
timeout /t %HOME_TIME_MONITOR_RESTART_DELAY_SECONDS% /nobreak >nul 2>&1
goto monitor_loop
