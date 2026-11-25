param([int]$TimeoutSec = 150, [string]$Game = 'P:\AI\forest-flowchart-claude\runtime')
# Keep the (inactive) game ticking until the bridge is up and the title is on screen.
$c = Join-Path $PSScriptRoot 'gamectl.ps1'
$log = Join-Path $Game 'forest-chart-progress\events.log'
$base = 0; if (Test-Path $log) { $base = @(Select-String -Path $log -Pattern 'native bridge ready').Count }
$t0 = Get-Date
while ($true) {
  try { & $c -Action activate -Game $Game | Out-Null } catch { }
  $now = 0; if (Test-Path $log) { $now = @(Select-String -Path $log -Pattern 'native bridge ready').Count }
  if ($now -gt $base) {
    $r = & (Join-Path $PSScriptRoot 'waitshot.ps1') -Out (Join-Path $Game '..\out\title_check.png') -TimeoutSec 20 -MinMean 30 -Game $Game
    "bridge up after $([int]((Get-Date) - $t0).TotalSeconds)s; $r"
    break
  }
  if (((Get-Date) - $t0).TotalSeconds -gt $TimeoutSec) { 'timeout'; break }
  Start-Sleep -Milliseconds 800
}
