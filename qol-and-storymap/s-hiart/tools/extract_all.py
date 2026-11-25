# -*- coding: utf-8 -*-
"""그림 묶음 → Y:\AI\forest-4k\src\<묶음>\<이름>.png (게임 폴더 낱 파일이 있으면 그것이 정본)."""
import sys, os, subprocess, concurrent.futures as cf
sys.path.insert(0, r'P:\AI\forest-kr-build\tools')
import xfl
G = r'Y:\AI\forest-qol-test-hiart\game'
OUT = r'Y:\AI\forest-4k\src'
TOOL = r'P:\AI\Codex\projects\_migrated_c_documents_codex\2026-07-29\p-game-forest\work\forest-en-korean-pilot\ui_work\tools\UiAssetTool.exe'
LOOSE = {'grpe.xfl':'grpe','grpo.xfl':'grpo','grpo_bg.xfl':'grpo','grpo_bu.xfl':'grpo','grpo_ci.xfl':'grpo','grpo_f.xfl':'grpo'}
jobs = []
for arc in ['grpe.xfl','grpo_bg.xfl','grpo_bu.xfl','grpo_ci.xfl','grpo_f.xfl','grpo.xfl']:
    d = os.path.join(OUT, arc[:-4]); os.makedirs(d, exist_ok=True)
    wd = os.path.join(r'Y:\AI\forest-4k\wcg', arc[:-4]); os.makedirs(wd, exist_ok=True)
    p = os.path.join(G, arc)
    for e in xfl.read_index(p):
        name = e[0]
        wcg = os.path.join(wd, name)
        loose = os.path.join(G, LOOSE[arc], name)
        src = 'loose' if os.path.exists(loose) else 'xfl'
        data = open(loose,'rb').read() if src == 'loose' else xfl.extract(p, e)
        open(wcg,'wb').write(data)
        jobs.append((arc, name, wcg, os.path.join(d, name[:-4] + '.png'), src))
def run(j):
    arc, name, wcg, png, src = j
    if os.path.exists(png): return j, 0, ''
    r = subprocess.run([TOOL, 'wcg2png', wcg, png], capture_output=True, text=True)
    return j, r.returncode, r.stderr[-200:]
bad = 0; loose = 0
with cf.ThreadPoolExecutor(8) as ex:
    for j, rc, err in ex.map(run, jobs):
        if j[4] == 'loose': loose += 1
        if rc or not os.path.exists(j[3]): bad += 1; print('FAIL', j[0], j[1], rc, err)
print('done', len(jobs), 'bad', bad, 'loose-override', loose)
