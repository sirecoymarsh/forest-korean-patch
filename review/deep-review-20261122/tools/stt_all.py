# -*- coding: utf-8 -*-
"""자막 음성 전부(654개) 뽑기 + Whisper large-v3 받아쓰기 (python 3.11, 코덱스 패키지).

  python -I tools\\stt_all.py extract   → voice\\NNNN.ogg  (voice.xfl 원본 게임은 읽기만)
  python -I tools\\stt_all.py whisper   → data\\stt_whisper.jsonl
앞 검수의 data\\stt.jsonl(같은 모델·같은 설정, 584개)은 그대로 옮겨 쓰고 없는 것만 새로 받는다.
"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa
PKG = r'P:\AI\Codex\projects\11-eyes-crossover-ko\research\python\faster-whisper'
MODEL = r'P:\AI\Codex\projects\drakoi-korean\vocal-subtitles\tools\faster-whisper-large-v3'
CUDA = r'P:\AI\Codex\projects\gemma4-26b-local\runtime'
sys.path.insert(0, r'P:\AI\forest-kr-build\tools')
VOICE_ARC = r'P:\GAME\Forest\voice.xfl'
VDIR = os.path.join(ROOT, 'voice')
PROMPT = 'アケル、九月、黛、刈谷、雨森、アリス、ガーデン、チェシャ、マッドハッター、ヤマネ、ピーターパン、フック、ティンク、シリウス。'


def voices():
    return sorted({r['voice'] for r in load_corpus() if r['kind'] == 'SUB' and r['voice'] is not None})


def extract():
    import xfl, oggfix
    os.makedirs(VDIR, exist_ok=True)
    idx = {e[0]: e for e in xfl.read_index(VOICE_ARC)}
    made = 0
    for v in voices():
        p = os.path.join(VDIR, '%04d.ogg' % v)
        if os.path.exists(p): continue
        e = idx.get('%04d.wav' % v)
        if not e: print('no voice', v); continue
        open(p, 'wb').write(oggfix.convert(xfl.extract(VOICE_ARC, e)))
        made += 1
    print('voices', len(voices()), 'extracted', made)


def whisper():
    sys.path.insert(0, PKG)
    os.add_dll_directory(CUDA); os.add_dll_directory(os.path.join(PKG, 'ctranslate2'))
    os.environ['PATH'] = CUDA + os.pathsep + os.environ.get('PATH', '')
    from faster_whisper import WhisperModel
    outp = os.path.join(DATA, 'stt_whisper.jsonl')
    done = {}
    for l in open(r'P:\AI\forest-gemini-review\data\stt.jsonl', encoding='utf-8'):
        o = json.loads(l); done[o['voice']] = o
    if os.path.exists(outp):
        for l in open(outp, encoding='utf-8'):
            o = json.loads(l); done[o['voice']] = o
    todo = [v for v in voices() if v not in done]
    print('whisper todo', len(todo), flush=True)
    model = WhisperModel(MODEL, device='cuda', compute_type='float16')
    t0 = time.time()
    for v in todo:
        p = os.path.join(VDIR, '%04d.ogg' % v)
        segs, info = model.transcribe(p, language='ja', beam_size=5, initial_prompt=PROMPT,
                                      vad_filter=False, condition_on_previous_text=False)
        segs = list(segs)
        done[v] = {'voice': v, 'dur': round(info.duration, 2), 'text': ''.join(s.text for s in segs).strip(),
                   'avg_logprob': round(sum(s.avg_logprob for s in segs) / len(segs), 3) if segs else None}
    with open(outp, 'w', encoding='utf-8') as fo:
        for v in voices():
            if v in done: fo.write(json.dumps(done[v], ensure_ascii=False) + '\n')
    print('whisper done', round(time.time() - t0), 's', len(done))


if __name__ == '__main__':
    {'extract': extract, 'whisper': whisper}[sys.argv[1]]()
