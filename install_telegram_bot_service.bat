@echo off
REM Install FinancialDashboardTelegramBot as a Windows service via NSSM.
REM Mirrors FinancialDashboardBackend's pattern (same venv, same project dir).
REM
REM Run this file as Administrator (right-click -> Run as administrator).

setlocal
set LOG=C:\financial-dashboard\logs\install_telegram_bot_service.log
echo [%DATE% %TIME%] install start > "%LOG%" 2>&1

set NSSM=C:\tools\nssm\nssm.exe
set SERVICE=FinancialDashboardTelegramBot
set PYTHON=C:\financial-dashboard\venv\Scripts\python.exe
set PROJECT=C:\financial-dashboard
set SCRIPT=telegram_bot.py
set STDOUT=C:\financial-dashboard\logs\telegram_bot_stdout.log
set STDERR=C:\financial-dashboard\logs\telegram_bot_stderr.log

echo === Telegram bot service install ===

REM Verify NSSM exists
if not exist "%NSSM%" (
    echo ERROR: NSSM not found at %NSSM% >> "%LOG%" 2>&1
    pause
    exit /b 1
)

REM Verify python exists
if not exist "%PYTHON%" (
    echo ERROR: Python not found at %PYTHON% >> "%LOG%" 2>&1
    pause
    exit /b 1
)

REM Check if service already exists
sc query %SERVICE% >nul 2>&1
if %errorlevel% equ 0 (
    echo Service %SERVICE% already exists. Stopping and removing first... >> "%LOG%" 2>&1
    "%NSSM%" stop %SERVICE% >> "%LOG%" 2>&1
    "%NSSM%" remove %SERVICE% confirm >> "%LOG%" 2>&1
)

echo Installing service %SERVICE%... >> "%LOG%" 2>&1
"%NSSM%" install %SERVICE% "%PYTHON%" -u %SCRIPT% >> "%LOG%" 2>&1
"%NSSM%" set %SERVICE% AppDirectory "%PROJECT%" >> "%LOG%" 2>&1
"%NSSM%" set %SERVICE% Start SERVICE_AUTO_START >> "%LOG%" 2>&1
"%NSSM%" set %SERVICE% AppStdout "%STDOUT%" >> "%LOG%" 2>&1
"%NSSM%" set %SERVICE% AppStderr "%STDERR%" >> "%LOG%" 2>&1
"%NSSM%" set %SERVICE% AppRotateFiles 1 >> "%LOG%" 2>&1
"%NSSM%" set %SERVICE% AppRotateOnline 1 >> "%LOG%" 2>&1
"%NSSM%" set %SERVICE% AppRotateBytes 10485760 >> "%LOG%" 2>&1
"%NSSM%" set %SERVICE% AppStopMethodSkip 0 >> "%LOG%" 2>&1
"%NSSM%" set %SERVICE% AppExit Default Restart >> "%LOG%" 2>&1
"%NSSM%" set %SERVICE% AppRestartDelay 5000 >> "%LOG%" 2>&1
"%NSSM%" set %SERVICE% Description "Financial Dashboard Telegram Bot - long-poll Telegram, forward to /api/chat." >> "%LOG%" 2>&1

echo Starting service... >> "%LOG%" 2>&1
"%NSSM%" start %SERVICE% >> "%LOG%" 2>&1

echo === Verifying state === >> "%LOG%" 2>&1
sc query %SERVICE% >> "%LOG%" 2>&1
echo [%DATE% %TIME%] install end >> "%LOG%" 2>&1
