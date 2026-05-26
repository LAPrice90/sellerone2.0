if (-not ("WinApi" -as [type])) {
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class WinApi {
  [DllImport("user32.dll")]
  public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")]
  public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
}
"@
}

while ($true) {
  try {
    $root = (Get-Location).Path
    $visibleLoginRequest = Join-Path $root "out\systems\F\price_list_manager\live\f061_visible_login.requested"
    if (Test-Path $visibleLoginRequest) {
      Start-Sleep -Milliseconds 500
      continue
    }
    $liveDir = Join-Path $root "out\systems\F\price_list_manager\live"
    $loginModeRequest = Join-Path $liveDir "f061_login_mode.requested"
    $visibilityState = Join-Path $liveDir "f061_browser_visibility_state.txt"
    if (Test-Path $loginModeRequest) {
      $requestText = ""
      $visibilityText = ""
      try { $requestText = Get-Content $loginModeRequest -Raw -ErrorAction Stop } catch {}
      try { $visibilityText = Get-Content $visibilityState -Raw -ErrorAction Stop } catch {}
      $activeRequest = $requestText -match "(?im)^status=(requested|holding|still_required)\s*$"
      $needsVisibleLogin = $visibilityText -match "auth_state=(LOGIN_REQUIRED|BBP_LOGIN_REQUIRED|AMAZON_DASHBOARD_LOGIN_REQUIRED)"
      if ($activeRequest -and $needsVisibleLogin) {
        Start-Sleep -Milliseconds 500
        continue
      }
    }
    $showHelper = Get-CimInstance Win32_Process |
      Where-Object {
        $_.Name -like "powershell*" -and
        $_.CommandLine -like "*f_show_scraper_windows.ps1*"
      } |
      Select-Object -First 1 -Expand ProcessId
    if ($showHelper) {
      Start-Sleep -Milliseconds 500
      continue
    }

    $targets = Get-CimInstance Win32_Process |
      Where-Object {
        $_.Name -eq "chrome.exe" -and
        $_.CommandLine -match "Chrome_UC136|Chrome_91_F061|GoogleChromePortable"
      } |
      Select-Object -Expand ProcessId

    foreach ($id in $targets) {
      try {
        $p = Get-Process -Id $id -ErrorAction Stop
        if ($p.MainWindowHandle -ne 0) {
          [WinApi]::SetWindowPos($p.MainWindowHandle, [IntPtr]::Zero, -32000, -32000, 1280, 720, 0x0040) | Out-Null
          [WinApi]::ShowWindowAsync($p.MainWindowHandle, 11) | Out-Null
          [WinApi]::ShowWindowAsync($p.MainWindowHandle, 6) | Out-Null
          [WinApi]::ShowWindowAsync($p.MainWindowHandle, 0) | Out-Null
        }
      } catch {
      }
    }
  } catch {
  }

  Start-Sleep -Milliseconds 500
}
