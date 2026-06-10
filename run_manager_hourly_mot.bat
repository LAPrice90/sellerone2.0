@echo off
setlocal
set "ROOT=%~dp0"
set "PY=C:\Users\Luke\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"
set "PYTHONPATH=%ROOT%;%ROOT%scripts;%PYTHONPATH%"
cd /d "%ROOT%"
"%PY%" -m sellerone_manager.app --hourly-mot --mot-flow all
endlocal
