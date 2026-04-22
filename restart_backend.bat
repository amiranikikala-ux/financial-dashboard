@echo off
REM ---------------------------------------------------------------------------
REM Financial Dashboard Backend — restart helper (admin-elevated)
REM
REM Usage: double-click this file OR run from cmd/PowerShell.
REM Opens an elevated PowerShell window that:
REM   1. Restarts the Windows Service "FinancialDashboardBackend"
REM   2. Shows post-restart status + PID
REM   3. Shows last 5 lines of backend_stdout.log
REM
REM Close the window when done reading.
REM ---------------------------------------------------------------------------

echo Starting admin-elevated PowerShell to restart Financial Dashboard Backend...
powershell -Command ^
    "Start-Process powershell -Verb RunAs -ArgumentList '-NoExit -Command \"^
        $ErrorActionPreference = ''Continue''; ^
        Write-Host ''Restarting FinancialDashboardBackend...'' -ForegroundColor Yellow; ^
        Restart-Service FinancialDashboardBackend -ErrorAction Continue; ^
        Start-Sleep -Seconds 3; ^
        Write-Host ''''; ^
        Write-Host ''Service status:'' -ForegroundColor Cyan; ^
        Get-Service FinancialDashboardBackend | Format-List Name, Status, StartType; ^
        Write-Host ''Backend log tail (last 10 lines):'' -ForegroundColor Cyan; ^
        $logPath = Join-Path $PSScriptRoot ''logs\backend_stdout.log''; ^
        if (Test-Path $logPath) { Get-Content $logPath -Tail 10 } else { Write-Host ''(log file not yet created)'' }; ^
        Write-Host ''''; ^
        Write-Host ''Done. Close this window when finished reading.'' -ForegroundColor Green^
    \"'"

exit /b 0
