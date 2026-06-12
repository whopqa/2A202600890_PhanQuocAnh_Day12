$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path   # …/06-lab-complete
$repoRoot    = Split-Path -Parent $projectRoot                    # …/2A202600890_PhanQuocAnh_Day12
$pythonExe   = Join-Path $repoRoot ".venv\Scripts\python.exe"
$runDir      = Join-Path $projectRoot ".run"
$pidFile     = Join-Path $runDir "service-pids.json"

# Fallback: use system python if venv not found
if (-not (Test-Path $pythonExe)) {
    $pythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $pythonExe) {
        throw "Python not found. Activate your virtualenv or install Python."
    }
    Write-Host "Warning: .venv not found, using system python: $pythonExe"
}

New-Item -ItemType Directory -Force -Path $runDir | Out-Null

function Start-ServiceProcess {
    param([string]$Name, [string]$ModuleName)
    $process = Start-Process `
        -FilePath $pythonExe `
        -ArgumentList @("-m", $ModuleName) `
        -WorkingDirectory $repoRoot `
        -WindowStyle Hidden `
        -PassThru
    [pscustomobject]@{
        Name = $Name
        ModuleName = $ModuleName
        Pid = $process.Id
    }
}

function Wait-HttpReady {
    param([string]$Name, [string]$Url, [int]$TimeoutSeconds = 30)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5 | Out-Null
            Write-Host "$Name is ready at $Url"
            return
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    throw "$Name did not become ready at $Url within $TimeoutSeconds seconds."
}

function Stop-StartedServices {
    param([array]$Services)
    foreach ($service in $Services) {
        try {
            Stop-Process -Id $service.Pid -ErrorAction Stop
        } catch {
        }
    }
}

$services = @()

try {
    Write-Host "Starting Day08 registry on port 11000..."
    $services += Start-ServiceProcess -Name "day08_registry" -ModuleName "Lab_Assigment.day08_registry"
    Wait-HttpReady -Name "Day08 Registry" -Url "http://127.0.0.1:11000/health"

    Write-Host "Starting Day08 legal RAG agent on port 11012..."
    $services += Start-ServiceProcess -Name "day08_legal_rag" -ModuleName "Lab_Assigment.day08_legal_rag_agent"
    Wait-HttpReady -Name "Day08 Legal RAG Agent" -Url "http://127.0.0.1:11012/.well-known/agent.json"

    Write-Host "Starting Day08 news RAG agent on port 11013..."
    $services += Start-ServiceProcess -Name "day08_news_rag" -ModuleName "Lab_Assigment.day08_news_rag_agent"
    Wait-HttpReady -Name "Day08 News RAG Agent" -Url "http://127.0.0.1:11013/.well-known/agent.json"

    Write-Host "Starting Day08 orchestrator agent on port 11011..."
    $services += Start-ServiceProcess -Name "day08_orchestrator" -ModuleName "Lab_Assigment.day08_orchestrator_agent"
    Wait-HttpReady -Name "Day08 Orchestrator Agent" -Url "http://127.0.0.1:11011/.well-known/agent.json"

    Write-Host "Starting Day08 customer agent on port 11010..."
    $services += Start-ServiceProcess -Name "day08_customer" -ModuleName "Lab_Assigment.day08_customer_agent"
    Wait-HttpReady -Name "Day08 Customer Agent" -Url "http://127.0.0.1:11010/.well-known/agent.json"

    Write-Host "Starting Day08 UI on port 11014..."
    $services += Start-ServiceProcess -Name "day08_ui" -ModuleName "Lab_Assigment.day08_ui"
    Wait-HttpReady -Name "Day08 UI" -Url "http://127.0.0.1:11014/health"

    $services | ConvertTo-Json | Set-Content -Path $pidFile

    Write-Host ""
    Write-Host "All Day08 services started:"
    Write-Host "  Registry:         http://127.0.0.1:11000"
    Write-Host "  Customer Agent:   http://127.0.0.1:11010"
    Write-Host "  Orchestrator:     http://127.0.0.1:11011"
    Write-Host "  Legal RAG:        http://127.0.0.1:11012"
    Write-Host "  News RAG:         http://127.0.0.1:11013"
    Write-Host "  Web UI:           http://127.0.0.1:11014"
    Write-Host ""
    Write-Host "PID file is in Lab_Assigment\.run\"
    Write-Host "Stop services with: .\Lab_Assigment\stop_all.ps1"
} catch {
    Stop-StartedServices -Services $services
    throw
}
