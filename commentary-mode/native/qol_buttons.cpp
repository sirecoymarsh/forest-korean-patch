// qol_buttons.cpp — 아이콘 줄 모듈: compane 의 빈 auto·menu 칸 = 자동·지도 단추.
//
// 그림: 게임 폴더 grps\compane.lwg(낱 파일, 엔진이 grps.xfl 보다 먼저 연다)에 auto·menu 층을 더했다.
//       엔진은 그 층으로 단추를 만들고 그리기·마우스 올림·숨김(Shift·시스템 화면·자동 중)을 스스로 한다(0x40fab1~).
// 단추: 엔진이 메시지 창 객체에 콜백을 채우는 명령 둘의 값만 바꾼다(엔진_메모 「아이콘 줄」).
//   메시지 창 객체는 불러오기 때마다 새로 만들어지므로(11-21 시험) 객체 칸이 아니라 채우는 명령(0x414de2·0x414e01)을 바꾼다.
//   auto  [+0x2c94] = 0x4166d0(엔진 자동 켜기) → autoButton: 진행 모듈 Play_AutoButton(), 0 이면 원래 콜백
//   menu  [+0x2c8c] = 0x4166c0(설정 화면)      → menuButton: 단추를 누른 때만 지도, 오른쪽 클릭은 원래 설정 화면
// 설정(forest-qol.ini): icon_row=0 이면 전부 원작(콜백 그대로, 낱 그림 파일도 안 보이게 해 grps.xfl 의 원래 그림),
//   icon_auto=0 → 자동 칸은 엔진 원래 자동, icon_map=0 → menu 칸은 원작대로 설정 화면.
#include "qol.h"
#include <intrin.h>
#include <cstring>

namespace forest { namespace qol {
namespace {
using Callback = int(__stdcall*)(int, int);
using CreateFileAFn = HANDLE(WINAPI*)(LPCSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);

const uintptr_t kMsgWinPtr = 0x46630c;      // 메시지 창 객체
const uintptr_t kAutoOrig = 0x4166d0, kMenuOrig = 0x4166c0;
const uintptr_t kSetMenuSlot = 0x414de2;    // mov dword ptr [ecx+0x2c8c], 0x4166c0
const uintptr_t kSetAutoSlot = 0x414e01;    // mov dword ptr [eax+0x2c94], 0x4166d0
const uintptr_t kRowShow = 0x410c20;        // thiscall(메시지 창): +0x2c7c=0, 단추 줄 다시 보이기(엔진 자동 끄기·실패 길과 같음)
const uintptr_t kMenuButtonRet = 0x410e19;  // 0x410e10(menu 단추 누름)의 call 0x410b90 다음 자리
const uintptr_t kCreateFileAIat = 0x459098;

bool gAuto = false, gMap = false;
bool gRightClick = false;       // 게임 창 스레드: 지금 원래 창 프로시저로 넘어가는 메시지가 오른쪽 단추
CreateFileAFn gOrigCreateFileA = nullptr;
volatile LONG gPicHidden = 0;

// ---------------------------------------------------------------- 콜백(게임 창 스레드에서 엔진이 부른다)
int __stdcall autoButton(int a, int b) {
    // 엔진 0x410bd0 이 부르기 전에 단추 줄을 숨기고 +0x2c7c=1 로 둔다(원작: 자동 중엔 줄이 숨는다).
    if (Play_AutoButton()) {
        if (!Play_AutoOn()) {   // 진행 모듈이 자동을 껐다면 원래 실패 길처럼 줄을 되살린다
            void* win = *(void**)kMsgWinPtr;
            if (win) ((void(__thiscall*)(void*))kRowShow)(win);
        }
        Log("buttons: auto button -> play module");
        return 1;
    }
    Log("buttons: auto button -> engine auto");
    return ((Callback)kAutoOrig)(a, b);
}

int __stdcall menuButton(int a, int b) {
    // [+0x2c8c] 를 부르는 0x410b90 은 단추(0x410e10)와 오른쪽 클릭(0x41558f·0x415747)이 부른다.
    // 0x410b90 은 인자 둘만 넣고 바로 부른다: [ra+0]=0x410b90 안 복귀, [ra+1..2]=인자, [ra+3]=0x410b90 을 부른 쪽의 복귀.
    const uintptr_t* ra = (const uintptr_t*)_AddressOfReturnAddress();
    bool pressed = ra[3] == kMenuButtonRet && !gRightClick;
    if (!pressed) {
        Log("buttons: right click -> settings");
        return ((Callback)kMenuOrig)(a, b);           // 오른쪽 클릭 → 원작 설정 화면
    }
    Log("buttons: map button -> chart");
    OpenChart();
    return 1;
}

// 엔진이 콜백을 채우는 명령(c7 8x <칸> <값>)의 값 4바이트만 바꾼다. 명령 전체가 기대한 것과 같을 때만.
bool patchSlotWriter(uintptr_t at, uint8_t modrm, uint32_t slot, uintptr_t orig, void* mine) {
    uint8_t expect[10] = {0xc7, modrm};
    memcpy(expect + 2, &slot, 4);
    uint32_t o = (uint32_t)orig; memcpy(expect + 6, &o, 4);
    if (memcmp((void*)at, expect, sizeof(expect)) != 0) return false;
    uint32_t m = (uint32_t)(uintptr_t)mine;
    return PatchBytes(at + 6, &o, &m, 4);
}

// ---------------------------------------------------------------- icon_row=0: 낱 그림 파일을 안 보이게(엔진은 grps.xfl 의 원래 그림을 쓴다)
bool isLooseCompane(LPCSTR name) {
    if (!name) return false;
    size_t n = strlen(name);
    const char tail[] = "grps\\compane.lwg";
    const size_t t = sizeof(tail) - 1;
    if (n < t || _stricmp(name + n - t, tail) != 0) return false;
    return n == t || name[n - t - 1] == '\\' || name[n - t - 1] == '/';
}
HANDLE WINAPI createFileA(LPCSTR name, DWORD access, DWORD share, LPSECURITY_ATTRIBUTES sa, DWORD disp, DWORD flags, HANDLE tmpl) {
    if (isLooseCompane(name)) {
        if (!InterlockedExchange(&gPicHidden, 1)) Log(std::string("buttons: icon row off -> original compane (hid ") + name + ")");
        SetLastError(ERROR_FILE_NOT_FOUND);
        return INVALID_HANDLE_VALUE;
    }
    return gOrigCreateFileA(name, access, share, sa, disp, flags, tmpl);
}
bool hidePicture() {
    std::wstring loose = Root() + L"\\grps\\compane.lwg";
    if (GetFileAttributesW(loose.c_str()) == INVALID_FILE_ATTRIBUTES) return false;   // 낱 파일이 없으면 이미 원작 그림
    CreateFileAFn cur = *(CreateFileAFn*)kCreateFileAIat;
    if (!cur) return false;
    gOrigCreateFileA = cur;
    CreateFileAFn mine = createFileA;
    return PatchBytes(kCreateFileAIat, &cur, &mine, sizeof(mine));
}
}  // namespace

bool Buttons_Install() {
    if (!Cfg("icon_row", 1)) {
        hidePicture();
        return false;
    }
    gAuto = Cfg("icon_auto", 1) != 0;
    gMap = Cfg("icon_map", 1) != 0;
    // 단추 길이 이 실행 파일의 것인지: 0x410e10 = mov ecx,[esp+8]; call 0x410b90
    static const uint8_t menuPress[9] = {0x8b, 0x4c, 0x24, 0x08, 0xe8, 0x77, 0xfd, 0xff, 0xff};
    if (gMap && memcmp((void*)0x410e10, menuPress, sizeof(menuPress)) != 0) gMap = false;
    if (gMap) gMap = patchSlotWriter(kSetMenuSlot, 0x81, 0x2c8c, kMenuOrig, (void*)menuButton);
    if (gAuto) gAuto = patchSlotWriter(kSetAutoSlot, 0x80, 0x2c94, kAutoOrig, (void*)autoButton);
    return gAuto || gMap;
}

void Buttons_WindowReady(HWND) {
    // 설치는 게임 진입점 전이라 그때는 기록이 아직 안 열린다 → 여기서 남긴다
    Log(std::string("buttons: auto ") + (gAuto ? "on" : "off") + ", map " + (gMap ? "on" : "off") +
        (gPicHidden || !Cfg("icon_row", 1) ? ", icon row off" : ""));
}

bool Buttons_WndProc(HWND, UINT m, WPARAM, LPARAM, LRESULT&) {
    gRightClick = m == WM_RBUTTONDOWN || m == WM_RBUTTONUP || m == WM_RBUTTONDBLCLK;
    return false;
}

}}  // namespace forest::qol
