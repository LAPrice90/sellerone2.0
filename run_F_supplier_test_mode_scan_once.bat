@echo off
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"

if "%~1"=="" (
  set "SUPPLIER_ID=stocklist_supplier"
) else (
  set "SUPPLIER_ID=%~1"
)

call "%ROOT%run_F_shure_test_mode_scan_once.bat" %SUPPLIER_ID%
endlocal
