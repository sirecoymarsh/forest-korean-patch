// qol_rewind.cpp — 「이전 대사로 되감기」 가능성 조사용 시험 모듈 (2026-11-25).
// 놀이 사본에 넣는 판이 아니다. 지연·복원 충실도를 재려고 만든 것이고, 화면·문구·설정 자리는 다듬지 않았다.
//
// 엔진 근거(Forest.exe f618b6… / 지도 로더판 eef917…, 코드 구역 같음)
//   · 엔진은 멈추는 자리마다(대사 0x51·0x52, 선택지 0x0e, 단추 고르기 0x49, 글 없는 클릭 대기 0x0a·0x0b)
//     「지금 상태」를 한 벌 떠 둔다(0x418a40): VM 문맥 0x46646c~ 11,324바이트 + 변수 V[0..6999] 14,000바이트.
//     세이브 파일(50,668바이트)은 이 한 벌과 「직전 선택지」 한 벌(0x46bce4~)을 그대로 쓴 것이다(0x418a80·0x418bb0).
//   · 문맥에는 대본 번호·자리(깊이별), 층 50개의 그림·자리·보임, 층 순서, 배경음·되풀이 효과음 번호, 대화창 상태가 들어 있다.
//   · 엔진은 문맥만으로 화면·소리를 다시 세운다: 대본 읽기 0x41a0c0 → 자리 0x4130e0 → 0x41e8b0(소리 + 층 50개 + 대화창)
//     → 0x43d350(전체 합성·찍기). 불러오기(0x415a40), 건너뛰기가 멈출 때(0x41ca28), 화면 단추가 부른 하위 대본에서 돌아올 때(0x41e730)가
//     다 이 길이다(설정 화면은 아니다 — 게임 화면 위에 덮였다 걷힐 뿐).
//   · 그래서 되감기 = 멈춘 자리마다 그 한 벌(+ 대화 기록 100줄)을 DLL 이 모아 두었다가, 고른 한 벌을 문맥에 넣고 같은 길을 부르는 것.
//
// 흐름
//   창 스레드: Backspace(또는 시험 메시지) → 큰 조건만 확인(지도·메뉴·하위 대본) → 요청을 남기고(gPending) VM 을 깨운다.
//             글이 찍히는 중이거나 화면 효과가 도는 중이면 엔진의 「한꺼번에 끝내기」([0x4663d4]=1, 엔진의 클릭이 하는 일).
//   VM 스레드: 기다리던 것(입력·음성 끝·시간·효과음 끝 — 모두 클릭으로도 끊기는 기다림)이 요청을 보고 바로 돌아옴
//             → 엔진이 그 명령의 뒷정리를 스스로 함 → 다음 명령을 꺼내기 직전(Rewind_AtFetch)에 「어디서 눌렀나」를 보고 돌아갈 자리를 정해
//             문맥을 바꾸고 화면을 다시 세움 → 그 자리의 명령이 다시 실행됨(글·음성·자막).
//               · 대사·선택지에 멈춰 있었다        → 그 앞 자리
//               · 소리 자막이 흐르는 중이었다      → 한참(0.8초) 흐른 뒤면 그 자막을 처음부터, 막 시작했으면 그 앞 자리
//               · 자리와 자리 사이(막 넘긴 뒤)였다  → 방금 떠난 자리
//   요청이 0.6초 안에 쓰이지 못하면(엔진이 끊을 수 없는 일을 하는 중) 버린다 — 한참 뒤에 느닷없이 되감기지 않게.
//   그 사이 게임 창으로 가는 찍기는 건너뛴다(빈 대화창이 한 번 비치지 않게). 다시 세운 뒤 전체 찍기 한 번.
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

constexpr uintptr_t kCtx = 0x46646c, kPriCtx = 0x4690a8, kSecCtx = 0x46bce4;
constexpr size_t kCtxSize = 0x2c3c, kVarSize = 14000;
constexpr uintptr_t kVars = 0x46643c, kPriVars = 0x466440, kSecVars = 0x466444;
constexpr uintptr_t kEngine = 0x466398, kScript = 0x46639c, kMsgWin = 0x46630c;
constexpr size_t kLogOff = 0xac, kLogSize = 0xaf0 * 4, kLogViewIdx = 0x2c6c, kLogViewing = 0x2c70;
constexpr uintptr_t kNested = 0x466432;                       // u16: 화면 단추가 부른 하위 대본 안이면 0 아님
constexpr uintptr_t kDepth = 0x4664bc, kDepthScripts = 0x46647e, kDepthPcs = 0x466494;
constexpr uintptr_t kClickWait = 0x4663e8, kTyping = 0x4663e0, kFinishNow = 0x4663d4, kChoice = 0x4663cc, kSelect = 0x466418;
constexpr uintptr_t kSettings = 0x46640c, kSaveScr = 0x466410, kLoadScr = 0x466414;
constexpr uintptr_t kAuto = 0x466408, kCtrlKey = 0x4663f8, kCtrlSkip = 0x466400, kTabReq = 0x4663fc, kTabSkip = 0x466404;
constexpr uintptr_t kDeferred = 0x4663d0;                     // 화면 바꿈 묶음(명령 0x1a … 0x1c) 안이면 1 — 층 명령이 화면에 바로 내지 않는다. 문맥 밖의 깃발

// 엔진 함수
constexpr uintptr_t fLoadScript = 0x41a0c0;   // int __cdecl(u16 대본): 지금 깊이의 대본을 읽는다
constexpr uintptr_t fSeek = 0x4130e0;         // int __thiscall(스크립트 객체, u32 pc)
constexpr uintptr_t fRebuild = 0x41e8b0;      // void __cdecl(): 문맥대로 소리·층·대화창을 다시 세운다
constexpr uintptr_t fFullPaint = 0x43d350;    // void __thiscall(엔진 객체): 전체 합성·찍기
constexpr uintptr_t fLock = 0x43cf60, fUnlock = 0x43cf70;   // void __thiscall(엔진 객체): 화면 잠금
constexpr uintptr_t fVoiceStop = 0x419000;    // void __cdecl(int): 음성 채널 끊기
constexpr uintptr_t fBgmStop = 0x43f750;      // void __thiscall(엔진 객체, int): 배경음 끊기
constexpr uintptr_t fChanStop = 0x43f630;     // void __thiscall(엔진 객체, int 채널, int): 채널 끊기
constexpr uintptr_t fBarAutoOff = 0x410c20;   // void __thiscall(대화창): 자동 진행 표시 끄고 아이콘 줄 되살림
constexpr uintptr_t fBgmPlay = 0x41e5c0;      // void __cdecl(u16 곡, u16): 배경음(같은 곡이면 엔진이 그대로 둔다 0x43f6cd)
constexpr uintptr_t fSeOpen = 0x41e420;       // void __cdecl(u16 번호): 효과음 채널을 끊고 그 파일을 연다([0x466472] 을 0 으로 만든다)
constexpr uintptr_t fSePlay = 0x41e490;       // void __cdecl(u16 되풀이(999 = 계속), u16, u16 음량)
constexpr uintptr_t fLayers = 0x41e920;       // void __cdecl(): 층 50개·글 객체·대화창·덮개를 문맥대로(화면 잠금 안에서 부른다)
constexpr uintptr_t fUpdateDirty = 0x43d240;  // void __thiscall(엔진 객체)
constexpr uintptr_t kLayerTable = 0x466238;   // 층 객체 50개
constexpr size_t kLayerRec = 0x288, kRecSize = 0xa4;   // 층 객체 → 문맥 안 자기 기록(0x4664e0 + i*0xa4)
constexpr int kLayers = 50;
constexpr uintptr_t fBarShow = 0x411280;      // void __thiscall(대화창, int): 아이콘 줄을 상태대로(대화창이 보이고 줄이 켜져 있을 때만 보임)

bool gOn = false, gLog = false, gVerify = false, gFast = false, gBarFix = true;
volatile LONG gVoiceFree = 0;              // 대사에 딸리지 않은 음성(명령 0x42)이 아직 울릴 수 있다
size_t gCap = 200;
UINT gMsgProbe = 0;
HANDLE gWake = nullptr;
CRITICAL_SECTION gCs;
LARGE_INTEGER gQpf;

// 문맥에 없어서 따로 적어 두는 것 둘.
//  · 층에 넣은 글(노란 자막): 원작은 글을 층 기록(+0x3c)에 넣어 두었는데(원판 0x4038bc), 영문 패치가 그 복사를 고정 버퍼 0x48fe00 으로
//    돌려놓았다(긴 자막이 81바이트 칸을 넘어서). 그래서 한국어판의 다시 세우기(불러오기·건너뛰기 멈춤)는 자막을 되살리지 못한다(불러오기는 11-25 화면으로 확인).
//    → 글 넣기 명령(0x20)이 실행된 직후에 0x48fe00 의 글을 층마다 적어 두고, 되돌린 뒤 엔진의 글 넣기(0x403870)로 다시 넣는다.
//  · 따로 튼 음성(0x42, 자막의 음성): 그 뒤 처음 멈춘 자리에 붙여 두었다가, 그 자리로 되돌아가면 다시 튼다.
constexpr uintptr_t kTextScratch = 0x48fe00;
constexpr uintptr_t fLayerText = 0x403870;    // void __thiscall(층, 글, 효과, x, y, 인자, 건너뛰는중): 명령 0x20 이 부르는 글 넣기
constexpr uintptr_t fVoicePlay = 0x41e550;    // void __cdecl(번호, 되풀이, ?, 음량): 명령 0x42
constexpr size_t kLayerRecs = 0x74;           // 문맥 안 층 기록 시작(0x4664e0)
struct TextSet { bool valid = false; int arg = 0; std::string text; };
struct FreeVoice { bool valid = false; uint16_t a[4] = {}; };
TextSet gText[kLayers + 1];                // VM 스레드만
FreeVoice gVoiceSince;                     // 지난 멈춤 뒤에 따로 튼 음성(VM 스레드만)
int gPrevOp = 0, gPrevLayer = 0, gPrevArg = 0;
bool gSubs = true;
volatile LONG gTextStale = 0;              // 불러오기·새 게임: 적어 둔 글은 버린다(VM 스레드가 다음 명령에서 비움)
// 대사 없이 흐르는 소리 자막도 한 걸음으로 친다(rewind_units=1). 대본의 꼴(음성 명령 0x42 뒤, 926곳을 셈):
//   ① 음성 → 자막 → 음성 끝 기다림(0x45) → 숨김                      252곳  대사 없이 흐른다
//   ② 음성 → 자막 → 시간 기다림(0x0d) → 숨김 → 다음 쪽 자막 → … → 대사   약 60곳  자막이 쪽을 넘기며 흐른 뒤 대사가 온다
//   ③ 음성 → 자막 → (1초 기다림) → 대사                               그 밖   대사에 딸린 자막 — 이것은 그 대사 자리에 자막·음성을 붙인다(위)
// ①②는 엔진이 상태를 뜨지 않는 자리다. 음성 명령을 꺼낼 때(= 그 명령 직전 상태) 한 벌을 떠 두었다가(gCand),
// 그 음성이 ①(0x45) 또는 ②(시간 기다림 바로 뒤가 숨김 0x24·음성 끊기 0x43·다음 음성 0x42)로 이어지면 줄에 넣는다.
// 그 자리로 되돌리면 VM 이 음성 명령부터 다시 실행한다 — 음성·자막·쪽 넘김이 엔진 자신의 명령으로 다시 흐르고, 끝나면 스스로 다음으로 넘어간다.
bool gUnits = true;
int gUnitRestartMs = 800;                  // 소리 자막이 흐르는 중의 되감기: 이만큼 흐른 뒤면 「그 자막을 처음부터」, 그 전이면 「그 앞 자리로」
constexpr uintptr_t kCheckpointOk = 0x4664d0, kVoiceWait = 0x4663f4, kSeWait = 0x4663f0, kTimedThread = 0x48fdf4;
volatile DWORD gUnitAt = 0;                // 지금 흐르는 소리 자막이 시작된 때(GetTickCount)
bool gUnitOpen = false, gAfterVoiceWait = false;   // VM 스레드만: 줄에 넣은 소리 자막이 아직 흐르는 중 / 앞 명령이 음성 끝 기다림이었다
LARGE_INTEGER gRestoredAt = {};            // 마지막 되돌리기가 화면을 낸 때(소리 자막이 다시 뜨기까지를 재려고)

struct Sec { uint8_t ctx[kCtxSize]; uint8_t vars[kVarSize]; };
struct Snap {
    uint8_t ctx[kCtxSize]; uint8_t vars[kVarSize]; uint8_t log[kLogSize];
    std::shared_ptr<Sec> sec;
    std::shared_ptr<Sec> pri;                     // 소리 자막 자리만: 그때 엔진이 들고 있던 「지금 상태」 한 벌(= 그 앞 대사의 것)
    int sid = 0, depth = 0; uint32_t pc = 0; uint16_t op = 0;
    int deferred = 0;                             // 그때의 [0x4663d0]
    std::vector<std::pair<int, TextSet>> texts;   // 그때 보이던 글 층
    FreeVoice voice;
};
std::unique_ptr<Snap> gCand;               // 음성 명령 직전에 떠 둔 한 벌(VM 스레드만) — 아래 「대사 없이 흐르는 소리 자막」
// 대본 인자(V꼴): 위 16비트 = 변수표를 거치는 횟수, 아래 16비트 = 값(엔진 0x41b8b0 과 같다)
uint16_t vres(uint32_t v) {
    int ind = (int16_t)(v >> 16); uint16_t val = (uint16_t)v;
    const uint16_t* vars = *(const uint16_t**)kVars;
    while (ind-- > 0 && vars) val = vars[(int16_t)val];
    return val;
}
std::deque<std::unique_ptr<Snap>> gHist;   // 뒤 = 지금 멈춘 자리
std::shared_ptr<Sec> gSec;                 // 지금의 「직전 선택지」 한 벌(바뀔 때까지 함께 씀)
volatile LONG gCount = 0;                  // gHist 크기(창 스레드가 읽음)
volatile LONG gPending = 0;                // 되돌아갈 걸음 수
volatile LONG gCutStop = 0;                // 요청이 대사·선택지의 입력 대기를 끊었다(= 그 자리에 멈춰 있었다)
volatile DWORD gReqTick = 0;               // 요청한 때(GetTickCount) — 오래 안 쓰이면 버린다
constexpr DWORD kReqLifeMs = 600;
volatile LONG gChoiceGo = 0;               // 선택지 대기를 풀어도 된다
volatile LONG gHold = 0;                   // 게임 창 찍기를 잠깐 건너뜀
volatile LONG gHeld = 0;                   // 그동안 건너뛴 찍기 수(기록용)
DWORD gHoldAt = 0;
DWORD gFetchTid = 0, gHistTid = 0;
volatile LONG gCurOp = 0;
LARGE_INTEGER gReqAt = {};
volatile LONG gSeq = 0;                    // 되감기 횟수

// 검증(rewind_verify=1): 같은 자리를 다시 지날 때 처음 뜬 한 벌과 바이트가 같은지
struct Seen { std::unique_ptr<uint8_t[]> bytes; };
std::unordered_map<uint64_t, Seen> gSeen;
uint64_t keyOf(int depth, int sid, uint32_t pc) { return ((uint64_t)(depth & 0xff) << 56) | ((uint64_t)(sid & 0xffff) << 32) | pc; }

void rlog(const char* fmt, ...) {
    char b[512]; va_list ap; va_start(ap, fmt); _vsnprintf_s(b, sizeof(b), _TRUNCATE, fmt, ap); va_end(ap);
    Log(std::string("rewind: ") + b);
}
double ms(const LARGE_INTEGER& a, const LARGE_INTEGER& b) { return (b.QuadPart - a.QuadPart) * 1000.0 / gQpf.QuadPart; }
void* engine() { return *(void* volatile*)kEngine; }
uint8_t* msgWin() { return (uint8_t*)*(void* volatile*)kMsgWin; }
bool screensOpen() { return EV(kSettings) || EV(kSaveScr) || EV(kLoadScr); }

void clearLocked(const char* why) {
    if (!gHist.empty() && gLog) rlog("history cleared (%s), had %d", why, (int)gHist.size());
    gHist.clear(); gSec.reset(); gSeen.clear();
    InterlockedExchange(&gCount, 0);
    InterlockedExchange(&gTextStale, 1);
}

int firstDiff(const uint8_t* a, const uint8_t* b, size_t n) { for (size_t i = 0; i < n; ++i) if (a[i] != b[i]) return (int)i; return -1; }
int countDiff(const uint8_t* a, const uint8_t* b, size_t n) { int c = 0; for (size_t i = 0; i < n; ++i) c += a[i] != b[i]; return c; }

void verifyLocked(const Snap& s) {
    uint64_t k = keyOf(s.depth, s.sid, s.pc);
    auto it = gSeen.find(k);
    const size_t total = kCtxSize + kVarSize + kLogSize;
    if (it == gSeen.end()) {
        if (gSeen.size() > 600) return;
        Seen e; e.bytes.reset(new uint8_t[total]);
        memcpy(e.bytes.get(), s.ctx, kCtxSize); memcpy(e.bytes.get() + kCtxSize, s.vars, kVarSize); memcpy(e.bytes.get() + kCtxSize + kVarSize, s.log, kLogSize);
        gSeen.emplace(k, std::move(e));
        return;
    }
    const uint8_t* o = it->second.bytes.get();
    int dc = countDiff(o, s.ctx, kCtxSize), dv = countDiff(o + kCtxSize, s.vars, kVarSize), dl = countDiff(o + kCtxSize + kVarSize, s.log, kLogSize);
    if (!dc && !dv && !dl) rlog("verify %04d:%u SAME (context, variables, text history)", s.sid, s.pc);
    else rlog("verify %04d:%u DIFF context %d bytes (first +0x%x), variables %d (first +%d), text history %d (first +0x%x)", s.sid, s.pc,
              dc, firstDiff(o, s.ctx, kCtxSize), dv, firstDiff(o + kCtxSize, s.vars, kVarSize), dl, firstDiff(o + kCtxSize + kVarSize, s.log, kLogSize));
}

// ---------------------------------------------------------------- 되돌리기(VM 스레드, 명령을 꺼내기 직전)
// 두 가지 길을 잰다.
//   느린 길(rewind_fast=0): 엔진의 불러오기와 같은 함수(0x41e8b0)를 통째로 부른다 — 층 50개를 모두 다시 읽고, 소리 명령을 무조건 보낸다.
//   빠른 길(rewind_fast=1): 같은 엔진 함수들을 쓰되 「달라진 것만」 —
//     · 층: 지금 문맥의 기록과 돌아갈 기록이 바이트까지 같은 층은 기록 포인터(+0x288)를 잠깐 비워 둔다.
//       엔진의 층 다시 세우기(0x403d10)는 기록 포인터가 비면 그 층을 건드리지 않고 돌아간다(0x403d40).
//     · 소리: 배경음은 엔진이 같은 곡이면 그대로 둔다. 되풀이 효과음·음성은 상태가 다를 때만 명령을 보낸다.
void restore(const Snap& s, int steps, int left) {
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
    // 지금 상태와 견주기(문맥을 덮기 전에)
    const uint16_t liveSe = EW(kCtx + 4), liveLoop = EW(kCtx + 6);
    const uint16_t wantBgm = *(const uint16_t*)(s.ctx + 0), wantSe = *(const uint16_t*)(s.ctx + 4), wantLoop = *(const uint16_t*)(s.ctx + 6), wantVol = *(const uint16_t*)(s.ctx + 8);
    uint8_t* mgr = eng ? *(uint8_t**)((uint8_t*)eng + 0x1a8) : nullptr;
    const int liveTrack = mgr ? *(int*)(mgr + 0x10) : 0;
    void* skipped[kLayers] = {}; int nSame = 0;
    if (gFast) {
        for (int i = 0; i < kLayers; ++i) {
            uint8_t* lay = *(uint8_t**)(kLayerTable + i * 4);
            if (!lay) continue;
            uint8_t* rec = *(uint8_t**)(lay + kLayerRec);
            if (!rec || rec < (uint8_t*)kCtx || rec + kRecSize > (uint8_t*)kCtx + kCtxSize) continue;
            const uint8_t* want = s.ctx + (rec - (uint8_t*)kCtx);
            if (*(const uint16_t*)(want + 0xa) == 2 || *(const uint16_t*)(rec + 0xa) == 2) continue;   // 글 층은 기록이 같아도 글이 다를 수 있다
            if (memcmp(rec, want, kRecSize) == 0) { skipped[i] = rec; ++nSame; }
        }
    }
    const char* snd = "";
    double voiceMs = 0, soundMs = 0;
    if (!gFast) {
        // 느린 길: 소리 명령을 무조건, 화면보다 먼저(엔진의 0x41e8b0 이 그 순서다)
        QueryPerformanceCounter(&tv);
        ((void(__cdecl*)(int))fVoiceStop)(0);
        QueryPerformanceCounter(&ts); voiceMs = ms(tv, ts);
    }
    // 문맥·변수·직전 선택지·대화 기록
    QueryPerformanceCounter(&tv);
    ((void(__thiscall*)(void*))fLock)(eng);
    memcpy((void*)kCtx, s.ctx, kCtxSize);
    memcpy(*(void**)kVars, s.vars, kVarSize);
    // 엔진의 「지금 상태」 한 벌(저장하면 파일에 들어가는 것): 대사·선택지 자리는 그 자리 자신,
    // 소리 자막 자리는 처음 흐를 때 그랬듯 그 앞 대사의 것(엔진은 소리 자막에서 상태를 뜨지 않는다 → 그 사이에 저장하면 앞 대사가 저장된다)
    memcpy((void*)kPriCtx, s.pri ? s.pri->ctx : s.ctx, kCtxSize);
    memcpy(*(void**)kPriVars, s.pri ? s.pri->vars : s.vars, kVarSize);
    if (s.sec) { memcpy((void*)kSecCtx, s.sec->ctx, kCtxSize); memcpy(*(void**)kSecVars, s.sec->vars, kVarSize); }
    if (uint8_t* w = msgWin()) { memcpy(w + kLogOff, s.log, kLogSize); *(int*)(w + kLogViewIdx) = 100; }
    ((void(__thiscall*)(void*))fUnlock)(eng);
    QueryPerformanceCounter(&tc);
    const double copyMs = ms(tv, tc);
    if (!gFast) {
        // 돌아간 자리에 배경음·되풀이 효과음이 없으면 끊는다(엔진의 다시 세우기는 「있는 것」만 다시 튼다)
        if (wantBgm == 0) ((void(__thiscall*)(void*, int))fBgmStop)(eng, 0);
        if (wantSe == 0 || wantLoop == 0) ((void(__thiscall*)(void*, int, int))fChanStop)(eng, 0, 0);
        QueryPerformanceCounter(&ts); soundMs = ms(tc, ts); tc = ts;
    }
    // 대본·자리
    int ok = ((int(__cdecl*)(unsigned))fLoadScript)((unsigned)(uint16_t)s.sid);
    if (ok) ((int(__thiscall*)(void*, uint32_t))fSeek)(*(void**)kScript, s.pc);
    QueryPerformanceCounter(&tsc);
    // 화면 다시 세우기
    if (gFast) {
        ((void(__thiscall*)(void*))fLock)(eng);
        for (int i = 0; i < kLayers; ++i) if (skipped[i]) *(void**)(*(uint8_t**)(kLayerTable + i * 4) + kLayerRec) = nullptr;
        ((void(__cdecl*)())fLayers)();
        for (int i = 0; i < kLayers; ++i) if (skipped[i]) *(void**)(*(uint8_t**)(kLayerTable + i * 4) + kLayerRec) = skipped[i];
        ((void(__thiscall*)(void*))fUnlock)(eng);
    } else {
        ((void(__cdecl*)())fRebuild)();
    }
    // 아이콘 줄: 엔진의 다시 세우기(0x410510)는 「보여야 하면 보이게」만 한다. 불러오기는 화면을 새로 만들어 숨긴 채 시작하지만
    // 여기서는 화면이 살아 있으므로, 숨겨져 있어야 하는 자리(대화창이 아직 안 나온 곳)로 돌아가면 줄이 남는다 → 엔진 함수로 다시 맞춘다.
    if (gBarFix && msgWin()) ((void(__thiscall*)(void*, int))fBarShow)(msgWin(), 1);
    QueryPerformanceCounter(&tl);
    // 글 층(노란 자막) 다시 넣기
    int nText = 0;
    if (gSubs) {
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
    }
    QueryPerformanceCounter(&tx);
    InterlockedExchange(&gHold, 0);
    ((void(__thiscall*)(void*))fFullPaint)(eng);
    QueryPerformanceCounter(&tp);            // ← 여기까지가 「화면이 바뀌는 데 걸린 시간」
    gRestoredAt = tp;
    if (gFast) {
        // 빠른 길: 소리는 화면을 낸 뒤에, 상태가 다를 때만.
        // 음성: 대사에 딸린 음성은 엔진이 그 대사를 넘길 때 스스로 끊었다(0x41cb65). 따로 튼 음성(0x42)만 끊는다.
        if (InterlockedExchange(&gVoiceFree, 0)) ((void(__cdecl*)(int))fVoiceStop)(0);
        QueryPerformanceCounter(&tv); voiceMs = ms(tp, tv);
        if (wantBgm) ((void(__cdecl*)(unsigned, unsigned))fBgmPlay)(wantBgm, 1);   // 같은 곡이면 엔진이 그대로 둔다
        else if (liveTrack) ((void(__thiscall*)(void*, int))fBgmStop)(eng, 1);
        bool want = wantSe && wantLoop, have = liveSe && liveLoop;
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
    }
    // 그 자리의 자막 음성 다시 틀기
    if (gSubs && s.voice.valid) {
        ((void(__cdecl*)(unsigned, unsigned, unsigned, unsigned))fVoicePlay)(s.voice.a[0], s.voice.a[1], s.voice.a[2], s.voice.a[3]);
        InterlockedExchange(&gVoiceFree, 1);
    }
    gVoiceSince = s.voice;      // 이 대사가 다시 실행되며 새로 뜨는 한 벌에 다시 붙는다
    gPrevOp = 0;
    gCand.reset();              // 되돌리기 전에 떠 둔 것은 버린다
    gUnitOpen = false; gAfterVoiceWait = false;
    QueryPerformanceCounter(&ts);
    if (gFast) soundMs = ms(tv, ts);
    LONG seq = InterlockedIncrement(&gSeq);
    int track2 = mgr ? *(int*)(mgr + 0x10) : 0;
    LONG held = InterlockedExchange(&gHeld, 0);
    rlog("#%ld back %d to %04d:%u op 0x%02x depth %d%s | key-to-start %.1f ms, voice %.2f, copy %.3f, sound %.2f, script %.2f, rebuild %.2f, paint %.2f, total %.2f ms | history left %d | %s layers kept %d/50, bgm %d>%d%s%s%s texts %d held %ld visual %.2f subs %.2f",
         seq, steps, s.sid, s.pc, s.op, s.depth, ok ? "" : " (SCRIPT LOAD FAILED)",
         gReqAt.QuadPart ? ms(gReqAt, t0) : -1.0, voiceMs, copyMs, soundMs, ms(tc, tsc), ms(tsc, tl), ms(tx, tp), ms(t0, ts), left,
         gFast ? "fast" : "full", nSame, liveTrack, track2, snd, nText ? " subtitle-restored" : "", (gSubs && s.voice.valid) ? " subtitle-voice-replayed" : "", nText, held,
         ms(t0, tp), ms(tl, tx));
}

const char* refuseWhy() {
    if (ChartIsOpen()) return "map open";
    if (screensOpen()) return "menu open";
    if (EV(kSelect)) return "button menu";
    if (EW(kNested)) return "inside a sub script";
    if (gCount < 1) return "no earlier stop";
    // 대사·선택지에 멈춰 있을 때(글이 찍히는 중 포함)는 그 앞 자리가 있어야 한다 — 없으면 아무것도 하지 않는다(입력 대기를 끊지 않는다)
    if (gCount < 2 && (EV(kClickWait) || EV(kChoice) || (EV(kTyping) && (gCurOp == 0x51 || gCurOp == 0x52)))) return "no earlier stop";
    uint8_t* w = msgWin();
    if (w && *(int*)(w + kLogViewing)) return "viewing earlier text";
    return nullptr;
}

bool expired() { return GetTickCount() - gReqTick > kReqLifeMs; }

// 창 스레드: 요청을 남긴다. 어디로 돌아갈지는 VM 스레드가 정한다(Rewind_AtFetch).
bool request(int steps, const char* from) {
    if (gPending) {
        if (!expired()) return false;
        InterlockedExchange(&gPending, 0);         // 쓰이지 못한 옛 요청은 버린다
    }
    if (const char* why = refuseWhy()) { rlog("%s refused: %s", from, why); return false; }
    QueryPerformanceCounter(&gReqAt);
    gReqTick = GetTickCount();
    gHoldAt = gReqTick; InterlockedExchange(&gHold, 1);
    if (EV(kChoice)) {
        EV(kChoice) = 0;                           // 엔진의 선택 콜백(0x4163b0)이 대기를 풀기 전에 하는 일
        if (gFast) EV(kCtrlSkip) = 1;              // 선택지를 닫는 효과(약 0.24초, 0x41c040)를 엔진의 「누르는 동안 건너뛰기」 길로 건너뛴다 — 되돌릴 때 깃발을 지운다
        InterlockedExchange(&gChoiceGo, 1);
    } else if (EV(kTyping) && !EV(kClickWait)) {
        EV(kFinishNow) = 1;                        // 엔진의 클릭(0x415a35)과 같다: 찍히는 글·도는 화면 효과를 한꺼번에 끝냄
    }
    InterlockedExchange(&gPending, steps);
    SetEvent(gWake);
    return true;
}

}  // namespace

// ---------------------------------------------------------------- 약속
bool Rewind_Install() {
    gOn = Cfg("rewind", 0) != 0;               // 시험 모듈: 기본 꺼짐
    if (!gOn) return false;
    gLog = Cfg("rewind_log", 0) != 0;
    gVerify = Cfg("rewind_verify", 0) != 0;
    gFast = Cfg("rewind_fast", 0) != 0;
    gBarFix = Cfg("rewind_barfix", 1) != 0;
    gSubs = Cfg("rewind_subs", 1) != 0;
    gUnits = Cfg("rewind_units", 1) != 0;
    gUnitRestartMs = Cfg("rewind_unit_restart_ms", 800);
    gCap = (size_t)std::max(8, std::min(2000, Cfg("rewind_cap", 200)));
    InitializeCriticalSection(&gCs);
    QueryPerformanceFrequency(&gQpf);
    gWake = CreateEventW(nullptr, FALSE, FALSE, nullptr);
    gMsgProbe = RegisterWindowMessageW(L"ForestRewindProbe");
    return gWake != nullptr;
}

// 지금 상태 한 벌(gCs 안에서 부른다). attach = 지난 멈춤 뒤에 따로 튼 음성을 이 자리에 붙일지
static std::unique_ptr<Snap> captureLocked(uint16_t op, bool attach) {
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
    s->deferred = EV(kDeferred);
    if (gSubs) {
        for (int i = 0; i < kLayers; ++i) {
            const uint8_t* rec = s->ctx + kLayerRecs + i * kRecSize;
            if (*(const uint16_t*)(rec + 0xa) == 2 && *(const int*)(rec + 0x18) && gText[i].valid) s->texts.emplace_back(i, gText[i]);
        }
        if (attach) { s->voice = gVoiceSince; gVoiceSince.valid = false; }   // 이 자리에 붙인다(다음 자리에는 안 붙음)
    }
    if (!attach) {
        s->pri = std::make_shared<Sec>();
        memcpy(s->pri->ctx, (void*)kPriCtx, kCtxSize); memcpy(s->pri->vars, *(void**)kPriVars, kVarSize);
    }
    return s;
}
static void pushLocked(std::unique_ptr<Snap> s, const char* kind) {
    if (gVerify) verifyLocked(*s);
    if (!gHist.empty() && gHist.back()->depth == s->depth && gHist.back()->sid == s->sid && gHist.back()->pc == s->pc) gHist.pop_back();
    if (gLog) rlog("stop %04d:%u op 0x%02x depth %d bgm %u se %u/%u -> history %d%s%s%s", s->sid, s->pc, s->op, s->depth,
                   *(uint16_t*)(s->ctx + 0), *(uint16_t*)(s->ctx + 4), *(uint16_t*)(s->ctx + 6), (int)gHist.size() + 1,
                   s->texts.empty() ? "" : " +subtitle", s->voice.valid ? " +voice" : "", kind);
    gHist.push_back(std::move(s));
    while (gHist.size() > gCap) gHist.pop_front();
    InterlockedExchange(&gCount, (LONG)gHist.size());
}

void Rewind_Fetch(uint16_t op, const uint8_t* cursor) {
    if (!gOn) return;
    DWORD tid = GetCurrentThreadId();
    gFetchTid = tid;
    gCurOp = op;
    if (tid != gHistTid && EV(kCheckpointOk) && !EW(kNested)) {
        // 새 게임·불러오기 뒤에는 VM 스레드가 새로 만들어진다 → 모아 둔 것은 옛 흐름의 것(첫 대사 전에 흐르는 소리 자막도 잡으려고 여기서 본다)
        EnterCriticalSection(&gCs); clearLocked("VM thread changed"); gHistTid = tid; LeaveCriticalSection(&gCs);
    }
    if (InterlockedExchange(&gTextStale, 0)) { for (auto& t : gText) t.valid = false; gVoiceSince.valid = false; gPrevOp = 0; gCand.reset(); gUnitOpen = false; }
    if (gAfterVoiceWait) { gAfterVoiceWait = false; gUnitOpen = false; }   // 음성이 끝났다 → 그 소리 자막은 끝
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
        gUnitOpen = false;
        const bool can = gUnits && !EW(kNested) && EV(kCheckpointOk) && tid == gHistTid;
        if (can) {
            EnterCriticalSection(&gCs);
            gCand = captureLocked(0x42, false);
            LeaveCriticalSection(&gCs);
        } else {
            gCand.reset();
            if (gLog && gUnits) rlog("voice command not kept as a possible stop (sub script %u, checkpoints %d, thread %s)", (unsigned)EW(kNested), EV(kCheckpointOk), tid == gHistTid ? "same" : "new");
        }
        // 따로 튼 음성(자막의 음성)은 대사를 넘겨도 울린다
        for (int i = 0; i < 4; ++i) gVoiceSince.a[i] = vres(*(const uint32_t*)(cursor + 2 + 4 * i));
        gVoiceSince.valid = gVoiceSince.a[0] != 0;
        InterlockedExchange(&gVoiceFree, 1);
    } else if (op == 0x45 || op == 0x0d) {
        if (gCand) {
            bool unit = op == 0x45;
            if (op == 0x0d) {
                // 시간 기다림(인자 V 하나) 바로 뒤가 숨김·음성 끊기·다음 음성이면 = 자막이 쪽을 넘기며 흐르는 자리
                const uint8_t* sc = *(const uint8_t**)kScript;
                const uint8_t* base = sc ? *(const uint8_t* const*)sc : nullptr;
                const uint32_t len = sc ? *(const uint32_t*)(sc + 0x28) : 0;
                if (base && cursor >= base && cursor + 8 <= base + len) {
                    const uint16_t next = *(const uint16_t*)(cursor + 6);
                    unit = next == 0x24 || next == 0x43 || next == 0x42;
                }
            }
            if (unit) {
                EnterCriticalSection(&gCs);
                const bool mine = tid == gHistTid;
                if (mine) pushLocked(std::move(gCand), " +unit");
                gCand.reset();
                LeaveCriticalSection(&gCs);
                if (mine) {
                    gUnitOpen = true;
                    gUnitAt = GetTickCount();
                    gVoiceSince.valid = false;               // 이 음성은 이 소리 자막의 것 — 뒤 대사에 붙이지 않는다
                    if (gLog && gRestoredAt.QuadPart) {
                        LARGE_INTEGER now; QueryPerformanceCounter(&now);
                        rlog("sound subtitle up again %.1f ms after the screen came back", ms(gRestoredAt, now));
                    }
                }
            }
        }
        gRestoredAt.QuadPart = 0;
        if (op == 0x45) { gVoiceSince.valid = false; InterlockedExchange(&gVoiceFree, 0); gAfterVoiceWait = true; }
    } else {
        if (op == 0x43) { gCand.reset(); gUnitOpen = false; }
        if (op == 0x43 || (op == 0x51 && (*(const uint32_t*)(cursor + 6) & 0xffff))) {
            // 음성 끊기·음성 있는 대사(같은 채널을 새로 씀)면 끝난 것으로 본다
            gVoiceSince.valid = false; InterlockedExchange(&gVoiceFree, 0);
        }
        if (op != 0x24) gRestoredAt.QuadPart = 0;
    }
}

void Rewind_Checkpoint() {
    if (!gOn) return;
    DWORD tid = GetCurrentThreadId();
    EnterCriticalSection(&gCs);
    if (tid != gFetchTid) { clearLocked("checkpoint off the VM thread"); LeaveCriticalSection(&gCs); return; }
    if (tid != gHistTid) { clearLocked("VM thread changed"); gHistTid = tid; }
    gCand.reset();                           // 음성 뒤에 대사·선택지가 왔다 → 그 음성은 이 자리에 딸린 것
    gUnitOpen = false;
    pushLocked(captureLocked((uint16_t)gCurOp, true), "");
    LeaveCriticalSection(&gCs);
}

void Rewind_SecondaryChanged() {
    if (!gOn) return;
    EnterCriticalSection(&gCs); gSec.reset(); LeaveCriticalSection(&gCs);
}

void Rewind_Reset(const char* why) {
    if (!gOn) return;
    EnterCriticalSection(&gCs); clearLocked(why); LeaveCriticalSection(&gCs);
    InterlockedExchange(&gPending, 0); InterlockedExchange(&gCutStop, 0); InterlockedExchange(&gChoiceGo, 0); InterlockedExchange(&gHold, 0);
}

HANDLE Rewind_WakeEvent() { return gOn ? gWake : nullptr; }

// VM 스레드, 입력 대기(대사의 클릭 대기·선택지) 안: 요청이 있으면 클릭이 온 것처럼 돌아간다.
bool Rewind_WaitShouldReturn() {
    if (!gOn || !gPending || EW(kNested) || expired()) return false;
    if (EV(kClickWait) || gChoiceGo) { InterlockedExchange(&gCutStop, 1); return true; }
    return false;
}

// VM 스레드가 지금 들어가는 기다림이 「클릭으로도 끊기는 기다림」인가(기다림 갈고리가 묻는다). 엔진의 클릭(0x415970)·영문 패치의 클릭(0x4586c0)이 끊는 것과 같은 셋:
//  · 음성 끝 기다림(명령 0x45, 0x41e6e0): [0x4663f4]=1 로 해 두고 음성 채널의 끝 이벤트를 기다린다(0x43f690 → … → 0x44ed70). 돌아가면 엔진이 음성 채널을 끊는다(0x41e713).
//  · 효과음 끝 기다림(0x41e6a0 언저리): [0x4663f0]=1, 같은 꼴.
//  · 시간 기다림(명령 0x0d, 영문 패치 0x458680): 잠자는 스레드를 만들어 그 핸들([0x48fdf4])을 기다린다. 돌아가면 핸들 칸을 비우고 끝(스레드는 제 시간에 스스로 끝난다).
bool Rewind_CuttableWait(HANDLE h) {
    if (!gOn || GetCurrentThreadId() != gFetchTid || EW(kNested)) return false;
    if (EV(kVoiceWait) || EV(kSeWait)) return true;
    return gCurOp == 0x0d && h && h == *(HANDLE volatile*)kTimedThread;
}
bool Rewind_CutNow() { return gOn && gPending && !EW(kNested) && !expired(); }

bool Rewind_AtFetch() {
    if (!gOn || !gPending || EW(kNested)) return false;
    if (EV(kTyping)) return false;             // 아직 글을 끝내는 중(다음 클릭 대기에서)
    LONG steps = InterlockedExchange(&gPending, 0);
    InterlockedExchange(&gChoiceGo, 0);
    const bool atStop = InterlockedExchange(&gCutStop, 0) != 0;
    if (steps <= 0) { InterlockedExchange(&gHold, 0); return false; }
    if (expired()) { InterlockedExchange(&gHold, 0); rlog("request dropped: the game was busy for %lu ms", (unsigned long)(GetTickCount() - gReqTick)); return false; }
    // 어디서 눌렀나 → 몇 걸음
    int back = (int)steps; const char* where = "at a line or a choice";
    if (!atStop) {
        if (gUnitOpen) {
            const DWORD played = GetTickCount() - gUnitAt;
            if (gUnitRestartMs > 0 && played >= (DWORD)gUnitRestartMs) { back = (int)steps - 1; where = "during a sound subtitle (restart it)"; }
            else where = "just after a sound subtitle started (go before it)";
        } else { back = (int)steps - 1; where = "between stops (back to the one just left)"; }
    }
    EnterCriticalSection(&gCs);
    if (gHist.empty()) { LeaveCriticalSection(&gCs); InterlockedExchange(&gHold, 0); rlog("nothing to go back to"); return false; }
    int idx = (int)gHist.size() - 1 - back;
    if (idx < 0) idx = 0;
    std::unique_ptr<Snap> target = std::move(gHist[idx]);
    gHist.resize(idx);                         // 고른 자리부터 뒤는 버린다(그 자리의 명령이 다시 실행되며 새로 뜬다)
    InterlockedExchange(&gCount, (LONG)gHist.size());
    gSec = target->sec;
    LeaveCriticalSection(&gCs);
    if (gLog) rlog("pressed %s", where);
    restore(*target, back, idx);
    gReqAt.QuadPart = 0;
    return true;
}

bool Rewind_HoldPresent() {
    if (!gOn || !gHold) return false;
    if (GetTickCount() - gHoldAt > kReqLifeMs) { InterlockedExchange(&gHold, 0); return false; }   // 요청이 쓰이지 못했다 → 화면을 붙잡아 두지 않는다
    InterlockedIncrement(&gHeld);
    return true;
}

bool Rewind_WndProc(HWND h, UINT m, WPARAM w, LPARAM l, LRESULT& r) {
    if (!gOn) return false;
    if (gMsgProbe && m == gMsgProbe) { r = request((int)l > 0 ? (int)l : 1, "probe") ? 1 : 0; return true; }
    if (m == WM_KEYDOWN && w == VK_BACK) {
        if (EV(kAuto)) return false;           // 자동 진행 중엔 진행 모듈이 끈다(지금 약속)
        if (!(l & 0x40000000)) request(1, "Backspace");
        r = 0; return true;
    }
    return false;
}

}}  // namespace forest::qol
