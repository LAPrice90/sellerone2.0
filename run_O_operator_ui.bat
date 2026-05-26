@echo off
setlocal
cd /d "%~dp0"
if not defined SELLERONE_STORAGE_MODE set "SELLERONE_STORAGE_MODE=sql_primary_csv_export"
if not defined SELLERONE_SQLITE_PATH set "SELLERONE_SQLITE_PATH=out/sql/sellerone_dev.sqlite3"
python -m streamlit run scripts\flows\O\O400_operator_ui.py
if errorlevel 1 (
    echo.
    echo Failed to launch O operator UI.
    echo Check that Python and Streamlit are installed in this environment.
    pause
)
