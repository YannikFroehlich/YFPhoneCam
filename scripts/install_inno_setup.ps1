$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$version = "6.7.3"
$expectedHash = "9c73c3bae7ed48d44112a0f48e66742c00090bdb5bef71d9d3c056c66e97b732"
$url = "https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-$version.exe"
$temporary = Join-Path ([System.IO.Path]::GetTempPath()) "yfphonecam-innosetup-$version.exe"

try {
    Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $temporary -MaximumRedirection 5
    $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $temporary).Hash.ToLowerInvariant()
    if ($actualHash -ne $expectedHash) {
        throw "Inno Setup SHA-256 mismatch (expected $expectedHash, got $actualHash)"
    }
    $signature = Get-AuthenticodeSignature -LiteralPath $temporary
    if ($signature.Status -ne "Valid" -or $signature.SignerCertificate.Subject -notlike "CN=Pyrsys B.V.*") {
        throw "The Inno Setup Authenticode signature is not valid or has an unexpected publisher."
    }
    $process = Start-Process -FilePath $temporary `
        -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/ALLUSERS" `
        -PassThru -Wait -WindowStyle Hidden
    if ($process.ExitCode -ne 0) {
        throw "Inno Setup installation failed with exit code $($process.ExitCode)."
    }
}
finally {
    Remove-Item -Force -ErrorAction SilentlyContinue -LiteralPath $temporary
}
