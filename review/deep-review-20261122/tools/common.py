# -*- coding: utf-8 -*-
"""Forest 깊은 검수 공용: 경로·말뭉치 읽기·폭 셈.
모든 도구는  python -I tools\\xxx.py  로 돈다(-I 라 sys.path 를 손으로 넣는다)."""
import sys, os, re, json, unicodedata
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, r'P:\AI\forest-gemini-review\tools')
from gscwalk import walk  # noqa: E402

ROOT = r'Y:\AI\forest-deep-review'
DATA = os.path.join(ROOT, 'data')
OUT = os.path.join(ROOT, 'out')
CUR = r'P:\AI\forest-flowchart-claude\runtime\scr'          # 제미나이 사본 — 읽기만
OLD = r'P:\AI\forest-flowchart-claude\runtime\scr_backup_20261121'
JA = r'P:\AI\forest-kr-build\ja_scr'
EN = (r'P:\AI\Codex\projects\_migrated_c_documents_codex\2026-07-29\p-game-forest'
      r'\work\english_patch_research\patch_payload_full\scr')
GEM = r'C:\Users\CadriacLord\.gemini\antigravity\brain\5a8e551d-80c7-4e24-98ae-0bd89f2eb6a0\scratch'

CHAP = {'2100': 'I', '2101': 'I', '2200': 'II', '2300': 'III', '2301': 'III', '2302': 'III',
        '2400': 'IV', '2500': 'V', '2501': 'V', '2600': 'VI', '2601': 'VI', '2700': 'VII', '2701': 'VII',
        '2800': 'VIII', '2801': 'VIII', '2900': 'IX'}
for f in ['3011', '3021', '3022', '3023', '3024', '3031', '3032', '3033', '3034', '3039', '3041', '3042', '3043', '3044']:
    CHAP[f] = 'II'
for f in ['3061', '3062', '3063']: CHAP[f] = 'III'
for f in ['3071', '3072', '3073', '3074', '3081', '3082']: CHAP[f] = 'IV'
for f in ['3091', '3092', '3093']: CHAP[f] = 'V'
for f in ['3101', '3102', '3103', '3104']: CHAP[f] = 'VI'
for f in ['3111', '3112', '3121', '3122', '3123']: CHAP[f] = 'VII'
CHAP['3131'] = 'VIII'
CHN = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 'VI': 6, 'VII': 7, 'VIII': 8, 'IX': 9}

# 사용자 진도: III장까지(2300번대). 대화·보고에 내용을 내도 되는 장
SAFE_CH = {'I', 'II', 'III'}

# 정책 보류: 대본 통째(앞 검수 보류 + 과제 지시) — 열지 않는다
HOLD_FILES = {'2301', '2302', '3039', '2701'}

TOK = re.compile(r'\^(g\d{3}|n|m|c[a-z])')


def eaw(s):
    s = TOK.sub('', s)
    return sum(2 if unicodedata.east_asian_width(c) in ('W', 'F', 'A') else 1 for c in s)


def flat(s):
    return TOK.sub(lambda m: ' / ' if m.group(1) == 'n' else '', s or '')


def plain(s):
    """토큰·따옴표 걷은 글(셈용)."""
    return TOK.sub(lambda m: ' ' if m.group(1) == 'n' else '', s or '')


def load_corpus(path=None):
    p = path or os.path.join(DATA, 'corpus.jsonl')
    return [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()]


def dump_jsonl(rows, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fo:
        for r in rows:
            fo.write(json.dumps(r, ensure_ascii=False) + '\n')


def idkey(i):
    a, b = i.split(':')
    return (int(a), int(b))
