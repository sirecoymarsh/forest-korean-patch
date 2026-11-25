# -*- coding: utf-8 -*-
"""AI 4배(Y:\\AI\\forest-4k\\ai) → 섞기·투명도 4배 → 게임용 4배 그림 + 색인.

입력: src\\<묶음>\\<번호>.png(1배 BGRA 또는 BGR), ai\\<묶음>\\<번호>.png(AI 4배 RGB, 투명 가장자리 메운 입력에서)
출력: Y:\\AI\\forest-4k\\out\\<묶음>\\<번호>.jpg(불투명, q95 4:4:4) 또는 .png(투명 있음, BGRA)
      Y:\\AI\\forest-4k\\out\\index.tsv  key\tfile\tw1\th1\talpha\tsum1\tmad\tkept\tlost_alpha
key = 엔진 경로 꼴 '<묶음>/<번호>' (예: grpe/4040). sum1 = 불투명 화소 색의 FNV-1a 32 — 런타임이 엔진 화소와 대조(엔진은 반투명 화소 색이 PNG 와 조금 달라 불투명만 본다).
검사(장마다): 크기 4배, 검은 그림 아님, 1배로 줄여 원본과 평균 차 ≤ 12, 색 평균 이동, 잃은 투명도 %.
python build4x.py [--lo 40 --hi 120] [--only grpe/4040,...] [--workers 6]
"""
import sys, os, json, argparse, time
import numpy as np, cv2
from concurrent.futures import ProcessPoolExecutor, as_completed
sys.path.insert(0, r'P:\AI\forest-qol\s-hiart\tools')
from blend4 import blend, alpha4, lost_alpha_pct

SRC = r'Y:\AI\forest-4k\src'
AI = r'Y:\AI\forest-4k\ai'
OUT = r'Y:\AI\forest-4k\out'
ARCS = ['grpe', 'grpo_bg', 'grpo_bu', 'grpo_f', 'grpo_ci']


def opaque_sum(bgra):
    """런타임 opaqueSum 과 같은 식: 불투명(a==255) 화소의 B|G<<8|R<<16 을 차례로 FNV-1a 32."""
    a = np.ascontiguousarray(bgra).view(np.uint32).ravel()
    sel = np.ascontiguousarray(bgra[:, :, 3]).ravel() == 255
    hh = 2166136261
    for v in (a[sel] & 0xFFFFFF).tolist():
        hh = ((hh ^ v) * 16777619) & 0xffffffff
    return hh


def one(key, lo, hi):
    arc, name = key.split('/')
    im = cv2.imread(os.path.join(SRC, arc, name + '.png'), cv2.IMREAD_UNCHANGED)
    h, w = im.shape[:2]
    bgra = im if im.shape[2] == 4 else cv2.cvtColor(im, cv2.COLOR_BGR2BGRA)
    a1 = bgra[:, :, 3]
    has_a = not (a1 == 255).all()
    rgb = np.ascontiguousarray(bgra[:, :, :3])
    aip = os.path.join(AI, arc, name + '.png')
    lo_p = r'Y:\AI\forest-4k\lanczos_only.txt'   # AI 결과가 원본과 너무 달라 원본을 부드럽게 키워 쓰는 그림(스킬 4절)
    lonly = set(l.split('\t')[0].strip() for l in open(lo_p, encoding='utf-8') if l.strip()) if os.path.exists(lo_p) else set()
    small = min(h, w) < 64 or key in lonly
    if small or not os.path.exists(aip):
        if not small: return key, {'error': 'no ai'}
        out_rgb = cv2.resize(rgb, (w * 4, h * 4), interpolation=cv2.INTER_LANCZOS4); kept = 0.0
    else:
        ai = cv2.imread(aip, cv2.IMREAD_COLOR)
        if ai is None or ai.shape[:2] != (h * 4, w * 4): return key, {'error': 'ai size'}
        if ai.mean() < 2 and rgb.mean() > 10: return key, {'error': 'ai black'}
        # 투명 그림은 AI 입력과 같게 가장자리 메운 색을 원본 쪽에도 써서 섞는다(투명 밑 색은 결과에서 가려진다)
        if has_a:
            from upscale import edge_fill
            rgb_f = edge_fill(rgb, a1)
        else:
            rgb_f = rgb
        out_rgb, kept = blend(rgb_f, ai, lo, hi)
    # 넓은 색 보정(도화월탄 방식): 결은 두고 넓은 색 흐름만 원본에 맞춘다. 1배에서 (원본 − 4배를 줄인 것)을 보이는 화소로만
    # σ3 흐려 4배로 키워 더한다. high-fidelity 가 아주 진한 주황·노랑 면의 0 채널을 들뜨게 하는 것(최대 16)을 잡는다.
    if not small:
        m1 = a1.astype(np.float32) / 255.0
        sm = cv2.resize(out_rgb, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32)
        diff = (rgb.astype(np.float32) - sm) * m1[:, :, None]
        den = cv2.GaussianBlur(m1, (0, 0), 3)
        D = cv2.GaussianBlur(diff, (0, 0), 3) / np.maximum(den, 1e-3)[:, :, None]
        D[den < 0.05] = 0
        out_rgb = np.clip(out_rgb.astype(np.float32) + cv2.resize(D, (w * 4, h * 4), interpolation=cv2.INTER_LINEAR) + 0.5, 0, 255).astype(np.uint8)
    res = {'w1': w, 'h1': h, 'alpha': int(has_a), 'kept': round(kept * 100, 1)}
    back = cv2.resize(out_rgb, (w, h), interpolation=cv2.INTER_AREA).astype(np.int16)
    vis = a1 > 0
    d = np.abs(back - rgb.astype(np.int16))
    res['mad'] = round(float(d[vis].mean()) if vis.any() else 0.0, 2)
    res['shift'] = [round(float((back[:, :, c][vis] - rgb[:, :, c][vis].astype(np.int16)).mean()), 2) for c in range(3)] if vis.any() else [0, 0, 0]
    if res['mad'] > 12: return key, dict(res, error='mad')
    os.makedirs(os.path.join(OUT, arc), exist_ok=True)
    if has_a:
        a4 = alpha4(a1)
        res['lost_alpha'] = round(lost_alpha_pct(a1, a4), 2)
        o = np.dstack([out_rgb, a4])
        fn = os.path.join(arc, name + '.png')
        cv2.imwrite(os.path.join(OUT, fn + '.tmp.png'), o, [cv2.IMWRITE_PNG_COMPRESSION, 6])
    else:
        fn = os.path.join(arc, name + '.jpg')
        cv2.imwrite(os.path.join(OUT, fn + '.tmp.jpg'), out_rgb, [cv2.IMWRITE_JPEG_QUALITY, 95, cv2.IMWRITE_JPEG_SAMPLING_FACTOR, cv2.IMWRITE_JPEG_SAMPLING_FACTOR_444])
        res['lost_alpha'] = 0.0
    tmp = os.path.join(OUT, fn + ('.tmp.png' if has_a else '.tmp.jpg'))
    os.replace(tmp, os.path.join(OUT, fn))
    res['file'] = fn.replace('\\', '/')
    res['sum1'] = '%08x' % opaque_sum(bgra)
    return key, res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lo', type=int, default=40); ap.add_argument('--hi', type=int, default=120)
    ap.add_argument('--only', default=''); ap.add_argument('--workers', type=int, default=6)
    a = ap.parse_args()
    import ctypes
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
    keys = a.only.split(',') if a.only else [arc + '/' + n[:-4] for arc in ARCS for n in sorted(os.listdir(os.path.join(SRC, arc))) if n.endswith('.png')]
    excl_p = os.path.join(r'Y:\AI\forest-4k', 'exclude.txt')
    excl = set(l.split('\t')[0].strip() for l in open(excl_p, encoding='utf-8') if l.strip() and not l.startswith('#')) if os.path.exists(excl_p) else set()
    keys = [k for k in keys if k not in excl]
    man_p = os.path.join(OUT, 'manifest.json')
    man = json.load(open(man_p, encoding='utf-8')) if os.path.exists(man_p) else {}
    t0 = time.time(); n = 0
    with ProcessPoolExecutor(a.workers) as ex:
        futs = [ex.submit(one, k, a.lo, a.hi) for k in keys]
        for f in as_completed(futs):
            k, r = f.result(); man[k] = r; n += 1
            if 'error' in r: print('FAIL', k, r, flush=True)
            if n % 50 == 0: print(n, len(keys), '%.0fs' % (time.time() - t0), flush=True)
    os.makedirs(OUT, exist_ok=True)
    json.dump(man, open(man_p, 'w', encoding='utf-8'), indent=0, sort_keys=True)
    with open(os.path.join(OUT, 'index.tsv'), 'w', encoding='utf-8') as f:
        f.write('# key\tfile\tw1\th1\talpha\tsum1\n')
        for k, r in sorted(man.items()):
            if 'error' in r or 'file' not in r: continue
            f.write('%s\t%s\t%d\t%d\t%d\t%s\n' % (k, r['file'], r['w1'], r['h1'], r['alpha'], r['sum1']))
    print('done', n, 'fails', sum(1 for r in man.values() if 'error' in r))


if __name__ == '__main__':
    main()
