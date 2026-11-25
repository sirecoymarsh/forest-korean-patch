# -*- coding: utf-8 -*-
"""「고화질 그림」 꾸러미: out\\Forest-hires-art-<ver>\\ (hiart\\ 705장 + index.tsv + 설치기).

본 패치(Forest-qol)와 따로 싣는다 — 1.76GB 이고 이미 JPEG/PNG 라 압축이 안 되며,
본 패치 설치기는 파일을 메모리에 다 올려 확인하는 방식이라 이 크기에 맞지 않는다.
게임 안 모듈(qol_hiart)은 hiart\\index.tsv 가 없으면 스스로 꺼지므로 이 꾸러미는 넣고 빼기만 하면 된다.
같은 드라이브(Y:)에서 만들 때는 하드 링크(용량 0)로 둔다 — 그림은 읽기만 한다.
"""
import hashlib, os, shutil, sys

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.0'
SRC = r'Y:\AI\forest-4k\out'
OUT = os.path.join(r'Y:\AI\forest-qol-release', 'Forest-hires-art-' + VER)
PS = r'''param(
    [Parameter(Mandatory=$true)][string]$GamePath,
    [ValidateSet('Verify','Install','Restore')][string]$Mode='Verify'
)
# Forest 고화질 그림(hiart\) 넣기·빼기. 본 패치(Forest-qol, ForestChart.dll)가 깔린 게임 폴더에 쓴다.
$ErrorActionPreference='Stop'
$game=[IO.Path]::GetFullPath((Resolve-Path -LiteralPath $GamePath).Path).TrimEnd('\')
$src=Join-Path $PSScriptRoot 'hiart'
$dst=Join-Path $game 'hiart'
function Files { Get-Content -LiteralPath (Join-Path $src 'index.tsv') -Encoding UTF8 | Where-Object { $_ -and -not $_.StartsWith('#') } | ForEach-Object { ($_.Split("`t"))[1] } }
if (-not (Test-Path -LiteralPath (Join-Path $game 'ForestChart.dll'))) { throw 'ForestChart.dll 이 없습니다 — 본 패치(Forest-qol)를 먼저 설치하세요' }
$running=Get-Process -Name Forest -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path.StartsWith($game,[StringComparison]::OrdinalIgnoreCase) }
if ($Mode -eq 'Verify') {
    $bad=@(); foreach ($f in Files) { $a=Join-Path $dst $f; $b=Join-Path $src $f; if (-not (Test-Path -LiteralPath $a) -or (Get-Item -LiteralPath $a).Length -ne (Get-Item -LiteralPath $b).Length) { $bad+=$f } }
    if ((Test-Path -LiteralPath $dst) -and -not $bad.Count) { 'PASS: 고화질 그림 설치됨 (' + (Files).Count + '장)' } elseif (Test-Path -LiteralPath $dst) { throw ('설치가 덜 됨: ' + $bad.Count + '장') } else { 'NOT INSTALLED: hiart\ 없음' }
    exit 0
}
if ($running) { throw '이 게임 폴더의 Forest 를 끈 뒤 하세요' }
if ($Mode -eq 'Restore') {
    if (Test-Path -LiteralPath $dst) { Remove-Item -LiteralPath $dst -Recurse -Force }
    'PASS: 고화질 그림을 뺐습니다(1배 늘림으로 돌아감)'; exit 0
}
$n=0
foreach ($f in Files) {
    $a=Join-Path $dst $f; $b=Join-Path $src $f
    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($a)) | Out-Null
    if ((Test-Path -LiteralPath $a) -and (Get-Item -LiteralPath $a).Length -eq (Get-Item -LiteralPath $b).Length) { $n++; continue }
    Copy-Item -LiteralPath $b -Destination ($a+'.tmp') -Force; Move-Item -LiteralPath ($a+'.tmp') -Destination $a -Force; $n++
}
Copy-Item -LiteralPath (Join-Path $src 'index.tsv') -Destination (Join-Path $dst 'index.tsv') -Force
'PASS: 고화질 그림 ' + $n + '장을 넣었습니다'
'''
README = """Forest 고화질 그림 (CG·스탠딩·배경·얼굴 창·컷인 4배, 705장)

본 패치(Forest-qol: 편의 기능 + 이야기의 지도)를 먼저 설치한 게임 폴더에 넣습니다.
창을 키우거나 전체 화면일 때 그림을 4배 그림으로 다시 합성합니다(1배 창에서는 쓰지 않음).
만드는 법: AI 4배(high-fidelity-4x)에서 원본 선에만 AI 를 쓰는 「섞기」 — 그림 느낌을 지키는 쪽.
앨리스 장면 CG 두 장은 넣지 않아 원래 그림을 늘려 보여 줍니다.

  검증: .\\Install-ForestHiresArt.ps1 -GamePath '게임 폴더' -Mode Verify
  설치: .\\Install-ForestHiresArt.ps1 -GamePath '게임 폴더' -Mode Install
  빼기: .\\Install-ForestHiresArt.ps1 -GamePath '게임 폴더' -Mode Restore

끄기만 하려면 게임 폴더 forest-qol.ini 에서 hiart=0.
"""


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    dst = os.path.join(OUT, 'hiart')
    rows = [l.rstrip('\n').split('\t') for l in open(os.path.join(SRC, 'index.tsv'), encoding='utf-8') if l.strip() and not l.startswith('#')]
    size = 0
    for r in rows:
        s = os.path.join(SRC, r[1].replace('/', os.sep)); d = os.path.join(dst, r[1].replace('/', os.sep))
        os.makedirs(os.path.dirname(d), exist_ok=True)
        try: os.link(s, d)
        except OSError: shutil.copy2(s, d)
        size += os.path.getsize(s)
    shutil.copy2(os.path.join(SRC, 'index.tsv'), os.path.join(dst, 'index.tsv'))
    open(os.path.join(OUT, 'Install-ForestHiresArt.ps1'), 'w', encoding='utf-8-sig').write(PS)
    open(os.path.join(OUT, '사용법.txt'), 'w', encoding='utf-8-sig').write(README)
    print('hires art package', OUT, 'pictures', len(rows), 'bytes', size)


if __name__ == '__main__':
    main()
