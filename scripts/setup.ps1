param([string]$PythonExe = "py")
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path $PSScriptRoot -Parent
$environmentPath = Join-Path $projectRoot ".venv-analysis"
$environmentPython = Join-Path $environmentPath "Scripts\python.exe"
Push-Location $projectRoot
try {
    if (-not (Test-Path -LiteralPath $environmentPath)) {
        if ($PythonExe -eq "py") {
            & $PythonExe -3.12 -m venv $environmentPath
        } else {
            & $PythonExe -m venv $environmentPath
        }
        if ($LASTEXITCODE -ne 0) { throw "Could not create Python environment" }
    }
    & $environmentPython -c "import sys; assert sys.version_info[:2] == (3, 12), 'Python 3.12 required'; print(sys.executable)"
    if ($LASTEXITCODE -ne 0) { throw "Existing .venv-analysis is unusable. Preserve it and choose a working Python 3.12 installation." }
    & $environmentPython -m pip install -r requirements-lock.txt
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
    & $environmentPython -m pip install --no-deps --no-build-isolation -e .
    if ($LASTEXITCODE -ne 0) { throw "Project installation failed" }
    & $environmentPython -m pip check
    if ($LASTEXITCODE -ne 0) { throw "Dependency consistency check failed" }
} finally {
    Pop-Location
}
