$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$processFile = Join-Path $workspaceRoot 'storage/processes.json'
if (-not (Test-Path -LiteralPath $processFile)) { Write-Host 'No recorded workspace processes.'; exit 0 }
$records = Get-Content -LiteralPath $processFile -Raw | ConvertFrom-Json
foreach ($record in $records) {
    $process = Get-Process -Id $record.Id -ErrorAction SilentlyContinue
    if (-not $process) { continue }
    if ($process.StartTime.ToUniversalTime().ToString('o') -ne $record.StartTime -or $process.Path -ne $record.Executable) { throw "PID $($record.Id) belongs to a different process. It was preserved." }
    Stop-Process -Id $process.Id -ErrorAction Stop
}
Write-Host 'Recorded knowledge workspace processes stopped.'

