// qol.h — Forest 편의 기능 모듈 사이의 약속 (2026-11-21).
// 이 파일·qol_core.cpp·engine_bridge.cpp 는 통합 세션 몫이다. 갈래 세션은 자기 모듈 파일만 고친다.
// 약속을 바꿔야 하면 고치지 말고 통합 세션에 알린다(엔진 근거는 P:\AI\forest-qol\엔진_메모.md).
//
// 모듈
//   화면(qol_present.cpp)   창 크게·해상도 안 바꾸는 전체 화면·창 자리 기억, 그림자 판과 겹그림 찍기
//   진행(qol_play.cpp)      자동 진행+배율, Ctrl 읽음 보호, S 바로 저장·L 불러오기, Home 조작 안내, 알림 그리기
//   되감기(qol_rewind.cpp)  Backspace = 이전 대사로(소리 자막도 한 걸음, 누르고 있으면 계속)
//   아이콘 줄(qol_buttons.cpp) compane 의 빈 auto·menu 칸 = 자동·지도 단추
//   4K 글자(qol_hitext.cpp)  늘린 창에서 대사·자막 글자를 화면 해상도로 다시 그림
//   4K 그림(qol_hiart.cpp)   늘린 창에서 CG·스탠딩·배경을 4배 그림으로 다시 합성
// 모든 기능은 게임 폴더의 forest-qol.ini 한 줄로 끈다(Cfg). qol=0 이면 전부 끈다.
#pragma once
#include "chart.h"

namespace forest { namespace qol {

// ---------------------------------------------------------------- 공용(qol_core.cpp)
bool History_Open();
bool History_WindowAvailable();
bool History_Retired();                            // 게임 화면이 내려가 대화창·층 객체가 해제된 동안 참(갈고리가 없으면 늘 거짓)
int Cfg(const char* key, int def);                 // forest-qol.ini 의 key=정수. 없으면 def
const std::wstring& Root();                        // 게임 폴더
UINT ShortcutKey(HWND window, WPARAM key, LPARAM messageBits);
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
bool Present_Active();
bool Present_Install();                            // ForestChartInitialize 안, 게임 진입점 전
void Present_WindowReady(HWND h);                  // 게임 창 서브클래스 직후(VM 스레드에서 불림 — 창 일은 PostMessage 로)
bool Present_WndProc(HWND h, UINT m, WPARAM w, LPARAM l, LRESULT& r);  // 지도 처리보다 먼저. true = 여기서 끝
void Present_MapMouse(UINT m, LPARAM& l);          // 지도가 닫혔을 때 게임에 넘기기 직전: 창 물리 좌표 → 800×600
// 게임 창 DC 로 가는 그리기만 불린다(지도가 열려 있어도). true 면 ret 을 돌려주고 원래 그리기는 하지 않는다.
bool Present_BitBlt(HDC d, int x, int y, int w, int h, HDC s, int sx, int sy, DWORD rop, BOOL& ret);
bool Present_StretchBlt(HDC d, int x, int y, int w, int h, HDC s, int sx, int sy, int sw, int sh, DWORD rop, BOOL& ret);
void Present_InvalidateLogical(const RECT& r);     // 겹그림이 바뀐 800×600 사각형을 다시 찍어 달라. 아무 스레드
POINT Present_ToClient(int x, int y);              // 800×600 → 창 물리 좌표(합성 클릭을 게시할 때)
const uint32_t* Present_ShadowBits();              // 800×600 그림자 판(BGRA 위→아래). PaintAbove 안(화면 잠금 안)에서만 읽는다 — 11-21 4K 그림 요청

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
bool Play_GuideOpen();
bool Play_AutoOn();
void Play_AutoOff();                               // 되감기 모듈: 자동 진행 중이면 끈다(게임 창 스레드)
void Play_Rewound();                               // 되감기 모듈: 문맥을 되돌렸다(VM 스레드) → 「고른 뒤 자동 계속」 기억을 버린다

// ---------------------------------------------------------------- 4K 글자 모듈(qol_hitext.cpp) — 11-21 더함
bool HiText_Install();
void HiText_WindowReady(HWND h);
// 늘린 그림 위·겹그림 아래에 또렷한 글자를 물리 좌표로 그린다(L 이 1배면 그리지 않아도 된다).
void HiText_Paint(HDC dc, const Layout& L, const RECT& clip);
bool HiText_Rects(std::vector<RECT>& out);         // 지금 또렷한 글자가 차지하는 800×600 사각형들
bool HiText_DialogueBounds(RECT& out);             // 지금 화면에 찍힌 본문 대사 글자들의 800×600 합집합 사각형
bool HiText_SubtitleBounds(RECT& out);             // 지금 화면에 찍힌 노란 음성 자막(구운 글)의 800×600 합집합 사각형
void HiText_ForceRepaint();                        // 해설 황금 문장 상태가 바뀔 때 엔진 앞 판을 다시 찍게 요청

// ---------------------------------------------------------------- 4K 그림 모듈(qol_hiart.cpp) — 11-21 더함
bool HiArt_Install();
void HiArt_WindowReady(HWND h);
// 늘린 그림 위·글자 아래: 4배 그림(CG·스탠딩·배경)으로 원작과 같게 다시 합성할 수 있는 곳만 물리 좌표로 덮어 그린다.
void HiArt_PaintBase(HDC dc, const Layout& L, const RECT& clip);
bool HiArt_Rects(std::vector<RECT>& out);          // 4배 그림이 차지하는(또는 막 바뀐) 800×600 사각형들
struct VisibleArtLayer { int layer = 0; std::string asset; RECT rect = {}; };
void HiArt_GetVisibleLayers(std::vector<VisibleArtLayer>& out);  // 지금 화면에 보이는 그림 층(grpe/grpo_bg/grpo_ci 등)과 논리 사각형
uint32_t HiArt_Epoch();                                          // 그림 층이 새로 읽힐 때마다 증가하는 세대 번호
int HiArt_LayerKeyCount();                                       // 그림 경로를 쥐고 있는 층 수(시험용)
long HiArt_GuardFaults();                                        // SEH 로 넘어간 엔진 메모리 읽기 수(시험용)

// ---------------------------------------------------------------- 화면 모듈이 찍기 직전에 부르는 묶음(qol_core.cpp) — 11-21 더함
// 화면 모듈은 Play_PaintOverlays·Play_OverlayRects 대신 이 둘을 부른다(4K 그림 → 4K 글자 → 겹그림 순서).
void PaintAbove(HDC dc, const Layout& L, const RECT& clip);
bool AboveRects(std::vector<RECT>& out);

// ---------------------------------------------------------------- 아이콘 줄 모듈(qol_buttons.cpp)
bool Buttons_Install();
void Buttons_WindowReady(HWND h);
bool Buttons_WndProc(HWND h, UINT m, WPARAM w, LPARAM l, LRESULT& r);

// ---------------------------------------------------------------- 되감기 모듈(qol_rewind.cpp) — 11-25 더함
// Backspace = 이전 대사로(그 대사가 떴을 때의 그림·소리·자막·변수까지). 엔진 근거·설계는 s-rewind\조사.md.
bool Rewind_Install();
bool Rewind_On();
void Rewind_Fetch(uint16_t op, const uint8_t* cursor);   // VM 스레드, 명령마다. 지도 모듈의 ObserveOpcode 보다 먼저 부른다(회차 기록의 시점을 그 명령을 보기 전으로 적는다)
void Rewind_Checkpoint();                          // 엔진이 「지금 상태」 한 벌을 뜬 직후(대사·선택지·클릭 대기), CapturePrimary 뒤
void Rewind_SecondaryChanged();                    // 엔진이 「직전 선택지」 한 벌을 바꾼 직후
void Rewind_Reset(const char* why);                // 불러오기·엔진의 「직전 선택지로」: 모아 둔 것을 버린다
HANDLE Rewind_WakeEvent();                         // 기다림을 바로 깨우는 이벤트(꺼져 있으면 nullptr)
bool Rewind_WaitShouldReturn();                    // VM 스레드, 입력 대기 안: true 면 클릭이 온 것처럼 돌아간다
bool Rewind_CuttableWait(HANDLE h);                // VM 스레드: 지금 들어가는 기다림이 클릭으로도 끊기는 기다림(음성 끝·효과음 끝·시간)인가
bool Rewind_CutNow();                              // 그 기다림 안: true 면 기다리던 일이 끝난 것처럼 돌아간다
void Rewind_WaitEnded(HANDLE h);                   // 그 기다림이 제 일로 끝났다(요청으로 끊은 것이 아니다)
bool Rewind_AtFetch();                             // VM 스레드, 명령을 꺼내기 직전: true = 문맥을 되돌렸다(스크립트 객체를 다시 읽을 것)
bool Rewind_HoldPresent();                         // 되감는 동안 게임 창 찍기를 건너뛸지
bool Rewind_WndProc(HWND h, UINT m, WPARAM w, LPARAM l, LRESULT& r);   // Play_WndProc 뒤

// ---------------------------------------------------------------- 해설판 모듈(qol_cm.cpp) — v2
class CmPresentationFrame {
public:
    CmPresentationFrame();
    ~CmPresentationFrame();
    CmPresentationFrame(const CmPresentationFrame&) = delete;
    CmPresentationFrame& operator=(const CmPresentationFrame&) = delete;
};
bool Cm_Install();
void Cm_WindowReady(HWND h);
bool Cm_Enabled();                                 // 인게임 설정 「해설 모드: 켬」 여부(초기 기본값 = false/끔)
bool Cm_Modal();                                   // 해설 카드 또는 F7 해설 도감이 열려 게임 입력·자동을 멈춰야 하는가
bool Cm_CoversScreen();                            // F7 해설 도감이 화면 전체를 불투명하게 덮고 있는가(아래 4K 그림·글자 합성 생략)
bool Cm_WantsGoldenText();                         // 1배 창에서도 황금 문장 채색을 위해 HiText 합성을 가동할지
bool Cm_GoldenTint(const RECT& glyphRect, uint32_t origColor, uint32_t& outColor);
bool Cm_WndProc(HWND h, UINT m, WPARAM w, LPARAM l, LRESULT& r);
void Cm_Fetch(void* script, int sid, uint32_t pc, uint16_t op, const uint8_t* cursor);
void Cm_OnReset(const char* why);                  // 되감기·불러오기·롤백 직후 해설 상태 동기화
void Cm_PaintOverlays(HDC dc, const Layout& L, const RECT& clip);
bool Cm_OverlayRects(std::vector<RECT>& out);

// ---------------------------------------------------------------- engine_bridge.cpp 가 부르는 묶음(qol_core.cpp)
void Core_Install();
void Core_WindowReady(HWND h);

}}  // namespace forest::qol
