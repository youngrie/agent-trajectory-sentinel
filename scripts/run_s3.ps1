# S3 -- compare the rerun against the committed artifacts, then recompute independently
# ASCII only on purpose: avoids PowerShell encoding issues on Windows.
#
# Usage (from repo root):
#     powershell -ExecutionPolicy Bypass -File scripts\run_s3.ps1

$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

New-Item -ItemType Directory -Force logs | Out-Null
$py = Join-Path $repo "..\.venv\Scripts\python.exe"

Write-Host "== 3.0 what changed, overall ==" -ForegroundColor Cyan
git status --porcelain | Tee-Object -FilePath logs\S3_git_status.txt

Write-Host ""
Write-Host "== 3.1 tables and figures ==" -ForegroundColor Cyan
git diff --stat -- results/tables results/figures | Tee-Object -FilePath logs\S3_git_diff.txt
Write-Host "(run_meta.json is expected to differ: it records machine info)"

Write-Host ""
Write-Host "== 3.2 R1: byte-level and metric-level ==" -ForegroundColor Cyan
& $py analysis\compare_r1.py *>&1 | Tee-Object -FilePath logs\S3_compare_r1.txt
$r1 = $LASTEXITCODE

Write-Host ""
Write-Host "== 3.3 R2: independent recomputation ==" -ForegroundColor Cyan
& $py analysis\recompute_r2.py *>&1 | Tee-Object -FilePath logs\S3_recompute_r2.txt
$r2 = $LASTEXITCODE

Write-Host ""
Write-Host "== summary ==" -ForegroundColor Cyan
Write-Host ("compare_r1 exit = {0}" -f $r1)
Write-Host ("recompute_r2 exit = {0}" -f $r2)
if (($r1 -eq 0) -and ($r2 -eq 0)) {
    Write-Host "Both checks passed." -ForegroundColor Green
} else {
    Write-Host "At least one check reported a difference -- read the logs before concluding." -ForegroundColor Yellow
}
