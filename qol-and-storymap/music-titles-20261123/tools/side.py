from PIL import Image, ImageDraw, ImageFont
B = 'Y:/AI/claude-work/forest-music-titles'
OUT = 'P:/AI/forest-qol/music-titles-20261123/음악감상_목록_원작_영문.png'
F = ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf', 22)
S = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 17)
sc = 2; w, h = 214 * sc, 28 * sc; gap = 6; pad = 16; lab = 40
W = pad * 3 + w * 2; H = pad + lab + 14 * (h + gap) + 40
im = Image.new('RGB', (W, H), (34, 34, 48)); d = ImageDraw.Draw(im)
d.text((pad, pad), '원작(grpo.xfl)', font=F, fill=(240, 236, 228))
d.text((pad * 2 + w, pad), '지금 게임(영문 패치 그림)', font=F, fill=(240, 236, 228))
for k, n in enumerate(range(3401, 3415)):
    y = pad + lab + k * (h + gap)
    for col, sub in ((0, 'ja'), (1, 'en')):
        t = Image.open(f'{B}/{sub}/{n}.png').convert('RGBA').resize((w, h), Image.NEAREST)
        bg = Image.new('RGBA', (w, h), (34, 34, 48, 255)); bg.alpha_composite(t)
        im.paste(bg.convert('RGB'), (pad + col * (w + pad), y))
d.text((pad, H - 32), '9번이 엔딩 스태프 롤 곡(대본 5000 이 BGM 9 를 한 번 틂). 음악 감상 n번 = BGM n번(bgm 폴더 TrackNN.wav).', font=S, fill=(250, 199, 117))
im.save(OUT); print(OUT, im.size)
