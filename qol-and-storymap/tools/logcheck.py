"""설치 기록 줄(qol: present … hiart …)만 확인하는 짧은 시험."""
import os, sys, time
os.environ.setdefault("FOREST_GAME", r"Y:\AI\forest-qol-test\game")
os.environ.setdefault("FOREST_OUT", r"Y:\AI\claude-work\forest-qol-int\out")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fhost
from fhost import log

g = fhost.Game().launch()
n0 = 0
line = None
t0 = time.time()
try:
    while time.time() - t0 < 120 and not line:
        g.activate()
        for l in g.events():
            if "qol: present" in l:
                line = l
        time.sleep(0.5)
    log("INSTALL LOG:", line)
finally:
    q = g.quit() if g.alive() else False
    log("quit normally" if q else "quit failed")
    if g.alive():
        g.kill()
