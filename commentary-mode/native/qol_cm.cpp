// qol_cm.cpp — Forest 한국어 해설판 v2 (고성능 캐시 렌더링 판).
//
// 성능 핵심 설계:
//  1. 모든 UI 층(설정 행 / 인게임 HUD / 팝업 카드 / F7 해설 도감)을 물리 해상도 DIB(CachedLayer)에 상태 키별로 캐시.
//     글자 타이핑·커서 깜빡임 등 부분 갱신(part BitBlt) 시 겹치는 위젯이 없으면 0.001ms 만에 즉시 반환하고,
//     겹치더라도 GDI+ 재렌더링 없이 캐시된 DIB 에서 AlphaBlend/BitBlt 만 수행(< 0.1ms).
//  2. 무거운 양피지·배경 PNG 는 창 크기(cw, ch)가 바뀔 때 단 한 번만 32bppPARGB 물리 크기로 미리 축소·확대(ScaledUi)하여
//     프레임마다 발생하던 HighQualityBicubic 비용(20ms+)을 제거.
//  3. WM_MOUSEMOVE 는 이산 HoverId 가 실제로 바뀔 때만 이전·새 단추 사각형만 국소 갱신(마우스 이동 중 전체 화면 재합성 0회).
//  4. HiText 황금 글자 판정은 무잠금 std::atomic<bool> 로 처리하고, 대사 진행 시 불필요한 스레드 생성·전체 재그리기를 하지 않음.
//  5. F7 해설 도감이 열려 있을 때는 Cm_CoversScreen()=true 로 아래쪽 4K 그림·글자 합성을 통째로 건너뛰고 SRCCOPY BitBlt 로 즉시 출력.

#include "qol.h"
#include <windowsx.h>
#include <objidl.h>
#include <gdiplus.h>
#include <imm.h>
#include <atomic>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <cwchar>
#include <memory>
#include <mutex>
#include <set>
#include <unordered_map>
#pragma comment(lib, "gdiplus.lib")
#pragma comment(lib, "msimg32.lib")

using namespace Gdiplus;

namespace forest { namespace qol {
namespace {

#define EV(a) (*(volatile int*)(uintptr_t)(a))
#define EW(a) (*(volatile uint16_t*)(uintptr_t)(a))

const uintptr_t kEngineObj   = 0x466398;
const uintptr_t kAuto        = 0x466408;
const uintptr_t kCtrlKey     = 0x4663f8, kCtrlSkip = 0x466400, kTabReq = 0x4663fc, kTabSkip = 0x466404;
const uintptr_t kClickWait   = 0x4663e8, kChoiceBox = 0x4663cc, kSelect = 0x466418;
const uintptr_t kSettings    = 0x46640c, kSaveScr = 0x466410, kLoadScr = 0x466414, kHidden = 0x466420;
const uintptr_t kCtx         = 0x46646c;   // +0 u16: live BGM track (1..21)
const uintptr_t kDepth       = 0x4664bc, kDepthScripts = 0x46647e;
const uintptr_t fIsRead      = 0x418d90;   // int __cdecl(int sid, int slot)
const uintptr_t fBgmPlay     = 0x41e5c0;   // void __cdecl(unsigned track, unsigned loop)
const uintptr_t fBgmStop     = 0x41e600;   // engine scene stop clears the saved BGM too
const uintptr_t fVoicePlay   = 0x41e550;   // void __cdecl(unsigned id, unsigned repeat, unsigned arg2, unsigned vol)
const uintptr_t fVoiceStop   = 0x419000;   // void __cdecl(int fade)
const uintptr_t kVoiceOnFlag = 0x466454;   // u16: 설정 화면 음성 켬/끔
const uintptr_t kTyping      = 0x4663e0;   // 글을 찍는 중 1(다 찍히면 엔진 틱 0x41604f 가 0 으로)
const uintptr_t kVmAlive     = 0x4663c0;   // 대본(VM) 스레드가 살아 있으면 1
const uintptr_t kVmQuit      = 0x4663c8;   // 엔진이 대본 스레드를 끝내려 할 때 1(0x420600)

const UINT_PTR kAnimTimer = 0xF0E72;

void* engineObj() { return *(void* volatile*)kEngineObj; }
bool autoOn() { return EV(kAuto) != 0; }
bool typingNow() { return EV(kTyping) && !EV(kClickWait); }   // 글을 찍는 중(엔진의 클릭 처리 0x415a03~ 와 같은 판정)
bool skipping() { return EV(kCtrlKey) || EV(kCtrlSkip) || EV(kTabReq) || EV(kTabSkip); }
bool screensOpen() { return EV(kSettings) || EV(kSaveScr) || EV(kLoadScr); }
bool settingsRowVisible() { return EV(kSettings) && !EV(kSaveScr) && !EV(kLoadScr); }
int curDepth() { int d = EW(kDepth); return d < 0 ? 0 : (d > 15 ? 15 : d); }
int topScript() { return ((volatile uint16_t*)kDepthScripts)[curDepth()]; }
int liveBgmTrack() { return (int)EW(kCtx); }

bool isSlotRead(int sid, int slot) {
    if (sid <= 0 || slot <= 0) return false;
    __try { return ((int(__cdecl*)(int, int))fIsRead)(sid, slot) != 0; }
    __except (EXCEPTION_EXECUTE_HANDLER) { return false; }
}

void playEngineBgm(int track, int loop = 1) {
    __try {
        if (track > 0) ((void(__cdecl*)(unsigned, unsigned))fBgmPlay)((unsigned)track, (unsigned)loop);
        else if (engineObj()) ((void(__cdecl*)(unsigned))fBgmStop)(0);
    } __except (EXCEPTION_EXECUTE_HANDLER) {}
}

bool isVoiceChannelPlaying() {
    __try {
        uint8_t* eng = (uint8_t*)engineObj(); if (!eng) return false;
        uint8_t* w = *(uint8_t**)(eng + 0x1ac + 4 * 1); if (!w || *(uint32_t*)w != 0x45d5d4) return false;
        uint8_t* in = *(uint8_t**)(w + 4); if (!in || *(uint32_t*)in != 0x45d518) return false;
        uint8_t* ev = *(uint8_t**)(in + 0xc); if (!ev || *(uint32_t*)ev != 0x45d4d0) return false;
        HANDLE h = *(HANDLE*)(ev + 4);
        return h && WaitForSingleObject(h, 0) == WAIT_TIMEOUT;
    } __except (EXCEPTION_EXECUTE_HANDLER) { return false; }
}

void playEngineVoice(int voiceId) {
    if (voiceId <= 0) return;
    __try {
        uint16_t prevVoiceOn = EW(kVoiceOnFlag);
        int prevCtrl = EV(kCtrlSkip), prevTab = EV(kTabSkip);
        if (!prevVoiceOn) EW(kVoiceOnFlag) = 1;
        EV(kCtrlSkip) = 0; EV(kTabSkip) = 0;
        ((void(__cdecl*)(unsigned, unsigned, unsigned, unsigned))fVoicePlay)((unsigned)voiceId, 0, 0, 0);
        if (!prevVoiceOn) EW(kVoiceOnFlag) = 0;
        EV(kCtrlSkip) = prevCtrl; EV(kTabSkip) = prevTab;
    } __except (EXCEPTION_EXECUTE_HANDLER) {}
}

void stopEngineVoice() {
    __try { ((void(__cdecl*)(int))fVoiceStop)(0); }
    __except (EXCEPTION_EXECUTE_HANDLER) {}
}

// ---------------------------------------------------------------- UTF-8 / JSON 파서
bool readAllBytes(const std::wstring& path, std::vector<uint8_t>& out) {
    out.clear();
    HANDLE f = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_EXISTING, 0, nullptr);
    if (f == INVALID_HANDLE_VALUE) return false;
    LARGE_INTEGER sz{}; GetFileSizeEx(f, &sz);
    bool ok = sz.QuadPart > 0 && sz.QuadPart < (64 << 20);
    if (ok) { out.resize((size_t)sz.QuadPart); DWORD n = 0; ok = ReadFile(f, out.data(), (DWORD)out.size(), &n, nullptr) && n == out.size(); }
    CloseHandle(f);
    return ok;
}

std::wstring utf8ToWide(const char* s, int len = -1) {
    if (!s || !*s) return {};
    int n = MultiByteToWideChar(CP_UTF8, 0, s, len, nullptr, 0);
    if (n <= 0) return {};
    std::wstring w(n, L'\0');
    MultiByteToWideChar(CP_UTF8, 0, s, len, &w[0], n);
    if (len < 0 && !w.empty() && w.back() == L'\0') w.pop_back();
    return w;
}

std::string wideToUtf8(const std::wstring& w) {
    if (w.empty()) return {};
    int n = WideCharToMultiByte(CP_UTF8, 0, w.c_str(), (int)w.size(), nullptr, 0, nullptr, nullptr);
    if (n <= 0) return {};
    std::string s(n, '\0');
    WideCharToMultiByte(CP_UTF8, 0, w.c_str(), (int)w.size(), &s[0], n, nullptr, nullptr);
    return s;
}

struct JV {
    enum T { Null, Bool, Num, Str, Arr, Obj } t = Null;
    bool b = false; double n = 0; std::wstring s;
    std::vector<JV> a; std::vector<std::pair<std::wstring, JV>> o;
    const JV* get(const wchar_t* k) const { if (t != Obj) return nullptr; for (auto& p : o) if (p.first == k) return &p.second; return nullptr; }
    std::wstring str(const wchar_t* k) const { auto v = get(k); return v && v->t == Str ? v->s : std::wstring(); }
    int numi(const wchar_t* k, int d = 0) const { auto v = get(k); return v && v->t == Num ? (int)std::lround(v->n) : d; }
    bool boolean(const wchar_t* k, bool d = false) const { auto v = get(k); return v && v->t == Bool ? v->b : d; }
};

struct JParse {
    const wchar_t* p; const wchar_t* e; bool ok = true;
    void ws() { while (p < e && (*p == L' ' || *p == L'\t' || *p == L'\r' || *p == L'\n')) ++p; }
    bool lit(const wchar_t* s) { size_t n = wcslen(s); if ((size_t)(e - p) >= n && wcsncmp(p, s, n) == 0) { p += n; return true; } return false; }
    int hex4() {
        int v = 0;
        for (int i = 0; i < 4; ++i) {
            if (p >= e) { ok = false; return 0; }
            wchar_t c = *p++; v <<= 4;
            if (c >= L'0' && c <= L'9') v |= c - L'0';
            else if (c >= L'a' && c <= L'f') v |= c - L'a' + 10;
            else if (c >= L'A' && c <= L'F') v |= c - L'A' + 10;
            else { ok = false; return 0; }
        }
        return v;
    }
    std::wstring str() {
        std::wstring s; ++p;
        while (p < e && *p != L'"') {
            wchar_t c = *p++;
            if (c != L'\\') { s += c; continue; }
            if (p >= e) { ok = false; break; }
            wchar_t k = *p++;
            switch (k) {
            case L'n': s += L'\n'; break; case L't': s += L'\t'; break; case L'r': s += L'\r'; break;
            case L'b': s += L'\b'; break; case L'f': s += L'\f'; break; case L'u': s += (wchar_t)hex4(); break;
            default: s += k; break;
            }
        }
        if (p < e) ++p; else ok = false;
        return s;
    }
    JV val(int d = 0) {
        JV v; ws();
        if (p >= e || d > 40) { ok = false; return v; }
        if (*p == L'{') {
            v.t = JV::Obj; ++p; ws();
            if (p < e && *p == L'}') { ++p; return v; }
            for (;;) {
                ws(); if (p >= e || *p != L'"') { ok = false; return v; }
                std::wstring k = str(); ws();
                if (p >= e || *p != L':') { ok = false; return v; }
                ++p; v.o.emplace_back(std::move(k), val(d + 1)); if (!ok) return v;
                ws(); if (p < e && *p == L',') { ++p; continue; }
                if (p < e && *p == L'}') { ++p; return v; }
                ok = false; return v;
            }
        }
        if (*p == L'[') {
            v.t = JV::Arr; ++p; ws();
            if (p < e && *p == L']') { ++p; return v; }
            for (;;) {
                v.a.push_back(val(d + 1)); if (!ok) return v;
                ws(); if (p < e && *p == L',') { ++p; continue; }
                if (p < e && *p == L']') { ++p; return v; }
                ok = false; return v;
            }
        }
        if (*p == L'"') { v.t = JV::Str; v.s = str(); return v; }
        if (lit(L"true")) { v.t = JV::Bool; v.b = true; return v; }
        if (lit(L"false")) { v.t = JV::Bool; return v; }
        if (lit(L"null")) return v;
        wchar_t* end = nullptr; v.n = wcstod(p, &end);
        if (!end || end == p) { ok = false; return v; }
        v.t = JV::Num; p = end; return v;
    }
};

// ---------------------------------------------------------------- 해설 데이터 구조
struct ArticleItem {
    std::string id, extImg;
    int chapter = 1;
    std::wstring kind, title, oneliner, source, mark, body, echo, extCaption;
};

struct TextEntry {
    std::string id, refArticle, extImg;
    std::wstring modal;
    int chapter = 1, sid = 0, ord = 0, slot = 0, pc = 0, op = 0, voice = 0, afterSlot = 0;
    std::wstring speaker, ja, ko, kind, title, oneliner, source, mark, body, echo, extCaption;
};

struct ArtEntry {
    std::string id, asset;
    int chapter = 1;
    std::wstring category, kind, title, oneliner, source, mark, body, echo;
    int crop[4] = {0, 0, 0, 0};
    bool hasCrop = false;
};

struct BgmCue {
    int sid = 0, pc = 0;
    std::wstring cueTitle, cueNote;
};

struct BgmEntry {
    std::string id;
    int track = 0, chapter = 1;
    bool inMusicMode = true;
    std::wstring koTitle, jaTitle, enTitle, kind, title, oneliner, source, mark, body, echo;
    std::vector<BgmCue> cues;
};

struct ReviewItem {
    std::string id, extImg;
    bool finaleOnly = false;
    std::wstring sphere, author, date, kind, title, oneliner, quoteOrig, quoteKo, source, mark, body, echo, extCaption;
};

struct LineAnchor { int sid = 0, slot = 0, pc = 0, op = 0, entry = -1; };

std::vector<ArticleItem> gArticles;
std::vector<TextEntry>   gEntries;
std::vector<ArtEntry>    gArts;
std::vector<BgmEntry>    gBgms;
std::vector<ReviewItem>  gReviews;
std::vector<LineAnchor>  gLineAnchors;
std::unordered_map<uint64_t, int> gByLineKey;
std::unordered_map<uint64_t, int> gBySubKey;
std::unordered_map<uint64_t, int> gByChoicePc;
std::unordered_map<uint64_t, int> gByChoiceQSlot;
std::unordered_map<std::string, int> gArtByAsset;
std::unordered_map<int, int> gBgmByTrack;
std::unordered_map<std::string, std::wstring> gHiartFiles;

bool gLoaded = false;
bool gModOn = false, gTestMode = false;
UINT gMsgTest = 0, gMsgSync = 0;
HWND gWnd = nullptr;

// ---------------------------------------------------------------- 사용자 설정·해금 상태
CRITICAL_SECTION gStateCs;
std::atomic<bool> gProgressDirty{false};
std::atomic<unsigned> gUnlockGeneration{0};
std::set<std::string> gSeenEntries;
std::set<std::string> gSeenArt;
std::set<int>         gSeenBgm;

// 무잠금 원자 플래그(HiText_Paint 내부에서 글리프마다 호출되므로 0ns 무잠금 처리)
std::atomic<bool> gGoldenLineAtom{false};
std::atomic<bool> gGoldenHoverAtom{false};

enum class CardKind { None, Text, Art, Bgm, Article, Review };
const int kNumEncycTabs = 6;
struct StoryState {
    int curSid = 0, lineSid = 0;
    uint32_t curPc = 0, lineSerial = 1;
    int activeLineEntry = -1, prevLineEntry = -1, activeSubEntry = -1, activeChoiceEntry = -1;
    bool lineAfterOk = true, inChoiceOp = false;
    int choiceOwnerSid = 0, choiceOwnerDepth = 0;
    DWORD choiceOwnerTid = 0;
};
struct UiState {
    CardKind cardKind = CardKind::None;
    int cardIdx = -1;
    bool encycOpen = false, enabled = false, qbarOpen = true, unlockAll = false;
    int guideMode = 1, cardArtCursor = 0, cardScroll = 0;
    int encycTab = 0, encycSel = 0, encycListScroll = 0, encycBodyScroll = 0;
    int savedSceneBgm = 0, previewingBgm = 0, previewingVoice = 0;
    DWORD artBreathStart = 0;
    uint32_t viewedSerial = 0;
    POINT mouse = {-100, -100};
    int hoverId = 0;
    std::shared_ptr<const std::vector<int>> visibleArt;
    const std::vector<int>& artIndices() const {
        static const std::vector<int> empty;
        return visibleArt ? *visibleArt : empty;
    }
};
struct CommentaryFrame : StoryState, UiState {};
std::mutex gViewMutex, gVmWriter;
StoryState gStory;
UiState gUi;
std::atomic<int> gCardMaxScroll{0}, gEncycListMaxScroll{0}, gEncycBodyMaxScroll{0};
std::atomic<bool> gModal{false}, gBookOpen{false}, gCmEnabled{false};
thread_local CommentaryFrame* gEditing = nullptr; // window input can reenter
thread_local CommentaryFrame gRenderFrame;
thread_local unsigned gRenderDepth = 0;
// Only the window thread uses these media cache keys.
std::string gLastArtSig;
uint32_t gLastArtEpoch = 0;
int gLastBgmTrack = -1;

CommentaryFrame snapshot() {
    CommentaryFrame out;
    std::lock_guard<std::mutex> lock(gViewMutex);
    static_cast<StoryState&>(out) = gStory;
    static_cast<UiState&>(out) = gEditing ? static_cast<const UiState&>(*gEditing) : gUi;
    return out;
}
void publishUi(const UiState& ui) {
    std::lock_guard<std::mutex> lock(gViewMutex);
    gUi = ui;
    gModal.store(ui.encycOpen || ui.cardKind != CardKind::None);
    gBookOpen.store(ui.encycOpen);
    gCmEnabled.store(ui.enabled);
}
class WindowEdit {
    CommentaryFrame* outer;
    CommentaryFrame local;
public:
    WindowEdit() : outer(gEditing) {
        if (!outer) { local = snapshot(); gEditing = &local; }
    }
    ~WindowEdit() {
        if (!outer) { publishUi(local); gEditing = nullptr; }
    }
    CommentaryFrame& get() { return *gEditing; }
};
class StoryEdit {
    std::lock_guard<std::mutex> writer;
public:
    CommentaryFrame frame;
    StoryEdit() : writer(gVmWriter), frame(snapshot()) {}
    ~StoryEdit() {
        std::lock_guard<std::mutex> lock(gViewMutex);
        gStory = frame;
    }
};

// 이산 마우스 호버 상태(마우스 좌표가 변해도 HoverId 가 같으면 재그리기 0회!)
enum HoverId : int {
    HovNone = 0,
    HovConfOn, HovConfOff, HovTitleCmBtn,
    HovBook, HovQMode, HovQArt, HovQBgm, HovQEncyc,
    HovArtSeal, HovChoicePill, HovSubPill, HovLinePill, HovPlate, HovGoldenText,
    HovCardClose, HovCardEncyc, HovCardAudio, HovCardPrev, HovCardNext, HovCardOk,
    HovEncycTab0, HovEncycTab1, HovEncycTab2, HovEncycTab3, HovEncycTab4, HovEncycTab5,
    HovEncycAudio, HovEncycUnlock, HovEncycChart, HovEncycClose,
    HovEncycRowBase = 100
};

// 본문 높이 메모이제이션: (kind<<24 | unlockAll<<23 | idx) -> 논리 높이
std::unordered_map<uint32_t, float> gHeightMemo;

std::wstring stateFilePath() { return Root() + L"\\forest-chart-progress\\commentary_v2.dat"; }

void saveUserState(CommentaryFrame& frame) {
    CreateDirectoryW((Root() + L"\\forest-chart-progress").c_str(), nullptr);
    gProgressDirty.exchange(false);
    std::string out;
    out += "enabled=" + std::to_string(frame.enabled ? 1 : 0) + "\n";
    out += "guide_mode=" + std::to_string(frame.guideMode) + "\n";
    out += "qbar_open=" + std::to_string(frame.qbarOpen ? 1 : 0) + "\n";
    out += "unlock_all=" + std::to_string(frame.unlockAll ? 1 : 0) + "\n";
    EnterCriticalSection(&gStateCs);
    for (auto& s : gSeenEntries) out += "entry=" + s + "\n";
    for (auto& a : gSeenArt) out += "art=" + a + "\n";
    for (int t : gSeenBgm) out += "bgm=" + std::to_string(t) + "\n";
    LeaveCriticalSection(&gStateCs);
    const auto path = stateFilePath();
    const auto temp = path + L".tmp";
    HANDLE f = CreateFileW(temp.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    DWORD bytes = 0;
    bool ok = f != INVALID_HANDLE_VALUE;
    if (ok) {
        ok = WriteFile(f, out.data(), (DWORD)out.size(), &bytes, nullptr) && bytes == out.size() && FlushFileBuffers(f);
        if (!CloseHandle(f)) ok = false;
    }
    if (ok) ok = MoveFileExW(temp.c_str(), path.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH) != FALSE;
    if (!ok) gProgressDirty.store(true);
}

void loadUserState(CommentaryFrame& frame) {
    frame.enabled = Cfg("cm_enable", 0) != 0;
    frame.guideMode = std::max(0, std::min(2, Cfg("cm_guide", 1)));
    frame.qbarOpen = true;
    frame.unlockAll = Cfg("cm_unlock_all", 0) != 0;
    std::vector<uint8_t> raw;
    if (!readAllBytes(stateFilePath(), raw)) return;
    std::string s((const char*)raw.data(), raw.size());
    size_t p = 0;
    EnterCriticalSection(&gStateCs);
    while (p < s.size()) {
        size_t e = s.find('\n', p); if (e == std::string::npos) e = s.size();
        std::string ln = s.substr(p, e - p); p = e + 1;
        if (!ln.empty() && ln.back() == '\r') ln.pop_back();
        size_t eq = ln.find('='); if (eq == std::string::npos) continue;
        std::string k = ln.substr(0, eq), v = ln.substr(eq + 1);
        if (k == "enabled") frame.enabled = atoi(v.c_str()) != 0;
        else if (k == "guide_mode") frame.guideMode = std::max(0, std::min(2, atoi(v.c_str())));
        else if (k == "qbar_open") frame.qbarOpen = atoi(v.c_str()) != 0;
        else if (k == "unlock_all") frame.unlockAll = atoi(v.c_str()) != 0;
        else if (k == "entry" && !v.empty()) gSeenEntries.insert(v);
        else if (k == "art" && !v.empty()) gSeenArt.insert(v);
        else if (k == "bgm") { int t = atoi(v.c_str()); if (t > 0) gSeenBgm.insert(t); }
    }
    LeaveCriticalSection(&gStateCs);
}

bool isEntryUnlocked(CommentaryFrame& frame, int idx) {
    if (idx < 0 || idx >= (int)gEntries.size()) return false;
    if (frame.unlockAll) return true;
    const auto& e = gEntries[idx];
    EnterCriticalSection(&gStateCs);
    bool seen = gSeenEntries.count(e.id) != 0;
    LeaveCriticalSection(&gStateCs);
    if (seen) return true;
    return isSlotRead(e.sid, e.slot);
}

bool isArtUnlocked(CommentaryFrame& frame, int idx) {
    if (idx < 0 || idx >= (int)gArts.size()) return false;
    if (frame.unlockAll) return true;
    EnterCriticalSection(&gStateCs);
    bool seen = gSeenArt.count(gArts[idx].asset) != 0;
    LeaveCriticalSection(&gStateCs);
    return seen;
}

bool isBgmUnlocked(CommentaryFrame& frame, int idx) {
    if (idx < 0 || idx >= (int)gBgms.size()) return false;
    if (frame.unlockAll) return true;
    EnterCriticalSection(&gStateCs);
    bool seen = gSeenBgm.count(gBgms[idx].track) != 0;
    LeaveCriticalSection(&gStateCs);
    return seen;
}

bool isReviewUnlocked(CommentaryFrame& frame, int idx) {
    if (idx < 0 || idx >= (int)gReviews.size()) return false;
    if (frame.unlockAll || !gReviews[idx].finaleOnly) return true;
    return isSlotRead(2900, 40);
}

// ---------------------------------------------------------------- 데이터 및 hiart 색인 로드
void loadHiartMap() {
    std::vector<uint8_t> raw;
    if (!readAllBytes(Root() + L"\\hiart\\index.tsv", raw)) return;
    std::string s((const char*)raw.data(), raw.size());
    size_t p = 0;
    while (p < s.size()) {
        size_t e = s.find('\n', p); if (e == std::string::npos) e = s.size();
        std::string ln = s.substr(p, e - p); p = e + 1;
        if (!ln.empty() && ln.back() == '\r') ln.pop_back();
        if (ln.empty() || ln[0] == '#') continue;
        char key[64]{}, file[128]{};
        if (sscanf_s(ln.c_str(), "%63s %127s", key, (unsigned)sizeof(key), file, (unsigned)sizeof(file)) == 2) {
            std::string k = key;
            for (char& c : k) c = (char)tolower((unsigned char)c);
            std::wstring wf;
            for (char* c = file; *c; ++c) wf += (wchar_t)(*c == '/' ? L'\\' : *c);
            gHiartFiles[k] = wf;
        }
    }
}

bool verifyGscLineAnchor(const std::vector<uint8_t>& gsc, int slot, int pc, int op) {
    if (gsc.size() < 32) return false;
    uint32_t start = *(const uint32_t*)&gsc[4];
    size_t off = (size_t)start + (size_t)pc;
    if (op == 0x51) return off + 30 <= gsc.size() && *(const uint16_t*)&gsc[off] == 0x51 && *(const int32_t*)&gsc[off + 22] == slot;
    if (op == 0x52) return off + 26 <= gsc.size() && *(const uint16_t*)&gsc[off] == 0x52 && *(const int32_t*)&gsc[off + 18] == slot;
    return false;
}

// The engine also accepts loose replacements in voice/. Scan only the XFL directory.
bool installedVoiceIds(std::set<int>& ids) {
    HANDLE file = CreateFileW((Root() + L"\\voice.xfl").c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) return false;
    uint32_t header[3] = {}; DWORD got = 0;
    LARGE_INTEGER size{};
    bool ok = GetFileSizeEx(file, &size) && ReadFile(file, header, sizeof(header), &got, nullptr) && got == sizeof(header) &&
              header[0] == 0x0001424c && header[2] <= 100000 && header[1] == header[2] * 40u &&
              size.QuadPart >= 12LL + header[1];
    std::vector<uint8_t> toc(ok ? header[1] : 0);
    if (ok && !toc.empty()) ok = ReadFile(file, toc.data(), header[1], &got, nullptr) && got == header[1];
    CloseHandle(file);
    if (ok) for (size_t off = 0; off < toc.size(); off += 40) {
        const char* name = (const char*)toc.data() + off;
        uint32_t pos, len; memcpy(&pos, name + 32, 4); memcpy(&len, name + 36, 4);
        if (len && 12LL + header[1] + pos + len <= size.QuadPart &&
            name[0] >= '0' && name[0] <= '9' && name[1] >= '0' && name[1] <= '9' &&
            name[2] >= '0' && name[2] <= '9' && name[3] >= '0' && name[3] <= '9' && !_strnicmp(name + 4, ".wav", 5))
            ids.insert(atoi(name));
    }
    return ok;
}

bool loadCommentaryJson() {
    std::set<int> voices;
    const bool indexed = installedVoiceIds(voices);
    std::vector<uint8_t> raw;
    if (!readAllBytes(Root() + L"\\cm\\commentary_v2.json", raw)) return false;
    size_t skip = (raw.size() >= 3 && raw[0] == 0xEF && raw[1] == 0xBB && raw[2] == 0xBF) ? 3 : 0;
    std::wstring w = utf8ToWide((const char*)raw.data() + skip, (int)(raw.size() - skip));
    if (w.empty()) return false;
    JParse jp{w.c_str(), w.c_str() + w.size()};
    JV root = jp.val();
    if (!jp.ok || root.t != JV::Obj) return false;

    if (const JV* arr = root.get(L"articles"); arr && arr->t == JV::Arr) {
        for (auto& j : arr->a) {
            ArticleItem it;
            it.id = wideToUtf8(j.str(L"id")); it.chapter = j.numi(L"chapter", 1);
            it.kind = j.str(L"kind"); it.title = j.str(L"title"); it.oneliner = j.str(L"oneliner");
            it.source = j.str(L"source"); it.mark = j.str(L"mark"); it.body = j.str(L"body"); it.echo = j.str(L"echo");
            it.extImg = wideToUtf8(j.str(L"ext_img")); it.extCaption = j.str(L"ext_caption");
            gArticles.push_back(std::move(it));
        }
    }
    if (const JV* arr = root.get(L"entries"); arr && arr->t == JV::Arr) {
        for (auto& j : arr->a) {
            TextEntry e;
            e.id = wideToUtf8(j.str(L"id")); e.refArticle = wideToUtf8(j.str(L"ref_article"));
            e.extImg = wideToUtf8(j.str(L"ext_img")); e.extCaption = j.str(L"ext_caption");
            e.modal = j.str(L"modal"); e.chapter = j.numi(L"chapter", 1);
            e.sid = j.numi(L"sid"); e.ord = j.numi(L"ord"); e.slot = j.numi(L"slot");
            e.pc = j.numi(L"pc"); e.op = j.numi(L"op", 0x51); e.voice = j.numi(L"voice", 0); e.afterSlot = j.numi(L"after_slot", 0);
            if (indexed && e.voice > 0 && !voices.count(e.voice)) {
                wchar_t loose[48]; swprintf_s(loose, L"\\voice\\%04d.wav", e.voice);
                if (GetFileAttributesW((Root() + loose).c_str()) == INVALID_FILE_ATTRIBUTES) e.voice = 0;
            }
            e.speaker = j.str(L"speaker"); e.ja = j.str(L"ja"); e.ko = j.str(L"ko");
            e.kind = j.str(L"kind"); e.title = j.str(L"title"); e.oneliner = j.str(L"oneliner");
            e.source = j.str(L"source"); e.mark = j.str(L"mark"); e.body = j.str(L"body"); e.echo = j.str(L"echo");
            gEntries.push_back(std::move(e));
        }
    }
    std::map<int, std::vector<uint8_t>> gscCache;
    auto getGsc = [&](int sid) -> const std::vector<uint8_t>& {
        auto it = gscCache.find(sid);
        if (it == gscCache.end()) {
            wchar_t fn[64]; swprintf_s(fn, L"\\scr\\%04d.gsc", sid);
            readAllBytes(Root() + fn, gscCache[sid]);
            it = gscCache.find(sid);
        }
        return it->second;
    };
    if (const JV* arr = root.get(L"line_anchors"); arr && arr->t == JV::Arr) {
        for (auto& j : arr->a) {
            LineAnchor a{j.numi(L"sid"), j.numi(L"slot"), j.numi(L"pc"), j.numi(L"op", 0x51), j.numi(L"entry", -1)};
            if (a.entry >= 0 && a.entry < (int)gEntries.size() && verifyGscLineAnchor(getGsc(a.sid), a.slot, a.pc, a.op)) {
                gLineAnchors.push_back(a);
                gByLineKey[((uint64_t)a.sid << 32) | (uint32_t)a.slot] = a.entry;
            }
        }
    }
    if (const JV* arr = root.get(L"sub_anchors"); arr && arr->t == JV::Arr) {
        for (auto& j : arr->a) {
            int sid = j.numi(L"sid"), slot = j.numi(L"slot"), ent = j.numi(L"entry", -1);
            if (ent >= 0 && ent < (int)gEntries.size()) gBySubKey[((uint64_t)sid << 32) | (uint32_t)slot] = ent;
        }
    }
    if (const JV* arr = root.get(L"choice_anchors"); arr && arr->t == JV::Arr) {
        for (auto& j : arr->a) {
            int sid = j.numi(L"sid"), pc = j.numi(L"pc"), qSlot = j.numi(L"q_slot"), ent = j.numi(L"entry", -1);
            if (ent >= 0 && ent < (int)gEntries.size()) {
                gByChoicePc[((uint64_t)sid << 32) | (uint32_t)pc] = ent;
                if (qSlot > 0) {
                    auto result = gByChoiceQSlot.emplace(((uint64_t)sid << 32) | (uint32_t)qSlot, ent);
                    if (!result.second) result.first->second = -1;
                }
            }
        }
    }
    if (const JV* arr = root.get(L"art_entries"); arr && arr->t == JV::Arr) {
        for (auto& j : arr->a) {
            ArtEntry a;
            a.id = wideToUtf8(j.str(L"id")); a.asset = wideToUtf8(j.str(L"asset")); a.chapter = j.numi(L"chapter", 1);
            a.category = j.str(L"category"); a.kind = j.str(L"kind"); a.title = j.str(L"title");
            a.oneliner = j.str(L"oneliner"); a.source = j.str(L"source"); a.mark = j.str(L"mark");
            a.body = j.str(L"body"); a.echo = j.str(L"echo");
            if (const JV* cr = j.get(L"crop"); cr && cr->t == JV::Arr && cr->a.size() == 4) {
                for (int k = 0; k < 4; ++k) a.crop[k] = (int)std::lround(cr->a[k].n);
                a.hasCrop = a.crop[2] > 0 && a.crop[3] > 0;
            }
            gArtByAsset[a.asset] = (int)gArts.size();
            gArts.push_back(std::move(a));
        }
    }
    if (const JV* arr = root.get(L"bgm_entries"); arr && arr->t == JV::Arr) {
        for (auto& j : arr->a) {
            BgmEntry m;
            m.id = wideToUtf8(j.str(L"id")); m.track = j.numi(L"track"); m.chapter = j.numi(L"chapter", 1);
            m.inMusicMode = j.boolean(L"in_music_mode", m.track <= 14);
            m.koTitle = j.str(L"ko_title"); m.jaTitle = j.str(L"ja_title"); m.enTitle = j.str(L"en_title");
            m.kind = j.str(L"kind"); m.title = j.str(L"title"); m.oneliner = j.str(L"oneliner");
            m.source = j.str(L"source"); m.mark = j.str(L"mark"); m.body = j.str(L"body"); m.echo = j.str(L"echo");
            if (const JV* cs = j.get(L"scene_cues"); cs && cs->t == JV::Arr) {
                for (auto& cj : cs->a) {
                    BgmCue cue{cj.numi(L"sid"), cj.numi(L"ko_pc", cj.numi(L"pc", 0)), cj.str(L"cue_title"), cj.str(L"cue_note")};
                    m.cues.push_back(std::move(cue));
                }
            }
            gBgmByTrack[m.track] = (int)gBgms.size();
            gBgms.push_back(std::move(m));
        }
    }
    if (const JV* arr = root.get(L"reviews"); arr && arr->t == JV::Arr) {
        for (auto& j : arr->a) {
            ReviewItem rv;
            rv.id = wideToUtf8(j.str(L"id"));
            rv.finaleOnly = j.boolean(L"finale_only", false);
            rv.sphere = j.str(L"sphere"); rv.author = j.str(L"author"); rv.date = j.str(L"date");
            rv.kind = j.str(L"kind"); rv.title = j.str(L"title"); rv.oneliner = j.str(L"oneliner");
            rv.quoteOrig = j.str(L"quote_orig"); rv.quoteKo = j.str(L"quote_ko");
            rv.source = j.str(L"source"); rv.mark = j.str(L"mark");
            rv.body = j.str(L"body"); rv.echo = j.str(L"echo");
            rv.extImg = wideToUtf8(j.str(L"ext_img")); rv.extCaption = j.str(L"ext_caption");
            gReviews.push_back(std::move(rv));
        }
    }
    return !gEntries.empty() || !gArts.empty();
}

// ---------------------------------------------------------------- GDI+ 원본 자산 + 물리 해상도 사전 스케일 캐시(ScaledUi)
// 프로세스 종료 시(Loader Lock 안) GDI+ 객체 소멸자가 불리면 교착이 생길 수 있으므로,
// 전역 캐시는 원시 포인터로 들고 창이 닫힐 때(WM_DESTROY) 안전하게 정리한다.
ULONG_PTR gGdipToken = 0;
bool gUiLoaded = false;
PrivateFontCollection* gFontCol = nullptr;
FontFamily* gFamSerif = nullptr;
FontFamily* gFamHeading = nullptr;
FontFamily* gFamJa = nullptr;

struct RawUi {
    Bitmap *confRow = nullptr, *confOn = nullptr, *confOnF = nullptr, *confOff = nullptr, *confOffF = nullptr;
    Bitmap *bookIdle = nullptr, *bookHover = nullptr, *bookActive = nullptr;
    Bitmap *qbarRibbon = nullptr, *ovalBrown = nullptr, *ovalGreen = nullptr, *glowGold = nullptr, *glowGreen = nullptr;
    Bitmap *titleOvalBrown = nullptr, *titleOvalGreen = nullptr;
    Bitmap *plateOneliner = nullptr, *plateDetail = nullptr, *cardParchment = nullptr, *folioParchment = nullptr;
    Bitmap *encycBg = nullptr, *encycFg = nullptr, *plateLit = nullptr, *plateDim = nullptr;
} UI;

struct ScaledUi {
    int cw = 0, ch = 0;
    Bitmap *confRow = nullptr, *qbarRibbon = nullptr, *plateOneliner = nullptr, *plateDetail = nullptr;
    Bitmap *cardParchment = nullptr, *folioParchment = nullptr, *encycBg = nullptr, *encycFg = nullptr;
    void clear() {
        for (Bitmap** p : {&confRow, &qbarRibbon, &plateOneliner, &plateDetail, &cardParchment, &folioParchment, &encycBg, &encycFg}) {
            if (*p) { delete *p; *p = nullptr; }
        }
        cw = ch = 0;
    }
} SUI;

std::unordered_map<std::string, Bitmap*> gArtThumbCache;
std::unordered_map<std::string, Bitmap*> gExtThumbCache;

Bitmap* getExtThumb(const std::string& extFile) {
    if (extFile.empty()) return nullptr;
    auto it = gExtThumbCache.find(extFile);
    if (it != gExtThumbCache.end()) return it->second;
    std::wstring path = Root() + L"\\cm\\ext\\" + utf8ToWide(extFile.c_str());
    std::unique_ptr<Bitmap> src(Bitmap::FromFile(path.c_str(), FALSE));
    if (!src || src->GetLastStatus() != Ok || !src->GetWidth()) { gExtThumbCache[extFile] = nullptr; return nullptr; }
    int sw = (int)src->GetWidth(), sh = (int)src->GetHeight();
    const int MW = 640, MH = 520;
    double scale = std::min(1.0, std::min((double)MW / sw, (double)MH / sh));
    int dw = std::max(16, (int)std::lround(sw * scale)), dh = std::max(16, (int)std::lround(sh * scale));
    Bitmap* dst = new Bitmap(dw, dh, PixelFormat32bppPARGB);
    Graphics g(dst);
    g.SetCompositingMode(CompositingModeSourceCopy);
    g.SetInterpolationMode(InterpolationModeHighQualityBicubic);
    g.DrawImage(src.get(), Rect(0, 0, dw, dh), 0, 0, sw, sh, UnitPixel);
    gExtThumbCache[extFile] = dst;
    return dst;
}

Bitmap* loadPngPargb(const std::wstring& rel) {
    std::unique_ptr<Bitmap> src(Bitmap::FromFile((Root() + rel).c_str(), FALSE));
    if (!src || src->GetLastStatus() != Ok || !src->GetWidth()) return nullptr;
    int w = (int)src->GetWidth(), h = (int)src->GetHeight();
    Bitmap* dst = new Bitmap(w, h, PixelFormat32bppPARGB);
    Graphics g(dst);
    g.SetCompositingMode(CompositingModeSourceCopy);
    g.DrawImage(src.get(), Rect(0, 0, w, h), 0, 0, w, h, UnitPixel);
    return dst;
}

Bitmap* prescaleBitmap(Bitmap* src, int pw, int ph) {
    if (!src || pw <= 0 || ph <= 0) return nullptr;
    Bitmap* dst = new Bitmap(pw, ph, PixelFormat32bppPARGB);
    Graphics g(dst);
    g.SetCompositingMode(CompositingModeSourceCopy);
    g.SetInterpolationMode(InterpolationModeHighQualityBicubic);
    g.SetPixelOffsetMode(PixelOffsetModeHalf);
    g.DrawImage(src, Rect(0, 0, pw, ph), 0, 0, src->GetWidth(), src->GetHeight(), UnitPixel);
    return dst;
}

void ensureUiAssets() {
    if (gUiLoaded) return;
    gUiLoaded = true;
    GdiplusStartupInput si;
    if (!gGdipToken) GdiplusStartup(&gGdipToken, &si, nullptr);

    gFontCol = new PrivateFontCollection();
    gFontCol->AddFontFile((Root() + L"\\fc\\ForestChartSerif-SemiBold.ttf").c_str());
    gFontCol->AddFontFile((Root() + L"\\fc\\ForestChartSerif-Black.ttf").c_str());

    int nFam = gFontCol->GetFamilyCount();
    if (nFam > 0) {
        std::vector<FontFamily> fams(nFam);
        int found = 0;
        gFontCol->GetFamilies(nFam, fams.data(), &found);
        for (int i = 0; i < found; ++i) {
            wchar_t name[LF_FACESIZE]{};
            if (fams[i].GetFamilyName(name) != Ok) continue;
            if (!gFamSerif && wcsstr(name, L"SemiBold")) gFamSerif = fams[i].Clone();
            if (!gFamHeading && wcsstr(name, L"Black")) gFamHeading = fams[i].Clone();
        }
    }
    if (!gFamSerif) {
        for (const wchar_t* family : {L"Batang", L"Malgun Gothic", L"Gulim"}) {
            auto face = new FontFamily(family);
            if (face->GetLastStatus() == Ok) { gFamSerif = face; break; }
            delete face;
        }
        if (!gFamSerif) gFamSerif = FontFamily::GenericSerif()->Clone();
    }
    if (!gFamHeading) gFamHeading = gFamSerif;
    gFamJa = new FontFamily(L"Yu Mincho");
    if (gFamJa->GetLastStatus() != Ok) { delete gFamJa; gFamJa = new FontFamily(L"MS Mincho"); }
    if (gFamJa->GetLastStatus() != Ok) { delete gFamJa; gFamJa = gFamSerif->Clone(); }

    UI.confRow        = loadPngPargb(L"\\cm\\ui\\conf_cm_row.png");
    UI.confOn         = loadPngPargb(L"\\cm\\ui\\conf_on.png");
    UI.confOnF        = loadPngPargb(L"\\cm\\ui\\conf_on_f.png");
    UI.confOff        = loadPngPargb(L"\\cm\\ui\\conf_off.png");
    UI.confOffF       = loadPngPargb(L"\\cm\\ui\\conf_off_f.png");
    UI.bookIdle       = loadPngPargb(L"\\cm\\ui\\book_idle.png");
    UI.bookHover      = loadPngPargb(L"\\cm\\ui\\book_hover.png");
    UI.bookActive     = loadPngPargb(L"\\cm\\ui\\book_active.png");
    UI.qbarRibbon     = loadPngPargb(L"\\cm\\ui\\qbar_ribbon.png");
    UI.ovalBrown      = loadPngPargb(L"\\cm\\ui\\oval_brown.png");
    UI.ovalGreen      = loadPngPargb(L"\\cm\\ui\\oval_green.png");
    UI.titleOvalBrown = loadPngPargb(L"\\fc\\oval_brown.png");
    UI.titleOvalGreen = loadPngPargb(L"\\fc\\oval_green.png");
    UI.glowGold       = loadPngPargb(L"\\cm\\ui\\glow_gold.png");
    UI.glowGreen      = loadPngPargb(L"\\cm\\ui\\glow_green.png");
    UI.plateOneliner  = loadPngPargb(L"\\cm\\ui\\plate_oneliner.png");
    UI.plateDetail    = loadPngPargb(L"\\cm\\ui\\plate_detail.png");
    UI.cardParchment  = loadPngPargb(L"\\cm\\ui\\card_parchment.png");
    UI.folioParchment = loadPngPargb(L"\\cm\\ui\\folio_parchment.png");
    UI.encycBg        = loadPngPargb(L"\\fc\\frame_bg.png");
    UI.encycFg        = loadPngPargb(L"\\fc\\frame_fg.png");
    UI.plateLit       = loadPngPargb(L"\\cm\\ui\\plate_lit.png");
    UI.plateDim       = loadPngPargb(L"\\cm\\ui\\plate_dim.png");
}

int scX(int v, int cw) { return (int)std::lround(v * (cw / 800.0)); }
int scY(int v, int ch) { return (int)std::lround(v * (ch / 600.0)); }

void ensureScaledUi(int cw, int ch, bool hud, bool card, bool book) {
    if (SUI.cw != cw || SUI.ch != ch) {
        SUI.clear(); SUI.cw = cw; SUI.ch = ch;
    }
    if (!SUI.confRow && settingsRowVisible()) SUI.confRow        = prescaleBitmap(UI.confRow,        scX(510, cw), scY(57, ch));
    if (!SUI.qbarRibbon && hud) SUI.qbarRibbon     = prescaleBitmap(UI.qbarRibbon,     scX(564, cw), scY(36, ch));
    if (!SUI.plateOneliner && hud) SUI.plateOneliner  = prescaleBitmap(UI.plateOneliner,  scX(604, cw), scY(68, ch));
    if (!SUI.plateDetail && hud) SUI.plateDetail    = prescaleBitmap(UI.plateDetail,    scX(604, cw), scY(124, ch));
    if (!SUI.cardParchment && card) SUI.cardParchment  = prescaleBitmap(UI.cardParchment,  scX(648, cw), scY(444, ch));
    if (!SUI.folioParchment && book) SUI.folioParchment = prescaleBitmap(UI.folioParchment, scX(496, cw), scY(376, ch));
    if (!SUI.encycBg && book) SUI.encycBg        = prescaleBitmap(UI.encycBg,        cw, ch);
    if (!SUI.encycFg && book) SUI.encycFg        = prescaleBitmap(UI.encycFg,        cw, ch);
}

Bitmap* getArtThumb(const ArtEntry& ae) {
    auto it = gArtThumbCache.find(ae.asset);
    if (it != gArtThumbCache.end()) return it->second;
    auto fit = gHiartFiles.find(ae.asset);
    if (fit == gHiartFiles.end()) { gArtThumbCache[ae.asset] = nullptr; return nullptr; }
    std::wstring path = Root() + L"\\hiart\\" + fit->second;
    std::unique_ptr<Bitmap> src(Bitmap::FromFile(path.c_str(), FALSE));
    if (!src || src->GetLastStatus() != Ok || !src->GetWidth()) { gArtThumbCache[ae.asset] = nullptr; return nullptr; }
    int sw = (int)src->GetWidth(), sh = (int)src->GetHeight();
    int cx = 0, cy = 0, cw = sw, ch = sh;
    if (ae.hasCrop) {
        double rx = sw / 800.0, ry = sh / 600.0;
        cx = std::max(0, (int)std::lround(ae.crop[0] * rx));
        cy = std::max(0, (int)std::lround(ae.crop[1] * ry));
        cw = std::min(sw - cx, std::max(16, (int)std::lround(ae.crop[2] * rx)));
        ch = std::min(sh - cy, std::max(16, (int)std::lround(ae.crop[3] * ry)));
    }
    const int TW = 320, TH = 240;
    Bitmap* dst = new Bitmap(TW, TH, PixelFormat32bppPARGB);
    Graphics g(dst);
    g.SetInterpolationMode(InterpolationModeHighQualityBicubic);
    g.Clear(Color(255, 22, 18, 14));
    double scale = std::min((double)TW / cw, (double)TH / ch);
    int dw = (int)std::lround(cw * scale), dh = (int)std::lround(ch * scale);
    g.DrawImage(src.get(), Rect((TW - dw) / 2, (TH - dh) / 2, dw, dh), cx, cy, cw, ch, UnitPixel);
    if (gArtThumbCache.size() > 36) {
        for (auto& kv : gArtThumbCache) delete kv.second;
        gArtThumbCache.clear();
    }
    gArtThumbCache[ae.asset] = dst;
    return dst;
}

// ---------------------------------------------------------------- 논리 사각형·좌표 상수(800×600)
const RECT kConfRowRect  = {145, 485, 655, 542};
const RECT kConfOnRect   = {343, 495, 483, 518};
const RECT kConfOffRect  = {497, 495, 637, 518};

const RECT kBookRect     = {760,   8, 790,  32};
const RECT kQbarRect     = {194,   5, 758,  41};
const RECT kQbarModeBtn  = {208,   8, 342,  38};
const RECT kQbarArtBtn   = {352,   8, 466,  38};
const RECT kQbarBgmBtn   = {474,   8, 634,  38};
const RECT kQbarEncycBtn = {642,   8, 752,  38};

const RECT kLinePillRect = {668, 440, 772, 466};
const RECT kOnePlateRect = { 98, 370, 702, 438};
const RECT kDetPlateRect = { 98, 314, 702, 438};
const RECT kChoicePill   = {265,  54, 535,  88};
const RECT kArtSealRect  = { 16,  46, 154,  76};

const RECT kCardRect     = { 76,  78, 724, 522};
const RECT kCardCloseBtn = {668,  94, 704, 124};
const RECT kCardBodyClip = {104, 152, 692, 462};
const RECT kCardEncycBtn = {104, 468, 286, 502};
const RECT kCardAudioBtn = {296, 468, 456, 502};
const RECT kCardPrevArt  = {296, 468, 384, 502};
const RECT kCardNextArt  = {392, 468, 480, 502};
const RECT kCardOkBtn    = {594, 468, 696, 502};

const RECT kEncycTabs[kNumEncycTabs] = {
    {276,  42, 357,  76},
    {361,  42, 442,  76},
    {446,  42, 527,  76},
    {531,  42, 612,  76},
    {616,  42, 697,  76},
    {701,  42, 782,  76},
};
const RECT kTitleCmBtn     = {515, 501, 699, 539};
const RECT kExtrasCmBtn    = {515, 462, 699, 500};
const RECT kEncycLeftBox   = { 24, 118, 274, 492};
const RECT kEncycRightBox  = {282, 116, 778, 492};
const RECT kEncycAudioBtn  = {584, 138, 750, 168};
const RECT kEncycUnlockBtn = {362, 540, 518, 576};
const RECT kEncycChartBtn  = {526, 540, 668, 576};
const RECT kEncycCloseBtn  = {676, 540, 778, 576};
const RECT kFullScreen     = {  0,   0, 800, 600};

bool ptIn(const RECT& r, POINT p) { return p.x >= r.left && p.x < r.right && p.y >= r.top && p.y < r.bottom; }
RECT inflateR(RECT r, int dx, int dy) { r.left -= dx; r.top -= dy; r.right += dx; r.bottom += dy; return r; }
RECT uniteR(const RECT& a, const RECT& b) {
    if (a.right <= a.left) return b;
    if (b.right <= b.left) return a;
    return RECT{std::min(a.left, b.left), std::min(a.top, b.top), std::max(a.right, b.right), std::max(a.bottom, b.bottom)};
}
RECT logToPhys(const Layout& L, const RECT& r) {
    return RECT{
        L.ox + (int)std::floor(r.left * (L.cw / 800.0)),
        L.oy + (int)std::floor(r.top * (L.ch / 600.0)),
        L.ox + (int)std::ceil(r.right * (L.cw / 800.0)),
        L.oy + (int)std::ceil(r.bottom * (L.ch / 600.0)),
    };
}

void invalidateAll() { Present_InvalidateLogical(kFullScreen); }

int titleMenuKind(CommentaryFrame& frame) {
    if (!gLoaded || !frame.enabled || frame.encycOpen || frame.cardKind != CardKind::None) return 0;
    if (screensOpen() || ChartIsOpen() || EV(kHidden)) return 0;
    // 타이틀에서 「이어하기」(또는 특전의 감상 화면)를 고르면 엔진은 게임 화면을 통째로 내리고(0x4151c0 — 대본 스레드도 끝냄)
    // 다른 화면을 띄운다. 그때도 대본 객체에는 메뉴 대기 자리의 pc 가 남아 있어 단추가 그 화면 위에 그려지고 눌렸다.
    // 메뉴가 떠 있는 동안에는 대본 스레드가 메뉴 명령(0x49) 안에서 살아 있으므로 그것으로 가린다. (2026-11-28)
    if (!EV(kVmAlive)) return 0;
    void* sc = *(void* volatile*)0x46639c;
    if (!sc) return 0;
    __try {
        uint8_t* base = *(uint8_t**)sc;
        uint8_t* cur  = *(uint8_t**)((uint8_t*)sc + 0x44);
        uint16_t sid  = *(uint16_t*)((uint8_t*)sc + 0x3c);
        if (sid != 1 || !base || cur < base) return 0;
        uint32_t pc = (uint32_t)(cur - base);
        if (pc >= 488 && pc <= 500) return 1;   // 타이틀 본 메뉴 OP_0049 대기
        if (pc >= 926 && pc <= 938) return 2;   // 특전 하위 메뉴 OP_0049 대기
    } __except (EXCEPTION_EXECUTE_HANDLER) {}
    return 0;
}

RECT titleMenuBtnRect(int tmk) {
    return (tmk == 2) ? kExtrasCmBtn : kTitleCmBtn;
}

bool gameplayHudVisible(CommentaryFrame& frame) {
    if (!gLoaded || !frame.enabled || !History_WindowAvailable() || Play_GuideOpen()) return false;
    if (frame.encycOpen || screensOpen() || ChartIsOpen() || EV(kHidden) || History_Open() || skipping()) return false;
    int ts = topScript();
    if (ts <= 1 || (ts >= 200 && ts <= 499)) return false;
    return true;
}

bool choiceActiveNow(CommentaryFrame& frame) {
    return (EV(kChoiceBox) || frame.inChoiceOp) && frame.activeChoiceEntry >= 0;
}

bool goldenForFrame(CommentaryFrame& frame) {
    bool ok = Present_Active() && gLoaded && frame.enabled && History_WindowAvailable() && !Play_GuideOpen() && !frame.encycOpen && !screensOpen() && !ChartIsOpen() &&
              !EV(kHidden) && !History_Open() && !skipping() && !EV(kSelect) && !choiceActiveNow(frame);
    if (ok) {
        int ts = topScript();
        if (ts <= 1 || (ts >= 200 && ts <= 499) || (ts >= 1000 && ts < 2000) || frame.lineSid != ts ||
            frame.activeLineEntry < 0 || frame.activeLineEntry >= (int)gEntries.size() || (!frame.lineAfterOk && !frame.unlockAll)) {
            ok = false;
        }
    }
    return ok;
}

void updateGoldenAtom(CommentaryFrame& frame) {
    gGoldenLineAtom.store(goldenForFrame(frame), std::memory_order_relaxed);
}

bool activeLineReady(CommentaryFrame& frame) {
    return goldenForFrame(frame);
}

bool getSubPillRect(CommentaryFrame& frame, RECT& out) {
    if (frame.activeSubEntry < 0) return false;
    RECT sb{};
    if (HiText_SubtitleBounds(sb)) {
        int pw = 166, ph = 28;
        int x = std::max(18, std::min(800 - pw - 18, (int)((sb.left + sb.right) / 2 - pw / 2)));
        int y = (sb.bottom + 36 <= 425) ? (sb.bottom + 6) : std::max(44, (int)sb.top - ph - 6);
        out = RECT{x, y, x + pw, y + ph};
        return true;
    }
    out = RECT{317, 334, 483, 362};
    return true;
}

// 세대 번호(HiArt_Epoch)가 바뀌었을 때만 그림 층을 다시 읽는다(평소 0ns)
void refreshLiveMedia(CommentaryFrame& frame, bool force = false) {
    if (!gLoaded) return;
    int trk = frame.previewingBgm ? frame.savedSceneBgm : liveBgmTrack();
    uint32_t ep = HiArt_Epoch();
    if (!force && ep == gLastArtEpoch && trk == gLastBgmTrack) return;

    bool changed = (trk != gLastBgmTrack);
    gLastBgmTrack = trk;
    gLastArtEpoch = ep;

    if (trk > 0 && gBgmByTrack.count(trk)) {
        EnterCriticalSection(&gStateCs);
        if (gSeenBgm.insert(trk).second) { ++gUnlockGeneration; gProgressDirty.store(true); }
        LeaveCriticalSection(&gStateCs);
    }
    std::vector<VisibleArtLayer> layers;
    HiArt_GetVisibleLayers(layers);
    std::vector<int> found;
    std::string sig;
    for (auto& vl : layers) {
        auto it = gArtByAsset.find(vl.asset);
        if (it != gArtByAsset.end() && std::find(found.begin(), found.end(), it->second) == found.end()) {
            found.push_back(it->second);
            sig += vl.asset + ";";
            EnterCriticalSection(&gStateCs);
            if (gSeenArt.insert(vl.asset).second) { ++gUnlockGeneration; gProgressDirty.store(true); }
            LeaveCriticalSection(&gStateCs);
        }
    }
    if (sig != gLastArtSig) {
        bool hadNew = !found.empty() && sig != gLastArtSig;
        gLastArtSig = sig;
        frame.visibleArt = std::make_shared<const std::vector<int>>(std::move(found));
        if (hadNew) frame.artBreathStart = GetTickCount();
        changed = true;
    }
    if (changed && frame.enabled) {
        Present_InvalidateLogical(uniteR(kQbarRect, kArtSealRect));
    }
}

const BgmCue* matchSceneCue(CommentaryFrame& frame, const BgmEntry& bm) {
    const BgmCue* best = nullptr;
    for (auto& c : bm.cues) {
        if (c.sid == frame.curSid && (uint32_t)c.pc <= frame.curPc + 64) {
            if (!best || c.pc >= best->pc) best = &c;
        }
    }
    if (!best) for (auto& c : bm.cues) if (c.sid == frame.curSid) return &c;
    return best;
}

struct EncycList {
    size_t count = 0;
    std::vector<int> scene;
    size_t size() const { return count + scene.size(); }
    bool empty() const { return size() == 0; }
    int operator[](int i) const { return scene.empty() ? i : scene[i]; }
};

EncycList currentEncycList(CommentaryFrame& frame) {
    EncycList result;
    const size_t counts[] = {gArticles.size(), gEntries.size(), gArts.size(), gBgms.size(), gReviews.size()};
    if (frame.encycTab >= 0 && frame.encycTab < 5) result.count = counts[frame.encycTab];
    if (frame.encycTab == 5) {
        auto& list = result.scene;
        if (frame.activeLineEntry >= 0) list.push_back(0x10000 | frame.activeLineEntry);
        else if (frame.prevLineEntry >= 0) list.push_back(0x10000 | frame.prevLineEntry);
        if (frame.activeSubEntry >= 0) list.push_back(0x10000 | frame.activeSubEntry);
        if (frame.activeChoiceEntry >= 0) list.push_back(0x10000 | frame.activeChoiceEntry);
        for (int ai : frame.artIndices()) list.push_back(0x20000 | ai);
        int trk = frame.encycOpen ? frame.savedSceneBgm : liveBgmTrack();
        if (gBgmByTrack.count(trk)) list.push_back(0x30000 | gBgmByTrack[trk]);
    }
    return result;
}

// 이산 HoverId 계산 및 해당 위젯의 논리 사각형 반환
int listOffset(CommentaryFrame& frame) {
    int count = (int)currentEncycList(frame).size();
    int limit = std::max(0, count * 46 - (int)(kEncycLeftBox.bottom - kEncycLeftBox.top));
    return std::clamp(frame.encycListScroll, 0, limit);
}

RECT modalControlRect(CommentaryFrame& frame, int id) {
    if (id >= HovCardClose && id <= HovCardOk) {
        const RECT buttons[] = {kCardCloseBtn, kCardEncycBtn, kCardAudioBtn, kCardPrevArt, kCardNextArt, kCardOkBtn};
        return inflateR(buttons[id - HovCardClose], 12, 8);
    }
    if (id >= HovEncycTab0 && id <= HovEncycTab5) return inflateR(kEncycTabs[id - HovEncycTab0], 12, 8);
    if (id >= HovEncycAudio && id <= HovEncycClose) {
        const RECT buttons[] = {kEncycAudioBtn, kEncycUnlockBtn, kEncycChartBtn, kEncycCloseBtn};
        return inflateR(buttons[id - HovEncycAudio], 12, 8);
    }
    if (id >= HovEncycRowBase) {
        int y = kEncycLeftBox.top + (id - HovEncycRowBase) * 46 - listOffset(frame);
        RECT visible{}, row{kEncycLeftBox.left, y, kEncycLeftBox.right, y + 46};
        IntersectRect(&visible, &row, &kEncycLeftBox);
        return visible;
    }
    return {};
}

int computeHoverId(CommentaryFrame& frame, RECT* outRect = nullptr) {
    auto setR = [&](const RECT& r, int id) { if (outRect) *outRect = r; return id; };
    if (outRect) *outRect = {};

    if (settingsRowVisible()) {
        if (ptIn(kConfOnRect, frame.mouse))  return setR(kConfRowRect, HovConfOn);
        if (ptIn(kConfOffRect, frame.mouse)) return setR(kConfRowRect, HovConfOff);
        return HovNone;
    }
    if (frame.encycOpen) {
        for (int i = 0; i < kNumEncycTabs; ++i) if (ptIn(kEncycTabs[i], frame.mouse)) return setR(kEncycTabs[i], HovEncycTab0 + i);
        if (ptIn(kEncycUnlockBtn, frame.mouse)) return setR(kEncycUnlockBtn, HovEncycUnlock);
        if (ptIn(kEncycChartBtn, frame.mouse))  return setR(kEncycChartBtn, HovEncycChart);
        if (ptIn(kEncycCloseBtn, frame.mouse))  return setR(kEncycCloseBtn, HovEncycClose);
        if (ptIn(kEncycAudioBtn, frame.mouse)) {
            auto list = currentEncycList(frame);
            if (frame.encycSel >= 0 && frame.encycSel < (int)list.size()) {
                const int raw = list[frame.encycSel];
                const int type = frame.encycTab == 5 ? raw >> 16 : (frame.encycTab == 1 ? 1 : frame.encycTab == 3 ? 3 : 0);
                const int idx = frame.encycTab == 5 ? raw & 0xffff : raw;
                if ((type == 1 && isEntryUnlocked(frame, idx) && gEntries[idx].voice > 0) ||
                    (type == 3 && isBgmUnlocked(frame, idx))) return setR(kEncycAudioBtn, HovEncycAudio);
            }
        }
        if (ptIn(kEncycLeftBox, frame.mouse)) {
            int idx = (frame.mouse.y - kEncycLeftBox.top + listOffset(frame)) / 46;
            if (idx >= 0 && idx < (int)currentEncycList(frame).size()) return setR(kEncycLeftBox, HovEncycRowBase + idx);
        }
        return HovNone;
    }
    if (frame.cardKind != CardKind::None) {
        if (ptIn(kCardCloseBtn, frame.mouse)) return setR(kCardCloseBtn, HovCardClose);
        if (ptIn(kCardEncycBtn, frame.mouse)) return setR(kCardEncycBtn, HovCardEncyc);
        if (ptIn(kCardOkBtn, frame.mouse))    return setR(kCardOkBtn, HovCardOk);
        bool hasCardAudio = (frame.cardKind == CardKind::Bgm) ||
                            (frame.cardKind == CardKind::Text && frame.cardIdx >= 0 && frame.cardIdx < (int)gEntries.size() && gEntries[frame.cardIdx].voice > 0);
        if (hasCardAudio && ptIn(kCardAudioBtn, frame.mouse)) return setR(kCardAudioBtn, HovCardAudio);
        if (frame.cardKind == CardKind::Art && frame.artIndices().size() > 1) {
            if (ptIn(kCardPrevArt, frame.mouse)) return setR(kCardPrevArt, HovCardPrev);
            if (ptIn(kCardNextArt, frame.mouse)) return setR(kCardNextArt, HovCardNext);
        }
        return HovNone;
    }
    if (int tmk = titleMenuKind(frame)) {
        RECT br = titleMenuBtnRect(tmk);
        if (ptIn(br, frame.mouse)) return setR(inflateR(br, 14, 8), HovTitleCmBtn);
        return HovNone;
    }
    if (!gameplayHudVisible(frame)) return HovNone;

    if (ptIn(kBookRect, frame.mouse)) return setR(kBookRect, HovBook);
    if (frame.qbarOpen && ptIn(kQbarRect, frame.mouse)) {
        if (ptIn(kQbarModeBtn, frame.mouse))  return setR(kQbarRect, HovQMode);
        if (ptIn(kQbarArtBtn, frame.mouse))   return setR(kQbarRect, HovQArt);
        if (ptIn(kQbarBgmBtn, frame.mouse))   return setR(kQbarRect, HovQBgm);
        if (ptIn(kQbarEncycBtn, frame.mouse)) return setR(kQbarRect, HovQEncyc);
    }
    if (!frame.artIndices().empty() && ptIn(kArtSealRect, frame.mouse)) return setR(inflateR(kArtSealRect, 12, 8), HovArtSeal);
    if (choiceActiveNow(frame) && ptIn(kChoicePill, frame.mouse)) return setR(inflateR(kChoicePill, 12, 8), HovChoicePill);
    RECT subPill{};
    if (frame.activeSubEntry >= 0 && getSubPillRect(frame, subPill) && ptIn(subPill, frame.mouse)) return setR(inflateR(subPill, 12, 8), HovSubPill);

    if (activeLineReady(frame)) {
        if (ptIn(kLinePillRect, frame.mouse)) return setR(inflateR(kLinePillRect, 12, 8), HovLinePill);
        if (!autoOn() && frame.guideMode == 1 && ptIn(kOnePlateRect, frame.mouse)) return setR(kOnePlateRect, HovPlate);
        if (!autoOn() && frame.guideMode == 2 && ptIn(kDetPlateRect, frame.mouse)) return setR(kDetPlateRect, HovPlate);
        if (frame.mouse.y >= 415 && frame.mouse.y <= 592) {
            RECT dlg{};
            if (HiText_DialogueBounds(dlg) && ptIn(inflateR(dlg, 6, 4), frame.mouse))
                return setR(uniteR(inflateR(dlg, 8, 8), inflateR(kLinePillRect, 12, 8)), HovGoldenText);
        }
    }
    return HovNone;
}

// ---------------------------------------------------------------- 카드·도감 열기/닫기
void stopVoicePreview(CommentaryFrame& frame) {
    if (frame.previewingVoice != 0) {
        stopEngineVoice();
        frame.previewingVoice = 0;
    }
}

void toggleVoicePreview(CommentaryFrame& frame, int vid) {
    if (vid <= 0) return;
    if (frame.previewingVoice == vid && isVoiceChannelPlaying()) {
        stopVoicePreview(frame);
    } else {
        playEngineVoice(vid);
        frame.previewingVoice = vid;
    }
}

void stopAudioPreviewAndRestore(CommentaryFrame& frame) {
    stopVoicePreview(frame);
    if (frame.previewingBgm != 0) {
        frame.previewingBgm = 0;
        playEngineBgm(frame.savedSceneBgm, 1);
    }
}

void closeCard(CommentaryFrame& frame) {
    if (frame.cardKind == CardKind::None) return;
    stopAudioPreviewAndRestore(frame);
    if (frame.cardKind == CardKind::Text && frame.cardIdx == frame.activeLineEntry) frame.viewedSerial = frame.lineSerial;
    frame.cardKind = CardKind::None;
    frame.cardIdx = -1;
    frame.cardScroll = 0; gCardMaxScroll.store(0);
    updateGoldenAtom(frame);
    invalidateAll();
}

void openCard(CommentaryFrame& frame, CardKind kind, int idx) {
    if (kind == CardKind::None || idx < 0) return;
    stopVoicePreview(frame);
    if (frame.previewingBgm == 0) frame.savedSceneBgm = liveBgmTrack();
    frame.cardKind = kind;
    frame.cardIdx = idx;
    frame.cardArtCursor = 0;
    frame.cardScroll = 0; gCardMaxScroll.store(0);
    if (kind == CardKind::Text && idx >= 0 && idx < (int)gEntries.size()) {
        EnterCriticalSection(&gStateCs);
        if (gSeenEntries.insert(gEntries[idx].id).second) { ++gUnlockGeneration; gProgressDirty.store(true); }
        LeaveCriticalSection(&gStateCs);
        saveUserState(frame);
    }
    invalidateAll();
}

void openEncyclopedia(CommentaryFrame& frame, int tab = -1, int selectIdx = 0) {
    stopVoicePreview(frame);
    refreshLiveMedia(frame, true);
    if (!frame.encycOpen && frame.previewingBgm == 0) frame.savedSceneBgm = liveBgmTrack();
    // 카드에서 도감으로 넘어가도(F7·카드의 「도감」 단추) 그 줄의 카드는 본 것이다 — closeCard 와 같은 표시를 남긴다.
    // 안 남기면 도감을 닫은 뒤 대사를 누를 때 진행 대신 같은 카드가 또 열린다. (2026-11-28)
    if (frame.cardKind == CardKind::Text && frame.cardIdx == frame.activeLineEntry) frame.viewedSerial = frame.lineSerial;
    frame.cardKind = CardKind::None;
    frame.encycOpen = true;
    if (tab >= 0 && tab < kNumEncycTabs) frame.encycTab = tab;
    frame.encycSel = std::max(0, selectIdx);
    frame.encycListScroll = std::max(0, (frame.encycSel - 2) * 46);
    frame.encycBodyScroll = 0;
    updateGoldenAtom(frame);
    invalidateAll();
}

void closeEncyclopedia(CommentaryFrame& frame) {
    if (!frame.encycOpen) return;
    stopAudioPreviewAndRestore(frame);
    frame.encycOpen = false;
    updateGoldenAtom(frame);
    invalidateAll();
}

// ---------------------------------------------------------------- 고속 DIB 캐시 표면(CachedLayer)
struct CachedLayer {
    HDC dc = nullptr; HBITMAP bmp = nullptr; uint32_t* bits = nullptr;
    int w = 0, h = 0;
    std::wstring key;
    ~CachedLayer() { if (dc) DeleteDC(dc); if (bmp) DeleteObject(bmp); }
    bool prepare(int W, int H, const std::wstring& wantKey, bool& needsRedraw) {
        if (bmp && w == W && h == H && key == wantKey) {
            needsRedraw = false;
            return true;
        }
        if (!bmp || w != W || h != H) {
            if (dc) { DeleteDC(dc); dc = nullptr; }
            if (bmp) { DeleteObject(bmp); bmp = nullptr; bits = nullptr; }
            BITMAPINFO bi{}; bi.bmiHeader.biSize = sizeof(bi.bmiHeader);
            bi.bmiHeader.biWidth = W; bi.bmiHeader.biHeight = -H; bi.bmiHeader.biPlanes = 1; bi.bmiHeader.biBitCount = 32;
            void* p = nullptr;
            bmp = CreateDIBSection(nullptr, &bi, DIB_RGB_COLORS, &p, nullptr, 0);
            if (!bmp) return false;
            dc = CreateCompatibleDC(nullptr);
            SelectObject(dc, bmp);
            bits = (uint32_t*)p; w = W; h = H;
        }
        memset(bits, 0, (size_t)W * H * 4);
        key = wantKey;
        needsRedraw = true;
        return true;
    }
};

CachedLayer gConfLayer, gTitleLayer, gHudLayer, gCardLayer, gEncycLayer;

// The full DIB contains the last committed modal frame. Restore the changed
// pixels from the original layers before drawing controls in their usual order.
struct ModalState {
    int hover = HovNone, listScroll = 0, bodyScroll = 0;
    RECT hoverRect{};
};
ModalState gCardPaint, gBookPaint;

struct ModalDamage {
    bool full;
    std::vector<RECT> parts;
    explicit ModalDamage(bool redraw) : full(redraw) {}
    void add(const RECT& r) { if (!full && !IsRectEmpty(&r)) parts.push_back(r); }
    bool hits(const RECT& r) const {
        if (full) return true;
        RECT hit{};
        for (const RECT& part : parts) if (IntersectRect(&hit, &r, &part)) return true;
        return false;
    }
    void trackHover(CommentaryFrame& frame, ModalState& last) {
        RECT now = modalControlRect(frame, frame.hoverId);
        if (frame.hoverId != last.hover || !EqualRect(&now, &last.hoverRect)) {
            add(last.hoverRect); add(now);
        }
        last.hover = frame.hoverId; last.hoverRect = now;
    }
    void clip(Graphics& g, CachedLayer& layer) const {
        if (full) return;
        Region area; area.MakeEmpty();
        Layout layout; layout.cw = layer.w; layout.ch = layer.h;
        RECT bounds{0, 0, layer.w, layer.h};
        GdiFlush();
        for (const RECT& part : parts) {
            RECT phys = logToPhys(layout, part), r{};
            if (!IntersectRect(&r, &phys, &bounds)) continue;
            area.Union(Rect(r.left, r.top, r.right-r.left, r.bottom-r.top));
            for (LONG y = r.top; y < r.bottom; ++y)
                std::fill_n(layer.bits + (size_t)y * layer.w + r.left, r.right - r.left, 0u);
        }
        g.SetClip(&area);
    }
};

const Color COL_INK(255, 52, 31, 12);
const Color COL_INK_MID(255, 92, 60, 26);
const Color COL_INK_SOFT(225, 122, 86, 44);
const Color COL_CREAM(255, 246, 238, 214);
const Color COL_GOLD(255, 255, 228, 138);
const Color COL_RULE(135, 112, 76, 34);

Font makeFont(const FontFamily* fam, float px, int style = FontStyleRegular) {
    return Font(fam ? fam : gFamSerif, px, style, UnitPixel);
}

void drawTextLine(Graphics& g, const std::wstring& s, float x, float y, float px, bool bold, Color col, int align = 0, const FontFamily* fam = nullptr, float width = 0.f) {
    Font f = makeFont(fam ? fam : (bold ? gFamHeading : gFamSerif), px, fam && bold ? FontStyleBold : FontStyleRegular);
    StringFormat sf(StringFormat::GenericTypographic());
    sf.SetFormatFlags(StringFormatFlagsNoWrap);
    if (align == 1) sf.SetAlignment(StringAlignmentCenter);
    else if (align == 2) sf.SetAlignment(StringAlignmentFar);
    SolidBrush b(col);
    if (width > 0.f) {
        sf.SetFormatFlags(StringFormatFlagsNoWrap);
        sf.SetTrimming(StringTrimmingEllipsisCharacter);
        g.DrawString(s.c_str(), -1, &f, RectF(x, y, width, px * 1.8f), &sf, &b);
    } else g.DrawString(s.c_str(), -1, &f, PointF(x, y), &sf, &b);
}

void drawShadowText(Graphics& g, const std::wstring& s, float x, float y, float px, bool bold, Color col, int align = 0) {
    drawTextLine(g, s, x + 1.0f, y + 1.0f, px, bold, Color(195, 14, 10, 6), align);
    drawTextLine(g, s, x, y, px, bold, col, align);
}

float drawWrapped(Graphics& g, const std::wstring& s, float x, float y, float w, float px, float lineGap, Color col, bool bold = false, const FontFamily* fam = nullptr, bool dryRun = false) {
    if (s.empty()) return 0.f;
    Font f = makeFont(fam ? fam : gFamSerif, px, bold ? FontStyleBold : FontStyleRegular);
    StringFormat sf(StringFormat::GenericDefault());
    SolidBrush br(col);
    float curY = y;
    size_t p = 0;
    while (p <= s.size()) {
        size_t e = s.find(L'\n', p);
        std::wstring para = (e == std::wstring::npos) ? s.substr(p) : s.substr(p, e - p);
        if (para.empty()) {
            curY += px * 0.55f;
        } else {
            RectF layout(x, curY, w, 4000.f), bound;
            g.MeasureString(para.c_str(), -1, &f, layout, &sf, &bound);
            if (!dryRun) g.DrawString(para.c_str(), -1, &f, RectF(x, curY, w, bound.Height + 6.f), &sf, &br);
            curY += bound.Height + lineGap;
        }
        if (e == std::wstring::npos) break;
        p = e + 1;
    }
    return curY - y;
}

void drawOvalPill(Graphics& g, const RECT& r, const std::wstring& label, bool green, bool hovered, float fontPx = 13.5f) {
    float x = (float)r.left, y = (float)r.top, w = (float)(r.right - r.left), h = (float)(r.bottom - r.top);
    if (hovered) {
        Bitmap* gl = green ? UI.glowGreen : UI.glowGold;
        if (gl) g.DrawImage(gl, RectF(x - 10, y - 6, w + 20, h + 12));
    }
    Bitmap* bg = green ? UI.ovalGreen : UI.ovalBrown;
    if (bg) g.DrawImage(bg, RectF(x, y, w, h));
    Color tc = hovered ? Color(255, 255, 248, 205) : (green ? Color(255, 228, 250, 208) : COL_GOLD);
    drawShadowText(g, label, x + w * 0.5f, y + (h - fontPx) * 0.5f - 1.f, fontPx, true, tc, 1);
}

std::wstring truncOneLine(const std::wstring& s, size_t maxChars) {
    std::wstring t;
    for (wchar_t c : s) t += (c == L'\n' || c == L'\r') ? L' ' : c;
    return (t.size() <= maxChars) ? t : (t.substr(0, maxChars - 1) + L"…");
}

// 사전 스케일된 비트맵을 물리 좌표(1:1 무변환)로 먼저 찍어 속도를 극대화하는 헬퍼
void drawPrescaled(Graphics& gPhys, Bitmap* pre, int px, int py) {
    if (!pre) return;
    gPhys.DrawImage(pre, px, py);
}

// ---------------------------------------------------------------- 공통 본문 블록 렌더러 + 높이 메모이제이션
float renderDetailContent(CommentaryFrame& frame, Graphics& g, float x, float y, float w, CardKind kind, int idx, bool dryRun) {
    uint32_t memoKey = ((uint32_t)kind << 24) | ((frame.unlockAll ? 1u : 0u) << 23) | ((uint32_t)(idx & 0x7FFFFF)) | ((w > 500.f ? 1u : 0u) << 22);
    if (dryRun && kind != CardKind::Bgm) {
        auto it = gHeightMemo.find(memoKey);
        if (it != gHeightMemo.end()) return it->second;
    }

    float cur = y;
    auto rule = [&](float ry) { if (!dryRun) { Pen p(COL_RULE, 1.f); g.DrawLine(&p, x, ry, x + w, ry); } };
    auto renderEcho = [&](const std::wstring& echo) {
        if (echo.empty()) return;
        cur += 8.f; rule(cur); cur += 10.f;
        if (frame.unlockAll) {
            float eh = drawWrapped(g, echo, x + 12.f, cur + 28.f, w - 24.f, 13.2f, 4.f, COL_INK, false, nullptr, true) + 36.f;
            if (!dryRun) {
                SolidBrush eb(Color(42, 62, 108, 48)); Pen ep(Color(120, 72, 118, 56), 1.f);
                g.FillRectangle(&eb, x, cur, w, eh); g.DrawRectangle(&ep, x, cur, w, eh);
                drawTextLine(g, L"✦ 복선과 메아리 (전체 열기 해금)", x + 12.f, cur + 7.f, 13.f, true, Color(255, 42, 88, 34));
                drawWrapped(g, echo, x + 12.f, cur + 28.f, w - 24.f, 13.2f, 4.f, COL_INK, false, nullptr, false);
            }
            cur += eh + 6.f;
        } else {
            if (!dryRun) {
                SolidBrush lb(Color(34, 96, 68, 32));
                g.FillRectangle(&lb, x, cur, w, 32.f);
                drawTextLine(g, L"※ 후속 장 복선과 메아리 — 해설 도감(F7)의 「전체 열기」를 켜면 열람됩니다.", x + 10.f, cur + 8.f, 12.3f, false, COL_INK_MID);
            }
            cur += 38.f;
        }
    };

    auto renderExtPlate = [&](const std::string& extImg, const std::wstring& extCap) {
        Bitmap* eb = getExtThumb(extImg);
        if (!eb) return;
        float maxW = (kind == CardKind::Article) ? 236.f : 204.f;
        float maxH = (kind == CardKind::Article) ? 156.f : 122.f;
        float r = std::min(1.f, std::min(maxW / eb->GetWidth(), maxH / eb->GetHeight()));
        float tw = eb->GetWidth() * r, th = eb->GetHeight() * r;
        if (!dryRun) {
            SolidBrush fb(Color(210, 48, 32, 16));
            Pen fp(COL_RULE, 1.f);
            float fx = x + (w - tw) * 0.5f;
            g.FillRectangle(&fb, fx - 4.f, cur, tw + 8.f, th + 8.f);
            g.DrawImage(eb, RectF(fx, cur + 4.f, tw, th));
            g.DrawRectangle(&fp, fx - 5.f, cur - 1.f, tw + 10.f, th + 10.f);
        }
        cur += th + 12.f;
        if (!extCap.empty()) {
            cur += drawWrapped(g, extCap, x + 8.f, cur, w - 16.f, 11.6f, 2.f, COL_INK_MID, false, nullptr, dryRun) + 8.f;
        } else {
            cur += 6.f;
        }
    };

    if (kind == CardKind::Text && idx >= 0 && idx < (int)gEntries.size()) {
        const auto& e = gEntries[idx];
        std::wstring jaTag = (e.modal == L"sub") ? L"원문 음성: " : L"원문: ";
        float qh = 12.f;
        if (!e.ja.empty()) qh += drawWrapped(g, jaTag + e.ja, x + 12.f, cur + qh, w - 24.f, 13.2f, 3.f, COL_INK, false, gFamJa, true) + 4.f;
        qh += drawWrapped(g, e.ko, x + 12.f, cur + qh, w - 24.f, 13.5f, 3.f, COL_INK, true, nullptr, true) + 8.f;
        if (!dryRun) {
            SolidBrush qb(Color(46, 118, 84, 38)); Pen qp(Color(115, 118, 84, 38), 1.f);
            g.FillRectangle(&qb, x, cur, w, qh); g.DrawRectangle(&qp, x, cur, w, qh);
            float iy = cur + 8.f;
            if (!e.ja.empty()) iy += drawWrapped(g, jaTag + e.ja, x + 12.f, iy, w - 24.f, 13.2f, 3.f, Color(255, 78, 46, 16), false, gFamJa, false) + 4.f;
            drawWrapped(g, e.ko, x + 12.f, iy, w - 24.f, 13.5f, 3.f, COL_INK, true, nullptr, false);
        }
        cur += qh + 12.f;
        if (!e.extImg.empty()) renderExtPlate(e.extImg, e.extCaption);
        cur += drawWrapped(g, e.body, x, cur, w, 14.2f, 6.f, COL_INK, false, nullptr, dryRun);
        cur += 8.f; rule(cur); cur += 8.f;
        cur += drawWrapped(g, L"출처 · 근거: " + e.source, x, cur, w, 12.6f, 3.f, COL_INK_MID, false, nullptr, dryRun);
        renderEcho(e.echo);
    } else if (kind == CardKind::Art && idx >= 0 && idx < (int)gArts.size()) {
        const auto& a = gArts[idx];
        Bitmap* thumb = getArtThumb(a);
        if (thumb) {
            float tw = 216.f, th = 162.f;
            if (!dryRun) {
                SolidBrush fb(Color(220, 32, 22, 12));
                g.FillRectangle(&fb, x + (w - tw) * 0.5f - 4.f, cur - 2.f, tw + 8.f, th + 8.f);
                g.DrawImage(thumb, RectF(x + (w - tw) * 0.5f, cur + 2.f, tw, th));
            }
            cur += th + 14.f;
        }
        cur += drawWrapped(g, a.body, x, cur, w, 14.2f, 6.f, COL_INK, false, nullptr, dryRun);
        cur += 8.f; rule(cur); cur += 8.f;
        cur += drawWrapped(g, L"도상 정보: " + a.source, x, cur, w, 12.6f, 3.f, COL_INK_MID, false, nullptr, dryRun);
        renderEcho(a.echo);
    } else if (kind == CardKind::Bgm && idx >= 0 && idx < (int)gBgms.size()) {
        const auto& m = gBgms[idx];
        std::wstring meta = L"한국어 곡명: " + m.koTitle +
                            (m.jaTitle.empty() ? L"" : L"   ｜   원제: " + m.jaTitle) +
                            (m.enTitle.empty() ? L"" : L"   ｜   영문: " + m.enTitle);
        cur += drawWrapped(g, meta, x, cur, w, 13.f, 4.f, COL_INK_MID, true, nullptr, dryRun) + 6.f;
        if (const BgmCue* cue = matchSceneCue(frame, m)) {
            std::wstring ct = L"[이 장면의 선율 연출 — " + cue->cueTitle + L"]\n" + cue->cueNote;
            float ch = drawWrapped(g, ct, x + 12.f, cur + 8.f, w - 24.f, 13.3f, 4.f, COL_INK, false, nullptr, true) + 16.f;
            if (!dryRun) {
                SolidBrush cb(Color(48, 72, 108, 48)); Pen cp(Color(125, 76, 114, 52), 1.f);
                g.FillRectangle(&cb, x, cur, w, ch); g.DrawRectangle(&cp, x, cur, w, ch);
                drawWrapped(g, ct, x + 12.f, cur + 8.f, w - 24.f, 13.3f, 4.f, COL_INK, false, nullptr, false);
            }
            cur += ch + 12.f;
        }
        cur += drawWrapped(g, m.body, x, cur, w, 14.2f, 6.f, COL_INK, false, nullptr, dryRun);
        cur += 8.f; rule(cur); cur += 8.f;
        cur += drawWrapped(g, L"수록 정보: " + m.source, x, cur, w, 12.6f, 3.f, COL_INK_MID, false, nullptr, dryRun);
        renderEcho(m.echo);
    } else if (kind == CardKind::Article && idx >= 0 && idx < (int)gArticles.size()) {
        const auto& a = gArticles[idx];
        cur += drawWrapped(g, a.oneliner, x, cur, w, 13.8f, 5.f, COL_INK_MID, true, nullptr, dryRun) + 8.f;
        rule(cur); cur += 10.f;
        if (!a.extImg.empty()) renderExtPlate(a.extImg, a.extCaption);
        cur += drawWrapped(g, a.body, x, cur, w, 14.2f, 6.f, COL_INK, false, nullptr, dryRun);
        cur += 8.f; rule(cur); cur += 8.f;
        cur += drawWrapped(g, L"참조 · 출전: " + a.source, x, cur, w, 12.6f, 3.f, COL_INK_MID, false, nullptr, dryRun);
        renderEcho(a.echo);
    } else if (kind == CardKind::Review && idx >= 0 && idx < (int)gReviews.size()) {
        const auto& rv = gReviews[idx];
        cur += drawWrapped(g, rv.oneliner, x, cur, w, 13.6f, 5.f, COL_INK_MID, true, nullptr, dryRun) + 8.f;
        bool hasCjk = false;
        for (wchar_t c : rv.quoteOrig) if (c >= 0x3000) { hasCjk = true; break; }
        const FontFamily* qFam = hasCjk ? gFamJa : gFamSerif;
        std::wstring qHead = L"원문 발췌  ·  " + rv.author + L" (" + rv.date + L")";
        float qh = 10.f;
        qh += drawWrapped(g, qHead, x + 12.f, cur + qh, w - 24.f, 11.8f, 3.f, COL_INK_MID, true, nullptr, true) + 3.f;
        if (!rv.quoteOrig.empty()) qh += drawWrapped(g, rv.quoteOrig, x + 12.f, cur + qh, w - 24.f, 13.0f, 3.5f, COL_INK, false, qFam, true) + 4.f;
        qh += drawWrapped(g, L"「" + rv.quoteKo + L"」", x + 12.f, cur + qh, w - 24.f, 13.4f, 3.5f, COL_INK, true, nullptr, true) + 8.f;
        if (!dryRun) {
            SolidBrush qb(Color(46, 118, 84, 38)); Pen qp(Color(115, 118, 84, 38), 1.f);
            g.FillRectangle(&qb, x, cur, w, qh); g.DrawRectangle(&qp, x, cur, w, qh);
            float iy = cur + 8.f;
            iy += drawWrapped(g, qHead, x + 12.f, iy, w - 24.f, 11.8f, 3.f, COL_INK_MID, true, nullptr, false) + 3.f;
            if (!rv.quoteOrig.empty()) iy += drawWrapped(g, rv.quoteOrig, x + 12.f, iy, w - 24.f, 13.0f, 3.5f, Color(255, 78, 46, 16), false, qFam, false) + 4.f;
            drawWrapped(g, L"「" + rv.quoteKo + L"」", x + 12.f, iy, w - 24.f, 13.4f, 3.5f, COL_INK, true, nullptr, false);
        }
        cur += qh + 12.f;
        if (!rv.extImg.empty()) renderExtPlate(rv.extImg, rv.extCaption);
        cur += drawWrapped(g, rv.body, x, cur, w, 14.2f, 6.f, COL_INK, false, nullptr, dryRun);
        cur += 8.f; rule(cur); cur += 8.f;
        cur += drawWrapped(g, L"출전 · 서지: " + rv.source, x, cur, w, 12.6f, 3.f, COL_INK_MID, false, nullptr, dryRun);
        renderEcho(rv.echo);
    }
    float res = cur - y;
    if (dryRun && kind != CardKind::Bgm) gHeightMemo[memoKey] = res;
    return res;
}

// ---------------------------------------------------------------- 캐시된 4대 레이어 렌더러
void buildSettingsLayer(CommentaryFrame& frame, int cw, int ch) {
    bool hovOn  = (frame.hoverId == HovConfOn);
    bool hovOff = (frame.hoverId == HovConfOff);
    wchar_t key[64];
    swprintf_s(key, L"conf|%d|%d|%d", frame.enabled ? 1 : 0, hovOn ? 1 : 0, hovOff ? 1 : 0);
    bool redraw = false;
    const int top = kConfRowRect.top * ch / 600;
    const int height = (kConfRowRect.bottom * ch + 599) / 600 - top;
    if (!gConfLayer.prepare(cw, height, key, redraw) || !redraw) return;

    Bitmap bmp(cw, height, cw * 4, PixelFormat32bppPARGB, (BYTE*)gConfLayer.bits);
    Graphics g(&bmp);
    g.SetInterpolationMode(InterpolationModeBilinear);
    g.TranslateTransform(0.f, (float)-top);
    drawPrescaled(g, SUI.confRow, scX(145, cw), scY(485, ch));

    g.ScaleTransform((REAL)(cw / 800.0), (REAL)(ch / 600.0));
    if (hovOn && !frame.enabled && UI.glowGold) g.DrawImage(UI.glowGold, RectF(335.f, 488.f, 156.f, 35.f));
    if (hovOff && frame.enabled && UI.glowGold) g.DrawImage(UI.glowGold, RectF(489.f, 488.f, 156.f, 35.f));
    Bitmap* bOn  = frame.enabled  ? UI.confOn  : UI.confOnF;
    Bitmap* bOff = !frame.enabled ? UI.confOff : UI.confOffF;
    if (bOn)  g.DrawImage(bOn,  RectF(343.f, 495.f, 140.f, 21.f));
    if (bOff) g.DrawImage(bOff, RectF(497.f, 495.f, 140.f, 21.f));
}

void buildTitleLayer(CommentaryFrame& frame, int cw, int ch, int tmk) {
    bool hov = (frame.hoverId == HovTitleCmBtn);
    wchar_t key[64];
    swprintf_s(key, L"title|%d|%d", tmk, hov ? 1 : 0);
    bool redraw = false;
    if (!gTitleLayer.prepare(cw, ch, key, redraw) || !redraw) return;

    Bitmap bmp(cw, ch, cw * 4, PixelFormat32bppPARGB, (BYTE*)gTitleLayer.bits);
    Graphics g(&bmp);
    g.SetSmoothingMode(SmoothingModeAntiAlias);
    g.SetTextRenderingHint(TextRenderingHintAntiAliasGridFit);
    g.SetInterpolationMode(InterpolationModeHighQualityBicubic);
    g.ScaleTransform((REAL)(cw / 800.0), (REAL)(ch / 600.0));

    RECT br = titleMenuBtnRect(tmk);
    float x = (float)br.left, y = (float)br.top, w = (float)(br.right - br.left), h = (float)(br.bottom - br.top);
    Bitmap* ov = hov ? (UI.titleOvalGreen ? UI.titleOvalGreen : UI.ovalGreen)
                     : (UI.titleOvalBrown ? UI.titleOvalBrown : UI.ovalBrown);
    if (ov) g.DrawImage(ov, RectF(x - 6.f, y, w + 12.f, h));

    Font f = makeFont(gFamSerif, 22.5f, FontStyleBold);
    StringFormat sf(StringFormat::GenericTypographic());
    sf.SetFormatFlags(StringFormatFlagsNoWrap);
    sf.SetAlignment(StringAlignmentCenter);
    const wchar_t* lbl = L"해설 · 평론";
    float tx = x + w * 0.5f, ty = y + (h - 23.5f) * 0.5f - 1.f;
    SolidBrush sh0(Color(165, 10, 4, 0));
    SolidBrush sh1(Color(235, 22, 10, 2));
    g.DrawString(lbl, -1, &f, PointF(tx + 2.2f, ty + 2.2f), &sf, &sh0);
    g.DrawString(lbl, -1, &f, PointF(tx + 1.2f, ty + 1.2f), &sf, &sh1);
    LinearGradientBrush gb(PointF(tx, ty), PointF(tx, ty + 24.f),
                           hov ? Color(255, 255, 255, 210) : Color(255, 255, 252, 134),
                           hov ? Color(255, 214, 250, 108) : Color(255, 238, 198, 60));
    g.DrawString(lbl, -1, &f, PointF(tx, ty), &sf, &gb);
}

void buildHudLayer(CommentaryFrame& frame, int cw, int ch) {
    const bool hasLine   = activeLineReady(frame);
    const bool hasSub    = frame.activeSubEntry >= 0;
    const bool hasChoice = choiceActiveNow(frame);
    const bool hasArt    = !frame.artIndices().empty();
    const int  bgmTrk    = liveBgmTrack();
    const bool hasBgm    = gBgmByTrack.count(bgmTrk) != 0;
    DWORD sinceArt = GetTickCount() - frame.artBreathStart;
    int artPhase = !hasArt ? 0 : (sinceArt < 1200 ? 2 : (sinceArt < 2400 ? 1 : 0));
    RECT subPill{};
    if (hasSub) getSubPillRect(frame, subPill);

    wchar_t key[192];
    swprintf_s(key, L"hud|%d|%d|%d|%d|%d|%d|%zu|%d|%d|%d|%d|%ld,%ld",
               frame.qbarOpen ? 1 : 0, frame.guideMode, autoOn() ? 1 : 0,
               hasLine ? frame.activeLineEntry : -1, hasSub ? frame.activeSubEntry : -1,
               hasChoice ? frame.activeChoiceEntry : -1, frame.artIndices().size(),
               hasArt ? frame.artIndices().back() : -1, artPhase, bgmTrk, frame.hoverId <= HovGoldenText ? frame.hoverId : HovNone,
               subPill.left, subPill.top);
    bool redraw = false;
    if (!gHudLayer.prepare(cw, ch, key, redraw) || !redraw) return;

    Bitmap bmp(cw, ch, cw * 4, PixelFormat32bppPARGB, (BYTE*)gHudLayer.bits);
    Graphics g(&bmp);
    g.SetSmoothingMode(SmoothingModeAntiAlias);
    g.SetTextRenderingHint(TextRenderingHintAntiAliasGridFit);
    g.SetInterpolationMode(InterpolationModeBilinear);

    // 1:1 사전 스케일 양피지 먼저 고속 복사
    if (frame.qbarOpen) drawPrescaled(g, SUI.qbarRibbon, scX(kQbarRect.left, cw), scY(kQbarRect.top, ch));
    if (hasLine && !autoOn()) {
        if (frame.guideMode == 1) drawPrescaled(g, SUI.plateOneliner, scX(98, cw), scY(370, ch));
        else if (frame.guideMode == 2) drawPrescaled(g, SUI.plateDetail, scX(98, cw), scY(314, ch));
    }

    g.ScaleTransform((REAL)(cw / 800.0), (REAL)(ch / 600.0));

    // 오른쪽 위 책갈피
    Bitmap* bk = (frame.hoverId == HovBook) ? UI.bookHover : ((hasLine || hasSub || hasChoice || hasArt) ? UI.bookActive : UI.bookIdle);
    if (bk) g.DrawImage(bk, RectF(760.f, 8.f, 28.f, 22.f));

    if (frame.qbarOpen) {
        static const wchar_t* kModes[3] = {L"표시: 문장", L"표시: 한 줄", L"표시: 자세히"};
        bool hMode  = (frame.hoverId == HovQMode);
        bool hArt   = (frame.hoverId == HovQArt);
        bool hBgm   = (frame.hoverId == HovQBgm);
        bool hEncyc = (frame.hoverId == HovQEncyc);

        drawTextLine(g, kModes[frame.guideMode], 275.f, 14.f, 13.5f, true, hMode ? Color(255, 148, 56, 12) : COL_INK, 1);
        drawTextLine(g, L"｜", 346.f, 14.f, 13.f, false, COL_INK_SOFT, 1);

        wchar_t artLbl[48];
        if (hasArt) swprintf_s(artLbl, L"✦ 그림 %zu", frame.artIndices().size());
        else wcscpy_s(artLbl, L"· 그림 없음");
        if ((hArt || artPhase > 0) && hasArt && UI.glowGold)
            g.DrawImage(UI.glowGold, RectF(352.f, 6.f, 114.f, 34.f));
        drawTextLine(g, artLbl, 409.f, 14.f, 13.5f, hasArt, hasArt ? (hArt ? Color(255, 160, 48, 8) : COL_INK) : COL_INK_SOFT, 1);

        drawTextLine(g, L"｜", 470.f, 14.f, 13.f, false, COL_INK_SOFT, 1);

        std::wstring bgmLbl = L"♪ 무음";
        if (hasBgm) bgmLbl = L"♪ " + truncOneLine(gBgms[gBgmByTrack[bgmTrk]].koTitle, 10);
        else if (bgmTrk > 0) { wchar_t tb[32]; swprintf_s(tb, L"♪ Track %02d", bgmTrk); bgmLbl = tb; }
        drawTextLine(g, bgmLbl, 554.f, 14.f, 13.5f, hasBgm, hasBgm ? (hBgm ? Color(255, 160, 48, 8) : COL_INK) : COL_INK_SOFT, 1);

        drawTextLine(g, L"｜", 638.f, 14.f, 13.f, false, COL_INK_SOFT, 1);
        drawTextLine(g, L"해설 도감 F7", 697.f, 14.f, 13.5f, true, hEncyc ? Color(255, 28, 96, 36) : COL_INK, 1);
    }

    if (hasArt) {
        bool hovSeal = (frame.hoverId == HovArtSeal);
        const ArtEntry& topArt = gArts[frame.artIndices().back()];
        std::wstring sealTxt = L"✦ " + truncOneLine(topArt.category.empty() ? L"도상 해설" : topArt.category + L" 해설", 10);
        if (artPhase > 0 || hovSeal) {
            drawOvalPill(g, kArtSealRect, sealTxt, false, hovSeal || artPhase == 2, 12.5f);
        } else {
            SolidBrush sb(Color(125, 36, 26, 15)); Pen sp(Color(145, 212, 178, 104), 1.f);
            g.FillRectangle(&sb, 16.f, 48.f, 112.f, 24.f); g.DrawRectangle(&sp, 16.f, 48.f, 112.f, 24.f);
            drawTextLine(g, L"✦ 도상 해설", 72.f, 52.f, 12.f, true, Color(215, 245, 224, 156), 1);
        }
    }

    if (hasChoice) {
        const auto& ce = gEntries[frame.activeChoiceEntry];
        drawOvalPill(g, kChoicePill, L"‣ 선택지 해설 · " + truncOneLine(ce.title, 15), true, frame.hoverId == HovChoicePill, 13.5f);
    }
    if (hasSub) {
        const auto& se = gEntries[frame.activeSubEntry];
        drawOvalPill(g, subPill, L"✦ 음성 해설 · " + truncOneLine(se.title, 9), true, frame.hoverId == HovSubPill, 12.5f);
    }
    if (hasLine) {
        const auto& le = gEntries[frame.activeLineEntry];
        drawOvalPill(g, kLinePillRect, L"✦ 해설 보기", false, frame.hoverId == HovLinePill || frame.hoverId == HovGoldenText, 12.5f);
        if (!autoOn() && frame.guideMode == 1) {
            if (frame.hoverId == HovPlate) { Pen hp(Color(165, 170, 96, 24), 1.3f); g.DrawRectangle(&hp, 112.f, 380.f, 576.f, 48.f); }
            drawTextLine(g, L"[" + le.kind + L"]  " + truncOneLine(le.title, 28), 124.f, 381.f, 13.5f, true, COL_INK);
            drawTextLine(g, L"전문 보기 ▸", 676.f, 382.f, 12.f, true, COL_INK_MID, 2);
            drawTextLine(g, truncOneLine(le.oneliner, 44), 124.f, 403.f, 13.f, false, COL_INK_MID);
        } else if (!autoOn() && frame.guideMode == 2) {
            if (frame.hoverId == HovPlate) { Pen hp(Color(165, 170, 96, 24), 1.2f); g.DrawRectangle(&hp, 116.f, 326.f, 568.f, 98.f); }
            drawTextLine(g, L"[" + le.kind + L"]  " + truncOneLine(le.title, 21), 124.f, 328.f, 13.8f, true, COL_INK);
            drawTextLine(g, L"카드 열기 ▸", 674.f, 329.f, 12.f, true, COL_INK_MID, 2);
            if (!le.ja.empty())
                drawTextLine(g, L"원문: " + truncOneLine(le.ja, le.ja.size() + 1), 124.f, 349.f, 12.4f, false, Color(255, 84, 48, 18), 0, gFamJa, 570.f);
            drawWrapped(g, truncOneLine(le.body, 82), 124.f, 369.f, 550.f, 12.6f, 2.5f, COL_INK_MID);
            drawTextLine(g, L"출처: " + truncOneLine(le.source, 42), 124.f, 405.f, 11.6f, false, COL_INK_SOFT);
        }
    }
}

void buildCardLayer(CommentaryFrame& frame, int cw, int ch) {
    int cardHov = (frame.hoverId >= HovCardClose && frame.hoverId <= HovCardOk) ? frame.hoverId : 0;
    int vLive = (frame.previewingVoice != 0 && isVoiceChannelPlaying()) ? frame.previewingVoice : 0;
    wchar_t key[128];
    swprintf_s(key, L"card|%d|%d|%d|%d|%d|%d",
               (int)frame.cardKind, frame.cardIdx, frame.cardArtCursor, frame.previewingBgm, vLive, frame.unlockAll ? 1 : 0);
    bool redraw = false;
    if (!gCardLayer.prepare(cw, ch, key, redraw)) return;
    ModalDamage damage(redraw);
    damage.trackHover(frame, gCardPaint);
    if (gCardPaint.bodyScroll != frame.cardScroll) damage.add(inflateR(kCardBodyClip, 4, 0));
    gCardPaint.bodyScroll = frame.cardScroll;
    if (!damage.full && damage.parts.empty()) return;

    Bitmap bmp(cw, ch, cw * 4, PixelFormat32bppPARGB, (BYTE*)gCardLayer.bits);
    Graphics g(&bmp);
    damage.clip(g, gCardLayer);
    g.SetSmoothingMode(SmoothingModeAntiAlias);
    g.SetTextRenderingHint(TextRenderingHintAntiAliasGridFit);
    g.SetInterpolationMode(InterpolationModeBilinear);

    SolidBrush dim(Color(158, 10, 14, 10));
    g.FillRectangle(&dim, 0, 0, cw, ch);
    drawPrescaled(g, SUI.cardParchment, scX(kCardRect.left, cw), scY(kCardRect.top, ch));

    g.ScaleTransform((REAL)(cw / 800.0), (REAL)(ch / 600.0));

    std::wstring badge, title;
    if (frame.cardKind == CardKind::Text && frame.cardIdx >= 0 && frame.cardIdx < (int)gEntries.size()) {
        const auto& e = gEntries[frame.cardIdx];
        badge = e.kind + L"  ·  " + e.mark + (e.speaker.empty() ? L"" : (L"  ｜  " + e.speaker));
        title = e.title;
    } else if (frame.cardKind == CardKind::Art && frame.cardIdx >= 0 && frame.cardIdx < (int)gArts.size()) {
        const auto& a = gArts[frame.cardIdx];
        badge = a.kind + L"  ·  " + a.mark + L"  ｜  " + a.category;
        title = a.title;
    } else if (frame.cardKind == CardKind::Bgm && frame.cardIdx >= 0 && frame.cardIdx < (int)gBgms.size()) {
        const auto& m = gBgms[frame.cardIdx];
        badge = m.kind + L"  ·  " + m.mark;
        title = m.title;
    } else if (frame.cardKind == CardKind::Article && frame.cardIdx >= 0 && frame.cardIdx < (int)gArticles.size()) {
        const auto& a = gArticles[frame.cardIdx];
        badge = a.kind + L"  ·  " + a.mark;
        title = a.title;
    } else if (frame.cardKind == CardKind::Review && frame.cardIdx >= 0 && frame.cardIdx < (int)gReviews.size()) {
        const auto& rv = gReviews[frame.cardIdx];
        badge = rv.sphere + L"  ·  " + truncOneLine(rv.author, 24) + L" (" + rv.date + L")  ｜  " + rv.mark;
        title = rv.title;
    }

    drawTextLine(g, truncOneLine(badge, 48), 106.f, 100.f, 12.6f, true, COL_INK_MID);
    drawTextLine(g, truncOneLine(title, 34), 106.f, 121.f, 18.f, true, COL_INK);
    Pen hr(COL_RULE, 1.5f);
    g.DrawLine(&hr, 104.f, 147.f, 696.f, 147.f);
    drawTextLine(g, L"✕", 686.f, 100.f, 17.f, true, (cardHov == HovCardClose) ? Color(255, 176, 36, 18) : COL_INK_MID, 1);

    if (damage.hits(inflateR(kCardBodyClip, 4, 0))) {
        float bx = (float)kCardBodyClip.left, by = (float)kCardBodyClip.top;
        float bw = (float)(kCardBodyClip.right - kCardBodyClip.left) - 12.f;
        float bh = (float)(kCardBodyClip.bottom - kCardBodyClip.top);

        float totalH = renderDetailContent(frame, g, bx, 0.f, bw, frame.cardKind, frame.cardIdx, true);
        gCardMaxScroll = std::max(0, (int)std::ceil(totalH - bh));
        frame.cardScroll = std::max(0, std::min(frame.cardScroll, gCardMaxScroll.load()));

        GraphicsState st = g.Save();
        g.SetClip(RectF(bx - 2.f, by, bw + 16.f, bh), CombineModeIntersect);
        renderDetailContent(frame, g, bx, by - (float)frame.cardScroll, bw, frame.cardKind, frame.cardIdx, false);
        g.Restore(st);

        if (gCardMaxScroll.load() > 0) {
            float trackX = (float)kCardBodyClip.right - 6.f;
            SolidBrush tb(Color(55, 92, 60, 26)); g.FillRectangle(&tb, trackX, by, 4.f, bh);
            float thumbH = std::max(28.f, bh * (bh / totalH));
            float thumbY = by + (bh - thumbH) * ((float)frame.cardScroll / gCardMaxScroll.load());
            SolidBrush thb(Color(185, 106, 68, 28)); g.FillRectangle(&thb, trackX, thumbY, 4.f, thumbH);
        }

    }

    g.DrawLine(&hr, 104.f, 464.f, 696.f, 464.f);
    drawOvalPill(g, kCardEncycBtn, L"해설 도감에서 보기 (F7)", true, cardHov == HovCardEncyc, 12.8f);

    bool hasAudioBtn = false;
    if (frame.cardKind == CardKind::Bgm && frame.cardIdx >= 0 && frame.cardIdx < (int)gBgms.size()) {
        int trk = gBgms[frame.cardIdx].track;
        drawOvalPill(g, kCardAudioBtn, (frame.previewingBgm == trk) ? L"■ 미리듣기 정지" : L"▶ 이 곡 재생", false, cardHov == HovCardAudio, 12.8f);
        hasAudioBtn = true;
    } else if (frame.cardKind == CardKind::Text && frame.cardIdx >= 0 && frame.cardIdx < (int)gEntries.size() && gEntries[frame.cardIdx].voice > 0) {
        int vid = gEntries[frame.cardIdx].voice;
        drawOvalPill(g, kCardAudioBtn, (vLive == vid) ? L"■ 음성 재생 정지" : L"♪ 음성 다시 듣기", false, cardHov == HovCardAudio, 12.6f);
        hasAudioBtn = true;
    } else if (frame.cardKind == CardKind::Art && frame.artIndices().size() > 1) {
        drawOvalPill(g, kCardPrevArt, L"◀ 이전", false, cardHov == HovCardPrev, 12.5f);
        drawOvalPill(g, kCardNextArt, L"다음 ▶", false, cardHov == HovCardNext, 12.5f);
        hasAudioBtn = true;
    }
    if (gCardMaxScroll.load() > 0) {
        if (hasAudioBtn) drawTextLine(g, L"휠·↑↓ 스크롤", 525.f, 478.f, 11.8f, false, COL_INK_MID, 1);
        else             drawTextLine(g, L"마우스 휠 · ↑↓ 로 스크롤", 438.f, 478.f, 12.2f, false, COL_INK_MID, 1);
    }
    drawOvalPill(g, kCardOkBtn, L"닫기 Esc", false, cardHov == HovCardOk, 13.f);
}

void buildEncycLayer(CommentaryFrame& frame, int cw, int ch) {
    int vLive = (frame.previewingVoice != 0 && isVoiceChannelPlaying()) ? frame.previewingVoice : 0;
    wchar_t key[128];
    swprintf_s(key, L"enc|%d|%d|%d|%d|%d|%u|%u|%d|%d|%u|%d",
               frame.encycTab, frame.encycSel, frame.previewingBgm, vLive, frame.unlockAll ? 1 : 0, gUnlockGeneration.load(), frame.lineSerial, frame.activeChoiceEntry, frame.activeSubEntry, frame.artBreathStart, liveBgmTrack());
    bool redraw = false;
    if (!gEncycLayer.prepare(cw, ch, key, redraw)) return;
    ModalDamage damage(redraw);
    damage.trackHover(frame, gBookPaint);
    if (gBookPaint.listScroll != frame.encycListScroll) damage.add(kEncycLeftBox);
    gBookPaint.listScroll = frame.encycListScroll;
    if (gBookPaint.bodyScroll != frame.encycBodyScroll) damage.add(kEncycRightBox);
    gBookPaint.bodyScroll = frame.encycBodyScroll;
    if (!damage.full && damage.parts.empty()) return;

    Bitmap bmp(cw, ch, cw * 4, PixelFormat32bppPARGB, (BYTE*)gEncycLayer.bits);
    Graphics g(&bmp);
    damage.clip(g, gEncycLayer);
    g.SetSmoothingMode(SmoothingModeAntiAlias);
    g.SetTextRenderingHint(TextRenderingHintAntiAliasGridFit);
    g.SetInterpolationMode(InterpolationModeBilinear);

    // 1:1 사전 스케일 배경 + 양피지 책장 먼저 고속 복사
    if (SUI.encycBg) drawPrescaled(g, SUI.encycBg, 0, 0);
    else { SolidBrush bg(Color(255, 18, 24, 18)); g.FillRectangle(&bg, 0, 0, cw, ch); }
    drawPrescaled(g, SUI.folioParchment, scX(kEncycRightBox.left, cw), scY(kEncycRightBox.top, ch));

    g.ScaleTransform((REAL)(cw / 800.0), (REAL)(ch / 600.0));

    auto list = currentEncycList(frame);
    if (frame.encycSel >= (int)list.size()) frame.encycSel = std::max(0, (int)list.size() - 1);

    auto itemMeta = [&](int rawCode, CardKind& ck, int& realIdx, bool& unlocked, std::wstring& rowTitle, std::wstring& rowSub) {
        unlocked = true;
        if (frame.encycTab == 0) {
            ck = CardKind::Article; realIdx = rawCode;
            const auto& ar = gArticles[realIdx];
            wchar_t chp[24]; swprintf_s(chp, L"제%d장 · ", ar.chapter);
            rowTitle = ar.title; rowSub = std::wstring(chp) + ar.kind;
        } else if (frame.encycTab == 1) {
            ck = CardKind::Text; realIdx = rawCode;
            unlocked = isEntryUnlocked(frame, realIdx);
            const auto& e = gEntries[realIdx];
            std::wstring tag = (e.modal == L"sub") ? L"[음성] " : (e.modal == L"choice" ? L"[선택] " : (e.voice > 0 ? L"♪ " : L""));
            wchar_t chp[24];
            if (e.sid >= 3000) wcscpy_s(chp, L"[막간] ");
            else swprintf_s(chp, L"[%d장] ", e.chapter);
            rowTitle = unlocked ? (tag + e.title) : (std::wstring(chp) + L"※ 미열람 문장 해설");
            rowSub   = unlocked ? (std::wstring(chp) + truncOneLine(e.ko, 15)) : L"이야기를 읽으면 자동으로 열립니다";
        } else if (frame.encycTab == 2) {
            ck = CardKind::Art; realIdx = rawCode;
            unlocked = isArtUnlocked(frame, realIdx);
            const auto& a = gArts[realIdx];
            rowTitle = unlocked ? a.title : L"※ 미열람 그림 해설";
            rowSub   = unlocked ? (a.category + L" · " + a.kind) : L"장면 등장 시 자동으로 열립니다";
        } else if (frame.encycTab == 3) {
            ck = CardKind::Bgm; realIdx = rawCode;
            unlocked = isBgmUnlocked(frame, realIdx);
            const auto& m = gBgms[realIdx];
            wchar_t num[16]; swprintf_s(num, L"%02d. ", m.track);
            rowTitle = unlocked ? (std::wstring(num) + m.koTitle) : (std::wstring(num) + L"※ 미청취 트랙");
            rowSub   = unlocked ? m.jaTitle : L"재생된 뒤 자동으로 열립니다";
        } else if (frame.encycTab == 4) {
            ck = CardKind::Review; realIdx = rawCode;
            unlocked = isReviewUnlocked(frame, realIdx);
            const auto& rv = gReviews[realIdx];
            rowTitle = unlocked ? rv.title : (L"※ [완주 후] " + rv.sphere);
            rowSub   = unlocked ? (rv.sphere + L" · " + rv.author + L" (" + rv.date + L")") : (rv.author + L" (" + rv.date + L") · 완주 후 해금");
        } else {
            int hi = rawCode & 0xF0000, lo = rawCode & 0xFFFF;
            if (hi == 0x10000) { ck = CardKind::Text; realIdx = lo; rowTitle = L"[문장] " + gEntries[lo].title; rowSub = truncOneLine(gEntries[lo].ko, 18); }
            else if (hi == 0x20000) { ck = CardKind::Art; realIdx = lo; rowTitle = L"[그림] " + gArts[lo].title; rowSub = gArts[lo].category; }
            else { ck = CardKind::Bgm; realIdx = lo; rowTitle = L"[음악] " + gBgms[lo].koTitle; rowSub = gBgms[lo].jaTitle; }
        }
    };

    const float lx = (float)kEncycLeftBox.left, ly = (float)kEncycLeftBox.top;
    const float lw = (float)(kEncycLeftBox.right - kEncycLeftBox.left), lh = (float)(kEncycLeftBox.bottom - kEncycLeftBox.top);
    const int rowH = 46;
    int totalListH = (int)list.size() * rowH;
    gEncycListMaxScroll = std::max(0, totalListH - (int)lh);
    frame.encycListScroll = std::max(0, std::min(frame.encycListScroll, gEncycListMaxScroll.load()));

    static int unlockedCount;
    if (redraw) {
        unlockedCount = 0;
        if (frame.unlockAll || frame.encycTab == 0 || frame.encycTab == 5) unlockedCount = (int)list.size();
        else for (int i = 0; i < (int)list.size(); ++i) {
            switch (frame.encycTab) {
            case 1: unlockedCount += isEntryUnlocked(frame, i); break;
            case 2: unlockedCount += isArtUnlocked(frame, i); break;
            case 3: unlockedCount += isBgmUnlocked(frame, i); break;
            case 4: unlockedCount += isReviewUnlocked(frame, i); break;
            }
        }
    }

    if (damage.hits(kEncycLeftBox)) {
        GraphicsState stL = g.Save();
        g.SetClip(RectF(lx, ly, lw, lh), CombineModeIntersect);
        if (list.empty()) {
            drawShadowText(g, L"현재 장면에 표시할 항목이 없습니다.", lx + lw * 0.5f, ly + 150.f, 13.5f, false, COL_CREAM, 1);
        } else {
            const int first = frame.encycListScroll / rowH;
            const int end = std::min((int)list.size(), (frame.encycListScroll + (int)lh) / rowH + 1);
            for (int i = first; i < end; ++i) {
                float ry = ly + i * rowH - frame.encycListScroll;
                RECT row{kEncycLeftBox.left, (LONG)ry, kEncycLeftBox.right, (LONG)ry + rowH};
                if (!damage.hits(row)) continue;
                CardKind ck; int ri; bool unl; std::wstring rt, rs;
                itemMeta(list[i], ck, ri, unl, rt, rs);
                bool sel = (i == frame.encycSel);
                bool hov = (frame.hoverId == HovEncycRowBase + i);

                Bitmap* pl = sel ? UI.plateLit : UI.plateDim;
                if (pl) g.DrawImage(pl, RectF(lx, ry, lw - 8.f, (float)(rowH - 3)));
                if (hov && !sel) { Pen hp(Color(150, 255, 230, 140), 1.f); g.DrawRectangle(&hp, lx + 1.f, ry + 1.f, lw - 10.f, (float)(rowH - 5)); }

                Color c1 = sel ? COL_INK : (unl ? COL_CREAM : Color(165, 190, 184, 168));
                Color c2 = sel ? COL_INK_MID : Color(195, 206, 194, 164);
                if (sel) {
                    drawTextLine(g, truncOneLine(rt, 18), lx + 12.f, ry + 5.f, 13.2f, true, c1);
                    drawTextLine(g, truncOneLine(rs, 20), lx + 12.f, ry + 24.f, 11.5f, false, c2);
                } else {
                    drawShadowText(g, truncOneLine(rt, 18), lx + 12.f, ry + 5.f, 13.2f, true, c1);
                    drawShadowText(g, truncOneLine(rs, 20), lx + 12.f, ry + 24.f, 11.5f, false, c2);
                }
            }
        }
        g.Restore(stL);

        if (gEncycListMaxScroll.load() > 0) {
            float tx = lx + lw - 5.f;
            SolidBrush tb(Color(80, 220, 200, 150)); g.FillRectangle(&tb, tx, ly, 3.f, lh);
            float th = std::max(24.f, lh * (lh / totalListH));
            float ty = ly + (lh - th) * ((float)frame.encycListScroll / gEncycListMaxScroll.load());
            SolidBrush thb(COL_GOLD); g.FillRectangle(&thb, tx, ty, 3.f, th);
        }

    }

    const float rx = (float)kEncycRightBox.left, ry = (float)kEncycRightBox.top;
    const float rw = (float)(kEncycRightBox.right - kEncycRightBox.left), rh = (float)(kEncycRightBox.bottom - kEncycRightBox.top);
    if (damage.hits(kEncycRightBox) && !list.empty() && frame.encycSel >= 0 && frame.encycSel < (int)list.size()) {
        CardKind ck; int ri; bool unl; std::wstring rt, rs;
        itemMeta(list[frame.encycSel], ck, ri, unl, rt, rs);
        if (!unl) {
            // 고전 황동 자물쇠 엠블럼 직접 벡터 렌더링 (PrivateFontCollection 서러게이트 이모지 결손 방지)
            float lx0 = rx + rw * 0.5f, ly0 = ry + 114.f;
            Pen shacklePen(Color(210, 96, 62, 24), 2.6f);
            g.DrawArc(&shacklePen, lx0 - 9.f, ly0 - 16.f, 18.f, 18.f, 180.f, 180.f);
            SolidBrush bodyFill(Color(215, 132, 92, 38));
            Pen bodyEdge(Color(235, 78, 48, 16), 1.4f);
            g.FillRectangle(&bodyFill, lx0 - 13.f, ly0 - 6.f, 26.f, 20.f);
            g.DrawRectangle(&bodyEdge, lx0 - 13.f, ly0 - 6.f, 26.f, 20.f);
            SolidBrush keyhole(Color(235, 246, 232, 198));
            g.FillEllipse(&keyhole, lx0 - 2.6f, ly0 - 1.5f, 5.2f, 5.2f);
            g.FillRectangle(&keyhole, lx0 - 1.3f, ly0 + 2.5f, 2.6f, 6.5f);

            if (ck == CardKind::Review) {
                drawTextLine(g, L"결말 완주 후 열리는 심층 평론입니다", rx + rw * 0.5f, ry + 144.f, 17.5f, true, COL_INK, 1);
                drawTextLine(g, L"에필로그까지 완주하신 뒤 자동으로 열리며,", rx + rw * 0.5f, ry + 178.f, 13.5f, false, COL_INK_MID, 1);
                drawTextLine(g, L"아래 「전체 열기」 단추를 켜면 지금 즉시 열람할 수 있습니다.", rx + rw * 0.5f, ry + 200.f, 13.5f, false, COL_INK_MID, 1);
            } else {
                drawTextLine(g, L"아직 열리지 않은 해설입니다", rx + rw * 0.5f, ry + 144.f, 17.5f, true, COL_INK, 1);
                drawTextLine(g, L"이야기를 진행하며 해당 문장·그림·음악을 만나거나,", rx + rw * 0.5f, ry + 178.f, 13.5f, false, COL_INK_MID, 1);
                drawTextLine(g, L"아래 「전체 열기」 단추를 켜면 즉시 모든 해설을 볼 수 있습니다.", rx + rw * 0.5f, ry + 200.f, 13.5f, false, COL_INK_MID, 1);
            }
        } else {
            std::wstring badge, head;
            if (ck == CardKind::Article) { badge = gArticles[ri].kind + L" · " + gArticles[ri].mark; head = gArticles[ri].title; }
            else if (ck == CardKind::Text) { badge = gEntries[ri].kind + L" · " + gEntries[ri].mark; head = gEntries[ri].title; }
            else if (ck == CardKind::Art)  { badge = gArts[ri].kind + L" · " + gArts[ri].mark; head = gArts[ri].title; }
            else if (ck == CardKind::Bgm)  { badge = gBgms[ri].kind + L" · " + gBgms[ri].mark; head = gBgms[ri].title; }
            else if (ck == CardKind::Review) {
                const auto& rv = gReviews[ri];
                badge = rv.sphere + L" · " + truncOneLine(rv.author, 20) + L" (" + rv.date + L") · " + rv.mark;
                head = rv.title;
            }

            bool hasEncycAudio = (ck == CardKind::Bgm) || (ck == CardKind::Text && gEntries[ri].voice > 0);
            const float headerWidth = (hasEncycAudio ? kEncycAudioBtn.left - 6.f : rx + rw - 20.f) - (rx + 26.f);
            drawTextLine(g, badge, rx + 26.f, ry + 20.f, 12.2f, true, COL_INK_MID, 0, nullptr, headerWidth);
            drawTextLine(g, head, rx + 26.f, ry + 39.f, 16.5f, true, COL_INK, 0, nullptr, headerWidth);

            if (ck == CardKind::Bgm) {
                int trk = gBgms[ri].track;
                drawOvalPill(g, kEncycAudioBtn, (frame.previewingBgm == trk) ? L"■ 재생 정지" : L"▶ 곡 미리듣기", false, frame.hoverId == HovEncycAudio, 12.5f);
            } else if (ck == CardKind::Text && gEntries[ri].voice > 0) {
                int vid = gEntries[ri].voice;
                drawOvalPill(g, kEncycAudioBtn, (vLive == vid) ? L"■ 음성 정지" : L"♪ 음성 다시 듣기", false, frame.hoverId == HovEncycAudio, 12.5f);
            }

            Pen hr(COL_RULE, 1.2f);
            g.DrawLine(&hr, rx + 24.f, ry + 66.f, rx + rw - 24.f, ry + 66.f);

            float bx = rx + 26.f, by = ry + 74.f, bw = rw - 58.f, bh = rh - 96.f;
            float totalH = renderDetailContent(frame, g, bx, 0.f, bw, ck, ri, true);
            gEncycBodyMaxScroll = std::max(0, (int)std::ceil(totalH - bh));
            frame.encycBodyScroll = std::max(0, std::min(frame.encycBodyScroll, gEncycBodyMaxScroll.load()));

            GraphicsState stR = g.Save();
            g.SetClip(RectF(bx - 2.f, by, bw + 14.f, bh), CombineModeIntersect);
            renderDetailContent(frame, g, bx, by - (float)frame.encycBodyScroll, bw, ck, ri, false);
            g.Restore(stR);

            if (gEncycBodyMaxScroll.load() > 0) {
                float tx = rx + rw - 24.f;
                SolidBrush tb(Color(55, 92, 60, 26)); g.FillRectangle(&tb, tx, by, 4.f, bh);
                float th = std::max(26.f, bh * (bh / totalH));
                float ty = by + (bh - th) * ((float)frame.encycBodyScroll / gEncycBodyMaxScroll.load());
                SolidBrush thb(Color(185, 106, 68, 28)); g.FillRectangle(&thb, tx, ty, 4.f, th);
            }
        }
    }

    g.ResetTransform();
    drawPrescaled(g, SUI.encycFg, 0, 0);
    g.ScaleTransform((REAL)(cw / 800.0), (REAL)(ch / 600.0));

    drawTextLine(g, L"숲의 주석서 · 해설 도감", 282.f, 18.f, 14.5f, true, COL_INK);
    static const wchar_t* kTabNames[kNumEncycTabs] = {L"총론·해제", L"문장·음성", L"그림 도감", L"음악 도감", L"평론·리뷰", L"현재 장면"};
    for (int i = 0; i < kNumEncycTabs; ++i) {
        bool sel = (frame.encycTab == i);
        bool hov = (frame.hoverId == HovEncycTab0 + i);
        drawOvalPill(g, kEncycTabs[i], kTabNames[i], sel, hov || sel, 11.8f);
    }

    wchar_t progTxt[96];
    swprintf_s(progTxt, L"열람 해금 %d / %zu 항목", unlockedCount, list.size());
    drawTextLine(g, progTxt, 32.f, 548.f, 15.f, true, COL_INK);
    drawTextLine(g, L"휠: 목록·본문 스크롤  ｜  F7 · Esc: 닫기", 32.f, 570.f, 11.8f, false, COL_INK_MID);

    drawOvalPill(g, kEncycUnlockBtn, frame.unlockAll ? L"전체 열기: 켬 ✓" : L"전체 열기: 끔", frame.unlockAll, frame.hoverId == HovEncycUnlock, 13.f);
    drawOvalPill(g, kEncycChartBtn,  L"이야기의 지도 F8", false, frame.hoverId == HovEncycChart, 13.f);
    drawOvalPill(g, kEncycCloseBtn,  L"닫기 Esc", false, frame.hoverId == HovEncycClose, 13.5f);
}

// ---------------------------------------------------------------- 시험 도우미(cm_test=1 일 때만)
void writeTestStateJson(CommentaryFrame& frame) {
    refreshLiveMedia(frame, true);
    updateGoldenAtom(frame);
    std::string j = "{\n";
    j += "  \"loaded\": " + std::string(gLoaded ? "true" : "false") + ",\n";
    j += "  \"enabled\": " + std::string(frame.enabled ? "true" : "false") + ",\n";
    j += "  \"guide_mode\": " + std::to_string(frame.guideMode) + ",\n";
    j += "  \"unlock_all\": " + std::string(frame.unlockAll ? "true" : "false") + ",\n";
    j += "  \"settings_open\": " + std::string(EV(kSettings) ? "true" : "false") + ",\n";
    j += "  \"encyc_open\": " + std::string(frame.encycOpen ? "true" : "false") + ",\n";
    j += "  \"encyc_tab\": " + std::to_string(frame.encycTab) + ",\n";
    j += "  \"card_kind\": " + std::to_string((int)frame.cardKind) + ",\n";
    j += "  \"card_idx\": " + std::to_string(frame.cardIdx) + ",\n";
    j += "  \"sid\": " + std::to_string(topScript()) + ",\n";
    j += "  \"cur_pc\": " + std::to_string(frame.curPc) + ",\n";
    j += "  \"active_line\": " + std::to_string(frame.activeLineEntry) + ",\n";
    j += "  \"active_sub\": " + std::to_string(frame.activeSubEntry) + ",\n";
    j += "  \"active_choice\": " + std::to_string(frame.activeChoiceEntry) + ",\n";
    j += "  \"visible_arts\": " + std::to_string(frame.artIndices().size()) + ",\n";
    j += "  \"live_bgm\": " + std::to_string(liveBgmTrack()) + ",\n";
    j += "  \"preview_bgm\": " + std::to_string(frame.previewingBgm) + ",\n";
    j += "  \"preview_voice\": " + std::to_string(frame.previewingVoice) + ",\n";
    j += "  \"voice_playing\": " + std::string(isVoiceChannelPlaying() ? "true" : "false") + ",\n";
    j += "  \"title_menu\": " + std::to_string(titleMenuKind(frame)) + ",\n";
    j += "  \"vm_alive\": " + std::to_string(EV(kVmAlive) ? 1 : 0) + ",\n";
    j += "  \"typing\": " + std::string(typingNow() ? "true" : "false") + ",\n";
    j += "  \"line_viewed\": " + std::string(frame.viewedSerial == frame.lineSerial ? "true" : "false") + ",\n";
    j += "  \"modal\": " + std::string(gModal.load() ? "true" : "false") + ",\n";
    j += "  \"hiart_keys\": " + std::to_string(HiArt_LayerKeyCount()) + ",\n";
    j += "  \"hiart_faults\": " + std::to_string(HiArt_GuardFaults()) + ",\n";
    j += "  \"reviews\": " + std::to_string(gReviews.size()) + ",\n";
    j += "  \"wants_golden\": " + std::string(Cm_WantsGoldenText() ? "true" : "false") + "\n";
    j += "}\n";
    HANDLE f = CreateFileW((Root() + L"\\cm_state.json").c_str(), GENERIC_WRITE, FILE_SHARE_READ, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (f != INVALID_HANDLE_VALUE) { DWORD w = 0; WriteFile(f, j.data(), (DWORD)j.size(), &w, nullptr); CloseHandle(f); }
}

void handleTestCmd(CommentaryFrame& frame, WPARAM w, LPARAM l) {
    switch (w) {
    case 1: writeTestStateJson(frame); break;
    case 2:
        frame.enabled = (l != 0);
        if (!frame.enabled) { closeCard(frame); closeEncyclopedia(frame); }
        saveUserState(frame);
        updateGoldenAtom(frame);
        HiText_ForceRepaint();
        invalidateAll();
        break;
    case 3:
        frame.guideMode = std::max(0, std::min(2, (int)l));
        saveUserState(frame);
        invalidateAll();
        break;
    case 4:
        refreshLiveMedia(frame, true);
        if (l == 0 && frame.activeLineEntry >= 0) openCard(frame, CardKind::Text, frame.activeLineEntry);
        else if (l == 1 && frame.activeSubEntry >= 0) openCard(frame, CardKind::Text, frame.activeSubEntry);
        else if (l == 2 && frame.activeChoiceEntry >= 0) openCard(frame, CardKind::Text, frame.activeChoiceEntry);
        else if (l == 3 && !frame.artIndices().empty()) openCard(frame, CardKind::Art, frame.artIndices().back());
        else if (l == 4 && gBgmByTrack.count(liveBgmTrack())) openCard(frame, CardKind::Bgm, gBgmByTrack[liveBgmTrack()]);
        break;
    case 5: closeCard(frame); closeEncyclopedia(frame); break;
    case 6: openEncyclopedia(frame, (int)l, 0); break;
    case 7:
        frame.unlockAll = (l != 0);
        saveUserState(frame);
        updateGoldenAtom(frame);
        invalidateAll();
        break;
    case 8:
        frame.encycSel = std::max(0, (int)l);
        frame.encycListScroll = std::max(0, (frame.encycSel - 3) * 46);
        frame.encycBodyScroll = 0;
        invalidateAll();
        break;
    case 9:
        if (l >= 0 && l < (int)gEntries.size()) openCard(frame, CardKind::Text, (int)l);
        break;
    case 10:
        if (l > 0) { toggleVoicePreview(frame, (int)l); invalidateAll(); }
        break;
    case 11:
        if (l >= 0 && l < (int)gReviews.size()) openCard(frame, CardKind::Review, (int)l);
        break;
    }
    writeTestStateJson(frame);
}

}  // namespace

// ================================================================ qol.h 공개 인터페이스
bool Cm_Install() {
    InitializeCriticalSection(&gStateCs);
    gModOn = Cfg("cm", 1) != 0;
    if (!gModOn) return false;
    gTestMode = Cfg("cm_test", 0) != 0;
    loadHiartMap();
    gLoaded = loadCommentaryJson();
    WindowEdit edit;
    auto& frame = edit.get();
    loadUserState(frame);
    if (gTestMode) gMsgTest = RegisterWindowMessageW(L"ForestCmV2Test");
    gMsgSync = RegisterWindowMessageW(L"ForestCmV2Sync");
    return gLoaded;
}

void Cm_WindowReady(HWND h) {
    gWnd = h;
    if (!gModOn || !gLoaded) return;
    PostMessageW(h, gMsgSync, 2, 0);
    Log("cm2: high-speed cached UI engine ready");
}

bool Cm_Enabled() { return gModOn && gLoaded && gCmEnabled.load(); }
bool Cm_Modal() { return gModOn && gLoaded && gModal.load(); }
bool Cm_CoversScreen() { return gModOn && gLoaded && (gRenderDepth ? gRenderFrame.encycOpen : gBookOpen.load()); }

bool Cm_WantsGoldenText() {
    return History_WindowAvailable() && !History_Open() && !Play_GuideOpen() && gGoldenLineAtom.load(std::memory_order_relaxed);
}

bool Cm_GoldenTint(const RECT& glyphRect, uint32_t origColor, uint32_t& outColor) {
    if (!Cm_WantsGoldenText()) return false;
    if (glyphRect.top < 415 || glyphRect.bottom > 592) return false;
    int r = (origColor >> 16) & 255, g = (origColor >> 8) & 255, b = origColor & 255;
    if (r < 140 || g < 140 || b < 140) return false;
    outColor = gGoldenHoverAtom.load(std::memory_order_relaxed) ? 0xFFF7CEu : 0xFFE28Au;
    return true;
}

void Cm_OnReset(const char* /*why*/) {
    if (!gModOn || !gLoaded) return;
    StoryEdit edit;
    auto& frame = edit.frame;
    frame.activeLineEntry = -1;
    ++frame.lineSerial;
    frame.activeSubEntry = -1;
    frame.activeChoiceEntry = -1;
    frame.inChoiceOp = false;
    updateGoldenAtom(frame);
    if (gWnd) PostMessageW(gWnd, gMsgSync, 1, 0);
}

// 목소리만 나오는 줄에서 카드·도감을 열어 두면, 음성이 끝나는 순간 대본 스레드가 자막을 지우고 다음 대사로 넘어가
// 닫았을 때는 이미 다음 줄이었다(보통 대사는 클릭 대기라 안 넘어간다). 음성 기다림(0x45)이 끝난 바로 다음 명령이나
// 자막 지우기(0x24 층 45~49)를 집으려는 참에 카드·도감이 열려 있으면 닫힐 때까지 그 자리에 머문다.
// 잠금 없이 기다린다(창 스레드가 카드를 닫으려면 gViewMutex 가 필요하다). 엔진이 대본 스레드를 끝내려 하면(창 닫기 —
// 0x420600 이 [0x4663c8] 을 세우고 이 스레드가 끝나기를 기다린다) 바로 놓아 준다. (2026-11-28)
void holdStoryWhileModal(int sid, uint32_t pc, uint16_t op, uint16_t prevOp, const uint8_t* cursor) {
    if (sid < 2000 || !gModal.load()) return;
    const bool afterVoiceWait = prevOp == 0x45;
    // 자막은 층 45~49(바깥선 사본 넷 + 글자)에 찍히고 대본은 층 45 부터 차례로 지운다. 음성 기다림(0x45)이 아니라 시간
    // 기다림(0x0d)으로 끝나는 자막도 있어(72곳 — 제미나이 독립 검수 11-28), 자막 층의 첫 지우기 앞에서 멈춘다. 층 49 만
    // 보면 그런 줄에서는 바깥선 넷이 먼저 지워진 뒤에야 멈춘다.
    const uint16_t clearLayer = op == 0x24 ? (uint16_t)(*(const uint32_t*)(cursor + 2) & 0xFFFF) : 0;
    const bool subtitleClear = clearLayer >= 45 && clearLayer <= 49;
    if (!afterVoiceWait && !subtitleClear) return;
    const DWORD t0 = GetTickCount();
    while (gModal.load() && !EV(kVmQuit)) Sleep(15);
    char b[256];
    sprintf_s(b, "cm2: story held %lums at %d:%u op %02x while a card or the encyclopedia was open (after voice wait %d, subtitle clear %d)%s",
              GetTickCount() - t0, sid, pc, (unsigned)op, afterVoiceWait ? 1 : 0, subtitleClear ? 1 : 0,
              EV(kVmQuit) ? " -> engine is ending the VM thread (window close)" : "");
    Log(b);
}

void Cm_Fetch(void* /*script*/, int sid, uint32_t pc, uint16_t op, const uint8_t* cursor) {
    static uint16_t sPrevOp = 0;   // 바로 앞에 집은 명령(대본 스레드만 부른다)
    const uint16_t prevOp = sPrevOp;
    sPrevOp = op;
    if (!gModOn || !gLoaded) return;
    holdStoryWhileModal(sid, pc, op, prevOp, cursor);
    StoryEdit edit;
    auto& frame = edit.frame;
    if (frame.inChoiceOp && frame.choiceOwnerTid == GetCurrentThreadId() &&
        (sid != frame.choiceOwnerSid || curDepth() != frame.choiceOwnerDepth) && EV(kChoiceBox)) return;
    int prevSid = frame.curSid;
    frame.curSid = sid;
    frame.curPc = pc;
    if (sid <= 1 || (sid >= 1000 && sid < 2000)) {
        bool hadAny = (frame.activeLineEntry >= 0 || frame.activeSubEntry >= 0 || frame.activeChoiceEntry >= 0 || frame.inChoiceOp);
        frame.activeLineEntry = frame.prevLineEntry = frame.activeSubEntry = frame.activeChoiceEntry = -1;
        frame.inChoiceOp = false;
        updateGoldenAtom(frame);
        if ((hadAny || (sid == 1 && (op == 0x49 || op == 0x3C))) && frame.enabled && gWnd) PostMessageW(gWnd, gMsgSync, 0, 0);
        return;
    }
    if (frame.inChoiceOp && op != 0x0E) {
        frame.inChoiceOp = false;
        frame.activeChoiceEntry = -1;
    }
    if (prevSid != sid && sid >= 2000) {
        frame.activeLineEntry = -1;
        frame.activeSubEntry = -1;
    }

    bool hudDirty = false;
    if (op == 0x51 || op == 0x52) {
        int slot = (op == 0x51) ? *(const int32_t*)(cursor + 22) : *(const int32_t*)(cursor + 18);
        if (op == 0x51 && frame.activeLineEntry >= 0) frame.prevLineEntry = frame.activeLineEntry;
        auto it = gByLineKey.find(((uint64_t)sid << 32) | (uint32_t)slot);
        int nextEnt = (it != gByLineKey.end()) ? it->second : -1;
        if (op == 0x51 || nextEnt >= 0) {
            if (frame.activeLineEntry != nextEnt) hudDirty = true;
            frame.activeLineEntry = nextEnt;
            frame.lineSid = sid;
            ++frame.lineSerial;
            frame.lineAfterOk = (nextEnt < 0 || gEntries[nextEnt].afterSlot <= 0 || isSlotRead(sid, gEntries[nextEnt].afterSlot));
            if (nextEnt >= 0) {
                EnterCriticalSection(&gStateCs);
                if (gSeenEntries.insert(gEntries[nextEnt].id).second) { ++gUnlockGeneration; gProgressDirty.store(true); }
                LeaveCriticalSection(&gStateCs);
            }
        }
        frame.activeChoiceEntry = -1;
        // 0x413020 실행 직전에 즉시 원자 플래그를 세워, 글리프가 찍히는 첫 순간부터 스레드 재생성 없이 황금빛으로 합성!
        updateGoldenAtom(frame);
    } else if (op == 0x20) {
        uint16_t layer = (uint16_t)(*(const uint32_t*)(cursor + 2) & 0xFFFF);
        int slot = *(const int32_t*)(cursor + 22);
        if (layer == 49 && slot > 0) {
            // 목소리만 나오는 줄(층 49 자막)이 시작됐다. 앞 대사는 이미 넘긴 줄이므로 「지금 줄」에서 내려놓는다 —
            // 안 그러면 앞 대사의 요약 띠·「해설 보기」 알약·금색 글자 판정이 자막 줄 내내 남는다(자막 줄에는 「음성 해설」 알약이 따로 있다).
            // 내려놓은 줄은 prevLineEntry 로 옮겨 두어 F7 도감의 「지금 줄」 자리에서는 계속 찾을 수 있다. (2026-11-28)
            if (frame.activeLineEntry >= 0) {
                frame.prevLineEntry = frame.activeLineEntry;
                frame.activeLineEntry = -1;
                ++frame.lineSerial;
                updateGoldenAtom(frame);
            }
            auto it = gBySubKey.find(((uint64_t)sid << 32) | (uint32_t)slot);
            frame.activeSubEntry = (it != gBySubKey.end()) ? it->second : -1;
            if (frame.activeSubEntry >= 0) {
                EnterCriticalSection(&gStateCs);
                if (gSeenEntries.insert(gEntries[frame.activeSubEntry].id).second) { ++gUnlockGeneration; gProgressDirty.store(true); }
                LeaveCriticalSection(&gStateCs);
            }
            hudDirty = true;
        }
    } else if (op == 0x24) {
        uint16_t layer = (uint16_t)(*(const uint32_t*)(cursor + 2) & 0xFFFF);
        if (layer == 49 && frame.activeSubEntry >= 0) {
            frame.activeSubEntry = -1;
            hudDirty = true;
        }
    } else if (op == 0x0E) {
        const int qSlot = *(const int32_t*)(cursor + 4);
        const auto pcEntry = gByChoicePc.find(((uint64_t)sid << 32) | pc);
        if (pcEntry != gByChoicePc.end()) frame.activeChoiceEntry = pcEntry->second;
        else {
            const auto byQuestion = gByChoiceQSlot.find(((uint64_t)sid << 32) | (uint32_t)qSlot);
            frame.activeChoiceEntry = qSlot > 0 && byQuestion != gByChoiceQSlot.end() ? byQuestion->second : -1;
        }
        frame.choiceOwnerSid = sid;
        frame.choiceOwnerDepth = curDepth();
        frame.choiceOwnerTid = GetCurrentThreadId();
        frame.inChoiceOp = true;
        updateGoldenAtom(frame);
        if (frame.activeChoiceEntry >= 0) {
            EnterCriticalSection(&gStateCs);
            if (gSeenEntries.insert(gEntries[frame.activeChoiceEntry].id).second) { ++gUnlockGeneration; gProgressDirty.store(true); }
            LeaveCriticalSection(&gStateCs);
        }
        hudDirty = true;
    } else if (op == 0x3C) {
        hudDirty = true;
    }

    if (hudDirty && frame.enabled && gWnd) PostMessageW(gWnd, gMsgSync, 0, 0);
}

static bool handleWindowInput(CommentaryFrame& frame, HWND h, UINT m, WPARAM w, LPARAM l, LRESULT& r) {
    if (!gModOn || !gLoaded) return false;
    if (Present_Active() && gTestMode && gMsgTest && m == gMsgTest) { handleTestCmd(frame, w, l); r = 1; return true; }
    if (gMsgSync && m == gMsgSync) {
        if (w == 2) {
            if (!SetTimer(h, kAnimTimer, 180, nullptr)) Log("cm2: commentary timer creation failed");
            r = 0; return true;
        }
        refreshLiveMedia(frame, w != 0);
        updateGoldenAtom(frame);
        if (w != 0 && frame.enabled) HiText_ForceRepaint();   // 되감기·불러오기 직후에만 1회 재찍기
        if (frame.enabled) {
            if (int tmk = titleMenuKind(frame)) {
                Present_InvalidateLogical(inflateR(titleMenuBtnRect(tmk), 14, 8));
            } else {
                // 전체 800×600 대신 실제 HUD 위젯 영역만 국소 갱신!
                Present_InvalidateLogical(uniteR(kQbarRect, kBookRect));
                Present_InvalidateLogical(uniteR(kDetPlateRect, kLinePillRect));
            }
        }
        r = 0; return true;
    }
    if (m == WM_CLOSE || m == WM_DESTROY || (m == WM_ENDSESSION && w) ||
        (m == WM_SYSCOMMAND && (w & 0xfff0) == SC_CLOSE)) {
        if (gProgressDirty.load()) saveUserState(frame);
        if (m == WM_DESTROY) KillTimer(h, kAnimTimer);
    }
    if (m == WM_TIMER && w == kAnimTimer) {
        static DWORD lastFlush = 0;
        if (gProgressDirty.load() && GetTickCount() - lastFlush >= 1200) {
            lastFlush = GetTickCount();
            saveUserState(frame);
        }
        static int sPrevTitleMenu = 0;
        int curTm = titleMenuKind(frame);
        if (curTm != sPrevTitleMenu) {
            sPrevTitleMenu = curTm;
            Present_InvalidateLogical(uniteR(inflateR(kTitleCmBtn, 14, 8), inflateR(kExtrasCmBtn, 14, 8)));
        }
        if (frame.previewingVoice != 0 && !isVoiceChannelPlaying()) {
            frame.previewingVoice = 0;
            if (frame.encycOpen) invalidateAll();
            else if (frame.cardKind != CardKind::None) Present_InvalidateLogical(kCardRect);
        }
        if (!frame.enabled && !settingsRowVisible()) { r = 0; return true; }
        refreshLiveMedia(frame, false);
        updateGoldenAtom(frame);
        if (frame.enabled && !frame.artIndices().empty()) {
            DWORD dt = GetTickCount() - frame.artBreathStart;
            if (dt >= 1150 && dt < 2650)
                Present_InvalidateLogical(uniteR(kQbarArtBtn, inflateR(kArtSealRect, 12, 8)));
        }
        r = 0; return true;
    }

    if (!Present_Active() || Play_GuideOpen()) return false;
    if ((m == WM_KEYUP && (w == VK_CONTROL || w == VK_LCONTROL || w == VK_RCONTROL)) ||
        ((m == WM_SYSKEYDOWN || m == WM_SYSKEYUP) && w == VK_F4)) return false;
    if (m == WM_KEYDOWN && w == VK_PROCESSKEY && (frame.cardKind != CardKind::None || frame.encycOpen)) {
        w = ShortcutKey(h, w, l);
        HIMC im = ImmGetContext(h);
        if (im) { ImmNotifyIME(im, NI_COMPOSITIONSTR, CPS_CANCEL, 0); ImmReleaseContext(h, im); }
    }
    // 마우스 좌표 및 이산 HoverId 변화 감지(바뀐 단추 영역만 최소 갱신!)
    if (m == WM_MOUSEMOVE || m == WM_LBUTTONDOWN || m == WM_LBUTTONUP || m == WM_RBUTTONDOWN) {
        frame.mouse = POINT{GET_X_LPARAM(l), GET_Y_LPARAM(l)};
        if (m == WM_MOUSEMOVE) {
            RECT oldR{}, newR{};
            // 이전 사각형 기억을 위해 임시 백업
            int prevHov = frame.hoverId;
            int nextHov = computeHoverId(frame, &newR);
            if (nextHov != prevHov) {
                frame.hoverId = nextHov;
                bool goldHov = (nextHov == HovGoldenText || nextHov == HovLinePill);
                bool prevGold = gGoldenHoverAtom.exchange(goldHov, std::memory_order_relaxed);
                if (frame.encycOpen || frame.cardKind != CardKind::None) {
                    RECT from = modalControlRect(frame, prevHov), to = modalControlRect(frame, nextHov);
                    if (!IsRectEmpty(&from)) Present_InvalidateLogical(from);
                    if (!IsRectEmpty(&to)) Present_InvalidateLogical(to);
                } else if (settingsRowVisible()) {
                    Present_InvalidateLogical(kConfRowRect);
                } else if (int tmk = titleMenuKind(frame)) {
                    Present_InvalidateLogical(inflateR(titleMenuBtnRect(tmk), 14, 8));
                } else {
                    if (prevGold != goldHov) {
                        RECT dlg{};
                        if (HiText_DialogueBounds(dlg)) Present_InvalidateLogical(inflateR(dlg, 8, 8));
                    }
                    Present_InvalidateLogical(uniteR(kQbarRect, kBookRect));
                    Present_InvalidateLogical(uniteR(kDetPlateRect, kLinePillRect));
                    if (newR.right > newR.left) Present_InvalidateLogical(newR);
                }
            }
            if (frame.encycOpen || frame.cardKind != CardKind::None) { r = 0; return true; }
            return false;
        }
    }

    // 1. 오른쪽 클릭 설정 화면(confscrn) 안의 「해설 모드: 켬 / 끔」
    if (settingsRowVisible()) {
        if (m == WM_LBUTTONDOWN) {
            if (ptIn(kConfOnRect, frame.mouse)) {
                if (!frame.enabled) {
                    frame.enabled = true;
                    saveUserState(frame);
                    refreshLiveMedia(frame, true);
                    updateGoldenAtom(frame);
                    HiText_ForceRepaint();
                }
                Present_InvalidateLogical(kConfRowRect);
                r = 0; return true;
            }
            if (ptIn(kConfOffRect, frame.mouse)) {
                if (frame.enabled) {
                    frame.enabled = false;
                    closeCard(frame); closeEncyclopedia(frame);
                    saveUserState(frame);
                    updateGoldenAtom(frame);
                    HiText_ForceRepaint();
                }
                Present_InvalidateLogical(kConfRowRect);
                r = 0; return true;
            }
        }
        return false;
    }

    // 2. F7 전체 해설 도감
    if (frame.encycOpen) {
        if (m == WM_MOUSEWHEEL) {
            int delta = GET_WHEEL_DELTA_WPARAM(w);
            int step = -(delta / WHEEL_DELTA) * 48;
            // WM_MOUSEWHEEL 의 lParam 은 화면 절대 좌표이므로 변환
            POINT sp{GET_X_LPARAM(l), GET_Y_LPARAM(l)};
            ScreenToClient(h, &sp);
            Layout L = CurrentLayout();
            int lx = L.cw > 0 ? (sp.x - L.ox) * 800 / L.cw : 400;
            int ly = L.ch > 0 ? (sp.y - L.oy) * 600 / L.ch : 300;
            if (ptIn(kEncycLeftBox, POINT{lx, ly})) {
                frame.encycListScroll = std::clamp(listOffset(frame) + step, 0, gEncycListMaxScroll.load());
                if (ptIn(kEncycLeftBox, frame.mouse)) frame.hoverId = computeHoverId(frame);
                Present_InvalidateLogical(kEncycLeftBox);
            } else {
                frame.encycBodyScroll = std::clamp(frame.encycBodyScroll + step, 0, gEncycBodyMaxScroll.load());
                Present_InvalidateLogical(kEncycRightBox);
            }
            r = 0; return true;
        }
        if (m == WM_KEYDOWN) {
            if (w == VK_ESCAPE || w == VK_F7) closeEncyclopedia(frame);
            else if (w == VK_F8) { closeEncyclopedia(frame); OpenChart(); }
            else if (w == 'V') {
                auto list = currentEncycList(frame);
                if (!list.empty() && frame.encycSel >= 0 && frame.encycSel < (int)list.size()) {
                    int raw = list[frame.encycSel];
                    int bgmIdx = (frame.encycTab == 3) ? raw : ((frame.encycTab == 5 && (raw & 0xF0000) == 0x30000) ? (raw & 0xFFFF) : -1);
                    int txtIdx = (frame.encycTab == 1) ? raw : ((frame.encycTab == 5 && (raw & 0xF0000) == 0x10000) ? (raw & 0xFFFF) : -1);
                    if (bgmIdx >= 0 && isBgmUnlocked(frame, bgmIdx)) {
                        int trk = gBgms[bgmIdx].track;
                        if (frame.previewingBgm == trk) stopAudioPreviewAndRestore(frame);
                        else { stopVoicePreview(frame); frame.previewingBgm = trk; playEngineBgm(trk, 1); }
                        invalidateAll();
                    } else if (txtIdx >= 0 && isEntryUnlocked(frame, txtIdx) && gEntries[txtIdx].voice > 0) {
                        toggleVoicePreview(frame, gEntries[txtIdx].voice);
                        invalidateAll();
                    }
                }
            }
            else if (w == VK_UP) {
                stopVoicePreview(frame);
                frame.encycSel = std::max(0, frame.encycSel - 1);
                if (frame.encycSel * 46 < frame.encycListScroll) frame.encycListScroll = frame.encycSel * 46;
                frame.encycBodyScroll = 0; invalidateAll();
            }
            else if (w == VK_DOWN) {
                stopVoicePreview(frame);
                int maxSel = std::max(0, (int)currentEncycList(frame).size() - 1);
                frame.encycSel = std::min(maxSel, frame.encycSel + 1);
                int visH = kEncycLeftBox.bottom - kEncycLeftBox.top;
                if ((frame.encycSel + 1) * 46 - visH > frame.encycListScroll) frame.encycListScroll = (frame.encycSel + 1) * 46 - visH;
                frame.encycBodyScroll = 0; invalidateAll();
            }
            else if (w == VK_PRIOR) { frame.encycBodyScroll = std::max(0, frame.encycBodyScroll - 220); Present_InvalidateLogical(kEncycRightBox); }
            else if (w == VK_NEXT)  { frame.encycBodyScroll = std::min(gEncycBodyMaxScroll.load(), frame.encycBodyScroll + 220); Present_InvalidateLogical(kEncycRightBox); }
            r = 0; return true;
        }
        if (m == WM_RBUTTONDOWN) { closeEncyclopedia(frame); r = 0; return true; }
        if (m == WM_LBUTTONDOWN) {
            for (int i = 0; i < kNumEncycTabs; ++i) if (ptIn(kEncycTabs[i], frame.mouse)) {
                stopVoicePreview(frame);
                frame.encycTab = i; frame.encycSel = 0; frame.encycListScroll = 0; frame.encycBodyScroll = 0;
                if (i == 1) {
                    int want = (frame.activeLineEntry >= 0) ? frame.activeLineEntry : frame.prevLineEntry;
                    if (want < 0 && frame.curSid >= 2000) {
                        for (int k = 0; k < (int)gEntries.size(); ++k) if (gEntries[k].sid == frame.curSid) { want = k; break; }
                    }
                    if (want >= 0) { frame.encycSel = want; frame.encycListScroll = std::max(0, (want - 2) * 46); }
                }
                invalidateAll(); r = 0; return true;
            }
            if (ptIn(kEncycLeftBox, frame.mouse)) {
                int idx = (frame.mouse.y - kEncycLeftBox.top + listOffset(frame)) / 46;
                auto list = currentEncycList(frame);
                if (idx >= 0 && idx < (int)list.size()) { stopVoicePreview(frame); frame.encycSel = idx; frame.encycBodyScroll = 0; invalidateAll(); }
                r = 0; return true;
            }
            auto list = currentEncycList(frame);
            if (!list.empty() && frame.encycSel >= 0 && frame.encycSel < (int)list.size()) {
                int raw = list[frame.encycSel];
                int bgmIdx = (frame.encycTab == 3) ? raw : ((frame.encycTab == 5 && (raw & 0xF0000) == 0x30000) ? (raw & 0xFFFF) : -1);
                int txtIdx = (frame.encycTab == 1) ? raw : ((frame.encycTab == 5 && (raw & 0xF0000) == 0x10000) ? (raw & 0xFFFF) : -1);
                if (bgmIdx >= 0 && isBgmUnlocked(frame, bgmIdx) && ptIn(kEncycAudioBtn, frame.mouse)) {
                    int trk = gBgms[bgmIdx].track;
                    if (frame.previewingBgm == trk) stopAudioPreviewAndRestore(frame);
                    else { stopVoicePreview(frame); frame.previewingBgm = trk; playEngineBgm(trk, 1); }
                    invalidateAll(); r = 0; return true;
                }
                if (txtIdx >= 0 && isEntryUnlocked(frame, txtIdx) && gEntries[txtIdx].voice > 0 && ptIn(kEncycAudioBtn, frame.mouse)) {
                    toggleVoicePreview(frame, gEntries[txtIdx].voice);
                    invalidateAll(); r = 0; return true;
                }
            }
            if (ptIn(kEncycUnlockBtn, frame.mouse)) { frame.unlockAll = !frame.unlockAll; saveUserState(frame); invalidateAll(); r = 0; return true; }
            if (ptIn(kEncycChartBtn, frame.mouse))  { closeEncyclopedia(frame); OpenChart(); r = 0; return true; }
            if (ptIn(kEncycCloseBtn, frame.mouse))  { closeEncyclopedia(frame); r = 0; return true; }
            r = 0; return true;
        }
        if ((m >= WM_MOUSEFIRST && m <= WM_MOUSELAST) || (m >= WM_KEYFIRST && m <= WM_KEYLAST)) { r = 0; return true; }
        return false;
    }

    // 3. 팝업 해설 카드
    if (frame.cardKind != CardKind::None) {
        if (m == WM_MOUSEWHEEL) {
            int delta = GET_WHEEL_DELTA_WPARAM(w);
            int nextScr = std::max(0, std::min(gCardMaxScroll.load(), frame.cardScroll - (delta / WHEEL_DELTA) * 52));
            if (nextScr != frame.cardScroll) {
                frame.cardScroll = nextScr;
                Present_InvalidateLogical(kCardBodyClip);
            }
            r = 0; return true;
        }
        if (m == WM_KEYDOWN) {
            if (w == VK_ESCAPE || w == VK_SPACE || w == VK_RETURN) closeCard(frame);
            else if (w == 'V') {
                if (frame.cardKind == CardKind::Text && frame.cardIdx >= 0 && frame.cardIdx < (int)gEntries.size() && gEntries[frame.cardIdx].voice > 0) {
                    toggleVoicePreview(frame, gEntries[frame.cardIdx].voice);
                    Present_InvalidateLogical(kCardRect);
                } else if (frame.cardKind == CardKind::Bgm && frame.cardIdx >= 0 && frame.cardIdx < (int)gBgms.size()) {
                    int trk = gBgms[frame.cardIdx].track;
                    if (frame.previewingBgm == trk) stopAudioPreviewAndRestore(frame);
                    else { stopVoicePreview(frame); frame.previewingBgm = trk; playEngineBgm(trk, 1); }
                    Present_InvalidateLogical(kCardRect);
                }
            }
            else if (w == VK_F7) {
                int tab = (frame.cardKind == CardKind::Art) ? 2 : (frame.cardKind == CardKind::Bgm ? 3 : (frame.cardKind == CardKind::Article ? 0 : (frame.cardKind == CardKind::Review ? 4 : 1)));
                openEncyclopedia(frame, tab, std::max(0, frame.cardIdx));
            }
            else if (w == VK_UP)   { frame.cardScroll = std::max(0, frame.cardScroll - 44); Present_InvalidateLogical(kCardBodyClip); }
            else if (w == VK_DOWN) { frame.cardScroll = std::min(gCardMaxScroll.load(), frame.cardScroll + 44); Present_InvalidateLogical(kCardBodyClip); }
            r = 0; return true;
        }
        if (m == WM_RBUTTONDOWN) { closeCard(frame); r = 0; return true; }
        if (m == WM_LBUTTONDOWN) {
            if (!ptIn(kCardRect, frame.mouse) || ptIn(kCardCloseBtn, frame.mouse) || ptIn(kCardOkBtn, frame.mouse)) {
                closeCard(frame); r = 0; return true;
            }
            if (ptIn(kCardEncycBtn, frame.mouse)) {
                int tab = (frame.cardKind == CardKind::Art) ? 2 : (frame.cardKind == CardKind::Bgm ? 3 : (frame.cardKind == CardKind::Article ? 0 : (frame.cardKind == CardKind::Review ? 4 : 1)));
                openEncyclopedia(frame, tab, std::max(0, frame.cardIdx));
                r = 0; return true;
            }
            if (frame.cardKind == CardKind::Bgm && ptIn(kCardAudioBtn, frame.mouse) && frame.cardIdx >= 0 && frame.cardIdx < (int)gBgms.size()) {
                int trk = gBgms[frame.cardIdx].track;
                if (frame.previewingBgm == trk) stopAudioPreviewAndRestore(frame);
                else { stopVoicePreview(frame); frame.previewingBgm = trk; playEngineBgm(trk, 1); }
                Present_InvalidateLogical(kCardRect); r = 0; return true;
            }
            if (frame.cardKind == CardKind::Text && ptIn(kCardAudioBtn, frame.mouse) && frame.cardIdx >= 0 && frame.cardIdx < (int)gEntries.size() && gEntries[frame.cardIdx].voice > 0) {
                toggleVoicePreview(frame, gEntries[frame.cardIdx].voice);
                Present_InvalidateLogical(kCardRect); r = 0; return true;
            }
            if (frame.cardKind == CardKind::Art && frame.artIndices().size() > 1) {
                if (ptIn(kCardPrevArt, frame.mouse)) {
                    frame.cardArtCursor = (frame.cardArtCursor + (int)frame.artIndices().size() - 1) % (int)frame.artIndices().size();
                    frame.cardIdx = frame.artIndices()[frame.cardArtCursor]; frame.cardScroll = 0; Present_InvalidateLogical(kCardRect);
                } else if (ptIn(kCardNextArt, frame.mouse)) {
                    frame.cardArtCursor = (frame.cardArtCursor + 1) % (int)frame.artIndices().size();
                    frame.cardIdx = frame.artIndices()[frame.cardArtCursor]; frame.cardScroll = 0; Present_InvalidateLogical(kCardRect);
                }
            }
            r = 0; return true;
        }
        if ((m >= WM_MOUSEFIRST && m <= WM_MOUSELAST) || (m >= WM_KEYFIRST && m <= WM_KEYLAST)) { r = 0; return true; }
        return false;
    }

    if (!frame.enabled) return false;


    if (m == WM_KEYDOWN && w == VK_F7 && !screensOpen() && !ChartIsOpen()) {
        if (!(l & (1u << 30))) {
            int ts = topScript();
            int defTab = (ts <= 1 || (ts >= 200 && ts <= 499)) ? 4 : 5;
            openEncyclopedia(frame, defTab, 0);
        }
        r = 0; return true;
    }
    if (m == WM_KEYUP && w == VK_F7) { r = 0; return true; }

    if (int tmk = titleMenuKind(frame)) {
        if (m == WM_LBUTTONDOWN && ptIn(titleMenuBtnRect(tmk), frame.mouse)) {
            openEncyclopedia(frame, 4, 0);
            r = 0; return true;
        }
        return false;
    }

    if (!gameplayHudVisible(frame)) return false;

    // 4. 인게임 클릭 처리
    if (m == WM_LBUTTONDOWN) {
        if (ptIn(kBookRect, frame.mouse)) {
            frame.qbarOpen = !frame.qbarOpen;
            saveUserState(frame);
            Present_InvalidateLogical(uniteR(kQbarRect, kBookRect));
            r = 0; return true;
        }
        if (frame.qbarOpen && ptIn(kQbarRect, frame.mouse)) {
            if (ptIn(kQbarModeBtn, frame.mouse)) {
                frame.guideMode = (frame.guideMode + 1) % 3;
                saveUserState(frame);
                Present_InvalidateLogical(uniteR(kQbarRect, kDetPlateRect));
            } else if (ptIn(kQbarArtBtn, frame.mouse)) {
                refreshLiveMedia(frame, true);
                if (!frame.artIndices().empty()) {
                    openCard(frame, CardKind::Art, frame.artIndices().back());
                    frame.cardArtCursor = (int)frame.artIndices().size() - 1;
                } else Toast(L"현재 화면에 해설이 등록된 그림이 없습니다");
            } else if (ptIn(kQbarBgmBtn, frame.mouse)) {
                int trk = liveBgmTrack();
                if (gBgmByTrack.count(trk)) openCard(frame, CardKind::Bgm, gBgmByTrack[trk]);
                else Toast(L"현재 재생 중인 배경음악이 없습니다");
            } else if (ptIn(kQbarEncycBtn, frame.mouse)) {
                openEncyclopedia(frame, 5, 0);
            }
            r = 0; return true;
        }
        if (!frame.artIndices().empty() && ptIn(kArtSealRect, frame.mouse)) {
            openCard(frame, CardKind::Art, frame.artIndices().back());
            frame.cardArtCursor = (int)frame.artIndices().size() - 1;
            r = 0; return true;
        }
        if (choiceActiveNow(frame) && ptIn(kChoicePill, frame.mouse)) {
            openCard(frame, CardKind::Text, frame.activeChoiceEntry);
            r = 0; return true;
        }
        RECT subPill{};
        if (frame.activeSubEntry >= 0 && getSubPillRect(frame, subPill) && ptIn(subPill, frame.mouse)) {
            openCard(frame, CardKind::Text, frame.activeSubEntry);
            r = 0; return true;
        }
        if (activeLineReady(frame)) {
            if (ptIn(kLinePillRect, frame.mouse) ||
                (!autoOn() && frame.guideMode == 1 && ptIn(kOnePlateRect, frame.mouse)) ||
                (!autoOn() && frame.guideMode == 2 && ptIn(kDetPlateRect, frame.mouse))) {
                openCard(frame, CardKind::Text, frame.activeLineEntry);
                r = 0; return true;
            }
            RECT dlg{};
            // 글이 찍히는 중에 대사를 누르면 엔진에 넘겨 글을 마저 찍게 한다(다 찍힌 뒤에 누르면 카드가 열린다).
            // 알약·요약 띠는 찍는 중에도 그대로 카드를 연다. (2026-11-28)
            if (!typingNow() && frame.viewedSerial != frame.lineSerial && frame.mouse.y >= 415 && HiText_DialogueBounds(dlg) && ptIn(inflateR(dlg, 4, 3), frame.mouse)) {
                openCard(frame, CardKind::Text, frame.activeLineEntry);
                r = 0; return true;
            }
        }
    }
    return false;
}

bool Cm_WndProc(HWND h, UINT m, WPARAM w, LPARAM l, LRESULT& r) {
    if (!gModOn || !gLoaded) return false;
    const bool input = (m >= WM_MOUSEFIRST && m <= WM_MOUSELAST) || (m >= WM_KEYFIRST && m <= WM_KEYLAST);
    const bool lifecycle = m == WM_CLOSE || m == WM_DESTROY || m == WM_ENDSESSION || m == WM_SYSCOMMAND ||
                           m == WM_CANCELMODE || m == WM_CAPTURECHANGED || m == WM_ACTIVATE;
    if (!input && !lifecycle && m != gMsgSync && m != gMsgTest && !(m == WM_TIMER && w == kAnimTimer)) return false;
    static UINT ownedButtons = 0; // accessed by the window thread
    if (m == WM_CANCELMODE || m == WM_CAPTURECHANGED ||
        (m == WM_ACTIVATE && LOWORD(w) == WA_INACTIVE)) ownedButtons = 0;
    const bool left = m == WM_LBUTTONDOWN || m == WM_LBUTTONDBLCLK || m == WM_LBUTTONUP;
    const bool right = m == WM_RBUTTONDOWN || m == WM_RBUTTONDBLCLK || m == WM_RBUTTONUP;
    const UINT bit = left ? 1u : 2u;
    const bool up = m == WM_LBUTTONUP || m == WM_RBUTTONUP;
    if (up && (ownedButtons & bit)) {
        ownedButtons &= ~bit; r = 0; return true;
    }
    if (m == WM_LBUTTONDBLCLK) m = WM_LBUTTONDOWN;
    if (m == WM_RBUTTONDBLCLK) m = WM_RBUTTONDOWN;
    WindowEdit edit;
    auto& frame = edit.get();
    const bool handled = handleWindowInput(frame, h, m, w, l, r);
    if (!up && (left || right)) {
        if (handled) ownedButtons |= bit;
        else ownedButtons &= ~bit;
    }
    return handled;
}

static bool commentaryRects(CommentaryFrame& frame, std::vector<RECT>& out) {
    out.clear();
    if (!gModOn || !gLoaded || !Present_Active() || Play_GuideOpen()) return false;
    if (settingsRowVisible()) { out.push_back(kConfRowRect); return true; }
    if (frame.encycOpen || frame.cardKind != CardKind::None) { out.push_back(kFullScreen); return true; }
    if (int tmk = titleMenuKind(frame)) {
        out.push_back(inflateR(titleMenuBtnRect(tmk), 14, 8));
        return true;
    }
    if (!gameplayHudVisible(frame)) return false;

    out.push_back(kBookRect);
    if (frame.qbarOpen) out.push_back(kQbarRect);
    if (!frame.artIndices().empty()) out.push_back(inflateR(kArtSealRect, 12, 8));
    if (choiceActiveNow(frame)) out.push_back(inflateR(kChoicePill, 12, 8));
    RECT subPill{};
    if (frame.activeSubEntry >= 0 && getSubPillRect(frame, subPill)) out.push_back(inflateR(subPill, 12, 8));
    if (activeLineReady(frame)) {
        out.push_back(inflateR(kLinePillRect, 12, 8));
        if (!autoOn() && frame.guideMode == 1) out.push_back(kOnePlateRect);
        else if (!autoOn() && frame.guideMode == 2) out.push_back(kDetPlateRect);
    }
    return !out.empty();
}

static void paintFrame(CommentaryFrame& frame, HDC dc, const Layout& L, const RECT& clip) {
    if (!gModOn || !gLoaded || L.cw <= 0 || L.ch <= 0) return;

    std::vector<RECT> logRects;
    if (!commentaryRects(frame, logRects)) return;

    // 1. 이번 물리 clip 사각형이 우리 위젯과 하나도 겹치지 않으면 0.001ms 만에 즉시 귀환!
    RECT physGame = {L.ox, L.oy, L.ox + L.cw, L.oy + L.ch}, D{};
    if (!IntersectRect(&D, &physGame, &clip)) return;

    bool anyHit = false;
    RECT hitUnion{};
    for (const RECT& lr : logRects) {
        RECT pr = logToPhys(L, lr), ir{};
        if (IntersectRect(&ir, &pr, &D)) {
            hitUnion = anyHit ? uniteR(hitUnion, ir) : ir;
            anyHit = true;
        }
    }
    if (!anyHit) return;

    ensureUiAssets();
    ensureScaledUi(L.cw, L.ch, gameplayHudVisible(frame), frame.cardKind != CardKind::None, frame.encycOpen);

    BLENDFUNCTION bf = {AC_SRC_OVER, 0, 255, AC_SRC_ALPHA};
    int sx = hitUnion.left - L.ox, sy = hitUnion.top - L.oy;
    int dw = hitUnion.right - hitUnion.left, dh = hitUnion.bottom - hitUnion.top;

    if (settingsRowVisible()) {
        buildSettingsLayer(frame, L.cw, L.ch);
        if (gConfLayer.dc) AlphaBlend(dc, hitUnion.left, hitUnion.top, dw, dh, gConfLayer.dc, sx, sy - kConfRowRect.top * L.ch / 600, dw, dh, bf);
        return;
    }
    if (frame.encycOpen) {
        buildEncycLayer(frame, L.cw, L.ch);
        // F7 해설 도감은 화면 전체 불투명이므로 AlphaBlend 대신 초고속 BitBlt(SRCCOPY)!
        if (gEncycLayer.dc) BitBlt(dc, hitUnion.left, hitUnion.top, dw, dh, gEncycLayer.dc, sx, sy, SRCCOPY);
        return;
    }

    if (frame.cardKind != CardKind::None) {
        if (gameplayHudVisible(frame)) {
            buildHudLayer(frame, L.cw, L.ch);
            if (gHudLayer.dc) AlphaBlend(dc, hitUnion.left, hitUnion.top, dw, dh, gHudLayer.dc, sx, sy, dw, dh, bf);
        }
        buildCardLayer(frame, L.cw, L.ch);
        if (gCardLayer.dc) AlphaBlend(dc, hitUnion.left, hitUnion.top, dw, dh, gCardLayer.dc, sx, sy, dw, dh, bf);
        return;
    }

    if (int tmk = titleMenuKind(frame)) {
        buildTitleLayer(frame, L.cw, L.ch, tmk);
        if (gTitleLayer.dc) AlphaBlend(dc, hitUnion.left, hitUnion.top, dw, dh, gTitleLayer.dc, sx, sy, dw, dh, bf);
        return;
    }

    buildHudLayer(frame, L.cw, L.ch);
    if (gHudLayer.dc) AlphaBlend(dc, hitUnion.left, hitUnion.top, dw, dh, gHudLayer.dc, sx, sy, dw, dh, bf);
}

CmPresentationFrame::CmPresentationFrame() {
    if (gModOn && gLoaded && gRenderDepth++ == 0) gRenderFrame = snapshot();
}
CmPresentationFrame::~CmPresentationFrame() { if (gModOn && gLoaded) --gRenderDepth; }

bool Cm_OverlayRects(std::vector<RECT>& out) {
    if (!gModOn || !gLoaded) { out.clear(); return false; }
    CmPresentationFrame view;
    return commentaryRects(gRenderFrame, out);
}
void Cm_PaintOverlays(HDC dc, const Layout& layout, const RECT& clip) {
    if (!gModOn || !gLoaded) return;
    CmPresentationFrame view;
    paintFrame(gRenderFrame, dc, layout, clip);
}

}}  // namespace forest::qol
