#pragma once
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <string>
#include <vector>
#include <set>
#include <map>
#include <cstdint>
#include <mutex>
namespace forest {
struct OptionDef { std::wstring label, classification, result; uint32_t target; std::vector<int> nextChoices, nextScenes; };
struct ChoiceDef { std::string id; int script, chapter, category; uint32_t pc; std::wstring prompt; std::vector<OptionDef> options; bool rejoins; };
struct SceneDef { int script, chapter; std::wstring title; std::vector<int> choices, parents; };
extern const std::vector<std::wstring> chapterNames;
extern const std::vector<SceneDef> scenes;
extern const std::vector<ChoiceDef> choices;
extern const std::string modelIdentity;
enum EventKind { SceneEnter=1, ChoiceReached=2, OptionChosen=3, SceneExit=4, Restart=5 };
struct Event { int kind, script, choice, option; uint32_t pc; };
struct RunState { bool known=false; int currentScript=0, currentChoice=-1; uint32_t currentPc=0; std::vector<Event> events; };
struct Progress { RunState run, primary, secondary; std::set<int> reachedScenes, completedScenes, reachedChoices; std::set<std::pair<int,int>> chosenOptions; };
extern Progress progress;
extern std::recursive_mutex progressMutex;
Progress SnapshotProgress();
void UnknownRun(const std::string& reason);
int SceneIndex(int script);
int ChapterOf(int script);
int CurrentSelection(int choice);
bool SceneKnown(int script);
void LoadProgress(const std::wstring& root);
void PersistProgress();
void ObserveOpcode(int script,uint32_t pc,uint16_t op);
void CapturePrimary();
void CaptureSecondary();
void RestoreSecondary();
void Saved(unsigned slot,const std::wstring& file);
void Loaded(unsigned slot,const std::wstring& file,bool success);
std::string Digest(const void* data,size_t size);
std::string DigestFile(const std::wstring& file);
void Log(const std::string& message);
void ShowChart(HWND game);
bool ChartIsOpen();
void SetChartAuditCallback(void(*callback)(bool opening));
}
