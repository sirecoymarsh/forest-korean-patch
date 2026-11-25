"""선택 뒤 자동 계속만 따로: 세이브 4(2300@10890)에서 자동 ×5 로 선택지까지 → 고르기 → 자동이 다시 켜지는지"""
import json, os, re, sys, time
sys.path.insert(0, r"P:\AI\forest-qol\s-play\tools")
os.environ.setdefault("FOREST_OUT", "Y:\\AI\\forest-qol-test-play\\out\\" + os.environ.get("RUN_NAME", "run5"))
import fhost
from fhost import log
from run2_full import launch_retry, EvTail, load, check, R, wait_lines, VK_DOWN, VK_RET, VK_BACK


def main():
    g = launch_retry()
    tail = EvTail(g)
    try:
        g.wait_state(lambda s: s.get("stack") == "0001" and s.get("select") == "1", timeout=150, step=1.0, desc="title")
        time.sleep(1.0)
        load(g, 4, "slot4"); time.sleep(0.6); tail.new()
        for _ in range(5): g.key(ord("A")); time.sleep(0.3)
        s = g.wait_state(lambda s: s.get("choice") == "1", timeout=240, step=1.0, desc="reach choice by auto")
        time.sleep(1.0); g.shot("f01_choice")
        depths = []
        for _ in range(6):
            st = g.state(); depths.append((st.get("stack"), st.get("pc"))); time.sleep(0.3)
        log("during choice stack/pc samples", depths)
        g.key(ord("A")); time.sleep(0.7); g.shot("f02_A_at_choice")
        for l in tail.new(): log("EV", l)
        g.key(VK_DOWN); time.sleep(0.4); g.key(VK_RET); time.sleep(1.5)
        ev = wait_lines(tail, r"auto resumed after choice|choice memory dropped", 1, 15)
        s = g.state(); g.shot("f03_after_choice")
        check("auto_resumes_after_choice", ev and "resumed" in ev[0] and "x5" in ev[0] and s.get("auto") == "1", {"ev": ev, "auto": s.get("auto"), "bar_hidden": s.get("bar_hidden")})
        p0 = s.get("pc"); time.sleep(6.0); s2 = g.state(); g.shot("f04_auto_after_choice")
        check("auto_keeps_going_after_choice", p0 != s2.get("pc") and s2.get("auto") == "1", {"pc": [p0, s2.get("pc")], "auto": s2.get("auto")})
        g.key(VK_BACK); time.sleep(0.6)
    finally:
        for l in tail.new(): log("EV", l)
        ok = g.quit()
        R["normal_quit"] = {"pass": bool(ok), "why": "quit dialog yes"}
        if not ok: g.kill()
        with open(fhost.OUT / "result.json", "w", encoding="utf-8") as f: json.dump(R, f, ensure_ascii=False, indent=1)
        log("RESULT", sum(1 for v in R.values() if v["pass"]), "/", len(R))


if __name__ == "__main__":
    main()
