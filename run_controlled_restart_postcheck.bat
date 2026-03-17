@echo off
setlocal

set "PY=C:\Users\Luke\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
cd /d "%ROOT%"

set "CTRL_SCRIPT=%ROOT%\scripts\tools\controlled_restart_controller.py"
if not exist "%CTRL_SCRIPT%" (
  echo [controlled_restart_postcheck] missing controller script: "%CTRL_SCRIPT%"
  endlocal & exit /b 1
)

"%PY%" -u "%CTRL_SCRIPT%" --ignore-window --max-wait-seconds 0 --poll-seconds 5 --clear-drain-on-skip
set "RC=%ERRORLEVEL%"
echo [controlled_restart_postcheck] controller exit rc=%RC%

endlocal & exit /b %RC%
