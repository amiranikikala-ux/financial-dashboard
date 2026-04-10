@echo off
chcp 65001 >nul
set "ROOT=%~dp0"
cd /d "%ROOT%" || (
    echo ERROR: ვერ გადავედი პროექტის საქაღალდეში.
    pause
    exit /b 1
)

if not exist "venv\Scripts\python.exe" (
    echo ERROR: venv არ მოიძებნა. დააყენეთ: python -m venv venv
    pause
    exit /b 1
)

if not exist "_verify_all_audit.py" (
    echo ERROR: _verify_all_audit.py არ მოიძებნა.
    pause
    exit /b 1
)

echo.
echo === მონაცემების სრული შემოწმება ===
echo რეკონცილიაცია, ფაილ-ფაილობით, RS vs data.json — შეიძლება 2-4 წუთი დასჭირდეს.
echo.
"%ROOT%venv\Scripts\python.exe" "%ROOT%_verify_all_audit.py"
set "CHK=%ERRORLEVEL%"
echo.
if "%CHK%"=="0" (
    echo [OK] ყველა ავტომატური შემოწმება გავიდა.
) else (
    echo [FAIL] ზოგიერთი შემოწმება ჩავარდა — გადახედეთ ზემოთ წითელ/შეცდომის ტექსტს.
)
pause
exit /b %CHK%
