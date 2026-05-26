param(
    [Parameter(Mandatory = $true)]
    [string]$Path,
    [double]$RotateMaxMb = 32,
    [int]$RotateMaxFiles = 6,
    [double]$RetentionDays = 14,
    [double]$FamilyMaxMb = 48
)

$ErrorActionPreference = 'Stop'

try {
    if (-not (Test-Path -LiteralPath $Path)) {
        exit 0
    }

    $maxBytes = [int64]([double]$RotateMaxMb * 1024 * 1024)
    if ($maxBytes -lt 524288) { $maxBytes = 524288 }
    $maxFiles = [int]$RotateMaxFiles
    if ($maxFiles -lt 2) { $maxFiles = 2 }
    $familyMaxBytes = [int64]([double]$FamilyMaxMb * 1024 * 1024)
    if ($familyMaxBytes -lt $maxBytes) { $familyMaxBytes = $maxBytes }
    $retention = [double]$RetentionDays

    $item = Get-Item -LiteralPath $Path -ErrorAction SilentlyContinue
    if (-not $item) {
        exit 0
    }

    $rotated = $false
    if ([int64]$item.Length -ge $maxBytes) {
        $oldest = "$Path.$maxFiles"
        if (Test-Path -LiteralPath $oldest) {
            Remove-Item -LiteralPath $oldest -Force -ErrorAction SilentlyContinue
        }
        for ($i = $maxFiles - 1; $i -ge 1; $i--) {
            $src = "$Path.$i"
            $dst = "$Path." + ($i + 1)
            if (Test-Path -LiteralPath $src) {
                Move-Item -LiteralPath $src -Destination $dst -Force -ErrorAction SilentlyContinue
            }
        }
        Move-Item -LiteralPath $Path -Destination "$Path.1" -Force -ErrorAction SilentlyContinue
        $rotated = $true
    }

    $cutoff = (Get-Date).ToUniversalTime().AddDays(-1.0 * $retention)
    $dir = [System.IO.Path]::GetDirectoryName($Path)
    $name = [System.IO.Path]::GetFileName($Path)
    if (-not $dir -or -not $name) {
        exit 0
    }

    # Note: Windows wildcard matching for "name.*" can include "name" (base file).
    Get-ChildItem -Path $dir -Filter ($name + '.*') -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_.LastWriteTimeUtc -lt $cutoff) {
            Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue
        }
    }

    $members = @()
    if (Test-Path -LiteralPath $Path) {
        $members += [pscustomobject]@{ idx = 0; file = (Get-Item -LiteralPath $Path) }
    }

    Get-ChildItem -Path $dir -Filter ($name + '.*') -ErrorAction SilentlyContinue | ForEach-Object {
        $entryName = [string]$_.Name
        if ($entryName.Length -le $name.Length) { return }
        if (-not $entryName.StartsWith(($name + '.'), [System.StringComparison]::OrdinalIgnoreCase)) { return }
        $suffix = $entryName.Substring($name.Length + 1)
        $idx = 0
        if ([int]::TryParse($suffix, [ref]$idx) -and $idx -gt 0) {
            $members += [pscustomobject]@{ idx = $idx; file = $_ }
        }
    }

    $members = @($members | Sort-Object idx)
    $rotatedMembers = @($members | Where-Object { $_.idx -gt 0 } | Sort-Object idx -Descending)

    while ($members.Count -gt ($maxFiles + 1) -and $rotatedMembers.Count -gt 0) {
        $target = $rotatedMembers[0]
        Remove-Item -LiteralPath $target.file.FullName -Force -ErrorAction SilentlyContinue
        $members = @($members | Where-Object { $_.file.FullName -ne $target.file.FullName })
        $rotatedMembers = @($rotatedMembers | Where-Object { $_.file.FullName -ne $target.file.FullName })
    }

    $familyTotal = [int64](($members | ForEach-Object { [int64]$_.file.Length } | Measure-Object -Sum).Sum)
    while ($familyTotal -gt $familyMaxBytes -and $rotatedMembers.Count -gt 0) {
        $target = $rotatedMembers[0]
        Remove-Item -LiteralPath $target.file.FullName -Force -ErrorAction SilentlyContinue
        $members = @($members | Where-Object { $_.file.FullName -ne $target.file.FullName })
        $rotatedMembers = @($rotatedMembers | Where-Object { $_.file.FullName -ne $target.file.FullName })
        $familyTotal = [int64](($members | ForEach-Object { [int64]$_.file.Length } | Measure-Object -Sum).Sum)
    }

    if ($rotated) {
        Write-Output ("task_log_rotated path=$Path max_bytes=$maxBytes max_files=$maxFiles family_max_bytes=$familyMaxBytes")
    }
    exit 0
} catch {
    Write-Error ("task_log_rotate_failed path={0} reason={1}" -f $Path, $_.Exception.Message)
    exit 97
}
