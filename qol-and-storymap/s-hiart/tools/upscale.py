# -*- coding: utf-8 -*-
"""한 장씩 Upscayl high-fidelity-4x. 장마다: nvlddmkm 사건 번호·검은 그림·크기·원본 대조. 연속 3장 실패면 멈춤.
python upscale.py <목록 파일 또는 arc/name,...> [--out DIR]
입력: Y:\AI\forest-4k\src\<arc>\<name>.png (투명 그림은 가장자리 색을 메운 RGB 로 바꿔 넣음)
출력: <out>\<arc>\<name>.png (RGB 4배, AI 그대로) + log.jsonl"""
import sys, os, json, subprocess, time, re, argparse, ctypes
import numpy as np, cv2
UP = r'P:\AI\Codex\projects\image-upscaling-tools\apps\Upscayl-2.15.0\resources'
SRC = r'Y:\AI\forest-4k\src'
TMP = r'Y:\AI\forest-4k\tmp_in'

def gpu_event():
    r = subprocess.run(['wevtutil', 'qe', 'System', "/q:*[System[Provider[@Name='nvlddmkm']]]", '/c:1', '/rd:true', '/f:xml'], capture_output=True, text=True, encoding='utf-8', errors='replace')
    m = re.search(r'<EventRecordID>(\d+)<', r.stdout)
    return int(m.group(1)) if m else 0

def edge_fill(rgb, alpha):
    clear = alpha == 0
    if not clear.any() or clear.all(): return rgb
    _, labels = cv2.distanceTransformWithLabels(clear.astype(np.uint8), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    ys, xs = np.nonzero(~clear)
    lab2i = np.zeros(labels.max() + 1, np.int64); lab2i[labels[ys, xs]] = np.arange(len(ys))
    out = rgb.copy(); i = lab2i[labels[clear]]; out[clear] = rgb[ys[i], xs[i]]
    soft = cv2.GaussianBlur(out, (0, 0), 1.5); out[clear] = soft[clear]
    return out

def prep(arc, name):
    im = cv2.imread(os.path.join(SRC, arc, name + '.png'), cv2.IMREAD_UNCHANGED)
    if im.shape[2] == 4 and (im[:, :, 3] < 255).any():
        rgb = edge_fill(np.ascontiguousarray(im[:, :, :3]), im[:, :, 3])
    else:
        rgb = im[:, :, :3]
    os.makedirs(os.path.join(TMP, arc), exist_ok=True)
    p = os.path.join(TMP, arc, name + '.png'); cv2.imwrite(p, rgb)
    return p, rgb

def one(arc, name, outdir):
    dst = os.path.join(outdir, arc, name + '.png')
    if os.path.exists(dst): return {'skip': True}
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    src, rgb = prep(arc, name)
    h, w = rgb.shape[:2]
    if min(h, w) < 64:
        return {'small': True}
    ev0 = gpu_event(); t0 = time.time()
    tmp = dst + '.tmp.png'
    r = subprocess.run([os.path.join(UP, 'bin', 'upscayl-bin.exe'), '-i', src, '-o', tmp, '-n', 'high-fidelity-4x', '-m', os.path.join(UP, 'models'), '-s', '4', '-f', 'png'], capture_output=True, text=True, encoding='utf-8', errors='replace')
    ev1 = gpu_event()
    res = {'rc': r.returncode, 'sec': round(time.time() - t0, 1)}
    if ev1 != ev0: res['gpu_event'] = ev1; return res
    ai = cv2.imread(tmp, cv2.IMREAD_COLOR) if os.path.exists(tmp) else None
    if ai is None: res['no_output'] = r.stderr[-300:]; return res
    if ai.shape[:2] != (h * 4, w * 4): res['bad_size'] = ai.shape; return res
    if ai.mean() < 2 and rgb.mean() > 10: res['black'] = True; return res
    small = cv2.resize(ai, (w, h), interpolation=cv2.INTER_AREA).astype(np.int16)
    res['mad'] = round(float(np.abs(small - rgb.astype(np.int16)).mean()), 2)
    if res['mad'] > 12: res['mismatch'] = True; return res
    os.replace(tmp, dst); res['ok'] = True
    return res

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('items'); ap.add_argument('--out', default=r'Y:\AI\forest-4k\ai')
    a = ap.parse_args()
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
    items = [l.strip() for l in open(a.items, encoding='utf-8')] if os.path.exists(a.items) else a.items.split(',')
    items = [x for x in items if x]
    fails = 0; log = open(os.path.join(a.out, 'log.jsonl'), 'a', encoding='utf-8') if os.makedirs(a.out, exist_ok=True) is None else None
    for k, it in enumerate(items):
        arc, name = it.split('/')
        res = one(arc, name, a.out); res['item'] = it; res['time'] = time.strftime('%H:%M:%S')
        log.write(json.dumps(res) + '\n'); log.flush()
        print(k + 1, len(items), res, flush=True)
        if res.get('gpu_event'): print('STOP: GPU event'); break
        if res.get('ok') or res.get('skip') or res.get('small'): fails = 0
        else:
            fails += 1
            if fails >= 3: print('STOP: 3 failures in a row'); break
