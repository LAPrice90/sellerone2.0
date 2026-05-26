@echo off
setlocal
echo Opening fixed scanner Chromium 136 directly.
echo This bypasses chrlauncher and will not run the updater.
echo Profile: C:\Users\Luke\AppData\Local\Chrome_UC136 / Profile 2
echo.
start "" "C:\Chrome_UC136\bin\chrome.exe" --user-data-dir="C:\Users\Luke\AppData\Local\Chrome_UC136" --profile-directory="Profile 2" --no-default-browser-check
