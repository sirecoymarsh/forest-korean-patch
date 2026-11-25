# -*- coding: utf-8 -*-
"""설정 화면 '메시지 건너뛰기' 두 버튼을 재조판한다.

  msk_on  未読文章を飛ばす  미독도 건너뜀  ->  안 읽은 부분도
  msk_off 未読文章で止まる  미독에서 멈춤  ->  읽은 부분만

'미독(未読)'은 일본식 한자어라 한국어 UI에서 읽히지 않는다. 행 제목이 이미
'메시지 건너뛰기'이므로 버튼은 범위만 말하면 된다.

원본 빌더(ui_work/tools/build_korean_ui_assets.py)를 그대로 돌리면 Codex 트리에
쓰고 20개 UI 자산을 전부 재생성한다. 여기서는 조판 함수만 재사용해서 msk 4개
레이어만 만들고, 설치본 confscrn.lwg 의 해당 엔트리만 교체한다.

  python retypeset_skip_labels.py build    래스터 생성 + 미리보기 PNG
  python retypeset_skip_labels.py install  confscrn.lwg 교체 (백업 후)
"""
import sys, io, os, shutil, hashlib, json, subprocess
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

PILOT = Path(r"P:\AI\Codex\projects\_migrated_c_documents_codex\2026-07-29\p-game-forest\work\forest-en-korean-pilot")
UI = PILOT / "ui_work"
TOOL = UI / "tools" / "UiAssetTool.exe"
JP_PNG = UI / "png_ui" / "japanese" / "confscrn"
JP_WCG = UI / "extracted_ui" / "japanese" / "confscrn"
SANS = Path(r"C:\Windows\Fonts\NotoSansKR-VF.ttf")

OUT = Path(r"P:\AI\forest-kr-build\ui_build")
GAME_LWG = Path(r"P:\AI\forest-kr-build\game\grps\confscrn.lwg")
BACKUP = Path(r"P:\AI\forest-kr-build\backup_ui\confscrn.lwg")

# 원본 빌더의 조판 함수를 그대로 재사용한다 (import 만, main 은 실행되지 않는다)
sys.path.insert(0, str(UI / "tools"))
sys.path.insert(0, str(PILOT / "adapter"))
import build_korean_ui_assets as B  # noqa: E402
from PIL import Image  # noqa: E402
import numpy as np  # noqa: E402

NEW_UNITS = (
    B.TranslationUnit(
        "config.skip.unread_allowed", "confscrn",
        "未読文章を飛ばす", "SKIP UNREAD", "안 읽은 부분도",
        ("msk_on", "msk_on_f"), (1, 0, 139, 21),
    ),
    B.TranslationUnit(
        "config.skip.stop_at_unread", "confscrn",
        "未読文章で止まる", "STOP AT UNREAD", "읽은 부분만",
        ("msk_off", "msk_off_f"), (1, 0, 139, 21),
    ),
)


def sha(b):
    return hashlib.sha256(b).hexdigest().upper()


def fail(m):
    print(f"[오류] {m}")
    print("RESULT: FAIL")
    sys.exit(1)


def build():
    for p in (TOOL, SANS, JP_PNG, JP_WCG):
        if not p.exists():
            fail(f"입력 없음: {p}")

    # 짧은 라벨 배경 템플릿 — 원본 빌더와 동일하게 bgm_on 계열에서 재구성
    teal = B.reconstruct_short_label_template(
        Image.open(JP_PNG / "bgm_on.png").convert("RGBA"))
    brown = B.reconstruct_short_label_template(
        Image.open(JP_PNG / "bgm_on_f.png").convert("RGBA"))
    blanks = {"teal": teal, "brown": brown}

    work = OUT / "work"
    wcg_out = OUT / "wcg"
    png_out = OUT / "png"
    for d in (work, wcg_out, png_out):
        d.mkdir(parents=True, exist_ok=True)

    records = []
    for unit in NEW_UNITS:
        for stem in unit.layer_stems:
            src_png = JP_PNG / f"{stem}.png"
            src_wcg = JP_WCG / f"{stem}.wcg"
            if not src_png.exists() or not src_wcg.exists():
                fail(f"레이어 원본 없음: {stem}")

            original = Image.open(src_png).convert("RGBA")
            style = B.config_style_for_layer(stem)
            edited, typo = B.typeset_config_layer(
                original, blanks[style], unit, stem, SANS)

            patch = work / f"{stem}.patch.png"
            mask = work / f"{stem}.mask.png"
            edited.save(patch)
            changed = B.save_diff_mask(original, edited, mask)
            if not changed.any():
                fail(f"픽셀 변화 없음: {stem}")

            dst_wcg = wcg_out / f"{stem}.wcg"
            dst_png = png_out / f"{stem}.png"
            B.run_checked([str(TOOL), "wcg-apply-patch",
                           str(src_wcg), str(patch), str(mask), str(dst_wcg)])
            B.run_checked([str(TOOL), "wcg2png", str(dst_wcg), str(dst_png)])

            # 편집 마스크 밖 픽셀은 변하면 안 된다
            dec = Image.open(dst_png).convert("RGBA")
            a = np.asarray(original, dtype=np.uint8)
            b = np.asarray(dec, dtype=np.uint8)
            outside = np.any(a != b, axis=2) & ~changed
            if outside.any():
                fail(f"편집 마스크 밖 픽셀 변경: {stem} ({int(outside.sum())}px)")
            if dec.size != original.size:
                fail(f"크기 변경: {stem} {original.size} -> {dec.size}")

            records.append({
                "layer": stem, "target_ko": unit.target_ko,
                "font_size": typo["font_size"], "style": typo["style"],
                "edited_px": int(changed.sum()),
                "wcg_sha256": sha(dst_wcg.read_bytes()),
            })
            print(f"  {stem:12s} {unit.target_ko:8s} "
                  f"font {typo['font_size']}px  {int(changed.sum())}px 변경")

    (OUT / "build_manifest.json").write_text(
        json.dumps({"records": records}, ensure_ascii=False, indent=1),
        encoding='utf-8')
    print(f"\n생성: {len(records)}개 레이어 -> {wcg_out}")
    print(f"미리보기 PNG: {png_out}")
    print("RESULT: PASS")


def install():
    from lwg_container import parse_lwg, rebuild_lwg
    wcg_out = OUT / "wcg"
    stems = [s for u in NEW_UNITS for s in u.layer_stems]
    for s in stems:
        if not (wcg_out / f"{s}.wcg").exists():
            fail(f"빌드 산출물 없음: {s}.wcg  (먼저 build 를 실행하라)")
    if not GAME_LWG.exists():
        fail(f"설치본 없음: {GAME_LWG}")

    src = GAME_LWG.read_bytes()
    parsed = parse_lwg(src)
    content = {e.name: e.content for e in parsed.entries}
    unknown = sorted(set(stems) - set(content))
    if unknown:
        fail(f"컨테이너에 없는 엔트리: {unknown}")

    repl = {s: (wcg_out / f"{s}.wcg").read_bytes() for s in stems}
    content.update(repl)
    rebuilt = rebuild_lwg(parsed, content)

    # 재파싱 검증 — 메타데이터 보존, 교체 대상 외 페이로드 불변
    re2 = parse_lwg(rebuilt)
    if len(re2.entries) != len(parsed.entries):
        fail("엔트리 개수 변경")
    changed = []
    for old, new in zip(parsed.entries, re2.entries):
        if (old.name, old.x, old.y, old.flag) != (new.name, new.x, new.y, new.flag):
            fail(f"메타데이터 변경: {old.name}")
        if old.content != new.content:
            changed.append(old.name)
    if sorted(changed) != sorted(stems):
        fail(f"예상과 다른 엔트리가 변경됨: {changed}")

    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    if not BACKUP.exists():
        shutil.copy2(GAME_LWG, BACKUP)
        print(f"백업: {BACKUP}")
    GAME_LWG.write_bytes(rebuilt)
    print(f"설치: {GAME_LWG}")
    print(f"  변경 엔트리 {len(changed)}개: {', '.join(sorted(changed))}")
    print(f"  {len(src)} -> {len(rebuilt)} bytes")
    print("RESULT: PASS")


mode = sys.argv[1] if len(sys.argv) > 1 else 'build'
if mode == 'build':
    build()
elif mode == 'install':
    install()
else:
    fail(f"알 수 없는 명령: {mode}")
