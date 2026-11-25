// qol_present.cpp — 「진행」 갈래 시험용 임시 판(넘기지 않는다).
// 1배 그대로 찍되, 그림자 판(800×600)을 두고 겹그림이 걸리는 사각형만 합성해 찍는다.
// 시험 도우미(이 파일에만): 등록 메시지 "ForestQolPlayTest"
//   w=1 상태를 게임 폴더 playtest_state.txt 로, w=2 l=칸 → 엔진 불러오기(Alt+Shift+숫자와 같은 길),
//   w=3 l=값 → 건너뛰기 범위 [0x466460], w=4 → 오른쪽 클릭과 같은 설정 화면 열기(0x410b90)
#include "qol.h"
#include <cstdio>

namespace forest { namespace qol {
namespace {
CRITICAL_SECTION cs;
bool init = false, valid = false;
HDC shDC = nullptr, coDC = nullptr;
HBITMAP shBmp = nullptr, coBmp = nullptr;
HWND wnd = nullptr;
UINT testMsg = 0;

bool makeDib(HDC& dc, HBITMAP& b) {
    BITMAPINFO bi = {}; bi.bmiHeader.biSize = sizeof(bi.bmiHeader); bi.bmiHeader.biWidth = 800; bi.bmiHeader.biHeight = -600;
    bi.bmiHeader.biPlanes = 1; bi.bmiHeader.biBitCount = 32; bi.bmiHeader.biCompression = BI_RGB;
    void* bits = nullptr;
    b = CreateDIBSection(nullptr, &bi, DIB_RGB_COLORS, &bits, nullptr, 0);
    if (!b) return false;
    dc = CreateCompatibleDC(nullptr); SelectObject(dc, b);
    return true;
}
bool hits(const RECT& r) {
    std::vector<RECT> v; Play_OverlayRects(v);
    std::wstring t; float a; if (ToastNow(t, a)) v.push_back(kToastRect);
    for (auto& o : v) { RECT x; if (IntersectRect(&x, &o, &r)) return true; }
    return false;
}
void compose(HDC d, RECT r) {
    RECT all = {0, 0, 800, 600};
    if (!IntersectRect(&r, &r, &all)) return;
    int w = r.right - r.left, h = r.bottom - r.top;
    if (hits(r)) {
        BitBlt(coDC, r.left, r.top, w, h, shDC, r.left, r.top, SRCCOPY);
        HRGN rg = CreateRectRgn(r.left, r.top, r.right, r.bottom);
        SelectClipRgn(coDC, rg); DeleteObject(rg);
        Play_PaintOverlays(coDC, Layout(), r);
        SelectClipRgn(coDC, nullptr);
        GdiFlush();
        BitBlt(d, r.left, r.top, w, h, coDC, r.left, r.top, SRCCOPY);
    } else {
        BitBlt(d, r.left, r.top, w, h, shDC, r.left, r.top, SRCCOPY);
    }
}
void dumpState() {
    auto I = [](uintptr_t a) { return *(volatile int*)a; };
    auto W = [](uintptr_t a) { return (int)*(volatile uint16_t*)a; };
    char buf[2048]; int n = 0;
    void* sc = *(void**)0x46639c;
    uint32_t pc = 0; int sid = -1;
    if (sc) { auto base = *(uint8_t**)sc; auto cur = *(uint8_t**)((uint8_t*)sc + 0x44); sid = *(uint16_t*)((uint8_t*)sc + 0x3c); pc = (uint32_t)(cur - base); }
    int d = W(0x4664bc);
    n += sprintf_s(buf + n, sizeof(buf) - n, "tick=%lu sid=%d pc=%u depth=%d stack=", GetTickCount(), sid, pc, d);
    for (int i = 0; i <= d && i < 16; ++i) n += sprintf_s(buf + n, sizeof(buf) - n, "%s%04d", i ? ">" : "", W(0x46647e + i * 2));
    uint8_t* mw = *(uint8_t**)0x46630c;
    n += sprintf_s(buf + n, sizeof(buf) - n,
        "\nauto=%d clickwait=%d typing=%d ctrlkey=%d ctrlskip=%d tabreq=%d tabskip=%d choice=%d select=%d settings=%d savescr=%d loadscr=%d hidden=%d"
        "\nskiprange=%d saveok=%d ckok=%d menulock=%d chart=%d bar_active=%d bar_hidden=%d autobtn_cb=%08x menubtn_cb=%08x\n",
        I(0x466408), I(0x4663e8), I(0x4663e0), I(0x4663f8), I(0x466400), I(0x4663fc), I(0x466404), I(0x4663cc), I(0x466418),
        I(0x46640c), I(0x466410), I(0x466414), I(0x466420), W(0x466460), I(0x4664cc), I(0x4664d0), W(0x466430), ChartIsOpen() ? 1 : 0,
        mw ? *(int*)(mw + 0x2c74) : -1, mw ? *(int*)(mw + 0x2c7c) : -1, mw ? *(int*)(mw + 0x2c94) : 0, mw ? *(int*)(mw + 0x2c8c) : 0);
    std::wstring p = Root() + L"\\playtest_state.txt";
    HANDLE f = CreateFileW(p.c_str(), GENERIC_WRITE, FILE_SHARE_READ, nullptr, CREATE_ALWAYS, 0, nullptr);
    if (f != INVALID_HANDLE_VALUE) { DWORD k; WriteFile(f, buf, (DWORD)n, &k, nullptr); CloseHandle(f); }
}
}  // namespace

bool Present_Install() {
    // 시험 전용: 다른 갈래의 시험 Forest 가 떠 있어도 띄울 수 있게 중복 실행 뮤텍스 이름(0x462ab8 "RSCRIPT")을 바꾼다
    if (Cfg("playtest_mutex", 0)) {
        static const char from[8] = "RSCRIPT", to[8] = "RSCRIPQ";
        if (PatchBytes(0x462ab8, from, to, 8)) Log("playtest: mutex renamed");
    }
    InitializeCriticalSection(&cs);
    if (!makeDib(shDC, shBmp) || !makeDib(coDC, coBmp)) return false;
    testMsg = RegisterWindowMessageW(L"ForestQolPlayTest");
    init = true;
    return true;
}
void Present_WindowReady(HWND h) { wnd = h; }
bool Present_WndProc(HWND, UINT m, WPARAM w, LPARAM l, LRESULT& r) {
    if (!testMsg || m != testMsg) return false;
    if (w == 1) dumpState();
    else if (w == 2) {
        int ok = ((int(__cdecl*)(unsigned))0x418bb0)((unsigned)l);
        Log("playtest: load slot " + std::to_string((int)l) + (ok ? " ok" : " failed"));
        if (ok) ((void(__thiscall*)(void*, int, int))0x43d910)(*(void**)0x466398, *(uint16_t*)0x4663a6, 0);
    } else if (w == 3) { *(volatile uint16_t*)0x466460 = (uint16_t)l; Log("playtest: skip range " + std::to_string((int)l)); }
    else if (w == 4) { void* mw = *(void**)0x46630c; if (mw) ((void(__thiscall*)(void*))0x410b90)(mw); Log("playtest: menu path"); }
    r = 0; return true;
}
void Present_MapMouse(UINT, LPARAM&) {}
bool Present_BitBlt(HDC d, int x, int y, int w, int h, HDC s, int sx, int sy, DWORD, BOOL& ret) {
    if (!init) return false;
    EnterCriticalSection(&cs);
    BitBlt(shDC, x, y, w, h, s, sx, sy, SRCCOPY);
    if (x <= 0 && y <= 0 && x + w >= 800 && y + h >= 600) valid = true;
    if (!ChartIsOpen()) compose(d, RECT{x, y, x + w, y + h});
    LeaveCriticalSection(&cs);
    ret = TRUE;
    return true;
}
bool Present_StretchBlt(HDC, int, int, int, int, HDC, int, int, int, int, DWORD, BOOL&) { return false; }
void Present_InvalidateLogical(const RECT& r) {
    if (!init || !valid || !wnd || ChartIsOpen()) return;
    EnterCriticalSection(&cs);
    HDC d = GetDC(wnd);
    if (d) { compose(d, r); ReleaseDC(wnd, d); }
    LeaveCriticalSection(&cs);
}
POINT Present_ToClient(int x, int y) { return POINT{x, y}; }
Layout CurrentLayout() { return Layout(); }

}}  // namespace forest::qol
