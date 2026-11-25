param([string]$Game = 'P:\AI\forest-flowchart-claude\runtime', [int]$LogLines = 6)
# One-line health report: windows, hung state, last log lines.
Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices;
public static class GS {
  [DllImport("user32.dll")] public static extern bool IsHungAppWindow(IntPtr h);
  [DllImport("user32.dll", SetLastError=true)] public static extern IntPtr SendMessageTimeout(IntPtr h, uint m, IntPtr w, IntPtr l, uint flags, uint timeout, out IntPtr result);
}
'@
$exe = Join-Path $Game 'Forest.exe'
$p = Get-CimInstance Win32_Process -Filter "Name='Forest.exe'" | Where-Object { $_.ExecutablePath -eq $exe }
if (-not $p) { 'game: not running' } else {
  $lines = & (Join-Path $PSScriptRoot 'gamectl.ps1') -Action windows -Game $Game
  foreach ($ln in $lines) {
    $h = [IntPtr][int64](($ln -split ' ')[0])
    $r = [IntPtr]::Zero; $ok = [GS]::SendMessageTimeout($h, 0, [IntPtr]0, [IntPtr]0, 2, 1500, [ref]$r)
    "$ln | hung=$([GS]::IsHungAppWindow($h)) ping=$($ok -ne [IntPtr]::Zero)"
  }
}
$log = Join-Path $Game 'forest-chart-progress\events.log'
if (Test-Path $log) { Get-Content $log -Tail $LogLines }
