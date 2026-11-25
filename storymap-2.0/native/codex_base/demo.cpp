#include "chart.h"
using namespace forest;
LRESULT CALLBACK HostProc(HWND h,UINT m,WPARAM w,LPARAM l){if(m==WM_DESTROY){PostQuitMessage(0);return 0;}return DefWindowProcW(h,m,w,l);}
int WINAPI wWinMain(HINSTANCE inst,HINSTANCE,LPWSTR,int){WNDCLASSW c{};c.hInstance=inst;c.lpszClassName=L"ForestChartUiTestHost";c.lpfnWndProc=HostProc;c.hCursor=LoadCursorW(nullptr,IDC_ARROW);RegisterClassW(&c);RECT r{0,0,800,600};AdjustWindowRect(&r,WS_OVERLAPPEDWINDOW,FALSE);HWND h=CreateWindowW(c.lpszClassName,L"Forest 차트 UI 검증용 — 게임 연결 전",WS_OVERLAPPEDWINDOW|WS_VISIBLE,CW_USEDEFAULT,CW_USEDEFAULT,r.right-r.left,r.bottom-r.top,nullptr,nullptr,inst,nullptr);ShowChart(h);DestroyWindow(h);return 0;}
