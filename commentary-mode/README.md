# Forest 해설 모드(해설판)

- `native/` — 릴리스 `patch-20261128-commentary` 의 `ForestChart.dll`(`38969d4b4643eb70…`) 소스. `build.cmd` 로 빌드(MSVC x86). 빌드 폴더가 다르면 MSVC 가 이름 없는 네임스페이스 꾸밈 이름을 소스 경로로 만들어 DLL 바이트가 달라진다 — 같은 코드인지는 `.obj` 코드 구역으로 비교할 것.
- DLL 은 대본 명령부 해시를 확인한다. `scr¨0.gsc` 는 원작 흐름판(`80c37597…`)과 짝이고, 5장 메뉴를 고친 대본과 섞으면 지도·자동·되감기·해설이 통째로 꺼진다.
- `game-files/cm/` — 게임 폴더 `cm\` 에 그대로 들어가는 자료: `commentary_v2.json`(해설 카드, `94ab7883…`), `ui/`(카드·단추 그림), `ext/`(Rackham·Tenniel·Wyeth 공개 저작물 삽화와 `manifest.json`).
- `game-files/forest-qol.ini` — 해설판 설정(`cm=1` = 해설 모듈을 읽음, 켜고 끄기는 게임 안 설정 화면, 처음엔 꺼짐).
- 해설 카드 글은 검수 중이다(다음 판에서 바뀔 수 있음).
