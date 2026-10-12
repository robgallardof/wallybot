$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskPidPath = Join-Path $taskRoot 'logs/ai_worker/worker.pid'
if (-not (Test-Path -LiteralPath $taskPidPath)) { exit 0 }
$taskPython = (Resolve-Path -LiteralPath (Join-Path $taskRoot '.venv/Scripts/python.exe')).Path
$taskWorkerId = [int](Get-Content -LiteralPath $taskPidPath)
$taskExisting = Get-CimInstance Win32_Process -Filter "ProcessId = $taskWorkerId"
if ($taskExisting) {
    if ($taskExisting.ExecutablePath -ne $taskPython -or $taskExisting.CommandLine -notmatch 'apps\.ai_worker') {
        throw 'Saved PID belongs to another process; nothing was stopped.'
    }
    Stop-Process -Id $taskWorkerId
}
Remove-Item -LiteralPath $taskPidPath
Write-Output 'WallyBot AI worker stopped.'
