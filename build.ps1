# Build script for TimeAudit.exe
#
# Produces a single-file Windows executable at dist\TimeAudit.exe that bundles
# the Python backend, the statically-built frontend, the reference workbook and
# the embedded .env. Run it from the project root:
#
#     powershell -ExecutionPolicy Bypass -File build.ps1
#
# Prerequisites (already set up once via `npm run setup`):
#   - backend\.venv          (Python virtual environment with requirements)
#   - frontend\node_modules  (frontend dependencies installed)
#   - PyInstaller installed in the venv

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

$venvPython = Join-Path $root "backend\.venv\Scripts\python.exe"
$pyinstaller = Join-Path $root "backend\.venv\Scripts\pyinstaller.exe"

Write-Host "==> Checking prerequisites..." -ForegroundColor Cyan
if (-not (Test-Path $venvPython)) {
    throw "Python venv not found at $venvPython. Run 'npm run setup' first."
}
if (-not (Test-Path $pyinstaller)) {
    Write-Host "PyInstaller not found in venv. Installing..." -ForegroundColor Yellow
    & $venvPython -m pip install pyinstaller
}

# A running TimeAudit.exe locks the output file and breaks the build.
$running = Get-Process TimeAudit -ErrorAction SilentlyContinue
if ($running) {
    throw "TimeAudit.exe is currently running. Close it and run this script again."
}

Write-Host "==> Building frontend (static export)..." -ForegroundColor Cyan
Push-Location (Join-Path $root "frontend")
try {
    & npm run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
}
finally {
    Pop-Location
}

Write-Host "==> Packaging with PyInstaller..." -ForegroundColor Cyan
& $pyinstaller TimeAudit.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

$exe = Join-Path $root "dist\TimeAudit.exe"
if (Test-Path $exe) {
    $sizeMb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
    Write-Host "==> Done. Built dist\TimeAudit.exe ($sizeMb MB)" -ForegroundColor Green
}
else {
    throw "Build finished but $exe was not found."
}
