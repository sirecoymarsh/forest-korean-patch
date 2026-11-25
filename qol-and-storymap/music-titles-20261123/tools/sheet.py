import sys
from PIL import Image
src = sys.argv[1]; dst = sys.argv[2]; first = int(sys.argv[3]); last = int(sys.argv[4])
ims = [Image.open(f'{src}/{n}.png').convert('RGBA') for n in range(first, last + 1)]
for n, im in zip(range(first, last + 1), ims):
    print(n, im.size)
W = max(i.width for i in ims) * 2 + 20; H = sum(i.height * 2 + 6 for i in ims) + 20
sheet = Image.new('RGBA', (W, H), (40, 40, 60, 255))
y = 10
for im in ims:
    big = im.resize((im.width * 2, im.height * 2), Image.NEAREST)
    sheet.alpha_composite(big, (10, y)); y += big.height + 6
sheet.convert('RGB').save(dst)
