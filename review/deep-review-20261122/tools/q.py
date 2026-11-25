import sys, os, json, re, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from sample import excluded_ids, line_type, BROAD, BROAD_KO
rows = load_corpus()
ex = excluded_ids(rows)
samp = {json.loads(l)['id'] for l in open(os.path.join(DATA, 'sample.jsonl'), encoding='utf-8')}
pop = [r for r in rows if r['kind'] == 'MSG' and r['chap'] and not r['changed'] and not r['hold'] and r['id'] not in ex
       and r['id'] not in samp and not BROAD.search(r['ja']) and not BROAD_KO.search(r['ko'])]
lt = sys.argv[2] if len(sys.argv) > 2 else ''
rnd = random.Random(5)
for pat in sys.argv[1].split('||'):
    c = [r for r in pop if re.search(pat, r['ko']) and (not lt or line_type(r) == lt)]
    print('==', pat, len(c))
    for r in rnd.sample(c, min(3, len(c))):
        print('%s|%s|%s|%s\n   JA %s\n   KO %s' % (r['id'], r['chap'], r['spk'], line_type(r), flat(r['ja']), flat(r['ko'])))
