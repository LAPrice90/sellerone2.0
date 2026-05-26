@echo off
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"

if "%~1"=="" (
  set "SUPPLIER_ID=stocklist_supplier"
) else (
  set "SUPPLIER_ID=%~1"
)

call "%ROOT%run_F_shure_full_legacy_scan.bat" %SUPPLIER_ID%
endlocal
