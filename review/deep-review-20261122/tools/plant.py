# -*- coding: utf-8 -*-
"""검수자 재현율용 결함 심기 — 표본 밖 손대지 않은 칸 53개의 사본 한국어에 결함을 하나씩 심는다(원본 파일은 안 건드림).

유형(각 5) : MEANING 뜻 뒤집기 · OMISSION 빠뜨리기 · ADDITION 보태기 · PRONOUN 대사에 그/그녀 · REGISTER 말투(높임) 깨기
             TERM 사용자 결정 표기 어기기 · HANJA 한자음 잔재 · WASEI 일본식 영어 · FALSE_FRIEND 다른 뜻으로 읽히는 한자어
             KOREAN 조사·어미 비문
눈에 띄는 것(3): BLATANT — 무관한 문장·극단 말투·무관한 보탬(검수자가 실제로 읽는지 확인)
→ data\\planted.jsonl  {id, type, before, after, span}
"""
import os, sys, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa

P = [
    ('2300:280', 'MEANING', '영리해 보이는', '멍청해 보이는'),
    ('3102:40', 'MEANING', '기억하지 못하니까', '똑똑히 기억하니까'),
    ('2500:1467', 'MEANING', '「1」과 「5」가', '「1」과 「6」이'),
    ('2600:1687', 'MEANING', '그 밖에는 아무도 없었다.', '그 밖에도 여럿이 있었다.'),
    ('2500:1293', 'MEANING', '앞을 내다볼 수 없으니까', '앞이 훤히 보이니까'),
    ('2600:130', 'OMISSION', '지하상가로 통하는 길을 향해 갔다.', '어딘가로 날아갔다.'),
    ('2300:117', 'OMISSION', '아케루라면 동료들의 거처를 알 수 있습니다.^n', ''),
    ('3042:15', 'OMISSION', 'LINE:희귀한 것은', ''),
    ('2700:235', 'OMISSION', 'LINE:나침반 바늘', ''),
    ('2500:2273', 'OMISSION', 'LINE:하지만 나는 불만이다.', ''),
    ('2300:369', 'ADDITION', '자랑스럽게 짖었다.', '자랑스럽게 짖으며 꼬리를 흔들었다.'),
    ('2200:150', 'ADDITION', '마유즈미가 말했습니다.', '마유즈미가 화난 얼굴로 말했습니다.'),
    ('3112:58', 'ADDITION', '쑥스러운 듯 말했어.', '쑥스러운 듯 웃으며 말했어.'),
    ('2600:1804', 'ADDITION', '지상에 거처가', '지상에 기다리는 가족과 거처가'),
    ('2600:865', 'ADDITION', '나 혼자서, 플린트 데리고.', '나 혼자서, 보물 지도랑 플린트 데리고.'),
    ('2700:809', 'PRONOUN', '기노사키 아케루에게 배운 학생!', '그에게 배운 학생!'),
    ('2200:31', 'PRONOUN', '「미스 메리인가?', '「그녀인가?'),
    ('2200:126', 'PRONOUN', '「나중에 메리에게', '「나중에 그녀에게'),
    ('2700:85', 'PRONOUN', '적어도, 나가츠키 쪽에서 보면', '적어도, 그녀 쪽에서 보면'),
    ('2600:1419', 'PRONOUN', '하지만, 아케루가 꾸민 게', '하지만, 그가 꾸민 게'),
    ('2500:2327', 'REGISTER', '상관없잖아, 너한테는!', '상관없잖아요, 당신한테는!'),
    ('2500:1706', 'REGISTER', '그 정도로 내가 속을 줄 알고?', '그 정도로 제가 속을 줄 아셨어요?'),
    ('3031:140', 'REGISTER', 'RE:바꾸지 마\\.(.*)될 거다\\.', '바꾸지 마세요.\\1될 겁니다.'),
    ('2500:1059', 'REGISTER', '우응, 조금은 말이지.', '우응, 조금은요.'),
    ('2500:691', 'REGISTER', '……너, 혹시 몸 상태 나빠?', '……당신, 혹시 몸 상태 나쁘세요?'),
    ('2700:1101', 'TERM', '기노사키 아케루가', '조노사키 아케루가'),
    ('3074:29', 'TERM', '파두아는 세계수의', '파도바는 세계수의'),
    ('2500:418', 'TERM', '아메노모리 씨의', '아마모리 씨의'),
    ('2700:286', 'TERM', '가든에서의 모습을', '정원에서의 모습을'),
    ('2100:664', 'TERM', '매드 해터.', '모자 장수.'),
    ('3031:18', 'HANJA', '의대생의 눈으로', '의학생의 눈으로'),
    ('2600:1465', 'HANJA', '아쉽게도 손에는', '아쉽게도 수원에는'),
    ('2300:621', 'HANJA', '깊숙이 박아 넣었다.', '심심히 박아 넣었다.'),
    ('2600:2065', 'HANJA', '오늘 아침, 동틀 녘에', '금조, 동틀 녘에'),
    ('2400:488', 'HANJA', '나는 싸움에는', '나는 훤화에는'),
    ('3033:52', 'WASEI', '고양이는 혼자서도', '고양이는 원맨으로도'),
    ('2500:264', 'WASEI', '불만이 있다면', '클레임이 있다면'),
    ('2700:582', 'WASEI', '깡마른 뼈마디에', '스마트한 뼈마디에'),
    ('2500:2827', 'WASEI', '제멋대로 굴다니!', '마이페이스로 굴다니!'),
    ('3073:196', 'WASEI', '예리하게', '나이브하게'),
    ('3032:12', 'FALSE_FRIEND', '컨디션을 체크했다.', '체조를 체크했다.'),
    ('3112:8', 'FALSE_FRIEND', '믿는 건 자유지만.', '믿는 건 승수지만.'),
    ('3073:160', 'FALSE_FRIEND', '당하면 큰일이니까.', '당하면 대변이니까.'),
    ('2500:1609', 'FALSE_FRIEND', '사정이 있어 이 모습으로', '도합이 있어 이 모습으로'),
    ('2600:2291', 'FALSE_FRIEND', '싸움의 모습이──', '싸움의 양자가──'),
    ('2500:1192', 'KOREAN', '나는 다이스를 던졌다.', '나는 다이스가 던졌다.'),
    ('2600:822', 'KOREAN', '내던져진 검은, 바닥을 미끄러졌다.', '내던져진 검을, 바닥이 미끄러졌다.'),
    ('2300:56', 'KOREAN', '감전된 것처럼 돼.', '감전된 것처럼 되어지게 돼.'),
    ('3122:124', 'KOREAN', '날아 올라가.', '날아 올라가는.'),
    ('2500:571', 'KOREAN', '들어갔을지도 모른다.', '들어갔을지도 모르다.'),
    ('2600:993', 'BLATANT', 'ALL', '오늘 저녁은 카레라이스를 먹기로 했다.^n맛있었다.'),
    ('3122:26', 'BLATANT', 'ALL', '그러하옵니다, 소인은 그리 아뢰옵나이다.'),
    ('3102:48', 'BLATANT', 'APPEND', '^n그리고 모두 함께 노래를 부르며 춤추기 시작했다.'),
]


def apply(ko, old, new):
    m = re.match(r'^(\^g\d{3})', ko)
    head = m.group(1) if m else ''
    body = ko[len(head):]
    if old == 'ALL':
        return head + new
    if old == 'APPEND':
        return ko + new
    if old.startswith('LINE:'):
        key = old[5:]
        parts = body.split('^n')
        keep = [p for p in parts if key not in p]
        assert len(keep) == len(parts) - 1, ('LINE', key, ko)
        return head + '^n'.join(keep)
    if old.startswith('RE:'):
        out, n = re.subn(old[3:], new, body)
        assert n == 1, ('RE', old, ko)
        return head + out
    assert old in body, (old, ko)
    return head + body.replace(old, new, 1)


def main():
    rows = {r['id']: r for r in load_corpus()}
    samp = {json.loads(l)['id'] for l in open(os.path.join(DATA, 'sample.jsonl'), encoding='utf-8')}
    out = []
    seen = set()
    for i, t, a, b in P:
        assert i not in samp, ('in sample', i)
        assert i not in seen, ('dup', i); seen.add(i)
        r = rows[i]
        assert not r['changed'] and not r['hold'], i
        after = apply(r['ko'], a, b)
        assert after != r['ko'], i
        out.append({'id': i, 'type': t, 'before': r['ko'], 'after': after, 'span': b if a not in ('ALL',) else 'ALL'})
    dump_jsonl(out, os.path.join(DATA, 'planted.jsonl'))
    import collections
    print(len(out), collections.Counter(o['type'] for o in out))


if __name__ == '__main__':
    main()
