# -*- coding: utf-8 -*-
"""Forest 편의 기능 묶음: out\\Forest-qol-<ver>\\ + zip.

지도 2.0 설치기(Manage-ForestStoryMap.ps1, manifest 방식)를 그대로 쓰고 실을 것만 늘렸다.
  바꿈(바이트 차분만 실음): Forest.exe(지도 DLL 로더판), scr\\0001.gsc(타이틀 「이야기의 지도」 단추)
  더함: ForestChart.dll(지도 + 편의 기능 합본), scr\\9000.gsc, fc\\(지도 그림·글꼴), grps\\compane.lwg(아이콘 줄),
        forest-qol.ini(기능 켜고 끄기, 모두 기본값 — 지우면 같은 기본값)
기준 사본(사용자 플레이 사본, 읽기만): P:\\AI\\forest-kr-build\\game
"""
import base64, hashlib, json, os, shutil, sys, zipfile

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.0'
NAME = 'Forest-qol-' + VER
ROOT = r'P:\AI\forest-qol'
OUT = os.path.join(ROOT, 'out', NAME)
BASE_GAME = r'P:\AI\forest-kr-build\game'                   # 원래 한국어판(읽기만)
MAP_GAME = r'Y:\AI\forest-qol-test\game'                     # 지도 2.0(코덱스 10-15 판)이 깔린 시험 사본
MAP_PKG = r'P:\AI\forest-flowchart-claude\out\Forest-story-map-2.0.0'
MAP_EXE = os.path.join(r'Y:\AI\forest-qol-test', 'Forest.exe.base')   # 시험용 뮤텍스 이름 바꾸기 전 로더판
BASE_EXE = 'f618b6f3948b26991861b088f4dc21b780aeb0b585783db059f2b3ffcc7b2c0f'
LOADER_EXE = 'eef9179e23276deefaa4b31b947e6ed4d2f51d3faac25da95f90643a1f04d555'
BASE_0001 = '0f007fea52433d8b82b338f3e6c255a41655d5f4cf8112e8363fc452190f3365'
INI = """; Forest 편의 기능 켜고 끄기 (1 = 켬, 0 = 끔). 이 파일을 지워도 아래 기본값으로 돈다.
qol=1                    ; 0 이면 편의 기능 모두 끔(이야기의 지도는 그대로)
; 화면
present=1                ; 창 크게·창 자리 기억·해상도를 안 바꾸는 전체 화면의 바탕
present_smooth=1         ; 늘릴 때 부드럽게(0 = 화소 그대로)
window_memory=1          ; 끌 때 창 자리·크기를 기억
borderless_fullscreen=1  ; 전체 화면에서 모니터 해상도를 바꾸지 않음(0 = 원작처럼 800×600 으로 바꿈)
window_keep_aspect=1     ; 창 크기를 바꿀 때 4:3 유지
hitext=1                 ; 큰 창에서 대사·자막 글자를 화면 해상도로 다시 그림
hiart=1                  ; 큰 창에서 CG·스탠딩·배경을 4배 그림으로(「고화질 그림」 꾸러미의 hiart\ 가 있을 때만)
hiart_cache_mb=256       ; 4배 그림을 메모리에 두는 양(MB)
; 진행
auto_key=1               ; A = 자동 진행(누를 때마다 ×1~×5). 끄기는 클릭·Enter
auto_text_wait=1         ; 자동 진행 기다림을 글 길이에 맞춤
auto_base_ms=1200        ; ×1 기다림 = 1.2초 + 글자당 0.08초(음성은 끝까지)
auto_char_ms=80
auto_after_choice=1      ; 선택지를 고른 뒤에도 자동 진행 계속
auto_indicator=1         ; 「자동 ×N」 표시
ctrl_protect=1           ; 설정이 「읽은 부분만」이면 Ctrl 건너뛰기도 안 읽은 대사에서 멈춤
quick_save_key=1         ; S = 다음 빈 칸에 바로 저장
load_key=1               ; L = 불러오기 화면
key_guide=1              ; Home = 조작 안내
; 되감기
rewind=1                 ; Backspace = 이전 대사로 되감기(그림·소리·노란 자막까지, 누르고 있으면 계속)
rewind_depth=300         ; 기억하는 걸음 수(한 걸음 약 37KB)
; 아이콘 줄
icon_row=1               ; 0 이면 원래 아이콘 줄 그림·동작
icon_auto=1              ; 「자동」 단추
icon_map=1               ; 「이야기의 지도」 단추
"""


def sha(b):
    return hashlib.sha256(b).hexdigest()


def rd(p):
    return open(p, 'rb').read()


def diff(a, b):
    out, n, i = [], max(len(a), len(b)), 0
    while i < n:
        if i < len(a) and i < len(b) and a[i] == b[i]:
            i += 1; continue
        j = i
        while j < n and not (j < len(a) and j < len(b) and a[j] == b[j] and a[j:j + 8] == b[j:j + 8]):
            j += 1
        out.append({'offset': i, 'data': base64.b64encode(b[i:j]).decode()})
        i = j
    return out


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    pay = os.path.join(OUT, 'payload')
    os.makedirs(pay)
    files = []
    base_exe, new_exe = rd(os.path.join(BASE_GAME, 'Forest.exe')), rd(MAP_EXE)
    assert sha(base_exe) == BASE_EXE and sha(new_exe) == LOADER_EXE, 'exe'
    files.append({'path': 'Forest.exe', 'kind': 'replace', 'original_sha256': BASE_EXE, 'installed_sha256': LOADER_EXE,
                  'installed_size': len(new_exe), 'changes': diff(base_exe, new_exe)})
    base_t, new_t = rd(os.path.join(BASE_GAME, 'scr', '0001.gsc')), rd(os.path.join(MAP_GAME, 'scr', '0001.gsc'))
    assert sha(base_t) == BASE_0001, '0001'
    files.append({'path': 'scr/0001.gsc', 'kind': 'replace', 'original_sha256': BASE_0001, 'installed_sha256': sha(new_t),
                  'installed_size': len(new_t), 'changes': diff(base_t, new_t)})

    def add(rel, data):
        dst = os.path.join(pay, rel.replace('/', os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, 'wb').write(data)
        files.append({'path': rel, 'kind': 'add', 'payload': 'payload/' + rel, 'installed_sha256': sha(data)})

    add('ForestChart.dll', rd(os.path.join(ROOT, 'build', 'ForestChart.dll')))
    add('scr/9000.gsc', rd(os.path.join(MAP_GAME, 'scr', '9000.gsc')))
    for n in sorted(os.listdir(os.path.join(MAP_PKG, 'payload', 'fc'))):
        add('fc/' + n, rd(os.path.join(MAP_PKG, 'payload', 'fc', n)))
    add('grps/compane.lwg', rd(os.path.join(ROOT, 'assets', 'grps', 'compane.lwg')))
    add('forest-qol.ini', INI.replace('\n', '\r\n').encode('utf-8'))   # BOM 없이(첫 줄 주석이 읽히게)
    old = json.load(open(os.path.join(MAP_PKG, 'manifest.json'), encoding='utf-8'))
    manifest = {'schema': 2, 'version': 'qol-' + VER,
                'supported': 'Forest Korean patch (command sections of the audited build)',
                'prerequisites': old['prerequisites'], 'code_sections': old['code_sections'], 'files': files}
    json.dump(manifest, open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    shutil.copyfile(os.path.join(MAP_PKG, 'Manage-ForestStoryMap.ps1'), os.path.join(OUT, 'Manage-ForestStoryMap.ps1'))
    shutil.copyfile(os.path.join(ROOT, 'docs', '사용법.txt'), os.path.join(OUT, '사용법.txt'))
    z = os.path.join(ROOT, 'out', NAME + '.zip')
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
        for d, _, fs in os.walk(OUT):
            for f in fs:
                p = os.path.join(d, f)
                zf.write(p, os.path.join(NAME, os.path.relpath(p, OUT)))
    dll = [f for f in files if f['path'] == 'ForestChart.dll'][0]['installed_sha256']
    print('package', OUT, 'files', len(files), 'dll', dll[:12], 'zip', os.path.getsize(z))


if __name__ == '__main__':
    main()
