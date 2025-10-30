# Test version of setup.ps1 - does not launch Jupyter Lab
# Used for CI/CD testing

# Create a virtual environment
Write-Host "Creating virtual environment..." -ForegroundColor Green
python -m venv venv

# Activate the virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Green
venv\Scripts\Activate

# Upgrade pip, setuptools, and wheel
Write-Host "Upgrading pip, setuptools, and wheel..." -ForegroundColor Green
python -m pip install --upgrade pip setuptools wheel

# Install GDAL-dependent packages (rasterio, geopandas, cartopy) from wheels
Write-Host "`nInstalling GDAL-dependent packages..." -ForegroundColor Green
Write-Host "Note: Using pre-compiled wheels to avoid GDAL compilation issues on Windows" -ForegroundColor Yellow

# Try installing rasterio first (it will pull in GDAL as a dependency)
$gdalPackages = @("rasterio")
$success = $true

foreach ($package in $gdalPackages) {
    Write-Host "Installing $package..." -ForegroundColor Cyan
    python -m pip install $package 2>&1 | Tee-Object -Variable output
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Warning: Failed to install $package from PyPI" -ForegroundColor Yellow
        $success = $false
        break
    }
}

if (-not $success) {
    Write-Host "`n========================================" -ForegroundColor Red
    Write-Host "ERROR: Failed to install GDAL-dependent packages" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "`nThis is a common issue on Windows. We recommend using conda instead:" -ForegroundColor Yellow
    Write-Host "  1. Install Miniconda from: https://docs.conda.io/en/latest/miniconda.html" -ForegroundColor White
    Write-Host "  2. Run: .\setup-conda.ps1" -ForegroundColor White
    Write-Host "`nAlternatively, you can try installing from Christoph Gohlke's wheel collection:" -ForegroundColor Yellow
    Write-Host "  https://github.com/cgohlke/geospatial-wheels/" -ForegroundColor White
    exit 1
}

# Install remaining dependencies
Write-Host "`nInstalling remaining dependencies from requirements.txt..." -ForegroundColor Green
# Create a temporary requirements file without the GDAL-related packages
Get-Content requirements.txt | Where-Object {
    $_ -notmatch "^\s*rasterio" -and
    $_ -notmatch "^\s*geopandas" -and
    $_ -notmatch "^\s*cartopy" -and
    $_ -notmatch "^\s*rasterstats" -and
    $_ -notmatch "^\s*#" -and
    $_.Trim() -ne ""
} | Set-Content requirements_temp.txt

pip install -r requirements_temp.txt

# Now install the remaining GDAL-dependent packages
Write-Host "Installing remaining geospatial packages..." -ForegroundColor Cyan
pip install geopandas cartopy rasterstats

# Clean up temp file
Remove-Item requirements_temp.txt

Write-Host "`nInstalling Jupyter kernel..." -ForegroundColor Green
python -m ipykernel install --user --name=venv --display-name "Python (venv)"

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "Setup completed successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "`nTo launch Jupyter Lab, run:" -ForegroundColor Cyan
Write-Host "  jupyter lab notebooks\1_exploration.ipynb" -ForegroundColor White
