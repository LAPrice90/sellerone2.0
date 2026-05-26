@echo off
setlocal
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\tools\h_owner_audit_readiness.ps1" -Action enable -Root "%ROOT%"
set "RC=%ERRORLEVEL%"
endlocal & exit /b %RC%
