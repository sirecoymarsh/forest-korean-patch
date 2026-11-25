# -*- coding: utf-8 -*-
"""본 보고서 out\\깊은검수_결과.md — 맨 위에 기준 미달 항목, 그다음 숫자 요약·사용자가 정할 것·방법별 결과."""
import os, sys, json, collections, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa

ADJ = json.load(open(os.path.join(DATA, 'adjudicated.json'), encoding='utf-8'))
RR = json.load(open(os.path.join(DATA, 'read_result.json'), encoding='utf-8'))
FIND = [json.loads(l) for l in open(os.path.join(DATA, 'findings.jsonl'), encoding='utf-8')]
TT = json.load(open(os.path.join(DATA, 'terms_table.json'), encoding='utf-8'))
POPJ = json.load(open(os.path.join(DATA, 'population.json'), encoding='utf-8'))
VC = [json.loads(l) for l in open(os.path.join(DATA, 'voice_compare.jsonl'), encoding='utf-8')]
SCORE = open(os.path.join(OUT, 'score.md'), encoding='utf-8').read()
BIB = os.path.join(DATA, 'biblio.md')


def pct(a, b): return 100.0 * a / b if b else 0


def main():
    tm = [x for x in TT if x['kind'] == '음차']; tb = [x for x in TT if x['kind'] == '번역']
    t_ok = sum(x['ok'] for x in tm); t_n = sum(x['n'] for x in tm)
    b_ok = sum(x['ok'] for x in tb); b_n = sum(x['n'] for x in tb)
    rc = RR['cells']
    now_hit = sum(1 for v in rc.values() if v.get('now', '').startswith('걸림'))
    fix_hit = sum(1 for v in rc.values() if v.get('fix', '').startswith('걸림'))
    fix_any = sum(1 for v in rc.values() if v.get('fix', '') and v.get('fix') != '안 걸림')
    n_read = sum(1 for v in rc.values() if 'now' in v and 'fix' in v)
    ctrl = RR['control']
    maj = [o for o in FIND if o['sev'] == 'major']
    maj_now = sum(1 for o in maj if rc.get(o['id'], {}).get('now', '').startswith('걸림'))
    split = [v for v in VC if v['split']]
    sub_sp = [v for v in split if not v['interjection']]
    L = []
    P = L.append
    P('# Forest 한국어판 「깊은 검수」 결과 (2026-11-22)')
    P('')
    P('> ⚠ **이 파일과 같은 폴더의 지적목록·음성 페이지에는 작품 IV장 이후 내용이 들어 있다.** 사용자는 III장(2300번대)까지 했다. 대화·보고에는 칸 번호와 개수만 쓴다.')
    P('> 게임 파일에는 아무것도 넣지 않았다. 목록만 낸다. 반영은 사용자가 제미나이에게 넘긴다.')
    P('')
    P('## 0. 기준에 못 미친 것 (먼저 읽을 것)')
    P('')
    P('기준은 검수를 시작하기 전에 정했다(MQM 실무에서 흔히 쓰는 출고 기준 + 이번 과제의 요구).')
    P('')
    P('| 지표 | 기준 | 결과 | 판정 |')
    P('|---|---|---|---|')
    P('| 표본 오류율(minor 이상, 손대지 않은 칸) | ≤ 3%% | 층화 추정 **%.1f%%** [95%% %.1f–%.1f], 포획-재포획 보정 **%.1f%%** | **미달** |' % (
        ADJ['rate_minor_strat'][0], ADJ['rate_minor_strat'][1], ADJ['rate_minor_strat'][2], ADJ['rate_minor_capture_recapture']))
    P('| 표본 오류율(major 이상) | ≤ 1%% (95%% 상한까지) | 점추정 **%.2f%%**(397칸 중 1칸), Wilson 상한 %.1f%% | 점추정은 통과, **상한은 미달(표본이 작아 확정 못 함)** |' % (
        ADJ['rate_major_wilson'][0], ADJ['rate_major_wilson'][2]))
    P('| 검수자 일치도 κ(오류 있음/없음) | ≥ 0.6 | Claude A–B **0.30** | **미달** — minor 판정은 검수자마다 크게 갈린다 |')
    P('| 검수자 일치도 κ(major 이상) | ≥ 0.6 | 0.67 | 통과 |')
    P('| 검수자 재현율(심은 결함, 유형별) | 유형마다 ≥ 80% | A: 일본식 영어 4/5(80%)까지 모두 통과 · B: **말투 3/5·용어 3/5(60%)** | **B 미달** |')
    P('| 한자음 검출기 재현율(앞 검수 실례 10곳) | ≥ 90% | 원문 음 규칙만 3/10 → 보조 규칙(한국어 쪽 드문 한자어) 더해 10/10 | 단독 **미달**, 합쳐서 통과 |')
    P('| 음차 용어 일관 비율 | ≥ 99%% | %.2f%% (%d/%d칸) | 통과 |' % (pct(t_ok, t_n), t_ok, t_n))
    P('| 같은 원문 문장 갈림(12자 이상) | 0 | 493묶음 중 1묶음 — 화자가 다른 두 인물이라 사용자 예외 ② | 통과 |')
    P('| 화면 넘침(고칠 안) | 0 | %d칸 중 0 | 통과(**대사창을 그리는 도구가 없어 엔진 칸 규칙으로 셈** — 아래 10절) |' % len(FIND))
    P('| 읽힘 시험: 고친 안을 다른 뜻으로 읽음 | ≤ 5%% | 0/%d칸(낱말이 눈에 띈 %d칸도 뜻은 맞게 읽음 — 그중 6칸은 「인간 사람」의 의도된 낯섦) | 통과 |' % (n_read, fix_hit))
    P('| 인용 원전 정착 표기 일치 | 100% | 확인한 29작품 중 **다름 8**(고칠 안 5종 23칸 + 결정 3), 번역본 없음 1 | **미달** |')
    P('| GPT 독립 판정 일치도 κ | ≥ 0.6 | **아직 없음** — 꾸러미만 만듦(사용자가 넘김) | 보류 |')
    P('')
    P('**한 줄 판단**: 뜻이 틀린 오역(major)은 드물다(표본 0.25%%, 손대지 않은 칸 약 %d칸 기준 22칸 안팎으로 추정). 대신 **어색한 번역투·한자음 잔재·다른 뜻으로 읽히는 한자어 같은 minor 결함이 칸의 4~5%%에 퍼져 있다** — 이번 부류 검출기로 %d칸을 찾았고, 남은 것은 무작위 전수 검수보다 부류 검출기가 싸게 잡는다(4절).' % (POPJ['N'], len(FIND)))
    P('')
    P('## 1. 숫자 요약')
    P('')
    P('| 무엇 | 숫자 |')
    P('|---|---|')
    P('| 손대지 않은 칸(제미나이 판 = 옛 판) 모집단 | %d칸(본문 대사 11,691 중 제미나이가 바꾼 칸·정책 보류·성적 구간 %d칸 제외) |' % (POPJ['N'], POPJ['excluded'].get('adult_or_near_hold', 0) + POPJ['excluded'].get('broad_sexual_word', 0)))
    P('| 층화 무작위 표본 | 400칸(장 9 × 줄 종류 5 × 화자 8, 88층) → 검수자가 정책 보류로 뺀 3칸 제외 397칸 |')
    P('| 표본 확정 오류 | %d칸(major %d) — 검수자 A·B 합집합 16칸 중 사람 확인으로 1칸 기각 |' % (ADJ['confirmed'], ADJ['major']))
    P('| 표본 오류율 | minor 이상 %.1f%% [%.1f–%.1f] · major %.2f%% [Wilson %.2f–%.2f] · 포획-재포획 추정 실제 오류 %.1f±%.1f칸(%.1f%%) |' % (
        ADJ['rate_minor_strat'][0], ADJ['rate_minor_strat'][1], ADJ['rate_minor_strat'][2], ADJ['rate_major_wilson'][0], ADJ['rate_major_wilson'][1],
        ADJ['rate_major_wilson'][2], ADJ['chapman_N'], ADJ['chapman_se'], ADJ['rate_minor_capture_recapture']))
    P('| 부류 검출기 후보 → 확정(지적목록) | 아래 5절 표 — 확정 지적 **%d칸**(major %d) · I~III장 %d칸 |' % (len(FIND), len(maj), sum(1 for o in FIND if o['chap'] in SAFE_CH)))
    P('| 용어 일관 비율 | 음차 용어 %d종 %.2f%% · 번역어 %d종 %.2f%%(문맥 따라 정당한 변주 포함) |' % (len(tm), pct(t_ok, t_n), len(tb), pct(b_ok, b_n)))
    P('| 결함 심기 재현율(검수자) | A 52/53(98%) · B 48/53(91%) · 둘 중 하나라도 53/53 |')
    P('| 검수자 일치도 | A–B κ 0.30(오류 유무) · 0.67(major) · GPT: 꾸러미 준비됨, 판정 대기 |')
    P('| 음성 자막 | 음성 %d개 중 두 받아쓰기 갈림 %d개(뜻이 걸린 것 %d개) → 문맥으로 못 가린 것 1개(2300:215, 앞 검수의 그 칸) |' % (len(VC), len(split), len(sub_sp)))
    P('| 읽힘 시험 | 지금 줄에서 고칠 낱말에 걸림 %d/%d · 고친 안에서 걸림 %d/%d · 대조군 헛걸림 %d/%d · major %d칸 중 지금 줄 걸림 %d |' % (
        now_hit, n_read, fix_hit, n_read, ctrl['flag'], ctrl['n'], len(maj), maj_now))
    P('| 화면 넘침 | 고칠 안 %d칸 중 0(엔진 칸 규칙) |' % len(FIND))
    P('')
    open(os.path.join(OUT, '깊은검수_결과_머리.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    main()
