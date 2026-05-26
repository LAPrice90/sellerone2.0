param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('status', 'pause', 'run-success', 'run-failure', 'resume')]
    [string]$Action,

    [string]$Root = '',
    [string]$TaskName = 'AMZ H Cycle',
    [switch]$DryRun,
    [switch]$NoAutoRunOnResume
)

$ErrorActionPreference = 'Stop'

function Resolve-RepoRoot {
    param([string]$ArgRoot)
    if ($ArgRoot) {
        return (Resolve-Path -LiteralPath $ArgRoot).Path
    }
    $scriptRoot = $PSScriptRoot
    if (-not $scriptRoot) {
        $commandPath = $PSCommandPath
        if ($commandPath) {
            $scriptRoot = Split-Path -Parent $commandPath
        }
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
    return ([string]$Value).Replace("`r", '').Replace("`n", '').Trim()
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

function Get-SafeFileLine {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return ''
    }
    try {
        return ((Get-Content -LiteralPath $Path -ErrorAction Stop | Select-Object -First 1) | Out-String).Trim()
    } catch {
        return ''
    }
}

function Read-JsonObjectWithRetry {
    param(
        [string]$Path,
        [int]$Attempts = 5,
        [int]$DelayMs = 200
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        return @{}
    }
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            $raw = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop
            if ([string]::IsNullOrWhiteSpace([string]$raw)) {
                throw 'json_empty'
            }
            return ($raw | ConvertFrom-Json -ErrorAction Stop)
        } catch {
            if ($attempt -lt $Attempts) {
                Start-Sleep -Milliseconds $DelayMs
                continue
            }
        }
    }
    return @{}
}

function Get-LockMetadata {
    param([string]$Path)
    $line = Get-SafeFileLine -Path $Path
    $lockPid = ''
    $run = ''
    if ($line -match 'pid=(\d+)') {
        $lockPid = $Matches[1]
    }
    if ($line -match 'launcher_pid=(\d+)') {
        $lockPid = $Matches[1]
    }
    if ($line -match 'run_id=([^|\s]+)') {
        $run = $Matches[1]
    }
    return @{
        path = $Path
        exists = (Test-Path -LiteralPath $Path)
        line = $line
        pid = $lockPid
        run_id = $run
    }
}

function Get-TaskState {
    param([string]$Name)
    $result = @{
        available = $false
        state = 'UNKNOWN'
        enabled = ''
        query_rc = 1
        query_stdout = ''
        query_stderr = ''
    }
    $tmpOut = [IO.Path]::GetTempFileName()
    $tmpErr = [IO.Path]::GetTempFileName()
    try {
        $taskArg = '"' + $Name + '"'
        $proc = Start-Process -FilePath 'schtasks.exe' -ArgumentList @('/Query', '/TN', $taskArg, '/V', '/FO', 'LIST') -NoNewWindow -PassThru -Wait -RedirectStandardOutput $tmpOut -RedirectStandardError $tmpErr
        $stdout = ''
        $stderr = ''
        try { $stdout = Get-Content -LiteralPath $tmpOut -Raw -ErrorAction Stop } catch {}
        try { $stderr = Get-Content -LiteralPath $tmpErr -Raw -ErrorAction Stop } catch {}
        $result.query_rc = [int]$proc.ExitCode
        $stdoutText = Normalize-Text -Value $stdout
        $stderrText = Normalize-Text -Value $stderr
        $result.query_stdout = $stdoutText
        $result.query_stderr = $stderrText
        if ($proc.ExitCode -eq 0) {
            $result.available = $true
            if ($stdout -match '(?im)^\s*Status\s*:\s*(.+)$') {
                $result.state = Normalize-Text -Value $Matches[1]
            }
            if ($stdout -match '(?im)^\s*Scheduled Task State\s*:\s*(.+)$') {
                $result.enabled = Normalize-Text -Value $Matches[1]
            }
        }
    } finally {
        Remove-Item -LiteralPath $tmpOut -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $tmpErr -Force -ErrorAction SilentlyContinue
    }
    return $result
}

function Get-HOwnerProcesses {
    param([string]$RepoRoot)
    $escaped = [regex]::Escape($RepoRoot)
    $out = @()
    try {
        $procs = Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
            $_.CommandLine -and $_.CommandLine -match $escaped -and (
                $_.CommandLine -match 'run_H_cycle\.bat' -or
                $_.CommandLine -match 'scripts\\cycles\\run_H_pricing_cycle_guarded\.py' -or
                $_.CommandLine -match 'scripts\\cycles\\run_H_pricing_cycle\.py'
            )
        }
        foreach ($p in $procs) {
            $out += [pscustomobject]@{
                pid = [string]$p.ProcessId
                parent_pid = [string]$p.ParentProcessId
                name = [string]$p.Name
                command = [string]$p.CommandLine
            }
        }
    } catch {
    }
    return @($out)
}

function Invoke-Schtasks {
    param(
        [string[]]$TaskArgs,
        [switch]$AllowFail
    )
    if ($DryRun) {
        return @{ rc = 0; stdout = ('DRY_RUN schtasks ' + ($TaskArgs -join ' ')); stderr = '' }
    }
    $tmpOut = [IO.Path]::GetTempFileName()
    $tmpErr = [IO.Path]::GetTempFileName()
    try {
        $proc = Start-Process -FilePath 'schtasks.exe' -ArgumentList $TaskArgs -NoNewWindow -PassThru -Wait -RedirectStandardOutput $tmpOut -RedirectStandardError $tmpErr
        $stdout = ''
        $stderr = ''
        try { $stdout = Get-Content -LiteralPath $tmpOut -Raw -ErrorAction Stop } catch {}
        try { $stderr = Get-Content -LiteralPath $tmpErr -Raw -ErrorAction Stop } catch {}
        $rc = [int]$proc.ExitCode
        if (-not $AllowFail -and $rc -ne 0) {
            $stderrText = ''
            if ($null -ne $stderr) { $stderrText = Normalize-Text -Value $stderr }
            throw ('schtasks failed rc=' + $rc + ' args=' + ($TaskArgs -join ' ') + ' stderr=' + $stderrText)
        }
        $stdoutText = Normalize-Text -Value $stdout
        $stderrText = Normalize-Text -Value $stderr
        return @{ rc = $rc; stdout = $stdoutText; stderr = $stderrText }
    } finally {
        Remove-Item -LiteralPath $tmpOut -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $tmpErr -Force -ErrorAction SilentlyContinue
    }
}

function Stop-HProcesses {
    param([string]$RepoRoot)
    $owners = @(Get-HOwnerProcesses -RepoRoot $RepoRoot)
    $stopped = @()
    foreach ($proc in $owners) {
        $procId = [int]$proc.pid
        if ($DryRun) {
            $stopped += ('DRY_RUN taskkill /PID ' + $procId + ' /T /F')
            continue
        }
        try {
            $tk = Start-Process -FilePath 'taskkill.exe' -ArgumentList @('/PID', [string]$procId, '/T', '/F') -NoNewWindow -PassThru -Wait
            $stopped += ('taskkill pid=' + $procId + ' rc=' + $tk.ExitCode)
        } catch {
            $stopped += ('taskkill pid=' + $procId + ' failed=' + $_.Exception.Message)
        }
    }
    return $stopped
}

function Set-ControlledMode {
    param([string]$RepoRoot)
    $flag = Join-Path $RepoRoot 'out\locks\h_controlled_mode.active'
    if ($DryRun) {
        return @{ flag_path = $flag; changed = $true; action = 'dry_run_set' }
    }
    $locks = Split-Path -Parent $flag
    if (-not (Test-Path -LiteralPath $locks)) {
        New-Item -ItemType Directory -Path $locks -Force | Out-Null
    }
    $utc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    $content = @(
        'controlled_mode=1',
        ('set_utc=' + $utc),
        ('set_by=h_validation_isolation')
    ) -join [Environment]::NewLine
    [IO.File]::WriteAllText($flag, $content + [Environment]::NewLine, [Text.Encoding]::ASCII)
    return @{ flag_path = $flag; changed = $true; action = 'set' }
}

function Clear-ControlledMode {
    param([string]$RepoRoot)
    $flag = Join-Path $RepoRoot 'out\locks\h_controlled_mode.active'
    if ($DryRun) {
        return @{ flag_path = $flag; changed = $true; action = 'dry_run_clear' }
    }
    if (Test-Path -LiteralPath $flag) {
        Remove-Item -LiteralPath $flag -Force -ErrorAction Stop
    }
    return @{ flag_path = $flag; changed = $true; action = 'clear' }
}

function Get-RepoState {
    param([string]$RepoRoot, [string]$Task)
    $live = Join-Path $RepoRoot 'out\systems\H\live'
    $statePath = Join-Path $live 'H_run_state.json'
    $runtimePath = Join-Path $live 'H_runtime_status.json'
    $inProgressPath = Join-Path $live 'H_run_in_progress.txt'
    $finalizedPath = Join-Path $live 'H_last_finalized_run_id.txt'
    $workerPath = Join-Path $live 'H_worker_lifecycle.json'
    $controlledPath = Join-Path $RepoRoot 'out\locks\h_controlled_mode.active'

    $taskState = Get-TaskState -Name $Task
    $owners = @(Get-HOwnerProcesses -RepoRoot $RepoRoot)

    $runState = Read-JsonObjectWithRetry -Path $statePath
    $runtimeState = Read-JsonObjectWithRetry -Path $runtimePath
    $workerState = Read-JsonObjectWithRetry -Path $workerPath

    return [ordered]@{
        utc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        repo_root = $RepoRoot
        is_admin = (Test-IsAdmin)
        task_name = $Task
        task = $taskState
        controlled_mode_active = (Test-Path -LiteralPath $controlledPath)
        controlled_mode_flag = $controlledPath
        owner_process_count = @($owners).Count
        owner_processes = $owners
        lock_launcher = (Get-LockMetadata -Path (Join-Path $live 'H_launcher.lock'))
        lock_cycle_live = (Get-LockMetadata -Path (Join-Path $live 'H_pricing_cycle.lock'))
        lock_cycle_root = (Get-LockMetadata -Path (Join-Path $RepoRoot 'out\H_pricing_cycle.lock'))
        run_in_progress = Get-SafeFileLine -Path $inProgressPath
        last_finalized = Get-SafeFileLine -Path $finalizedPath
        h_run_state = $runState
        h_runtime_status = $runtimeState
        h_worker_lifecycle = $workerState
    }
}

function Test-TaskEnabledState {
    param(
        [hashtable]$TaskState,
        [ValidateSet('enabled', 'disabled')]
        [string]$Expected
    )
    $enabledText = Normalize-Text -Value $TaskState.enabled
    if ($enabledText) {
        if ($Expected -eq 'disabled') {
            return ($enabledText -match 'Disabled')
        }
        return ($enabledText -notmatch 'Disabled')
    }

    $stdout = Normalize-Text -Value $TaskState.query_stdout
    if ($stdout -match '(?im)^\s*Scheduled Task State\s*:\s*(.+)$') {
        $stateText = Normalize-Text -Value $Matches[1]
        if ($Expected -eq 'disabled') {
            return ($stateText -match 'Disabled')
        }
        return ($stateText -notmatch 'Disabled')
    }
    return $false
}

function Wait-ForPauseReady {
    param(
        [string]$RepoRoot,
        [string]$Task,
        [int]$TimeoutSeconds = 18
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $attempt = 0
    $history = @()
    $lastState = $null
    $lastReconcile = [ordered]@{ success = $false; blocking_reasons = @('not_attempted') }
    $lastRemainingLocks = @()
    while ((Get-Date) -lt $deadline) {
        $attempt += 1
        $state = Get-RepoState -RepoRoot $RepoRoot -Task $Task
        $lastState = $state

        $reconcile = [ordered]@{ success = $false; blocking_reasons = @('owner_or_controlled_not_ready') }
        if (([int]$state.owner_process_count -eq 0) -and $state.controlled_mode_active) {
            $reconcile = Invoke-StaleLockReconcile -RepoRoot $RepoRoot -State $state -RequirePaused
            $state = Get-RepoState -RepoRoot $RepoRoot -Task $Task
            $lastState = $state
        }
        $lastReconcile = $reconcile

        $remainingLocks = @($state.lock_launcher, $state.lock_cycle_live, $state.lock_cycle_root) | Where-Object { $_.exists }
        $lastRemainingLocks = $remainingLocks

        $taskDisabled = Test-TaskEnabledState -TaskState $state.task -Expected 'disabled'
        $taskNotRunning = ($state.task.state -notmatch 'Running')
        $ready = $taskDisabled -and $taskNotRunning -and ([int]$state.owner_process_count -eq 0) -and $state.controlled_mode_active -and $reconcile.success -and ($remainingLocks.Count -eq 0)

        $history += [ordered]@{
            attempt = $attempt
            utc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
            task_disabled = $taskDisabled
            task_state = [string]$state.task.state
            owner_process_count = [int]$state.owner_process_count
            controlled_mode_active = [bool]$state.controlled_mode_active
            reconcile_success = [bool]$reconcile.success
            remaining_lock_count = [int]$remainingLocks.Count
            ready = [bool]$ready
        }

        if ($ready) {
            return [ordered]@{
                success = $true
                attempts = $history
                state = $state
                lock_reconcile = $reconcile
                remaining_locks = $remainingLocks
            }
        }
        Start-Sleep -Milliseconds 1000
    }

    return [ordered]@{
        success = $false
        attempts = $history
        state = $lastState
        lock_reconcile = $lastReconcile
        remaining_locks = $lastRemainingLocks
    }
}

function Wait-ForResumeReady {
    param(
        [string]$RepoRoot,
        [string]$Task,
        [int]$TimeoutSeconds = 18
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $attempt = 0
    $history = @()
    $clearActions = @()
    $lastState = $null
    while ((Get-Date) -lt $deadline) {
        $attempt += 1
        $state = Get-RepoState -RepoRoot $RepoRoot -Task $Task
        $lastState = $state

        if ($state.controlled_mode_active -and -not $DryRun) {
            $clearActions += (Clear-ControlledMode -RepoRoot $RepoRoot)
            Start-Sleep -Milliseconds 250
            $state = Get-RepoState -RepoRoot $RepoRoot -Task $Task
            $lastState = $state
        }

        $taskEnabled = Test-TaskEnabledState -TaskState $state.task -Expected 'enabled'
        $ready = (-not $state.controlled_mode_active) -and $taskEnabled
        $history += [ordered]@{
            attempt = $attempt
            utc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
            controlled_mode_active = [bool]$state.controlled_mode_active
            task_state = [string]$state.task.state
            task_enabled = [bool]$taskEnabled
            ready = [bool]$ready
        }

        if ($ready) {
            return [ordered]@{
                success = $true
                attempts = $history
                state = $state
                clear_actions = $clearActions
            }
        }
        Start-Sleep -Milliseconds 1000
    }

    return [ordered]@{
        success = $false
        attempts = $history
        state = $lastState
        clear_actions = $clearActions
    }
}

function Get-IsolationLockPaths {
    param([string]$RepoRoot)
    $live = Join-Path $RepoRoot 'out\systems\H\live'
    return @(
        (Join-Path $live 'H_launcher.lock'),
        (Join-Path $live 'H_pricing_cycle.lock'),
        (Join-Path $RepoRoot 'out\H_pricing_cycle.lock')
    )
}

function Get-LockPidInfo {
    param([string]$Line)
    $pidText = ''
    $pidSource = ''
    if ($Line -match 'launcher_pid=(\d+)') {
        $pidText = $Matches[1]
        $pidSource = 'launcher_pid'
    } elseif ($Line -match 'pid=(\d+)') {
        $pidText = $Matches[1]
        $pidSource = 'pid'
    }
    $runId = ''
    if ($Line -match 'run_id=([^|\s]+)') {
        $runId = $Matches[1]
    }
    return @{
        pid_text = $pidText
        pid_source = $pidSource
        run_id = $runId
    }
}

function Test-PidAliveState {
    param([string]$PidText)
    if (-not $PidText) {
        return @{ known = $false; alive = $false; reason = 'pid_missing' }
    }
    $pidInt = 0
    try {
        $pidInt = [int]$PidText
    } catch {
        return @{ known = $false; alive = $false; reason = 'pid_parse_invalid' }
    }
    if ($pidInt -le 0) {
        return @{ known = $false; alive = $false; reason = 'pid_invalid_nonpositive' }
    }
    try {
        $proc = Get-Process -Id $pidInt -ErrorAction Stop
        if ($proc) {
            return @{ known = $true; alive = $true; reason = 'pid_alive' }
        }
        return @{ known = $true; alive = $false; reason = 'pid_dead' }
    } catch {
        $msg = Normalize-Text -Value $_.Exception.Message
        if ($msg -match 'Cannot find a process') {
            return @{ known = $true; alive = $false; reason = 'pid_dead' }
        }
        if ($msg -match 'Access is denied') {
            return @{ known = $false; alive = $false; reason = 'pid_access_denied' }
        }
        return @{ known = $false; alive = $false; reason = ('pid_check_error:' + (Normalize-Text -Value $_.Exception.GetType().Name)) }
    }
}

function New-LockArchivePath {
    param(
        [string]$RepoRoot,
        [string]$LockPath
    )
    $archiveDir = Join-Path $RepoRoot 'out\locks\archive'
    if (-not (Test-Path -LiteralPath $archiveDir)) {
        New-Item -ItemType Directory -Path $archiveDir -Force | Out-Null
    }
    $stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
    $name = [IO.Path]::GetFileName($LockPath)
    $candidate = Join-Path $archiveDir ('H.lock.' + $stamp + '.' + $name + '.isolation')
    $suffix = 1
    while (Test-Path -LiteralPath $candidate) {
        $suffix += 1
        $candidate = Join-Path $archiveDir ('H.lock.' + $stamp + '.' + $name + '.isolation.' + $suffix)
    }
    return $candidate
}

function New-RunMarkerArchivePath {
    param(
        [string]$RepoRoot,
        [string]$MarkerPath
    )
    $archiveDir = Join-Path $RepoRoot 'out\locks\archive'
    if (-not (Test-Path -LiteralPath $archiveDir)) {
        New-Item -ItemType Directory -Path $archiveDir -Force | Out-Null
    }
    $stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
    $name = [IO.Path]::GetFileName($MarkerPath)
    $candidate = Join-Path $archiveDir ('H.marker.' + $stamp + '.' + $name + '.isolation')
    $suffix = 1
    while (Test-Path -LiteralPath $candidate) {
        $suffix += 1
        $candidate = Join-Path $archiveDir ('H.marker.' + $stamp + '.' + $name + '.isolation.' + $suffix)
    }
    return $candidate
}

function Invoke-StaleLockReconcile {
    param(
        [string]$RepoRoot,
        [hashtable]$State,
        [switch]$RequirePaused
    )
    $result = [ordered]@{
        success = $true
        checked_utc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        locks = @()
        blocking_reasons = @()
    }

    if ($RequirePaused) {
        if ($State.task.state -match 'Running') {
            $result.success = $false
            $result.blocking_reasons += 'scheduler_running'
        }
        if ($State.task.enabled -and $State.task.enabled -notmatch 'Disabled') {
            $result.success = $false
            $result.blocking_reasons += 'scheduler_not_disabled'
        }
    }
    if ([int]$State.owner_process_count -gt 0) {
        $result.success = $false
        $result.blocking_reasons += ('owner_process_count=' + $State.owner_process_count)
    }
    if (-not $result.success) {
        return $result
    }

    foreach ($lockPath in (Get-IsolationLockPaths -RepoRoot $RepoRoot)) {
        $entry = [ordered]@{
            path = $lockPath
            exists = (Test-Path -LiteralPath $lockPath)
            line = ''
            parsed_pid = ''
            parsed_pid_source = ''
            parsed_run_id = ''
            pid_state = ''
            action = 'none'
            archive_path = ''
            removed = $false
            status = 'ok'
            reason = ''
        }
        if (-not $entry.exists) {
            $result.locks += $entry
            continue
        }

        $line = ''
        try {
            $line = Normalize-Text -Value (Get-Content -LiteralPath $lockPath -Raw -ErrorAction Stop)
            $entry.line = $line
        } catch {
            $entry.status = 'blocked'
            $entry.reason = 'lock_read_error'
            $entry.action = 'none'
            $result.success = $false
            $result.blocking_reasons += ('lock_read_error:' + $lockPath)
            $result.locks += $entry
            continue
        }

        $pidInfo = Get-LockPidInfo -Line $line
        $entry.parsed_pid = [string]$pidInfo.pid_text
        $entry.parsed_pid_source = [string]$pidInfo.pid_source
        $entry.parsed_run_id = [string]$pidInfo.run_id

        if (-not $entry.parsed_pid) {
            $entry.status = 'blocked'
            $entry.reason = 'pid_parse_missing'
            $entry.action = 'none'
            $result.success = $false
            $result.blocking_reasons += ('pid_parse_missing:' + $lockPath)
            $result.locks += $entry
            continue
        }

        $pidState = Test-PidAliveState -PidText $entry.parsed_pid
        $entry.pid_state = [string]$pidState.reason
        if ($pidState.known -and $pidState.alive) {
            $entry.status = 'blocked'
            $entry.reason = 'live_pid_lock_owner'
            $entry.action = 'retain_live_lock'
            $result.success = $false
            $result.blocking_reasons += ('live_lock_pid=' + $entry.parsed_pid + ' path=' + $lockPath)
            $result.locks += $entry
            continue
        }
        if (-not $pidState.known -and ($entry.parsed_pid -ne '')) {
            $entry.status = 'blocked'
            $entry.reason = $entry.pid_state
            $entry.action = 'none'
            $result.success = $false
            $result.blocking_reasons += ('ambiguous_pid_state path=' + $lockPath + ' pid=' + $entry.parsed_pid + ' reason=' + $entry.pid_state)
            $result.locks += $entry
            continue
        }

        $archivePath = New-LockArchivePath -RepoRoot $RepoRoot -LockPath $lockPath
        $entry.archive_path = $archivePath
        $entry.action = 'archive_and_remove_stale'
        if ($DryRun) {
            $entry.removed = $true
            $entry.status = 'dry_run'
            $entry.reason = $entry.pid_state
            $result.locks += $entry
            continue
        }

        try {
            Move-Item -LiteralPath $lockPath -Destination $archivePath -Force -ErrorAction Stop
            $entry.removed = -not (Test-Path -LiteralPath $lockPath)
            if (-not $entry.removed) {
                $entry.status = 'blocked'
                $entry.reason = 'lock_remove_failed_after_move'
                $result.success = $false
                $result.blocking_reasons += ('lock_remove_failed:' + $lockPath)
            } else {
                $entry.status = 'reconciled'
                $entry.reason = $entry.pid_state
            }
        } catch {
            try {
                [IO.File]::WriteAllText($archivePath, $line + [Environment]::NewLine, [Text.Encoding]::ASCII)
                Remove-Item -LiteralPath $lockPath -Force -ErrorAction Stop
                $entry.removed = -not (Test-Path -LiteralPath $lockPath)
                if (-not $entry.removed) {
                    $entry.status = 'blocked'
                    $entry.reason = 'lock_remove_failed_after_copy'
                    $result.success = $false
                    $result.blocking_reasons += ('lock_remove_failed:' + $lockPath)
                } else {
                    $entry.status = 'reconciled'
                    $entry.reason = $entry.pid_state
                }
            } catch {
                $entry.status = 'blocked'
                $entry.reason = 'archive_or_remove_error'
                $result.success = $false
                $result.blocking_reasons += ('archive_or_remove_error:' + $lockPath)
            }
        }
        $result.locks += $entry
    }

    return $result
}

function Invoke-StaleRunMarkerReconcile {
    param(
        [string]$RepoRoot,
        [hashtable]$State,
        [switch]$RequirePaused
    )
    $live = Join-Path $RepoRoot 'out\systems\H\live'
    $markerPath = Join-Path $live 'H_run_in_progress.txt'
    $result = [ordered]@{
        success = $true
        checked_utc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        run_in_progress = ''
        last_finalized = ''
        run_state_run_id = ''
        run_state_state = ''
        run_state_owner_pid = ''
        run_state_owner_pid_state = ''
        action = 'none'
        archive_path = ''
        removed = $false
        blocking_reasons = @()
        reason = ''
    }

    if ($RequirePaused) {
        if ($State.task.state -match 'Running') {
            $result.success = $false
            $result.blocking_reasons += 'scheduler_running'
        }
        if ($State.task.enabled -and $State.task.enabled -notmatch 'Disabled') {
            $result.success = $false
            $result.blocking_reasons += 'scheduler_not_disabled'
        }
    }
    if ([int]$State.owner_process_count -gt 0) {
        $result.success = $false
        $result.blocking_reasons += ('owner_process_count=' + $State.owner_process_count)
    }
    $activeLocks = @($State.lock_launcher, $State.lock_cycle_live, $State.lock_cycle_root) | Where-Object { $_.exists }
    if ($activeLocks.Count -gt 0) {
        $result.success = $false
        $result.blocking_reasons += ('active_lock_count=' + $activeLocks.Count)
    }
    if (-not $result.success) {
        $result.reason = 'preconditions_blocked'
        return $result
    }

    $runInProgress = Normalize-Text -Value $State.run_in_progress
    $lastFinalized = Normalize-Text -Value $State.last_finalized
    $runStateRunId = Normalize-Text -Value $State.h_run_state.run_id
    $runStateState = (Normalize-Text -Value $State.h_run_state.state).ToLowerInvariant()
    $runStateOwnerPid = Normalize-Text -Value $State.h_run_state.owner_pid

    $result.run_in_progress = $runInProgress
    $result.last_finalized = $lastFinalized
    $result.run_state_run_id = $runStateRunId
    $result.run_state_state = $runStateState
    $result.run_state_owner_pid = $runStateOwnerPid

    if (-not $runInProgress) {
        $result.reason = 'marker_missing'
        return $result
    }
    if ($runInProgress -eq $lastFinalized) {
        $result.reason = 'already_finalized_marker'
        return $result
    }
    if ($runStateRunId -and ($runStateRunId -ne $runInProgress)) {
        $result.reason = 'run_state_marker_mismatch'
        return $result
    }
    if (-not $runStateRunId) {
        $result.success = $false
        $result.blocking_reasons += 'run_state_missing_for_marker'
        $result.reason = 'run_state_missing_for_marker'
        return $result
    }

    $ownerPidState = Test-PidAliveState -PidText $runStateOwnerPid
    $result.run_state_owner_pid_state = [string]$ownerPidState.reason
    if ($ownerPidState.known -and $ownerPidState.alive) {
        $result.success = $false
        $result.blocking_reasons += ('run_state_owner_pid_live=' + $runStateOwnerPid)
        $result.reason = 'owner_pid_live'
        return $result
    }
    if (-not $ownerPidState.known -and $runStateOwnerPid) {
        $result.success = $false
        $result.blocking_reasons += ('ambiguous_owner_pid_state=' + $ownerPidState.reason)
        $result.reason = 'ambiguous_owner_pid_state'
        return $result
    }

    $archivePath = New-RunMarkerArchivePath -RepoRoot $RepoRoot -MarkerPath $markerPath
    $result.archive_path = $archivePath
    $result.action = 'archive_and_remove_stale'
    if ($DryRun) {
        $result.removed = $true
        $result.reason = 'dry_run_stale_marker_no_live_owner'
        return $result
    }

    try {
        Move-Item -LiteralPath $markerPath -Destination $archivePath -Force -ErrorAction Stop
        $result.removed = -not (Test-Path -LiteralPath $markerPath)
        if ($result.removed) {
            $result.reason = 'stale_marker_archived'
            return $result
        }
        $result.success = $false
        $result.blocking_reasons += 'marker_remove_failed_after_move'
        $result.reason = 'marker_remove_failed_after_move'
        return $result
    } catch {
        try {
            $line = ''
            if (Test-Path -LiteralPath $markerPath) {
                $line = Normalize-Text -Value (Get-Content -LiteralPath $markerPath -Raw -ErrorAction Stop)
            }
            [IO.File]::WriteAllText($archivePath, $line + [Environment]::NewLine, [Text.Encoding]::ASCII)
            Remove-Item -LiteralPath $markerPath -Force -ErrorAction Stop
            $result.removed = -not (Test-Path -LiteralPath $markerPath)
            if ($result.removed) {
                $result.reason = 'stale_marker_archived_after_copy'
                return $result
            }
            $result.success = $false
            $result.blocking_reasons += 'marker_remove_failed_after_copy'
            $result.reason = 'marker_remove_failed_after_copy'
            return $result
        } catch {
            $result.success = $false
            $result.blocking_reasons += 'marker_archive_or_remove_error'
            $result.reason = 'marker_archive_or_remove_error'
            return $result
        }
    }
}

function Assert-AdminForControl {
    param([string]$Act)
    if ($DryRun) {
        return
    }
    if (-not (Test-IsAdmin)) {
        throw ($Act + ' requires elevation. Re-run from elevated PowerShell or cmd (Run as administrator).')
    }
}

function Assert-ReadyForIsolatedRun {
    param([hashtable]$State)
    if ($DryRun) {
        return
    }
    if ($State.task.state -match 'Running') {
        throw 'Task Scheduler still reports AMZ H Cycle as Running. Pause ownership first.'
    }
    if ($State.task.enabled -and $State.task.enabled -notmatch 'Disabled') {
        throw 'Task Scheduler task is still enabled. Pause ownership first.'
    }
    if (-not $State.controlled_mode_active) {
        throw 'Controlled mode is not active. Set controlled mode before isolated one-shot runs.'
    }
    if ([int]$State.owner_process_count -gt 0) {
        throw ('H owner processes are still active (' + $State.owner_process_count + '). Pause ownership first.')
    }
}

function Invoke-RunHCycleOneShot {
    param(
        [string]$RepoRoot,
        [string]$RunMode
    )
    if ($DryRun) {
        if ($RunMode -eq 'success') {
            return @{ rc = 0; mode = 'success'; command = 'cmd /c run_H_cycle.bat (one-shot guarded)' }
        }
        return @{ rc = 1; mode = 'failure'; command = 'cmd /c run_H_cycle.bat (one-shot guarded with H_LOCK_TEST_RAISE_AFTER_ACQUIRE=1)' }
    }

    $cmdLine = @()
    $cmdLine += 'set "H_RUN_ONCE=1"'
    $cmdLine += 'set "H_USE_GUARD_WRAPPER=1"'
    $cmdLine += 'set "H_LAUNCHER_AUTO_DETACH=0"'
    $cmdLine += 'set "H_LAUNCHER_RESTART_ON_EXIT=0"'
    $cmdLine += 'set "H_PHASE1_PILOT_MODE=subprocess"'
    $cmdLine += 'set "H_PHASE1_INTEL_MODE=inline"'
    $cmdLine += 'set "H_PHASE1_PUBLISH_MODE=inline"'
    $cmdLine += 'set "H_LOCK_TEST_RAISE_AFTER_ACQUIRE=0"'
    if ($RunMode -eq 'failure') {
        $cmdLine += 'set "H_TASK_SKIP_STAGE_ARGS="'
        $cmdLine += 'set "H_LOCK_TEST_RAISE_AFTER_ACQUIRE=1"'
    } else {
        $cmdLine += 'set "H_TASK_SKIP_STAGE_ARGS="'
    }
    $cmdLine += 'call run_H_cycle.bat'
    $joined = ($cmdLine -join ' && ')

    Push-Location $RepoRoot
    try {
        $proc = Start-Process -FilePath 'cmd.exe' -ArgumentList @('/c', $joined) -NoNewWindow -PassThru -Wait
        return @{ rc = [int]$proc.ExitCode; mode = $RunMode; command = $joined }
    } finally {
        Pop-Location
    }
}

function Get-TerminalSummary {
    param([string]$RepoRoot)
    $live = Join-Path $RepoRoot 'out\systems\H\live'
    $statePath = Join-Path $live 'H_run_state.json'
    $workerPath = Join-Path $live 'H_worker_lifecycle.json'
    $runState = Read-JsonObjectWithRetry -Path $statePath
    $workerState = Read-JsonObjectWithRetry -Path $workerPath
    return [ordered]@{
        run_id = [string]($runState.run_id)
        run_state = [string]($runState.state)
        run_publish_status = [string]($runState.publish_status)
        run_failure_code = [string]($runState.failure_code)
        worker_state = [string]($workerState.state)
        worker_terminal_outcome = [string]($workerState.terminal_outcome)
        worker_reason_code = [string]($workerState.reason_code)
    }
}

$repoRoot = Resolve-RepoRoot -ArgRoot $Root

switch ($Action) {
    'status' {
        $state = Get-RepoState -RepoRoot $repoRoot -Task $TaskName
        $state | ConvertTo-Json -Depth 8
        break
    }

    'pause' {
        Assert-AdminForControl -Act 'pause'
        $before = Get-RepoState -RepoRoot $repoRoot -Task $TaskName

        $taskArg = '"' + $TaskName + '"'
        $disable = Invoke-Schtasks -TaskArgs @('/Change', '/TN', $taskArg, '/Disable')
        $end = Invoke-Schtasks -TaskArgs @('/End', '/TN', $taskArg) -AllowFail
        $stopped = Stop-HProcesses -RepoRoot $repoRoot
        $mode = Set-ControlledMode -RepoRoot $repoRoot
        Start-Sleep -Milliseconds 750

        $settle = Wait-ForPauseReady -RepoRoot $repoRoot -Task $TaskName
        $post = $settle.state
        $reconcile = $settle.lock_reconcile
        $remainingLocks = $settle.remaining_locks
        $ok = [bool]$settle.success
        if ($DryRun) { $ok = $true }

        [ordered]@{
            action = 'pause'
            dry_run = [bool]$DryRun
            success = [bool]$ok
            before = $before
            scheduler_disable = $disable
            scheduler_end = $end
            process_stop = $stopped
            controlled_mode = $mode
            settle = $settle
            lock_reconcile = $reconcile
            after = $post
            failure_reason = $(if ($ok) { '' } else { 'pause_preconditions_not_met' })
        } | ConvertTo-Json -Depth 10

        if (-not $ok) {
            exit 2
        }
        break
    }

    'run-success' {
        $state = Get-RepoState -RepoRoot $repoRoot -Task $TaskName
        Assert-ReadyForIsolatedRun -State $state
        $reconcile = Invoke-StaleLockReconcile -RepoRoot $repoRoot -State $state -RequirePaused
        if (-not $reconcile.success) {
            [ordered]@{
                action = 'run-success'
                dry_run = [bool]$DryRun
                success = $false
                lock_reconcile = $reconcile
                failure_reason = 'stale_lock_reconcile_blocked'
            } | ConvertTo-Json -Depth 10
            exit 6
        }
        $stateAfterReconcile = Get-RepoState -RepoRoot $repoRoot -Task $TaskName
        $runMarkerReconcile = Invoke-StaleRunMarkerReconcile -RepoRoot $repoRoot -State $stateAfterReconcile -RequirePaused
        if (-not $runMarkerReconcile.success) {
            [ordered]@{
                action = 'run-success'
                dry_run = [bool]$DryRun
                success = $false
                lock_reconcile = $reconcile
                run_marker_reconcile = $runMarkerReconcile
                failure_reason = 'stale_run_marker_reconcile_blocked'
            } | ConvertTo-Json -Depth 10
            exit 10
        }
        $stateAfterRunMarkerReconcile = Get-RepoState -RepoRoot $repoRoot -Task $TaskName
        Assert-ReadyForIsolatedRun -State $stateAfterRunMarkerReconcile
        $unresolvedLocks = @($stateAfterRunMarkerReconcile.lock_launcher, $stateAfterRunMarkerReconcile.lock_cycle_live, $stateAfterRunMarkerReconcile.lock_cycle_root) | Where-Object { $_.exists }
        if ($unresolvedLocks.Count -gt 0 -and -not $DryRun) {
            [ordered]@{
                action = 'run-success'
                dry_run = [bool]$DryRun
                success = $false
                lock_reconcile = $reconcile
                run_marker_reconcile = $runMarkerReconcile
                unresolved_locks = $unresolvedLocks
                failure_reason = 'unresolved_lock_conflict_after_reconcile'
            } | ConvertTo-Json -Depth 10
            exit 7
        }
        $run = Invoke-RunHCycleOneShot -RepoRoot $repoRoot -RunMode 'success'
        $term = Get-TerminalSummary -RepoRoot $repoRoot
        $after = Get-RepoState -RepoRoot $repoRoot -Task $TaskName
        $postRunReconcile = Invoke-StaleLockReconcile -RepoRoot $repoRoot -State $after -RequirePaused
        $afterFinal = Get-RepoState -RepoRoot $repoRoot -Task $TaskName
        $terminalOk = ($term.run_state -in @('finalized', 'succeeded', 'success')) -or ($term.worker_state -eq 'succeeded')
        if ($DryRun) { $terminalOk = $true }
        [ordered]@{
            action = 'run-success'
            dry_run = [bool]$DryRun
            run = $run
            lock_reconcile = $reconcile
            run_marker_reconcile = $runMarkerReconcile
            post_run_lock_reconcile = $postRunReconcile
            terminal = $term
            after = $afterFinal
            success = [bool]$terminalOk
            failure_reason = $(if ($terminalOk) { '' } else { 'terminal_success_not_proven' })
        } | ConvertTo-Json -Depth 10
        if (-not $terminalOk) {
            exit 3
        }
        break
    }

    'run-failure' {
        $state = Get-RepoState -RepoRoot $repoRoot -Task $TaskName
        Assert-ReadyForIsolatedRun -State $state
        $reconcile = Invoke-StaleLockReconcile -RepoRoot $repoRoot -State $state -RequirePaused
        if (-not $reconcile.success) {
            [ordered]@{
                action = 'run-failure'
                dry_run = [bool]$DryRun
                success = $false
                lock_reconcile = $reconcile
                failure_reason = 'stale_lock_reconcile_blocked'
            } | ConvertTo-Json -Depth 10
            exit 8
        }
        $stateAfterReconcile = Get-RepoState -RepoRoot $repoRoot -Task $TaskName
        $runMarkerReconcile = Invoke-StaleRunMarkerReconcile -RepoRoot $repoRoot -State $stateAfterReconcile -RequirePaused
        if (-not $runMarkerReconcile.success) {
            [ordered]@{
                action = 'run-failure'
                dry_run = [bool]$DryRun
                success = $false
                lock_reconcile = $reconcile
                run_marker_reconcile = $runMarkerReconcile
                failure_reason = 'stale_run_marker_reconcile_blocked'
            } | ConvertTo-Json -Depth 10
            exit 11
        }
        $stateAfterRunMarkerReconcile = Get-RepoState -RepoRoot $repoRoot -Task $TaskName
        Assert-ReadyForIsolatedRun -State $stateAfterRunMarkerReconcile
        $unresolvedLocks = @($stateAfterRunMarkerReconcile.lock_launcher, $stateAfterRunMarkerReconcile.lock_cycle_live, $stateAfterRunMarkerReconcile.lock_cycle_root) | Where-Object { $_.exists }
        if ($unresolvedLocks.Count -gt 0 -and -not $DryRun) {
            [ordered]@{
                action = 'run-failure'
                dry_run = [bool]$DryRun
                success = $false
                lock_reconcile = $reconcile
                run_marker_reconcile = $runMarkerReconcile
                unresolved_locks = $unresolvedLocks
                failure_reason = 'unresolved_lock_conflict_after_reconcile'
            } | ConvertTo-Json -Depth 10
            exit 9
        }
        $run = Invoke-RunHCycleOneShot -RepoRoot $repoRoot -RunMode 'failure'
        $term = Get-TerminalSummary -RepoRoot $repoRoot
        $after = Get-RepoState -RepoRoot $repoRoot -Task $TaskName
        $postRunReconcile = Invoke-StaleLockReconcile -RepoRoot $repoRoot -State $after -RequirePaused
        $afterFinal = Get-RepoState -RepoRoot $repoRoot -Task $TaskName
        $terminalFailed = ($term.run_state -in @('failed', 'abandoned')) -or ($term.worker_state -in @('failed', 'abandoned'))
        if ($DryRun) { $terminalFailed = $true }
        [ordered]@{
            action = 'run-failure'
            dry_run = [bool]$DryRun
            run = $run
            lock_reconcile = $reconcile
            run_marker_reconcile = $runMarkerReconcile
            post_run_lock_reconcile = $postRunReconcile
            terminal = $term
            after = $afterFinal
            success = [bool]$terminalFailed
            failure_reason = $(if ($terminalFailed) { '' } else { 'terminal_failure_not_proven' })
            induced_failure_mode = 'lock_test_raise_after_acquire'
        } | ConvertTo-Json -Depth 10
        if (-not $terminalFailed) {
            exit 4
        }
        break
    }

    'resume' {
        Assert-AdminForControl -Act 'resume'
        $before = Get-RepoState -RepoRoot $repoRoot -Task $TaskName
        $clear = Clear-ControlledMode -RepoRoot $repoRoot
        $taskArg = '"' + $TaskName + '"'
        $enable = Invoke-Schtasks -TaskArgs @('/Change', '/TN', $taskArg, '/Enable')
        $runTask = @{ rc = 0; stdout = 'skipped'; stderr = '' }
        if (-not $NoAutoRunOnResume) {
            $runTask = Invoke-Schtasks -TaskArgs @('/Run', '/TN', $taskArg) -AllowFail
        }
        Start-Sleep -Milliseconds 750
        $settle = Wait-ForResumeReady -RepoRoot $repoRoot -Task $TaskName
        $after = $settle.state
        $ok = [bool]$settle.success
        if ($DryRun) { $ok = $true }
        [ordered]@{
            action = 'resume'
            dry_run = [bool]$DryRun
            success = [bool]$ok
            before = $before
            controlled_mode = $clear
            scheduler_enable = $enable
            scheduler_run = $runTask
            settle = $settle
            after = $after
            failure_reason = $(if ($ok) { '' } else { 'resume_preconditions_not_met' })
        } | ConvertTo-Json -Depth 10
        if (-not $ok) {
            exit 5
        }
        break
    }
}

exit 0
