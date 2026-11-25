# -*- coding: utf-8 -*-
"""Qwen3-ASR-1.7B 로 자막 음성 받아쓰기 — Whisper 와 구조가 다른 두 번째 받아쓰기.
(오디오 인코더 + Qwen LLM 디코더. 앞 문맥 이어 쓰기·무음 환각 성향이 Whisper 와 다르다.)

forge venv(python 3.10, torch 2.7 cu128)로 돈다:
  P:\\AI\\forge\\venv\\Scripts\\python.exe tools\\stt_qwen.py  → data\\stt_qwen.jsonl
"""
import os, sys, json, time
sys.stdout.reconfigure(encoding='utf-8'); sys.stderr.reconfigure(encoding='utf-8')
R = r'P:\AI\Codex\projects\drakoi-korean\vocal-subtitles'
sys.path[:0] = [R + r'\tools\qwen_asr_pkgs', R + r'\tools\separation_pkgs',
                r'P:\AI\Codex\projects\forest-opening-korean\tools\stt_pkgs']
os.environ['HF_HOME'] = R + r'\tools\hf-cache'; os.environ['HF_HUB_DISABLE_XET'] = '1'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'; os.environ['HF_HUB_OFFLINE'] = '1'
import numpy as np, soundfile as sf, torch
from scipy.signal import resample_poly
from qwen_asr import Qwen3ASRModel

ROOT = r'Y:\AI\forest-deep-review'
VDIR = os.path.join(ROOT, 'voice')
outp = os.path.join(ROOT, 'data', 'stt_qwen.jsonl')
done = set()
if os.path.exists(outp):
    done = {json.loads(l)['voice'] for l in open(outp, encoding='utf-8') if l.strip()}
files = sorted(f for f in os.listdir(VDIR) if f.endswith('.ogg'))
model = Qwen3ASRModel.from_pretrained(R + r'\tools\Qwen3-ASR-1.7B', dtype=torch.bfloat16, device_map='cuda:0',
                                      attn_implementation='sdpa', max_inference_batch_size=1, max_new_tokens=300)
t0 = time.time()
with open(outp, 'a', encoding='utf-8') as fo:
    for n, f in enumerate(files, 1):
        v = int(f[:4])
        if v in done: continue
        a, sr = sf.read(os.path.join(VDIR, f), dtype='float32')
        if a.ndim > 1: a = a.mean(axis=1)
        if sr != 16000:
            from math import gcd
            g = gcd(sr, 16000); a = resample_poly(a, 16000 // g, sr // g).astype('float32'); sr = 16000
        pk = float(np.max(np.abs(a))) if len(a) else 0.0
        if pk > 1e-5: a = a * (0.94 / pk)
        out = model.transcribe(audio=(a, sr), language='Japanese')[0]
        fo.write(json.dumps({'voice': v, 'dur': round(len(a) / sr, 2), 'text': out.text}, ensure_ascii=False) + '\n')
        fo.flush()
        if n % 50 == 0: print(n, '/', len(files), round(time.time() - t0), 's', flush=True)
print('qwen done', round(time.time() - t0), 's')
