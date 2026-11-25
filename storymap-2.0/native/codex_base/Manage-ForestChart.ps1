param(
    [Parameter(Mandatory=$true)][string]$GamePath,
    [ValidateSet('Verify','Install','Restore')][string]$Mode='Verify'
)
$ErrorActionPreference='Stop'
$chartRoot=[IO.Path]::GetFullPath((Resolve-Path -LiteralPath $GamePath).Path).TrimEnd('\')
$bundleRoot=$PSScriptRoot
$manifest=Get-Content -LiteralPath (Join-Path $bundleRoot 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$backupRoot=Join-Path $chartRoot 'forest-chart-backup-v1'
$receiptPath=Join-Path $chartRoot 'forest-chart-receipt.json'
function Target([string]$relative) {
    if ([IO.Path]::IsPathRooted($relative)) { throw 'Absolute manifest path rejected' }
    $resolved=[IO.Path]::GetFullPath((Join-Path $chartRoot $relative))
    if (-not $resolved.StartsWith($chartRoot+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Manifest path escaped game directory' }
    return $resolved
}
function Hash([string]$path) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { return '' }
    return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function AtomicWrite([string]$path,[byte[]]$bytes) {
    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($path)) | Out-Null
    $temporary=$path+'.forest-chart-tmp'
    [IO.File]::WriteAllBytes($temporary,$bytes)
    if ([IO.File]::Exists($path)) { [IO.File]::Replace($temporary,$path,[NullString]::Value) } else { [IO.File]::Move($temporary,$path) }
}
function AssertInstalled {
    foreach ($file in $manifest.files) {
        if ((Hash (Target $file.path)) -ne $file.installed_sha256) { throw ('Installed file mismatch: '+$file.path) }
    }
}
function AssertBase {
    foreach ($entry in $manifest.prerequisites) {
        if ((Hash (Target $entry.path)) -ne $entry.sha256) { throw ('Unsupported build; nothing changed: '+$entry.path) }
    }
    foreach ($file in $manifest.files) {
        $target=Target $file.path
        if ($file.kind -eq 'add' -and (Test-Path -LiteralPath $target)) { throw ('Added-file collision; nothing changed: '+$file.path) }
    }
}
if (-not (Test-Path -LiteralPath (Target 'Forest.exe') -PathType Leaf)) { throw 'Forest.exe is missing' }
$alreadyInstalled=(Hash (Target 'Forest.exe')) -eq ($manifest.files | Where-Object path -eq 'Forest.exe').installed_sha256
if ($Mode -eq 'Verify') {
    if ($alreadyInstalled) { AssertInstalled; 'PASS: installed chart files verified' } else { AssertBase; 'PASS: supported Korean base build verified' }
    exit 0
}
$running=Get-Process -Name Forest -ErrorAction SilentlyContinue | Where-Object { $_.Path -and [string]::Equals($_.Path,(Target 'Forest.exe'),[StringComparison]::OrdinalIgnoreCase) }
if ($running) { throw 'Close this Forest instance before installing or restoring' }
if ($Mode -eq 'Restore') {
    AssertInstalled
    foreach ($file in $manifest.files | Where-Object kind -eq 'replace') {
        $backup=Join-Path $backupRoot $file.path
        if ((Hash $backup) -ne $file.original_sha256) { throw ('Backup mismatch; nothing changed: '+$file.path) }
    }
    foreach ($file in $manifest.files | Where-Object kind -eq 'replace') { AtomicWrite (Target $file.path) ([IO.File]::ReadAllBytes((Join-Path $backupRoot $file.path))) }
    foreach ($file in $manifest.files | Where-Object kind -eq 'add') {
        $target=Target $file.path
        if ((Hash $target) -ne $file.installed_sha256) { throw 'Added file changed during restoration' }
        Remove-Item -LiteralPath $target
    }
    AssertBase
    @{schema=1;status='restored';version=$manifest.version;time=(Get-Date).ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath $receiptPath -Encoding UTF8
    'PASS: original executable/title hashes restored; saves and chart history retained'
    exit 0
}
if ($alreadyInstalled) { AssertInstalled; 'PASS: chart already installed'; exit 0 }
AssertBase
# Prepare every output and verify its hash before changing any game file.
$prepared=@{}
foreach ($file in $manifest.files) {
    if ($file.kind -eq 'replace') {
        $original=[IO.File]::ReadAllBytes((Target $file.path))
        [byte[]]$bytes=New-Object byte[] $file.installed_size
        [Array]::Copy($original,$bytes,[Math]::Min($original.Length,$bytes.Length))
        foreach ($change in $file.changes) { $chunk=[Convert]::FromBase64String($change.data); [Array]::Copy($chunk,0,$bytes,[int]$change.offset,$chunk.Length) }
    } else { [byte[]]$bytes=[IO.File]::ReadAllBytes((Join-Path $bundleRoot $file.payload)) }
    $sha=[Security.Cryptography.SHA256]::Create()
    try { $digest=[BitConverter]::ToString($sha.ComputeHash($bytes)).Replace('-','').ToLowerInvariant() } finally { $sha.Dispose() }
    if ($digest -ne $file.installed_sha256) { throw ('Package payload mismatch; nothing changed: '+$file.path) }
    $prepared[$file.path]=$bytes
}
foreach ($file in $manifest.files | Where-Object kind -eq 'replace') {
    $backup=Join-Path $backupRoot $file.path
    if (Test-Path -LiteralPath $backup) { if ((Hash $backup) -ne $file.original_sha256) { throw 'Existing backup mismatch' } }
    else { [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($backup)) | Out-Null; [IO.File]::Copy((Target $file.path),$backup) }
}
$changed=[Collections.Generic.List[object]]::new()
try {
    foreach ($file in $manifest.files) { AtomicWrite (Target $file.path) $prepared[$file.path]; $changed.Add($file) }
    AssertInstalled
} catch {
    $failure=$_
    foreach ($file in $changed) {
        if ($file.kind -eq 'replace') { AtomicWrite (Target $file.path) ([IO.File]::ReadAllBytes((Join-Path $backupRoot $file.path))) }
        elseif ((Hash (Target $file.path)) -eq $file.installed_sha256) { Remove-Item -LiteralPath (Target $file.path) }
    }
    throw $failure
}
@{schema=1;status='installed';version=$manifest.version;time=(Get-Date).ToString('o');files=$manifest.files.path;backup=$backupRoot} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $receiptPath -Encoding UTF8
'PASS: chart installed; original saves unchanged'
