@echo off
setlocal

if "%~1"=="" (
  echo Usage: %~nx0 "C:\Path\To\ManageInventoryExport.csv"
  echo Example: %~nx0 "C:\Users\Luke\Downloads\ManageInventoryExport.csv" "seller-sku"
  exit /b 2
)

set "INPUT_PATH=%~1"
set "ACTIVE_OUT=out\active_listings.csv"
set "SKU_COL=%~2"
set "SKU_COL_ARG="
if not "%SKU_COL%"=="" set "SKU_COL_ARG=--sku-col ""%SKU_COL%"""

python scripts\tools\build_active_listings_csv.py --input "%INPUT_PATH%" --output "%ACTIVE_OUT%" %SKU_COL_ARG%
if errorlevel 1 exit /b %errorlevel%

python scripts\tools\diff_active_vs_scope.py
if errorlevel 1 exit /b %errorlevel%

echo.
echo DIFF outputs:
echo - out\DIFF_active_excluded_by_scope.csv
echo - out\DIFF_active_missing_from_scope.csv
exit /b 0
