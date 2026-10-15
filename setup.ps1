function Fail($message) {
    Write-Host "`n========================================" -ForegroundColor Red
    Write-Host "ERROR: $message" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "`nWe recommend using conda instead:" -ForegroundColor Yellow
    Write-Host "  1. Install Miniconda from: https://www.anaconda.com/docs/getting-started/miniconda/install" -ForegroundColor White
    Write-Host "  2. Run: .\setup-conda.ps1" -ForegroundColor White
    Write-Host "`nPress any key to exit..." -ForegroundColor Gray
    try { $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") } catch {}
    exit 1
}

# Find a Python 3.11+ interpreter. On Windows, `python` is often missing from
# the PATH (python.org's installer leaves that box unchecked by default) or is
# the Microsoft Store placeholder, so try the `py` launcher first.
$versionCheck = 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'
$candidates = 'py -3.13', 'py -3.12', 'py -3.11', 'py -3', 'python', 'python3'
$pyExe = $null
$pyArgs = @()
foreach ($candidate in $candidates) {
    $parts = $candidate -split ' '
    $exe = $parts[0]
    $exeArgs = @($parts | Select-Object -Skip 1)
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
    & $exe @exeArgs -c $versionCheck 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        $pyExe = $exe
        $pyArgs = $exeArgs
        break
    }
}
if (-not $pyExe) {
    Fail ("Python 3.11 or newer was not found. Install Python 3.13 from " +
          "https://www.python.org/downloads/ and try again.")
}
Write-Host "Using: $pyExe $pyArgs" -ForegroundColor Cyan

# Create a virtual environment
Write-Host "Creating virtual environment..." -ForegroundColor Green
& $pyExe @pyArgs -m venv venv
if ($LASTEXITCODE -ne 0) { Fail "Creating the virtual environment failed." }

# Call the venv's own python directly rather than activating the venv, so every
# install below is guaranteed to land in the venv and not the global Python.
$venvPython = "venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) { Fail "The virtual environment was not created correctly." }

# Upgrade pip, setuptools, and wheel
Write-Host "Upgrading pip, setuptools, and wheel..." -ForegroundColor Green
& $venvPython -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) { Fail "Upgrading pip failed." }

# Install GDAL-dependent packages (rasterio pulls in GDAL) from pre-compiled wheels
Write-Host "`nInstalling GDAL-dependent packages..." -ForegroundColor Green
Write-Host "Note: Using pre-compiled wheels to avoid GDAL compilation issues on Windows" -ForegroundColor Yellow
Write-Host "Installing rasterio..." -ForegroundColor Cyan
& $venvPython -m pip install rasterio
if ($LASTEXITCODE -ne 0) {
    Fail ("Failed to install rasterio. This is a common issue on Windows. You can also try " +
          "wheels from https://github.com/cgohlke/geospatial-wheels/")
}

# Install remaining dependencies, minus the geospatial packages handled separately
Write-Host "`nInstalling remaining dependencies from requirements.txt..." -ForegroundColor Green
Get-Content requirements.txt | Where-Object {
    $_ -notmatch "^\s*rasterio" -and
    $_ -notmatch "^\s*geopandas" -and
    $_ -notmatch "^\s*cartopy" -and
    $_ -notmatch "^\s*rasterstats" -and
    $_ -notmatch "^\s*#" -and
    $_.Trim() -ne ""
} | Set-Content requirements_temp.txt

& $venvPython -m pip install -r requirements_temp.txt
$reqStatus = $LASTEXITCODE
Remove-Item requirements_temp.txt
if ($reqStatus -ne 0) { Fail "Installing packages from requirements.txt failed." }

Write-Host "Installing remaining geospatial packages..." -ForegroundColor Cyan
& $venvPython -m pip install geopandas cartopy rasterstats
if ($LASTEXITCODE -ne 0) { Fail "Installing geopandas, cartopy, or rasterstats failed." }

Write-Host "`nInstalling Jupyter kernel..." -ForegroundColor Green
& $venvPython -m ipykernel install --user --name=venv --display-name "Python (venv)"
if ($LASTEXITCODE -ne 0) { Fail "Installing the Jupyter kernel failed." }

# Launch Jupyter Lab with the specified notebook
Write-Host "`nLaunching Jupyter Lab..." -ForegroundColor Green
Write-Host "The notebook will open in your default browser." -ForegroundColor Cyan
& $venvPython -m jupyter lab notebooks\1_exploration.ipynb