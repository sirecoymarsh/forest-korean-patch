// qol_hiart.cpp — 4K 그림 모듈(세션 「4K 그림」 몫, 2026-11-21).
//
// 늘린 창에서 CG·배경·스탠딩·얼굴 창·컷인을 4배 그림(hiart\ 폴더)으로 다시 합성한다. 엔진 근거는 P:\AI\forest-qol\s-hiart\진행.md.
//  - 층 50개(`[0x466238+i*4]`, 크기 0x364). 층 바탕 S = 층 + [[층]+4](=0x2a4): +0xc 보임, +0x1c/+0x20 자리, +0x30 효과(6 = 색 절반).
//    층의 그림 객체 I = [층+0x50], 그 바탕 SI = I + 4 + [[I+4]+4]: +4 화소(BGRA, 알파 바이트 = 투명도 255−a), +0xc 보임,
//    +0x14/+0x18 크기, +0x28 섞기 방식(그림은 0), +0x3c 사각형(층 기준).
//  - 그림은 층::그림 읽기 0x4069d0(thiscall: 경로 ".\grpe\4040", 인자) 로만 바뀐다 → 여기 갈고리에서 층마다 열쇠를 적고 1배 화소를 복사.
//  - 엔진은 층을 번호 순으로 앞 판에 섞고(검정 바탕 위 (s·a + d·(255−a))/255, ±2), 장면·스탠딩·얼굴 창 전환은 옛 화면과 새 합성을
//    화면 전체 같은 t 로 섞는다(0.05·0.1 단계).
// 방식: 찍기마다(화면 모듈 PaintAbove, 화면 잠금 안) 그림자 판(1배 화면)을 층 모형으로 화소마다 맞춰 본다.
//  맞는 화소만 4배 합성으로 덮는다 — 지금 상태 / 바로 앞 상태 / 둘 사이 같은 t 섞기(전환 중). 안 맞는 곳(아이콘 줄·선택지·
//  설정 화면·지도·4K 글자 갈래가 남긴 1배 글자 등)은 늘린 1배 그대로라 어긋남이 없다.
// forest-qol.ini: hiart=0 이면 끔(1배 늘림). hiart_cache_mb(기본 256), hiart_tol(기본 3), hiart_log=1 이면 시간·사건 기록.
#include "qol.h"
#include <wincodec.h>
#include <emmintrin.h>
#include <unordered_map>
#include <deque>
#include <set>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#pragma comment(lib, "ole32.lib")
#pragma comment(lib, "windowscodecs.lib")

namespace forest { namespace qol {
const uint32_t* Present_ShadowBits();   // 화면 모듈: 800×600 그림자 판(약속에 넣어 달라고 요청)

namespace {
constexpr uintptr_t kLayerTable = 0x466238;
constexpr int kLayers = 50;
constexpr uintptr_t kLoadFn = 0x4069d0;
constexpr int W1 = 800, H1 = 600;

bool gOn = false, gLog = false, gDiag = false, gTestFlag = false;
int gTol = 3;
size_t gCacheCap = 256u << 20;
CRITICAL_SECTION gCs;          // 열쇠·1배 복사·캐시·상태
std::wstring gDir;             // 게임\hiart

// ---------------------------------------------------------------- 기록
CRITICAL_SECTION gLogCs;
void hlog(const char* fmt, ...) {
    if (!gLog) return;
    char buf[600];
    va_list ap; va_start(ap, fmt); int n = _vsnprintf_s(buf, sizeof(buf) - 3, _TRUNCATE, fmt, ap); va_end(ap);
    if (n < 0) n = (int)strlen(buf);
    char line[700]; int m = sprintf_s(line, "%llu %s\r\n", GetTickCount64(), buf);
    EnterCriticalSection(&gLogCs);
    HANDLE f = CreateFileW((Root() + L"\\hiart.log").c_str(), FILE_APPEND_DATA, FILE_SHARE_READ, nullptr, OPEN_ALWAYS, 0, nullptr);
    if (f != INVALID_HANDLE_VALUE) { DWORD w; WriteFile(f, line, m, &w, nullptr); CloseHandle(f); }
    LeaveCriticalSection(&gLogCs);
}

// ---------------------------------------------------------------- 색인(hiart\index.tsv)
struct Entry { std::wstring file; int w = 0, h = 0; bool alpha = false; uint32_t sum = 0; };
std::unordered_map<std::string, Entry> gIndex;

bool loadIndex() {
    HANDLE f = CreateFileW((gDir + L"\\index.tsv").c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING, 0, nullptr);
    if (f == INVALID_HANDLE_VALUE) return false;
    DWORD size = GetFileSize(f, nullptr);
    std::string s(size, '\0'); DWORD got = 0; ReadFile(f, &s[0], size, &got, nullptr); CloseHandle(f);
    size_t p = 0;
    while (p < s.size()) {
        size_t e = s.find('\n', p); if (e == std::string::npos) e = s.size();
        std::string line = s.substr(p, e - p); p = e + 1;
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty() || line[0] == '#') continue;
        char key[64], file[128]; int w, h, a; unsigned sum;
        if (sscanf_s(line.c_str(), "%63s %127s %d %d %d %x", key, (unsigned)sizeof(key), file, (unsigned)sizeof(file), &w, &h, &a, &sum) != 6) continue;
        Entry en; en.w = w; en.h = h; en.alpha = a != 0; en.sum = sum;
        for (char* c = file; *c; ++c) en.file += (wchar_t)(*c == '/' ? '\\' : *c);
        gIndex[key] = en;
    }
    return !gIndex.empty();
}

// ".\grpo_bu\0062" → "grpo_bu/0062"(그림 묶음만, 색인에 있을 때)
std::string keyOf(const char* path) {
    if (!path) return {};
    const char* s = path;
    if (s[0] == '.' && (s[1] == '\\' || s[1] == '/')) s += 2;
    std::string k;
    for (; *s; ++s) k += (*s == '\\') ? '/' : (char)tolower((unsigned char)*s);
    size_t sl = k.find('/');
    if (sl == std::string::npos) return {};
    std::string folder = k.substr(0, sl);
    if (folder != "grpe" && folder != "grpo_bg" && folder != "grpo_bu" && folder != "grpo_f" && folder != "grpo_ci") return {};
    return gIndex.count(k) ? k : std::string();
}

// ---------------------------------------------------------------- 1배 복사(엔진 화소 그대로)
struct Img1 { int w = 0, h = 0; std::vector<uint32_t> px; bool ok = false; DWORD used = 0; };
std::unordered_map<std::string, Img1> gImg1;
std::string gLayerKey[kLayers];          // 층마다 지금 열쇠(색인 밖이면 빈 칸)

uint32_t opaqueSum(const uint32_t* p, size_t n) {
    uint32_t h = 2166136261u;
    for (size_t i = 0; i < n; ++i) if ((p[i] >> 24) == 0) h = (h ^ (p[i] & 0xffffffu)) * 16777619u;
    return h;
}
bool safeCopy(void* dst, const void* src, size_t n) {
    __try { memcpy(dst, src, n); return true; } __except (EXCEPTION_EXECUTE_HANDLER) { return false; }
}
template <class T> bool rd(const void* p, T& v) { return safeCopy(&v, p, sizeof(T)); }
uint8_t* vbase(uint8_t* obj, int vbptrAt) {   // 가상 바탕 = obj + vbptrAt + [[obj+vbptrAt]+4]
    uint8_t* vb = nullptr; int off = 0;
    if (!rd(obj + vbptrAt, vb) || !vb || !rd(vb + 4, off)) return nullptr;
    return obj + vbptrAt + off;
}

// ---------------------------------------------------------------- 4배 캐시(창 배율 크기로 줄인 PBGRA)
using Buf = std::shared_ptr<std::vector<uint32_t>>;   // 뒤 스레드 합성이 쓰는 동안 캐시에서 빠져도 살아 있게
struct Pre { int cw = 0, pw = 0, ph = 0; Buf px; DWORD used = 0; };
std::unordered_map<std::string, Pre> gPre;
size_t gPreBytes = 0;
std::deque<std::pair<std::string, int>> gQueue;   // (열쇠, 맞출 cw)
std::set<std::string> gQueued;
HANDLE gWake = nullptr;
volatile LONG gRecheckAt = 0;   // 이 시각(GetTickCount)에 그림 전체를 다시 찍어 달라(뒤 스레드가 처리, 0 = 없음)
bool buildOne();                // 아래: 상태 합성(뒤 스레드)
std::set<std::string> gBad;                        // 4배를 쓰지 않을 열쇠(지문 다름·읽기 실패)

int preSize(int n1, int cw) { return (int)std::lround((double)n1 * cw / W1); }

void request(const std::string& key, int cw) {   // gCs 안
    if (key.empty() || gBad.count(key) || cw <= W1) return;
    auto it = gPre.find(key);
    if (it != gPre.end() && it->second.cw == cw) return;
    std::string q = key + "@" + std::to_string(cw);
    if (gQueued.count(q)) return;
    gQueued.insert(q); gQueue.push_back({key, cw});
    SetEvent(gWake);
}

bool decodeScaled(IWICImagingFactory* fac, const std::wstring& path, int pw, int ph, std::vector<uint32_t>& out) {
    IWICBitmapDecoder* dec = nullptr; IWICBitmapFrameDecode* fr = nullptr; IWICFormatConverter* cv = nullptr; IWICBitmapScaler* sc = nullptr;
    HRESULT hr = fac->CreateDecoderFromFilename(path.c_str(), nullptr, GENERIC_READ, WICDecodeMetadataCacheOnDemand, &dec);
    if (SUCCEEDED(hr)) hr = dec->GetFrame(0, &fr);
    if (SUCCEEDED(hr)) hr = fac->CreateFormatConverter(&cv);
    if (SUCCEEDED(hr)) hr = cv->Initialize(fr, GUID_WICPixelFormat32bppPBGRA, WICBitmapDitherTypeNone, nullptr, 0, WICBitmapPaletteTypeCustom);
    if (SUCCEEDED(hr)) hr = fac->CreateBitmapScaler(&sc);
    if (SUCCEEDED(hr)) {
        hr = sc->Initialize(cv, pw, ph, (WICBitmapInterpolationMode)4 /* HighQualityCubic */);
        if (FAILED(hr)) hr = sc->Initialize(cv, pw, ph, WICBitmapInterpolationModeFant);
    }
    if (SUCCEEDED(hr)) {
        try { out.assign((size_t)pw * ph, 0); } catch (...) { hr = E_OUTOFMEMORY; }
    }
    if (SUCCEEDED(hr)) hr = sc->CopyPixels(nullptr, pw * 4, (UINT)(out.size() * 4), (BYTE*)out.data());
    if (sc) sc->Release(); if (cv) cv->Release(); if (fr) fr->Release(); if (dec) dec->Release();
    return SUCCEEDED(hr);
}

std::set<std::string> gInUse;   // 지금·바로 앞 상태가 쓰는 열쇠(내쫓지 않는다)

void evict() {   // gCs 안
    while (gPreBytes > gCacheCap) {
        auto victim = gPre.end();
        for (auto it = gPre.begin(); it != gPre.end(); ++it)
            if (!gInUse.count(it->first) && (victim == gPre.end() || (int)(it->second.used - victim->second.used) < 0)) victim = it;
        if (victim == gPre.end()) break;
        gPreBytes -= victim->second.px ? victim->second.px->size() * 4 : 0;
        gPre.erase(victim);
    }
}

DWORD WINAPI loader(void*) {
    SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_BELOW_NORMAL);
    if (FAILED(CoInitializeEx(nullptr, COINIT_MULTITHREADED))) return 1;
    IWICImagingFactory* fac = nullptr;
    if (FAILED(CoCreateInstance(CLSID_WICImagingFactory, nullptr, CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&fac)))) { hlog("hiart: WIC unavailable"); return 2; }
    for (;;) {
        WaitForSingleObject(gWake, 60);
        LONG at = gRecheckAt;
        if (at && (LONG)(GetTickCount() - (DWORD)at) >= 0) {   // 화면이 그대로인지 보려고, 또는 색 변환을 맞춘 뒤 다시 찍기
            InterlockedCompareExchange(&gRecheckAt, 0, at);
            Present_InvalidateLogical(RECT{0, 0, W1, H1});
        }
        for (;;) {
            if (buildOne()) continue;
            std::pair<std::string, int> job; Entry en;
            EnterCriticalSection(&gCs);
            if (gQueue.empty()) { LeaveCriticalSection(&gCs); break; }
            job = gQueue.front(); gQueue.pop_front();
            gQueued.erase(job.first + "@" + std::to_string(job.second));
            auto it = gIndex.find(job.first);
            bool skip = it == gIndex.end() || gBad.count(job.first);
            auto pit = gPre.find(job.first);
            if (pit != gPre.end() && pit->second.cw == job.second) skip = true;
            if (!skip) en = it->second;
            LeaveCriticalSection(&gCs);
            if (skip) continue;
            if (CurrentLayout().cw != job.second) continue;   // 그새 창 크기가 바뀜
            int pw = preSize(en.w, job.second), ph = preSize(en.h, job.second);
            std::vector<uint32_t> px;
            DWORD t0 = GetTickCount();
            bool ok = decodeScaled(fac, gDir + L"\\" + en.file, pw, ph, px);
            hlog("hiart: load %s %dx%d %s %lums", job.first.c_str(), pw, ph, ok ? "ok" : "FAILED", GetTickCount() - t0);
            EnterCriticalSection(&gCs);
            if (!ok) gBad.insert(job.first);
            else {
                auto& p = gPre[job.first];
                gPreBytes -= p.px ? p.px->size() * 4 : 0;
                p.cw = job.second; p.pw = pw; p.ph = ph; p.px = std::make_shared<std::vector<uint32_t>>(std::move(px)); p.used = GetTickCount();
                gPreBytes += p.px->size() * 4;
                evict();
            }
            bool visible = gInUse.count(job.first) != 0;
            LeaveCriticalSection(&gCs);
            if (ok && visible) Present_InvalidateLogical(RECT{0, 0, W1, H1});
        }
    }
}

// ---------------------------------------------------------------- 층 상태
// 색 변환(층마다): 채널 c' = clamp(((c·k + 128) >> 8) + b), k 는 1/256 단위. 엔진이 그림을 어둡게 그리는 장면(회상 등)이
// 있는데 그 세기가 장면마다 달라(0.5·0.69…) 엔진 칸으로는 못 읽는다 → 안정된 화면에서 원본 → 화면으로 맞춰 본다(fitXf).
struct Xf { int k[3] = {256, 256, 256}, b[3] = {0, 0, 0}; bool on = false; };
struct LS { int idx; std::string key; int x, y, w, h; Xf xf; const Img1* one; Buf pre; int pw = 0, ph = 0; };
struct State { std::vector<LS> ls; std::string sig; };
State gCur, gPrev;          // 지금 상태, 바로 앞(다른) 상태
std::vector<RECT> gRects;   // 4배 그림이 차지하는 자리(마지막 찍기 기준)

int __fastcall hookLoad(uint8_t* self, void*, const char* path, int arg) {
    void* img = *(void**)(self + 0x50);
    typedef int(__fastcall * F)(void*, void*, const char*, int);
    F f = (F)(*(void***)img)[0x60 / 4];
    int r = f(img, nullptr, path, arg);
    int li = -1;
    for (int i = 0; i < kLayers; ++i) if (*(void**)(kLayerTable + i * 4) == self) { li = i; break; }
    if (li < 0) return r;
    std::string key = keyOf(path);
    // 1배 화소 복사(엔진 표현 그대로) — 같은 열쇠는 한 번만
    std::vector<uint32_t> copy; int w = 0, h = 0; bool fresh = false;
    if (!key.empty()) {
        EnterCriticalSection(&gCs);
        auto it = gImg1.find(key);
        fresh = it == gImg1.end();
        LeaveCriticalSection(&gCs);
        uint8_t* si = vbase((uint8_t*)img, 4);
        uint32_t* bits = nullptr;
        if (fresh && si && rd(si + 4, bits) && rd(si + 0x14, w) && rd(si + 0x18, h) && bits && w > 0 && h > 0 && w <= 4096 && h <= 4096) {
            copy.resize((size_t)w * h);
            if (!safeCopy(copy.data(), bits, copy.size() * 4)) copy.clear();
        }
    }
    EnterCriticalSection(&gCs);
    gLayerKey[li] = key;
    if (!key.empty() && fresh && !copy.empty()) {
        Img1& im = gImg1[key];
        im.w = w; im.h = h; im.px.swap(copy); im.used = GetTickCount();
        const Entry& en = gIndex[key];
        uint32_t s = opaqueSum(im.px.data(), im.px.size());
        im.ok = en.w == w && en.h == h && s == en.sum;
        if (!im.ok) { gBad.insert(key); hlog("hiart: %s differs from index (%dx%d sum %08x, index %dx%d %08x) — 1x kept", key.c_str(), w, h, s, en.w, en.h, en.sum); }
        // 오래된 복사본 정리(최대 40장)
        if (gImg1.size() > 40) {
            auto old = gImg1.end();
            for (auto i2 = gImg1.begin(); i2 != gImg1.end(); ++i2)
                if (!gInUse.count(i2->first) && i2->first != key && (old == gImg1.end() || (int)(i2->second.used - old->second.used) < 0)) old = i2;
            if (old != gImg1.end()) gImg1.erase(old);
        }
    }
    Layout L = CurrentLayout();
    if (!key.empty() && L.cw > W1) request(key, L.cw);
    LeaveCriticalSection(&gCs);
    return r;
}

// 층 표를 읽어 그림 층만 고른다(gCs 안에서 부른다; 엔진 메모리는 SEH 로 읽음)
void snapshot(State& st, const Layout& L) {
    st.ls.clear(); st.sig.clear();
    for (int i = 0; i < kLayers; ++i) {
        const std::string& key = gLayerKey[i];
        if (key.empty()) continue;
        uint8_t* Lp = nullptr; if (!rd((void*)(kLayerTable + i * 4), Lp) || !Lp) continue;
        uint8_t* S = vbase(Lp, 0); if (!S) continue;
        int vis = 0, sx = 0, sy = 0, eff = 0;
        if (!rd(S + 0xc, vis) || !vis || !rd(S + 0x1c, sx) || !rd(S + 0x20, sy) || !rd(S + 0x30, eff)) continue;
        uint8_t* I = nullptr; if (!rd(Lp + 0x50, I) || !I) continue;
        uint8_t* SI = vbase(I, 4); if (!SI) continue;
        int ivis = 0, w = 0, h = 0, blend = 0; RECT lr{};
        if (!rd(SI + 0xc, ivis) || !ivis || !rd(SI + 0x14, w) || !rd(SI + 0x18, h) || !rd(SI + 0x28, blend) || !rd(SI + 0x3c, lr)) continue;
        if (w <= 0 || h <= 0 || blend != 0 || (eff != 0 && eff != 6)) continue;   // 모르는 섞기 → 모형에서 빼면 그 자리는 1배로 남는다
        auto it = gImg1.find(key);
        if (it == gImg1.end() || !it->second.ok || it->second.w != w || it->second.h != h) continue;
        LS l; l.idx = i; l.key = key; l.x = sx + lr.left; l.y = sy + lr.top; l.w = w; l.h = h;
        l.one = &it->second; it->second.used = GetTickCount();
        auto pit = gPre.find(key);
        if (pit != gPre.end() && pit->second.cw == L.cw) { l.pre = pit->second.px; l.pw = pit->second.pw; l.ph = pit->second.ph; pit->second.used = GetTickCount(); }
        st.ls.push_back(l);
        char b[96]; sprintf_s(b, "%d:%s@%d,%d;", i, key.c_str(), l.x, l.y);
        st.sig += b;
    }
}

inline uint32_t applyXf(const Xf& f, uint32_t c) {   // 곧은 색(BGR)
    uint32_t o = 0;
    for (int ch = 0; ch < 3; ++ch) {
        int v = (int)((c >> (8 * ch)) & 255);
        v = ((v * f.k[ch] + 128) >> 8) + f.b[ch];
        o |= (uint32_t)(v < 0 ? 0 : v > 255 ? 255 : v) << (8 * ch);
    }
    return o;
}
inline uint32_t applyXfPm(const Xf& f, uint32_t p) {  // 미리 곱한 색(BGRA): b 는 알파만큼
    int a = (int)(p >> 24);
    uint32_t o = p & 0xff000000;
    for (int ch = 0; ch < 3; ++ch) {
        int v = (int)((p >> (8 * ch)) & 255);
        v = ((v * f.k[ch] + 128) >> 8) + (f.b[ch] * a + 127) / 255;
        o |= (uint32_t)(v < 0 ? 0 : v > a ? a : v) << (8 * ch);
    }
    return o;
}
std::unordered_map<std::string, std::vector<std::pair<int, Xf>>> gXform;   // 기본 상태 서명 → 층별 변환
std::string gFitBase; DWORD gFitTime = 0;
std::vector<std::pair<int, Xf>> gFitCand;
std::unordered_map<std::string, DWORD> gFitFail;

uint32_t sampleHash(const uint32_t* F) {
    uint32_t h = 2166136261u;
    for (int y = 3; y < 600; y += 7) for (int x = 5; x < 800; x += 11) h = (h ^ (F[(size_t)y * 800 + x] & 0xffffff)) * 16777619u;
    return h;
}

// ---------------------------------------------------------------- 1배 모형
// 사각형 [x0,x1)×[y0,y1) 의 모형을 out(가로 x1-x0)에 만든다. 그림이 하나도 안 덮은 곳 = 검정.
void model1(const State& st, int x0, int y0, int x1, int y1, uint32_t* out) {
    int n = x1 - x0;
    for (int y = y0; y < y1; ++y) memset(out + (size_t)(y - y0) * n, 0, (size_t)n * 4);
    for (const LS& l : st.ls) {
        int ax = std::max(x0, l.x), bx = std::min(x1, l.x + l.w), ay = std::max(y0, l.y), by = std::min(y1, l.y + l.h);
        if (ax >= bx || ay >= by) continue;
        for (int y = ay; y < by; ++y) {
            const uint32_t* s = l.one->px.data() + (size_t)(y - l.y) * l.w + (ax - l.x);
            uint32_t* d = out + (size_t)(y - y0) * n + (ax - x0);
            for (int x = ax; x < bx; ++x, ++s, ++d) {
                uint32_t p = *s, A = p >> 24;
                if (A == 255) continue;
                uint32_t c = p & 0xffffff;
                if (l.xf.on) c = applyXf(l.xf, c);
                if (A == 0) { *d = c; continue; }
                uint32_t a = 255 - A, q = *d;
                uint32_t rb = ((c & 0xff00ff) * a + (q & 0xff00ff) * A);
                uint32_t g = ((c & 0xff00) * a + (q & 0xff00) * A);
                // /255 를 채널마다
                uint32_t r0 = ((rb >> 16) & 0xffff) / 255, b0 = (rb & 0xffff) / 255, g0 = (g >> 8) / 255;
                *d = (r0 << 16) | (g0 << 8) | b0;
            }
        }
    }
}
inline int dmaxRaw(uint32_t a, uint32_t b) {
    int d0 = abs((int)(a & 255) - (int)(b & 255)), d1 = abs((int)((a >> 8) & 255) - (int)((b >> 8) & 255)), d2 = abs((int)((a >> 16) & 255) - (int)((b >> 16) & 255));
    return std::max(d0, std::max(d1, d2));
}
// 안정된 화면 F 에서 층마다 「위에 다른 그림이 없고 자신이 불투명한」 화소로 원본 → 화면 색 변환을 맞춘다.
// 층마다 표본 3000개 이상, 97% 이상이 오차 안이면 받아들인다. 바뀐 것이 하나라도 있으면 true.
bool fitXf(const State& st, const uint32_t* F, int tol, std::vector<std::pair<int, Xf>>& out) {
    // 표본: 층 j 가 맨 위이고 불투명한 화소(격자 2). 선택지·글자 같은 덮개는 직선 관계를 안 따르므로
    // 1차 맞춤 → 잔차 12 넘는 표본 빼고 2차 맞춤 → 남은 표본의 95% 가 오차 안이고 남은 비율이 50% 이상이면 받아들인다.
    struct Smp { uint32_t s, f; int j; };
    std::vector<Smp> smp; smp.reserve(130000);
    for (int y = 1; y < H1; y += 2) for (int x = 1; x < W1; x += 2) {
        for (int j = (int)st.ls.size() - 1; j >= 0; --j) {
            const LS& l = st.ls[j];
            if (x < l.x || y < l.y || x >= l.x + l.w || y >= l.y + l.h) continue;
            uint32_t p = l.one->px[(size_t)(y - l.y) * l.w + (x - l.x)];
            if ((p >> 24) == 255) continue;
            if ((p >> 24) == 0) smp.push_back({p & 0xffffff, F[(size_t)y * W1 + x] & 0xffffff, j});
            break;
        }
    }
    out.clear();
    bool any = false;
    for (size_t j = 0; j < st.ls.size(); ++j) {
        Xf f; f.on = true;
        std::vector<uint8_t> use;
        int nAll = 0;
        for (auto& s : smp) if (s.j == (int)j) ++nAll;
        if (nAll < 3000) continue;
        for (int round = 0; round < 2; ++round) {
            double n = 0, sx[3] = {}, sy[3] = {}, sxx[3] = {}, sxy[3] = {};
            for (auto& s : smp) {
                if (s.j != (int)j) continue;
                if (round == 1 && dmaxRaw(applyXf(f, s.s), s.f) > 12) continue;
                n += 1;
                for (int c = 0; c < 3; ++c) { double a = (s.s >> (8 * c)) & 255, b = (s.f >> (8 * c)) & 255; sx[c] += a; sy[c] += b; sxx[c] += a * a; sxy[c] += a * b; }
            }
            if (n < 1500) { f.on = false; break; }
            for (int c = 0; c < 3; ++c) {
                double den = n * sxx[c] - sx[c] * sx[c];
                double k = den > 1e-6 ? (n * sxy[c] - sx[c] * sy[c]) / den : 1.0;
                double b = (sy[c] - k * sx[c]) / n;
                f.k[c] = (int)std::lround(k * 256); f.b[c] = (int)std::lround(b);
            }
        }
        if (!f.on) continue;
        int inl = 0, good = 0;
        for (auto& s : smp) {
            if (s.j != (int)j) continue;
            int d = dmaxRaw(applyXf(f, s.s), s.f);
            if (d <= 12) { ++inl; if (d <= tol + 1) ++good; }
        }
        bool ok = inl * 2 >= nAll && good * 100 >= inl * 95;
        bool ident = true, dark = true;
        for (int c = 0; c < 3; ++c) { if (abs(f.k[c] - 256) > 2 || abs(f.b[c]) > 1) ident = false; if (f.k[c] > 38) dark = false; }
        hlog("hiart: fit layer %d %s k %d,%d,%d b %d,%d,%d inliers %d/%d good %d %s", st.ls[j].idx, st.ls[j].key.c_str(), f.k[0], f.k[1], f.k[2], f.b[0], f.b[1], f.b[2], inl, nAll, good, ok ? (ident ? "identity" : "set") : "rejected");
        if (!ok || dark) continue;
        if (ident) f.on = false;
        out.push_back({st.ls[j].idx, f});
        if (f.on) any = true;
    }
    return any;
}
bool sameXf(const std::vector<std::pair<int, Xf>>& a, const std::vector<std::pair<int, Xf>>& b) {
    if (a.size() != b.size()) return false;
    for (size_t i = 0; i < a.size(); ++i) {
        if (a[i].first != b[i].first || a[i].second.on != b[i].second.on) return false;
        for (int c = 0; c < 3; ++c) if (abs(a[i].second.k[c] - b[i].second.k[c]) > 3 || abs(a[i].second.b[c] - b[i].second.b[c]) > 2) return false;
    }
    return true;
}
inline int dmax(uint32_t a, uint32_t b) {
    int d0 = abs((int)(a & 255) - (int)(b & 255)), d1 = abs((int)((a >> 8) & 255) - (int)((b >> 8) & 255)), d2 = abs((int)((a >> 16) & 255) - (int)((b >> 16) & 255));
    return std::max(d0, std::max(d1, d2));
}

// ---------------------------------------------------------------- 4배 합성(물리 좌표 한 줄)
// 상태의 그림들을 물리 줄 Y 의 [X0,X1) 에 합성(PBGRA, 검정 바탕). 4배가 없는 그림이 그 자리를 덮으면 ok[x]=0.
void row4(const State& st, const Layout& L, int Y, int X0, int X1, uint32_t* out, uint8_t* ok) {
    int n = X1 - X0;
    memset(out, 0, (size_t)n * 4);
    memset(ok, 1, n);
    for (const LS& l : st.ls) {
        int px0 = L.ox + (int)std::lround((double)l.x * L.cw / W1), py0 = L.oy + (int)std::lround((double)l.y * L.ch / H1);
        if (!l.pre) {
            int pw = preSize(l.w, L.cw), ph = preSize(l.h, L.cw);
            if (Y < py0 || Y >= py0 + ph) continue;
            int a = std::max(X0, px0), b = std::min(X1, px0 + pw);
            if (a < b) memset(ok + (a - X0), 0, b - a);
            continue;
        }
        int ry = Y - py0;
        if (ry < 0 || ry >= l.ph) continue;
        int a = std::max(X0, px0), b = std::min(X1, px0 + l.pw);
        if (a >= b) continue;
        const uint32_t* s = l.pre->data() + (size_t)ry * l.pw + (a - px0);
        uint32_t* d = out + (a - X0);
        int m = b - a;
        const __m128i z = _mm_setzero_si128(), c255 = _mm_set1_epi16(255), half = _mm_set1_epi16(0x80), mask7f = _mm_set1_epi8(0x7f);
        int i = 0;
        const __m128i amask = _mm_set1_epi32((int)0xff000000);
        // 색 변환(미리 곱한 색): c' = clamp((c·k + 128)>>8 + (b·α)>>8, 0, α) — 채널별 k·b, 알파 칸은 k=256·b=0
        const __m128i kv = _mm_setr_epi16((short)l.xf.k[0], (short)l.xf.k[1], (short)l.xf.k[2], 256, (short)l.xf.k[0], (short)l.xf.k[1], (short)l.xf.k[2], 256);
        const __m128i bv = _mm_setr_epi16((short)std::max(-100, std::min(100, l.xf.b[0])), (short)std::max(-100, std::min(100, l.xf.b[1])), (short)std::max(-100, std::min(100, l.xf.b[2])), 0,
                                          (short)std::max(-100, std::min(100, l.xf.b[0])), (short)std::max(-100, std::min(100, l.xf.b[1])), (short)std::max(-100, std::min(100, l.xf.b[2])), 0);
        const bool sseOk = !l.xf.on || (l.xf.k[0] <= 256 && l.xf.k[1] <= 256 && l.xf.k[2] <= 256);   // 밝게 하는 변환은 16비트를 넘쳐 한 화소씩
        for (; sseOk && i + 4 <= m; i += 4) {
            __m128i sv = _mm_loadu_si128((const __m128i*)(s + i));
            __m128i av = _mm_and_si128(sv, amask);
            if (_mm_movemask_epi8(_mm_cmpeq_epi32(av, z)) == 0xffff) continue;            // 넷 다 완전 투명
            if (l.xf.on) {
                __m128i sl = _mm_unpacklo_epi8(sv, z), sh = _mm_unpackhi_epi8(sv, z);
                __m128i al = _mm_shufflehi_epi16(_mm_shufflelo_epi16(sl, 0xff), 0xff), ah = _mm_shufflehi_epi16(_mm_shufflelo_epi16(sh, 0xff), 0xff);
                sl = _mm_add_epi16(_mm_srli_epi16(_mm_add_epi16(_mm_mullo_epi16(sl, kv), half), 8), _mm_srai_epi16(_mm_mullo_epi16(bv, al), 8));
                sh = _mm_add_epi16(_mm_srli_epi16(_mm_add_epi16(_mm_mullo_epi16(sh, kv), half), 8), _mm_srai_epi16(_mm_mullo_epi16(bv, ah), 8));
                sl = _mm_min_epi16(_mm_max_epi16(sl, z), al); sh = _mm_min_epi16(_mm_max_epi16(sh, z), ah);
                sv = _mm_packus_epi16(sl, sh);
            }
            if (_mm_movemask_epi8(_mm_cmpeq_epi32(av, amask)) == 0xffff) { _mm_storeu_si128((__m128i*)(d + i), sv); continue; }   // 넷 다 불투명
            __m128i dv = _mm_loadu_si128((const __m128i*)(d + i));
            // d = s + d·(255−αs)/255 (미리 곱한 섞기)
            __m128i sl = _mm_unpacklo_epi8(sv, z), sh = _mm_unpackhi_epi8(sv, z);
            __m128i al = _mm_shufflehi_epi16(_mm_shufflelo_epi16(sl, 0xff), 0xff), ah = _mm_shufflehi_epi16(_mm_shufflelo_epi16(sh, 0xff), 0xff);
            __m128i il = _mm_sub_epi16(c255, al), ih = _mm_sub_epi16(c255, ah);
            __m128i dl = _mm_mullo_epi16(_mm_unpacklo_epi8(dv, z), il), dh = _mm_mullo_epi16(_mm_unpackhi_epi8(dv, z), ih);
            dl = _mm_add_epi16(dl, half); dh = _mm_add_epi16(dh, half);
            dl = _mm_srli_epi16(_mm_add_epi16(dl, _mm_srli_epi16(dl, 8)), 8); dh = _mm_srli_epi16(_mm_add_epi16(dh, _mm_srli_epi16(dh, 8)), 8);
            __m128i r = _mm_adds_epu8(sv, _mm_packus_epi16(dl, dh));
            _mm_storeu_si128((__m128i*)(d + i), r);
            (void)mask7f;
        }
        for (; i < m; ++i) {
            uint32_t sp = s[i];
            if (l.xf.on) sp = applyXfPm(l.xf, sp);
            uint32_t ia = 255 - (sp >> 24), dp = d[i], o = 0;
            for (int k = 0; k < 32; k += 8) {
                uint32_t v = ((dp >> k) & 255) * ia + 128; v = (v + (v >> 8)) >> 8;
                uint32_t sum = ((sp >> k) & 255) + v; if (sum > 255) sum = 255;
                o |= sum << k;
            }
            d[i] = o;
        }
    }
}

// ---------------------------------------------------------------- 시간 통계
struct Stat { int n = 0; double sum = 0, max = 0; } gT;
LARGE_INTEGER gFreq;
double nowMs() { LARGE_INTEGER c; QueryPerformanceCounter(&c); return c.QuadPart * 1000.0 / gFreq.QuadPart; }

std::vector<uint8_t> gCode;       // 1배 화소마다: 0 그대로, 1 지금, 2 앞, 3 섞기
std::vector<uint8_t> gErodeH;
std::vector<uint32_t> gRowC, gRowP; std::vector<uint8_t> gOkC, gOkP;
int gLastCw = 0;

// 상태마다 한 번만: 800×600 1배 모형(두 칸 돌려 씀)
struct M1 { std::string sig; std::vector<uint32_t> m; DWORD used = 0; } gM1[2];
const uint32_t* modelOf(const State& st) {
    for (auto& c : gM1) if (!c.sig.empty() && c.sig == st.sig) { c.used = GetTickCount(); return c.m.data(); }
    M1& c = (gM1[0].sig.empty() || (gM1[1].sig.size() && (int)(gM1[0].used - gM1[1].used) < 0)) ? gM1[0] : gM1[1];
    try { c.m.resize((size_t)W1 * H1); } catch (...) { c.sig.clear(); return nullptr; }
    model1(st, 0, 0, W1, H1, c.m.data());
    c.sig = st.sig; c.used = GetTickCount();
    return c.m.data();
}
// 상태마다 한 번만: 물리 크기 4배 합성. 엔진 스레드를 세우지 않게 뒤 스레드가 만든다(그동안 넓은 찍기는 1배).
struct C4 { std::string sig; int cw = 0, ch = 0; Buf px; DWORD used = 0; } gC4[2];
struct BuildJob { bool want = false; State st; Layout L; } gJob;
bool gDirect = false;   // 이번 찍기가 작아 그 자리에서 합성해도 되는가
bool allReady(const State& st) { for (auto& l : st.ls) if (!l.pre) return false; return !st.ls.empty(); }
C4* compOf(const State& st, const Layout& L, bool weak = false) {   // gCs 안. weak = 일감이 비었을 때만 맡김(앞 상태)
    if (!allReady(st)) return nullptr;
    for (auto& c : gC4) if (c.px && c.sig == st.sig && c.cw == L.cw && c.ch == L.ch) { c.used = GetTickCount(); return &c; }
    if (!(gJob.want && gJob.st.sig == st.sig && gJob.L.cw == L.cw && gJob.L.ch == L.ch) && !(weak && gJob.want)) {
        gJob.want = true; gJob.st = st; gJob.L = L;
        SetEvent(gWake);
    }
    return nullptr;
}
// 뒤 스레드: 맡은 상태를 통째로 합성해 캐시 칸(오래 안 쓴 쪽)에 넣는다. true = 하나 만들었다.
bool buildOne() {
    EnterCriticalSection(&gCs);
    if (!gJob.want) { LeaveCriticalSection(&gCs); return false; }
    BuildJob job = gJob; gJob.want = false;
    LeaveCriticalSection(&gCs);
    const Layout& L = job.L;
    if (CurrentLayout().cw != L.cw) return true;
    Buf px;
    try { px = std::make_shared<std::vector<uint32_t>>((size_t)L.cw * L.ch); } catch (...) { hlog("hiart: composite allocation failed %dx%d", L.cw, L.ch); return true; }
    std::vector<uint8_t> ok(L.cw);
    DWORD t0 = GetTickCount();
    for (int y = 0; y < L.ch; ++y) row4(job.st, L, L.oy + y, L.ox, L.ox + L.cw, px->data() + (size_t)y * L.cw, ok.data());
    EnterCriticalSection(&gCs);
    C4& c = (!gC4[0].px || (gC4[1].px && (int)(gC4[0].used - gC4[1].used) < 0)) ? gC4[0] : gC4[1];
    c.sig = job.st.sig; c.cw = L.cw; c.ch = L.ch; c.px = px; c.used = GetTickCount();
    bool current = gCur.sig == job.st.sig || gPrev.sig == job.st.sig;
    LeaveCriticalSection(&gCs);
    hlog("hiart: composite %dx%d built in %lums", L.cw, L.ch, GetTickCount() - t0);
    if (current) InterlockedExchange(&gRecheckAt, (LONG)(GetTickCount() + 1));
    return true;
}
// 물리 줄 Y(창 좌표)의 그림 안 [X0,X1) 합성을 돌려준다. ok 는 4배를 쓸 수 있는 화소.
const uint32_t* rowOf(const State& st, C4* c, const Layout& L, int Y, int X0, int X1, uint32_t* tmp, uint8_t* ok) {
    if (c) {
        memset(ok, 1, X1 - X0);
        return c->px->data() + (size_t)(Y - L.oy) * L.cw + (X0 - L.ox);
    }
    if (gDirect) { row4(st, L, Y, X0, X1, tmp, ok); return tmp; }
    memset(ok, 0, X1 - X0);
    return tmp;
}
}  // namespace

bool HiArt_Install() {
    if (!Cfg("hiart", 1)) return false;
    gLog = Cfg("hiart_log", 0) != 0;
    gDiag = gLog && Cfg("hiart_diag", 0) != 0;
    gTestFlag = Cfg("hiart_test_flag", 0) != 0;   // 시험 전용: hiart\off.flag 가 있으면 1배(같은 화면 켬/끔 비교)
    gTol = std::max(1, Cfg("hiart_tol", 3));
    gCacheCap = (size_t)std::max(64, Cfg("hiart_cache_mb", 256)) << 20;
    InitializeCriticalSection(&gCs); InitializeCriticalSection(&gLogCs);
    QueryPerformanceFrequency(&gFreq);
    gDir = Root() + L"\\hiart";
    if (!loadIndex()) { Log("hiart: no hiart\\index.tsv — off"); return false; }
    static const uint8_t loadBytes[] = {0x8b, 0x54, 0x24, 0x08, 0x8b, 0x49, 0x50, 0x52};
    if (memcmp((void*)kLoadFn, loadBytes, sizeof(loadBytes)) != 0) { Log("hiart: load function bytes differ — off"); return false; }
    uint8_t jmp[5] = {0xE9}; *(int32_t*)(jmp + 1) = (int32_t)((uintptr_t)&hookLoad - (kLoadFn + 5));
    if (!PatchBytes(kLoadFn, loadBytes, jmp, 5)) { Log("hiart: patch failed — off"); return false; }
    gWake = CreateEventW(nullptr, FALSE, FALSE, nullptr);
    HANDLE t = CreateThread(nullptr, 0, loader, nullptr, 0, nullptr);
    if (t) CloseHandle(t);
    gOn = true;
    Log("hiart: " + std::to_string(gIndex.size()) + " pictures indexed");
    return true;
}
void HiArt_WindowReady(HWND) {}

void HiArt_PaintBase(HDC dc, const Layout& L, const RECT& clip) {
    { static int calls = 0; if (gLog && calls++ < 3) hlog("hiart: paint call %d layout %dx%d clip %ld,%ld,%ld,%ld shadow %p", calls, L.cw, L.ch, clip.left, clip.top, clip.right, clip.bottom, Present_ShadowBits()); }
    if (!gOn || L.cw <= W1) return;
    if (gTestFlag && GetFileAttributesW((gDir + L"\\off.flag").c_str()) != INVALID_FILE_ATTRIBUTES) return;
    const uint32_t* F = Present_ShadowBits();
    if (!F) return;
    double t0 = nowMs();
    // 뒷판 화소
    DIBSECTION ds{};
    HGDIOBJ bmp = GetCurrentObject(dc, OBJ_BITMAP);
    // 화면 모듈의 뒷판은 위→아래 DIB(biHeight 음수로 만듦). GetObject 는 높이를 양수로 돌려줄 수 있어 부호는 보지 않는다.
    if (!bmp || GetObject(bmp, sizeof(ds), &ds) != sizeof(ds) || !ds.dsBm.bmBits || ds.dsBm.bmBitsPixel != 32) {
        static int warned = 0; if (warned++ < 3) hlog("hiart: back buffer is not a 32-bit DIB section");
        return;
    }
    uint32_t* bk = (uint32_t*)ds.dsBm.bmBits; int BW = ds.dsBm.bmWidth, BH = ds.dsBm.bmHeight;
    RECT P{std::max<LONG>(clip.left, L.ox), std::max<LONG>(clip.top, L.oy), std::min<LONG>(clip.right, std::min(L.ox + L.cw, BW)), std::min<LONG>(clip.bottom, std::min(L.oy + L.ch, BH))};
    if (P.right <= P.left || P.bottom <= P.top) return;

    EnterCriticalSection(&gCs);
    if (L.cw != gLastCw) {   // 창 크기가 바뀜: 맞는 크기로 다시
        gLastCw = L.cw;
        for (int i = 0; i < kLayers; ++i) if (!gLayerKey[i].empty()) request(gLayerKey[i], L.cw);
    }
    State st; snapshot(st, L);
    const std::string base = st.sig;
    {
        auto xit = gXform.find(base);
        if (xit != gXform.end()) {
            std::string tag = "|x";
            for (auto& pr : xit->second) {
                for (auto& l : st.ls) if (l.idx == pr.first) l.xf = pr.second;
                if (pr.second.on) { char b[80]; sprintf_s(b, "%d:%d,%d,%d/%d,%d,%d;", pr.first, pr.second.k[0], pr.second.k[1], pr.second.k[2], pr.second.b[0], pr.second.b[1], pr.second.b[2]); tag += b; }
            }
            st.sig += tag;
        }
    }
    if (st.sig != gCur.sig) {
        if (!gCur.sig.empty()) gPrev = gCur;
        gCur = st;
        hlog("hiart: state %s (prev %s)", gCur.sig.c_str(), gPrev.sig.c_str());
        if (gDiag) {   // 진단(hiart_diag=1): 보이는 층 모두(경로 없는 층 포함) — 느리다
            for (int i = 0; i < kLayers; ++i) {
                uint8_t* Lp = nullptr; if (!rd((void*)(kLayerTable + i * 4), Lp) || !Lp) continue;
                uint8_t* S = vbase(Lp, 0); if (!S) continue;
                int vis = 0, eff = 0, m28 = 0, m2c = 0; rd(S + 0xc, vis); rd(S + 0x30, eff); rd(S + 0x28, m28); rd(S + 0x2c, m2c);
                uint8_t* I = nullptr; rd(Lp + 0x50, I);
                uint8_t* SI = I ? vbase(I, 4) : nullptr;
                int ivis = 0, w = 0, h = 0, bl = 0, op = 0, b30 = 0; RECT lr{}; uint32_t* bits = nullptr; uint32_t px0 = 0, pxc = 0;
                if (SI) { rd(SI + 0xc, ivis); rd(SI + 0x14, w); rd(SI + 0x18, h); rd(SI + 0x28, bl); rd(SI + 0x2c, op); rd(SI + 0x30, b30); rd(SI + 0x3c, lr); rd(SI + 4, bits); }
                if (bits && w > 0 && h > 0) { rd(bits, px0); rd(bits + (size_t)(h / 2) * w + w / 2, pxc); }
                if (!vis && !ivis) continue;
                uint32_t* lb4 = nullptr; uint32_t* lb8 = nullptr; int lw = 0, lh = 0; uint32_t lc4 = 0, lc8 = 0;
                rd(S + 4, lb4); rd(S + 8, lb8); rd(S + 0x14, lw); rd(S + 0x18, lh);
                if (lw > 0 && lh > 0 && lw <= 4096 && lh <= 4096) {
                    if (lb4) rd(lb4 + (size_t)(lh / 2) * lw + lw / 2, lc4);
                    if (lb8) rd(lb8 + (size_t)(lh / 2) * lw + lw / 2, lc8);
                }
                hlog("  L%02d vis %d eff %d m28 %d m2c %d | img vis %d %dx%d blend %d op %d b30 %d rect %ld,%ld,%ld,%ld px0 %08x pxc %08x key '%s' | S+4 %p S+8 %p %dx%d c4 %08x c8 %08x",
                     i, vis, eff, m28, m2c, ivis, w, h, bl, op, b30, lr.left, lr.top, lr.right, lr.bottom, px0, pxc, gLayerKey[i].c_str(), lb4, lb8, lw, lh, lc4, lc8);
                // 자식 목록(그릇 = 층+0x250: [-0x24] 칸 배열(12바이트), [-0x20] 개수 u16, [-0x1c] z 순 색인)
                uint8_t* kids = nullptr; uint16_t nk = 0; uint16_t* zi = nullptr;
                rd(Lp + 0x30, kids); rd(Lp + 0x34, nk); rd(Lp + 0x38, zi);
                for (int k = 0; k < nk && k < 8 && kids; ++k) {
                    uint16_t z = 0; if (zi) rd(zi + k, z);
                    uint8_t* c = nullptr; rd(kids + z * 12, c);
                    if (!c) continue;
                    void* vt = nullptr; rd(c, vt);
                    int cv = 0, cw = 0, ch = 0, cb = 0, co = 0, c30 = 0; RECT cr{}; uint32_t* cbits = nullptr; uint32_t cpx = 0;
                    rd(c + 0xc, cv); rd(c + 0x14, cw); rd(c + 0x18, ch); rd(c + 0x28, cb); rd(c + 0x2c, co); rd(c + 0x30, c30); rd(c + 0x3c, cr); rd(c + 4, cbits);
                    if (cbits && cw > 0 && ch > 0 && cw <= 4096 && ch <= 4096) rd(cbits + (size_t)(ch / 2) * cw + cw / 2, cpx);
                    hlog("     child %d z %u obj %p vt %p vis %d %dx%d blend %d op %d b30 %d rect %ld,%ld,%ld,%ld pxc %08x (img SI %p)", k, z, c, vt, cv, cw, ch, cb, co, c30, cr.left, cr.top, cr.right, cr.bottom, cpx, SI);
                }
            }
        }
    } else gCur = st;   // 4배 준비 상태·포인터 새로
    // 앞 상태의 포인터도 새로(캐시가 바뀌었을 수 있다)
    if (!gPrev.sig.empty()) {
        for (LS& l : gPrev.ls) {
            auto it = gImg1.find(l.key); l.one = (it != gImg1.end() && it->second.ok) ? &it->second : nullptr;
            auto pit = gPre.find(l.key);
            if (pit != gPre.end() && pit->second.cw == L.cw) { l.pre = pit->second.px; l.pw = pit->second.pw; l.ph = pit->second.ph; } else l.pre.reset();
        }
        gPrev.ls.erase(std::remove_if(gPrev.ls.begin(), gPrev.ls.end(), [](const LS& l) { return !l.one; }), gPrev.ls.end());
    }
    gInUse.clear();
    for (auto& l : gCur.ls) { gInUse.insert(l.key); if (!l.pre) request(l.key, L.cw); }
    for (auto& l : gPrev.ls) gInUse.insert(l.key);
    gRects.clear();
    for (auto& l : gCur.ls) gRects.push_back(RECT{l.x, l.y, l.x + l.w, l.y + l.h});
    if (gCur.ls.empty()) { LeaveCriticalSection(&gCs); return; }

    // 1배 범위(물리 사각형이 기대는 화소 + 1)
    int x0 = std::max(0, (int)std::floor((P.left - L.ox) * (double)W1 / L.cw) - 1), x1 = std::min(W1, (int)std::ceil((P.right - L.ox) * (double)W1 / L.cw) + 1);
    int y0 = std::max(0, (int)std::floor((P.top - L.oy) * (double)H1 / L.ch) - 1), y1 = std::min(H1, (int)std::ceil((P.bottom - L.oy) * (double)H1 / L.ch) + 1);
    int n = x1 - x0, m = y1 - y0;
    gCode.assign((size_t)n * m, 0);
    double tA = nowMs();
    const uint32_t* Mc = modelOf(gCur);
    double tB = nowMs();
    if (!Mc) { LeaveCriticalSection(&gCs); return; }
    bool havePrev = !gPrev.ls.empty();
    int miss = 0;
    for (int y = 0; y < m; ++y) {
        const uint32_t* f = F + (size_t)(y0 + y) * W1 + x0;
        const uint32_t* mc = Mc + (size_t)(y0 + y) * W1 + x0;
        uint8_t* cd = gCode.data() + (size_t)y * n;
        for (int x = 0; x < n; ++x) {
            if (dmax(f[x] & 0xffffff, mc[x]) <= gTol) cd[x] = 1; else ++miss;
        }
    }
    double tC = nowMs();
    double tBlend = -1;
    const uint32_t* Mp = nullptr;
    if (miss && havePrev) Mp = modelOf(gPrev);
    if (miss && Mp) {
        // 전환(옛 화면 → 새 합성, 화면 전체 같은 t) 인가: 지금·앞 모형이 크게 다른 화소에서 t 를 잰다
        int64_t num = 0, den = 0; int cnt = 0;
        for (int y = 0; y < m; ++y) {
            const uint32_t* f = F + (size_t)(y0 + y) * W1 + x0;
            const uint32_t* mc = Mc + (size_t)(y0 + y) * W1 + x0;
            const uint32_t* mp = Mp + (size_t)(y0 + y) * W1 + x0;
            uint8_t* cd = gCode.data() + (size_t)y * n;
            for (int x = 0; x < n; ++x) {
                if (cd[x]) continue;
                uint32_t fp = f[x] & 0xffffff;
                if (dmax(fp, mp[x]) <= gTol) { cd[x] = 2; continue; }
                if ((x | y) & 1) continue;   // t 쌓기는 2×2 에 하나
                uint32_t c = mc[x], p = mp[x];
                if (dmax(c, p) < 24) continue;
                ++cnt;
                for (int k = 0; k < 24; k += 8) {
                    int dv = (int)((c >> k) & 255) - (int)((p >> k) & 255);
                    num += (int64_t)((int)((fp >> k) & 255) - (int)((p >> k) & 255)) * dv; den += (int64_t)dv * dv;
                }
            }
        }
        if (cnt >= 250 && den > 0) {
            double t = (double)num / den;
            if (t > 0.02 && t < 0.98) {
                int t256 = (int)std::lround(t * 256), good = 0, tried = 0;
                int tolb = gTol + 2;
                for (int pass = 0; pass < 2; ++pass) {   // 0: 셈만, 1: 표시(90% 이상 맞을 때)
                    if (pass == 1 && good < tried * 9 / 10) break;
                    for (int y = 0; y < m; y += (pass == 0 && m > 64) ? 2 : 1) {   // 셈은 한 줄 걸러
                        const uint32_t* f = F + (size_t)(y0 + y) * W1 + x0;
                        const uint32_t* mc = Mc + (size_t)(y0 + y) * W1 + x0;
                        const uint32_t* mp = Mp + (size_t)(y0 + y) * W1 + x0;
                        uint8_t* cd = gCode.data() + (size_t)y * n;
                        for (int x = 0; x < n; ++x) {
                            if (cd[x]) continue;
                            uint32_t c = mc[x], p = mp[x], fp = f[x] & 0xffffff; int bad = 0;
                            for (int k = 0; k < 24 && !bad; k += 8) {
                                int pv = (p >> k) & 255, e = pv + ((((int)((c >> k) & 255) - pv) * t256) >> 8);
                                if (abs(e - (int)((fp >> k) & 255)) > tolb) bad = 1;
                            }
                            if (pass == 0) { if (dmax(c, p) >= 24) { ++tried; good += !bad; } }
                            else if (!bad) cd[x] = 3;
                        }
                    }
                }
                if (good >= tried * 9 / 10) tBlend = t;
            }
        }
    }
    double tD = nowMs();
    // 크게 안 맞고 전환도 아니면: 화면이 200ms 넘게 그대로일 때 층 색 변환(어둡게 그린 장면)을 맞춰 본다.
    // 한 번 맞추고, 200ms 넘게 지난 다음 찍기에서 다시 맞춰 같은 변환이 나오면(=화면이 안정) 받아들인다.
    if (tBlend < 0 && (int64_t)n * m >= (int64_t)W1 * H1 / 2 && miss > n * m / 5) {
        DWORD now = GetTickCount();
        auto ff = gFitFail.find(base);
        bool cooling = ff != gFitFail.end() && now - ff->second < 2000;
        if (!cooling && (gFitBase != base || now - gFitTime >= 200)) {
            State raw = gCur; for (auto& l : raw.ls) l.xf = Xf();
            std::vector<std::pair<int, Xf>> xf;
            bool any = fitXf(raw, F, gTol, xf);
            if (!any) { gFitFail[base] = now; gFitBase.clear(); }
            else if (gFitBase == base && sameXf(xf, gFitCand)) {
                gXform[base] = xf; gFitBase.clear();
                InterlockedExchange(&gRecheckAt, (LONG)(now + 1));
                hlog("hiart: transform set for %s", base.c_str());
            } else {
                gFitBase = base; gFitCand = xf; gFitTime = now;
                InterlockedExchange(&gRecheckAt, (LONG)(now + 260));
            }
        }
    }
    double tE = nowMs();
    // 외딴 맞음 없애기: UI·글자 화소가 우연히 그림 모형과 오차 안에서 맞는 일이 있다(설정 화면에서 600여 화소).
    // 진짜 그림 자리는 넓게 이어지므로, 3×3 이웃이 모두 맞은(판정 ≠ 0) 화소만 남긴다. 구역 밖 이웃은 맞은 것으로 본다.
    {
        std::vector<uint8_t>& h = gErodeH; h.assign((size_t)n * m, 0);
        for (int y = 0; y < m; ++y) {
            const uint8_t* cd = gCode.data() + (size_t)y * n; uint8_t* hr = h.data() + (size_t)y * n;
            for (int x = 0; x < n; ++x) hr[x] = (cd[x] != 0) & (x == 0 || cd[x - 1] != 0) & (x == n - 1 || cd[x + 1] != 0);
        }
        for (int y = 0; y < m; ++y) {
            uint8_t* cd = gCode.data() + (size_t)y * n;
            const uint8_t* hu = h.data() + (size_t)std::max(0, y - 1) * n, *hc = h.data() + (size_t)y * n, *hd = h.data() + (size_t)std::min(m - 1, y + 1) * n;
            for (int x = 0; x < n; ++x) if (!(hu[x] & hc[x] & hd[x])) cd[x] = 0;
        }
    }
    double tF = nowMs();
    // 4배 합성: 물리 화소마다 가장 가까운 1배 화소의 판정을 따른다. 합성 줄은 상태마다 한 번 만들어 둔다.
    // 1배 열마다 물리 구간 [sx[x], sx[x+1]) — 같은 판정이 이어지면 통째로 복사.
    int PW = P.right - P.left;
    gRowC.resize(PW); gRowP.resize(PW); gOkC.resize(PW); gOkP.resize(PW);
    int it256 = tBlend < 0 ? 0 : (int)std::lround(tBlend * 256);
    std::vector<int> sx(n + 1, PW);
    {
        int X = P.left;
        for (int x = 0; x < n; ++x) {
            sx[x] = X - P.left;
            while (X < P.right && (int)std::floor((X - L.ox + 0.5) * W1 / (double)L.cw) - x0 <= x) ++X;
        }
        sx[0] = 0; sx[n] = PW;
    }
    gDirect = (int64_t)(P.right - P.left) * (P.bottom - P.top) <= (int64_t)L.cw * L.ch / 4;   // 작은 찍기(글자·아이콘)는 그 자리에서
    C4* cc = compOf(gCur, L);
    C4* cp = havePrev ? compOf(gPrev, L, true) : nullptr;
    if (cc && cp == cc) cp = nullptr;
    int drawn = 0;
    for (int Y = P.top; Y < P.bottom; ++Y) {
        int v = (int)std::floor((Y - L.oy + 0.5) * H1 / (double)L.ch);
        int ry = std::min(m - 1, std::max(0, v - y0));
        const uint8_t* code = gCode.data() + (size_t)ry * n;
        bool needC = false, needP = false;
        for (int x = 0; x < n; ++x) { uint8_t c = code[x]; if (sx[x] == sx[x + 1]) continue; if (c == 1 || c == 3) needC = true; if (c == 2 || c == 3) needP = true; }
        if (!needC && !needP) continue;
        const uint32_t* rc = needC ? rowOf(gCur, cc, L, Y, P.left, P.right, gRowC.data(), gOkC.data()) : nullptr;
        const uint32_t* rp = needP ? rowOf(gPrev, cp, L, Y, P.left, P.right, gRowP.data(), gOkP.data()) : nullptr;
        uint32_t* d = bk + (size_t)Y * BW + P.left;
        for (int x = 0; x < n;) {
            uint8_t c = code[x];
            int xe = x + 1;
            while (xe < n && code[xe] == c) ++xe;
            int a = sx[x], b = sx[xe];
            x = xe;
            if (!c || a >= b) continue;
            if (c == 1 || c == 2) {
                const uint32_t* r = c == 1 ? rc : rp; const uint8_t* ok = c == 1 ? gOkC.data() : gOkP.data();
                if ((c == 1 && cc) || (c == 2 && cp)) { memcpy(d + a, r + a, (size_t)(b - a) * 4); drawn += b - a; }
                else for (int k = a; k < b; ++k) if (ok[k]) { d[k] = r[k]; ++drawn; }
            } else {
                int k = a;
                if (cc && cp) {   // 둘 다 캐시: 4화소씩 SSE2 로 B + (A−B)·t
                    const __m128i z = _mm_setzero_si128(), tw = _mm_set1_epi16((short)it256), iw = _mm_set1_epi16((short)(256 - it256));
                    for (; k + 4 <= b; k += 4) {
                        __m128i A = _mm_loadu_si128((const __m128i*)(rc + k)), B = _mm_loadu_si128((const __m128i*)(rp + k));
                        __m128i lo = _mm_srli_epi16(_mm_add_epi16(_mm_mullo_epi16(_mm_unpacklo_epi8(A, z), tw), _mm_mullo_epi16(_mm_unpacklo_epi8(B, z), iw)), 8);
                        __m128i hi = _mm_srli_epi16(_mm_add_epi16(_mm_mullo_epi16(_mm_unpackhi_epi8(A, z), tw), _mm_mullo_epi16(_mm_unpackhi_epi8(B, z), iw)), 8);
                        _mm_storeu_si128((__m128i*)(d + k), _mm_packus_epi16(lo, hi));
                    }
                    drawn += k - a;
                }
                for (; k < b; ++k) {
                    if (!gOkC[k] || !gOkP[k]) continue;
                    uint32_t A = rc[k], B = rp[k];
                    uint32_t rb = ((((A & 0xff00ff) * it256) + ((B & 0xff00ff) * (256 - it256))) >> 8) & 0xff00ff;
                    uint32_t g = ((((A & 0xff00) * it256) + ((B & 0xff00) * (256 - it256))) >> 8) & 0xff00;
                    d[k] = rb | g; ++drawn;
                }
            }
        }
    }
    LeaveCriticalSection(&gCs);
    double dt = nowMs() - t0;
    ++gT.n; gT.sum += dt; gT.max = std::max(gT.max, dt);
    if (gLog && (gT.n % 200 == 0 || dt > 30 || tBlend >= 0))
        hlog("hiart: paint %ldx%ld %.2fms (avg %.2f max %.2f n %d) miss %d t %.3f drawn %d | pre %.1f model %.1f codes %.1f blend %.1f fit %.1f erode %.1f comp %.1f", P.right - P.left, P.bottom - P.top, dt, gT.sum / gT.n, gT.max, gT.n, miss, tBlend, drawn, tA - t0, tB - tA, tC - tB, tD - tC, tE - tD, tF - tE, nowMs() - tF);
}

bool HiArt_Rects(std::vector<RECT>& out) {
    out.clear();
    if (!gOn) return false;
    // 그림 층이 하나라도 있으면 그림 전체(찍기마다 맞춰 보려면 화면 모듈이 PaintAbove 를 불러야 한다).
    // 1배 창이면 알리지 않는다(뒷판을 거치지 않게).
    if (CurrentLayout().cw <= W1) return false;
    EnterCriticalSection(&gCs);
    bool any = false;
    for (int i = 0; i < kLayers && !any; ++i) any = !gLayerKey[i].empty();
    LeaveCriticalSection(&gCs);
    if (any) out.push_back(RECT{0, 0, W1, H1});
    return !out.empty();
}

}}  // namespace forest::qol
