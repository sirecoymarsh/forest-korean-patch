# -*- coding: utf-8 -*-
"""노란 자막 전건을 영문 팬패치 원문과 기계적으로 대조한다.

자막(^cy/^ck)은 일본어 원문이 스크립트에 없어 영문 팬패치가 유일한 번역 출처다.
그런데 실제로 두 층의 오류가 섞여 있다:

  ① 영문판이 일본어 음성에서 벗어난 것  — 청해 없이는 발견 불가 (이 도구 범위 밖)
  ② 한국어가 영문판에서 벗어난 것        — 영문만 봐도 발견 가능 (이 도구 범위)

②를 잡는다. 의미 판정은 하지 않고 **구조 지표만** 비교한다:

  - 문장 수      : 영문 종결부호(. ! ? …) 개수 vs 한국어 종결부호 개수
  - 줄 수        : ^n 개수 (자막은 줄 구성이 화면 배치라 어긋나면 안 된다)
  - 물음표/느낌표: 개수 (의문·감탄이 통째로 사라지거나 생기는 것)
  - 말줄임        : ...... vs ……
  - 길이비       : 한국어 EAW폭 / 영문 문자수 (극단값은 축약·부연 의심)

구조가 어긋난다고 반드시 오류는 아니다(한국어 어순상 합치는 게 자연스러운 경우도 있다).
**검토 후보를 좁히는 용도**이며, 최종 판단은 사람이 한다.

  python audit_subtitles.py            전체 요약 + 상위 후보
  python audit_subtitles.py 2100       특정 파일만
  python audit_subtitles.py --all      전건 출력
"""
import json, sys, io, os, re, unicodedata
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

PILOT = Path(r"P:\AI\Codex\projects\_migrated_c_documents_codex\2026-07-29\p-game-forest\work\forest-en-korean-pilot")
# 영문 정본은 팬패치 배포 페이로드다. pilot\game\scr 은 파이프라인 실행 중 덮여 있어
# 쓰면 안 된다(2100.gsc 크기는 같은데 해시가 다르고 한글 CP949 바이트가 섞여 있다).
# trusted\2100.english.gsc 와 해시가 일치하는 쪽이 이 경로다.
EN_SCR = Path(r"P:\AI\Codex\projects\_migrated_c_documents_codex\2026-07-29\p-game-forest"
              r"\work\english_patch_research\patch_payload_full\scr")
VISIBLE = (PILOT / "translation_work" / "correction_work" / "visible_map.corrected.sealed.json")
CURRENT = Path(r"P:\AI\forest-kr-build\current\translation_map.current.json")
OUT = Path(r"P:\AI\forest-kr-build\audit\subtitle_structure.json")

# 내용 정책상 어떤 형태로도 처리하지 않는 파일
EXCLUDED = {'2101', '2301', '2302', '2501', '2601', '2700', '2801',
            '3022', '3039', '3081', '3121'}

sys.path.insert(0, str(PILOT / "translation_work" / "tools"))
from gsc_codec import parse_gsc  # noqa: E402


def eaw(s):
    return sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in s)


def strip_tokens(s):
    """제어 토큰을 제거해 순수 본문만 남긴다."""
    return re.sub(r'\^(?:g\d{3}|c[a-z]|[nm])', '', s)


def sentences_en(s):
    """영문 종결 단위 수. '......'(6점)는 하나로 센다."""
    s = re.sub(r'\.{3,}', '\u2026', s)
    return len(re.findall(r'[.!?\u2026]+', s))


def sentences_ko(s):
    s = re.sub(r'\.{3,}', '\u2026', s)
    s = re.sub(r'\u2026+', '\u2026', s)
    return len(re.findall(r'[.!?\u2026]+', s))


def load_slots():
    """uid -> (file, center_slot)"""
    d = json.load(open(VISIBLE, encoding='utf-8'))
    out = {}
    for r in d['records']:
        if r.get('lane') != 'voice_subtitle_overlay':
            continue
        t = r.get('target', {})
        out[r['uid']] = (t.get('file'), t.get('center_slot'))
    return out


def load_en_strings():
    """file -> [slot 문자열]"""
    cache = {}
    for p in sorted(EN_SCR.glob('*.gsc')):
        try:
            parts = parse_gsc(p.read_bytes())
        except Exception:
            continue
        cache[p.name] = parts.strings
    return cache


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith('-')]
    show_all = '--all' in sys.argv
    only = argv[0] if argv else None

    slots = load_slots()
    en_files = load_en_strings()
    recs = json.load(open(CURRENT, encoding='utf-8'))
    recs = recs['records'] if isinstance(recs, dict) else recs

    rows = []
    missing = 0
    for r in recs:
        uid = r['uid']
        if 'VOICE_OVERLAY' not in uid:
            continue
        fno = re.search(r'/(\d{4})\.gsc', uid).group(1)
        if fno in EXCLUDED:
            continue
        if only and fno != only:
            continue
        fn, slot = slots.get(uid, (None, None))
        if fn is None or fn not in en_files or slot is None:
            missing += 1
            continue
        try:
            raw = en_files[fn][slot]
        except Exception:
            missing += 1
            continue
        en = raw.decode('cp932', errors='replace') if isinstance(raw, bytes) else str(raw)
        ko = r['target']

        en_b, ko_b = strip_tokens(en), strip_tokens(ko)
        d = {
            'uid': uid, 'file': fno, 'slot': slot, 'en': en, 'ko': ko,
            'sent_en': sentences_en(en_b), 'sent_ko': sentences_ko(ko_b),
            'n_en': en.count('^n'), 'n_ko': ko.count('^n'),
            'q_en': en_b.count('?'), 'q_ko': ko_b.count('?'),
            'x_en': en_b.count('!'), 'x_ko': ko_b.count('!'),
            'len_en': len(en_b), 'len_ko': eaw(ko_b),
        }
        flags = []
        if d['n_en'] != d['n_ko']:
            flags.append('줄수')
        if d['sent_en'] != d['sent_ko']:
            flags.append('문장수')
        if d['q_en'] != d['q_ko']:
            flags.append('물음표')
        if d['x_en'] != d['x_ko']:
            flags.append('느낌표')
        ratio = d['len_ko'] / max(1, d['len_en'])
        d['ratio'] = round(ratio, 2)
        if ratio < 0.55:
            flags.append('축약의심')
        elif ratio > 1.35:
            flags.append('부연의심')
        d['flags'] = flags
        rows.append(d)

    flagged = [r for r in rows if r['flags']]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({'total': len(rows), 'flagged': len(flagged),
                               'records': flagged}, ensure_ascii=False, indent=1),
                   encoding='utf-8')

    import collections
    fc = collections.Counter(f for r in flagged for f in r['flags'])
    byfile = collections.Counter(r['file'] for r in flagged)
    print(f"대조 대상 자막 {len(rows)}건  (슬롯 미해결 {missing}건, 제외파일 밖)")
    print(f"구조 불일치 {len(flagged)}건 ({len(flagged)*100//max(1,len(rows))}%)")
    print(f"  지표별: {dict(fc)}")
    print(f"  파일별: {dict(sorted(byfile.items()))}")
    print(f"\n결과: {OUT}")

    order = {'줄수': 0, '문장수': 1, '느낌표': 2, '물음표': 3, '축약의심': 4, '부연의심': 5}
    flagged.sort(key=lambda r: (-len(r['flags']), min(order.get(f, 9) for f in r['flags']), r['file'], r['slot']))
    show = flagged if show_all else flagged[:25]
    print(f"\n=== 우선 검토 후보 {len(show)}건 ===")
    for r in show:
        print(f"[{r['file']}:{r['slot']}] {'·'.join(r['flags'])}  "
              f"문장 {r['sent_en']}->{r['sent_ko']} 줄 {r['n_en']}->{r['n_ko']} "
              f"?{r['q_en']}->{r['q_ko']} !{r['x_en']}->{r['x_ko']} 비{r['ratio']}")
        print(f"   EN {strip_tokens(r['en'])}")
        print(f"   KO {strip_tokens(r['ko'])}")


main()
