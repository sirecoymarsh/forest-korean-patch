# -*- coding: utf-8 -*-
"""engine_bridge.cpp: 타이틀 다시보기(런처 9000) 연결."""
P = r'P:\AI\forest-flowchart-claude\native\engine_bridge.cpp'
s = open(P, encoding='utf-8').read()


def rep(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:90])
    s = s.replace(a, b)


rep('#include "code_hashes.inc"', '#include "code_hashes.inc"\n#include "title_layout.inc"')

rep("const UINT WM_CHART_OPEN=WM_APP+0x3E7;",
    "const UINT WM_CHART_OPEN=WM_APP+0x3E7,WM_CHART_CLICKMAP=WM_APP+0x3E8;const UINT_PTR clickTimer=0xF0E57;\n"
    "volatile LONG titleChart=0,pendingPlay=0;int clickStep=0;")

# 닫힘: 타이틀 지도면 런처 변수에 고른 장면(없으면 닫기)을, 멈춘 스크립트면 놓아준다
rep("void chartDone(){if(chartClosed)SetEvent(chartClosed);}",
    "uint16_t* vmVars(){return *(uint16_t**)0x46643c;}\n"
    "void chartDone(int play){\n"
    " if(InterlockedExchange(&titleChart,0)!=0){uint16_t*v=vmVars();if(v)v[kReplayVar]=(uint16_t)(play?play:kReplayClose);Log(play?\"replay requested \"+std::to_string(play):std::string(\"title chart closed\"));return;}\n"
    " if(play)InterlockedExchange(&pendingPlay,play);\n"
    " if(chartClosed)SetEvent(chartClosed);\n"
    "}\n"
    "// 타이틀 본 메뉴에서 기다리는 중인가(F8 → 지도 단추를 누른 것으로 바꾼다)\n"
    "bool atTitleMenu(){void*sc=*(void**)0x46639c;if(!sc)return false;auto base=*(uint8_t**)sc;auto cur=*(uint8_t**)((uint8_t*)sc+0x44);uint16_t sid=*(uint16_t*)((uint8_t*)sc+0x3c);uint32_t pc=(uint32_t)(cur-base);return sid==1&&pc>=kTitleMenuWaitPc&&pc<=kTitleMenuWaitPc+10;}")

# 입력 대기: 타이틀 본 메뉴면 단추 누르기로, 아니면 그 자리에 멈춤
rep("for(;;){if(InterlockedExchange(&chartRequested,0)!=0)park();DWORD result=originalWait(handle,32);if(result!=WAIT_TIMEOUT)return result;}",
    "for(;;){if(InterlockedExchange(&chartRequested,0)!=0){if(atTitleMenu()){Log(\"F8 at title: pressing the map button\");PostMessageW(gameWindow,WM_CHART_CLICKMAP,0,0);}else park();}DWORD result=originalWait(handle,32);if(result!=WAIT_TIMEOUT)return result;}")

# 게임 창: 지도 열기(모드), 단추 누르기 흉내(올림→누름→뗌)
rep("if(m==WM_CHART_OPEN){if(!ChartBegin(h))chartDone();return 0;}",
    "if(m==WM_CHART_OPEN){if(!ChartBegin(h,(int)w))chartDone(0);return 0;}\n"
    " if(m==WM_CHART_CLICKMAP){clickStep=0;PostMessageA(h,WM_MOUSEMOVE,0,MAKELPARAM(kTitleMapButtonX,kTitleMapButtonY));SetTimer(h,clickTimer,120,nullptr);return 0;}\n"
    " if(m==WM_TIMER&&w==clickTimer){LPARAM at=MAKELPARAM(kTitleMapButtonX,kTitleMapButtonY);if(clickStep==0){PostMessageA(h,WM_LBUTTONDOWN,MK_LBUTTON,at);clickStep=1;}else{PostMessageA(h,WM_LBUTTONUP,0,at);KillTimer(h,clickTimer);}return 0;}")

# 명령 읽기: 런처 첫 명령에서 지도(타이틀 모드)를 띄우거나 고른 장면을 건넨다
rep("if(sid==9000&&pc==0&&!ChartIsOpen())InterlockedExchange(&chartRequested,1);",
    "if(sid==9000&&pc==0){uint16_t*v=vmVars();LONG play=InterlockedExchange(&pendingPlay,0);if(v){if(play){v[kReplayVar]=(uint16_t)play;Log(\"replay start \"+std::to_string(play));}else if(!ChartIsOpen()&&!titleChart){v[kReplayVar]=0;InterlockedExchange(&titleChart,1);PostMessageW(gameWindow,WM_CHART_OPEN,1,0);}}}")

open(P, 'w', encoding='utf-8').write(s)
print('bridge replay patched')
