// qol_play.cpp — 진행 모듈(세션 「진행」 몫, 2026-11-21).
//
// 하는 일
//   1. 자동 진행: A(한글 입력 상태 포함, 누르고 있어도 한 번) — 꺼져 있으면 켜고 ×1, 켜져 있으면 ×2→×3→×4→×5→×1.
//      Backspace = 끄기. 클릭·Enter 로 꺼지는 원작 동작은 그대로 둔다.
//      켜는 모양은 엔진의 auto 단추(0x410bd0)와 같다: 아이콘 줄을 숨기고(+0x2c7c=1, 0x411280(0)) 0x4166d0(0,0).
//      끄는 모양도 엔진과 같다: [0x466408]=0 + 메시지 창 0x410c20(줄 다시 보이기).
//   2. 글 길이에 맞춘 대기: 자동 대기 0x41c70a 의 Sleep(1000) 자리를 바꾼다.
//      기다림 = (기본 1.2초 + 보이는 글자 하나에 0.08초) ÷ 배율, 대사가 찍히기 시작한 때부터 잰다.
//      다 찍힌 뒤로도 최소 1초÷배율(0.25초 밑으로는 안 내림)은 둔다 = ×1 은 원작의 「다 찍힌 뒤 1초」보다 짧아지지 않는다.
//      음성이 끝날 때까지 기다리는 엔진 단계(0x43f690(1))는 그대로 둔다(음성은 끝까지).
//      기다리는 동안이나 음성을 기다리는 동안 자동이 꺼지면 원작의 클릭 대기(0x41c72b)로 간다(원작은 그냥 넘어갔다).
//      Home 안내·대화창 숨기기·설정·세이브·불러오기 화면·지도가 열려 있으면 셈을 멈춘다.
//      글 없는 클릭 대기(명령 0x0a, 0x41de3b)의 자동 1초도 같은 배율로 나누고, 자동이 꺼지면 클릭 대기(0x41de4a)로.
//      ×1 값의 까닭: 소리 내지 않고 읽는 한국어 산문은 분당 600~900음절쯤이라 그 가운데(750음절 = 초당 12.5자)를 잡았다.
//      대사 대부분이 10~50자(전수 11,768줄)라 ×1 에서 한 줄 2~5초, 3줄 가득(60자)이면 약 6초. 바꾸려면 ini 의
//      auto_base_ms·auto_char_ms.
//   3. 선택 뒤에도 자동 계속: 이야기 선택지는 모두 CHOICE(명령 0x0e, 101개)이고 엔진은 0x41e054 에서 자동을 끈다.
//      자동이 켜진 채 CHOICE 를 만나면 기억해 두었다가, 고른 뒤 같은 깊이·같은 대본에서 처음 꺼낸 명령이 CHOICE 인자의
//      갈래 목적지(엔진은 고른 갈래로 바로 뛴다)이면 다시 켠다. 불러오기 등으로 VM 스레드가 바뀌면 기억을 버린다.
//      (0x41d7fd 는 타이틀·특전 메뉴의 단추 고르기 0x49, 0x41e76f 는 하위 대본 부르기 0x41e730 — 이야기 선택지가 아니다.)
//   4. Ctrl 읽음 보호: 대사(0x51)를 꺼낼 때 Ctrl 건너뛰기 중이고 설정이 「읽은 부분만」인데 안 읽은 줄이면
//      Ctrl 깃발([0x4663f8]·[0x466400])을 내리고, Ctrl 을 뗄 때까지 키 반복(엔진은 반복마다 한 줄씩 넘긴다)을 삼킨다.
//   5. S = 다음 빈 칸에 바로 저장(엔진 0x418a80, 게임 창 스레드). 가장 최근에 쓴 칸 다음의 빈 칸(끝에 닿으면 앞에서).
//      L = 불러오기 화면: 설정 화면 「불러오기」 단추 콜백 0x416210(효과음 + 0x415d80).
//   6. Home = 조작 안내 한 장(지도 2.0 틀). 열린 동안 게임 입력을 막고 Home·Esc·클릭으로 닫는다. 켜진 기능만 적는다.
//   7. 겹그림: 알림(qol::Toast), 「자동 ×N」(자동 중엔 엔진이 아이콘 줄을 숨기므로 그 자리), 조작 안내.
//
// 자동 진행 중에 오른쪽 클릭·F8·L: 엔진은 클릭 대기에서만 설정 화면·지도를 연다(자동 대기 중엔 단추 줄이 꺼져 있어
//   오른쪽 클릭이 아무 일도 안 하고, 지도는 입력 대기에서만 연다). 그래서 이 셋은 자동을 끄고, 클릭 대기에 들어가면 연다.
//   Shift 는 자동을 끄지 않고 대화창만 숨긴다(숨기기 단추 콜백 0x416570). 숨긴 동안 자동 셈이 멈춘다.
// 자동 대기 중 불러오기·되감기: 엔진은 VM 문맥을 먼저 덮어쓰고 다음 입력 대기에서 옛 VM 스레드를 끝낸다(0x4151c0 →
//   0x420600, 입력 대기 0x420680 의 끝내기 깃발). 그래서 대기 중 문맥이 바뀌면 명령을 더 실행하지 않고 클릭 대기로 보낸다.
//   (원작의 1초 Sleep 도 같은 틈이 있었다 — 자동을 못 켜서 드러나지 않았을 뿐.)
// 엔진은 불러오기 뒤 게임 화면을 다시 시작하며 자동 깃발을 0 으로 둔다(0x41513c) → 불러온 뒤에는 자동이 꺼져 있다.
//
// 설정(forest-qol.ini): play=1(이 모듈 전부), auto_key=1, auto_text_wait=1, auto_after_choice=1, ctrl_protect=1,
//   quick_save_key=1, load_key=1, key_guide=1, auto_indicator=1, auto_base_ms=1200, auto_char_ms=80,
//   play_log=0(1 이면 줄마다 기다린 시간을 events.log 에 — 진단용).
#include "qol.h"
#include <windowsx.h>
#include <objidl.h>
#include <gdiplus.h>
#include <imm.h>
#include <algorithm>
#include <cmath>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <memory>
#pragma comment(lib, "gdiplus.lib")
#pragma comment(lib, "imm32.lib")
#pragma comment(lib, "msimg32.lib")

using namespace Gdiplus;

namespace forest { namespace qol {
namespace {

// ---------------------------------------------------------------- 엔진 주소(Forest.exe f618b6… / 지도 로더판 eef917…, 코드 구역 같음)
#define EV(a) (*(volatile int*)(uintptr_t)(a))
#define EW(a) (*(volatile uint16_t*)(uintptr_t)(a))
const uintptr_t kEngineObj = 0x466398, kMsgWinPtr = 0x46630c;
const uintptr_t kAuto = 0x466408, kCtrlKey = 0x4663f8, kCtrlSkip = 0x466400, kTabReq = 0x4663fc, kTabSkip = 0x466404;
const uintptr_t kClickWait = 0x4663e8, kChoiceBox = 0x4663cc, kSelect = 0x466418;
const uintptr_t kSettings = 0x46640c, kSaveScr = 0x466410, kLoadScr = 0x466414, kHidden = 0x466420;
const uintptr_t kSkipRange = 0x466460 /*u16: 0 = 읽은 부분만*/, kSaveOk = 0x4664cc, kCheckpointOk = 0x4664d0, kMenuLock = 0x466430 /*u16*/;
const uintptr_t kDepth = 0x4664bc /*u16*/, kDepthScripts = 0x46647e /*u16[]*/;
const uintptr_t kConfigPtr = 0x46e924;   // char*: +0x43 세이브 폴더, +0x25 이름 머리
const uintptr_t kWinBarActive = 0x2c74, kWinBarHidden = 0x2c7c;   // 메시지 창 객체 칸

// 엔진 함수
const uintptr_t fAutoOn = 0x4166d0;        // int __stdcall(int,int): 자동 켜기(선택지·단추 고르기면 거절하고 줄을 되살림)
const uintptr_t fLoadButton = 0x416210;    // int __stdcall(int,int): 설정 화면 「불러오기」 = 효과음 0x418e80(1) + 0x415d80
const uintptr_t fScriptButton = 0x416470;  // int __stdcall(int,int idx): 대본 단추의 시스템 동작(5 = 불러오기 화면), 단추 고르기 중에만
const uintptr_t fBarAutoOff = 0x410c20;    // thiscall(메시지 창): +0x2c7c=0, 줄 다시 보이기
const uintptr_t fBarShow = 0x411280;       // thiscall(메시지 창, int): 줄 보이기/숨기기(+0x2c7c 가 1 이면 숨김)
const uintptr_t fMenuPath = 0x410b90;      // thiscall(메시지 창): 오른쪽 클릭과 같은 길(설정 화면)
const uintptr_t fHideButton = 0x416570;    // int __stdcall(int,int): 아이콘 줄 숨기기 단추 콜백([0x466420]=1)
const uintptr_t fUpdateDirty = 0x43d240;   // thiscall(엔진 객체)
const uintptr_t fFullRedraw = 0x43d350;    // thiscall(엔진 객체)
const uintptr_t fSkipResync = 0x41e8b0;    // 건너뛰기가 끝날 때 엔진이 장면을 다시 맞추는 함수(VM 스레드)
const uintptr_t fSave = 0x418a80;          // void __cdecl(u16 칸) — 지도 DLL 의 save 갈고리를 거친다
const uintptr_t fIsRead = 0x418d90;        // int __cdecl(대본, 슬롯)
const uintptr_t fSlotText = 0x413080;      // char* __thiscall(스크립트 객체, 슬롯)

// 바꾸는 자리
const uintptr_t pTextWait = 0x41c70a;      // push 1000 / call [Sleep]  (11바이트) → jmp textWaitStub
const uintptr_t pAfterVoice = 0x41c721;    // mov [0x4663d8], ebx      (6바이트)  → jmp afterVoiceStub
const uintptr_t pPauseWait = 0x41de3b;     // push 1000 / call [Sleep]  (11바이트) → call pauseWait; test; jz 0x41de4a
const uint8_t kSleep1000[11] = {0x68, 0xe8, 0x03, 0x00, 0x00, 0xff, 0x15, 0x68, 0x90, 0x45, 0x00};
const uint8_t kMovD8[6] = {0x89, 0x1d, 0xd8, 0x63, 0x46, 0x00};
uintptr_t gPlayJmpVoice = 0x41c715, gPlayJmpEnd = 0x41c721, gPlayJmpClick = 0x41c72b, gPlayJmpRet = 0x41c727;

void* msgWin() { return *(void* volatile*)kMsgWinPtr; }
void* engineObj() { return *(void* volatile*)kEngineObj; }

// ---------------------------------------------------------------- 설정·상태
struct Config {
    bool on = false, autoKey = true, textWait = true, afterChoice = true, ctrlProtect = true;
    bool quickSave = true, loadKey = true, guide = true, indicator = true, presentKeys = true;
    int baseMs = 1200, charMs = 80;
    bool debugLog = false;   // play_log=1: 줄마다 기다린 시간을 events.log 에(진단용)
} C;
bool gTextWaitPatched = false;
HWND gWnd = nullptr;
UINT gMsgPlay = 0;
const UINT_PTR kTimerId = 0xF0E60;

volatile LONG gRate = 1;            // 자동 배율 1~5
volatile DWORD gMsgStart = 0;       // 지금 대사가 찍히기 시작한 때(0x51 을 꺼낸 때)
volatile LONG gMsgHalf = 0;         // 지금 대사의 보이는 글자 수 ×2(한글 등 2바이트 글자 = 2, 반각 = 1, 빈칸 0)
volatile LONG gInWait = 0;          // 1 = 자동 글 대기 중, 2 = 음성 대기 중(VM 스레드)
volatile DWORD gVoiceFrom = 0;      // 음성 대기에 들어간 때(play_log 용)
volatile LONG gGuideOpen = 0;
volatile LONG gCtrlBlocked = 0;     // Ctrl 을 뗄 때까지 Ctrl 키 반복을 삼킨다
volatile LONG gStopTabSkip = 0;     // 안내를 연 동안 Tab 건너뛰기를 VM 스레드에서 멈춰 달라
volatile LONG gChoicePending = 0;   // 자동인 채 CHOICE 를 만났다
volatile LONG gChoiceSid = 0, gChoicePc = 0, gChoiceDepth = 0;
uint32_t gChoiceTargets[5] = {};     // CHOICE 인자의 갈래 목적지(엔진은 고른 갈래로 바로 뛴다)
volatile DWORD gChoiceThread = 0;   // 불러오기를 하면 VM 스레드가 바뀐다 → 기억을 버린다
volatile LONG gLastOp = 0;          // VM 이 마지막으로 꺼낸 명령(0x51 이면 아직 그 대사를 처리하는 중: 찍기·대기)
volatile LONG gBarHideReq = 0;      // VM 스레드가 자동을 되살렸으니 창 스레드에서 줄을 숨겨 달라
enum { PendNone = 0, PendMenu = 1, PendLoad = 2 };
volatile LONG gPending = PendNone;  // 자동을 끈 뒤 클릭 대기에 들어가면 할 일
DWORD gPendingAt = 0;
bool gCtrlHintShown = false;
DWORD gHintAt = 0;
int gLastIndSig = -1;
bool gToastWasOn = false;
bool gGuideMouseDown = false;

bool autoOn() { return EV(kAuto) != 0; }
bool skipping() { return EV(kCtrlKey) || EV(kCtrlSkip) || EV(kTabReq) || EV(kTabSkip); }
bool screensOpen() { return EV(kSettings) || EV(kSaveScr) || EV(kLoadScr); }
bool barActive() { auto w = (uint8_t*)msgWin(); return w && *(volatile int*)(w + kWinBarActive) != 0; }
bool countPaused() { return gGuideOpen || Cm_Modal() || EV(kHidden) || screensOpen() || ChartIsOpen(); }

// 대본 깊이별 번호(엔진 읽음 검사와 같은 식)
int scriptAt(int d) { return ((volatile uint16_t*)kDepthScripts)[d]; }
int depth() { int d = EW(kDepth); return d < 0 ? 0 : (d > 15 ? 15 : d); }
int topScript() { return scriptAt(depth()); }
bool stackHas(int lo, int hi) { for (int i = 0, d = depth(); i <= d; ++i) { int s = scriptAt(i); if (s >= lo && s <= hi) return true; } return false; }
// 대기 중 VM 문맥이 밖에서 바뀌었는가(불러오기·되감기는 VM 문맥 0x46646c~ 을 통째로 바꾼다)
struct Ctx { int d, s; uint32_t pc; };
Ctx ctxNow() { int d = depth(); return Ctx{d, scriptAt(d), ((volatile uint32_t*)0x466494)[d]}; }
bool ctxChanged(const Ctx& a) { Ctx b = ctxNow(); return a.d != b.d || a.s != b.s || a.pc != b.pc; }
Ctx gWaitCtx = {0, 0, 0};   // 자동 글 대기에 들어갈 때의 VM 문맥(음성 대기 뒤에 다시 대 본다)
std::string stackText() { std::string s; for (int i = 0, d = depth(); i <= d; ++i) { char b[8]; sprintf_s(b, "%04d", scriptAt(i)); if (i) s += '>'; s += b; } return s; }

const RECT kIndRect = {640, 574, 800, 600};   // 「자동 ×N」: 자동 중엔 엔진이 아이콘 줄(x 607~800, 아이콘 y 585~600)을 숨기므로 그 자리

// ---------------------------------------------------------------- 엔진 부르기(게임 창 스레드)
void barHideForAuto() {
    auto w = (uint8_t*)msgWin(); if (!w) return;
    *(volatile int*)(w + kWinBarHidden) = 1;
    ((void(__thiscall*)(void*, int))fBarShow)(w, 0);
    if (engineObj()) ((void(__thiscall*)(void*))fUpdateDirty)(engineObj());
}
void engineAutoOff() {
    EV(kAuto) = 0;
    if (msgWin()) ((void(__thiscall*)(void*))fBarAutoOff)(msgWin());
}
// 켜기: 클릭 대기면 엔진 길 그대로(그 줄을 넘긴다). 대사가 찍히는 중이면 깃발만 세운다
// (엔진 길은 입력 대기를 풀면서 찍히는 글을 한꺼번에 끝내 버린다 — 0x415970 → [0x4663d4]=1).
bool engineAutoOn() {
    if (EV(kChoiceBox) || EV(kSelect)) return false;
    auto w = (uint8_t*)msgWin(); if (!w) return false;
    if (EV(kClickWait)) {
        *(volatile int*)(w + kWinBarHidden) = 1;
        ((void(__thiscall*)(void*, int))fBarShow)(w, 0);
        return ((int(__stdcall*)(int, int))fAutoOn)(0, 0) != 0;   // 거절하면 엔진이 0x410c20 으로 줄을 되살린다
    }
    EV(kAuto) = 1;
    barHideForAuto();
    return true;
}

// ---------------------------------------------------------------- 자동 대기(VM 스레드, 엔진 코드에서 바로 불린다)
int curRate() { LONG r = gRate; return r < 1 ? 1 : (r > 5 ? 5 : (int)r); }
int readNeedMs() {
    int rate = curRate();
    return (C.baseMs + C.charMs * gMsgHalf / 2) / rate;
}
int floorMs() { return std::max(250, 1000 / curRate()); }

// 0 = 클릭 대기로(자동이 꺼졌다), 1 = 음성 대기로, 2 = 바로 끝(건너뛰기가 켜졌다)
int __cdecl PlayTextWait() {
    InterlockedExchange(&gInWait, 1);
    DWORD enter = GetTickCount(), last = enter, paused = 0;
    DWORD start = gMsgStart && (enter - gMsgStart) < 600000 ? gMsgStart : enter;
    Ctx ctx = ctxNow();
    gWaitCtx = ctx;
    for (;;) {
        if (skipping()) return 2;
        // 불러오기·되감기는 VM 문맥을 먼저 덮어쓰고, 다음 입력 대기에서 이 VM 스레드를 끝낸다(0x4151c0 → 0x420600).
        // 여기서 명령을 더 실행하면 안 되므로 엔진의 입력 대기(클릭 대기)로 바로 보낸다.
        if (ctxChanged(ctx)) { InterlockedExchange(&gInWait, 0); Log("play: VM context changed during auto wait (load/rollback) -> engine input wait"); return 0; }
        if (!autoOn()) { InterlockedExchange(&gInWait, 0); return 0; }
        DWORD now = GetTickCount(), dt = now - last; last = now;
        if (countPaused()) paused += dt;
        else if ((int)(now - start - paused) >= readNeedMs() && (int)(now - enter - paused) >= floorMs()) {
            InterlockedExchange(&gInWait, 2);
            if (C.debugLog) {
                char b[160];
                sprintf_s(b, "play: wait x%d chars %.1f need %dms typed %lums waited %lums paused %lums", curRate(), gMsgHalf / 2.0,
                          readNeedMs(), enter - start, now - enter, paused);
                Log(b);
            }
            gVoiceFrom = now;
            return 1;
        }
        Sleep(15);
    }
}
// 음성 대기 뒤: 1 = 클릭 대기로
int __cdecl PlayAfterVoice() {
    InterlockedExchange(&gInWait, 0);
    while (Cm_Modal() && autoOn() && !ctxChanged(gWaitCtx)) Sleep(15);   // 해설 판이 열린 동안은 음성이 끝나도 넘기지 않는다
    if (ctxChanged(gWaitCtx)) { Log("play: VM context changed during voice wait -> engine input wait"); return 1; }
    if (C.debugLog && gVoiceFrom) { Log("play: voice wait " + std::to_string(GetTickCount() - gVoiceFrom) + "ms, auto " + std::to_string(EV(kAuto))); gVoiceFrom = 0; }
    return autoOn() || skipping() ? 0 : 1;
}
// 글 없는 클릭 대기(0x0a)의 자동 1초: 0 = 클릭 대기로, 1 = 넘어감
int __cdecl PlayPauseWait() {
    DWORD enter = GetTickCount(), last = enter, paused = 0;
    Ctx ctx = ctxNow();
    for (;;) {
        if (ctxChanged(ctx)) return 0;   // 불러오기·되감기 → 입력 대기에서 엔진이 이 스레드를 끝낸다
        if (skipping()) return 1;
        if (!autoOn()) return 0;
        DWORD now = GetTickCount(), dt = now - last; last = now;
        if (countPaused()) paused += dt;
        else if ((int)(now - enter - paused) >= floorMs()) return 1;
        Sleep(15);
    }
}

__declspec(naked) void textWaitStub() {
    __asm {
        call PlayTextWait
        cmp eax, 1
        je to_voice
        test eax, eax
        je to_click
        jmp dword ptr [gPlayJmpEnd]
    to_voice:
        jmp dword ptr [gPlayJmpVoice]
    to_click:
        jmp dword ptr [gPlayJmpClick]
    }
}
__declspec(naked) void afterVoiceStub() {
    __asm {
        mov dword ptr ds:[4663d8h], ebx
        call PlayAfterVoice
        test eax, eax
        jne to_click
        jmp dword ptr [gPlayJmpRet]
    to_click:
        jmp dword ptr [gPlayJmpClick]
    }
}

bool patchJmp(uintptr_t at, const uint8_t* expect, size_t n, void* to) {
    uint8_t b[16]; memset(b, 0x90, sizeof(b));
    b[0] = 0xe9; *(int32_t*)(b + 1) = (int32_t)((uintptr_t)to - at - 5);
    return PatchBytes(at, expect, b, n);
}
bool patchPauseWait() {
    uint8_t b[11] = {0xe8, 0, 0, 0, 0, 0x85, 0xc0, 0x74, 0x06, 0x90, 0x90};   // call; test eax,eax; jz 0x41de4a
    *(int32_t*)(b + 1) = (int32_t)((uintptr_t)PlayPauseWait - pPauseWait - 5);
    return PatchBytes(pPauseWait, kSleep1000, b, sizeof(b));
}

// ---------------------------------------------------------------- 대사 글자 세기·읽음
const char* slotText(void* script, uint32_t slot) {
    __try { return ((const char*(__thiscall*)(void*, uint32_t))fSlotText)(script, slot); }
    __except (EXCEPTION_EXECUTE_HANDLER) { return nullptr; }
}
// 보이는 글자 수 ×2: ^g### ^n ^m ^c? 를 뺀다
int halfUnits(const char* s) {
    if (!s) return 0;
    int n = 0;
    __try {
        for (int i = 0; s[i] && i < 4096;) {
            unsigned char c = (unsigned char)s[i];
            if (c == '^') {
                char t = s[i + 1];
                if (t == 'g') { i += 2; for (int k = 0; k < 3 && s[i] >= '0' && s[i] <= '9'; ++k) ++i; continue; }
                if (t == 'n' || t == 'm') { i += 2; continue; }
                if (t == 'c' && s[i + 2]) { i += 3; continue; }
            }
            if (c >= 0x81 && s[i + 1]) { n += 2; i += 2; continue; }
            if (c > 0x20) n += 1;
            ++i;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) { return n; }
    return n;
}
bool isRead(int script, uint32_t slot) {
    __try { return ((int(__cdecl*)(int, int))fIsRead)(script, (int)slot) != 0; }
    __except (EXCEPTION_EXECUTE_HANDLER) { return true; }
}

// ---------------------------------------------------------------- 저장 칸
std::wstring widen(const char* s) {
    int n = MultiByteToWideChar(CP_ACP, 0, s, -1, nullptr, 0);
    if (n <= 0) return L"";
    std::wstring w(n, L'\0'); MultiByteToWideChar(CP_ACP, 0, s, -1, &w[0], n); w.resize(n - 1);
    return w;
}
std::wstring savePath(int slot) {
    char* cfg = *(char**)kConfigPtr;
    if (!cfg) return L"";
    char path[512];
    wsprintfA(path, "%s\\%s%02d.dat", cfg + 0x43, cfg + 0x25, slot & 0xffff);
    return widen(path);
}
// 가장 최근에 쓴 칸 다음의 빈 칸(없으면 -1). latest 에 가장 최근 칸(없으면 -1)
int pickSlot(int& latest) {
    latest = -1;
    ULONGLONG best = 0;
    bool used[100] = {};
    for (int i = 0; i < 100; ++i) {
        WIN32_FILE_ATTRIBUTE_DATA a;
        if (!GetFileAttributesExW(savePath(i).c_str(), GetFileExInfoStandard, &a)) continue;
        used[i] = true;
        ULONGLONG t = ((ULONGLONG)a.ftLastWriteTime.dwHighDateTime << 32) | a.ftLastWriteTime.dwLowDateTime;
        if (t >= best) { best = t; latest = i; }
    }
    for (int k = 1; k <= 100; ++k) { int i = (latest + k) % 100; if (!used[i]) return i; }
    return -1;
}

// ---------------------------------------------------------------- 알림 문구
void say(const wchar_t* text, DWORD ms = 2500) { Toast(text, ms); }
void sayf(DWORD ms, const wchar_t* fmt, ...) {
    wchar_t b[256]; va_list ap; va_start(ap, fmt); _vsnwprintf_s(b, _TRUNCATE, fmt, ap); va_end(ap);
    Toast(b, ms);
}

// ---------------------------------------------------------------- 그리기(GDI+, 물리 좌표)
CRITICAL_SECTION gDrawCs;
bool gDrawInit = false;
ULONG_PTR gGdip = 0;
std::unique_ptr<PrivateFontCollection> gFonts;
std::unique_ptr<FontFamily[]> gFam;
FontFamily* famSemi = nullptr; FontFamily* famBlack = nullptr;
std::unique_ptr<FontFamily> famFallback, famArrow;
std::unique_ptr<Bitmap> imgFrame, imgStrip;

const Color INK(255, 58, 35, 15), INK_SOFT(255, 96, 70, 40);
const Color GOLD_TXT(255, 255, 246, 102), GOLD_EDGE(255, 70, 40, 0);
const Color CREAM(255, 236, 222, 182), LIGHT(255, 252, 248, 232), DIM(255, 190, 176, 140);

bool startDraw() {
    if (gGdip) return true;
    GdiplusStartupInput in;
    if (GdiplusStartup(&gGdip, &in, nullptr) != Ok) { gGdip = 0; return false; }
    gFonts.reset(new PrivateFontCollection());
    gFonts->AddFontFile((Root() + L"\\fc\\ForestChartSerif-SemiBold.ttf").c_str());
    gFonts->AddFontFile((Root() + L"\\fc\\ForestChartSerif-Black.ttf").c_str());
    int n = gFonts->GetFamilyCount(), found = 0;
    if (n > 0) { gFam.reset(new FontFamily[n]); gFonts->GetFamilies(n, gFam.get(), &found); }
    for (int i = 0; i < found; ++i) {
        WCHAR name[LF_FACESIZE] = {}; gFam[i].GetFamilyName(name);
        std::wstring s = name;
        if (s.find(L"Black") != std::wstring::npos) famBlack = &gFam[i];
        else if (s.find(L"SemiBold") != std::wstring::npos) famSemi = &gFam[i];
    }
    famArrow.reset(new FontFamily(L"Malgun Gothic"));
    if (!famSemi || !famBlack) {
        famFallback.reset(new FontFamily(L"Malgun Gothic"));
        if (!famSemi) famSemi = famFallback.get();
        if (!famBlack) famBlack = famFallback.get();
        Log("play: chart fonts missing; using Malgun Gothic");
    }
    imgFrame.reset(Bitmap::FromFile((Root() + L"\\fc\\frame_bg.png").c_str()));
    if (imgFrame && imgFrame->GetLastStatus() != Ok) imgFrame.reset();
    imgStrip.reset(Bitmap::FromFile((Root() + L"\\fc\\q_lit.png").c_str()));
    if (imgStrip && imgStrip->GetLastStatus() != Ok) imgStrip.reset();
    return true;
}

// 글꼴에 없는 화살표(↑↓)는 맑은 고딕으로
bool needsArrowFont(wchar_t c) { return c == 0x2191 || c == 0x2193; }
float measure(Graphics& g, const std::wstring& s, float size, bool black) {
    if (s.empty()) return 0;
    StringFormat fmt(StringFormat::GenericTypographic());
    fmt.SetFormatFlags(fmt.GetFormatFlags() | StringFormatFlagsMeasureTrailingSpaces);
    float w = 0; size_t i = 0;
    while (i < s.size()) {
        bool arrow = needsArrowFont(s[i]); size_t j = i;
        while (j < s.size() && needsArrowFont(s[j]) == arrow) ++j;
        Font f(arrow ? famArrow.get() : (black ? famBlack : famSemi), size, arrow ? FontStyleBold : FontStyleRegular, UnitPixel);
        RectF out; g.MeasureString(s.c_str() + i, (INT)(j - i), &f, PointF(0, 0), &fmt, &out);
        w += out.Width; i = j;
    }
    return w;
}
// align 0 왼쪽, 1 가운데, 2 오른쪽. y = 글줄 가운데. 테두리를 주면 경로로 그린다.
void text(Graphics& g, const std::wstring& s, float x, float y, float size, bool black, Color fill, int align = 0,
          float maxW = 0, const Color* edge = nullptr, float ew = 0) {
    if (s.empty()) return;
    float sz = size;
    if (maxW > 0) while (sz > 8 && measure(g, s, sz, black) > maxW) sz -= 0.5f;
    float w = measure(g, s, sz, black);
    float left = align == 1 ? x - w / 2 : align == 2 ? x - w : x;
    StringFormat fmt(StringFormat::GenericTypographic());
    fmt.SetFormatFlags(fmt.GetFormatFlags() | StringFormatFlagsMeasureTrailingSpaces);
    size_t i = 0;
    while (i < s.size()) {
        bool arrow = needsArrowFont(s[i]); size_t j = i;
        while (j < s.size() && needsArrowFont(s[j]) == arrow) ++j;
        FontFamily* fam = arrow ? famArrow.get() : (black ? famBlack : famSemi);
        INT style = arrow ? FontStyleBold : FontStyleRegular;
        float top = y - sz * (arrow ? 0.66f : 0.62f);
        std::wstring part = s.substr(i, j - i);
        if (edge) {
            GraphicsPath path;
            path.AddString(part.c_str(), (INT)part.size(), fam, style, sz, PointF(left, top), &fmt);
            Pen pen(*edge, ew * 2); pen.SetLineJoin(LineJoinRound);
            g.DrawPath(&pen, &path);
            SolidBrush br(fill); g.FillPath(&br, &path);
        } else {
            Font f(fam, sz, style, UnitPixel);
            SolidBrush br(fill);
            g.DrawString(part.c_str(), (INT)part.size(), &f, PointF(left, top), &fmt, &br);
        }
        Font fm(fam, sz, style, UnitPixel);
        RectF out; g.MeasureString(part.c_str(), (INT)part.size(), &fm, PointF(0, 0), &fmt, &out);
        left += out.Width; i = j;
    }
}
void goldText(Graphics& g, const std::wstring& s, float x, float y, float size, int align = 0, float maxW = 0) {
    text(g, s, x, y, size, true, GOLD_TXT, align, maxW, &GOLD_EDGE, 1.6f);
}
// 세 토막 늘이기(찢긴 양 끝을 살린다)
void draw3(Graphics& g, Bitmap* b, float x, float y, float w, float h, int cap) {
    if (!b) return;
    float sw = (float)b->GetWidth(), sh = (float)b->GetHeight();
    float capd = std::min(cap * h / sh, w / 2.f);
    g.DrawImage(b, RectF(x, y, capd, h), 0, 0, (REAL)cap, sh, UnitPixel);
    g.DrawImage(b, RectF(x + capd, y, w - 2 * capd, h), (REAL)cap, 0, sw - 2 * cap, sh, UnitPixel);
    g.DrawImage(b, RectF(x + w - capd, y, capd, h), sw - cap, 0, (REAL)cap, sh, UnitPixel);
}

// 물리 크기 ARGB(premultiplied) 그림 한 장
struct Layer {
    HDC dc = nullptr; HBITMAP bmp = nullptr, old = nullptr; void* bits = nullptr;
    int w = 0, h = 0; std::wstring key; RECT logical{};
    void reset() { if (dc) { SelectObject(dc, old); DeleteDC(dc); } if (bmp) DeleteObject(bmp); dc = nullptr; bmp = old = nullptr; bits = nullptr; w = h = 0; key.clear(); }
    bool make(int W, int H) {
        reset();
        BITMAPINFO bi = {}; bi.bmiHeader.biSize = sizeof(bi.bmiHeader); bi.bmiHeader.biWidth = W; bi.bmiHeader.biHeight = -H;
        bi.bmiHeader.biPlanes = 1; bi.bmiHeader.biBitCount = 32; bi.bmiHeader.biCompression = BI_RGB;
        bmp = CreateDIBSection(nullptr, &bi, DIB_RGB_COLORS, &bits, nullptr, 0);
        if (!bmp) return false;
        dc = CreateCompatibleDC(nullptr); old = (HBITMAP)SelectObject(dc, bmp);
        w = W; h = H; memset(bits, 0, (size_t)W * H * 4);
        return true;
    }
};
Layer gToastLayer, gIndLayer, gGuideLayer;

struct Map { double sx, sy; int ox, oy; };
Map mapOf(const Layout& L) { return Map{L.cw / 800.0, L.ch / 600.0, L.ox, L.oy}; }
RECT phys(const Map& m, const RECT& r) {
    return RECT{m.ox + (int)std::floor(r.left * m.sx), m.oy + (int)std::floor(r.top * m.sy),
                m.ox + (int)std::ceil(r.right * m.sx), m.oy + (int)std::ceil(r.bottom * m.sy)};
}

// 그림을 새로 그려야 하면 그린다. fn(g) 는 논리 좌표로 그린다.
template <class Fn>
bool render(Layer& L, const Map& m, const RECT& logical, const std::wstring& key, Fn fn) {
    RECT P = phys(m, logical);
    int W = P.right - P.left, H = P.bottom - P.top;
    if (W <= 0 || H <= 0) return false;
    if (L.bmp && L.key == key && L.w == W && L.h == H) return true;
    if (!L.make(W, H)) return false;
    L.key = key; L.logical = logical;
    Bitmap b(W, H, W * 4, PixelFormat32bppPARGB, (BYTE*)L.bits);
    Graphics g(&b);
    g.SetSmoothingMode(SmoothingModeAntiAlias);
    g.SetTextRenderingHint(TextRenderingHintAntiAliasGridFit);
    g.SetInterpolationMode(InterpolationModeHighQualityBicubic);
    g.SetPixelOffsetMode(PixelOffsetModeHalf);
    g.ScaleTransform((REAL)(W / ((logical.right - logical.left) * 1.0)), (REAL)(H / ((logical.bottom - logical.top) * 1.0)));
    g.TranslateTransform((REAL)-logical.left, (REAL)-logical.top);
    fn(g);
    return true;
}
// clip 안에서만 찍는다
void blit(HDC dc, const Layer& L, const Map& m, const RECT& clip, BYTE alpha, bool opaque) {
    if (!L.bmp) return;
    RECT P = phys(m, L.logical), D;
    P.right = P.left + L.w; P.bottom = P.top + L.h;
    if (!IntersectRect(&D, &P, &clip)) return;
    int sx = D.left - P.left, sy = D.top - P.top, w = D.right - D.left, h = D.bottom - D.top;
    if (opaque && alpha == 255) { BitBlt(dc, D.left, D.top, w, h, L.dc, sx, sy, SRCCOPY); return; }
    BLENDFUNCTION bf = {AC_SRC_OVER, 0, alpha, AC_SRC_ALPHA};
    AlphaBlend(dc, D.left, D.top, w, h, L.dc, sx, sy, w, h, bf);
}

// ---------------------------------------------------------------- 그림 내용
void drawToast(Graphics& g, const std::wstring& s) {
    const RECT& R = kToastRect;
    float maxText = (float)(R.right - R.left) - 40;
    float size = 15.5f;
    while (size > 10 && measure(g, s, size, false) > maxText) size -= 0.5f;
    float tw = measure(g, s, size, false);
    float w = std::min<float>((float)(R.right - R.left), std::max(160.f, tw + 40));
    float x = (float)R.left, y = (float)R.top + 1, h = (float)(R.bottom - R.top) - 2;
    if (imgStrip) draw3(g, imgStrip.get(), x, y, w, h, 18);
    else { SolidBrush b(Color(235, 240, 224, 176)); g.FillRectangle(&b, x, y, w, h); }
    text(g, s, x + 20, y + h / 2 + 0.5f, size, false, INK);
}
std::wstring indicatorText() { wchar_t b[32]; swprintf_s(b, L"자동 ×%d", (int)gRate); return b; }
void drawIndicator(Graphics& g) {
    goldText(g, indicatorText(), 793.f, 587.f, 15.f, 2);   // 아이콘 줄 높이(가운데 y 약 591)보다 조금 위, 아래 끝 600 에 안 닿게
}

struct GuideRow { std::wstring key, desc; };
void guideRows(std::vector<GuideRow>& left, std::vector<GuideRow>& right, std::vector<std::wstring>& notes) {
    left = {
        {L"클릭 · Enter · Space", L"다음 대사"},
        {L"Ctrl (누르는 동안)", C.ctrlProtect ? L"건너뛰기 (설정 범위를 따름)" : L"건너뛰기"},
        {L"Tab", L"건너뛰기 켜기 (설정 범위를 따름)"},
        {L"Shift", L"대화창 숨기기 · 다시 보이기"},
        {L"휠 위 · ↑", L"앞 쪽 대사 다시 보기"},
        {L"휠 아래 · ↓", L"다음 쪽으로"},
        {L"오른쪽 클릭", L"설정 화면 · 열린 화면 닫기"},
        {L"Esc", L"열린 화면 닫기"},
        {L"Alt + 0~9", L"1쪽 그 칸에 바로 저장 (덮어씀)"},
        {L"Alt + Shift + 0~9", L"1쪽 그 칸 불러오기"},
    };
    right.clear();
    if (C.autoKey) {
        right.push_back({L"A", C.textWait ? L"자동 진행 · 누를 때마다 ×1~×5" : L"자동 진행 켜기 · 끄기"});
        right.push_back({L"Backspace", L"자동 진행 끄기 (클릭 · Enter 도)"});
    }
    if (C.quickSave) right.push_back({L"S", L"다음 빈 칸에 바로 저장"});
    if (C.loadKey) right.push_back({L"L", L"불러오기 화면"});
    right.push_back({L"F8", L"이야기의 지도"});
    if (Cm_On()) {
        right.push_back({L"F7", L"해설 열기 · 닫기"});
        right.push_back({L"F6", L"해설 안내 단계 바꾸기"});
    }
    if (C.presentKeys) right.push_back({L"Alt + Enter", L"전체 화면 · 창"});
    right.push_back({L"Home", L"이 안내 열기 · 닫기"});
    notes.clear();
    if (C.ctrlProtect) notes.push_back(L"설정이 「읽은 부분만」이면 Ctrl 도 안 읽은 대사에서 멈춥니다.");
    if (C.autoKey && C.afterChoice) notes.push_back(L"자동 진행은 선택지를 고른 뒤에도 이어집니다.");
}
void drawGuide(Graphics& g) {
    if (imgFrame) g.DrawImage(imgFrame.get(), RectF(0, 0, 800, 600));
    else { SolidBrush b(Color(255, 20, 24, 20)); g.FillRectangle(&b, 0, 0, 800, 600); }
    std::vector<GuideRow> left, right; std::vector<std::wstring> notes;
    guideRows(left, right, notes);
    // 위 띠: 지도의 「전체 지도」 자리
    text(g, L"모든 키", 292, 62, 30, true, INK);
    text(g, L"새로 넣은 키는 켜 둔 것만 적었습니다.", 294, 92, 13.5f, false, INK_SOFT);
    // 가운데 어두운 띠
    goldText(g, L"원래 있던 키", 48, 148, 17);
    goldText(g, L"새로 넣은 키", 438, 148, 17);
    Pen rule(Color(110, 255, 230, 140), 1.f);
    g.DrawLine(&rule, 48.f, 166.f, 392.f, 166.f);
    g.DrawLine(&rule, 438.f, 166.f, 768.f, 166.f);
    float y = 188;
    for (auto& r : left) {
        text(g, r.key, 48, y, 14.5f, true, LIGHT, 0, 150);
        text(g, r.desc, 204, y, 13.5f, false, CREAM, 0, 196);
        y += 29;
    }
    y = 188;
    for (auto& r : right) {
        text(g, r.key, 438, y, 14.5f, true, LIGHT, 0, 110);
        text(g, r.desc, 552, y, 13.5f, false, CREAM, 0, 216);
        y += 29;
    }
    y += 8;
    for (auto& n : notes) { text(g, n, 438, y, 12.5f, false, DIM, 0, 330); y += 22; }
    // 아래 띠: 지도의 「이야기의 지도」 자리
    text(g, L"조작 안내", 26, 556, 28, true, INK);
    text(g, L"Home · Esc · 클릭하면 닫힙니다.", 232, 556, 14, false, INK_SOFT);
    goldText(g, L"닫기", 772, 556, 17, 2);
}

bool indicatorVisible() {
    return C.indicator && C.autoKey && autoOn() && !EV(kHidden) && !screensOpen() && !ChartIsOpen() && !gGuideOpen;
}

// ---------------------------------------------------------------- 키 처리(게임 창 스레드)
bool atTitleMenu() { return topScript() == 1 && EV(kSelect); }
void openLoadScreen() {
    Log("play: L -> load screen (settings load button path) at " + stackText());
    ((int(__stdcall*)(int, int))fLoadButton)(0, 0);
}

void keyAuto() {
    if (autoOn()) {
        if (!C.textWait) { engineAutoOff(); Log("play: A -> auto off"); return; }
        InterlockedExchange(&gRate, gRate % 5 + 1);
        Log("play: A -> rate x" + std::to_string(gRate));
        Present_InvalidateLogical(kIndRect);
        return;
    }
    if (screensOpen()) { say(L"메뉴를 닫은 뒤에 켜 주세요"); return; }
    if (EV(kChoiceBox) || EV(kSelect)) {
        if (gChoicePending) say(L"고르고 나면 자동 진행이 이어집니다");
        else say(L"선택지·메뉴에서는 자동 진행을 켤 수 없습니다");
        return;
    }
    InterlockedExchange(&gRate, 1);
    bool ok = engineAutoOn();
    Log(std::string("play: A -> auto on x1 ") + (ok ? "ok" : "refused") + " at " + stackText());
    if (!ok) say(L"지금은 자동 진행을 켤 수 없습니다");
    else if (!C.indicator) say(L"자동 진행 ×1");
    Present_InvalidateLogical(kIndRect);
}
void keyAutoOff() {
    engineAutoOff();
    Log("play: Backspace -> auto off");
    Present_InvalidateLogical(kIndRect);
}

// S: 이야기 중 대사에서 멈춘 때만
bool saveAllowed(const wchar_t*& why) {
    why = nullptr;
    if (screensOpen()) why = L"메뉴가 열려 있어 저장하지 않았습니다";
    else if (atTitleMenu() || topScript() == 1) why = L"타이틀 화면에서는 저장할 수 없습니다";
    else if (stackHas(200, 499)) why = L"특전 화면에서는 저장할 수 없습니다";
    else if (stackHas(9000, 9000)) why = L"다시보기 중에는 저장할 수 없습니다";
    else if (EV(kChoiceBox) || EV(kSelect)) why = L"선택지에서는 저장할 수 없습니다";
    else if (!EV(kSaveOk) || !EV(kCheckpointOk)) why = L"이 장면에서는 저장할 수 없습니다";
    else if (!(EV(kClickWait) || gInWait || gLastOp == 0x51)) why = L"대사가 나올 때 눌러 주세요";
    return why == nullptr;
}
void keySave() {
    const wchar_t* why;
    if (!saveAllowed(why)) { Log("play: S refused at " + stackText()); say(why); return; }
    int latest = -1, slot = pickSlot(latest);
    if (slot < 0) { say(L"빈 칸이 없어 저장하지 않았습니다 (100칸 모두 사용 중)", 3500); Log("play: S no empty slot"); return; }
    ((void(__cdecl*)(unsigned))fSave)((unsigned)slot);
    WIN32_FILE_ATTRIBUTE_DATA a;
    bool ok = GetFileAttributesExW(savePath(slot).c_str(), GetFileExInfoStandard, &a) && a.nFileSizeLow == 50668;
    Log("play: S -> slot " + std::to_string(slot) + (ok ? " saved" : " FAILED") + " (latest was " + std::to_string(latest) + ") at " + stackText());
    // 세이브 화면은 한 쪽에 왼쪽 열 5칸(칸 0~4) → 오른쪽 열 5칸(5~9), 쪽 번호는 1부터 보인다
    static const wchar_t* kRow[5] = {L"첫째", L"둘째", L"셋째", L"넷째", L"다섯째"};
    if (ok) sayf(3000, L"%d쪽 %s %s 칸에 저장했습니다", slot / 10 + 1, (slot % 10) < 5 ? L"왼쪽" : L"오른쪽", kRow[slot % 5]);
    else say(L"저장하지 못했습니다", 3000);
}

void keyLoad() {
    if (EV(kLoadScr)) return;
    if (EV(kSettings) || EV(kSaveScr)) { say(L"열린 화면을 닫은 뒤에 눌러 주세요"); return; }
    if (atTitleMenu()) {
        Log("play: L -> load screen (title button path)");
        ((int(__stdcall*)(int, int))fScriptButton)(0, 5);
        return;
    }
    if (EW(kMenuLock)) { say(L"이 장면에서는 불러오기 화면을 열 수 없습니다"); return; }
    if (EV(kClickWait) && barActive() && !EV(kChoiceBox) && !EV(kSelect)) { openLoadScreen(); return; }
    if (autoOn() && !EV(kChoiceBox) && !EV(kSelect)) {
        engineAutoOff();
        InterlockedExchange(&gPending, PendLoad); gPendingAt = GetTickCount();
        Log("play: L during auto -> auto off, load screen at next click wait");
        return;
    }
    say(L"대사가 멈춘 곳에서 눌러 주세요 (불러오기)");
}

void guideOpen() {
    InterlockedExchange(&gGuideOpen, 1);
    gGuideMouseDown = false;
    if (EV(kCtrlKey) || EV(kCtrlSkip)) { InterlockedExchange(&gCtrlBlocked, 1); EV(kCtrlKey) = 0; EV(kCtrlSkip) = 0; }
    if (EV(kTabReq)) EV(kTabReq) = 0;
    if (EV(kTabSkip)) InterlockedExchange(&gStopTabSkip, 1);
    Log("play: key guide open");
    Present_InvalidateLogical(RECT{0, 0, 800, 600});
}
void guideClose() {
    InterlockedExchange(&gGuideOpen, 0);
    Log("play: key guide closed");
    Present_InvalidateLogical(RECT{0, 0, 800, 600});
}

// 한글 입력기가 켜져 있으면 글자 키가 VK_PROCESSKEY 로 온다
UINT realKey(HWND h, WPARAM w) {
    if (w != VK_PROCESSKEY) return (UINT)w;
    return ImmGetVirtualKey(h);
}
void cancelComposition(HWND h) {
    HIMC c = ImmGetContext(h);
    if (c) { ImmNotifyIME(c, NI_COMPOSITIONSTR, CPS_CANCEL, 0); ImmReleaseContext(h, c); }
}

bool guideWndProc(HWND h, UINT m, WPARAM w, LPARAM l, LRESULT& r) {
    switch (m) {
    case WM_KEYDOWN: {
        UINT vk = realKey(h, w);
        if (w == VK_PROCESSKEY) cancelComposition(h);
        if (!(l & 0x40000000) && (vk == VK_HOME || vk == VK_ESCAPE)) guideClose();
        r = 0; return true;
    }
    case WM_KEYUP: return false;   // 엔진은 Ctrl 뗌만 본다
    case WM_SYSKEYDOWN: if (w == VK_F4) return false; r = 0; return true;
    case WM_CHAR: case WM_SYSCHAR: case WM_DEADCHAR: r = 0; return true;
    case WM_LBUTTONDOWN: case WM_RBUTTONDOWN: case WM_MBUTTONDOWN:
    case WM_LBUTTONDBLCLK: case WM_RBUTTONDBLCLK: case WM_MBUTTONDBLCLK:
        gGuideMouseDown = true; r = 0; return true;
    case WM_LBUTTONUP: case WM_RBUTTONUP: case WM_MBUTTONUP:
        if (gGuideMouseDown) guideClose();   // 뗄 때 닫는다(누름이 안내 밖으로 새지 않게)
        r = 0; return true;
    case WM_MOUSEMOVE: case WM_MOUSEWHEEL: r = 0; return true;
    case WM_SYSCOMMAND: if ((w & 0xfff0) == SC_CLOSE) guideClose(); return false;
    }
    return false;
}

// ---------------------------------------------------------------- 창 스레드 타이머
void tick() {
    DWORD now = GetTickCount();
    int sig = indicatorVisible() ? (int)gRate : 0;
    if (sig != gLastIndSig) { gLastIndSig = sig; Present_InvalidateLogical(kIndRect); }
    std::wstring t; float a = 0;
    bool on = ToastNow(t, a);
    if (on && a < 0.999f) Present_InvalidateLogical(kToastRect);
    if (!on && gToastWasOn) Present_InvalidateLogical(kToastRect);
    gToastWasOn = on;
    if (gHintAt && (int)(now - gHintAt) >= 0) {
        gHintAt = 0;
        say(L"계속 넘기려면 설정에서 「안 읽은 부분도」를 고르세요", 4000);
    }
    if (InterlockedExchange(&gBarHideReq, 0) && autoOn()) barHideForAuto();
    LONG p = gPending;
    if (p != PendNone) {
        if (now - gPendingAt > 3000 || autoOn()) InterlockedExchange(&gPending, PendNone);
        else if (EV(kClickWait) && barActive() && !screensOpen() && !EV(kChoiceBox) && !EV(kSelect) && !ChartIsOpen() && !gGuideOpen) {
            InterlockedExchange(&gPending, PendNone);
            if (p == PendMenu) {
                Log("play: right-click during auto -> settings at click wait");
                if (msgWin()) ((void(__thiscall*)(void*))fMenuPath)(msgWin());
            } else if (p == PendLoad) openLoadScreen();
        }
    }
}

}  // namespace

// ---------------------------------------------------------------- 약속(qol.h)
bool Play_Install() {
    C.on = Cfg("play", 1) != 0;
    if (!C.on) return false;
    C.autoKey = Cfg("auto_key", 1) != 0;
    C.textWait = Cfg("auto_text_wait", 1) != 0;
    C.afterChoice = Cfg("auto_after_choice", 1) != 0;
    C.ctrlProtect = Cfg("ctrl_protect", 1) != 0;
    C.quickSave = Cfg("quick_save_key", 1) != 0;
    C.loadKey = Cfg("load_key", 1) != 0;
    C.guide = Cfg("key_guide", 1) != 0;
    C.indicator = Cfg("auto_indicator", 1) != 0;
    C.presentKeys = Cfg("present", 1) != 0;   // 화면 모듈의 Alt+Enter 가 켜졌는지(안내에 적을지)
    C.baseMs = std::max(0, std::min(10000, Cfg("auto_base_ms", 1200)));
    C.charMs = std::max(0, std::min(1000, Cfg("auto_char_ms", 80)));
    C.debugLog = Cfg("play_log", 0) != 0;
    InitializeCriticalSection(&gDrawCs); gDrawInit = true;
    if (C.textWait) {
        // 세 자리가 모두 원래 바이트일 때만 바꾼다(하나라도 다르면 하나도 안 바꿈)
        bool same = memcmp((void*)pTextWait, kSleep1000, 11) == 0 && memcmp((void*)pAfterVoice, kMovD8, 6) == 0 &&
                    memcmp((void*)pPauseWait, kSleep1000, 11) == 0;
        if (same && patchJmp(pTextWait, kSleep1000, 11, (void*)textWaitStub)) {
            bool b = patchJmp(pAfterVoice, kMovD8, 6, (void*)afterVoiceStub);
            bool c = patchPauseWait();
            gTextWaitPatched = true;
            Log(std::string("play: auto wait patched (text") + (b ? ", after-voice" : "") + (c ? ", pause" : "") + ")");
        } else {
            C.textWait = false;
            Log("play: auto wait code differs; rates off (engine waits 1s)");
        }
    }
    Log("play: on (auto_key " + std::to_string(C.autoKey) + ", text_wait " + std::to_string(C.textWait) + ", after_choice " +
        std::to_string(C.afterChoice) + ", ctrl_protect " + std::to_string(C.ctrlProtect) + ", S " + std::to_string(C.quickSave) +
        ", L " + std::to_string(C.loadKey) + ", guide " + std::to_string(C.guide) + ", base " + std::to_string(C.baseMs) +
        "ms, char " + std::to_string(C.charMs) + "ms)");
    return true;
}

void Play_WindowReady(HWND h) {
    if (!C.on) return;
    gWnd = h;
    gMsgPlay = RegisterWindowMessageW(L"ForestQolPlay");
    PostMessageW(h, gMsgPlay, 1, 0);   // 타이머는 창 스레드에서 건다
}

bool Play_WndProc(HWND h, UINT m, WPARAM w, LPARAM l, LRESULT& r) {
    if (!C.on) return false;
    if (gMsgPlay && m == gMsgPlay) { if (w == 1) SetTimer(h, kTimerId, 50, nullptr); r = 0; return true; }
    if (m == WM_TIMER && w == kTimerId) { tick(); r = 0; return true; }
    if (gGuideOpen && guideWndProc(h, m, w, l, r)) return true;
    switch (m) {
    case WM_ACTIVATE:
        if (LOWORD(w) == WA_INACTIVE) InterlockedExchange(&gCtrlBlocked, 0);   // 엔진도 Ctrl 을 놓는다
        return false;
    case WM_KEYUP:
        if (w == VK_CONTROL && gCtrlBlocked) InterlockedExchange(&gCtrlBlocked, 0);
        return false;
    case WM_RBUTTONDOWN:
        // 자동 대기 중엔 단추 줄이 꺼져 있어 오른쪽 클릭이 아무 일도 안 한다 → 자동을 끄고 클릭 대기에서 설정 화면
        if (C.autoKey && autoOn() && !barActive() && !EV(kHidden) && !screensOpen() && !EV(kChoiceBox) && !EV(kSelect)) {
            engineAutoOff();
            InterlockedExchange(&gPending, PendMenu); gPendingAt = GetTickCount();
            Log("play: right-click during auto -> auto off");
            r = 0; return true;
        }
        return false;
    case WM_KEYDOWN: {
        bool repeat = (l & 0x40000000) != 0;
        if (w == VK_CONTROL && gCtrlBlocked) { r = 0; return true; }   // 반복마다 한 줄씩 넘기지 않게
        UINT vk = realKey(h, w);
        bool ime = w == VK_PROCESSKEY;
        switch (vk) {
        case 'A':
            if (!C.autoKey) return false;
            if (ime) cancelComposition(h);
            if (!repeat && !ChartIsOpen()) keyAuto();
            r = 0; return true;
        case VK_BACK:
            if (!C.autoKey) return false;
            if (autoOn()) { if (ime) cancelComposition(h); if (!repeat) keyAutoOff(); r = 0; return true; }
            if (gChoicePending && (EV(kChoiceBox) || EV(kSelect))) {
                InterlockedExchange(&gChoicePending, 0);
                if (!repeat) { say(L"고른 뒤에 자동 진행을 이어 가지 않습니다"); Log("play: Backspace -> no auto after this choice"); }
                r = 0; return true;
            }
            return false;
        case 'S':
            if (!C.quickSave) return false;
            if (ime) cancelComposition(h);
            if (!repeat) keySave();
            r = 0; return true;
        case 'L':
            if (!C.loadKey) return false;
            if (ime) cancelComposition(h);
            if (!repeat) keyLoad();
            r = 0; return true;
        case VK_HOME:
            if (!C.guide) return false;
            if (!repeat) guideOpen();
            r = 0; return true;
        case VK_SHIFT:
            // 자동 중엔 단추 줄이 꺼져 있어 원작 Shift(0x410cc0)가 숨기지 못한다 → 숨기기 단추 콜백(0x416570)을 바로 부른다.
            // 숨긴 동안 자동 셈은 멈추고, 다시 Shift·오른쪽 클릭이면 원작대로 보인다(0x4165b0).
            if (C.autoKey && autoOn() && !EV(kHidden) && !barActive() && !screensOpen() && !EV(kChoiceBox) && !EV(kSelect)) {
                if (!repeat) { ((int(__stdcall*)(int, int))fHideButton)(0, 0); Log("play: Shift during auto -> hide (auto paused)"); }
                r = 0; return true;
            }
            return false;
        case VK_F8:
            // 지도는 입력 대기에서만 열린다 → 자동 중이면 자동을 끈다(엔진의 클릭 대기에서 지도가 열린다)
            if (!repeat && autoOn() && !EV(kChoiceBox) && !EV(kSelect)) { engineAutoOff(); Log("play: F8 during auto -> auto off"); }
            return false;
        }
        return false;
    }
    }
    return false;
}

void Play_Fetch(void* script, int sid, uint32_t pc, uint16_t op, const uint8_t* cursor) {
    if (!C.on) return;
    // 선택 뒤 자동 계속: 고른 뒤 같은 깊이·같은 대본에서 처음 꺼낸 명령이 CHOICE 의 갈래 목적지(또는 CHOICE+60)일 때만.
    // 고르는 동안 엔진은 날짜 잎사귀 움직임 대본(0501 등)을 한 단계 깊이 돌린다 → 그 명령은 건너뛴다.
    // (엔진은 고르는 동안 잎사귀 움직임 대본을 더 깊이, 또는 VM 문맥을 맡겨 두고 깊이 0 에서 돌린다(0x41e730) → 그 명령은 모두 건너뛴다.)
    if (gChoicePending) {
        if (GetCurrentThreadId() != gChoiceThread) {   // 불러오기·타이틀로: VM 스레드가 바뀜
            InterlockedExchange(&gChoicePending, 0);
            if (C.debugLog) Log("play: choice memory dropped (VM thread changed)");
        } else if (depth() == gChoiceDepth && sid == gChoiceSid && !(op == 0x0e && (LONG)pc == gChoicePc)) {
            bool next = (LONG)pc == gChoicePc + 60;
            for (uint32_t t : gChoiceTargets) if (t && pc == t) next = true;
            InterlockedExchange(&gChoicePending, 0);
            if (next && !autoOn() && !skipping()) {
                EV(kAuto) = 1;
                InterlockedExchange(&gBarHideReq, 1);
                Log("play: auto resumed after choice x" + std::to_string(gRate));
            } else if (C.debugLog) Log("play: choice memory dropped at " + std::to_string(sid) + ":" + std::to_string(pc));
        }
    }
    if (op == 0x0e && C.afterChoice && C.autoKey && autoOn()) {
        gChoiceSid = sid; gChoicePc = (LONG)pc; gChoiceDepth = depth(); gChoiceThread = GetCurrentThreadId();
        // 꼴: 명령 u16, H 갈래 수, I[0] 질문 슬롯, I[1..5] 갈래 목적지, I[6..10] 갈래 슬롯, V×3 (60바이트)
        for (int i = 0; i < 5; ++i) gChoiceTargets[i] = *(const uint32_t*)(cursor + 8 + 4 * i);
        InterlockedExchange(&gChoicePending, 1);
        if (C.debugLog) Log("play: choice with auto on at " + std::to_string(sid) + ":" + std::to_string(pc) + " depth " + std::to_string(gChoiceDepth));
    }
    gLastOp = op;
    if (gCtrlBlocked) EV(kCtrlKey) = 0;
    if (op != 0x51 && op != 0x52) return;
    uint32_t slot = *(const uint32_t*)(cursor + (op == 0x51 ? 22 : 18));
    gMsgStart = GetTickCount();
    InterlockedExchange(&gMsgHalf, halfUnits(slotText(script, slot)));
    // 안내를 연 동안 Tab 건너뛰기를 멈춘다(엔진이 안 읽은 줄에서 멈출 때와 같은 길: 0x41c9e0)
    if (gStopTabSkip) {
        InterlockedExchange(&gStopTabSkip, 0);
        if (EV(kTabSkip)) {
            EV(kTabSkip) = 0;
            ((void(__cdecl*)())fSkipResync)();
            if (engineObj()) ((void(__thiscall*)(void*))fFullRedraw)(engineObj());
            Log("play: tab skip stopped for key guide");
        }
    }
    // Ctrl 읽음 보호
    if (op == 0x51 && C.ctrlProtect && (EV(kCtrlKey) || EV(kCtrlSkip)) && EW(kSkipRange) == 0) {
        int scr = topScript();
        if (!isRead(scr, slot)) {
            InterlockedExchange(&gCtrlBlocked, 1);
            EV(kCtrlKey) = 0; EV(kCtrlSkip) = 0;
            Log("play: ctrl skip stopped at unread line " + std::to_string(scr) + ":" + std::to_string(slot));
            say(L"안 읽은 대사라 Ctrl 건너뛰기를 멈췄습니다", 2500);
            if (!gCtrlHintShown) { gCtrlHintShown = true; gHintAt = GetTickCount() + 2600; if (!gHintAt) gHintAt = 1; }
        }
    }
}

void Play_PaintOverlays(HDC dc, const Layout& L, const RECT& clip) {
    if (!C.on || !gDrawInit || !dc) return;
    std::wstring t; float a = 0;
    bool toast = ToastNow(t, a);
    bool guide = gGuideOpen != 0, ind = !guide && indicatorVisible();
    if (!toast && !guide && !ind) return;
    EnterCriticalSection(&gDrawCs);
    if (startDraw()) {
        Map m = mapOf(L);
        wchar_t sc[48]; swprintf_s(sc, L"|%d|%d", L.cw, L.ch);
        if (guide && render(gGuideLayer, m, RECT{0, 0, 800, 600}, std::wstring(L"guide") + sc +
                                (C.ctrlProtect ? L"c" : L"") + (C.presentKeys ? L"p" : L""), [](Graphics& g) { drawGuide(g); }))
            blit(dc, gGuideLayer, m, clip, 255, true);
        if (ind && render(gIndLayer, m, kIndRect, indicatorText() + sc, [](Graphics& g) { drawIndicator(g); }))
            blit(dc, gIndLayer, m, clip, 255, false);
        if (toast && render(gToastLayer, m, kToastRect, t + sc, [&](Graphics& g) { drawToast(g, t); }))
            blit(dc, gToastLayer, m, clip, (BYTE)std::max(0.f, std::min(255.f, a * 255.f)), false);
    }
    LeaveCriticalSection(&gDrawCs);
}

bool Play_OverlayRects(std::vector<RECT>& out) {
    out.clear();
    if (!C.on) return false;
    if (gGuideOpen) out.push_back(RECT{0, 0, 800, 600});
    else if (indicatorVisible()) out.push_back(kIndRect);
    std::wstring t; float a = 0;
    if (ToastNow(t, a)) out.push_back(kToastRect);
    return !out.empty();
}

int Play_AutoButton() {
    if (!C.on) return 0;
    if (autoOn()) { engineAutoOff(); Log("play: auto button -> off"); return 1; }
    InterlockedExchange(&gRate, 1);
    int ok = ((int(__stdcall*)(int, int))fAutoOn)(0, 0);   // 엔진 0x410bd0 이 이미 줄을 숨겼다; 거절하면 엔진이 되살린다
    Log(std::string("play: auto button -> on x1 ") + (ok ? "ok" : "refused"));
    Present_InvalidateLogical(kIndRect);
    return 1;
}

bool Play_AutoOn() { return *(volatile int*)0x466408 != 0; }

bool Play_GuideOpen() { return gGuideOpen != 0; }

}}  // namespace forest::qol
