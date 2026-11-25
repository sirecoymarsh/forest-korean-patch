# -*- coding: utf-8 -*-
"""게임이 guard 로 떠 있을 때: 타이틀까지 기다린 뒤(활성 알림을 보내며) 「이어하기」→ 쪽 → 칸을 눌러 불러온다.
  python -I boot.py SLOT        (SLOT 0~99)
대사 대기(wait2=1)까지 기다리고 끝난다."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ftest

slot = int(sys.argv[1]) if len(sys.argv) > 1 else 1


def wait_window(sec=30):
    t = time.time()
    while time.time() - t < sec:
        if ftest.find_pid():
            try:
                return ftest.main_window()
            except SystemExit:
                pass
        time.sleep(0.5)
    raise SystemExit('no window')


def script_pc(m):
    sc = m.u32(0x46639c)
    if not sc:
        return None, None
    base = m.u32(sc); cur = m.u32(sc + 0x44)
    sid = m.read(sc + 0x3c, 2)
    return (int.from_bytes(sid, 'little') if sid else None), (cur - base if cur and base else None)


h = wait_window()
m = ftest.Mem()
t0 = time.time()
while True:
    ftest.act(h)
    sid, pc = script_pc(m)
    if sid == 1 and pc is not None and 488 <= pc <= 498:
        break
    if time.time() - t0 > 150:
        raise SystemExit('title timeout sid=%s pc=%s' % (sid, pc))
    time.sleep(1.0)
print('title after %.0fs' % (time.time() - t0), flush=True)
time.sleep(1.0)
ftest.click(605, 325)                 # 이어하기
time.sleep(2.0)
page = slot // 10
# 화면은 마지막으로 본 쪽을 기억한다 → 왼쪽 화살표로 1쪽까지 간 뒤 오른쪽으로
for _ in range(10):
    ftest.click(578, 552); time.sleep(0.35)
for _ in range(page):
    ftest.click(655, 552); time.sleep(0.35)
k = slot % 10
x = 235 if k < 5 else 550
y = 165 + (k % 5) * 66
time.sleep(0.6)
ftest.click(x, y)
t1 = time.time()
while time.time() - t1 < 20:
    ftest.act(h)
    if m.u32(0x4663e8) == 1:
        print('loaded slot %d, waiting for click' % slot); break
    time.sleep(0.5)
else:
    print('no text wait after load')
