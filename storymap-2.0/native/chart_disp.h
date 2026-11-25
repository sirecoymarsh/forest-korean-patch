#pragma once
// 이야기의 지도 표시 모델(tools/gen_cpp.py 가 chart_data.inc 를 만든다).
#include <vector>
#include <string>

namespace forest {

struct Wit { int script; int slot; };                 // 읽음 비트 하나(스크립트, 문자열 슬롯)

struct ChapterDef {
    const wchar_t* id;          // L"III"
    const wchar_t* title;       // 신주쿠 표류
    float w, h;                 // 장 쪽 캔버스 크기
    std::vector<int> order;     // 이야기 차례(kScenes 번호)
    int retry;                  // 실패하면 이 장을 다시 시작하는 장
};

struct SceneDisp {
    int script;
    int chapter;
    const wchar_t* title;
    int kind;                   // 0 짧은 이야기, 1 본편, 2 곁가지
    float x, y, w, h;           // 장 쪽 캔버스 좌표
    std::vector<int> slots;     // 대사 슬롯(읽은 정도)
    std::vector<int> exits;     // 정상 끝맺음 직전 대사
    int page;                   // 장 쪽 번호(-1: 배치 없음)
    int parent;                 // 곁가지 장면의 주인(kScenes 번호)
};

enum OutKind { OutChoice = 0, OutBack = 1, OutEnd = 2, OutRestart = 3, OutStop = 4 };
enum OptTag { TagRandom = 1, TagCond = 2, TagLate = 4, TagNav = 8 };

struct Out { int kind; int target; };                // target: kChoices 번호(선택으로 갈 때)

struct VarVal { int var; int value; };

struct OptionDisp {
    const wchar_t* label;
    int slot;                   // 선택지 문구 슬롯(설치된 번역에서 다시 읽는다)
    std::vector<Wit> witness;   // 이 갈래에만 있는 대사 = 고른 적 있음
    std::vector<Out> outs;
    int tags;
    const char* srcId;          // 진행 기록의 선택 ID(쪽을 합친 칸은 원래 쪽)
    int srcOption;              // 진행 기록의 선택지 번호(1부터)
    std::vector<VarVal> sig;    // 이 선택지만 세우는 이야기 변수 = 세이브만으로 이번 회차 선택을 안다
};

struct Pred { int choice; int option; };              // option: 0부터

struct ChoiceDisp {
    const char* id;
    int script;
    int chapter;
    int scene;
    const wchar_t* question;
    int qslot;
    float x, y, w, h;
    std::vector<OptionDisp> options;
    std::vector<Wit> reach;     // 이 칸에 닿았다는 대사
    std::vector<Wit> pre;       // 선택 바로 앞 대사
    std::vector<Pred> preds;    // 이 칸으로 오는 앞 선택(하나뿐이면 거꾸로 추론)
    std::vector<const char*> pages;  // 진행 기록 ID(쪽 넘김으로 이어진 목록은 둘)
    int page;
    int cluster;
};

struct BackEdge { int from; int to; };
struct ClusterDisp {
    int page;
    int index;
    int scene;
    int anchorRight;
    std::vector<BackEdge> back;
};

extern const int kChapterCount;
extern const ChapterDef kChapters[];
extern const std::vector<SceneDisp> kScenes;
extern const std::vector<ChoiceDisp> kChoices;
extern const std::vector<ClusterDisp> kClusters;
extern const float kQH, kLH;

}  // namespace forest
