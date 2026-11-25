// qol_cm.cpp — 해설 모듈(1단계 장치 시험판, 2026-11-23). 계획: P:\AI\commentary-mode\forest\해설모드_계획_20261122.md
//
// 하는 일
//   1. 자료: 게임 폴더 cm\commentary.json(P:\AI\commentary-mode\forest\trial\cm_build.py 가 만든다).
//      닻 = (대본, 한국어판 슬롯, 명령 위치 pc). 시작할 때 깔린 scr\NNNN.gsc 의 그 자리(명령부 시작 + pc)가 정말 같은 슬롯의
//      MESSAGE(0x51)인지 다시 보고, 아니면 그 해설만 끈다(번역 글이 바뀌어도 자리가 같으면 그대로 쓴다).
//   2. 지금 줄(VM 스레드, 명령마다): MESSAGE 를 꺼낼 때 (대본, 슬롯)이 닻이면 「지금 해설」. 다음 명령을 꺼내면(그 줄을 넘김)
//      「앞선 해설」로 남고, 다음 해설이 오거나 다른 대본의 대사가 나오거나 타이틀로 가면 사라진다.
//      불러오기·되감기(VM 스레드가 바뀜)면 둘 다 비우고, 그 뒤 첫 대사보다 앞(pc)에 있는 같은 대본의 닻 가운데
//      읽은 줄(엔진 읽음 0x418d90)의 마지막을 「앞선 해설」로 되살린다.
//   3. 안내 단계(F6 으로 돌림): 끔 / 표시만 / 한 줄 / 자세히. 처음 값 = ini cm_level(기본 1 표시만), 고른 값은
//      forest-chart-progress\commentary.dat 에 남는다(세이브는 건드리지 않음).
//      표시만 = 대사 상자 오른쪽 위 포인트 「해설 · 제목」(앞선 해설이면 흐리게 「앞선 해설 · 제목」).
//      한 줄 = 닻 줄에서 대사 상자 위 글판(원문 일본어 + 「해설 · 한 줄」). 자세히 = 글판에 출처·짧은 풀이를 더한다.
//      자동 진행 중에는 글판 대신 포인트만 띄운다.
//   4. 가벼운 판(F7, 포인트·글판 누름): 화면 가운데, 바탕을 어둡게. 연 동안 게임 입력을 모두 막고(대사가 넘어가지 않는다)
//      진행 모듈의 자동 셈을 멈춘다(Cm_Modal). 아무 키·누름(뗄 때)으로 닫는다. 연 직후·닫은 직후 0.35초의 누름·키는 버리고,
//      판을 닫은 키를 누르고 있어도 그 키의 반복은 게임에 넘기지 않는다. 판이 있는 동안 F7 은 「끔」 단계에서도 연다.
//   5. 숨는 때: 건너뛰기·Ctrl, 대화창 숨김(Shift), 설정·세이브·불러오기 화면, 선택지, 지도, 조작 안내, 타이틀.
//
// 설정(forest-qol.ini): cm=1(이 모듈 전부, 자료가 없으면 저절로 꺼짐), cm_level=1(처음 단계 0~3),
//   cm_test=0(1 이면 시험 도우미 메시지 "ForestCmTest": 1 상태 쓰기, 2 건너뛰기를 그 대사에서 멈춤, 3 그 칸에 저장,
//   4 단계 바꾸기, 5 판 열기(F7 과 같음), 6 판 닫기).
#include "qol.h"
#include <windowsx.h>
#include <objidl.h>
#include <gdiplus.h>
#include <imm.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <cwchar>
#include <memory>
#include <unordered_map>
#pragma comment(lib, "gdiplus.lib")
#pragma comment(lib, "imm32.lib")
#pragma comment(lib, "msimg32.lib")

using namespace Gdiplus;

namespace forest { namespace qol {
namespace {

// ---------------------------------------------------------------- 엔진 주소(엔진_메모.md)
#define EV(a) (*(volatile int*)(uintptr_t)(a))
#define EW(a) (*(volatile uint16_t*)(uintptr_t)(a))
const uintptr_t kEngineObj = 0x466398, kMsgWinPtr = 0x46630c;
const uintptr_t kAuto = 0x466408, kCtrlKey = 0x4663f8, kCtrlSkip = 0x466400, kTabReq = 0x4663fc, kTabSkip = 0x466404;
const uintptr_t kClickWait = 0x4663e8, kChoiceBox = 0x4663cc, kSelect = 0x466418;
const uintptr_t kSettings = 0x46640c, kSaveScr = 0x466410, kLoadScr = 0x466414, kHidden = 0x466420;
const uintptr_t kDepth = 0x4664bc /*u16*/, kDepthScripts = 0x46647e /*u16[]*/;
const uintptr_t fIsRead = 0x418d90;        // int __cdecl(대본, 슬롯)
const uintptr_t fSave = 0x418a80;          // void __cdecl(u16 칸) — 지도 DLL 의 save 갈고리를 거친다
const uintptr_t fSkipResync = 0x41e8b0;    // 건너뛰기가 끝날 때 장면을 다시 맞춘다(VM 스레드)
const uintptr_t fFullRedraw = 0x43d350;    // thiscall(엔진 객체)

void* msgWin() { return *(void* volatile*)kMsgWinPtr; }
void* engineObj() { return *(void* volatile*)kEngineObj; }
bool autoOn() { return EV(kAuto) != 0; }
bool skipping() { return EV(kCtrlKey) || EV(kCtrlSkip) || EV(kTabReq) || EV(kTabSkip); }
bool screensOpen() { return EV(kSettings) || EV(kSaveScr) || EV(kLoadScr); }
int depth() { int d = EW(kDepth); return d < 0 ? 0 : (d > 15 ? 15 : d); }
int topScript() { return ((volatile uint16_t*)kDepthScripts)[depth()]; }
bool isRead(int script, uint32_t slot) {
    __try { return ((int(__cdecl*)(int, int))fIsRead)(script, (int)slot) != 0; }
    __except (EXCEPTION_EXECUTE_HANDLER) { return false; }
}

// ---------------------------------------------------------------- 설정
struct Config { bool on = false, test = false; int level0 = 1; } C;
HWND gWnd = nullptr;
UINT gMsgCm = 0, gMsgTest = 0;
const UINT_PTR kTimerId = 0xF0E70;
std::string gInstallNote;

// ---------------------------------------------------------------- 자료
struct Entry { std::wstring kind, title, line, source, mark, more, ja; std::string id; bool ok = false; };
struct Anchor { int sid = 0; uint32_t slot = 0, pc = 0; int entry = -1; bool ok = false; };
std::vector<Entry> gE;
std::vector<Anchor> gA;
std::unordered_map<uint64_t, int> gByLine;   // (대본 << 32 | 슬롯) → 닻 번호. 읽기 전용(설치 뒤 안 바뀜)
bool gReady = false;

// 작은 JSON 읽개(자료 파일 꼴만 — 객체·배열·문자열·수·참거짓·null)
struct JV {
    enum T { Null, Bool, Num, Str, Arr, Obj } t = Null;
    bool b = false; double n = 0; std::wstring s;
    std::vector<JV> a; std::vector<std::pair<std::wstring, JV>> o;
    const JV* get(const wchar_t* k) const { if (t != Obj) return nullptr; for (auto& p : o) if (p.first == k) return &p.second; return nullptr; }
    std::wstring str(const wchar_t* k) const { auto v = get(k); return v && v->t == Str ? v->s : std::wstring(); }
    double num(const wchar_t* k, double d) const { auto v = get(k); return v && v->t == Num ? v->n : d; }
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
            if (c >= L'0' && c <= L'9') v |= c - L'0'; else if (c >= L'a' && c <= L'f') v |= c - L'a' + 10;
            else if (c >= L'A' && c <= L'F') v |= c - L'A' + 10; else { ok = false; return 0; }
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
            default: s += k;
            }
        }
        if (p < e) ++p; else ok = false;
        return s;
    }
    JV val(int d = 0) {
        JV v; ws();
        if (p >= e || d > 32) { ok = false; return v; }
        if (*p == L'{') {
            v.t = JV::Obj; ++p; ws();
            if (p < e && *p == L'}') { ++p; return v; }
            for (;;) {
                ws(); if (p >= e || *p != L'"') { ok = false; return v; }
                std::wstring k = str(); ws();
                if (p >= e || *p != L':') { ok = false; return v; }
                ++p; v.o.emplace_back(k, val(d + 1)); if (!ok) return v;
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

bool readAll(const std::wstring& path, std::vector<uint8_t>& out) {
    out.clear();
    HANDLE f = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_EXISTING, 0, nullptr);
    if (f == INVALID_HANDLE_VALUE) return false;
    LARGE_INTEGER sz{}; GetFileSizeEx(f, &sz);
    bool ok = sz.QuadPart > 0 && sz.QuadPart < (64 << 20);
    if (ok) { out.resize((size_t)sz.QuadPart); DWORD n = 0; ok = ReadFile(f, out.data(), (DWORD)out.size(), &n, nullptr) && n == out.size(); }
    CloseHandle(f);
    return ok;
}
std::string narrow(const std::wstring& w) {
    int n = WideCharToMultiByte(CP_UTF8, 0, w.c_str(), (int)w.size(), nullptr, 0, nullptr, nullptr);
    std::string s(n > 0 ? n : 0, '\0');
    if (n > 0) WideCharToMultiByte(CP_UTF8, 0, w.c_str(), (int)w.size(), &s[0], n, nullptr, nullptr);
    return s;
}

// 닻 자리 확인: 명령부 시작(머리 u32[1]) + pc 에 같은 슬롯의 MESSAGE(인자 7번째 = 1)가 있는가
bool anchorHolds(const std::vector<uint8_t>& d, const Anchor& a) {
    if (d.size() < 32) return false;
    uint32_t start = *(const uint32_t*)&d[4];
    size_t off = (size_t)start + a.pc;
    if (off + 30 > d.size()) return false;
    return *(const uint16_t*)&d[off] == 0x51 && *(const uint32_t*)&d[off + 22] == a.slot && *(const int32_t*)&d[off + 26] == 1;
}

void loadData() {
    std::vector<uint8_t> raw;
    if (!readAll(Root() + L"\\cm\\commentary.json", raw)) { gInstallNote = "no data (cm\\commentary.json)"; return; }
    size_t skip = raw.size() >= 3 && raw[0] == 0xEF && raw[1] == 0xBB && raw[2] == 0xBF ? 3 : 0;
    int n = MultiByteToWideChar(CP_UTF8, 0, (const char*)raw.data() + skip, (int)(raw.size() - skip), nullptr, 0);
    if (n <= 0) { gInstallNote = "data not utf-8"; return; }
    std::wstring w(n, L'\0');
    MultiByteToWideChar(CP_UTF8, 0, (const char*)raw.data() + skip, (int)(raw.size() - skip), &w[0], n);
    JParse jp{w.c_str(), w.c_str() + w.size()};
    JV root = jp.val();
    const JV* ents = root.get(L"entries");
    if (!jp.ok || !ents || ents->t != JV::Arr) { gInstallNote = "data parse error"; return; }
    std::map<int, std::vector<uint8_t>> scr;
    int anchorsOk = 0, anchorsBad = 0;
    for (auto& je : ents->a) {
        Entry e;
        e.id = narrow(je.str(L"id")); e.kind = je.str(L"kind"); e.title = je.str(L"title"); e.line = je.str(L"line");
        e.source = je.str(L"source"); e.mark = je.str(L"mark"); e.more = je.str(L"more"); e.ja = je.str(L"ja");
        int idx = (int)gE.size();
        if (const JV* as = je.get(L"anchors")) if (as->t == JV::Arr) for (auto& ja : as->a) {
            Anchor a; a.sid = (int)ja.num(L"sid", 0); a.slot = (uint32_t)ja.num(L"slot", -1); a.pc = (uint32_t)ja.num(L"pc", -1); a.entry = idx;
            if (a.sid <= 0 || a.sid > 9999) { ++anchorsBad; continue; }
            if (!scr.count(a.sid)) {
                wchar_t name[32]; swprintf_s(name, L"\\scr\\%04d.gsc", a.sid);
                readAll(Root() + name, scr[a.sid]);
            }
            a.ok = anchorHolds(scr[a.sid], a);
            if (a.ok) { ++anchorsOk; e.ok = true; gByLine[((uint64_t)(uint32_t)a.sid << 32) | a.slot] = (int)gA.size(); }
            else { ++anchorsBad; Log("cm: anchor " + e.id + " " + std::to_string(a.sid) + ":" + std::to_string(a.slot) + " does not match installed script; off"); }
            gA.push_back(a);
        }
        gE.push_back(e);
    }
    int entriesOk = 0; for (auto& e : gE) entriesOk += e.ok;
    gReady = entriesOk > 0;
    gInstallNote = "entries " + std::to_string(entriesOk) + "/" + std::to_string(gE.size()) + ", anchors ok " + std::to_string(anchorsOk) +
                   (anchorsBad ? ", off " + std::to_string(anchorsBad) : "");
}

// ---------------------------------------------------------------- 상태(VM 스레드가 쓰고 다른 스레드가 읽는다)
volatile LONG gCur = -1;          // 지금 줄의 해설(Entry 번호)
volatile LONG gRecent = -1;       // 앞선 해설
volatile LONG gRecentSid = 0;
volatile LONG gNeedRestore = 0;   // 불러오기·되감기 뒤 첫 대사에서 앞선 해설을 되살린다
volatile LONG gLastSid = 0, gLastSlot = -1, gLastPc = 0, gHits = 0, gThreadChanges = 0;
DWORD gVmThread = 0;
volatile LONG gStopAt = 0;        // 시험: (대본 << 16 | 슬롯) 대사에서 건너뛰기를 멈춘다
volatile LONG gLevel = 1;         // 0 끔, 1 표시만, 2 한 줄, 3 자세히
volatile LONG gCardOpen = 0;
volatile LONG gCardEntry = -1;
DWORD gOpenedAt = 0, gClosedAt = 0;
bool gCardDown = false, gDownOnHint = false;
UINT gSwallowKey = 0;             // 판을 닫은 키: 뗄 때까지 반복을 삼킨다

void clearAll() { InterlockedExchange(&gCur, -1); InterlockedExchange(&gRecent, -1); InterlockedExchange(&gRecentSid, 0); }

// 불러오기·되감기 뒤: 같은 대본에서 지금 자리(pc)보다 앞의 닻 가운데 읽은 줄의 마지막
int restoreRecent(int sid, uint32_t pc) {
    int best = -1; uint32_t bestPc = 0;
    for (auto& a : gA) {
        if (!a.ok || a.sid != sid || a.pc >= pc) continue;
        if (best >= 0 && a.pc <= bestPc) continue;
        if (!isRead(sid, a.slot)) continue;
        best = a.entry; bestPc = a.pc;
    }
    return best;
}

void stopSkipHere() {   // VM 스레드(시험 도우미만)
    EV(kCtrlKey) = 0; EV(kCtrlSkip) = 0; EV(kTabReq) = 0;
    if (EV(kTabSkip)) {
        EV(kTabSkip) = 0;
        ((void(__cdecl*)())fSkipResync)();
        if (engineObj()) ((void(__thiscall*)(void*))fFullRedraw)(engineObj());
    }
}

// ---------------------------------------------------------------- 글꼴(GDI+ 와 GDI 로 같은 시스템 글꼴을 본다)
enum { F_KO = 0, F_KOB = 1, F_JA = 2, F_UI = 3, F_N = 4 };
ULONG_PTR gGdip = 0;
std::unique_ptr<FontFamily> gFam[F_N];
bool gSynthBold = false;
struct Cov { HDC dc = nullptr; HFONT f = nullptr; bool known = false; std::unordered_map<wchar_t, char> m; } gCov[F_N];
std::unordered_map<uint64_t, float> gWidth;

std::unique_ptr<FontFamily> pickFamily(std::initializer_list<const wchar_t*> names, std::wstring* got = nullptr) {
    for (auto n : names) {
        std::unique_ptr<FontFamily> f(new FontFamily(n));
        if (f->GetLastStatus() == Ok && f->IsAvailable()) { if (got) *got = n; return f; }
    }
    return nullptr;
}
void covInit(Cov& c, FontFamily* fam) {
    if (!fam) return;
    WCHAR name[LF_FACESIZE] = {}; fam->GetFamilyName(name);
    c.dc = CreateCompatibleDC(nullptr);
    c.f = CreateFontW(-32, 0, 0, 0, FW_NORMAL, 0, 0, 0, DEFAULT_CHARSET, 0, 0, ANTIALIASED_QUALITY, 0, name);
    if (!c.dc || !c.f) return;
    SelectObject(c.dc, c.f);
    WCHAR face[LF_FACESIZE] = {}; GetTextFaceW(c.dc, LF_FACESIZE, face);
    c.known = _wcsicmp(face, name) == 0;   // GDI 가 다른 글꼴로 바꿔 끼웠으면 모른다(= 다 있다고 본다)
}
bool covHas(int f, wchar_t ch) {
    Cov& c = gCov[f == F_KOB ? F_KO : f];
    if (!c.known) return true;
    auto it = c.m.find(ch);
    if (it != c.m.end()) return it->second != 0;
    WORD g = 0xFFFF;
    GetGlyphIndicesW(c.dc, &ch, 1, &g, GGI_MARK_NONEXISTING_GLYPHS);
    bool h = g != 0xFFFF;
    c.m[ch] = h ? 1 : 0;
    return h;
}
FontFamily* famOf(int f) { return gFam[f] ? gFam[f].get() : gFam[F_KO].get(); }
INT styleOf(int f) { return f == F_KOB && gSynthBold ? FontStyleBold : FontStyleRegular; }
// 글자마다 글꼴: 주 글꼴에 없으면 한국어 → 일본어 차례로
int fontFor(int prim, wchar_t c) {
    if (c < 0x80) return prim;
    if (covHas(prim, c)) return prim;
    if (prim != F_KO && prim != F_KOB && covHas(F_KO, c)) return F_KO;
    if (prim != F_JA && covHas(F_JA, c)) return F_JA;
    return prim;
}

bool startDraw() {
    if (gGdip) return true;
    GdiplusStartupInput in;
    if (GdiplusStartup(&gGdip, &in, nullptr) != Ok) { gGdip = 0; return false; }
    std::wstring ko, kob, ja;
    gFam[F_KO] = pickFamily({L"Noto Serif KR", L"Batang", L"\uBC14\uD0D5", L"Malgun Gothic"}, &ko);
    gFam[F_KOB] = pickFamily({L"Noto Serif KR SemiBold", L"Noto Serif KR Medium"}, &kob);
    if (!gFam[F_KOB]) { gSynthBold = true; kob = ko + L" (bold)"; }
    gFam[F_JA] = pickFamily({L"Yu Mincho", L"MS Mincho", L"Noto Serif JP", L"Yu Gothic", L"Meiryo", L"MS Gothic"}, &ja);
    gFam[F_UI] = pickFamily({L"Malgun Gothic"});
    if (!gFam[F_KO]) gFam[F_KO] = pickFamily({L"Arial"});
    for (int i = 0; i < F_N; ++i) if (i != F_KOB) covInit(gCov[i], famOf(i));
    Log("cm: fonts ko=" + narrow(ko) + " bold=" + narrow(kob) + " ja=" + narrow(ja) + (gCov[F_KO].known ? "" : " (ko glyph check unknown)"));
    return true;
}

float charW(Graphics& g, int f, float size, wchar_t c) {
    uint64_t k = ((uint64_t)f << 48) | ((uint64_t)(uint32_t)(size * 8) << 16) | (uint64_t)c;
    auto it = gWidth.find(k);
    if (it != gWidth.end()) return it->second;
    Font font(famOf(f), size, styleOf(f), UnitPixel);
    StringFormat fmt(StringFormat::GenericTypographic());
    fmt.SetFormatFlags(fmt.GetFormatFlags() | StringFormatFlagsMeasureTrailingSpaces | StringFormatFlagsNoWrap);
    RectF out; g.MeasureString(&c, 1, &font, PointF(0, 0), &fmt, &out);
    gWidth[k] = out.Width;
    return out.Width;
}
float strW(Graphics& g, const std::wstring& s, int prim, float size) {
    float w = 0; for (wchar_t c : s) w += charW(g, fontFor(prim, c), size, c); return w;
}

// ---------------------------------------------------------------- 글줄 짜기
struct Run { std::wstring s; int f = 0; float x = 0; };
struct TLine { std::vector<Run> runs; float x = 0, base = 0, size = 14, w = 0; Color color; };
struct Box { std::vector<TLine> lines; float w = 0, h = 0; };

TLine makeLine(Graphics& g, const std::wstring& s, int prim, float size, const Color& col, float x, float base) {
    TLine t; t.x = x; t.base = base; t.size = size; t.color = col;
    float cx = 0; int cf = -1;
    for (wchar_t c : s) {
        int f = fontFor(prim, c);
        if (f != cf || t.runs.empty()) { Run r; r.f = f; r.x = cx; t.runs.push_back(r); cf = f; }
        t.runs.back().s += c;
        cx += charW(g, f, size, c);
    }
    t.w = cx;
    return t;
}
bool noLineStart(wchar_t c) {
    static const wchar_t* k = L"\u3001\u3002\uFF0C\uFF0E,.)\uFF09\u300D\u300F\u3011\u3009\u300B\uFF01\uFF1F!?\u30FC\u2026\u30FB"
                              L"\u3041\u3043\u3045\u3047\u3049\u3063\u3083\u3085\u3087\u308E\u30A1\u30A3\u30A5\u30A7\u30A9\u30C3\u30E3\u30E5\u30E7\u30EE";
    return wcschr(k, c) != nullptr;
}
// 한국어는 빈칸 뒤에서 끊고(낱말이 줄보다 길면 글자로), 일본어는 글자마다 끊되 줄머리 금지 글자는 앞줄에 매단다.
std::vector<std::wstring> wrap(Graphics& g, const std::wstring& s, int prim, float size, float maxW, float firstIndent = 0) {
    std::vector<std::wstring> out, toks;
    if (prim == F_JA) { for (wchar_t c : s) toks.push_back(std::wstring(1, c)); }
    else {
        std::wstring cur;
        for (wchar_t c : s) { cur += c; if (c == L' ') { toks.push_back(cur); cur.clear(); } }
        if (!cur.empty()) toks.push_back(cur);
    }
    std::wstring line; float w = 0, lim = maxW - firstIndent;
    auto push = [&]() {
        while (!line.empty() && line.back() == L' ') line.pop_back();
        out.push_back(line); line.clear(); w = 0; lim = maxW;
    };
    for (auto& t : toks) {
        float tw = strW(g, t, prim, size);
        float tight = (!t.empty() && t.back() == L' ') ? tw - charW(g, fontFor(prim, L' '), size, L' ') : tw;
        if (w + tight <= lim) { line += t; w += tw; continue; }
        if (prim == F_JA && !line.empty() && noLineStart(t[0])) { line += t; w += tw; push(); continue; }
        if (!line.empty()) push();
        if (tight <= lim) { line = t; w = tw; continue; }
        for (wchar_t c : t) {
            float cw = charW(g, fontFor(prim, c), size, c);
            if (w + cw > lim && !line.empty()) push();
            line += c; w += cw;
        }
    }
    if (!line.empty()) push();
    return out;
}

// ---------------------------------------------------------------- 색(시안 11-22 과 같은 값)
const Color C_GOLD(255, 250, 199, 117), C_EDGE_GOLD(255, 239, 159, 39), C_EDGE_DIM(255, 95, 94, 90);
const Color C_TXT(255, 241, 239, 232), C_JP(255, 211, 209, 199), C_DIM(255, 180, 178, 169), C_DIMMER(255, 136, 135, 128);
const Color C_PANEL(199, 20, 20, 18), C_PILL(204, 20, 20, 18), C_CARD(248, 44, 44, 42), C_BACK(140, 0, 0, 0);

// 자리(800×600 논리 좌표). 대사 상자는 y 462~600, 대사 글자는 x 176~.
const float kRight = 788, kBottom = 456, kPanelX = 176, kPanelW = 612, kPanelTopMin = 214, kPillH = 26;

std::wstring pillText(int e, bool bright) { return std::wstring(bright ? L"\uD574\uC124 \u00B7 " : L"\uC55E\uC120 \uD574\uC124 \u00B7 ") + gE[e].title; }

Box layPanel(Graphics& g, const Entry& e, int level, float k) {
    Box b; b.w = kPanelW;
    const float pad = 11, inner = b.w - 2 * pad;
    float jaS = 14 * k, lnS = 14.5f * k, srcS = 12.5f * k, moreS = 14 * k, y = 8;
    for (auto& s : wrap(g, e.ja, F_JA, jaS, inner)) { b.lines.push_back(makeLine(g, s, F_JA, jaS, C_JP, pad, y + jaS * 1.12f)); y += jaS * 1.5f; }
    y += 2;
    std::wstring lab = L"\uD574\uC124";   // 해설
    float labW = strW(g, lab, F_KOB, lnS);
    auto rows = wrap(g, L" \u00B7 " + e.line, F_KO, lnS, inner, labW);
    b.lines.push_back(makeLine(g, lab, F_KOB, lnS, C_GOLD, pad, y + lnS * 1.12f));
    for (size_t i = 0; i < rows.size(); ++i) { b.lines.push_back(makeLine(g, rows[i], F_KO, lnS, C_TXT, pad + (i ? 0 : labW), y + lnS * 1.12f)); y += lnS * 1.5f; }
    if (level >= 3) {
        y += 3;
        std::wstring src = L"\uCD9C\uCC98  " + e.source + (e.mark.empty() ? L"" : L"   \u00B7   " + e.mark);   // 출처
        for (auto& s : wrap(g, src, F_UI, srcS, inner)) { b.lines.push_back(makeLine(g, s, F_UI, srcS, C_DIM, pad, y + srcS * 1.12f)); y += srcS * 1.5f; }
        y += 2;
        for (auto& s : wrap(g, e.more, F_KO, moreS, inner)) { b.lines.push_back(makeLine(g, s, F_KO, moreS, C_TXT, pad, y + moreS * 1.12f)); y += moreS * 1.55f; }
    }
    b.h = y + 7;
    return b;
}
Box layCard(Graphics& g, const Entry& e) {
    Box b; b.w = 560;
    const float pad = 22, inner = b.w - 2 * pad;
    float y = 16, hS = 12.5f, tS = 20, sS = 12.5f, jS = 14.5f, mS = 15.5f;
    std::wstring head = L"\uD574\uC124 \u00B7 \uAC8C\uC784 \uBA48\uCDA4";   // 해설 · 게임 멈춤
    b.lines.push_back(makeLine(g, head, F_UI, hS, C_DIMMER, pad, y + hS * 1.12f));
    float kw = strW(g, e.kind, F_UI, hS);
    b.lines.push_back(makeLine(g, e.kind, F_UI, hS, C_DIMMER, b.w - pad - kw, y + hS * 1.12f));
    y += hS * 1.5f + 6;
    for (auto& s : wrap(g, e.line, F_KOB, tS, inner)) { b.lines.push_back(makeLine(g, s, F_KOB, tS, C_GOLD, pad, y + tS * 1.12f)); y += tS * 1.42f; }
    y += 1;
    std::wstring src = L"\uCD9C\uCC98  " + e.source + (e.mark.empty() ? L"" : L"   \u00B7   " + e.mark);
    for (auto& s : wrap(g, src, F_UI, sS, inner)) { b.lines.push_back(makeLine(g, s, F_UI, sS, C_DIM, pad, y + sS * 1.12f)); y += sS * 1.5f; }
    y += 8;
    for (auto& s : wrap(g, e.ja, F_JA, jS, inner)) { b.lines.push_back(makeLine(g, s, F_JA, jS, C_JP, pad, y + jS * 1.12f)); y += jS * 1.55f; }
    y += 8;
    for (auto& s : wrap(g, e.more, F_KO, mS, inner)) { b.lines.push_back(makeLine(g, s, F_KO, mS, C_TXT, pad, y + mS * 1.12f)); y += mS * 1.65f; }
    y += 12;
    std::wstring foot = L"\uC544\uBB34 \uD0A4\uB098 \uB204\uB974\uBA74 \uB2EB\uD799\uB2C8\uB2E4";   // 아무 키나 누르면 닫힙니다
    b.lines.push_back(makeLine(g, foot, F_UI, 12.5f, C_DIMMER, pad, y + 12.5f * 1.12f));
    y += 12.5f * 1.5f + 14;
    b.h = y;
    return b;
}

// 해설마다 한 번 짠다(창 스레드, gCs 안)
struct Lay { bool done = false; float pillW[2] = {0, 0}; Box panel[2]; Box card; };
std::vector<Lay> gLay;
void ensureLayout(int e) {
    if (e < 0 || e >= (int)gE.size()) return;
    if ((int)gLay.size() != (int)gE.size()) gLay.resize(gE.size());
    Lay& L = gLay[e];
    if (L.done || !startDraw()) return;
    Bitmap bmp(4, 4, PixelFormat32bppPARGB);
    Graphics g(&bmp);
    g.SetTextRenderingHint(TextRenderingHintAntiAlias);
    for (int b = 0; b < 2; ++b) L.pillW[b] = 10 + 13 + 7 + std::min(360.f, strW(g, pillText(e, b != 0), F_KO, 14)) + 13;
    for (int lv = 2; lv <= 3; ++lv) {
        float k = 1;
        Box bx = layPanel(g, gE[e], lv, k);
        while (kBottom - bx.h < kPanelTopMin && k > 0.7f) { k -= 0.05f; bx = layPanel(g, gE[e], lv, k); }
        L.panel[lv - 2] = bx;
    }
    L.card = layCard(g, gE[e]);
    L.done = true;
}

// ---------------------------------------------------------------- 보이는 상태(창 스레드 타이머가 정한다)
struct Vis { int pill = -1, bright = 0, panel = -1, level = 0, card = -1; };
Vis gVis;
RECT gPillRect{}, gPanelRect{}, gCardBox{};
CRITICAL_SECTION gCs;
bool gCsInit = false;

bool visibleNow() {
    return !EV(kHidden) && !skipping() && !screensOpen() && !EV(kChoiceBox) && !EV(kSelect) && !ChartIsOpen() && !Play_GuideOpen() &&
           msgWin() != nullptr && topScript() != 1;
}
Vis desired() {
    Vis v; v.level = gLevel;
    if (!C.on || !gReady) return v;
    if (gCardOpen) { v.card = gCardEntry; return v; }
    if (gLevel <= 0 || !visibleNow()) return v;
    int cur = gCur, rec = gRecent;
    if (cur >= 0) {
        if (gLevel >= 2 && !autoOn()) v.panel = cur;
        else { v.pill = cur; v.bright = 1; }
    } else if (rec >= 0) { v.pill = rec; v.bright = 0; }
    return v;
}
RECT rectF(float x0, float y0, float x1, float y1) { return RECT{(LONG)std::floor(x0), (LONG)std::floor(y0), (LONG)std::ceil(x1), (LONG)std::ceil(y1)}; }
void rectsOf(const Vis& v, std::vector<RECT>& out) {
    if (v.card >= 0) { out.push_back(RECT{0, 0, 800, 600}); return; }
    if (v.pill >= 0) out.push_back(gPillRect);
    if (v.panel >= 0) out.push_back(gPanelRect);
}
// gCs 안에서
void placeRects(const Vis& v) {
    gPillRect = gPanelRect = gCardBox = RECT{0, 0, 0, 0};
    if (v.pill >= 0) { ensureLayout(v.pill); float w = gLay[v.pill].pillW[v.bright ? 1 : 0]; gPillRect = rectF(kRight - w, kBottom - kPillH, kRight, kBottom); }
    if (v.panel >= 0) { ensureLayout(v.panel); const Box& b = gLay[v.panel].panel[std::min(1, std::max(0, v.level - 2))]; gPanelRect = rectF(kPanelX, kBottom - b.h, kPanelX + b.w, kBottom); }
    if (v.card >= 0) {
        ensureLayout(v.card); const Box& b = gLay[v.card].card;
        float x0 = 400 - b.w / 2, y0 = std::max(24.f, 288 - b.h / 2);
        gCardBox = rectF(x0, y0, x0 + b.w, y0 + b.h);
    }
}
void update() {   // 창 스레드
    if (!gCsInit) return;
    Vis v = desired();
    std::vector<RECT> before, after;
    EnterCriticalSection(&gCs);
    bool changed = memcmp(&v, &gVis, sizeof v) != 0;
    if (changed) { rectsOf(gVis, before); gVis = v; placeRects(gVis); rectsOf(gVis, after); }
    LeaveCriticalSection(&gCs);
    for (auto& r : before) Present_InvalidateLogical(r);
    for (auto& r : after) Present_InvalidateLogical(r);
}

// ---------------------------------------------------------------- 그리기(물리 좌표, qol_play 와 같은 틀)
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
Layer gPillLayer, gPanelLayer, gCardLayer;
struct Map { double sx, sy; int ox, oy; };
Map mapOf(const Layout& L) { return Map{L.cw / 800.0, L.ch / 600.0, L.ox, L.oy}; }
RECT phys(const Map& m, const RECT& r) {
    return RECT{m.ox + (int)std::floor(r.left * m.sx), m.oy + (int)std::floor(r.top * m.sy),
                m.ox + (int)std::ceil(r.right * m.sx), m.oy + (int)std::ceil(r.bottom * m.sy)};
}
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
    g.SetTextRenderingHint(TextRenderingHintAntiAlias);
    g.SetInterpolationMode(InterpolationModeHighQualityBicubic);
    g.SetPixelOffsetMode(PixelOffsetModeHalf);
    g.ScaleTransform((REAL)(W / ((logical.right - logical.left) * 1.0)), (REAL)(H / ((logical.bottom - logical.top) * 1.0)));
    g.TranslateTransform((REAL)-logical.left, (REAL)-logical.top);
    fn(g);
    return true;
}
void blit(HDC dc, const Layer& L, const Map& m, const RECT& clip) {
    if (!L.bmp) return;
    RECT P = phys(m, L.logical), D;
    P.right = P.left + L.w; P.bottom = P.top + L.h;
    if (!IntersectRect(&D, &P, &clip)) return;
    BLENDFUNCTION bf = {AC_SRC_OVER, 0, 255, AC_SRC_ALPHA};
    AlphaBlend(dc, D.left, D.top, D.right - D.left, D.bottom - D.top, L.dc, D.left - P.left, D.top - P.top, D.right - D.left, D.bottom - D.top, bf);
}

void roundRect(GraphicsPath& p, float x, float y, float w, float h, float r) {
    float d = r * 2;
    p.AddArc(x, y, d, d, 180, 90); p.AddArc(x + w - d, y, d, d, 270, 90);
    p.AddArc(x + w - d, y + h - d, d, d, 0, 90); p.AddArc(x, y + h - d, d, d, 90, 90);
    p.CloseFigure();
}
void drawLine(Graphics& g, const TLine& t, float ox, float oy) {
    SolidBrush br(t.color);
    StringFormat fmt(StringFormat::GenericTypographic());
    fmt.SetFormatFlags(fmt.GetFormatFlags() | StringFormatFlagsMeasureTrailingSpaces | StringFormatFlagsNoWrap);
    for (auto& r : t.runs) {
        FontFamily* fam = famOf(r.f); INT st = styleOf(r.f);
        Font font(fam, t.size, st, UnitPixel);
        float asc = t.size * fam->GetCellAscent(st) / (float)std::max<UINT16>(1, fam->GetEmHeight(st));
        g.DrawString(r.s.c_str(), (INT)r.s.size(), &font, PointF(ox + t.x + r.x, oy + t.base - asc), &fmt, &br);
    }
}
void drawBox(Graphics& g, const Box& b, float ox, float oy) { for (auto& t : b.lines) drawLine(g, t, ox, oy); }
void bookIcon(Graphics& g, float x, float y, const Color& c) {   // 13×10
    PointF L[4] = {PointF(x, y + 1.2f), PointF(x + 6.5f, y + 2.6f), PointF(x + 6.5f, y + 10.5f), PointF(x, y + 9.1f)};
    PointF R[4] = {PointF(x + 13, y + 1.2f), PointF(x + 6.5f, y + 2.6f), PointF(x + 6.5f, y + 10.5f), PointF(x + 13, y + 9.1f)};
    SolidBrush f(Color(60, c.GetR(), c.GetG(), c.GetB()));
    Pen pen(c, 1.15f); pen.SetLineJoin(LineJoinRound);
    g.FillPolygon(&f, L, 4); g.FillPolygon(&f, R, 4);
    g.DrawPolygon(&pen, L, 4); g.DrawPolygon(&pen, R, 4);
}
void drawPill(Graphics& g, int e, bool bright, const RECT& r) {
    float x = (float)r.left, y = (float)r.top, w = (float)(r.right - r.left), h = (float)(r.bottom - r.top);
    GraphicsPath p; roundRect(p, x + 0.5f, y + 0.5f, w - 1, h - 1, (h - 1) / 2);
    SolidBrush bg(C_PILL); g.FillPath(&bg, &p);
    Pen pen(bright ? C_EDGE_GOLD : C_EDGE_DIM, 1.1f); g.DrawPath(&pen, &p);
    const Color& c = bright ? C_GOLD : C_DIM;
    bookIcon(g, x + 10, y + h / 2 - 5.5f, c);
    TLine t = makeLine(g, pillText(e, bright), F_KO, 14, c, x + 30, y + h / 2 + 14 * 0.36f);
    drawLine(g, t, 0, 0);
}
void drawPanel(Graphics& g, const Box& b, const RECT& r) {
    float x = (float)r.left, y = (float)r.top;
    GraphicsPath p; roundRect(p, x + 0.5f, y + 0.5f, b.w - 1, b.h - 1, 7);
    SolidBrush bg(C_PANEL); g.FillPath(&bg, &p);
    Pen pen(C_EDGE_DIM, 0.8f); g.DrawPath(&pen, &p);
    drawBox(g, b, x, y);
}
void drawCard(Graphics& g, const Box& b, const RECT& r) {
    SolidBrush back(C_BACK); g.FillRectangle(&back, 0.f, 0.f, 800.f, 600.f);
    float x = (float)r.left, y = (float)r.top;
    GraphicsPath p; roundRect(p, x, y, b.w, b.h, 9);
    SolidBrush bg(C_CARD); g.FillPath(&bg, &p);
    Pen pen(C_EDGE_GOLD, 1.3f); g.DrawPath(&pen, &p);
    drawBox(g, b, x, y);
}

// ---------------------------------------------------------------- 단계·판
std::wstring levelName(int lv) {
    static const wchar_t* n[4] = {L"\uB054", L"\uD45C\uC2DC\uB9CC", L"\uD55C \uC904", L"\uC790\uC138\uD788"};   // 끔 표시만 한 줄 자세히
    return n[std::max(0, std::min(3, lv))];
}
std::wstring levelFile() { return Root() + L"\\forest-chart-progress\\commentary.dat"; }
void saveLevel() {
    char b[32]; int n = sprintf_s(b, "level=%d\r\n", (int)gLevel);
    HANDLE f = CreateFileW(levelFile().c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (f == INVALID_HANDLE_VALUE) return;
    DWORD w = 0; WriteFile(f, b, (DWORD)n, &w, nullptr); CloseHandle(f);
}
int readLevel(int def) {
    std::vector<uint8_t> b;
    if (!readAll(levelFile(), b)) return def;
    std::string s(b.begin(), b.end());
    size_t p = s.find("level=");
    if (p == std::string::npos) return def;
    int v = atoi(s.c_str() + p + 6);
    return v >= 0 && v <= 3 ? v : def;
}
void setLevel(int lv, bool announce) {
    InterlockedExchange(&gLevel, std::max(0, std::min(3, lv)));
    saveLevel();
    Log("cm: level " + std::to_string(gLevel));
    if (announce) {
        static const wchar_t* t[4] = {
            L"\uD574\uC124 \uB054 \u00B7 F6 \uC73C\uB85C \uB2E4\uC2DC \uCF2D\uB2C8\uB2E4",                                          // 해설 끔 · F6 으로 다시 켭니다
            L"\uD574\uC124: \uD45C\uC2DC\uB9CC \u00B7 \uD574\uC124\uC774 \uC788\uB294 \uC904\uC5D0 \uD45C\uC2DC\uB9CC \uD569\uB2C8\uB2E4",   // 해설: 표시만 · 해설이 있는 줄에 표시만 합니다
            L"\uD574\uC124: \uD55C \uC904 \u00B7 \uC6D0\uBB38\uACFC \uD55C \uC904 \uD480\uC774\uB97C \uB300\uC0AC \uC704\uC5D0 \uB744\uC6C1\uB2C8\uB2E4",   // 해설: 한 줄 · 원문과 한 줄 풀이를 대사 위에 띄웁니다
            L"\uD574\uC124: \uC790\uC138\uD788 \u00B7 \uCD9C\uCC98\uC640 \uC9E7\uC740 \uD480\uC774\uAE4C\uC9C0 \uB744\uC6C1\uB2C8\uB2E4"};  // 해설: 자세히 · 출처와 짧은 풀이까지 띄웁니다
        Toast(t[gLevel], 2600);
    }
    update();
}
void openCard(int e, const char* how) {
    if (e < 0 || e >= (int)gE.size()) return;
    InterlockedExchange(&gCardEntry, e);
    InterlockedExchange(&gCardOpen, 1);
    gOpenedAt = GetTickCount(); gCardDown = false; gDownOnHint = false;
    Log(std::string("cm: card open ") + gE[e].id + " (" + how + ") at " + std::to_string(gLastSid) + ":" + std::to_string(gLastSlot) +
        (autoOn() ? " auto paused" : ""));
    update();
}
void closeCard(const char* how) {
    if (!gCardOpen) return;
    InterlockedExchange(&gCardOpen, 0);
    gClosedAt = GetTickCount();
    Log(std::string("cm: card closed (") + how + ")");
    update();
}
void keyF7() {
    if (gCardOpen) { closeCard("F7"); return; }
    if (skipping()) { Toast(L"\uAC74\uB108\uB6F0\uB294 \uB3D9\uC548\uC5D0\uB294 \uD574\uC124\uC744 \uC5F4\uC9C0 \uC54A\uC2B5\uB2C8\uB2E4"); return; }   // 건너뛰는 동안에는 해설을 열지 않습니다
    if (screensOpen() || ChartIsOpen() || Play_GuideOpen()) return;
    int e = gCur >= 0 ? (int)gCur : (int)gRecent;
    if (e < 0 || topScript() == 1) { Toast(L"\uC9C0\uAE08 \uBCFC \uC218 \uC788\uB294 \uD574\uC124\uC774 \uC5C6\uC2B5\uB2C8\uB2E4"); return; }   // 지금 볼 수 있는 해설이 없습니다
    openCard(e, "F7");
}

// 한글 입력기가 켜져 있으면 글자 키가 VK_PROCESSKEY 로 온다
UINT realKey(HWND h, WPARAM w) { return w == VK_PROCESSKEY ? ImmGetVirtualKey(h) : (UINT)w; }

bool cardWndProc(HWND h, UINT m, WPARAM w, LPARAM l, LRESULT& r) {
    DWORD now = GetTickCount();
    switch (m) {
    case WM_KEYDOWN:
        if (!(l & 0x40000000) && now - gOpenedAt >= 350) { gSwallowKey = realKey(h, w); closeCard("key"); }
        r = 0; return true;
    case WM_KEYUP: return false;   // 엔진은 Ctrl 뗌만 본다
    case WM_SYSKEYDOWN: if (w == VK_F4) return false; r = 0; return true;
    case WM_CHAR: case WM_SYSCHAR: case WM_DEADCHAR: r = 0; return true;
    case WM_LBUTTONDOWN: case WM_RBUTTONDOWN: case WM_MBUTTONDOWN:
    case WM_LBUTTONDBLCLK: case WM_RBUTTONDBLCLK: case WM_MBUTTONDBLCLK:
        gCardDown = now - gOpenedAt >= 350; r = 0; return true;
    case WM_LBUTTONUP: case WM_RBUTTONUP: case WM_MBUTTONUP:
        if (gCardDown) { gCardDown = false; closeCard("click"); }
        r = 0; return true;
    case WM_MOUSEMOVE: case WM_MOUSEWHEEL: r = 0; return true;
    case WM_SYSCOMMAND: if ((w & 0xfff0) == SC_CLOSE) closeCard("close"); return false;
    }
    return false;
}

bool hintAt(LPARAM l, int& e) {
    POINT pt = {GET_X_LPARAM(l), GET_Y_LPARAM(l)};
    EnterCriticalSection(&gCs);
    Vis v = gVis; RECT pr = gPillRect, nr = gPanelRect;
    LeaveCriticalSection(&gCs);
    if (v.pill >= 0 && PtInRect(&pr, pt)) { e = v.pill; return true; }
    if (v.panel >= 0 && PtInRect(&nr, pt)) { e = v.panel; return true; }
    return false;
}

// ---------------------------------------------------------------- 시험 도우미(cm_test=1)
void dumpState() {
    Vis v; RECT pr, nr, cb;
    EnterCriticalSection(&gCs); v = gVis; pr = gPillRect; nr = gPanelRect; cb = gCardBox; LeaveCriticalSection(&gCs);
    char b[1024];
    int n = sprintf_s(b, "sid=%d top=%d slot=%d pc=%d cur=%d recent=%d recentSid=%d level=%d card=%d cardEntry=%d pill=%d bright=%d panel=%d "
                         "pillRect=%d,%d,%d,%d panelRect=%d,%d,%d,%d cardBox=%d,%d,%d,%d hits=%d threads=%d auto=%d click=%d ctrl=%d ctrlskip=%d "
                         "tabreq=%d tabskip=%d hidden=%d choice=%d select=%d screens=%d chart=%d guide=%d ready=%d stopAt=%d\r\n",
                  (int)gLastSid, topScript(), (int)gLastSlot, (int)gLastPc, (int)gCur, (int)gRecent, (int)gRecentSid, (int)gLevel, (int)gCardOpen,
                  (int)gCardEntry, v.pill, v.bright, v.panel, (int)pr.left, (int)pr.top, (int)pr.right, (int)pr.bottom, (int)nr.left, (int)nr.top,
                  (int)nr.right, (int)nr.bottom, (int)cb.left, (int)cb.top, (int)cb.right, (int)cb.bottom, (int)gHits, (int)gThreadChanges,
                  EV(kAuto), EV(kClickWait), EV(kCtrlKey), EV(kCtrlSkip), EV(kTabReq), EV(kTabSkip), EV(kHidden), EV(kChoiceBox), EV(kSelect),
                  screensOpen() ? 1 : 0, ChartIsOpen() ? 1 : 0, Play_GuideOpen() ? 1 : 0, gReady ? 1 : 0, (int)gStopAt);
    std::wstring tmp = Root() + L"\\cm_state.tmp", fin = Root() + L"\\cm_state.txt";
    HANDLE f = CreateFileW(tmp.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (f == INVALID_HANDLE_VALUE) return;
    DWORD w = 0; WriteFile(f, b, (DWORD)n, &w, nullptr); CloseHandle(f);
    MoveFileExW(tmp.c_str(), fin.c_str(), MOVEFILE_REPLACE_EXISTING);
}
void testMsg(WPARAM w, LPARAM l) {
    switch (w) {
    case 1: dumpState(); break;
    case 2: InterlockedExchange(&gStopAt, (LONG)l); Log("cm test: stop skip at " + std::to_string((l >> 16) & 0xffff) + ":" + std::to_string(l & 0xffff)); break;
    case 3: {
        ((void(__cdecl*)(unsigned))fSave)((unsigned)l);
        Log("cm test: saved slot " + std::to_string((int)l) + " at " + std::to_string(gLastSid) + ":" + std::to_string(gLastSlot));
        break;
    }
    case 4: setLevel((int)l, false); break;
    case 5: keyF7(); break;
    case 6: closeCard("test"); break;
    }
}

}  // namespace

// ---------------------------------------------------------------- 약속(qol.h)
bool Cm_Install() {
    C.on = Cfg("cm", 1) != 0;
    if (!C.on) return false;
    C.test = Cfg("cm_test", 0) != 0;
    C.level0 = std::max(0, std::min(3, Cfg("cm_level", 1)));
    InitializeCriticalSection(&gCs); gCsInit = true;
    loadData();
    if (!gReady) { C.on = false; return false; }
    return true;
}

void Cm_WindowReady(HWND h) {
    if (!gInstallNote.empty()) { Log("cm: " + gInstallNote); }
    if (!C.on) return;
    gWnd = h;
    InterlockedExchange(&gLevel, readLevel(C.level0));
    Log("cm: on, level " + std::to_string(gLevel) + (C.test ? ", test messages" : ""));
    gMsgCm = RegisterWindowMessageW(L"ForestQolCm");
    if (C.test) gMsgTest = RegisterWindowMessageW(L"ForestCmTest");
    PostMessageW(h, gMsgCm, 1, 0);   // 타이머는 창 스레드에서 건다
}

bool Cm_WndProc(HWND h, UINT m, WPARAM w, LPARAM l, LRESULT& r) {
    if (!C.on) return false;
    if (gMsgCm && m == gMsgCm) { if (w == 1) SetTimer(h, kTimerId, 50, nullptr); r = 0; return true; }
    if (m == WM_TIMER && w == kTimerId) { update(); r = 0; return true; }
    if (gMsgTest && m == gMsgTest) { testMsg(w, l); r = 0; return true; }
    if (gCardOpen) return cardWndProc(h, m, w, l, r);
    DWORD now = GetTickCount();
    // 판을 닫은 키는 뗄 때까지 반복을 넘기지 않는다
    if (gSwallowKey) {
        if (m == WM_KEYDOWN && realKey(h, w) == gSwallowKey && (l & 0x40000000)) { r = 0; return true; }
        if (m == WM_KEYUP && (UINT)w == gSwallowKey) gSwallowKey = 0;
    }
    // 닫은 직후 0.35초: 누름·키를 버린다(대사가 넘어가지 않게)
    if (now - gClosedAt < 350) {
        switch (m) {
        case WM_LBUTTONDOWN: case WM_LBUTTONUP: case WM_LBUTTONDBLCLK: case WM_RBUTTONDOWN: case WM_RBUTTONUP:
        case WM_KEYDOWN: case WM_CHAR: r = 0; return true;
        }
    }
    switch (m) {
    case WM_KEYDOWN: {
        UINT vk = realKey(h, w);
        bool repeat = (l & 0x40000000) != 0;
        if (vk == VK_F7) { if (!repeat) keyF7(); r = 0; return true; }
        if (vk == VK_F6) { if (!repeat) setLevel((gLevel + 1) % 4, true); r = 0; return true; }
        return false;
    }
    case WM_KEYUP:
        if (w == VK_F7 || w == VK_F6) { r = 0; return true; }
        return false;
    case WM_LBUTTONDOWN: case WM_LBUTTONDBLCLK: {
        int e = -1;
        gDownOnHint = hintAt(l, e);
        if (gDownOnHint) { r = 0; return true; }
        return false;
    }
    case WM_LBUTTONUP:
        if (gDownOnHint) {
            gDownOnHint = false;
            int e = -1;
            if (hintAt(l, e) && !skipping() && !screensOpen() && !ChartIsOpen() && !Play_GuideOpen()) openCard(e, "click");
            r = 0; return true;
        }
        return false;
    }
    return false;
}

void Cm_Fetch(void* script, int sid, uint32_t pc, uint16_t op, const uint8_t* cursor) {
    (void)script;
    if (!C.on) return;
    DWORD t = GetCurrentThreadId();
    if (t != gVmThread) {
        if (gVmThread) {
            InterlockedIncrement(&gThreadChanges);
            if (gCur >= 0 || gRecent >= 0) Log("cm: VM thread changed (load/rollback) -> cleared");
            clearAll();
            InterlockedExchange(&gNeedRestore, 1);
        }
        gVmThread = t;
    }
    if (sid == 1 || (sid == 9000 && pc == 0)) {   // 타이틀·다시보기 시작
        if (gCur >= 0 || gRecent >= 0) clearAll();
        InterlockedExchange(&gNeedRestore, 0);
        return;
    }
    if (op == 0x52) return;                        // 덧붙이는 대사: 같은 줄이 이어진다
    if (op != 0x51) { if (gCur >= 0) InterlockedExchange(&gCur, -1); return; }   // 그 줄을 넘겼다
    uint32_t slot = *(const uint32_t*)(cursor + 22);
    InterlockedExchange(&gLastSid, sid); InterlockedExchange(&gLastSlot, (LONG)slot); InterlockedExchange(&gLastPc, (LONG)pc);
    LONG stop = gStopAt;
    if (stop && ((stop >> 16) & 0xffff) == sid && (stop & 0xffff) == (LONG)slot) {
        InterlockedExchange(&gStopAt, 0);
        stopSkipHere();
        Log("cm test: skip stopped at " + std::to_string(sid) + ":" + std::to_string(slot));
    }
    auto it = gByLine.find(((uint64_t)(uint32_t)sid << 32) | slot);
    if (InterlockedExchange(&gNeedRestore, 0) && it == gByLine.end()) {
        int e = restoreRecent(sid, pc);
        if (e >= 0) {
            InterlockedExchange(&gRecent, e); InterlockedExchange(&gRecentSid, sid);
            Log("cm: recent restored -> " + gE[e].id + " (" + std::to_string(sid) + " pc " + std::to_string(pc) + ")");
        }
    }
    if (it != gByLine.end()) {
        const Anchor& a = gA[it->second];
        InterlockedExchange(&gCur, a.entry); InterlockedExchange(&gRecent, a.entry); InterlockedExchange(&gRecentSid, sid);
        InterlockedIncrement(&gHits);
        Log("cm: line " + std::to_string(sid) + ":" + std::to_string(slot) + " pc " + std::to_string(pc) + " (data pc " + std::to_string(a.pc) +
            ") -> " + gE[a.entry].id);
        return;
    }
    InterlockedExchange(&gCur, -1);
    if (gRecent >= 0 && gRecentSid != sid) { InterlockedExchange(&gRecent, -1); InterlockedExchange(&gRecentSid, 0); }   // 대목이 바뀌었다
}

void Cm_Paint(HDC dc, const Layout& L, const RECT& clip) {
    if (!C.on || !gCsInit || !dc || !gGdip) return;
    EnterCriticalSection(&gCs);
    Vis v = gVis;
    if (v.pill >= 0 || v.panel >= 0 || v.card >= 0) {
        Map m = mapOf(L);
        wchar_t sc[48]; swprintf_s(sc, L"|%d|%d", L.cw, L.ch);
        if (v.card >= 0 && gLay[v.card].done) {
            RECT box = gCardBox;
            if (render(gCardLayer, m, RECT{0, 0, 800, 600}, L"card|" + std::to_wstring(v.card) + sc, [&](Graphics& g) { drawCard(g, gLay[v.card].card, box); }))
                blit(dc, gCardLayer, m, clip);
        } else {
            if (v.panel >= 0 && gLay[v.panel].done) {
                const Box& b = gLay[v.panel].panel[std::min(1, std::max(0, v.level - 2))];
                RECT pr = gPanelRect;
                if (render(gPanelLayer, m, pr, L"panel|" + std::to_wstring(v.panel) + L"|" + std::to_wstring(v.level) + sc, [&](Graphics& g) { drawPanel(g, b, pr); }))
                    blit(dc, gPanelLayer, m, clip);
            }
            if (v.pill >= 0 && gLay[v.pill].done) {
                RECT pr = gPillRect; int e = v.pill; bool br = v.bright != 0;
                if (render(gPillLayer, m, pr, L"pill|" + std::to_wstring(e) + (br ? L"|1" : L"|0") + sc, [&](Graphics& g) { drawPill(g, e, br, pr); }))
                    blit(dc, gPillLayer, m, clip);
            }
        }
    }
    LeaveCriticalSection(&gCs);
}

bool Cm_Rects(std::vector<RECT>& out) {
    out.clear();
    if (!C.on || !gCsInit) return false;
    EnterCriticalSection(&gCs);
    rectsOf(gVis, out);
    LeaveCriticalSection(&gCs);
    return !out.empty();
}

bool Cm_On() { return C.on; }
bool Cm_Modal() { return C.on && gCardOpen != 0; }

}}  // namespace forest::qol
