@echo off
chcp 65001 >nul
set "ROOT=%~dp0"
for %%I in ("%ROOT%..") do set "WORKSPACE_ROOT=%%~fI"
set "PYTHON_BIN=%WORKSPACE_ROOT%\venv\Scripts\python.exe"
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

rem ============================================================
rem  IDEMPOTENT MODE (added 2026-04-21)
rem  - If API on :8000 is already healthy (e.g. Windows Service
rem    FinancialDashboardBackend), we DO NOT kill anything. We
rem    reuse the running API.
rem  - If Vite on :5173 is already healthy, we reuse it as well.
rem  This prevents the script from tearing down the managed
rem  Windows Service that Phase 4A installed and from churning
rem  a fresh Vite every launch.
rem ============================================================

echo.
echo INFO: Checking if FastAPI on :8000 is already healthy...
rem  Using /api/status (lightweight, no-auth, ~2ms) instead of the data tab
rem  endpoint, which can take over 3 seconds while the data worker is busy
rem  refreshing Excel. TimeoutSec bumped from 3 to 10 to survive transient
rem  latency spikes during heavy scheduler runs.
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/status' -UseBasicParsing -TimeoutSec 10; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }"
if not errorlevel 1 (
  echo INFO: API already healthy on :8000 — skipping API restart.
  goto vite_check
)

echo INFO: API not healthy — cleaning up stale windows/processes...
taskkill /F /FI "WINDOWTITLE eq Dashboard API*" /T >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command "$conns = Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue; $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique; if ($pids) { foreach ($p in $pids) { taskkill.exe /F /PID $p /T 2>$null } }"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process -Filter 'name=''python.exe''' | Where-Object { $_.CommandLine -match 'server.py' -and $_.CommandLine -notmatch 'cursor' } | ForEach-Object { taskkill.exe /F /PID $_.ProcessId /T 2>&1 | Out-Null }"

echo Starting FastAPI...
start "Dashboard API" cmd /k "_api-dev.bat"
echo INFO: FastAPI health-check ^(მოლოდინი მაქს. 45 წმ^)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$deadline = (Get-Date).AddSeconds(45); $ok = $false; while ((Get-Date) -lt $deadline) { try { $res = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/status' -UseBasicParsing -TimeoutSec 4; if ($res.StatusCode -eq 200) { $ok = $true; break } } catch {}; Start-Sleep -Milliseconds 800 }; if (-not $ok) { Write-Host 'ERROR: API did not become ready on http://127.0.0.1:8000'; exit 1 }"
if errorlevel 1 (
  echo ERROR: API ვერ გაეშვა დროულად. გადახედე "Dashboard API" ფანჯარას.
  pause
  exit /b 1
)

:vite_check
echo.
echo INFO: Checking if Vite on :5173 is already healthy...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:5173/' -UseBasicParsing -TimeoutSec 3; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }"
if not errorlevel 1 (
  echo INFO: Vite already healthy on :5173 — skipping Vite restart.
  goto open_browser
)

echo INFO: Vite not healthy — cleaning up stale windows/processes...
taskkill /F /FI "WINDOWTITLE eq Dashboard Server*" /T >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ports = 5173..5177; $conns = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $ports -contains $_.LocalPort }; $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique; if ($pids) { foreach ($p in $pids) { taskkill.exe /F /PID $p /T 2>$null } }"

echo Starting Vite (no data refresh)...
start "Dashboard Server" cmd /k "rs-dashboard\_vite-dev.bat"
echo INFO: Vite health-check ^(მოლოდინი მაქს. 25 წმ^)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$deadline = (Get-Date).AddSeconds(25); $ok = $false; while ((Get-Date) -lt $deadline) { try { $res = Invoke-WebRequest -Uri 'http://127.0.0.1:5173/' -UseBasicParsing -TimeoutSec 3; if ($res.StatusCode -eq 200) { $ok = $true; break } } catch {}; Start-Sleep -Milliseconds 800 }; if (-not $ok) { Write-Host 'WARN: Vite did not become ready in 25s — browser will still open, you may need one manual refresh.' }"

:open_browser
echo.
start "" "http://127.0.0.1:5173/"
echo Open: http://127.0.0.1:5173/  ^| API + Vite გაშვებულია
echo.
echo ==============================================================
echo  Tip: ამ script-ის ხელახლა გაშვება უსაფრთხოა — idempotent-ია.
echo  Healthy API/Vite აღარ გადატვირთდება, მხოლოდ browser გაიხსნება.
echo ==============================================================
pause
