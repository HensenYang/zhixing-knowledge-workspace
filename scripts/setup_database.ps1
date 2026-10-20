$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $workspaceRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Please run scripts/install.ps1 first.' }
& $pythonPath (Join-Path $PSScriptRoot 'setup_database.py')
if ($LASTEXITCODE -ne 0) { throw 'Database setup failed.' }

