$ErrorActionPreference = "Stop"

$files = [ordered]@{
    "CRYPTO_PY"   = "rzservice/crypto.py"
    "ARCHIVE_PY"  = "rzservice/archive.py"
    "SELFTEST_PY" = "selftest.py"
}

foreach ($name in $files.Keys) {
    $path = $files[$name]
    if (-not (Test-Path -LiteralPath $path)) {
        Write-Error "File not found: $path"
    }
    $b64 = [Convert]::ToBase64String(
        [IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $path)))
    Write-Host "== $name =="
    Write-Host $b64
    Write-Host ""
}

Write-Host "Add these values as repository Secrets on GitHub:"
Write-Host "Settings -> Secrets and variables -> Actions -> New repository secret"
Write-Host "(one secret per block above)"
