param(
  [string]$RepoRoot = "c:\Users\Luke\Desktop\SellerOne 2.0"
)
$ErrorActionPreference = "Stop"
$BackupRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Map = @(
  @{ Src = "run_H_cycle.bat"; Dst = "run_H_cycle.bat" },
  @{ Src = "scripts/cycles/run_H_pricing_cycle.py"; Dst = "scripts/cycles/run_H_pricing_cycle.py" },
  @{ Src = "scripts/cycles/run_H_pricing_cycle_guarded.py"; Dst = "scripts/cycles/run_H_pricing_cycle_guarded.py" },
  @{ Src = "scripts/phase1/phase1_storage.py"; Dst = "scripts/phase1/phase1_storage.py" },
  @{ Src = "out/cycle_alerts/checklist_H_split.csv"; Dst = "out/cycle_alerts/checklist_H_split.csv" }
)
foreach ($entry in $Map) {
  $srcPath = Join-Path $BackupRoot $entry.Src
  $dstPath = Join-Path $RepoRoot $entry.Dst
  if (-not (Test-Path $srcPath)) {
    throw "Missing backup source: $srcPath"
  }
  $dstDir = Split-Path -Parent $dstPath
  if ($dstDir -and -not (Test-Path $dstDir)) {
    New-Item -ItemType Directory -Path $dstDir -Force | Out-Null
  }
  Copy-Item -Path $srcPath -Destination $dstPath -Force
  Write-Host "Restored $($entry.Dst)"
}
Write-Host "H pre-migration restore completed from $BackupRoot"
