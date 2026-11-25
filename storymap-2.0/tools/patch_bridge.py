# -*- coding: utf-8 -*-
"""engine_bridge.cpp: 별도 창 → 게임 창 안 덧그리기로 바꾼다(문자열 치환, 한 번만)."""
import re, sys

P = r'P:\AI\forest-flowchart-claude\native\engine_bridge.cpp'
s = open(P, encoding='utf-8').read()


def rep(old, new):
    global s
    if old not in s:
        sys.exit('not found: ' + old[:90])
    s = s.replace(old, new, 1)


# 0) 새 가로채기 원형과 상태
rep("WaitFn originalWait=nullptr;DWORD vmThread=0;volatile LONG chartRequested=0;",
    "WaitFn originalWait=nullptr;DWORD vmThread=0;volatile LONG chartRequested=0;\n"
    "using BitBltFn=BOOL(WINAPI*)(HDC,int,int,int,int,HDC,int,int,DWORD);using StretchBltFn=BOOL(WINAPI*)(HDC,int,int,int,int,HDC,int,int,int,int,DWORD);\n"
    "BitBltFn originalBitBlt=nullptr;StretchBltFn originalStretchBlt=nullptr;HANDLE chartClosed=nullptr;\n"
    "const UINT WM_CHART_OPEN=WM_APP+0x3E7;")

# 1) open()/serviceChartRequest() → 입력 대기에서 멈추고 게임 창 스레드에 지도를 맡긴다
old_open = s[s.index("void open(){"):s.index("DWORD WINAPI waitForSingleObject")]
new_open = (
    "void chartDone(){if(chartClosed)SetEvent(chartClosed);}\n"
    "// 스크립트 스레드가 입력 대기에 들어간 자리에서만 멈춘다(그동안 게임 창 스레드는 평소처럼 돈다).\n"
    "void park(){\n"
    " SetChartPaths(gameRoot,globalSavePath());SetChartVarSource(storyVars);\n"
    " if(!chartClosed)chartClosed=CreateEventW(nullptr,TRUE,FALSE,nullptr);\n"
    " if(!chartClosed||!IsWindow(gameWindow))return;\n"
    " ResetEvent(chartClosed);audit(true);Log(\"script parked at input wait for chart\");\n"
    " if(!PostMessageW(gameWindow,WM_CHART_OPEN,0,0)){audit(false);return;}\n"
    " for(;;){DWORD r=originalWait(chartClosed,100);if(r==WAIT_OBJECT_0)break;if(!IsWindow(gameWindow)){Log(\"game window gone while parked\");break;}}\n"
    " audit(false);Log(\"script resumed\");\n"
    "}\n"
    "bool toGameWindow(HDC d){return ChartIsOpen()&&gameWindow&&WindowFromDC(d)==gameWindow;}\n"
    "// 지도가 열린 동안 게임이 창에 찍는 그림만 건너뛴다(게임 안 버퍼에는 그대로 그린다).\n"
    "BOOL WINAPI bitBlt(HDC d,int x,int y,int w,int h,HDC src,int sx,int sy,DWORD rop){if(toGameWindow(d))return TRUE;return originalBitBlt(d,x,y,w,h,src,sx,sy,rop);}\n"
    "BOOL WINAPI stretchBlt(HDC d,int x,int y,int w,int h,HDC src,int sx,int sy,int sw,int sh,DWORD rop){if(toGameWindow(d))return TRUE;return originalStretchBlt(d,x,y,w,h,src,sx,sy,sw,sh,rop);}\n"
    "void requestChart(){if(!supported){MessageBoxW(gameWindow,L\"게임 스크립트가 지원 버전과 다릅니다. 차트 설치 파일을 확인해 주세요.\",L\"Forest 이야기의 지도\",MB_OK|MB_ICONINFORMATION);return;}InterlockedExchange(&chartRequested,1);}\n"
)
s = s.replace(old_open, new_open, 1)

# 2) 입력 대기 가로채기: 요청이 있으면 그 자리에서 멈춤
rep("for(;;){serviceChartRequest();DWORD result=originalWait(handle,32);if(result!=WAIT_TIMEOUT)return result;}",
    "for(;;){if(InterlockedExchange(&chartRequested,0)!=0)park();DWORD result=originalWait(handle,32);if(result!=WAIT_TIMEOUT)return result;}")

# 3) 게임 창 프로시저: 지도가 열려 있으면 지도가 먼저 받는다
old_proc = s[s.index("LRESULT CALLBACK gameWndProc("):s.index("BOOL CALLBACK findWindow(")]
new_proc = (
    "LRESULT CALLBACK gameWndProc(HWND h,UINT m,WPARAM w,LPARAM l){\n"
    " if(m==WM_CHART_OPEN){if(!ChartBegin(h))chartDone();return 0;}\n"
    " if(ChartIsOpen()){LRESULT r=0;if(ChartWndProc(h,m,w,l,r))return r;}\n"
    " if(m==WM_KEYDOWN&&w==VK_F8){if(!(l&(1u<<30)))requestChart();return 0;}\n"
    " if(m==WM_KEYUP&&w==VK_F8)return 0;\n"
    " if(m==WM_SYSCOMMAND&&(w&0xfff0)==chartMenuId){requestChart();return 0;}\n"
    " return CallWindowProcA(gameProc,h,m,w,l);\n"
    "}\n"
)
s = s.replace(old_proc, new_proc, 1)

# 4) 감사 콜백 등록 → 닫힘 콜백 등록
rep("SetChartAuditCallback(audit);", "SetChartClosedCallback(chartDone);")

# 5) 명령 읽기: 지도를 열지 않고 요청만(타이틀 단추 9000)
rep("if(supported){serviceChartRequest();auto base=",
    "if(supported){auto base=")
rep("if(sid==9000&&pc==0)open();",
    "if(sid==9000&&pc==0&&!ChartIsOpen())InterlockedExchange(&chartRequested,1);")

# 6) 그리기 가로채기 설치(IAT), 실패 시 되돌림
rep("originalWait=*(WaitFn*)waitForSingleObjectIat;WaitFn wait=waitForSingleObject;if(ok)ok=protectWrite((void*)waitForSingleObjectIat,&wait,sizeof(wait));",
    "originalWait=*(WaitFn*)waitForSingleObjectIat;WaitFn wait=waitForSingleObject;if(ok)ok=protectWrite((void*)waitForSingleObjectIat,&wait,sizeof(wait));\n"
    " originalBitBlt=*(BitBltFn*)bitBltIat;BitBltFn bb=bitBlt;if(ok)ok=protectWrite((void*)bitBltIat,&bb,sizeof(bb));\n"
    " originalStretchBlt=*(StretchBltFn*)stretchBltIat;StretchBltFn sb=stretchBlt;if(ok)ok=protectWrite((void*)stretchBltIat,&sb,sizeof(sb));")
rep("if(!ok){protectWrite((void*)writeFileIat,&originalWrite,sizeof(originalWrite));",
    "if(!ok){if(originalBitBlt)protectWrite((void*)bitBltIat,&originalBitBlt,sizeof(originalBitBlt));if(originalStretchBlt)protectWrite((void*)stretchBltIat,&originalStretchBlt,sizeof(originalStretchBlt));protectWrite((void*)writeFileIat,&originalWrite,sizeof(originalWrite));")

open(P, 'w', encoding='utf-8').write(s)

# engine_layout.h: IAT 주소
L = r'P:\AI\forest-flowchart-claude\native\engine_layout.h'
t = open(L, encoding='utf-8').read()
if 'bitBltIat' not in t:
    t = t.replace("const uintptr_t waitForSingleObjectIat=0x459058;",
                  "const uintptr_t waitForSingleObjectIat=0x459058;\nconst uintptr_t bitBltIat=0x459018;      // GDI32!BitBlt\nconst uintptr_t stretchBltIat=0x45901c;  // GDI32!StretchBlt")
    open(L, 'w', encoding='utf-8').write(t)
print('bridge patched')
