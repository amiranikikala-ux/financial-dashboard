@echo off
setlocal
cd /d "%~dp0"
echo Vite dev server: http://127.0.0.1:5173/
echo Close this window to stop the server.
echo.
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort --open
if errorlevel 1 (
  echo.
  echo ERROR: npm run dev failed. Is Node.js installed?
  pause
)
endlocal
