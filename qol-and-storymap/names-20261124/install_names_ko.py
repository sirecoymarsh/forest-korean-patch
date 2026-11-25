# -*- coding: utf-8 -*-
"""Forest 이름표 그림 48장(grps\gf001~055.wcg) 넣기·되돌리기 (2026-11-24).

코덱스가 만든 한국어 이름표는 글자가 위로 붙어 있어(그림 y 3~22), 대사 첫 줄보다 5px 높았다(1배 화면 실측: 이름 가운데 485, 대사 490).
→ 글자를 5px 내린 판. 사용자 11-24 「이름과 대사 줄이 일치하지 않는군 대사가 조금 아래로 내려가있어」.

  python -X utf8 install_names_ko.py install [게임 폴더] [--live]   (기본: P:\AI\forest-kr-build\game)
  python -X utf8 install_names_ko.py revert  [게임 폴더]
  python -X utf8 install_names_ko.py verify  [게임 폴더]

- 넣기 전 원래 파일은 <게임>\forest-names-backup\ 에 한 번만 둔다. 하드 링크로 묶인 사본도 안전하게 지우고 새로 쓴다.
- 이 폴더의 게임이 켜져 있으면 멈춘다(--live 면 그림만 바꿔 넣는다).
"""
import hashlib, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / 'install'
DEFAULT_GAME = Path(r'P:\AI\forest-kr-build\game')
BACKUP = 'forest-names-backup'


def files():
    return sorted(p.relative_to(SRC) for p in SRC.rglob('*') if p.is_file())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def forest_running(game):
    """이 게임 폴더의 Forest.exe 가 켜져 있나(다른 사본의 Forest 는 상관없음)."""
    import ctypes, ctypes.wintypes as wt
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    psapi = ctypes.WinDLL('psapi')
    want = str((Path(game) / 'Forest.exe').resolve()).lower()
    arr = (wt.DWORD * 4096)(); got = wt.DWORD()
    if not psapi.EnumProcesses(arr, ctypes.sizeof(arr), ctypes.byref(got)):
        return False
    k32.OpenProcess.restype = wt.HANDLE
    for pid in arr[:got.value // 4]:
        h = k32.OpenProcess(0x1000, False, pid)
        if not h:
            continue
        buf = ctypes.create_unicode_buffer(1024); n = wt.DWORD(1024)
        ok = k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n))
        k32.CloseHandle(h)
        if ok and buf.value.lower() == want:
            return True
    return False


def replace(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + '.new')
    shutil.copyfile(src, tmp)
    if dst.exists():
        os.remove(dst)            # 하드 링크면 이 사본의 링크만 끊긴다
    os.replace(tmp, dst)


def install(game):
    bk = game / BACKUP
    n_new = n_same = 0
    for rel in files():
        dst = game / rel
        b = bk / rel
        if dst.exists() and not b.exists():
            b.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(dst, b)
        elif not dst.exists():
            n_new += 1
        if dst.exists() and sha(dst) == sha(SRC / rel):
            n_same += 1          # 이미 같은 파일은 건드리지 않는다(켜진 게임이 읽는 중일 수 있음)
            continue
        replace(SRC / rel, dst)
    ok = verify(game)
    if ok:
        print(f'installed {len(files())} files (replaced {len(files()) - n_same}, unchanged {n_same}, new {n_new}); backup {bk}')
    return ok


def revert(game):
    bk = game / BACKUP
    if not bk.exists():
        print('no backup folder', bk); return False
    for rel in files():
        b = bk / rel
        if b.exists():
            replace(b, game / rel)
        else:
            print('no backup for', rel, '(left as is)')
    bad = [str(rel) for rel in files() if (bk / rel).exists() and sha(game / rel) != sha(bk / rel)]
    print('reverted' if not bad else f'revert mismatch: {bad}')
    return not bad


def verify(game):
    bad = [str(rel) for rel in files() if not (game / rel).exists() or sha(game / rel) != sha(SRC / rel)]
    print('verify', 'PASS' if not bad else f'FAIL {bad}')
    return not bad


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ('install', 'revert', 'verify'):
        print(__doc__); return 2
    game = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_GAME
    if not (game / 'Forest.exe').exists():
        print('not a Forest folder:', game); return 2
    live = '--live' in sys.argv[3:]
    if sys.argv[1] != 'verify' and forest_running(game) and not live:
        print('this Forest is running — close it first (or --live: grpo/grpe pictures only change, re-enter the screen to see)'); return 3
    ok = {'install': install, 'revert': revert, 'verify': verify}[sys.argv[1]](game)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
