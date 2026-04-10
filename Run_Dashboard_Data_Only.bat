@echo off
chcp 65001 >nul
title Dashboard: მხოლოდ data.json ^(Python^)
set "ROOT=%~dp0"
set PYTHONUNBUFFERED=1
cd /d "%ROOT%" || (echo ERROR: cd & pause & exit /b 1)

if not exist "venv\Scripts\python.exe" (
    echo ERROR: venv არ მოიძებნა.
    pause
    exit /b 1
)

echo.
echo === მხოლოდ Excel → data.json + download/ ===
echo სერვერი არ გაეშვება. დრო: ხშირად 3-15 წუთი — ქვემოთ უნდა ჩანდეს ლოგი.
echo.
echo დაწყება %TIME%
echo.
"%ROOT%venv\Scripts\python.exe" -u "%ROOT%generate_dashboard_data.py"
if errorlevel 1 (
    echo ERROR
    pause
    exit /b 1
)
echo.
echo დასრულდა %TIME%
echo გვერდის სანახავად: Run_Dashboard_Quick.bat
pause
