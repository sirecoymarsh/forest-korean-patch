# -*- coding: utf-8 -*-
"""이야기의 지도를 게임 사본에 설치한다(사본 전용, 원본·사용자 사본은 건드리지 않음).

  python install_runtime.py <게임 사본 폴더>

설치: Forest.exe(DLL 로더만 붙인 판, Codex 1.0 과 같은 바이트), ForestChart.dll,
      scr\\0001.gsc(타이틀에 단추 추가), scr\\9000.gsc(단추 → 지도), fc\\(그림·글꼴·단추 그림)
되돌리기 자료: <사본>\\forest-chart-backup\\
"""
import hashlib, os, shutil, sys, json

ROOT = r'P:\AI\forest-flowchart-claude'
CODEX_RT = r'P:\AI\Codex\projects\forest-flowchart\work\ingame-chart\runtime'
BASE_EXE = 'f618b6f3948b26991861b088f4dc21b780aeb0b585783db059f2b3ffcc7b2c0f'
LOADER_EXE = 'eef9179e23276deefaa4b31b947e6ed4d2f51d3faac25da95f90643a1f04d555'
BASE_0001 = '0f007fea52433d8b82b338f3e6c255a41655d5f4cf8112e8363fc452190f3365'


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def title_script():
    """Codex 가 단추를 끼운 0001 에서 「이야기의 지도」와 「게임 종료」 자리를 맞바꾼다."""
    b = bytearray(open(os.path.join(CODEX_RT, 'scr', '0001.gsc'), 'rb').read())
    swaps = [
        (bytes.fromhex('1e000f000000ed030000030200 00a7010000'.replace(' ', '')), 0x1ce),   # 게임 종료 423 → 462
        (bytes.fromhex('4b000f00000051040000030200 00a7010000'.replace(' ', '')), 0x1ce),
        (bytes.fromhex('1e001000000049090000030200 00d2010000'.replace(' ', '')), 0x1a7),   # 지도 466 → 423
        (bytes.fromhex('4b00100000004a090000030200 00d2010000'.replace(' ', '')), 0x1a7),
    ]
    for pat, y in swaps:
        i = b.find(pat)
        assert i >= 0 and b.find(pat, i + 1) < 0, pat.hex()
        b[i + len(pat) - 4:i + len(pat)] = y.to_bytes(4, 'little')
    return bytes(b)


def main(game):
    exe = os.path.join(game, 'Forest.exe')
    bk = os.path.join(game, 'forest-chart-backup')
    cur = sha(exe)
    if cur not in (BASE_EXE, LOADER_EXE):
        sys.exit('지원하지 않는 Forest.exe: ' + cur)
    if sha(os.path.join(game, 'scr', '0001.gsc')) not in (BASE_0001,) and not os.path.isdir(bk):
        sys.exit('타이틀 스크립트가 예상과 다르다')
    os.makedirs(os.path.join(bk, 'scr'), exist_ok=True)
    if cur == BASE_EXE and not os.path.exists(os.path.join(bk, 'Forest.exe')):
        shutil.copyfile(exe, os.path.join(bk, 'Forest.exe'))
    t = os.path.join(game, 'scr', '0001.gsc')
    if sha(t) == BASE_0001 and not os.path.exists(os.path.join(bk, 'scr', '0001.gsc')):
        shutil.copyfile(t, os.path.join(bk, 'scr', '0001.gsc'))
    # 새 파일로 쓰고 바꿔 끼운다(하드링크 사본이어도 원본으로 새지 않게)
    def put(dst, data):
        tmp = dst + '.new'
        with open(tmp, 'wb') as f:
            f.write(data)
        if os.path.exists(dst):
            os.remove(dst)
        os.replace(tmp, dst)
    put(exe, open(os.path.join(CODEX_RT, 'Forest.exe'), 'rb').read())
    assert sha(exe) == LOADER_EXE
    put(os.path.join(game, 'ForestChart.dll'), open(os.path.join(ROOT, 'build', 'ForestChart.dll'), 'rb').read())
    put(t, title_script())
    put(os.path.join(game, 'scr', '9000.gsc'), open(os.path.join(ROOT, 'assets', 'launcher', '9000.gsc'), 'rb').read())
    fc = os.path.join(game, 'fc')
    os.makedirs(fc, exist_ok=True)
    for n in os.listdir(os.path.join(ROOT, 'assets')):
        if n.endswith('.png'):
            put(os.path.join(fc, n), open(os.path.join(ROOT, 'assets', n), 'rb').read())
    for n in os.listdir(os.path.join(ROOT, 'assets', 'fonts')):
        if n.endswith('.ttf'):
            put(os.path.join(fc, n), open(os.path.join(ROOT, 'assets', 'fonts', n), 'rb').read())
    for n in ('2377.wcg', '2378.wcg'):
        put(os.path.join(fc, n), open(os.path.join(ROOT, 'assets', 'title', n), 'rb').read())
    rec = {'exe': sha(exe), 'dll': sha(os.path.join(game, 'ForestChart.dll')), '0001': sha(t)}
    json.dump(rec, open(os.path.join(game, 'forest-chart-install.json'), 'w'), indent=1)
    print('installed', rec)


if __name__ == '__main__':
    main(sys.argv[1])
