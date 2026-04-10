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

echo INFO: Releasing ports 5173-5177 if busy...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ports = 5173..5177; $conns = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $ports -contains $_.LocalPort }; $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique; if ($pids) { Stop-Process -Id $pids -Force -ErrorAction SilentlyContinue }"

echo Starting Vite (no data refresh)...
start "Dashboard Server" "%ROOT%rs-dashboard\_vite-dev.bat"
echo Open: http://127.0.0.1:5173/
pause
