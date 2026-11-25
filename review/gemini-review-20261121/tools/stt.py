# -*- coding: utf-8 -*-
"""바뀐 음성 자막의 음성을 일본어로 받아 적는다(faster-whisper large-v3, 이미 깔린 코덱스 패키지·모델 그대로).

  python -I stt.py            → ..\\data\\stt.jsonl  {voice, text, segments}
음성은 voice.xfl(원본 게임, 읽기만) → WAV 안 Vorbis → 진짜 Ogg 스트림만(oggfix) → ..\\voice\\NNNN.ogg
"""
import json, os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = r'P:\AI\Codex\projects\11-eyes-crossover-ko\research\python\faster-whisper'
MODEL = r'P:\AI\Codex\projects\drakoi-korean\vocal-subtitles\tools\faster-whisper-large-v3'
CUDA = r'P:\AI\Codex\projects\gemma4-26b-local\runtime'
sys.path.insert(0, PKG)
sys.path.insert(0, r'P:\AI\forest-kr-build\tools')
os.add_dll_directory(CUDA)
os.add_dll_directory(os.path.join(PKG, 'ctranslate2'))
os.environ['PATH'] = CUDA + os.pathsep + os.environ.get('PATH', '')
import xfl            # noqa: E402  forest-kr-build 도구
import oggfix         # noqa: E402
from faster_whisper import WhisperModel   # noqa: E402

VOICE_ARC = r'P:\GAME\Forest\voice.xfl'
PROMPT = 'アケル、九月、黛、刈谷、雨森、アリス、ガーデン、チェシャ、マッドハッター、ヤマネ、ピーターパン、フック、ティンク、シリウス。'


def main():
    rows = [json.loads(l) for l in open(os.path.join(ROOT, 'data', 'changes.jsonl'), encoding='utf-8')]
    voices = sorted({r['voice'] for r in rows if r['lane'] == 'sub' and r['voice'] is not None})
    vdir = os.path.join(ROOT, 'voice'); os.makedirs(vdir, exist_ok=True)
    idx = {e[0]: e for e in xfl.read_index(VOICE_ARC)}
    made = 0
    for v in voices:
        p = os.path.join(vdir, '%04d.ogg' % v)
        if os.path.exists(p):
            continue
        e = idx.get('%04d.wav' % v)
        if not e:
            print('no voice', v); continue
        open(p, 'wb').write(oggfix.convert(xfl.extract(VOICE_ARC, e)))
        made += 1
    print('voices', len(voices), 'extracted', made, flush=True)
    try:
        model = WhisperModel(MODEL, device='cuda', compute_type='float16')
        dev = 'cuda'
    except Exception as ex:
        print('cuda failed:', ex, '-> cpu int8', flush=True)
        model = WhisperModel(MODEL, device='cpu', compute_type='int8')
        dev = 'cpu'
    outp = os.path.join(ROOT, 'data', 'stt.jsonl')
    done = set()
    if os.path.exists(outp):
        done = {json.loads(l)['voice'] for l in open(outp, encoding='utf-8')}
    t0 = time.time()
    with open(outp, 'a', encoding='utf-8') as fo:
        for n, v in enumerate(voices, 1):
            if v in done:
                continue
            p = os.path.join(vdir, '%04d.ogg' % v)
            if not os.path.exists(p):
                continue
            segs, info = model.transcribe(p, language='ja', beam_size=5, initial_prompt=PROMPT,
                                          vad_filter=False, condition_on_previous_text=False)
            segs = list(segs)
            text = ''.join(s.text for s in segs).strip()
            fo.write(json.dumps({'voice': v, 'dur': round(info.duration, 2), 'text': text,
                                 'avg_logprob': round(sum(s.avg_logprob for s in segs) / len(segs), 3) if segs else None},
                                ensure_ascii=False) + '\n')
            fo.flush()
            if n % 25 == 0:
                print(dev, n, '/', len(voices), round(time.time() - t0), 's', flush=True)
    print('done', dev, round(time.time() - t0), 's')


if __name__ == '__main__':
    main()
