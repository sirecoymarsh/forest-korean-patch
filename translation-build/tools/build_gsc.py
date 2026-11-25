# -*- coding: utf-8 -*-
"""번역 맵으로 GSC 52개를 다시 만든다. (자립 빌더)

2026-08-14 작성. Codex 트리 소실로 원래 빌더(`build_forest_gsc_from_translation_map.py`)와
하네스가 사라져 `rebuild.py`가 죽었다. 남아 있던 것만으로 다시 세웠다:

  기반 GSC   base_scr\\                     (gsc_build\\scr 의 스냅숏)
  슬롯 매핑  gsc_build\\manifests\\gsc_build_manifest.json
             files[].records[] = {uid, target_kind, slots}
  코덱       tools\\gsc.py

**인코딩 규칙**(매니페스트·실물 대조로 확정):
  target_kind == 'slot'           slots[0] 에 cp949(target)
  target_kind == 'overlay_group'  slots[0] 에 '^cy'+본문, slots[1] 에 '^ck'+본문
    (맵의 target 에는 ^cy/^ck 가 없다. 빌더가 붙인다.)

**검증**: 패치 75 직후 맵(`current\\...json.prev`)으로 빌드하면 현재 `gsc_build\\scr`와
바이트 단위로 같아야 한다. `verify` 명령이 그걸 확인한다.

  python build_gsc.py verify          .prev 로 빌드해 gsc_build\\scr 와 대조
  python build_gsc.py build [출력경로]  현재 맵으로 빌드 (기본 gsc_build\\scr)
"""
import json, sys, io, os, shutil, hashlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gsc import Gsc  # noqa: E402

ROOT = r"P:\AI\forest-kr-build"
BASE = os.path.join(ROOT, 'base_scr')
OUT = os.path.join(ROOT, 'gsc_build', 'scr')
MAN = os.path.join(ROOT, 'gsc_build', 'manifests', 'gsc_build_manifest.json')
CUR = os.path.join(ROOT, 'current', 'translation_map.current.json')
PREV = CUR + '.prev'

CY, CK = b'^cy', b'^ck'


def sha(b):
    return hashlib.sha256(b).hexdigest().upper()


def load_targets(path):
    m = json.load(open(path, encoding='utf-8'))
    recs = m['records'] if isinstance(m, dict) else m
    return {r['uid']: r['target'] for r in recs}


def build(map_path, out_dir, quiet=False):
    if not os.path.isdir(BASE):
        raise SystemExit(f'기반 GSC 없음: {BASE}  (gsc_build\\scr 를 복사해 두라)')
    tgt = load_targets(map_path)
    man = json.load(open(MAN, encoding='utf-8'))
    os.makedirs(out_dir, exist_ok=True)

    written = miss = 0
    for f in man['files']:
        name = f['file']
        g = Gsc(open(os.path.join(BASE, name), 'rb').read())
        ss = list(g.strings)
        for r in f['records']:
            t = tgt.get(r['uid'])
            if t is None:
                miss += 1
                continue
            body = t.encode('cp949')
            slots = r['slots']
            if r['target_kind'] == 'overlay_group':
                ss[slots[0]] = CY + body
                ss[slots[1]] = CK + body
            else:
                ss[slots[0]] = body
        open(os.path.join(out_dir, name), 'wb').write(g.rebuild(ss))
        written += 1
    if not quiet:
        print(f'빌드 {written}개 -> {out_dir}   (맵에 없는 uid {miss}건)')
    return written


def verify():
    """패치 75 직후 맵으로 빌드해 그 시점 산출물(base_scr)과 대조한다.

    base_scr 은 원래 파이프라인이 만든 마지막 산출물의 스냅숏이므로 **움직이지 않는
    기준**이다. gsc_build\\scr 은 새 패치가 들어갈 때마다 바뀌므로 기준으로 쓸 수 없다.
    """
    tmp = os.path.join(ROOT, '_verify_scr')
    if os.path.isdir(tmp):
        shutil.rmtree(tmp)
    build(PREV, tmp, quiet=True)
    bad = []
    for n in sorted(os.listdir(tmp)):
        a = sha(open(os.path.join(tmp, n), 'rb').read())
        b = sha(open(os.path.join(BASE, n), 'rb').read())
        if a != b:
            bad.append(n)
    print('검증: 패치75 직후 맵으로 빌드 -> 원래 파이프라인 산출물(base_scr)과 대조')
    print(f'  일치 {len(os.listdir(tmp))-len(bad)} / 불일치 {len(bad)}')
    if bad:
        print('  불일치:', ', '.join(bad[:10]))
        print('RESULT: FAIL')
    else:
        shutil.rmtree(tmp)
        print('RESULT: PASS  — 빌더가 원래 파이프라인과 동일한 산출물을 낸다')
    return not bad


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'verify'
    if cmd == 'verify':
        sys.exit(0 if verify() else 1)
    elif cmd == 'build':
        out = sys.argv[2] if len(sys.argv) > 2 else OUT
        build(CUR, out)
        print('RESULT: PASS')
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
