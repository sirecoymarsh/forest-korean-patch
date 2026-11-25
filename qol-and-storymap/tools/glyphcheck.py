"""새 문구(진행·아이콘 줄·화면 모듈의 L"…" 문자열)의 글자가 지도 글꼴 축소본에 다 있는지."""
import os, re, sys
from fontTools.ttLib import TTFont

NATIVE = r"P:\AI\forest-qol\native"
FC = sys.argv[1] if len(sys.argv) > 1 else r"Y:\AI\forest-qol-test\game\fc"
src = ""
for n in ("qol_play.cpp", "qol_buttons.cpp", "qol_present.cpp", "qol_core.cpp"):
    src += open(os.path.join(NATIVE, n), encoding="utf-8").read()
lits = re.findall(r'L"((?:[^"\\]|\\.)*)"', src)
chars = {c for s in lits for c in s if ord(c) > 0x7F}
for f in ("ForestChartSerif-SemiBold.ttf", "ForestChartSerif-Black.ttf"):
    cmap = TTFont(os.path.join(FC, f)).getBestCmap()
    miss = sorted(c for c in chars if ord(c) not in cmap)
    print(f, "chars", len(chars), "missing", " ".join("U+%04X" % ord(c) for c in miss) or "-")
    for c in miss:
        for s in lits:
            if c in s:
                print("   U+%04X in:" % ord(c), s.encode("unicode_escape").decode("ascii")[:120]); break
