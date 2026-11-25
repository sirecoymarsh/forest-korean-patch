# -*- coding: utf-8 -*-
"""판정 모으기 → 오역 목록(제미나이에게 넘길 꼴) + 요약.

결과
  ..\\오역목록_제미나이최신본.md      사람이 읽는 목록(IV장 이후 내용 포함 — 사용자 진도 주의)
  ..\\data\\errors.json               같은 내용(기계용)
  ..\\data\\aggregate_summary.json    개수
사용자 결정(11-21 「오역만 잡으란거야」): 말맛(STYLE)·지나친 교정 되돌림·따옴표·물결표·줄표 길이는 오역 목록에서 뺀다.
"""
import json, glob, os, re, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'data')
TOK = re.compile(r'\^(g\d{3}|n|m|c[a-z])')

CAT_KO = {'meaning': '뜻이 틀림', 'omission': '빠짐', 'addition': '원문에 없는 보탬', 'pronoun': '인칭·지칭', 'direction': '방향(주다/받다·능동/수동)',
          'register': '말투(높임·반말·인물 말씨)', 'term': '표기·용어 결정 위반', 'korean': '한국어 흠(비문·오자·어색)'}
ERROR_CATS = {'meaning', 'omission', 'addition', 'pronoun', 'direction', 'register', 'term'}


def show(s):
    return TOK.sub(lambda m: ' / ' if m.group(1) == 'n' else '', s).strip()


def main():
    rows = {}
    for l in open(os.path.join(D, 'changes.jsonl'), encoding='utf-8'):
        r = json.loads(l)
        rows['%d:%d' % (r['file'], r['slot'])] = r
    heard = {}
    for p in glob.glob(os.path.join(D, 'packets', 'sub_*.jsonl')):
        for l in open(p, encoding='utf-8'):
            it = json.loads(l)
            heard[it['id']] = it.get('gemini_heard_ja') or it.get('stt_ja') or ''
    verdicts = {}
    for p in sorted(glob.glob(os.path.join(D, 'verdicts', '*.jsonl'))):
        for l in open(p, encoding='utf-8'):
            if l.strip():
                v = json.loads(l)
                v['_packet'] = os.path.basename(p)[:-6]
                verdicts[v['id']] = v
    # 통합 세션이 다시 읽고 오역이 아니라고 본 칸(11-21): 2100:478 은 new 가 원문(お乗りなさい・配ってください)에 더 가깝고,
    # 2300:370 은 「안녕하십니까/안녕하심까」 차이뿐.
    EXCLUDE = {'2100:478', '2300:370'}
    decision = collections.defaultdict(list)   # 결정 항목: 이름 → [id]
    errors, korean, listen, hold = [], [], [], []
    for vid, v in verdicts.items():
        r = rows.get(vid)
        if r is None or vid in EXCLUDE:
            continue
        ja = r['ja'] or ''
        new, old = r['new'], r['old']
        vd, cat = v['verdict'], v.get('cat', '')
        if vd == 'HOLD':
            hold.append(vid); continue
        if vd == 'LISTEN':
            listen.append((vid, v)); continue
        # 결정 항목으로 돌리는 것(오역 아님)
        if '借り暮らし' in ja or '借りぐらし' in ja or '빌려 사는 소인' in new:
            decision['borrowers'].append(vid); continue
        if r['file'] == 3111 and ('오빠' in old and '너' in new):
            decision['oppa'].append(vid); continue
        if '아타시' in new:
            decision['atashi'].append(vid); continue
        if '쨩' in new and '쨩' not in old:
            decision['chan'].append(vid); continue
        # やれくそ → 어이쿠야(짜증이 놀람으로) — 갈래마다 판정이 갈려 여기서 하나로
        if 'やれくそ' in ja and '어이쿠' in new and '어이쿠' not in old:
            errors.append({'id': vid, 'cat': 'meaning', 'why': 'やれくそ(짜증·자포자기)를 「어이쿠야」(놀람)로 바꿈 — 같은 말버릇 전부',
                           'fix': '옛 판 그대로: ' + show(old), 'v': v, 'r': r}); continue
        if vd in ('REVERT', 'FIX') and cat in ERROR_CATS:
            fix = v.get('fix') or ''
            errors.append({'id': vid, 'cat': cat, 'why': v.get('why', ''), 'fix': show(fix) if fix else '옛 판 그대로: ' + show(old), 'v': v, 'r': r})
        elif vd in ('REVERT', 'FIX') and cat == 'korean':
            fix = v.get('fix') or ''
            korean.append({'id': vid, 'cat': cat, 'why': v.get('why', ''), 'fix': show(fix) if fix else '옛 판 그대로: ' + show(old), 'v': v, 'r': r})
    errors.sort(key=lambda e: (e['r']['chapter'] or 99, e['r']['file'], e['r']['slot']))
    korean.sort(key=lambda e: (e['r']['chapter'] or 99, e['r']['file'], e['r']['slot']))
    mech = [json.loads(l) for l in open(os.path.join(D, 'mech.jsonl'), encoding='utf-8')]
    quote = [m for m in mech if any(f == 'QUOTE' for f, _ in m['flags'])]
    latin = [m for m in mech if any(f == 'HALF_LATIN' for f, _ in m['flags'])]

    def line(e):
        r = e['r']
        ja = r['ja'] or (('[음성] ' + heard.get(e['id'], '')) if r['lane'] == 'sub' else '')
        return '| %s | %s | %s | %s | %s | %s |' % (
            r['chapter'] or '-', e['id'], show(ja).replace('|', '｜') or '—', show(r['new']).replace('|', '｜'),
            (CAT_KO.get(e['cat'], e['cat']) + ' — ' + e['why']).replace('|', '｜'), e['fix'].replace('|', '｜'))

    md = ['# Forest 제미나이 최신본(11-21) 오역 목록', '',
          '검수: Claude, 2026-11-21. 대상은 제미나이가 고친 칸 3,219개(대사 1,804 · 음성 자막 657묶음 · 선택지 49 · 크레딧·컨티뉴 50)이고,',
          '고치지 않은 칸은 보지 않았다. 판정 근거는 일본어 원문(자막은 음성 — 제미나이 받아쓰기와 Whisper 받아쓰기를 맞대 봄).',
          '**말맛만 다른 것·「원문에 더 가깝게」 고친 것·따옴표/물결표/줄표 모양은 오역이 아니므로 뺐다.** 이 파일에는 IV장 이후 내용이 들어 있다.', '',
          '## 개수', '',
          '| 무엇 | 개수 |', '|---|---|',
          '| 오역(뜻·빠짐·보탬·인칭·방향·말투·표기 결정) | %d |' % len(errors),
          '| 한국어 흠(비문·오자·어색함) | %d |' % len(korean),
          '| 직접 들어 볼 자막(두 받아쓰기가 갈리고 문맥으로 못 가림) | %d |' % len(listen),
          '| 결정이 필요한 것(오역 아님) | %d묶음 |' % len([k for k in decision if decision[k]]),
          '| 표기 규칙 위반: 따옴표 `"`→「」 / 전각 로마자→반각 | %d / %d칸 |' % (len(quote), len(latin)),
          '| 정책상 검수하지 않은 칸(미성숙하게 묘사된 인물의 성적 장면) | %d |' % len(hold), '']
    bycat = collections.Counter(e['cat'] for e in errors)
    md.append('오역 종류: ' + ', '.join('%s %d' % (CAT_KO[c], n) for c, n in bycat.most_common()))
    md += ['', '## 1. 오역', '', '| 장 | 대본:슬롯 | 일본어 | 제미나이 판 | 무엇이 틀렸나 | 고칠 안 |', '|---|---|---|---|---|---|']
    md += [line(e) for e in errors]
    md += ['', '## 2. 한국어 흠(오역은 아니지만 고칠 것)', '', '| 장 | 대본:슬롯 | 일본어 | 제미나이 판 | 무엇 | 고칠 안 |', '|---|---|---|---|---|---|']
    md += [line(e) for e in korean]
    md += ['', '## 3. 직접 들어 볼 자막', '']
    for vid, v in sorted(listen, key=lambda x: (rows[x[0]]['chapter'] or 99, rows[x[0]]['file'], rows[x[0]]['slot'])):
        r = rows[vid]
        md.append('- %s(장 %s, 음성 %s): %s — 제미나이 판 「%s」' % (vid, r['chapter'], r['voice'], v.get('why', ''), show(r['new'])))
    md += ['', '## 4. 결정이 필요한 것(오역 아님)', '']
    if decision['borrowers']:
        md.append('- **借り暮らし 표기** (%d칸): 제미나이가 「빌려 사는 소인(들)」로 한꺼번에 통일. 옛 판은 바로우어즈·소인족·더부살이·빌려 살기 족·마루 밑 작은 사람들로 제각각이었고, 예전 결정은 「빌려 사는 일족」(보통명사화 의도). 하나로 정해 주세요. 칸: %s' % (len(decision['borrowers']), ', '.join(sorted(decision['borrowers']))))
    if decision['atashi']:
        md.append('- **토룬가 あたし 말장난** (%d칸): 남자가 여자 말씨 あたし 를 쓰는 데서 나오는 농담. 제미나이는 「아타시」로 소리를 남겼고(농담은 통하나 일본어가 남음), 옛 판 「나」는 「“나”라니 이상해요」가 안 통함. 한국어로 겹치는 말이 없는 말장난 — 어느 쪽을 잃을지 골라 주세요. 칸: %s' % (len(decision['atashi']), ', '.join(sorted(decision['atashi']))))
    if decision['chan']:
        md.append('- **자막의 ちゃん** (%d칸): 제미나이가 「쨩」으로 넣음. 본문 번역은 대부분 「양」(카코 양·마유즈미 양 등, 옛 판 한 곳만 「마유즈미 쨩」). 한쪽으로 정해 주세요. 칸: %s' % (len(decision['chan']), ', '.join(sorted(decision['chan']))))
    if decision['oppa']:
        md.append('- **3111 나가츠키가 아케루를 부르는 あんた** (%d칸): 옛 판 「오빠」 → 제미나이 「너」. 원문은 あんた 라 「너」가 원문에 가깝고 「오빠」는 옛 판의 보탬. 취향 문제. 칸: %s' % (len(decision['oppa']), ', '.join(sorted(decision['oppa']))))
    md += ['', '## 5. 표기 규칙 위반(오역 아님, 기계 검사)', '',
           '- 따옴표: ASCII `"`를 「」로 바꾼 칸 %d개 — 사용자 결정 「따옴표는 그대로」(8/8)에 어긋남. 칸: %s' % (len(quote), ', '.join('%d:%d' % (m['file'], m['slot']) for m in quote)),
           '- 전각 로마자를 반각으로 바꾼 칸 %d개 — 굴림에서 반각 로마자가 겹쳐 찍혀 전각으로 고쳐 둔 것. 칸: %s' % (len(latin), ', '.join('%d:%d' % (m['file'], m['slot']) for m in latin)),
           '', '## 6. 검수하지 않은 칸', '',
           '- 정책상 보류 %d칸: 어리게 묘사된 인물의 성적 장면(2301·2302·3039 대부분과 3031:189·3073:85·3081:46·53·57). 판정도 고칠 안도 내지 않았다.' % len(hold), '']
    open(os.path.join(ROOT, '오역목록_제미나이최신본.md'), 'w', encoding='utf-8').write('\n'.join(md))
    out = [{'id': e['id'], 'chapter': e['r']['chapter'], 'lane': e['r']['lane'], 'cat': e['cat'], 'ja': e['r']['ja'], 'gemini': e['r']['new'],
            'old': e['r']['old'], 'why': e['why'], 'fix': e['fix']} for e in errors + korean]
    json.dump(out, open(os.path.join(D, 'errors.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    early = [e for e in errors if (e['r']['chapter'] or 99) <= 3]
    summ = {'errors': len(errors), 'korean': len(korean), 'listen': len(listen), 'hold': len(hold), 'quote': len(quote), 'latin': len(latin),
            'by_cat': bycat, 'errors_ch1_3': len(early), 'decision': {k: len(v) for k, v in decision.items()}}
    json.dump(summ, open(os.path.join(D, 'aggregate_summary.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(summ, ensure_ascii=False))


if __name__ == '__main__':
    main()
