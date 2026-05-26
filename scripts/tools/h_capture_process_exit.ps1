param(
    [Parameter(Mandatory = $true)][int]$TargetPid,
    [Parameter(Mandatory = $true)][string]$LiveDir,
    [string]$RunId = "",
    [string]$WindowLabel = "owner_wait_enter",
    [string]$WindowToken = "",
    [string]$StopSignalPath = "",
    [string]$ContextPath = "",
    [string]$ReadySignalPath = "",
    [int]$PollIntervalMs = 500,
    [int]$MaxWaitSeconds = 600
)

$ErrorActionPreference = "Stop"

function To-UtcString {
    param([datetime]$Value)
    return $Value.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
}

function Read-FirstLine {
    param([string]$Path)
    if (-not $Path -or -not (Test-Path $Path)) {
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
    if (-not $Path -or -not (Test-Path $Path)) {
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
        ((ConvertTo-Json $Payload -Depth 12) + [Environment]::NewLine),
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

function Get-ProcessSessionId {
    param([int]$PidValue)
    try {
        return [string](Get-Process -Id $PidValue -ErrorAction Stop).SessionId
    } catch {
        return ""
    }
}

function Get-ProcessOwner {
    param([object]$ProcessInfo)
    if (-not $ProcessInfo) {
        return [ordered]@{ status = "unavailable"; reason = "process_missing"; account = ""; sid = "" }
    }
    try {
        $ownerResult = Invoke-CimMethod -InputObject $ProcessInfo -MethodName GetOwner -ErrorAction Stop
        $sidResult = Invoke-CimMethod -InputObject $ProcessInfo -MethodName GetOwnerSid -ErrorAction Stop
        $account = ""
        if ($ownerResult -and [int]$ownerResult.ReturnValue -eq 0) {
            $account = ("{0}\{1}" -f [string]$ownerResult.Domain, [string]$ownerResult.User).Trim("\")
        }
        return [ordered]@{
            status = "available"
            reason = ""
            account = $account
            sid = [string]$sidResult.Sid
        }
    } catch {
        return [ordered]@{
            status = "unavailable"
            reason = ("{0}:{1}" -f $_.Exception.GetType().Name, $_.Exception.Message)
            account = ""
            sid = ""
        }
    }
}

function Build-ProcessNode {
    param(
        [int]$PidValue
    )
    $info = Get-ProcessInfo -PidValue $PidValue
    if (-not $info) {
        return [ordered]@{
            pid = [string]$PidValue
            status = "missing"
        }
    }
    $owner = Get-ProcessOwner -ProcessInfo $info
    return [ordered]@{
        pid = [string]$PidValue
        status = "present"
        process_name = [string]$info.Name
        parent_pid = [string]$info.ParentProcessId
        creation_utc = To-UtcString ([datetime]$info.CreationDate)
        command_line = [string]$info.CommandLine
        executable_path = [string]$info.ExecutablePath
        session_id = Get-ProcessSessionId -PidValue $PidValue
        owner = $owner
    }
}

function Build-CreatorChain {
    param(
        [int]$PidValue,
        [int]$MaxDepth = 5
    )
    $nodes = @()
    $seen = @{}
    $cursor = $PidValue
    for ($depth = 0; $depth -lt $MaxDepth; $depth++) {
        if ($seen.ContainsKey([string]$cursor)) {
            break
        }
        $seen[[string]$cursor] = $true
        $node = Build-ProcessNode -PidValue $cursor
        $nodeWithDepth = [ordered]@{
            depth = $depth
            node = $node
        }
        $nodes += $nodeWithDepth
        if ($node.status -ne "present") {
            break
        }
        $parentPidText = [string]$node.parent_pid
        if (-not $parentPidText -or $parentPidText -eq "0") {
            break
        }
        try {
            $cursor = [int]$parentPidText
        } catch {
            break
        }
    }
    return $nodes
}

function _Build-EventQueryOutcome {
    param(
        [string]$SourceName,
        [bool]$Available,
        [string]$AccessResult,
        [string]$QueryStatus,
        [string]$Reason,
        [int]$TotalRecords,
        [int]$RecordsFound,
        [object[]]$Events
    )
    return [ordered]@{
        source = $SourceName
        attempted = $true
        available = $Available
        access_result = $AccessResult
        query_status = $QueryStatus
        reason = $Reason
        total_records = [string]$TotalRecords
        records_found = [string]$RecordsFound
        matched = $(if ($RecordsFound -gt 0) { "1" } else { "0" })
        events = $Events
    }
}

function Select-RelevantEvents {
    param(
        [string]$SourceName,
        [string]$LogName,
        [datetime]$StartUtc,
        [datetime]$EndUtc,
        [string[]]$Patterns,
        [int[]]$EventIds = @(),
        [int]$MaxEvents = 300
    )
    $filter = @{
        LogName = $LogName
        StartTime = $StartUtc
        EndTime = $EndUtc
    }
    if ($EventIds -and $EventIds.Count -gt 0) {
        $filter["Id"] = $EventIds
    }
    $records = @()
    try {
        $records = @(Get-WinEvent -FilterHashtable $filter -MaxEvents $MaxEvents -ErrorAction Stop)
    } catch {
        $errText = ("{0}:{1}" -f $_.Exception.GetType().Name, $_.Exception.Message)
        $lower = $errText.ToLowerInvariant()
        if ($lower.Contains("no events were found")) {
            return _Build-EventQueryOutcome -SourceName $SourceName -Available $true -AccessResult "ok" -QueryStatus "no_records" -Reason $errText -TotalRecords 0 -RecordsFound 0 -Events @()
        }
        if ($lower.Contains("access is denied") -or $lower.Contains("not have permission")) {
            return _Build-EventQueryOutcome -SourceName $SourceName -Available $false -AccessResult "denied" -QueryStatus "access_denied" -Reason $errText -TotalRecords 0 -RecordsFound 0 -Events @()
        }
        return _Build-EventQueryOutcome -SourceName $SourceName -Available $false -AccessResult "error" -QueryStatus "query_failed" -Reason $errText -TotalRecords 0 -RecordsFound 0 -Events @()
    }
    $selected = @()
    $totalRecords = @($records).Count
    foreach ($record in $records) {
        $messageText = [string]$record.Message
        $isMatch = $false
        if (-not $Patterns -or $Patterns.Count -eq 0) {
            $isMatch = $true
        } else {
            foreach ($pattern in $Patterns) {
                if (-not $pattern) {
                    continue
                }
                if ($messageText -match [Regex]::Escape($pattern)) {
                    $isMatch = $true
                    break
                }
            }
        }
        if (-not $isMatch) {
            continue
        }
        $excerpt = $messageText
        if ($excerpt.Length -gt 500) {
            $excerpt = $excerpt.Substring(0, 500)
        }
        $selected += [ordered]@{
            utc = To-UtcString $record.TimeCreated
            provider = [string]$record.ProviderName
            id = [string]$record.Id
            level = [string]$record.LevelDisplayName
            record_id = [string]$record.RecordId
            message_excerpt = $excerpt
        }
        if ($selected.Count -ge 20) {
            break
        }
    }
    if ($selected.Count -gt 0) {
        return _Build-EventQueryOutcome -SourceName $SourceName -Available $true -AccessResult "ok" -QueryStatus "ok" -Reason "" -TotalRecords $totalRecords -RecordsFound $selected.Count -Events $selected
    }
    return _Build-EventQueryOutcome -SourceName $SourceName -Available $true -AccessResult "ok" -QueryStatus "no_matches" -Reason "" -TotalRecords $totalRecords -RecordsFound 0 -Events @()
}

function Build-SecurityTerminationLinkage {
    param(
        [object]$SecurityOutcome,
        [string]$TargetPidText,
        [string]$TargetPidHex
    )
    $candidates = @()
    if (-not $SecurityOutcome -or -not $SecurityOutcome.events) {
        return [ordered]@{
            attempted = $true
            available = $(if ($SecurityOutcome) { [string]$SecurityOutcome.available } else { "0" })
            attribution_possible = "0"
            attribution_level = "none"
            reason = "no_security_events"
            candidates = @()
        }
    }
    foreach ($ev in $SecurityOutcome.events) {
        $idText = [string]$ev.id
        $msg = [string]$ev.message_excerpt
        $containsTarget = ($msg -match [Regex]::Escape($TargetPidText) -or $msg -match [Regex]::Escape($TargetPidHex))
        if (-not $containsTarget) {
            continue
        }
        $creatorPidHex = ""
        $creatorPidDec = ""
        $creatorMatch = [regex]::Match($msg, "Creator Process ID:\s*(0x[0-9a-fA-F]+)")
        if ($creatorMatch.Success) {
            $creatorPidHex = $creatorMatch.Groups[1].Value
            try {
                $creatorPidDec = [string][int]$creatorPidHex
            } catch {
                $creatorPidDec = ""
            }
        }
        $eventClass = if ($idText -eq "4689") { "process_exit" } elseif ($idText -eq "4688") { "process_create" } else { "security_other" }
        $candidates += [ordered]@{
            utc = [string]$ev.utc
            id = $idText
            event_class = $eventClass
            contains_target_pid = "1"
            creator_pid_hex = $creatorPidHex
            creator_pid_dec = $creatorPidDec
            record_id = [string]$ev.record_id
        }
    }
    if ($candidates.Count -eq 0) {
        return [ordered]@{
            attempted = $true
            available = [string]$SecurityOutcome.available
            attribution_possible = "0"
            attribution_level = "none"
            reason = "no_target_security_events"
            candidates = @()
        }
    }
    $hasExit = $false
    $hasCreator = $false
    foreach ($c in $candidates) {
        if ($c.event_class -eq "process_exit") {
            $hasExit = $true
        }
        if ([string]$c.creator_pid_hex) {
            $hasCreator = $true
        }
    }
    $level = "best_effort"
    if ($hasExit -and $hasCreator) {
        $level = "authoritative_candidate"
    }
    return [ordered]@{
        attempted = $true
        available = [string]$SecurityOutcome.available
        attribution_possible = "1"
        attribution_level = $level
        reason = ""
        candidates = $candidates
    }
}

$livePath = [System.IO.Path]::GetFullPath($LiveDir)
$runIdNorm = ([string]$RunId).Trim()
$windowLabelNorm = ([string]$WindowLabel).Trim()
if (-not $windowLabelNorm) {
    $windowLabelNorm = "owner_wait_enter"
}
$windowTokenNorm = ([string]$WindowToken).Trim()
if (-not $windowTokenNorm) {
    $windowTokenNorm = ("pid{0}" -f $TargetPid)
}
$timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$safeRun = ($runIdNorm -replace "[^A-Za-z0-9_.-]", "_")
if ($safeRun) {
    $artifactPath = Join-Path $livePath ("H_owner_termination_provenance.{0}.{1}.{2}.json" -f $safeRun, $TargetPid, $timestamp)
    $errorArtifactPath = Join-Path $livePath ("H_owner_termination_provenance.error.{0}.{1}.{2}.json" -f $safeRun, $TargetPid, $timestamp)
} else {
    $artifactPath = Join-Path $livePath ("H_core_parent_exit_capture.{0}.{1}.json" -f $TargetPid, $timestamp)
    $errorArtifactPath = Join-Path $livePath ("H_core_parent_exit_capture.error.{0}.{1}.json" -f $TargetPid, $timestamp)
}

$runCurrentPath = Join-Path $livePath "H_cycle_current_run_id.txt"
$runInProgressPath = Join-Path $livePath "H_run_in_progress.txt"
$runtimeStatusPath = Join-Path $livePath "H_runtime_status.json"
$eventWindowStart = (Get-Date).ToUniversalTime()
$monitorStartPath = Join-Path $livePath ("H_owner_termination_provenance.monitor_start.{0}.{1}.txt" -f $TargetPid, $timestamp)
$startLine = "{0} pid={1} run_id={2} window={3}" -f (To-UtcString $eventWindowStart), $TargetPid, $runIdNorm, $windowLabelNorm
[System.IO.File]::WriteAllText($monitorStartPath, $startLine + [Environment]::NewLine, [System.Text.Encoding]::UTF8)
if ($ReadySignalPath) {
    $readyDir = Split-Path -Parent $ReadySignalPath
    if ($readyDir) {
        New-Item -ItemType Directory -Force -Path $readyDir | Out-Null
    }
    [System.IO.File]::WriteAllText($ReadySignalPath, ($startLine + " ready=1" + [Environment]::NewLine), [System.Text.Encoding]::UTF8)
}

$contextPayload = Read-JsonObject -Path $ContextPath
$unavailableTelemetry = @()
$inferred = @()

$payload = [ordered]@{
    schema_version = "h_owner_termination_provenance_v1"
    capture_type = "owner_wait_window_provenance"
    run_id = $runIdNorm
    window_label = $windowLabelNorm
    window_token = $windowTokenNorm
    target_pid = [string]$TargetPid
    observed = [ordered]@{
        capture_start_utc = To-UtcString $eventWindowStart
        poll_interval_ms = [string]$PollIntervalMs
        max_wait_seconds = [string]$MaxWaitSeconds
        monitor_pid = [string]$PID
        target_identity_start = Build-ProcessNode -PidValue $TargetPid
        creator_chain_start = Build-CreatorChain -PidValue $TargetPid -MaxDepth 6
        context = $contextPayload
        runtime_status_start = Read-JsonObject $runtimeStatusPath
        run_id_current_start = (Read-FirstLine $runCurrentPath)
        run_id_in_progress_start = (Read-FirstLine $runInProgressPath)
    }
    liveness = [ordered]@{
        last_seen_utc = ""
        disappearance_utc = ""
        capture_end_utc = ""
        exit_detection = ""
        stop_signal_observed = "0"
        stop_signal_payload = $null
    }
    correlation = [ordered]@{
        task_scheduler_operational = $null
        security = $null
        security_4688_4689 = $null
        application = $null
        system = $null
    }
    authoritative_linkage = [ordered]@{
        target_pid_dec = [string]$TargetPid
        target_pid_hex = ("0x{0:X}" -f [int]$TargetPid)
        security_process_audit = $null
        attribution_possible = "0"
        attribution_level = "none"
        best_available_control_boundary = ""
    }
    observed_end = [ordered]@{
        target_identity_end = $null
        creator_chain_end = @()
        runtime_status_end = $null
        run_id_current_end = ""
        run_id_in_progress_end = ""
    }
    unavailable = @()
    inferred = @()
}

try {
    $processInfo = Get-ProcessInfo -PidValue $TargetPid
    if (-not $processInfo) {
        $payload.liveness.exit_detection = "missing_at_capture_start"
        $payload.liveness.disappearance_utc = To-UtcString ((Get-Date).ToUniversalTime())
        $payload.liveness.capture_end_utc = $payload.liveness.disappearance_utc
    } else {
        $deadlineUtc = (Get-Date).ToUniversalTime().AddSeconds([double]$MaxWaitSeconds)
        while (-not $payload.liveness.capture_end_utc) {
            $nowUtc = (Get-Date).ToUniversalTime()
            if ($StopSignalPath -and (Test-Path $StopSignalPath)) {
                $payload.liveness.stop_signal_observed = "1"
                $payload.liveness.stop_signal_payload = Read-JsonObject -Path $StopSignalPath
                $currentInfo = Get-ProcessInfo -PidValue $TargetPid
                if ($currentInfo) {
                    $payload.liveness.last_seen_utc = To-UtcString $nowUtc
                    $payload.liveness.exit_detection = "stop_signal_observed_target_still_alive"
                    $payload.liveness.capture_end_utc = To-UtcString $nowUtc
                } else {
                    $payload.liveness.disappearance_utc = To-UtcString $nowUtc
                    $payload.liveness.exit_detection = "stop_signal_observed_target_missing"
                    $payload.liveness.capture_end_utc = $payload.liveness.disappearance_utc
                }
                break
            }
            $currentInfo = Get-ProcessInfo -PidValue $TargetPid
            if ($currentInfo) {
                $payload.liveness.last_seen_utc = To-UtcString $nowUtc
                if ($nowUtc -ge $deadlineUtc) {
                    $payload.liveness.exit_detection = "capture_timeout_target_still_alive"
                    $payload.liveness.capture_end_utc = To-UtcString $nowUtc
                    break
                }
                Start-Sleep -Milliseconds $PollIntervalMs
                continue
            }
            $payload.liveness.disappearance_utc = To-UtcString $nowUtc
            $payload.liveness.exit_detection = "missing_from_win32_process"
            $payload.liveness.capture_end_utc = $payload.liveness.disappearance_utc
            break
        }
    }

    if (-not $payload.liveness.capture_end_utc) {
        $payload.liveness.capture_end_utc = To-UtcString ((Get-Date).ToUniversalTime())
        if (-not $payload.liveness.exit_detection) {
            $payload.liveness.exit_detection = "capture_ended_without_terminal_condition"
        }
    }

    $windowStart = $eventWindowStart.AddMinutes(-1)
    $windowEnd = ([datetime]::Parse($payload.liveness.capture_end_utc)).AddMinutes(1)
    $targetPidHex = ("0x{0:X}" -f [int]$TargetPid)
    $patterns = @(
        [string]$TargetPid,
        $targetPidHex,
        $runIdNorm,
        "AMZ H Cycle",
        "run_H_cycle.bat",
        "python.exe"
    )

    $payload.correlation.task_scheduler_operational = Select-RelevantEvents -SourceName "task_scheduler_operational" -LogName "Microsoft-Windows-TaskScheduler/Operational" -StartUtc $windowStart -EndUtc $windowEnd -Patterns $patterns
    $payload.correlation.security = Select-RelevantEvents -SourceName "security_generic" -LogName "Security" -StartUtc $windowStart -EndUtc $windowEnd -Patterns $patterns
    $payload.correlation.security_4688_4689 = Select-RelevantEvents -SourceName "security_4688_4689" -LogName "Security" -StartUtc $windowStart -EndUtc $windowEnd -Patterns $patterns -EventIds @(4688,4689)
    $payload.correlation.application = Select-RelevantEvents -SourceName "application" -LogName "Application" -StartUtc $windowStart -EndUtc $windowEnd -Patterns $patterns
    $payload.correlation.system = Select-RelevantEvents -SourceName "system" -LogName "System" -StartUtc $windowStart -EndUtc $windowEnd -Patterns $patterns

    $securityLinkage = Build-SecurityTerminationLinkage -SecurityOutcome $payload.correlation.security_4688_4689 -TargetPidText ([string]$TargetPid) -TargetPidHex $targetPidHex
    $payload.authoritative_linkage.security_process_audit = $securityLinkage
    $payload.authoritative_linkage.attribution_possible = [string]$securityLinkage.attribution_possible
    $payload.authoritative_linkage.attribution_level = [string]$securityLinkage.attribution_level
    if ([string]$securityLinkage.attribution_possible -eq "1") {
        $payload.authoritative_linkage.best_available_control_boundary = "security_process_audit_linkage"
    } elseif ([string]$payload.liveness.exit_detection -match "missing") {
        $payload.authoritative_linkage.best_available_control_boundary = "win32_process_disappearance_only"
    } else {
        $payload.authoritative_linkage.best_available_control_boundary = "no_boundary_signal"
    }

    $payload.observed_end.target_identity_end = Build-ProcessNode -PidValue $TargetPid
    $payload.observed_end.creator_chain_end = Build-CreatorChain -PidValue $TargetPid -MaxDepth 6
    $payload.observed_end.runtime_status_end = Read-JsonObject $runtimeStatusPath
    $payload.observed_end.run_id_current_end = (Read-FirstLine $runCurrentPath)
    $payload.observed_end.run_id_in_progress_end = (Read-FirstLine $runInProgressPath)

    $integrityUnavailable = [ordered]@{
        source = "integrity_level"
        status = "unavailable"
        reason = "not_collected_in_current_capture"
    }
    $unavailableTelemetry += $integrityUnavailable
    foreach ($sourceName in @("task_scheduler_operational", "security", "security_4688_4689", "application", "system")) {
        $entry = $payload.correlation.$sourceName
        if ($entry -and -not [bool]$entry.available) {
            $unavailableTelemetry += [ordered]@{
                source = $sourceName
                status = "unavailable"
                reason = [string]$entry.reason
            }
        }
    }
    if ([string]$payload.authoritative_linkage.attribution_possible -ne "1") {
        $unavailableTelemetry += [ordered]@{
            source = "authoritative_linkage"
            status = "unavailable"
            reason = [string]$payload.authoritative_linkage.best_available_control_boundary
        }
    }
    if ($payload.liveness.exit_detection -eq "missing_from_win32_process" -and $payload.liveness.stop_signal_observed -ne "1") {
        $inferred += [ordered]@{
            inference = "owner_disappeared_without_stop_signal"
            basis = "win32_process_missing_after_last_seen"
        }
    }
    if ($payload.liveness.exit_detection -eq "stop_signal_observed_target_still_alive") {
        $inferred += [ordered]@{
            inference = "window_closed_by_owner_wait_settle"
            basis = "stop_signal_received_before_owner_disappearance"
        }
    }
    if ([string]$payload.authoritative_linkage.attribution_possible -eq "1") {
        $inferred += [ordered]@{
            inference = "security_linkage_candidate_available"
            basis = [string]$payload.authoritative_linkage.attribution_level
        }
    }
    $payload.unavailable = $unavailableTelemetry
    $payload.inferred = $inferred

    Write-Json -Path $artifactPath -Payload $payload
} catch {
    $errorPayload = [ordered]@{
        schema_version = "h_owner_termination_provenance_v1"
        capture_type = "owner_wait_window_provenance"
        capture_error_utc = To-UtcString ((Get-Date).ToUniversalTime())
        target_pid = [string]$TargetPid
        monitor_pid = [string]$PID
        run_id = $runIdNorm
        window_label = $windowLabelNorm
        window_token = $windowTokenNorm
        error_type = $_.Exception.GetType().FullName
        error_message = $_.Exception.Message
        partial_payload = $payload
    }
    Write-Json -Path $errorArtifactPath -Payload $errorPayload
    throw
}
