# -*- coding: utf-8 -*-
"""사본 폴더에 적용 기록을 남긴다(번호·숫자·해시만 — 대사 내용은 싣지 않는다)."""
import os, sys, json, collections
sys.path.insert(0, r'Y:\AI\forest-deep-review\tools')
from common import *  # noqa
AP = r'Y:\AI\forest-deep-review\apply'
TOP = r'Y:\AI\forest-deep-review\applied_20261122'
log = json.load(open(os.path.join(AP, 'a2_log.json'), encoding='utf-8'))
ver = json.load(open(os.path.join(AP, 'a3_verify.json'), encoding='utf-8'))
cells = log['cells']
bychap = collections.Counter(CHAP.get(c['file'][:4], '?') for c in cells)
kinds = collections.Counter(c['kind'] for c in cells)
L = []; P = L.append
P('# Forest 한국어 대본 — 확정 541칸을 넣은 사본 (2026-11-22)')
P('')
P('- 이 폴더의 `scr\\` 는 최신판 `P:\\AI\\forest-flowchart-claude\\runtime\\scr`(제미나이 6차까지, 11-22 00:52 판) 104개 파일을 통째로 복사한 뒤, `P:\\AI\\forest-gemini-review\\제미나이_전달_20261122\\01_확정_반영목록.jsonl` 541칸을 넣은 것이다.')
P('- **원본 `runtime\\scr` 와 놀이 사본 `P:\\AI\\forest-kr-build\\game` 은 건드리지 않았다.** 게임에서 보려면 이 `scr\\` 를 쓰려는 게임 사본의 `scr\\` 자리에 통째로 덮어쓰면 된다(어디에 넣을지는 사용자가 정한다).')
P('')
P('## 무엇이 바뀌었나')
P('')
P('- 바뀐 파일 %d개 / 104개. 바뀐 칸 %d칸 + 자막 외곽선 사본 %d칸(%s 의 몸체와 같은 글로).' % (len(log['files']), len(cells), len(log['outline']), ', '.join(o['id'] for o in log['outline'])))
P('- 종류: ' + ' · '.join('%s %d' % kv for kv in kinds.most_common()) + ' (MSG 대사·지문, SUB 음성 자막, CHO 선택지)')
P('- 장별: ' + ' · '.join('%s장 %d' % (k, bychap[k]) for k in sorted(bychap, key=lambda x: CHN.get(x, 99))))
P('- 크기 변화 합: %+d 바이트' % sum(v['size'][1] - v['size'][0] for v in log['files'].values()))
P('- 들어 있지 않은 것: 사용자 결정 대기 25칸(`02`), 선택 37칸(`03`), 빼기(`04`), 정책 보류 40칸(`05`).')
P('')
P('## 어떻게 확인했나')
P('')
P('- 쓰기 도구(`apply\\gscrw.py`, 파일 머리 값으로 구역을 정함): 104개를 고치지 않고 다시 쓰면 원본과 바이트까지 같고, 제미나이 6차 앞뒤 파일(2400·2600)을 같은 문자열로 다시 쓰면 지금 파일과 바이트까지 같다.')
P('- 넣은 뒤 다른 판독기(명령 길이표로 명령부를 걷는 `gscwalk`)로 대조: 명령부 %d/%d 파일 같음 · 목록 칸이 넣을 글과 같음 %d/%d · 외곽선 %d · 나머지 슬롯 %d개 바이트까지 그대로 · 꼬리 구역 같음 · 목록 밖 파일 %d개는 원본과 같음 · 어긋남 %s.' % (
    ver['res'].get('명령부 같음', 0), len(log['files']), ver['res'].get('목록 칸 = fix 와 같음', 0), len(cells), ver['res'].get('외곽선 = 몸체와 같은 글', 0),
    ver['res'].get('나머지 슬롯 그대로', 0), ver['res'].get('목록 밖 파일 = 원본과 같음', 0), '없음' if not ver['bad'] else json.dumps(ver['bad'], ensure_ascii=False)))
P('- 코덱스 `gsc_codec`(제미나이가 쓰는 도구)도 바뀐 33개를 같은 문자열로 읽고, 고치지 않고 다시 쓰면 바이트까지 같다.')
P('- 넣은 글은 모두 CP949, 한 줄 57칸 이하, 대사 3줄 이하, 토큰·ASCII 따옴표 수 그대로. 줄 수가 느는 칸은 3122:34 하나(2→3줄).')
P('- 게임을 띄워 본 것은 아니다. 화면은 엔진의 칸 규칙으로만 쟀다.')
P('')
P('## 다시 만들기')
P('')
P('`Y:\\AI\\forest-deep-review\\apply\\` 에서 `python -I a1_prepare.py`(복사 — 뒤쪽 옛 도구 점검은 실패해도 됨) → `python -I a2_apply.py`(원본에서 읽어 사본에 씀, 몇 번 돌려도 같음) → `python -I a3_verify.py` → `python -I a4_compat.py`. 칸마다의 기록은 `apply\\a2_log.json`.')
P('')
P('## 바뀐 파일과 해시(SHA-256 앞 12자리: 넣기 전 → 넣은 뒤)')
P('')
P('| 파일 | 칸 | 크기 | 해시 |')
P('|---|---|---|---|')
for f in sorted(log['files']):
    v = log['files'][f]
    P('| %s | %d | %d → %d | %s → %s |' % (f, v['cells'], v['size'][0], v['size'][1], v['sha256'][0][:12], v['sha256'][1][:12]))
open(os.path.join(TOP, '적용기록.md'), 'w', encoding='utf-8', newline='\n').write('\n'.join(L) + '\n')
print('기록', os.path.join(TOP, '적용기록.md'), '| 장별', dict(bychap), '| 종류', dict(kinds))
