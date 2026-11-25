// qol_rewind.cpp — 이전 대사로 되감기 (2026-11-25).
//
// 하는 일
//   Backspace = 한 걸음 뒤로. 문장만이 아니라 그 대사가 떴을 때의 상태(그림·음악·환경음·음성·노란 자막·변수·대화 기록·
//   「직전 선택지」·이야기의 지도 회차 기록)가 통째로 돌아온다. 누르고 있으면 계속 뒤로 간다.
//   걸음 = 엔진이 멈추는 자리(대사·선택지·글 없는 클릭 대기) + 대사 없이 흐르는 소리 자막(노란 자막과 음성만 흐르는 311곳).
//   되감아서 다시 보는 구간의 소리 자막은 음성이 끝나도 남아 있고 클릭·Enter 로 넘긴다(사용자 11-25 「되감아도 클릭으로 넘기게 해줘」).
//   처음 보는 곳부터는 원작대로 저절로 흐른다.
//
// 엔진 근거(Forest.exe f618b6… / 지도 로더판 eef917…, 코드 구역 같음. 자세한 것은 P:\AI\forest-qol\s-rewind\조사.md)
//   · 엔진은 멈추는 자리마다 「지금 상태」 한 벌을 뜬다(0x418a40): VM 문맥 0x46646c~ 11,324바이트 + 변수 14,000바이트.
//     세이브 파일은 이 한 벌과 「직전 선택지」 한 벌을 그대로 쓴 것이다. 문맥에는 대본 자리, 층 50개, 배경음·환경음 번호, 대화창 상태가 있다.
//   · 엔진은 문맥만으로 화면을 다시 세운다: 대본 읽기 0x41a0c0 → 자리 0x4130e0 → 층·대화창 0x41e920 → 전체 찍기 0x43d350.
//     (불러오기·건너뛰기 멈춤이 쓰는 0x41e8b0 의 뒷부분이다.)
//   → 되감기 = 멈춘 자리마다 그 한 벌(+ 대화 기록 100줄)을 모아 두었다가, 고른 한 벌을 문맥에 넣고 같은 함수를 부르는 것.
//     층은 지금과 바이트까지 같은 것은 건드리지 않고(기록 포인터를 잠깐 비우면 엔진의 층 다시 세우기 0x403d10 이 그냥 돌아간다),
//     소리는 상태가 다를 때만 명령을 보낸다(같은 곡이면 엔진이 그대로 이어 둔다).
//   · 문맥에 없어서 따로 챙기는 것
//       노란 자막의 글: 영문 패치가 글 넣기(0x403870)의 복사 대상을 고정 버퍼 0x48fe00 으로 돌려놓아 문맥에 글이 없다
//         → 글 넣기 명령(0x20) 직후에 그 글을 층마다 적어 두고, 되돌린 뒤 엔진의 글 넣기로 다시 넣는다.
//       대사보다 먼저 나오는 자막 음성(명령 0x42): 그 뒤 처음 멈춘 자리에 붙여 두었다가 그 자리로 가면 다시 튼다.
//       되풀이 효과음(환경음): 엔진의 다시 세우기가 되풀이 깃발을 스스로 지워 못 살린다 → 그 자리의 값으로 직접 켜고 끈다.
//       엔진 깃발 둘: 「한꺼번에 끝내기」[0x4663d4], 화면 바꿈 묶음 [0x4663d0].
//   · 대사 없이 흐르는 소리 자막(음성 0x42 → 자막 → 음성 끝 기다림 0x45, 또는 시간 기다림 0x0d 로 쪽을 넘김)은 엔진이 멈추지도
//     상태를 뜨지도 않는다 → 음성 명령을 꺼낼 때(= 그 명령 직전 상태) 한 벌을 떠 두었다가 걸음으로 삼는다. 그 자리로 돌아가면 VM 이
//     음성 명령부터 다시 실행한다(음성·자막·쪽 넘김이 엔진 자신의 명령으로 다시 흐른다).
//   · 붙잡아 두기: 그 기다림이 끝난 뒤 다음 명령을 꺼내기 직전에, 엔진의 「글 없는 클릭 대기」(명령 0x0a 의 처리기 0x41de10)의
//     상태 뜨기 다음부터(0x41de23)를 부른다 — 건너뛰기 중이면 바로 돌아오고, 자동 진행이면 잠깐 쉬고, 아니면 클릭을 기다린다.
//     엔진 자신의 클릭 대기라서 그동안 오른쪽 클릭·지도·저장·자동·건너뛰기·대화 기록이 평소대로 된다.
//
// 흐름
//   창 스레드: Backspace → 큰 조건만 확인(지도·메뉴·하위 대본·더 앞이 없음) → 자동 진행이면 끄고 → 요청을 남기고 VM 을 깨운다. 그 밖의 일은 모두 VM 스레드가 한다.
//   VM 스레드: 글이 찍히는 중이거나 화면 효과가 도는 중이면 엔진의 「한꺼번에 끝내기」([0x4663d4]=1, 엔진의 클릭이 하는 일) — 그림을 찍을 때마다 본다.
//             기다리던 것(입력·음성 끝·효과음 끝·시간 — 모두 클릭으로도 끊기는 기다림)이 요청을 보고 바로 돌아옴
//             → 엔진이 그 명령의 뒷정리를 스스로 함 → 다음 명령을 꺼내기 직전(Rewind_AtFetch)에 「어디서 눌렀나」로 자리를 정해
//             문맥을 바꾸고 화면을 다시 세움 → 그 자리의 명령이 다시 실행됨(글·음성·자막).
//               · 대사·선택지·붙잡힌 소리 자막에 멈춰 있었다 → 그 앞 자리
//               · 소리 자막이 흐르는 중이었다              → 0.8초 넘게 흐른 뒤면 그 자막을 처음부터, 막 시작했으면 그 앞 자리
//               · 자리와 자리 사이(막 넘긴 뒤)였다          → 방금 떠난 자리
//   요청이 0.6초 안에 쓰이지 못하면(엔진이 끊을 수 없는 일을 하는 중) 버린다 — 한참 뒤에 느닷없이 되감기지 않게.
//   그 사이 게임 창으로 가는 찍기는 건너뛴다(빈 대화창이 한 번 비치지 않게). 다시 세운 뒤 전체 찍기 한 번.
//
// 불러오기·타이틀로·엔진의 「직전 선택지로」 뒤에는 모아 둔 것을 버린다(세이브 파일에는 아무것도 넣지 않는다).
//
// 설정(forest-qol.ini): rewind=1, rewind_depth=300(기억하는 걸음 수, 한 걸음 약 37KB),
//   rewind_log=0(1 이면 걸음마다 events.log 에 — 진단용), 시험용 rewind_verify=0·rewind_test=0.
#include "qol.h"
#include <algorithm>
#include <deque>
#include <memory>
#include <unordered_map>
#include <cstring>
#include <cstdio>
#include <cstdarg>

namespace forest { namespace qol {
namespace {
#define EV(a) (*(volatile int*)(uintptr_t)(a))
#define EW(a) (*(volatile uint16_t*)(uintptr_t)(a))

// ---------------------------------------------------------------- 엔진 주소
constexpr uintptr_t kCtx = 0x46646c, kPriCtx = 0x4690a8, kSecCtx = 0x46bce4;
constexpr size_t kCtxSize = 0x2c3c, kVarSize = 14000;
constexpr uintptr_t kVars = 0x46643c, kPriVars = 0x466440, kSecVars = 0x466444;
constexpr uintptr_t kEngine = 0x466398, kScript = 0x46639c, kMsgWin = 0x46630c;
constexpr size_t kLogOff = 0xac, kLogSize = 0xaf0 * 4, kLogViewIdx = 0x2c6c, kLogViewing = 0x2c70;   // 대화창 객체 안: 대화 기록 100줄
constexpr uintptr_t kNested = 0x466432;                       // u16: 화면 단추가 부른 하위 대본 안이면 0 아님
constexpr uintptr_t kDepth = 0x4664bc, kDepthScripts = 0x46647e, kDepthPcs = 0x466494;
constexpr uintptr_t kClickWait = 0x4663e8, kTyping = 0x4663e0, kFinishNow = 0x4663d4, kChoice = 0x4663cc, kSelect = 0x466418;
constexpr uintptr_t kSettings = 0x46640c, kSaveScr = 0x466410, kLoadScr = 0x466414;
constexpr uintptr_t kAuto = 0x466408, kCtrlKey = 0x4663f8, kCtrlSkip = 0x466400, kTabReq = 0x4663fc, kTabSkip = 0x466404;
constexpr uintptr_t kDeferred = 0x4663d0;                     // 화면 바꿈 묶음(명령 0x1a … 0x1c) 안이면 1 — 층 명령이 화면에 바로 내지 않는다. 문맥 밖
constexpr uintptr_t kCheckpointOk = 0x4664d0;                 // 엔진이 상태를 떠도 되는 곳인가(대본이 켜고 끈다, 문맥 안)
constexpr uintptr_t kUserHide = 0x466420;                     // 사용자가 대화창을 숨겼다(Shift·아이콘 줄). 숨긴 동안 엔진은 클릭·Enter 를 대화창 되돌리기에만 쓴다
constexpr uintptr_t kVoiceWait = 0x4663f4;                    // 음성 끝 기다림(명령 0x45) 중 — 클릭이 음성을 끊고 0 으로 만든다(0x4159da)
constexpr uintptr_t kTimedThread = 0x48fdf4;                  // 시간 기다림(명령 0x0d, 영문 패치 0x458680)이 기다리는 스레드 핸들
constexpr uintptr_t kTextScratch = 0x48fe00;                  // 글 넣기(0x403870)가 글을 복사해 두는 고정 버퍼(영문 패치)
constexpr uintptr_t kLayerTable = 0x466238;                   // 층 객체 50개
constexpr size_t kLayerRec = 0x288, kRecSize = 0xa4, kLayerRecs = 0x74;   // 층 객체 → 문맥 안 자기 기록(0x4664e0 + i*0xa4)
constexpr int kLayers = 50;
constexpr uint16_t kTitleScript = 1;                          // 대본 0001 = 타이틀 화면(여기로 돌아오면 판이 끝난 것)

// 엔진 함수
constexpr uintptr_t fLoadScript = 0x41a0c0;   // int __cdecl(u16 대본): 지금 깊이의 대본을 읽는다
constexpr uintptr_t fSeek = 0x4130e0;         // int __thiscall(스크립트 객체, u32 pc)
constexpr uintptr_t fLayers = 0x41e920;       // void __cdecl(): 층 50개·글 객체·대화창·덮개를 문맥대로(화면 잠금 안에서 부른다)
constexpr uintptr_t fFullPaint = 0x43d350;    // void __thiscall(엔진 객체): 전체 합성·찍기
constexpr uintptr_t fLock = 0x43cf60, fUnlock = 0x43cf70;   // void __thiscall(엔진 객체): 화면 잠금
constexpr uintptr_t fVoiceStop = 0x419000;    // void __cdecl(int): 음성 채널 끊기
constexpr uintptr_t fBgmStop = 0x43f750;      // void __thiscall(엔진 객체, int): 배경음 끊기
constexpr uintptr_t fChanStop = 0x43f630;     // void __thiscall(엔진 객체, int 채널, int): 채널 끊기
constexpr uintptr_t fBgmPlay = 0x41e5c0;      // void __cdecl(u16 곡, u16): 배경음(같은 곡이면 엔진이 그대로 둔다 0x43f6cd)
constexpr uintptr_t fSeOpen = 0x41e420;       // void __cdecl(u16 번호): 효과음 채널을 끊고 그 파일을 연다([0x466472] 을 0 으로 만든다)
constexpr uintptr_t fSePlay = 0x41e490;       // void __cdecl(u16 되풀이(999 = 계속), u16, u16 음량)
constexpr uintptr_t fBarAutoOff = 0x410c20;   // void __thiscall(대화창): 자동 진행 표시 끄고 아이콘 줄 되살림
constexpr uintptr_t fUnhide = 0x4165b0;       // int __stdcall(int, int): 숨긴 대화창 되돌리기(대화창 보이기, [0x466420]=0, 더러운 곳 찍기 — 화면 잠금은 제가 쥔다)
constexpr uintptr_t fBarShow = 0x411280;      // void __thiscall(대화창, int): 아이콘 줄을 상태대로(대화창이 보이고 줄이 켜져 있을 때만 보임)
constexpr uintptr_t fLayerText = 0x403870;    // void __thiscall(층, 글, 효과, x, y, 인자, 건너뛰는중): 명령 0x20 이 부르는 글 넣기
constexpr uintptr_t fVoicePlay = 0x41e550;    // void __cdecl(번호, 되풀이, ?, 음량): 명령 0x42
constexpr uintptr_t pClickWaitCmd = 0x41de10; // 명령 0x0a 의 처리기: 상태 뜨기 → (0x41de23) 건너뛰기면 끝 / 자동이면 잠깐 / 아니면 클릭 대기
const uint8_t kClickWaitCmdHead[25] = {0xa1, 0xd0, 0x64, 0x46, 0x00, 0x53, 0x33, 0xdb, 0x56, 0x3b, 0xc3, 0x57, 0x74, 0x05, 0xe8, 0x1d, 0xac, 0xff, 0xff,
                                       0x39, 0x1d, 0x00, 0x64, 0x46, 0x00};
constexpr uint32_t kVtChannel = 0x45d5d4, kVtChannelImpl = 0x45d518, kVtEvent = 0x45d4d0;   // 소리 채널 객체 → 안쪽 → 끝 이벤트

// 멈추는 명령(엔진이 상태를 뜨는 자리): 대사·이어 쓰기·선택지·단추 고르기·글 없는 클릭 대기 둘
bool isStopOp(uint16_t op) { return op == 0x51 || op == 0x52 || op == 0x0e || op == 0x49 || op == 0x0a || op == 0x0b; }

// ---------------------------------------------------------------- 설정·상태
struct Config {
    bool on = false, log = false, verify = false, test = false;
    size_t depth = 300;
} C;
constexpr DWORD kReqLifeMs = 600;             // 요청이 이 안에 쓰이지 못하면 버린다
constexpr DWORD kUnitRestartMs = 800;         // 소리 자막이 이만큼 흐른 뒤에 누르면 「그 자막을 처음부터」, 그 전이면 「그 앞 자리로」
constexpr DWORD kRepeatMs = 100;              // 누르고 있을 때 걸음 사이(초당 10걸음)
bool gHoldOk = false;                         // 붙잡아 두기를 쓸 수 있다(엔진 코드가 아는 꼴)
UINT gMsgTest = 0;
HANDLE gWake = nullptr;
CRITICAL_SECTION gCs;
LARGE_INTEGER gQpf;

struct TextSet { bool valid = false; int arg = 0; std::string text; };
struct FreeVoice { bool valid = false; uint16_t a[4] = {}; };
struct Sec { uint8_t ctx[kCtxSize]; uint8_t vars[kVarSize]; };
struct Snap {
    uint8_t ctx[kCtxSize]; uint8_t vars[kVarSize]; uint8_t log[kLogSize];
    std::shared_ptr<Sec> sec;                     // 그때의 「직전 선택지」 한 벌(바뀔 때까지 여러 걸음이 함께 쓴다)
    std::shared_ptr<Sec> pri;                     // 소리 자막 걸음만: 그때 엔진이 들고 있던 「지금 상태」 한 벌(= 그 앞 대사의 것)
    int sid = 0, depth = 0; uint32_t pc = 0; uint16_t op = 0;
    bool unit = false;                            // 소리 자막 걸음
    int deferred = 0;                             // 그때의 [0x4663d0]
    std::vector<std::pair<int, TextSet>> texts;   // 그때 보이던 글 층
    FreeVoice voice;                              // 이 자리에 붙은 자막 음성
    RunMark mark;                                 // 이야기의 지도 회차 기록의 그 시점
};
uint64_t keyOf(int depth, int sid, uint32_t pc) { return ((uint64_t)(depth & 0xff) << 56) | ((uint64_t)(sid & 0xffff) << 32) | pc; }
uint64_t keyOf(const Snap& s) { return keyOf(s.depth, s.sid, s.pc); }

// 걸음 줄(gCs 로 지킨다)
std::deque<std::unique_ptr<Snap>> gHist;   // 뒤 = 지금 자리
std::shared_ptr<Sec> gSec;                 // 지금의 「직전 선택지」 한 벌
std::vector<uint64_t> gAhead;              // 되감아서 떼어 낸 걸음들의 자리(차례대로) = 「다시 보는 구간」. 같은 차례로 다시 지나는 동안만 유효하다
size_t gAheadPos = 0;
volatile LONG gCount = 0;                  // gHist 크기(창 스레드가 읽음)

// 창 스레드 ↔ VM 스레드
volatile LONG gPending = 0;                // 되돌아갈 걸음 수(요청)
volatile LONG gCutStop = 0;                // 요청이 대사·선택지·붙잡힌 자막의 입력 대기를 끊었다(= 그 자리에 멈춰 있었다)
volatile LONG gHold = 0;                   // 게임 창 찍기를 잠깐 건너뜀
volatile LONG gHeld = 0;                   // 그동안 건너뛴 찍기 수(기록용)
volatile DWORD gHoldAt = 0, gReqTick = 0;
volatile LONG gCurOp = 0;                  // VM 이 마지막으로 꺼낸 명령
volatile DWORD gUnitAt = 0;                // 지금 흐르는 소리 자막이 뜬 때
volatile LONG gVoiceFree = 0;              // 대사에 딸리지 않은 음성(명령 0x42)이 아직 울릴 수 있다
volatile LONG gTextStale = 0;              // 모아 둔 것을 버렸다 → VM 스레드가 다음 명령에서 제 상태도 비운다
LARGE_INTEGER gReqAt = {};
DWORD gFetchTid = 0, gHistTid = 0;
volatile LONG gSeq = 0;

// VM 스레드만
TextSet gText[kLayers + 1];                // 층마다 마지막으로 넣은 글
FreeVoice gVoiceSince;                     // 지난 걸음 뒤에 따로 튼 음성
int gPrevOp = 0, gPrevLayer = 0, gPrevArg = 0;
std::unique_ptr<Snap> gCand;               // 음성 명령 직전에 떠 둔 한 벌(소리 자막이면 이것이 걸음이 된다)
bool gUnitOpen = false;                    // 줄에 넣은 소리 자막이 아직 흐르는 중
bool gUnitHeld = false;                    // 그 자막은 다시 보는 것 → 기다림이 끝나면 붙잡아 둔다
bool gAfterVoiceWait = false;              // 앞 명령이 음성 끝 기다림이었다
bool gHoldAfter = false;                   // 지금 명령(기다림)이 끝나면 붙잡아 둔다
bool gSkipTimer = false;                   // 지금 명령(시간 기다림)은 기다리지 않는다(바로 붙잡아 두기로)
bool gUserCut = false;                     // 그 기다림을 사용자가 클릭으로 끊었다(→ 붙잡지 않고 넘어간다)
bool gHintShown = false;
LARGE_INTEGER gRestoredAt = {};            // 마지막 되돌리기가 화면을 낸 때(진단: 소리 자막이 다시 뜨기까지)
RunMark gPreMark; bool gPreMarkOk = false; // 지금 명령(멈추는 명령)을 지도 모듈이 보기 전의 회차 기록 시점

// 창 스레드만
DWORD gLastAccept = 0, gLastNoMore = 0;

// 시험(rewind_verify=1): 같은 자리를 다시 지날 때 처음 뜬 한 벌과 바이트가 같은지
struct Seen { std::unique_ptr<uint8_t[]> bytes; RunMark mark; };
std::unordered_map<uint64_t, Seen> gSeen;

void rlog(const char* fmt, ...) {
    char b[640]; va_list ap; va_start(ap, fmt); _vsnprintf_s(b, sizeof(b), _TRUNCATE, fmt, ap); va_end(ap);
    Log(std::string("rewind: ") + b);
}
double ms(const LARGE_INTEGER& a, const LARGE_INTEGER& b) { return (b.QuadPart - a.QuadPart) * 1000.0 / gQpf.QuadPart; }
void* engine() { return *(void* volatile*)kEngine; }
uint8_t* msgWin() { return (uint8_t*)*(void* volatile*)kMsgWin; }
bool screensOpen() { return EV(kSettings) || EV(kSaveScr) || EV(kLoadScr); }
bool expired() { return GetTickCount() - gReqTick > kReqLifeMs; }
uint16_t curScript() { const uint8_t* sc = *(const uint8_t* volatile*)kScript; return sc ? *(const uint16_t*)(sc + 0x3c) : 0; }

// 대본 인자(V꼴): 위 16비트 = 변수표를 거치는 횟수, 아래 16비트 = 값(엔진 0x41b8b0 과 같다)
uint16_t vres(uint32_t v) {
    int ind = (int16_t)(v >> 16); uint16_t val = (uint16_t)v;
    const uint16_t* vars = *(const uint16_t**)kVars;
    while (ind-- > 0 && vars) val = vars[(int16_t)val];
    return val;
}
// 지금 명령(cursor) 뒤 skip 바이트에 있는 다음 명령(없으면 0)
uint16_t opAfter(const uint8_t* cursor, size_t skip) {
    const uint8_t* sc = *(const uint8_t**)kScript;
    const uint8_t* base = sc ? *(const uint8_t* const*)sc : nullptr;
    const uint32_t len = sc ? *(const uint32_t*)(sc + 0x28) : 0;
    if (!base || cursor < base || cursor + skip + 2 > base + len) return 0;
    return *(const uint16_t*)(cursor + skip);
}
// 소리 채널이 끝날 때 서는 이벤트(엔진 0x43f690 → 채널 객체 → 안쪽 → 0x44ed70 이 기다리는 핸들). 꼴이 다르면 nullptr
HANDLE chanEvent(int ch) {
    uint8_t* eng = (uint8_t*)engine(); if (!eng) return nullptr;
    uint8_t* w = *(uint8_t**)(eng + 0x1ac + 4 * ch); if (!w || *(uint32_t*)w != kVtChannel) return nullptr;
    uint8_t* in = *(uint8_t**)(w + 4); if (!in || *(uint32_t*)in != kVtChannelImpl) return nullptr;
    uint8_t* ev = *(uint8_t**)(in + 0xc); if (!ev || *(uint32_t*)ev != kVtEvent) return nullptr;
    return *(HANDLE*)(ev + 4);
}

// 엔진의 「글 없는 클릭 대기」를 상태 뜨기 없이: 명령 0x0a 처리기(0x41de10)의 머리를 그대로 밟고 0x41de23 으로 들어간다.
// 그 뒤는 엔진 코드다 — 건너뛰기면 바로 ret, 자동이면 잠깐(진행 모듈의 PlayPauseWait), 아니면 대기 표시·아이콘 줄을 켜고 입력을 기다렸다가 되돌리고 ret.
__declspec(naked) void engineClickWait() {
    __asm {
        push ebx
        xor ebx, ebx
        push esi
        push edi
        mov eax, 41de23h
        jmp eax
    }
}

void clearLocked(const char* why) {
    if (!gHist.empty() && C.log) rlog("history cleared (%s), had %d", why, (int)gHist.size());
    gHist.clear(); gSec.reset(); gSeen.clear(); gAhead.clear(); gAheadPos = 0;
    InterlockedExchange(&gCount, 0);
    InterlockedExchange(&gTextStale, 1);
}

// 모아 둔 것과 걸려 있는 요청을 모두 버린다(불러오기·엔진의 「직전 선택지로」·타이틀로 돌아옴)
void resetAll(const char* why) {
    EnterCriticalSection(&gCs); clearLocked(why); LeaveCriticalSection(&gCs);
    InterlockedExchange(&gPending, 0); InterlockedExchange(&gCutStop, 0); InterlockedExchange(&gHold, 0);
}

int firstDiff(const uint8_t* a, const uint8_t* b, size_t n) { for (size_t i = 0; i < n; ++i) if (a[i] != b[i]) return (int)i; return -1; }
int countDiff(const uint8_t* a, const uint8_t* b, size_t n) { int c = 0; for (size_t i = 0; i < n; ++i) c += a[i] != b[i]; return c; }
void verifyLocked(const Snap& s) {
    const size_t total = kCtxSize + kVarSize + kLogSize;
    auto it = gSeen.find(keyOf(s));
    if (it == gSeen.end()) {
        if (gSeen.size() > 600) return;
        Seen e; e.bytes.reset(new uint8_t[total]); e.mark = s.mark;
        memcpy(e.bytes.get(), s.ctx, kCtxSize); memcpy(e.bytes.get() + kCtxSize, s.vars, kVarSize); memcpy(e.bytes.get() + kCtxSize + kVarSize, s.log, kLogSize);
        gSeen.emplace(keyOf(s), std::move(e));
        return;
    }
    const uint8_t* o = it->second.bytes.get();
    int dc = countDiff(o, s.ctx, kCtxSize), dv = countDiff(o + kCtxSize, s.vars, kVarSize), dl = countDiff(o + kCtxSize + kVarSize, s.log, kLogSize);
    auto same = [](const RunPoint& a, const RunPoint& b) { return a.known == b.known && a.script == b.script && a.choice == b.choice && a.pc == b.pc && a.events == b.events; };
    const RunMark& m = it->second.mark;
    const bool dr = !(m.epoch == s.mark.epoch && same(m.run, s.mark.run) && same(m.primary, s.mark.primary) && same(m.secondary, s.mark.secondary) && m.pending == s.mark.pending && m.lastStory == s.mark.lastStory);
    if (!dc && !dv && !dl && !dr) rlog("verify %04d:%u SAME (context, variables, text history, run journal %u events)", s.sid, s.pc, s.mark.run.events);
    else rlog("verify %04d:%u DIFF context %d bytes (first +0x%x), variables %d (first +%d), text history %d (first +0x%x), run journal %s (events %u/%u/%u was %u/%u/%u, choice %d was %d, pending %d was %d)", s.sid, s.pc,
              dc, firstDiff(o, s.ctx, kCtxSize), dv, firstDiff(o + kCtxSize, s.vars, kVarSize), dl, firstDiff(o + kCtxSize + kVarSize, s.log, kLogSize), dr ? "differs" : "same",
              s.mark.run.events, s.mark.primary.events, s.mark.secondary.events, m.run.events, m.primary.events, m.secondary.events, s.mark.run.choice, m.run.choice, (int)s.mark.pending.size(), (int)m.pending.size());
}

// ---------------------------------------------------------------- 한 벌 뜨기·줄에 넣기(VM 스레드, gCs 안)
// unitCand = 음성 명령 직전(소리 자막의 걸음이 될 수 있는 것). 아니면 엔진이 막 상태를 뜬 자리.
std::unique_ptr<Snap> captureLocked(uint16_t op, bool unitCand) {
    auto s = std::make_unique<Snap>();
    memcpy(s->ctx, (void*)kCtx, kCtxSize);
    memcpy(s->vars, *(void**)kVars, kVarSize);
    if (uint8_t* w = msgWin()) memcpy(s->log, w + kLogOff, kLogSize); else memset(s->log, 0, kLogSize);
    if (!gSec) { gSec = std::make_shared<Sec>(); memcpy(gSec->ctx, (void*)kSecCtx, kCtxSize); memcpy(gSec->vars, *(void**)kSecVars, kVarSize); }
    s->sec = gSec;
    s->depth = EW(kDepth);
    s->sid = ((volatile uint16_t*)kDepthScripts)[s->depth & 15];
    s->pc = ((volatile uint32_t*)kDepthPcs)[s->depth & 15];
    s->op = op;
    s->unit = unitCand;
    s->deferred = EV(kDeferred);
    for (int i = 0; i < kLayers; ++i) {
        const uint8_t* rec = s->ctx + kLayerRecs + i * kRecSize;
        if (*(const uint16_t*)(rec + 0xa) == 2 && *(const int*)(rec + 0x18) && gText[i].valid) s->texts.emplace_back(i, gText[i]);
    }
    if (unitCand) {
        // 엔진은 소리 자막에서 상태를 뜨지 않는다 → 그 사이에 저장하면 앞 대사가 저장된다. 되돌아와서도 그렇도록 엔진의 한 벌을 함께 둔다.
        s->pri = std::make_shared<Sec>();
        memcpy(s->pri->ctx, (void*)kPriCtx, kCtxSize); memcpy(s->pri->vars, *(void**)kPriVars, kVarSize);
    } else {
        s->voice = gVoiceSince; gVoiceSince.valid = false;   // 이 자리에 붙인다(다음 자리에는 안 붙음)
    }
    // 회차 기록의 시점은 「이 자리의 명령을 지도 모듈이 보기 전」이다 — 되돌린 뒤 그 명령이 다시 실행되면 지도 모듈이 처음과 똑같이 다시 적는다.
    // (음성 명령 직전에 뜨는 한 벌은 지금이 그때다. 엔진이 상태를 뜬 자리는 그 명령을 꺼낼 때 적어 둔 것을 쓴다.)
    s->mark = (!unitCand && gPreMarkOk) ? gPreMark : MarkRun();
    return s;
}
// 돌려주는 값: 이 걸음이 「다시 보는 구간」 안인가
bool pushLocked(std::unique_ptr<Snap> s) {
    if (C.verify) verifyLocked(*s);
    if (!gHist.empty() && keyOf(*gHist.back()) == keyOf(*s)) gHist.pop_back();
    bool reread = false;
    if (gAheadPos < gAhead.size()) {
        if (gAhead[gAheadPos] == keyOf(*s)) { reread = true; if (++gAheadPos == gAhead.size()) { gAhead.clear(); gAheadPos = 0; } }
        else { gAhead.clear(); gAheadPos = 0; }             // 다른 길로 갔다 → 여기부터는 처음 보는 곳
    }
    if (C.log) rlog("stop %04d:%u op 0x%02x depth %d bgm %u se %u/%u -> history %d%s%s%s%s", s->sid, s->pc, s->op, s->depth,
                    *(uint16_t*)(s->ctx + 0), *(uint16_t*)(s->ctx + 4), *(uint16_t*)(s->ctx + 6), (int)gHist.size() + 1,
                    s->texts.empty() ? "" : " +subtitle", s->voice.valid ? " +voice" : "", s->unit ? " +unit" : "", reread ? " +reread" : "");
    gHist.push_back(std::move(s));
    while (gHist.size() > C.depth) gHist.pop_front();
    InterlockedExchange(&gCount, (LONG)gHist.size());
    return reread;
}

// ---------------------------------------------------------------- 되돌리기(VM 스레드, 명령을 꺼내기 직전)
void restore(const Snap& s, int steps, int left, const LARGE_INTEGER& reqAt) {
    LARGE_INTEGER t0, tc, tsc, tl, tx, tp, tv, ts;
    QueryPerformanceCounter(&t0);
    void* eng = engine();
    // 진행 깃발: 건너뛰기·자동은 끈다(되감은 뒤엔 손으로 읽는다)
    EV(kCtrlKey) = 0; EV(kCtrlSkip) = 0; EV(kTabReq) = 0; EV(kTabSkip) = 0;
    if (EV(kAuto)) { EV(kAuto) = 0; if (msgWin()) ((void(__thiscall*)(void*))fBarAutoOff)(msgWin()); }
    EV(kChoice) = 0;
    // 문맥 밖의 엔진 깃발 둘: 「한꺼번에 끝내기」는 지우고(엔진도 판을 새로 시작할 때 지운다 0x41515b), 화면 바꿈 묶음 깃발은 그 자리의 값으로.
    // 자리와 자리 사이에서 되감으면 묶음(0x1a … 0x1c) 한가운데일 수 있다 — 깃발이 남으면 돌아간 자리의 글·그림이 화면에 나오지 않는다.
    EV(kFinishNow) = 0; EV(kDeferred) = s.deferred;
    // 지금 상태와 견주기(문맥을 덮기 전에): 기록이 바이트까지 같은 층은 건드리지 않는다
    const uint16_t liveSe = EW(kCtx + 4), liveLoop = EW(kCtx + 6);
    const uint16_t wantBgm = *(const uint16_t*)(s.ctx + 0), wantSe = *(const uint16_t*)(s.ctx + 4), wantLoop = *(const uint16_t*)(s.ctx + 6), wantVol = *(const uint16_t*)(s.ctx + 8);
    uint8_t* mgr = eng ? *(uint8_t**)((uint8_t*)eng + 0x1a8) : nullptr;
    const int liveTrack = mgr ? *(int*)(mgr + 0x10) : 0;
    void* skipped[kLayers] = {}; int nSame = 0;
    for (int i = 0; i < kLayers; ++i) {
        uint8_t* lay = *(uint8_t**)(kLayerTable + i * 4);
        if (!lay) continue;
        uint8_t* rec = *(uint8_t**)(lay + kLayerRec);
        if (!rec || rec < (uint8_t*)kCtx || rec + kRecSize > (uint8_t*)kCtx + kCtxSize) continue;
        const uint8_t* want = s.ctx + (rec - (uint8_t*)kCtx);
        if (*(const uint16_t*)(want + 0xa) == 2 || *(const uint16_t*)(rec + 0xa) == 2) continue;   // 글 층은 기록이 같아도 글이 다를 수 있다
        if (memcmp(rec, want, kRecSize) == 0) { skipped[i] = rec; ++nSame; }
    }
    // 문맥·변수·엔진의 한 벌 둘·대화 기록
    ((void(__thiscall*)(void*))fLock)(eng);
    memcpy((void*)kCtx, s.ctx, kCtxSize);
    memcpy(*(void**)kVars, s.vars, kVarSize);
    // 엔진의 「지금 상태」 한 벌(저장하면 파일에 들어가는 것): 대사·선택지 자리는 그 자리 자신, 소리 자막 걸음은 그 앞 대사의 것
    memcpy((void*)kPriCtx, s.pri ? s.pri->ctx : s.ctx, kCtxSize);
    memcpy(*(void**)kPriVars, s.pri ? s.pri->vars : s.vars, kVarSize);
    if (s.sec) { memcpy((void*)kSecCtx, s.sec->ctx, kCtxSize); memcpy(*(void**)kSecVars, s.sec->vars, kVarSize); }
    if (uint8_t* w = msgWin()) { memcpy(w + kLogOff, s.log, kLogSize); *(int*)(w + kLogViewIdx) = 100; }
    ((void(__thiscall*)(void*))fUnlock)(eng);
    QueryPerformanceCounter(&tc);
    // 대본·자리
    int ok = ((int(__cdecl*)(unsigned))fLoadScript)((unsigned)(uint16_t)s.sid);
    if (ok) ((int(__thiscall*)(void*, uint32_t))fSeek)(*(void**)kScript, s.pc);
    else rlog("ERROR script %04d could not be loaded while going back", s.sid);
    QueryPerformanceCounter(&tsc);
    // 화면 다시 세우기: 같은 층은 기록 포인터를 잠깐 비워 둔다 — 엔진의 층 다시 세우기(0x403d10)는 포인터가 비면 그 층을 그냥 둔다(0x403d40)
    ((void(__thiscall*)(void*))fLock)(eng);
    for (int i = 0; i < kLayers; ++i) if (skipped[i]) *(void**)(*(uint8_t**)(kLayerTable + i * 4) + kLayerRec) = nullptr;
    ((void(__cdecl*)())fLayers)();
    for (int i = 0; i < kLayers; ++i) if (skipped[i]) *(void**)(*(uint8_t**)(kLayerTable + i * 4) + kLayerRec) = skipped[i];
    ((void(__thiscall*)(void*))fUnlock)(eng);
    // 사용자가 대화창을 숨겨 둔 채 되감았으면 숨김을 푼다(엔진이 숨긴 동안의 클릭에 하는 일 그대로). 그대로 두면 돌아간 대사의 글이 안 보이고,
    // 다음 Enter 한 번이 대화창을 되돌리는 데 쓰인다. 층 다시 세우기는 이 숨김을 건드리지 않는다. (찍기는 아래 전체 찍기까지 붙잡혀 있다)
    if (EV(kUserHide)) ((int(__stdcall*)(int, int))fUnhide)(0, 0);
    // 아이콘 줄: 엔진의 대화창 다시 세우기(0x410510)는 「보여야 하면 보이게」만 한다. 숨겨져 있어야 하는 자리(대화창이 아직 안 나온 곳)로
    // 돌아가면 줄이 남으므로 엔진 함수로 상태대로 맞춘다.
    if (msgWin()) ((void(__thiscall*)(void*, int))fBarShow)(msgWin(), 1);
    QueryPerformanceCounter(&tl);
    // 글 층(노란 자막) 다시 넣기
    int nText = 0;
    for (auto& t : s.texts) {
        uint8_t* lay = *(uint8_t**)(kLayerTable + t.first * 4);
        if (!lay) continue;
        const uint8_t* want = s.ctx + kLayerRecs + t.first * kRecSize;
        ((void(__thiscall*)(void*))fLock)(eng);
        ((void(__thiscall*)(void*, const char*, int, int, int, int, int))fLayerText)(lay, t.second.text.c_str(), 0, *(const int*)(want + 0), *(const int*)(want + 4), t.second.arg, 0);
        memcpy((uint8_t*)kCtx + kLayerRecs + t.first * kRecSize, want, kRecSize);   // 글 넣기가 건드린 기록 칸을 그 자리의 값으로
        ((void(__thiscall*)(void*))fUnlock)(eng);
        gText[t.first] = t.second;
        ++nText;
    }
    QueryPerformanceCounter(&tx);
    InterlockedExchange(&gHold, 0);
    ((void(__thiscall*)(void*))fFullPaint)(eng);
    QueryPerformanceCounter(&tp);            // ← 여기까지가 「화면이 바뀌는 데 걸린 시간」
    gRestoredAt = tp;
    // 되돌리는 동안 다음 요청이 와 있으면(누르고 있을 때) 이 자리는 곧 지나간다: 그 요청의 화면 붙잡기를 다시 걸고, 아래에서 이 자리의 자막 음성은 틀지 않는다
    const bool passing = gPending != 0;
    if (passing) { gHoldAt = GetTickCount(); InterlockedExchange(&gHold, 1); }
    // 소리는 화면을 낸 뒤에, 상태가 다를 때만(엔진의 소리 명령은 하나에 약 0.03초).
    // 음성: 대사에 딸린 음성은 엔진이 그 대사를 넘길 때 스스로 끊었다(0x41cb65). 따로 튼 음성(0x42)만 끊는다.
    if (InterlockedExchange(&gVoiceFree, 0)) ((void(__cdecl*)(int))fVoiceStop)(0);
    QueryPerformanceCounter(&tv);
    const char* snd = "";
    if (wantBgm) ((void(__cdecl*)(unsigned, unsigned))fBgmPlay)(wantBgm, 1);   // 같은 곡이면 엔진이 그대로 둔다
    else if (liveTrack) ((void(__thiscall*)(void*, int))fBgmStop)(eng, 1);     // 엔진의 다시 세우기는 「있는 곡」만 튼다 → 없는 자리면 끊는다
    const bool want = wantSe && wantLoop, have = liveSe && liveLoop;
    if (want && !(have && liveSe == wantSe)) {
        ((void(__cdecl*)(unsigned))fSeOpen)(wantSe);
        ((void(__cdecl*)(unsigned, unsigned, unsigned))fSePlay)(999, 1, wantVol);
        snd = " se-loop-restarted";
    } else if (!want && have) {
        ((void(__thiscall*)(void*, int, int))fChanStop)(eng, 0, 1);
        snd = " se-loop-stopped";
    }
    // 엔진의 효과음 열기(0x41e420 → 0x41e520)는 문맥의 되풀이 깃발을 지운다 → 돌아간 자리의 값으로 다시 맞춘다
    EW(kCtx + 4) = wantSe; EW(kCtx + 6) = wantLoop; EW(kCtx + 8) = wantVol;
    // 그 자리에 붙은 자막 음성 다시 틀기
    const bool voiced = s.voice.valid && !passing;
    if (voiced) {
        ((void(__cdecl*)(unsigned, unsigned, unsigned, unsigned))fVoicePlay)(s.voice.a[0], s.voice.a[1], s.voice.a[2], s.voice.a[3]);
        InterlockedExchange(&gVoiceFree, 1);
    }
    QueryPerformanceCounter(&ts);
    // VM 쪽 상태: 이 자리의 명령이 다시 실행되며 새로 쌓인다
    gVoiceSince = s.voice;
    gPrevOp = 0;
    gCand.reset();
    gUnitOpen = false; gUnitHeld = false; gAfterVoiceWait = false; gHoldAfter = false; gSkipTimer = false; gUserCut = false;
    // 이야기의 지도 회차 기록도 그 시점으로, 진행 모듈의 「고른 뒤 자동 계속」 기억은 버린다
    const bool runOk = RewindRun(s.mark);
    Play_Rewound();
    LONG seq = InterlockedIncrement(&gSeq);
    LONG held = InterlockedExchange(&gHeld, 0);
    if (C.log) {
        int track2 = mgr ? *(int*)(mgr + 0x10) : 0;
        rlog("#%ld back %d to %04d:%u op 0x%02x depth %d%s | key-to-start %.1f ms, voice %.2f, copy %.3f, sound %.2f, script %.2f, rebuild %.2f, paint %.2f, total %.2f ms | history left %d | fast layers kept %d/50, bgm %d>%d%s%s%s%s texts %d held %ld visual %.2f subs %.2f",
             seq, steps, s.sid, s.pc, s.op, s.depth, ok ? "" : " (SCRIPT LOAD FAILED)",
             ms(reqAt, t0), ms(tp, tv), ms(t0, tc), ms(tv, ts), ms(tc, tsc), ms(tsc, tl), ms(tx, tp), ms(t0, ts), left,
             nSame, liveTrack, track2, snd, nText ? " subtitle-restored" : "", voiced ? " subtitle-voice-replayed" : (s.voice.valid ? " subtitle-voice-skipped(passing)" : ""), runOk ? "" : " run-journal-unknown",
             nText, held, ms(t0, tp), ms(tl, tx));
    }
}

// ---------------------------------------------------------------- 요청(창 스레드)
enum class No { Ok, Map, Menu, Buttons, SubScript, Nothing, Backlog };
No refuseWhy() {
    if (ChartIsOpen()) return No::Map;
    if (screensOpen()) return No::Menu;
    if (EV(kSelect)) return No::Buttons;
    if (EW(kNested)) return No::SubScript;
    if (gCount < 1) return No::Nothing;
    // 멈추는 명령 안(글이 찍히는 중·클릭 대기·자동 진행의 쉼·선택지)에서는 그 앞 자리가 있어야 한다 — 없으면 아무것도 하지 않는다
    if (gCount < 2 && (EV(kClickWait) || EV(kChoice) || isStopOp((uint16_t)gCurOp))) return No::Nothing;
    uint8_t* w = msgWin();
    if (w && *(int*)(w + kLogViewing)) return No::Backlog;
    return No::Ok;
}
const char* noText(No n) {
    switch (n) {
    case No::Map: return "map open"; case No::Menu: return "menu open"; case No::Buttons: return "button menu";
    case No::SubScript: return "inside a sub script"; case No::Nothing: return "no earlier stop"; case No::Backlog: return "viewing earlier text";
    default: return "";
    }
}

// 요청을 남긴다. 어디로 돌아갈지는 VM 스레드가 정한다(Rewind_AtFetch).
bool request(int steps, bool key, bool repeat) {
    if (gPending) {
        if (!expired()) return false;
        InterlockedExchange(&gPending, 0);         // 쓰이지 못한 옛 요청은 버린다
    }
    const No why = refuseWhy();
    if (why != No::Ok) {
        if (C.log) rlog("%s refused: %s", key ? "Backspace" : "test", noText(why));
        if (why == No::Nothing && key && !repeat && GetTickCount() - gLastNoMore > 3000) {
            gLastNoMore = GetTickCount();
            Toast(L"여기서 더 앞으로는 되감을 수 없습니다");
        }
        return false;
    }
    Play_AutoOff();                                // 자동 진행 중이면 끈다 → 자동의 쉼이 엔진의 클릭 대기로 넘어간다
    QueryPerformanceCounter(&gReqAt);
    gReqTick = GetTickCount();
    gHoldAt = gReqTick; InterlockedExchange(&gHold, 1);
    InterlockedExchange(&gPending, steps);
    // 지금 글이 찍히는 중이거나 화면 효과가 도는 중이면 바로 「한꺼번에 끝내기」(엔진의 클릭 0x415a35 가 창 스레드에서 하는 일 그대로).
    // 요청 뒤에 찍히기 시작하는 글은 VM 스레드가 찍기마다 본다(Rewind_HoldPresent).
    if (EV(kTyping) && !EV(kClickWait)) EV(kFinishNow) = 1;
    SetEvent(gWake);
    return true;
}

// ---------------------------------------------------------------- 붙잡아 두기(VM 스레드, 명령과 명령 사이)
void holdNow() {
    if (C.log) rlog("holding the sound subtitle until a click");
    if (!gHintShown) { gHintShown = true; Toast(L"다시 보는 소리 자막은 클릭 · Enter 로 넘깁니다", 3500); }
    engineClickWait();
    if (C.log) rlog("hold over");
}

}  // namespace

// ---------------------------------------------------------------- 약속(qol.h)
bool Rewind_Install() {
    C.on = Cfg("rewind", 1) != 0;
    if (!C.on) return false;
    C.log = Cfg("rewind_log", 0) != 0;
    C.verify = Cfg("rewind_verify", 0) != 0;
    C.test = Cfg("rewind_test", 0) != 0;
    C.depth = (size_t)std::max(8, std::min(2000, Cfg("rewind_depth", 300)));
    InitializeCriticalSection(&gCs);
    QueryPerformanceFrequency(&gQpf);
    gWake = CreateEventW(nullptr, FALSE, FALSE, nullptr);
    if (!gWake) { C.on = false; return false; }
    gHoldOk = memcmp((void*)pClickWaitCmd, kClickWaitCmdHead, sizeof(kClickWaitCmdHead)) == 0;
    if (C.test) gMsgTest = RegisterWindowMessageW(L"ForestRewindTest");
    return true;
}
bool Rewind_On() { return C.on; }

void Rewind_Fetch(uint16_t op, const uint8_t* cursor) {
    if (!C.on) return;
    DWORD tid = GetCurrentThreadId();
    gFetchTid = tid;
    gCurOp = op;
    if (tid != gHistTid && EV(kCheckpointOk) && !EW(kNested)) {
        // 새 게임·불러오기 뒤에는 VM 스레드가 새로 만들어진다 → 모아 둔 것은 옛 흐름의 것
        EnterCriticalSection(&gCs); clearLocked("VM thread changed"); gHistTid = tid; LeaveCriticalSection(&gCs);
    }
    // 타이틀 대본이 돌고 있다 = 판이 끝났다. 엔진이 타이틀로 가는 길은 둘이다: VM 을 끝내고 새로 만들거나(Alt+E, 이야기의 끝 = 명령 0x08),
    // 대본만 갈아탄다(명령 0x0c 1 — 같은 VM 스레드 그대로: 지도에서 연 다시보기가 끝난 뒤 등). 스레드가 바뀌었는지에 기대지 않고 여기서 버린다 —
    // 새로 시작한 첫 자리에서 옛 판의 대사로 되감기면 안 된다.
    if (curScript() == kTitleScript) {
        EnterCriticalSection(&gCs);
        const bool had = !gHist.empty() || !gAhead.empty();
        LeaveCriticalSection(&gCs);
        if (had) resetAll("back at the title");
    }
    if (InterlockedExchange(&gTextStale, 0)) {
        for (auto& t : gText) t.valid = false;
        gVoiceSince.valid = false; gPrevOp = 0; gCand.reset();
        gUnitOpen = false; gUnitHeld = false; gAfterVoiceWait = false; gHoldAfter = false; gSkipTimer = false; gUserCut = false;
    }
    if (gAfterVoiceWait) { gAfterVoiceWait = false; gUnitOpen = false; gUnitHeld = false; }   // 음성이 끝났다 → 그 소리 자막은 끝
    gPreMarkOk = isStopOp(op);
    if (gPreMarkOk) gPreMark = MarkRun();
    // 앞 명령이 글 넣기(0x20)였으면 엔진이 고정 버퍼에 남긴 글을 그 층 것으로 적어 둔다
    if (gPrevOp == 0x20 && gPrevLayer >= 0 && gPrevLayer <= kLayers) {
        const char* p = (const char*)kTextScratch;
        TextSet& t = gText[gPrevLayer];
        t.valid = true; t.arg = gPrevArg; t.text.assign(p, strnlen(p, 0x3ff));
    }
    gPrevOp = op;
    if (op == 0x20) {
        // 꼴: 층(V), x(V), y(V), 효과(V), 인자(V), 글 슬롯(I) — 엔진은 층이나 슬롯이 0 이면 아무것도 안 한다(0x41cd16)
        uint16_t layer = vres(*(const uint32_t*)(cursor + 2));
        if (layer && layer <= kLayers && *(const uint32_t*)(cursor + 22)) { gPrevLayer = layer; gPrevArg = vres(*(const uint32_t*)(cursor + 18)); }
        else gPrevOp = 0;
    } else if (op == 0x42) {
        // 음성 명령 직전의 상태를 떠 둔다(대사 없이 흐르는 소리 자막이면 이것이 그 걸음이 된다)
        gUnitOpen = false; gUnitHeld = false;
        if (!EW(kNested) && EV(kCheckpointOk) && tid == gHistTid) {
            EnterCriticalSection(&gCs);
            gCand = captureLocked(0x42, true);
            LeaveCriticalSection(&gCs);
        } else gCand.reset();
        // 따로 튼 음성(자막의 음성)은 대사를 넘겨도 울린다
        for (int i = 0; i < 4; ++i) gVoiceSince.a[i] = vres(*(const uint32_t*)(cursor + 2 + 4 * i));
        gVoiceSince.valid = gVoiceSince.a[0] != 0;
        InterlockedExchange(&gVoiceFree, 1);
    } else if (op == 0x45 || op == 0x0d) {
        const uint16_t next = opAfter(cursor, op == 0x45 ? 2 : 6);   // 0x45 는 인자 없음, 0x0d 는 V 하나
        if (gCand) {
            // 음성 끝 기다림이 오거나, 시간 기다림 바로 뒤가 숨김(0x24)·음성 끊기(0x43)·다음 음성(0x42)이면 = 대사 없이 흐르는 소리 자막
            const bool unit = op == 0x45 || next == 0x24 || next == 0x43 || next == 0x42;
            if (unit) {
                bool mine = false, reread = false;
                EnterCriticalSection(&gCs);
                if (tid == gHistTid) { mine = true; reread = pushLocked(std::move(gCand)); }
                gCand.reset();
                LeaveCriticalSection(&gCs);
                if (mine) {
                    gUnitOpen = true;
                    gUnitHeld = reread && gHoldOk;
                    gUnitAt = GetTickCount();
                    gVoiceSince.valid = false;               // 이 음성은 이 소리 자막의 것 — 뒤 대사에 붙이지 않는다
                    if (C.log && gRestoredAt.QuadPart) {
                        LARGE_INTEGER now; QueryPerformanceCounter(&now);
                        rlog("sound subtitle up again %.1f ms after the screen came back", ms(gRestoredAt, now));
                    }
                }
            }
        }
        gRestoredAt.QuadPart = 0;
        // 다시 보는 소리 자막: 이 기다림이 끝나면 붙잡아 둔다. 다만 바로 뒤가 멈추는 명령(대사 등)이면 그 명령이 스스로 기다리므로 그대로 둔다.
        gHoldAfter = gUnitOpen && gUnitHeld && !isStopOp(next);
        gSkipTimer = gHoldAfter && op == 0x0d;               // 쪽의 시간 기다림은 재지 않는다 — 클릭할 때까지 그 쪽을 둔다
        gUserCut = false;
        if (op == 0x45) { gVoiceSince.valid = false; InterlockedExchange(&gVoiceFree, 0); gAfterVoiceWait = true; }
    } else {
        if (op == 0x43) { gCand.reset(); gUnitOpen = false; gUnitHeld = false; }
        if (op == 0x43 || (op == 0x51 && (*(const uint32_t*)(cursor + 6) & 0xffff))) {
            // 음성 끊기·음성 있는 대사(같은 채널을 새로 씀)면 끝난 것으로 본다
            gVoiceSince.valid = false; InterlockedExchange(&gVoiceFree, 0);
        }
        if (op != 0x24) gRestoredAt.QuadPart = 0;
    }
}

void Rewind_Checkpoint() {
    if (!C.on) return;
    DWORD tid = GetCurrentThreadId();
    EnterCriticalSection(&gCs);
    if (tid != gFetchTid) { clearLocked("checkpoint off the VM thread"); LeaveCriticalSection(&gCs); return; }
    if (tid != gHistTid) { clearLocked("VM thread changed"); gHistTid = tid; }
    gCand.reset();                           // 음성 뒤에 대사·선택지가 왔다 → 그 음성은 이 자리에 딸린 것
    gUnitOpen = false; gUnitHeld = false;
    pushLocked(captureLocked((uint16_t)gCurOp, false));
    LeaveCriticalSection(&gCs);
}

void Rewind_SecondaryChanged() {
    if (!C.on) return;
    EnterCriticalSection(&gCs); gSec.reset(); LeaveCriticalSection(&gCs);
}

void Rewind_Reset(const char* why) { if (C.on) resetAll(why); }

HANDLE Rewind_WakeEvent() { return C.on ? gWake : nullptr; }

// VM 스레드, 입력 대기(대사의 클릭 대기·선택지·붙잡힌 소리 자막) 안: 요청이 있으면 클릭이 온 것처럼 돌아간다.
bool Rewind_WaitShouldReturn() {
    if (!C.on || !gPending || EW(kNested) || expired()) return false;
    if (EV(kClickWait)) { InterlockedExchange(&gCutStop, 1); return true; }
    if (EV(kChoice)) {
        // 선택지 대기: 엔진의 선택 콜백(0x4163b0)이 대기를 풀기 전에 하듯 깃발을 내리고, 선택지를 닫는 효과(약 0.24초, 0x41c040)는
        // 엔진의 「누르는 동안 건너뛰기」 길로 건너뛴다 — 되돌릴 때 그 깃발을 지운다.
        EV(kChoice) = 0; EV(kCtrlSkip) = 1;
        InterlockedExchange(&gCutStop, 1);
        return true;
    }
    return false;
}

// VM 스레드가 지금 들어가는 기다림이 「클릭으로도 끊기는 기다림」인가(기다림 갈고리가 묻는다).
//  · 음성 끝(명령 0x45 의 0x41e704, 자동 진행의 0x41c71c)·효과음 끝(명령 0x44 의 0x41e6bd): 그 채널의 끝 이벤트를 기다린다.
//    엔진의 클릭(0x415970)은 그 채널을 끊어 기다림을 끝낸다. 갈고리가 먼저 돌아가면 엔진이 뒤이어 채널을 끊는다(0x41e713·0x41e6cc).
//  · 시간(명령 0x0d, 영문 패치 0x458680): 잠자는 스레드의 핸들([0x48fdf4])을 기다린다. 영문 패치의 클릭·Enter(0x4586c0·0x458700)는 그 스레드를 끝낸다.
//    갈고리가 먼저 돌아가면 엔진이 핸들 칸을 비우고 끝난다(스레드는 제 시간에 스스로 끝난다).
bool Rewind_CuttableWait(HANDLE h) {
    if (!C.on || !h || GetCurrentThreadId() != gFetchTid || EW(kNested)) return false;
    if (h == chanEvent(1) || h == chanEvent(0)) return true;
    return gCurOp == 0x0d && h == *(HANDLE volatile*)kTimedThread;
}
// 그 기다림 안: true 면 기다리던 일이 끝난 것처럼 돌아간다(되감기 요청, 또는 붙잡아 둘 쪽의 시간 기다림).
bool Rewind_CutNow() {
    if (!C.on || EW(kNested)) return false;
    if (gSkipTimer && gCurOp == 0x0d) { gSkipTimer = false; return true; }
    return gPending && !expired();
}
// 그 기다림이 제 일로 끝났다(요청으로 끊은 것이 아니다). 붙잡아 둘 음성 끝 기다림이면: 음성이 스스로 끝났는가, 사용자가 클릭으로 끊었는가.
// 클릭이면 엔진이 채널을 끊고 곧바로 [0x4663f4] 를 0 으로 만든다(0x4159e9). 스스로 끝났으면 우리가 돌아갈 때까지 1 이다.
void Rewind_WaitEnded(HANDLE h) {
    if (!C.on || !gHoldAfter || gCurOp != 0x45 || h != chanEvent(1)) return;
    for (int i = 0; i < 8 && EV(kVoiceWait); ++i) Sleep(2);
    gUserCut = EV(kVoiceWait) == 0;
}

bool Rewind_AtFetch() {
    if (!C.on || EW(kNested)) return false;
    if (gHoldAfter) {
        // 다시 보는 소리 자막의 기다림이 끝났다 → 클릭할 때까지 그대로 둔다(되감기 요청이 이미 와 있거나 사용자가 클릭으로 끊었으면 넘어간다)
        gHoldAfter = false;
        if (!gUserCut && !gPending) holdNow();
    }
    if (!gPending) return false;
    if (EV(kTyping)) return false;             // 아직 글을 끝내는 중(다음 클릭 대기에서)
    LONG steps = InterlockedExchange(&gPending, 0);
    const LARGE_INTEGER reqAt = gReqAt;        // 되돌리는 동안 다음 요청이 들어와 덮어쓸 수 있다
    const bool atStop = InterlockedExchange(&gCutStop, 0) != 0;
    if (steps <= 0) { InterlockedExchange(&gHold, 0); return false; }
    if (expired()) { InterlockedExchange(&gHold, 0); if (C.log) rlog("request dropped: the game was busy for %lu ms", (unsigned long)(GetTickCount() - gReqTick)); return false; }
    // 어디서 눌렀나 → 몇 걸음
    int back = (int)steps; const char* where = "at a line or a choice";
    if (!atStop) {
        if (gUnitOpen) {
            if (GetTickCount() - gUnitAt >= kUnitRestartMs) { back = (int)steps - 1; where = "during a sound subtitle (restart it)"; }
            else where = "just after a sound subtitle started (go before it)";
        } else { back = (int)steps - 1; where = "between stops (back to the one just left)"; }
    }
    EnterCriticalSection(&gCs);
    if (gHist.empty()) { LeaveCriticalSection(&gCs); InterlockedExchange(&gHold, 0); return false; }
    int idx = (int)gHist.size() - 1 - back;
    if (idx < 0) idx = 0;
    // 떼어 내는 걸음들의 자리 = 「다시 보는 구간」(앞서 되감아 아직 다 지나지 않은 구간이 있으면 그 앞에 잇는다)
    std::vector<uint64_t> ahead;
    for (size_t i = (size_t)idx; i < gHist.size(); ++i) ahead.push_back(keyOf(*gHist[i]));
    ahead.insert(ahead.end(), gAhead.begin() + (std::ptrdiff_t)gAheadPos, gAhead.end());
    gAhead.swap(ahead); gAheadPos = 0;
    std::unique_ptr<Snap> target = std::move(gHist[(size_t)idx]);
    gHist.resize((size_t)idx);                 // 고른 자리부터 뒤는 버린다(그 자리의 명령이 다시 실행되며 새로 뜬다)
    InterlockedExchange(&gCount, (LONG)gHist.size());
    gSec = target->sec;
    LeaveCriticalSection(&gCs);
    if (C.log) rlog("pressed %s", where);
    restore(*target, back, idx, reqAt);
    return true;
}

// 게임 창으로 가는 찍기마다 불린다(글이 찍히는 동안·화면 효과가 도는 동안에도 한 장마다).
bool Rewind_HoldPresent() {
    if (!C.on) return false;
    // 요청이 기다리는 동안 글이 찍히거나 화면 효과가 돌면 엔진의 「한꺼번에 끝내기」(엔진의 클릭 0x415a35 가 하는 일) → 곧 클릭 대기나 다음 명령에 닿는다
    if (gPending && !expired() && EV(kTyping) && !EV(kClickWait) && !EW(kNested)) EV(kFinishNow) = 1;
    if (!gHold) return false;
    if (GetTickCount() - gHoldAt > kReqLifeMs) { InterlockedExchange(&gHold, 0); return false; }   // 요청이 쓰이지 못했다 → 화면을 붙잡아 두지 않는다
    InterlockedIncrement(&gHeld);
    return true;
}

bool Rewind_WndProc(HWND h, UINT m, WPARAM w, LPARAM l, LRESULT& r) {
    if (!C.on) return false;
    if (gMsgTest && m == gMsgTest) { r = request((int)l > 0 ? (int)l : 1, false, false) ? 1 : 0; return true; }   // 시험: 여러 걸음을 한 번에
    if (m == WM_KEYDOWN && w == VK_BACK) {
        const bool repeat = (l & 0x40000000) != 0;
        const DWORD now = GetTickCount();
        if (!repeat || now - gLastAccept >= kRepeatMs) { if (request(1, true, repeat)) gLastAccept = now; }
        r = 0; return true;
    }
    return false;
}

}}  // namespace forest::qol
