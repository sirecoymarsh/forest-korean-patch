// qol_present.cpp — 화면 모듈(세션 「화면」 몫, 2026-11-21).
//
// 하는 일
//   1. 그림자 판: 게임 창으로 가는 BitBlt/StretchBlt 를 800×600 그림자 DIB 에 그대로 옮겨 두고, 창 크기에 맞춰 찍는다.
//      지도가 열려 있으면 그림자만 갱신한다(지도는 스스로 창 크기에 맞춰 그린다).
//   2. 늘려 찍기: 4:3 을 지키고 남는 곳은 검게. 화소마다 같은 전역 대응 u=(X+0.5)·800/cw−0.5 의 이중선형이라
//      부분 사각형만 다시 찍어도 전체를 찍은 것과 화소가 같다. 1배(800×600 그림)면 그림자에서 바로 BitBlt 한다.
//   3. 겹그림: 찍기 직전 물리 크기 뒷판에 PaintAbove(4K 글자 → 겹그림)를 부른다. 자리는 AboveRects.
//   4. 창: 끌어서 크기 조절·최대화·최소화, 창 메뉴의 1배·2배·3배, 끄는 동안 4:3 유지(설정).
//   5. 전체 화면: 엔진의 0x43cce0 입구를 바꿔 해상도는 그대로 두고 창이 있는 모니터를 테두리 없이 덮는다(맨 위 고정 없음).
//      Alt+Enter·원작 설정 「전체 화면/창」·Alt+F/W 모두 이 길로 들어온다.
//   6. 창 자리 기억: forest-qol-window.ini (끊긴 모니터 위 자리는 쓰지 않음).
//   7. 오프닝 영상 자식 창을 그림 자리에 맞추고, 확인 창(MessageBox)을 게임 그림 가운데에 띄운다.
//
// 설정(forest-qol.ini): present=1, present_smooth=1(0 = 가장 가까운 화소), window_memory=1, borderless_fullscreen=1,
//   window_keep_aspect=1. 시험 전용: present_test_shift_x=N(창 자리를 N 화소 오른쪽으로 옮겨 사용자 화면 밖에서 돌린다).
//
// 엔진 근거(Forest.exe f618b6…): 창 스타일 push 0x82c80000 @0x417e03(창 만들기 0x43c810 에 넘김, [엔진+0x2a0] 에 남음),
//   전체 화면 thiscall 0x43cce0(flag): 부르는 곳 0x40a3ad/0x40a3ed(설정 화면, word[0x46644c] 를 먼저 씀), 0x415699/0x4156b6(Alt+F/W,
//   [0x46e920] 을 먼저 씀), 0x43cafb(시작, 돌아갈 곳 0x43cb00), 0x43ccd0(끝내기, 돌아갈 곳 0x43ccd5).
//   창으로 찍는 곳: 0x43d050(전체) 0x43d0e0(사각형) 0x43d170(흔들림 오프셋) — 모두 GetDC(게임 창)+BitBlt(SRCCOPY).
//   영상: 0x4467dc MpegWindowClass 자식을 GetClientRect(부모) 크기로 만들고 MCI_PUT 으로 자식 클라이언트 전체에 그린다.
#include "qol.h"
#include <intrin.h>
#include <emmintrin.h>
#include <windowsx.h>
#include <mmsystem.h>
#include <digitalv.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>

#pragma intrinsic(_ReturnAddress)

namespace forest { namespace qol {
namespace {

constexpr int kW = 800, kH = 600;

// ---------------------------------------------------------------- 엔진 주소
constexpr uintptr_t kEngineGlobal = 0x466398;     // [ ] 엔진(화면) 객체
constexpr uintptr_t kFsFunc = 0x43cce0;           // 전체 화면 전환 thiscall(int flag), ret 4
constexpr uintptr_t kFsRetInit = 0x43cb00;        // 시작 때 부른 곳의 돌아갈 자리
constexpr uintptr_t kFsRetQuit = 0x43ccd5;        // 끝낼 때(전체 화면이면 창으로 되돌림)
constexpr uintptr_t kFsAltFlag = 0x46e920;        // Alt+F/W 가 먼저 쓰는 값
constexpr uintptr_t kFsSetting = 0x46644c;        // 설정 화면 「전체 화면/창」 u16(설정 파일에 남는다)
constexpr uintptr_t kStylePush = 0x417e03;        // push 0x82c80000 (게임 창 스타일)
constexpr uintptr_t kRetMainCreate = 0x43c902;    // 게임 창 CreateWindowExA 의 돌아갈 자리
constexpr uintptr_t kIatCreateWindowEx = 0x45928c, kIatShowWindow = 0x459298, kIatMessageBox = 0x459260, kIatMci = 0x4592b4;
constexpr int kOffFull = 0x1f8, kOffStyle = 0x2a0, kOffExStyle = 0x2a8;

constexpr UINT kMenuScale1 = 0xEED0, kMenuScale2 = 0xEEE0, kMenuScale3 = 0xEEF0, kMenuFull = 0xEF00;   // 창 메뉴(16의 배수, < 0xF000)
constexpr UINT_PTR kOverlayTimer = 0xF0E60;

// ---------------------------------------------------------------- 설정·상태
bool gOn = false, gSmooth = true, gMemory = true, gBorderless = true, gKeepAspect = true;
int gShift = 0;                                   // 시험: 창 자리를 오른쪽으로 옮긴다
HWND gWnd = nullptr;
UINT gMsgRepaint = 0, gMsgSetup = 0;

CRITICAL_SECTION gCs;                             // 그림자·뒷판·대응표(두 스레드)
CRITICAL_SECTION gPendCs;                         // 다시 찍을 사각형(잎 잠금)
CRITICAL_SECTION gLogCs;
std::vector<std::string> gEarly;                  // 지도 로그가 준비되기 전 줄
bool gLogReady = false;

// 그림자 판(800×600, 위에서 아래로 32비트)
HDC gShDC = nullptr; HBITMAP gShBmp = nullptr; uint32_t* gSh = nullptr;
// 물리 크기 뒷판(창 클라이언트 크기)
HDC gBkDC = nullptr; HBITMAP gBkBmp = nullptr; uint32_t* gBk = nullptr; int gBkW = 0, gBkH = 0;
// 지금 대응
Layout gL{0, 0, 0, 0, 0, 0};
bool gSmoothBuilt = true;
struct Axis { std::vector<int> i0, i1; std::vector<uint16_t> f; };
Axis gAX, gAY;
std::vector<uint16_t> gWx;                        // 가로 무게, 화소당 4칸(SSE2)
std::vector<uint32_t> gLine[2];
int gLineRow[2] = {-1, -1};

// 다시 찍기 요청
std::vector<RECT> gPending;
volatile LONG gRepaintPosted = 0;
std::vector<RECT> gLastOverlay;
bool gOverlayTimer = false;

// 시간 재기
struct Stat { int n = 0; double sum = 0, max = 0; };
Stat gTFull, gTPart;
int gStatW = 0, gStatH = 0;
LARGE_INTEGER gQpf{};

// 창 자리·전체 화면
using CreateWindowExAFn = HWND(WINAPI*)(DWORD, LPCSTR, LPCSTR, DWORD, int, int, int, int, HWND, HMENU, HINSTANCE, LPVOID);
using ShowWindowFn = BOOL(WINAPI*)(HWND, int);
using MessageBoxAFn = int(WINAPI*)(HWND, LPCSTR, LPCSTR, UINT);
using MciFn = MCIERROR(WINAPI*)(MCIDEVICEID, UINT, DWORD_PTR, DWORD_PTR);
using FsFn = void(__thiscall*)(void*, int);
CreateWindowExAFn origCreateWindowExA = nullptr;
ShowWindowFn origShowWindow = nullptr;
MessageBoxAFn origMessageBoxA = nullptr;
MciFn origMci = nullptr;
void* gFsTramp = nullptr;                         // 원래 0x43cce0(전체 화면 끔 설정일 때)

struct Memory { bool valid = false; RECT rc{}; bool maximized = false; };
Memory gMem;                                      // 읽은 기억
RECT gNormal{};                                   // 지금 창(최대화·전체 화면 아닐 때) 바깥 사각형, 시험 이동을 뺀 화면 좌표
bool gHaveNormal = false, gMax = false;
bool gPendingMax = false;                         // 첫 ShowWindow 에서 최대화
volatile bool gTransition = false;                // 우리가 창을 바꾸는 중(자리 기억 멈춤). 다른 스레드가 보낸 창 메시지에서도 읽는다
bool gSavedMax = false;                           // 전체 화면 들어가기 전 최대화였나

// 영상
MCIDEVICEID gMovieDev = 0;
HWND gMovieWnd = nullptr;

// 지도 다리가 서기 전(오프닝 영상 동안)에도 창 일을 받으려고 첫 ShowWindow 때 미리 서브클래스한다.
WNDPROC gEngineProc = nullptr;
volatile bool gBridgeReady = false;

// ---------------------------------------------------------------- 로그
void plog(const std::string& s) {
    EnterCriticalSection(&gLogCs);
    if (gLogReady) { LeaveCriticalSection(&gLogCs); Log("present: " + s); return; }
    if (gEarly.size() < 200) gEarly.push_back(s);
    if (gShift) {   // 시험: 지도 로그가 서기 전에 게임이 끝나도 남도록 따로 적는다
        HANDLE f = CreateFileW((Root() + L"\\forest-qol-present-early.log").c_str(), FILE_APPEND_DATA, FILE_SHARE_READ, nullptr, OPEN_ALWAYS, 0, nullptr);
        if (f != INVALID_HANDLE_VALUE) { std::string l = std::to_string(GetTickCount64()) + " " + s + "\r\n"; DWORD n; WriteFile(f, l.data(), (DWORD)l.size(), &n, nullptr); CloseHandle(f); }
    }
    LeaveCriticalSection(&gLogCs);
}
std::string rs(const RECT& r) {
    char b[96]; sprintf_s(b, "(%ld,%ld)-(%ld,%ld) %ldx%ld", r.left, r.top, r.right, r.bottom, r.right - r.left, r.bottom - r.top);
    return b;
}
double nowMs() { LARGE_INTEGER t; QueryPerformanceCounter(&t); return t.QuadPart * 1000.0 / gQpf.QuadPart; }

uint8_t* engine() { return *(uint8_t**)kEngineGlobal; }
bool engineFull() { uint8_t* e = engine(); return e && *(int*)(e + kOffFull) != 0; }

// ---------------------------------------------------------------- 대응 계산
Layout computeLayout(int w, int h) {
    Layout L; L.clientW = w; L.clientH = h;
    if (w <= 0 || h <= 0) { L.cw = L.ch = L.ox = L.oy = 0; return L; }
    if ((int64_t)w * kH <= (int64_t)h * kW) { L.cw = w; L.ch = (int)(((int64_t)w * kH + kW / 2) / kW); }
    else { L.ch = h; L.cw = (int)(((int64_t)h * kW + kH / 2) / kH); }
    L.cw = std::max(1, std::min(L.cw, w)); L.ch = std::max(1, std::min(L.ch, h));
    L.ox = (w - L.cw) / 2; L.oy = (h - L.ch) / 2;
    return L;
}
Layout clientLayout(HWND h) {
    RECT rc{};
    if (!h || !GetClientRect(h, &rc)) return computeLayout(kW, kH);
    return computeLayout(rc.right - rc.left, rc.bottom - rc.top);
}
bool identity(const Layout& L) { return L.cw == kW && L.ch == kH; }

void buildAxis(Axis& a, int dst, int src, bool smooth) {
    a.i0.assign(dst, 0); a.i1.assign(dst, 0); a.f.assign(dst, 0);
    for (int X = 0; X < dst; ++X) {
        if (smooth) {
            double u = (X + 0.5) * src / dst - 0.5;
            int i = (int)std::floor(u);
            double fr = u - i;
            if (i < 0) { i = 0; fr = 0; }
            if (i >= src - 1) { i = src - 1; fr = 0; }
            int f = (int)std::lround(fr * 256.0);
            int j = std::min(i + 1, src - 1);
            if (f >= 256) { i = j; f = 0; }
            a.i0[X] = i; a.i1[X] = f ? j : i; a.f[X] = (uint16_t)f;
        } else {
            int i = (int)std::floor((X + 0.5) * src / dst);
            i = std::max(0, std::min(i, src - 1));
            a.i0[X] = a.i1[X] = i; a.f[X] = 0;
        }
    }
}

bool makeDib(int w, int h, HDC& dc, HBITMAP& bmp, uint32_t*& bits) {
    BITMAPINFO bi{}; bi.bmiHeader.biSize = sizeof(bi.bmiHeader); bi.bmiHeader.biWidth = w; bi.bmiHeader.biHeight = -h;
    bi.bmiHeader.biPlanes = 1; bi.bmiHeader.biBitCount = 32; bi.bmiHeader.biCompression = BI_RGB;
    void* p = nullptr;
    HBITMAP b = CreateDIBSection(nullptr, &bi, DIB_RGB_COLORS, &p, nullptr, 0);
    if (!b) return false;
    HDC d = CreateCompatibleDC(nullptr);
    if (!d) { DeleteObject(b); return false; }
    SelectObject(d, b);
    memset(p, 0, (size_t)w * h * 4);
    dc = d; bmp = b; bits = (uint32_t*)p;
    return true;
}
void freeDib(HDC& dc, HBITMAP& bmp, uint32_t*& bits) {
    if (dc) DeleteDC(dc);
    if (bmp) DeleteObject(bmp);
    dc = nullptr; bmp = nullptr; bits = nullptr;
}

void logStats(const char* why) {
    if (gTFull.n == 0 && gTPart.n == 0) return;
    char b[256];
    sprintf_s(b, "timing %dx%d (%s): full n=%d avg=%.2fms max=%.2fms; part n=%d avg=%.3fms max=%.2fms", gStatW, gStatH, why,
              gTFull.n, gTFull.n ? gTFull.sum / gTFull.n : 0.0, gTFull.max, gTPart.n, gTPart.n ? gTPart.sum / gTPart.n : 0.0, gTPart.max);
    plog(b);
    gTFull = Stat(); gTPart = Stat();
}

// 잠금 안에서: 창 크기가 바뀌었으면 대응표·뒷판을 새로 만든다.
bool ensureLayout() {
    Layout L = clientLayout(gWnd);
    if (L.clientW == gL.clientW && L.clientH == gL.clientH && gSmoothBuilt == gSmooth && (gBk || identity(L))) return L.cw > 0;
    if (L.clientW != gStatW || L.clientH != gStatH) { logStats("size change"); gStatW = L.clientW; gStatH = L.clientH; }
    gL = L;
    if (L.cw <= 0) return false;
    buildAxis(gAX, L.cw, kW, gSmooth); buildAxis(gAY, L.ch, kH, gSmooth); gSmoothBuilt = gSmooth;
    gWx.assign((size_t)L.cw * 4 + 8, 0);
    for (int X = 0; X < L.cw; ++X) for (int k = 0; k < 4; ++k) gWx[(size_t)X * 4 + k] = gAX.f[X];
    gLine[0].assign((size_t)L.cw + 8, 0); gLine[1].assign((size_t)L.cw + 8, 0);
    if (gBkW != L.clientW || gBkH != L.clientH || !gBk) {
        freeDib(gBkDC, gBkBmp, gBk); gBkW = gBkH = 0;
        if (makeDib(L.clientW, L.clientH, gBkDC, gBkBmp, gBk)) { gBkW = L.clientW; gBkH = L.clientH; }
        else plog("back buffer allocation failed " + std::to_string(L.clientW) + "x" + std::to_string(L.clientH));
    }
    return true;
}

// ---------------------------------------------------------------- 늘려 찍기(SSE2)
inline uint32_t lerp1(uint32_t a, uint32_t b, uint32_t f) {
    uint32_t g = 256 - f;
    uint32_t rb = (((a & 0x00ff00ffu) * g + (b & 0x00ff00ffu) * f) >> 8) & 0x00ff00ffu;
    uint32_t ag = ((((a >> 8) & 0x00ff00ffu) * g + ((b >> 8) & 0x00ff00ffu) * f)) & 0xff00ff00u;
    return rb | ag;
}
void hline(const uint32_t* row, int xa, int xb, uint32_t* out) {
    const int* i0 = gAX.i0.data(); const int* i1 = gAX.i1.data(); const uint16_t* w = gWx.data();
    const __m128i z = _mm_setzero_si128(), c256 = _mm_set1_epi16(256);
    int X = xa;
    for (; X + 2 <= xb; X += 2) {
        __m128i a = _mm_unpacklo_epi8(_mm_set_epi32(0, 0, (int)row[i0[X + 1]], (int)row[i0[X]]), z);
        __m128i b = _mm_unpacklo_epi8(_mm_set_epi32(0, 0, (int)row[i1[X + 1]], (int)row[i1[X]]), z);
        __m128i wt = _mm_loadu_si128((const __m128i*)(w + (size_t)X * 4));
        __m128i r = _mm_srli_epi16(_mm_add_epi16(_mm_mullo_epi16(a, _mm_sub_epi16(c256, wt)), _mm_mullo_epi16(b, wt)), 8);
        _mm_storel_epi64((__m128i*)(out + (X - xa)), _mm_packus_epi16(r, z));
    }
    for (; X < xb; ++X) out[X - xa] = lerp1(row[i0[X]], row[i1[X]], gAX.f[X]);
}
void vline(const uint32_t* h0, const uint32_t* h1, int n, int fy, uint32_t* out) {
    if (fy == 0) { memcpy(out, h0, (size_t)n * 4); return; }
    const __m128i z = _mm_setzero_si128(), wt = _mm_set1_epi16((short)fy), iw = _mm_set1_epi16((short)(256 - fy));
    int i = 0;
    for (; i + 4 <= n; i += 4) {
        __m128i a = _mm_loadu_si128((const __m128i*)(h0 + i)), b = _mm_loadu_si128((const __m128i*)(h1 + i));
        __m128i lo = _mm_srli_epi16(_mm_add_epi16(_mm_mullo_epi16(_mm_unpacklo_epi8(a, z), iw), _mm_mullo_epi16(_mm_unpacklo_epi8(b, z), wt)), 8);
        __m128i hi = _mm_srli_epi16(_mm_add_epi16(_mm_mullo_epi16(_mm_unpackhi_epi8(a, z), iw), _mm_mullo_epi16(_mm_unpackhi_epi8(b, z), wt)), 8);
        _mm_storeu_si128((__m128i*)(out + i), _mm_packus_epi16(lo, hi));
    }
    for (; i < n; ++i) out[i] = lerp1(h0[i], h1[i], (uint32_t)fy);
}
const uint32_t* srcLine(int r, int xa, int xb) {
    if (gLineRow[0] == r) return gLine[0].data();
    if (gLineRow[1] == r) return gLine[1].data();
    int slot = gLineRow[0] < gLineRow[1] ? 0 : 1;     // 줄은 늘 아래로만 가므로 더 위 줄을 버린다
    hline(gSh + (size_t)r * kW, xa, xb, gLine[slot].data());
    gLineRow[slot] = r;
    return gLine[slot].data();
}
// 그림 안 좌표 [xa,xb)×[ya,yb) 를 뒷판(클라이언트 좌표)에 채운다.
void scaleRect(int xa, int xb, int ya, int yb) {
    int n = xb - xa;
    if (n <= 0 || yb <= ya || !gBk) return;
    gLineRow[0] = gLineRow[1] = -1;
    for (int Y = ya; Y < yb; ++Y) {
        int fy = gAY.f[Y];
        const uint32_t* h0 = srcLine(gAY.i0[Y], xa, xb);
        const uint32_t* h1 = fy ? srcLine(gAY.i1[Y], xa, xb) : h0;
        vline(h0, h1, n, fy, gBk + (size_t)(gL.oy + Y) * gBkW + gL.ox + xa);
    }
}
// 논리 [a,b) 에 기대는 그림 안 화소 범위(대응표가 단조라 앞뒤에서 찾는다)
void span(const Axis& ax, int a, int b, int& lo, int& hi) {
    int n = (int)ax.i0.size();
    lo = 0; while (lo < n && ax.i1[lo] < a) ++lo;
    hi = n; while (hi > lo && ax.i0[hi - 1] > b - 1) --hi;
}

bool rectsHit(const RECT& a, const RECT& b) { return a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom; }
// 지금 겹그림 자리(논리 좌표). 알림은 공용 바탕이 갖고 있으니 함께 센다.
void overlayRects(std::vector<RECT>& out) {
    out.clear();
    AboveRects(out);
    std::wstring t; float a = 0;
    if (ToastNow(t, a)) out.push_back(kToastRect);
}
void paintOverlays(const RECT& P) {
    HRGN rg = CreateRectRgn(P.left, P.top, P.right, P.bottom);
    SelectClipRgn(gBkDC, rg);
    DeleteObject(rg);
    PaintAbove(gBkDC, gL, P);
    SelectClipRgn(gBkDC, nullptr);
    GdiFlush();
}
void fillBars(HDC d) {
    const Layout& L = gL;
    HBRUSH k = (HBRUSH)GetStockObject(BLACK_BRUSH);
    RECT r[4] = {{0, 0, L.clientW, L.oy}, {0, L.oy + L.ch, L.clientW, L.clientH}, {0, L.oy, L.ox, L.oy + L.ch}, {L.ox + L.cw, L.oy, L.clientW, L.oy + L.ch}};
    for (auto& x : r) if (x.right > x.left && x.bottom > x.top) FillRect(d, &x, k);
}

// 잠금 안에서: 논리 사각형 r 을 창 DC d 에 찍는다. 그림자는 이미 갱신되어 있다.
void presentLogical(HDC d, RECT r) {
    r.left = std::max<LONG>(r.left, 0); r.top = std::max<LONG>(r.top, 0);
    r.right = std::min<LONG>(r.right, kW); r.bottom = std::min<LONG>(r.bottom, kH);
    if (r.right <= r.left || r.bottom <= r.top) return;
    if (!ensureLayout()) return;
    double t0 = nowMs();
    bool full = r.left == 0 && r.top == 0 && r.right == kW && r.bottom == kH;
    CmPresentationFrame commentary;
    std::vector<RECT> ov; overlayRects(ov);
    bool hit = false; for (auto& o : ov) if (rectsHit(o, r)) { hit = true; break; }
    GdiFlush();
    if (identity(gL)) {
        RECT P{r.left + gL.ox, r.top + gL.oy, r.right + gL.ox, r.bottom + gL.oy};
        if (!hit || !gBk) BitBlt(d, P.left, P.top, P.right - P.left, P.bottom - P.top, gShDC, r.left, r.top, SRCCOPY);
        else {
            BitBlt(gBkDC, P.left, P.top, P.right - P.left, P.bottom - P.top, gShDC, r.left, r.top, SRCCOPY);
            paintOverlays(P);
            BitBlt(d, P.left, P.top, P.right - P.left, P.bottom - P.top, gBkDC, P.left, P.top, SRCCOPY);
        }
    } else {
        int xa, xb, ya, yb;
        span(gAX, r.left, r.right, xa, xb); span(gAY, r.top, r.bottom, ya, yb);
        if (xb > xa && yb > ya && gBk) {
            scaleRect(xa, xb, ya, yb);
            RECT P{gL.ox + xa, gL.oy + ya, gL.ox + xb, gL.oy + yb};
            if (hit) paintOverlays(P);
            BitBlt(d, P.left, P.top, P.right - P.left, P.bottom - P.top, gBkDC, P.left, P.top, SRCCOPY);
        }
    }
    if (full) fillBars(d);
    double dt = nowMs() - t0;
    Stat& s = full ? gTFull : gTPart;
    ++s.n; s.sum += dt; s.max = std::max(s.max, dt);
}

// 창 스레드: 받아 둔 사각형을 다시 찍는다.
void repaintPending(const std::vector<RECT>& rects) {
    if (!gWnd || ChartIsOpen() || IsIconic(gWnd)) return;
    HDC d = GetDC(gWnd);
    if (!d) return;
    EnterCriticalSection(&gCs);
    for (auto& r : rects) presentLogical(d, r);
    LeaveCriticalSection(&gCs);
    ReleaseDC(gWnd, d);
}
void overlayTick() {
    std::vector<RECT> now; overlayRects(now);
    std::wstring t; float a = 1;
    bool fading = ToastNow(t, a) && a < 1.f;
    std::vector<RECT> redo;
    bool same = now.size() == gLastOverlay.size() && std::equal(now.begin(), now.end(), gLastOverlay.begin(), [](const RECT& x, const RECT& y) { return EqualRect(&x, &y) != 0; });
    if (!same) { redo = gLastOverlay; redo.insert(redo.end(), now.begin(), now.end()); }
    else if (fading) redo.push_back(kToastRect);
    gLastOverlay = now;
    if (!redo.empty()) repaintPending(redo);
    if (now.empty() && gOverlayTimer) { KillTimer(gWnd, kOverlayTimer); gOverlayTimer = false; }
}

// ---------------------------------------------------------------- 창 자리
RECT unshift(RECT r) { OffsetRect(&r, -gShift, 0); return r; }
RECT doShift(RECT r) { OffsetRect(&r, gShift, 0); return r; }
bool workAreaOf(const RECT& screenRc, RECT& work, RECT& mon, DWORD flag) {
    HMONITOR m = MonitorFromRect(&screenRc, flag);
    if (!m) return false;
    MONITORINFO mi{sizeof(mi)};
    if (!GetMonitorInfoW(m, &mi)) return false;
    work = mi.rcWork; mon = mi.rcMonitor;
    return true;
}
RECT frameFor(DWORD style, DWORD ex) { RECT f{0, 0, 0, 0}; AdjustWindowRectEx(&f, style, FALSE, ex); return f; }
// 클라이언트 cw×ch 인 바깥 사각형을 (cx,cy) 가운데에, 작업 영역 안에 둔다.
RECT outerRect(int cx, int cy, int cw, int ch, DWORD style, DWORD ex, const RECT& work) {
    RECT f = frameFor(style, ex);
    int fw = f.right - f.left, fh = f.bottom - f.top;
    int ww = cw + fw, wh = ch + fh;
    RECT r{cx - ww / 2, cy - wh / 2, 0, 0}; r.right = r.left + ww; r.bottom = r.top + wh;
    if (r.right > work.right) OffsetRect(&r, work.right - r.right, 0);
    if (r.bottom > work.bottom) OffsetRect(&r, 0, work.bottom - r.bottom);
    if (r.left < work.left) OffsetRect(&r, work.left - r.left, 0);
    if (r.top < work.top) OffsetRect(&r, 0, work.top - r.top);
    return r;
}
// 작업 영역에 들어가는 가장 큰 4:3 클라이언트(상한 maxCh)
void fitClient(const RECT& work, DWORD style, DWORD ex, int wantCh, int& cw, int& ch) {
    RECT f = frameFor(style, ex);
    int availW = (work.right - work.left) - (f.right - f.left), availH = (work.bottom - work.top) - (f.bottom - f.top);
    ch = std::min(wantCh, availH);
    ch = std::min(ch, availW * kH / kW);
    ch = std::max(ch, 150);
    cw = (ch * kW + kH / 2) / kH;
}

std::wstring memPath() { return Root() + L"\\forest-qol-window.ini"; }
void readMemory() {
    gMem = Memory();
    if (!gMemory) return;
    std::wstring p = memPath();
    if (GetFileAttributesW(p.c_str()) == INVALID_FILE_ATTRIBUTES) { plog("window memory: none"); return; }
    auto get = [&](const wchar_t* k, int def) { return (int)GetPrivateProfileIntW(L"window", k, def, p.c_str()); };
    RECT r{get(L"left", 0), get(L"top", 0), get(L"right", 0), get(L"bottom", 0)};
    gMem.maximized = get(L"maximized", 0) != 0;
    if (get(L"version", 0) != 1 || r.right - r.left < 200 || r.bottom - r.top < 150) { plog("window memory: unusable " + rs(r)); return; }
    // 끊긴 모니터 위 자리는 쓰지 않는다: 제목 줄 띠가 어느 모니터 작업 영역에 넉넉히 걸려야 한다.
    RECT work{}, mon{};
    RECT bar{r.left, r.top, r.right, r.top + 32};
    if (!workAreaOf(bar, work, mon, MONITOR_DEFAULTTONULL)) { plog("window memory: monitor gone " + rs(r)); return; }
    RECT inter{};
    if (!IntersectRect(&inter, &bar, &work) || inter.right - inter.left < 120 || inter.bottom - inter.top < 16) { plog("window memory: title bar off screen " + rs(r)); return; }
    gMem.valid = true; gMem.rc = r;
    plog("window memory: read " + rs(r) + (gMem.maximized ? " maximized" : ""));
}
void writeMemory(const char* why) {
    if (!gMemory || !gHaveNormal) return;
    std::wstring p = memPath(), tmp = p + L".tmp";
    char b[256];
    int n = sprintf_s(b, "[window]\r\nversion=1\r\nleft=%ld\r\ntop=%ld\r\nright=%ld\r\nbottom=%ld\r\nmaximized=%d\r\n",
                      gNormal.left, gNormal.top, gNormal.right, gNormal.bottom, gMax ? 1 : 0);
    HANDLE f = CreateFileW(tmp.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (f == INVALID_HANDLE_VALUE) return;
    DWORD w = 0; BOOL ok = WriteFile(f, b, (DWORD)n, &w, nullptr) && w == (DWORD)n;
    FlushFileBuffers(f); CloseHandle(f);
    if (ok && MoveFileExW(tmp.c_str(), p.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) plog(std::string("window memory: wrote ") + rs(gNormal) + (gMax ? " maximized" : "") + " (" + why + ")");
    else DeleteFileW(tmp.c_str());
}
// 창 자리를 지켜본다(최대화·최소화·전체 화면이 아닐 때의 바깥 사각형).
void trackPlacement() {
    if (!gWnd || gTransition || engineFull() || IsIconic(gWnd) || !IsWindowVisible(gWnd)) return;
    if (IsZoomed(gWnd)) { gMax = true; return; }
    RECT r; if (!GetWindowRect(gWnd, &r)) return;
    gNormal = unshift(r); gHaveNormal = true; gMax = false;
}

// 게임 창을 처음 만들 때의 자리(바깥 사각형, 시험 이동 포함)
void initialRect(int& x, int& y, int& w, int& h, DWORD style, DWORD ex) {
    RECT eng{x, y, x + w, y + h};
    RECT r;
    if (gMem.valid) {
        r = gMem.rc;
        gPendingMax = gMem.maximized;
        // 해상도가 줄었으면 작업 영역 안으로 줄인다
        RECT work{}, mon{};
        if (workAreaOf(r, work, mon, MONITOR_DEFAULTTONEAREST) && (r.right - r.left > work.right - work.left || r.bottom - r.top > work.bottom - work.top)) {
            int cw, ch; fitClient(work, style, ex, 100000, cw, ch);
            r = outerRect((r.left + r.right) / 2, (r.top + r.bottom) / 2, cw, ch, style, ex, work);
            plog("window memory: shrunk to fit " + rs(r));
        }
    } else {
        // 기억이 없을 때: 엔진이 고른 모니터(주 모니터) 작업 영역 높이의 약 2/3, 1배보다 작게는 안 한다.
        RECT work{}, mon{};
        if (!workAreaOf(eng, work, mon, MONITOR_DEFAULTTOPRIMARY)) { work = eng; }
        int want = std::max(kH, (int)((work.bottom - work.top) * 2 / 3));
        int cw, ch; fitClient(work, style, ex, want, cw, ch);
        if (ch < kH) { r = eng; }   // 작은 모니터: 엔진 기본(800×600 가운데)
        else r = outerRect((work.left + work.right) / 2, (work.top + work.bottom) / 2, cw, ch, style, ex, work);
        plog("window default: work " + rs(work) + " -> " + rs(r));
    }
    r = doShift(r);
    x = r.left; y = r.top; w = r.right - r.left; h = r.bottom - r.top;
}

// 화면(시험 이동 뺀 좌표)에서 창이 걸친 모니터 전체 사각형(시험 이동 포함)
RECT monitorRectFor(HWND h) {
    RECT wr{}; GetWindowRect(h, &wr);
    RECT work{}, mon{};
    if (!workAreaOf(unshift(wr), work, mon, MONITOR_DEFAULTTONEAREST)) mon = RECT{0, 0, GetSystemMetrics(SM_CXSCREEN), GetSystemMetrics(SM_CYSCREEN)};
    return doShift(mon);
}

void placeMovie();

// ---------------------------------------------------------------- 전체 화면(0x43cce0 대신)
// 창으로 돌아올 자리: 지켜본 바깥 사각형(gNormal)에 SetWindowPos, 최대화였으면 그 뒤 최대화.
// SetWindowPlacement 는 쓰지 않는다 — 화면 밖 자리를 보이는 곳으로 끌어온다(11-21 시험에서 확인).
void restoreWindowed(HWND h) {
    RECT n = gNormal;
    if (!gHaveNormal) { RECT wr{}; GetWindowRect(h, &wr); n = unshift(wr); }
    n = doShift(n);
    SetWindowPos(h, HWND_NOTOPMOST, n.left, n.top, n.right - n.left, n.bottom - n.top, SWP_NOOWNERZORDER | SWP_FRAMECHANGED | SWP_NOACTIVATE);
    if (gSavedMax && IsWindowVisible(h)) {
        if (gShift) plog("maximize after fullscreen skipped while shifted for test");
        else ShowWindow(h, SW_MAXIMIZE);
    }
}
void enterFull(uint8_t* eng, HWND h) {
    gTransition = true;
    gSavedMax = IsZoomed(h) || gPendingMax;
    gPendingMax = false;
    gMax = gSavedMax;                     // 전체 화면인 채 끄면 돌아갈 창 상태를 기억한다
    RECT m = monitorRectFor(h);
    *(int*)(eng + kOffFull) = 1;
    LONG st = GetWindowLongA(h, GWL_STYLE);
    st = (st & ~(LONG)(WS_CAPTION | WS_THICKFRAME | WS_SYSMENU | WS_MINIMIZEBOX | WS_MAXIMIZEBOX)) | (LONG)WS_POPUP;
    SetWindowLongA(h, GWL_STYLE, st);
    SetWindowLongA(h, GWL_EXSTYLE, *(LONG*)(eng + kOffExStyle));
    SetWindowPos(h, HWND_TOP, m.left, m.top, m.right - m.left, m.bottom - m.top, SWP_NOOWNERZORDER | SWP_FRAMECHANGED | SWP_NOACTIVATE);
    gTransition = false;
    placeMovie();                         // 시작 때 전체 화면이면 영상 창이 먼저 만들어져 있다
    RECT wr{}; GetWindowRect(h, &wr);
    plog("fullscreen on: monitor " + rs(m) + " window " + rs(wr) + (gSavedMax ? " (was maximized)" : ""));
}
void leaveFull(uint8_t* eng, HWND h) {
    gTransition = true;
    *(int*)(eng + kOffFull) = 0;
    LONG st = *(LONG*)(eng + kOffStyle) | (IsWindowVisible(h) ? (LONG)WS_VISIBLE : 0);
    SetWindowLongA(h, GWL_STYLE, st);
    SetWindowLongA(h, GWL_EXSTYLE, *(LONG*)(eng + kOffExStyle));
    restoreWindowed(h);
    gTransition = false;
    placeMovie();
    trackPlacement();
    RECT wr{}; GetWindowRect(h, &wr);
    plog("fullscreen off: window " + rs(wr) + (IsZoomed(h) ? " maximized" : ""));
}
void __fastcall fsHook(uint8_t* eng, void*, int flag) {
    void* ret = _ReturnAddress();
    if (!eng) return;
    HWND h = *(HWND*)(eng + 4);
    flag = flag ? 1 : 0;
    if (*(int*)(eng + kOffFull) == flag) return;
    if (ret == (void*)kFsRetQuit) { *(int*)(eng + kOffFull) = 0; plog("fullscreen off at quit (nothing to restore)"); return; }
    if (!IsWindow(h)) return;
    if (ret != (void*)kFsRetInit) {
        *(int*)kFsAltFlag = flag;             // Alt+F/W 와 같은 값
        *(uint16_t*)kFsSetting = (uint16_t)flag;  // 설정 화면 「전체 화면/창」도 같게(다음 시작도 그대로)
    }
    if (flag) enterFull(eng, h); else leaveFull(eng, h);
    InvalidateRect(h, nullptr, FALSE);
}
// borderless_fullscreen=0: 원래 길(해상도 바꿈)을 쓰되 창을 800×600 으로 맞추고, 돌아오면 기억한 자리로.
void __fastcall fsOrigHook(uint8_t* eng, void*, int flag) {
    void* ret = _ReturnAddress();
    if (!eng) return;
    HWND h = *(HWND*)(eng + 4);
    bool was = *(int*)(eng + kOffFull) != 0;
    if (flag && !was) { gSavedMax = IsZoomed(h) || gPendingMax; gPendingMax = false; }
    gTransition = true;
    ((FsFn)gFsTramp)(eng, flag);
    bool is = *(int*)(eng + kOffFull) != 0;
    if (is && !was) SetWindowPos(h, nullptr, 0, 0, kW, kH, SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE);
    if (!is && was && ret != (void*)kFsRetQuit) restoreWindowed(h);
    gTransition = false;
    placeMovie();
    if (!is) trackPlacement();
}
void callEngineFull(int flag) {
    uint8_t* eng = engine();
    if (!eng) return;
    *(int*)kFsAltFlag = flag;
    ((FsFn)kFsFunc)(eng, flag);   // 엔진 입구(우리 갈고리로 들어온다)
}

// ---------------------------------------------------------------- 영상 자식 창
void placeMovie() {
    if (!gWnd) return;
    HWND c = FindWindowExA(gWnd, nullptr, "MpegWindowClass", nullptr);
    if (!c) return;
    Layout L = clientLayout(gWnd);
    SetWindowPos(c, nullptr, L.ox, L.oy, L.cw, L.ch, SWP_NOZORDER | SWP_NOACTIVATE);
    if (gMovieDev && gMovieWnd == c && origMci) {
        MCI_DGV_PUT_PARMS p{}; p.rc = RECT{0, 0, L.cw, L.ch};
        MCIERROR e = origMci(gMovieDev, MCI_PUT, MCI_DGV_PUT_DESTINATION | MCI_DGV_RECT, (DWORD_PTR)&p);
        plog("movie placed " + std::to_string(L.ox) + "," + std::to_string(L.oy) + " " + std::to_string(L.cw) + "x" + std::to_string(L.ch) + " put=" + std::to_string(e));
    }
}

// ---------------------------------------------------------------- 가로챈 가져오기
HWND WINAPI createWindowExA(DWORD ex, LPCSTR cls, LPCSTR name, DWORD style, int x, int y, int w, int h, HWND parent, HMENU menu, HINSTANCE inst, LPVOID param) {
    void* ret = _ReturnAddress();
    bool named = cls && !IS_INTRESOURCE(cls);
    bool mainWnd = ret == (void*)kRetMainCreate && !parent && !(style & WS_CHILD);
    bool movie = parent && (style & WS_CHILD) && named && strcmp(cls, "MpegWindowClass") == 0;
    if (mainWnd) initialRect(x, y, w, h, style, ex);
    if (movie) { Layout L = clientLayout(parent); x = L.ox; y = L.oy; w = L.cw; h = L.ch; }
    HWND hw = origCreateWindowExA(ex, cls, name, style, x, y, w, h, parent, menu, inst, param);
    DWORD err = hw ? 0 : GetLastError();
    if (mainWnd && hw) { gWnd = hw; RECT r; GetWindowRect(hw, &r); gNormal = unshift(r); gHaveNormal = true; }
    if (mainWnd || movie || !hw || (named && (strcmp(cls, "RgnDialog") == 0))) {
        char b[220]; sprintf_s(b, "create %s style=%08lx ex=%08lx at %d,%d %dx%d parent=%p -> %p err=%lu", named ? cls : "#atom", style, ex, x, y, w, h, (void*)parent, (void*)hw, err);
        plog(b);
    }
    return hw;
}
LRESULT CALLBACK earlyProc(HWND h, UINT m, WPARAM w, LPARAM l) {
    // 다리가 위에 서브클래스하면(맨 위 프로시저가 내가 아니면) 다리가 Present_WndProc 를 부르므로 그냥 넘긴다.
    if (!gBridgeReady && m != WM_ERASEBKGND && m != WM_PAINT && GetWindowLongPtrA(h, GWLP_WNDPROC) == (LONG_PTR)earlyProc) {
        LRESULT r = 0;
        if (Present_WndProc(h, m, w, l, r)) return r;
    }
    return CallWindowProcA(gEngineProc, h, m, w, l);
}
BOOL WINAPI showWindow(HWND h, int cmd) {
    if (h && h == gWnd && !gEngineProc) {    // 엔진이 창 프로시저(0x441bc0)를 건 뒤 처음 보일 때
        gEngineProc = (WNDPROC)SetWindowLongPtrA(h, GWLP_WNDPROC, (LONG_PTR)earlyProc);
        plog("early subclass before the script starts");
    }
    if (h && h == gWnd && gPendingMax && (cmd == SW_SHOW || cmd == SW_SHOWNORMAL) && !engineFull()) {
        gPendingMax = false;
        if (gShift) { plog("window memory: maximized (not applied while shifted for test)"); }
        else { plog("window memory: show maximized"); cmd = SW_SHOWMAXIMIZED; }
    }
    return origShowWindow(h, cmd);
}
// 확인 창을 게임 그림 가운데에(창이 화면 밖이면 함께 밖으로).
thread_local HHOOK tlHook = nullptr;
thread_local bool tlCentered = false;
void centerOnGame(HWND d) {
    if (!gWnd || !IsWindowVisible(gWnd) || IsIconic(gWnd)) return;
    RECT dr; if (!GetWindowRect(d, &dr)) return;
    Layout L = clientLayout(gWnd);
    POINT c{L.ox + L.cw / 2, L.oy + L.ch / 2}; ClientToScreen(gWnd, &c);
    int w = dr.right - dr.left, hh = dr.bottom - dr.top;
    RECT r{c.x - w / 2, c.y - hh / 2, c.x - w / 2 + w, c.y - hh / 2 + hh};
    RECT u = unshift(r), work{}, mon{};
    if (workAreaOf(u, work, mon, MONITOR_DEFAULTTONEAREST)) {
        if (u.right > work.right) OffsetRect(&u, work.right - u.right, 0);
        if (u.bottom > work.bottom) OffsetRect(&u, 0, work.bottom - u.bottom);
        if (u.left < work.left) OffsetRect(&u, work.left - u.left, 0);
        if (u.top < work.top) OffsetRect(&u, 0, work.top - u.top);
    }
    r = doShift(u);
    SetWindowPos(d, nullptr, r.left, r.top, 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE);
    plog("dialog centered " + rs(r));
}
LRESULT CALLBACK cbtProc(int code, WPARAM w, LPARAM l) {
    if (code == HCBT_ACTIVATE && !tlCentered) {
        char cls[32] = {};
        GetClassNameA((HWND)w, cls, 32);
        if (strcmp(cls, "#32770") == 0) { tlCentered = true; centerOnGame((HWND)w); }
    }
    return CallNextHookEx(tlHook, code, w, l);
}
int WINAPI messageBoxA(HWND o, LPCSTR text, LPCSTR cap, UINT f) {
    HHOOK prevHook = tlHook; bool prevC = tlCentered;
    tlCentered = false;
    tlHook = SetWindowsHookExW(WH_CBT, cbtProc, nullptr, GetCurrentThreadId());
    int r = origMessageBoxA(o, text, cap, f);
    if (tlHook) UnhookWindowsHookEx(tlHook);
    tlHook = prevHook; tlCentered = prevC;
    return r;
}
MCIERROR WINAPI mciSendCommandAHook(MCIDEVICEID id, UINT msg, DWORD_PTR flags, DWORD_PTR parm) {
    MCIERROR e = origMci(id, msg, flags, parm);
    if (msg == MCI_WINDOW && (flags & MCI_DGV_WINDOW_HWND) && parm && !e) { gMovieDev = id; gMovieWnd = ((MCI_DGV_WINDOW_PARMSA*)parm)->hWnd; }
    if (msg == MCI_PUT && parm && id == gMovieDev) {
        const RECT& rc = ((MCI_DGV_PUT_PARMS*)parm)->rc;
        plog("movie put flags=" + std::to_string((unsigned)flags) + " rect " + std::to_string(rc.left) + "," + std::to_string(rc.top) + "," + std::to_string(rc.right) + "," + std::to_string(rc.bottom) + " err=" + std::to_string(e));
    }
    if (msg == MCI_CLOSE && id == gMovieDev) { gMovieDev = 0; gMovieWnd = nullptr; }
    return e;
}

bool hookIat(uintptr_t at, void* repl, void** orig) {
    void* cur = *(void**)at;
    if (!cur) return false;
    *orig = cur;
    return PatchBytes(at, &cur, &repl, sizeof(repl));
}
void* makeFsTramp() {
    static const uint8_t head[6] = {0x81, 0xEC, 0xBC, 0x00, 0x00, 0x00};   // sub esp,0BCh
    uint8_t* t = (uint8_t*)VirtualAlloc(nullptr, 16, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!t) return nullptr;
    memcpy(t, head, 6);
    t[6] = 0xE9; *(int32_t*)(t + 7) = (int32_t)((kFsFunc + 6) - ((uintptr_t)t + 11));
    DWORD old; VirtualProtect(t, 16, PAGE_EXECUTE_READ, &old);
    return t;
}
bool patchFs(void* target) {
    static const uint8_t head[6] = {0x81, 0xEC, 0xBC, 0x00, 0x00, 0x00};
    uint8_t jmp[6]; jmp[0] = 0xE9; *(int32_t*)(jmp + 1) = (int32_t)((uintptr_t)target - (kFsFunc + 5)); jmp[5] = 0x90;
    return PatchBytes(kFsFunc, head, jmp, 6);
}

// ---------------------------------------------------------------- 창 메뉴·크기
void addMenu(HWND h) {
    HMENU m = GetSystemMenu(h, FALSE);
    if (!m) return;
    AppendMenuW(m, MF_SEPARATOR, 0, nullptr);
    AppendMenuW(m, MF_STRING, kMenuScale1, L"창 크기: 원래 크기 (800×600)");
    AppendMenuW(m, MF_STRING, kMenuScale2, L"창 크기: 2배 (1600×1200)");
    AppendMenuW(m, MF_STRING, kMenuScale3, L"창 크기: 3배 (2400×1800)");
    AppendMenuW(m, MF_STRING, kMenuFull, L"전체 화면\tAlt+Enter");
}
void setScale(HWND h, int k) {
    if (engineFull()) callEngineFull(0);
    if (IsZoomed(h)) ShowWindow(h, SW_RESTORE);
    DWORD st = (DWORD)GetWindowLongA(h, GWL_STYLE), ex = (DWORD)GetWindowLongA(h, GWL_EXSTYLE);
    RECT wr; GetWindowRect(h, &wr);
    RECT u = unshift(wr), work{}, mon{};
    if (!workAreaOf(u, work, mon, MONITOR_DEFAULTTONEAREST)) return;
    int cw, ch; fitClient(work, st, ex, kH * k, cw, ch);
    RECT r = doShift(outerRect((u.left + u.right) / 2, (u.top + u.bottom) / 2, cw, ch, st, ex, work));
    SetWindowPos(h, nullptr, r.left, r.top, r.right - r.left, r.bottom - r.top, SWP_NOZORDER | SWP_NOACTIVATE);
    placeMovie();
    plog("scale x" + std::to_string(k) + " -> client " + std::to_string(cw) + "x" + std::to_string(ch) + " window " + rs(r));
    trackPlacement(); writeMemory("scale");
}
void keepAspect(HWND h, WPARAM edge, RECT* r) {
    DWORD st = (DWORD)GetWindowLongA(h, GWL_STYLE), ex = (DWORD)GetWindowLongA(h, GWL_EXSTYLE);
    RECT f = frameFor(st, ex);
    int fw = f.right - f.left, fh = f.bottom - f.top;
    int cw = std::max(400, (int)(r->right - r->left) - fw), ch = std::max(300, (int)(r->bottom - r->top) - fh);
    if (edge == WMSZ_TOP || edge == WMSZ_BOTTOM) cw = (ch * kW + kH / 2) / kH;
    else ch = (cw * kH + kW / 2) / kW;
    if (edge == WMSZ_LEFT || edge == WMSZ_TOPLEFT || edge == WMSZ_BOTTOMLEFT) r->left = r->right - (cw + fw); else r->right = r->left + cw + fw;
    if (edge == WMSZ_TOP || edge == WMSZ_TOPLEFT || edge == WMSZ_TOPRIGHT) r->top = r->bottom - (ch + fh); else r->bottom = r->top + ch + fh;
}

}  // namespace

// ================================================================ 약속(qol.h)
bool Present_Active() { return gOn && gShDC; }

Layout CurrentLayout() {
    if (!gOn || !gWnd) return Layout();
    return clientLayout(gWnd);
}

bool Present_Install() {
    gOn = Cfg("present", 1) != 0;
    if (!gOn) return false;
    gSmooth = Cfg("present_smooth", 1) != 0;
    gMemory = Cfg("window_memory", 1) != 0;
    gBorderless = Cfg("borderless_fullscreen", 1) != 0;
    gKeepAspect = Cfg("window_keep_aspect", 1) != 0;
    gShift = Cfg("present_test_shift_x", 0);
    QueryPerformanceFrequency(&gQpf);
    InitializeCriticalSection(&gCs); InitializeCriticalSection(&gPendCs); InitializeCriticalSection(&gLogCs);
    gMsgRepaint = RegisterWindowMessageW(L"ForestQolPresentRepaint");
    gMsgSetup = RegisterWindowMessageW(L"ForestQolPresentSetup");
    if (!makeDib(kW, kH, gShDC, gShBmp, gSh)) { gOn = false; return false; }
    static const uint8_t oldStyle[5] = {0x68, 0x00, 0x00, 0xC8, 0x82}, newStyle[5] = {0x68, 0x00, 0x00, 0xCF, 0x82};   // + WS_THICKFRAME|WS_MINIMIZEBOX|WS_MAXIMIZEBOX
    bool styleOk = PatchBytes(kStylePush, oldStyle, newStyle, 5);
    bool cwOk = hookIat(kIatCreateWindowEx, (void*)createWindowExA, (void**)&origCreateWindowExA);
    bool swOk = hookIat(kIatShowWindow, (void*)showWindow, (void**)&origShowWindow);
    bool mbOk = hookIat(kIatMessageBox, (void*)messageBoxA, (void**)&origMessageBoxA);
    bool mciOk = hookIat(kIatMci, (void*)mciSendCommandAHook, (void**)&origMci);
    bool fsOk;
    if (gBorderless) fsOk = patchFs((void*)fsHook);
    else { gFsTramp = makeFsTramp(); fsOk = gFsTramp && patchFs((void*)fsOrigHook); }
    readMemory();
    char b[256];
    sprintf_s(b, "install smooth=%d memory=%d borderless=%d keep_aspect=%d shift=%d; style=%d createwindow=%d showwindow=%d messagebox=%d mci=%d fullscreen=%d",
              gSmooth, gMemory, gBorderless, gKeepAspect, gShift, styleOk, cwOk, swOk, mbOk, mciOk, fsOk);
    plog(b);
    return true;
}

void Present_WindowReady(HWND h) {
    if (!gOn) return;
    EnterCriticalSection(&gLogCs);
    gLogReady = true;
    std::vector<std::string> early; early.swap(gEarly);
    LeaveCriticalSection(&gLogCs);
    for (auto& s : early) Log("present: " + s);
    if (gWnd != h) { plog("window ready (not from create hook)"); gWnd = h; }
    gBridgeReady = true;
    PostMessageW(h, gMsgSetup, 0, 0);
}

bool Present_WndProc(HWND h, UINT m, WPARAM w, LPARAM l, LRESULT& r) {
    if (!gOn) return false;
    if (m == gMsgRepaint) {
        if (w == 1) Present_InvalidateLogical(RECT{0, 0, kW, kH});   // 그림 전체를 그림자에서 다시(시험·도구용)
        InterlockedExchange(&gRepaintPosted, 0);
        std::vector<RECT> rects;
        EnterCriticalSection(&gPendCs); rects.swap(gPending); LeaveCriticalSection(&gPendCs);
        repaintPending(rects);
        if (!gOverlayTimer) { gOverlayTimer = SetTimer(h, kOverlayTimer, 33, nullptr) != 0; }
        r = 0; return true;
    }
    if (m == gMsgSetup) {
        addMenu(h);
        trackPlacement();
        RECT wr{}; GetWindowRect(h, &wr);
        Layout L = clientLayout(h);
        char b[200]; sprintf_s(b, "setup window %s client %dx%d picture %d,%d %dx%d%s", rs(wr).c_str(), L.clientW, L.clientH, L.ox, L.oy, L.cw, L.ch, IsZoomed(h) ? " maximized" : "");
        plog(b);
        InvalidateRect(h, nullptr, FALSE);
        r = 0; return true;
    }
    switch (m) {
    case WM_TIMER:
        if (w == kOverlayTimer) { overlayTick(); r = 0; return true; }
        return false;
    case WM_ERASEBKGND:
        r = 1; return true;
    case WM_SIZE:
        if (w != SIZE_MINIMIZED) { placeMovie(); InvalidateRect(h, nullptr, FALSE); }
        trackPlacement();
        return false;
    case WM_WINDOWPOSCHANGED:
        trackPlacement();
        return false;
    case WM_EXITSIZEMOVE:
        trackPlacement(); writeMemory("move/size");
        return false;
    case WM_GETMINMAXINFO: {
        if (engineFull()) return false;
        RECT f = frameFor((DWORD)GetWindowLongA(h, GWL_STYLE), (DWORD)GetWindowLongA(h, GWL_EXSTYLE));
        auto* mm = (MINMAXINFO*)l;
        mm->ptMinTrackSize.x = 400 + (f.right - f.left); mm->ptMinTrackSize.y = 300 + (f.bottom - f.top);
        r = 0; return true;
    }
    case WM_SIZING:
        if (gKeepAspect && !engineFull()) { keepAspect(h, w, (RECT*)l); r = TRUE; return true; }
        return false;
    case WM_SYSKEYDOWN:
        if (w == VK_RETURN) { if (!(l & 0x40000000)) callEngineFull(engineFull() ? 0 : 1); r = 0; return true; }
        return false;
    case WM_SYSCHAR:
        if (w == VK_RETURN) { r = 0; return true; }   // 삑 소리 막기
        return false;
    case WM_SYSCOMMAND: {
        UINT c = (UINT)(w & 0xFFF0);
        if (c == kMenuScale1 || c == kMenuScale2 || c == kMenuScale3) { setScale(h, c == kMenuScale1 ? 1 : c == kMenuScale2 ? 2 : 3); r = 0; return true; }
        if (c == kMenuFull) { callEngineFull(engineFull() ? 0 : 1); r = 0; return true; }
        if (c == SC_MAXIMIZE && gShift) { plog("maximize ignored while shifted for test"); r = 0; return true; }
        return false;
    }
    case WM_INITMENUPOPUP:
        if (HIWORD(l)) {
            HMENU sm = GetSystemMenu(h, FALSE);
            CheckMenuItem(sm, kMenuFull, MF_BYCOMMAND | (engineFull() ? MF_CHECKED : MF_UNCHECKED));
        }
        return false;
    case WM_CLOSE:
        trackPlacement(); writeMemory("close");
        return false;
    case WM_ENDSESSION:
        if (w) { trackPlacement(); writeMemory("end session"); }
        return false;
    case WM_DESTROY:
        trackPlacement(); writeMemory("destroy");
        EnterCriticalSection(&gCs); logStats("exit"); LeaveCriticalSection(&gCs);
        if (gOverlayTimer) { KillTimer(h, kOverlayTimer); gOverlayTimer = false; }
        return false;
    }
    return false;
}

void Present_MapMouse(UINT, LPARAM& l) {
    if (!gOn || !gWnd) return;
    Layout L = clientLayout(gWnd);
    if (L.cw <= 0 || (identity(L) && L.ox == 0 && L.oy == 0)) return;
    int X = GET_X_LPARAM(l), Y = GET_Y_LPARAM(l);
    int x = (int)std::floor((X - L.ox + 0.5) * kW / (double)L.cw);
    int y = (int)std::floor((Y - L.oy + 0.5) * kH / (double)L.ch);
    l = MAKELPARAM((WORD)(short)x, (WORD)(short)y);
}

bool Present_BitBlt(HDC d, int x, int y, int w, int h, HDC s, int sx, int sy, DWORD rop, BOOL& ret) {
    if (!gOn || !gShDC) return false;
    EnterCriticalSection(&gCs);
    BOOL ok = BitBlt(gShDC, x, y, w, h, s, sx, sy, rop);   // 원래 창에 그려질 그림을 그림자에
    if (!ChartIsOpen() && !IsIconic(gWnd)) presentLogical(d, RECT{x, y, x + w, y + h});
    LeaveCriticalSection(&gCs);
    ret = ok;
    return true;
}

bool Present_StretchBlt(HDC d, int x, int y, int w, int h, HDC s, int sx, int sy, int sw, int sh, DWORD rop, BOOL& ret) {
    if (!gOn || !gShDC) return false;
    EnterCriticalSection(&gCs);
    BOOL ok = StretchBlt(gShDC, x, y, w, h, s, sx, sy, sw, sh, rop);
    RECT r{std::min(x, x + w), std::min(y, y + h), std::max(x, x + w), std::max(y, y + h)};
    if (!ChartIsOpen() && !IsIconic(gWnd)) presentLogical(d, r);
    LeaveCriticalSection(&gCs);
    ret = ok;
    return true;
}

void Present_InvalidateLogical(const RECT& r) {
    if (!gOn || !gWnd) return;
    EnterCriticalSection(&gPendCs); gPending.push_back(r); LeaveCriticalSection(&gPendCs);
    if (InterlockedExchange(&gRepaintPosted, 1) == 0) PostMessageW(gWnd, gMsgRepaint, 0, 0);
}

POINT Present_ToClient(int x, int y) {
    if (!gOn || !gWnd) return POINT{x, y};
    Layout L = clientLayout(gWnd);
    if (L.cw <= 0) return POINT{x, y};
    return POINT{L.ox + (int)std::floor((x + 0.5) * L.cw / (double)kW), L.oy + (int)std::floor((y + 0.5) * L.ch / (double)kH)};
}

// 4K 그림 모듈이 4K 글자가 넘기는 글자 없는 사본과 맞춰 볼 때 읽는다(PaintAbove 안, 화면 잠금 안에서만).
const uint32_t* Present_ShadowBits() { return gOn ? gSh : nullptr; }

}}  // namespace forest::qol
