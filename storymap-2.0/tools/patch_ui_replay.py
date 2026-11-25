# -*- coding: utf-8 -*-
"""chart_ui.cpp / chart.h: 타이틀에서 연 지도에서 누르면 다시보기."""
P = r'P:\AI\forest-flowchart-claude\native\chart_ui.cpp'
s = open(P, encoding='utf-8').read()


def rep(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:80])
    s = s.replace(a, b)


rep("std::wstring gNote;               // 아래 띠 안내(누른 것)",
    "std::wstring gNote;               // 아래 띠 안내(누른 것)\n"
    "bool gTitleMode = false;          // 타이틀에서 연 지도(다시보기 가능)")

rep("// ------------------------------------------------------------------ 안내 문구",
    "// ------------------------------------------------------------------ 다시보기 대상\n"
    "// 타이틀에서 연 지도에서만: 이야기 명판·갈림길을 누르면 그 장면을 처음부터 재생한다(본 것만, 가린 것 보기면 모두).\n"
    "int PlayScriptFor(int type, int a) {\n"
    "    if (type == HitScene && a >= 0 && kScenes[a].kind != 2 && SceneSeen(a)) return kScenes[a].script;\n"
    "    if ((type == HitQuestion || type == HitOption) && a >= 0 && ChoiceSeen(a)) return kScenes[kChoices[a].scene].script;\n"
    "    return 0;\n"
    "}\n\n"
    "// ------------------------------------------------------------------ 안내 문구")

rep('''        std::wstring l1 = Quote(gOptLabel[d][k]) + L" · " + st;
        std::wstring l2;''',
    '''        std::wstring l1 = Quote(gOptLabel[d][k]) + L" · " + st;
        std::wstring l2;
        if (gTitleMode && !(S.all || Chosen(d, k))) return Lines2(l1, L"누르면 「" + std::wstring(kScenes[kChoices[d].scene].title) + L"」을 처음부터 다시 봅니다.");''')

rep('''        return Lines2(Quote(gQuestion[d]), L"선택지 " + std::to_wstring(n) + L"개 중 고른 적 있는 것 " + std::to_wstring(c) + L"개");''',
    '''        if (gTitleMode) return Lines2(Quote(gQuestion[d]) + L" · 고른 적 있는 선택지 " + std::to_wstring(c) + L"/" + std::to_wstring(n),
                                      L"누르면 이 갈림길이 있는 「" + std::wstring(kScenes[kChoices[d].scene].title) + L"」을 처음부터 다시 봅니다.");
        return Lines2(Quote(gQuestion[d]), L"선택지 " + std::to_wstring(n) + L"개 중 고른 적 있는 것 " + std::to_wstring(c) + L"개");''')

rep('''        return Lines2(Quote(kScenes[s].title) + L" · " + st, s == S.curScene ? L"지금 이 이야기를 읽고 있습니다." : L"");''',
    '''        if (gTitleMode) return Lines2(Quote(kScenes[s].title) + L" · " + st, L"누르면 이 이야기를 처음부터 다시 봅니다. 다 보면 지도로 돌아옵니다.");
        return Lines2(Quote(kScenes[s].title) + L" · " + st, s == S.curScene ? L"지금 이 이야기를 읽고 있습니다." : L"");''')

rep('''    if (gPage < 0) return Lines2(L"장을 누르면 그 장의 이야기 차례와 갈림길이 펼쳐집니다.", L"금빛은 이번 회차, ✓ 는 끝까지 읽은 이야기입니다.");''',
    '''    if (gTitleMode && gPage < 0) return Lines2(L"장을 누르면 이야기 차례와 갈림길이 펼쳐집니다.", L"이야기를 누르면 처음부터 다시 보고, 다 보면 지도로 돌아옵니다.");
    if (gTitleMode) return Lines2(L"이야기 명판이나 갈림길을 누르면 그 장면을 처음부터 다시 봅니다.", L"휠: 확대·축소 · 끌기: 옮기기 · 0: 맞춤");
    if (gPage < 0) return Lines2(L"장을 누르면 그 장의 이야기 차례와 갈림길이 펼쳐집니다.", L"금빛은 이번 회차, ✓ 는 끝까지 읽은 이야기입니다.");''')

rep("void (*gOnClosed)() = nullptr;", "void (*gOnClosed)(int) = nullptr;")

rep('''void CloseChart(const char* why) {
    if (!gOpen) return;
    gOpen = false;
    if (gDown) { gDown = false; gMoved = false; if (GetCapture() == gGame) ReleaseCapture(); }
    Log(std::string("ui closed (") + why + ")");
    if (gGame) InvalidateRect(gGame, nullptr, TRUE);   // 게임이 제 화면을 다시 그리게
    if (gOnClosed) gOnClosed();                        // 멈춰 있던 스크립트를 놓아준다
}''', '''void CloseChart(const char* why, int play = 0) {
    if (!gOpen) return;
    gOpen = false;
    if (gDown) { gDown = false; gMoved = false; if (GetCapture() == gGame) ReleaseCapture(); }
    Log(std::string("ui closed (") + why + ")" + (play ? " replay " + std::to_string(play) : std::string()));
    if (gGame) InvalidateRect(gGame, nullptr, TRUE);   // 게임이 제 화면을 다시 그리게
    if (gOnClosed) gOnClosed(play);                    // 멈춰 있던 스크립트를 놓아주거나 다시보기를 건넨다
}''')

rep('''    } else if (h.type == HitOption || h.type == HitQuestion || h.type == HitScene) {
        gNote = InfoText();
    }''', '''    } else if (h.type == HitOption || h.type == HitQuestion || h.type == HitScene) {
        int play = PlayScriptFor(h.type, h.a);
        if (gTitleMode && play) { CloseChart("play", play); return; }
        gNote = InfoText();
        if (!gTitleMode && play) gNote = Lines2(gNote.substr(0, gNote.find(L'\\n')), L"다시보기는 타이틀 화면의 「이야기의 지도」에서 할 수 있습니다.");
    }''')

rep("void SetChartClosedCallback(void (*fn)()) { gOnClosed = fn; }",
    "void SetChartClosedCallback(void (*fn)(int)) { gOnClosed = fn; }")

rep('''bool ChartBegin(HWND game) {
    if (gOpen || !IsWindow(game)) return false;
    gGame = game;''', '''bool ChartBegin(HWND game, int mode) {
    if (gOpen || !IsWindow(game)) return false;
    gGame = game;
    gTitleMode = mode == 1;''')

rep('''    Prepare(root);
    GoCurrent();
    gOpen = true;''', '''    Prepare(root);
    if (gTitleMode) {       // 타이틀·다시보기 중엔 「이번 회차」가 없다
        S.runPick.assign(S.runPick.size(), -1); S.runInferred.assign(S.runInferred.size(), 0);
        S.runScenes.clear(); S.runChapters.clear(); S.runKnown = true;
        S.curScene = S.curChoice = S.afterChoice = S.afterOption = -1;
    }
    GoCurrent();
    gOpen = true;''')

rep('Log("ui opened in game window");',
    'Log(gTitleMode ? "ui opened in game window (title, replay enabled)" : "ui opened in game window");')

open(P, 'w', encoding='utf-8').write(s)

H = r'P:\AI\forest-flowchart-claude\native\chart.h'
h = open(H, encoding='utf-8').read()
assert "bool ChartBegin(HWND game);" in h and "void SetChartClosedCallback(void(*callback)());" in h
h = h.replace("bool ChartBegin(HWND game);", "bool ChartBegin(HWND game,int mode);")
h = h.replace("void SetChartClosedCallback(void(*callback)());", "void SetChartClosedCallback(void(*callback)(int play));")
open(H, 'w', encoding='utf-8').write(h)
print('ui patched')
