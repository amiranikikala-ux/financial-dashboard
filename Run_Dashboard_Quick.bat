@echo off
chcp 65001 >nul
set "ROOT=%~dp0"
cd /d "%ROOT%" || (
  echo ERROR: Could not cd to project folder.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo  Run_Dashboard_Quick.bat — მხოლოდ სერვერი
echo  data.json და Excel არ განახლდება.
echo  სრული ციკლი: Run_Dashboard.bat ან Run_Dashboard_With_Check.bat
echo ============================================================
echo.

echo PowerShell-ში:  .\Run_Dashboard_Quick.bat  ^(წერტილი-შტრიხი სავალდებულოა^)
echo.

if not exist "rs-dashboard\node_modules" (
  echo INFO: npm install needed...
  pushd "rs-dashboard"
  call npm install
  if errorlevel 1 (
    echo ERROR: npm install failed
    popd
    pause
    exit /b 1
  )
  popd
)

echo INFO: Cleaning up old Dashboard API windows and processes...
taskkill /F /FI "WINDOWTITLE eq Dashboard API*" /T >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command "$conns = Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue; $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique; if ($pids) { foreach ($p in $pids) { taskkill.exe /F /PID $p /T 2>$null } }"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process -Filter 'name=''python.exe''' | Where-Object { $_.CommandLine -match 'server.py' -and $_.CommandLine -notmatch 'cursor' } | ForEach-Object { taskkill.exe /F /PID $_.ProcessId /T 2>&1 | Out-Null }"

echo Starting FastAPI...
start "Dashboard API" cmd /k "venv\Scripts\python.exe server.py"
echo INFO: FastAPI health-check ^(მოლოდინი მაქს. 45 წმ^)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$deadline = (Get-Date).AddSeconds(45); $ok = $false; while ((Get-Date) -lt $deadline) { try { $res = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/data?tab=suppliers' -UseBasicParsing -TimeoutSec 4; if ($res.StatusCode -eq 200) { $ok = $true; break } } catch {}; Start-Sleep -Milliseconds 800 }; if (-not $ok) { Write-Host 'ERROR: API did not become ready on http://127.0.0.1:8000'; exit 1 }"
if errorlevel 1 (
  echo ERROR: API ვერ გაეშვა დროულად. გადახედე "Dashboard API" ფანჯარას.
  pause
  exit /b 1
)

echo INFO: Cleaning up old Dashboard Server windows and processes...
taskkill /F /FI "WINDOWTITLE eq Dashboard Server*" /T >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ports = 5173..5177; $conns = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $ports -contains $_.LocalPort }; $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique; if ($pids) { foreach ($p in $pids) { taskkill.exe /F /PID $p /T 2>$null } }"

echo Starting Vite (no data refresh)...
start "Dashboard Server" cmd /k "rs-dashboard\_vite-dev.bat"
echo.
echo Vite იწყება — 4 წამში გაიხსნება ბრაუზერი ^(თუ არა — ხელით: http://127.0.0.1:5173/^)
timeout /t 4 /nobreak >nul
start "" "http://127.0.0.1:5173/"
echo.
echo Open: http://127.0.0.1:5173/  ^| API + Vite გაშვებულია
pause
