<#
Sets up the headless export CLI next to an installed HaizFlow.

  powershell -ExecutionPolicy Bypass -File scripts\setup-export-cli.ps1 `
    -HaizflowHome "C:\Users\ADMIN\AppData\Local\Programs\HaizFlow\runtime"

Creates .venv with Python 3.13 (installs it with winget if missing), installs
the hash-locked runtime dependencies, then runs `list` against the installed
data. It changes no system settings and does not modify the installed app.
#>
param(
    [Parameter(Mandatory = $true)][string]$HaizflowHome,
    [string]$Root = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"
$lock = Join-Path $Root "requirements-lock-py313-win64.txt"
$venv = Join-Path $Root ".venv"
$venvPython = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path $HaizflowHome)) { throw "HaizFlow runtime folder not found: $HaizflowHome" }
if (-not (Test-Path $lock)) { throw "Lock file missing: $lock" }

function Find-Python313 {
    foreach ($candidate in @("py -3.13", "python3.13", "python")) {
        try {
            $parts = $candidate.Split(" ")
            $version = & $parts[0] $parts[1..($parts.Length - 1)] -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
            if ($LASTEXITCODE -eq 0 -and $version -eq "3.13") { return $parts }
        } catch { }
    }
    return $null
}

$python = Find-Python313
if (-not $python) {
    Write-Host "Python 3.13 not found. Installing with winget..."
    winget install --id Python.Python.3.13 --silent --accept-package-agreements --accept-source-agreements
    $python = Find-Python313
    if (-not $python) { throw "Python 3.13 is still unavailable. Open a new PowerShell window and rerun this script." }
}

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating virtual environment in $venv"
    & $python[0] $python[1..($python.Length - 1)] -m venv $venv
}

Write-Host "Installing locked dependencies (this can take a while)..."
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install --require-hashes -r $lock

# Only this process sees these; no permanent user or system environment change.
$env:HAIZFLOW_HOME = $HaizflowHome
$env:RUNTIME_DATA_DIR = Join-Path $HaizflowHome "data"
$env:PYTHONPATH = Join-Path $Root "src"

Write-Host "Checking the CLI against the installed HaizFlow data..."
& $venvPython -m haizflow.services.export_cli list
Write-Host ""
Write-Host "Done. To use the CLI in this window, run:"
Write-Host "  `$env:HAIZFLOW_HOME='$HaizflowHome'; `$env:PYTHONPATH='$(Join-Path $Root 'src')'; $venvPython -m haizflow.services.export_cli list"
