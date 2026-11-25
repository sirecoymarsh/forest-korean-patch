param([string]$Out, [int]$TimeoutSec = 60, [string]$Class = '', [int]$MinMean = 18, [string]$Game = 'P:\AI\forest-flowchart-claude\runtime')
# Wait until the window shows something (mean brightness above MinMean), then save that frame.
$c = Join-Path $PSScriptRoot 'gamectl.ps1'
Add-Type -AssemblyName System.Drawing
$t0 = Get-Date
while ($true) {
  $tmp = $Out + '.tmp.png'
  try { & $c -Action print -Out $tmp -Class $Class -Game $Game | Out-Null } catch { }
  if (Test-Path $tmp) {
    $b = [System.Drawing.Bitmap]::FromFile($tmp)
    $sum = 0; $n = 0
    for ($y = 40; $y -lt $b.Height - 10; $y += 23) { for ($x = 10; $x -lt $b.Width - 10; $x += 23) { $p = $b.GetPixel($x, $y); $sum += ($p.R + $p.G + $p.B) / 3; $n++ } }
    $b.Dispose()
    $mean = [math]::Round($sum / [math]::Max(1, $n), 1)
    if ($mean -ge $MinMean) { Move-Item -Force $tmp $Out; "mean=$mean after $([int]((Get-Date) - $t0).TotalSeconds)s"; break }
  }
  if (((Get-Date) - $t0).TotalSeconds -gt $TimeoutSec) { if (Test-Path $tmp) { Move-Item -Force $tmp $Out }; "timeout mean=$mean"; break }
  Start-Sleep -Milliseconds 700
}
