# -*- coding: utf-8 -*-
"""바뀐 칸 기계 검사 → ..\\data\\mech.jsonl(문제 있는 칸만) + ..\\data\\mech_summary.json

검사(사용자 확정 규칙·기존 게이트 그대로):
  TOKEN_G     ^g### 화자 코드 순서가 바뀜
  TOKEN_C     ^c? 색 코드가 바뀜(자막 ^cy/^ck)
  LINES       대사 4줄 이상(^n 기준 3줄 넘음) / 자막 줄 수 바뀜
  WIDTH       한 줄 57 EAW 넘음(W·F·A 를 2로)
  DIGIT_G     ^g### 바로 뒤 반각 숫자(엔진이 탐욕적으로 읽어 깨짐)
  OUTLINE     자막 몸체(^cy)와 외곽선(^ck) 글이 다름
  HALF_LATIN  새로 생긴 반각 로마자(굴림에서 겹쳐 찍힘 — 원문이 전각이면 전각)
  QUOTE       ASCII " 개수가 바뀜(사용자: 따옴표는 그대로 — 재제안 금지)
  TERM        사용자 확정 표기를 어김
  JOSA        이름 뒤 조사 받침 불일치
  CONSIST     같은 일본어가 고치기 전엔 같은 번역이었는데 고친 뒤 갈라짐
"""
import json, os, re, collections, unicodedata

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
TOK = re.compile(r'\^(g\d{3}|n|m|c[a-z])')

# 사용자 확정 표기(메모리 forest-korean-patch): 틀린 형 → 맞는 형
TERMS = [
    (r'조노사키', '기노사키'), (r'파도바', '파두아'), (r'라케루', '라켈'), (r'메어리', '메리'),
    (r'헤파렘프', '히파럼프'), (r'스킴블샹스|샹스(?!크)', '샹크스'), (r'토룽가', '토룬가'),
    (r'모자\s?장수', '매드 해터(帽子屋는 작품에 0회)'), (r'미친 다과회', '매드 티 파티'),
    (r'롱 샷', '롱 숏'), (r'라케르', '라켈'),
]
NAMES = ['라켈', '가든', '앨리스', '아케루', '나가츠키', '마유즈미', '카리야', '아메노모리', '기노사키', '파두아',
         '샹크스', '티거', '체셔', '매드 해터', '겨울잠쥐', '히파럼프', '시리우스', '헤르마이', '이이토모', '조조']
JOSA = {('이', '가'), ('은', '는'), ('을', '를'), ('과', '와'), ('으로', '로')}


def has_batchim(ch):
    o = ord(ch) - 0xAC00
    return 0 <= o < 11172 and o % 28 != 0


def batchim_l(ch):
    o = ord(ch) - 0xAC00
    return 0 <= o < 11172 and o % 28 == 8


def eaw(s):
    return sum(2 if unicodedata.east_asian_width(c) in 'WFA' else 1 for c in s)


def plain(s):
    return TOK.sub('', s)


def lines(s):
    return s.split('^n')


def main():
    rows = [json.loads(l) for l in open(os.path.join(DATA, 'changes.jsonl'), encoding='utf-8')]
    by_key = {(r['file'], r['slot']): r for r in rows}
    out, cnt = [], collections.Counter()
    # 자막 외곽선 짝: 몸체 슬롯 C 의 외곽선은 C+1(같은 묶음) — 고친 뒤 글을 비교
    for r in rows:
        flags = []
        o, n = r['old'], r['new']
        go, gn = re.findall(r'\^g\d{3}', o), re.findall(r'\^g\d{3}', n)
        if go != gn:
            flags.append(('TOKEN_G', f'{go} → {gn}'))
        co, cn = re.findall(r'\^c[a-z]', o), re.findall(r'\^c[a-z]', n)
        if co != cn:
            flags.append(('TOKEN_C', f'{co} → {cn}'))
        lo, ln = len(lines(o)), len(lines(n))
        if r['lane'] == 'msg':
            body = [l for l in lines(n)]
            while body and plain(body[-1]).strip() == '':
                body.pop()
            if len(body) > 3:
                flags.append(('LINES', f'{len(body)}줄'))
        elif r['lane'] in ('sub', 'sub_outline') and lo != ln:
            flags.append(('LINES', f'자막 줄 수 {lo} → {ln}'))
        w = max((eaw(plain(l)) for l in lines(n)), default=0)
        if w > 57:
            flags.append(('WIDTH', f'{w} EAW'))
        if re.search(r'\^g[0-9]{3}[0-9]', n):          # 반각만(전각 숫자는 안전 — \d 는 전각도 잡아 오탐)
            flags.append(('DIGIT_G', re.search(r'\^g[0-9]{3}[0-9]', n).group()))
        if r['lane'] in ('msg', 'choice_option', 'choice_prompt', 'sub'):
            lat_o = len(re.findall(r'[A-Za-z]', plain(o)))
            lat_n = len(re.findall(r'[A-Za-z]', plain(n)))
            if lat_n > lat_o:
                flags.append(('HALF_LATIN', ''.join(re.findall(r'[A-Za-z]+', plain(n)))[:40]))
        if o.count('"') != n.count('"'):
            flags.append(('QUOTE', f'" {o.count(chr(34))} → {n.count(chr(34))}'))
        for bad, good in TERMS:
            if re.search(bad, plain(n)) and not re.search(bad, plain(o)):
                flags.append(('TERM', f'{re.search(bad, plain(n)).group()} (확정: {good})'))
        for name in NAMES:
            for m in re.finditer(re.escape(name) + r'(으로|로|이|가|은|는|을|를|과|와)(?![가-힣])', plain(n)):
                last, j = name[-1], m.group(1)
                if j in ('으로', '로'):
                    good = '로' if (not has_batchim(last) or batchim_l(last)) else '으로'
                else:
                    pair = next(p for p in JOSA if j in p)
                    good = pair[0] if has_batchim(last) else pair[1]
                if j != good:
                    flags.append(('JOSA', f'{name}{j} → {name}{good}'))
        if r['lane'] == 'sub':
            mate = by_key.get((r['file'], r['slot'] + 1))
            if mate and mate['lane'] == 'sub_outline':
                if re.sub(r'\^c[a-z]', '', mate['new']) != re.sub(r'\^c[a-z]', '', n):
                    flags.append(('OUTLINE', '몸체와 외곽선 글이 다름'))
        if flags:
            out.append({**r, 'flags': flags})
            for f, _ in flags:
                cnt[f] += 1
    # 같은 일본어 → 같은 번역(사용자 확정 원칙): 대사만
    groups = collections.defaultdict(list)
    for r in rows:
        if r['lane'] == 'msg' and r['ja']:
            groups[r['ja']].append(r)
    # 바뀌지 않은 같은 원문 칸도 봐야 하므로 전체 대사를 다시 읽지 않고, 바뀐 칸끼리만 본다(바뀐 칸 vs 고치기 전 같은 번역)
    consist = 0
    for ja, rs in groups.items():
        if len(rs) < 2:
            continue
        olds = {plain(r['old']) for r in rs}
        news = {plain(r['new']) for r in rs}
        if len(olds) == 1 and len(news) > 1:
            consist += 1
            out.append({**rs[0], 'flags': [('CONSIST', f'같은 원문 {len(rs)}곳이 {len(news)}가지로 갈라짐')],
                        'consist_variants': sorted(news)})
            cnt['CONSIST'] += 1
    with open(os.path.join(DATA, 'mech.jsonl'), 'w', encoding='utf-8') as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    json.dump({'checked': len(rows), 'flagged_rows': len(out), 'flags': cnt}, open(os.path.join(DATA, 'mech_summary.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('checked', len(rows), 'flagged', len(out), dict(cnt))


if __name__ == '__main__':
    main()
