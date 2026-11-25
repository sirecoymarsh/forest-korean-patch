param([string]$Game = 'P:\AI\forest-flowchart-claude\runtime2', [string]$Until = 'ui opened in game window', [int]$MaxClicks = 300, [int]$DelayMs = 260)
# Click through dialogue until the log shows $Until (counted after start), keeping the window active.
$c = Join-Path $PSScriptRoot 'gamectl.ps1'
$log = Join-Path $Game 'forest-chart-progress\events.log'
$base = @(Select-String -Path $log -Pattern $Until -SimpleMatch).Count
for ($i = 1; $i -le $MaxClicks; $i++) {
  & $c -Action activate -Game $Game | Out-Null
  & $c -Action click -X 400 -Y 300 -Game $Game | Out-Null
  Start-Sleep -Milliseconds $DelayMs
  if (@(Select-String -Path $log -Pattern $Until -SimpleMatch).Count -gt $base) { "reached '$Until' after $i clicks"; exit 0 }
}
"not reached after $MaxClicks clicks"
