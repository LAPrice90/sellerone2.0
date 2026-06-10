param(
    [string]$Root = '',
    [string]$TaskName = 'AMZ H Cycle',
    [string]$RequestPath = '',
    [switch]$Once,
    [switch]$DryRun,
    [switch]$StatusOnly,
    [int]$MaxRequestAgeMinutes = 30
)

$ErrorActionPreference = 'Stop'

$FORBIDDEN_ACTIONS = @(
    'no Google Sheets writes',
    'no price changes',
    'no queue edits',
    'no local DB alignment',
    'no purchase orders',
    'no receiving events',
    'no send-to-Amazon handoff',
    'no output deletion',
    'no market proof scan'
)

function Get-UtcStamp {
    return [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
}

function Get-UtcFileStamp {
    return [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
}

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

function Normalize-Text {
    param($Value)
    if ($null -eq $Value) {
        return ''
    }
    return ([string]$Value).Replace("`r", '').Trim()
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
    $json = $Payload | ConvertTo-Json -Depth 16
    [IO.File]::WriteAllText($tmp, $json + [Environment]::NewLine, [Text.Encoding]::ASCII)
    Move-Item -LiteralPath $tmp -Destination $Path -Force
}

function Read-JsonObject {
    param([string]$Path)
    $raw = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop
    if ([string]::IsNullOrWhiteSpace($raw)) {
        throw 'request_json_empty'
    }
    return ($raw | ConvertFrom-Json -ErrorAction Stop)
}

function Test-PathUnder {
    param(
        [string]$Candidate,
        [string]$Parent
    )
    $candidateFull = [IO.Path]::GetFullPath($Candidate)
    $parentFull = [IO.Path]::GetFullPath($Parent)
    if (-not $parentFull.EndsWith('\')) {
        $parentFull += '\'
    }
    return $candidateFull.StartsWith($parentFull, [StringComparison]::OrdinalIgnoreCase)
}

function Sanitize-FilePart {
    param([string]$Value)
    $safe = ([string]$Value) -replace '[^A-Za-z0-9_.-]', '_'
    if ([string]::IsNullOrWhiteSpace($safe)) {
        return 'request'
    }
    if ($safe.Length -gt 80) {
        return $safe.Substring(0, 80)
    }
    return $safe
}

function Quote-CommandArg {
    param([string]$Value)
    return '"' + ([string]$Value).Replace('"', '\"') + '"'
}

function Validate-Request {
    param($Request)
    $errors = @()
    $action = Normalize-Text $Request.action
    $flow = Normalize-Text $Request.flow
    $requestId = Normalize-Text $Request.request_id
    $reason = Normalize-Text $Request.reason
    $requestedUtcRaw = Normalize-Text $Request.requested_utc

    if ($flow -ne 'H') {
        $errors += 'flow_must_be_H'
    }
    if ($action -notin @('status', 'pause', 'resume')) {
        $errors += 'action_must_be_status_pause_or_resume'
    }
    if ($requestId -notmatch '^[A-Za-z0-9_.:-]{1,120}$') {
        $errors += 'request_id_has_unsafe_characters'
    }
    if ([string]::IsNullOrWhiteSpace($reason) -or $reason.Length -gt 160 -or $reason -match '[\r\n]') {
        $errors += 'reason_must_be_short_single_line_text'
    }
    if ([string]::IsNullOrWhiteSpace($requestedUtcRaw)) {
        $errors += 'requested_utc_required'
    } else {
        try {
            $requestedUtc = [DateTimeOffset]::Parse($requestedUtcRaw).UtcDateTime
            $ageMinutes = ([DateTime]::UtcNow - $requestedUtc).TotalMinutes
            if ($ageMinutes -gt $MaxRequestAgeMinutes) {
                $errors += 'request_is_too_old'
            }
            if ($ageMinutes -lt -5) {
                $errors += 'request_is_from_future'
            }
        } catch {
            $errors += 'requested_utc_not_parseable'
        }
    }

    return [ordered]@{
        ok = ($errors.Count -eq 0)
        errors = $errors
        action = $action
        flow = $flow
        request_id = $requestId
        reason = $reason
    }
}

function Invoke-HIsolation {
    param(
        [string]$RepoRoot,
        [string]$Action,
        [string]$IsolationTaskName
    )
    $scriptPath = Join-Path $RepoRoot 'scripts\tools\h_validation_isolation.ps1'
    if (-not (Test-Path -LiteralPath $scriptPath)) {
        throw 'h_validation_isolation_missing'
    }
    $args = @(
        '-NoProfile',
        '-ExecutionPolicy',
        'Bypass',
        '-File',
        (Quote-CommandArg $scriptPath),
        '-Action',
        $Action,
        '-Root',
        (Quote-CommandArg $RepoRoot),
        '-TaskName',
        (Quote-CommandArg $IsolationTaskName)
    )
    if ($DryRun) {
        $args += '-DryRun'
    }
    $tmpOut = [IO.Path]::GetTempFileName()
    $tmpErr = [IO.Path]::GetTempFileName()
    try {
        $proc = Start-Process -FilePath 'powershell.exe' -ArgumentList $args -NoNewWindow -PassThru -Wait -RedirectStandardOutput $tmpOut -RedirectStandardError $tmpErr
        $stdout = ''
        $stderr = ''
        try { $stdout = Get-Content -LiteralPath $tmpOut -Raw -ErrorAction Stop } catch {}
        try { $stderr = Get-Content -LiteralPath $tmpErr -Raw -ErrorAction Stop } catch {}
        $parsed = $null
        try {
            if (-not [string]::IsNullOrWhiteSpace($stdout)) {
                $parsed = $stdout | ConvertFrom-Json -ErrorAction Stop
            }
        } catch {
            $parsed = $null
        }
        return [ordered]@{
            rc = [int]$proc.ExitCode
            stdout = Normalize-Text $stdout
            stderr = Normalize-Text $stderr
            parsed_json = $parsed
        }
    } finally {
        Remove-Item -LiteralPath $tmpOut -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $tmpErr -Force -ErrorAction SilentlyContinue
    }
}

function Archive-Request {
    param(
        [string]$ActiveRequestPath,
        [string]$ArchiveDir,
        [string]$RequestId,
        [string]$Action
    )
    if (-not (Test-Path -LiteralPath $ActiveRequestPath)) {
        return ''
    }
    if (-not (Test-Path -LiteralPath $ArchiveDir)) {
        New-Item -ItemType Directory -Path $ArchiveDir -Force | Out-Null
    }
    $leaf = (Get-UtcFileStamp) + '_' + (Sanitize-FilePart $RequestId) + '_' + (Sanitize-FilePart $Action) + '.json'
    $archivePath = Join-Path $ArchiveDir $leaf
    Copy-Item -LiteralPath $ActiveRequestPath -Destination $archivePath -Force
    Remove-Item -LiteralPath $ActiveRequestPath -Force
    return $archivePath
}

$repoRoot = Resolve-RepoRoot -ArgRoot $Root
$locksDir = Join-Path $repoRoot 'out\locks'
$liveDir = Join-Path $repoRoot 'out\systems\H\live'
if (-not $RequestPath) {
    $RequestPath = Join-Path $locksDir 'h_maintenance_request.json'
}
$requestFullPath = [IO.Path]::GetFullPath($RequestPath)
$resultPath = Join-Path $locksDir 'h_maintenance_controller_last_result.json'
$statusPath = Join-Path $liveDir 'h_maintenance_controller_status.json'
$archiveDir = Join-Path $locksDir 'h_maintenance_requests\archive'

if (-not (Test-PathUnder -Candidate $requestFullPath -Parent $locksDir)) {
    $result = [ordered]@{
        schema_version = '1'
        controller = 'h_maintenance_controller'
        observed_utc = Get-UtcStamp
        success = $false
        action = 'reject'
        failure_reason = 'request_path_outside_out_locks'
        request_path = $requestFullPath
        forbidden_actions = $FORBIDDEN_ACTIONS
    }
    Write-JsonAtomic -Path $resultPath -Payload $result
    Write-JsonAtomic -Path $statusPath -Payload $result
    exit 2
}

$request = $null
$validation = $null
if ($StatusOnly) {
    $request = [ordered]@{
        schema_version = '1'
        flow = 'H'
        action = 'status'
        reason = 'controller_status_only'
        request_id = 'STATUS_ONLY_' + (Get-UtcFileStamp)
        requested_by = 'h_maintenance_controller'
        requested_utc = Get-UtcStamp
    }
    $validation = Validate-Request -Request $request
} elseif (Test-Path -LiteralPath $requestFullPath) {
    try {
        $request = Read-JsonObject -Path $requestFullPath
        $validation = Validate-Request -Request $request
    } catch {
        $result = [ordered]@{
            schema_version = '1'
            controller = 'h_maintenance_controller'
            observed_utc = Get-UtcStamp
            success = $false
            action = 'reject'
            failure_reason = 'request_json_unreadable'
            error = $_.Exception.Message
            request_path = $requestFullPath
            forbidden_actions = $FORBIDDEN_ACTIONS
        }
        Write-JsonAtomic -Path $resultPath -Payload $result
        Write-JsonAtomic -Path $statusPath -Payload $result
        exit 2
    }
} else {
    $result = [ordered]@{
        schema_version = '1'
        controller = 'h_maintenance_controller'
        observed_utc = Get-UtcStamp
        success = $true
        action = 'no_request'
        failure_reason = ''
        request_path = $requestFullPath
        forbidden_actions = $FORBIDDEN_ACTIONS
    }
    Write-JsonAtomic -Path $resultPath -Payload $result
    Write-JsonAtomic -Path $statusPath -Payload $result
    exit 0
}

if (-not [bool]$validation.ok) {
    $archivePath = Archive-Request -ActiveRequestPath $requestFullPath -ArchiveDir $archiveDir -RequestId $validation.request_id -Action 'rejected'
    $result = [ordered]@{
        schema_version = '1'
        controller = 'h_maintenance_controller'
        observed_utc = Get-UtcStamp
        success = $false
        action = 'reject'
        failure_reason = 'request_validation_failed'
        validation_errors = $validation.errors
        request = $request
        request_archive_path = $archivePath
        forbidden_actions = $FORBIDDEN_ACTIONS
    }
    Write-JsonAtomic -Path $resultPath -Payload $result
    Write-JsonAtomic -Path $statusPath -Payload $result
    exit 2
}

$running = [ordered]@{
    schema_version = '1'
    controller = 'h_maintenance_controller'
    observed_utc = Get-UtcStamp
    state = 'running'
    action = $validation.action
    request_id = $validation.request_id
    reason = $validation.reason
    dry_run = [bool]$DryRun
    forbidden_actions = $FORBIDDEN_ACTIONS
}
Write-JsonAtomic -Path $statusPath -Payload $running

$requestArchivePath = ''
if (-not $StatusOnly) {
    $requestArchivePath = Archive-Request -ActiveRequestPath $requestFullPath -ArchiveDir $archiveDir -RequestId $validation.request_id -Action $validation.action
}

$invoke = $null
$success = $false
$failure = ''
try {
    $invoke = Invoke-HIsolation -RepoRoot $repoRoot -Action $validation.action -IsolationTaskName $TaskName
    $success = ([int]$invoke.rc -eq 0)
    if (-not $success) {
        $failure = 'h_isolation_returned_nonzero'
    }
} catch {
    $success = $false
    $failure = $_.Exception.Message
    $invoke = [ordered]@{
        rc = 99
        stdout = ''
        stderr = $_.Exception.Message
        parsed_json = $null
    }
}

$result = [ordered]@{
    schema_version = '1'
    controller = 'h_maintenance_controller'
    observed_utc = Get-UtcStamp
    success = [bool]$success
    action = $validation.action
    flow = 'H'
    request_id = $validation.request_id
    reason = $validation.reason
    request = $request
    request_path = $requestFullPath
    request_archive_path = $requestArchivePath
    dry_run = [bool]$DryRun
    isolation = $invoke
    failure_reason = $failure
    forbidden_actions = $FORBIDDEN_ACTIONS
}
Write-JsonAtomic -Path $resultPath -Payload $result
Write-JsonAtomic -Path $statusPath -Payload $result

if (-not $success) {
    if ($invoke -and [int]$invoke.rc -gt 0 -and [int]$invoke.rc -lt 90) {
        exit ([int]$invoke.rc)
    }
    exit 3
}

exit 0
