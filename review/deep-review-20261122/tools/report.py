# -*- coding: utf-8 -*-
"""최종 보고서: out\\깊은검수_결과.md(요약·방법·숫자) + out\\지적목록.md / .tsv(지적 한 줄마다 모든 칸)."""
import os, sys, json, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa
from findings_spec import ADULT_ONLY

FIND = [json.loads(l) for l in open(os.path.join(DATA, 'findings.jsonl'), encoding='utf-8')]
RR = json.load(open(os.path.join(DATA, 'read_result.json'), encoding='utf-8'))
ADJ = json.load(open(os.path.join(DATA, 'adjudicated.json'), encoding='utf-8'))
CLS = {'S': '표본', 'A': '한자음 잔재', 'C': '다른 뜻으로 읽힘', 'B': '일본식 영어·외래어 표기', 'D': '같은 원문 갈림', 'E': '말투', 'F': '운문', 'G': '인용 원전'}


def cls_name(c): return '+'.join(CLS.get(x, x) for x in c.split('+'))


def esc(s): return (s or '').replace('|', '\\|').replace('\n', ' ')


def main():
    order = {'major': 0, 'minor': 1}
    FIND.sort(key=lambda o: (CHN.get(o['chap'], 99), idkey(o['id'])))
    # 지적목록
    L = ['# Forest 한국어판 깊은 검수 — 지적 목록 (2026-11-22)', '',
         '> ⚠ **이 파일에는 작품 IV장 이후 내용이 들어 있다.** 사용자는 III장까지 했다 — 표에서 「장」이 IV 이상인 줄은 진도 뒤에 볼 것.', '',
         '- 지적 %d칸(같은 고침이 여러 칸이면 칸마다 한 줄). 근거 칸이 빈 지적은 없다.' % len(FIND),
         '- 「고칠 안」은 대본 글 그대로(토큰 `^g###` 화자·`^n` 줄바꿈 포함) — 그대로 넣으면 된다. 게임 파일에는 아무것도 넣지 않았다.',
         '- 「읽힘」= 원문을 모르는 새 독자(한국어만 봄)가 지금 줄·고친 줄에서 그 낱말에 걸렸는지. 「화면」= 엔진 칸 규칙(2바이트 글자 2칸, 한 줄 57칸, 대사 3줄, 줄 수 안 늘림, `^g` 뒤 숫자 금지).',
         '- 정책: 성적 구간이라 열지 않은 후보 %d칸은 번호만 맨 끝에.' % len(ADULT_ONLY), '',
         '| 칸 | 장 | 부류 | 유형/심각도 | 원문 | 지금 | 고칠 안 | 근거 | 읽힘 시험(지금 → 고친 안) | 화면 |',
         '|---|---|---|---|---|---|---|---|---|---|']
    tsv = ['칸\t장\t부류\t유형\t심각도\t원문\t지금\t고칠안\t근거\t읽힘_지금\t독자풀이_지금\t읽힘_고친안\t독자풀이_고친안\t화면\t제미나이가바꾼칸']
    for o in FIND:
        r = dict(RR['cells'].get(o['id'], {}))
        if r.get('fix', '').startswith('걸림'):
            r['fix'] += (' — 의도된 낯섦(사용자 결정 「인간 사람」)' if '인간 사람' in r['fix'] else ' — 뜻은 맞게 읽음(사람 확인)')
        rd = ('%s → %s' % (r.get('now', '—'), r.get('fix', '—'))) if r else '시험 뒤 추가(서지·표기) — 해당 없음'
        L.append('| %s | %s | %s | %s / %s | %s | `%s` | `%s` | %s | %s | %s |' % (
            o['id'], o['chap'], cls_name(o['cls']), esc(o['cat']), o['sev'], esc(o['ja']), esc(o['now']), esc(o['fix']), esc(o['why']), esc(rd), o['screen']))
        tsv.append('\t'.join([o['id'], o['chap'] or '', cls_name(o['cls']), o['cat'], o['sev'], o['ja'], o['now'], o['fix'], o['why'],
                              r.get('now', ''), r.get('now_para', ''), r.get('fix', ''), r.get('fix_para', ''), o['screen'], 'Y' if o['changed_by_gemini'] else '']))
    L += ['', '## 성적 구간이라 열지 않은 후보(번호만)', '', ' '.join(ADULT_ONLY)]
    open(os.path.join(OUT, '지적목록.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    open(os.path.join(OUT, '지적목록.tsv'), 'w', encoding='utf-8-sig').write('\n'.join(tsv) + '\n')
    c = collections.Counter(o['cls'] for o in FIND)
    print('지적', len(FIND), dict(c), collections.Counter(o['sev'] for o in FIND),
          'I~III', sum(1 for o in FIND if o['chap'] in SAFE_CH))
    print('읽힘', collections.Counter((RR['cells'].get(o['id'], {}).get('now', '—').split(':')[0], RR['cells'].get(o['id'], {}).get('fix', '—').split(':')[0]) for o in FIND))


if __name__ == '__main__':
    main()
