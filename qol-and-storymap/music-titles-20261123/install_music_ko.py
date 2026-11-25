# -*- coding: utf-8 -*-
"""Forest 특전 화면 한국어 그림 넣기·되돌리기 (2026-11-23).

넣는 것(37개, 이 폴더 install\\ 아래와 같은 자리):
  grpo\\3401~3414.wcg, 3501~3514.wcg  음악 감상 목록 14곡(평소·올림)
  grpo\\4730.wcg, 4740.wcg            「뒤로」 단추(남아 있던 「戻る」 획을 없앤 판)
  grpe\\4004~4006.wcg                 CG 감상·장면 감상·음악 감상 화면 배경의 라벨
  hiart\\grpe\\4004~4006.jpg            위 배경의 4K 판
  hiart\\index.tsv                     4K 짝 맞춤 값(위 세 배경의 sum1 만 바뀜)

  python -X utf8 install_music_ko.py install [게임 폴더]   (기본: P:\\AI\\forest-kr-build\\game)
  python -X utf8 install_music_ko.py revert  [게임 폴더]
  python -X utf8 install_music_ko.py verify  [게임 폴더]

- 넣기 전 원래 파일은 <게임>\\forest-music-ko-backup\\ 에 한 번만 둔다(이미 있으면 덮지 않음).
- 하드 링크로 묶인 사본이어도 다른 사본이 바뀌지 않게, 지우고 새로 쓴다.
- 게임이 켜져 있으면 멈춘다(그림을 읽는 중일 수 있음).
"""
import hashlib, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / 'install'
DEFAULT_GAME = Path(r'P:\AI\forest-kr-build\game')
BACKUP = 'forest-music-ko-backup'


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
