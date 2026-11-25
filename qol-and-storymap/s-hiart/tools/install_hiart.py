# -*- coding: utf-8 -*-
"""게임 폴더에 hiart\ (4배 그림 + index.tsv) 넣기. 같은 드라이브면 하드 링크(용량 0), 아니면 복사.
python -I install_hiart.py <게임 폴더> [--copy]"""
import os, sys, shutil
OUT = r'Y:\AI\forest-4k\out'
game = sys.argv[1]
force_copy = '--copy' in sys.argv
dst_root = os.path.join(game, 'hiart')
idx = [l.rstrip('\n').split('\t') for l in open(os.path.join(OUT, 'index.tsv'), encoding='utf-8') if l.strip() and not l.startswith('#')]
same = os.path.splitdrive(os.path.abspath(game))[0].lower() == os.path.splitdrive(OUT)[0].lower() and not force_copy
n = linked = 0
for row in idx:
    rel = row[1].replace('/', os.sep)
    s = os.path.join(OUT, rel); d = os.path.join(dst_root, rel)
    os.makedirs(os.path.dirname(d), exist_ok=True)
    if os.path.exists(d):
        if os.path.getsize(d) == os.path.getsize(s): n += 1; continue
        os.remove(d)
    if same:
        try: os.link(s, d); linked += 1
        except OSError: shutil.copy2(s, d)
    else: shutil.copy2(s, d)
    n += 1
shutil.copy2(os.path.join(OUT, 'index.tsv'), os.path.join(dst_root, 'index.tsv'))
print('installed', n, 'pictures into', dst_root, '(hard links %d)' % linked)
