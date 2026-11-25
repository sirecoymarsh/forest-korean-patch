// qol_hitext.cpp — 4K 글자 모듈(세션 「4K 글자」 몫). 지금은 빈 판: 원작 글자 그대로.
#include "qol.h"

namespace forest { namespace qol {

bool HiText_Install() { return false; }
void HiText_WindowReady(HWND) {}
void HiText_Paint(HDC, const Layout&, const RECT&) {}
bool HiText_Rects(std::vector<RECT>& out) { out.clear(); return false; }

}}  // namespace forest::qol
