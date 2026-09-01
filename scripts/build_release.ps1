param(
    [string]$Tag = ""
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repositoryRoot

$python = Join-Path $repositoryRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Create the Python 3.13 environment before building."
}

if ($Tag) {
    & $python scripts/check_version.py $Tag
    if ($LASTEXITCODE -ne 0) { throw "Version validation failed." }
}

& "$PSScriptRoot\fetch_unity_capture.ps1"
& $python -m pytest
if ($LASTEXITCODE -ne 0) { throw "Tests failed." }
& $python -m PyInstaller packaging/YFPhoneCam.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }

$frozenExecutable = Join-Path $repositoryRoot "dist\YFPhoneCam\YFPhoneCam.exe"
$previousQtPlatform = $env:QT_QPA_PLATFORM
try {
    $env:QT_QPA_PLATFORM = "offscreen"
    $smokeArguments = @{
        FilePath = $frozenExecutable
        ArgumentList = "--gui-smoke-test"
        WorkingDirectory = Split-Path -Parent $frozenExecutable
        WindowStyle = "Hidden"
        Wait = $true
        PassThru = $true
    }
    $smokeTest = Start-Process @smokeArguments
    if ($smokeTest.ExitCode -ne 0) {
        throw "Frozen GUI smoke test failed with exit code $($smokeTest.ExitCode)."
    }
}
finally {
    $env:QT_QPA_PLATFORM = $previousQtPlatform
}
Write-Host "Frozen GUI smoke test passed."

$version = & $python -c "from yfphonecam.version import __version__; print(__version__)"
$isccCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 was not found." }
& $iscc "/DAppVersion=$version" "/DSourceRoot=$repositoryRoot" installer/YFPhoneCam.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed." }

$installer = Join-Path $repositoryRoot "installer\output\YFPhoneCam-Setup-$version.exe"
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $installer).Hash.ToLowerInvariant()
$checksumPath = "$installer.sha256"
Set-Content -LiteralPath $checksumPath -Encoding ascii -Value "$hash  $(Split-Path -Leaf $installer)"
& $python scripts/generate_sbom.py "installer/output/YFPhoneCam-$version.cdx.json"
Write-Host "Release artifacts are in installer\output"
