# -*- coding: utf-8 -*-
"""Forest 음악 감상 목록 한국어 그림(3401~3414 평소, 3501~3514 올림).
원작 일본어 그림 14장에서 글자를 뺀 바탕(14장이 같은 종이결)을 만들고, 그 위에 한국어 제목을 얹는다.
  python -X utf8 render_ko.py <글꼴 sans|serif> <출력 폴더>
"""
import sys, os, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

B = os.path.dirname(os.path.abspath(__file__))
TITLES = ['가든', '포레스트', '오늘은 축제', '혼자서', '황금빛 오후', '둘이서', '손을 잡자',
          '백파이퍼', 'Sprout', '런던 나이트', 'Ennui', '밴드', 'On the bridge', '뭔가 좋은 일이']
INK = (94, 54, 25)          # 원작 글자 색(가장 어두운 화소)
FONTS = {'sans': 'C:/Windows/Fonts/NotoSansKR-VF.ttf', 'serif': 'C:/Windows/Fonts/NotoSerifKR-VF.ttf'}


def blank(base):
    """14장에서 화소마다 가장 밝은 값 = 바탕. 모든 장에서 글자에 덮인 몇 점은 이웃 가운데값으로 메운다."""
    st = np.stack([np.array(Image.open(f'{B}/ja/{base + k}.png').convert('RGB')).astype(int) for k in range(1, 15)])
    lum = st.sum(3); idx = lum.argmax(0); H, W = idx.shape
    bg = st[idx, np.arange(H)[:, None], np.arange(W)[None, :]]
    agree = (st == bg[None]).all(3).sum(0)
    med = np.array(Image.fromarray(bg.astype(np.uint8)).filter(ImageFilter.MedianFilter(5))).astype(int)
    bad = (agree < 3) | (bg.sum(2) < med.sum(2) - 45)
    bg[bad] = med[bad]
    return bg.astype(np.uint8), int(bad.sum())


def render(bg, k, font_path, size, weight):
    im = Image.fromarray(bg).convert('RGBA')
    f = ImageFont.truetype(font_path, size)
    if str(weight).isdigit():
        f.set_variation_by_axes([int(weight)])
    else:
        f.set_variation_by_name(weight)
    num, title = f'{k}.', TITLES[k - 1]
    layer = Image.new('RGBA', im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
    x = 15 if k < 10 else 13
    # 글자 세로 자리: 한글 「가」 의 윗끝·아랫끝이 원작 글자 띠(y 4~23) 가운데에 오게
    gb = f.getbbox('가')
    y = (4 + 23) / 2 - (gb[1] + gb[3]) / 2
    d.text((x, y), num, font=f, fill=INK + (255,))
    nx = x + f.getlength(num) + max(5, size * 0.35)
    d.text((nx, y), title, font=f, fill=INK + (255,))
    im.alpha_composite(layer)
    w = d.textbbox((nx, y), title, font=f)[2]
    return im.convert('RGB'), w


def main():
    kind, out = sys.argv[1], sys.argv[2]
    size = int(sys.argv[3]) if len(sys.argv) > 3 else 19
    weight = sys.argv[4] if len(sys.argv) > 4 else 'Bold'
    os.makedirs(out, exist_ok=True)
    rep = {}
    for base in (3400, 3500):
        bg, fixed = blank(base)
        Image.fromarray(bg).save(f'{out}/blank_{base}.png')
        rep[f'blank_{base}_filled_pixels'] = fixed
        for k in range(1, 15):
            im, right = render(bg, k, FONTS[kind], size, weight)
            im.save(f'{out}/{base + k}.png')
            rep[str(base + k)] = {'title': TITLES[k - 1], 'right_edge': round(right, 1)}
    json.dump(rep, open(f'{out}/render.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(kind, size, weight, 'max right edge', max(v['right_edge'] for kk, v in rep.items() if isinstance(v, dict)), 'filled', rep['blank_3400_filled_pixels'], rep['blank_3500_filled_pixels'])


if __name__ == '__main__':
    main()
