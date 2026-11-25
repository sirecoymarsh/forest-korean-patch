# -*- coding: utf-8 -*-
"""실행 중 객체 주소 엿보기(정적 분석 확인용): 소리 채널 객체의 vtable, 층 객체의 문맥 기록 포인터, 대화창 상태 포인터."""
import os, sys, time, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rw

g = rw.Game(r'Y:\AI\forest-qol-test-rewind\out\t0')
try:
    assert g.wait_title()
    time.sleep(0.5)
    g.click(607, 286)
    g.wait(lambda z: z['choice'] == 1, 30)
    eng = g.u32(0x466398)
    g.L('engine obj %08x' % eng)
    for ch in range(4):
        o = g.u32(eng + 0x1ac + ch * 4)
        vt = g.u32(o) if o else 0
        g.L(' channel %d obj %08x vtable %08x' % (ch, o, vt), [('%08x' % g.u32(vt + 4 * i)) for i in range(12)] if vt else '')
    mgr = g.u32(eng + 0x1a8)
    g.L(' bgm mgr %08x: players %08x %08x idx %d track %d' % (mgr, g.u32(mgr + 4), g.u32(mgr + 8), g.u32(mgr + 0xc), g.u32(mgr + 0x10)))
    for i in (0, 1):
        o = g.u32(mgr + 4 + 4 * i); vt = g.u32(o) if o else 0
        g.L(' bgm player %d obj %08x vtable %08x' % (i, o, vt), [('%08x' % g.u32(vt + 4 * k)) for k in range(12)] if vt else '')
    recs = []
    for i in range(50):
        lay = g.u32(0x466238 + 4 * i)
        rec = g.u32(lay + 0x288) if lay else 0
        recs.append(rec)
    g.L(' layer records:', ' '.join('%x' % r for r in recs[:6]), '...', '%x' % recs[49], 'step', sorted(set(recs[i + 1] - recs[i] for i in range(49))))
    mw = g.u32(0x46630c)
    g.L(' msgwin %08x state ptr %08x style ptr %08x view %d viewing %d' % (mw, g.u32(mw + 0xa4), g.u32(mw + 0xa8), g.u32(mw + 0x2c6c), g.u32(mw + 0x2c70)))
    for p in range(0x466204, 0x466238, 4):
        g.L('  obj [%x] = %08x' % (p, g.u32(p)))
finally:
    g.L('quit', g.quit() if g.alive() and g.h else False)
    g.close()
