# -*- coding: utf-8 -*-
"""제미나이 4차 재검수: 3차 스냅숏 → 지금 scr."""
import os, sys, glob, json, re, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gscwalk import walk
RT = r'P:\AI\forest-flowchart-claude\runtime'
GS = r'C:\Users\CadriacLord\.gemini\antigravity\brain\5a8e551d-80c7-4e24-98ae-0bd89f2eb6a0\scratch'
P3 = os.path.join(GS, 'scr_pass3_snapshot'); CUR = os.path.join(RT, 'scr'); OLD = os.path.join(RT, 'scr_backup_20261121')
JA = r'P:\AI\forest-kr-build\ja_scr'
D = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'recheck')
V = json.load(open(os.path.join(D, 'V.json'), encoding='utf-8'))['V']
TOK = re.compile(r'\^(g\d{3}|n|m|c[a-z])')
def eaw(s):
    s = TOK.sub('', s); return sum(2 if unicodedata.east_asian_width(c) in ('W', 'F', 'A') else 1 for c in s)
out = []
diff, snapbad, cmdbad = [], [], []
for p in sorted(glob.glob(os.path.join(CUR, '*.gsc'))):
    f = os.path.basename(p); fid = int(f[:4])
    c4, s4 = walk(p); c3, s3 = walk(os.path.join(P3, f)); c0, _ = walk(os.path.join(OLD, f))
    if c4 != c0 or len(s4) != len(s3): cmdbad.append(f)
    for sl in range(len(s3)):
        k = '%d:%d' % (fid, sl)
        a, b = s3[sl].decode('cp949', 'replace'), s4[sl].decode('cp949', 'replace')
        if k in V and V[k]['cur'] != a: snapbad.append(k)
        if a != b: diff.append((k, a, b))
out.append('명령부/칸 수 어긋남: %s' % cmdbad)
out.append('3차 스냅숏이 내가 본 3차와 다른 칸: %s' % snapbad)
out.append('4차에서 바뀐 칸 %d개' % len(diff))
for k, a, b in diff:
    ls = re.sub(r'\^g\d{3}|\^c[a-z]|\^m', '', b).split('^n')
    prob = []
    ga, gb = re.match(r'^\^g\d{3}', a), re.match(r'^\^g\d{3}', b)
    if (ga and ga.group()) != (gb and gb.group()): prob.append('화자코드')
    if len([l for l in ls if l]) > 3: prob.append('줄수')
    if max(eaw(l) for l in ls) > 57: prob.append('폭%d' % max(eaw(l) for l in ls))
    if a.count('"') != b.count('"'): prob.append('따옴표수')
    out.append('  %s %s' % (k, prob or 'OK'))
# 토룬가 장면: 3082 전부, 3101 전부(대사·서술), 일본어와 지금
for fid in (3082, 3101):
    c, s = walk(os.path.join(CUR, '%04d.gsc' % fid)); jc, js = walk(os.path.join(JA, '%04d.gsc' % fid))
    jm = [js[a[5]].decode('cp932', 'replace') for _, op, a in jc if op == 0x51]
    km = [(a[5], s[a[5]].decode('cp949', 'replace')) for _, op, a in c if op == 0x51]
    out.append('\n== %d ==' % fid)
    for (sl, ko), ja in zip(km, jm):
        out.append('%d:%d\n  JA: %s\n  KO: %s' % (fid, sl, TOK.sub(' / ', ja).replace(' /  / ', ' / '), TOK.sub(lambda m: ' / ' if m.group(1) == 'n' else '', ko)))
open(os.path.join(D, 'recheck4.txt'), 'w', encoding='utf-8').write('\n'.join(out))
