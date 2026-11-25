param(
  [Parameter(Mandatory=$true)][string]$Action,
  [string]$Game = 'P:\AI\forest-flowchart-claude\runtime',
  [string]$Out = '',
  [int]$X = 0, [int]$Y = 0,
  [string]$Key = '',
  [string]$Class = '',
  [int]$Delta = 0
)
# Forest test driver: messages go straight to the window, the real cursor never moves.
Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;
using System.Collections.Generic;
public static class W {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc f, IntPtr l);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f);
  [DllImport("user32.dll")] public static extern IntPtr GetDC(IntPtr h);
  [DllImport("user32.dll")] public static extern int ReleaseDC(IntPtr h, IntPtr dc);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
  public static List<IntPtr> Windows(uint pid) {
    var list = new List<IntPtr>();
    EnumWindows((h, l) => { uint p; GetWindowThreadProcessId(h, out p); if (p == pid && IsWindowVisible(h)) list.Add(h); return true; }, IntPtr.Zero);
    return list;
  }
  public static string Cls(IntPtr h) { var s = new StringBuilder(256); GetClassName(h, s, 256); return s.ToString(); }
  public static string Title(IntPtr h) { var s = new StringBuilder(256); GetWindowText(h, s, 256); return s.ToString(); }
}
'@ -ReferencedAssemblies System.Drawing
Add-Type -AssemblyName System.Drawing

function Get-ForestProcess {
  $exe = Join-Path $Game 'Forest.exe'
  Get-CimInstance Win32_Process -Filter "Name='Forest.exe'" | Where-Object { $_.ExecutablePath -eq $exe }
}
function Get-Target([string]$cls) {
  $p = Get-ForestProcess
  if (-not $p) { throw 'game not running' }
  $wins = [W]::Windows([uint32]$p.ProcessId)
  if ($cls) { $wins = @($wins | Where-Object { [W]::Cls($_) -eq $cls }) }
  else { $wins = @($wins | Where-Object { [W]::Title($_) -eq 'Forest' }) }
  if ($wins.Count -eq 0) { throw "window not found ($cls)" }
  return $wins[0]
}
function MkL([int]$x, [int]$y) { return [IntPtr](($y -shl 16) -bor ($x -band 0xffff)) }

switch ($Action) {
  'launch' {
    if (Get-ForestProcess) { 'already running'; break }
    $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = '"' + (Join-Path $Game 'Forest.exe') + '"'; CurrentDirectory = $Game }
    "launched pid=$($r.ProcessId) rc=$($r.ReturnValue)"
  }
  'windows' {
    $p = Get-ForestProcess
    if (-not $p) { 'not running'; break }
    foreach ($h in [W]::Windows([uint32]$p.ProcessId)) {
      $c = New-Object W+RECT; [void][W]::GetClientRect($h, [ref]$c)
      $wr = New-Object W+RECT; [void][W]::GetWindowRect($h, [ref]$wr)
      "{0} cls={1} title={2} client={3}x{4} at={5},{6}" -f $h, [W]::Cls($h), [W]::Title($h), $c.R, $c.B, $wr.L, $wr.T
    }
  }
  'shot' {
    $h = Get-Target $Class
    $c = New-Object W+RECT; [void][W]::GetClientRect($h, [ref]$c)
    $pt = New-Object W+POINT; [void][W]::ClientToScreen($h, [ref]$pt)
    $bmp = New-Object System.Drawing.Bitmap $c.R, $c.B
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($pt.X, $pt.Y, 0, 0, $bmp.Size)
    $g.Dispose(); $bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
    "saved $Out"
  }
  'print' {
    $h = Get-Target $Class
    $c = New-Object W+RECT; [void][W]::GetClientRect($h, [ref]$c)
    $wr = New-Object W+RECT; [void][W]::GetWindowRect($h, [ref]$wr)
    $bmp = New-Object System.Drawing.Bitmap ($wr.R - $wr.L), ($wr.B - $wr.T)
    $g = [System.Drawing.Graphics]::FromImage($bmp); $dc = $g.GetHdc()
    [void][W]::PrintWindow($h, $dc, 2); $g.ReleaseHdc($dc); $g.Dispose()
    $bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
    "printed $Out"
  }
  'activate' {
    # The engine pauses drawing while inactive; tell it it is active without stealing focus.
    $h = Get-Target $Class
    [void][W]::PostMessage($h, 0x1C, [IntPtr]1, [IntPtr]0); [void][W]::PostMessage($h, 0x06, [IntPtr]1, [IntPtr]0); 'activated'
  }
  'move' { $h = Get-Target $Class; [void][W]::PostMessage($h, 0x200, [IntPtr]0, (MkL $X $Y)); 'moved' }
  'click' {
    $h = Get-Target $Class
    [void][W]::PostMessage($h, 0x200, [IntPtr]0, (MkL $X $Y)); Start-Sleep -Milliseconds 150
    [void][W]::PostMessage($h, 0x201, [IntPtr]1, (MkL $X $Y)); Start-Sleep -Milliseconds 120
    [void][W]::PostMessage($h, 0x202, [IntPtr]0, (MkL $X $Y)); 'clicked'
  }
  'rclick' {
    $h = Get-Target $Class
    [void][W]::PostMessage($h, 0x204, [IntPtr]2, (MkL $X $Y)); Start-Sleep -Milliseconds 100
    [void][W]::PostMessage($h, 0x205, [IntPtr]0, (MkL $X $Y)); 'rclicked'
  }
  'wheel' {
    $h = Get-Target $Class
    $pt = New-Object W+POINT; $pt.X = $X; $pt.Y = $Y; [void][W]::ClientToScreen($h, [ref]$pt)
    $w = [IntPtr]([int64]($Delta -shl 16))
    [void][W]::PostMessage($h, 0x20A, $w, (MkL $pt.X $pt.Y)); 'wheeled'
  }
  'key' {
    $h = Get-Target $Class
    $vk = switch ($Key) { 'F8' {0x77} 'ESC' {0x1B} 'ENTER' {0x0D} 'SPACE' {0x20} 'HOME' {0x24} 'PGUP' {0x21} 'PGDN' {0x22} 'LEFT' {0x25} 'RIGHT' {0x27} 'UP' {0x26} 'DOWN' {0x28} '0' {0x30} default {[int][char]$Key} }
    [void][W]::PostMessage($h, 0x100, [IntPtr]$vk, [IntPtr]1); Start-Sleep -Milliseconds 80
    [void][W]::PostMessage($h, 0x101, [IntPtr]$vk, [IntPtr]([int64]0xC0000001)); "key $Key"
  }
  'kill' { $p = Get-ForestProcess; if ($p) { Stop-Process -Id $p.ProcessId -Force; 'killed' } else { 'not running' } }
  'log' { Get-Content (Join-Path $Game 'forest-chart-progress\events.log') -Tail 40 }
}
