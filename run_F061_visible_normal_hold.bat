@echo off
setlocal
cd /d "%~dp0"
echo Starting visible normal F061 browser hold.
echo This is a no-Sheets diagnostic run.
echo If Chrome opens, use that scanner-owned Chrome window only.
echo.
python scripts\one_off\F063_run_f061_practice_list.py --input out\systems\F\diagnostics\f061_visible_normal_single_bbp_product_20260511T161500Z.csv --limit 1 --browser-mode visible --login-hold-seconds 900 --page-load-timeout-seconds 45 --row-pause-seconds 1 --final-hold-seconds 900
echo.
echo Visible normal F061 browser hold finished.
pause
