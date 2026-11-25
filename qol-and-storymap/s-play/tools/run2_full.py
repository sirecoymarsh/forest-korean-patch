"""진행 모듈 전체 시험(숨김·무음). 결과는 out\\run2\\ 의 그림과 run2_result.json.
순서: 타이틀(안내·S 거절·L) → Ctrl 읽음 보호 → 자동 대기·배율 → 클릭·Backspace 끄기 → 음성 대기 중 끄기
      → 선택 뒤 자동 계속 → S 저장·불러오기 → 안내(입력 막기·셈 멈춤) → 다녀온 뒤(지도·설정·숨기기·자동 중 F8/오른쪽 클릭) → 정상 종료
"""
import json, os, re, sys, time
sys.path.insert(0, r"P:\AI\forest-qol\s-play\tools")
os.environ.setdefault("FOREST_OUT", "Y:\\AI\\forest-qol-test-play\\out\\" + os.environ.get("RUN_NAME", "run2"))
import fhost
from fhost import log

VK_HOME, VK_ESC, VK_BACK, VK_F8, VK_CTRL, VK_SHIFT, VK_DOWN, VK_UP, VK_RET = 0x24, 0x1B, 0x08, 0x77, 0x11, 0x10, 0x28, 0x26, 0x0D
R = {}   # 시험 이름 -> (통과, 근거)


def check(name, ok, why):
    R[name] = {"pass": bool(ok), "why": why}
    log(("PASS " if ok else "FAIL ") + name + " :: " + str(why))


class EvTail:
    def __init__(self, g):
        self.g = g
        self.n = len(g.events())

    def new(self):
        ev = self.g.events()
        out = ev[self.n:]
        self.n = len(ev)
        return [l for l in out if " play" in l or "playtest" in l or "AUDIT" in l or "chart" in l.lower() or "save" in l or "load" in l]


def guard(g):
    if g.user_touched():
        raise SystemExit("user touched the game window — stopping automation")


def load(g, slot, desc):
    g.test(2, slot)
    s = g.wait_state(lambda s: s.get("clickwait") == "1" and s.get("stack", "").startswith("0110") and s.get("choice") == "0", timeout=30, desc=desc)
    return s


def at_choice(g, slot):
    g.test(2, slot)
    return g.wait_state(lambda s: s.get("choice") == "1", timeout=30, desc="choice")


def wait_lines(tail, pat, count, timeout):
    got, t0 = [], time.time()
    while time.time() - t0 < timeout and len(got) < count:
        for l in tail.new():
            log("EV", l)
            if re.search(pat, l):
                got.append(l)
        time.sleep(0.1)
    return got


def launch_retry():
    for i in range(8):
        try:
            return fhost.Game().launch()
        except RuntimeError as e:
            log("launch failed:", e, "- retry in 30s")
            time.sleep(30)
    raise RuntimeError("could not launch")


def main():
    g = launch_retry()
    tail = EvTail(g)
    try:
        # ---------------------------------------------------------------- 타이틀
        s = g.wait_state(lambda s: s.get("stack") == "0001" and s.get("select") == "1", timeout=150, step=1.0, desc="title")
        time.sleep(1.5); guard(g)
        g.key(VK_HOME); time.sleep(0.8); g.shot("a01_guide_title")
        g.key(VK_ESC); time.sleep(0.6)
        ev = tail.new(); [log("EV", l) for l in ev]
        check("guide_title_open_close", any("key guide open" in l for l in ev) and any("key guide closed" in l for l in ev), ev[-3:])
        g.key(ord("S")); time.sleep(0.5); g.shot("a02_S_title")
        ev = tail.new(); check("S_refused_at_title", any("S refused" in l for l in ev), ev)
        g.key(ord("L")); time.sleep(1.3); s1 = g.state(); g.shot("a03_L_title")
        g.click(400, 300, button="r"); time.sleep(1.2); s2 = g.state()
        check("L_title_opens_load_screen", s1.get("loadscr") == "1" and s2.get("loadscr") == "0" and s2.get("stack") == "0001",
              {"open": s1.get("loadscr"), "after": s2.get("loadscr"), "stack": s2.get("stack")})
        tail.new()

        # ---------------------------------------------------------------- Ctrl 읽음 보호(3011 슬롯 9~19 를 안 읽음으로 해 둠)
        g.test(3, 0)   # 건너뛰기 범위 = 읽은 부분만
        s = load(g, 1, "slot1"); log("slot1", s); time.sleep(0.5); guard(g)
        pc0 = int(s.get("pc", 0))
        g.activate(); g.keydown(VK_CTRL)
        t0 = time.time()
        while time.time() - t0 < 5.0:
            time.sleep(0.04); g.keydown(VK_CTRL, repeat=True)
            if int(time.time() * 4) % 4 == 0: g.activate()
        s = g.state(); g.shot("b01_ctrl_stopped")
        ev = tail.new(); [log("EV", l) for l in ev]
        stop = [l for l in ev if "ctrl skip stopped" in l]
        check("ctrl_stops_at_unread", len(stop) == 1 and "3011:9" in stop[0] and s.get("clickwait") == "1" and s.get("ctrlskip") == "0",
              {"stops": stop, "pc": s.get("pc"), "from_pc": pc0})
        g.keyup(VK_CTRL); time.sleep(0.3)
        pc_stop = s.get("pc")
        time.sleep(1.0); s = g.state()
        check("ctrl_repeat_swallowed", s.get("pc") == pc_stop, {"pc_after_release": s.get("pc"), "pc_at_stop": pc_stop})
        # 다시 누르면 한 줄(안 읽은 줄) 넘어가고 다시 멈춤
        g.activate(); g.keydown(VK_CTRL); time.sleep(0.15)
        for _ in range(20): time.sleep(0.04); g.keydown(VK_CTRL, repeat=True)
        g.keyup(VK_CTRL); time.sleep(0.6)
        ev = tail.new(); [log("EV", l) for l in ev]
        check("ctrl_again_one_line", any("3011:10" in l for l in ev), [l for l in ev if "ctrl" in l])
        # 「안 읽은 부분도」면 계속 넘김
        g.test(3, 1); time.sleep(0.2)
        s_before = g.state()
        g.activate(); g.keydown(VK_CTRL)
        t0 = time.time()
        while time.time() - t0 < 2.5:
            time.sleep(0.04); g.keydown(VK_CTRL, repeat=True)
            if int(time.time() * 4) % 4 == 0: g.activate()
        g.keyup(VK_CTRL); time.sleep(0.5)
        s_after = g.state(); ev = tail.new(); [log("EV", l) for l in ev]
        check("ctrl_range_all_passes", not any("ctrl skip stopped" in l for l in ev) and s_after.get("pc") != s_before.get("pc"),
              {"pc": [s_before.get("pc"), s_after.get("pc"), s_after.get("stack")]})
        g.test(3, 0)

        # ---------------------------------------------------------------- 자동 대기·배율(3011@144: 음성 없는 줄과 있는 줄이 번갈아)
        s = load(g, 1, "slot1 again"); time.sleep(0.6); guard(g); tail.new()
        g.key(ord("A")); time.sleep(0.8); s = g.state(); g.shot("c01_auto_on_x1")
        check("A_turns_auto_on", s.get("auto") == "1" and s.get("bar_hidden") == "1", {"auto": s.get("auto"), "bar_hidden": s.get("bar_hidden")})
        waits = wait_lines(tail, r"play: wait x1", 4, 60)
        voices = []
        check("x1_waits_logged", len(waits) >= 4, waits)
        g.key(ord("A")); time.sleep(0.3); g.shot("c02_x2")
        w2 = wait_lines(tail, r"play: wait x2", 2, 40)
        check("x2_waits_logged", len(w2) >= 2, w2)
        g.key(ord("A")); time.sleep(0.25); g.key(ord("A")); time.sleep(0.25); g.key(ord("A")); time.sleep(0.25)
        g.shot("c03_x5")
        w5 = wait_lines(tail, r"play: wait x5", 2, 30)
        check("x5_waits_logged", len(w5) >= 2, w5)
        g.key(ord("A")); time.sleep(0.4)
        w1 = wait_lines(tail, r"play: (A -> rate x1|wait x1)", 1, 20)
        check("x5_wraps_to_x1", len(w1) >= 1, w1)

        # ---------------------------------------------------------------- 클릭으로 끄기(글 대기 중)
        time.sleep(0.3)
        g.click(400, 300); time.sleep(0.8); s1 = g.state(); time.sleep(2.0); s2 = g.state()
        g.shot("d01_clicked_off")
        check("click_turns_off_and_stays", s1.get("auto") == "0" and s2.get("pc") == s1.get("pc") and s2.get("clickwait") == "1",
              {"auto": s1.get("auto"), "pc": [s1.get("pc"), s2.get("pc")], "clickwait": s2.get("clickwait"), "bar_hidden": s2.get("bar_hidden")})
        g.click(400, 300); time.sleep(1.5); s3 = g.state()
        check("next_click_advances", s3.get("pc") != s2.get("pc"), {"pc": [s2.get("pc"), s3.get("pc")]})
        # Backspace
        g.key(ord("A")); time.sleep(0.6); g.key(VK_BACK); time.sleep(0.6); s = g.state()
        check("backspace_turns_off", s.get("auto") == "0" and s.get("bar_hidden") == "0", {"auto": s.get("auto"), "bar_hidden": s.get("bar_hidden")})
        tail.new()

        # ---------------------------------------------------------------- 음성 대기 중에 끄기(음성 있는 줄에서 voice 단계에 들어가면 클릭)
        s = load(g, 1, "slot1 voice"); time.sleep(0.5); tail.new()
        g.key(ord("A"))
        clicked = False; t0 = time.time(); voice_line = None
        while time.time() - t0 < 40 and not clicked:
            for l in tail.new():
                log("EV", l)
                m = re.search(r"play: wait .* typed (\d+)ms waited (\d+)ms", l)
                if m and g.keeper.peak > 0.02:
                    g.click(400, 300); clicked = True; voice_line = l; break
            time.sleep(0.02)
        time.sleep(1.0)
        vw = wait_lines(tail, r"voice wait", 1, 20)
        s1 = g.state(); time.sleep(1.5); s2 = g.state()
        check("voice_wait_click_goes_to_click_wait", clicked and vw and "auto 0" in vw[0] and s1.get("pc") == s2.get("pc") and s2.get("clickwait") == "1",
              {"wait": voice_line, "voice": vw, "pc": [s1.get("pc"), s2.get("pc")]})
        g.shot("e01_voice_click")

        # ---------------------------------------------------------------- 선택 뒤 자동 계속(자동인 채 1020 의 CHOICE 세이브를 불러옴)
        # 세이브 4(2300@10890)에서 자동 ×5 로 23줄 흘러가 선택지(2300@15008)에 닿게 한다(불러오기는 자동을 끄므로 불러온 뒤 켠다)
        s = load(g, 4, "slot4"); time.sleep(0.6); tail.new()
        for _ in range(5): g.key(ord("A")); time.sleep(0.3)
        s = g.wait_state(lambda s: s.get("choice") == "1", timeout=240, step=1.0, desc="reach choice by auto")
        time.sleep(1.0); g.shot("f01_choice"); log("choice", s)
        check("auto_off_at_choice", s.get("choice") == "1" and s.get("auto") == "0", {"auto": s.get("auto"), "choice": s.get("choice"), "stack": s.get("stack"), "pc": s.get("pc")})
        g.key(ord("A")); time.sleep(0.6); g.shot("f02_A_at_choice")
        ev = tail.new(); [log("EV", l) for l in ev]
        g.key(VK_DOWN); time.sleep(0.4); g.key(VK_RET); time.sleep(1.5)
        ev = wait_lines(tail, r"auto resumed after choice", 1, 15)
        s = g.state(); g.shot("f03_after_choice")
        check("auto_resumes_after_choice", ev and s.get("auto") == "1" and "x5" in ev[0], {"ev": ev, "auto": s.get("auto"), "bar_hidden": s.get("bar_hidden")})
        p0 = s.get("pc"); time.sleep(6.0); p1 = g.state().get("pc")
        check("auto_keeps_going_after_choice", p0 != p1, {"pc": [p0, p1]})
        g.key(VK_BACK); time.sleep(0.5)

        # ---------------------------------------------------------------- S 바로 저장 → 그 칸 불러오기
        s = load(g, 1, "slot1 for S"); time.sleep(0.6); tail.new()
        before = set(p.name for p in (fhost.GAME / "save").glob("rssave??.dat"))
        saved_at = g.state()
        g.key(ord("S")); time.sleep(0.8); g.shot("g01_S_saved")
        ev = tail.new(); [log("EV", l) for l in ev]
        after = set(p.name for p in (fhost.GAME / "save").glob("rssave??.dat"))
        new = sorted(after - before)
        m = [re.search(r"S -> slot (\d+) saved", l) for l in ev]
        slot = next((int(x.group(1)) for x in m if x), None)
        check("S_saves_next_empty", slot is not None and new == ["rssave%02d.dat" % slot], {"slot": slot, "new_files": new, "ev": ev})
        for _ in range(3): g.click(400, 300); time.sleep(1.2)
        moved = g.state()
        if slot is not None:
            g.key(ord("L")); time.sleep(1.2); g.shot("g02_L_story"); sL = g.state()
            check("L_story_opens_load_screen", sL.get("loadscr") == "1", {"loadscr": sL.get("loadscr")})
            g.click(400, 300, button="r"); time.sleep(1.0)
            s = load(g, slot, "load saved slot")
            check("load_saved_slot_returns_there", s.get("stack") == saved_at.get("stack") and s.get("pc") == saved_at.get("pc"),
                  {"saved": [saved_at.get("stack"), saved_at.get("pc")], "moved": moved.get("pc"), "loaded": [s.get("stack"), s.get("pc")]})

        # ---------------------------------------------------------------- 안내: 입력 막기, 자동 셈 멈춤
        s0 = g.state()
        g.key(VK_HOME); time.sleep(0.8); g.shot("h01_guide_story")
        g.click(400, 300); time.sleep(1.2); s1 = g.state()
        g.click(400, 300); time.sleep(1.2); s2 = g.state()
        check("guide_click_closes_without_advancing", s1.get("pc") == s0.get("pc") and s2.get("pc") != s1.get("pc"),
              {"pc": [s0.get("pc"), s1.get("pc"), s2.get("pc")]})
        g.key(ord("A")); time.sleep(0.4); g.key(VK_HOME); time.sleep(0.3); sa = g.state(); time.sleep(6.0); sb = g.state()
        g.shot("h02_guide_during_auto")
        g.key(VK_HOME); time.sleep(8.0); sc = g.state()
        check("guide_pauses_auto", sa.get("pc") == sb.get("pc") and sc.get("pc") != sb.get("pc") and sc.get("auto") == "1",
              {"pc": [sa.get("pc"), sb.get("pc"), sc.get("pc")], "auto": sc.get("auto")})
        g.key(VK_BACK); time.sleep(0.6)

        # ---------------------------------------------------------------- 다녀온 뒤: 지도·설정·숨기기
        tail.new()
        g.key(VK_F8); s1 = g.wait_state(lambda s: s.get("chart") == "1", timeout=12, step=0.3, desc="chart"); time.sleep(0.8); g.shot("i01_chart")
        g.key(VK_ESC); time.sleep(1.5); s2 = g.state()
        ev = tail.new(); [log("EV", l) for l in ev]
        check("chart_open_close", s1.get("chart") == "1" and s2.get("chart") == "0" and any("AUDIT PASS" in l for l in ev), {"chart": [s1.get("chart"), s2.get("chart")]})
        g.click(400, 300, button="r"); time.sleep(1.2); s1 = g.state(); g.shot("i02_settings")
        g.click(400, 300, button="r"); time.sleep(1.2); s2 = g.state()
        check("settings_open_close", s1.get("settings") == "1" and s2.get("settings") == "0", {"settings": [s1.get("settings"), s2.get("settings")]})
        g.key(VK_SHIFT); time.sleep(0.8); s1 = g.state(); g.shot("i03_hidden")
        g.key(VK_SHIFT); time.sleep(0.8); s2 = g.state()
        check("hide_toggle", s1.get("hidden") == "1" and s2.get("hidden") == "0", {"hidden": [s1.get("hidden"), s2.get("hidden")]})
        # 자동 중 F8 → 자동 끄고 지도
        g.key(ord("A")); time.sleep(1.0); g.key(VK_F8); s1 = g.wait_state(lambda s: s.get("chart") == "1", timeout=12, step=0.3, desc="chart2"); time.sleep(0.8); g.shot("i04_F8_during_auto")
        g.key(VK_ESC); time.sleep(1.5); s2 = g.state()
        check("F8_during_auto", s1.get("chart") == "1" and s1.get("auto") == "0" and s2.get("chart") == "0", {"s1": [s1.get("chart"), s1.get("auto")], "s2": s2.get("chart")})
        # 자동 중 오른쪽 클릭 → 자동 끄고 설정 화면
        g.key(ord("A")); time.sleep(1.0); g.click(400, 300, button="r"); s1 = g.wait_state(lambda s: s.get("settings") == "1", timeout=12, step=0.3, desc="settings2"); time.sleep(0.5); g.shot("i05_rclick_during_auto")
        g.click(400, 300, button="r"); time.sleep(1.2); s2 = g.state()
        check("rclick_during_auto", s1.get("settings") == "1" and s1.get("auto") == "0" and s2.get("settings") == "0", {"s1": [s1.get("settings"), s1.get("auto")], "s2": s2.get("settings")})
        # 자동 중 L → 자동 끄고 클릭 대기에서 불러오기 화면
        g.key(ord("A")); time.sleep(1.0); g.key(ord("L")); s1 = g.wait_state(lambda s: s.get("loadscr") == "1", timeout=12, step=0.3, desc="L auto"); g.shot("i07_L_during_auto")
        g.click(400, 300, button="r"); time.sleep(1.2); s2 = g.state()
        check("L_during_auto", s1.get("loadscr") == "1" and s1.get("auto") == "0" and s2.get("loadscr") == "0", {"s1": [s1.get("loadscr"), s1.get("auto")], "s2": s2.get("loadscr")})
        # 자동 대기 중(숨겨서 셈이 멈춘 채)에 불러오기 → 걸리지 않고 그 칸으로
        tail.new()
        got_bail = False; ok_all = True; tries = []
        for attempt in range(4):
            hide = attempt % 2 == 0
            g.key(ord("A")); time.sleep(3.2)
            if hide: g.key(VK_SHIFT); time.sleep(0.6)
            sh = g.state()
            if attempt == 0: g.shot("i08a_hidden_during_auto")
            g.test(2, 12)
            s = g.wait_state(lambda s: s.get("stack") == "0110>1010>3011" and s.get("pc") == "174", timeout=12, step=0.3, desc="load while hidden auto")
            ev = tail.new(); [log("EV", l) for l in ev]
            bail = any("context changed" in l for l in ev)
            got_bail = got_bail or bail
            ok = s.get("pc") == "174" and any("VM thread changed" in l for l in ev)
            ok_all = ok_all and ok
            tries.append({"hidden": sh.get("hidden"), "auto_before": sh.get("auto"), "bail": bail, "loaded_pc": s.get("pc"), "hidden_after": s.get("hidden"), "auto_after": s.get("auto")})
            if s.get("hidden") == "1": g.key(VK_SHIFT); time.sleep(0.6)
            if s.get("auto") == "1": g.key(VK_BACK); time.sleep(0.5)
        g.shot("i08_after_load_in_wait")
        check("load_during_auto_wait", ok_all and got_bail, tries)
        p0 = g.wait_state(lambda s: s.get("clickwait") == "1", timeout=15, desc="click wait after loads").get("pc")
        g.click(400, 300); time.sleep(1.5); p1 = g.state().get("pc")
        check("advances_after_loads", p0 != p1, {"pc": [p0, p1]})
        # 마지막으로 이야기가 계속 넘어가는지
        p0 = g.state().get("pc"); g.click(400, 300); time.sleep(1.5); p1 = g.state().get("pc")
        check("story_still_advances", p0 != p1, {"pc": [p0, p1]})
        g.shot("i06_end")
    finally:
        for l in tail.new(): log("EV", l)
        ok = g.quit()
        R["normal_quit"] = {"pass": bool(ok), "why": "quit dialog yes"}
        if not ok:
            g.kill()
        with open(fhost.OUT / "run2_result.json", "w", encoding="utf-8") as f:
            json.dump(R, f, ensure_ascii=False, indent=1)
        log("RESULT", sum(1 for v in R.values() if v["pass"]), "/", len(R))


if __name__ == "__main__":
    main()
