// qol.h — Forest 편의 기능 모듈 사이의 약속 (2026-11-21).
// 이 파일·qol_core.cpp·engine_bridge.cpp 는 통합 세션 몫이다. 갈래 세션은 자기 모듈 파일만 고친다.
// 약속을 바꿔야 하면 고치지 말고 통합 세션에 알린다(엔진 근거는 P:\AI\forest-qol\엔진_메모.md).
//
// 모듈
//   화면(qol_present.cpp)   창 크게·해상도 안 바꾸는 전체 화면·창 자리 기억, 그림자 판과 겹그림 찍기
//   진행(qol_play.cpp)      자동 진행+배율, Ctrl 읽음 보호, S 바로 저장·L 불러오기, Home 조작 안내, 알림 그리기
//   아이콘 줄(qol_buttons.cpp) compane 의 빈 auto·menu 칸 = 자동·지도 단추
//   4K 글자(qol_hitext.cpp)  늘린 창에서 대사·자막 글자를 화면 해상도로 다시 그림
// 모든 기능은 게임 폴더의 forest-qol.ini 한 줄로 끈다(Cfg). qol=0 이면 전부 끈다.
#pragma once
#include "chart.h"

namespace forest { namespace qol {

// ---------------------------------------------------------------- 공용(qol_core.cpp)
int Cfg(const char* key, int def);                 // forest-qol.ini 의 key=정수. 없으면 def
const std::wstring& Root();                        // 게임 폴더
HWND GameWindow();                                 // 서브클래스한 게임 창(아직 없으면 nullptr)
bool PatchBytes(uintptr_t at, const void* expect, const void* bytes, size_t n);  // expect 와 같을 때만 바꿈
void OpenChart();                                  // 이야기의 지도 열기 요청(F8 과 같은 길)

// 알림(왼쪽 위 한 줄). 아무 스레드. 그리기는 진행 모듈의 Play_PaintOverlays 가 한다.
void Toast(const wchar_t* text, DWORD ms = 2500);
bool ToastNow(std::wstring& text, float& alpha);   // 지금 보일 알림과 불투명도(0~1)
extern const RECT kToastRect;                      // 알림이 차지하는 800×600 좌표

// 창 안에서 800×600 그림이 들어가는 물리 사각형. 화면 모듈이 채운다(기본 = 1배, 여백 없음).
struct Layout { int clientW = 800, clientH = 600, ox = 0, oy = 0, cw = 800, ch = 600; };
Layout CurrentLayout();

// ---------------------------------------------------------------- 화면 모듈(qol_present.cpp)
bool Present_Install();                            // ForestChartInitialize 안, 게임 진입점 전
void Present_WindowReady(HWND h);                  // 게임 창 서브클래스 직후(VM 스레드에서 불림 — 창 일은 PostMessage 로)
bool Present_WndProc(HWND h, UINT m, WPARAM w, LPARAM l, LRESULT& r);  // 지도 처리보다 먼저. true = 여기서 끝
void Present_MapMouse(UINT m, LPARAM& l);          // 지도가 닫혔을 때 게임에 넘기기 직전: 창 물리 좌표 → 800×600
// 게임 창 DC 로 가는 그리기만 불린다(지도가 열려 있어도). true 면 ret 을 돌려주고 원래 그리기는 하지 않는다.
bool Present_BitBlt(HDC d, int x, int y, int w, int h, HDC s, int sx, int sy, DWORD rop, BOOL& ret);
bool Present_StretchBlt(HDC d, int x, int y, int w, int h, HDC s, int sx, int sy, int sw, int sh, DWORD rop, BOOL& ret);
void Present_InvalidateLogical(const RECT& r);     // 겹그림이 바뀐 800×600 사각형을 다시 찍어 달라. 아무 스레드
POINT Present_ToClient(int x, int y);              // 800×600 → 창 물리 좌표(합성 클릭을 게시할 때)

// ---------------------------------------------------------------- 진행 모듈(qol_play.cpp)
bool Play_Install();                               // ForestChartInitialize 안(코드 바꾸기는 여기서)
void Play_WindowReady(HWND h);
bool Play_WndProc(HWND h, UINT m, WPARAM w, LPARAM l, LRESULT& r);   // 지도 닫힘, 마우스는 이미 800×600
void Play_Fetch(void* script, int sid, uint32_t pc, uint16_t op, const uint8_t* cursor);  // VM 스레드, 명령마다
// 겹그림(알림·「자동 ×N」·조작 안내)을 dc 에 물리 좌표로 그린다. 화면 모듈이 찍기 직전에 부른다(창·VM 스레드 어느 쪽이든).
// L 은 그때의 배치, clip 은 이번에 찍는 물리 사각형. 그릴 것이 없으면 아무것도 하지 않는다.
void Play_PaintOverlays(HDC dc, const Layout& L, const RECT& clip);
bool Play_OverlayRects(std::vector<RECT>& out);   // 지금 겹그림이 차지하는 800×600 사각형들(화면 모듈이 다시 찍을 자리)
int Play_AutoButton();                             // 아이콘 줄 「자동」 단추. 1 = 처리함(꺼져 있으면 켬, 켜져 있으면 끔)
bool Play_AutoOn();

// ---------------------------------------------------------------- 4K 글자 모듈(qol_hitext.cpp) — 11-21 더함
bool HiText_Install();
void HiText_WindowReady(HWND h);
// 늘린 그림 위·겹그림 아래에 또렷한 글자를 물리 좌표로 그린다(L 이 1배면 그리지 않아도 된다).
void HiText_Paint(HDC dc, const Layout& L, const RECT& clip);
bool HiText_Rects(std::vector<RECT>& out);         // 지금 또렷한 글자가 차지하는 800×600 사각형들

// ---------------------------------------------------------------- 화면 모듈이 찍기 직전에 부르는 묶음(qol_core.cpp) — 11-21 더함
// 화면 모듈은 Play_PaintOverlays·Play_OverlayRects 대신 이 둘을 부른다(4K 글자 → 겹그림 순서).
void PaintAbove(HDC dc, const Layout& L, const RECT& clip);
bool AboveRects(std::vector<RECT>& out);

// ---------------------------------------------------------------- 아이콘 줄 모듈(qol_buttons.cpp)
bool Buttons_Install();
void Buttons_WindowReady(HWND h);
bool Buttons_WndProc(HWND h, UINT m, WPARAM w, LPARAM l, LRESULT& r);

// ---------------------------------------------------------------- engine_bridge.cpp 가 부르는 묶음(qol_core.cpp)
void Core_Install();
void Core_WindowReady(HWND h);

}}  // namespace forest::qol
