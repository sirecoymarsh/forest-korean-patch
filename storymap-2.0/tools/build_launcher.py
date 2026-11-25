# -*- coding: utf-8 -*-
"""다시보기 런처 scr\\9000.gsc 와 타이틀 배치 상수(native\\title_layout.inc)를 만든다.

9000 의 흐름(타이틀의 「이야기의 지도」 단추가 LOAD_SCRIPT 9000):
  pc0   WAIT 1                    ← DLL 이 여기서 지도를 띄우거나(V[9990]=0), 고른 장면 번호를 V[9990]에 넣는다
  LOOP  V[9990]==0 이면 WAIT 1 하고 LOOP
  V[9990]==9999 → V[9990]=0, LOAD_SCRIPT 1(타이틀)
  그 밖: 「처음부터」(0100) 초기화 그대로(마지막 LOAD_SCRIPT 110 만 뺌, 이야기 변수 12~6998 을 비움)
        → 장 진입과 같은 전환(V[501..503], CALL 501, WAIT 10, PRESENT60 15, CALL 510)
        → V[1]=장 제목 번호, CALL_SCRIPT 장면 → JUMP 0(다시 지도로)
"""
import json, os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import gscread
import install_runtime as IR

GAME = r'P:\AI\forest-kr-build\game'
CODEX = r'P:\AI\Codex\projects\forest-flowchart'
OUT = os.path.join(ROOT, 'assets', 'launcher')
REQ = 9990          # 다시보기 요청 변수(어느 스크립트도 안 씀)
CLOSE = 9999


def op(n, *args):
    if n & 0xF000:
        return struct.pack('<H', n) + struct.pack('<H' + 'h' * (len(args) - 1), *args)
    return struct.pack('<H', n) + struct.pack('<' + 'I' * len(args), *args)


class Asm:
    def __init__(self):
        self.code = bytearray(); self.labels = {}; self.fix = []

    def emit(self, n, *a):
        self.code += op(n, *a)

    def raw(self, b):
        self.code += b

    def label(self, l):
        assert l not in self.labels, l
        self.labels[l] = len(self.code)

    def jump(self, n, l):
        self.fix.append((len(self.code) + 2, l)); self.emit(n, 0)

    def eq(self, var, val):              # 비교 V[var]==val → 결과 레지스터
        self.emit(0x4800, 1, var, val); self.emit(0xF100, 0, 1)

    def let(self, var, val):             # 대입 V[var]=val
        self.emit(0x1800, 1, var, val); self.emit(0xF100, 0, 1)

    def finish(self):
        for at, l in self.fix:
            struct.pack_into('<I', self.code, at, self.labels[l])
        return bytes(self.code)


def main():
    model = json.load(open(os.path.join(ROOT, 'data', 'model.json'), encoding='utf-8'))
    parsed = json.load(open(os.path.join(CODEX, r'work\scripts_ko.json'), encoding='utf-8-sig'))
    # 장면별 V[1](장 진입 스크립트가 장면 직전에 넣는 값)
    label = {}
    for sid, s in parsed.items():
        if not (sid.startswith('10') or sid.startswith('11')):
            continue
        cm = sorted(s['commands'], key=lambda c: c['offset'])
        for i, c in enumerate(cm):
            if c['name'] == 'CALL_SCRIPT' and 2000 <= c['args'][0] < 4000:
                j = i - 1
                while j >= 0 and cm[j]['name'] == 'EXPR':
                    if cm[j]['op'] == 0x1800 and cm[j]['args'][1] == 1:
                        label[c['args'][0]] = cm[j]['args'][2]
                    j -= 1
    scenes = [int(sid) for c in model['chapters'] for sid in c['scenes'] if sid in model['scenes']]
    missing = [s for s in scenes if s not in label]
    assert not missing, missing

    # 「처음부터」 초기화(0100): 명령부를 그대로 옮기되 점프 대상만 옮긴 자리로 바꾼다
    g100 = gscread.load(os.path.join(GAME, 'scr', '0100.gsc'))
    cm100 = sorted(parsed['0100']['commands'], key=lambda c: c['offset'])
    last = cm100[-1]
    assert last['name'] == 'LOAD_SCRIPT' and last['args'] == [110], last
    init_len = last['offset']

    a = Asm()
    a.emit(0x0D, 1)                       # pc0: WAIT 1 — DLL 걸이 자리
    a.label('loop')
    a.eq(REQ, 0); a.jump(0x03, 'dispatch')
    a.emit(0x0D, 1); a.jump(0x05, 'loop')
    a.label('dispatch')
    a.eq(REQ, CLOSE); a.jump(0x03, 'play')
    a.let(REQ, 0)
    # 닫기 → 타이틀. 다시보기의 초기화(0100)가 레이어 11 을 grpo_bg 로 바꿔 두므로
    # 타이틀 단추가 쓰는 레이어 11~15 를 grpo(문자열 슬롯 1)로 되돌린다(16 은 타이틀이 fc 로 잡는다).
    assert g100.strings[1] == 'grpo'
    for layer in range(11, 16):
        a.emit(0x79, layer, 1)
    a.emit(0x0C, 1)
    a.label('play')
    base = len(a.code)
    init = bytearray(g100.code[:init_len])
    for c in cm100[:-1]:
        if c['name'] in ('JUMP', 'JUMP_IF_ZERO', 'JUMP_IF_NONZERO'):
            at = c['offset'] + 2
            tgt = struct.unpack_from('<I', init, at)[0]
            assert tgt < init_len
            struct.pack_into('<I', init, at, tgt + base)
        elif c['name'] in ('CHOICE',):
            raise SystemExit('unexpected CHOICE in 0100 init')
    a.raw(bytes(init))
    # 장 진입과 같은 전환
    a.let(501, 999); a.let(502, 1); a.let(503, 5)
    a.emit(0x0F, 501); a.emit(0x0D, 10); a.emit(0x3C, 15, 0); a.emit(0x0F, 510)
    for s in scenes:
        a.eq(REQ, s); a.jump(0x03, 'n%d' % s)
        a.let(REQ, 0); a.let(1, label[s]); a.emit(0x0F, s); a.jump(0x05, 'top')
        a.label('n%d' % s)
    a.let(REQ, 0)
    a.label('top_alias')
    a.jump(0x05, 'top')
    a.labels['top'] = 0
    code = a.finish()

    # 문자열 표는 0100 것을 그대로(RESOURCE121 이 슬롯 번호로 자원 폴더를 고른다)
    strings = g100.raw_strings
    offs = []; blob = b''
    for s in strings:
        offs.append(len(blob)); blob += s + b'\0'
    table = struct.pack('<%dI' % len(offs), *offs)
    tail = b'\0' * 6
    body = code + table + blob + tail
    head = struct.pack('<7I', len(body) + 27, 28, len(code), len(table), len(blob), 4, 1)
    data = head + body
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, '9000.gsc'), 'wb').write(data)
    chk = gscread.Gsc(data)
    assert chk.raw_strings == strings and chk.code == code

    # 타이틀 본 메뉴 대기 자리(OP_0049 [0,0] 첫 번째)와 지도 단추 자리
    t = IR.title_script()
    th = struct.unpack_from('<7I', t, 0)
    tcode = t[th[1]:th[1] + th[2]]
    pat = op(0x49, 0, 0)
    i = tcode.find(pat)
    assert i >= 0 and tcode[i + len(pat):i + len(pat) + 6] == op(0x3E, 1), 'main menu wait not found'
    after = tcode[i + len(pat) + 6 + 14:i + len(pat) + 6 + 14 + 8]
    open(os.path.join(ROOT, 'native', 'title_layout.inc'), 'w', encoding='utf-8').write(
        '// Generated by tools/build_launcher.py\n'
        'const uint32_t kTitleMenuWaitPc=%d;      // 타이틀 본 메뉴의 OP_0049 [0,0]\n'
        'const int kTitleMapButtonX=%d,kTitleMapButtonY=%d;  // 「이야기의 지도」 단추 가운데\n'
        'const int kReplayVar=%d,kReplayClose=%d;\n' % (i, 515 + 92, 0x1a7 + 19, REQ, CLOSE))
    print('9000.gsc', len(data), 'bytes; code', len(code), 'scenes', len(scenes), 'init base', base,
          'title menu wait pc', i)


if __name__ == '__main__':
    main()
