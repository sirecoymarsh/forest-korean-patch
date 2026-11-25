# -*- coding: utf-8 -*-
"""검출기 E: 인물별 말투 이탈 — 화자 코드(^g###, 999 지문 상자 제외)마다 1·2인칭·높임 분포를 원문·번역 양쪽에서 재고,
번역만 튀는 칸을 찾는다.

규칙
 - 원문 자질: 1인칭(俺/僕/私/あたし/あたい/わたくし/わし/うち…), 2인칭(あなた/あんた/きみ/おまえ/てめえ/貴様…),
   높임(문장 끝 です・ます・でした・ました・ません・でしょう・ください・ございます 가 있으면 polite).
 - 번역 자질: 1인칭(나·내가·난 = 나 / 저·제가·전 = 저), 2인칭(너·네가·넌 = 너 / 당신 / 자네 / 그쪽 / 댁),
   높임(문장 끝 요·니다·니까·세요·십시오 → polite).
 - 화자 s, 원문 자질 값 v 마다 번역 값 분포를 세고, 그 칸의 번역 값이 그 (s, v) 에서 15% 미만인 소수면 후보.
   원문 값 v 자체가 그 화자에게 10% 미만이면(원문도 튀는 곳) 뺀다. (s, v) 칸이 6칸 미만이면 판정하지 않는다.
 - 말버릇: 원문 っす 를 쓰는 칸(화자별 8칸 이상)에서 번역 끝말 분포를 재고 소수 끝말을 후보로.
→ out\\det_voice.tsv · out\\det_voice_profile.tsv
"""
import os, sys, re, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa

JFP = [('ore', r'俺|おれ|オレ'), ('boku', r'僕|ぼく|ボク'), ('watakushi', r'わたくし'), ('atashi', r'あたし|アタシ'),
       ('atai', r'あたい'), ('washi', r'わし|ワシ'), ('uchi', r'うち(?=[はがもの、])'), ('watashi', r'私|わたし|ワタシ')]
JSP = [('anata', r'あなた|貴方'), ('anta', r'あんた|アンタ'), ('kimi', r'きみ|君(?![主子臨])|キミ'), ('omae', r'おまえ|お前|オマエ'),
       ('temee', r'てめえ|てめー|テメエ'), ('kisama', r'貴様'), ('sonata', r'そなた|おぬし|お主')]
JPOL = re.compile(r'(です|ます|でした|ました|ません|でしょう|ください|下さい|ございます|ませ)(?:よ|ね|か|わ|の|って)*[。！？!?…」』\s]*$')
KFP = [('jeo', r'(?<![가-힣])(저|제가|전|절|제|저는|저를|저도|저한테|저희)(?![가-힣])'),
       ('na', r'(?<![가-힣])(나|내가|난|날|내|나는|나를|나도|나한테|나랑|우리)(?![가-힣])')]
KSP = [('neo', r'(?<![가-힣])(너|네가|니가|넌|널|너는|너를|너도|너한테|너랑|너희)(?![가-힣])'), ('dangsin', r'당신'), ('jane', r'자네'),
       ('geujjok', r'그쪽'), ('daek', r'(?<![가-힣])댁(?![가-힣])')]
KPOL = re.compile(r'(요|니다|니까|세요|십시오|시오|죠|지요|군요|네요|래요|에요|예요|어요|아요|해요|까요)(?:[?!.~…─"」\s]*)$')


def first(pats, t):
    hits = [k for k, p in pats if re.search(p, t)]
    return hits[0] if hits else None


def sentences(t, ja=False):
    t = plain(t)
    parts = re.split(r'(?<=[。！？!?])|(?<=[.!?])\s|\s{2,}' if not ja else r'(?<=[。！？!?])', t)
    return [p.strip() for p in parts if p and p.strip()]


def pol(t, ja):
    ss = sentences(t, ja)
    if not ss: return None
    pat = JPOL if ja else KPOL
    p = sum(1 for s in ss if pat.search(s))
    if p == 0: return 'plain'
    if p == len(ss): return 'polite'
    return 'mixed'


def ko_ending(t):
    ss = sentences(t)
    if not ss: return ''
    s = re.sub(r'[^가-힣]+$', '', ss[-1])
    return s[-2:]


def main():
    rows = [r for r in load_corpus() if r['kind'] == 'MSG' and r['chap'] and r['spk'] not in ('999', '') and r['ja'] and not r['hold']]
    ad = set(json.load(open(os.path.join(DATA, 'adult.json'), encoding='utf-8'))['ids'])
    feats = []
    for r in rows:
        ja, ko = plain(r['ja']), plain(r['ko'])
        feats.append({'r': r, 'jfp': first(JFP, ja), 'kfp': first(KFP, ko), 'jsp': first(JSP, ja), 'ksp': first(KSP, ko),
                      'jpol': pol(r['ja'], True), 'kpol': pol(r['ko'], False), 'ssu': 'っす' in ja or 'ッス' in ja, 'kend': ko_ending(r['ko'])})
    by = collections.defaultdict(list)
    for f in feats: by[f['r']['spk']].append(f)
    cands = []
    prof = []
    for s, fs in by.items():
        if len(fs) < 30: continue
        for jk, kk in (('jfp', 'kfp'), ('jsp', 'ksp'), ('jpol', 'kpol')):
            jd = collections.Counter(f[jk] for f in fs if f[jk])
            tot = sum(jd.values())
            for v, nv in jd.items():
                if nv < 6 or nv / tot < 0.10: continue
                sub = [f for f in fs if f[jk] == v and f[kk]]
                kd = collections.Counter(f[kk] for f in sub)
                if not sub: continue
                prof.append((s, jk, v, nv, dict(kd)))
                for f in sub:
                    share = kd[f[kk]] / len(sub)
                    if share < 0.15 and not (jk == 'jpol' and 'mixed' in (f[kk], v)):
                        cands.append((s, jk + '→' + kk, v, f[kk], '%d/%d' % (kd[f[kk]], len(sub)), f['r']))
        # 말버릇 っす
        ss = [f for f in fs if f['ssu']]
        if len(ss) >= 8:
            ed = collections.Counter(f['kend'] for f in ss)
            prof.append((s, 'っす→끝말', 'っす', len(ss), dict(ed.most_common(8))))
    with open(os.path.join(OUT, 'det_voice_profile.tsv'), 'w', encoding='utf-8') as fo:
        fo.write('화자\t자질\t원문값\t원문칸수\t번역값분포\n')
        for p in sorted(prof): fo.write('%s\t%s\t%s\t%d\t%s\n' % (p[0], p[1], p[2], p[3], json.dumps(p[4], ensure_ascii=False)))
    with open(os.path.join(OUT, 'det_voice.tsv'), 'w', encoding='utf-8') as fo:
        fo.write('화자\t자질\t원문값\t번역값\t그 값의 몫\t칸\t장\t성적구간\t일본어\t한국어\n')
        for s, k, v, kv, share, r in sorted(cands, key=lambda x: (x[0], x[1], idkey(x[5]['id']))):
            a = r['id'] in ad
            fo.write('%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (s, k, v, kv, share, r['id'], r['chap'], '*' if a else '',
                     '(생략)' if a else flat(r['ja']), '(생략)' if a else flat(r['ko'])))
    print('speakers profiled', len({p[0] for p in prof}), 'candidates', len(cands),
          collections.Counter(c[1] for c in cands))


if __name__ == '__main__':
    main()


# ---- E2: 한국어 안의 짝 어긋남(문장 단위) ----
NA = re.compile(r'(?<![가-힣])(나는|내가|나도|나를|나한테|나랑|난|내)(?![가-힣])')
JEO = re.compile(r'(?<![가-힣])(저는|제가|저도|저를|저한테|저랑|저희|전|절)(?![가-힣])')
NEO = re.compile(r'(?<![가-힣])(너는|네가|니가|너도|너를|너한테|너랑|넌|널|너)(?![가-힣])')
POLE = re.compile(r'(요|니다|니까|세요|십시오|시오|죠)[?!.~…─"」\s]*$')


def e2():
    rows = [r for r in load_corpus() if r['kind'] in ('MSG', 'SUB') and r['chap'] and not r['hold']]
    ad = set(json.load(open(os.path.join(DATA, 'adult.json'), encoding='utf-8'))['ids'])
    out = []
    for r in rows:
        t = re.sub(r'[「"“][^」"”]*[」"”]', ' ', plain(r['ko']))   # 안긴 인용은 뺀다
        for s in re.split(r'(?<=[.!?…])\s+|(?<=[.!?])(?=[^.!?…])', t):
            s = s.strip()
            if len(s) < 4: continue
            pol = bool(POLE.search(s))
            if pol and NA.search(s): out.append((r, 'R1 높임 문장에 나/내가', s))
            elif not pol and JEO.search(s) and re.search(r'(다|어|아|야|지|네|군|냐|니|자|라|걸|게|래|든|데)[?!.~…─\s]*$', s):
                out.append((r, 'R2 반말 문장에 저/제가', s))
            if pol and NEO.search(s) and not re.search(r'너무|너머|너희', s): out.append((r, 'R3 높임 문장에 너', s))
    with open(os.path.join(OUT, 'det_voice_pair.tsv'), 'w', encoding='utf-8') as fo:
        fo.write('규칙\t칸\t장\t화자\t바뀜\t성적구간\t문장\t일본어\n')
        for r, k, s in sorted(out, key=lambda x: (x[1], idkey(x[0]['id']))):
            a = r['id'] in ad
            fo.write('%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (k, r['id'], r['chap'], r['spk'], 'Y' if r['changed'] else '', '*' if a else '',
                     '(생략)' if a else s, '(생략)' if a else flat(r['ja'])))
    print('E2 pairs', len(out), collections.Counter(k for _, k, _ in out))


if __name__ == '__main__' and len(sys.argv) > 1 and sys.argv[1] == 'e2':
    e2()
