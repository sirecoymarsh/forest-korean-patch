# -*- coding: utf-8 -*-
"""시험 결과(out\\<이름>\\result.json·run.log)를 표 한 줄씩으로 뽑는다. 숫자를 손으로 옮겨 적지 않으려는 것.
사용: python -I results_table.py <이름> [<이름> …]"""
import json, os, re, sys

OUT = r'Y:\AI\forest-qol-test-rewind\out'


def one(name):
    d = os.path.join(OUT, name)
    log = open(os.path.join(d, 'run.log'), encoding='utf-8', errors='replace').read().splitlines() if os.path.exists(os.path.join(d, 'run.log')) else []
    s = {}
    p = os.path.join(d, 'result.json')
    if os.path.exists(p): s = json.load(open(p, encoding='utf-8'))['summary']
    npass = sum(1 for l in log if ' PASS ' in l); nfail = sum(1 for l in log if ' FAIL ' in l)
    cmpn = s.get('compared'); cmpd = s.get('pixel_diff_count')
    quit_ok = any('quit normally' in l for l in log); code = [l for l in log if 'exit code' in l]
    client = next((m.group(1) for l in log for m in [re.search(r'client \((\d+, \d+)\)', l)] if m), '')
    return dict(name=name, client=client, checks=s.get('checks_passed') or ('%d/%d' % (npass, npass + nfail) if npass + nfail else ''), fails=[l[9:200] for l in log if ' FAIL ' in l],
                compared=cmpn, differing=cmpd, diffs=[(c['tag'], c['id'], c['n'], c.get('box')) for c in (s.get('pixel_diffs') or [])],
                verify_same=s.get('verify_same'), verify_diff=len(s.get('verify_diff') or []), backs=s.get('backs'),
                visual=s.get('visual_ms'), second_try=len(s.get('same_on_second_try') or []), partial=s.get('partial_captures'), retries=s.get('capture_retries'),
                quit=quit_ok, exit=(code[-1].split('exit code')[-1].strip() if code else ''), dropped=[l[9:160] for l in log if 'request dropped' in l][:3])


rows = [one(n) for n in sys.argv[1:]]
for r in rows:
    v = r['visual']
    print('%-6s client %-11s checks %-7s compares %s (differing %s, same on 2nd try %s, partly empty captures %s, retries %s) verify same %s diff %s | backs %s screen ms %s | quit %s exit %s' % (
        r['name'], r['client'], r['checks'], r['compared'], r['differing'], r['second_try'], r['partial'], r['retries'], r['verify_same'], r['verify_diff'], r['backs'],
        ('%.1f/%.1f/%.1f (min/med/max)' % (v['min'], v['med'], v['max'])) if v else '-', r['quit'], r['exit']))
    for f in r['fails']: print('       FAIL', f)
    for d in r['diffs'][:12]: print('       diff', d)
print('total verify same', sum(r['verify_same'] or 0 for r in rows), 'different', sum(r['verify_diff'] or 0 for r in rows))
