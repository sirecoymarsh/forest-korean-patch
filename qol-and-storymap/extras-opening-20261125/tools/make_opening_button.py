# -*- coding: utf-8 -*-
"""특전 메뉴 「오프닝」 단추(보통 1010 · 올림 1110)를 한국어판 타이틀 단추와 같은 함수로 만든다.
바탕 = 원본 「戻る」(1009/1109) 타원에서 글자를 지운 빈 판(코덱스 reconstruct_title_blank), 글 = typeset_title_layer."""
import sys, shutil, subprocess
from pathlib import Path
UI = Path(r'P:\AI\Codex\projects\_migrated_c_documents_codex\2026-07-29\p-game-forest\work\forest-en-korean-pilot\ui_work')
sys.path.insert(0, str(UI / 'tools'))
import build_korean_static_ui as B
from PIL import Image

OUT = Path(r'Y:\AI\claude-work\forest-optest\button'); OUT.mkdir(parents=True, exist_ok=True)
tool = UI / 'tools' / 'UiAssetTool.exe'
font = Path(r'C:\Windows\Fonts\NotoSerifKR-VF.ttf')
for src, dst in (('1009', '1010'), ('1109', '1110')):
    orig = Image.open(UI / 'png_ui' / 'japanese' / 'grpo' / f'{src}.png').convert('RGBA')
    blank = B.reconstruct_title_blank(orig)
    edited, info, _ = B.typeset_title_layer(orig, '오프닝', font, blank)
    patch = OUT / f'{dst}.patch.png'; mask = OUT / f'{dst}.mask.png'
    edited.save(patch)
    B.save_diff_mask(orig, edited, mask)
    wcg = OUT / f'{dst}.wcg'
    B.run_checked([str(tool), 'wcg-apply-patch', str(UI / 'trusted_ui' / 'japanese' / 'grpo' / f'{src}.wcg'), str(patch), str(mask), str(wcg)])
    B.run_checked([str(tool), 'wcg2png', str(wcg), str(OUT / f'{dst}.png')])
    print(dst, info)
# 비교용: 지금 깔린 한국어 「뒤로」 단추
for s in ('1009', '1109'):
    B.run_checked([str(tool), 'wcg2png', r'P:\AI\forest-kr-build\game\grpo\%s.wcg' % s, str(OUT / f'cur_{s}.png')])
