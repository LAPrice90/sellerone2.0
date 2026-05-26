Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class WinApiShow {
  [DllImport("user32.dll")]
  public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);

  [DllImport("user32.dll")]
  public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
}
"@

$positions = @(
  @{ X = 0; Y = 0; W = 1280; H = 720 },
  @{ X = 1280; Y = 0; W = 1280; H = 720 },
  @{ X = 0; Y = 720; W = 1280; H = 720 }
)

while ($true) {
  try {
    $targets = Get-CimInstance Win32_Process |
      Where-Object {
        $_.Name -eq "chrome.exe" -and
        (
          $_.CommandLine -match "Chrome_UC136|Chrome_91_F061|Chrome_91" -or
          $_.ExecutablePath -match "Chrome_UC136|Chrome_91_F061|Chrome_91|GoogleChromePortable"
        )
      } |
      Select-Object -Expand ProcessId

    $index = 0
    foreach ($id in $targets) {
      try {
        $p = Get-Process -Id $id -ErrorAction Stop
        if ($p.MainWindowHandle -ne 0) {
          $pos = $positions[$index % $positions.Count]
          [WinApiShow]::ShowWindowAsync($p.MainWindowHandle, 9) | Out-Null
          [WinApiShow]::SetWindowPos($p.MainWindowHandle, [IntPtr]::Zero, $pos.X, $pos.Y, $pos.W, $pos.H, 0x0040) | Out-Null
          $index++
        }
      } catch {
      }
    }
  } catch {
  }

  Start-Sleep -Milliseconds 1000
}
