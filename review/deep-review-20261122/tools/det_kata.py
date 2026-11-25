# -*- coding: utf-8 -*-
"""검출기 B: 일본식 영어(원맨 류) — 원문 가타카나어를 한국어가 소리로 옮겼는데, 그 말이 한국어에선 다른 뜻이거나 안 쓰이는 곳.

규칙
 1. 원문 MSG 의 가타카나 낱말(3자 이상, ー・ 포함)마다 가나→한글 근사 전사(T)를 만든다.
 2. 같은 칸 한국어 어절(조사 떼어냄) 중 자모 편집거리 비율이 가장 작은 것(≤0.45)을 「음차」로 짝짓는다.
 3. (가나, 한국어 음차) 쌍을 모두 모아 표로 낸다 → 두 거르개:
    a. 사전식 목록 WASEI(일본식 영어·일본에서만 다른 뜻인 외래어 — 한국어 뜻과 다른 것)에 든 가나가 음차로 옮겨졌으면 후보.
    b. 한국어 음차가 한국어 말뭉치(OpenSubtitles) 빈도 0~2 이고 고유명사(작품 용어 표)가 아니면 「드문 음차」 후보(사람이 가림).
→ out\\det_kata.tsv · data\\kata_pairs.json
"""
import os, sys, re, json, collections, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa
from kores import kofreq

# (가나, 한국어에서 그대로 옮기면 생기는 문제, 한국어 뜻)
WASEI = {
    'ワンマン': '원맨=독단적·독재(한국어 원맨은 「혼자서 하는」)', 'マンション': '맨션=고급 아파트(한국어 맨션은 고급 저택 느낌)',
    'スマート': '스마트=날씬한(한국어 스마트는 똑똑한)', 'ナイーブ': '나이브=예민한·섬세한(한국어 나이브는 순진한·어수룩한)',
    'タレント': '탤런트=방송 연예인(한국어 탤런트는 드라마 배우)', 'クレーム': '클레임=불평(한국어 클레임은 업무상 이의)',
    'マイペース': '마이페이스=자기 방식대로(한국어엔 거의 안 씀)', 'テンション': '텐션=들뜬 기분(한국어도 쓰지만 「텐션」은 구어)',
    'ハイテンション': '하이텐션=들뜬', 'ドンマイ': '돈마이=괜찮아(한국어 「괜찮아·신경 쓰지 마」)', 'マンツーマン': '맨투맨=일대일(한국어는 「일대일」·맨투맨은 옷)',
    'サラリーマン': '샐러리맨=회사원(한국어도 쓰나 예스러움)', 'オーバー': '오버=과장(한국어도 「오버하다」 구어)', 'ナイター': '나이터=야간 경기',
    'ガソリンスタンド': '주유소', 'コンセント': '콘센트(한국어도 씀)', 'シャーペン': '샤프', 'パソコン': '컴퓨터', 'ノートパソコン': '노트북',
    'ペーパードライバー': '장롱면허', 'ジェットコースター': '롤러코스터', 'フライドポテト': '감자튀김', 'ベビーカー': '유모차', 'キーホルダー': '열쇠고리',
    'モーニングコール': '모닝콜(한국어도 씀)', 'ゴールデンタイム': '황금 시간대', 'フロント': '프런트(안내 데스크)', 'ロマンチスト': '로맨티스트',
    'イメージアップ': '이미지 개선', 'バージョンアップ': '업그레이드', 'リストラ': '구조조정', 'カンニング': '커닝(한국어도 씀)', 'プリント': '프린트(유인물)',
    'デパート': '백화점', 'コンビニ': '편의점', 'アイドル': '아이돌(한국어도 씀)', 'ワイシャツ': '와이셔츠', 'ジャンパー': '점퍼', 'ボールペン': '볼펜',
    'ホッチキス': '스테이플러', 'ガードマン': '경비원', 'マイホーム': '내 집', 'マイカー': '자가용', 'ゴールイン': '결혼·결승', 'ナイスバディ': '몸매가 좋은',
    'バックミラー': '백미러', 'ノルマ': '할당량', 'パニック': '패닉(한국어도 씀)', 'ペアルック': '커플룩', 'スタイル': '스타일=몸매(한국어 스타일은 옷맵시·방식)',
    'セレブ': '부유층', 'フリーター': '아르바이트로 사는 사람', 'ニート': '니트(한국어도 씀)', 'リベンジ': '설욕·복수', 'チャレンジ': '도전',
    'メリット': '장점', 'デメリット': '단점', 'トランプ': '카드(트럼프=카드 놀이, 한국어에선 대개 「카드」)', 'ファイト': '힘내', 'ゲームセンター': '오락실',
    'アルバイト': '아르바이트', 'ハンドル': '핸들(한국어도 씀)', 'ムード': '무드=분위기', 'シール': '스티커', 'トレーナー': '맨투맨 티(한국어 트레이너는 코치)',
    'パーカー': '후드티', 'ビニール': '비닐', 'ミシン': '재봉틀', 'レンジ': '전자레인지', 'クーラー': '에어컨', 'スキンシップ': '스킨십(한국어도 씀)',
    'ベテラン': '베테랑(한국어도 씀)', 'ハプニング': '돌발 상황', 'フィーリング': '느낌·궁합', 'ポリシー': '신조(한국어 폴리시는 드묾)',
    'マニア': '마니아(한국어도 씀)', 'ナルシスト': '나르시시스트', 'マザコン': '마마보이', 'ロリコン': '로리콘', 'シスコン': '시스콘', 'ブラコン': '브라콘',
    'ガッツポーズ': '승리의 포즈', 'ガッツ': '근성', 'ピンチ': '위기(사용자 결정: 「핀치」 유지 — 셈하지 않음)', 'ノリ': '분위기',
    'ネタ': '소재·개그', 'キャラ': '캐릭터', 'ツッコミ': '태클', 'ボケ': '바보짓', 'ギャグ': '개그', 'コント': '콩트', 'アドリブ': '애드리브',
    'リアクション': '리액션', 'ノスタルジー': '향수', 'アベック': '연인', 'ランドセル': '책가방', 'オートバイ': '오토바이',
    'デマ': '헛소문', 'ジンクス': '징크스', 'ペンション': '펜션', 'マスコミ': '언론', 'ワンピース': '원피스', 'ノーメイク': '민낯',
    'イメチェン': '이미지 변신', 'オーダーメイド': '맞춤', 'ブランコ': '그네', 'カステラ': '카스텔라', 'コック': '요리사', 'シュークリーム': '슈크림',
    'ホームシック': '향수병', 'ナンセンス': '말도 안 됨', 'センス': '감각', 'ドラマチック': '극적', 'ロマンチック': '낭만적',
    'グロテスク': '그로테스크', 'スタンド': '스탠드', 'ストーブ': '난로', 'レトルト': '즉석', 'ハーフ': '혼혈',
}

K2H = {}
_base = ('アイウエオ', ['아', '이', '우', '에', '오'])
rowsK = {'': 'アイウエオ', 'k': 'カキクケコ', 'g': 'ガギグゲゴ', 's': 'サシスセソ', 'z': 'ザジズゼゾ', 't': 'タチツテト', 'd': 'ダヂヅデド',
         'n': 'ナニヌネノ', 'h': 'ハヒフヘホ', 'b': 'バビブベボ', 'p': 'パピプペポ', 'm': 'マミムメモ', 'r': 'ラリルレロ'}
rowsH = {'': ['아', '이', '우', '에', '오'], 'k': ['카', '키', '쿠', '케', '코'], 'g': ['가', '기', '구', '게', '고'], 's': ['사', '시', '스', '세', '소'],
         'z': ['자', '지', '즈', '제', '조'], 't': ['타', '치', '츠', '테', '토'], 'd': ['다', '지', '즈', '데', '도'], 'n': ['나', '니', '누', '네', '노'],
         'h': ['하', '히', '후', '헤', '호'], 'b': ['바', '비', '부', '베', '보'], 'p': ['파', '피', '푸', '페', '포'], 'm': ['마', '미', '무', '메', '모'],
         'r': ['라', '리', '루', '레', '로']}
for k in rowsK:
    for a, b in zip(rowsK[k], rowsH[k]): K2H[a] = b
K2H.update({'ヤ': '야', 'ユ': '유', 'ヨ': '요', 'ワ': '와', 'ヲ': '오', 'ヴ': '브', 'ァ': '아', 'ィ': '이', 'ゥ': '우', 'ェ': '에', 'ォ': '오',
            'ャ': '야', 'ュ': '유', 'ョ': '요'})


def jamo(s):
    out = []
    for c in s:
        o = ord(c) - 0xAC00
        if 0 <= o < 11172:
            out += [o // 588, 100 + (o % 588) // 28, 200 + o % 28 if o % 28 else None]
        else:
            out.append(c)
    return [x for x in out if x is not None]


def k2h(w):
    out = ''
    i = 0
    while i < len(w):
        c = w[i]
        if c in 'ー・＝': i += 1; continue
        if c == 'ン' or c == 'ッ':
            if out:
                o = ord(out[-1]) - 0xAC00
                if 0 <= o < 11172 and o % 28 == 0:
                    out = out[:-1] + chr(ord(out[-1]) + (4 if c == 'ン' else 19))
                    i += 1; continue
            i += 1; continue
        h = K2H.get(c, '')
        if i + 1 < len(w) and w[i + 1] in 'ャュョァィゥェォ' and h:
            # 拗音: 키+ャ → 캬 근사(모음만 바꿈)
            v = {'ャ': 2, 'ュ': 17, 'ョ': 12, 'ァ': 0, 'ィ': 20, 'ゥ': 13, 'ェ': 5, 'ォ': 8}[w[i + 1]]
            o = ord(h) - 0xAC00
            h = chr(0xAC00 + (o // 588) * 588 + v * 28)
            i += 1
        out += h
        i += 1
    return out


def lev(a, b):
    a, b = jamo(a), jamo(b)
    if not a or not b: return 99
    d = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        p, d[0] = d[0], i
        for j, y in enumerate(b, 1):
            p, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, p + (x != y))
    return d[len(b)] / max(len(a), len(b))


PART = re.compile(r'(에게서|으로는|에서는|이라는|이라고|라는|라고|에서|에게|한테|으로|로는|처럼|까지|부터|보다|이나|이며|이고|이다|이야|이지|이랑|하고|하는|해서|하게|한|을|를|이|가|은|는|의|에|와|과|도|만|로|야|요|다)$')


def ko_words(ko):
    out = []
    for t in re.findall(r'[가-힣]+', plain(ko)):
        out.append(t)
        s = PART.sub('', t)
        if s and s != t: out.append(s)
    return out


KATA = re.compile(r'[ァ-ヴー・]{3,}')


def main():
    rows = [r for r in load_corpus() if r['kind'] in ('MSG', 'CHQ', 'CHO') and r['ja'] and not r['hold']]
    pairs = collections.defaultdict(list)
    for r in rows:
        ws = ko_words(r['ko'])
        if not ws: continue
        kws = set(k.strip('・') for k in KATA.findall(plain(r['ja'])))
        # 합성어(ワンマンママ 등) 안의 일본식 영어 머리말도 따로 짝짓는다
        for k in list(kws):
            for w in WASEI:
                if len(w) >= 3 and k != w and k.startswith(w): kws.add(w)
        for kw in kws:
            t = k2h(kw)
            if len(t) < 2: continue
            best = min(ws, key=lambda w: lev(t, w))
            sc = lev(t, best)
            if sc <= 0.45:
                pairs[(kw, best)].append(r['id'])
            else:
                pairs[(kw, '∅')].append(r['id'])
    allp = [{'kana': k, 'ko': h, 'n': len(v), 'freq': (kofreq(h) if h != '∅' else -1), 'ids': v} for (k, h), v in pairs.items()]
    allp.sort(key=lambda x: (-x['n']))
    json.dump(allp, open(os.path.join(DATA, 'kata_pairs.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    with open(os.path.join(OUT, 'det_kata.tsv'), 'w', encoding='utf-8') as fo:
        fo.write('규칙\tkana\tko\t한국어빈도\t칸수\tids\t메모\n')
        nw = nr = 0
        for p in allp:
            if p['ko'] == '∅': continue
            base = None
            for w in WASEI:
                if p['kana'] == w or (len(w) >= 4 and (p['kana'].startswith(w) or p['kana'].endswith(w))
                                      and p['kana'] not in ('リストランテ',)):
                    base = w
            if base and 'ピンチ' != base:
                fo.write('a.일본식영어\t%s\t%s\t%d\t%d\t%s\t%s\n' % (p['kana'], p['ko'], p['freq'], p['n'], ' '.join(p['ids']), WASEI[base])); nw += 1
            elif p['freq'] <= 2 and len(p['ko']) >= 3:
                fo.write('b.드문음차\t%s\t%s\t%d\t%d\t%s\t\n' % (p['kana'], p['ko'], p['freq'], p['n'], ' '.join(p['ids']))); nr += 1
    print('kata pairs', len(allp), 'matched', sum(1 for p in allp if p['ko'] != '∅'), 'wasei cand', nw, 'rare cand', nr)


if __name__ == '__main__':
    main()


# ---- B2: 목록 직접 대조(자막 포함 — 자막은 Whisper 받아쓰기를 원문으로) ----
def list_check(version='ko'):
    W = {json.loads(l)['voice']: json.loads(l)['text'] for l in open(os.path.join(DATA, 'stt_whisper.jsonl'), encoding='utf-8')}
    forms = {w: d.split('=')[0] for w, d in WASEI.items() if '=' in d and re.match(r'^[가-힣]+=', d)}
    out = []
    for r in load_corpus():
        if r['kind'] not in ('MSG', 'SUB', 'CHQ', 'CHO') or not r['chap'] or r['hold']: continue
        ja = W.get(r['voice'], '') if r['kind'] == 'SUB' else plain(r['ja'])
        ko = plain(r[version])
        for w, f in forms.items():
            if w == 'ピンチ': continue
            if w in ja and f in ko: out.append((r['id'], w, f))
    return out


if __name__ == '__main__' and len(sys.argv) > 1 and sys.argv[1] == 'list':
    for v in ('ko', 'old'):
        print(v, list_check(v))
