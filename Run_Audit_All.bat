@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
    echo [შეცდომა] venv ვერ მოიძებნა
    pause
    exit /b 1
)
echo სასურველია: generate_dashboard_data.py ჯერ, რომ data.json იმავე მონაცემზე იყოს, რაც RS/ბანკი.
echo.
"%~dp0venv\Scripts\python.exe" audit_all.py
echo.
pause
