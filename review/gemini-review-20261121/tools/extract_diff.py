# -*- coding: utf-8 -*-
"""제미나이 판(runtime\\scr) ↔ 고치기 전 판(scr_backup_20261121 = 플레이 사본) 칸마다 비교.

바뀐 칸마다: 파일·슬롯·갈래(msg/sub/sub_outline/choice/append/other)·화자 코드·음성 번호·
일본어 원문(같은 순번 명령)·영문 패치 글·고치기 전·고친 뒤.
결과: ..\\data\\changes.jsonl, ..\\data\\summary.json
"""
import json, os, re, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gscwalk import walk

OLD = r'P:\AI\forest-flowchart-claude\runtime\scr_backup_20261121'
NEW = r'P:\AI\forest-flowchart-claude\runtime\scr'
JA = r'P:\AI\forest-kr-build\ja_scr'
EN = (r'P:\AI\Codex\projects\_migrated_c_documents_codex\2026-07-29\p-game-forest'
      r'\work\english_patch_research\patch_payload_full\scr')
MODEL = r'P:\AI\forest-flowchart-claude\data\model.json'
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')


def dec(b, enc):
    return b.decode(enc, 'replace')


def chapter_of():
    """대본 번호 → 장(1~9). 지도 모델의 장면 표에서."""
    try:
        m = json.load(open(MODEL, encoding='utf-8'))
    except Exception:
        return {}
    out = {}
    for ch in m.get('chapters', []):
        for s in ch.get('scenes', []):
            out[int(s)] = ch['n']          # 1~9
    for s, sc in m.get('scenes', {}).items():   # 곁가지 장면(성인 장면 등)
        if int(s) not in out:
            for ch in m.get('chapters', []):
                if ch['id'] == sc.get('chapter'):
                    out[int(s)] = ch['n']
    return out


def index_slots(cmds):
    """슬롯 → 정보. 명령 순번(같은 종류 안에서 k번째)도 남겨 일본어 맞추기에 쓴다."""
    info = {}
    k_msg = k_ch = 0
    voice = None
    for pc, op, a in cmds:
        if op == 0x42:
            voice = a[0]
        elif op == 0x51:
            info.setdefault(a[5], ('msg', k_msg, a[1] if a[1] else None, pc))
            k_msg += 1
        elif op == 0x52:
            info.setdefault(a[4], ('append', None, None, pc))
        elif op == 0x20 and 45 <= a[0] <= 49:
            info.setdefault(a[5], ('sub' if a[0] == 49 else 'sub_outline', None, voice, pc))
        elif op == 0x0E:
            info.setdefault(a[1], ('choice_prompt', k_ch, None, pc))
            for j, s in enumerate(a[7:12]):
                if s:
                    info.setdefault(s, ('choice_option', (k_ch, j), None, pc))
            k_ch += 1
    return info


def ja_index(cmds, strings):
    msgs, chs = [], []
    for pc, op, a in cmds:
        if op == 0x51:
            msgs.append(dec(strings[a[5]], 'cp932'))
        elif op == 0x0E:
            chs.append((dec(strings[a[1]], 'cp932'), [dec(strings[s], 'cp932') if s else '' for s in a[7:12]]))
    return msgs, chs


def main():
    os.makedirs(OUT, exist_ok=True)
    chap = chapter_of()
    rows, per = [], collections.Counter()
    for f in sorted(os.listdir(NEW)):
        if not f.endswith('.gsc'):
            continue
        po, pn = os.path.join(OLD, f), os.path.join(NEW, f)
        if not os.path.exists(po):
            continue
        co, so = walk(po)
        cn, sn = walk(pn)
        assert [(p, o, a) for p, o, a in co] == [(p, o, a) for p, o, a in cn], 'command section differs: ' + f
        if so == sn:
            continue
        info = index_slots(co)
        jmsgs = jchs = None
        jp = os.path.join(JA, f)
        if os.path.exists(jp):
            jc, js = walk(jp)
            jmsgs, jchs = ja_index(jc, js)
        en = None
        ep = os.path.join(EN, f)
        if os.path.exists(ep):
            en = walk(ep)[1]
        sid = int(f[:4])
        for i in range(max(len(so), len(sn))):
            a = so[i] if i < len(so) else b''
            b = sn[i] if i < len(sn) else b''
            if a == b:
                continue
            lane, k, voice, pc = info.get(i, ('other', None, None, None))
            ja = ''
            if lane == 'msg' and jmsgs is not None and k is not None and k < len(jmsgs):
                ja = jmsgs[k]
            elif lane == 'choice_prompt' and jchs is not None and k < len(jchs):
                ja = jchs[k][0]
            elif lane == 'choice_option' and jchs is not None and k[0] < len(jchs):
                ja = jchs[k[0]][1][k[1]]
            old, new = dec(a, 'cp949'), dec(b, 'cp949')
            m = re.match(r'\^g(\d{3})', new) or re.match(r'\^g(\d{3})', old)
            rows.append({'file': sid, 'slot': i, 'lane': lane, 'pc': pc, 'chapter': chap.get(sid),
                         'spk': m.group(1) if m else '', 'voice': voice, 'ja': ja,
                         'en': dec(en[i], 'cp932') if en is not None and i < len(en) else '',
                         'old': old, 'new': new})
            per[(sid, lane)] += 1
    with open(os.path.join(OUT, 'changes.jsonl'), 'w', encoding='utf-8') as fo:
        for r in rows:
            fo.write(json.dumps(r, ensure_ascii=False) + '\n')
    lanes = collections.Counter(r['lane'] for r in rows)
    files = collections.Counter(r['file'] for r in rows)
    json.dump({'changed_slots': len(rows), 'lanes': lanes, 'files': {str(k): v for k, v in sorted(files.items())}},
              open(os.path.join(OUT, 'summary.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('changed slots', len(rows), dict(lanes), 'files', len(files))


if __name__ == '__main__':
    main()
