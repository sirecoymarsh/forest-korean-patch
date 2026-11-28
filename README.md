# Forest(라이어소프트, 2004) 한국어 패치 작업물

비공개 보관용 저장소. 원본 게임 파일·4K 그림(hiart)은 넣지 않았다. 바로 까는 패치 ZIP(한국어 오프닝 영상 포함)은 릴리스에 있다.

| 폴더 | 원래 위치 | 내용 |
|---|---|---|
| `qol-and-storymap/` | `P:\AI\forest-qol` | 통합 DLL(ForestChart.dll) 소스 `native/` — 이야기의 지도 2.0 + 편의 기능(화면·진행·단추·4K 글자·4K 그림·되감기), 갈래별 시험 도구·기록, 특전 「오프닝」(`extras-opening-20261125`) |
| `translation-build/` | `P:\AI\forest-kr-build` | 번역 반입·대본 빌드 도구, 패치 목록, 검수 기록 |
| `storymap-2.0/` | `P:\AI\forest-flowchart-claude` | 이야기의 지도 2.0 모델·도구 |
| `review/` | `Y:\AI\forest-deep-review`, `P:\AI\forest-gemini-review` | 깊은 검수·제미나이 검수 목록(스포일러 있음) |
| `assets-ko/` | 놀이 사본 `P:\AI\forest-kr-build\game` (2026-11-25) | 게임이 읽는 한국어 덮어쓰기 파일 그대로: 대본 `scr`, 그림 `grpe`·`grpo`·`grps`, 지도 그림·글꼴 `fc` |
| `commentary-mode/` | 해설판 사본 `Y:\AIorest-cm-v2\game`, DLL 소스 `Y:\AI\claude-workorest-cm-v2-deepix-20261128ix
ative` | 해설판 DLL 소스 `native/`(해설 모드 + 위 편의 기능, 창 닫기 굳음·자막 머묾 고침, 5장 메뉴는 원작 흐름), 해설 자료 `game-files/cm/`, 해설판 `forest-qol.ini` |
| `release/` | `Y:\AI\claude-work\patches\delta-kit`, `Y:\AI\claude-workorest-release-cm` | 차분 꾸러미 만들기·설치 시험 도구, 판별 꾸러미 설정 |

## 릴리스

- **`patch-20261128-commentary` (최신, 해설판 기준)**: `ForestChart.dll` `38969d4b4643` + 해설 자료 `commentary_v2.json` `94ab78833823` + 대본 `scr¨0.gsc` `80c3759726fd`(원작 흐름) + 한국어 오프닝 R28. 사용자 손 확인(2026-11-28)을 통과한 해설판 사본과 같은 파일이다. 단, 그 사본의 `Forest.exe` 는 시험용으로 뮤텍스 이름 한 글자를 바꿔 둔 것이라 꾸러미에는 원래 이름의 실행 파일을 쓴다.
- `patch-20261125`: 해설 모드 이전 판(DLL `79c70107235b`).

DLL 두 갈래: `commentary-mode/native`(릴리스에 들어가는 해설판 DLL)와 `qol-and-storymap/native`(놀이 사본 통합 빌드, 2026-11-28 `5499d7f399ee` — 해설 모드 없음, 한/영 한글 상태 단축키 보강 포함)는 따로 고쳐 왔다. 한쪽 고침을 다른 쪽에 옮길 때는 두 소스를 대조할 것.
