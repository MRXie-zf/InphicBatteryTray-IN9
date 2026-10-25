# InphicBatteryTray9 一键编译脚本
# 只需要 Windows 自带的 .NET Framework 编译器, 无需安装任何 SDK
$ErrorActionPreference = "Stop"

$csc = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path $csc)) {
    $csc = Join-Path $env:WINDIR "Microsoft.NET\Framework\v4.0.30319\csc.exe"
}

Write-Host "using compiler: $csc"

& $csc /target:winexe /platform:x64 /codepage:65001 `
    /out:InphicBatteryTray9.exe `
    /reference:System.dll /reference:System.Windows.Forms.dll `
    /reference:System.Drawing.dll /reference:System.Core.dll `
    src\InphicBatteryTray9.cs

if ($LASTEXITCODE -ne 0) {
    Write-Host "BUILD FAILED"
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "BUILD OK -> InphicBatteryTray9.exe"
Write-Host ""
Write-Host "建议先自检:  .\InphicBatteryTray9.exe --list"
Write-Host "             .\InphicBatteryTray9.exe --test"
