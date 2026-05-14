#requires -Version 5.1
<#
.SYNOPSIS
    Daily/weekly backup of critical financial-dashboard data to OneDrive.

.DESCRIPTION
    Creates date-stamped snapshots in OneDrive so a hard-drive failure or
    accidental deletion does not destroy financial history.

    Daily snapshot (~36 MB):
      - Financial_Analysis JSON/CSV/MD configs + manual journals
      - Financial_Analysis/cache parquets (bank data)
      - .env* credential files
      - Claude memory folder

    Weekly snapshot (Sundays, ~150 MB extra):
      - Full Financial_Analysis (bank XLSX + waybills + invoices)
      - EXCLUDES მეგაპლიუსის არქიტექტურა (2.46 GB MegaPlus ZIPs — restorable from SQL backups)

    Retention:
      - 7 daily snapshots
      - 4 weekly snapshots

.NOTES
    Runs as a Windows Scheduled Task. Logs to OneDrive\backups\financial-dashboard\_logs\.
    Idempotent — safe to run multiple times per day.
#>

$ErrorActionPreference = 'Stop'

# ============================================================================
# CONFIG
# ============================================================================
$ProjectRoot  = 'C:\financial-dashboard'
$MemoryPath   = 'C:\Users\tengiz\.claude\projects\C--financial-dashboard\memory'
$BackupRoot   = 'C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\backups\financial-dashboard'

$DateStamp    = Get-Date -Format 'yyyy-MM-dd'
$IsWeeklyDay  = (Get-Date).DayOfWeek -eq 'Sunday'

$DailyDir     = Join-Path $BackupRoot "daily\$DateStamp"
$WeeklyDir    = Join-Path $BackupRoot "weekly\$DateStamp"
$LogDir       = Join-Path $BackupRoot '_logs'
$LogFile      = Join-Path $LogDir   "backup_$DateStamp.log"
$StatusFile   = Join-Path $BackupRoot '_status.txt'

# ============================================================================
# HELPERS
# ============================================================================
function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [$Level] $Message"
    Write-Output $line
    Add-Content -Path $LogFile -Value $line -Encoding utf8
}

function Invoke-Robocopy {
    param(
        [string]$Source,
        [string]$Dest,
        [string[]]$Files = @(),
        [string[]]$ExcludeDirs = @(),
        [switch]$Recurse
    )
    $args = @($Source, $Dest)
    $args += $Files
    if ($Recurse) { $args += '/E' }
    $args += @('/R:2', '/W:5', '/NP', '/NDL', '/NJH', '/NJS')
    if ($ExcludeDirs.Count -gt 0) {
        $args += '/XD'
        $args += $ExcludeDirs
    }
    & robocopy @args | Out-Null
    # Robocopy exit codes 0-7 are success (8+ are errors)
    if ($LASTEXITCODE -ge 8) {
        throw "robocopy failed: $Source -> $Dest (exit $LASTEXITCODE)"
    }
}

# ============================================================================
# SETUP
# ============================================================================
New-Item -ItemType Directory -Force -Path $DailyDir | Out-Null
New-Item -ItemType Directory -Force -Path $LogDir   | Out-Null

Write-Log "Backup started: $DateStamp (weekly=$IsWeeklyDay)"

# ============================================================================
# DAILY — small critical files
# ============================================================================
try {
    # 1. Financial_Analysis JSON/CSV/MD at top level (manual journals + configs)
    Invoke-Robocopy `
        "$ProjectRoot\Financial_Analysis" `
        "$DailyDir\Financial_Analysis" `
        -Files @('*.json', '*.csv', '*.md', '*.xlsx') `
        -ExcludeDirs @('cache', '_backups', '_samples')
    Write-Log "  [OK] Financial_Analysis top-level configs"

    # 2. Cache parquets — bank data (recursive: bog/, tbc/, rsge/ subfolders)
    if (Test-Path "$ProjectRoot\Financial_Analysis\cache") {
        Invoke-Robocopy `
            "$ProjectRoot\Financial_Analysis\cache" `
            "$DailyDir\Financial_Analysis\cache" `
            -Files @('*.*') `
            -Recurse
        Write-Log "  [OK] cache parquets"
    }

    # 3. .env* files
    $envFiles = Get-ChildItem $ProjectRoot -Filter '.env*' -File -Force -ErrorAction SilentlyContinue
    if ($envFiles) {
        foreach ($f in $envFiles) {
            Copy-Item -Path $f.FullName -Destination $DailyDir -Force
        }
        Write-Log "  [OK] $($envFiles.Count) .env files"
    }

    # 4. Claude memory
    if (Test-Path $MemoryPath) {
        Invoke-Robocopy `
            $MemoryPath `
            "$DailyDir\memory" `
            -Files @('*.*')
        Write-Log "  [OK] Claude memory"
    }

    $dailySize = [math]::Round(((Get-ChildItem $DailyDir -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum / 1MB), 2)
    Write-Log "Daily snapshot complete: $DailyDir ($dailySize MB)"
} catch {
    Write-Log "DAILY BACKUP FAILED: $_" 'ERROR'
    Set-Content -Path $StatusFile -Value "FAIL ${DateStamp}: $_" -Encoding utf8
    throw
}

# ============================================================================
# WEEKLY — full Financial_Analysis (Sundays only)
# ============================================================================
if ($IsWeeklyDay) {
    try {
        New-Item -ItemType Directory -Force -Path $WeeklyDir | Out-Null

        # Full Financial_Analysis EXCEPT MegaPlus ZIPs (restorable from SQL)
        Invoke-Robocopy `
            "$ProjectRoot\Financial_Analysis" `
            "$WeeklyDir\Financial_Analysis" `
            -Files @('*.*') `
            -ExcludeDirs @('მეგაპლიუსის არქიტექტურა') `
            -Recurse

        $weeklySize = [math]::Round(((Get-ChildItem $WeeklyDir -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum / 1MB), 2)
        Write-Log "Weekly snapshot complete: $WeeklyDir ($weeklySize MB)"
    } catch {
        Write-Log "WEEKLY BACKUP FAILED: $_" 'ERROR'
        Set-Content -Path $StatusFile -Value "WEEKLY FAIL ${DateStamp}: $_" -Encoding utf8
        throw
    }
}

# ============================================================================
# RETENTION — clean up old snapshots
# ============================================================================
function Remove-OldSnapshots {
    param([string]$Path, [int]$Keep)
    if (-not (Test-Path $Path)) { return }
    $old = Get-ChildItem $Path -Directory | Sort-Object Name -Descending | Select-Object -Skip $Keep
    foreach ($d in $old) {
        Remove-Item $d.FullName -Recurse -Force
        Write-Log "  [PRUNED] $($d.Name)"
    }
}

Remove-OldSnapshots -Path (Join-Path $BackupRoot 'daily')  -Keep 7
Remove-OldSnapshots -Path (Join-Path $BackupRoot 'weekly') -Keep 4

# Trim log files older than 30 days
Get-ChildItem $LogDir -Filter 'backup_*.log' | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | Remove-Item -Force

# ============================================================================
# STATUS
# ============================================================================
Set-Content -Path $StatusFile -Value "OK $DateStamp $(Get-Date -Format 'HH:mm:ss')" -Encoding utf8
Write-Log "All operations complete"
