#requires -Version 5.1
$ErrorActionPreference = 'SilentlyContinue'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$servicePattern = 'app\.api\.main|app\.workflow\.celery_app'
$stopped = 0

# Stop each service window and its whole process tree via the PID recorded at start.
$runDir = Join-Path $root 'data\run'
Get-ChildItem $runDir -Filter '*.pid' -ErrorAction SilentlyContinue | ForEach-Object {
    $servicePid = [int](Get-Content $_.FullName -ErrorAction SilentlyContinue)
    if ($servicePid) {
        & taskkill.exe /PID $servicePid /T /F *> $null
        $stopped++
    }
    Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
}

# Stop the actual service processes (uv / python / celery / vite) first.
$processes = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match '^(uv|python|celery|node)\.exe$' -and
    $_.CommandLine -and
    ($_.CommandLine -match $servicePattern -or $_.CommandLine -match 'roxy_pipline\\\\web.*vite')
}
foreach ($proc in $processes) {
    Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
    $stopped++
}

# Close every service window this project opened, including empty leftovers.
$windows = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq 'powershell.exe' -and $_.CommandLine -match '-EncodedCommand'
}
foreach ($window in $windows) {
    $match = [regex]::Match($window.CommandLine, '-EncodedCommand\s+(\S+)')
    if (-not $match.Success) { continue }
    try {
        $decoded = [Text.Encoding]::Unicode.GetString([Convert]::FromBase64String($match.Groups[1].Value))
    } catch { continue }
    if ($decoded -match 'roxy_pipline' -or $decoded -match 'app\.workflow\.celery_app') {
        Stop-Process -Id $window.ProcessId -Force -ErrorAction SilentlyContinue
        $stopped++
    }
}

Write-Host "Stopped $stopped Roxy Pipeline process/window(s)."
Write-Host 'Redis container is left running; use "docker compose -f compose.local.yml down" to stop it.'