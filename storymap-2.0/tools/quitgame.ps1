param([string]$Game = 'P:\AI\forest-flowchart-claude\runtime2')
# Quit the way a player does: window X -> game's own "Quit Confirmation" -> Yes.
Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices;
public static class QG { [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l); }
'@
$c = Join-Path $PSScriptRoot 'gamectl.ps1'
$exe = Join-Path $Game 'Forest.exe'
if (-not (Get-CimInstance Win32_Process -Filter "Name='Forest.exe'" | Where-Object { $_.ExecutablePath -eq $exe })) { 'not running'; exit 0 }
$main = (& $c -Action windows -Game $Game) | Where-Object { $_ -match 'cls=LiosGameClass' } | Select-Object -Last 1
$h = [IntPtr][int64](($main -split ' ')[0])
[QG]::PostMessage($h, 0x112, [IntPtr]0xF060, [IntPtr]0) | Out-Null
$dlg = $null
for ($i = 0; $i -lt 15; $i++) { try { & $c -Action activate -Game $Game | Out-Null } catch {}; Start-Sleep -Milliseconds 400; $w = (& $c -Action windows -Game $Game) | Where-Object { $_ -match 'Quit Confirmation' }; if ($w) { $dlg = ($w -split ' ')[0]; break } }
if ($dlg) { [QG]::PostMessage([IntPtr][int64]$dlg, 0x111, [IntPtr]6, [IntPtr]0) | Out-Null } else { 'no confirmation dialog' }
for ($i = 0; $i -lt 20; $i++) { Start-Sleep -Milliseconds 400; if (-not (Get-CimInstance Win32_Process -Filter "Name='Forest.exe'" | Where-Object { $_.ExecutablePath -eq $exe })) { 'quit normally'; exit 0 } }
'still running'
