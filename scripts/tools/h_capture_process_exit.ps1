param(
    [Parameter(Mandatory = $true)][int]$TargetPid,
    [Parameter(Mandatory = $true)][string]$LiveDir
)

$ErrorActionPreference = "Stop"

function Read-FirstLine {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        return ""
    }
    try {
        return [string](Get-Content -Path $Path -Raw -ErrorAction Stop).Trim()
    } catch {
        return ""
    }
}

function Read-JsonObject {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        return $null
    }
    try {
        return Get-Content -Path $Path -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    } catch {
        return $null
    }
}

function Write-Json {
    param(
        [string]$Path,
        [object]$Payload
    )
    $dir = Split-Path -Parent $Path
    if ($dir) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    $tmp = "$Path.tmp"
    [System.IO.File]::WriteAllText(
        $tmp,
        ((ConvertTo-Json $Payload -Depth 8) + [Environment]::NewLine),
        [System.Text.Encoding]::UTF8
    )
    Move-Item -Path $tmp -Destination $Path -Force
}

function Get-ProcessInfo {
    param([int]$PidValue)
    try {
        return Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $PidValue) -ErrorAction Stop
    } catch {
        return $null
    }
}

function Select-RelevantEvents {
    param(
        [string]$LogName,
        [datetime]$StartUtc,
        [datetime]$EndUtc,
        [string]$TargetPidText
    )
    try {
        return Get-WinEvent -FilterHashtable @{
            LogName = $LogName
            StartTime = $StartUtc
            EndTime = $EndUtc
        } -MaxEvents 100 -ErrorAction SilentlyContinue | Where-Object {
            $_.Message -match "python" -or $_.Message -match $TargetPidText
        } | Select-Object -First 10 TimeCreated, ProviderName, Id, LevelDisplayName, Message
    } catch {
        return @()
    }
}

$livePath = [System.IO.Path]::GetFullPath($LiveDir)
$timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$artifactPath = Join-Path $livePath ("H_core_parent_exit_capture.{0}.{1}.json" -f $TargetPid, $timestamp)
$errorArtifactPath = Join-Path $livePath ("H_core_parent_exit_capture.error.{0}.{1}.json" -f $TargetPid, $timestamp)
$runCurrentPath = Join-Path $livePath "H_cycle_current_run_id.txt"
$runInProgressPath = Join-Path $livePath "H_run_in_progress.txt"
$runtimeStatusPath = Join-Path $livePath "H_runtime_status.json"
$eventWindowStart = (Get-Date).ToUniversalTime()
$monitorStartPath = Join-Path $livePath ("H_core_parent_exit_capture.monitor_start.{0}.{1}.txt" -f $TargetPid, $timestamp)
$startLine = "{0} pid={1}" -f $eventWindowStart.ToString("yyyy-MM-ddTHH:mm:ssZ"), $TargetPid
[System.IO.File]::WriteAllText($monitorStartPath, $startLine + [Environment]::NewLine, [System.Text.Encoding]::UTF8)

$payload = [ordered]@{
    capture_type = "win32_process_poll_capture"
    capture_start_utc = $eventWindowStart.ToString("yyyy-MM-ddTHH:mm:ssZ")
    target_pid = $TargetPid
    poll_interval_ms = 500
    monitor_pid = $PID
    process_name = ""
    parent_pid_start = ""
    creation_utc = ""
    command_line = ""
    run_id_current_start = (Read-FirstLine $runCurrentPath)
    run_id_in_progress_start = (Read-FirstLine $runInProgressPath)
    runtime_status_start = Read-JsonObject $runtimeStatusPath
    last_seen_utc = ""
    disappearance_utc = ""
    exit_detection = ""
    runtime_status_end = $null
    run_id_current_end = ""
    run_id_in_progress_end = ""
    application_events = @()
    system_events = @()
}

try {
    $processInfo = Get-ProcessInfo -PidValue $TargetPid
    if ($processInfo) {
        $payload.process_name = [string]$processInfo.Name
        $payload.parent_pid_start = [string]$processInfo.ParentProcessId
        $payload.creation_utc = ([datetime]$processInfo.CreationDate).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        $payload.command_line = [string]$processInfo.CommandLine
    } else {
        $payload.exit_detection = "missing_at_capture_start"
        $payload.disappearance_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    }

    while (-not $payload.disappearance_utc) {
        $currentInfo = Get-ProcessInfo -PidValue $TargetPid
        $nowUtc = (Get-Date).ToUniversalTime()
        if ($currentInfo) {
            $payload.last_seen_utc = $nowUtc.ToString("yyyy-MM-ddTHH:mm:ssZ")
            Start-Sleep -Milliseconds 500
            continue
        }
        $payload.disappearance_utc = $nowUtc.ToString("yyyy-MM-ddTHH:mm:ssZ")
        $payload.exit_detection = "missing_from_win32_process"
    }

    $windowStart = $eventWindowStart.AddMinutes(-1)
    $windowEnd = ([datetime]::Parse($payload.disappearance_utc)).AddMinutes(1)
    $payload.capture_end_utc = $payload.disappearance_utc
    $payload.run_id_current_end = (Read-FirstLine $runCurrentPath)
    $payload.run_id_in_progress_end = (Read-FirstLine $runInProgressPath)
    $payload.runtime_status_end = Read-JsonObject $runtimeStatusPath
    $payload.application_events = Select-RelevantEvents -LogName "Application" -StartUtc $windowStart -EndUtc $windowEnd -TargetPidText ([string]$TargetPid)
    $payload.system_events = Select-RelevantEvents -LogName "System" -StartUtc $windowStart -EndUtc $windowEnd -TargetPidText ([string]$TargetPid)
    Write-Json -Path $artifactPath -Payload $payload
} catch {
    $errorPayload = [ordered]@{
        capture_type = "win32_process_poll_capture"
        capture_start_utc = $payload.capture_start_utc
        capture_error_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        target_pid = $TargetPid
        monitor_pid = $PID
        error_type = $_.Exception.GetType().FullName
        error_message = $_.Exception.Message
        partial_payload = $payload
    }
    Write-Json -Path $errorArtifactPath -Payload $errorPayload
    throw
}
