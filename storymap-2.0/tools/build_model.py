# -*- coding: utf-8 -*-
"""Forest 이야기의 지도 — 표시 모델 + 배치 생성.

입력
  구조: Codex 분석(story-map.json, forest-full-flow.json, scripts_ko.json)
        명령부는 game_ko 와 forest-kr-build 가 103개 모두 같다(2026-10-10 확인).
  문구: 최신 한국어판 forest-kr-build\\game\\scr (질문·선택지 슬롯을 그대로 읽는다)
출력
  data\\model.json  — 차트 자료와 배치(캔버스 좌표). 시안 그림과 게임 안 렌더러가 같이 쓴다.
"""
import json, os, sys, collections, hashlib, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import gscread

CODEX = r'P:\AI\Codex\projects\forest-flowchart'
GAME = os.environ.get('FC_GAME', r'P:\AI\forest-kr-build\game')
OUT = os.path.join(ROOT, 'data', 'model.json')

story = json.load(open(os.path.join(CODEX, r'work\ingame-chart\story-map.json'), encoding='utf-8-sig'))
flow = json.load(open(os.path.join(CODEX, r'outputs\forest-full-flow.json'), encoding='utf-8-sig'))
parsed = json.load(open(os.path.join(CODEX, r'work\scripts_ko.json'), encoding='utf-8-sig'))

CONTROL = {'JUMP', 'JUMP_IF_ZERO', 'JUMP_IF_NONZERO', 'CHOICE', 'RETURN', 'STOP', 'LOAD_SCRIPT'}
HELPER = lambda s: s.startswith('05') or s.startswith('06') or s.startswith('00') or s.startswith('01')

# ---------------------------------------------------------------- 스크립트
gsc = {}
for sid in parsed:
    p = os.path.join(GAME, 'scr', sid + '.gsc')
    gsc[sid] = gscread.load(p)
    # 명령부 동일성: Codex 가 해석한 명령 오프셋이 그대로 맞아야 한다
    assert len(gsc[sid].code) == parsed[sid]['header'][2], sid

cmds = {sid: sorted(parsed[sid]['commands'], key=lambda c: c['offset']) for sid in parsed}
cmd_at = {sid: {c['offset']: i for i, c in enumerate(cmds[sid])} for sid in parsed}


def strings(sid):
    return gsc[sid].strings


def clean(s):
    """화면 문구에서 제어 토큰을 걷어 낸다."""
    s = re.sub(r'\^g\d{3}', '', s)
    s = re.sub(r'\^c[a-z]', '', s)
    s = s.replace('^n', ' ').replace('^m', '')
    return s.strip()


def messages_of(sid):
    return [c for c in cmds[sid] if c['name'] == 'MESSAGE']


def walk_witness(sid, kpc, limit=3):
    """선택지 목적지부터 갈림 명령까지의 대사 슬롯(그 선택지에만 있는 대사).

    목적지는 대개 「무조건 점프」 토막이라 점프는 따라간다. 조건 점프·선택·반환에서 멈춘다.
    """
    i = cmd_at[sid].get(kpc)
    if i is None:
        return [], None
    out = []
    sub = None
    steps = 0
    while i is not None and i < len(cmds[sid]) and steps < 4000:
        steps += 1
        c = cmds[sid][i]
        if c['name'] == 'JUMP':
            i = cmd_at[sid].get(c['args'][0])
            continue
        if c['name'] in CONTROL:
            break
        if c['name'] == 'CALL_SCRIPT':
            t = '%04d' % c['args'][0]
            if not HELPER(t) and t in parsed:
                sub = t
                break
        if c['name'] == 'MESSAGE':
            out.append([sid, c['args'][5]])
            if len(out) >= limit:
                break
        i += 1
    return out, sub


def pre_witness(sid, kpc, limit=2):
    """선택 명령 바로 앞에서 그 선택으로 곧장 흘러드는 대사(선택에 닿았다는 증거)."""
    i = cmd_at[sid][kpc] - 1
    out = []
    while i >= 0 and len(out) < limit:
        c = cmds[sid][i]
        if c['name'] in ('JUMP', 'RETURN', 'STOP', 'LOAD_SCRIPT', 'CHOICE'):
            break
        if c['name'] == 'MESSAGE':
            out.append([sid, c['args'][5]])
        i -= 1
    return out


# ---------------------------------------------------------------- 흐름 그래프
graphs = flow['graphs']
gnode = {}
gout = collections.defaultdict(list)
for sid, g in graphs.items():
    for n in g['nodes']:
        gnode[n['id']] = n
    for e in g['edges']:
        gout[e['from']].append(e)


def is_restart(effects):
    for e in effects or []:
        lhs = e.get('lhs')
        if lhs == ['v', 3999] and e.get('rhs') not in (0, None):
            return True
    return False


def resolve(node_id, effects, depth=0, seen=None):
    """호출 노드 뒤를 따라가 다음 선택/끝/재시작/중단을 찾는다."""
    seen = seen or set()
    if node_id in seen or depth > 40:
        return []
    seen = seen | {node_id}
    n = gnode.get(node_id)
    if not n:
        return []
    k = n['kind']
    if k == 'choice':
        return [{'k': 'choice', 'node': node_id}]
    if k == 'return':
        return [{'k': 'restart' if is_restart(effects) else 'end'}]
    if k == 'stop':
        return [{'k': 'stop'}]
    if k == 'load':
        return [{'k': 'end'}]
    res = []
    calls = []
    if k == 'call':
        t = n.get('target')
        if t and not HELPER(t):
            calls.append(t)
    for e in gout.get(node_id, []):
        for r in resolve(e['to'], (effects or []) + (e.get('effects') or []), depth + 1, seen):
            if calls:
                r = dict(r, sub=calls[0])
            res.append(r)
    return res


# ---------------------------------------------------------------- 장·장면
roman = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX']
chapters = []
scene_info = {s['id']: s for s in story['scenes']}
for i, c in enumerate(story['chapters']):
    chapters.append({'id': c['id'], 'n': i + 1, 'title': c['title'], 'scenes': list(c['scenes'])})

calls_to = collections.defaultdict(list)
for c in flow['calls']:
    calls_to[c['target']].append(c['source'])

scenes = {}
for s in story['scenes']:
    sid = s['id']
    msgs = messages_of(sid)
    slots = [m['args'][5] for m in msgs]
    exits = []
    for b in s.get('completion_boundaries') or []:
        before = [m for m in msgs if m['offset'] < b]
        if before:
            exits.append(before[-1]['args'][5])
    if not exits and msgs:
        exits.append(msgs[-1]['args'][5])
    scenes[sid] = {
        'id': sid, 'chapter': s['chapter'], 'title': s['title'],
        'kind': 'sub' if s['kind'] == 'neutral_subscene' else ('main' if sid[0] == '2' else 'story'),
        'slots': slots, 'exit_slots': sorted(set(exits)),
        'first_slots': slots[:2],
        'callers': sorted(set(calls_to.get(sid, []))),
        'choices': [],
    }

# 곁가지 장면의 주인
for sid, s in scenes.items():
    if s['kind'] == 'sub':
        par = [c for c in s['callers'] if c in scenes and scenes[c]['kind'] != 'sub']
        s['parent'] = par[0] if par else None

# ---------------------------------------------------------------- 선택
choices = {}
alias = {}
for ch in story['choices']:
    if ch['category'] != 'story':
        continue
    sid = ch['script']
    kpc = ch['korean_pc']
    c = cmds[sid][cmd_at[sid][kpc]]
    assert c['name'] == 'CHOICE', (ch['id'], c)
    a = c['args']
    n = a[0]
    st = strings(sid)
    q_slot = a[1]
    opts = []
    for o in ch['options']:
        idx = o['index']
        slot = a[7 + idx - 1]
        tgt = a[2 + idx - 1]
        assert tgt == o['target_korean'], (ch['id'], idx, tgt, o['target_korean'])
        wit, sub = walk_witness(sid, tgt)
        outs = []
        for oc in o['outcomes']:
            k = oc['kind']
            if k == 'choice':
                outs.append({'k': 'choice', 'node': oc['node']})
            elif k == 'return':
                outs.append({'k': 'restart' if is_restart(oc.get('effects')) else 'end'})
            elif k == 'stop':
                outs.append({'k': 'stop'})
            elif k == 'call':
                outs += resolve(oc['node'], oc.get('effects'))
            else:
                outs.append({'k': k})
        tags = []
        cl = o['classification']
        if '난수 관여' in cl:
            tags.append('random')
        if '이전 조건에 따라 분기' in cl:
            tags.append('cond')
        if '후반 조건' in cl:
            tags.append('late')
        if '선택 목록 이동' in cl:
            tags.append('nav')
        if sub is None:
            for oc in outs:
                if oc.get('sub'):
                    sub = oc['sub']
        if sub and not wit and sub in scenes:
            wit = [[sub, x] for x in scenes[sub]['first_slots']]
        opts.append({'idx': idx, 'src': [ch['id'], idx], 'slot': slot, 'label': clean(st[slot]), 'target': tgt,
                     'witness': wit, 'sub': sub, 'outs': outs, 'tags': tags})
    # 다른 갈래와 겹치는 대사는 증거가 못 된다
    cnt = collections.Counter(tuple(w) for o in opts for w in o['witness'])
    reach = [list(w) for w in dict.fromkeys(tuple(w) for o in opts for w in o['witness'])]
    # 질문 문구에도 읽음 비트가 서는 일이 있다 — 다른 대사가 같은 슬롯을 쓰지 않을 때만 증거로
    if not any(m['args'][5] == q_slot for m in messages_of(sid)):
        reach.append([sid, q_slot])
    for o in opts:
        o['witness'] = [w for w in o['witness'] if cnt[tuple(w)] == 1]
    choices[ch['id']] = {'id': ch['id'], 'script': sid, 'chapter': ch['chapter'], 'kpc': kpc,
                         'q_slot': q_slot, 'question': clean(st[q_slot]), 'options': opts,
                         'pages': [kpc], 'page_ids': [ch['id']], 'pre': pre_witness(sid, kpc), 'reach': reach}

# 쪽 넘김(「다음 선택지」/「이전 선택지」)으로 이어진 같은 단어 목록은 한 칸으로 합친다
for cid, c in list(choices.items()):
    if cid not in choices:
        continue
    nxt = [o for o in c['options'] if 'nav' in o['tags'] and o['label'].startswith('다음')]
    if not nxt:
        continue
    o = nxt[0]
    tid = [x['node'] for x in o['outs'] if x['k'] == 'choice'][0]
    t = choices.pop(tid)
    alias[tid] = cid
    c['options'] = [x for x in c['options'] if x is not o] + \
                   [x for x in t['options'] if not ('nav' in x['tags'] and x['label'].startswith('이전'))]
    c['pages'].append(t['kpc'])
    c['page_ids'].append(tid)
    c['reach'] = c['reach'] + [w for w in t['reach'] if w not in c['reach']]
    c['pre'] = c['pre'] + [w for w in t['pre'] if w not in c['pre']]
for c in choices.values():
    for o in c['options']:
        for oc in o['outs']:
            if oc.get('node') in alias:
                oc['node'] = alias[oc['node']]
        # 같은 결과는 하나로
        seen = []
        for oc in o['outs']:
            key = (oc['k'], oc.get('node'))
            if key not in [(x['k'], x.get('node')) for x in seen]:
                seen.append(oc)
        o['outs'] = seen
        # 「역시 그만둔다」처럼 앞 목록으로 돌아가는 항목
        if 'nav' in o['tags']:
            for oc in o['outs']:
                if oc['k'] == 'choice':
                    oc['k'] = 'back'
    sc = scenes[c['script']]
    sc['choices'].append(c['id'])
for s in scenes.values():
    s['choices'].sort(key=lambda cid: choices[cid]['kpc'])
for c in choices.values():
    c['preds'] = []
for c in choices.values():
    for o in c['options']:
        for oc in o['outs']:
            t = oc.get('node')
            if oc['k'] == 'choice' and t in choices and t != c['id']:
                if [c['id'], o['idx']] not in choices[t]['preds']:
                    choices[t]['preds'].append([c['id'], o['idx']])

# ---------------------------------------------------------------- 이번 회차 변수 증거
# 그 선택지에서만 세우는 이야기 변수(세이브마다 저장되는 7000 미만)는 세이브만 있어도
# 「이번 회차에 이것을 골랐다」를 확실히 알려 준다. 실패 표식 V[3999] 와 연출 변수는 뺀다.
opt_edge = {}
for sid_, g in graphs.items():
    for e in g['edges']:
        if e['kind'] == 'option':
            opt_edge[(e['from'], e['option'])] = e
SKIPV = {501, 502, 503, 3501, 3502, 3503, 3504, 3999}
cand = {}
for c in choices.values():
    for o in c['options']:
        e = opt_edge.get(tuple(o['src']))
        last = {}
        for x in (e['effects'] if e else []):
            lhs = x.get('lhs')
            if isinstance(lhs, list) and lhs[0] == 'v' and isinstance(x.get('rhs'), int):
                last[lhs[1]] = x['rhs']
        cand[(c['id'], o['idx'])] = {v: val for v, val in last.items() if val != 0 and v < 7000 and v not in SKIPV}
setters = collections.Counter((v, val) for sig in cand.values() for v, val in sig.items())
# 같은 변수를 다른 값으로 세우는 곳도 있으면 뺀다
anyset = collections.Counter(v for sig in cand.values() for v in sig)
for c in choices.values():
    for o in c['options']:
        sig = cand[(c['id'], o['idx'])]
        o['sig'] = [[v, val] for v, val in sorted(sig.items()) if setters[(v, val)] == 1 and anyset[v] == 1]

# ---------------------------------------------------------------- 재시작 관문
retry = {'III': '1300', 'V': '1500', 'VI': '1600'}
for c in chapters:
    c['retry'] = retry.get(c['id'])

# ---------------------------------------------------------------- 배치
PLATE_W, PLATE_H = 168, 40
GAP_X, GAP_Y = 30, 34
PER_ROW = 4
NODE_W = 220
Q_H, L_H = 30, 25
LAYER_GAP = 104
NODE_GAP = 22


def layout_strip(ids, y0=0):
    pos = {}
    for i, sid in enumerate(ids):
        r, k = divmod(i, PER_ROW)
        col = k if r % 2 == 0 else PER_ROW - 1 - k
        pos[sid] = [col * (PLATE_W + GAP_X), y0 + r * (PLATE_H + GAP_Y), PLATE_W, PLATE_H]
    return pos


def node_h(c):
    return Q_H + len(c['options']) * L_H + 8


def layout_cluster(ids):
    """선택 묶음: 왼쪽→오른쪽 층 배치. 되돌아가는 간선은 따로 표시."""
    ids = sorted(ids, key=lambda i: choices[i]['kpc'])
    succ = {i: [] for i in ids}
    for i in ids:
        for o in choices[i]['options']:
            for oc in o['outs']:
                if oc['k'] in ('choice', 'back') and oc.get('node') in succ:
                    succ[i].append(oc['node'])
    back = set()
    state = {}

    def dfs(u):
        state[u] = 1
        for v in succ[u]:
            if state.get(v) == 1:
                back.add((u, v))
            elif v not in state:
                dfs(v)
        state[u] = 2
    for i in ids:
        if i not in state:
            dfs(i)
    layer = {i: 0 for i in ids}
    for _ in range(len(ids) + 2):
        for u in ids:
            for v in succ[u]:
                if (u, v) not in back and layer[v] < layer[u] + 1:
                    layer[v] = layer[u] + 1
    nl = max(layer.values()) + 1 if ids else 0
    cols = [[i for i in ids if layer[i] == L] for L in range(nl)]
    order = {i: k for L in cols for k, i in enumerate(L)}
    preds = {i: [u for u in ids if i in succ[u] and (u, i) not in back] for i in ids}
    for _ in range(4):
        for L in range(1, nl):
            cols[L].sort(key=lambda i: (sum(order[p] for p in preds[i]) / len(preds[i])) if preds[i] else order[i])
            for k, i in enumerate(cols[L]):
                order[i] = k
    # 칸 높이: 첫 층은 위에서부터, 다음 층은 그 칸으로 오는 선택지 높이에 맞춘다(선이 수평으로 흐르게)
    pos = {}
    for L, col in enumerate(cols):
        x = L * (NODE_W + LAYER_GAP)
        want = {}
        for i in col:
            ys = []
            for u in preds[i]:
                if u not in pos:
                    continue
                ys.append(pos[u][1])
            want[i] = (sum(ys) / len(ys)) if ys else None
        if L > 0:
            col.sort(key=lambda i: want[i] if want[i] is not None else 1e9)
        y = None
        for i in col:
            h = node_h(choices[i])
            wy = want[i] if (L > 0 and want[i] is not None) else (0 if y is None else y)
            yy = wy if y is None else max(wy, y)
            pos[i] = [x, yy, NODE_W, h]
            y = yy + h + NODE_GAP
    top = min(v[1] for v in pos.values()) if pos else 0
    for v in pos.values():
        v[1] -= top
    return pos, sorted(back)


pages = []
for c in chapters:
    ids = [s for s in c['scenes'] if s in scenes]
    main = [s for s in ids if scenes[s]['kind'] == 'main']
    stories = [s for s in ids if s not in main]
    strip = layout_strip(stories)
    y = (max(v[1] + v[3] for v in strip.values()) + 46) if strip else 0
    clusters = []
    # 짧은 이야기 안의 선택(VII 의 3121): 이야기 줄 아래, 그 명판 밑에서 오른쪽으로
    for sid in stories:
        cl = scenes[sid]['choices']
        if not cl:
            continue
        pos, back = layout_cluster(cl)
        ox = strip[sid][0]
        for v in pos.values():
            v[0] += ox; v[1] += y
        w = max(v[0] + v[2] for v in pos.values()); h = max(v[1] + v[3] for v in pos.values())
        clusters.append({'scene': sid, 'pos': pos, 'back': back, 'box': [ox, y, w - ox, h - y], 'anchor': 'below'})
        y = h + 46
    # 본편: 새 줄 왼쪽 명판, 오른쪽으로 갈림길
    for sid in main:
        cl = scenes[sid]['choices']
        if cl:
            strip[sid] = [0, y, PLATE_W, PLATE_H]
            y += PLATE_H + 30
            pos, back = layout_cluster(cl)
            tall = max(v[1] + v[3] for v in pos.values())
            ox = 44
            for v in pos.values():
                v[0] += ox; v[1] += y
            w = max(v[0] + v[2] for v in pos.values())
            clusters.append({'scene': sid, 'pos': pos, 'back': back, 'box': [ox, y, w - ox, tall], 'anchor': 'below'})
            y += tall + 46
        else:
            strip[sid] = [0, y, PLATE_W, PLATE_H]
            y += PLATE_H + 46
    W = max([v[0] + v[2] for v in strip.values()] + [cl['box'][0] + cl['box'][2] for cl in clusters])
    H = max([v[1] + v[3] for v in strip.values()] + [cl['box'][1] + cl['box'][3] for cl in clusters])
    pages.append({'chapter': c['id'], 'order': stories + main, 'strip': strip, 'clusters': clusters, 'size': [W, H]})

model = {
    'schema': 'forest-story-map-claude-1',
    'game': GAME,
    'code_sha256': {sid: gsc[sid].code_sha256() for sid in sorted(gsc)},
    'chapters': chapters, 'scenes': scenes, 'choices': choices, 'alias': alias,
    'pages': pages,
    'sizes': {'plate': [PLATE_W, PLATE_H], 'node_w': NODE_W, 'q_h': Q_H, 'l_h': L_H},
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(model, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# 요약
print('scenes', len(scenes), 'choices', len(choices), 'merged', len(alias))
nw = sum(1 for c in choices.values() for o in c['options'] if o['witness'])
no = sum(len(c['options']) for c in choices.values())
print('options', no, 'with witness', nw, 'with var signature', sum(1 for c in choices.values() for o in c['options'] if o['sig']))
for p in pages:
    print(p['chapter'], 'size', p['size'], 'clusters', [(cl['scene'], len(cl['pos']), cl['back']) for cl in p['clusters']])
