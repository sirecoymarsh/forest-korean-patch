// 이야기의 지도 — 게임 안 화면(GDI+).
// 그림 재료·글꼴은 게임 폴더의 fc\ 에서 읽는다. 모양 규칙은 tools/mock.py 시안과 같다:
//   금빛 = 이번 회차(지금 자리·지나온 길), ✓ = 끝까지 읽음/고른 적 있음, 흐림 = 아직.
//   닿지 않은 장·선택은 이름·문구·행선지를 가린다(？？？). 「가린 것 보기」는 화면만 바꾼다.
#include "chart.h"
#include "chart_disp.h"
#include <windowsx.h>
#include <objidl.h>
#include <gdiplus.h>
#include <algorithm>
#include <atomic>
#include <cmath>
#include <map>
#include <memory>
#include <set>
#include <sstream>
#pragma comment(lib, "gdiplus.lib")

using namespace Gdiplus;

namespace forest {
namespace {

// ------------------------------------------------------------------ 상수
const float kW = 800, kH = 600;
const float kBandTop = 125, kBandBottom = 486;     // 담쟁이 띠 안쪽(assets/band.json)
const float kChapterTop = 230;
int gPage = -1;                    // -1 전체 지도, 0~8 장
float CanvasTop() { return gPage < 0 ? kBandTop : kChapterTop; }
const float kClipTop = 98, kClipBottom = 514;      // 찢긴 가장자리 밑으로 들어가는 범위

const Color INK(255, 58, 35, 15), INK_DIM(255, 128, 108, 76), INK_SOFT(255, 96, 70, 40), INK_LOCK(255, 172, 148, 104);
const Color GOLD(255, 255, 206, 72), GOLD_TXT(255, 255, 246, 102), GOLD_EDGE(255, 70, 40, 0), GOLD_SHADOW(210, 38, 27, 5);
const Color CREAM(215, 222, 204, 152), FAINT(150, 150, 140, 118), RUST(255, 226, 104, 60);
const Color WHITE(255, 252, 248, 232), LEAF_EDGE(255, 20, 42, 12), LEAF_DIM_TXT(255, 196, 202, 178), LEAF_DIM_EDGE(255, 18, 30, 12);
const Color CHECK_LEAF(255, 255, 248, 206), PROGRESS(235, 125, 76, 26), TAG_EDGE(255, 16, 16, 12);

// ------------------------------------------------------------------ 자원
std::wstring gRoot;
std::wstring gGlobalSave;
const uint16_t* (*gVarSource)() = nullptr;
ULONG_PTR gdipToken = 0;
std::unique_ptr<PrivateFontCollection> gFonts;
FontFamily* famSemi = nullptr;
FontFamily* famBlack = nullptr;
std::unique_ptr<FontFamily> famFallback;
std::map<std::wstring, std::unique_ptr<Bitmap>> gImages;
std::unique_ptr<FontFamily[]> gFamilies;

Bitmap* Img(const wchar_t* name) {
    auto it = gImages.find(name);
    if (it != gImages.end()) return it->second.get();
    std::wstring p = gRoot + L"\\fc\\" + name;
    std::unique_ptr<Bitmap> b(Bitmap::FromFile(p.c_str()));
    if (!b || b->GetLastStatus() != Ok) {
        Log("missing chart image " + std::string(p.begin(), p.end()));
        b.reset();
    }
    Bitmap* raw = b.get();
    gImages[name] = std::move(b);
    return raw;
}

bool StartGraphics() {
    if (gdipToken) return true;
    GdiplusStartupInput in;
    if (GdiplusStartup(&gdipToken, &in, nullptr) != Ok) { gdipToken = 0; return false; }
    gFonts.reset(new PrivateFontCollection());
    gFonts->AddFontFile((gRoot + L"\\fc\\ForestChartSerif-SemiBold.ttf").c_str());
    gFonts->AddFontFile((gRoot + L"\\fc\\ForestChartSerif-Black.ttf").c_str());
    int n = gFonts->GetFamilyCount();
    int found = 0;
    if (n > 0) {
        gFamilies.reset(new FontFamily[n]);
        gFonts->GetFamilies(n, gFamilies.get(), &found);
    }
    for (int i = 0; i < found; ++i) {
        WCHAR name[LF_FACESIZE] = {};
        gFamilies[i].GetFamilyName(name);
        std::wstring s = name;
        if (s.find(L"Black") != std::wstring::npos) famBlack = &gFamilies[i];
        else if (s.find(L"SemiBold") != std::wstring::npos) famSemi = &gFamilies[i];
    }
    if (!famSemi || !famBlack) {
        famFallback.reset(new FontFamily(L"바탕"));
        if (famFallback->GetLastStatus() != Ok) famFallback.reset(new FontFamily(L"Malgun Gothic"));
        if (!famSemi) famSemi = famFallback.get();
        if (!famBlack) famBlack = famFallback.get();
        Log("chart fonts missing; using system serif");
    }
    return true;
}

// ------------------------------------------------------------------ 설치된 번역 문구
std::map<int, std::vector<std::wstring>> gStrings;   // 스크립트 -> 슬롯 문자열

std::wstring Widen949(const char* s, int n) {
    int m = MultiByteToWideChar(949, 0, s, n, nullptr, 0);
    std::wstring w(m, L'\0');
    if (m) MultiByteToWideChar(949, 0, s, n, &w[0], m);
    return w;
}

std::wstring CleanText(const std::wstring& in) {
    std::wstring o;
    for (size_t i = 0; i < in.size(); ++i) {
        if (in[i] == L'^' && i + 1 < in.size()) {
            wchar_t k = in[i + 1];
            if (k == L'g') { i += 4; continue; }
            if (k == L'c') { i += 2; continue; }
            if (k == L'n') { o += L' '; i += 1; continue; }
            if (k == L'm') { i += 1; continue; }
        }
        o += in[i];
    }
    size_t a = o.find_first_not_of(L" 　"), b = o.find_last_not_of(L" 　");
    return a == std::wstring::npos ? L"" : o.substr(a, b - a + 1);
}

const std::vector<std::wstring>* ScriptStrings(int script) {
    auto it = gStrings.find(script);
    if (it != gStrings.end()) return it->second.empty() ? nullptr : &it->second;
    std::vector<std::wstring>& out = gStrings[script];
    wchar_t name[64];
    swprintf_s(name, L"\\scr\\%04d.gsc", script);
    HANDLE f = CreateFileW((gRoot + name).c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (f == INVALID_HANDLE_VALUE) return nullptr;
    DWORD size = GetFileSize(f, nullptr), got = 0;
    std::vector<char> b(size);
    bool ok = size > 28 && ReadFile(f, b.data(), size, &got, nullptr) && got == size;
    CloseHandle(f);
    if (!ok) return nullptr;
    const uint32_t* h = (const uint32_t*)b.data();
    uint64_t tp = (uint64_t)h[1] + h[2], n = h[3] / 4, base = tp + h[3];
    if (base > size || tp + 4 * n > size) return nullptr;
    const uint32_t* off = (const uint32_t*)(b.data() + tp);
    for (uint64_t i = 0; i < n; ++i) {
        uint64_t p = base + off[i];
        if (p >= size) { out.clear(); return nullptr; }
        uint64_t e = p;
        while (e < size && b[e]) ++e;
        out.push_back(Widen949(b.data() + p, (int)(e - p)));
    }
    return &out;
}

std::wstring Installed(int script, int slot, const wchar_t* fallback) {
    auto* s = ScriptStrings(script);
    if (s && slot >= 0 && slot < (int)s->size()) {
        std::wstring t = CleanText((*s)[slot]);
        if (!t.empty()) return t;
    }
    return fallback;
}

// ------------------------------------------------------------------ 게임 자체 읽음 기록(rssave.dat 끝부분)
std::map<int, std::vector<uint8_t>> gBits;

void LoadReadBits() {
    gBits.clear();
    std::wstring path = gGlobalSave.empty() ? gRoot + L"\\save\\rssave.dat" : gGlobalSave;
    HANDLE f = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (f == INVALID_HANDLE_VALUE) { Log("read record not found"); return; }
    DWORD size = GetFileSize(f, nullptr), got = 0;
    std::vector<uint8_t> b(size);
    bool ok = size < (1u << 22) && ReadFile(f, b.data(), size, &got, nullptr) && got == size;
    CloseHandle(f);
    if (!ok) return;
    // (u16 스크립트, u32 길이, 비트) 묶음이 파일 끝에서 정확히 끝나는 가장 긴 사슬
    size_t bestStart = 0, bestCount = 0;
    for (size_t s0 = 0x90; s0 + 6 <= size; ++s0) {
        size_t p = s0, count = 0;
        bool good = true;
        while (p < size) {
            if (p + 6 > size) { good = false; break; }
            uint16_t sid = *(const uint16_t*)&b[p];
            uint32_t len = *(const uint32_t*)&b[p + 2];
            if (sid < 1 || sid > 9999 || len > 4000) { good = false; break; }
            p += 6 + len;
            ++count;
        }
        if (good && p == size && count > bestCount) { bestCount = count; bestStart = s0; }
    }
    for (size_t p = bestStart; bestCount && p < size;) {
        uint16_t sid = *(const uint16_t*)&b[p];
        uint32_t len = *(const uint32_t*)&b[p + 2];
        gBits[sid].assign(b.begin() + p + 6, b.begin() + p + 6 + len);
        p += 6 + len;
    }
    Log("read record scripts " + std::to_string(gBits.size()));
}

bool Bit(int script, int slot) {
    auto it = gBits.find(script);
    if (it == gBits.end() || slot < 0) return false;
    size_t byte = (size_t)slot >> 3;
    return byte < it->second.size() && ((it->second[byte] >> (slot & 7)) & 1);
}
bool AnyBit(const std::vector<Wit>& w) {
    for (auto& x : w) if (Bit(x.script, x.slot)) return true;
    return false;
}

// ------------------------------------------------------------------ 화면 상태
struct State {
    bool all = false;
    bool runKnown = false;
    std::vector<char> sceneSeen, sceneDone, reached;
    std::vector<float> sceneFrac;
    std::vector<std::vector<char>> chosen;
    std::vector<int> runPick;
    std::vector<char> runInferred;     // 세이브 변수로 안 이번 회차 선택
    std::set<int> runScenes;
    std::set<int> runChapters;
    int curScene = -1, curChoice = -1, afterChoice = -1, afterOption = -1;
} S;

std::map<std::string, int> gCodexIndex;                       // 진행 기록 선택 ID -> model.cpp 번호
std::map<std::pair<std::string, int>, std::pair<int, int>> gOptMap;   // (ID, 선택지) -> (칸, 선택지)
std::map<std::string, int> gChoiceOfPage;                     // 진행 기록 선택 ID -> 칸
std::vector<std::wstring> gQuestion;
std::vector<std::vector<std::wstring>> gOptLabel;

int SceneOfScript(int script) {
    for (size_t i = 0; i < kScenes.size(); ++i)
        if (kScenes[i].script == script) return kScenes[i].kind == 2 && kScenes[i].parent >= 0 ? kScenes[i].parent : (int)i;
    return -1;
}

void BuildMaps() {
    if (!gOptMap.empty()) return;
    for (size_t i = 0; i < choices.size(); ++i) gCodexIndex[choices[i].id] = (int)i;
    for (size_t d = 0; d < kChoices.size(); ++d) {
        for (auto p : kChoices[d].pages) gChoiceOfPage[p] = (int)d;
        for (size_t k = 0; k < kChoices[d].options.size(); ++k)
            gOptMap[{kChoices[d].options[k].srcId, kChoices[d].options[k].srcOption}] = {(int)d, (int)k};
    }
    gQuestion.resize(kChoices.size());
    gOptLabel.resize(kChoices.size());
    for (size_t d = 0; d < kChoices.size(); ++d) {
        auto& c = kChoices[d];
        gQuestion[d] = Installed(c.script, c.qslot, c.question);
        for (auto& o : c.options) gOptLabel[d].push_back(Installed(c.script, o.slot, o.label));
    }
}

void ComputeState(const Progress& pg) {
    size_t ns = kScenes.size(), nc = kChoices.size();
    S.sceneSeen.assign(ns, 0); S.sceneDone.assign(ns, 0); S.sceneFrac.assign(ns, 0.f);
    S.reached.assign(nc, 0); S.chosen.assign(nc, {}); S.runPick.assign(nc, -1);
    S.runInferred.assign(nc, 0);
    S.runScenes.clear(); S.runChapters.clear();
    S.curScene = S.curChoice = S.afterChoice = S.afterOption = -1;
    for (size_t d = 0; d < nc; ++d) S.chosen[d].assign(kChoices[d].options.size(), 0);
    // 장면: 게임 읽음 기록 + 차트가 지켜본 기록
    for (size_t i = 0; i < ns; ++i) {
        auto& s = kScenes[i];
        int read = 0;
        for (int slot : s.slots) read += Bit(s.script, slot) ? 1 : 0;
        S.sceneFrac[i] = s.slots.empty() ? 0.f : (float)read / s.slots.size();
        bool done = false;
        for (int slot : s.exits) done = done || Bit(s.script, slot);
        S.sceneSeen[i] = read > 0 || pg.reachedScenes.count(s.script);
        S.sceneDone[i] = done || pg.completedScenes.count(s.script);
    }
    for (size_t i = 0; i < ns; ++i)   // 곁가지를 읽었으면 주인 장면도 본 것
        if (kScenes[i].kind == 2 && kScenes[i].parent >= 0 && S.sceneSeen[i]) S.sceneSeen[kScenes[i].parent] = 1;
    // 선택: 직접 증거
    for (size_t d = 0; d < nc; ++d) {
        auto& c = kChoices[d];
        if (AnyBit(c.reach) || AnyBit(c.pre)) S.reached[d] = 1;
        for (size_t k = 0; k < c.options.size(); ++k)
            if (AnyBit(c.options[k].witness)) { S.chosen[d][k] = 1; S.reached[d] = 1; }
    }
    for (int ci : pg.reachedChoices) {
        if (ci < 0 || ci >= (int)choices.size()) continue;
        auto it = gChoiceOfPage.find(choices[ci].id);
        if (it != gChoiceOfPage.end()) S.reached[it->second] = 1;
    }
    for (auto& co : pg.chosenOptions) {
        if (co.first < 0 || co.first >= (int)choices.size()) continue;
        auto it = gOptMap.find({choices[co.first].id, co.second});
        if (it != gOptMap.end()) { S.chosen[it->second.first][it->second.second] = 1; S.reached[it->second.first] = 1; }
    }
    // 이번 회차
    S.runKnown = pg.run.known;
    int lastSceneEvent = -1;
    for (size_t e = 0; e < pg.run.events.size(); ++e) {
        auto& ev = pg.run.events[e];
        if (ev.kind == SceneEnter) {
            int si = SceneOfScript(ev.script);
            if (si >= 0) S.runScenes.insert(si);
            lastSceneEvent = (int)e;
        } else if (ev.kind == OptionChosen && ev.choice >= 0 && ev.choice < (int)choices.size()) {
            auto it = gOptMap.find({choices[ev.choice].id, ev.option});
            if (it != gOptMap.end()) {
                S.runPick[it->second.first] = it->second.second;
                S.chosen[it->second.first][it->second.second] = 1;
                S.reached[it->second.first] = 1;
            }
        } else if (ev.kind == Restart) {
            int ch = ev.option - 1;   // model.cpp 장 번호(0부터)
            for (size_t d = 0; d < nc; ++d) if (kChoices[d].chapter == ch) S.runPick[d] = -1;
            for (auto it = S.runScenes.begin(); it != S.runScenes.end();)
                it = kScenes[*it].chapter == ch ? S.runScenes.erase(it) : std::next(it);
        }
    }
    // 지금 자리
    int cs = SceneOfScript(pg.run.currentScript);
    if (cs >= 0) {
        S.curScene = cs;
        S.runScenes.insert(cs);
        S.sceneSeen[cs] = 1;
        const Event* last = pg.run.events.empty() ? nullptr : &pg.run.events.back();
        if (last && last->kind == ChoiceReached && last->choice >= 0 && last->choice < (int)choices.size()) {
            auto it = gChoiceOfPage.find(choices[last->choice].id);
            if (it != gChoiceOfPage.end()) { S.curChoice = it->second; S.reached[it->second] = 1; }
        }
        if (S.curChoice < 0) {
            for (int e = (int)pg.run.events.size() - 1; e > lastSceneEvent && e >= 0; --e) {
                auto& ev = pg.run.events[e];
                if (ev.kind == OptionChosen && ev.choice >= 0 && ev.choice < (int)choices.size()) {
                    auto it = gOptMap.find({choices[ev.choice].id, ev.option});
                    if (it != gOptMap.end() && kChoices[it->second.first].scene == cs) {
                        S.afterChoice = it->second.first; S.afterOption = it->second.second;
                    }
                    break;
                }
            }
        }
    }
    // 앞선 선택 기록이 없는 세이브: 게임이 변수로 남긴 선택만 이번 회차로 칠한다
    const uint16_t* vars = (!pg.run.known && S.curScene >= 0 && gVarSource) ? gVarSource() : nullptr;
    if (vars) {
        int inferred = 0;
        for (size_t d = 0; d < nc; ++d) {
            if (S.runPick[d] >= 0) continue;
            int hit = -1, hits = 0;
            for (size_t k = 0; k < kChoices[d].options.size(); ++k) {
                auto& sig = kChoices[d].options[k].sig;
                if (sig.empty()) continue;
                bool all = true;
                for (auto& v : sig) all = all && v.var >= 0 && v.var < 7000 && (int)vars[v.var] == v.value;
                if (all) { hit = (int)k; ++hits; }
            }
            if (hits == 1) {
                S.runPick[d] = hit; S.runInferred[d] = 1;
                S.chosen[d][hit] = 1; S.reached[d] = 1; ++inferred;
            }
        }
        Log("this-run choices from save variables: " + std::to_string(inferred));
    }
    if (pg.run.known) { for (int s : S.runScenes) S.runChapters.insert(kScenes[s].chapter); }
    else if (S.curScene >= 0) { for (int c = 0; c <= kScenes[S.curScene].chapter; ++c) S.runChapters.insert(c); }
    // 확실한 거꾸로 추론: 뒤 칸에 닿았고 그리로 오는 길이 하나뿐이면 그 길을 지났다
    for (bool changed = true; changed;) {
        changed = false;
        for (size_t d = 0; d < nc; ++d) {
            if (!S.reached[d]) continue;
            std::vector<Pred> ps;
            for (auto& p : kChoices[d].preds) if (p.choice != (int)d) ps.push_back(p);
            if (ps.size() != 1) continue;
            auto& p = ps[0];
            if (!S.chosen[p.choice][p.option]) { S.chosen[p.choice][p.option] = 1; changed = true; }
            if (!S.reached[p.choice]) { S.reached[p.choice] = 1; changed = true; }
        }
    }
    // 선택에 닿았으면 그 장면도 본 것
    for (size_t d = 0; d < nc; ++d) if (S.reached[d]) S.sceneSeen[kChoices[d].scene] = 1;
}

bool SceneSeen(int i) { return S.all || S.sceneSeen[i]; }
bool ChoiceSeen(int d) { return S.all || S.reached[d]; }
bool Chosen(int d, int k) { return S.chosen[d][k] != 0; }
bool ChapterSeen(int c) {
    if (S.all) return true;
    for (size_t i = 0; i < kScenes.size(); ++i) if (kScenes[i].chapter == c && S.sceneSeen[i]) return true;
    return false;
}
bool ChapterSummarySeen(int c) {
    if (S.all) return true;
    if (kChapters[c].order.empty()) return false;
    for (int si : kChapters[c].order) if (!S.sceneDone[si]) return false;
    return true;
}
int CurChapter() { return S.curScene >= 0 ? kScenes[S.curScene].chapter : -1; }

// ------------------------------------------------------------------ 그리기 도구
struct Hit { RectF r; int type; int a; int b; };
enum HitType { HitTab = 1, HitButton, HitScene, HitQuestion, HitOption, HitPlate };
std::vector<Hit> gHits;

void Clip(Graphics& g, bool on) {
    float top = gPage < 0 ? kClipTop : kChapterTop - 12;
    if (on) g.SetClip(RectF(0, top, kW, kClipBottom - top));
    else g.ResetClip();
}

void Draw(Graphics& g, Bitmap* b, float x, float y, float w, float h, float alpha = 1.f) {
    if (!b || w < 1 || h < 1) return;
    if (alpha >= 0.999f) { g.DrawImage(b, RectF(x, y, w, h)); return; }
    ColorMatrix m = {{{1, 0, 0, 0, 0}, {0, 1, 0, 0, 0}, {0, 0, 1, 0, 0}, {0, 0, 0, alpha, 0}, {0, 0, 0, 0, 1}}};
    ImageAttributes ia;
    ia.SetColorMatrix(&m);
    g.DrawImage(b, RectF(x, y, w, h), 0, 0, (REAL)b->GetWidth(), (REAL)b->GetHeight(), UnitPixel, &ia);
}

// 세 토막 늘이기(찢긴 양 끝을 살린다)
void Draw3(Graphics& g, Bitmap* b, float x, float y, float w, float h, int cap) {
    if (!b) return;
    float sw = (float)b->GetWidth(), sh = (float)b->GetHeight();
    float capd = std::min(cap * h / sh, w / 2.f);
    g.DrawImage(b, RectF(x, y, capd, h), 0, 0, (REAL)cap, sh, UnitPixel);
    g.DrawImage(b, RectF(x + capd, y, w - 2 * capd, h), (REAL)cap, 0, sw - 2 * cap, sh, UnitPixel);
    g.DrawImage(b, RectF(x + w - capd, y, capd, h), sw - cap, 0, (REAL)cap, sh, UnitPixel);
}

float Measure(Graphics& g, const std::wstring& s, float size, bool black) {
    Font f(black ? famBlack : famSemi, size, FontStyleRegular, UnitPixel);
    RectF out;
    StringFormat fmt(StringFormat::GenericTypographic());
    fmt.SetFormatFlags(fmt.GetFormatFlags() | StringFormatFlagsMeasureTrailingSpaces);
    g.MeasureString(s.c_str(), (INT)s.size(), &f, PointF(0, 0), &fmt, &out);
    return out.Width;
}

// align: 0 왼쪽, 1 가운데, 2 오른쪽. y 는 글줄 가운데.
void Text(Graphics& g, const std::wstring& s, float x, float y, float size, bool black, Color fill,
          int align = 0, float maxW = 0, const Color* outline = nullptr, float ow = 0, const Color* shadow = nullptr) {
    if (s.empty()) return;
    float sz = size;
    if (maxW > 0) while (sz > 7 && Measure(g, s, sz, black) > maxW) sz -= 0.5f;
    FontFamily* fam = black ? famBlack : famSemi;
    float w = Measure(g, s, sz, black);
    float left = align == 1 ? x - w / 2 : align == 2 ? x - w : x;
    // 이 글꼴(Noto Serif KR)의 em 상자 기준으로 글자 가운데를 y 에 맞춘다
    float top = y - sz * 0.62f;
    StringFormat fmt(StringFormat::GenericTypographic());
    if (outline || shadow) {
        GraphicsPath path;
        path.AddString(s.c_str(), (INT)s.size(), fam, FontStyleRegular, sz, PointF(left, top), &fmt);
        if (shadow) {
            Matrix mt; mt.Translate(1, 2);
            std::unique_ptr<GraphicsPath> sp(path.Clone());
            sp->Transform(&mt);
            Pen sp2(*shadow, ow * 2 + 0.01f); sp2.SetLineJoin(LineJoinRound);
            g.DrawPath(&sp2, sp.get());
            SolidBrush sb(*shadow); g.FillPath(&sb, sp.get());
        }
        if (outline) {
            Pen pen(*outline, ow * 2); pen.SetLineJoin(LineJoinRound);
            g.DrawPath(&pen, &path);
        }
        SolidBrush br(fill);
        g.FillPath(&br, &path);
        return;
    }
    Font f(fam, sz, FontStyleRegular, UnitPixel);
    SolidBrush br(fill);
    g.DrawString(s.c_str(), (INT)s.size(), &f, PointF(left, top), &fmt, &br);
}

void GoldText(Graphics& g, const std::wstring& s, float x, float y, float size, int align = 1, float maxW = 0) {
    Text(g, s, x, y, size, true, GOLD_TXT, align, maxW, &GOLD_EDGE, 1.7f);
}

void Check(Graphics& g, float x, float y, float size, Color c, float width) {
    Pen pen(c, width);
    pen.SetLineJoin(LineJoinRound); pen.SetStartCap(LineCapRound); pen.SetEndCap(LineCapRound);
    PointF p[3] = {PointF(x, y + size * 0.55f), PointF(x + size * 0.38f, y + size * 0.92f), PointF(x + size, y + size * 0.05f)};
    g.DrawLines(&pen, p, 3);
}

struct Bz { PointF p0, p1, p2, p3; };
PointF BzAt(const Bz& b, float t) {
    float a = (1 - t) * (1 - t) * (1 - t), c = 3 * (1 - t) * (1 - t) * t, d = 3 * (1 - t) * t * t, e = t * t * t;
    return PointF(a * b.p0.X + c * b.p1.X + d * b.p2.X + e * b.p3.X, a * b.p0.Y + c * b.p1.Y + d * b.p2.Y + e * b.p3.Y);
}
void BzSplit(const Bz& b, float t, Bz& l, Bz& r) {
    auto lerp = [](PointF a, PointF c, float t) { return PointF(a.X + (c.X - a.X) * t, a.Y + (c.Y - a.Y) * t); };
    PointF a = lerp(b.p0, b.p1, t), c = lerp(b.p1, b.p2, t), d = lerp(b.p2, b.p3, t);
    PointF e = lerp(a, c, t), f = lerp(c, d, t), m = lerp(e, f, t);
    l = {b.p0, a, e, m}; r = {m, f, d, b.p3};
}

void Stroke(Graphics& g, const Bz& b, Color c, float width, bool dashed = false, float dashOn = 5, float dashOff = 5) {
    Pen pen(c, width);
    pen.SetStartCap(LineCapRound); pen.SetEndCap(LineCapRound); pen.SetLineJoin(LineJoinRound);
    if (dashed) {
        REAL pat[2] = {dashOn / width, dashOff / width};
        pen.SetDashPattern(pat, 2);
        pen.SetDashCap(DashCapRound);
    }
    g.DrawBezier(&pen, b.p0, b.p1, b.p2, b.p3);
}
void StrokeLine(Graphics& g, PointF a, PointF b, Color c, float width, bool dashed = false) {
    Stroke(g, {a, PointF(a.X + (b.X - a.X) / 3, a.Y + (b.Y - a.Y) / 3), PointF(a.X + (b.X - a.X) * 2 / 3, a.Y + (b.Y - a.Y) * 2 / 3), b}, c, width, dashed);
}

void Arrow(Graphics& g, PointF tip, PointF from, Color c, float size) {
    float ang = atan2f(tip.Y - from.Y, tip.X - from.X);
    PointF p[3] = {tip, PointF(tip.X - size * cosf(ang - 0.42f), tip.Y - size * sinf(ang - 0.42f)),
                   PointF(tip.X - size * cosf(ang + 0.42f), tip.Y - size * sinf(ang + 0.42f))};
    SolidBrush br(c);
    g.FillPolygon(&br, p, 3);
}

void Glow(Graphics& g, float x, float y, float w, float h, bool green = false) {
    Draw(g, Img(green ? L"glow_green.png" : L"glow_gold.png"), x, y, w, h);
}

void Pin(Graphics& g, float x, float y, float z, bool below) {
    float r = 6 * std::max(z, .8f);
    GraphicsPath gp; gp.AddEllipse(x - 22, y - 22, 44.f, 44.f);
    PathGradientBrush pb(&gp);
    pb.SetCenterColor(Color(170, 255, 214, 92));
    Color sur(0, 255, 214, 92); INT one = 1;
    pb.SetSurroundColors(&sur, &one);
    g.FillPath(&pb, &gp);
    SolidBrush fill(GOLD); Pen edge(GOLD_EDGE, 1.5f);
    g.FillEllipse(&fill, x - r, y - r, 2 * r, 2 * r);
    g.DrawEllipse(&edge, x - r, y - r, 2 * r, 2 * r);
    GoldText(g, L"지금 여기", x, y + (below ? 17 : -15) * std::max(z, .8f), 12 * std::max(z, .85f));
}

// ------------------------------------------------------------------ 보기(쪽·배율)
struct ViewXf { float z = 1, ox = 0, oy = 0; bool set = false; };
ViewXf gXf[10];
int gHoverType = 0, gHoverA = -1, gHoverB = -1;
std::wstring gNote;               // 아래 띠 안내(누른 것)
bool gTitleMode = false;          // 타이틀에서 연 지도(다시보기 가능)

ViewXf& Xf() { return gXf[gPage + 1]; }

void FitPage(bool focusCurrent) {
    if (gPage < 0) return;
    auto& ch = kChapters[gPage];
    ViewXf& v = Xf();
    const float bandH = kBandBottom - CanvasTop();
    float f = std::min((kW - 50) / ch.w, (bandH - 40) / ch.h);
    if (f >= 0.8f) {
        v.z = std::min(f, 1.1f);
        v.ox = (kW - ch.w * v.z) / 2;
        v.oy = CanvasTop() + (bandH - ch.h * v.z) / 2;
        v.set = true;
        return;
    }
    v.z = 0.92f;
    float fx = 0, fy = 0;
    bool has = false;
    if (focusCurrent) {
        if (S.curChoice >= 0 && kChoices[S.curChoice].page == gPage) { auto& c = kChoices[S.curChoice]; fx = c.x + c.w / 2; fy = c.y + c.h / 2; has = true; }
        else if (S.afterChoice >= 0 && kChoices[S.afterChoice].page == gPage) { auto& c = kChoices[S.afterChoice]; fx = c.x + c.w; fy = c.y + c.h / 2; has = true; }
        else if (S.curScene >= 0 && kScenes[S.curScene].page == gPage) { auto& s = kScenes[S.curScene]; fx = s.x + s.w / 2; fy = s.y + s.h / 2; has = true; }
    }
    if (has) { v.ox = kW / 2 - fx * v.z; v.oy = CanvasTop() + bandH / 2 - fy * v.z; }
    else { v.ox = 30; v.oy = CanvasTop() + 24; }      // 장의 첫머리부터
    if (ch.w * v.z > kW - 60) v.ox = std::min(30.f, std::max(v.ox, kW - 30 - ch.w * v.z));
    else v.ox = (kW - ch.w * v.z) / 2;
    if (ch.h * v.z > bandH - 48) v.oy = std::min(CanvasTop() + 24, std::max(v.oy, kBandBottom - 24 - ch.h * v.z));
    else v.oy = CanvasTop() + (bandH - ch.h * v.z) / 2;
    v.set = true;
}

void GoPage(int p, bool focusCurrent) {
    gPage = p;
    gNote.clear();
    if (p >= 0 && (!Xf().set || focusCurrent)) FitPage(focusCurrent);
    Log("ui page " + std::to_string(p));
}

// ------------------------------------------------------------------ 머리·발
float OvalButton(Graphics& g, float cx, float cy, const std::wstring& label, bool hover, int id) {
    float w = Measure(g, label, 14, true) + 24;
    Draw(g, Img(hover ? L"oval_green.png" : L"oval_brown.png"), cx - w / 2 - 7, cy - 17, w + 14, 34);
    Text(g, label, cx, cy, 14, true, GOLD_TXT, 1, 0, &GOLD_EDGE, 1.0f, &GOLD_SHADOW);
    gHits.push_back({RectF(cx - w / 2 - 4, cy - 15, w + 8, 30), HitButton, id, 0});
    return w;
}

std::wstring Lines2(const std::wstring& a, const std::wstring& b) { return b.empty() ? a : a + L"\n" + b; }

void Chrome(Graphics& g, const std::wstring& info) {
    float xs = 284;
    int cur = CurChapter();
    for (int i = -1; i < kChapterCount; ++i) {
        std::wstring label = i < 0 ? L"전체" : kChapters[i].id;
        float fs = i < 0 ? 14.5f : 18.f;
        float w = Measure(g, label, fs, true) + 21;
        float cx = xs + w / 2, cy = 35;
        bool sel = gPage == i;
        bool seen = i < 0 || ChapterSeen(i);
        bool hov = gHoverType == HitTab && gHoverA == i;
        if (sel || hov) {
            Draw(g, Img(hov && !sel ? L"oval_green.png" : L"oval_brown.png"), cx - w / 2 - 9, cy - 19, w + 18, 38);
            Text(g, label, cx, cy, fs, true, GOLD_TXT, 1, 0, &GOLD_EDGE, 1.0f, &GOLD_SHADOW);
        } else {
            Text(g, label, cx, cy, fs, true, seen ? INK : INK_LOCK, 1);
        }
        if (i >= 0 && i == cur) {
            SolidBrush b(Color(255, 222, 156, 18)); Pen p(Color(255, 110, 62, 0), 1.f);
            g.FillEllipse(&b, cx - 3.5f, cy + 15, 7.f, 7.f); g.DrawEllipse(&p, cx - 3.5f, cy + 15, 7.f, 7.f);
        }
        gHits.push_back({RectF(xs, cy - 18, w, 36), HitTab, i, 0});
        xs += w;
    }
    std::wstring title = gPage < 0 ? L"전체 지도" : (ChapterSeen(gPage) ? kChapters[gPage].title : L"？？？");
    Text(g, title, 289, 74, 21, true, INK, 0, 490);
    Text(g, L"이야기의 지도", 26, 556, 27, true, INK);
    // 안내 두 줄
    size_t nl = info.find(L'\n');
    std::wstring a = nl == std::wstring::npos ? info : info.substr(0, nl), b = nl == std::wstring::npos ? L"" : info.substr(nl + 1);
    if (b.empty()) Text(g, a, 236, 553, 13, false, INK_SOFT, 0, 300);
    else { Text(g, a, 236, 543, 13, false, INK_SOFT, 0, 300); Text(g, b, 236, 564, 13, false, INK_SOFT, 0, 300); }
    float bx = 552;
    const wchar_t* labels[3] = {S.all ? L"다시 가리기" : L"가린 것 보기", L"지금 자리", L"닫기"};
    for (int i = 0; i < 3; ++i) {
        float w = Measure(g, labels[i], 14, true) + 24;
        OvalButton(g, bx + w / 2, 556, labels[i], gHoverType == HitButton && gHoverA == i, i);
        bx += w + 5;
    }
}

// ------------------------------------------------------------------ 전체 지도
const float OV_PW = 214, OV_PH = 86;
PointF OvPos(int i) {
    static const int order[9][2] = {{0, 0}, {0, 1}, {0, 2}, {1, 2}, {1, 1}, {1, 0}, {2, 0}, {2, 1}, {2, 2}};
    static const float xs[3] = {44, 293, 542}, ys[3] = {140, 263, 386};
    return PointF(xs[order[i][1]], ys[order[i][0]]);
}

void ChapterCounts(int c, int& done, int& total, int& seenCh, int& nch) {
    done = total = seenCh = nch = 0;
    for (int si : kChapters[c].order) {
        ++total;
        done += S.sceneDone[si] ? 1 : 0;
    }
    for (size_t d = 0; d < kChoices.size(); ++d)
        if (kChoices[d].chapter == c) { ++nch; seenCh += S.reached[d] ? 1 : 0; }
}

void Overview(Graphics& g) {
    int cur = CurChapter();
    const std::set<int>& runCh = S.runChapters;
    for (int i = 0; i + 1 < kChapterCount; ++i) {
        PointF a = OvPos(i), b = OvPos(i + 1);
        bool seen = ChapterSeen(i) && ChapterSeen(i + 1);
        bool run = runCh.count(i) && (runCh.count(i + 1) || i + 1 == cur);
        Color c = run ? GOLD : seen ? CREAM : FAINT;
        float wd = run ? 4.4f : 2.6f;
        if (fabsf(a.Y - b.Y) < 1) {
            float l = std::min(a.X, b.X), r = std::max(a.X, b.X);
            StrokeLine(g, PointF(l + OV_PW, a.Y + OV_PH / 2), PointF(r, a.Y + OV_PH / 2), c, wd, !seen);
        } else {
            PointF pa(a.X + OV_PW / 2, a.Y + OV_PH), pb(b.X + OV_PW / 2, b.Y);
            Stroke(g, {pa, PointF(pa.X, pa.Y + 30), PointF(pb.X, pb.Y - 30), pb}, c, wd, !seen, 6, 6);
        }
    }
    for (int i = 0; i < kChapterCount; ++i) {
        PointF p = OvPos(i);
        bool seen = ChapterSeen(i);
        bool hov = gHoverType == HitPlate && gHoverA == i;
        if (i == cur) Glow(g, p.X - 24, p.Y - 22, OV_PW + 48, OV_PH + 44);
        else if (hov) Glow(g, p.X - 22, p.Y - 20, OV_PW + 44, OV_PH + 40, true);
        Draw(g, Img(seen ? L"plate_lit.png" : L"plate_dim.png"), p.X, p.Y, OV_PW, OV_PH);
        Text(g, kChapters[i].id, p.X + 22, p.Y + 27, 20, true, seen ? INK : INK_DIM);
        float nx = p.X + 22 + Measure(g, kChapters[i].id, 20, true) + 10;
        Text(g, seen ? kChapters[i].title : L"？？？", nx, p.Y + 27, 15.5f, true, seen ? INK : INK_DIM, 0, p.X + OV_PW - 36 - nx);
        if (seen) {
            int done, total, sc, nch;
            ChapterCounts(i, done, total, sc, nch);
            std::wstring t = L"이야기 " + std::to_wstring(done) + L"/" + std::to_wstring(total);
            if (nch) t += L"  ·  선택 " + std::to_wstring(sc) + L"/" + std::to_wstring(nch);
            Text(g, t, p.X + 24, p.Y + 68, 11.5f, false, INK_SOFT);
            if (done == total && sc == nch) Check(g, p.X + OV_PW - 31, p.Y + 17, 15, INK, 2.6f);
        }
        Text(g, ChapterSummarySeen(i) ? kChapters[i].shortSummary : L"완독 후 요약 공개",
             p.X + 24, p.Y + 47, 12.5f, false, seen ? INK_SOFT : INK_DIM, 0, OV_PW - 46);
        if (i == cur) GoldText(g, L"지금 여기", p.X + OV_PW / 2, p.Y - 11, 12.5f);
        gHits.push_back({RectF(p.X, p.Y, OV_PW, OV_PH), HitPlate, i, 0});
    }
}

// ------------------------------------------------------------------ 장 쪽
struct T { float z, ox, oy; PointF operator()(float x, float y) const { return PointF(ox + x * z, oy + y * z); } };

void DrawChoice(Graphics& g, int d, const T& t, std::vector<std::pair<int, int>>& tagsOut);

void ChapterPage(Graphics& g) {
    auto& ch = kChapters[gPage];
    if (!ChapterSeen(gPage)) {
        float w = 360, h = 70, x = (kW - w) / 2, y = (CanvasTop() + kBandBottom) / 2 - h / 2;
        Draw(g, Img(L"plate_dim.png"), x, y, w, h);
        Text(g, L"아직 펼쳐지지 않은 장입니다", kW / 2, y + h / 2, 16, true, INK_DIM, 1);
        return;
    }
    ViewXf& v = Xf();
    T t{v.z, v.ox, v.oy};
    float z = v.z, lw = std::max(z, .65f);
    // 이야기 차례 선
    for (size_t k = 0; k + 1 < ch.order.size(); ++k) {
        int a = ch.order[k], b = ch.order[k + 1];
        auto &ra = kScenes[a], &rb = kScenes[b];
        bool run = S.runScenes.count(a) && (S.runScenes.count(b) || b == S.curScene);
        bool seen = SceneSeen(a) && SceneSeen(b);
        Color c = run ? GOLD : seen ? CREAM : FAINT;
        float wd = (run ? 4.f : 2.2f) * lw;
        if (fabsf(ra.y - rb.y) < 1) {
            const SceneDisp& l = ra.x < rb.x ? ra : rb; const SceneDisp& r = ra.x < rb.x ? rb : ra;
            StrokeLine(g, t(l.x + l.w, l.y + l.h / 2), t(r.x, r.y + r.h / 2), c, wd, !seen);
        } else {
            PointF pa = t(ra.x + ra.w / 2, ra.y + ra.h), pb = t(rb.x + rb.w / 2, rb.y);
            Stroke(g, {pa, PointF(pa.X, pa.Y + 26 * z), PointF(pb.X, pb.Y - 26 * z), pb}, c, wd, !seen);
        }
    }
    // 명판
    for (int si : ch.order) {
        auto& s = kScenes[si];
        PointF p = t(s.x, s.y);
        float w = s.w * z, h = s.h * z;
        bool seen = SceneSeen(si);
        bool hov = gHoverType == HitScene && gHoverA == si;
        if (si == S.curScene) Glow(g, p.X - 22 * z, p.Y - 20 * z, w + 44 * z, h + 40 * z);
        else if (hov) Glow(g, p.X - 20 * z, p.Y - 18 * z, w + 40 * z, h + 36 * z, true);
        Draw(g, Img(seen ? L"plate_lit.png" : L"plate_dim.png"), p.X, p.Y, w, h);
        bool done = seen && S.sceneDone[si];
        float tx = p.X + (done ? 27 : 14) * z;
        Text(g, seen ? s.title : L"？？？", tx, p.Y + h / 2 + 1 * z, 14 * z, true, seen ? INK : INK_DIM, 0, w - (done ? 40 : 27) * z);
        if (done) Check(g, p.X + 10 * z, p.Y + h / 2 - 7 * z, 12.5f * z, INK, 2.4f * z);
        else if (seen && !S.all) {
            float fr = S.sceneFrac[si];
            if (fr > 0 && fr < 1) StrokeLine(g, PointF(p.X + 14 * z, p.Y + h - 8.5f * z), PointF(p.X + 14 * z + (w - 28 * z) * fr, p.Y + h - 8.5f * z), PROGRESS, 2.2f * z);
        }
        if (si == S.curScene && S.curChoice < 0 && S.afterChoice < 0) Pin(g, p.X + 24 * z, p.Y - 1 * z, z, false);
        gHits.push_back({RectF(p.X, p.Y, w, h), HitScene, si, 0});
    }
    // 선택 묶음
    for (auto& cl : kClusters) {
        if (cl.page != gPage) continue;
        int first = -1;
        for (size_t d = 0; d < kChoices.size(); ++d)
            if (kChoices[d].page == gPage && kChoices[d].cluster == cl.index &&
                (first < 0 || kChoices[d].x < kChoices[first].x || (kChoices[d].x == kChoices[first].x && kChoices[d].y < kChoices[first].y)))
                first = (int)d;
        if (first < 0) continue;
        auto& s = kScenes[cl.scene];
        auto& fc = kChoices[first];
        PointF pa = cl.anchorRight ? t(s.x + s.w, s.y + s.h / 2) : t(s.x + 34, s.y + s.h);
        PointF pb = t(fc.x, fc.y + kQH / 2);
        bool seen = ChoiceSeen(first);
        bool run = S.runPick[first] >= 0 || S.curChoice == first;
        Bz b = cl.anchorRight ? Bz{pa, PointF(pa.X + 30 * z, pa.Y), PointF(pb.X - 30 * z, pb.Y), pb}
                              : Bz{pa, PointF(pa.X, pb.Y), PointF(pb.X - 30 * z, pb.Y), pb};
        Stroke(g, b, run ? GOLD : seen ? CREAM : FAINT, (run ? 3.8f : 2.2f) * lw, !seen);
        std::vector<std::pair<int, int>> tags;
        for (size_t d = 0; d < kChoices.size(); ++d)
            if (kChoices[d].page == gPage && kChoices[d].cluster == cl.index) DrawChoice(g, (int)d, t, tags);
    }
}

void DrawChoice(Graphics& g, int d, const T& t, std::vector<std::pair<int, int>>&) {
    auto& c = kChoices[d];
    float z = t.z, lw = std::max(z, .65f);
    PointF p = t(c.x, c.y);
    float w = c.w * z, qh = kQH * z, lh = kLH * z;
    bool reached = ChoiceSeen(d);
    bool hovQ = gHoverType == HitQuestion && gHoverA == d;
    if (S.curChoice == d) Glow(g, p.X - 22 * z, p.Y - 22 * z, w + 44 * z, c.h * z + 44 * z);
    else if (hovQ) Glow(g, p.X - 18 * z, p.Y - 16 * z, w + 36 * z, qh + 32 * z, true);
    Draw3(g, Img(reached ? L"q_lit.png" : L"q_dim.png"), p.X, p.Y, w, qh, 40);
    std::wstring q = gQuestion[d].empty() ? L"……" : gQuestion[d];
    Text(g, reached ? q : L"？？？", p.X + 15 * z, p.Y + qh / 2 + 1 * z, 13 * z, true, reached ? INK : INK_DIM, 0, w - 30 * z);
    gHits.push_back({RectF(p.X, p.Y, w, qh), HitQuestion, d, 0});
    if (S.curChoice == d) Pin(g, p.X + w - 26 * z, p.Y - 2 * z, z, false);
    for (size_t k = 0; k < c.options.size(); ++k) {
        auto& o = c.options[k];
        float ly = p.Y + qh + 3 * z + k * lh, lx = p.X + 10 * z, lww = w - 10 * z;
        bool chosen = Chosen(d, (int)k);
        bool thisRun = S.runPick[d] == (int)k;
        bool hov = gHoverType == HitOption && gHoverA == d && gHoverB == (int)k;
        if (thisRun) Glow(g, lx - 14 * z, ly - 9 * z, lww + 28 * z, lh + 18 * z);
        else if (hov) Glow(g, lx - 14 * z, ly - 9 * z, lww + 28 * z, lh + 18 * z, true);
        const wchar_t* leaf = (thisRun || hov) ? L"leaf_hi.png" : (chosen || S.all) ? L"leaf_lit.png" : L"leaf_dim.png";
        Draw(g, Img(leaf), lx, ly + 1 * z, lww, lh - 2 * z);
        std::wstring label = reached ? gOptLabel[d][k] : L"？？？";
        Color col = thisRun ? GOLD_TXT : (chosen || S.all) ? WHITE : LEAF_DIM_TXT;
        Color edge = thisRun ? GOLD_EDGE : (chosen || S.all) ? LEAF_EDGE : LEAF_DIM_EDGE;
        float tx = lx + ((chosen && !thisRun) ? 25 : 13) * z;
        Text(g, label, tx, ly + lh / 2, 12.5f * z, true, col, 0, lww * 0.68f, &edge, 1.5f * z);
        if (chosen && !thisRun) Check(g, lx + 9 * z, ly + lh / 2 - 5.5f * z, 10.5f * z, CHECK_LEAF, 2.2f * z);
        gHits.push_back({RectF(lx, ly, lww, lh), HitOption, d, (int)k});
        if (!(S.all || chosen)) continue;
        // 결과
        float ex = lx + lww - 2 * z, ey = ly + lh / 2;
        bool curHere = S.afterChoice == d && S.afterOption == (int)k;
        std::vector<std::pair<std::wstring, Color>> tags;
        bool edgeOut = false;
        for (auto& oc : o.outs) {
            if ((oc.kind == OutChoice || oc.kind == OutBack) && oc.target >= 0 && kChoices[oc.target].page == gPage) {
                edgeOut = true;
                auto& tc = kChoices[oc.target];
                PointF tp = t(tc.x, tc.y + kQH / 2);
                bool destSeen = ChoiceSeen(oc.target);
                bool gold = thisRun && (S.runPick[oc.target] >= 0 || S.curChoice == oc.target);
                Bz b;
                // 잎 끝에서 결과 표시 자리(RUN)만큼 수평으로 나간 뒤 꺾는다 — 이웃 잎의 표시를 가로지르지 않게
                const float RUN = 58 * z;
                if (tp.X > ex + RUN + 8) {
                    StrokeLine(g, PointF(ex, ey), PointF(ex + RUN, ey), (thisRun && S.runPick[oc.target] >= 0) ? GOLD : CREAM,
                               ((thisRun && S.runPick[oc.target] >= 0) ? 3.8f : 2.0f) * lw, !destSeen && !S.all && !curHere);
                    b = {PointF(ex + RUN, ey), PointF(ex + RUN + 34 * z, ey), PointF(tp.X - 34 * z, tp.Y), PointF(tp.X - 2, tp.Y)};
                } else if (tp.X > ex + 4) {
                    b = {PointF(ex, ey), PointF(ex + 44 * z, ey), PointF(tp.X - 44 * z, tp.Y), PointF(tp.X - 2, tp.Y)};
                } else {
                    // 되돌아가는 간선: 칸 아래로 돌아 앞 칸으로
                    float low = 0;
                    for (auto& cc : kChoices) if (cc.page == gPage && cc.cluster == c.cluster) low = std::max(low, t(0, cc.y + cc.h).Y);
                    float yy = low + 18 * z, mx = (ex + tp.X) / 2;
                    Bz b1{PointF(ex, ey), PointF(ex + 50 * z, ey), PointF(ex + 50 * z, yy), PointF(mx, yy)};
                    Bz b2{PointF(mx, yy), PointF(tp.X - 50 * z, yy), PointF(tp.X - 50 * z, tp.Y), PointF(tp.X - 2, tp.Y)};
                    Color col2 = gold ? GOLD : CREAM;
                    bool dashed = !destSeen && !S.all;
                    Stroke(g, b1, col2, (gold ? 3.8f : 2.1f) * lw, true, 7, 5);
                    Stroke(g, b2, col2, (gold ? 3.8f : 2.1f) * lw, true, 7, 5);
                    if (!dashed) Arrow(g, b2.p3, BzAt(b2, 0.9f), col2, 8 * lw);
                    continue;
                }
                if (curHere && !destSeen) {
                    Bz l, r; BzSplit(b, 0.12f, l, r);
                    StrokeLine(g, PointF(ex, ey), b.p0, GOLD, 3.8f * lw);
                    Stroke(g, l, GOLD, 3.8f * lw);
                    Stroke(g, r, CREAM, 2.0f * lw, true);
                    Pin(g, b.p0.X, b.p0.Y, z, true);
                } else if (!destSeen && !S.all) {
                    Stroke(g, b, CREAM, 2.0f * lw, true);
                } else {
                    Color col2 = gold ? GOLD : CREAM;
                    Stroke(g, b, col2, (gold ? 3.8f : 2.1f) * lw, oc.kind == OutBack, 7, 5);
                    Arrow(g, b.p3, BzAt(b, 0.92f), col2, 8 * lw);
                }
            } else if (oc.kind == OutEnd) tags.push_back({L"이어짐", CREAM});
            else if (oc.kind == OutRestart) tags.push_back({L"다시 시작", RUST});
            else if (oc.kind == OutStop) tags.push_back({L"이야기 끝", RUST});
            else if (oc.kind == OutChoice || oc.kind == OutBack) tags.push_back({L"↩ 앞으로", CREAM});
        }
        float tx3 = ex + 8 * z;
        std::set<std::wstring> seenTags;
        for (auto& tg : tags) {
            if (!seenTags.insert(tg.first).second) continue;
            float fs = 11.5f * std::max(z, .8f);
            float tw = Measure(g, tg.first, fs, true);
            GraphicsPath pill;
            float ph = fs + 6, px = tx3 - 4, py = ey - ph / 2, pw = tw + 8, r = ph / 2;
            pill.AddArc(px, py, ph, ph, 90, 180); pill.AddArc(px + pw - ph, py, ph, ph, 270, 180); pill.CloseFigure();
            SolidBrush pb(Color(170, 10, 14, 10)); g.FillPath(&pb, &pill);
            Text(g, tg.first, tx3, ey, fs, true, tg.second, 0, 0, &TAG_EDGE, 1.2f);
            tx3 += tw + 12;
        }
        if (curHere && !edgeOut) Pin(g, tx3 + 14 * z, ey, z, true);
    }
}

// ------------------------------------------------------------------ 다시보기 대상
// 타이틀에서 연 지도에서만: 이야기 명판·갈림길을 누르면 그 장면을 처음부터 재생한다(본 것만, 가린 것 보기면 모두).
int PlayScriptFor(int type, int a) {
    if (type == HitScene && a >= 0 && kScenes[a].kind != 2 && SceneSeen(a)) return kScenes[a].script;
    if ((type == HitQuestion || type == HitOption) && a >= 0 && ChoiceSeen(a)) return kScenes[kChoices[a].scene].script;
    return 0;
}

// ------------------------------------------------------------------ 안내 문구
std::wstring Quote(const std::wstring& s) { return L"「" + s + L"」"; }

std::wstring OutcomeText(int d, int k) {
    auto& o = kChoices[d].options[k];
    std::wstring r;
    for (auto& oc : o.outs) {
        std::wstring part;
        if (oc.kind == OutChoice && oc.target >= 0) part = ChoiceSeen(oc.target) ? L"다음 갈림길 " + Quote(gQuestion[oc.target]) : L"다음 갈림길로";
        else if (oc.kind == OutBack) part = L"앞 목록으로 돌아감";
        else if (oc.kind == OutEnd) part = L"이야기가 이어짐";
        else if (oc.kind == OutRestart) part = L"실패 — 장을 다시 시작";
        else if (oc.kind == OutStop) part = L"이야기가 여기서 끝남";
        if (!part.empty() && r.find(part) == std::wstring::npos) r += (r.empty() ? L"→ " : L" / ") + part;
    }
    return r;
}

std::wstring InfoText() {
    if (gHoverType == HitOption) {
        int d = gHoverA, k = gHoverB;
        if (!ChoiceSeen(d)) return L"아직 닿지 않은 갈림길입니다.";
        std::wstring st = S.runPick[d] == k ? (S.runInferred[d] ? L"이번 회차에 고름(세이브에 남은 기록)" : L"이번 회차에 고름") : Chosen(d, k) ? L"고른 적 있음" : L"아직 고르지 않음";
        std::wstring l1 = Quote(gOptLabel[d][k]) + L" · " + st;
        std::wstring l2;
        if (gTitleMode && !(S.all || Chosen(d, k))) return Lines2(l1, L"누르면 「" + std::wstring(kScenes[kChoices[d].scene].title) + L"」을 처음부터 다시 봅니다.");
        if (S.all || Chosen(d, k)) {
            l2 = OutcomeText(d, k);
            int tags = kChoices[d].options[k].tags;
            if (tags & TagRandom) l2 += L" (주사위 운)";
            else if (tags & TagCond) l2 += L" (앞선 선택에 따라)";
        }
        return Lines2(l1, l2);
    }
    if (gHoverType == HitQuestion) {
        int d = gHoverA;
        if (!ChoiceSeen(d)) return L"아직 닿지 않은 갈림길입니다.";
        int n = (int)kChoices[d].options.size(), c = 0;
        for (int k = 0; k < n; ++k) c += Chosen(d, k) ? 1 : 0;
        if (gTitleMode) return Lines2(Quote(gQuestion[d]) + L" · 고른 적 있는 선택지 " + std::to_wstring(c) + L"/" + std::to_wstring(n),
                                      L"누르면 이 갈림길이 있는 「" + std::wstring(kScenes[kChoices[d].scene].title) + L"」을 처음부터 다시 봅니다.");
        return Lines2(Quote(gQuestion[d]), L"선택지 " + std::to_wstring(n) + L"개 중 고른 적 있는 것 " + std::to_wstring(c) + L"개");
    }
    if (gHoverType == HitScene) {
        int s = gHoverA;
        if (!SceneSeen(s)) return L"아직 읽지 않은 이야기입니다.";
        std::wstring st = S.sceneDone[s] ? L"끝까지 읽음" : S.sceneFrac[s] > 0 ? L"읽은 곳 " + std::to_wstring((int)lround(S.sceneFrac[s] * 100)) + L"%" : L"읽는 중";
        if (gTitleMode) return Lines2(Quote(kScenes[s].title) + L" · " + st, L"누르면 이 이야기를 처음부터 다시 봅니다. 다 보면 지도로 돌아옵니다.");
        return Lines2(Quote(kScenes[s].title) + L" · " + st, s == S.curScene ? L"지금 이 이야기를 읽고 있습니다." : L"");
    }
    if (gHoverType == HitPlate) {
        int c = gHoverA;
        if (!ChapterSeen(c)) return L"아직 펼쳐지지 않은 장입니다.";
        return Lines2(std::wstring(kChapters[c].id) + L"  " + kChapters[c].title, L"누르면 이 장의 이야기 차례와 갈림길이 펼쳐집니다.");
    }
    if (gHoverType == HitButton) {
        if (gHoverA == 0) return S.all ? L"가린 이름과 갈림길, 장 요약을 다시 가립니다." : Lines2(L"아직 닿지 않은 이름과 갈림길, 장 요약까지 보여 줍니다.", L"진행 기록은 바뀌지 않습니다.");
        if (gHoverA == 1) return L"지금 읽고 있는 자리로 갑니다.";
        return L"지도를 닫고 이야기로 돌아갑니다. (Esc · F8)";
    }
    if (gHoverType == HitTab) return gHoverA < 0 ? L"아홉 장을 한눈에 봅니다." : (ChapterSeen(gHoverA) ? std::wstring(kChapters[gHoverA].id) + L"  " + kChapters[gHoverA].title : L"아직 펼쳐지지 않은 장입니다.");
    if (!gNote.empty()) return gNote;
    if (gTitleMode && gPage < 0) return Lines2(L"장을 누르면 이야기 차례와 갈림길이 펼쳐집니다.", L"이야기를 누르면 처음부터 다시 보고, 다 보면 지도로 돌아옵니다.");
    if (gTitleMode) return Lines2(L"이야기 명판이나 갈림길을 누르면 그 장면을 처음부터 다시 봅니다.", L"휠: 장 넘기기 · Ctrl+휠: 확대 · 끌기: 옮기기 · 0: 맞춤");
    if (gPage < 0) return Lines2(L"장을 누르면 그 장의 이야기 차례와 갈림길이 펼쳐집니다.", L"금빛은 이번 회차, ✓ 는 끝까지 읽은 이야기입니다.");
    if (!S.runKnown && S.curScene >= 0) return Lines2(L"이 세이브는 지도 기록 없이 저장돼, 게임이 남긴 선택만 금빛으로 칠합니다.", L"휠: 장 넘기기 · Ctrl+휠: 확대 · 끌기: 옮기기 · 0: 맞춤");
    return Lines2(L"선택지에 마우스를 올리면 고른 뒤 이어진 곳이 여기 나옵니다.", L"휠: 장 넘기기 · Ctrl+휠: 확대 · 끌기: 옮기기 · 0: 맞춤");
}

// 장 요약: 차트의 확대/이동에 영향을 받지 않는 읽기 영역.
std::vector<std::wstring> SummaryLines(Graphics& g, int c) {
    std::wistringstream words(kChapters[c].summary);
    std::vector<std::wstring> lines;
    std::wstring word, line;
    while (words >> word) {
        std::wstring next = line.empty() ? word : line + L" " + word;
        if (!line.empty() && Measure(g, next, 14, false) > 710) { lines.push_back(line); line = word; }
        else line = next;
    }
    if (!line.empty()) lines.push_back(line);
    return lines;
}
void ChapterSummary(Graphics& g) {
    Draw3(g, Img(L"q_lit.png"), 20, 114, 760, 96, 40);
    Text(g, L"이 장의 이야기", 43, 132, 13, true, INK);
    if (!ChapterSummarySeen(gPage)) {
        Text(g, L"이 장을 끝까지 읽으면 요약이 열립니다.", 43, 158, 14, false, INK_SOFT);
        Text(g, L"미리 읽으려면 아래의 「가린 것 보기」를 눌러 주세요.", 43, 182, 13, false, INK_SOFT);
        return;
    }
    auto lines = SummaryLines(g, gPage);
    for (size_t i = 0; i < lines.size(); ++i)
        Text(g, lines[i], 43, 153 + 20 * i, 14, false, INK);
}

// ------------------------------------------------------------------ 한 화면 그리기
std::unique_ptr<Bitmap> gBack;
// 지도 판(800×600 PARGB)을 DIB 메모리 위에 둔다 → 늘리기·창으로 옮기기가 그 메모리를 바로 읽는다(11-24 「지도가 느리다」).
HBITMAP gBackDib = nullptr; HDC gBackDC = nullptr; uint32_t* gBackBits = nullptr;
void EnsureBack() {
    if (gBack) return;
    BITMAPINFO bi = {}; bi.bmiHeader.biSize = sizeof(bi.bmiHeader); bi.bmiHeader.biWidth = (LONG)kW; bi.bmiHeader.biHeight = -(LONG)kH; bi.bmiHeader.biPlanes = 1; bi.bmiHeader.biBitCount = 32;
    void* bits = nullptr;
    gBackDib = CreateDIBSection(nullptr, &bi, DIB_RGB_COLORS, &bits, nullptr, 0);
    if (gBackDib && bits) {
        gBackBits = (uint32_t*)bits;
        gBackDC = CreateCompatibleDC(nullptr);
        if (gBackDC) SelectObject(gBackDC, gBackDib);
        gBack.reset(new Bitmap((INT)kW, (INT)kH, (INT)kW * 4, PixelFormat32bppPARGB, (BYTE*)bits));
    } else {
        if (gBackDib) DeleteObject(gBackDib);
        gBackDib = nullptr; gBackBits = nullptr;
        gBack.reset(new Bitmap((INT)kW, (INT)kH, PixelFormat32bppPARGB));   // DIB 를 못 만들면 예전대로
    }
}
// 바탕·앞 그림(frame_bg·frame_fg, 800×600)은 늘 1:1 이다. 예전엔 장마다 높은 품질 보간 + 형식 바꾸기로 한 장에 30ms 씩 들었다
// → 처음 한 번 같은 설정으로 PARGB 판에 그려 두고, 그 뒤로는 보간 없이 그대로 옮긴다.
// 앞 그림은 위·아래 띠에만 그림이 있다(가운데 약 370줄은 완전히 투명) → 그림이 있는 줄 범위만 섞는다.
struct FrameImg { std::unique_ptr<Bitmap> bmp; std::vector<std::pair<int, int>> rows; bool ready = false; };
FrameImg gFrameBg, gFrameFg;
FrameImg* FrameP(FrameImg& slot, const wchar_t* name) {
    if (slot.ready) return slot.bmp ? &slot : nullptr;
    slot.ready = true;
    Bitmap* src = Img(name);
    if (!src) return nullptr;
    std::unique_ptr<Bitmap> b(new Bitmap((INT)kW, (INT)kH, PixelFormat32bppPARGB));
    {
        Graphics g(b.get());
        g.SetCompositingMode(CompositingModeSourceCopy);
        g.SetInterpolationMode(InterpolationModeHighQualityBicubic);
        g.SetPixelOffsetMode(PixelOffsetModeHalf);
        g.DrawImage(src, RectF(0, 0, kW, kH));
    }
    // 알파가 있는 줄 범위(4줄 안 틈은 잇는다)
    BitmapData bd; Rect rr(0, 0, (INT)kW, (INT)kH);
    if (b->LockBits(&rr, ImageLockModeRead, PixelFormat32bppPARGB, &bd) == Ok) {
        int y0 = -1, last = -100;
        for (int y = 0; y < (int)kH; ++y) {
            const uint32_t* row = (const uint32_t*)((const uint8_t*)bd.Scan0 + (size_t)y * bd.Stride);
            bool any = false;
            for (int x = 0; x < (int)kW && !any; ++x) any = (row[x] >> 24) != 0;
            if (!any) continue;
            if (y0 < 0) y0 = y;
            else if (y - last > 4) { slot.rows.push_back({y0, last + 1}); y0 = y; }
            last = y;
        }
        if (y0 >= 0) slot.rows.push_back({y0, last + 1});
        b->UnlockBits(&bd);
    } else slot.rows.push_back({0, (int)kH});
    slot.bmp = std::move(b);
    return &slot;
}
void DrawFrame(Graphics& g, FrameImg* f, bool copy) {
    if (!f || !f->bmp) return;
    InterpolationMode im = g.GetInterpolationMode(); PixelOffsetMode po = g.GetPixelOffsetMode(); CompositingMode cm = g.GetCompositingMode();
    g.SetInterpolationMode(InterpolationModeNearestNeighbor); g.SetPixelOffsetMode(PixelOffsetModeNone);
    if (copy) g.SetCompositingMode(CompositingModeSourceCopy);
    if (copy) g.DrawImage(f->bmp.get(), Rect(0, 0, (INT)kW, (INT)kH), 0, 0, (INT)kW, (INT)kH, UnitPixel);
    else for (auto& r : f->rows) g.DrawImage(f->bmp.get(), Rect(0, r.first, (INT)kW, r.second - r.first), 0, r.first, (INT)kW, r.second - r.first, UnitPixel);
    g.SetInterpolationMode(im); g.SetPixelOffsetMode(po); g.SetCompositingMode(cm);
}

// 그리기 시간 재기(11-24 사용자 「이야기 지도만 들어가면 너무 느려져」): 토막별 µs 누적.
// 0 바탕 1 장·전체 쪽 2 앞 그림 3 머리·발 4 요약 5 늘려 옮기기(창 크기)
LONGLONG gQf = 0; double gTUs[6] = {}; int gTN = 0;
LONGLONG Qpc() { LARGE_INTEGER q; QueryPerformanceCounter(&q); if (!gQf) { LARGE_INTEGER f; QueryPerformanceFrequency(&f); gQf = f.QuadPart; } return q.QuadPart; }
double UsSince(LONGLONG t) { return (Qpc() - t) * 1e6 / (double)gQf; }

void Paint() {
    EnsureBack();
    Graphics g(gBack.get());
    g.SetSmoothingMode(SmoothingModeAntiAlias);
    g.SetInterpolationMode(InterpolationModeHighQualityBicubic);
    g.SetPixelOffsetMode(PixelOffsetModeHalf);
    g.SetTextRenderingHint(TextRenderingHintAntiAlias);
    g.SetCompositingQuality(CompositingQualityHighQuality);
    gHits.clear();
    LONGLONG t = Qpc();
    DrawFrame(g, FrameP(gFrameBg, L"frame_bg.png"), true);
    gTUs[0] += UsSince(t); t = Qpc();
    Clip(g, true);
    if (gPage < 0) Overview(g); else ChapterPage(g);
    Clip(g, false);
    gTUs[1] += UsSince(t); t = Qpc();
    // 찢긴 종이 밑으로 들어간 칸은 누를 수 없게
    for (auto& h : gHits) if (h.type != HitTab && h.type != HitButton) {
        float top = std::max(h.r.Y, gPage < 0 ? kBandTop - 18 : kChapterTop - 12), bottom = std::min(h.r.Y + h.r.Height, kBandBottom + 18);
        h.r.Height = std::max(0.f, bottom - top); h.r.Y = top;
    }
    DrawFrame(g, FrameP(gFrameFg, L"frame_fg.png"), false);
    gTUs[2] += UsSince(t); t = Qpc();
    Chrome(g, InfoText());
    gTUs[3] += UsSince(t); t = Qpc();
    if (gPage >= 0) ChapterSummary(g);
    gTUs[4] += UsSince(t);
}

// ------------------------------------------------------------------ 게임 창 안 덧그리기
// 지도는 별도 창이 아니라 게임 창 안에 그린다. 모든 처리는 게임 창 스레드에서 한다.
// 스크립트(VM) 스레드는 입력 대기 지점에서 멈춰 기다리므로 게임 창 스레드는 평소처럼 돈다.
HWND gGame = nullptr;
std::atomic<bool> gOpen{false};
void (*gOnClosed)(int) = nullptr;
bool gDown = false, gMoved = false;
POINT gDownPt{}, gLastPt{};

void ClientMap(HWND h, float& s, float& ox, float& oy) {
    RECT r; GetClientRect(h, &r);
    float cw = (float)(r.right - r.left), chh = (float)(r.bottom - r.top);
    s = std::min(cw / kW, chh / kH);
    if (s <= 0) s = 1;
    ox = (cw - kW * s) / 2; oy = (chh - kH * s) / 2;
}
PointF ToLogical(HWND h, int x, int y) {
    float s, ox, oy; ClientMap(h, s, ox, oy);
    return PointF((x - ox) / s, (y - oy) / s);
}
const Hit* HitAt(PointF p) {
    for (int i = (int)gHits.size() - 1; i >= 0; --i) if (gHits[i].r.Contains(p)) return &gHits[i];
    return nullptr;
}
bool InBand(PointF p) { return p.Y > CanvasTop() - 10 && p.Y < kBandBottom + 10; }

void Redraw() { if (gOpen && gGame) InvalidateRect(gGame, nullptr, FALSE); }

// 창이 800×600 이 아닐 때(2배·3배·최대화·전체 화면)는 늘려 그리는 데 시간이 든다(3배 창에서 약 80ms).
// 예전엔 창에 바로 검게 칠한 뒤 늘려 그려서, 그동안 검은 화면이 보여 지도가 번쩍였다(11-23 사용자 「번쩍거린다」).
// → 화면 밖 판에 다 그린 뒤 창에는 한 번에 옮긴다. 판은 지도가 열려 있는 동안만 둔다.
HDC gBufDC = nullptr;
HBITMAP gBufBmp = nullptr, gBufOld = nullptr;
uint32_t* gBufBits = nullptr;   // 창 크기 판(DIB, 위→아래 BGRA)
int gBufW = 0, gBufH = 0;

void ReleasePaintBuffer() {
    if (gBufDC) { if (gBufOld) SelectObject(gBufDC, gBufOld); DeleteDC(gBufDC); }
    if (gBufBmp) DeleteObject(gBufBmp);
    gBufDC = nullptr; gBufBmp = gBufOld = nullptr; gBufBits = nullptr; gBufW = gBufH = 0;
}
bool EnsurePaintBuffer(int cw, int chh) {
    if (gBufDC && gBufBits && gBufW == cw && gBufH == chh) return true;
    ReleasePaintBuffer();
    BITMAPINFO bi = {}; bi.bmiHeader.biSize = sizeof(bi.bmiHeader); bi.bmiHeader.biWidth = cw; bi.bmiHeader.biHeight = -chh; bi.bmiHeader.biPlanes = 1; bi.bmiHeader.biBitCount = 32;
    void* bits = nullptr;
    gBufBmp = CreateDIBSection(nullptr, &bi, DIB_RGB_COLORS, &bits, nullptr, 0);
    if (!gBufBmp || !bits) { ReleasePaintBuffer(); return false; }
    gBufDC = CreateCompatibleDC(nullptr);
    if (!gBufDC) { ReleasePaintBuffer(); return false; }
    gBufOld = (HBITMAP)SelectObject(gBufDC, gBufBmp);
    gBufBits = (uint32_t*)bits; gBufW = cw; gBufH = chh;
    return true;
}

void GoCurrent() {
    int c = CurChapter();
    if (c >= 0) GoPage(c, true); else GoPage(-1, false);
}

void Prepare(const std::wstring& root) {
    if (gRoot.empty()) gRoot = root;
    StartGraphics();
    BuildMaps();
    LoadReadBits();
    ComputeState(SnapshotProgress());
    S.all = false;
    for (auto& x : gXf) x.set = false;
    gHoverType = 0; gHoverA = gHoverB = -1;
    gNote.clear();
}

void CloseChart(const char* why, int play = 0) {
    if (!gOpen) return;
    gOpen = false;
    ReleasePaintBuffer();
    if (gDown) { gDown = false; gMoved = false; if (GetCapture() == gGame) ReleaseCapture(); }
    Log(std::string("ui closed (") + why + ")" + (play ? " replay " + std::to_string(play) : std::string()));
    if (gGame) InvalidateRect(gGame, nullptr, TRUE);   // 게임이 제 화면을 다시 그리게
    if (gOnClosed) gOnClosed(play);                    // 멈춰 있던 스크립트를 놓아주거나 다시보기를 건넨다
}

void Act(const Hit& h) {
    if (h.type == HitTab) { GoPage(h.a, h.a == CurChapter()); }
    else if (h.type == HitPlate) { GoPage(h.a, h.a == CurChapter()); }
    else if (h.type == HitButton) {
        if (h.a == 0) { S.all = !S.all; Log(S.all ? "ui show hidden on" : "ui show hidden off"); }
        else if (h.a == 1) GoCurrent();
        else { CloseChart("button"); return; }
    } else if (h.type == HitOption || h.type == HitQuestion || h.type == HitScene) {
        int play = PlayScriptFor(h.type, h.a);
        if (gTitleMode && play) { CloseChart("play", play); return; }
        gNote = InfoText();
        if (!gTitleMode && play) gNote = Lines2(gNote.substr(0, gNote.find(L'\n')), L"다시보기는 타이틀 화면의 「이야기의 지도」에서 할 수 있습니다.");
    }
    Redraw();
}

void DrawScaled(Graphics& g, int cw, int chh, float s, float ox, float oy) {
    SolidBrush black(Color(255, 0, 0, 0));
    g.FillRectangle(&black, 0, 0, cw, chh);
    g.SetInterpolationMode(InterpolationModeHighQualityBilinear);
    g.DrawImage(gBack.get(), RectF(ox, oy, kW * s, kH * s));
}

// 800×600 지도 판(PARGB, 불투명)을 대상 판의 (ox,oy,w,h) 로 쌍선형 늘리기(정수 계산, 화소 가운데 맞춤). 나머지는 검정.
// GDI+ 높은 품질 쌍선형(2400×1800 에 49ms)을 대신한다(11-24).
void UpscaleBilinear(const uint32_t* src, int sw, int sh, uint32_t* dst, int dw, int dh, int ox, int oy, int w, int h) {
    if (w <= 0 || h <= 0 || sw < 2 || sh < 2) return;
    for (int y = 0; y < dh; ++y) {
        uint32_t* row = dst + (size_t)y * dw;
        if (y < oy || y >= oy + h) { memset(row, 0, (size_t)dw * 4); continue; }
        if (ox > 0) memset(row, 0, (size_t)ox * 4);
        if (ox + w < dw) memset(row + ox + w, 0, (size_t)(dw - ox - w) * 4);
    }
    std::vector<int> xi(w), xw(w);
    for (int x = 0; x < w; ++x) {
        double fx = (x + 0.5) * sw / (double)w - 0.5; if (fx < 0) fx = 0;
        int i = (int)fx; if (i >= sw - 1) { i = sw - 2; fx = sw - 1; }
        xi[x] = i; xw[x] = (int)((fx - i) * 256 + 0.5);
    }
    std::vector<uint32_t> r0(w), r1(w);
    int c0 = -1, c1 = -1;
    auto hpass = [&](int sy, std::vector<uint32_t>& out) {
        const uint32_t* s = src + (size_t)sy * sw;
        for (int x = 0; x < w; ++x) {
            uint32_t a = s[xi[x]], b = s[xi[x] + 1]; uint32_t k = (uint32_t)xw[x], k1 = 256 - k;
            uint32_t rb = (((a & 0xff00ff) * k1 + (b & 0xff00ff) * k) >> 8) & 0xff00ff;
            uint32_t ag = ((((a >> 8) & 0xff00ff) * k1 + ((b >> 8) & 0xff00ff) * k) >> 8) & 0xff00ff;
            out[x] = rb | (ag << 8);
        }
    };
    for (int y = 0; y < h; ++y) {
        if (oy + y < 0 || oy + y >= dh) continue;
        double fy = (y + 0.5) * sh / (double)h - 0.5; if (fy < 0) fy = 0;
        int j = (int)fy; if (j >= sh - 1) { j = sh - 2; fy = sh - 1; }
        uint32_t ky = (uint32_t)((fy - j) * 256 + 0.5), ky1 = 256 - ky;
        if (c0 != j) { if (c1 == j) { std::swap(r0, r1); std::swap(c0, c1); } else { hpass(j, r0); c0 = j; } }
        if (c1 != j + 1) { hpass(j + 1, r1); c1 = j + 1; }
        uint32_t* d = dst + (size_t)(oy + y) * dw + ox;
        int x0 = std::max(0, -ox), x1 = std::min(w, dw - ox);
        for (int x = x0; x < x1; ++x) {
            uint32_t a = r0[x], b = r1[x];
            uint32_t rb = (((a & 0xff00ff) * ky1 + (b & 0xff00ff) * ky) >> 8) & 0xff00ff;
            uint32_t ag = ((((a >> 8) & 0xff00ff) * ky1 + ((b >> 8) & 0xff00ff) * ky) >> 8) & 0xff00ff;
            d[x] = rb | (ag << 8);
        }
    }
}

void PaintTimingTick(int cw, int chh) {
    if (++gTN < 30) return;
    char b[256];
    snprintf(b, sizeof b, "ui paint avg ms (%d): bg %.1f page %.1f fg %.1f chrome %.1f summary %.1f scale %.1f (client %dx%d)",
             gTN, gTUs[0] / gTN / 1000, gTUs[1] / gTN / 1000, gTUs[2] / gTN / 1000, gTUs[3] / gTN / 1000, gTUs[4] / gTN / 1000, gTUs[5] / gTN / 1000, cw, chh);
    Log(b);
    for (double& v : gTUs) v = 0;
    gTN = 0;
}

void PaintTo(HWND h, HDC dc) {
    Paint();
    LONGLONG t = Qpc();
    RECT r; GetClientRect(h, &r);
    int cw = r.right - r.left, chh = r.bottom - r.top;
    if (cw <= 0 || chh <= 0) return;
    float s, ox, oy; ClientMap(h, s, ox, oy);
    if (s == 1.f && ox == 0 && oy == 0) {
        if (gBackDC) BitBlt(dc, 0, 0, (int)kW, (int)kH, gBackDC, 0, 0, SRCCOPY);
        else { Graphics sg(dc); sg.DrawImage(gBack.get(), 0, 0); }
    } else if (gBackBits && EnsurePaintBuffer(cw, chh)) {
        // 화면 밖 판에 직접 쌍선형으로 늘린 뒤 창에는 한 번에 옮긴다(번쩍임 없음, 3배 창에서 GDI+ 49ms → 약 10ms)
        int w = (int)lroundf(kW * s), hh = (int)lroundf(kH * s);
        UpscaleBilinear(gBackBits, (int)kW, (int)kH, gBufBits, cw, chh, (int)lroundf(ox), (int)lroundf(oy), w, hh);
        BitBlt(dc, 0, 0, cw, chh, gBufDC, 0, 0, SRCCOPY);
    } else {
        Graphics sg(dc); DrawScaled(sg, cw, chh, s, ox, oy);   // 판을 못 만들면 예전 길(번쩍일 수 있음)
    }
    gTUs[5] += UsSince(t);
    PaintTimingTick(cw, chh);
}

// 시험(paint_timing): 장 쪽을 n 번 그리며 칸마다 마우스를 올린 것처럼 바꾼다. out[0..4] = Paint 토막 평균 ms,
// out[5] = 지금 늘리기(높은 품질 쌍선형) cw×chh, out[6] = 보통 쌍선형, out[7] = 칸 수
void TimePaintImpl(int page, int n, int cw, int chh, double* out) {
    GoPage(page, page == CurChapter());
    for (double& v : gTUs) v = 0;
    gTN = 0;
    Paint();
    std::vector<Hit> hits = gHits;
    for (double& v : gTUs) v = 0;
    for (int i = 0; i < n; ++i) {
        gHoverType = 0; gHoverA = gHoverB = -1;
        if (!hits.empty()) { const Hit& hh = hits[i % hits.size()]; gHoverType = hh.type; gHoverA = hh.a; gHoverB = hh.b; }
        Paint();
    }
    for (int k = 0; k < 5; ++k) out[k] = gTUs[k] / n / 1000;
    out[7] = (double)hits.size();
    // 늘리기: 제품 길(gBackBits → 창 크기 DIB, 직접 쌍선형)
    float s = std::min(cw / kW, chh / kH), ox = (cw - kW * s) / 2, oy = (chh - kH * s) / 2;
    if (gBackBits && EnsurePaintBuffer(cw, chh)) {
        LONGLONG t = Qpc();
        for (int i = 0; i < n; ++i) UpscaleBilinear(gBackBits, (int)kW, (int)kH, gBufBits, cw, chh, (int)lroundf(ox), (int)lroundf(oy), (int)lroundf(kW * s), (int)lroundf(kH * s));
        out[9] = UsSince(t) / n / 1000;
        ReleasePaintBuffer();
    }
}

}  // namespace

void SetChartPaths(const std::wstring& root, const std::wstring& globalSave) { gRoot = root; gGlobalSave = globalSave; }
void SetChartVarSource(const uint16_t* (*source)()) { gVarSource = source; }
void SetChartClosedCallback(void (*fn)(int)) { gOnClosed = fn; }
bool ChartIsOpen() { return gOpen; }

// 게임 창 스레드에서: 스크립트가 입력 대기에서 멈춘 뒤 부른다.
bool ChartBegin(HWND game, int mode) {
    if (gOpen || !IsWindow(game)) return false;
    gGame = game;
    gTitleMode = mode == 1;
    wchar_t path[MAX_PATH]; GetModuleFileNameW(nullptr, path, MAX_PATH);
    std::wstring root = path; root.resize(root.find_last_of(L"\\/"));
    Prepare(root);
    if (gTitleMode) {       // 타이틀·다시보기 중엔 「이번 회차」가 없다
        S.runPick.assign(S.runPick.size(), -1); S.runInferred.assign(S.runInferred.size(), 0);
        S.runScenes.clear(); S.runChapters.clear(); S.runKnown = true;
        S.curScene = S.curChoice = S.afterChoice = S.afterOption = -1;
    }
    GoCurrent();
    gOpen = true;
    Log(gTitleMode ? "ui opened in game window (title, replay enabled)" : "ui opened in game window");
    InvalidateRect(game, nullptr, FALSE);
    return true;
}

// 게임 창 프로시저 앞에서 부른다. true 를 돌려주면 게임에는 넘기지 않는다.
bool ChartWndProc(HWND h, UINT m, WPARAM wp, LPARAM lp, LRESULT& result) {
    if (!gOpen) return false;
    result = 0;
    switch (m) {
    case WM_ERASEBKGND: result = 1; return true;
    case WM_PAINT: {
        PAINTSTRUCT ps; HDC dc = BeginPaint(h, &ps);
        PaintTo(h, dc);
        EndPaint(h, &ps);
        return true;
    }
    case WM_MOUSEMOVE: {
        PointF p = ToLogical(h, GET_X_LPARAM(lp), GET_Y_LPARAM(lp));
        if (gDown && gPage >= 0 && InBand(ToLogical(h, gDownPt.x, gDownPt.y))) {
            POINT cur{GET_X_LPARAM(lp), GET_Y_LPARAM(lp)};
            if (abs(cur.x - gDownPt.x) + abs(cur.y - gDownPt.y) > 4) gMoved = true;
            if (gMoved) {
                float s, ox, oy; ClientMap(h, s, ox, oy);
                Xf().ox += (cur.x - gLastPt.x) / s; Xf().oy += (cur.y - gLastPt.y) / s;
                gLastPt = cur; Redraw();
            }
            return true;
        }
        const Hit* hit = HitAt(p);
        int t = hit ? hit->type : 0, a = hit ? hit->a : -1, b = hit ? hit->b : -1;
        if (t != gHoverType || a != gHoverA || b != gHoverB) { gHoverType = t; gHoverA = a; gHoverB = b; Redraw(); }
        POINT cp; RECT cr;
        if (GetCursorPos(&cp) && ScreenToClient(h, &cp) && GetClientRect(h, &cr) && PtInRect(&cr, cp)) {
            TRACKMOUSEEVENT tme{sizeof(tme), TME_LEAVE, h, 0}; TrackMouseEvent(&tme);
        }
        return true;
    }
    case WM_MOUSELEAVE: gHoverType = 0; gHoverA = gHoverB = -1; Redraw(); return true;
    case WM_LBUTTONDOWN: case WM_LBUTTONDBLCLK: {
        PointF p = ToLogical(h, GET_X_LPARAM(lp), GET_Y_LPARAM(lp));
        gDownPt = gLastPt = POINT{GET_X_LPARAM(lp), GET_Y_LPARAM(lp)};
        gDown = true;
        gMoved = false;
        (void)p;
        SetCapture(h);
        return true;
    }
    case WM_LBUTTONUP: {
        PointF p = ToLogical(h, GET_X_LPARAM(lp), GET_Y_LPARAM(lp));
        bool click = !gMoved;
        bool wasDown = gDown;
        if (gMoved) Log("ui drag");
        gDown = false; gMoved = false;
        if (GetCapture() == h) ReleaseCapture();
        if (wasDown && click) if (const Hit* hit = HitAt(p)) { Hit copy = *hit; Act(copy); }
        return true;
    }
    case WM_CAPTURECHANGED: gDown = false; gMoved = false; return true;
    case WM_RBUTTONDOWN: case WM_RBUTTONDBLCLK: case WM_MBUTTONDOWN: case WM_MBUTTONUP: case WM_MBUTTONDBLCLK:
    case WM_XBUTTONDOWN: case WM_XBUTTONUP: case WM_XBUTTONDBLCLK:
        return true;
    case WM_RBUTTONUP: CloseChart("right click"); return true;   // 오른쪽 클릭 = 뒤로(게임과 같은 버릇)
    case WM_MOUSEWHEEL: {
        // 11-24 사용자: 휠 = 다른 장(시나리오)으로 넘기기, Ctrl+휠 = 확대·축소(예전엔 휠이 확대였다)
        POINT sp{GET_X_LPARAM(lp), GET_Y_LPARAM(lp)}; ScreenToClient(h, &sp);
        PointF p = ToLogical(h, sp.x, sp.y);
        int delta = GET_WHEEL_DELTA_WPARAM(wp);
        if (GET_KEYSTATE_WPARAM(wp) & MK_CONTROL) {
            if (gPage >= 0 && InBand(p) && ChapterSeen(gPage)) {
                ViewXf& v = Xf();
                float old = v.z;
                v.z = std::clamp(v.z * powf(1.15f, delta / 120.f), 0.25f, 2.2f);
                v.ox = p.X - (p.X - v.ox) * v.z / old;
                v.oy = p.Y - (p.Y - v.oy) * v.z / old;
                Redraw();
            }
            return true;
        }
        static int acc = 0;                   // 고운 휠(120 보다 작은 값)은 모아서 한 칸씩
        acc += delta;
        int steps = 0;
        while (acc >= 120) { acc -= 120; --steps; }   // 위로 = 앞 장
        while (acc <= -120) { acc += 120; ++steps; }  // 아래로 = 다음 장
        if (steps) {
            int np = std::clamp(gPage + steps, -1, kChapterCount - 1);
            if (np != gPage) { GoPage(np, false); Redraw(); }
        }
        return true;
    }
    case WM_KEYDOWN:
        if (wp == VK_ESCAPE || wp == VK_F8) { if (!(lp & (1u << 30))) CloseChart("key"); return true; }
        if (wp == VK_HOME) { GoCurrent(); Redraw(); return true; }
        if (wp == '0' || wp == VK_NUMPAD0) { if (gPage >= 0) { FitPage(false); Redraw(); } return true; }
        if (wp == VK_PRIOR) { GoPage(std::max(-1, gPage - 1), false); Redraw(); return true; }
        if (wp == VK_NEXT) { GoPage(std::min(kChapterCount - 1, gPage + 1), false); Redraw(); return true; }
        if (gPage >= 0 && (wp == VK_LEFT || wp == VK_RIGHT || wp == VK_UP || wp == VK_DOWN)) {
            Xf().ox += wp == VK_LEFT ? 60.f : wp == VK_RIGHT ? -60.f : 0.f;
            Xf().oy += wp == VK_UP ? 50.f : wp == VK_DOWN ? -50.f : 0.f;
            Redraw();
        }
        return true;
    case WM_KEYUP: case WM_CHAR: case WM_DEADCHAR:
        return true;
    case WM_SYSKEYDOWN: case WM_SYSKEYUP: case WM_SYSCHAR:
        // Alt+F4 등 창 조작은 그대로 넘긴다(닫기는 아래 WM_CLOSE 에서 지도를 먼저 닫는다)
        return false;
    case WM_CLOSE:
        CloseChart("window close");
        return false;          // 게임의 원래 종료 절차로
    case WM_SYSCOMMAND:
        if ((wp & 0xfff0) == SC_CLOSE) CloseChart("window close");
        return false;
    case WM_DESTROY:
        CloseChart("window destroyed");
        return false;
    }
    return false;
}

// 시험용: 창 없이 한 화면을 PNG 로 그린다(page -1 전체, 0~8 장).
bool TimeChartPaint(const std::wstring& root, int page, int n, int cw, int chh, double* out) {
    Prepare(root);
    TimePaintImpl(page, n, cw, chh, out);
    return true;
}

bool RenderChartPng(const std::wstring& root, int page, bool showAll, const std::wstring& outPng, int hoverType, int hoverA, int hoverB) {
    Prepare(root);
    S.all = showAll;
    if (page == -2) GoCurrent(); else GoPage(page, page == CurChapter());
    gHoverType = hoverType; gHoverA = hoverA; gHoverB = hoverB;
    Paint();
    if (gPage >= 0) {
        Graphics check(gBack.get());
        auto lines = SummaryLines(check, gPage);
        wprintf(L"SUMMARY %s %s lines=%u\n", kChapters[gPage].id,
                ChapterSummarySeen(gPage) ? L"visible" : L"locked", (unsigned)lines.size());
        if (lines.size() > 3) return false;
    }
    CLSID png{};
    UINT n = 0, size = 0;
    GetImageEncodersSize(&n, &size);
    std::vector<uint8_t> buf(size);
    auto* enc = (ImageCodecInfo*)buf.data();
    GetImageEncoders(n, size, enc);
    for (UINT i = 0; i < n; ++i) if (wcscmp(enc[i].MimeType, L"image/png") == 0) png = enc[i].Clsid;
    return gBack->Save(outPng.c_str(), &png, nullptr) == Ok;
}

}  // namespace forest
