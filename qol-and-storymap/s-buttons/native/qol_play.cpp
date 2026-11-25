// qol_play.cpp — 진행 모듈(세션 「진행 기능」 몫). 지금은 빈 판.
#include "qol.h"

namespace forest { namespace qol {

bool Play_Install() { return false; }
void Play_WindowReady(HWND) {}
bool Play_WndProc(HWND, UINT, WPARAM, LPARAM, LRESULT&) { return false; }
void Play_Fetch(void*, int, uint32_t, uint16_t, const uint8_t*) {}
void Play_PaintOverlays(HDC, const Layout&, const RECT&) {}
bool Play_OverlayRects(std::vector<RECT>& out) { out.clear(); return false; }
int Play_AutoButton() { return 0; }
bool Play_AutoOn() { return *(volatile int*)0x466408 != 0; }

}}  // namespace forest::qol
