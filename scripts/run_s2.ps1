# S2 -- Reproduce R2 (deterministic checks vs behavioural monitor)
# ASCII only on purpose: avoids PowerShell encoding issues on Windows.
#
# Usage (from repo root):
#     powershell -ExecutionPolicy Bypass -File scripts\run_s2.ps1
#     powershell -ExecutionPolicy Bypass -File scripts\run_s2.ps1 -Optional
#
# Every command is logged to logs\S2_*.log and echoed to the console.

param(
    [switch]$Optional
)

$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

New-Item -ItemType Directory -Force logs | Out-Null
$py = Join-Path $repo "..\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    throw "venv python not found at $py"
}

Write-Host "== HEAD ==" -ForegroundColor Cyan
git log --oneline -1

Write-Host ""
Write-Host "== pre-run git status (results/tables) ==" -ForegroundColor Cyan
git status --porcelain -- results/tables | Tee-Object -FilePath logs\S2_git_before.txt

# --- 1. the arm table (cold + ext) -----------------------------------------
Write-Host ""
Write-Host "== [1/3] verification_vs_monitor.csv ==" -ForegroundColor Cyan
& $py -m derail.verify.run_verification_study *>&1 | Tee-Object -FilePath logs\S2_vs_monitor.log

# --- 2. cold corpus, episode level ----------------------------------------
Write-Host ""
Write-Host "== [2/3] verification_cold.csv ==" -ForegroundColor Cyan
& $py -m derail.verify.run_verification_study --holdout organic_demo7b_cold *>&1 |
    Tee-Object -FilePath logs\S2_cold.log

# --- 3. held-out corpus, 120 episodes, checks frozen ----------------------
Write-Host ""
Write-Host "== [3/3] verification_holdout.csv ==" -ForegroundColor Cyan
& $py -m derail.verify.run_verification_study --holdout organic_demo7b_holdout *>&1 |
    Tee-Object -FilePath logs\S2_holdout.log

if ($Optional) {
    Write-Host ""
    Write-Host "== [opt] provoked corpus ==" -ForegroundColor Cyan
    & $py -m derail.verify.run_verification_study --holdout organic_demo7b_provoked *>&1 |
        Tee-Object -FilePath logs\S2_provoked.log

    Write-Host ""
    Write-Host "== [opt] tool_contract coverage ==" -ForegroundColor Cyan
    & $py -m derail.verify.run_verification_study --contract-coverage *>&1 |
        Tee-Object -FilePath logs\S2_contract.log
}

Write-Host ""
Write-Host "== post-run git status (results/tables) ==" -ForegroundColor Cyan
git status --porcelain -- results/tables | Tee-Object -FilePath logs\S2_git_after.txt

Write-Host ""
Write-Host "== git diff --stat ==" -ForegroundColor Cyan
git diff --stat -- results/tables

# Windows PowerShell 5.1's Tee-Object has no -Encoding switch and always writes
# UTF-16LE. git then treats the log as binary and GitHub renders it as
# "Binary file not shown" -- which defeats the purpose of committing the
# evidence. Re-encode anything carrying a UTF-16 BOM in place.
Get-ChildItem logs\S2_*.txt -ErrorAction SilentlyContinue | ForEach-Object {
    $b = [System.IO.File]::ReadAllBytes($_.FullName)
    if ($b.Length -ge 2 -and $b[0] -eq 0xFF -and $b[1] -eq 0xFE) {
        $t = [System.Text.Encoding]::Unicode.GetString($b, 2, $b.Length - 2)
        [System.IO.File]::WriteAllText($_.FullName, $t, (New-Object System.Text.UTF8Encoding $false))
        Write-Host ("  re-encoded {0} to utf-8" -f $_.Name) -ForegroundColor DarkGray
    }
}

Write-Host ""
Write-Host "Done. If 'git diff --stat' printed nothing above, the tables were rebuilt byte-identically." -ForegroundColor Green
