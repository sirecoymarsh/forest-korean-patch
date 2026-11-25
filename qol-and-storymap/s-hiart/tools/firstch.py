# -*- coding: utf-8 -*-
"""그림마다 처음 나오는 장(대본 명령 기준). 층→묶음은 0100.gsc 의 0x79 표."""
import sys, json, collections; sys.path.insert(0, r'P:\AI\forest-qol\s-hiart\tools')
import gscwalk
sc = {int(k): v[0] for k, v in json.load(open(r'Y:\AI\forest-4k\scenes.json', encoding='utf-8')).items()}
rows, strs = gscwalk.read_gsc(r'P:\AI\forest-kr-build\ja_scr\0100.gsc')
folder = {0: 'grpe'}
for pc, op, a in rows:
    if op == 0x79: folder[a[0]] = strs[a[1]]
inv = json.load(open(r'Y:\AI\forest-4k\inventory_raw.json', encoding='utf-8'))
have = collections.defaultdict(set)
for e in inv:
    if e['name'][:4].isdigit(): have[e['arc'][:-4]].add(int(e['name'][:4]))
uses = collections.defaultdict(set)   # (arc, id) -> scripts
for sid, p in gscwalk.all_scripts():
    rows, _ = gscwalk.read_gsc(p)
    for pc, op, a in rows:
        if op == 0x1e and a[1] < 65536:
            f = folder.get(a[0])
            if f and a[1] in have.get(f, ()): uses[(f, a[1])].add(sid)
        if op == 0x1800 and len(a) == 3 and a[1] in (501, 502, 503, 504) and a[2] in have['grpe']:
            uses[('grpe', a[2])].add(sid)
        if op == 0x14 and a[0] in have['grpe']: uses[('grpe', a[0])].add(sid)
out = {}
for (f, i), ss in uses.items():
    chs = [sc[s] for s in ss if s in sc]
    out['%s/%04d' % (f, i)] = {'first': min(chs) if chs else -1, 'scripts': sorted(ss)}
json.dump({'folder': folder, 'uses': out}, open(r'Y:\AI\forest-4k\first_chapter.json', 'w'), indent=0)
print('layer folders', folder)
for f in ['grpe', 'grpo_bg', 'grpo_bu', 'grpo_f', 'grpo_ci', 'grpo']:
    c = collections.Counter(v['first'] for k, v in out.items() if k.startswith(f + '/'))
    tot = len(have[f]); used = sum(c.values())
    print(f, 'total', tot, 'used', used, 'by first chapter', sorted(c.items()))
