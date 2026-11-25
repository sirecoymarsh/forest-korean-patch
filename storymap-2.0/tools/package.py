# -*- coding: utf-8 -*-
"""배포 묶음: out\\Forest-story-map-<ver>\\ + zip.

원본 EXE·타이틀 스크립트는 싣지 않고 바이트 차분만 싣는다(Codex 1.0 과 같은 방식).
"""
import base64, hashlib, json, os, shutil, sys, zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gscread
import install_runtime as IR

ROOT = r'P:\AI\forest-flowchart-claude'
VER = '2.0.0'
NAME = 'Forest-story-map-' + VER
OUT = os.path.join(ROOT, 'out', NAME)
BASE_GAME = r'P:\AI\forest-kr-build\game'


def sha(b):
    return hashlib.sha256(b).hexdigest()


def diff(a, b):
    """a→b 로 바꾸는 바이트 덩어리(길이가 늘면 꼬리 포함)."""
    out = []
    n = max(len(a), len(b))
    i = 0
    while i < n:
        if i < len(a) and i < len(b) and a[i] == b[i]:
            i += 1
            continue
        j = i
        while j < n and not (j < len(a) and j < len(b) and a[j] == b[j] and a[j:j + 8] == b[j:j + 8]):
            j += 1
        out.append({'offset': i, 'data': base64.b64encode(b[i:j]).decode()})
        i = j
    return out


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    pay = os.path.join(OUT, 'payload')
    os.makedirs(os.path.join(pay, 'fc'))
    os.makedirs(os.path.join(pay, 'scr'))
    files = []
    base_exe = open(os.path.join(BASE_GAME, 'Forest.exe'), 'rb').read()
    new_exe = open(os.path.join(IR.CODEX_RT, 'Forest.exe'), 'rb').read()
    assert sha(base_exe) == IR.BASE_EXE and sha(new_exe) == IR.LOADER_EXE
    files.append({'path': 'Forest.exe', 'kind': 'replace', 'original_sha256': IR.BASE_EXE,
                  'installed_sha256': IR.LOADER_EXE, 'installed_size': len(new_exe), 'changes': diff(base_exe, new_exe)})
    base_t = open(os.path.join(BASE_GAME, 'scr', '0001.gsc'), 'rb').read()
    new_t = IR.title_script()
    assert sha(base_t) == IR.BASE_0001
    files.append({'path': 'scr/0001.gsc', 'kind': 'replace', 'original_sha256': IR.BASE_0001,
                  'installed_sha256': sha(new_t), 'installed_size': len(new_t), 'changes': diff(base_t, new_t)})

    def add(rel, data):
        dst = os.path.join(pay, rel.replace('/', os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, 'wb').write(data)
        files.append({'path': rel, 'kind': 'add', 'payload': 'payload/' + rel, 'installed_sha256': sha(data)})
    add('ForestChart.dll', open(os.path.join(ROOT, 'build', 'ForestChart.dll'), 'rb').read())
    add("scr/9000.gsc", open(os.path.join(ROOT, "assets", "launcher", "9000.gsc"), "rb").read())
    for n in sorted(os.listdir(os.path.join(ROOT, 'assets'))):
        if n.endswith('.png'):
            add('fc/' + n, open(os.path.join(ROOT, 'assets', n), 'rb').read())
    for n in sorted(os.listdir(os.path.join(ROOT, 'assets', 'fonts'))):
        if n.endswith('.ttf'):
            add('fc/' + n, open(os.path.join(ROOT, 'assets', 'fonts', n), 'rb').read())
    add('fc/OFL.txt', open(os.path.join(ROOT, 'assets', 'fonts', 'OFL.txt'), 'rb').read())
    for n in ('2377.wcg', '2378.wcg'):
        add('fc/' + n, open(os.path.join(ROOT, 'assets', 'title', n), 'rb').read())
    model = json.load(open(os.path.join(ROOT, 'data', 'model.json'), encoding='utf-8'))
    code = [{'path': 'scr/%s.gsc' % sid, 'sha256': h} for sid, h in sorted(model['code_sha256'].items()) if sid != '0001']
    manifest = {'schema': 2, 'version': VER, 'supported': 'Forest Korean patch (command sections of the audited build)',
                'prerequisites': [{'path': 'Forest.exe', 'sha256': IR.BASE_EXE}, {'path': 'scr/0001.gsc', 'sha256': IR.BASE_0001}],
                'code_sections': code, 'files': files}
    json.dump(manifest, open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    ps = open(os.path.join(ROOT, 'tools', 'Manage-ForestStoryMap.ps1'), encoding='utf-8').read()
    open(os.path.join(OUT, 'Manage-ForestStoryMap.ps1'), 'w', encoding='utf-8-sig').write(ps)
    shutil.copyfile(os.path.join(ROOT, 'docs', '사용법.txt'), os.path.join(OUT, '사용법.txt'))
    z = os.path.join(ROOT, 'out', NAME + '.zip')
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
        for d, _, fs in os.walk(OUT):
            for f in fs:
                p = os.path.join(d, f)
                zf.write(p, os.path.join(NAME, os.path.relpath(p, OUT)))
    print('package', OUT, 'files', len(files), 'zip', os.path.getsize(z))


if __name__ == '__main__':
    main()
