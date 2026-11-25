# -*- coding: utf-8 -*-
"""4K 글자 숨긴 시험 한 판. 게임이 guard 로 떠 있고(3배 시험 화면 판) 타이틀 이후일 때.
  python -I scenario.py OUTDIR
A: 1번 칸(3011) — 대사·찍히는 중·다음 쪽·숨기기·앞 쪽·설정·세이브 화면·지도·F11 켜고 끄기·배율 바꾸기
B: 5번 칸(1020 → II장 첫머리) — 노란 자막·장면 전환
단계마다 비교 그림(위 = 1배를 늘린 것, 아래 = 4K 글자)과 수치를 OUTDIR 에 남기고, 끝에 흐린 1배 글자 남음 검사를 한다."""
import os, sys, time, struct, json
OUT = sys.argv[1] if len(sys.argv) > 1 else r'Y:\AI\claude-work\hitext\run'
os.environ['HCAP_OUT'] = OUT
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ftest, hcap, remnant
import numpy as np

ftest.SCALE = 3
results = []


def cap(name, **kw):
    r = hcap.cap(name, **kw); r['state'] = {k: ftest.state()[k] for k in ('hide', 'settings', 'system', 'wait2')}; r['sid'] = sid()
    results.append(r); print(json.dumps(r, ensure_ascii=False), flush=True); return r


def sid():
    m = hcap.mem(); sc = m.u32(0x46639c)
    return struct.unpack('<H', m.read(sc + 0x3c, 2))[0] if sc else None


def yellow_pixels():
    F = hcap.front()
    reg = F[30:260, 150:700].astype(int)
    return int(((reg[:, :, 0] > 200) & (reg[:, :, 1] > 170) & (reg[:, :, 2] < 90)).sum())


def advance(wait=8):
    ftest.click(400, 300); return hcap.wait_text(wait)


def part_a():
    hcap.wait_text(); time.sleep(0.4)
    cap('a01_dialog', note='대사')
    ftest.click(400, 300)
    for k in range(10):
        hcap.snap('a02_typing_%d' % k, note='찍히는 중')
    print('typing snaps', hcap.flush(), flush=True)
    hcap.wait_text(); time.sleep(0.3); cap('a03_page', note='다음 쪽')
    ftest.key('SHIFT'); time.sleep(0.8); cap('a04_hidden', note='Shift 숨김')
    ftest.key('SHIFT'); time.sleep(0.8); cap('a05_unhidden', note='다시 보임')
    ftest.key('UP'); time.sleep(0.8); cap('a06_backlog1', note='앞 쪽 ↑')
    ftest.key('UP'); time.sleep(0.8); cap('a07_backlog2', note='앞 쪽 ↑↑')
    ftest.key('DOWN'); time.sleep(0.5); ftest.key('DOWN'); time.sleep(0.8); cap('a08_back', note='↓↓ 돌아옴')
    ftest.rclick(400, 300); time.sleep(1.2); cap('a09_settings', crop=(0, 0, 800, 600), note='설정 화면')
    ftest.click(340, 445); time.sleep(1.5); cap('a10_save', crop=(100, 130, 680, 470), note='세이브 화면')
    ftest.move(560, 230); time.sleep(0.8); cap('a11_save_hover', crop=(100, 130, 680, 470), note='칸 위 마우스')
    ftest.rclick(400, 300); time.sleep(1.2); ftest.rclick(400, 300); time.sleep(1.2); cap('a12_after_save', note='세이브·설정 닫음')
    hcap.wait_text(); ftest.key('F8'); time.sleep(2.5); cap('a13_chart', crop=(0, 0, 800, 600), note='지도')
    ftest.key('ESC'); time.sleep(2.0); cap('a14_after_chart', note='지도 닫음')
    ftest.key('F11'); time.sleep(0.8); cap('a15_off', note='F11 끔(원래 그리기)')
    ftest.key('F11'); time.sleep(0.8); cap('a16_on', note='F11 켬')
    # 배율 바꾸기 3 → 2 → 1 → 3
    ftest.key('F12'); time.sleep(1.5); ftest.SCALE = 2; cap('a17_scale2', note='2배로 바꿈')
    ftest.key('F12'); time.sleep(1.5); ftest.SCALE = 1; cap('a18_scale1', note='1배(원작)')
    ftest.key('F12'); time.sleep(1.5); ftest.SCALE = 3; cap('a19_scale3', note='다시 3배')
    advance(); time.sleep(0.3); cap('a20_after_scale', note='바꾼 뒤 다음 쪽')


def load_slot_from_settings(slot):
    ftest.rclick(400, 300); time.sleep(1.2)
    ftest.click(470, 445); time.sleep(1.5)   # 불러오기
    for _ in range(10): ftest.click(578, 552); time.sleep(0.3)
    for _ in range(slot // 10): ftest.click(655, 552); time.sleep(0.3)
    k = slot % 10
    ftest.click(235 if k < 5 else 550, 165 + (k % 5) * 66); time.sleep(0.8)
    pid = ftest.find_pid()
    for _ in range(20):   # 「Loading save data. Is this okay?」 → 예
        dl = [w for w in ftest.windows(pid) if ftest.cls(w) == '#32770']
        if dl: ftest.post(dl[0], 0x111, 6, 0); break
        time.sleep(0.2)
    time.sleep(2.0)
    return True


def part_b():
    ok = load_slot_from_settings(5)
    print('loaded slot 5', ok, 'sid', sid(), flush=True)
    cap('b00_slot5', note='5번 칸')
    seen_sub = 0; last = sid()
    for i in range(80):
        st = ftest.state()
        if st['settings']: ftest.rclick(400, 300); time.sleep(1.0); continue
        ftest.click(400, 300)
        # 장면 전환을 잡으려고 바로 몇 장
        for k in range(4):
            time.sleep(0.12)
            if sid() != last:
                cap('b%02d_trans_%d' % (i, k), crop=(0, 0, 800, 600), note='장면 전환 %s→%s' % (last, sid()))
        ok = hcap.wait_text(10)
        st = ftest.state()
        y = yellow_pixels() if not (st['settings'] or st['system']) else 0
        if y > 40:
            seen_sub += 1
            cap('b%02d_subtitle' % i, crop=(150, 40, 700, 220), note='노란 자막')
            if seen_sub >= 3: break
        if sid() != last:
            cap('b%02d_newscene' % i, crop=(0, 0, 800, 600), note='새 장면 %s' % sid()); last = sid()
        if not ok:
            print('no text wait', i, {k: st[k] for k in ('system', 'settings', 'hide', 'auto')}, flush=True)
    print('subtitles seen', seen_sub, flush=True)


if __name__ == '__main__':
    part_a()
    if os.environ.get('PART', 'AB') == 'AB': part_b()
    files = sorted(f for f in os.listdir(OUT) if f.endswith('_win.png'))
    bad = []
    for f in files:
        n = os.path.join(OUT, f[:-8])
        if not os.path.exists(n + '_engine1x.png'): continue
        im = hcap.Image.open(n + '_win.png')
        k = im.size[0] // 800
        if k < 2: continue
        s = remnant.check(n + '_win.png', n + '_engine1x.png', k=k)
        if s: bad.append((f, s[:4]))
    print('remnant frames', len(bad), 'of', len(files))
    for b in bad: print('  ', b)
    print('log:', '\n'.join(hcap.log_tail(3)))
    json.dump(results, open(os.path.join(OUT, 'results.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
