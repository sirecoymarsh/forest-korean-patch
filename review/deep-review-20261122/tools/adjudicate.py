# -*- coding: utf-8 -*-
"""사람 확정(16칸 중 15칸 확정, 2500:2592 기각)으로 표본 오류율·포획-재포획 추정."""
import os, sys, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import score
CONF = {'2500:3017': 'minor', '2500:2665': 'minor', '2700:442': 'minor', '2900:18': 'minor', '2500:891': 'minor', '2500:928': 'minor',
        '2700:378': 'minor', '2500:2925': 'minor', '2801:49': 'minor', '2500:1203': 'minor', '2600:1019': 'minor', '2600:494': 'major',
        '2500:614': 'minor', '2600:359': 'minor', '2500:1727': 'minor'}
REJ = {'2500:2592'}
U = [json.loads(l) for l in open(os.path.join(DATA, 'flags_union.jsonl'), encoding='utf-8')]
byA = {u['id'] for u in U if 'A' in u['by']} & set(CONF)
byB = {u['id'] for u in U if 'B' in u['by']} & set(CONF)
m = len(byA & byB)
n1, n2 = len(byA), len(byB)
chap = (n1 + 1) * (n2 + 1) / (m + 1) - 1
var = (n1 + 1) * (n2 + 1) * (n1 - m) * (n2 - m) / ((m + 1) ** 2 * (m + 2))
hold = ['2801:33', '2100:955', '2801:127']
for h in hold: score.SAMPLE.pop(h, None)
N = len(score.SAMPLE)
f1 = {i: (i in CONF) for i in score.SAMPLE}
f5 = {i: (CONF.get(i) == 'major') for i in score.SAMPLE}
e1 = score.strat_rate(f1); e5 = score.strat_rate(f5)
w1 = score.wilson(sum(f1.values()), N); w5 = score.wilson(sum(f5.values()), N)
res = {'n': N, 'confirmed': len(CONF), 'major': sum(1 for v in CONF.values() if v == 'major'), 'rejected': len(REJ),
       'A_found': n1, 'B_found': n2, 'both': m, 'chapman_N': round(chap, 1), 'chapman_se': round(math.sqrt(var), 1),
       'rate_minor_strat': [round(100 * x, 2) for x in e1], 'rate_minor_wilson': [round(100 * x, 2) for x in w1],
       'rate_major_strat': [round(100 * x, 2) for x in e5], 'rate_major_wilson': [round(100 * x, 2) for x in w5],
       'rate_minor_capture_recapture': round(100 * chap / N, 2),
       'pop_N': score.POP['N']}
json.dump(res, open(os.path.join(DATA, 'adjudicated.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
