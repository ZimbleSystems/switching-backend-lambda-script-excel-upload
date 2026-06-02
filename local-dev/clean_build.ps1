# Remove root-owned files from local-dev\build (Docker pip leaves them on Windows).
# Run:  powershell -ExecutionPolicy Bypass -File clean_build.ps1

$BuildDir = Join-Path $PSScriptRoot "build"
if (-not (Test-Path $BuildDir)) { New-Item -ItemType Directory -Path $BuildDir | Out-Null }

Write-Host "Cleaning $BuildDir"
docker run --rm -v "${BuildDir}:/build" alpine sh -c "rm -rf /build/*"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Done. Run build_zip.sh from Git Bash or WSL next."
