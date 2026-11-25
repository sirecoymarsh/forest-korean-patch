#include "chart.h"
#include <windowsx.h>
#include <algorithm>
#include <cmath>
#include <sstream>
#include <atomic>

namespace forest {
namespace {
const COLORREF bg=RGB(15,31,26), panel=RGB(30,53,42), border=RGB(71,99,77), ink=RGB(232,236,222), muted=RGB(159,181,169), gold=RGB(213,194,135), mint=RGB(124,208,168);
HWND view=nullptr,owner=nullptr; std::atomic<bool> modalActive{false}; void(*audit)(bool)=nullptr;
Progress shown;
enum Page { Overview,Chapter,Scene,Choice,Menus,Connections,Gates,Retries };
enum Action { Close=1,Home,Current,Full,Fit,Back,Prev,Next,MenuList,Details,GateMap,RetryList,ToChapter=100,ToScene=1000,ToChoice=2000,ToOption=3000,ToNextChoice=4000,ToNextScene=5000 };
struct Hit { RECT r;int id; };
std::vector<Hit> hits;
Page page=Overview;int chapter=0,scene=-1,choice=-1,option=-1,listPage=0,focus=-1;
bool all=false,dragging=false,moved=false;
POINT down{},last{}; double zoom=1,panX=0,panY=0; RECT canvas{}; double mapW=700,mapH=300;
struct Location {Page page;int chapter,scene,choice,option,listPage;};
std::vector<Location> history;

int selectedOption(int id){for(auto it=shown.run.events.rbegin();it!=shown.run.events.rend();++it){if(it->kind==Restart&&it->option==choices[id].chapter+1)return -1;if(it->kind==OptionChosen&&it->choice==id)return it->option;}return -1;}
int retryChoice(int script){for(size_t i=0;i<choices.size();++i)if(choices[i].script==script&&choices[i].category==2)return (int)i;return -1;}
bool mapPage(){return page==Choice||page==Overview||page==Gates;}
RECT rect(int x,int y,int w,int h){return RECT{x,y,x+w,y+h};}
void fill(HDC dc,RECT r,COLORREF c){HBRUSH b=CreateSolidBrush(c);FillRect(dc,&r,b);DeleteObject(b);}
void line(HDC dc,int x,int y,int xx,int yy,COLORREF c,int width=1){HPEN p=CreatePen(PS_SOLID,width,c);auto old=SelectObject(dc,p);MoveToEx(dc,x,y,nullptr);LineTo(dc,xx,yy);SelectObject(dc,old);DeleteObject(p);}
void card(HDC dc,RECT r,COLORREF b=panel,COLORREF edge=border,int width=1){fill(dc,r,b);HPEN p=CreatePen(PS_SOLID,width,edge);auto old=SelectObject(dc,p);auto brush=SelectObject(dc,GetStockObject(NULL_BRUSH));Rectangle(dc,r.left,r.top,r.right,r.bottom);SelectObject(dc,brush);SelectObject(dc,old);DeleteObject(p);}
void txt(HDC dc,RECT r,const std::wstring& s,int size=16,COLORREF c=ink,bool bold=false,UINT flags=DT_LEFT|DT_WORDBREAK|DT_NOPREFIX){
 int wanted=std::max(9,size);HFONT f=nullptr;HGDIOBJ old=nullptr;
 for(int n=wanted;n>=9;--n){f=CreateFontW(-n,0,0,0,bold?FW_SEMIBOLD:FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,CLEARTYPE_QUALITY,DEFAULT_PITCH,L"맑은 고딕");old=SelectObject(dc,f);RECT measured=r;DrawTextW(dc,s.c_str(),(int)s.size(),&measured,flags|DT_CALCRECT);if(measured.bottom-measured.top<=r.bottom-r.top||n==9)break;SelectObject(dc,old);DeleteObject(f);}
 int saved=SaveDC(dc);IntersectClipRect(dc,r.left,r.top,r.right,r.bottom);SetBkMode(dc,TRANSPARENT);SetTextColor(dc,c);DrawTextW(dc,s.c_str(),(int)s.size(),&r,flags);RestoreDC(dc,saved);SelectObject(dc,old);DeleteObject(f);
}

void button(HDC dc,RECT r,const std::wstring& label,int id,bool active=false,int size=15){int n=(int)hits.size();card(dc,r,active?RGB(53,80,58):panel,focus==n?mint:active?gold:border,focus==n?2:1);txt(dc,rect(r.left+9,r.top+7,r.right-r.left-18,r.bottom-r.top-10),label,size,active?gold:ink,active);hits.push_back({r,id});}
bool knownScene(int i){return i>=0&&(all||(shown.reachedScenes.count(scenes[i].script)||shown.run.currentScript==scenes[i].script));}
bool knownChoice(int i){return i>=0&&(all||shown.reachedChoices.count(i));}
std::wstring sceneLabel(int i){return knownScene(i)?scenes[i].title:L"미도달 장면";}
std::wstring choiceLabel(int i){return knownChoice(i)?choices[i].prompt:L"미도달 선택";}
std::wstring sceneState(int i){int sid=scenes[i].script;if(shown.run.currentScript==sid)return L"● 현재 위치";if(shown.completedScenes.count(sid))return L"✓ 도달 경로 완료";if(shown.reachedScenes.count(sid))return L"○ 도달";return L"· 미도달";}
RECT transformed(double x,double y,double w,double h){return rect(canvas.left+(int)std::lround(panX+x*zoom),canvas.top+(int)std::lround(panY+y*zoom),(int)std::lround(w*zoom),(int)std::lround(h*zoom));}
void mapLine(HDC dc,double x,double y,double xx,double yy,COLORREF c=mint){POINT a{canvas.left+(int)(panX+x*zoom),canvas.top+(int)(panY+y*zoom)},b{canvas.left+(int)(panX+xx*zoom),canvas.top+(int)(panY+yy*zoom)};line(dc,a.x,a.y,b.x,b.y,c,2);}
void mapArrow(HDC dc,double x,double y,double xx,double yy,COLORREF c=mint){mapLine(dc,x,y,xx,yy,c);double a=atan2(yy-y,xx-x);mapLine(dc,xx,yy,xx-9*cos(a-.45),yy-9*sin(a-.45),c);mapLine(dc,xx,yy,xx-9*cos(a+.45),yy-9*sin(a+.45),c);}
void mapCard(HDC dc,double x,double y,double w,double h,const std::wstring& label,const std::wstring& sub,int action,COLORREF edge=border){RECT r=transformed(x,y,w,h);if(action&&focus==(int)hits.size())edge=mint;card(dc,r,panel,edge,edge==mint?2:1);txt(dc,transformed(x+12,y+10,w-24,h*.65-5),label,(int)(22*zoom),ink,true);txt(dc,transformed(x+12,y+h*.77,w-24,h*.23-3),sub,(int)(15*zoom),edge==mint?mint:muted);RECT hit;if(action&&IntersectRect(&hit,&r,&canvas))hits.push_back({hit,action});}
void resizeMap(){if(!view)return;RECT r{};GetClientRect(view,&r);canvas=rect(210,172,r.right-229,r.bottom-268);if(canvas.bottom<canvas.top+90)canvas.bottom=canvas.top+90;}
void fit(){resizeMap();zoom=std::clamp(std::min((canvas.right-canvas.left-26)/mapW,(canvas.bottom-canvas.top-20)/mapH),.2,1.6);panX=(canvas.right-canvas.left-mapW*zoom)/2;panY=(canvas.bottom-canvas.top-mapH*zoom)/2;}
void dimensions(){if(page==Overview){mapW=850;mapH=565;}else if(page==Gates){mapW=1050;mapH=465;}else if(page==Choice&&choice>=0){mapW=700;mapH=std::max(240.,choices[choice].options.size()*110.+(choices[choice].rejoins?95:0));}else{mapW=700;mapH=300;}}
void remember(){history.push_back({page,chapter,scene,choice,option,listPage});if(history.size()>64)history.erase(history.begin());}
void navigate(Page p,int value=0,bool push=true){if(push)remember();page=p;listPage=0;if(p!=Connections)option=-1;focus=-1;if(p==Chapter||p==Menus||p==Retries)chapter=value;if(p==Scene){scene=value;chapter=scenes[scene].chapter;}if(p==Choice){choice=value;if(choices[choice].chapter>=0)chapter=choices[choice].chapter;scene=SceneIndex(choices[choice].script);}dimensions();fit();InvalidateRect(view,nullptr,FALSE);Log("ui page "+std::to_string((int)page)+" chapter "+std::to_string(chapter+1)+(page==Choice?" choice "+choices[choice].id:""));}
void current(){int c=shown.run.currentChoice,s=SceneIndex(shown.run.currentScript);if(c>=0&&c<(int)choices.size()&&choices[c].script==shown.run.currentScript)navigate(Choice,c);else if(s>=0)navigate(Scene,s);else navigate(Overview);}
std::vector<int> chapterScenes(){std::vector<int>a;for(size_t i=0;i<scenes.size();++i)if(scenes[i].chapter==chapter)a.push_back((int)i);return a;}
std::vector<int> menuChoices(){std::vector<int>a;for(size_t i=0;i<choices.size();++i)if(choices[i].chapter==chapter&&choices[i].category==(page==Retries?2:1))a.push_back((int)i);return a;}
void act(int id){
 if(id==Close){DestroyWindow(view);return;}
 if(id==Home)navigate(Overview);
 else if(id==Current)current();
 else if(id==Full){all=!all;option=-1;InvalidateRect(view,nullptr,FALSE);Log(all?"ui full-view on":"ui full-view off");}
 else if(id==Fit){Log("ui fit");fit();InvalidateRect(view,nullptr,FALSE);}
 else if(id==Back){if(history.empty())navigate(Overview,0,false);else{auto h=history.back();history.pop_back();page=h.page;chapter=h.chapter;scene=h.scene;choice=h.choice;option=h.option;listPage=h.listPage;focus=-1;dimensions();fit();InvalidateRect(view,nullptr,FALSE);}}
 else if(id==Prev){if(listPage>0)--listPage;InvalidateRect(view,nullptr,FALSE);}
 else if(id==Next){++listPage;InvalidateRect(view,nullptr,FALSE);}
 else if(id==MenuList)navigate(Menus,chapter);
 else if(id==RetryList)navigate(Retries,chapter);else if(id==GateMap)navigate(Gates);else if(id==Details)navigate(Connections);
 else if(id>=ToNextScene){int s=SceneIndex(id-ToNextScene);if(s>=0)navigate(Scene,s);}
 else if(id>=ToNextChoice)navigate(Choice,id-ToNextChoice);
 else if(id>=ToOption){option=id-ToOption;InvalidateRect(view,nullptr,FALSE);}
 else if(id>=ToChoice)navigate(Choice,id-ToChoice);
 else if(id>=ToScene)navigate(Scene,id-ToScene);
 else if(id>=ToChapter)navigate(Chapter,id-ToChapter);
}
std::wstring chapterLabel(int i){bool seen=false;for(auto&s:scenes)if(s.chapter==i&&(shown.reachedScenes.count(s.script)||shown.run.currentScript==s.script))seen=true;return all||seen?chapterNames[i]:std::to_wstring(i+1)+L"  미도달 장";}
void overview(HDC dc){
 const POINT pos[]={{0,0},{290,0},{580,0},{580,155},{290,155},{0,155},{0,310},{580,310},{580,465}};
 mapArrow(dc,260,47,287,47);mapArrow(dc,550,47,577,47);mapArrow(dc,710,99,710,151);mapArrow(dc,580,202,554,202);mapArrow(dc,290,202,264,202);mapArrow(dc,130,254,130,306);mapArrow(dc,260,357,287,357);mapArrow(dc,550,357,577,357);mapArrow(dc,710,409,710,461);mapArrow(dc,580,512,554,512);
 for(int i=0;i<9;++i){int cnt=0;for(auto&s:scenes)if(s.chapter==i)++cnt;mapCard(dc,pos[i].x,pos[i].y,260,99,chapterLabel(i),L"장면 "+std::to_wstring(cnt)+L"개",ToChapter+i,i==ChapterOf(shown.run.currentScript)?mint:border);}
 mapCard(dc,290,310,260,99,all?L"앞선 선택 확인":L"이후 진행 조건",all?L"충족 → VIII / 미충족 → 재시작":L"전체 보기에서 자세히",GateMap,gold);mapCard(dc,290,465,260,99,all?L"이야기 마침":L"이후 흐름",L"",0);
}
void gates(HDC dc){
 const int ch[]={2,4,5},scripts[]={1300,1500,1600};
 for(int i=0;i<3;++i){int x=i*355;mapCard(dc,x,0,300,94,chapterLabel(ch[i]),all?L"통과 → 다음 장":L"진행 조건",ToChapter+ch[i]);mapArrow(dc,x+150,95,x+150,133,gold);mapCard(dc,x,135,300,100,all?L"실패 · 재시작 여부":L"이후 흐름 미확인",all?L"계속 → 같은 장 / 거절 → 종료":L"전체 보기에서 자세히",ToChoice+retryChoice(scripts[i]),gold);mapLine(dc,x+300,185,x+330,185,gold);mapLine(dc,x+330,185,x+330,46,gold);mapArrow(dc,x+330,46,x+301,46,gold);}
 mapCard(dc,0,280,300,100,all?L"VII장 이후 조건 확인":L"후반 진행 조건",all?L"두 조건 모두 충족 → VIII · IX":L"전체 보기에서 자세히",ToChapter+6,gold);mapArrow(dc,302,330,350,330);mapCard(dc,355,280,300,100,all?L"IV의 조건 미충족":L"이후 흐름 미확인",all?L"재시작 수락 → IV / 거절 → 종료":L"전체 보기에서 자세히",ToChoice+retryChoice(1400),gold);mapArrow(dc,302,373,700,421);mapCard(dc,710,370,340,95,all?L"IV 충족 · V 조건 미충족":L"이후 흐름 미확인",all?L"재시작 수락 → V / 거절 → 종료":L"전체 보기에서 자세히",ToChoice+retryChoice(1500),gold);
}
void connections(HDC dc,int w,int h){
 if(choice<0||option<0)return;auto&o=choices[choice].options[option];bool known=all||shown.chosenOptions.count({choice,option+1});if(!known){txt(dc,rect(225,181,w-252,90),L"선택 결과 미확인. 전체 보기에서 확인할 수 있습니다.",18,muted);return;}
 txt(dc,rect(225,175,w-250,60),o.label+L" — "+o.result,15,ink);std::vector<std::pair<int,std::wstring>> links;for(int n:o.nextChoices)links.push_back({ToNextChoice+n,choiceLabel(n)});for(int n:o.nextScenes){int i=SceneIndex(n);if(i>=0)links.push_back({ToScene+i,sceneLabel(i)});}
 int rows=std::max(1,(h-300)/60),pages=std::max(1,((int)links.size()+rows-1)/rows);listPage=std::clamp(listPage,0,pages-1);if(links.empty())txt(dc,rect(225,244,w-252,96),L"다음 선택 없이 구간을 마치거나 상위 흐름으로 돌아갑니다. 장 목록과 진행 조건에서 이어지는 흐름을 볼 수 있습니다.",17,muted);
 for(int k=0;k<rows&&listPage*rows+k<(int)links.size();++k){auto&v=links[listPage*rows+k];button(dc,rect(220,238+k*60,w-242,51),v.second,v.first,false,14);}if(listPage>0)button(dc,rect(220,h-57,100,31),L"이전",Prev);if(listPage+1<pages)button(dc,rect(w-122,h-57,100,31),L"다음",Next);txt(dc,rect(w/2,h-51,115,25),std::to_wstring(listPage+1)+L" / "+std::to_wstring(pages),14,muted);
}
void lists(HDC dc,int width,int height){
 int rows=std::max(1,(height-250)/68);std::vector<int> ids;bool isScene=page==Chapter;
 if(isScene)ids=chapterScenes();else if(page==Scene&&scene>=0)ids=scenes[scene].choices;else if(page==Menus||page==Retries)ids=menuChoices();
 int pages=std::max(1,((int)ids.size()+rows-1)/rows);listPage=std::clamp(listPage,0,pages-1);
 if(ids.empty()){card(dc,rect(220,198,width-242,156));txt(dc,rect(238,216,width-278,55),page==Scene?L"이 장면에는 이야기 선택이 없습니다.":L"이 장의 별도 이동 메뉴는 없습니다.",20);txt(dc,rect(238,282,width-278,52),L"장면 목록에서 다른 파트를 선택해 살펴볼 수 있습니다.",15,muted);}
 for(int k=0;k<rows&&listPage*rows+k<(int)ids.size();++k){int i=ids[listPage*rows+k];RECT r=rect(220,174+k*68,width-241,58);
 std::wstring title=isScene?sceneLabel(i):choiceLabel(i);std::wstring sub=isScene?sceneState(i):choices[i].category==1?L"장면 이동 메뉴":choices[i].category==2?L"재시작 메뉴":L"이야기 선택 · "+std::to_wstring(choices[i].options.size())+L"개 항목";
 button(dc,r,title,isScene?ToScene+i:ToChoice+i,isScene?shown.run.currentScript==scenes[i].script:shown.run.currentChoice==i,16);
 txt(dc,rect(r.right-166,r.top+35,158,20),sub,11,muted);
 }
 if(listPage>0)button(dc,rect(220,height-66,108,32),L"이전",Prev);
 if(listPage+1<pages)button(dc,rect(width-129,height-66,108,32),L"다음",Next);
 txt(dc,rect(width/2,height-60,110,24),std::to_wstring(listPage+1)+L" / "+std::to_wstring(pages),14,muted);
}
void drawChoice(HDC dc,int width,int height){
 const auto& c=choices[choice];bool visible=knownChoice(choice);int selected=selectedOption(choice),count=(int)c.options.size();
 double cy=(count*110.-10)/2;
 mapCard(dc,0,cy-44,230,90,choiceLabel(choice),visible?(c.category==1?L"장면 이동 메뉴":L"선택에 따른 갈림"):L"아직 도달하지 않은 선택",0,shown.run.currentChoice==choice?mint:gold);
 for(int j=0;j<count;++j){const auto&o=c.options[j];double y=j*110.;bool outcome=all||shown.chosenOptions.count({choice,j+1});std::wstring label=visible?o.label:L"미도달 선택지";std::wstring sub=outcome?o.classification:L"선택 결과 미확인";if(selected==j+1)sub=L"● 이번 회차 선택  "+sub;
 mapArrow(dc,232,cy,296,y+45,selected==j+1?gold:mint);
 mapCard(dc,300,y,398,94,label,sub,ToOption+j,selected==j+1?gold:option==j?mint:border);
 }
 if(c.rejoins){double y=count*110.+14;for(int j=0;j<count;++j){mapLine(dc,697,j*110.+88,710,j*110.+88);mapLine(dc,710,j*110.+88,710,y+25);}mapArrow(dc,710,y+25,695,y+25);mapCard(dc,300,y,398,54,all||visible?L"갈래가 다시 합류":L"이후 흐름 미확인",L"",0);}
}

void paint(HDC dc,int w,int h){
 hits.clear();fill(dc,rect(0,0,w,h),bg);line(dc,18,70,w-18,70,border);txt(dc,rect(20,12,176,45),L"FOREST",29,gold,true);txt(dc,rect(214,18,202,32),L"이야기의 지도",23,ink,true);
 button(dc,rect(w-273,19,87,31),L"현재 위치",Current,false,13);button(dc,rect(w-178,19,87,31),all?L"전체 보기 ●":L"전체 보기",Full,all,12);button(dc,rect(w-83,19,63,31),L"닫기",Close,false,13);
 txt(dc,rect(20,84,166,25),L"CHAPTERS",12,gold);
 int step=std::max(34,std::min(44,(h-222)/9));for(int i=0;i<9;++i){bool seen=false;for(auto&s:scenes)if(s.chapter==i&&(shown.reachedScenes.count(s.script)||shown.run.currentScript==s.script))seen=true;std::wstring s=all||seen?chapterNames[i]:std::to_wstring(i+1)+L"  미도달 장";button(dc,rect(18,113+i*step,173,step-5),s,ToChapter+i,page!=Overview&&chapter==i,13);}
 button(dc,rect(18,h-106,173,29),L"전체 진행",Home,page==Overview,13);button(dc,rect(18,h-71,173,29),L"재시작 · 진행 조건",GateMap,page==Gates,13);txt(dc,rect(18,h-34,178,25),shown.run.known?L"현재 회차 기록 중":L"이전 선택 기록 미확인",11,muted);line(dc,201,84,201,h-14,border);
 std::wstring title=page==Overview?L"전체 이야기 흐름":page==Gates?L"재시작과 후반 진행 조건":page==Connections?L"선택 결과와 연결":page==Chapter||page==Menus||page==Retries?(all||std::any_of(scenes.begin(),scenes.end(),[](const SceneDef&s){return s.chapter==chapter&&(shown.reachedScenes.count(s.script)||shown.run.currentScript==s.script);})?chapterNames[chapter]:L"미도달 장"):page==Scene?sceneLabel(scene):choiceLabel(choice);
 txt(dc,rect(220,87,w-240,39),title,21,ink,true);button(dc,rect(220,132,77,29),L"뒤로",Back,false,12);
 if(page==Chapter){button(dc,rect(307,132,141,29),L"장면 이동 메뉴",MenuList,false,12);button(dc,rect(458,132,112,29),L"재시작 메뉴",RetryList,false,12);}
 bool map=mapPage();if(map){button(dc,rect(w-105,132,83,29),L"전체 맞춤",Fit,false,12);txt(dc,rect(310,138,w-428,25),L"휠 확대 · 드래그 이동 · 0 맞춤",12,muted);}
 if(page==Connections)connections(dc,w,h);else if(!map)lists(dc,w,h);
 else{resizeMap();int saved=SaveDC(dc);IntersectClipRect(dc,canvas.left,canvas.top,canvas.right,canvas.bottom);if(page==Overview)overview(dc);else if(page==Gates)gates(dc);else drawChoice(dc,w,h);RestoreDC(dc,saved);
 // Non-map controls/details are drawn outside the clipped viewport.
 if(page==Overview||page==Gates)txt(dc,rect(220,h-80,w-242,61),all?L"III·V·VI 실패 경로는 해당 장으로 돌아갑니다. VII장 뒤에서는 앞선 선택의 조건을 확인합니다.":L"전체 보기로 모든 제목과 분기를 볼 수 있습니다. 보기 설정은 플레이·해금 기록을 바꾸지 않습니다.",14,muted);
 if(page==Choice){auto&c=choices[choice];if(option>=0&&option<(int)c.options.size()){auto&o=c.options[option];bool known=all||shown.chosenOptions.count({choice,option+1});txt(dc,rect(220,h-85,w-243,36),known?o.result:L"선택 결과 미확인 — 전체 보기에서 확인할 수 있습니다.",14,muted);if(known)button(dc,rect(220,h-44,w-242,30),L"연결 "+std::to_wstring(o.nextChoices.size()+o.nextScenes.size())+L"곳 · 결과 자세히",Details,false,13);}else txt(dc,rect(220,h-78,w-243,53),L"선택지 카드를 누르면 결과와 이어지는 분기를 확인합니다. 재합류해도 이전 선택의 영향은 남을 수 있습니다.",14,muted);}
 }
}
LRESULT CALLBACK wndProc(HWND h,UINT msg,WPARAM wp,LPARAM lp){
 switch(msg){
 case WM_ERASEBKGND:return 1;
 case WM_PAINT:{PAINTSTRUCT ps;HDC dc=BeginPaint(h,&ps);RECT r;GetClientRect(h,&r);HDC mem=CreateCompatibleDC(dc);HBITMAP bitmap=CreateCompatibleBitmap(dc,r.right,r.bottom);auto old=SelectObject(mem,bitmap);paint(mem,r.right,r.bottom);BitBlt(dc,0,0,r.right,r.bottom,mem,0,0,SRCCOPY);SelectObject(mem,old);DeleteObject(bitmap);DeleteDC(mem);EndPaint(h,&ps);return 0;}
 case WM_SIZE:if(view){dimensions();fit();InvalidateRect(h,nullptr,FALSE);}return 0;
 case WM_LBUTTONDOWN:{down=last=POINT{GET_X_LPARAM(lp),GET_Y_LPARAM(lp)};dragging=mapPage()&&PtInRect(&canvas,down);moved=false;if(dragging)SetCapture(h);return 0;}
 case WM_MOUSEMOVE:if(dragging){POINT p{GET_X_LPARAM(lp),GET_Y_LPARAM(lp)};if(abs(p.x-down.x)+abs(p.y-down.y)>5)moved=true;if(moved){panX+=p.x-last.x;panY+=p.y-last.y;InvalidateRect(h,nullptr,FALSE);}last=p;}return 0;
 case WM_LBUTTONUP:{POINT p{GET_X_LPARAM(lp),GET_Y_LPARAM(lp)};bool click=!moved;if(moved)Log("ui drag "+std::to_string(p.x-down.x)+","+std::to_string(p.y-down.y));dragging=false;ReleaseCapture();if(click)for(int i=(int)hits.size()-1;i>=0;--i)if(PtInRect(&hits[i].r,p)){act(hits[i].id);break;}return 0;}
 case WM_MOUSEWHEEL:{POINT p{GET_X_LPARAM(lp),GET_Y_LPARAM(lp)};ScreenToClient(h,&p);if(mapPage()&&PtInRect(&canvas,p)&&!(GET_KEYSTATE_WPARAM(wp)&MK_CONTROL)){double old=zoom,x=p.x-canvas.left,y=p.y-canvas.top,mx=(x-panX)/zoom,my=(y-panY)/zoom;zoom=std::clamp(zoom*pow(1.17,GET_WHEEL_DELTA_WPARAM(wp)/120.),.2,3.5);panX=x-(x-panX)*zoom/old;panY=y-(y-panY)*zoom/old;InvalidateRect(h,nullptr,FALSE);std::ostringstream s;s<<"ui zoom "<<old<<" -> "<<zoom<<" anchor-error "<<fabs((x-panX)/zoom-mx)+fabs((y-panY)/zoom-my);Log(s.str());return 0;}break;}
 case WM_KEYDOWN:
 if(wp==VK_ESCAPE||wp==VK_F8){act(Close);return 0;}if(wp==VK_TAB){Log("ui keyboard Tab");if(!hits.empty())focus=(focus+(GetKeyState(VK_SHIFT)<0?-1:1)+(int)hits.size())%(int)hits.size();InvalidateRect(h,nullptr,FALSE);return 0;}if(wp==VK_RETURN&&focus>=0&&focus<(int)hits.size()){Log("ui keyboard Enter");act(hits[focus].id);return 0;}if(wp==VK_BACK){act(Back);return 0;}if(wp==VK_HOME){act(Current);return 0;}if(wp=='0'){act(Fit);return 0;}if(wp==VK_LEFT||wp==VK_RIGHT||wp==VK_UP||wp==VK_DOWN){panX+=wp==VK_LEFT?40:wp==VK_RIGHT?-40:0;panY+=wp==VK_UP?40:wp==VK_DOWN?-40:0;InvalidateRect(h,nullptr,FALSE);return 0;}break;
 case WM_CLOSE:DestroyWindow(h);return 0;
 case WM_DESTROY:view=nullptr;return 0;
 }
 return DefWindowProcW(h,msg,wp,lp);
}
}
bool ChartIsOpen(){return modalActive;}
void SetChartAuditCallback(void(*fn)(bool)){audit=fn;}
void ShowChart(HWND game){
 if(modalActive||!IsWindow(game))return;modalActive=true;owner=game;shown=SnapshotProgress();all=false;history.clear();focus=-1;page=Overview;option=-1;
 if(audit)audit(true);Log("ui opened");
 WNDCLASSW wc{};wc.lpfnWndProc=wndProc;wc.hInstance=GetModuleHandleW(nullptr);wc.lpszClassName=L"ForestFlowchartNativeV1";wc.hCursor=LoadCursorW(nullptr,IDC_ARROW);RegisterClassW(&wc);
 RECT r;GetClientRect(game,&r);POINT p{0,0};ClientToScreen(game,&p);bool enabled=IsWindowEnabled(game)!=FALSE;
 MONITORINFO monitor{};monitor.cbSize=sizeof(monitor);if(GetMonitorInfoW(MonitorFromWindow(game,MONITOR_DEFAULTTONEAREST),&monitor)){auto m=monitor.rcMonitor;r.right=std::min(r.right,m.right-m.left);r.bottom=std::min(r.bottom,m.bottom-m.top);p.x=std::clamp(p.x,m.left,m.right-r.right);p.y=std::clamp(p.y,m.top,m.bottom-r.bottom);}
 Log("ui viewport "+std::to_string(r.right)+"x"+std::to_string(r.bottom));
 view=CreateWindowExW(WS_EX_CONTROLPARENT,wc.lpszClassName,L"Forest — 이야기의 지도",WS_POPUP|WS_VISIBLE,p.x,p.y,r.right,r.bottom,game,nullptr,wc.hInstance,nullptr);
 if(!view){if(audit)audit(false);modalActive=false;return;}EnableWindow(game,FALSE);dimensions();fit();if(shown.run.currentScript)current();SetForegroundWindow(view);SetFocus(view);
 MSG m{};bool quit=false;int exitCode=0;
 while(view){BOOL got=GetMessageW(&m,nullptr,0,0);if(got<=0){quit=got==0;exitCode=(int)m.wParam;break;}
   // The game script stays on this call stack. Its input/timer messages must not run reentrantly.
   if(m.hwnd==game){if(m.message==WM_PAINT){ValidateRect(game,nullptr);}else if(m.message==WM_CLOSE){DestroyWindow(view);PostMessageW(game,WM_CLOSE,0,0);}continue;}
   TranslateMessage(&m);DispatchMessageW(&m);
 }
 if(view){DestroyWindow(view);view=nullptr;}EnableWindow(game,enabled);SetForegroundWindow(game);SetFocus(game);InvalidateRect(game,nullptr,FALSE);
 Log("ui closed");if(audit)audit(false);modalActive=false;if(quit)PostQuitMessage(exitCode);
}
}
