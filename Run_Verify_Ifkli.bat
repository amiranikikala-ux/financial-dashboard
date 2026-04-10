@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [შეცდომა] venv ვერ მოიძებნა: %~dp0
    pause
    exit /b 1
)

set "PY=%~dp0venv\Scripts\python.exe"

echo ============================================================
echo შემოწმება: იფქლი ^(საგადასახადო ID 200179118^)
echo ============================================================
echo.
"%PY%" verify_supplier_reconciliation.py 200179118
echo.
echo ------------------------------------------------------------
echo BOG+TBC დეტალურად:
"%PY%" debug_ifkli.py
echo.
pause
