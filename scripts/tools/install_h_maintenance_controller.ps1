param(
    [string]$Root = '',
    [string]$ControllerTaskName = 'SellerOne H Maintenance Controller'
)

$ErrorActionPreference = 'Stop'

function Resolve-RepoRoot {
    param([string]$ArgRoot)
    if ($ArgRoot) {
        return (Resolve-Path -LiteralPath $ArgRoot).Path
    }
    $scriptRoot = $PSScriptRoot
    if (-not $scriptRoot) {
        $scriptRoot = Split-Path -Parent $PSCommandPath
    }
    if (-not $scriptRoot) {
        throw 'unable_to_resolve_script_root'
    }
    return (Resolve-Path -LiteralPath (Join-Path $scriptRoot '..\..')).Path
}

function Test-IsAdmin {
    try {
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
        $principal = New-Object Security.Principal.WindowsPrincipal($identity)
        return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } catch {
        return $false
    }
}

function Get-UtcStamp {
    return [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
}

function Write-JsonAtomic {
    param(
        [string]$Path,
        $Payload
    )
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $tmp = $Path + '.tmp.' + [string]$PID
    $json = $Payload | ConvertTo-Json -Depth 12
    [IO.File]::WriteAllText($tmp, $json + [Environment]::NewLine, [Text.Encoding]::ASCII)
    Move-Item -LiteralPath $tmp -Destination $Path -Force
}

$repoRoot = Resolve-RepoRoot -ArgRoot $Root
$locksDir = Join-Path $repoRoot 'out\locks'
$statusPath = Join-Path $locksDir 'h_maintenance_controller_install_status.json'
$controllerPath = Join-Path $repoRoot 'scripts\tools\h_maintenance_controller.ps1'

if (-not (Test-Path -LiteralPath $controllerPath)) {
    throw 'h_maintenance_controller_missing'
}

$arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $controllerPath + '" -Root "' + $repoRoot + '" -Once'
$user = [Security.Principal.WindowsIdentity]::GetCurrent().Name

try {
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable

    Register-ScheduledTask -TaskName $ControllerTaskName -Action $action -Principal $principal -Settings $settings -Force | Out-Null

    $task = Get-ScheduledTask -TaskName $ControllerTaskName -ErrorAction Stop
    $payload = [ordered]@{
        schema_version = '1'
        controller_task_name = $ControllerTaskName
        observed_utc = Get-UtcStamp
        installed = $true
        success = $true
        failure_reason = ''
        registration_attempted = $true
        is_admin_shell = [bool](Test-IsAdmin)
        user = $user
        run_level = 'Highest'
        controller_path = $controllerPath
        repo_root = $repoRoot
        task_state = [string]$task.State
        task_path = [string]$task.TaskPath
        task_name = [string]$task.TaskName
        normal_request_path = (Join-Path $locksDir 'h_maintenance_request.json')
        normal_result_path = (Join-Path $locksDir 'h_maintenance_controller_last_result.json')
    }
    Write-JsonAtomic -Path $statusPath -Payload $payload
    Write-Output ($payload | ConvertTo-Json -Depth 12)
    exit 0
} catch {
    $payload = [ordered]@{
        schema_version = '1'
        controller_task_name = $ControllerTaskName
        observed_utc = Get-UtcStamp
        installed = $false
        success = $false
        failure_reason = 'scheduled_task_registration_failed'
        registration_attempted = $true
        is_admin_shell = [bool](Test-IsAdmin)
        user = $user
        run_level = 'Highest'
        controller_path = $controllerPath
        repo_root = $repoRoot
        error = $_.Exception.Message
        normal_request_path = (Join-Path $locksDir 'h_maintenance_request.json')
        normal_result_path = (Join-Path $locksDir 'h_maintenance_controller_last_result.json')
    }
    Write-JsonAtomic -Path $statusPath -Payload $payload
    Write-Output ($payload | ConvertTo-Json -Depth 12)
    exit 1
}
