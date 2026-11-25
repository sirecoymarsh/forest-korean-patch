#include "chart.h"
#include "qol.h"
#include "engine_layout.h"
#include "code_hashes.inc"
#include "title_layout.inc"
#include <algorithm>
#include <cstring>
#include <sstream>
#include <atomic>

namespace forest { namespace {
using VoidFn=void(__cdecl*)();using SaveFn=void(__cdecl*)(unsigned);using LoadFn=int(__cdecl*)(unsigned);
VoidFn originalPrimary=nullptr,originalSecondary=nullptr,originalRollback=nullptr;
SaveFn originalSave=nullptr;LoadFn originalLoad=nullptr;
using WriteFn=BOOL(WINAPI*)(HANDLE,LPCVOID,DWORD,LPDWORD,LPOVERLAPPED);
WriteFn originalWrite=nullptr;
using WaitFn=DWORD(WINAPI*)(HANDLE,DWORD);
WaitFn originalWait=nullptr;DWORD vmThread=0;volatile LONG chartRequested=0;
using BitBltFn=BOOL(WINAPI*)(HDC,int,int,int,int,HDC,int,int,DWORD);using StretchBltFn=BOOL(WINAPI*)(HDC,int,int,int,int,HDC,int,int,int,int,DWORD);
BitBltFn originalBitBlt=nullptr;StretchBltFn originalStretchBlt=nullptr;HANDLE chartClosed=nullptr;
const UINT WM_CHART_OPEN=WM_APP+0x3E7,WM_CHART_CLICKMAP=WM_APP+0x3E8;const UINT_PTR clickTimer=0xF0E57;
volatile LONG titleChart=0,pendingPlay=0;int clickStep=0;
bool initialized=false;std::atomic<bool> supported{false};thread_local bool saving=false;thread_local DWORD written=0;HWND gameWindow=nullptr;WNDPROC gameProc=nullptr;
std::wstring gameRoot;
const UINT chartMenuId=0xEEC0;
struct Region {std::string name,hash;};std::vector<Region> before;
std::wstring widen(const char*s){int n=MultiByteToWideChar(CP_ACP,0,s,-1,nullptr,0);if(n<=0)return L"";std::wstring w(n,L'\0');MultiByteToWideChar(CP_ACP,0,s,-1,&w[0],n);w.resize(n-1);return w;}
std::wstring savePath(unsigned slot){char*cfg=*(char**)0x46e924;if(!cfg)return L"";char path[512];wsprintfA(path,"%s\\%s%02d.dat",cfg+0x43,cfg+0x25,slot&0xffff);return widen(path);}
bool fileData(const std::wstring&path,std::vector<uint8_t>&b){HANDLE f=CreateFileW(path.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);if(f==INVALID_HANDLE_VALUE)return false;DWORD size=GetFileSize(f,nullptr),read=0;bool ok=size==50668;if(ok){b.resize(size);ok=ReadFile(f,b.data(),size,&read,nullptr)&&read==size;}CloseHandle(f);return ok;}
bool matchState(const std::vector<uint8_t>&b,bool active){if(b.size()!=50668)return false;uint8_t*state=(uint8_t*)(active?0x46646c:0x4690a8);uint8_t*vars=*(uint8_t**)(active?0x46643c:0x466440);uint8_t*secondary=*(uint8_t**)0x466444;return vars&&secondary&&!memcmp(b.data()+20,state,0x2c3c)&&!memcmp(b.data()+20+0x2c3c,vars,14000)&&!memcmp(b.data()+20+0x2c3c+14000,(void*)0x46bce4,0x2c3c)&&!memcmp(b.data()+20+0x2c3c*2+14000,secondary,14000);}
// 번역 문자열만 바뀐 판(같은 명령부)도 받아들이도록 명령부만 해시한다.
std::string CodeDigest(const std::wstring&path){HANDLE f=CreateFileW(path.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);if(f==INVALID_HANDLE_VALUE)return std::string();DWORD size=GetFileSize(f,nullptr),got=0;std::vector<uint8_t>b(size);bool ok=size>=28&&ReadFile(f,b.data(),size,&got,nullptr)&&got==size;CloseHandle(f);if(!ok)return std::string();const uint32_t*h=(const uint32_t*)b.data();if((uint64_t)h[1]+h[2]>size)return std::string();return Digest(b.data()+h[1],h[2]);}
std::wstring globalSavePath(){char*cfg=*(char**)0x46e924;if(!cfg)return L"";char path[512];wsprintfA(path,"%s\\%s.dat",cfg+0x43,cfg+0x25);return widen(path);}
std::vector<Region> snapshot(){std::vector<Region> v;v.push_back({"vm-context",Digest((void*)0x46646c,0x2c3c)});void*vars=*(void**)0x46643c;if(vars)v.push_back({"all-10000-variables",Digest(vars,20000)});v.push_back({"expression-registers",Digest((void*)0x46ea98,32)});void*script=*(void**)0x46639c;if(script)v.push_back({"script-PC-and-buffer",Digest(script,0x48)});void*ptd=((void*(__cdecl*)())0x4494e3)();v.push_back({"game-RNG-seed",Digest((uint8_t*)ptd+20,4)});return v;}
void audit(bool opening){if(opening){before=snapshot();for(auto&r:before)Log("audit before "+r.name+" "+r.hash);}else{auto after=snapshot();bool equal=before.size()==after.size();for(size_t i=0;i<std::min(before.size(),after.size());++i){bool same=before[i].name==after[i].name&&before[i].hash==after[i].hash;equal=equal&&same;Log("audit after "+after[i].name+" "+after[i].hash+(same?" SAME":" CHANGED"));}Log(equal?"AUDIT PASS: VM, variables, stack, registers and RNG preserved":"AUDIT FAIL: engine state changed while chart was open");}}
const uint16_t* storyVars(){return *(const uint16_t**)0x46643c;}
uint16_t* vmVars(){return *(uint16_t**)0x46643c;}
void chartDone(int play){
 if(InterlockedExchange(&titleChart,0)!=0){uint16_t*v=vmVars();if(v)v[kReplayVar]=(uint16_t)(play?play:kReplayClose);Log(play?"replay requested "+std::to_string(play):std::string("title chart closed"));return;}
 if(play)InterlockedExchange(&pendingPlay,play);
 if(chartClosed)SetEvent(chartClosed);
}
// 타이틀 본 메뉴에서 기다리는 중인가(F8 → 지도 단추를 누른 것으로 바꾼다)
bool atTitleMenu(){void*sc=*(void**)0x46639c;if(!sc)return false;auto base=*(uint8_t**)sc;auto cur=*(uint8_t**)((uint8_t*)sc+0x44);uint16_t sid=*(uint16_t*)((uint8_t*)sc+0x3c);uint32_t pc=(uint32_t)(cur-base);return sid==1&&pc>=kTitleMenuWaitPc&&pc<=kTitleMenuWaitPc+10;}
// 스크립트 스레드가 입력 대기에 들어간 자리에서만 멈춘다(그동안 게임 창 스레드는 평소처럼 돈다).
void park(){
 SetChartPaths(gameRoot,globalSavePath());SetChartVarSource(storyVars);
 if(!chartClosed)chartClosed=CreateEventW(nullptr,TRUE,FALSE,nullptr);
 if(!chartClosed||!IsWindow(gameWindow))return;
 ResetEvent(chartClosed);audit(true);Log("script parked at input wait for chart");
 if(!PostMessageW(gameWindow,WM_CHART_OPEN,0,0)){audit(false);return;}
 for(;;){DWORD r=originalWait(chartClosed,100);if(r==WAIT_OBJECT_0)break;if(!IsWindow(gameWindow)){Log("game window gone while parked");break;}}
 audit(false);Log("script resumed");
}
bool isGameWindowDC(HDC d){return gameWindow&&WindowFromDC(d)==gameWindow;}
// 게임 창으로 가는 그림은 먼저 화면 모듈(qol)에 준다(그림자 판·창 크기 맞춤·겹그림).
// 화면 모듈이 받지 않으면: 지도가 열린 동안은 건너뛰고(게임 안 버퍼에는 그대로 그린다), 아니면 원래대로.
BOOL WINAPI bitBlt(HDC d,int x,int y,int w,int h,HDC src,int sx,int sy,DWORD rop){if(isGameWindowDC(d)){BOOL r=TRUE;if(qol::Present_BitBlt(d,x,y,w,h,src,sx,sy,rop,r))return r;if(ChartIsOpen())return TRUE;}return originalBitBlt(d,x,y,w,h,src,sx,sy,rop);}
BOOL WINAPI stretchBlt(HDC d,int x,int y,int w,int h,HDC src,int sx,int sy,int sw,int sh,DWORD rop){if(isGameWindowDC(d)){BOOL r=TRUE;if(qol::Present_StretchBlt(d,x,y,w,h,src,sx,sy,sw,sh,rop,r))return r;if(ChartIsOpen())return TRUE;}return originalStretchBlt(d,x,y,w,h,src,sx,sy,sw,sh,rop);}
void requestChart(){if(!supported){MessageBoxW(gameWindow,L"게임 스크립트가 지원 버전과 다릅니다. 차트 설치 파일을 확인해 주세요.",L"Forest 이야기의 지도",MB_OK|MB_ICONINFORMATION);return;}InterlockedExchange(&chartRequested,1);}
DWORD WINAPI waitForSingleObject(HANDLE handle,DWORD timeout){
 if(supported&&GetCurrentThreadId()!=GetWindowThreadProcessId(gameWindow,nullptr)&&handle==*(HANDLE*)0x4663c4&&timeout==INFINITE){
   DWORD waiter=GetCurrentThreadId();if(vmThread!=waiter){vmThread=waiter;Log("VM wait thread changed: "+std::to_string(waiter));}
   // Cooperatively pause on the VM's own input event. Never suspend a live thread.
   for(;;){if(InterlockedExchange(&chartRequested,0)!=0){if(atTitleMenu()){Log("F8 at title: pressing the map button");PostMessageW(gameWindow,WM_CHART_CLICKMAP,0,0);}else park();}DWORD result=originalWait(handle,32);if(result!=WAIT_TIMEOUT)return result;}
 }
 return originalWait(handle,timeout);
}
LPARAM titleMapAt(){POINT p=qol::Present_ToClient(kTitleMapButtonX,kTitleMapButtonY);return MAKELPARAM(p.x,p.y);}   // 합성 클릭은 창 물리 좌표로 게시(아래에서 다시 800×600 으로 바뀐다)
LRESULT CALLBACK gameWndProc(HWND h,UINT m,WPARAM w,LPARAM l){
 {LRESULT qr=0;if(qol::Present_WndProc(h,m,w,l,qr))return qr;}   // 창 크기·전체 화면(지도가 열려 있어도)
 if(m==WM_CHART_OPEN){if(!ChartBegin(h,(int)w))chartDone(0);return 0;}
 if(m==WM_CHART_CLICKMAP){clickStep=0;PostMessageA(h,WM_MOUSEMOVE,0,titleMapAt());SetTimer(h,clickTimer,120,nullptr);return 0;}
 if(m==WM_TIMER&&w==clickTimer){LPARAM at=titleMapAt();if(clickStep==0){PostMessageA(h,WM_LBUTTONDOWN,MK_LBUTTON,at);clickStep=1;}else{PostMessageA(h,WM_LBUTTONUP,0,at);KillTimer(h,clickTimer);}return 0;}
 if(ChartIsOpen()){LRESULT r=0;if(ChartWndProc(h,m,w,l,r))return r;}
 if(m>=WM_MOUSEFIRST&&m<=WM_MBUTTONDBLCLK&&m!=WM_MOUSEWHEEL)qol::Present_MapMouse(m,l);   // 여기부터 마우스 좌표는 800×600
 {LRESULT qr=0;if(qol::Cm_WndProc(h,m,w,l,qr))return qr;if(qol::Play_WndProc(h,m,w,l,qr))return qr;if(qol::Buttons_WndProc(h,m,w,l,qr))return qr;}
 if(m==WM_KEYDOWN&&w==VK_F8){if(!(l&(1u<<30)))requestChart();return 0;}
 if(m==WM_KEYUP&&w==VK_F8)return 0;
 if(m==WM_SYSCOMMAND&&(w&0xfff0)==chartMenuId){requestChart();return 0;}
 return CallWindowProcA(gameProc,h,m,w,l);
}
BOOL CALLBACK findWindow(HWND h,LPARAM){if(GetWindow(h,GW_OWNER)==nullptr&&IsWindowVisible(h)){wchar_t title[128];GetWindowTextW(h,title,128);if(wcscmp(title,L"Forest")==0){gameWindow=h;return FALSE;}}return TRUE;}
void initializeRuntime(){if(initialized)return;initialized=true;wchar_t path[MAX_PATH];GetModuleFileNameW(nullptr,path,MAX_PATH);gameRoot=path;gameRoot.resize(gameRoot.find_last_of(L"\\/"));SetCurrentDirectoryW(gameRoot.c_str());LoadProgress(gameRoot+L"\\forest-chart-progress");supported=true;for(auto&s:kCodeHashes){wchar_t name[32];swprintf_s(name,L"\\scr\\%04d.gsc",s.script);std::string got=CodeDigest(gameRoot+name);if(got!=s.sha){supported=false;Log("UNSUPPORTED SCRIPT "+std::to_string(s.script)+": command section "+(got.empty()?std::string("unreadable"):got));break;}}
 vmThread=GetCurrentThreadId();auto engine=*(uint8_t**)0x466398;if(engine)gameWindow=*(HWND*)(engine+4);DWORD ownerPid=0;if(gameWindow)GetWindowThreadProcessId(gameWindow,&ownerPid);if(IsWindow(gameWindow)&&ownerPid==GetCurrentProcessId()){gameProc=(WNDPROC)SetWindowLongPtrA(gameWindow,GWLP_WNDPROC,(LONG_PTR)gameWndProc);HMENU menu=GetSystemMenu(gameWindow,FALSE);AppendMenuW(menu,MF_SEPARATOR,0,nullptr);AppendMenuW(menu,MF_STRING,chartMenuId,L"이야기의 지도\tF8");Log("VM thread "+std::to_string(vmThread)+"; window thread "+std::to_string(GetWindowThreadProcessId(gameWindow,nullptr)));qol::Core_WindowReady(gameWindow);}else{supported=false;Log("verified engine window unavailable");}SetChartClosedCallback(chartDone);Log(supported?"native bridge ready; script hashes verified":"native bridge inactive; game continues");}
int __fastcall fetch(void*script){
 DWORD currentVm=GetCurrentThreadId();if(initialized&&vmThread!=currentVm)Log("VM thread changed after load: "+std::to_string(currentVm));vmThread=currentVm;
 try{initializeRuntime();if(supported){auto base=*(uint8_t**)script;auto cursor=*(uint8_t**)((uint8_t*)script+0x44);auto sid=*(uint16_t*)((uint8_t*)script+0x3c);auto pc=(uint32_t)(cursor-base);if(sid==9000&&pc==0){uint16_t*v=vmVars();LONG play=InterlockedExchange(&pendingPlay,0);if(v){if(play){v[kReplayVar]=(uint16_t)play;Log("replay start "+std::to_string(play));}else if(!ChartIsOpen()&&!titleChart){v[kReplayVar]=0;InterlockedExchange(&titleChart,1);PostMessageW(gameWindow,WM_CHART_OPEN,1,0);}}}if(cursor>=base&&pc<*(uint32_t*)((uint8_t*)script+0x28)){uint16_t op=*(uint16_t*)cursor;if(!ChartIsOpen())ObserveOpcode(sid,pc,op);qol::Play_Fetch(script,sid,pc,op,cursor);qol::Cm_Fetch(script,sid,pc,op,cursor);}}}
 catch(...){supported=false;Log("bridge tracking disabled after internal error");}
 return ((int(__fastcall*)(void*))0x413020)(script);
}
void __cdecl primary(){bool capture=*(uint16_t*)0x466432==0;originalPrimary();if(supported&&capture)CapturePrimary();}
void __cdecl secondary(){bool capture=*(uint16_t*)0x466432==0;originalSecondary();if(supported&&capture)CaptureSecondary();}
void __cdecl rollback(){originalRollback();if(supported)RestoreSecondary();}
BOOL WINAPI writeFile(HANDLE h,LPCVOID p,DWORD size,LPDWORD count,LPOVERLAPPED ov){BOOL ok=originalWrite(h,p,size,count,ov);if(saving&&ok&&count)written+=*count;return ok;}
void __cdecl save(unsigned slot){saving=true;written=0;originalSave(slot);saving=false;if(supported){std::vector<uint8_t>b;auto path=savePath(slot);if(written==50668&&fileData(path,b)&&matchState(b,false))Saved(slot,path);else Log("save not verified; existing journal not overwritten");}}
int __cdecl load(unsigned slot){if(!supported)return originalLoad(slot);auto path=savePath(slot);std::vector<uint8_t>b;if(!fileData(path,b)){Log("save has unsupported size or cannot be read; load skipped");return 0;}int ok=originalLoad(slot);if(ok){if(matchState(b,true))Loaded(slot,path,true);else UnknownRun("load succeeded but checkpoint mismatch; prior choices unknown");}return ok;}
bool protectWrite(void*address,const void*bytes,size_t size){DWORD old=0;if(!VirtualProtect(address,size,PAGE_EXECUTE_READWRITE,&old))return false;memcpy(address,bytes,size);DWORD ignored;VirtualProtect(address,size,old,&ignored);FlushInstructionCache(GetCurrentProcess(),address,size);return true;}
void relative(uint8_t*out,uint8_t opcode,uintptr_t at,uintptr_t to){out[0]=opcode;*(uint32_t*)(out+1)=(uint32_t)(to-at-5);}
void* trampoline(const HookLayout&l){uint8_t*t=(uint8_t*)VirtualAlloc(nullptr,l.length+5,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);if(!t)return nullptr;memcpy(t,l.bytes,l.length);relative(t+l.length,0xe9,(uintptr_t)t+l.length,l.address+l.length);DWORD old;VirtualProtect(t,l.length+5,PAGE_EXECUTE_READ,&old);return t;}
struct Install {const HookLayout* layout;void* replacement;void** original;};
}
namespace qol { void OpenChart(){requestChart();} }
extern "C" __declspec(dllexport) void __stdcall ForestChartInitialize(){
 // Called before the game's entry point, so no VM thread can race these verified patches.
 wchar_t path[MAX_PATH];GetModuleFileNameW(nullptr,path,MAX_PATH);std::wstring cwd=path;cwd.resize(cwd.find_last_of(L"\\/"));SetCurrentDirectoryW(cwd.c_str());
 Install hooks[]={{&layoutPrimary,(void*)primary,(void**)&originalPrimary},{&layoutSecondary,(void*)secondary,(void**)&originalSecondary},{&layoutRollback,(void*)rollback,(void**)&originalRollback},{&layoutSave,(void*)save,(void**)&originalSave},{&layoutLoad,(void*)load,(void**)&originalLoad}};
 if(memcmp((void*)0x41a240,fetchBytes,5))return;
 for(auto&h:hooks)if(memcmp((void*)h.layout->address,h.layout->bytes,h.layout->length))return;
 for(auto&h:hooks){*h.original=trampoline(*h.layout);if(!*h.original)return;}
 size_t patched=0;bool ok=true;for(auto&h:hooks){uint8_t b[16];memset(b,0x90,h.layout->length);relative(b,0xe9,h.layout->address,(uintptr_t)h.replacement);if(!protectWrite((void*)h.layout->address,b,h.layout->length)){ok=false;break;}++patched;}
 uint8_t call[5];relative(call,0xe8,0x41a240,(uintptr_t)fetch);if(ok)ok=protectWrite((void*)0x41a240,call,5);
 originalWrite=*(WriteFn*)writeFileIat;WriteFn wf=writeFile;if(ok)ok=protectWrite((void*)writeFileIat,&wf,sizeof(wf));
 originalWait=*(WaitFn*)waitForSingleObjectIat;WaitFn wait=waitForSingleObject;if(ok)ok=protectWrite((void*)waitForSingleObjectIat,&wait,sizeof(wait));
 originalBitBlt=*(BitBltFn*)bitBltIat;BitBltFn bb=bitBlt;if(ok)ok=protectWrite((void*)bitBltIat,&bb,sizeof(bb));
 originalStretchBlt=*(StretchBltFn*)stretchBltIat;StretchBltFn sb=stretchBlt;if(ok)ok=protectWrite((void*)stretchBltIat,&sb,sizeof(sb));
 if(ok)qol::Core_Install();   // 편의 기능(화면·진행·아이콘 줄). 지도 갈고리가 다 걸린 뒤에만
 if(!ok){if(originalBitBlt)protectWrite((void*)bitBltIat,&originalBitBlt,sizeof(originalBitBlt));if(originalStretchBlt)protectWrite((void*)stretchBltIat,&originalStretchBlt,sizeof(originalStretchBlt));protectWrite((void*)writeFileIat,&originalWrite,sizeof(originalWrite));protectWrite((void*)waitForSingleObjectIat,&originalWait,sizeof(originalWait));protectWrite((void*)0x41a240,fetchBytes,5);for(size_t i=0;i<patched;++i)protectWrite((void*)hooks[i].layout->address,hooks[i].layout->bytes,hooks[i].layout->length);}
}
}
BOOL WINAPI DllMain(HINSTANCE module,DWORD reason,LPVOID){if(reason==DLL_PROCESS_ATTACH)DisableThreadLibraryCalls(module);return TRUE;}
