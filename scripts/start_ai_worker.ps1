$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskPython = (Resolve-Path -LiteralPath (Join-Path $taskRoot '.venv/Scripts/python.exe')).Path
$taskLogDirectory = Join-Path $taskRoot 'logs/ai_worker'
New-Item -ItemType Directory -Path $taskLogDirectory -Force | Out-Null
$taskPidPath = Join-Path $taskLogDirectory 'worker.pid'
if (Test-Path -LiteralPath $taskPidPath) {
    $taskWorkerId = [int](Get-Content -LiteralPath $taskPidPath)
    $taskExisting = Get-CimInstance Win32_Process -Filter "ProcessId = $taskWorkerId"
    if ($taskExisting -and $taskExisting.ExecutablePath -eq $taskPython -and $taskExisting.CommandLine -match 'apps\.ai_worker') {
        Write-Output 'WallyBot AI worker is already running.'
        exit 0
    }
}
$taskProcess = Start-Process -FilePath $taskPython -ArgumentList '-m', 'apps.ai_worker' `
    -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $taskLogDirectory 'stdout.log') `
    -RedirectStandardError (Join-Path $taskLogDirectory 'stderr.log')
$taskProcess.Id | Set-Content -LiteralPath $taskPidPath
Write-Output "WallyBot AI worker started (PID $($taskProcess.Id))."
