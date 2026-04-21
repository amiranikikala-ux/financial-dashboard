@echo off
chcp 65001 >nul
title Dashboard: Excel — data.json ^(დაელოდეთ^)
set "ROOT=%~dp0"
for %%I in ("%ROOT%..") do set "WORKSPACE_ROOT=%%~fI"
set "PYTHON_BIN=%WORKSPACE_ROOT%\venv\Scripts\python.exe"
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

if not exist "%PYTHON_BIN%" (
    echo ERROR: venv was not found in this folder:
    echo   %PYTHON_BIN%
    echo Open CMD here and run: python -m venv venv
    pause
    exit /b 1
)

echo [1/2] მონაცემების გენერაცია... დაწყება %TIME%
echo.
"%PYTHON_BIN%" -u "%ROOT%generate_dashboard_data.py"
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
echo [2/3] API სერვერი ^(ახალ ფანჯარაში^)...
echo INFO: Cleaning up old Dashboard API windows and processes...
taskkill /F /FI "WINDOWTITLE eq Dashboard API*" /T >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$conns = Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue; $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique; if ($pids) { foreach ($p in $pids) { taskkill.exe /F /PID $p /T 2>$null } }"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process -Filter 'name=''python.exe''' | Where-Object { $_.CommandLine -match 'server.py' -and $_.CommandLine -notmatch 'cursor' } | ForEach-Object { taskkill.exe /F /PID $_.ProcessId /T 2>&1 | Out-Null }"

echo Starting FastAPI...
start "Dashboard API" cmd /k "_api-dev.bat"
echo INFO: FastAPI health-check ^(მოლოდინი მაქს. 45 წმ^)...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$deadline = (Get-Date).AddSeconds(45); $ok = $false; while ((Get-Date) -lt $deadline) { try { $res = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/data?tab=suppliers' -UseBasicParsing -TimeoutSec 4; if ($res.StatusCode -eq 200) { $ok = $true; break } } catch {}; Start-Sleep -Milliseconds 800 }; if (-not $ok) { Write-Host 'ERROR: API did not become ready on http://127.0.0.1:8000'; exit 1 }"
if errorlevel 1 (
  echo ERROR: API ვერ გაეშვა დროულად. გადახედე "Dashboard API" ფანჯარას.
  popd
  pause
  exit /b 1
)

title Dashboard: Vite სერვერი
echo [3/3] Dashboard სერვერი ^(ახალ ფანჯარაში^) — არ დახუროთ ის ფანჯარა მუშაობის დროს.
pushd "rs-dashboard"
echo INFO: Cleaning up old Dashboard Server windows and processes...
taskkill /F /FI "WINDOWTITLE eq Dashboard Server*" /T >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ports = 5173..5177; $conns = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $ports -contains $_.LocalPort }; $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique; if ($pids) { foreach ($p in $pids) { taskkill.exe /F /PID $p /T 2>$null } }"
echo INFO: Opening on http://127.0.0.1:5173
rem Use helper script so paths with spaces / Unicode never break quoting
start "Dashboard Server" cmd /k "_vite-dev.bat"
echo INFO: ბრაუზერის გახსნა 4 წამში ^(თუ არ გაიხსნა — გახსენი ხელით^)...
timeout /t 4 /nobreak >nul
start "" "http://127.0.0.1:5173/"
popd
popd
echo.
echo Dashboard and API servers were started in new windows.
echo ბრაუზერი: http://127.0.0.1:5173/  ^(Ctrl+F5 — ძლიერი განახლება^)
echo დამატებითი შემოწმება: ორმაგი დაკლიკება Check_Data.bat
pause
