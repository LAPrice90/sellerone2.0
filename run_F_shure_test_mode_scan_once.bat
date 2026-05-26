@echo off
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"

if "%~1"=="" (
  set "SUPPLIER_ID=stocklist_supplier"
) else (
  set "SUPPLIER_ID=%~1"
)
set "MAX_ROWS=10"
set "SCRAPE_MODE=legacy_module"
set "PRICE_SOURCE=native_comp_summary"
set "PRICING_MIN_INTERVAL_SECONDS=32"
set "F061_CATALOG_MIN_INTERVAL_SEC=0.6"
set "F061_HAZMAT_MIN_INTERVAL_SEC=1.2"
set "F061_FEES_MIN_INTERVAL_SEC=1.2"
set "LEGACY_ROOT=%ROOT%scripts\flows\F\legacy_scanner_2_1"

set "PYTHONUNBUFFERED=1"
set "BBP_FILE_LOG=1"

echo [F062] Resetting temporary test queue from canonical_current for %SUPPLIER_ID%
where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python scripts\flows\F\F062_reset_supplier_test_mode.py --supplier-id %SUPPLIER_ID%
) else (
  py -3 scripts\flows\F\F062_reset_supplier_test_mode.py --supplier-id %SUPPLIER_ID%
)

if %ERRORLEVEL% neq 0 (
  echo [F062] Reset failed. Stopping test run.
  exit /b 1
)

echo [F061] Running temporary test scan for %SUPPLIER_ID% (%MAX_ROWS% rows)
where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python scripts\flows\F\F061_run_legacy_first_checks_local.py ^
    --supplier-id %SUPPLIER_ID% ^
    --max-rows %MAX_ROWS% ^
    --scrape-mode %SCRAPE_MODE% ^
    --price-source %PRICE_SOURCE% ^
    --pricing-min-interval-seconds %PRICING_MIN_INTERVAL_SECONDS% ^
    --legacy-scanner-root "%LEGACY_ROOT%"
) else (
  py -3 scripts\flows\F\F061_run_legacy_first_checks_local.py ^
    --supplier-id %SUPPLIER_ID% ^
    --max-rows %MAX_ROWS% ^
    --scrape-mode %SCRAPE_MODE% ^
    --price-source %PRICE_SOURCE% ^
    --pricing-min-interval-seconds %PRICING_MIN_INTERVAL_SECONDS% ^
    --legacy-scanner-root "%LEGACY_ROOT%"
)

if %ERRORLEVEL% neq 0 (
  echo [F061] Test scan failed.
  exit /b 1
)

echo [F061] Test scan finished.
endlocal
