# -*- coding: utf-8 -*-
"""qol_hiart.cpp: 4배 캐시를 공유 포인터로, 상태 합성을 뒤 스레드로."""
p = r'P:\AI\forest-qol\s-hiart\native\qol_hiart.cpp'
s = open(p, encoding='utf-8').read()


def rep(old, new, count=1):
    global s
    n = s.count(old)
    assert n == count, (n, old[:80])
    s = s.replace(old, new)


rep('struct Pre { int cw = 0, pw = 0, ph = 0; std::vector<uint32_t> px; DWORD used = 0; };',
    'using Buf = std::shared_ptr<std::vector<uint32_t>>;   // 뒤 스레드 합성이 쓰는 동안 캐시에서 빠져도 살아 있게\n'
    'struct Pre { int cw = 0, pw = 0, ph = 0; Buf px; DWORD used = 0; };')
rep('        gPreBytes -= victim->second.px.size() * 4;\n        gPre.erase(victim);',
    '        gPreBytes -= victim->second.px ? victim->second.px->size() * 4 : 0;\n        gPre.erase(victim);')
rep('                auto& p = gPre[job.first];\n                gPreBytes -= p.px.size() * 4;\n                p.cw = job.second; p.pw = pw; p.ph = ph; p.px.swap(px); p.used = GetTickCount();\n                gPreBytes += p.px.size() * 4;',
    '                auto& p = gPre[job.first];\n                gPreBytes -= p.px ? p.px->size() * 4 : 0;\n                p.cw = job.second; p.pw = pw; p.ph = ph; p.px = std::make_shared<std::vector<uint32_t>>(std::move(px)); p.used = GetTickCount();\n                gPreBytes += p.px->size() * 4;')
rep('struct LS { int idx; std::string key; int x, y, w, h; Xf xf; const Img1* one; const Pre* pre; };',
    'struct LS { int idx; std::string key; int x, y, w, h; Xf xf; const Img1* one; Buf pre; int pw = 0, ph = 0; };')
rep('        auto pit = gPre.find(key);\n        l.pre = (pit != gPre.end() && pit->second.cw == L.cw) ? &pit->second : nullptr;\n        if (l.pre) pit->second.used = GetTickCount();',
    '        auto pit = gPre.find(key);\n        if (pit != gPre.end() && pit->second.cw == L.cw) { l.pre = pit->second.px; l.pw = pit->second.pw; l.ph = pit->second.ph; pit->second.used = GetTickCount(); }')
rep('        const Pre& p = *l.pre;\n        int ry = Y - py0;\n        if (ry < 0 || ry >= p.ph) continue;\n        int a = std::max(X0, px0), b = std::min(X1, px0 + p.pw);\n        if (a >= b) continue;\n        const uint32_t* s = p.px.data() + (size_t)ry * p.pw + (a - px0);',
    '        int ry = Y - py0;\n        if (ry < 0 || ry >= l.ph) continue;\n        int a = std::max(X0, px0), b = std::min(X1, px0 + l.pw);\n        if (a >= b) continue;\n        const uint32_t* s = l.pre->data() + (size_t)ry * l.pw + (a - px0);')
rep('            auto pit = gPre.find(l.key); l.pre = (pit != gPre.end() && pit->second.cw == L.cw) ? &pit->second : nullptr;',
    '            auto pit = gPre.find(l.key);\n            if (pit != gPre.end() && pit->second.cw == L.cw) { l.pre = pit->second.px; l.pw = pit->second.pw; l.ph = pit->second.ph; } else l.pre.reset();')

# 상태 합성 캐시: 뒤 스레드가 만든다
a = s.index('// 상태마다 한 번만: 물리 크기 4배 합성(줄 단위로 처음 쓸 때 만든다). 그림이 다 준비된 상태에만.')
b = s.index('}  // namespace\n\nbool HiArt_Install() {')
s = s[:a] + '''// 상태마다 한 번만: 물리 크기 4배 합성. 엔진 스레드를 세우지 않게 뒤 스레드가 만든다(그동안 넓은 찍기는 1배).
struct C4 { std::string sig; int cw = 0, ch = 0; Buf px; DWORD used = 0; } gC4[2];
struct BuildJob { bool want = false; State st; Layout L; } gJob;
bool gDirect = false;   // 이번 찍기가 작아 그 자리에서 합성해도 되는가
bool allReady(const State& st) { for (auto& l : st.ls) if (!l.pre) return false; return !st.ls.empty(); }
C4* compOf(const State& st, const Layout& L) {   // gCs 안
    if (!allReady(st)) return nullptr;
    for (auto& c : gC4) if (c.px && c.sig == st.sig && c.cw == L.cw && c.ch == L.ch) { c.used = GetTickCount(); return &c; }
    if (!(gJob.want && gJob.st.sig == st.sig && gJob.L.cw == L.cw && gJob.L.ch == L.ch)) {
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
''' + s[b:]

# 뒤 스레드 고리: 합성 일을 먼저
rep('''        for (;;) {
            std::pair<std::string, int> job; Entry en;''', '''        for (;;) {
            if (buildOne()) continue;
            std::pair<std::string, int> job; Entry en;''')
open(p, 'w', encoding='utf-8').write(s)
print('ok')
