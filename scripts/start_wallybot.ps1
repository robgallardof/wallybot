$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Push-Location $taskRoot
try {
    docker compose up -d --wait
    if ($LASTEXITCODE -ne 0) { throw 'WallyBot services did not become ready.' }
    & (Join-Path $PSScriptRoot 'start_ai_worker.ps1')
    Write-Output 'WallyBot: http://localhost:3333'
} finally {
    Pop-Location
}
