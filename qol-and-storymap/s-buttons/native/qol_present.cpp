// qol_present.cpp — 화면 모듈(세션 「화면」 몫). 지금은 빈 판: 원작대로 1배로 그린다.
#include "qol.h"

namespace forest { namespace qol {

bool Present_Install() { return false; }
void Present_WindowReady(HWND) {}
bool Present_WndProc(HWND, UINT, WPARAM, LPARAM, LRESULT&) { return false; }
void Present_MapMouse(UINT, LPARAM&) {}
bool Present_BitBlt(HDC, int, int, int, int, HDC, int, int, DWORD, BOOL&) { return false; }
bool Present_StretchBlt(HDC, int, int, int, int, HDC, int, int, int, int, DWORD, BOOL&) { return false; }
void Present_InvalidateLogical(const RECT&) {}
POINT Present_ToClient(int x, int y) { return POINT{x, y}; }
Layout CurrentLayout() { return Layout(); }

}}  // namespace forest::qol
