# -*- coding: utf-8 -*-
"""줄 폭 초과(화면에서 접히는 대사)를 전수 검출한다.

한 줄이 표시 한계를 넘으면 엔진이 글자 단위로 강제 개행한다. 낱말 중간에서
끊기고("진작 / 에 나는") 3줄짜리 대사가 6줄이 되어 대사창 밖으로 밀린다.

표시 한계 = **57 EAW** (실측)
  3021.gsc 0x000370 두 줄이 각각 63인데 화면에서 접혔고, 접힌 지점의 누적폭이
  56/57이며 다음 글자를 포함하면 58 — 57까지 들어가고 58부터 접힌다.
  교차검증: 영문 팬패치 시나리오 30,270줄이 전건 54 이하(본문·자막 모두).

폭 계산은 EAW의 W/F/A를 2로 센다. A(애매폭)를 빼면 과소평가돼서 놓친다 —
하네스 runtime_line_eaw_width 와 같은 기준이다.

  python audit_line_width.py              전체 요약 + 파일별
  python audit_line_width.py 2600         특정 파일 전건 출력
  python audit_line_width.py --list       초과 레코드 전건 출력
"""
import json, sys, io, os, re, unicodedata, collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

CUR = r"P:\AI\forest-kr-build\current\translation_map.current.json"
OUT = r"P:\AI\forest-kr-build\audit\line_width.json"
MAX_EAW = 57

EXCLUDED = {'2101', '2301', '2302', '2501', '2601', '2700', '2801',
            '3022', '3039', '3081', '3121'}

TOK = re.compile(r'\^(?:g\d{3}|c[a-z]|[nm])')


def eaw(s):
    return sum(2 if unicodedata.east_asian_width(c) in 'WFA' else 1
               for c in TOK.sub('', s))


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith('-')]
    only = argv[0] if argv else None
    show_list = '--list' in sys.argv

    m = json.load(open(CUR, encoding='utf-8'))
    recs = m['records'] if isinstance(m, dict) else m

    bad = []
    for r in recs:
        fno = re.search(r'/(\d{4})\.gsc', r['uid']).group(1)
        if fno in EXCLUDED:
            continue
        if only and fno != only:
            continue
        lines = r['target'].split('^n')
        widths = [eaw(l) for l in lines]
        over = [(i, w) for i, w in enumerate(widths) if w > MAX_EAW]
        if not over:
            continue
        bad.append({
            'uid': r['uid'], 'file': fno,
            'is_overlay': 'VOICE_OVERLAY' in r['uid'],
            'max': max(widths), 'over_lines': len(over),
            'total_lines': len(lines),
            'widths': widths, 'target': r['target'],
        })

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({'limit': MAX_EAW, 'count': len(bad), 'records': bad},
              open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    byfile = collections.Counter(b['file'] for b in bad)
    hist = collections.Counter(b['max'] for b in bad)
    print(f"표시 한계 {MAX_EAW} EAW 초과 레코드: {len(bad)}건  (제외파일 밖)")
    print(f"  초과 줄 총계 {sum(b['over_lines'] for b in bad)}"
          f" / 2줄 이상 초과 {sum(1 for b in bad if b['over_lines'] > 1)}건"
          f" / 자막 {sum(1 for b in bad if b['is_overlay'])}건")
    print(f"  파일별: {dict(sorted(byfile.items()))}")
    print(f"  최대폭 분포: {dict(sorted(hist.items()))}")
    print(f"  초과분(줄여야 할 폭) 합계: "
          f"{sum(w - MAX_EAW for b in bad for w in b['widths'] if w > MAX_EAW)} EAW")
    print(f"\n결과: {OUT}")

    if only or show_list:
        print()
        for b in sorted(bad, key=lambda x: -x['max']):
            tag = ' 자막' if b['is_overlay'] else ''
            print(f"[{b['file']}]{tag} {b['uid'].split('::')[1][:26]}  최대 {b['max']}")
            for w, l in zip(b['widths'], b['target'].split('^n')):
                mark = '!' if w > MAX_EAW else ' '
                print(f"  {mark}{w:3d} {TOK.sub('', l)}")


main()
