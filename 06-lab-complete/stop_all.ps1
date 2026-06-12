$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidFile = Join-Path $projectRoot ".run\service-pids.json"

if (-not (Test-Path $pidFile)) {
    Write-Host "No PID file found at Lab_Assigment\.run\service-pids.json"
    exit 0
}

$services = Get-Content $pidFile | ConvertFrom-Json
foreach ($service in $services) {
    try {
        Stop-Process -Id $service.Pid -ErrorAction Stop
        Write-Host "Stopped $($service.Name) (PID $($service.Pid))"
    } catch {
        Write-Host "Skipping $($service.Name) (PID $($service.Pid)) - process not running"
    }
}

Remove-Item $pidFile -ErrorAction SilentlyContinue

