// 시험: 게임 없이 이야기의 지도를 PNG 로 그린다.
//   render_test <게임 폴더> <출력 폴더> <장면 이름>
// 진행 기록은 장면 이름에 맞춰 흉내 낸다. 읽음 비트는 <게임 폴더>\save\rssave.dat 를 그대로 쓴다.
#include "chart.h"
#include "chart_disp.h"
#include <cstdio>
#include <string>
using namespace forest;

static int ChoiceIndex(const char* id) {
    for (size_t i = 0; i < choices.size(); ++i) if (choices[i].id == id) return (int)i;
    return -1;
}

int wmain(int argc, wchar_t** argv) {
    if (argc < 4) { fwprintf(stderr, L"usage: render_test <game> <outdir> <scenario>\n"); return 2; }
    std::wstring game = argv[1], out = argv[2], sc = argv[3];
    SetChartPaths(game, game + L"\\save\\rssave.dat");
    bool isolated = sc == L"unread" || sc == L"complete" || sc == L"partial" || sc == L"partial-all";
    if (isolated) SetChartPaths(game, out + L"\\no-player-history.dat");
    progress = Progress();
    if (sc == L"complete") {
        for (const auto& s : kScenes) { progress.reachedScenes.insert(s.script); progress.completedScenes.insert(s.script); }
    } else if (sc == L"partial" || sc == L"partial-all") {
        progress.reachedScenes.insert(2100); progress.completedScenes.insert(2100);
        progress.reachedScenes.insert(3011); progress.completedScenes.insert(3011);
        progress.reachedScenes.insert(2200); // II started but not completed.
    }
    if (sc == L"user" || sc == L"user-all" || sc == L"hover") {
        // 사용자 진도 흉내: I·II·III 앞 이야기 → 2300 에서 「밖으로」를 고른 뒤
        progress.run.known = true;
        int scenes[] = {2100, 3011, 3021, 3022, 3023, 3024, 3031, 3032, 3033, 3034, 3041, 3042, 3043, 3044, 2200, 3061, 3062, 3063, 2300};
        for (int s : scenes) { progress.run.events.push_back({SceneEnter, s, -1, 0, 0}); progress.reachedScenes.insert(s); }
        int c = ChoiceIndex("2300@0x0018DA");
        progress.run.events.push_back({ChoiceReached, 2300, c, 0, 0});
        progress.run.events.push_back({OptionChosen, 2300, c, 2, 0});
        progress.run.currentScript = 2300;
        progress.run.currentChoice = c;
    } else if (sc == L"atchoice") {
        progress.run.known = true;
        int scenes[] = {2100};
        for (int s : scenes) { progress.run.events.push_back({SceneEnter, s, -1, 0, 0}); progress.reachedScenes.insert(s); }
        int c0 = ChoiceIndex("2100@0x000078");
        progress.run.events.push_back({ChoiceReached, 2100, c0, 0, 0});
        progress.run.events.push_back({OptionChosen, 2100, c0, 2, 0});
        int c1 = ChoiceIndex("2100@0x000148");
        progress.run.events.push_back({ChoiceReached, 2100, c1, 0, 0});
        progress.run.currentScript = 2100;
        progress.run.currentChoice = c1;
    } else if (sc == L"title") {
        // 타이틀에서 열었을 때: 지금 자리 없음
    }
    struct Shot { int page; bool all; const wchar_t* name; int ht, ha, hb; };
    Shot shots[] = {
        {-2, false, L"open", 0, -1, -1},
        {-1, false, L"overview", 0, -1, -1},
        {0, false, L"ch1", 0, -1, -1},
        {1, false, L"ch2", 0, -1, -1},
        {2, false, L"ch3", 0, -1, -1},
        {3, false, L"ch4", 0, -1, -1},
        {4, false, L"ch5", 0, -1, -1},
        {5, false, L"ch6", 0, -1, -1},
        {6, false, L"ch7", 0, -1, -1},
        {7, false, L"ch8", 0, -1, -1},
        {8, false, L"ch9", 0, -1, -1},
    };
    bool all = sc == L"user-all" || sc == L"partial-all";
    bool success = true;
    for (auto& s : shots) {
        std::wstring path = out + L"\\" + sc + L"_" + s.name + L".png";
        int ht = s.ht, ha = s.ha, hb = s.hb;
        if (sc == L"hover" && s.page == 2) { ht = 5; }  // 선택지 위
        bool ok = RenderChartPng(game, s.page, all || s.all, path, ht, ha, hb);
        success = success && ok;
        wprintf(L"%s %s\n", ok ? L"OK" : L"FAIL", path.c_str());
    }
    return success ? 0 : 1;
}
