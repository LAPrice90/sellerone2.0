$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$src = $PSScriptRoot
Copy-Item (Join-Path $src "run_H_cycle.bat") (Join-Path $root "run_H_cycle.bat") -Force
Copy-Item (Join-Path $src "scripts\cycles\run_H_pricing_cycle.py") (Join-Path $root "scripts\cycles\run_H_pricing_cycle.py") -Force
Copy-Item (Join-Path $src "scripts\cycles\run_H_pricing_cycle_guarded.py") (Join-Path $root "scripts\cycles\run_H_pricing_cycle_guarded.py") -Force
Copy-Item (Join-Path $src "scripts\phase1\phase1_storage.py") (Join-Path $root "scripts\phase1\phase1_storage.py") -Force
Write-Host "H pre-migration files restored from $src"
