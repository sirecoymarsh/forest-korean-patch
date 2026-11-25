# -*- coding: utf-8 -*-
"""음성 자막: 성격이 다른 받아쓰기 둘(Whisper large-v3 = 인코더·디코더 / Qwen3-ASR-1.7B = 오디오 인코더+LLM)을
가나 읽기로 맞춰 대조하고, 갈린 음성만 들어 보는 페이지를 만든다.

판정 규칙
 - 둘 다 pykakasi 로 히라가나 읽기로 바꾸고 문장부호·공백을 걷은 뒤 difflib 비율 r 을 잰다.
 - r < 0.80 이면 「갈림」. Whisper 환각 문구(ご視聴ありがとうございました 류)나 한쪽이 빈 것도 갈림.
 - 제미나이 받아쓰기(ja_heard, 번역에 쓴 것)도 같이 재서, 제미나이가 어느 쪽에 가까운지 적는다.
→ data\\voice_compare.jsonl · out\\voice\\<대본>.html (+ out\\voice\\ogg\\ 상대 경로 음성)
"""
import os, sys, re, json, difflib, shutil, collections, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa
import pykakasi

KK = pykakasi.kakasi()
HALL = re.compile(r'ご視聴|ありがとうございました。?$|チャンネル登録|字幕')


def kana(t):
    t = re.sub(r'[\s、。，．,.!！?？…‥・「」『』（）()〜～ー―─\-"\'“”]', '', t or '')
    return ''.join(x['hira'] for x in KK.convert(t))


def ratio(a, b):
    a, b = kana(a), kana(b)
    if not a and not b: return 1.0
    if not a or not b: return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def main():
    rows = [r for r in load_corpus() if r['kind'] == 'SUB']
    W = {json.loads(l)['voice']: json.loads(l) for l in open(os.path.join(DATA, 'stt_whisper.jsonl'), encoding='utf-8')}
    Q = {json.loads(l)['voice']: json.loads(l) for l in open(os.path.join(DATA, 'stt_qwen.jsonl'), encoding='utf-8')}
    ad = set(json.load(open(os.path.join(DATA, 'adult.json'), encoding='utf-8'))['ids'])
    byv = collections.OrderedDict()
    for r in sorted(rows, key=lambda r: (r['file'], r['seq'])):
        byv.setdefault(r['voice'], []).append(r)
    out = []
    for v, rs in byv.items():
        w = (W.get(v) or {}).get('text', ''); q = (Q.get(v) or {}).get('text', '')
        g = ' '.join(x['gem_heard'] for x in rs if x['gem_heard'])
        # 제미나이 ja_heard 는 묶음 자막마다 같은 음성 전체를 적은 경우가 많다 → 중복 제거
        gs = []
        for x in rs:
            if x['gem_heard'] and x['gem_heard'] not in gs: gs.append(x['gem_heard'])
        g = ''.join(gs)
        rwq = ratio(w, q)
        hall = bool(HALL.search(w))
        split = rwq < 0.80 or hall or not w.strip() or not q.strip()
        interj = max(len(kana(w)), len(kana(q))) <= 5
        o = {'voice': v, 'ids': [x['id'] for x in rs], 'file': rs[0]['file'], 'chap': rs[0]['chap'],
             'hold': any(x['hold'] for x in rs) or any(x['id'] in ad for x in rs),
             'dur': (W.get(v) or {}).get('dur'), 'whisper': w, 'qwen': q, 'gemini': g,
             'r_wq': round(rwq, 3), 'r_gw': round(ratio(g, w), 3), 'r_gq': round(ratio(g, q), 3),
             'whisper_hallucination': hall, 'split': split, 'interjection': interj,
             'ko': ' ‖ '.join(flat(x['ko']) for x in rs),
             'en': ' ‖ '.join(x['en'] for x in rs), 'changed': any(x['changed'] for x in rs)}
        out.append(o)
    dump_jsonl(out, os.path.join(DATA, 'voice_compare.jsonl'))
    sp = [o for o in out if o['split']]
    print('substantive split', sum(1 for o in sp if not o['interjection']))
    print('voices', len(out), 'split', len(sp), 'hallucination', sum(o['whisper_hallucination'] for o in out),
          'hold', sum(1 for o in sp if o['hold']))
    print('r_wq dist', collections.Counter(round(o['r_wq'], 1) for o in out))
    print('gemini closer: whisper', sum(1 for o in sp if o['r_gw'] > o['r_gq']), 'qwen', sum(1 for o in sp if o['r_gq'] > o['r_gw']))
    # 페이지
    od = os.path.join(OUT, 'voice'); os.makedirs(os.path.join(od, 'ogg'), exist_ok=True)
    byf = collections.defaultdict(list)
    for o in sp: byf[o['file']].append(o)
    idx = []
    for f, os_ in sorted(byf.items()):
        ch = os_[0]['chap']
        rowsh = []
        for o in os_:
            src = os.path.join(ROOT, 'voice', '%04d.ogg' % o['voice'])
            dst = os.path.join(od, 'ogg', '%04d.ogg' % o['voice'])
            if o['hold']:
                rowsh.append('<tr class="hold"><td>%s</td><td>%04d</td><td colspan="5">정책 보류 구간 — 음성·글 생략</td></tr>' % (' '.join(o['ids']), o['voice']))
                continue
            if not os.path.exists(dst): shutil.copyfile(src, dst)
            e = html.escape
            rowsh.append('<tr><td>%s</td><td>%04d<br><small>%.1f초 · 일치 %.2f%s</small></td>'
                         '<td><audio controls preload="none" src="ogg/%04d.ogg"></audio></td>'
                         '<td class="ja">%s</td><td class="ja">%s</td><td class="ja g">%s</td><td class="ko">%s<div class="en">%s</div></td></tr>' % (
                             '<br>'.join(o['ids']), o['voice'], o['dur'] or 0, o['r_wq'], ' · Whisper 환각' if o['whisper_hallucination'] else '',
                             o['voice'], e(o['whisper']), e(o['qwen']), e(o['gemini']), e(o['ko']), e(o['en'])))
        warn = '' if ch in SAFE_CH else '<p class="warn">⚠ %s장 — 아직 플레이하지 않은 장입니다. 진도 뒤에 여세요.</p>' % ch
        page = PAGE.format(title='Forest 자막 %s (%s장) — 받아쓰기 갈린 %d개' % (f, ch, len(os_)), warn=warn, rows='\n'.join(rowsh))
        open(os.path.join(od, '%s.html' % f), 'w', encoding='utf-8').write(page)
        idx.append((f, ch, len(os_)))
    lis = '\n'.join('<li><a href="%s.html">%s</a> — %s장, %d개%s</li>' % (f, f, ch, n, '' if ch in SAFE_CH else ' ⚠ 진도 뒤') for f, ch, n in idx)
    open(os.path.join(od, 'index.html'), 'w', encoding='utf-8').write(INDEX.format(n=len(sp), tot=len(out), lis=lis))
    print('pages', len(idx))


PAGE = '''<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>{title}</title>
<style>
:root{{--bg:#fff;--fg:#1d1d1f;--mut:#666;--line:#ddd;--ja:#f6f7fb;--g:#fff7e8;--hold:#eee}}
@media (prefers-color-scheme: dark){{:root{{--bg:#161616;--fg:#eee;--mut:#aaa;--line:#333;--ja:#1f2230;--g:#2a2416;--hold:#222}}}}
body{{background:var(--bg);color:var(--fg);font:14px/1.5 "Malgun Gothic",sans-serif;margin:16px}}
table{{border-collapse:collapse;width:100%}} td,th{{border:1px solid var(--line);padding:6px;vertical-align:top}}
th{{position:sticky;top:0;background:var(--bg)}} .ja{{background:var(--ja)}} .g{{background:var(--g)}} .en{{color:var(--mut);font-size:12px;margin-top:4px}}
.hold td{{background:var(--hold);color:var(--mut)}} .warn{{color:#c33;font-weight:bold}} small{{color:var(--mut)}}
</style></head><body><h1>{title}</h1>{warn}
<p>두 기계 받아쓰기(성격이 다른 모델)가 갈린 음성만 모았다. 들어 보고 한국어 자막(오른쪽)이 실제 음성과 맞는지 본다. 제미나이 열은 번역에 쓴 받아쓰기.</p>
<table><tr><th>칸</th><th>음성</th><th>재생</th><th>Whisper large-v3</th><th>Qwen3-ASR</th><th>제미나이가 들은 것</th><th>지금 한국어 자막 (영문 패치)</th></tr>
{rows}</table></body></html>'''
INDEX = '''<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>Forest 자막 듣기 목록</title>
<style>body{{font:15px/1.6 "Malgun Gothic",sans-serif;margin:16px}}</style></head><body>
<h1>Forest 음성 자막 — 받아쓰기 갈린 {n}개 / 전체 {tot}개 음성</h1><ul>{lis}</ul></body></html>'''

if __name__ == '__main__':
    main()
