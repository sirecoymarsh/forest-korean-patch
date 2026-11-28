# -*- coding: utf-8 -*-
"""원본 게임 파일을 싣지 않는 한국어 패치 꾸러미(xdelta 차분 + 설치·제거 bat)를 만들고 시험한다.

spec(JSON):
{
 "title": "밤이 온다! 한국어 누적 패치 2026-11-17",
 "exe": "NightRemaster.exe",              # 게임 폴더 확인용(있어야 하는 파일), 켜져 있으면 설치 거부
 "orig": "<원본 게임 폴더>",
 "patched": "<한국어판 결과 폴더(바뀌거나 새로 생긴 파일만 있어도 됨)>",
 "deltas": [["<원본 상대경로>", "<결과 상대경로>"], ...],   # 원본 파일에서 결과 파일을 만든다(같은 이름이면 덮어씀, 다른 이름이면 새로 생김)
 "copy": ["<결과 상대경로 또는 폴더>", ...],                # 원작에 없는 우리 파일(번역 대본·한국어 그림·DLL·글꼴 등)
 "out": "<출력 폴더>", "zip": "<ZIP 이름>"
}
python make_delta_patch.py build spec.json      # 꾸러미 만들기
python make_delta_patch.py test spec.json <빈 시험 폴더>   # 원본 사본에 설치 → 결과와 해시 대조 → 제거 → 원본과 해시 대조
"""
import json, os, sys, shutil, subprocess, hashlib, zipfile
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import ctypes
def sp(p):
    b = ctypes.create_unicode_buffer(1024)
    n = ctypes.windll.kernel32.GetShortPathNameW(str(p), b, 1024)
    return b.value if n else str(p)
XD = r'P:\AI\demonbane-ps2-kr\release\pkg\tools\xdelta3.exe'

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 24), b''): h.update(c)
    return h.hexdigest()

def win(*ps):
    n = max(os.path.getsize(p) for p in ps); b = 1 << 20
    while b < n: b <<= 1
    return min(b, (1 << 31) - 1)

def bs(p):
    return p.replace('/', chr(92))

def files_under(root, rel):
    p = os.path.join(root, rel)
    if os.path.isfile(p): return [rel]
    out = []
    for dp, dn, fn in os.walk(p):
        for f in fn: out.append(os.path.relpath(os.path.join(dp, f), root))
    return out

BAT_HEAD = '@echo off\r\nsetlocal EnableExtensions\r\nchcp 949 >nul\r\ncd /d "%~dp0"\r\nset "P=%~dp0KoreanPatch"\r\nset "XD=%P%\\tools\\xdelta3.exe"\r\nset "BK=%P%\\backup"\r\nset "S32=%SystemRoot%\\System32"\r\nset "FAILED="\r\n'

def build(spec):
    out = spec['out']; root = os.path.join(out, 'pkg'); P = os.path.join(root, 'KoreanPatch')
    if os.path.isdir(root): shutil.rmtree(root)
    os.makedirs(os.path.join(P, 'delta')); os.makedirs(os.path.join(P, 'tools')); os.makedirs(os.path.join(P, 'files'))
    shutil.copy2(XD, os.path.join(P, 'tools', 'xdelta3.exe'))
    man = {'title': spec['title'], 'deltas': [], 'copied': []}
    for i, (src, dst) in enumerate(spec['deltas']):
        so = os.path.join(spec['orig'], src); tp = os.path.join(spec['patched'], dst)
        name = f'd{i:02d}'
        b = str(win(so, tp))
        r = subprocess.run([XD, '-e', '-9', '-f', '-B', b, '-s', src, tp, os.path.join(P, 'delta', name + '.vcdiff')], capture_output=True, cwd=spec['orig'])
        assert r.returncode == 0, r.stderr.decode('mbcs', 'replace')
        restore = None
        if src.lower() == dst.lower():   # 덮어쓰는 원본은 되돌림 차분도
            r = subprocess.run([XD, '-e', '-9', '-f', '-B', b, '-s', tp, src, os.path.join(P, 'delta', name + '.restore.vcdiff')], capture_output=True, cwd=spec['orig'])
            assert r.returncode == 0, r.stderr.decode('mbcs', 'replace'); restore = name + '.restore.vcdiff'
        man['deltas'].append({'src': src, 'dst': dst, 'delta': name + '.vcdiff', 'restore': restore, 'win': b,
                              'src_size': os.path.getsize(so), 'src_sha256': sha(so), 'dst_sha256': sha(tp),
                              'delta_bytes': os.path.getsize(os.path.join(P, 'delta', name + '.vcdiff'))})
        print('delta', src, '->', dst, round(os.path.getsize(os.path.join(P, 'delta', name + '.vcdiff')) / 1048576, 1), 'MB', flush=True)
    for rel in spec['copy']:
        for f in files_under(spec['patched'], rel):
            d = os.path.join(P, 'files', f); os.makedirs(os.path.dirname(d), exist_ok=True); shutil.copy2(os.path.join(spec['patched'], f), d)
            man['copied'].append({'path': f.replace('\\', '/'), 'sha256': sha(d)})
    for dst, src in spec.get('extra_pkg', {}).items():
        d = os.path.join(P, dst)
        if os.path.isdir(src): shutil.copytree(src, d)
        else: os.makedirs(os.path.dirname(d), exist_ok=True); shutil.copy2(src, d)
    man['extra_targets'] = spec.get('extra_targets', [])
    json.dump(man, open(os.path.join(P, 'manifest.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    exe = spec['exe']
    # 설치
    L = [BAT_HEAD, f'set "EXE={exe}"\r\n', 'echo ' + '=' * 60 + '\r\n', f'echo  {spec["title"]} 설치\r\n', 'echo ' + '=' * 60 + '\r\n', 'echo.\r\n',
         'if not exist "%EXE%" goto :notgame\r\nif not exist "%XD%" goto :nopatch\r\n',
         '"%S32%\\tasklist.exe" /fi "imagename eq %EXE%" 2>nul | "%S32%\\find.exe" /i "%EXE%" >nul\r\nif not errorlevel 1 goto :running\r\n',
         'if exist "%BK%\\installed.txt" goto :already\r\nif not exist "%BK%" mkdir "%BK%"\r\nif exist "%BK%\\applied.txt" del "%BK%\\applied.txt"\r\n']
    for d in man['deltas']:
        L.append(f'if exist "{bs(d["src"])}" for %%A in ("{bs(d["src"])}") do if not "%%~zA"=="{d["src_size"]}" echo [주의] {d["src"]} 크기가 원본과 다릅니다(%%~zA 바이트). 다른 판본일 수 있지만 그대로 시도합니다.\r\n')
    L.append(f'echo [1/2] 원본 파일 {len(man["deltas"])}개에서 한국어판을 만드는 중... 몇 분 걸릴 수 있습니다.\r\n')
    for d in man['deltas']:
        L.append(f'call :apply "{bs(d["src"])}" "{bs(d["dst"])}" "{d["delta"]}" {d["win"]}\r\n')
    for line in spec.get('install_extra', []): L.append(line + '\r\n')
    L.append('echo [2/2] 한국어 파일을 넣는 중...\r\n"%S32%\\robocopy.exe" "%P%\\files" "." /E /NJH /NJS /NFL /NDL /NP >nul\r\nif errorlevel 8 set "FAILED=%FAILED% 한국어파일"\r\n')
    L.append('echo installed %DATE% %TIME%> "%BK%\\installed.txt"\r\necho.\r\nif defined FAILED goto :partial\r\necho 설치를 마쳤습니다. 되돌리려면 한국어패치_제거.bat 을 실행하세요.\r\ngoto :done\r\n:partial\r\necho [알림] 다음은 적용하지 못했습니다:%FAILED%\r\necho        원본 파일이 이 패치가 기대하는 판과 다를 수 있습니다.\r\n:done\r\nif not "%KR_NOPAUSE%"=="1" pause\r\nexit /b 0\r\n')
    L.append(':apply\r\nif not exist "%~1" (\r\n  set "FAILED=%FAILED% %~1"\r\n  exit /b 0\r\n)\r\nfor %%D in ("%~2") do if not exist "%%~dpD" mkdir "%%~dpD"\r\n"%XD%" -d -f -B %~4 -s "%~1" "%P%\\delta\\%~3" "%~2.kr_tmp"\r\nif errorlevel 1 (\r\n  if exist "%~2.kr_tmp" del "%~2.kr_tmp"\r\n  set "FAILED=%FAILED% %~2"\r\n  exit /b 0\r\n)\r\nmove /y "%~2.kr_tmp" "%~2" >nul\r\necho %~1^|%~2^|%~3^|%~4>> "%BK%\\applied.txt"\r\nexit /b 0\r\n')
    L.append(':notgame\r\necho [오류] 게임 폴더, 곧 %EXE% 가 있는 폴더에 압축을 풀어서 실행해야 합니다.\r\nif not "%KR_NOPAUSE%"=="1" pause\r\nexit /b 1\r\n:nopatch\r\necho [오류] KoreanPatch 폴더가 없습니다. 압축을 통째로 게임 폴더에 풀어 주세요.\r\nif not "%KR_NOPAUSE%"=="1" pause\r\nexit /b 1\r\n:running\r\necho [오류] 게임이 켜져 있습니다. 게임을 끄고 다시 실행해 주세요.\r\nif not "%KR_NOPAUSE%"=="1" pause\r\nexit /b 1\r\n:already\r\necho 이미 설치되어 있습니다. 다시 설치하려면 먼저 한국어패치_제거.bat 을 실행하세요.\r\nif not "%KR_NOPAUSE%"=="1" pause\r\nexit /b 1\r\n')
    open(os.path.join(root, '한국어패치_설치.bat'), 'wb').write(''.join(L).encode('cp949'))
    # 제거
    R = [BAT_HEAD, f'set "EXE={exe}"\r\n', f'echo  {spec["title"]} 제거\r\n', 'echo.\r\n', 'if not exist "%BK%\\installed.txt" goto :notinstalled\r\n',
         '"%S32%\\tasklist.exe" /fi "imagename eq %EXE%" 2>nul | "%S32%\\find.exe" /i "%EXE%" >nul\r\nif not errorlevel 1 goto :running\r\n',
         'if not "%KR_NOASK%"=="1" (\r\n  "%S32%\\choice.exe" /c YN /m "한국어 패치를 지우고 원래 게임으로 되돌릴까요"\r\n  if errorlevel 2 exit /b 0\r\n)\r\n']
    for line in spec.get('remove_extra', []): R.append(line + '\r\n')
    for d in man['deltas']:
        if d['restore']:
            R.append(f'call :restore "{bs(d["dst"])}" "{d["restore"]}" {d["win"]}\r\n')
        else:
            R.append(f'if exist "{bs(d["dst"])}" del /q "{bs(d["dst"])}"\r\n')
    for c in man['copied']:
        R.append(f'if exist "{c["path"].replace("/", chr(92))}" del /q "{c["path"].replace("/", chr(92))}"\r\n')
    dirs = sorted({os.path.dirname(c['path']).replace('/', '\\') for c in man['copied']} | {os.path.dirname(d['dst']).replace('/', '\\') for d in man['deltas'] if not d['restore']}, key=len, reverse=True)
    for dd in dirs:
        if dd: R.append(f'rd "{dd}" 2>nul\r\n')
    R.append('del "%BK%\\installed.txt"\r\nif exist "%BK%\\applied.txt" del "%BK%\\applied.txt"\r\necho.\r\nif defined FAILED echo [알림] 다음은 되돌리지 못했습니다:%FAILED%\r\nif not defined FAILED echo 원래 게임으로 되돌렸습니다. 세이브는 그대로 두었습니다.\r\nif not "%KR_NOPAUSE%"=="1" pause\r\nexit /b 0\r\n')
    R.append(':restore\r\n"%XD%" -d -f -B %~3 -s "%~1" "%P%\\delta\\%~2" "%~1.orig_tmp"\r\nif errorlevel 1 (\r\n  if exist "%~1.orig_tmp" del "%~1.orig_tmp"\r\n  set "FAILED=%FAILED% %~1"\r\n  exit /b 0\r\n)\r\nmove /y "%~1.orig_tmp" "%~1" >nul\r\nexit /b 0\r\n')
    R.append(':notinstalled\r\necho 설치 기록이 없습니다.\r\nif not "%KR_NOPAUSE%"=="1" pause\r\nexit /b 1\r\n:running\r\necho [오류] 게임이 켜져 있습니다. 게임을 끄고 다시 실행해 주세요.\r\nif not "%KR_NOPAUSE%"=="1" pause\r\nexit /b 1\r\n')
    open(os.path.join(root, '한국어패치_제거.bat'), 'wb').write(''.join(R).encode('cp949'))
    if spec.get('readme'):
        open(os.path.join(root, '패치_사용방법.txt'), 'wb').write(spec['readme'].replace('\n', '\r\n').encode('utf-8-sig'))
    zp = os.path.join(out, spec['zip'])
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        for dp, dn, fn in os.walk(root):
            for f in fn:
                p = os.path.join(dp, f); rel = os.path.relpath(p, root)
                z.write(p, rel, compress_type=zipfile.ZIP_STORED if f.endswith(('.vcdiff', '.mpg', '.mp4', '.webm', '.apeg', '.ngs')) else zipfile.ZIP_DEFLATED)
    print('zip', zp, round(os.path.getsize(zp) / 1048576, 1), 'MB')

def test(spec, T):
    man = json.load(open(os.path.join(spec['out'], 'pkg', 'KoreanPatch', 'manifest.json'), encoding='utf-8'))
    if os.path.isdir(T): shutil.rmtree(T)
    os.makedirs(T)
    need = {d['src'] for d in man['deltas']} | {spec['exe']} | set(man.get('extra_targets', []))
    for rel in need:
        d = os.path.join(T, rel); os.makedirs(os.path.dirname(d), exist_ok=True); shutil.copy2(os.path.join(spec['orig'], rel), d)
    before = {rel: sha(os.path.join(T, rel)) for rel in need}
    with zipfile.ZipFile(os.path.join(spec['out'], spec['zip'])) as z: z.extractall(T)
    env = dict(os.environ, KR_NOPAUSE='1', KR_NOASK='1')
    r = subprocess.run(['cmd', '/c', os.path.join(T, '한국어패치_설치.bat')], cwd=T, env=env, capture_output=True)
    print('install rc', r.returncode); print(r.stdout.decode('cp949', 'replace')[-1500:]); print(r.stderr.decode('cp949','replace')[-800:])
    bad = [d['dst'] for d in man['deltas'] if not os.path.exists(os.path.join(T, d['dst'])) or sha(os.path.join(T, d['dst'])) != d['dst_sha256']]
    bad += [c['path'] for c in man['copied'] if sha(os.path.join(T, c['path'])) != c['sha256']]
    bad += [r for r in man.get('extra_targets', []) if sha(os.path.join(T, r)) != sha(os.path.join(spec['patched'], r))]
    print('after install mismatched:', bad)
    r = subprocess.run(['cmd', '/c', os.path.join(T, '한국어패치_제거.bat')], cwd=T, env=env, capture_output=True)
    print('remove rc', r.returncode, r.stdout.decode('cp949', 'replace').strip().splitlines()[-2:])
    back = [rel for rel in need if sha(os.path.join(T, rel)) != before[rel]]
    left = [c['path'] for c in man['copied'] if os.path.exists(os.path.join(T, c['path']))] + [d['dst'] for d in man['deltas'] if not d['restore'] and os.path.exists(os.path.join(T, d['dst']))]
    print('after remove not original:', back, 'left over:', left[:5])
    ok = not bad and not back and not left
    print('RESULT', 'PASS' if ok else 'FAIL')
    shutil.rmtree(T)
    return ok

if __name__ == '__main__':
    spec = json.load(open(sys.argv[2], encoding='utf-8'))
    if sys.argv[1] == 'build': build(spec)
    else: sys.exit(0 if test(spec, sys.argv[3]) else 1)
