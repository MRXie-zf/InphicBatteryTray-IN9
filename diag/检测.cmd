@echo off
REM ============================================================================
REM IN9 HID diagnosis launcher (double-click to run)
REM Uses system Python - no install needed.
REM ============================================================================
cd /d "%~dp0"

set PY=C:\Users\Lenovo\AppData\Local\Programs\Python\Python311\python.exe
if not exist "%PY%" set PY=C:\Users\Lenovo\AppData\Local\Programs\Python\Python312\python.exe
if not exist "%PY%" set PY=python

echo.
echo Using Python: %PY%
echo.
"%PY%" diag.py %*

echo.
echo ============================================================
echo Done. Send this output back for analysis.
echo ============================================================
pause
