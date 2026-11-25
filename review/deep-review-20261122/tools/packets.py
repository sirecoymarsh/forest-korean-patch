# -*- coding: utf-8 -*-
"""표본 400 + 심은 결함 53 → 섞어서 익명 번호(Q001~)를 붙인 판정 꾸러미.

judge\\packet_1..4.jsonl   검수자 A·B(Claude)용 — 4묶음
judge\\gpt\\packet_all.jsonl  GPT(코덱스)용 — 같은 453칸 한 파일(사용자가 넘김)
judge\\_key.json           pid → 진짜 칸 id·심은 결함 여부(검수자에게 주지 않음)
"""
import os, sys, json, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa

J = os.path.join(ROOT, 'judge')


def load_stt():
    w, q = {}, {}
    for l in open(os.path.join(DATA, 'stt_whisper.jsonl'), encoding='utf-8'):
        o = json.loads(l); w[o['voice']] = o['text']
    if os.path.exists(os.path.join(DATA, 'stt_qwen.jsonl')):
        for l in open(os.path.join(DATA, 'stt_qwen.jsonl'), encoding='utf-8'):
            o = json.loads(l); q[o['voice']] = o['text']
    return w, q


def item(src, ko, w, q):
    it = {'chap': src['chap'], 'lt': src['lt'], 'spk': src['spk']}
    if src['lt'] == 'sub':
        it['asr_whisper'] = w.get(src['voice'], '')
        it['asr_qwen'] = q.get(src['voice'], '')
    else:
        it['ja'] = flat(src['ja']).strip()
    it['ko'] = flat(ko).strip()
    it['context'] = [{'rel': c['rel'], 'spk': c['spk'], 'ja': c['ja'], 'ko': c['ko']} for c in src['context']]
    return it


def main():
    w, q = load_stt()
    sample = [json.loads(l) for l in open(os.path.join(DATA, 'sample.jsonl'), encoding='utf-8')]
    planted = [json.loads(l) for l in open(os.path.join(DATA, 'planted.jsonl'), encoding='utf-8')]
    # 심은 칸의 문맥은 표본과 같은 꼴로 만든다
    from sample import context, line_type
    import collections
    rows = load_corpus()
    byf = collections.defaultdict(list)
    for r in rows:
        if r['kind'] in ('MSG', 'SUB', 'CHQ', 'CHO'): byf[r['file']].append(r)
    idx = {}
    for f in byf:
        byf[f].sort(key=lambda r: r['seq'])
        for i, r in enumerate(byf[f]): r['_i'] = i; idx[r['id']] = r
    items = []
    for s in sample:
        if s['lt'] == 'sub' and not w.get(s['voice']):
            print('missing whisper', s['id'])
        items.append(('S', s['id'], item(s, s['ko'], w, q)))
    for p in planted:
        r = idx[p['id']]
        src = dict(r); src['lt'] = line_type(r); src['context'] = context(byf, r)
        items.append(('P', p['id'], item(src, p['after'], w, q)))
    rnd = random.Random(1122)
    rnd.shuffle(items)
    key = {}
    os.makedirs(os.path.join(J, 'gpt'), exist_ok=True)
    allp = []
    for n, (kind, cid, it) in enumerate(items, 1):
        pid = 'Q%03d' % n
        key[pid] = {'id': cid, 'planted': kind == 'P'}
        allp.append(dict(pid=pid, **it))
    json.dump(key, open(os.path.join(J, '_key.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    k = 4
    per = (len(allp) + k - 1) // k
    for b in range(k):
        dump_jsonl(allp[b * per:(b + 1) * per], os.path.join(J, 'packet_%d.jsonl' % (b + 1)))
    dump_jsonl(allp, os.path.join(J, 'gpt', 'packet_all.jsonl'))
    print('items', len(allp), 'per packet', per, 'sub items', sum(1 for x in allp if x['lt'] == 'sub'),
          'sub w/o qwen', sum(1 for x in allp if x['lt'] == 'sub' and not x.get('asr_qwen')))


if __name__ == '__main__':
    main()
