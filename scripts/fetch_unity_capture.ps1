$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $repositoryRoot "vendor\unitycapture.json"
$targetDirectory = Join-Path $repositoryRoot "vendor\UnityCapture"
$manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json

New-Item -ItemType Directory -Force -Path $targetDirectory | Out-Null

foreach ($entry in $manifest.files.PSObject.Properties) {
    $fileName = $entry.Name
    $expectedHash = [string]$entry.Value
    $target = Join-Path $targetDirectory $fileName
    $url = "https://raw.githubusercontent.com/schellingb/UnityCapture/$($manifest.commit)/Install/$fileName"
    $temporary = "$target.download"

    try {
        Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $temporary -MaximumRedirection 3
        $length = (Get-Item -LiteralPath $temporary).Length
        if ($length -lt 50000 -or $length -gt 1048576) {
            throw "Unexpected Unity Capture file size for $fileName: $length bytes"
        }
        $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $temporary).Hash.ToLowerInvariant()
        if ($actualHash -ne $expectedHash.ToLowerInvariant()) {
            throw "SHA-256 mismatch for $fileName (expected $expectedHash, got $actualHash)"
        }
        Move-Item -Force -LiteralPath $temporary -Destination $target
        Write-Host "Verified $fileName ($actualHash)"
    }
    finally {
        Remove-Item -Force -ErrorAction SilentlyContinue -LiteralPath $temporary
    }
}
