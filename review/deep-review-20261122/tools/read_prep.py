import sys, os, json, random, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
rows = {r['id']: r for r in load_corpus()}
F = [json.loads(l) for l in open(os.path.join(DATA, 'findings.jsonl'), encoding='utf-8')]
ROUND = sys.argv[1] if len(sys.argv) > 1 else '1'
NAMES = ('R1', 'R2') if ROUND == '1' else ('R3', 'R4')
KEYF = os.path.join(DATA, '_read_key.json' if ROUND == '1' else '_read_key2.json')
if ROUND != '1':
    done = {v['id'] for v in json.load(open(os.path.join(DATA, '_read_key.json'), encoding='utf-8')).values()}
    F = [o for o in F if o['id'] not in done]
key = json.load(open(os.path.join(DATA, '_judge_key.json'), encoding='utf-8'))
union = {json.loads(l)['id'] for l in open(os.path.join(DATA, 'flags_union.jsonl'), encoding='utf-8')}
J = {}
for n in ('A', 'B'):
    for f in glob.glob(os.path.join(ROOT, 'judge', n, '*.jsonl')):
        for l in open(f, encoding='utf-8'):
            if l.strip(): o = json.loads(l); J.setdefault(o['pid'], []).append(o.get('verdict'))
ctrl = sorted(k['id'] for p, k in key.items() if not k['planted'] and J.get(p) == ['OK', 'OK'] and k['id'] not in union)
rnd = random.Random(7)
ctrl = [c for c in rnd.sample(ctrl, 60) if rows[c]['kind'] == 'MSG'][:30 if ROUND == '1' else 10]
if ROUND != '1': rnd = random.Random(99)
byf = {}
for r in rows.values():
    if r['kind'] in ('MSG', 'SUB'): byf.setdefault(r['file'], []).append(r)
for f in byf: byf[f].sort(key=lambda x: x['seq'])
def prev(i):
    r = rows[i]; L = byf[r['file']]
    if r not in L: return ''
    k = L.index(r)
    return flat(L[k - 1]['ko']) if k > 0 else ''
items1, items2 = [], []
for o in F:
    items1.append(('F', o['id'], flat(o['now']))); items2.append(('F', o['id'], flat(o['fix'])))
for c in ctrl:
    items1.append(('C', c, flat(rows[c]['ko']))); items2.append(('C', c, flat(rows[c]['ko'])))
k = {}
for name, its in ((NAMES[0], items1), (NAMES[1], items2)):
    rnd.shuffle(its)
    out = []
    for n, (t, i, ko) in enumerate(its, 1):
        rid = '%s-%03d' % (name, n)
        k[rid] = {'type': t, 'id': i}
        out.append({'rid': rid, 'before': prev(i), 'line': ko})
    dump_jsonl(out, os.path.join(ROOT, 'read', name + '.jsonl'))
json.dump(k, open(KEYF, 'w', encoding='utf-8'), ensure_ascii=False)
print(len(items1), len(items2), 'controls', len(ctrl))
