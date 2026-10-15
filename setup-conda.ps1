$envName = "sif-arset"

function Fail($message) {
    Write-Host "`nERROR: $message" -ForegroundColor Red
    Write-Host "`nPress any key to exit..." -ForegroundColor Gray
    try { $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") } catch {}
    exit 1
}

# Locate conda. In a plain PowerShell window conda is often not on the PATH
# (the Miniconda installer doesn't add it by default, and `conda init powershell`
# may never have been run), so also check the usual install locations.
$conda = $env:CONDA_EXE
if (-not $conda) {
    $cmd = Get-Command conda.exe -ErrorAction SilentlyContinue
    if ($cmd) { $conda = $cmd.Source }
}
if (-not $conda) {
    $candidates = @(
        "$env:USERPROFILE\miniconda3\Scripts\conda.exe",
        "$env:USERPROFILE\anaconda3\Scripts\conda.exe",
        "$env:LOCALAPPDATA\miniconda3\Scripts\conda.exe",
        "$env:LOCALAPPDATA\anaconda3\Scripts\conda.exe",
        "$env:ProgramData\miniconda3\Scripts\conda.exe",
        "$env:ProgramData\anaconda3\Scripts\conda.exe"
    )
    $conda = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $conda) {
    Fail ("Could not find conda. Install Miniconda from " +
          "https://www.anaconda.com/docs/getting-started/miniconda/install, " +
          "then run this script from the 'Anaconda PowerShell Prompt' in the Start menu.")
}
Write-Host "Using conda at $conda" -ForegroundColor Cyan

# Create the environment, or update it if an earlier run already created it.
$envExists = (& $conda env list) | Where-Object { ($_ -split '\s+')[0] -eq $envName }
if ($envExists) {
    Write-Host "Environment '$envName' already exists; updating it from environment.yml..." -ForegroundColor Green
    & $conda env update -n $envName -f environment.yml
} else {
    Write-Host "Creating conda environment '$envName'..." -ForegroundColor Green
    & $conda env create -f environment.yml
}
if ($LASTEXITCODE -ne 0) { Fail "Creating the conda environment failed (see the messages above)." }

# Run commands inside the environment with `conda run` instead of activating it,
# since `conda activate` only works in PowerShell after `conda init powershell`.
Write-Host "`nInstalling Jupyter kernel..." -ForegroundColor Green
& $conda run -n $envName python -m ipykernel install --user --name=$envName --display-name "Python ($envName)"
if ($LASTEXITCODE -ne 0) { Fail "Installing the Jupyter kernel failed." }

Write-Host "`nLaunching Jupyter Lab..." -ForegroundColor Green
Write-Host "The notebook will open in your default browser." -ForegroundColor Cyan
& $conda run -n $envName --no-capture-output jupyter lab notebooks\1_exploration.ipynb