#requires -Version 5.1
$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $root

foreach ($cmd in @('docker', 'uv', 'npm')) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        throw "$cmd not found in PATH"
    }
}

function Test-Port([int]$Port) {
    return [bool](Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
}

function Test-Process([string]$Pattern) {
    return [bool](Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -match $Pattern })
}

function Test-Docker {
    docker info *> $null
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

function Start-ServiceWindow([string]$Title, [string]$Command) {
    $script = "`$Host.UI.RawUI.WindowTitle = '$Title'; $Command"
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($script))
    Start-Process 'powershell.exe' -ArgumentList @(
        '-NoProfile', '-NoExit', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $encoded
    ) -WindowStyle Normal
}

if (-not (Test-Docker)) { Start-Docker }
Write-Host '[1/4] Docker ready'

docker compose -f compose.infra.yml --profile storage up -d postgres rabbitmq redis minio
if ($LASTEXITCODE -ne 0) { throw 'docker compose up failed' }

Write-Host '[2/4] waiting for infra...'
$deadline = (Get-Date).AddSeconds(120)
$ready = $false
while ((Get-Date) -lt $deadline) {
    $pg = (docker compose -f compose.infra.yml exec -T postgres pg_isready -U roxy 2>$null) -match 'accepting connections'
    $rd = (docker compose -f compose.infra.yml exec -T redis redis-cli ping 2>$null) -eq 'PONG'
    $mq = (docker compose -f compose.infra.yml exec -T rabbitmq rabbitmq-diagnostics -q ping 2>$null) -match 'succeeded|ok'
    $mn = [bool](docker compose -f compose.infra.yml --profile storage ps --status running -q minio 2>$null)
    if ($pg -and $rd -and $mq -and $mn) { $ready = $true; break }
    Start-Sleep -Seconds 2
}
if (-not $ready) { throw 'infra services are not ready' }
Write-Host '[3/4] infra healthy'

uv run python scripts/tools/ensure_minio_buckets.py
if ($LASTEXITCODE -ne 0) { throw 'MinIO bucket init failed' }

$apiCmd = "Set-Location '$root'; uv run uvicorn app.api.main:app --reload --port 8000"
$mainCmd = "Set-Location '$root'; uv run celery -A app.workflow.celery_app worker -Q workflow,agent,render -l info --pool=solo -n `"worker-main@%h`""
$mediaCmd = "Set-Location '$root'; uv run celery -A app.workflow.celery_app worker -Q media -l info --pool=solo -n `"worker-media@%h`""
$beatCmd = "Set-Location '$root'; uv run celery -A app.workflow.celery_app beat -l info"
$webCmd = "Set-Location '$root\web'; if (-not (Test-Path node_modules)) { npm install }; npm run dev"

if (-not (Test-Port 8000)) { Start-ServiceWindow 'API 8000' $apiCmd }
if (-not (Test-Process 'celery.*worker-main@')) { Start-ServiceWindow 'Worker main' $mainCmd }
if (-not (Test-Process 'celery.*worker-media@')) { Start-ServiceWindow 'Worker media' $mediaCmd }
if (-not (Test-Process 'celery.*beat')) { Start-ServiceWindow 'Celery beat' $beatCmd }
if (-not (Test-Port 5173)) { Start-ServiceWindow 'Frontend 5173' $webCmd }

$deadline = (Get-Date).AddSeconds(60)
while ((Get-Date) -lt $deadline) {
    try {
        $health = Invoke-RestMethod -TimeoutSec 2 'http://127.0.0.1:8000/health'
        if ($health.status -eq 'ok') { break }
    } catch {}
    Start-Sleep -Seconds 2
}

Write-Host '[4/4] services started'
Write-Host ''
Write-Host 'Roxy Pipeline is up:'
Write-Host '  API      http://127.0.0.1:8000'
Write-Host '  Docs     http://127.0.0.1:8000/docs'
Write-Host '  Frontend http://localhost:5173'
Write-Host ''
Write-Host 'Each service runs in its own PowerShell window; close a window to stop it.'
