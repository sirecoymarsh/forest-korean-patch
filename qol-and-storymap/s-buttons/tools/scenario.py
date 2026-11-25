# -*- coding: utf-8 -*-
"""아이콘 줄 시험 한 판(게임이 guard 로 떠 있고 1번 칸을 불러 대사 대기 중일 때).
  python -I scenario.py OUTDIR
단계마다 상태·로그를 찍고 그림을 OUTDIR 에 남긴다. 실패해도 다음 단계로 간다(끝에 요약)."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ftest
import numpy as np
from PIL import Image

OUT = sys.argv[1] if len(sys.argv) > 1 else r'Y:\AI\fq_shots\run'
os.makedirs(OUT, exist_ok=True)
X0, Y0 = 600, 582                     # compane 캔버스 원점(화면)
MAP = (X0 + 54 + 7, Y0 + 2 + 9)       # 아이콘 가운데(판정이 2줄 아래로 밀린 것 감안해 +9)
AUTO = (X0 + 71 + 7, Y0 + 2 + 9)
results = []


def ok(name, cond, extra=''):
    results.append((name, bool(cond), extra))
    print(('PASS ' if cond else 'FAIL ') + name + ('  ' + extra if extra else ''), flush=True)


def st():
    return ftest.state()


def logtail(n=400):
    p = os.path.join(ftest.GAME, 'forest-chart-progress', 'events.log')
    with open(p, 'rb') as f:
        return f.read().decode('utf-8', 'replace').splitlines()[-n:]


def log_since(mark):
    lines = logtail(2000)
    return lines[mark:] if mark <= len(lines) else []


def log_mark():
    return len(logtail(2000))


def shot(name):
    return ftest.shot(os.path.join(OUT, name + '.png'))


def row_visible(im):
    a = np.array(im).astype(int)[Y0 + 2:Y0 + 16, X0 + 88:X0 + 187]     # ⇑~숨김 자리
    return (a.max(-1) > 120).sum()


def text_of(m):
    """스크립트 커서(대사가 바뀌었는지 보려고)."""
    sc = m.u32(0x46639c)
    return m.u32(sc + 0x44) if sc else None


def wait_until(fn, sec=6.0, step=0.2):
    t = time.time()
    while time.time() - t < sec:
        ftest.act()
        if fn():
            return True
        time.sleep(step)
    return False


m = ftest.Mem()
h = ftest.main_window()
ftest.act(h)
ftest.move(400, 300); time.sleep(0.4)

# 1. 평소 줄 / 단추 콜백
s = st()
ok('wait for text', s['wait2'] == 1, str(s))
ok('callbacks are ours', s['slot_auto'] not in ('0x4166d0',) and s['slot_menu'] not in ('0x4166c0',), s['slot_auto'] + ' ' + s['slot_menu'])
ok('slider uses shrunk slide_lev', s.get('slider', (0, 0, 0, 0))[2] == 41 and s['slider'][3] == 37, str(s.get('slider')))
im = shot('s01_normal')
ok('row visible', row_visible(im) > 40, str(row_visible(im)))

# 2. 판정 칸: 새 단추 14×14 전체. 엔진은 층 알파를 2줄 아래로 밀어 본다(원래 ⇑ 도 같다) → 캔버스 y 4..17
for off, x, name in [(0x7c, X0 + 54, 'map'), (0x78, X0 + 71, 'auto')]:
    hits = 0
    for ly in range(4, 18, 2):
        for lx in range(0, 14, 2):
            ftest.post(h, 0x200, 0, ftest.L(x + lx, Y0 + ly)); time.sleep(0.04)
            hits += 1 if m.u32(m.u32(m.u32(0x46630c) + off) + 0xb0) else 0
    ok('hit area %s' % name, hits == 49, '%d/49' % hits)
ftest.post(h, 0x200, 0, ftest.L(400, 300)); time.sleep(0.3)

# 3. 마우스 올림 그림
ftest.move(*MAP); time.sleep(0.6); shot('s02_hover_map')
ftest.move(*AUTO); time.sleep(0.6); shot('s03_hover_auto')
ftest.move(400, 300); time.sleep(0.4)

# 4. 오른쪽 클릭 → 원작 설정 화면
mk = log_mark()
ftest.rclick(400, 300)
opened = wait_until(lambda: m.u32(0x46640c) == 1, 4)
time.sleep(0.6); im = shot('s04_rclick_settings')
lg = log_since(mk)
ok('right click opens settings', opened, 'settings=%s' % m.u32(0x46640c))
ok('right click logged as settings', any('right click -> settings' in l for l in lg), ' | '.join(lg[-3:]))
ok('no chart on right click', not any('chart' in l for l in lg))
ok('row hidden under settings', row_visible(im) < 10, str(row_visible(im)))
ftest.rclick(400, 300)
closed = wait_until(lambda: m.u32(0x46640c) == 0, 4)
ok('settings closed by right click', closed)
time.sleep(0.8)
im = shot('s05_after_settings')
ok('row back after settings', row_visible(im) > 40, str(row_visible(im)))

# 5. 지도 단추 → 지도 열림 → ESC 로 닫힘 → 게임 계속
wait_until(lambda: m.u32(0x4663e8) == 1, 4)
mk = log_mark()
ftest.click(*MAP)
chart = wait_until(lambda: any('ui opened' in l for l in log_since(mk)), 6)
time.sleep(1.0); shot('s06_chart')
lg = log_since(mk)
ok('map button logged', any('map button -> chart' in l for l in lg), ' | '.join(lg[-4:]))
ok('chart opened', chart)
ok('settings not opened by map button', m.u32(0x46640c) == 0)
ftest.key('ESC')
resumed = wait_until(lambda: any('script resumed' in l for l in log_since(mk)), 6)
lg = log_since(mk)
ok('chart closed and script resumed', resumed, ' | '.join(lg[-3:]))
ok('chart audit pass', any('AUDIT PASS' in l for l in lg))
time.sleep(0.8)
c0 = text_of(m)
ftest.click(400, 300)
adv = wait_until(lambda: text_of(m) != c0, 6)
ok('game continues after chart (click advances)', adv, '%s -> %s' % (c0, text_of(m)))
wait_until(lambda: m.u32(0x4663e8) == 1, 6)
im = shot('s07_after_chart')
ok('row visible after chart', row_visible(im) > 40)

# 6. 자동 단추 → (진행 모듈이 빈 판이라) 엔진 자동 → 대사가 저절로 넘어감 → 클릭으로 끔
mk = log_mark()
c0 = text_of(m)
ftest.click(*AUTO)
on = wait_until(lambda: m.u32(0x466408) == 1, 3)
time.sleep(0.5); im = shot('s08_auto_on')
lg = log_since(mk)
ok('auto button turns auto on', on, 'auto=%s' % m.u32(0x466408))
ok('auto button logged', any('auto button ->' in l for l in lg), ' | '.join(lg[-2:]))
ok('row hidden during auto (original behaviour)', row_visible(im) < 10, str(row_visible(im)))
moved = wait_until(lambda: text_of(m) != c0, 12)
ok('auto advances text by itself', moved)
ftest.click(400, 300)
off = wait_until(lambda: m.u32(0x466408) == 0, 4)
ok('click turns auto off', off)
wait_until(lambda: m.u32(0x4663e8) == 1, 8)
time.sleep(0.5); im = shot('s09_auto_off')
ok('row back after auto off', row_visible(im) > 40, str(row_visible(im)))

# 7. 대화창 숨기기(Shift) — 새 단추도 같이 숨는지
ftest.key('SHIFT')
hid = wait_until(lambda: m.u32(0x466420) == 1, 3)
time.sleep(0.5); im = shot('s10_shift_hidden')
a = np.array(im).astype(int)[Y0 + 2:Y0 + 16, X0 + 54:X0 + 85]
ok('shift hides window', hid)
ok('new buttons hidden too', (a.max(-1) > 120).sum() < 4, str((a.max(-1) > 120).sum()))
ftest.key('SHIFT')
wait_until(lambda: m.u32(0x466420) == 0, 3)
time.sleep(0.5); im = shot('s11_shift_back')
ok('shift brings row back', row_visible(im) > 40)

# 8. 글자 속도 슬라이더: 손잡이를 왼쪽 끝 → 오른쪽 끝
sl = m.u32(m.u32(0x46630c) + 0x60)
v0 = m.u32(sl + 0x38)
knob = X0 + 3 + round(v0 * 37 / 255) + 2
ftest.drag(knob, Y0 + 9, X0 - 20, Y0 + 9)
time.sleep(0.5); v_left = m.u32(sl + 0x38); shot('s12_slider_left')
ftest.drag(X0 + 5, Y0 + 9, X0 + 60, Y0 + 9)
time.sleep(0.5); v_right = m.u32(sl + 0x38); shot('s13_slider_right')
ftest.drag(X0 + 43, Y0 + 9, X0 + 3 + 18 + 2, Y0 + 9)
time.sleep(0.5); v_mid = m.u32(sl + 0x38)
ok('slider reaches 0 at left end', v_left == 0, 'start %s left %s' % (v0, v_left))
ok('slider reaches 255 at right end', v_right == 255, 'right %s' % v_right)
ok('slider middle', 100 <= (v_mid or 0) <= 160, 'mid %s' % v_mid)
ftest.drag(X0 + 3 + 20, Y0 + 9, X0 + 60, Y0 + 9)        # 원래 값(끝)으로 되돌림
time.sleep(0.5)
ok('slider restored', m.u32(sl + 0x38) == v0, '%s' % m.u32(sl + 0x38))

print('\nSUMMARY %d/%d pass' % (sum(1 for r in results if r[1]), len(results)))
for r in results:
    if not r[1]:
        print('  FAIL', r[0], r[2])
