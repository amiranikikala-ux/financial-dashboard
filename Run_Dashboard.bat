@echo off
chcp 65001 >nul
title Dashboard: Excel — data.json ^(დაელოდეთ^)
set "ROOT=%~dp0"
set PYTHONUNBUFFERED=1
pushd "%ROOT%" || (
    echo ERROR: Could not switch to project folder:
    echo   "%ROOT%"
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  Run_Dashboard.bat — სტანდარტული რეჟიმი
echo  1^) Excel-იდან განახლება: data.json + download\
echo  2^) Vite სერვერი: http://127.0.0.1:5173/
echo.
echo  მნიშვნელოვანი ანალიზისთვის: Run_Dashboard_With_Check.bat
echo  ^(იგივე + სრული ავტოშემოწმება; თუ შეცდომაა — დეშბორდი არ გაეშვება^)
echo ============================================================
echo.
echo  [მნიშვნელოვანი] ნაბიჯი 1 ^(Python^) შეიძლება 3-15 წუთი გრძელდეს — ეს ნორმაა.
echo  ქვემოთ უნდა გარბინოს ტექსტი ^(მომწოდებლები, ბანკი, RS...^). არ დახუროთ ფანჯარა.
echo  მხოლოდ მონაცემები გინდათ სწრაფად: Run_Dashboard_Data_Only.bat — შემდეგ Run_Dashboard_Quick.bat
echo ============================================================
echo.

if not exist "venv\Scripts\python.exe" (
    echo ERROR: venv was not found in this folder:
    echo   %~dp0
    echo Open CMD here and run: python -m venv venv
    pause
    exit /b 1
)

echo [1/2] მონაცემების გენერაცია... დაწყება %TIME%
echo.
"%ROOT%venv\Scripts\python.exe" -u "%ROOT%generate_dashboard_data.py"
if errorlevel 1 (
    echo ERROR: generate_dashboard_data.py failed
    popd
    pause
    exit /b 1
)
echo.
echo [OK] Python დასრულდა %TIME%

if not exist "rs-dashboard\node_modules" (
    echo INFO: Installing npm dependencies in rs-dashboard...
    pushd "rs-dashboard"
    call npm install
    popd
)

echo.
echo [OK] data.json განახლდა.
echo.
title Dashboard: Vite სერვერი
echo [2/2] Dashboard სერვერი ^(ახალ ფანჯარაში^) — არ დახუროთ ის ფანჯარა მუშაობის დროს.
pushd "rs-dashboard"
echo INFO: Releasing old Vite ports 5173-5177 if busy...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ports = 5173..5177; $conns = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $ports -contains $_.LocalPort }; $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique; if ($pids) { Stop-Process -Id $pids -Force -ErrorAction SilentlyContinue }"
echo INFO: Opening on http://127.0.0.1:5173
rem Use helper script so paths with spaces / Unicode never break quoting
start "Dashboard Server" "%ROOT%rs-dashboard\_vite-dev.bat"
popd
popd
echo.
echo Dashboard server was started in a new window.
echo ბრაუზერი: http://127.0.0.1:5173/  ^(Ctrl+F5 — ძლიერი განახლება^)
echo დამატებითი შემოწმება: ორმაგი დაკლიკება Check_Data.bat
pause
