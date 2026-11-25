# -*- coding: utf-8 -*-
"""검출기 재료: 한자 → 한국 한자음(Unihan kHangul + 이체자), 한국어 낱말 빈도(OpenSubtitles 2018 ko_full).

hangul_readings(word) → 가능한 한글 읽기 집합(두음법칙 변형 포함)
kofreq(prefix)        → 그 글자로 시작하는 어절들의 빈도 합(조사 붙은 어절이 많아 앞머리 합으로 센다)
"""
import os, re, bisect, itertools, functools
EXT = r'Y:\AI\forest-deep-review\ext'

_H = {}
for l in open(os.path.join(EXT, 'unihan', 'Unihan_Readings.txt'), encoding='utf-8'):
    if l.startswith('U+') and '\tkHangul\t' in l:
        cp, _, v = l.rstrip('\n').split('\t')
        _H[chr(int(cp[2:], 16))] = [x.split(':')[0] for x in v.split()]
_VAR = {}
import zipfile
with zipfile.ZipFile(os.path.join(EXT, 'unihan', 'Unihan.zip')) as z:
    for l in z.read('Unihan_Variants.txt').decode('utf-8').split('\n'):
        if not l.startswith('U+'): continue
        cp, f, v = l.split('\t')
        if f in ('kTraditionalVariant', 'kSemanticVariant', 'kZVariant', 'kSpecializedSemanticVariant', 'kCompatibilityVariant'):
            c = chr(int(cp[2:], 16))
            for x in v.split():
                x = x.split('<')[0]
                if x.startswith('U+'): _VAR.setdefault(c, []).append(chr(int(x[2:], 16)))
# 흔한 일본 신자체 → 정자 (Unihan 이체자에 없을 때 대비)
for a, b in zip('広沢円気国学会体変戦売読団単図当挙権歓対権浜辺辺継続経軽験険検剣乱恋楽薬鉄関顔県弁伝転点党灯闘独徳届貫観与誉余予医囲為壱隠栄営衛駅円塩奥応欧殴桜価仮絵拡覚学岳楽巻陥観勧寛関歓気帰亀偽戯犠旧拠挙虚峡挟狭郷暁勤謹区駆勲径茎恵掲携渓経継軽鶏芸撃欠倹剣圏検権献研県険顕験厳広効恒黄鉱号国黒穀砕済斎剤桜冊雑参惨桟蚕賛残糸歯児辞湿実写釈寿収従渋獣縦粛処緒叙奨将焼称証乗剰壌嬢条浄状畳譲醸触嘱寝慎晋真尽図粋酔随髄枢数瀬声斉静窃摂専戦浅践銭潜繊禅双壮捜挿巣争総聡荘装騒臓蔵属続堕対体帯滞台滝択沢単嘆担胆団弾断痴遅昼虫鋳庁徴聴鎮塚逓鉄転点伝都灯当党盗稲闘徳独読届縄弐悩脳覇廃拝売麦発髪抜蛮秘浜瓶払仏並併塀辺変弁瓣辯舗歩宝豊没翻毎万満黙訳薬予余与誉揺様謡来頼乱覧欄竜隆虜両猟緑涙塁励礼霊齢暦歴恋炉労郎楼録湾',
                '廣澤圓氣國學會體變戰賣讀團單圖當擧權歡對權濱邊邊繼續經輕驗險檢劍亂戀樂藥鐵關顏縣辯傳轉點黨燈鬪獨德屆貫觀與譽餘豫醫圍爲壹隱榮營衞驛圓鹽奧應歐毆櫻價假繪擴覺學嶽樂卷陷觀勸寬關歡氣歸龜僞戲犧舊據擧虛峽挾狹鄕曉勤謹區驅勳徑莖惠揭攜溪經繼輕鷄藝擊缺儉劍圈檢權獻硏縣險顯驗嚴廣效恆黃鑛號國黑穀碎濟齋劑櫻册雜參慘棧蠶贊殘絲齒兒辭濕實寫釋壽收從澁獸縱肅處緖敍奬將燒稱證乘剩壤孃條淨狀疊讓釀觸囑寢愼晉眞盡圖粹醉隨髓樞數瀨聲齊靜竊攝專戰淺踐錢潛纖禪雙壯搜揷巢爭總聰莊裝騷臟藏屬續墮對體帶滯臺瀧擇澤單嘆擔膽團彈斷癡遲晝蟲鑄廳徵聽鎭塚遞鐵轉點傳都燈當黨盜稻鬪德獨讀屆繩貳惱腦霸廢拜賣麥發髮拔蠻祕濱甁拂佛竝倂塀邊變辯瓣辯舖步寶豐沒飜每萬滿默譯藥豫餘與譽搖樣謠來賴亂覽欄龍隆虜兩獵綠淚壘勵禮靈齡曆歷戀爐勞郞樓錄灣'):
    _VAR.setdefault(a, []).append(b)


def char_readings(c):
    r = list(_H.get(c, []))
    if not r:
        for v in _VAR.get(c, []):
            r += _H.get(v, [])
    # 순서 지키며 중복 빼기
    out = []
    for x in r:
        if x not in out: out.append(x)
    return out


def is_kanji(c):
    o = ord(c)
    return 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF or c in '々'


CHO = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'


def _dueum(s):
    """첫소리 두음법칙 변형: 라→나, 리→이, 녀→여 …"""
    o = ord(s) - 0xAC00
    if o < 0 or o > 11171: return [s]
    ch, ju, jo = o // 588, (o % 588) // 28, o % 28
    out = [s]
    iy = ju in (2, 3, 6, 7, 12, 17, 20)  # ㅑ ㅒ ㅕ ㅖ ㅛ ㅠ ㅣ
    if ch == 5:  # ㄹ
        out.append(chr(0xAC00 + (11 if iy else 2) * 588 + ju * 28 + jo))
    elif ch == 2 and iy:  # ㄴ + ㅣ계
        out.append(chr(0xAC00 + 11 * 588 + ju * 28 + jo))
    return out


@functools.lru_cache(maxsize=None)
def hangul_readings(word, limit=64):
    per = []
    for c in word:
        if c == '々':
            if not per: return frozenset()
            per.append(per[-1]); continue
        r = char_readings(c)
        if not r: return frozenset()
        per.append(r[:4])
    out = set()
    for combo in itertools.product(*per):
        if len(out) > limit: break
        first = _dueum(combo[0])
        for f in first:
            out.add(f + ''.join(combo[1:]))
        # 둘째 이하 음절의 렬/률 → 열/율 (모음·ㄴ 뒤)
    return frozenset(out)


# ---- 한국어 빈도 ----
_W, _C = [], []
_tot = 0
for l in open(os.path.join(EXT, 'kofreq', 'ko_full.txt'), encoding='utf-8'):
    p = l.rstrip('\n').rsplit(' ', 1)
    if len(p) != 2: continue
    try: n = int(p[1])
    except ValueError: continue
    _W.append(p[0]); _C.append(n); _tot += n
_order = sorted(range(len(_W)), key=lambda i: _W[i])
_SW = [_W[i] for i in _order]
_PS = [0]
for i in _order: _PS.append(_PS[-1] + _C[i])
TOTAL = _tot
_EXACT = dict(zip(_W, _C))


def kofreq(prefix):
    a = bisect.bisect_left(_SW, prefix)
    b = bisect.bisect_left(_SW, prefix + '\U0010ffff')
    return _PS[b] - _PS[a]


def kofreq_exact(w):
    return _EXACT.get(w, 0)


def per_million(n):
    return n * 1e6 / TOTAL


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    for w in ['好天下', '青空', '外見的', '黒点', '奇遇', '杞憂', '広場', '沢山', '自分', '世界']:
        print(w, sorted(hangul_readings(w)), [(r, kofreq(r)) for r in sorted(hangul_readings(w))][:6])
    print('TOTAL', TOTAL)
