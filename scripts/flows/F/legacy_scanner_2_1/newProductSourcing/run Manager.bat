@echo off
cd "C:\Users\Luke\Desktop\Amazon Price List Scanner 2.1\newProductSourcing"

:loop
python manager.py

:: Only retry if script failed
if %errorlevel% neq 0 (
    echo [ERROR] Script crashed or failed. Retrying in 10 minutes...
    timeout /t 600
    goto loop
)

:: Script exited cleanly (A1 = completed or finished normally)
echo [INFO] Script completed successfully. No retry needed.
exit /b
