# -*- coding: utf-8 -*-
"""제미나이 3차(11-21 21:46) 재검수: 2차 스냅숏(내가 검수한 판) → 지금 scr 로 바뀐 칸을 모두 가른다.

  python -I recheck.py      → ..\\data\\recheck\\*.txt / *.json
"""
import json, os, re, sys, glob, collections, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gscwalk import walk

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'data')
OUT = os.path.join(D, 'recheck'); os.makedirs(OUT, exist_ok=True)
RT = r'P:\AI\forest-flowchart-claude\runtime'
OLD = os.path.join(RT, 'scr_backup_20261121')
CUR = os.path.join(RT, 'scr')
GS = r'C:\Users\CadriacLord\.gemini\antigravity\brain\5a8e551d-80c7-4e24-98ae-0bd89f2eb6a0\scratch'
P2 = os.path.join(GS, 'scr_pass2_snapshot')
JA = r'P:\AI\forest-kr-build\ja_scr'
TOK = re.compile(r'\^(g\d{3}|n|m|c[a-z])')


def dec(b):
    try:
        return b.decode('cp949')
    except UnicodeDecodeError:
        return '<<CP949 오류>>' + b.decode('cp949', 'replace')


def short(s):
    return TOK.sub(lambda m: ' / ' if m.group(1) == 'n' else '', s).strip()


def eaw(s):
    s = TOK.sub('', s)
    return sum(2 if unicodedata.east_asian_width(c) in ('W', 'F', 'A') else 1 for c in s)


def norm(s):
    s = re.sub(r'^\^c[a-z]', '', s)
    s = s.replace('「', '"').replace('」', '"').replace('　', ' ')
    return re.sub(r'\s+', ' ', s).strip()


def load(dirp, f, enc='cp949'):
    p = os.path.join(dirp, f)
    if not os.path.exists(p):
        return None, None
    c, s = walk(p)
    return c, [x.decode(enc, 'replace') if enc != 'cp949' else dec(x) for x in s]


def main():
    files = sorted(os.path.basename(p) for p in glob.glob(os.path.join(CUR, '*.gsc')))
    rows = {}
    for l in open(os.path.join(D, 'changes.jsonl'), encoding='utf-8'):
        r = json.loads(l); rows['%d:%d' % (r['file'], r['slot'])] = r
    verdicts = {}
    for p in sorted(glob.glob(os.path.join(D, 'verdicts', '*.jsonl'))):
        for l in open(p, encoding='utf-8'):
            if l.strip():
                v = json.loads(l); verdicts[v['id']] = v
    errs = json.load(open(os.path.join(D, 'errors.json'), encoding='utf-8'))
    clog = {x['id']: x for x in json.load(open(os.path.join(GS, 'pass3_changelog.json'), encoding='utf-8'))}
    stt = {}
    for l in open(os.path.join(D, 'stt.jsonl'), encoding='utf-8'):
        d = json.loads(l); stt[d['voice']] = d['text']
    heard = {}
    for k in range(1, 5):
        p = os.path.join(GS, 'sub_revised_%d.json' % k)
        if os.path.exists(p):
            for e in json.load(open(p, encoding='utf-8')):
                if e.get('ja_heard'):
                    heard['%d:%d' % (int(e['sid']), int(e['c_slot']))] = e['ja_heard']

    V = {}          # id -> dict(old, p2, cur, ja, kind)
    seq = {}        # file -> [id 순서]
    outline = set()
    snap_bad = []
    for f in files:
        fid = int(f[:4])
        co, so = load(OLD, f)
        c2, s2 = load(P2, f)
        cc, sc = load(CUR, f)
        if so is None or s2 is None:
            continue
        jc, js = load(JA, f, 'cp932')
        jcmd = jc if (jc is not None and len(jc) == len(cc)) else None
        jmsg = [js[a[5]] for _, op, a in jc if op == 0x51] if jc is not None else []
        kmsg = 0
        order = []
        for i, (_, op, a) in enumerate(cc):
            slots = []
            if op == 0x51:
                slots = [('msg', a[5], 5)]
            elif op == 0x52 and len(a) > 4:
                slots = [('append', a[4], 4)]
            elif op == 0x20 and a and a[0] == 49:
                slots = [('sub', a[5], 5)]
            elif op == 0x20 and a and 45 <= a[0] <= 48:
                outline.add('%d:%d' % (fid, a[5])); continue
            elif op == 0x0E:
                n = a[0]
                slots = [('choice_q', a[1], 1)] + [('choice_o', a[7 + k], 7 + k) for k in range(n) if 7 + k < len(a)]
            for kind, sl, ai in slots:
                key = '%d:%d' % (fid, sl)
                ja = ''
                if kind == 'msg':
                    ja = jmsg[kmsg] if kmsg < len(jmsg) else ''
                    kmsg += 1
                elif jcmd is not None and kind != 'sub':
                    ja = js[jcmd[i][2][ai]] if jcmd[i][2][ai] < len(js) else ''
                if key not in V:
                    V[key] = {'old': so[sl], 'p2': s2[sl], 'cur': sc[sl], 'ja': ja, 'kind': kind}
                    order.append(key)
        seq[fid] = order
        # 스냅숏이 내가 검수한 판과 같은가
        for sl in range(len(s2)):
            key = '%d:%d' % (fid, sl)
            if key in rows and rows[key]['new'] != s2[sl]:
                snap_bad.append(key)
        # 대사 칸 밖의 바뀜도 잡는다
        for sl in range(min(len(s2), len(sc))):
            key = '%d:%d' % (fid, sl)
            if key not in V and (s2[sl] != sc[sl] or key in rows):
                V[key] = {'old': so[sl], 'p2': s2[sl], 'cur': sc[sl], 'ja': '', 'kind': 'outline' if key in outline else 'other'}

    p3 = {k for k, v in V.items() if v['p2'] != v['cur']}
    p3_content = {k for k in p3 if V[k]['kind'] != 'outline'}
    rep = collections.OrderedDict()
    rep['snapshot_mismatch_vs_reviewed'] = snap_bad
    rep['p3_changed_physical'] = len(p3)
    rep['p3_changed_content'] = len(p3_content)
    rep['p3_unlogged'] = sorted(k for k in p3_content if k not in clog)
    rep['changelog_not_in_scr'] = sorted(k for k in clog if k not in p3_content)

    # --- 1. 내 목록 199칸 ---
    status = collections.Counter()
    detail = []
    hold_ids = {k for k, v in verdicts.items() if v['verdict'] == 'HOLD'}
    for e in errs:
        k = e['id']; v = verdicts[k]; x = V[k]
        r = rows[k]
        if 'やれくそ' in (r['ja'] or '') and '어이쿠' in r['new']:
            exp = r['old']
        else:
            exp = v.get('fix') or r['old']
        if x['cur'] == x['p2']:
            st = 'NOT_APPLIED'
        elif x['cur'] == exp:
            st = 'EXACT'
        elif norm(x['cur']) == norm(exp):
            st = 'NEAR'
        else:
            st = 'OTHER'
        status[st] += 1
        detail.append({'id': k, 'st': st, 'cat': e['cat'], 'reason': clog.get(k, {}).get('reason', ''), 'chapter': e['chapter'],
                       'ja': x['ja'] or ('[음성] ' + heard.get(k, '') + ' ‖ Whisper: ' + stt.get(r.get('voice'), '') if x['kind'] == 'sub' else ''),
                       'old': x['old'], 'p2': x['p2'], 'exp': exp, 'cur': x['cur'], 'why': e['why']})
    rep['my_list_status'] = dict(status)
    my_ids = {e['id'] for e in errs}

    # --- 2. 표기 규칙 ---
    mech = [json.loads(l) for l in open(os.path.join(D, 'mech.jsonl'), encoding='utf-8')]
    qk = ['%d:%d' % (m['file'], m['slot']) for m in mech if any(f == 'QUOTE' for f, _ in m['flags'])]
    lk = ['%d:%d' % (m['file'], m['slot']) for m in mech if any(f == 'HALF_LATIN' for f, _ in m['flags'])]
    rep['quote_still_bad'] = [k for k in qk if V[k]['cur'].count('"') != V[k]['old'].count('"') or ('「' in V[k]['cur'] and '「' not in V[k]['old'])]
    rep['latin_still_bad'] = [k for k in lk if len(re.findall(r'[A-Za-z]', TOK.sub('', V[k]['cur']))) > len(re.findall(r'[A-Za-z]', TOK.sub('', V[k]['old'])))]
    # 바뀐 모든 칸(옛 판 대비)에서 따옴표 개수가 달라진 곳
    rep['quote_count_drift_all'] = sorted(k for k, x in V.items() if x['kind'] != 'outline' and x['cur'] != x['old']
                                          and x['cur'].count('"') != x['old'].count('"'))

    # --- 3. 보류 칸 ---
    rep['hold_changed_in_p3'] = sorted(k for k in hold_ids if k in p3_content)

    # --- 4. 기계 점검(지금 판, 옛 판에 없던 흠만) ---
    mech_new = []
    def probs(x):
        s = x['cur']; out = []
        if '<<CP949' in s: out.append('CP949')
        if x['kind'] in ('msg', 'append'):
            go = re.match(r'^\^g\d{3}', x['old']); gn = re.match(r'^\^g\d{3}', s)
            if (go.group() if go else None) != (gn.group() if gn else None): out.append('화자코드 %s→%s' % (go and go.group(), gn and gn.group()))
            ls = re.sub(r'\^g\d{3}|\^c[a-z]|\^m', '', s).split('^n')
            while ls and ls[-1] == '': ls.pop()
            if len(ls) > 3: out.append('%d줄' % len(ls))
            w = max((eaw(l) for l in ls), default=0)
            if w > 57: out.append('폭 %d' % w)
            if re.search(r'\^g\d{3}[0-9]', s): out.append('^g뒤 반각숫자')
        if x['kind'] == 'sub' and s.strip() and not s.startswith('^cy'): out.append('^cy 없음')
        if '。' in s or '、' in s: out.append('일본 문장부호')
        return out
    for k in sorted(p3_content):
        x = V[k]
        pc = probs(x)
        po = probs({**x, 'cur': x['old']})
        new = [p for p in pc if p not in po]
        if new:
            mech_new.append((k, new))
    rep['mech_new_problems'] = mech_new
    # 자막 몸체·외곽선 맞춤(지금 판 전체)
    sync_bad = []
    for f in files:
        fid = int(f[:4]); cc, sc = load(CUR, f)
        for i, (_, op, a) in enumerate(cc):
            if op == 0x20 and a and a[0] == 45:
                grp = [g for g in cc[i:i + 5] if g[1] == 0x20]
                if [g[2][0] for g in grp] == [45, 46, 47, 48, 49]:
                    body = sc[grp[4][2][5]]
                    if body.strip():
                        for g in grp[:4]:
                            if sc[g[2][5]] != '^ck' + body[3:]:
                                sync_bad.append('%d:%d' % (fid, g[2][5])); break
    rep['outline_unsynced'] = sync_bad

    # --- 5. 借り暮らし ---
    bor = []
    for k, x in V.items():
        if re.search(r'借り暮|借りぐらし|借り暮し|ボロワ|ボロウ', x['ja']) or re.search(r'빌려 ?사는|소인|더부살이|바로우|바로워|보로워', x['cur']):
            bor.append(k)
    rep['borrowers_slots'] = sorted(bor, key=lambda k: tuple(map(int, k.split(':'))))

    # --- 6. ちゃん/짱/쨩 ---
    chan = []
    for k, x in V.items():
        if x['kind'] == 'outline': continue
        if re.search(r'짱|쨩', x['cur']) or ('灰流ちゃん' in x['ja']):
            chan.append(k)
    rep['chan_slots'] = sorted(chan, key=lambda k: tuple(map(int, k.split(':'))))

    json.dump({'V': V, 'seq': seq, 'heard': heard}, open(os.path.join(OUT, 'V.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump(rep, open(os.path.join(OUT, 'summary.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    def ctx(k, n_before=2, n_after=1):
        fid = int(k.split(':')[0]); order = seq.get(fid, [])
        if k not in order: return []
        i = order.index(k)
        return [(o, V[o]['ja'], short(V[o]['cur'])) for o in order[max(0, i - n_before):i] + order[i + 1:i + 1 + n_after]]

    # 목록 칸 중 그대로 안 들어간 것
    with open(os.path.join(OUT, 'mylist_not_exact.txt'), 'w', encoding='utf-8') as fo:
        for d in detail:
            if d['st'] in ('EXACT',): continue
            fo.write('\n#%s [%s] 장%s %s %s\n  JA : %s\n  OLD: %s\n  P2 : %s\n  내안: %s\n  지금: %s\n  까닭: %s\n' % (
                d['id'], d['st'], d['chapter'], d['cat'], d['reason'], d['ja'], short(d['old']), short(d['p2']), short(d['exp']), short(d['cur']), d['why']))
    # 내 목록 밖에서 이번에 바뀐 칸(검수 대상) — 보류 칸은 내용을 쓰지 않는다
    with open(os.path.join(OUT, 'p3_other.txt'), 'w', encoding='utf-8') as fo:
        for k in sorted(p3_content - my_ids, key=lambda k: tuple(map(int, k.split(':')))):
            x = V[k]
            reason = clog.get(k, {}).get('reason', '(기록 없음)')
            if k in hold_ids:
                fo.write('\n#%s [%s] — 정책 보류 칸: 내용 생략\n' % (k, reason)); continue
            r = rows.get(k, {})
            fo.write('\n#%s [%s] 종류=%s 장=%s\n' % (k, reason, x['kind'], r.get('chapter', '?')))
            for o, oj, ok in ctx(k):
                fo.write('   (문맥 %s) JA: %s | KO: %s\n' % (o, oj[:100], ok[:100]))
            if x['kind'] == 'sub':
                fo.write('  들음(제미나이): %s\n  Whisper: %s\n' % (heard.get(k, ''), stt.get(r.get('voice'), '')))
            else:
                fo.write('  JA : %s\n' % x['ja'])
            fo.write('  OLD: %s\n  P2 : %s\n  지금: %s\n' % (short(x['old']), short(x['p2']), short(x['cur'])))
    with open(os.path.join(OUT, 'borrowers.txt'), 'w', encoding='utf-8') as fo:
        for k in rep['borrowers_slots']:
            x = V[k]
            fo.write('#%s JA: %s\n   지금: %s\n' % (k, x['ja'], short(x['cur'])))
    with open(os.path.join(OUT, 'chan.txt'), 'w', encoding='utf-8') as fo:
        for k in rep['chan_slots']:
            x = V[k]
            fo.write('#%s (%s) JA: %s\n   지금: %s\n' % (k, x['kind'], x['ja'] or heard.get(k, ''), short(x['cur'])))
    print(json.dumps({k: (v if not isinstance(v, list) or len(v) < 40 else '%d건' % len(v)) for k, v in rep.items()}, ensure_ascii=True))


if __name__ == '__main__':
    main()
