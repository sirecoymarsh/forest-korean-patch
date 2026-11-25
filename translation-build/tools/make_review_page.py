# -*- coding: utf-8 -*-
"""시나리오 하나를 통째로 훑어보는 검수 페이지를 만든다.

명령부를 재생 순서대로 걸어 **일본어 원문 · 한국어 · 노란 자막 · 음성**을 한 줄로 세운다.
자막은 일본어 원본에 텍스트가 없으므로(영문 팬패치가 얹은 층) 음성이 유일한 근거다.
그래서 음성을 그 자리에 바로 재생 가능하게 붙인다.

명령 형식(직접 재해독):
  0x51 MESSAGE   u16 + i32*7,  arg[5]=문자열 슬롯, arg[6]=1
  0x20 OVERLAY   u16 + i32*6,  arg[0]=오브젝트(45~49), arg[1..2]=좌표, arg[5]=슬롯
                 자막 하나 = 5개 묶음(외곽선 4 + 본체 1). 본체는 오브젝트 49.
  0x42 VOICE     u16 + i32,    voice.xfl 의 파일 번호

**자막은 세 층을 나란히 세운다** — 일본어 원본에는 텍스트가 없으므로 실제로는
영문(팬패치가 귀로 받아 적은 것)과 한국어(그걸 옮긴 것) 둘이다. 셋을 함께 보면
어디서 어긋났는지가 한눈에 드러난다. 영문 GSC 가 있으면 `--en <폴더>` 로 준다.

  python make_review_page.py 2300 [출력폴더] [--en <영문 scr 폴더>]
"""
import sys, io, os, struct, json, html, shutil

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gsc import Gsc            # noqa: E402
from xfl import read_index, extract  # noqa: E402
from oggfix import convert as ogg_convert  # noqa: E402

ROOT = r"P:\AI\forest-kr-build"
VOICE_ARC = r"P:\GAME\Forest\voice.xfl"
TITLES = {'2100': '프롤로그', '2200': '이정표', '2300': '신주쿠 표류',
          '2400': '네버랜드', '2500': '더 게임', '2600': '라퓨타'}


def walk(path, enc):
    """명령부를 위치 순서로 걸어 (종류, 값) 목록을 만든다."""
    d = open(path, 'rb').read()
    h = struct.unpack_from('<7I', d, 0)
    A, B = h[1], min(h[2], len(d))
    g = Gsc(d)
    ev = []
    for i in range(A, B - 30, 2):
        op = struct.unpack_from('<H', d, i)[0]
        if op == 0x51:
            a = struct.unpack_from('<7i', d, i + 2)
            if 0 <= a[5] < g.count and a[6] == 1:
                ev.append((i, 'msg', g.strings[a[5]].decode(enc, 'replace')))
        elif op == 0x20:
            a = struct.unpack_from('<6i', d, i + 2)
            if a[0] == 49 and 0 <= a[5] < g.count:          # 본체만
                ev.append((i, 'sub', g.strings[a[5]].decode(enc, 'replace')))
        elif op == 0x42:
            v = struct.unpack_from('<i', d, i + 2)[0]
            if 0 <= v < 6134:
                ev.append((i, 'voice', v))
    ev.sort()
    return ev


TOK = ('^n', '^m')


def fmt(t):
    """제어토큰을 표시용으로 바꾼다. 화자 코드는 따로 떼어 낸다."""
    spk = ''
    if t.startswith('^g') and len(t) > 5:
        spk, t = t[2:5], t[5:]
    if t.startswith('^cy') or t.startswith('^ck'):
        t = t[3:]
    for k in TOK:
        t = t.replace(k, '\n')
    return spk, t


def main():
    argv = sys.argv[1:]
    en_dir = None
    if '--en' in argv:
        k = argv.index('--en')
        en_dir = argv[k + 1] if k + 1 < len(argv) else None
        argv = argv[:k] + argv[k + 2:]
    fno = argv[0] if argv else '2300'
    out = argv[1] if len(argv) > 1 else os.path.join(ROOT, 'review')
    vdir = os.path.join(out, 'voice')
    os.makedirs(vdir, exist_ok=True)

    ko = walk(os.path.join(ROOT, 'game', 'scr', f'{fno}.gsc'), 'cp949')
    ja = walk(os.path.join(ROOT, 'ja_scr', f'{fno}.gsc'), 'cp932')
    ja_msgs = [v for _, k, v in ja if k == 'msg']

    # 영문 팬패치가 있으면 자막·대사를 같은 순서로 세운다(한국어와 구조가 같다)
    en_msgs, en_subs = [], []
    if en_dir:
        p = os.path.join(en_dir, f'{fno}.gsc')
        if os.path.exists(p):
            ev = walk(p, 'cp932')
            en_msgs = [v for _, k, v in ev if k == 'msg']
            en_subs = [v for _, k, v in ev if k == 'sub']
            print(f'영문 대조: 대사 {len(en_msgs)} · 자막 {len(en_subs)}')
        else:
            print(f'영문 GSC 없음: {p}')

    # 음성 추출
    idx = read_index(VOICE_ARC)
    by_name = {e[0]: e for e in idx}
    nums = sorted({v for _, k, v in ko if k == 'voice'})
    got = 0
    for n in nums:
        p = os.path.join(vdir, f'{n:04d}.ogg')
        if os.path.exists(p):
            got += 1
            continue
        e = by_name.get(f'{n:04d}.wav')
        if not e:
            continue
        try:
            open(p, 'wb').write(ogg_convert(extract(VOICE_ARC, e)))
        except Exception as exc:
            print(f'  음성 {n} 변환 실패: {exc}')
            continue
        got += 1
    print(f'음성 {got}/{len(nums)}개 추출 -> {vdir}')

    # 행 만들기 — 음성은 뒤따르는 대사에 붙인다
    rows, mi, si, pending = [], 0, 0, None
    for _, kind, val in ko:
        if kind == 'voice':
            pending = val
            continue
        if kind == 'msg':
            jt = ja_msgs[mi] if mi < len(ja_msgs) else ''
            et = en_msgs[mi] if mi < len(en_msgs) else ''
            mi += 1
            spk, k1 = fmt(val)
            _, j1 = fmt(jt)
            _, e1 = fmt(et)
            rows.append(('msg', spk, j1, e1, k1, pending))
        else:
            et = en_subs[si] if si < len(en_subs) else ''
            si += 1
            _, k1 = fmt(val)
            _, e1 = fmt(et)
            rows.append(('sub', '', '', e1, k1, pending))
        pending = None

    nsub = sum(1 for r in rows if r[0] == 'sub')
    nvoice = sum(1 for r in rows if r[5] is not None)
    nen = sum(1 for r in rows if r[3].strip())
    title = TITLES.get(fno, fno)

    doc = [f'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<title>{fno} {title} — 검수</title><style>
:root{{--bg:#12131a;--fg:#e8e6e3;--dim:#9a9aa8;--line:#2a2c38;--sub:#f5d76e;--ja:#8fb8de;--acc:#7ee0a0}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.7 "Malgun Gothic","Yu Gothic",system-ui,sans-serif}}
header{{position:sticky;top:0;background:#0d0e14;border-bottom:1px solid var(--line);padding:14px 20px;z-index:9}}
h1{{margin:0;font-size:18px}} .meta{{color:var(--dim);font-size:13px;margin-top:4px}}
.wrap{{max-width:1100px;margin:0 auto;padding:0 20px 80px}}
.row{{display:grid;grid-template-columns:52px 1fr;gap:14px;padding:12px 0;border-bottom:1px solid var(--line)}}
.n{{color:var(--dim);font-size:12px;text-align:right;padding-top:3px;font-variant-numeric:tabular-nums}}
.ja{{color:var(--ja);white-space:pre-wrap;font-size:14px}}
.en{{color:#b9a6d8;white-space:pre-wrap;font-size:13.5px;margin-top:3px}}
.ko{{white-space:pre-wrap;margin-top:3px}}
.sub .ko{{color:var(--sub)}}
.sub .tag{{color:var(--sub);border-color:var(--sub)}}
.tag{{display:inline-block;font-size:11px;color:var(--dim);border:1px solid var(--line);
  border-radius:3px;padding:0 5px;margin-right:6px;vertical-align:2px}}
audio{{height:30px;vertical-align:middle;margin-top:6px;max-width:340px}}
.novoice{{color:#4a4c5a;font-size:12px}}
.f{{position:sticky;bottom:0;background:#0d0e14;border-top:1px solid var(--line);
  padding:8px 20px;font-size:13px;color:var(--dim)}}
.f b{{color:var(--acc)}}
</style></head><body>
<header><h1>{fno}.gsc — {html.escape(title)}</h1>
<div class="meta">일본어 원문 · <span style="color:#b9a6d8">영문 팬패치</span> · 한국어 · 음성
&nbsp;|&nbsp; 대사 {len(rows)-nsub} · 자막 {nsub} · 음성 {nvoice} · 영문 {nen}</div></header>
<div class="wrap">''']

    for i, (kind, spk, ja_t, en_t, ko_t, v) in enumerate(rows, 1):
        cls = 'row sub' if kind == 'sub' else 'row'
        tag = '자막' if kind == 'sub' else (spk or '지문')
        doc.append(f'<div class="{cls}"><div class="n">{i}</div><div>')
        doc.append(f'<span class="tag">{html.escape(tag)}</span>')
        if ja_t.strip():
            doc.append(f'<span class="ja">{html.escape(ja_t)}</span>')
        elif kind == 'sub':
            doc.append('<span class="novoice">일본어 원본에 텍스트 없음 — 음성만</span>')
        if en_t.strip():
            doc.append(f'<div class="en">{html.escape(en_t)}</div>')
        doc.append(f'<div class="ko">{html.escape(ko_t)}</div>')
        if v is not None:
            doc.append(f'<audio controls preload="none" src="voice/{v:04d}.ogg"></audio>')
        doc.append('</div></div>')

    doc.append(f'''</div><div class="f">
자막은 일본어 원본에 <b>텍스트가 없다</b> — 영문 팬패치가 음성을 듣고 받아 적어 얹은 층이다.
그러므로 <b>귀로 들은 것이 영문판보다 상위 근거</b>다.</div></body></html>''')

    p = os.path.join(out, f'{fno}_{title}.html')
    open(p, 'w', encoding='utf-8').write(''.join(doc))
    print(f'페이지: {p}  (행 {len(rows)} / 자막 {nsub} / 음성 {nvoice})')


main()
