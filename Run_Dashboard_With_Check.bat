@echo off
chcp 65001 >nul
title Dashboard: გენერაცია + შემოწმება ^(დაელოდეთ^)
set "ROOT=%~dp0"
for %%I in ("%ROOT%..") do set "WORKSPACE_ROOT=%%~fI"
set "PYTHON_BIN=%WORKSPACE_ROOT%\venv\Scripts\python.exe"
set PYTHONUNBUFFERED=1
cd /d "%ROOT%" || (
    echo ERROR: ვერ გადავედი პროექტის საქაღალდეში.
    pause
    exit /b 1
)

if not exist "%PYTHON_BIN%" (
    echo ERROR: venv არ მოიძებნა.
    pause
    exit /b 1
)

echo.
echo [1/3] Excel-იდან მონაცემების გენერაცია ^(3-15 წუთი შეიძლება^)... %TIME%
echo.
"%PYTHON_BIN%" -u "%ROOT%generate_dashboard_data.py"
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
    "%PYTHON_BIN%" -u "%ROOT%_verify_all_audit.py"
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
echo [3/4] API სერვერის გაშვება ახალ ფანჯარაში...
echo INFO: Cleaning up old Dashboard API windows and processes...
taskkill /F /FI "WINDOWTITLE eq Dashboard API*" /T >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$conns = Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue; $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique; if ($pids) { foreach ($p in $pids) { taskkill.exe /F /PID $p /T 2>$null } }"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process -Filter 'name=''python.exe''' | Where-Object { $_.CommandLine -match 'server.py' -and $_.CommandLine -notmatch 'cursor' } | ForEach-Object { taskkill.exe /F /PID $_.ProcessId /T 2>&1 | Out-Null }"
start "Dashboard API" cmd /k "_api-dev.bat"
echo INFO: FastAPI health-check ^(მოლოდინი მაქს. 45 წმ^)...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$deadline = (Get-Date).AddSeconds(45); $ok = $false; while ((Get-Date) -lt $deadline) { try { $res = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/data?tab=suppliers' -UseBasicParsing -TimeoutSec 4; if ($res.StatusCode -eq 200) { $ok = $true; break } } catch {}; Start-Sleep -Milliseconds 800 }; if (-not $ok) { Write-Host 'ERROR: API did not become ready on http://127.0.0.1:8000'; exit 1 }"
if errorlevel 1 (
    echo ERROR: API ვერ გაეშვა დროულად. გადახედე "Dashboard API" ფანჯარას.
    pause
    exit /b 1
)

echo.
echo [4/4] Vite სერვერის გაშვება ახალ ფანჯარაში...
pushd "rs-dashboard"
echo INFO: Cleaning up old Dashboard Server windows and processes...
taskkill /F /FI "WINDOWTITLE eq Dashboard Server*" /T >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ports = 5173..5177; $conns = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $ports -contains $_.LocalPort }; $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique; if ($pids) { foreach ($p in $pids) { taskkill.exe /F /PID $p /T 2>$null } }"
start "Dashboard Server" cmd /k "_vite-dev.bat"
echo INFO: ბრაუზერის გახსნა 4 წამში...
timeout /t 4 /nobreak >nul
start "" "http://127.0.0.1:5173/"
popd

echo.
echo === მზადაა ===
echo ბრაუზერი: http://127.0.0.1:5173/
echo მონაცემები განახლებულია, შემოწმებულია და API/Vite ორივე გაშვებულია.
pause
