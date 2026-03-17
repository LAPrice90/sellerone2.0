param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('gate', 'confirm')]
    [string]$Mode,

    [Parameter(Mandatory = $true)]
    [string]$Root,

    [Parameter(Mandatory = $true)]
    [int]$SelfPid,

    [Parameter(Mandatory = $true)]
    [string]$LockPath,

    [Parameter(Mandatory = $true)]
    [string]$HeartbeatPath,

    [Parameter(Mandatory = $true)]
    [double]$HeartbeatStaleSeconds
)

$ErrorActionPreference = 'SilentlyContinue'
$repo = [regex]::Escape($Root)

function Get-HPython {
    Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq 'python.exe' -and
        $_.CommandLine -match $repo -and
        (
            $_.CommandLine -like '*scripts\cycles\run_H_pricing_cycle.py*' -or
            $_.CommandLine -like '*scripts\cycles\run_H_pricing_cycle_guarded.py*'
        )
    }
}

function Get-LockLine {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        return ''
    }
    try {
        return (Get-Content $Path -Raw).Trim()
    } catch {
        return ''
    }
}

function Get-LockPid {
    param([string]$Line)
    if ($Line -match 'launcher_pid=(\d+)') {
        try {
            return [int]$Matches[1]
        } catch {
        }
    }
    return $null
}

function Test-LiveLauncher {
    param([int]$TargetProcessId)
    if (-not $TargetProcessId) {
        return $false
    }
    $proc = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $TargetProcessId) -ErrorAction SilentlyContinue
    return [bool]($proc -and $proc.Name -eq 'cmd.exe')
}

function Get-HeartbeatState {
    param(
        [string]$Path,
        [int]$ExpectedPid
    )
    if (-not (Test-Path $Path)) {
        return @{
            State = 'missing'
            OwnerPid = ''
            AgeSeconds = ''
            Utc = ''
        }
    }
    $line = ''
    try {
        $line = (Get-Content $Path -Raw).Trim()
    } catch {
        return @{
            State = 'read_error'
            OwnerPid = ''
            AgeSeconds = ''
            Utc = ''
        }
    }
    $hbPid = ''
    if ($line -match 'launcher_pid=(\d+)') {
        $hbPid = $Matches[1]
    }
    if (-not $hbPid) {
        return @{
            State = 'missing_pid'
            OwnerPid = ''
            AgeSeconds = ''
            Utc = ''
        }
    }
    if ([string]$hbPid -ne [string]$ExpectedPid) {
        return @{
            State = 'pid_mismatch'
            OwnerPid = [string]$hbPid
            AgeSeconds = ''
            Utc = ''
        }
    }
    $hbUtc = ''
    if ($line -match 'utc=([0-9T:\-]+Z)') {
        $hbUtc = $Matches[1]
    }
    if (-not $hbUtc) {
        return @{
            State = 'missing_utc'
            OwnerPid = [string]$hbPid
            AgeSeconds = ''
            Utc = ''
        }
    }
    try {
        $hbTime = [datetime]::Parse($hbUtc).ToUniversalTime()
    } catch {
        return @{
            State = 'invalid_utc'
            OwnerPid = [string]$hbPid
            AgeSeconds = ''
            Utc = $hbUtc
        }
    }
    $age = [math]::Round(((Get-Date).ToUniversalTime() - $hbTime).TotalSeconds, 2)
    $state = 'fresh'
    if ($age -gt $HeartbeatStaleSeconds) {
        $state = 'stale'
    }
    return @{
        State = $state
        OwnerPid = [string]$hbPid
        AgeSeconds = [string]$age
        Utc = $hbUtc
    }
}

function Confirm-OwnerState {
    param(
        [string]$Path,
        [int]$ExpectedPid
    )
    $line2 = Get-LockLine -Path $Path
    if (-not $line2) {
        return @{
            State = 'missing'
            Line = $line2
            Pid = $null
            HeartbeatState = 'missing'
            HeartbeatAge = ''
            HPython = 'false'
            HPids = ''
        }
    }
    $pid2 = Get-LockPid -Line $line2
    if (-not $pid2) {
        return @{
            State = 'uncertain_foreign'
            Line = $line2
            Pid = $pid2
            HeartbeatState = 'missing'
            HeartbeatAge = ''
            HPython = 'false'
            HPids = ''
        }
    }
    if ($pid2 -ne $ExpectedPid) {
        return @{
            State = 'changed_foreign'
            Line = $line2
            Pid = $pid2
            HeartbeatState = 'missing'
            HeartbeatAge = ''
            HPython = 'false'
            HPids = ''
        }
    }
    Start-Sleep -Milliseconds 75
    $live = Test-LiveLauncher -TargetProcessId $pid2
    $procs = Get-HPython
    $hasHPython = [bool]$procs
    $pids = ''
    if ($procs) {
        $pids = @($procs | ForEach-Object { [string]$_.ProcessId }) -join ','
    }
    $heartbeat = Get-HeartbeatState -Path $HeartbeatPath -ExpectedPid $pid2
    if ($live) {
        if ($hasHPython -or $heartbeat.State -eq 'fresh') {
            return @{
                State = 'healthy_live_owner'
                Line = $line2
                Pid = $pid2
                HeartbeatState = [string]$heartbeat.State
                HeartbeatAge = [string]$heartbeat.AgeSeconds
                HPython = ($hasHPython.ToString().ToLower())
                HPids = $pids
            }
        }
        return @{
            State = 'stalled_live_owner'
            Line = $line2
            Pid = $pid2
            HeartbeatState = [string]$heartbeat.State
            HeartbeatAge = [string]$heartbeat.AgeSeconds
            HPython = ($hasHPython.ToString().ToLower())
            HPids = $pids
        }
    }
    return @{
        State = 'dead_foreign'
        Line = $line2
        Pid = $pid2
        HeartbeatState = [string]$heartbeat.State
        HeartbeatAge = [string]$heartbeat.AgeSeconds
        HPython = ($hasHPython.ToString().ToLower())
        HPids = $pids
    }
}

function TryAcquire {
    param(
        [string]$Path,
        [string]$Payload
    )
    try {
        $fs = [System.IO.File]::Open(
            $Path,
            [System.IO.FileMode]::CreateNew,
            [System.IO.FileAccess]::Write,
            [System.IO.FileShare]::None
        )
        try {
            $bytes = [System.Text.Encoding]::ASCII.GetBytes($Payload + [Environment]::NewLine)
            $fs.Write($bytes, 0, $bytes.Length)
        } finally {
            $fs.Dispose()
        }
        return $true
    } catch {
        return $false
    }
}

if ($SelfPid -le 0) {
    Write-Output 'launcher_self_pid self_pid=0 decision=reject_invalid_self'
    exit 96
}

if ($Mode -eq 'gate') {
    $payload = 'launcher_pid=' + $SelfPid + '|utc=' + (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    $attempt = 0
    while ($attempt -lt 3) {
        $attempt = $attempt + 1
        if (TryAcquire -Path $LockPath -Payload $payload) {
            $procs = Get-HPython
            if ($procs) {
                $pids = @($procs | ForEach-Object { [string]$_.ProcessId }) -join ','
                Remove-Item -Path $LockPath -Force -ErrorAction SilentlyContinue
                Write-Output ('active_h_python_detected self_pid=' + $SelfPid + ' pids=' + $pids + ' decision=reject_after_acquire')
                exit 96
            }
            $action = 'fresh'
            if ($attempt -gt 1) {
                $action = 'owner_replaced'
            }
            Write-Output ('launcher_lock_acquired self_pid=' + $SelfPid + ' owner_pid=' + $SelfPid + ' owner_class=self action=' + $action + ' decision=allow attempt=' + $attempt)
            exit 0
        }

        $lockLine = Get-LockLine -Path $LockPath
        $ownerPid = Get-LockPid -Line $lockLine
        if ($ownerPid -eq $SelfPid) {
            Write-Output ('launcher_lock_seen self_pid=' + $SelfPid + ' owner_pid=' + $ownerPid + ' owner_class=self decision=allow attempt=' + $attempt)
            exit 0
        }

        $confirmed = Confirm-OwnerState -Path $LockPath -ExpectedPid $ownerPid
        $confirmedState = [string]$confirmed.State
        $confirmedLine = [string]$confirmed.Line
        $confirmedPid = $confirmed.Pid
        $heartbeatState = [string]$confirmed.HeartbeatState
        $heartbeatAge = [string]$confirmed.HeartbeatAge
        $hPython = [string]$confirmed.HPython
        $hPids = [string]$confirmed.HPids

        if ($confirmedState -eq 'healthy_live_owner') {
            $pidsText = 'none'
            if ($hPids) {
                $pidsText = $hPids
            }
            Write-Output ('active_h_launcher_detected self_pid=' + $SelfPid + ' owner_pid=' + $confirmedPid + ' owner_line=' + $confirmedLine + ' owner_class=healthy_live_owner launcher_live=true h_python_active=' + $hPython + ' h_python_pids=' + $pidsText + ' heartbeat_state=' + $heartbeatState + ' heartbeat_age_seconds=' + $heartbeatAge + ' decision=reject attempt=' + $attempt)
            exit 96
        }

        if ($confirmedState -eq 'stalled_live_owner') {
            $procs = Get-HPython
            if ($procs) {
                $pids = @($procs | ForEach-Object { [string]$_.ProcessId }) -join ','
                Write-Output ('active_h_python_detected self_pid=' + $SelfPid + ' owner_pid=' + $confirmedPid + ' owner_class=stalled_live_owner launcher_live=true heartbeat_state=' + $heartbeatState + ' heartbeat_age_seconds=' + $heartbeatAge + ' pids=' + $pids + ' decision=reject attempt=' + $attempt)
                exit 96
            }
            if (Test-Path $LockPath) {
                Remove-Item -Path $LockPath -Force -ErrorAction SilentlyContinue
                if (Test-Path $LockPath) {
                    Write-Output ('stale_h_launcher_lock_remove_failed self_pid=' + $SelfPid + ' owner_pid=' + $confirmedPid + ' owner_line=' + $confirmedLine + ' owner_class=stalled_live_owner launcher_live=true h_python_active=' + $hPython + ' heartbeat_state=' + $heartbeatState + ' heartbeat_age_seconds=' + $heartbeatAge + ' decision=reject attempt=' + $attempt)
                    exit 96
                }
                Write-Output ('stale_h_launcher_lock_removed self_pid=' + $SelfPid + ' owner_pid=' + $confirmedPid + ' owner_line=' + $confirmedLine + ' owner_class=stalled_live_owner launcher_live=true h_python_active=' + $hPython + ' heartbeat_state=' + $heartbeatState + ' heartbeat_age_seconds=' + $heartbeatAge + ' decision=replace attempt=' + $attempt)
                Start-Sleep -Milliseconds 50
                continue
            }
            Write-Output ('launcher_lock_missing self_pid=' + $SelfPid + ' owner_pid=none owner_class=missing decision=retry attempt=' + $attempt)
            Start-Sleep -Milliseconds 50
            continue
        }

        if ($confirmedState -eq 'dead_foreign') {
            $procs = Get-HPython
            if ($procs) {
                $pids = @($procs | ForEach-Object { [string]$_.ProcessId }) -join ','
                Write-Output ('active_h_python_detected self_pid=' + $SelfPid + ' owner_pid=' + $confirmedPid + ' owner_class=dead_foreign launcher_live=false h_python_active=true pids=' + $pids + ' heartbeat_state=' + $heartbeatState + ' heartbeat_age_seconds=' + $heartbeatAge + ' decision=reject attempt=' + $attempt)
                exit 96
            }
            if (Test-Path $LockPath) {
                Remove-Item -Path $LockPath -Force -ErrorAction SilentlyContinue
                if (Test-Path $LockPath) {
                    Write-Output ('stale_h_launcher_lock_remove_failed self_pid=' + $SelfPid + ' owner_pid=' + $confirmedPid + ' owner_line=' + $confirmedLine + ' owner_class=dead_foreign launcher_live=false h_python_active=' + $hPython + ' heartbeat_state=' + $heartbeatState + ' heartbeat_age_seconds=' + $heartbeatAge + ' decision=reject attempt=' + $attempt)
                    exit 96
                }
                Write-Output ('stale_h_launcher_lock_removed self_pid=' + $SelfPid + ' owner_pid=' + $confirmedPid + ' owner_line=' + $confirmedLine + ' owner_class=dead_foreign launcher_live=false h_python_active=' + $hPython + ' heartbeat_state=' + $heartbeatState + ' heartbeat_age_seconds=' + $heartbeatAge + ' decision=replace attempt=' + $attempt)
                Start-Sleep -Milliseconds 50
                continue
            }
            Write-Output ('launcher_lock_missing self_pid=' + $SelfPid + ' owner_pid=none owner_class=missing decision=retry attempt=' + $attempt)
            Start-Sleep -Milliseconds 50
            continue
        }

        if ($confirmedState -eq 'missing') {
            Write-Output ('launcher_lock_missing self_pid=' + $SelfPid + ' owner_pid=none owner_class=missing decision=retry attempt=' + $attempt)
            Start-Sleep -Milliseconds 50
            continue
        }

        $ownerPidText = 'none'
        if ($confirmedPid) {
            $ownerPidText = [string]$confirmedPid
        }
        Write-Output ('active_h_launcher_detected self_pid=' + $SelfPid + ' owner_pid=' + $ownerPidText + ' owner_line=' + $confirmedLine + ' owner_class=' + $confirmedState + ' launcher_live=unknown h_python_active=' + $hPython + ' heartbeat_state=' + $heartbeatState + ' heartbeat_age_seconds=' + $heartbeatAge + ' decision=reject attempt=' + $attempt)
        exit 96
    }
    Write-Output ('launcher_lock_not_acquired self_pid=' + $SelfPid + ' owner_class=unknown decision=reject retries_exhausted')
    exit 96
}

$lockLine = Get-LockLine -Path $LockPath
if (-not $lockLine) {
    Write-Output ('launcher_lock_confirmation self_pid=' + $SelfPid + ' owner_pid=none owner_class=missing decision=allow')
    exit 0
}

$ownerPid = Get-LockPid -Line $lockLine
if ($ownerPid -and $ownerPid -eq $SelfPid) {
    Write-Output ('launcher_lock_confirmation self_pid=' + $SelfPid + ' owner_pid=' + $ownerPid + ' owner_class=self decision=allow')
    exit 0
}

$live = Test-LiveLauncher -TargetProcessId $ownerPid
$procs = Get-HPython
$hasHPython = [bool]$procs
$pids = ''
if ($procs) {
    $pids = @($procs | ForEach-Object { [string]$_.ProcessId }) -join ','
}
$heartbeat = Get-HeartbeatState -Path $HeartbeatPath -ExpectedPid $ownerPid

if ($live -and ($hasHPython -or $heartbeat.State -eq 'fresh')) {
    $pidsText = 'none'
    if ($pids) {
        $pidsText = $pids
    }
    Write-Output ('active_h_launcher_detected self_pid=' + $SelfPid + ' owner_pid=' + $ownerPid + ' owner_line=' + $lockLine + ' owner_class=healthy_live_owner h_python_active=' + ($hasHPython.ToString().ToLower()) + ' h_python_pids=' + $pidsText + ' heartbeat_state=' + $heartbeat.State + ' heartbeat_age_seconds=' + $heartbeat.AgeSeconds + ' decision=reject_postconfirm')
    exit 96
}

if ($live) {
    Write-Output ('launcher_lock_confirmation self_pid=' + $SelfPid + ' owner_pid=' + $ownerPid + ' owner_line=' + $lockLine + ' owner_class=stalled_live_owner h_python_active=' + ($hasHPython.ToString().ToLower()) + ' heartbeat_state=' + $heartbeat.State + ' heartbeat_age_seconds=' + $heartbeat.AgeSeconds + ' decision=allow_replace_confirmed')
    exit 0
}

Write-Output ('launcher_lock_confirmation self_pid=' + $SelfPid + ' owner_pid=' + $ownerPid + ' owner_line=' + $lockLine + ' owner_class=dead_foreign h_python_active=' + ($hasHPython.ToString().ToLower()) + ' heartbeat_state=' + $heartbeat.State + ' heartbeat_age_seconds=' + $heartbeat.AgeSeconds + ' decision=allow_replace_confirmed')
exit 0
