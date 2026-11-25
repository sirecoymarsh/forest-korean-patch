"""Forest 편의 기능 합본 교차 시험 (통합 세션, 2026-11-21).

네 모듈(화면·진행·아이콘 줄·4K 글자)을 한 DLL 로 합친 판을 통합 시험 사본에서 숨겨 띄우고,
큰 창(기본 2.35배)에서 서로 맞물리는 곳을 본다. 창은 present_test_shift_x 로 화면 밖, 확인 창도 밖, 소리는 세션 음소거.
입력은 PostMessage 만. 결과: OUT\\cross.json, OUT\\*.png, OUT\\run.log
"""
import ctypes, ctypes.wintypes as wt, json, os, sys, time, re, math
os.environ.setdefault("FOREST_GAME", r"Y:\AI\forest-qol-test\game")
os.environ.setdefault("FOREST_OUT", r"Y:\AI\claude-work\forest-qol-int\out")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fhost
from fhost import log, U, GAME, OUT

K = ctypes.WinDLL("kernel32", use_last_error=True)
K.OpenProcess.restype = ctypes.c_void_p
results = []


def check(name, cond, extra=""):
    results.append({"name": name, "ok": bool(cond), "extra": str(extra)})
    log(("PASS " if cond else "FAIL ") + name, extra)


class Mem:
    def __init__(self, pid):
        self.h = K.OpenProcess(0x10 | 0x400, False, pid)

    def u32(self, a):
        b = ctypes.create_string_buffer(4); n = ctypes.c_size_t()
        K.ReadProcessMemory(ctypes.c_void_p(self.h), ctypes.c_void_p(a), b, 4, ctypes.byref(n))
        return int.from_bytes(b.raw, "little")

    def sid(self):
        sc = self.u32(0x46639c)
        return (self.u32(sc + 0x3c) & 0xffff) if sc else -1


def client(h):
    r = wt.RECT(); U.GetClientRect(h, ctypes.byref(r)); return r.right, r.bottom


def to_phys(h, x, y):
    w, hh = client(h)
    if w * 600 <= hh * 800: cw, ch = w, (w * 600 + 400) // 800
    else: ch, cw = hh, (hh * 800 + 300) // 600
    ox, oy = (w - cw) // 2, (hh - ch) // 2
    return ox + math.floor((x + 0.5) * cw / 800), oy + math.floor((y + 0.5) * ch / 600)


def lclick(g, x, y, button="l"):
    X, Y = to_phys(g.h, x, y)
    g.click(X, Y, button=button)


class Tail:
    def __init__(self, g): self.g = g; self.n = len(g.events())
    def new(self):
        ev = self.g.events(); out = ev[self.n:]; self.n = len(ev); return out


def wait(g, fn, sec=10, step=0.2):
    t0 = time.time()
    while time.time() - t0 < sec:
        g.activate()
        if fn(): return True
        time.sleep(step)
    return False


def dialog(g):
    for h in fhost.windows_of(g.pid):
        if fhost.cls(h) == "#32770": return h
    return None


def answer_yes(g, sec=6):
    t0 = time.time()
    while time.time() - t0 < sec:
        g.activate(); d = dialog(g)
        if d:
            log("dialog:", fhost.title(d)); time.sleep(0.3); U.PostMessageW(d, 0x111, 6, 0); return True
        time.sleep(0.1)
    return False


def main():
    g = fhost.Game().launch()
    m = Mem(g.pid)
    tail = Tail(g)
    try:
        # 오프닝(약 62초)이 끝나 타이틀(대본 1)에서 기다릴 때까지
        ok = wait(g, lambda: m.sid() == 1 and m.u32(0x466418) == 1, 120, 0.5)
        check("title reached", ok, "sid=%d" % m.sid())
        time.sleep(1.5)
        w, hh = client(g.h)
        check("enlarged window by default", w > 800 and hh > 600, "%dx%d" % (w, hh))
        ev = "\n".join(g.events())
        for mod, want in (("present", "ok"), ("play", "ok"), ("buttons", "ok"), ("hitext", "ok"), ("hiart", "ok")):
            check("module %s %s" % (mod, want), "qol: %s %s" % (mod, want) in ev)
        g.shot("a_title")

        # Home 안내(타이틀)
        g.key(0x24); time.sleep(0.8); g.shot("b_guide_title")
        g.key(0x24); time.sleep(0.6)
        # 타이틀에서 S = 거절 알림
        tail.new(); g.key(ord("S")); time.sleep(0.5); g.shot("c_S_title")
        check("S refused at title", not any(re.search(r"S -> slot \d+ saved", l) for l in tail.new()))

        # L = 불러오기 화면 → 0번 칸 → 확인 「예」
        g.key(ord("L"))
        ok = wait(g, lambda: m.u32(0x466414) == 1, 8)
        check("L opens load screen at title", ok)
        time.sleep(0.8); g.shot("d_load_screen")
        lclick(g, 235, 168); answer_yes(g)
        ok = wait(g, lambda: m.sid() >= 2000 and m.u32(0x4663e8) == 1, 40)
        check("loaded slot 0 into a story line", ok, "sid=%d" % m.sid())
        time.sleep(1.0); g.shot("e_line_hitext")

        # 아이콘 줄: 자동 단추(늘린 창 좌표)
        tail.new()
        lclick(g, 678, 593)
        ok = wait(g, lambda: m.u32(0x466408) == 1, 5)
        lines = tail.new()
        check("auto button (scaled) -> auto on", ok)
        check("auto button went through play module", any("auto button -> play module" in l for l in lines), lines[-3:])
        time.sleep(1.5); g.shot("f_auto_x1")
        g.key(ord("A")); time.sleep(0.6); g.shot("f_auto_x2")
        # 자동이 몇 줄 스스로 넘기는지
        sc = m.u32(0x46639c); pc0 = m.u32(sc + 0x44)
        moved = wait(g, lambda: m.u32(m.u32(0x46639c) + 0x44) != pc0, 15)
        check("auto advances by itself (x2)", moved)
        g.key(0x08)  # Backspace
        ok = wait(g, lambda: m.u32(0x466408) == 0, 5)
        check("Backspace turns auto off", ok)
        wait(g, lambda: m.u32(0x4663e8) == 1, 15)
        time.sleep(0.6); g.shot("g_auto_off")

        # 지도 단추
        tail.new(); lclick(g, 661, 593)
        ok = wait(g, lambda: any("ui opened" in l for l in tail.new()), 8)
        check("map button (scaled) opens chart", ok)
        time.sleep(1.0); g.shot("h_chart")
        g.key(0x1B)
        ok = wait(g, lambda: any("AUDIT PASS" in l for l in g.events()[-8:]), 8)
        check("chart closed with AUDIT PASS", ok)
        time.sleep(0.8)

        # 오른쪽 클릭 = 설정 화면(지도 칸을 바꿨어도)
        lclick(g, 400, 300, button="r")
        ok = wait(g, lambda: m.u32(0x46640c) == 1, 6)
        check("right click still opens settings", ok)
        time.sleep(0.8); g.shot("i_settings")
        lclick(g, 400, 300, button="r")
        wait(g, lambda: m.u32(0x46640c) == 0, 6)
        wait(g, lambda: m.u32(0x4663e8) == 1, 10)

        # S = 바로 저장(알림)
        tail.new(); g.key(ord("S")); time.sleep(0.4); g.shot("j_S_toast")
        lines = tail.new()
        saved = [re.search(r"S -> slot (\d+) saved", l) for l in lines]
        slot = next((int(x.group(1)) for x in saved if x), None)
        check("S saves to a slot in story", slot is not None, lines[-3:])

        # 3배 창(창 메뉴) — 글자·겹그림이 따라오는지
        U.PostMessageW(g.h, 0x112, 0xEEF0, 0); time.sleep(1.2)
        w3, h3 = client(g.h)
        check("x3 window via system menu", w3 >= 2300, "%dx%d" % (w3, h3))
        g.key(ord("A")); time.sleep(1.2); g.shot("k_x3_auto")
        g.key(0x08); wait(g, lambda: m.u32(0x466408) == 0, 5)
        wait(g, lambda: m.u32(0x4663e8) == 1, 15); time.sleep(0.6); g.shot("k_x3_line")

        # 전체 화면(Alt+Enter) 왕복 — present_test_shift_x 로 옮긴 모니터 위
        U.PostMessageW(g.h, 0x104, 0x0D, 0x20000001); U.PostMessageW(g.h, 0x105, 0x0D, 0xE0000001)
        time.sleep(1.5); wf, hf = client(g.h)
        check("Alt+Enter fullscreen (no mode change)", (wf, hf) in ((4096, 2160), (3840, 2160), (1440, 2560)), "%dx%d" % (wf, hf))
        g.shot("l_full")
        U.PostMessageW(g.h, 0x104, 0x0D, 0x20000001); U.PostMessageW(g.h, 0x105, 0x0D, 0xE0000001)
        time.sleep(1.5); wb, hb = client(g.h)
        check("Alt+Enter back to window", (wb, hb) == (w3, h3), "%dx%d" % (wb, hb))

        # 아이콘 줄 자동 단추로 켜고 클릭으로 끄기(엔진 원래 길)
        lclick(g, 678, 593); ok1 = wait(g, lambda: m.u32(0x466408) == 1, 5)
        time.sleep(0.8); lclick(g, 400, 300); ok2 = wait(g, lambda: m.u32(0x466408) == 0, 5)
        check("auto via button then click off", ok1 and ok2)

        ev = g.events()
        errs = [l for l in ev if re.search(r"(?i)exception|AUDIT FAIL|failed|error", l)]
        check("no error lines in events.log", not errs, errs[-5:])
    finally:
        q = g.quit() if g.alive() else False
        check("normal quit (Yes on quit confirmation)", q)
        if g.alive(): g.kill()
        json.dump(results, open(OUT / "cross.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        log("RESULT %d/%d" % (sum(r["ok"] for r in results), len(results)))


if __name__ == "__main__":
    main()
