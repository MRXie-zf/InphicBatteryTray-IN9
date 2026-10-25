@echo off
REM ============================================================================
REM IN9 HID sniffer launcher (double-click to run)
REM Passive listen only - never writes to the mouse. Safe.
REM Usage: 旁听.cmd [seconds]   (default 90)
REM ============================================================================
chcp 65001 >nul
cd /d "%~dp0"

set PY=C:\Users\Lenovo\AppData\Local\Programs\Python\Python311\python.exe
if not exist "%PY%" set PY=C:\Users\Lenovo\AppData\Local\Programs\Python\Python312\python.exe
if not exist "%PY%" set PY=python
set PYTHONIOENCODING=utf-8

echo.
echo ============================================================
echo  IN9 HID SNIFFER - passive listen, no writes, safe
echo  Duration: 90 seconds (or pass a number: 旁听.cmd 120)
echo.
echo  WHAT TO DO:
echo   1) When you see "open official software" below,
echo      start the Inphic official app and read battery.
echo   2) Click refresh a few times. Keep mouse awake.
echo   3) When done, send back sniff_log.txt
echo ============================================================
echo.
echo Using Python: %PY%
echo.

"%PY%" sniff.py %1

echo.
echo ============================================================
echo Done. Sending sniff_log.txt to Notepad - please copy it back.
echo ============================================================
if exist sniff_log.txt start notepad sniff_log.txt
pause
