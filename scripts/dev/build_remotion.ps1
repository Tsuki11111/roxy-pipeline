#requires -Version 5.1
param([switch]$SkipCachePrune)
$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $root

docker build -f infra/remotion/Dockerfile -t roxy-remotion:4.0.539 .
if ($LASTEXITCODE -ne 0) { throw 'Remotion image build failed' }

# Only prune dangling images produced by this project.
docker image prune -f --filter "dangling=true" --filter "label=roxy.pipeline=remotion" | Out-Null

# Keep recent layers for fast rebuilds and drop stale build cache.
if (-not $SkipCachePrune) {
    docker builder prune -f --filter "until=168h" | Out-Null
    # Best-effort cap on Docker versions that support it.
    docker builder prune -f --max-used-space 2GB | Out-Null
}

docker system df