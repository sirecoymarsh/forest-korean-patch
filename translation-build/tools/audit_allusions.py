# -*- coding: utf-8 -*-
"""인용·고유명사 색인 — "모르면 틀린 줄도 모르는" 것들을 드러낸다.

Forest는 인용 밀도가 비정상적으로 높다. 원전을 모르면 오역인지 판별조차 못 하므로,
일본어 원문의 카타카나 어휘를 전수로 뽑아 **알려진 작품 목록과 대조**하고,
어디에도 안 걸리는 것을 남긴다. 남은 것이 곧 사각지대다.

이미 있는 자료(둘 다 Codex 트리, 읽기 전용):
  literary_reference_context.json   사용자 확정 14작품 + reference_names
  literary_reference_findings.final.json  12,387건 스캔 결과 86건(확정 67)

이 도구는 그 위에 얹는다. 목록에 없는 계열(일본 TV·만화, 미등재 문학)이 실제로
빠져나갔다 — 이이토모(笑っていいとも！), 타이거 마스크, 오베론, 아라고른 등.

  python audit_allusions.py            요약 + 미분류 상위
  python audit_allusions.py --all      미분류 전건
  python audit_allusions.py --known    분류된 것도 함께
"""
import json, sys, io, os, re, glob, collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

JA_MAPS = (r"P:\AI\Codex\projects\_migrated_c_documents_codex\2026-07-29\p-game-forest"
           r"\outputs\forest_full_ja_compact_packets_20260802\maps")
TW = (r"P:\AI\Codex\projects\_migrated_c_documents_codex\2026-07-29\p-game-forest"
      r"\work\forest-en-korean-pilot\translation_work")
CUR = r"P:\AI\forest-kr-build\current\translation_map.current.json"
OUT = r"P:\AI\forest-kr-build\audit\allusions.json"

MIN_FREQ = 3
KAT = re.compile(r'[ァ-ヴー・]{2,}')

# 일반 외래어 — 고유명사가 아니므로 뺀다. 판단이 애매하면 빼지 않는다(빠뜨리는 것보다 낫다).
COMMON = {
    'テーブル', 'ゲーム', 'ルール', 'ターン', 'サービス', 'ビル', 'コース', 'ゴール',
    'ペナルティ', 'パーティ', 'プレイヤ', 'パートナ', 'オリジナル', 'リアル', 'ムーブ',
    'マス', 'ダイス', 'サイコロ', 'ボク', 'ヒト', 'クマ', 'ウサギ', 'ネズミ', 'ネコ',
    'バカ', 'ダメ', 'キミ', 'トランプ', 'イギリス', 'ケーキ', 'カップ', 'ポット',
    'テレビ', 'ドア', 'ベッド', 'カーテン', 'ソファ', 'スカート', 'シャツ', 'ボタン',
    'メール', 'ボール', 'コーヒー', 'ジュース', 'ワイン', 'ビール', 'タバコ',
    'エレベータ', 'ビニール', 'ガラス', 'コンクリート', 'ズボン', 'ポケット',
}


def load_known():
    """알려진 이름 -> 작품 매핑."""
    ctx = json.load(open(os.path.join(TW, 'literary_reference_context.json'),
                         encoding='utf-8'))
    known = {}
    for w in ctx['works']:
        for n in w.get('reference_names', []):
            known[n] = w['title_ko']
        known[w['title_ko']] = w['title_ko']
    return ctx, known


def main():
    show_all = '--all' in sys.argv
    show_known = '--known' in sys.argv

    ctx, known_ko = load_known()

    ja = {}
    for f in glob.glob(os.path.join(JA_MAPS, '*.jsonl')):
        for line in open(f, encoding='utf-8'):
            r = json.loads(line)
            ja[r['uid']] = r['source_ja']

    m = json.load(open(CUR, encoding='utf-8'))
    ko = {r['uid']: r['target'] for r in (m['records'] if isinstance(m, dict) else m)}

    freq = collections.Counter()
    where = collections.defaultdict(set)
    for uid, s in ja.items():
        fno = re.search(r'/(\d{4})\.gsc', uid).group(1)
        for tok in KAT.findall(s):
            t = tok.strip('ー・')
            if len(t) >= 2:
                freq[t] += 1
                where[t].add(fno)

    # 한국어 쪽 표기 후보 — 해당 uid들의 한국어를 붙여 놓고 사람이 확인한다
    rows = []
    for t, n in freq.most_common():
        if n < MIN_FREQ or t in COMMON:
            continue
        # 알려진 이름과 맞닿는가 (한국어 표기 문자열 포함으로 근사)
        hit = None
        for name, work in known_ko.items():
            uids = [u for u, s in ja.items() if t in s][:40]
            if any(name in ko.get(u, '') for u in uids):
                hit = (name, work)
                break
        sample = next((ko[u] for u, s in ja.items()
                       if t in s and u in ko), '')
        rows.append({'ja': t, 'freq': n, 'files': sorted(where[t]),
                     'known': hit, 'sample_ko': sample[:70]})

    unknown = [r for r in rows if not r['known']]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({'min_freq': MIN_FREQ, 'total': len(rows),
               'unclassified': len(unknown), 'records': rows},
              open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print(f"카타카나 고유명사 후보 {len(rows)}종 (빈도 {MIN_FREQ}회 이상, 일반 외래어 제외)")
    print(f"  알려진 작품에 연결됨 {len(rows) - len(unknown)}종")
    print(f"  **미분류 {len(unknown)}종**  <- 원전을 모르면 오역 판별 불가")
    print(f"\n결과: {OUT}")

    show = unknown if show_all else unknown[:40]
    print(f"\n=== 미분류 {len(show)}종 (빈도순) ===")
    for r in show:
        print(f"  {r['freq']:4d} {r['ja']:16s} [{','.join(r['files'][:5])}]")
        print(f"        KO: {r['sample_ko']}")

    if show_known:
        print(f"\n=== 연결됨 ===")
        for r in rows:
            if r['known']:
                print(f"  {r['freq']:4d} {r['ja']:16s} -> {r['known'][0]} ({r['known'][1]})")


main()
