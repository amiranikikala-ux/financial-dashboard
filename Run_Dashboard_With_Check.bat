@echo off
chcp 65001 >nul
title Dashboard: გენერაცია + შემოწმება ^(დაელოდეთ^)
set "ROOT=%~dp0"
set PYTHONUNBUFFERED=1
cd /d "%ROOT%" || (
    echo ERROR: ვერ გადავედი პროექტის საქაღალდეში.
    pause
    exit /b 1
)

if not exist "venv\Scripts\python.exe" (
    echo ERROR: venv არ მოიძებნა.
    pause
    exit /b 1
)

echo.
echo [1/3] Excel-იდან მონაცემების გენერაცია ^(3-15 წუთი შეიძლება^)... %TIME%
echo.
"%ROOT%venv\Scripts\python.exe" -u "%ROOT%generate_dashboard_data.py"
if errorlevel 1 (
    echo.
    echo ERROR: გენერაცია ჩავარდა — დეშბორდი არ გაეშვება.
    pause
    exit /b 1
)

if exist "%ROOT%_verify_all_audit.py" (
    echo.
    echo [2/3] დამატებითი ავტოშემოწმება ^(რეკონცილიაცია, RS, TBC ველები^)...
    echo შეიძლება 2-4 წუთი დასჭირდეს.
    echo.
    "%ROOT%venv\Scripts\python.exe" -u "%ROOT%_verify_all_audit.py"
    if errorlevel 1 (
        echo.
        echo ERROR: შემოწმებამ პრობლემა აღმოაჩინა — დეშბორდი არ გაეშვება. გადახედეთ ზემოთ.
        echo სცადეთ Check_Data.bat ან გამოასწორეთ Excel/კონფიგი.
        pause
        exit /b 1
    )
    echo.
    echo [OK] შემოწმება გავიდა.
) else (
    echo.
    echo [2/3] გამოტოვებული: _verify_all_audit.py არ არის ^(იგივე რაც Run_Dashboard.bat^).
)

if not exist "rs-dashboard\node_modules" (
    echo.
    echo npm install rs-dashboard-ში...
    pushd "rs-dashboard"
    call npm install
    if errorlevel 1 (
        echo ERROR: npm install
        popd
        pause
        exit /b 1
    )
    popd
)

echo.
echo [3/3] Vite სერვერის გაშვება ახალ ფანჯარაში...
pushd "rs-dashboard"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ports = 5173..5177; $conns = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $ports -contains $_.LocalPort }; $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique; if ($pids) { Stop-Process -Id $pids -Force -ErrorAction SilentlyContinue }"
start "Dashboard Server" "%ROOT%rs-dashboard\_vite-dev.bat"
popd

echo.
echo === მზადაა ===
echo ბრაუზერი: http://127.0.0.1:5173/
echo მონაცემები განახლებულია და შემოწმებულია.
pause
