# S3 -- compare the rerun against the BASELINE commit, then recompute independently
# ASCII only on purpose: avoids PowerShell encoding issues on Windows.
#
# Why a baseline commit and not HEAD:
#   after the rerun we commit the new artifacts, so HEAD == "this run".
#   Comparing against HEAD would compare the run with itself and always pass.
#   Always compare against the commit that shipped the published numbers.
#
# Usage (from repo root):
#     powershell -ExecutionPolicy Bypass -File scripts\run_s3.ps1
#     powershell -ExecutionPolicy Bypass -File scripts\run_s3.ps1 -Base 1b3e07fe

param(
    [string]$Base = "1b3e07fe"
)

$ErrorActionPreference = "Stop"

# python detects a pipe and falls back to cp936, which cannot encode the tick marks
# the analysis scripts print; force UTF-8 so they do not die halfway through.
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

# python emits UTF-8 (see below); without this the PS 5.1 host decodes it as cp936
# and Tee-Object writes mojibake into the logs.
try {
    [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
    $OutputEncoding = New-Object System.Text.UTF8Encoding $false
} catch { }

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

New-Item -ItemType Directory -Force logs | Out-Null
$py = Join-Path $repo "..\.venv\Scripts\python.exe"

$baseFull = (git rev-parse --short $Base 2>$null)
if (-not $baseFull) {
    Write-Host ("ERROR: baseline commit '{0}' not found. Try: git log --oneline -5" -f $Base) -ForegroundColor Red
    exit 2
}

Write-Host ("== 3.0 baseline {0} vs HEAD {1} ==" -f $baseFull, (git rev-parse --short HEAD)) -ForegroundColor Cyan
git status --porcelain | Tee-Object -FilePath logs\S3_git_status.txt

Write-Host ""
Write-Host "== 3.1 tables and figures, diff vs baseline ==" -ForegroundColor Cyan
git diff --stat $baseFull -- results/tables results/figures | Tee-Object -FilePath logs\S3_git_diff.txt
Write-Host "(run_meta.json is expected to differ: it records machine info)"

Write-Host ""
Write-Host "== 3.2 R1: byte-level and metric-level ==" -ForegroundColor Cyan
& $py analysis\compare_r1.py $baseFull *>&1 | Tee-Object -FilePath logs\S3_compare_r1.txt
$r1 = $LASTEXITCODE

Write-Host ""
Write-Host "== 3.3 R2: independent recomputation ==" -ForegroundColor Cyan
& $py analysis\recompute_r2.py *>&1 | Tee-Object -FilePath logs\S3_recompute_r2.txt
$r2 = $LASTEXITCODE

# Windows PowerShell 5.1's Tee-Object has no -Encoding switch and always writes
# UTF-16LE. git then treats the log as binary and GitHub renders it as
# "Binary file not shown" -- which defeats the purpose of committing the
# evidence. Re-encode anything carrying a UTF-16 BOM in place.
Get-ChildItem logs\S3_*.txt -ErrorAction SilentlyContinue | ForEach-Object {
    $b = [System.IO.File]::ReadAllBytes($_.FullName)
    if ($b.Length -ge 2 -and $b[0] -eq 0xFF -and $b[1] -eq 0xFE) {
        $t = [System.Text.Encoding]::Unicode.GetString($b, 2, $b.Length - 2)
        [System.IO.File]::WriteAllText($_.FullName, $t, (New-Object System.Text.UTF8Encoding $false))
        Write-Host ("  re-encoded {0} to utf-8" -f $_.Name) -ForegroundColor DarkGray
    }
}

Write-Host ""
Write-Host "== summary ==" -ForegroundColor Cyan
Write-Host ("baseline = {0}" -f $baseFull)
Write-Host ("compare_r1 exit = {0}" -f $r1)
Write-Host ("recompute_r2 exit = {0}" -f $r2)
if (($r1 -eq 0) -and ($r2 -eq 0)) {
    Write-Host "Both checks passed." -ForegroundColor Green
} else {
    Write-Host "At least one check reported a difference -- read the logs before concluding." -ForegroundColor Yellow
}
