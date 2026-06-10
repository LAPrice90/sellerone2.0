@echo off
setlocal
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\tools\install_h_maintenance_controller.ps1" -Root "%ROOT%"
set "RC=%ERRORLEVEL%"
endlocal & exit /b %RC%
