# -*- coding: utf-8 -*-
"""되감기 시험 사본 준비: 시험 DLL 넣기, 뮤텍스 이름 바꾸기(놀이 사본과 동시에 떠도 되게), 시험용 ini 줄.

시험 사본에만 쓴다. 놀이 사본(P:\\AI\\forest-kr-build\\game)은 읽지도 쓰지도 않는다.
사용: python -I prep_copy.py [키=값 ...]     예) present=1 hitext=0 hiart=0
"""
import hashlib, os, shutil, sys

GAME = r'Y:\AI\forest-qol-test-rewind\game'
DLL = r'P:\AI\forest-qol\s-rewind\build\ForestChart.dll'
assert os.path.normcase(GAME).startswith(os.path.normcase(r'Y:\AI\forest-qol-test-rewind'))

def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()[:12]

# 1) DLL — 기본은 되감기 작업 사본의 빌드. dll=<경로> 를 주면 그 DLL(예: 통합 소스의 빌드 P:\AIorest-qoluild\ForestChart.dll)
for a in list(sys.argv[1:]):
    if a.startswith('dll='): DLL = a.split('=', 1)[1]; sys.argv.remove(a)
shutil.copyfile(DLL, os.path.join(GAME, 'ForestChart.dll'))
print('dll', sha(os.path.join(GAME, 'ForestChart.dll')))

# 2) 뮤텍스 이름 RSCRIPT → RSCRIPZ (.data 의 한 곳)
exe = os.path.join(GAME, 'Forest.exe')
b = bytearray(open(exe, 'rb').read())
n = b.count(b'RSCRIPT\0')
if n == 1:
    i = b.index(b'RSCRIPT\0'); b[i + 6] = ord('Z')
    open(exe, 'wb').write(b); print('mutex renamed at file offset 0x%x' % i)
else:
    print('mutex name occurrences:', n, '(already renamed)' if b.count(b'RSCRIPZ\0') == 1 else '(unexpected)')
print('exe', sha(exe))

# 3) ini: 시험 줄을 바꿔 쓴다(다른 줄은 그대로)
ini = os.path.join(GAME, 'forest-qol.ini')
want = {'rewind': '1', 'rewind_log': '1', 'rewind_verify': '1', 'rewind_test': '1', 'present_test_shift_x': '20000',
        'hiart_test_mute': '1', 'hiart_test_skipmovie': '1'}
DROP = {'rewind_fast', 'rewind_units', 'rewind_barfix', 'rewind_subs', 'rewind_cap', 'rewind_unit_restart_ms'}   # 조사 때의 실험 줄(정식 모듈에는 없다)
for a in sys.argv[1:]:
    k, v = a.split('=', 1); want[k] = v
lines = open(ini, encoding='utf-8-sig').read().splitlines()
out = []; seen = set()
for ln in lines:
    k = ln.split('=', 1)[0].strip() if '=' in ln and not ln.lstrip().startswith(';') else None
    if k in DROP: continue
    if k in want:
        tail = ln.split(';', 1)[1] if ';' in ln else None
        out.append('%s=%s' % (k, want[k]) + ('   ;' + tail if tail else '')); seen.add(k)
    else:
        out.append(ln)
for k, v in want.items():
    if k not in seen: out.append('%s=%s' % (k, v))
open(ini, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
print('ini', {k: want[k] for k in sorted(want)})
