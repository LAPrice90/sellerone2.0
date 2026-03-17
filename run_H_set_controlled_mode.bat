@echo off
setlocal
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
if not exist "%ROOT%\out\locks" mkdir "%ROOT%\out\locks"
set "FLAG=%ROOT%\out\locks\h_controlled_mode.active"
(
  echo controlled_mode=1
  echo set_utc=%date% %time%
) > "%FLAG%"
echo [H_controlled] enabled flag=%FLAG%
endlocal
