// qol_buttons.cpp — 아이콘 줄 모듈(세션 「아이콘 줄」 몫). 지금은 빈 판.
#include "qol.h"

namespace forest { namespace qol {

bool Buttons_Install() { return false; }
void Buttons_WindowReady(HWND) {}
bool Buttons_WndProc(HWND, UINT, WPARAM, LPARAM, LRESULT&) { return false; }

}}  // namespace forest::qol
