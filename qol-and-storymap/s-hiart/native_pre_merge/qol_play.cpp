// qol_play.cpp — 진행 모듈 빈 판 + 「4K 그림」 갈래 시험용 소리 끄기(화면 갈래 사본에서 가져옴. 이 사본에만. 넘기지 않는다).
#include "qol.h"
#include <mmdeviceapi.h>
#include <audiopolicy.h>
#pragma comment(lib, "ole32.lib")
#include <mmsystem.h>
#pragma comment(lib, "winmm.lib")

namespace forest { namespace qol {

namespace {
bool gTestOverlay = false;
volatile LONG gShow = 1;
const RECT kTestRect = {560, 70, 790, 112};
DWORD WINAPI toggler(void*) {
    for (;;) {
        Sleep(2000);
        InterlockedExchange(&gShow, gShow ? 0 : 1);
        Present_InvalidateLogical(kTestRect);
    }
}
DWORD WINAPI muter(void*) {
    // 시험 사본만: 이 프로세스의 기본 소리 묶음을 끈다(게임이 소리를 열기 전에).
    if (FAILED(CoInitializeEx(nullptr, COINIT_MULTITHREADED))) return 1;
    IMMDeviceEnumerator* en = nullptr; IMMDevice* dev = nullptr; IAudioSessionManager* sm = nullptr; ISimpleAudioVolume* v = nullptr;
    HRESULT hr = CoCreateInstance(__uuidof(MMDeviceEnumerator), nullptr, CLSCTX_ALL, __uuidof(IMMDeviceEnumerator), (void**)&en);
    if (SUCCEEDED(hr)) hr = en->GetDefaultAudioEndpoint(eRender, eConsole, &dev);
    if (SUCCEEDED(hr)) hr = dev->Activate(__uuidof(IAudioSessionManager), CLSCTX_ALL, nullptr, (void**)&sm);
    if (SUCCEEDED(hr)) hr = sm->GetSimpleAudioVolume(nullptr, FALSE, &v);
    if (SUCCEEDED(hr)) hr = v->SetMute(TRUE, nullptr);
    if (v) v->Release(); if (sm) sm->Release(); if (dev) dev->Release(); if (en) en->Release();
    CoUninitialize();
    return SUCCEEDED(hr) ? 0 : 2;
}
// 시험 전용(test_skipmovie=1): 영상 재생을 곧바로 「끝남」으로 알려 오프닝을 건너뛴다(4K 글자 갈래 사본 방식, 화면 모듈 갈고리 뒤에 이어 붙임)
using MciFn = MCIERROR(WINAPI*)(MCIDEVICEID, UINT, DWORD_PTR, DWORD_PTR);
MciFn oMci;
MCIERROR WINAPI hMci(MCIDEVICEID id, UINT m, DWORD_PTR f, DWORD_PTR p) {
    MCIERROR r = oMci(id, m, f, p);
    if (m == MCI_PLAY && (f & MCI_NOTIFY) && p) PostMessageW((HWND)((MCI_GENERIC_PARMS*)p)->dwCallback, MM_MCINOTIFY, MCI_NOTIFY_SUCCESSFUL, id);
    return r;
}
}  // namespace

bool Play_Install() {
    if (Cfg("test_skipmovie", 0)) {
        void** slot = (void**)0x4592b4; oMci = (MciFn)*slot; void* to = (void*)hMci;
        PatchBytes((uintptr_t)slot, nullptr, &to, 4);
    }
    if (Cfg("test_mute", 0)) {
        HANDLE t = CreateThread(nullptr, 0, muter, nullptr, 0, nullptr);
        if (t) { WaitForSingleObject(t, 5000); DWORD code = 9; GetExitCodeThread(t, &code); CloseHandle(t); if (code) MessageBeep(0); }
    }
    gTestOverlay = Cfg("test_overlay", 0) != 0;
    return false;
}
void Play_WindowReady(HWND) {
    if (gTestOverlay) { HANDLE t = CreateThread(nullptr, 0, toggler, nullptr, 0, nullptr); if (t) CloseHandle(t); Log("test overlay on"); }
}
bool Play_WndProc(HWND, UINT, WPARAM, LPARAM, LRESULT&) { return false; }
void Play_Fetch(void*, int, uint32_t, uint16_t, const uint8_t*) {}
void Play_PaintOverlays(HDC dc, const Layout& L, const RECT& clip) {
    if (!gTestOverlay || !gShow) return;
    RECT r{L.ox + kTestRect.left * L.cw / 800, L.oy + kTestRect.top * L.ch / 600, L.ox + kTestRect.right * L.cw / 800, L.oy + kTestRect.bottom * L.ch / 600};
    RECT x; if (!IntersectRect(&x, &r, &clip)) return;
    HBRUSH b = CreateSolidBrush(RGB(30, 60, 30)); FillRect(dc, &r, b); DeleteObject(b);
    HBRUSH f = CreateSolidBrush(RGB(240, 230, 200)); FrameRect(dc, &r, f); DeleteObject(f);
    int fh = (r.bottom - r.top) * 6 / 10;
    HFONT font = CreateFontW(-fh, 0, 0, 0, FW_BOLD, 0, 0, 0, HANGUL_CHARSET, 0, 0, ANTIALIASED_QUALITY, 0, L"Malgun Gothic");
    HGDIOBJ old = SelectObject(dc, font);
    SetBkMode(dc, TRANSPARENT); SetTextColor(dc, RGB(240, 230, 200));
    DrawTextW(dc, L"겹그림 시험", -1, &r, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
    SelectObject(dc, old); DeleteObject(font);
}
bool Play_OverlayRects(std::vector<RECT>& out) {
    out.clear();
    if (gTestOverlay && gShow) out.push_back(kTestRect);
    return !out.empty();
}
int Play_AutoButton() { return 0; }
bool Play_AutoOn() { return *(volatile int*)0x466408 != 0; }

}}  // namespace forest::qol
