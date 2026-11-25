# -*- coding: utf-8 -*-
"""result.json 의 되감기 시간을 갈래별로 모아 본다. 사용: python -I stats.py <out 폴더 이름> [...]"""
import json, os, sys

def stat(v):
    v = sorted(v)
    if not v: return 'n=0'
    return 'n=%d min %.1f med %.1f p90 %.1f max %.1f' % (len(v), v[0], v[len(v) // 2], v[max(0, int(len(v) * 0.9) - 1)], v[-1])

for name in sys.argv[1:]:
    d = json.load(open(os.path.join(r'Y:\AI\forest-qol-test-rewind\out', name, 'result.json'), encoding='utf-8'))
    backs = d['backs']; s = d['summary']
    print('==', name, 'backs', len(backs), 'compared', s.get('compared'), 'pixel diffs', s.get('pixel_diff_count', len(s.get('pixel_diffs', []))),
          'verify same', s.get('verify_same'), 'diff', len(s.get('verify_diff', [])), 'ok', s.get('ok'))
    def cat(b):
        tags = []
        if b['bgm'][0] != b['bgm'][1]: tags.append('곡 바뀜')
        if 'se-loop' in b.get('note', ''): tags.append('환경음')
        if 'subtitle-voice' in b.get('note', ''): tags.append('자막 음성')
        elif 'subtitle-restored' in b.get('note', ''): tags.append('자막')
        if b.get('voice', 0) > 5: tags.append('남은 음성 끊음')
        return ' + '.join(tags) if tags else '소리 일 없음'
    groups = {}
    for b in backs: groups.setdefault(cat(b), []).append(b)
    for k in sorted(groups, key=lambda k: -len(groups[k])):
        g = groups[k]
        if any(b.get('visual', -1) >= 0 for b in g): print('  %-28s screen: %s' % (k, stat([b['visual'] for b in g if b.get('visual', -1) >= 0])))
        print('  %-28s total: %s' % (k, stat([b['total'] for b in g])))
        print('  %-28s   rebuild %s | sound %s | voice %s | key-to-start %s' % ('', stat([b['rebuild'] for b in g]), stat([b['sound'] for b in g]), stat([b.get('voice', 0) for b in g]), stat([b['wake'] for b in g if b['wake'] >= 0])))
    print('  all: total', stat([b['total'] for b in backs]), '| key-to-start', stat([b['wake'] for b in backs if b['wake'] >= 0]), '| kept layers', stat([b['kept'] for b in backs]), '| held', stat([b.get('held', -1) for b in backs]))
    for c in s.get('pixel_diffs', [])[:10]: print('  pixel diff:', c)
    for v in s.get('verify_diff', [])[:6]: print('  verify diff:', v)
    if s.get('checks'):
        for c in s['checks']: print('  %s %s %s' % ('PASS' if c['ok'] else 'FAIL', c['name'], c['extra'][:200]))
    if s.get('resources'):
        for x in s['resources']: print('  res', x)
