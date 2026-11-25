# -*- coding: utf-8 -*-
import json, re, collections, os
D = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'recheck')
d = json.load(open(os.path.join(D, 'V.json'), encoding='utf-8'))
V, heard = d['V'], d['heard']
clog = {x['id']: x for x in json.load(open(r'C:\Users\CadriacLord\.gemini\antigravity\brain\5a8e551d-80c7-4e24-98ae-0bd89f2eb6a0\scratch\pass3_changelog.json', encoding='utf-8'))}
TOK = re.compile(r'\^(g\d{3}|n|m|c[a-z])')
sh = lambda s: TOK.sub(lambda m: ' / ' if m.group(1) == 'n' else '', s).strip()
out = []
# 1) MECH_QUOTE: 따옴표 말고 바뀐 것이 있나
bad = []
for k, c in clog.items():
    if c['reason'] == 'MECH_QUOTE':
        a = re.sub(r'["「」]', 'Q', c['pass2']); b = re.sub(r'["「」]', 'Q', c['pass3'])
        if a != b: bad.append(k)
out.append('MECH_QUOTE 따옴표 밖 바뀜: %s' % bad)
# 2) 본문(대사)의 ちゃん 옮김 집계: 이름+ちゃん → 한국어
cnt = collections.Counter(); ex = collections.defaultdict(list)
for k, x in V.items():
    if x['kind'] not in ('msg', 'choice_q', 'choice_o'): continue
    for m in re.finditer(r'([一-龥ァ-ヶー]+)ちゃん', x['ja']):
        nm = m.group(1)
        ko = sh(x['cur'])
        form = '쨩' if '쨩' in ko else ('짱' if '짱' in ko else ('양' if re.search(r'[가-힣] ?양', ko) else '기타'))
        spk = x['cur'][:5]
        cnt[(nm, form)] += 1
        if len(ex[(nm, form)]) < 3: ex[(nm, form)].append('%s %s %s' % (k, spk, ko[:60]))
out.append('\n본문 이름+ちゃん 옮김(이름, 꼴): 개수')
for (nm, form), n in sorted(cnt.items(), key=lambda t: (-t[1])):
    out.append('  %s %s: %d  예) %s' % (nm, form, n, ' ‖ '.join(ex[(nm, form)])))
# 3) 자막의 ちゃん(들은 일본어 기준)
out.append('\n자막 ちゃん(제미나이 들은 글 기준):')
for k, x in V.items():
    if x['kind'] == 'sub' and 'ちゃん' in heard.get(k, ''):
        out.append('  %s 들음=%s | 지금=%s' % (k, heard[k][:50], sh(x['cur'])[:60]))
# 4) 몇 칸
for k in ('2400:267', '2400:268', '3081:149', '2100:302', '2300:215', '2400:82'):
    x = V.get(k)
    if x: out.append('\n%s kind=%s 들음=%s\n  JA=%s\n  OLD=%s\n  P2=%s\n  CUR=%s' % (k, x['kind'], heard.get(k, ''), x['ja'], sh(x['old']), sh(x['p2']), sh(x['cur'])))
open(os.path.join(D, 'recheck2.txt'), 'w', encoding='utf-8').write('\n'.join(out))
