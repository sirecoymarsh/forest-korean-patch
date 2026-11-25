# -*- coding: utf-8 -*-
"""뜻 검수 꾸러미: 바뀐 대사·선택지·기타 칸마다 앞뒤 문맥을 붙여 ..\\data\\packets\\<이름>.jsonl 로 나눈다.

  python -I make_packets.py msg     대사·선택지·크레딧(자막 빼고)
  python -I make_packets.py sub     음성 자막(stt.jsonl 의 받아쓰기를 붙임)
"""
import json, os, re, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gscwalk import walk

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD = r'P:\AI\forest-flowchart-claude\runtime\scr_backup_20261121'
NEW = r'P:\AI\forest-flowchart-claude\runtime\scr'
JA = r'P:\AI\forest-kr-build\ja_scr'
TOK = re.compile(r'\^(g\d{3}|n|m|c[a-z])')


def seq_of(f):
    """재생 순서 목록: [(kind, slot, ja, old, new)] — 대사·자막 몸체·선택지 질문."""
    co, so = walk(os.path.join(OLD, f))
    _, sn = walk(os.path.join(NEW, f))
    jm = []
    jp = os.path.join(JA, f)
    if os.path.exists(jp):
        jc, js = walk(jp)
        jm = [js[a[5]].decode('cp932', 'replace') for _, op, a in jc if op == 0x51]
    out, k = [], 0
    for _, op, a in co:
        if op == 0x51:
            out.append(('msg', a[5], jm[k] if k < len(jm) else '', so[a[5]].decode('cp949', 'replace'), sn[a[5]].decode('cp949', 'replace')))
            k += 1
        elif op == 0x20 and a[0] == 49:
            out.append(('sub', a[5], '', so[a[5]].decode('cp949', 'replace'), sn[a[5]].decode('cp949', 'replace')))
        elif op == 0x0E:
            out.append(('choice', a[1], '', so[a[1]].decode('cp949', 'replace'), sn[a[1]].decode('cp949', 'replace')))
    return out


def short(s):
    return TOK.sub(lambda m: '/' if m.group(1) == 'n' else '', s).strip()


def main():
    mode = sys.argv[1]
    rows = [json.loads(l) for l in open(os.path.join(ROOT, 'data', 'changes.jsonl'), encoding='utf-8')]
    stt = {}
    sp = os.path.join(ROOT, 'data', 'stt.jsonl')
    if os.path.exists(sp):
        for l in open(sp, encoding='utf-8'):
            d = json.loads(l); stt[d['voice']] = d['text']
    # 제미나이가 직접 들어 적은 일본어(ja_heard): 그 작업 폴더의 sub_revised_*.json — (대본, 몸체 슬롯) → 글
    heard = {}
    gs = r'C:\Users\CadriacLord\.gemini\antigravity\brain\5a8e551d-80c7-4e24-98ae-0bd89f2eb6a0\scratch'
    for k in range(1, 5):
        p = os.path.join(gs, 'sub_revised_%d.json' % k)
        if os.path.exists(p):
            for e in json.load(open(p, encoding='utf-8')):
                if e.get('ja_heard'):
                    heard[(int(e['sid']), int(e['c_slot']))] = e['ja_heard']
    want = (lambda r: r['lane'] == 'sub') if mode == 'sub' else (lambda r: r['lane'] in ('msg', 'choice_prompt', 'choice_option', 'append', 'other'))
    sel = [r for r in rows if want(r)]
    seqs, items = {}, []
    for r in sel:
        f = '%04d.gsc' % r['file']
        if f not in seqs:
            seqs[f] = seq_of(f)
        sq = seqs[f]
        pos = next((i for i, e in enumerate(sq) if e[1] == r['slot']), None)
        ctx = []
        if pos is not None:
            for e in sq[max(0, pos - 2):pos] + sq[pos + 1:pos + 2]:
                ctx.append({'kind': e[0], 'ja': e[2], 'ko': short(e[4])})
        it = {'id': '%d:%d' % (r['file'], r['slot']), 'file': r['file'], 'chapter': r['chapter'], 'lane': r['lane'],
              'spk': r['spk'], 'ja': r['ja'], 'en': r['en'], 'old': r['old'], 'new': r['new'], 'context': ctx}
        if mode == 'sub':
            it['voice'] = r['voice']
            it['stt_ja'] = stt.get(r['voice'], '')
            it['gemini_heard_ja'] = heard.get((r['file'], r['slot']), '')
        items.append(it)
    # 나누기: 장 순서대로 대략 같은 크기로
    items.sort(key=lambda x: (x['chapter'] or 99, x['file'], int(x['id'].split(':')[1])))
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 220
    pdir = os.path.join(ROOT, 'data', 'packets'); os.makedirs(pdir, exist_ok=True)
    n = 0
    for i in range(0, len(items), size):
        n += 1
        chunk = items[i:i + size]
        name = '%s_%02d.jsonl' % (mode, n)
        with open(os.path.join(pdir, name), 'w', encoding='utf-8') as fo:
            for it in chunk:
                fo.write(json.dumps(it, ensure_ascii=False) + '\n')
        chs = sorted({c['chapter'] for c in chunk if c['chapter']})
        print(name, len(chunk), 'chapters', chs, 'files', sorted({c['file'] for c in chunk})[:12])


if __name__ == '__main__':
    main()
