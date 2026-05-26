@echo off
setlocal
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\tools\h_validation_isolation.ps1" -Action resume -Root "%ROOT%"
set "RC=%ERRORLEVEL%"
endlocal & exit /b %RC%
