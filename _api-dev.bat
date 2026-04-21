@echo off
setlocal
set "ROOT=%~dp0"
for %%I in ("%ROOT%..") do set "WORKSPACE_ROOT=%%~fI"
set "PYTHON_BIN=%WORKSPACE_ROOT%\venv\Scripts\python.exe"
set PYTHONUNBUFFERED=1
cd /d "%ROOT%"
if not exist "%PYTHON_BIN%" (
  echo ERROR: Python venv was not found:
  echo   %PYTHON_BIN%
  pause
  exit /b 1
)
echo Dashboard API: http://127.0.0.1:8000/
echo Close this window to stop the server.
echo.
"%PYTHON_BIN%" -u server.py
if errorlevel 1 (
  echo.
  echo ERROR: server.py failed.
  pause
)
endlocal
