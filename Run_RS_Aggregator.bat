@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [შეცდომა] venv ვერ მოიძებნა: %~dp0
    pause
    exit /b 1
)

echo RS მონაცემების აგრეგაცია მიმდინარეობს...
"%~dp0venv\Scripts\python.exe" create_final_excel.py
if errorlevel 1 (
    echo [შეცდომა] create_final_excel.py
    pause
    exit /b 1
)

echo.
echo ოპერაცია დასრულდა. RS_Final_Check.xlsx ამ ფოლდერში უნდა განახლდეს.
pause
