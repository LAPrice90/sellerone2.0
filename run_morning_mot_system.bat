@echo off
setlocal

set "PY=C:\Users\Luke\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
cd /d "%ROOT%"

if not defined SELLERONE_STORAGE_MODE set "SELLERONE_STORAGE_MODE=sql_primary_csv_export"
if not defined SELLERONE_SQLITE_PATH set "SELLERONE_SQLITE_PATH=out/sql/sellerone_dev.sqlite3"
set "PYTHONPATH=%ROOT%;%ROOT%\scripts;%PYTHONPATH%"

"%PY%" -u "%ROOT%\scripts\tools\morning_mot_system.py" %*
set "RC=%ERRORLEVEL%"
echo [morning_mot_system] exit rc=%RC%

endlocal & exit /b %RC%
