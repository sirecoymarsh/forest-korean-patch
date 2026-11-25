# -*- coding: utf-8 -*-
"""꾸러미 칸을 읽기 좋게 보여 준다(검수자용).

  python -I show.py <꾸러미 이름> <시작 번호(0부터)> <개수>
  예) python -I show.py msg_03 0 30
출력은 UTF-8 파일 ..\\data\\show_<꾸러미>.txt 에도 쓴다(콘솔 글자 깨짐 대비) — 그 파일을 Read 로 읽어도 된다.
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    name, start, count = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    items = [json.loads(l) for l in open(os.path.join(ROOT, 'data', 'packets', name + '.jsonl'), encoding='utf-8')]
    out = ['꾸러미 %s: 전체 %d칸, %d~%d 보여 줌' % (name, len(items), start, min(len(items), start + count) - 1)]
    for k, it in enumerate(items[start:start + count], start):
        out.append('')
        out.append('#%d  id=%s  장=%s  갈래=%s  화자=%s%s' % (k, it['id'], it['chapter'], it['lane'], it['spk'],
                                                         ('  음성=%s' % it['voice']) if it.get('voice') is not None else ''))
        for c in it.get('context', [])[:-1] if it.get('context') else []:
            pass
        ctx = it.get('context', [])
        for c in ctx:
            out.append('   (문맥 %s) JA: %s | KO: %s' % (c['kind'], c['ja'][:120], c['ko'][:120]))
        out.append('   JA : %s' % it['ja'])
        if it.get('gemini_heard_ja') is not None:
            out.append('   제미나이가 들은 일본어: %s' % it.get('gemini_heard_ja'))
        if it.get('stt_ja') is not None:
            out.append('   Whisper 받아쓰기   : %s' % it.get('stt_ja'))
        out.append('   EN : %s' % it['en'])
        out.append('   OLD: %s' % it['old'])
        out.append('   NEW: %s' % it['new'])
    text = '\n'.join(out)
    p = os.path.join(ROOT, 'data', 'show_%s.txt' % name)
    with open(p, 'w', encoding='utf-8') as f:
        f.write(text)
    sys.stdout.buffer.write(text.encode('utf-8', 'replace'))


if __name__ == '__main__':
    main()
