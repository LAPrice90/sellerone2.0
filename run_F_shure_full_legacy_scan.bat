@echo off
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"

if "%~1"=="" (
  set "SUPPLIER_ID=stocklist_supplier"
) else (
  set "SUPPLIER_ID=%~1"
)
set "MAX_ROWS=5"
set "SCRAPE_MODE=legacy_module"
set "PRICE_SOURCE=native_comp_summary"
set "PRICING_MIN_INTERVAL_SECONDS=32"
set "F061_CATALOG_MIN_INTERVAL_SEC=0.6"
set "F061_HAZMAT_MIN_INTERVAL_SEC=1.2"
set "F061_FEES_MIN_INTERVAL_SEC=1.2"
set "F061_CATALOG_MAX_CANDIDATES=3"
set "F061_SCRAPE_PAGE_LOAD_TIMEOUT_SEC=45"
set "F061_MODE=data_collection"
set "F061_WEBSCRAPE_MODE=data"
set "LEGACY_ROOT=%ROOT%scripts\flows\F\legacy_scanner_2_1"
set "F061_LOG_DIR=%ROOT%out\systems\F\live"
set "F061_RUN_LOG_PATH=%F061_LOG_DIR%\f061_hometime.log"
set "F061_COMPONENT_LOG_PATH=%F061_LOG_DIR%\f061_hometime_components.log"
set "F061_LOG_PATH=%F061_COMPONENT_LOG_PATH%"

set "PYTHONUNBUFFERED=1"
set "BBP_FILE_LOG=1"

if not exist "%F061_LOG_DIR%" mkdir "%F061_LOG_DIR%"

echo [F061] Starting full legacy scan for %SUPPLIER_ID% (home-time chunk mode)
echo [F061] This run checkpoints every %MAX_ROWS% rows.
echo [F061] Runtime log: %F061_RUN_LOG_PATH%
echo [F061] Component log: %F061_COMPONENT_LOG_PATH%

:loop
where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python scripts\flows\F\F061_run_legacy_first_checks_local.py ^
    --supplier-id %SUPPLIER_ID% ^
    --max-rows %MAX_ROWS% ^
    --loop ^
    --loop-sleep-seconds 15 ^
    --scrape-mode %SCRAPE_MODE% ^
    --price-source %PRICE_SOURCE% ^
    --pricing-min-interval-seconds %PRICING_MIN_INTERVAL_SECONDS% ^
    --legacy-scanner-root "%LEGACY_ROOT%" >> "%F061_RUN_LOG_PATH%" 2>&1
) else (
  py -3 scripts\flows\F\F061_run_legacy_first_checks_local.py ^
    --supplier-id %SUPPLIER_ID% ^
    --max-rows %MAX_ROWS% ^
    --loop ^
    --loop-sleep-seconds 15 ^
    --scrape-mode %SCRAPE_MODE% ^
    --price-source %PRICE_SOURCE% ^
    --pricing-min-interval-seconds %PRICING_MIN_INTERVAL_SECONDS% ^
    --legacy-scanner-root "%LEGACY_ROOT%" >> "%F061_RUN_LOG_PATH%" 2>&1
)

if %ERRORLEVEL% neq 0 (
  echo [F061] Script crashed or failed. Retrying in 2 minutes...
  timeout /t 120
  goto loop
)

echo [F061] Run completed. Restarting in 2 minutes...
timeout /t 120 >nul
goto loop
