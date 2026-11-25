# -*- coding: utf-8 -*-
"""제미나이 5차(GPT 권고 반영) 재검수: 4차 스냅숏 → 지금 scr.
python -I recheck5.py → ..\\data\\recheck\\recheck5.txt"""
import os, sys, glob, json, re, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gscwalk import walk
RT = r'P:\AI\forest-flowchart-claude\runtime'
GS = r'C:\Users\CadriacLord\.gemini\antigravity\brain\5a8e551d-80c7-4e24-98ae-0bd89f2eb6a0\scratch'
P3 = os.path.join(GS, 'scr_pass3_snapshot'); P4 = os.path.join(GS, 'scr_pass4_snapshot')
CUR = os.path.join(RT, 'scr'); OLD = os.path.join(RT, 'scr_backup_20261121')
JA = r'P:\AI\forest-kr-build\ja_scr'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'data', 'recheck')
TOK = re.compile(r'\^(g\d{3}|n|m|c[a-z])')
def eaw(s):
    s = TOK.sub('', s); return sum(2 if unicodedata.east_asian_width(c) in ('W', 'F', 'A') else 1 for c in s)
def k(s): return s.decode('cp949', 'replace')
def j(s): return s.decode('cp932', 'replace')
def flat(s): return TOK.sub(lambda m: ' / ' if m.group(1) == 'n' else '', s)
stt = {}
for l in open(os.path.join(ROOT, 'data', 'stt.jsonl'), encoding='utf-8'):
    o = json.loads(l); stt[o['voice']] = o['text']
gpt = {}
for l in open(r'P:\AI\Codex\projects\forest-translation-review-20261121\outputs\수정권고.jsonl', encoding='utf-8'):
    if l.strip():
        o = json.loads(l); gpt[o['id']] = o
out = []
def P(*a): out.append(' '.join(str(x) for x in a))

files = sorted(os.path.basename(p) for p in glob.glob(os.path.join(CUR, '*.gsc')))
cur, p4, p3, old, ja = {}, {}, {}, {}, {}
cmdbad = []
for f in files:
    fid = int(f[:4])
    cur[fid] = walk(os.path.join(CUR, f)); p4[fid] = walk(os.path.join(P4, f))
    p3[fid] = walk(os.path.join(P3, f)); old[fid] = walk(os.path.join(OLD, f))
    if os.path.exists(os.path.join(JA, f)): ja[fid] = walk(os.path.join(JA, f))
    if cur[fid][0] != old[fid][0] or len(cur[fid][1]) != len(old[fid][1]): cmdbad.append(f)
P('대본 %d개, 명령부/칸 수가 원본과 다른 대본: %s' % (len(files), cmdbad))

def diffs(A, B):
    r = []
    for fid in A:
        for sl in range(len(A[fid][1])):
            a, b = k(A[fid][1][sl]), k(B[fid][1][sl])
            if a != b: r.append(('%d:%d' % (fid, sl), a, b))
    return r
d34 = diffs(p3, p4)
P('\n## 3차 스냅숏 → 4차 스냅숏: %d칸(외곽선 포함)' % len(d34))
for key, a, b in d34: P('  %s\n    3: %s\n    4: %s' % (key, flat(a), flat(b)))
d45 = diffs(p4, cur)
P('\n## 4차 스냅숏 → 지금: %d칸(외곽선 포함)' % len(d45))

# 슬롯 → 종류, 일본어 msg 짝
def slotinfo(fid):
    cmds, ss = cur[fid]
    kind, msgk = {}, {}
    n = 0
    for _, op, a in cmds:
        if op == 0x51: kind.setdefault(a[5], 'MSG'); msgk.setdefault(a[5], n); n += 1
        elif op == 0x52: kind.setdefault(a[4], 'APP')
        elif op == 0x20 and a and a[0] == 49: kind.setdefault(a[5], 'SUB')
        elif op == 0x20 and a and a[0] in (45, 46, 47, 48): kind.setdefault(a[5], 'OUT')
        elif op == 0x0E:
            kind.setdefault(a[1], 'CHQ')
            for i in range(a[0]): kind.setdefault(a[7 + i], 'CHO')
    jm = []
    if fid in ja:
        jm = [j(ja[fid][1][a[5]]) for _, op, a in ja[fid][0] if op == 0x51]
    msgslots = [a[5] for _, op, a in cmds if op == 0x51]
    return kind, msgk, jm, msgslots
info = {}
main = []
for key, a, b in d45:
    fid, sl = map(int, key.split(':'))
    if fid not in info: info[fid] = slotinfo(fid)
    kind = info[fid][0].get(sl, '?')
    if kind == 'OUT': continue
    main.append((key, a, b, kind))
P('외곽선 빼고 %d칸' % len(main))
# 외곽선 맞춤
outbad = []
for fid in info:
    cmds, ss = cur[fid]
    for i, (_, op, a) in enumerate(cmds):
        if op == 0x20 and a and a[0] == 45:
            grp = [x for x in cmds[i:i + 5] if x[1] == 0x20]
            if [x[2][0] for x in grp] == [45, 46, 47, 48, 49]:
                body = k(ss[grp[4][2][5]])
                if body.strip():
                    for x in grp[:4]:
                        if k(ss[x[2][5]]) != '^ck' + body[3:]: outbad.append('%d:%d' % (fid, x[2][5]))
P('자막 외곽선 어긋남(바뀐 대본 안): %s' % outbad)

for key, a, b, kind in main:
    fid, sl = map(int, key.split(':'))
    _, msgk, jm, msgslots = info[fid]
    ls = re.sub(r'\^g\d{3}|\^c[a-z]|\^m', '', b).split('^n')
    prob = []
    ga, gb = re.match(r'^\^(g\d{3}|c[a-z])', a), re.match(r'^\^(g\d{3}|c[a-z])', b)
    if (ga and ga.group()) != (gb and gb.group()): prob.append('앞코드')
    if kind == 'MSG' and len([l for l in ls if l]) > 3: prob.append('줄수')
    if max(eaw(l) for l in ls) > 57: prob.append('폭%d' % max(eaw(l) for l in ls))
    if a.count('"') != b.count('"'): prob.append('따옴표수')
    if re.search(r'\^g\d{3}\d', b): prob.append('g뒤숫자')
    if '。' in b or '、' in b: prob.append('일본문장부호')
    P('\n### %s [%s] %s' % (key, kind, prob or '형식 OK'))
    if kind == 'MSG' and sl in msgk and msgk[sl] < len(jm):
        P('  JA : ' + flat(jm[msgk[sl]]))
    g = gpt.get(key)
    if g:
        if kind == 'SUB': P('  JA(GPT 인용): ' + g['source_ja'])
        if g.get('voice') in stt: P('  Whisper: ' + stt[g['voice']])
        P('  GPT %s: %s' % (g['finding_id'], g['reason'][:300]))
    P('  옛판: ' + flat(k(old[fid][1][sl])))
    P('  4차 : ' + flat(a))
    P('  지금: ' + flat(b))
    if kind == 'MSG' and sl in msgslots:
        i = msgslots.index(sl)
        for q in range(max(0, i - 2), min(len(msgslots), i + 3)):
            if q == i: continue
            s2 = msgslots[q]
            P('    %s%d: %s | %s' % ('-' if q < i else '+', s2, flat(jm[q]) if q < len(jm) else '', flat(k(cur[fid][1][s2]))))

# 용어 훑기
def scan_ko(pat):
    r = []
    for fid in cur:
        for sl, s in enumerate(cur[fid][1]):
            t = k(s)
            if t.startswith('^ck'): continue
            if re.search(pat, t): r.append('%d:%d %s' % (fid, sl, flat(t)))
    return r
def scan_ja(pat):
    r = []
    for fid in ja:
        if fid not in info: info[fid] = slotinfo(fid)
        _, msgk, jm, msgslots = info[fid]
        for q, t in enumerate(jm):
            if re.search(pat, t):
                ko = flat(k(cur[fid][1][msgslots[q]])) if q < len(msgslots) else ''
                r.append('%d:%s JA %s\n      KO %s' % (fid, msgslots[q] if q < len(msgslots) else '?', flat(t), ko))
    return r
P('\n## 용어 훑기(지금 판, 외곽선 뺌)')
for lab, pat in [('KO 흑점', '흑점'), ('KO 검은 딱지', '검은 딱지'), ('KO 고양이 인간', '고양이 인간'),
                 ('KO 고양이 사람', '고양이 사람'), ('KO 개 인간', '개 인간'), ('KO 개 사람', '개 사람'),
                 ('KO 인간 사람', '인간 사람'), ('KO 핀치', '핀치'), ('KO 대위기', '대위기'), ('KO 원맨', '원맨'),
                 ('KO 독재', '독재'), ('KO 레이디', '레이디'), ('KO 숙녀', '숙녀'), ('KO 젠틀맨', '젠틀맨'), ('KO 신사', '신사'),
                 ('KO 플레이보이', '플레이보이'), ('KO 바람둥이', '바람둥이'), ('KO 벨', '벨 소리|벨소리|벨의'),
                 ('KO 방울', '방울'), ('KO 펄스', '펄스'), ('KO 맥박', '맥박'), ('KO 프레시', '프레시'),
                 ('KO 바디 스내처', '스내처|강탈자|도둑맞은 도시'), ('KO 각본', '각본|대본'), ('KO 호천하', '호천하|화창한 하늘')]:
    r = scan_ko(pat); P('- %s: %d' % (lab, len(r)))
    for x in r[:40]: P('    ' + x)
P('\n## 일본어 본문 훑기(msg만; 자막 음성은 대본에 없음)')
for lab, pat in [('黒丸', '黒丸'), ('ブラック', 'ブラック'), ('ピンチ', 'ピンチ'), ('ワンマン', 'ワンマン'), ('人間のヒト', '人間のヒト'),
                 ('猫の人/猫のヒト', '猫の(人|ヒト)'), ('犬の人/犬のヒト', '犬の(人|ヒト)'), ('レディ', 'レディ'), ('プレイボーイ', 'プレイボーイ'),
                 ('ベル', 'ベル'), ('フレッシュ', 'フレッシュ'), ('盗まれた街', '盗まれた|ボディ'), ('脚本', '脚本'), ('好天', '好天'),
                 ('プルス/ブレス/脈', 'プルス|ブレス|脈拍')]:
    r = scan_ja(pat); P('- %s: %d' % (lab, len(r)))
    for x in r[:30]: P('    ' + x)
open(os.path.join(D, 'recheck5.txt'), 'w', encoding='utf-8').write('\n'.join(out))
print('ok', len(d34), len(d45), len(main))
