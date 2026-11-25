# -*- coding: utf-8 -*-
"""배경으로 도는 시험 묶음(final_pass.sh)이 끝날 때까지 기다린다. 한 번에 9분 남짓만 기다리고 DONE 또는 NOT YET 을 찍는다.
사용: python -I wait_pass.py <묶음의 출력 파일>      (NOT YET 이면 다시 돌린다)"""
import io, sys, time

path = sys.argv[1]
t0 = time.time()
while time.time() - t0 < 555:
    try:
        s = io.open(path, encoding='utf-8', errors='replace').read()
    except OSError:
        s = ''
    if '##### done' in s:
        print('DONE'); sys.exit(0)
    time.sleep(15)
last = [l for l in s.splitlines() if l.startswith('=== ')]
print('NOT YET - last started:', last[-1] if last else '(nothing)')
