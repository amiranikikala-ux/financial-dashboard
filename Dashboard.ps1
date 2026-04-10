# PowerShell:  .\Dashboard.ps1
# ExecutionPolicy: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
cmd.exe /c "Run_Dashboard.bat"
