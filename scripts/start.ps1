param([string]$ConfigurationPath = '.env')
$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $workspaceRoot '.venv/Scripts/python.exe'
if (-not [System.IO.Path]::IsPathRooted($ConfigurationPath)) { $ConfigurationPath = Join-Path $workspaceRoot $ConfigurationPath }
if (-not (Test-Path -LiteralPath $ConfigurationPath)) { throw 'Run scripts/setup_database.ps1 first to configure the local database.' }
$env:WORKSPACE_ENV_FILE = (Resolve-Path -LiteralPath $ConfigurationPath).Path
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Run scripts/install.ps1 first.' }
Set-Location -LiteralPath $workspaceRoot
& $pythonPath (Join-Path $PSScriptRoot 'migrate.py')
if ($LASTEXITCODE -ne 0) { throw 'Database migration failed. Nothing was started.' }
foreach ($port in @(8001,5174)) {
    $listener = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    if ($listener) { throw "Port $port is in use. Stop the existing instance before starting." }
}
$logDirectory = Join-Path $workspaceRoot 'storage/logs'
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$backendProcess = Start-Process -FilePath $pythonPath -ArgumentList @('-m','uvicorn','backend.app:app','--host','127.0.0.1','--port','8001') -WorkingDirectory $workspaceRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDirectory 'backend.out.log') -RedirectStandardError (Join-Path $logDirectory 'backend.err.log') -PassThru
$nodePath = (Get-Command node -ErrorAction Stop).Source
$vitePath = Join-Path $workspaceRoot 'frontend_Web/node_modules/vite/bin/vite.js'
$frontendArguments = '"' + $vitePath + '" --host 127.0.0.1 --port 5174 --strictPort'
try {
    $frontendProcess = Start-Process -FilePath $nodePath -ArgumentList $frontendArguments -WorkingDirectory (Join-Path $workspaceRoot 'frontend_Web') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDirectory 'frontend.out.log') -RedirectStandardError (Join-Path $logDirectory 'frontend.err.log') -PassThru
    $processes = @($backendProcess,$frontendProcess) | ForEach-Object { @{Id=$_.Id;StartTime=$_.StartTime.ToUniversalTime().ToString('o');Executable=$_.Path} }
    $processes | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $workspaceRoot 'storage/processes.json') -Encoding utf8
    $ready = $false
    for ($attempt = 0; $attempt -lt 15; $attempt++) {
        Start-Sleep -Milliseconds 500
        try {
            $health = Invoke-RestMethod 'http://127.0.0.1:8001/api/health' -TimeoutSec 2
            $front = Invoke-WebRequest 'http://127.0.0.1:5174/' -TimeoutSec 2 -UseBasicParsing
            if ($health.database -eq 'ready' -and $front.StatusCode -eq 200) { $ready = $true; break }
        } catch { }
    }
    if (-not $ready) { throw 'Services did not become ready. Check storage/logs.' }
    Write-Host 'Knowledge workspace ready: http://127.0.0.1:5174/'
    Write-Host 'Stop with: powershell -ExecutionPolicy Bypass -File scripts/stop.ps1'
} catch {
    if ($frontendProcess -and -not $frontendProcess.HasExited) { Stop-Process -Id $frontendProcess.Id -ErrorAction SilentlyContinue }
    if (-not $backendProcess.HasExited) { Stop-Process -Id $backendProcess.Id -ErrorAction SilentlyContinue }
    throw
}
