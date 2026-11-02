#requires -Version 5.1
param([switch]$Dev)
$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $root
$runDir = Join-Path $root 'data\run'
New-Item -ItemType Directory -Path $runDir -Force | Out-Null

foreach ($cmd in @('docker', 'uv')) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        throw "$cmd not found in PATH"
    }
}

$distIndex = Join-Path $root 'web\dist\index.html'
if ($Dev) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw 'npm not found in PATH (required for -Dev)'
    }
} elseif (-not (Test-Path -LiteralPath $distIndex)) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw 'web/dist is missing and npm is not installed; run npm ci && npm run build in web/'
    }
    Push-Location (Join-Path $root 'web')
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'frontend build failed' }
    Pop-Location
}

function Test-Port([int]$Port) {
    return [bool](Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
}

function Test-Process([string]$Pattern) {
    return [bool](Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -match $Pattern })
}

function Test-Docker {
    cmd /c "docker info >nul 2>&1"
    return $LASTEXITCODE -eq 0
}

function Reset-DockerSockets {
    $ts = Get-Date -Format 'yyyyMMddHHmmss'
    foreach ($name in @('Docker\run', 'docker-secrets-engine')) {
        $dir = Join-Path $env:LOCALAPPDATA $name
        if (Test-Path -LiteralPath $dir) {
            try {
                Rename-Item -LiteralPath $dir -NewName ((Split-Path $dir -Leaf) + '.bak-' + $ts) -ErrorAction Stop
            } catch {}
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
    }
}

function Start-Docker {
    $dockerExe = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
    if (-not (Test-Path -LiteralPath $dockerExe)) {
        throw "Docker Desktop not found: $dockerExe"
    }
    if (Get-Process 'Docker Desktop' -ErrorAction SilentlyContinue) {
        # Docker Desktop 4.72 on Windows leaves undeletable AF_UNIX sockets after crashes.
        & 'C:\Program Files\Docker\Docker\DockerCli.exe' -Shutdown *> $null
        Start-Sleep -Seconds 5
        foreach ($p in @('Docker Desktop', 'com.docker.backend', 'com.docker.build', 'docker-sandbox', 'docker-ai', 'docker-mcp')) {
            Get-Process $p -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Seconds 2
    }
    Reset-DockerSockets
    Start-Process $dockerExe
    $deadline = (Get-Date).AddSeconds(180)
    while ((Get-Date) -lt $deadline) {
        if (Test-Docker) { return }
        Start-Sleep -Seconds 3
    }
    throw 'Docker engine did not start within 180s.'
}

function Start-ServiceWindow([string]$Title, [string]$Command, [string]$Slug) {
    $script = "`$Host.UI.RawUI.WindowTitle = '$Title'; $Command"
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($script))
    $process = Start-Process 'powershell.exe' -ArgumentList @(
        '-NoProfile', '-NoExit', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $encoded
    ) -WindowStyle Normal -PassThru
    Set-Content -Path (Join-Path $runDir "$Slug.pid") -Value $process.Id
}

function Close-StaleServiceWindows {
    # Earlier runs leave empty -NoExit windows behind after a service is killed.
    $procs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq 'powershell.exe' -and $_.CommandLine -match '-EncodedCommand' }
    foreach ($proc in $procs) {
        $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$($proc.ProcessId)" -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -ne 'conhost.exe' }
        if ($children) { continue }
        $match = [regex]::Match($proc.CommandLine, '-EncodedCommand\s+(\S+)')
        if (-not $match.Success) { continue }
        try {
            $decoded = [Text.Encoding]::Unicode.GetString([Convert]::FromBase64String($match.Groups[1].Value))
        } catch { continue }
        if ($decoded -match 'roxy_pipline' -or $decoded -match 'app\.workflow\.celery_app') {
            Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }
}

if (-not (Test-Docker)) { Start-Docker }
Write-Host '[1/4] Docker ready'

docker compose -f compose.local.yml up -d
if ($LASTEXITCODE -ne 0) { throw 'docker compose -f compose.local.yml up failed' }

Write-Host '[2/4] waiting for Redis...'
$deadline = (Get-Date).AddSeconds(60)
$ready = $false
while ((Get-Date) -lt $deadline) {
    $rd = (docker compose -f compose.local.yml exec -T redis redis-cli ping 2>$null) -eq 'PONG'
    if ($rd) { $ready = $true; break }
    Start-Sleep -Seconds 2
}
if (-not $ready) { throw 'Redis is not ready' }
Write-Host '[3/4] Redis healthy'

$apiCmd = "Set-Location '$root'; uv run uvicorn app.api.main:app --reload --port 8000"
$mainCmd = "Set-Location '$root'; uv run celery -A app.workflow.celery_app worker -Q workflow,agent,render -l info --pool=solo -n `"worker-main@%h`""
$mediaCmd = "Set-Location '$root'; uv run celery -A app.workflow.celery_app worker -Q media -l info --pool=solo -n `"worker-media@%h`""
$beatCmd = "Set-Location '$root'; uv run celery -A app.workflow.celery_app beat -l info -s data/celerybeat-schedule"
$webCmd = "Set-Location '$root\web'; if (-not (Test-Path node_modules)) { npm install }; npm run dev"

Close-StaleServiceWindows
Get-ChildItem $runDir -Filter '*.pid' -ErrorAction SilentlyContinue | ForEach-Object {
    $servicePid = [int](Get-Content $_.FullName -ErrorAction SilentlyContinue)
    if (-not (Get-Process -Id $servicePid -ErrorAction SilentlyContinue)) {
        Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
    }
}

if (Test-Port 8000) {
    try {
        $existing = Invoke-RestMethod -TimeoutSec 3 'http://127.0.0.1:8000/health'
        if ($existing.status -ne 'ok') { throw 'unhealthy' }
    } catch {
        throw 'Port 8000 is occupied but the Roxy API is not healthy; stop the other process first.'
    }
} else {
    Start-ServiceWindow 'API 8000' $apiCmd 'api'
}
if (-not (Test-Process 'celery.*worker-main@')) { Start-ServiceWindow 'Worker main' $mainCmd 'worker-main' }
if (-not (Test-Process 'celery.*worker-media@')) { Start-ServiceWindow 'Worker media' $mediaCmd 'worker-media' }
if (-not (Test-Process 'celery.*beat')) { Start-ServiceWindow 'Celery beat' $beatCmd 'beat' }
if ($Dev -and -not (Test-Port 5173)) { Start-ServiceWindow 'Frontend 5173' $webCmd 'web' }

$deadline = (Get-Date).AddSeconds(60)
$healthy = $false
while ((Get-Date) -lt $deadline) {
    try {
        $health = Invoke-RestMethod -TimeoutSec 2 'http://127.0.0.1:8000/health'
        if ($health.status -eq 'ok') {
            $healthy = $true
            break
        }
    } catch {}
    Start-Sleep -Seconds 2
}
if (-not $healthy) {
    throw 'API did not become healthy within 60s; check the "API 8000" PowerShell window for errors.'
}

Write-Host '[4/4] services started'
Write-Host ''
Write-Host 'Roxy Pipeline is up:'
Write-Host '  API      http://127.0.0.1:8000'
Write-Host '  Docs     http://127.0.0.1:8000/docs'
if ($Dev) {
    Write-Host '  Frontend http://localhost:5173 (Vite dev)'
} else {
    Write-Host '  Web      http://127.0.0.1:8000'
}
Write-Host ''
Write-Host 'Each service runs in its own PowerShell window; close a window to stop it.'
