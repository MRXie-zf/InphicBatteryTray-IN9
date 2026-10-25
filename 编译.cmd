@echo off
REM ============================================================================
REM InphicBatteryTray9 one-click build (double-click to run)
REM Uses the csc.exe shipped with .NET Framework 4.x - no SDK needed.
REM ============================================================================
cd /d "%~dp0"

set CSC=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe
if not exist "%CSC%" set CSC=C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe
if not exist "%CSC%" (
    echo [ERROR] csc.exe not found. Install .NET Framework 4.x first.
    pause
    exit /b 1
)

echo Compiling with: %CSC%
echo.

"%CSC%" /nologo /target:winexe /platform:x64 /codepage:65001 ^
    /out:InphicBatteryTray9.exe ^
    /reference:System.dll ^
    /reference:System.Windows.Forms.dll ^
    /reference:System.Drawing.dll ^
    /reference:System.Core.dll ^
    src\InphicBatteryTray9.cs

if errorlevel 1 (
    echo.
    echo [FAILED] Compile errors above. Fix them and run this script again.
    pause
    exit /b 1
)

echo.
echo [OK] InphicBatteryTray9.exe built successfully.
echo.
echo Next steps:
echo   1. InphicBatteryTray9.exe --list    ^(check your mouse VID/PID^)
echo   2. InphicBatteryTray9.exe --test    ^(send 0x10 query, dump raw response^)
echo   3. InphicBatteryTray9.exe          ^(run in tray^)
echo.
pause
