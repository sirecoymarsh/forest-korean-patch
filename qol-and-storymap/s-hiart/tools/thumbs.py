import sys, os
from PIL import Image, ImageDraw
SRC = r'Y:\AI\forest-4k\src'
items = [x.split(':') for x in sys.argv[2].split(',')]
cell = int(sys.argv[3]) if len(sys.argv) > 3 else 200
ims = []
for arc, n in items:
    im = Image.open(os.path.join(SRC, arc, n + '.png')).convert('RGBA')
    bg = Image.new('RGBA', im.size, (90, 90, 90, 255)); bg.alpha_composite(im)
    s = cell / max(im.size); t = bg.resize((max(1, int(im.size[0] * s)), max(1, int(im.size[1] * s))), Image.LANCZOS)
    ims.append((arc + '/' + n, t))
cols = 6; rows = (len(ims) + cols - 1) // cols
sheet = Image.new('RGB', (cols * (cell + 6), rows * (cell + 20)), (30, 30, 30))
d = ImageDraw.Draw(sheet)
for i, (lab, t) in enumerate(ims):
    x, y = (i % cols) * (cell + 6), (i // cols) * (cell + 20)
    sheet.paste(t.convert('RGB'), (x, y)); d.text((x + 2, y + cell + 4), lab, fill=(230, 230, 230))
sheet.save(sys.argv[1])
