# -*- coding: utf-8 -*-
"""되감기 충실도·지연 시험(몰이 drv.py 사용).

처음부터 N 걸음 읽으며 멈춘 자리마다 그림을 떠 두고, 되감기(1걸음·여러 걸음·끝까지)와 다시 읽기를 섞어
① 되돌아간 화면이 처음 지날 때와 같은지(화소) ② 엔진 상태가 같은지(시험 모듈의 verify 줄) ③ 걸린 시간 ④ 정상 종료.
노란 자막이 있던 자리·곡이 바뀌는 자리·되풀이 효과음 자리로는 일부러 찾아가 본다.
사용: python -I t5_fidelity.py <출력 이름> [걸음 수] [마구잡이 횟수]"""
import os, random, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drv

NAME = sys.argv[1] if len(sys.argv) > 1 else 't5'
N = int(sys.argv[2]) if len(sys.argv) > 2 else 120
R = int(sys.argv[3]) if len(sys.argv) > 3 else 40
SETTLE = float(sys.argv[4]) if len(sys.argv) > 4 else 0.45     # 큰 창 + 4배 그림은 뒤 스레드 합성을 기다리려고 길게(1.6 쯤)
r = drv.Run(NAME, settle=SETTLE); g = r.g
ok = False
try:
    r.start_new_game()
    r.first_pass(N, save_every=40)
    first = list(r.stops)                      # 처음 읽을 때의 멈춘 자리들(차례대로)
    pos = len(first) - 1                       # 지금 자리(first 안의 번호)

    def goto(i, tag):
        """first[i] 자리로: 뒤면 되감고, 앞이면 읽어 간다."""
        global pos
        if i < pos:
            b = r.back(pos - i, tag)
            if b: pos = i
            return b
        if i > pos:
            r.fwd(i - pos, tag); pos = i
        return None

    r.back(1, 'one'); pos -= 1
    r.back(1, 'one-again'); pos -= 1
    r.back(5, 'five'); pos -= 5
    r.fwd(7, 'reread'); pos += 7
    r.back(20, 'twenty'); pos -= 20
    r.fwd(3, 'reread20'); pos += 3
    # 일부러 찾아가기: 자막 자리, 곡이 바뀐 바로 뒤 자리, 되풀이 효과음 자리
    subs = [i for i, s in enumerate(first) if s['sub']]
    bgmch = [i for i in range(1, len(first)) if first[i]['bgm'] != first[i - 1]['bgm']]
    loops = [i for i, s in enumerate(first) if s['loop']]
    r.L('targets: subtitle stops', len(subs), 'bgm changes', len(bgmch), 'se-loop stops', len(loops))
    for i in (subs[-3:] + subs[:3]):
        goto(i + 1, 'past-sub%d' % i)          # 자막 다음 자리에 섰다가
        b = goto(i, 'onto-sub%d' % i)          # 한 걸음 뒤로 = 자막 자리
    for i in bgmch[-4:]:
        goto(i, 'at-bgm%d' % i)
        goto(i - 1, 'before-bgm%d' % i)        # 곡이 바뀌기 전 자리로 한 걸음
        goto(i, 'again-bgm%d' % i)
    for i in loops[:4]:
        goto(i + 2 if i + 2 < len(first) else i, 'past-loop%d' % i)
        goto(i, 'onto-loop%d' % i)
    # 마구잡이
    rnd = random.Random(1125)
    for t in range(R):
        if rnd.random() < 0.6:
            k = rnd.choice([1, 1, 1, 2, 3, 4, 8, 15])
            b = r.back(k, 'rand%02d' % t)
            if b: pos = max(0, pos - k)
        else:
            k = min(rnd.choice([1, 1, 2, 3]), len(first) - 1 - pos)
            if k > 0: r.fwd(k, 'rand%02d' % t); pos += k
    # 맨 처음까지, 그보다 더는 거절
    r.back(1000, 'all-the-way'); pos = 0
    r.L('at oldest stop', g.state())
    r.back(1, 'beyond-oldest', compare=False)
    r.fwd(4, 'reread-from-start'); pos += 4
    ok = True
finally:
    try:
        r.summary(ok)
    finally:
        r.finish(ok)
