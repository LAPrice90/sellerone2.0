@echo off
setlocal
set "PY=C:\Users\Luke\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"
set "ROOT=%~dp0"
"%PY%" "%ROOT%scripts\cycles\run_30day_catchup.py"
endlocal
