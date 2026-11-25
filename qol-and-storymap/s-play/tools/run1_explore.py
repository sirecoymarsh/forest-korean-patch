"""탐색 시험: 타이틀·안내·L·불러온 뒤 자동 켜기·클릭 끄기·지도 — 화면 자리 확인용"""
import sys, time
sys.path.insert(0, r"P:\AI\forest-qol\s-play\tools")
import fhost
from fhost import log

VK_HOME, VK_ESC, VK_BACK, VK_F8 = 0x24, 0x1B, 0x08, 0x77


def play_lines(g, start):
    ev = g.events()
    return [l for l in ev[start:] if " play" in l or "playtest" in l or "chart" in l.lower()]


def main():
    g = fhost.Game().launch()
    ev0 = len(g.events())
    try:
        s = g.wait_state(lambda s: s.get("stack") == "0001" and s.get("select") == "1", timeout=150, step=1.0, desc="title")
        log("title state", s)
        time.sleep(1.5)
        g.shot("t01_title")
        if g.user_touched(): raise SystemExit("user touched the game window")
        g.key(VK_HOME); time.sleep(0.8); g.shot("t02_guide_title")
        g.key(VK_ESC); time.sleep(0.6); g.shot("t03_after_guide")
        g.key(ord("S")); time.sleep(0.5); g.shot("t04_S_title")
        g.key(ord("L")); time.sleep(1.2); log("after L", g.state()); g.shot("t05_L_title")
        g.click(400, 300, button="r"); time.sleep(1.0); log("after rclick", g.state()); g.shot("t06_after_L")
        g.test(2, 1)
        s = g.wait_state(lambda s: s.get("clickwait") == "1" and s.get("stack", "").startswith("0110"), timeout=30, desc="loaded")
        log("loaded", s); time.sleep(0.5); g.shot("t07_loaded")
        if g.user_touched(): raise SystemExit("user touched the game window")
        g.key(ord("A")); time.sleep(0.6); log("auto on", g.state()); g.shot("t08_auto_on")
        for i in range(10):
            time.sleep(1.0); g.activate()
        g.shot("t09_auto_10s")
        g.key(ord("A")); time.sleep(0.4); g.shot("t10_x2")
        time.sleep(6)
        g.click(400, 300); time.sleep(0.6); s = g.state(); log("after click", s); g.shot("t11_clicked")
        time.sleep(2.0); s2 = g.state(); log("2s later (should be same pc)", s2)
        g.key(VK_HOME); time.sleep(0.8); g.shot("t12_guide_story")
        g.click(300, 300); time.sleep(0.6); g.shot("t13_guide_closed"); log("after guide close", g.state())
        g.key(ord("L")); time.sleep(1.2); log("L story", g.state()); g.shot("t14_L_story")
        g.click(400, 300, button="r"); time.sleep(1.0); log("closed", g.state())
        g.key(VK_F8); time.sleep(2.0); log("F8", g.state()); g.shot("t15_chart")
        g.key(VK_ESC); time.sleep(1.2); log("chart closed", g.state()); g.shot("t16_after_chart")
    finally:
        for l in play_lines(g, ev0): log("EV", l)
        ok = g.quit()
        if not ok: g.kill()
        log("moved windows", g.keeper.moved if g.keeper else None, "muted", g.keeper.muted if g.keeper else None)


if __name__ == "__main__":
    main()
