// qol_hitext.cpp — 4K 글자 모듈(세션 「4K 글자」 몫, 2026-11-21).
//
// 늘린 창에서 대사·노란 자막·대화 기록(앞 쪽)·세이브 화면 날짜 글자를 실제 글꼴(엔진이 고른 굴림·바탕)로 화면 해상도에 다시 그린다.
// 엔진 근거는 P:\AI\forest-qol\s-hitext\조사.md. 요점:
//  - 글자는 한 글자씩 「글리프 스프라이트」(주 vtable 0x45ca90)다. 0x444ce0 → 0x4452b0(ch, 높이, 글꼴, 세로, 모드, 굵게, 기울임, 색)이
//    CreateFontA + GetGlyphOutlineA(GGO_GRAY8)로 BlackBox 크기 32비트 표면을 채운다(색은 단색, 알파 바이트 = 255 − v·255/64 = 투명도).
//  - 장면 합성(장면 vtable 0x45b97c +0x30 부분·+0x34 전체)이 자식 스프라이트의 그리기 0x42ee40(dest, clip, offset)을 z 순으로 불러
//    앞 화면 판(엔진 +0x9c, 800×600 위→아래 BGRA)에 직접 섞는다. 글리프 자리 = offset + 스프라이트 사각형(+0x3c).
//  - 노란 자막(OVERLAY 객체 45~49, 검정 4겹 + 노랑)은 「구운 글」이다: 0x4082d0 이 임시 텍스트 객체를 만들어 0x438690 으로 글리프를
//    자막 스프라이트 자신의 판에 한 번 찍고(글자마다 0x42def0) 임시 객체를 지운다. 그 뒤에는 그림 스프라이트로 합성된다.
//
// 방식(엔진 판은 한 화소도 바꾸지 않는다 — 전환 효과·지도·저장이 쓰는 원래 그림 그대로):
//  1. 합성 한 번(패스)마다 글자 스프라이트(글리프 또는 구운 글 판) 그리기 직전·직후 화소를 적어 두고, 패스 끝에 역순으로 되감아
//     「글자 없는 배경」(gFbg)을 만든다. 되감기 전 화소가 그 스프라이트 직후와 다르면 그 위에 다른 것이 그려진 것 → 그 글자는 원래대로(1배).
//     글자의 실제 불투명도(한 글자씩 페이드·창 페이드)는 직전·직후 차이로 잰다(혼합 방식을 몰라도 맞는다).
//  2. 창으로 가는 BitBlt(engine_bridge 의 bitBlt 앞에 이어 붙임)에서, 늘린 창일 때만 글자 자리를 gFbg 로 바꾼 사본을 넘긴다
//     → 화면 모듈은 글자 없는 그림을 늘린다. 넘기기 직전 엔진 판의 글자 자리가 패스 직후와 같은지 본다(전환 효과가 바꿨으면 원래대로).
//  3. HiText_Paint 가 그 글자들을 물리 좌표에 실제 글꼴로 섞는다(같은 혼합 식: dst += (색 − dst)·덮임·불투명도).
// 1배 창이면 BitBlt 를 그대로 넘기고 그리지 않는다(원작 그대로). forest-qol.ini hitext=0 이면 갈고리를 하나도 걸지 않는다.
#include "qol.h"
#include <unordered_map>
#include <algorithm>
#include <atomic>
#include <tuple>
#include <cstdio>
#include <cstring>
#include <cmath>

namespace forest { namespace qol {
namespace {

// ---------------------------------------------------------------- 기록(hitext_log=1 일 때만)
bool gLogOn = false;
CRITICAL_SECTION gLogCs;
void HLog(const char* fmt, ...) {
    if (!gLogOn) return;
    char buf[1024];
    va_list ap; va_start(ap, fmt); int n = _vsnprintf_s(buf, sizeof(buf) - 3, _TRUNCATE, fmt, ap); va_end(ap);
    if (n < 0) n = (int)strlen(buf);
    char line[1100]; int m = sprintf_s(line, "%llu %s\r\n", GetTickCount64(), buf);
    EnterCriticalSection(&gLogCs);
    HANDLE f = CreateFileW((Root() + L"\\hitext.log").c_str(), FILE_APPEND_DATA, FILE_SHARE_READ, nullptr, OPEN_ALWAYS, 0, nullptr);
    if (f != INVALID_HANDLE_VALUE) { DWORD w; WriteFile(f, line, m, &w, nullptr); CloseHandle(f); }
    LeaveCriticalSection(&gLogCs);
}

// ---------------------------------------------------------------- 엔진 주소(엔진_메모·조사.md)
const uintptr_t kGlyphCall = 0x444d0d;      // call 0x4452b0 (글리프 그리기 분기)
const uintptr_t kGlyphRender = 0x4452b0;    // thiscall(this=글리프 객체) 8 인자, ret 0x20
const uintptr_t kGlyphVtbl = 0x45ca90;      // 글리프 객체 주 vtable
const uintptr_t kSpriteDraw = 0x42ee40;     // 스프라이트 그리기 thiscall(dest, clip, offset), ret 0xc
const uintptr_t kSceneVtbl = 0x45b97c;      // 장면 vtable(+0x30 부분 합성, +0x34 전체 합성)
const uintptr_t kBake = 0x438690;           // 텍스트 객체를 판에 굽기 thiscall(dest, clip, offset), ret 0xc
const uintptr_t kBakeCalls[2] = {0x4081c2, 0x408400};   // 그것을 부르는 곳(자막 글 넣기)
const uintptr_t kBakeGlyphCall = 0x4386fb;  // 굽기 안의 call 0x42def0(글자 하나 찍기, 같은 인자 꼴)
const uintptr_t kBakeGlyphDraw = 0x42def0;
const uintptr_t kBitBltIat = 0x459018;
const uintptr_t kRepaintAll = 0x43d000;     // 엔진 thiscall: 앞 판 전체를 창으로
const int W = 800, H = 600;

uint32_t* frontBits(uintptr_t* subOut = nullptr) {
    uint8_t* eng = *(uint8_t**)0x466398; if (!eng) return nullptr;
    uint8_t* f = *(uint8_t**)(eng + 0x9c); if (!f) return nullptr;
    uint8_t* sub = f + *(int32_t*)(*(uint8_t**)f + 4);
    if (subOut) *subOut = (uintptr_t)sub;
    if (*(int*)(sub + 0x14) != W || *(int*)(sub + 0x18) != H) return nullptr;
    return *(uint32_t**)(sub + 8);
}
uint8_t* spriteOf(void* obj) { uint8_t* o = (uint8_t*)obj; return o + 4 + *(int32_t*)(*(uint8_t**)(o + 4) + 4); }
// 표면(스프라이트 하위 객체): +8 화소(위→아래 BGRA, 알파 바이트 = 투명도), +0x14 너비, +0x18 높이
const uint32_t* surfBits(const void* s) { return *(const uint32_t* const*)((const uint8_t*)s + 8); }
int surfW(const void* s) { return *(const int*)((const uint8_t*)s + 0x14); }
int surfH(const void* s) { return *(const int*)((const uint8_t*)s + 0x18); }

// ---------------------------------------------------------------- 사각형
bool empty(const RECT& r) { return r.right <= r.left || r.bottom <= r.top; }
RECT isect(const RECT& a, const RECT& b) { RECT r = {std::max(a.left, b.left), std::max(a.top, b.top), std::min(a.right, b.right), std::min(a.bottom, b.bottom)}; return r; }
bool overlaps(const RECT& a, const RECT& b) { return !empty(isect(a, b)); }
RECT unite(const RECT& a, const RECT& b) { RECT r = {std::min(a.left, b.left), std::min(a.top, b.top), std::max(a.right, b.right), std::max(a.bottom, b.bottom)}; return r; }
bool inside(const RECT& in, const RECT& out) { return in.left >= out.left && in.top >= out.top && in.right <= out.right && in.bottom <= out.bottom; }
RECT moved(const RECT& r, int dx, int dy) { return RECT{r.left + dx, r.top + dy, r.right + dx, r.bottom + dy}; }
const RECT kScreen = {0, 0, W, H};
void copyRect(uint32_t* dst, const uint32_t* src, const RECT& r) { for (int y = r.top; y < r.bottom; ++y) memcpy(dst + y * W + r.left, src + y * W + r.left, (r.right - r.left) * 4); }
bool sameRect(const uint32_t* a, const uint32_t* b, const RECT& r) { for (int y = r.top; y < r.bottom; ++y) if (memcmp(a + y * W + r.left, b + y * W + r.left, (r.right - r.left) * 4)) return false; return true; }
void grab(std::vector<uint32_t>& out, const uint32_t* f, const RECT& r) { int w = r.right - r.left; out.resize(w * (r.bottom - r.top)); for (int y = r.top; y < r.bottom; ++y) memcpy(&out[(y - r.top) * w], f + y * W + r.left, w * 4); }
void put(uint32_t* f, const std::vector<uint32_t>& in, const RECT& r) { int w = r.right - r.left; for (int y = r.top; y < r.bottom; ++y) memcpy(f + y * W + r.left, &in[(y - r.top) * w], w * 4); }
bool sameAs(const uint32_t* f, const std::vector<uint32_t>& in, const RECT& r) { int w = r.right - r.left; for (int y = r.top; y < r.bottom; ++y) if (memcmp(f + y * W + r.left, &in[(y - r.top) * w], w * 4)) return false; return true; }

// ---------------------------------------------------------------- 글리프 등록(엔진이 글자를 만들 때)
struct Glyph {
    uint16_t ch = 0; int16_t height = 0; uint8_t face = 0, bold = 0, italic = 0, mode = 0;
    uint32_t color = 0;                // 0x00RRGGBB
    int bbw = 0, bbh = 0, orgx = 0, orgy = 0;
    void* obj = nullptr;
};
struct GlyphAt { Glyph g; RECT d; };  // d = BlackBox 사각형(화면 좌표, 구운 글 목록에서는 판 좌표)
SRWLOCK gRegLock = SRWLOCK_INIT;
std::unordered_map<uintptr_t, Glyph> gReg;    // 글리프 스프라이트 하위 객체 → 글리프
const char* kFaces[] = {"Gulim", "Batang"};

using GlyphFn = void(__fastcall*)(void*, void*, unsigned, int, const char*, int, int, int, int, unsigned);
void __fastcall hGlyph(void* self, void* edx, unsigned ch, int height, const char* face, int vertical, int mode, int bold, int italic, unsigned color) {
    ((GlyphFn)kGlyphRender)(self, edx, ch, height, face, vertical, mode, bold, italic, color);
    uintptr_t key = (uintptr_t)spriteOf(self);
    uint8_t* o = (uint8_t*)self;
    int fi = -1;
    if (face) for (int i = 0; i < 2; ++i) if (!strcmp(face, kFaces[i])) fi = i;
    // 모드 1(따로 섞는 회색 판)·4·5(TextOutA)·세로쓰기는 원래대로 둔다
    bool ok = !vertical && fi >= 0 && (mode == 0 || mode == 2 || mode == 3) && height > 0 && height < 200;
    if (!ok && gLogOn) { static volatile LONG n = 0; if (InterlockedIncrement(&n) <= 20) HLog("glyph not tracked ch=%04x h=%d face=%s vert=%d mode=%d", ch & 0xffff, height, face ? face : "?", vertical, mode); }
    AcquireSRWLockExclusive(&gRegLock);
    if (!ok) gReg.erase(key);
    else {
        Glyph g; g.ch = (uint16_t)ch; g.height = (int16_t)height; g.face = (uint8_t)fi; g.bold = bold != 0; g.italic = italic != 0; g.mode = (uint8_t)mode;
        g.color = color & 0xffffff; g.bbw = *(int*)(o + 8); g.bbh = *(int*)(o + 0xc); g.orgx = *(int*)(o + 0x10); g.orgy = *(int*)(o + 0x14); g.obj = self;
        if (gReg.size() > 20000) gReg.clear();
        gReg[key] = g;
    }
    ReleaseSRWLockExclusive(&gRegLock);
}
bool lookupGlyph(void* spr, Glyph& g) {
    AcquireSRWLockShared(&gRegLock);
    auto it = gReg.find((uintptr_t)spr);
    bool hit = it != gReg.end();
    if (hit) g = it->second;
    ReleaseSRWLockShared(&gRegLock);
    if (!hit) return false;
    // 지운 뒤 같은 주소를 다른 스프라이트가 쓰는 경우를 거른다
    if (*(uintptr_t*)g.obj != kGlyphVtbl || surfW(spr) != g.bbw || surfH(spr) != g.bbh) {
        AcquireSRWLockExclusive(&gRegLock); gReg.erase((uintptr_t)spr); ReleaseSRWLockExclusive(&gRegLock);
        return false;
    }
    return true;
}

// ---------------------------------------------------------------- 구운 글(자막): 판 → 글자 목록
struct Bake { int w = 0, h = 0; uint64_t hash = 0; std::vector<GlyphAt> glyphs; };
std::unordered_map<uintptr_t, Bake> gBake;    // 판(스프라이트 하위 객체) → 구운 글자들(판 좌표), gRegLock 으로 지킴
thread_local std::vector<GlyphAt>* tBakeList = nullptr;
thread_local uintptr_t tBakeDest = 0;
uint64_t surfHash(const void* s) {
    const uint32_t* p = surfBits(s); int n = surfW(s) * surfH(s);
    if (!p || n <= 0) return 0;
    uint64_t h = 1469598103934665603ull;
    for (int i = 0; i < n; ++i) { h ^= p[i]; h *= 1099511628211ull; }
    return h;
}
using DrawFn = int(__fastcall*)(void*, void*, void*, RECT*, POINT*);
int __fastcall hBakeGlyph(void* spr, void* edx, void* dest, RECT* clip, POINT* off) {
    int r = ((DrawFn)kBakeGlyphDraw)(spr, edx, dest, clip, off);
    Glyph g;
    if (tBakeList && (uintptr_t)dest == tBakeDest && lookupGlyph(spr, g)) {
        // 굽기(0x42def0 → 0x42e540)는 자리를 스프라이트 +0x1c·+0x20(부모 기준) + offset 으로 잡는다(장면에 안 붙은 임시 객체라 +0x3c 는 비어 있음)
        uint8_t* s = (uint8_t*)spr; POINT o = off ? *off : POINT{0, 0};
        int x = o.x + *(int*)(s + 0x1c), y = o.y + *(int*)(s + 0x20);
        if (g.bbw > 0 && g.bbh > 0) tBakeList->push_back(GlyphAt{g, RECT{x, y, x + g.bbw, y + g.bbh}});
    }
    return r;
}
int __fastcall hBake(void* text, void* edx, void* dest, RECT* clip, POINT* off) {
    std::vector<GlyphAt> list;
    tBakeList = &list; tBakeDest = (uintptr_t)dest;
    int r = ((DrawFn)kBake)(text, edx, dest, clip, off);
    tBakeList = nullptr; tBakeDest = 0;
    Bake b; b.w = surfW(dest); b.h = surfH(dest); b.hash = surfHash(dest); b.glyphs = std::move(list);
    AcquireSRWLockExclusive(&gRegLock);
    if (b.glyphs.empty() || !b.hash) gBake.erase((uintptr_t)dest); else { if (gBake.size() > 200) gBake.clear(); gBake[(uintptr_t)dest] = std::move(b); }
    ReleaseSRWLockExclusive(&gRegLock);
    return r;
}
bool lookupBake(void* spr, Bake& b) {
    AcquireSRWLockShared(&gRegLock);
    auto it = gBake.find((uintptr_t)spr);
    bool hit = it != gBake.end();
    if (hit) b = it->second;
    ReleaseSRWLockShared(&gRegLock);
    if (!hit) return false;
    if (surfW(spr) != b.w || surfH(spr) != b.h || surfHash(spr) != b.hash) {   // 판이 다른 그림으로 바뀜
        AcquireSRWLockExclusive(&gRegLock); gBake.erase((uintptr_t)spr); ReleaseSRWLockExclusive(&gRegLock);
        return false;
    }
    return true;
}

// ---------------------------------------------------------------- 패스(장면 합성 한 번)
struct Item { uintptr_t key; std::vector<GlyphAt> glyphs; RECT d, dr; std::vector<uint32_t> before, after; float alpha; bool measured; };
struct Pass { uintptr_t dest; RECT r; uint32_t* f; std::vector<Item> items; };
thread_local Pass* tPass = nullptr;

struct Inst { std::vector<GlyphAt> glyphs; RECT d = {}; float alpha = 1.f; bool fallback = false, shown = false; };
CRITICAL_SECTION gCs;
std::unordered_map<uintptr_t, Inst> gInst;    // 화면에 있는 글자 스프라이트(하위 객체 → 상태)
std::vector<uint32_t> gFbg, gFA;              // 글자 없는 배경, 패스 직후 판(800×600)
LONGLONG gQpf = 1, tPassUs = 0, tSubUs = 0, tPaintUs = 0, maxPassUs = 0, maxSubUs = 0, maxPaintUs = 0;
int nPass = 0, nSub = 0, nPaint = 0, nGlyphPaint = 0, nStale = 0, nCovered = 0, nBakeDraw = 0;
LONGLONG now() { LARGE_INTEGER q; QueryPerformanceCounter(&q); return q.QuadPart; }
LONGLONG us(LONGLONG t0) { return (now() - t0) * 1000000 / gQpf; }

// 글자의 실제 불투명도: 직전·직후 화소와 스프라이트 판(덮임 = 255 − 알파 바이트, 색 = 판의 RGB)으로 최소제곱
void measure(Item& it, const void* surf) {
    const uint32_t* sb = surfBits(surf); int sw = surfW(surf);
    if (!sb) return;
    double num = 0, den = 0;
    int w = it.dr.right - it.dr.left;
    for (int y = it.dr.top; y < it.dr.bottom; ++y) for (int x = it.dr.left; x < it.dr.right; ++x) {
        uint32_t sp = sb[(y - it.d.top) * sw + (x - it.d.left)];
        double c = (255 - (sp >> 24)) / 255.0;
        if (c <= 0) continue;
        int cb = sp & 255, cg = (sp >> 8) & 255, cr = (sp >> 16) & 255;
        uint32_t b = it.before[(y - it.dr.top) * w + (x - it.dr.left)], a = it.after[(y - it.dr.top) * w + (x - it.dr.left)];
        int bb = b & 255, bg = (b >> 8) & 255, br = (b >> 16) & 255, ab = a & 255, ag = (a >> 8) & 255, ar = (a >> 16) & 255;
        num += c * ((ar - br) * (cr - br) + (ag - bg) * (cg - bg) + (ab - bb) * (cb - bb));
        den += c * c * ((cr - br) * (cr - br) + (cg - bg) * (cg - bg) + (cb - bb) * (cb - bb));
    }
    if (den > 900) { it.alpha = (float)std::min(1.0, std::max(0.0, num / den)); it.measured = true; }
}

DrawFn oDraw = nullptr;
int __fastcall hDraw(void* spr, void* edx, void* dest, RECT* clip, POINT* off) {
    Pass* p = tPass;
    if (!p || (uintptr_t)dest != p->dest) return oDraw(spr, edx, dest, clip, off);   // 패스 밖·다른 판(전환용 판 등)
    uint8_t* s = (uint8_t*)spr;
    // 혼합 방식 0(보통)·2(전체 불투명도 +0x2c — 한 글자씩 찍힐 때 63→127→191→255)만. 불투명도는 measure 가 잰다
    int blendMode = *(int*)(s + 0x28);
    if ((blendMode != 0 && blendMode != 2) || *(int*)(s + 0x30) != 0) return oDraw(spr, edx, dest, clip, off);
    Glyph g; Bake b;
    bool isGlyph = lookupGlyph(spr, g), isBake = !isGlyph && lookupBake(spr, b);
    if (!isGlyph && !isBake) return oDraw(spr, edx, dest, clip, off);
    POINT o = off ? *off : POINT{0, 0};
    RECT d = {o.x + *(int*)(s + 0x3c), o.y + *(int*)(s + 0x40), o.x + *(int*)(s + 0x44), o.y + *(int*)(s + 0x48)};
    if (d.right - d.left != surfW(spr) || d.bottom - d.top != surfH(spr)) return oDraw(spr, edx, dest, clip, off);
    RECT dr = isect(isect(d, clip ? *clip : kScreen), kScreen);
    if (empty(dr)) return oDraw(spr, edx, dest, clip, off);
    Item it; it.key = (uintptr_t)spr; it.d = d; it.dr = dr; it.alpha = 1.f; it.measured = false;
    if (isGlyph) it.glyphs.push_back(GlyphAt{g, d});
    else { for (auto& ga : b.glyphs) it.glyphs.push_back(GlyphAt{ga.g, moved(ga.d, d.left, d.top)}); ++nBakeDraw; }
    grab(it.before, p->f, dr);
    int r = oDraw(spr, edx, dest, clip, off);
    grab(it.after, p->f, dr);
    measure(it, spr);
    p->items.push_back(std::move(it));
    return r;
}

void passEnd(Pass& p) {
    EnterCriticalSection(&gCs);
    // 이번 패스 자리에 있었는데 그려지지 않은 글자 = 사라짐(숨김·쪽 넘김·장면 바뀜)
    for (auto it = gInst.begin(); it != gInst.end();) {
        bool drawn = false;
        for (auto& i : p.items) if (i.key == it->first) { drawn = true; break; }
        if (!drawn && overlaps(it->second.d, p.r)) it = gInst.erase(it); else ++it;
    }
    if (!p.items.empty()) {
        std::vector<char> covered(p.items.size(), 0);
        for (auto& i : p.items) copyRect(gFbg.data(), p.f, i.dr);
        for (int i = (int)p.items.size() - 1; i >= 0; --i) {
            Item& it = p.items[i];
            if (!sameAs(gFbg.data(), it.after, it.dr)) covered[i] = 1;   // 이 글자 뒤에 다른 것이 그 자리에 그려졌다
            put(gFbg.data(), it.before, it.dr);
        }
        for (size_t i = 0; i < p.items.size(); ++i) if (covered[i])
            for (size_t j = 0; j < p.items.size(); ++j) if (j != i && overlaps(p.items[j].dr, p.items[i].dr)) covered[j] = 1;
        for (size_t i = 0; i < p.items.size(); ++i) {
            Item& it = p.items[i];
            copyRect(gFA.data(), p.f, it.dr);
            Inst& in = gInst[it.key];
            bool changed = !EqualRect(&in.d, &it.d) || in.glyphs.size() != it.glyphs.size() || (!it.glyphs.empty() && in.glyphs[0].g.ch != it.glyphs[0].g.ch);
            in.glyphs = std::move(it.glyphs); in.d = it.d;
            if (it.measured) in.alpha = it.alpha; else if (changed) in.alpha = 1.f;
            in.fallback = covered[i] != 0;
            if (covered[i]) ++nCovered;
        }
    }
    LeaveCriticalSection(&gCs);
}

using Compose1Fn = int(__fastcall*)(void*, void*, void*, RECT*);
using Compose2Fn = int(__fastcall*)(void*, void*, void*);
Compose1Fn oComposeRect = nullptr; Compose2Fn oComposeAll = nullptr;
template <class F> int runPass(void* dest, const RECT& r, F&& call) {
    uintptr_t front = 0; uint32_t* f = frontBits(&front);
    if (!f || (uintptr_t)dest != front || tPass) return call();
    Pass p; p.dest = front; p.r = isect(r, kScreen); p.f = f;
    tPass = &p;
    int ret = call();
    tPass = nullptr;
    LONGLONG t0 = now();
    passEnd(p);
    LONGLONG u = us(t0); tPassUs += u; maxPassUs = std::max(maxPassUs, u); ++nPass;
    return ret;
}
int __fastcall hComposeRect(void* self, void* edx, void* dest, RECT* r) { return runPass(dest, r ? *r : kScreen, [&] { return oComposeRect(self, edx, dest, r); }); }
int __fastcall hComposeAll(void* self, void* edx, void* dest) { return runPass(dest, kScreen, [&] { return oComposeAll(self, edx, dest); }); }

bool gOn = false;   // 설치됨·켜짐(HiText_SetActive)

// ---------------------------------------------------------------- 창으로 가는 BitBlt: 글자 자리를 배경으로 바꾼 사본을 넘긴다
using BitBltFn = BOOL(WINAPI*)(HDC, int, int, int, int, HDC, int, int, DWORD);
BitBltFn nextBitBlt = nullptr;
bool scaled(const Layout& L) { return L.cw != W || L.ch != H; }
struct Sub { HDC dc = nullptr; HBITMAP bmp = nullptr; uint32_t* bits = nullptr; };
thread_local Sub tSub;
void subFree() { if (tSub.dc) { DeleteDC(tSub.dc); DeleteObject(tSub.bmp); tSub = Sub(); } }
bool subReady() {
    if (tSub.dc) return true;
    BITMAPINFO bi = {}; bi.bmiHeader.biSize = sizeof(bi.bmiHeader); bi.bmiHeader.biWidth = W; bi.bmiHeader.biHeight = -H; bi.bmiHeader.biPlanes = 1; bi.bmiHeader.biBitCount = 32;
    void* bits = nullptr;
    HBITMAP b = CreateDIBSection(nullptr, &bi, DIB_RGB_COLORS, &bits, nullptr, 0);
    if (!b) return false;
    HDC dc = CreateCompatibleDC(nullptr);
    SelectObject(dc, b);
    tSub.dc = dc; tSub.bmp = b; tSub.bits = (uint32_t*)bits;
    return true;
}
// 넘길 사각형 U 를 정하고 사본을 채운다. 바꿀 것이 없으면 false(그래도 U 는 걸친 글자를 덮게 넓혀 둔다)
bool buildSub(RECT& U) {
    uint32_t* f = frontBits();
    if (!f || !subReady()) return false;
    bool any = false;
    EnterCriticalSection(&gCs);
    // 걸친 글자는 통째로 넘긴다(화면 모듈 판에 반쪽 글자가 남지 않게). 1배로 되돌릴 글자(덮임·전환 효과로 낡음)도 같다:
    // 예전엔 대체할 글자만 넓혀서, 전환 효과가 노란 자막의 일부 자리만 바꾸면 그 자리만 1배로 다시 칠해지고
    // 나머지엔 전에 그린 고해상도 글자가 남아 한 줄이 깨져 보였다(11-24 사용자 「고해상도 글자 노란색이 일부 깨지네」).
    for (bool grow = true; grow;) {
        grow = false;
        for (auto& kv : gInst) if (overlaps(kv.second.d, U) && !inside(isect(kv.second.d, kScreen), U)) { U = unite(U, isect(kv.second.d, kScreen)); grow = true; }
    }
    for (auto it = gInst.begin(); it != gInst.end();) {
        Inst& in = it->second;
        RECT d = isect(in.d, kScreen);
        if (!overlaps(d, U)) { ++it; continue; }
        if (in.fallback) { in.shown = false; ++it; continue; }
        if (!sameRect(f, gFA.data(), d)) { ++nStale; it = gInst.erase(it); continue; }   // 전환 효과 등이 판을 바꿨다 → 원래대로
        if (!any) { GdiFlush(); copyRect(tSub.bits, f, U); any = true; }
        ++it;
    }
    if (any) for (auto& kv : gInst) {
        Inst& in = kv.second;
        RECT d = isect(in.d, kScreen);
        if (in.fallback || !overlaps(d, U)) continue;
        copyRect(tSub.bits, gFbg.data(), d);
        in.shown = true;
    }
    LeaveCriticalSection(&gCs);
    return any;
}
BOOL WINAPI hBitBlt(HDC d, int x, int y, int w, int h, HDC s, int sx, int sy, DWORD rop) {
    HWND gw = GameWindow();
    if (gOn && gw && d && x == sx && y == sy && rop == SRCCOPY && w > 0 && h > 0 && WindowFromDC(d) == gw && scaled(CurrentLayout())) {
        LONGLONG t0 = now();
        RECT U0 = isect(RECT{x, y, x + w, y + h}, kScreen), U = U0;
        if (!empty(U) && buildSub(U)) {
            LONGLONG u = us(t0); tSubUs += u; maxSubUs = std::max(maxSubUs, u); ++nSub;
            return nextBitBlt(d, U.left, U.top, U.right - U.left, U.bottom - U.top, tSub.dc, U.left, U.top, SRCCOPY);
        }
        // 대체할 글자는 없지만 걸친 글자 때문에 넓어졌으면(1배로 되돌린 글자) 넓힌 자리를 엔진 판에서 통째로 넘긴다
        if (!empty(U) && !EqualRect(&U, &U0) && inside(RECT{x, y, x + w, y + h}, U))
            return nextBitBlt(d, U.left, U.top, U.right - U.left, U.bottom - U.top, s, U.left, U.top, rop);
    }
    return nextBitBlt(d, x, y, w, h, s, sx, sy, rop);
}

// ---------------------------------------------------------------- 실제 글꼴로 그리기
struct CovKey { uint16_t ch; uint8_t face, bold, italic; int16_t px; bool operator==(const CovKey& o) const { return ch == o.ch && face == o.face && bold == o.bold && italic == o.italic && px == o.px; } };
struct CovHash { size_t operator()(const CovKey& k) const { return ((size_t)k.ch * 1315423911u) ^ ((size_t)k.face << 1) ^ ((size_t)k.bold << 2) ^ ((size_t)k.italic << 3) ^ ((size_t)k.px << 8); } };
struct Cov { int w = 0, h = 0, ox = 0, oy = 0; std::vector<uint8_t> v; };   // v: 0..64
CRITICAL_SECTION gCovCs;
std::unordered_map<CovKey, Cov, CovHash> gCov;
HDC gCovDc = nullptr;
struct FontKey { uint8_t face, bold, italic; int16_t px; bool operator<(const FontKey& o) const { return std::tie(face, bold, italic, px) < std::tie(o.face, o.bold, o.italic, o.px); } };
std::map<FontKey, HFONT> gFonts;
const Cov& coverage(const Glyph& g, int px) {
    CovKey k{g.ch, g.face, g.bold, g.italic, (int16_t)px};
    auto it = gCov.find(k);
    if (it != gCov.end()) return it->second;
    if (gCov.size() > 6000) gCov.clear();
    Cov& c = gCov[k];
    FontKey fk{g.face, g.bold, g.italic, (int16_t)px};
    HFONT& f = gFonts[fk];
    if (!f) f = CreateFontA(px, 0, 0, 0, g.bold ? 700 : 0, g.italic, 0, 0, HANGEUL_CHARSET, 0, 0, 0, 0, kFaces[g.face]);
    if (!gCovDc) gCovDc = CreateCompatibleDC(nullptr);
    HGDIOBJ old = SelectObject(gCovDc, f);
    MAT2 m = {{0, 1}, {0, 0}, {0, 0}, {0, 1}};
    GLYPHMETRICS gm = {};
    DWORD n = GetGlyphOutlineA(gCovDc, g.ch, GGO_GRAY8_BITMAP, &gm, 0, nullptr, &m);
    if (n != GDI_ERROR && n > 0) {
        std::vector<uint8_t> raw(n);
        if (GetGlyphOutlineA(gCovDc, g.ch, GGO_GRAY8_BITMAP, &gm, n, raw.data(), &m) != GDI_ERROR) {
            c.w = gm.gmBlackBoxX; c.h = gm.gmBlackBoxY; c.ox = gm.gmptGlyphOrigin.x; c.oy = gm.gmptGlyphOrigin.y;
            int pitch = (c.w + 3) & ~3;
            c.v.resize(c.w * c.h);
            for (int y = 0; y < c.h; ++y) memcpy(&c.v[y * c.w], &raw[y * pitch], c.w);
        }
    }
    SelectObject(gCovDc, old);
    return c;
}
struct Target { uint8_t* bits = nullptr; int w = 0, h = 0, pitch = 0; };
bool targetOf(HDC dc, Target& t) {
    POINT vo{}, wo{}; GetViewportOrgEx(dc, &vo); GetWindowOrgEx(dc, &wo);
    if (vo.x || vo.y || wo.x || wo.y || GetMapMode(dc) != MM_TEXT) return false;
    HBITMAP b = (HBITMAP)GetCurrentObject(dc, OBJ_BITMAP);
    DIBSECTION ds = {};
    if (!b || GetObject(b, sizeof(ds), &ds) != sizeof(ds) || ds.dsBm.bmBitsPixel != 32 || !ds.dsBm.bmBits) return false;
    t.w = ds.dsBm.bmWidth; t.h = std::abs(ds.dsBm.bmHeight); t.pitch = ds.dsBm.bmWidthBytes;
    t.bits = (uint8_t*)ds.dsBm.bmBits;
    // GetObject 는 위→아래 DIB 도 biHeight 를 양수로 돌려줄 수 있다 → 판마다 한 번 (0,0) 한 점으로 직접 잰다
    static HBITMAP lastB = nullptr; static int lastW = 0, lastH = 0; static bool lastTopDown = true;
    if (b != lastB || t.w != lastW || t.h != lastH) {
        GdiFlush();
        uint32_t* p0 = (uint32_t*)t.bits; uint32_t save = *p0;
        *p0 = 0x00010203;
        COLORREF c = GetPixel(dc, 0, 0);
        *p0 = save;
        if (c == CLR_INVALID) return false;
        lastTopDown = c == RGB(1, 2, 3); lastB = b; lastW = t.w; lastH = t.h;
    }
    if (!lastTopDown) { t.bits += (size_t)(t.h - 1) * t.pitch; t.pitch = -t.pitch; }   // 아래→위 DIB
    return true;
}
// 한 글자를 섞는다: dst += (색 − dst)·덮임·불투명도 (엔진 혼합과 같은 식)
void blend(Target& t, const Cov& c, int X, int Y, uint32_t color, float alpha, const RECT& clip) {
    RECT r = isect(RECT{X, Y, X + c.w, Y + c.h}, isect(clip, RECT{0, 0, t.w, t.h}));
    if (empty(r)) return;
    int cr = (color >> 16) & 255, cg = (color >> 8) & 255, cb = color & 255;
    int a256 = (int)(alpha * 256.f + 0.5f);
    for (int y = r.top; y < r.bottom; ++y) {
        uint8_t* row = t.bits + (ptrdiff_t)y * t.pitch;
        const uint8_t* cv = &c.v[(y - Y) * c.w];
        for (int x = r.left; x < r.right; ++x) {
            int v = cv[x - X]; if (!v) continue;
            int k = v * a256 / 64;   // 0..256
            uint8_t* p = row + x * 4;
            p[0] = (uint8_t)(p[0] + (((cb - p[0]) * k) >> 8));
            p[1] = (uint8_t)(p[1] + (((cg - p[1]) * k) >> 8));
            p[2] = (uint8_t)(p[2] + (((cr - p[2]) * k) >> 8));
        }
    }
}
// GDI 판이 아니면(드묾) 한 글자씩 AlphaBlend
void blendGdi(HDC dc, const Cov& c, int X, int Y, uint32_t color, float alpha, const RECT& clip) {
    if (c.w <= 0 || c.h <= 0) return;
    BITMAPINFO bi = {}; bi.bmiHeader.biSize = sizeof(bi.bmiHeader); bi.bmiHeader.biWidth = c.w; bi.bmiHeader.biHeight = -c.h; bi.bmiHeader.biPlanes = 1; bi.bmiHeader.biBitCount = 32;
    void* bits = nullptr; HBITMAP b = CreateDIBSection(nullptr, &bi, DIB_RGB_COLORS, &bits, nullptr, 0); if (!b) return;
    uint8_t* p = (uint8_t*)bits;
    for (int i = 0; i < c.w * c.h; ++i) { int k = c.v[i] * 255 / 64; p[i * 4] = (uint8_t)((color & 255) * k / 255); p[i * 4 + 1] = (uint8_t)(((color >> 8) & 255) * k / 255); p[i * 4 + 2] = (uint8_t)(((color >> 16) & 255) * k / 255); p[i * 4 + 3] = (uint8_t)k; }
    HDC m = CreateCompatibleDC(dc); HGDIOBJ o = SelectObject(m, b);
    int sv = SaveDC(dc); IntersectClipRect(dc, clip.left, clip.top, clip.right, clip.bottom);
    BLENDFUNCTION bf = {AC_SRC_OVER, 0, (BYTE)(alpha * 255.f + 0.5f), AC_SRC_ALPHA};
    AlphaBlend(dc, X, Y, c.w, c.h, m, 0, 0, c.w, c.h, bf);
    RestoreDC(dc, sv); SelectObject(m, o); DeleteDC(m); DeleteObject(b);
}
struct Shown { Glyph g; RECT d; float alpha; };
Layout gLastL; bool gHaveLastL = false;
std::atomic<bool> gRefreshQueued{false};
DWORD WINAPI refreshThread(void*) {
    Sleep(60);
    gRefreshQueued = false;
    void* eng = *(void**)0x466398;
    if (eng && GameWindow()) ((void(__fastcall*)(void*, void*))kRepaintAll)(eng, nullptr);   // 엔진 BitBlt → 우리 사본 → 화면 모듈
    subFree();   // 이 스레드가 만든 사본 판
    return 0;
}
void queueRefresh() {
    bool expect = false;
    if (gRefreshQueued.compare_exchange_strong(expect, true)) { HANDLE th = CreateThread(nullptr, 0, refreshThread, nullptr, 0, nullptr); if (th) CloseHandle(th); else gRefreshQueued = false; }
}
bool gInstalled = false;
}  // namespace

bool HiText_Install() {
    InitializeCriticalSection(&gLogCs);
    gLogOn = Cfg("hitext_log", 0) != 0;
    if (!Cfg("hitext", 1)) { HLog("hitext off"); return false; }
    LARGE_INTEGER q; QueryPerformanceFrequency(&q); gQpf = q.QuadPart;
    InitializeCriticalSection(&gCs); InitializeCriticalSection(&gCovCs);
    gFbg.assign(W * H, 0); gFA.assign(W * H, 0);
    static const uint8_t eCall[5] = {0xE8, 0x9E, 0x05, 0x00, 0x00};                // 0x444d0d: call 0x4452b0
    static const uint8_t eDraw[7] = {0x6A, 0xFF, 0x68, 0xB8, 0x75, 0x45, 0x00};    // 0x42ee40: push -1; push 0x4575b8
    static const uint8_t eBake1[5] = {0xE8, 0xC9, 0x04, 0x03, 0x00};               // 0x4081c2: call 0x438690
    static const uint8_t eBake2[5] = {0xE8, 0x8B, 0x02, 0x03, 0x00};               // 0x408400: call 0x438690
    static const uint8_t eBakeG[5] = {0xE8, 0xF0, 0x57, 0xFF, 0xFF};               // 0x4386fb: call 0x42def0
    const uintptr_t vRect = kSceneVtbl + 0x30, vAll = kSceneVtbl + 0x34;
    if (memcmp((void*)kGlyphCall, eCall, 5) || memcmp((void*)kSpriteDraw, eDraw, 7) || *(uintptr_t*)vRect != 0x435b50 || *(uintptr_t*)vAll != 0x435b60) {
        HLog("hitext: engine bytes differ, not installed"); return false;
    }
    bool bakeOk = !memcmp((void*)kBakeCalls[0], eBake1, 5) && !memcmp((void*)kBakeCalls[1], eBake2, 5) && !memcmp((void*)kBakeGlyphCall, eBakeG, 5);
    uint8_t* tramp = (uint8_t*)VirtualAlloc(nullptr, 16, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!tramp) return false;
    memcpy(tramp, eDraw, 7); tramp[7] = 0xE9; *(int32_t*)(tramp + 8) = (int32_t)(kSpriteDraw + 7 - ((uintptr_t)tramp + 12));
    oDraw = (DrawFn)tramp;
    oComposeRect = (Compose1Fn)*(uintptr_t*)vRect; oComposeAll = (Compose2Fn)*(uintptr_t*)vAll;
    nextBitBlt = *(BitBltFn*)kBitBltIat;   // engine_bridge 의 bitBlt(그 뒤가 화면 모듈)
    auto rel = [](uint8_t* b, uintptr_t at, void* to) { b[0] = 0xE8; *(int32_t*)(b + 1) = (int32_t)((uintptr_t)to - (at + 5)); };
    uint8_t call[5]; rel(call, kGlyphCall, (void*)hGlyph);
    uint8_t jmp[7]; memset(jmp, 0x90, 7); jmp[0] = 0xE9; *(int32_t*)(jmp + 1) = (int32_t)((uintptr_t)hDraw - (kSpriteDraw + 5));
    uintptr_t pr = (uintptr_t)hComposeRect, pa = (uintptr_t)hComposeAll, eR = 0x435b50, eA = 0x435b60;
    BitBltFn bb = hBitBlt, cur = nextBitBlt;
    bool ok = PatchBytes(kSpriteDraw, eDraw, jmp, 7)
           && PatchBytes(vRect, &eR, &pr, 4) && PatchBytes(vAll, &eA, &pa, 4)
           && PatchBytes(kBitBltIat, &cur, &bb, 4)
           && PatchBytes(kGlyphCall, eCall, call, 5);
    if (ok && bakeOk) {   // 자막(구운 글)
        uint8_t c1[5], c2[5], c3[5]; rel(c1, kBakeCalls[0], (void*)hBake); rel(c2, kBakeCalls[1], (void*)hBake); rel(c3, kBakeGlyphCall, (void*)hBakeGlyph);
        bakeOk = PatchBytes(kBakeCalls[0], eBake1, c1, 5) && PatchBytes(kBakeCalls[1], eBake2, c2, 5) && PatchBytes(kBakeGlyphCall, eBakeG, c3, 5);
    }
    HLog("hitext installed %d (subtitles %d)", ok, bakeOk);
    gInstalled = gOn = ok;
    return ok;
}
void HiText_WindowReady(HWND) {}
// qol.h 밖(시험·통합용): 실행 중 켜고 끄기. 끄면 BitBlt 를 그대로 넘기고 그리지 않는다. 바꾼 뒤 엔진 전체 다시 찍기를 부른다.
void HiText_SetActive(bool on) {
    if (!gInstalled) return;
    gOn = on;
    queueRefresh();
}
bool HiText_Active() { return gOn; }

void HiText_Paint(HDC dc, const Layout& L, const RECT& clip) {
    if (!gOn || !scaled(L) || empty(clip)) return;
    LONGLONG t0 = now();
    if (!gHaveLastL || memcmp(&gLastL, &L, sizeof(L))) {
        // 배율이 바뀌면 화면 모듈 판의 글자 자리를 새로 받게 엔진 전체 다시 찍기(1배 때 받은 판에는 흐린 1배 글자가 들어 있다)
        gLastL = L; gHaveLastL = true;
        queueRefresh();
    }
    std::vector<Shown> list;
    double sx = L.cw / (double)W, sy = L.ch / (double)H;
    EnterCriticalSection(&gCs);
    for (auto& kv : gInst) {
        const Inst& in = kv.second;
        if (!in.shown || in.fallback || in.alpha <= 0.f) continue;
        for (auto& ga : in.glyphs) {
            RECT pr = {L.ox + (int)floor((ga.d.left - 2) * sx), L.oy + (int)floor((ga.d.top - 2) * sy), L.ox + (int)ceil((ga.d.right + 2) * sx), L.oy + (int)ceil((ga.d.bottom + 2) * sy)};
            if (overlaps(pr, clip)) list.push_back(Shown{ga.g, ga.d, in.alpha});
        }
    }
    LeaveCriticalSection(&gCs);
    if (!list.empty()) {
        Target t; bool direct = targetOf(dc, t);
        if (direct) GdiFlush();
        EnterCriticalSection(&gCovCs);
        for (auto& s : list) {
            int px = std::max(1, (int)lround(s.g.height * sy));
            const Cov& c = coverage(s.g, px);
            if (c.w <= 0) continue;
            double penX = s.d.left - s.g.orgx, base = s.d.top + s.g.orgy;   // 1배 펜·기준선
            int X = L.ox + (int)lround(penX * sx) + c.ox, Y = L.oy + (int)lround(base * sy) - c.oy;
            if (direct) blend(t, c, X, Y, s.g.color, s.alpha, clip); else blendGdi(dc, c, X, Y, s.g.color, s.alpha, clip);
            ++nGlyphPaint;
        }
        LeaveCriticalSection(&gCovCs);
    }
    LONGLONG u = us(t0); tPaintUs += u; maxPaintUs = std::max(maxPaintUs, u); ++nPaint;
    static DWORD lastLog = 0;
    if (gLogOn && GetTickCount() - lastLog > 3000) {
        lastLog = GetTickCount();
        HLog("stats: pass %d avg %.0fus max %lldus | sub %d avg %.0fus max %lldus | paint %d avg %.0fus max %lldus glyphs %d | inst %zu stale %d covered %d bakeDraw %d",
             nPass, nPass ? tPassUs / (double)nPass : 0., maxPassUs, nSub, nSub ? tSubUs / (double)nSub : 0., maxSubUs,
             nPaint, nPaint ? tPaintUs / (double)nPaint : 0., maxPaintUs, nGlyphPaint, gInst.size(), nStale, nCovered, nBakeDraw);
    }
}

bool HiText_Rects(std::vector<RECT>& out) {
    out.clear();
    if (!gOn) return false;
    EnterCriticalSection(&gCs);
    for (auto& kv : gInst) if (kv.second.shown && !kv.second.fallback) {
        RECT d = kv.second.d; InflateRect(&d, 2, 2); out.push_back(isect(d, kScreen));
    }
    LeaveCriticalSection(&gCs);
    // 화면 모듈이 목록이 바뀌었는지 비교하므로 순서를 고정한다
    std::sort(out.begin(), out.end(), [](const RECT& a, const RECT& b) { return std::tie(a.top, a.left, a.bottom, a.right) < std::tie(b.top, b.left, b.bottom, b.right); });
    return !out.empty();
}

}}  // namespace forest::qol
