# -*- coding: utf-8 -*-
"""줄 폭 초과 레코드를 **글자를 바꾸지 않고** 줄바꿈 위치만 옮겨 해소한다.

`^n` 개수는 제어토큰 계약이라 늘릴 수 없다. 대신 같은 줄 수 안에서 어절을 재배분해
최대폭을 낮춘다. 글자는 하나도 바뀌지 않으므로 내용 판단이 필요 없다.

**문장 경계를 넘지 않는다.** 이 제약이 없으면 사고가 난다 — 실측 사례:

    전  「당신, 어째서……」
    전  카리야는 아마모리가 나오는 것을 보고 무척 놀란 모양이었습니다.
    후  「당신, 어째서……」 카리야는 아마모리가      <- 대사와 지문이 한 줄로 붙음

그래서 앞줄이 종결부호(。.!?…」』―)로 끝나거나 뒷줄이 인용부호·전각들여쓰기로
시작하면 그 경계로는 어절을 넘기지 않는다. 이어붙일 수 있는 인접 줄끼리만 블록을
이뤄 블록 안에서 DP로 최대폭 최소 분할을 찾는다.

제약을 풀면 203건 중 83건(40%)이 해결되지만 위 사고가 섞인다.
제약을 지키면 22건(10%)만 해결되고 전부 안전하다. 나머지는 문장 압축이 필요하다.

  python rebalance_lines.py            후보 미리보기
  python rebalance_lines.py --emit     patches/ 에 패치 파일 생성
"""
import json, sys, io, os, re, unicodedata, functools

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

CUR = r"P:\AI\forest-kr-build\current\translation_map.current.json"
PATCH_OUT = r"P:\AI\forest-kr-build\patches\71_line_rebalance.json"
MAX_EAW = 57

EXCLUDED = {'2101', '2301', '2302', '2501', '2601', '2700', '2801',
            '3022', '3039', '3081', '3121'}

TOK = re.compile(r'\^(?:g\d{3}|c[a-z]|[nm])')
CODE = re.compile(r'\^g\d{3}|\^n|\^c[a-z]')
TERM = ('。', '.', '!', '?', '！', '？', '」', '』', '…', '~', '♪', '―', '─')

# 줄을 끊어도 자연스러운 자리 = 앞 어절이 조사·어미로 끝나는 자리.
# 관형어("나간", "싹싹한")나 맨 명사("식별", "엘") 뒤에서 끊으면 뒤 낱말과 갈라져
# 「식별 / 태그」, 「엘 / 아라이라」처럼 한 덩어리가 두 줄로 쪼개진다.
NATURAL_2 = ('에서', '에게', '한테', '께서', '으로', '처럼', '보다', '부터', '까지',
             '마다', '조차', '라고', '하고', '든지', '지만', '면서', '으며', '도록',
             '니까', '어서', '아서', '이나', '라는', '라도')
NATURAL_1 = tuple('은는이가을를에의도와과로만요야여다고며서니면자지게어아네데죠랑')


def break_penalty(tok):
    """이 어절 뒤에서 줄을 끊었을 때의 부자연스러움. 낮을수록 좋다.

    0  문장·인용이 끝난 자리 — 한 줄에 한 문장이 되므로 가장 좋다
    1  쉼표 — 절 경계라 다음으로 좋다
    2  조사·어미로 끝난 자리 — 구 경계라 무난하다
    4  그 밖 — 관형어나 맨 명사 뒤라 뒤 낱말과 갈라진다
         (「식별 / 태그」 「엘 / 아라이라」 「개러지 / 크랭크」)

    2와 4를 끝 글자로만 가르므로 오판이 난다 — 「같은」의 은을 조사로, 「개러지」의
    지를 어미로 본다. 그래서 동점일 때 균형(최대폭 최소)으로 한 번 더 거른다.
    """
    t = TOK.sub('', tok).rstrip()
    if not t:
        return 4
    if t[-1] in '。.!?！？…」』~♪―─':
        return 0
    if t[-1] in '，,、:;':
        return 1
    return 2 if (t.endswith(NATURAL_2) or t.endswith(NATURAL_1)) else 4


def W(s):
    return sum(2 if unicodedata.east_asian_width(c) in 'WFA' else 1
               for c in TOK.sub('', s))


def can_join(prev, nxt):
    """prev 줄 끝에서 nxt 줄로 어절을 넘겨도 되는가."""
    p = TOK.sub('', prev).rstrip()
    q = TOK.sub('', nxt).lstrip('　 ')
    if not p or not q:
        return False
    if p.endswith(TERM):          # 문장·인용이 끝난 자리
        return False
    if q[0] in '「『"“':            # 인용이 시작하는 자리
        return False
    if nxt.startswith('　'):       # 전각 들여쓰기는 의도된 배치
        return False
    return True


def rebalance(lines):
    """같은 줄 수로 어절 재배분.

    목표는 **최소 이동**이다. 폭이 들어가는 분할 중 원래 줄바꿈 위치에서 가장 적게
    움직인 것을 고른다. '최대폭 최소'로 잡으면 가장 균등한 분할을 고르는데, 그러면
    필요 이상으로 갈아엎고 고유명사가 쪼개진다 — 실측 사례:

        최대폭최소: 내 매지컬 다이스는 싹싹한 개처럼 엘 / 아라이라에게 들러붙어…
                                                  ^^^^^^^^^ 엘 아라이라가 잘림
        최소이동:   내 매지컬 다이스는 싹싹한 / 개처럼 엘 아라이라에게 들러붙어…

    결함을 고치는 것이지 줄 배치를 새로 설계하는 게 아니다.
    """
    n = len(lines)
    heads = ['　' if l.startswith('　') else '' for l in lines]
    toks, orig = [], []
    for l in lines:
        body = l[1:] if l.startswith('　') else l
        toks.extend([t for t in body.split(' ') if t])
        orig.append(len(toks))          # 원래 각 줄의 끝 어절 인덱스
    m = len(toks)
    if m < n:
        return None

    def widths(bounds):
        out, prev = [], 0
        for idx, j in enumerate(bounds):
            out.append(W(heads[idx] + ' '.join(toks[prev:j])))
            prev = j
        return out

    best = None
    def search(k, start, bounds):
        nonlocal best
        if k == n - 1:
            b = tuple(bounds) + (m,)
            ws = widths(b)
            if max(ws) > MAX_EAW:
                return
            # ①부자연스러운 끊김 최소 ②최대폭 최소 ③원래 위치에서 최소 이동
            #
            # ①이 1순위여야 고유명사·복합어가 안 쪼개진다. 그 다음 ②로 균형을 잡는
            # 이유: "같은/좋은" 같은 관형형이 조사 은/는으로 오인돼 ①을 통과하는
            # 경우가 있는데, 균형 기준이 대체로 그런 분할을 밀어낸다. 최소이동을
            # 2순위로 두면 반대로 그런 분할이 채택된다(「칠흑 같은 / 어둠을」).
            unnat = sum(break_penalty(toks[b[i] - 1]) for i in range(n - 1))
            move = sum(abs(b[i] - orig[i]) for i in range(n))
            key = (unnat, max(ws), move)
            if best is None or key < best[0]:
                best = (key, b)
            return
        for j in range(start + 1, m - (n - 1 - k) + 1):
            search(k + 1, j, bounds + [j])

    search(0, 0, [])
    if best is None:
        return None
    b = best[1]
    out, prev = [], 0
    for idx, j in enumerate(b):
        out.append(heads[idx] + ' '.join(toks[prev:j]))
        prev = j
    return max(widths(b)), out


def main():
    emit = '--emit' in sys.argv
    m = json.load(open(CUR, encoding='utf-8'))
    recs = m['records'] if isinstance(m, dict) else m

    solved, unsolved = [], 0
    for r in recs:
        fno = re.search(r'/(\d{4})\.gsc', r['uid']).group(1)
        if fno in EXCLUDED:
            continue
        lines = r['target'].split('^n')
        if max(W(l) for l in lines) <= MAX_EAW:
            continue

        # 이어붙일 수 있는 인접 줄끼리 블록으로 묶는다
        blocks = [[0]]
        for i in range(1, len(lines)):
            (blocks[-1].append(i) if can_join(lines[i - 1], lines[i])
             else blocks.append([i]))

        new, ok = list(lines), True
        for blk in blocks:
            seg = [lines[i] for i in blk]
            if max(W(x) for x in seg) <= MAX_EAW:
                continue
            if len(seg) == 1:
                ok = False
                continue
            res = rebalance(seg)
            if res is None or res[0] > MAX_EAW:
                ok = False
                continue
            for i, v in zip(blk, res[1]):
                new[i] = v

        after = '^n'.join(new)
        if not ok or max(W(l) for l in new) > MAX_EAW:
            unsolved += 1
            continue
        # 안전 검증 — 제어토큰 시퀀스와 공백 제거 후 본문이 완전히 같아야 한다
        if CODE.findall(after) != CODE.findall(r['target']):
            unsolved += 1
            continue
        if after.replace('^n', ' ').replace('　', ' ').replace(' ', '') != \
           r['target'].replace('^n', ' ').replace('　', ' ').replace(' ', ''):
            unsolved += 1
            continue
        solved.append((r['uid'], r['target'], after, fno))

    print(f"재배치로 해결 {len(solved)}건 / 문장 압축 필요 {unsolved}건")
    for uid, before, after, fno in solved:
        print(f"\n[{fno}] {uid.split('::')[1][:26]}")
        for l in before.split('^n'):
            print(f"   전 {W(l):3d} {TOK.sub('', l)}")
        for l in after.split('^n'):
            print(f"   후 {W(l):3d} {TOK.sub('', l)}")

    if emit:
        entries = [{
            'uid': uid, 'before': before, 'after': after,
            'reason': ('줄 폭 초과로 화면에서 강제 개행되던 레코드. 글자는 바꾸지 않고 '
                       '같은 줄 수 안에서 어절만 재배분해 최대폭을 57 EAW 이하로 낮췄다. '
                       '문장·인용 경계는 넘지 않았다(넘기면 대사와 지문이 한 줄에 붙는 사고가 난다). '
                       '생성: tools/rebalance_lines.py'),
        } for uid, before, after, _ in solved]
        json.dump(entries, open(PATCH_OUT, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print(f"\n패치 생성: {PATCH_OUT}  ({len(entries)}건)")


main()
