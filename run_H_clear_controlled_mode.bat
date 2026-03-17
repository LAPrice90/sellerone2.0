@echo off
setlocal
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "FLAG=%ROOT%\out\locks\h_controlled_mode.active"
if exist "%FLAG%" del "%FLAG%" >nul 2>&1
if exist "%FLAG%" (
  echo [H_controlled] clear_failed flag=%FLAG%
  endlocal & exit /b 1
)
echo [H_controlled] disabled flag=%FLAG%
endlocal
