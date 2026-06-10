$ErrorActionPreference = "Stop"

$managerDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $managerDir

Push-Location $repoRoot
try {
    python -m sellerone_manager.app --what-next
}
finally {
    Pop-Location
}
