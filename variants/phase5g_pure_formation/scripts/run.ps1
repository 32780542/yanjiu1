param([Parameter(Position=0)][string]$Command = 'verify')
$ErrorActionPreference = 'Stop'
$researchRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $researchRoot
New-Item -ItemType Directory -Path (Join-Path $researchRoot 'tmp') -Force | Out-Null
$env:TEMP = Join-Path $researchRoot 'tmp'
$env:TMP = $env:TEMP
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONUTF8 = '1'
$toolConfig = Get-Content -LiteralPath 'configs/tools.json' -Raw | ConvertFrom-Json
& $toolConfig.python -I -B -S (Join-Path $researchRoot 'run.py') $Command
exit $LASTEXITCODE
