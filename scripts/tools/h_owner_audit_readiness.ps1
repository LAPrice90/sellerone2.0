param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('status', 'enable', 'revert')]
    [string]$Action,
    [string]$Root = '',
    [string]$BaselinePath = '',
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

function Resolve-RepoRoot {
    param([string]$ArgRoot)
    if ($ArgRoot) {
        return (Resolve-Path -LiteralPath $ArgRoot).Path
    }
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    return (Resolve-Path -LiteralPath (Join-Path $scriptDir '..\..')).Path
}

function To-UtcNow {
    return (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
}

function Normalize-Text {
    param($Value)
    if ($null -eq $Value) {
        return ''
    }
    return ([string]$Value).Replace("`r", '').Trim()
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

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Args,
        [switch]$AllowFail
    )
    $tmpOut = [IO.Path]::GetTempFileName()
    $tmpErr = [IO.Path]::GetTempFileName()
    try {
        $proc = Start-Process -FilePath $FilePath -ArgumentList $Args -NoNewWindow -PassThru -Wait -RedirectStandardOutput $tmpOut -RedirectStandardError $tmpErr
        $stdout = ''
        $stderr = ''
        try { $stdout = Get-Content -LiteralPath $tmpOut -Raw -ErrorAction Stop } catch {}
        try { $stderr = Get-Content -LiteralPath $tmpErr -Raw -ErrorAction Stop } catch {}
        $result = [ordered]@{
            rc = [int]$proc.ExitCode
            stdout = Normalize-Text -Value $stdout
            stderr = Normalize-Text -Value $stderr
            command = ($FilePath + ' ' + ($Args -join ' '))
        }
        if (-not $AllowFail -and $result.rc -ne 0) {
            throw ('command_failed rc=' + $result.rc + ' cmd=' + $result.command + ' stderr=' + $result.stderr)
        }
        return $result
    } finally {
        Remove-Item -LiteralPath $tmpOut -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $tmpErr -Force -ErrorAction SilentlyContinue
    }
}

function Invoke-CmdLine {
    param(
        [Parameter(Mandatory = $true)][string]$CommandText,
        [switch]$AllowFail
    )
    return Invoke-Native -FilePath 'cmd.exe' -Args @('/c', $CommandText) -AllowFail:$AllowFail
}

function Parse-AuditPolicyOutput {
    param([string]$Text)
    $line = ''
    foreach ($raw in ($Text -split "`n")) {
        $clean = Normalize-Text -Value $raw
        if (-not $clean) {
            continue
        }
        if ($clean -match '^(Machine Name|Policy Target|Subcategory,|System audit policy)') {
            continue
        }
        if ($clean -match 'Process Creation|Process Termination') {
            $line = $clean
            break
        }
    }
    if (-not $line) {
        return @{
            parsed = $false
            inclusion = ''
            success = $false
            failure = $false
            reason = 'subcategory_line_not_found'
        }
    }
    $parts = $line -split ','
    $inclusion = ''
    if ($parts.Count -ge 5) {
        $inclusion = Normalize-Text -Value $parts[4]
    } elseif ($parts.Count -ge 1) {
        $inclusion = Normalize-Text -Value $parts[-1]
    }
    $inclusionLower = $inclusion.ToLowerInvariant()
    return @{
        parsed = $true
        inclusion = $inclusion
        success = ($inclusionLower -match 'success')
        failure = ($inclusionLower -match 'failure')
        reason = ''
    }
}

function Get-AuditPolicySubcategory {
    param([string]$Subcategory)
    $commandText = 'auditpol /get /subcategory:"' + $Subcategory + '" /r'
    $query = Invoke-CmdLine -CommandText $commandText -AllowFail
    $available = ($query.rc -eq 0)
    $access = 'ok'
    $status = 'ok'
    $reason = ''
    if (-not $available) {
        $status = 'query_failed'
        $reason = $query.stderr
        if ($reason.ToLowerInvariant().Contains('0x00000522')) {
            $access = 'privilege_missing'
            $status = 'privilege_missing'
        } elseif ($reason.ToLowerInvariant().Contains('access is denied')) {
            $access = 'access_denied'
            $status = 'access_denied'
        } else {
            $access = 'error'
        }
    }
    $parsed = @{
        parsed = $false
        inclusion = ''
        success = $false
        failure = $false
        reason = 'not_parsed'
    }
    if ($available) {
        $parsed = Parse-AuditPolicyOutput -Text $query.stdout
    }
    return [ordered]@{
        source = 'auditpol'
        subcategory = $Subcategory
        attempted = $true
        available = $available
        access_result = $access
        query_status = $status
        reason = $reason
        raw_stdout = $query.stdout
        raw_stderr = $query.stderr
        parsed = $parsed
    }
}

function Set-AuditPolicySubcategory {
    param(
        [string]$Subcategory,
        [bool]$SuccessEnabled,
        [bool]$FailureEnabled
    )
    $successValue = if ($SuccessEnabled) { 'enable' } else { 'disable' }
    $failureValue = if ($FailureEnabled) { 'enable' } else { 'disable' }
    $commandText = 'auditpol /set /subcategory:"' + $Subcategory + '" /success:' + $successValue + ' /failure:' + $failureValue
    $result = Invoke-CmdLine -CommandText $commandText -AllowFail
    return [ordered]@{
        subcategory = $Subcategory
        desired_success = $SuccessEnabled
        desired_failure = $FailureEnabled
        rc = $result.rc
        stdout = $result.stdout
        stderr = $result.stderr
    }
}

function Get-ProcessCmdlineAuditPolicy {
    $query = Invoke-CmdLine -CommandText 'reg query "HKLM\Software\Microsoft\Windows\CurrentVersion\Policies\System\Audit" /v ProcessCreationIncludeCmdLine_Enabled' -AllowFail
    if ($query.rc -ne 0) {
        return [ordered]@{
            source = 'registry_process_creation_cmdline'
            attempted = $true
            available = $false
            value = ''
            enabled = $false
            query_status = 'missing_or_unreadable'
            reason = $query.stderr
            raw_stdout = $query.stdout
        }
    }
    $value = ''
    foreach ($line in ($query.stdout -split "`n")) {
        $clean = Normalize-Text -Value $line
        if ($clean -match 'ProcessCreationIncludeCmdLine_Enabled') {
            $parts = $clean -split '\s+'
            if ($parts.Count -ge 3) {
                $value = $parts[-1]
            }
            break
        }
    }
    $enabled = $false
    if ($value) {
        try {
            if ($value.ToLowerInvariant().StartsWith('0x')) {
                $enabled = ([Convert]::ToInt32($value, 16) -ne 0)
            } else {
                $enabled = ([int]$value -ne 0)
            }
        } catch {
            $enabled = $false
        }
    }
    return [ordered]@{
        source = 'registry_process_creation_cmdline'
        attempted = $true
        available = $true
        value = $value
        enabled = $enabled
        query_status = 'ok'
        reason = ''
        raw_stdout = $query.stdout
    }
}

function Set-ProcessCmdlineAuditPolicy {
    param([bool]$Enabled)
    $valueText = if ($Enabled) { '1' } else { '0' }
    $commandText = 'reg add "HKLM\Software\Microsoft\Windows\CurrentVersion\Policies\System\Audit" /v ProcessCreationIncludeCmdLine_Enabled /t REG_DWORD /d ' + $valueText + ' /f'
    $result = Invoke-CmdLine -CommandText $commandText -AllowFail
    return [ordered]@{
        desired_enabled = $Enabled
        rc = $result.rc
        stdout = $result.stdout
        stderr = $result.stderr
    }
}

function Get-SecurityChannelReadStatus {
    try {
        $entry = Get-WinEvent -LogName 'Security' -MaxEvents 1 -ErrorAction Stop
        if ($entry) {
            return [ordered]@{
                attempted = $true
                available = $true
                query_status = 'ok'
                access_result = 'ok'
                reason = ''
            }
        }
    } catch {
        $reason = Normalize-Text -Value $_.Exception.Message
        $lower = $reason.ToLowerInvariant()
        if ($lower.Contains('no events were found')) {
            return [ordered]@{
                attempted = $true
                available = $true
                query_status = 'no_records'
                access_result = 'ok'
                reason = $reason
            }
        }
        if ($lower.Contains('unauthorized') -or $lower.Contains('access is denied')) {
            return [ordered]@{
                attempted = $true
                available = $false
                query_status = 'access_denied'
                access_result = 'denied'
                reason = $reason
            }
        }
        return [ordered]@{
            attempted = $true
            available = $false
            query_status = 'query_failed'
            access_result = 'error'
            reason = $reason
        }
    }
    return [ordered]@{
        attempted = $true
        available = $false
        query_status = 'unknown'
        access_result = 'error'
        reason = 'unexpected_null_result'
    }
}

function Get-SecurityProcessEventStatus {
    param([int]$EventId)
    try {
        $events = Get-WinEvent -FilterHashtable @{ LogName = 'Security'; Id = $EventId } -MaxEvents 1 -ErrorAction Stop
        if ($events) {
            return [ordered]@{
                attempted = $true
                available = $true
                query_status = 'ok'
                access_result = 'ok'
                records_found = 1
                reason = ''
            }
        }
    } catch {
        $reason = Normalize-Text -Value $_.Exception.Message
        $lower = $reason.ToLowerInvariant()
        if ($lower.Contains('no events were found')) {
            return [ordered]@{
                attempted = $true
                available = $true
                query_status = 'no_records'
                access_result = 'ok'
                records_found = 0
                reason = $reason
            }
        }
        if ($lower.Contains('unauthorized') -or $lower.Contains('access is denied')) {
            return [ordered]@{
                attempted = $true
                available = $false
                query_status = 'access_denied'
                access_result = 'denied'
                records_found = 0
                reason = $reason
            }
        }
        return [ordered]@{
            attempted = $true
            available = $false
            query_status = 'query_failed'
            access_result = 'error'
            records_found = 0
            reason = $reason
        }
    }
    return [ordered]@{
        attempted = $true
        available = $false
        query_status = 'unknown'
        access_result = 'error'
        records_found = 0
        reason = 'unexpected_null_result'
    }
}

function Get-AuditReadiness {
    $procCreate = Get-AuditPolicySubcategory -Subcategory 'Process Creation'
    $procTerminate = Get-AuditPolicySubcategory -Subcategory 'Process Termination'
    $cmdlinePolicy = Get-ProcessCmdlineAuditPolicy
    $securityRead = Get-SecurityChannelReadStatus
    $event4688 = Get-SecurityProcessEventStatus -EventId 4688
    $event4689 = Get-SecurityProcessEventStatus -EventId 4689

    $processCreationSuccessEnabled = ($procCreate.available -and $procCreate.parsed.parsed -and [bool]$procCreate.parsed.success)
    $processTerminationSuccessEnabled = ($procTerminate.available -and $procTerminate.parsed.parsed -and [bool]$procTerminate.parsed.success)
    $securityReadable = ([bool]$securityRead.available)
    $minimumReady = $processCreationSuccessEnabled -and $processTerminationSuccessEnabled -and $securityReadable
    $cmdlineReady = ($cmdlinePolicy.available -and [bool]$cmdlinePolicy.enabled)

    return [ordered]@{
        checked_utc = To-UtcNow
        is_admin = (Test-IsAdmin)
        sources = [ordered]@{
            audit_process_creation = $procCreate
            audit_process_termination = $procTerminate
            process_creation_cmdline_policy = $cmdlinePolicy
            security_channel_read = $securityRead
            security_event_4688 = $event4688
            security_event_4689 = $event4689
        }
        assessment = [ordered]@{
            minimum_process_audit_policy_ready = $minimumReady
            process_creation_success_enabled = $processCreationSuccessEnabled
            process_termination_success_enabled = $processTerminationSuccessEnabled
            security_channel_readable = $securityReadable
            cmdline_capture_enabled = $cmdlineReady
            ready_for_owner_termination_capture = $minimumReady
            ready_reason = $(if ($minimumReady) { 'minimum_ready' } else { 'missing_prerequisites' })
        }
    }
}

function Assert-Admin {
    if ($DryRun) {
        return
    }
    if (-not (Test-IsAdmin)) {
        throw 'elevation_required: run from elevated PowerShell or cmd (Run as administrator).'
    }
}

function Write-JsonFile {
    param(
        [string]$Path,
        [object]$Payload
    )
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    $tmp = "$Path.tmp"
    [IO.File]::WriteAllText($tmp, ((ConvertTo-Json $Payload -Depth 12) + [Environment]::NewLine), [Text.Encoding]::UTF8)
    Move-Item -LiteralPath $tmp -Destination $Path -Force
}

$repoRoot = Resolve-RepoRoot -ArgRoot $Root
$baselineDefault = Join-Path $repoRoot 'out\systems\H\live\H_owner_audit_policy_baseline.json'
$baselineFile = if ($BaselinePath) { $BaselinePath } else { $baselineDefault }

switch ($Action) {
    'status' {
        [ordered]@{
            action = 'status'
            dry_run = [bool]$DryRun
            repo_root = $repoRoot
            baseline_file = $baselineFile
            readiness = Get-AuditReadiness
        } | ConvertTo-Json -Depth 12
        exit 0
    }

    'enable' {
        Assert-Admin
        $before = Get-AuditReadiness
        $changes = @()
        $savedBaseline = $false

        $baselinePayload = [ordered]@{
            saved_utc = To-UtcNow
            source = 'h_owner_audit_readiness_enable'
            before = $before
        }
        if ($DryRun) {
            $savedBaseline = $true
            $changes += 'DRY_RUN baseline_save'
        } else {
            Write-JsonFile -Path $baselineFile -Payload $baselinePayload
            $savedBaseline = $true
            $changes += ('baseline_saved=' + $baselineFile)
        }

        $setResults = @()
        $procCreateBefore = $before.sources.audit_process_creation
        $procTerminateBefore = $before.sources.audit_process_termination
        if (-not $procCreateBefore.available -or -not $procCreateBefore.parsed.parsed) {
            throw 'enable_failed: process creation audit policy is not readable in this context.'
        }
        if (-not $procTerminateBefore.available -or -not $procTerminateBefore.parsed.parsed) {
            throw 'enable_failed: process termination audit policy is not readable in this context.'
        }

        if (-not [bool]$procCreateBefore.parsed.success) {
            if ($DryRun) {
                $setResults += [ordered]@{ subcategory = 'Process Creation'; action = 'DRY_RUN set_success_enable' }
            } else {
                $setResults += Set-AuditPolicySubcategory -Subcategory 'Process Creation' -SuccessEnabled $true -FailureEnabled ([bool]$procCreateBefore.parsed.failure)
            }
            $changes += 'process_creation_success_enabled'
        }
        if (-not [bool]$procTerminateBefore.parsed.success) {
            if ($DryRun) {
                $setResults += [ordered]@{ subcategory = 'Process Termination'; action = 'DRY_RUN set_success_enable' }
            } else {
                $setResults += Set-AuditPolicySubcategory -Subcategory 'Process Termination' -SuccessEnabled $true -FailureEnabled ([bool]$procTerminateBefore.parsed.failure)
            }
            $changes += 'process_termination_success_enabled'
        }
        $cmdlineBefore = $before.sources.process_creation_cmdline_policy
        if (-not ($cmdlineBefore.available -and [bool]$cmdlineBefore.enabled)) {
            if ($DryRun) {
                $setResults += [ordered]@{ source = 'registry_process_creation_cmdline'; action = 'DRY_RUN set_enabled_1' }
            } else {
                $setResults += Set-ProcessCmdlineAuditPolicy -Enabled $true
            }
            $changes += 'process_creation_cmdline_enabled'
        }

        $after = Get-AuditReadiness
        $success = [bool]$after.assessment.ready_for_owner_termination_capture
        if ($DryRun) {
            $success = $true
        }
        [ordered]@{
            action = 'enable'
            dry_run = [bool]$DryRun
            repo_root = $repoRoot
            baseline_file = $baselineFile
            baseline_saved = $savedBaseline
            changes = $changes
            set_results = $setResults
            before = $before
            after = $after
            success = $success
            failure_reason = $(if ($success) { '' } else { 'environment_not_ready_after_enable' })
        } | ConvertTo-Json -Depth 12
        if (-not $success) {
            exit 2
        }
        exit 0
    }

    'revert' {
        Assert-Admin
        if (-not (Test-Path -LiteralPath $baselineFile)) {
            [ordered]@{
                action = 'revert'
                dry_run = [bool]$DryRun
                repo_root = $repoRoot
                baseline_file = $baselineFile
                success = $false
                failure_reason = 'baseline_file_missing'
            } | ConvertTo-Json -Depth 12
            exit 3
        }
        $baseline = Get-Content -LiteralPath $baselineFile -Raw | ConvertFrom-Json -AsHashtable
        $before = Get-AuditReadiness
        $setResults = @()
        $changes = @()

        $restoreCreate = $baseline.before.sources.audit_process_creation
        $restoreTerminate = $baseline.before.sources.audit_process_termination
        $restoreCmdline = $baseline.before.sources.process_creation_cmdline_policy

        if ($restoreCreate -and $restoreCreate.parsed -and $restoreCreate.parsed.parsed) {
            $targetSuccess = [bool]$restoreCreate.parsed.success
            $targetFailure = [bool]$restoreCreate.parsed.failure
            if ($DryRun) {
                $setResults += [ordered]@{ subcategory = 'Process Creation'; action = 'DRY_RUN restore'; success = $targetSuccess; failure = $targetFailure }
            } else {
                $setResults += Set-AuditPolicySubcategory -Subcategory 'Process Creation' -SuccessEnabled $targetSuccess -FailureEnabled $targetFailure
            }
            $changes += 'restore_process_creation_audit'
        }
        if ($restoreTerminate -and $restoreTerminate.parsed -and $restoreTerminate.parsed.parsed) {
            $targetSuccess = [bool]$restoreTerminate.parsed.success
            $targetFailure = [bool]$restoreTerminate.parsed.failure
            if ($DryRun) {
                $setResults += [ordered]@{ subcategory = 'Process Termination'; action = 'DRY_RUN restore'; success = $targetSuccess; failure = $targetFailure }
            } else {
                $setResults += Set-AuditPolicySubcategory -Subcategory 'Process Termination' -SuccessEnabled $targetSuccess -FailureEnabled $targetFailure
            }
            $changes += 'restore_process_termination_audit'
        }
        if ($restoreCmdline -and $restoreCmdline.available) {
            $targetCmdline = [bool]$restoreCmdline.enabled
            if ($DryRun) {
                $setResults += [ordered]@{ source = 'registry_process_creation_cmdline'; action = 'DRY_RUN restore'; enabled = $targetCmdline }
            } else {
                $setResults += Set-ProcessCmdlineAuditPolicy -Enabled $targetCmdline
            }
            $changes += 'restore_process_creation_cmdline_policy'
        }

        $after = Get-AuditReadiness
        [ordered]@{
            action = 'revert'
            dry_run = [bool]$DryRun
            repo_root = $repoRoot
            baseline_file = $baselineFile
            changes = $changes
            set_results = $setResults
            before = $before
            after = $after
            success = $true
            failure_reason = ''
        } | ConvertTo-Json -Depth 12
        exit 0
    }
}
