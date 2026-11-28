// qol_core.cpp — 편의 기능 공용 바탕(통합 세션 몫).
#include "qol.h"
#include <cstring>
#include <cstdlib>
#include <imm.h>

namespace forest { namespace qol {
namespace {
std::wstring gRoot;
HWND gWnd = nullptr;
std::map<std::string, int> gCfg;
bool gCfgRead = false;
bool gAll = true;
CRITICAL_SECTION gToastCs;
bool gToastInit = false;
std::wstring gToast;
DWORD gToastStart = 0, gToastUntil = 0;
std::string gInstallLog;

// The two native history stores and the message-window lifetime run before or
// inside the owning engine operation. Only the published value crosses threads.
volatile LONG gHistoryState = -1;  // -1 retired, 0 current line, 1 history
bool gHistoryInstalled = false;

__declspec(naked) void historyOpen() {
    __asm {
        mov dword ptr [esi + 2c70h], 1
        push eax
        mov eax, 1
        xchg eax, gHistoryState
        pop eax
        ret
    }
}
__declspec(naked) void historyClose() {
    __asm {
        mov dword ptr [esi + 2c70h], 0
        push eax
        mov eax, 0
        xchg eax, gHistoryState
        pop eax
        ret
    }
}
__declspec(naked) void historyCreate() {
    __asm {
        mov dword ptr ds:[46630ch], eax
        push eax
        mov eax, 0
        xchg eax, gHistoryState
        pop eax
        ret
    }
}
__declspec(naked) void historyRetire() {
    __asm {
        mov eax, -1
        xchg eax, gHistoryState
        mov eax, dword ptr ds:[46630ch]
        ret
    }
}

bool installHistoryState() {
    struct Site { uintptr_t at; void (*handler)(); size_t size; uint8_t original[10]; };
    const Site sites[] = {
        {0x410b2b, historyOpen,   10, {0xc7,0x86,0x70,0x2c,0,0,1,0,0,0}},
        {0x4109f1, historyClose,  10, {0xc7,0x86,0x70,0x2c,0,0,0,0,0,0}},
        {0x414ae4, historyCreate,  5, {0xa3,0x0c,0x63,0x46,0}},
        {0x415234, historyRetire,  5, {0xa1,0x0c,0x63,0x46,0}},
    };
    for (const auto& s : sites)
        if (memcmp((void*)s.at, s.original, s.size)) return false;
    for (const auto& s : sites) {
        uint8_t call[10];
        memset(call, 0x90, sizeof(call)); call[0] = 0xe8;
        const int32_t offset = (int32_t)((uintptr_t)s.handler - s.at - 5);
        memcpy(call + 1, &offset, 4);
        if (!PatchBytes(s.at, s.original, call, s.size)) {
            for (const auto& prior : sites) {
                if (&prior == &s) break;
                PatchBytes(prior.at, nullptr, prior.original, prior.size);
            }
            return false;
        }
    }
    return true;
}

void readCfg() {
    if (gCfgRead) return;
    gCfgRead = true;
    if (gRoot.empty()) {
        wchar_t path[MAX_PATH]; GetModuleFileNameW(nullptr, path, MAX_PATH);
        gRoot = path; gRoot.resize(gRoot.find_last_of(L"\\/"));
    }
    HANDLE f = CreateFileW((gRoot + L"\\forest-qol.ini").c_str(), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_EXISTING, 0, nullptr);
    if (f == INVALID_HANDLE_VALUE) return;
    char buf[8192] = {}; DWORD n = 0; ReadFile(f, buf, sizeof(buf) - 1, &n, nullptr); CloseHandle(f);
    char* ctx = nullptr;
    for (char* line = strtok_s(buf, "\r\n", &ctx); line; line = strtok_s(nullptr, "\r\n", &ctx)) {
        while (*line == ' ' || *line == '\t') ++line;
        if (!*line || *line == ';' || *line == '#' || *line == '[') continue;
        char* eq = strchr(line, '='); if (!eq) continue;
        *eq = 0; std::string k = line; while (!k.empty() && (k.back() == ' ' || k.back() == '\t')) k.pop_back();
        gCfg[k] = atoi(eq + 1);
    }
}
}  // namespace

UINT ShortcutKey(HWND window, WPARAM key, LPARAM messageBits) {
    if (key != VK_PROCESSKEY) return (UINT)key;
    UINT original = ImmGetVirtualKey(window);
    if (original && original != VK_PROCESSKEY) return original;
    // TranslateMessage can consume the original key before the window procedure.
    UINT scan = (UINT(messageBits) >> 16) & 0xff;
    if (!scan) return VK_PROCESSKEY;
    if (messageBits & (1u << 24)) scan |= 0xe000;
    return MapVirtualKeyExW(scan, MAPVK_VSC_TO_VK_EX, GetKeyboardLayout(0));
}

bool History_Open() { return InterlockedCompareExchange(&gHistoryState, 0, 0) == 1; }
bool History_WindowAvailable() { return gHistoryInstalled && InterlockedCompareExchange(&gHistoryState, 0, 0) >= 0; }
// 게임 화면이 내려가 있는 동안(엔진 0x415234 해제 ~ 0x414ae4 다시 만들기) 참. 갈고리를 못 걸었으면 늘 거짓(모른다).
bool History_Retired() { return gHistoryInstalled && InterlockedCompareExchange(&gHistoryState, 0, 0) < 0; }

const RECT kToastRect = {12, 10, 520, 46};

int Cfg(const char* key, int def) {
    readCfg();
    if (strcmp(key, "qol") != 0 && !gAll) return 0;
    auto it = gCfg.find(key);
    return it == gCfg.end() ? def : it->second;
}
const std::wstring& Root() { readCfg(); return gRoot; }
HWND GameWindow() { return gWnd; }

bool PatchBytes(uintptr_t at, const void* expect, const void* bytes, size_t n) {
    if (expect && memcmp((void*)at, expect, n) != 0) return false;
    DWORD old = 0;
    if (!VirtualProtect((void*)at, n, PAGE_EXECUTE_READWRITE, &old)) return false;
    memcpy((void*)at, bytes, n);
    DWORD ignored; VirtualProtect((void*)at, n, old, &ignored);
    FlushInstructionCache(GetCurrentProcess(), (void*)at, n);
    return true;
}

void Toast(const wchar_t* text, DWORD ms) {
    if (!gToastInit) return;
    {
        EnterCriticalSection(&gToastCs);
        gToast = text ? text : L"";
        gToastStart = GetTickCount(); gToastUntil = gToastStart + ms;
        LeaveCriticalSection(&gToastCs);
    }
    Present_InvalidateLogical(kToastRect);
}
bool ToastNow(std::wstring& text, float& alpha) {
    if (!gToastInit) return false;
    EnterCriticalSection(&gToastCs);
    DWORD now = GetTickCount();
    bool on = !gToast.empty() && (int)(gToastUntil - now) > 0;
    if (on) {
        text = gToast;
        DWORD left = gToastUntil - now;
        alpha = left < 400 ? left / 400.f : 1.f;
    }
    LeaveCriticalSection(&gToastCs);
    return on;
}

void PaintAbove(HDC dc, const Layout& L, const RECT& clip) {
    if (!Cm_CoversScreen()) {
        HiArt_PaintBase(dc, L, clip);
        HiText_Paint(dc, L, clip);
        Play_PaintOverlays(dc, L, clip);
    }
    Cm_PaintOverlays(dc, L, clip);
}
bool AboveRects(std::vector<RECT>& out) {
    out.clear();
    std::vector<RECT> a, b, c, d;
    HiArt_Rects(c); HiText_Rects(a); Play_OverlayRects(b); Cm_OverlayRects(d);
    out.insert(out.end(), c.begin(), c.end());
    out.insert(out.end(), a.begin(), a.end());
    out.insert(out.end(), b.begin(), b.end());
    out.insert(out.end(), d.begin(), d.end());
    return !out.empty();
}

void Core_Install() {
    readCfg();
    gAll = Cfg("qol", 1) != 0;
    InitializeCriticalSection(&gToastCs); gToastInit = true;
    // 설치는 게임 진입점 전이라 지도 기록이 아직 안 열렸다 → 결과를 모아 두었다가 창이 준비되면 남긴다.
    if (!gAll) {
        // 모두 끔: 아이콘 줄 모듈만 불러 낱 그림 파일(grps\compane.lwg)을 가리게 한다(Cfg 가 모두 0 이라 그 길로 감).
        Buttons_Install();
        gInstallLog = "qol: all features off (forest-qol.ini qol=0)";
        return;
    }
    gHistoryInstalled = installHistoryState();
    gInstallLog = std::string("qol: history ") + (gHistoryInstalled ? "ok; " : "unavailable; ");
    gInstallLog += std::string("qol: present ") + (Present_Install() ? "ok" : "off");
    gInstallLog += std::string("; qol: play ") + (Play_Install() ? "ok" : "off");
    gInstallLog += std::string("; qol: buttons ") + (Buttons_Install() ? "ok" : "off");
    gInstallLog += std::string("; qol: hitext ") + (HiText_Install() ? "ok" : "off");
    gInstallLog += std::string("; qol: hiart ") + (HiArt_Install() ? "ok" : "off");
    gInstallLog += std::string("; qol: rewind ") + (Rewind_Install() ? "ok" : "off");
    gInstallLog += std::string("; qol: cm ") + (Cm_Install() ? "ok" : "off");
}
void Core_WindowReady(HWND h) {
    gWnd = h;
    if (!gInstallLog.empty()) { Log(gInstallLog); gInstallLog.clear(); }
    if (!gAll) return;
    Present_WindowReady(h);
    Play_WindowReady(h);
    Buttons_WindowReady(h);
    HiText_WindowReady(h);
    HiArt_WindowReady(h);
    Cm_WindowReady(h);
}

}}  // namespace forest::qol
