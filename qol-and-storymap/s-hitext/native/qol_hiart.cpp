// qol_hiart.cpp — 4K 그림 모듈(세션 「4K 그림」 몫). 지금은 빈 판: 늘린 1배 그림 그대로.
#include "qol.h"

namespace forest { namespace qol {

bool HiArt_Install() { return false; }
void HiArt_WindowReady(HWND) {}
void HiArt_PaintBase(HDC, const Layout&, const RECT&) {}
bool HiArt_Rects(std::vector<RECT>& out) { out.clear(); return false; }

}}  // namespace forest::qol
