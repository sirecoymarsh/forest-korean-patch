@echo off
rem 빠른 빌드: qol_hitext.cpp·qol_present.cpp 만 다시 컴파일해 링크(나머지 obj 는 build.cmd 결과를 씀)
setlocal
set "TEMP=%~dp0..\tmp"
set "TMP=%TEMP%"
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x86 >nul
set "SRC=%~dp0."
set "OUT=%~dp0..\build"
cd /d "%OUT%"
set "CF=/nologo /std:c++17 /EHsc /MT /O2 /utf-8 /W3 /wd4100 /wd4244 /wd4267 /wd4305 /DUNICODE /D_UNICODE /I"%SRC%""
cl %CF% /c "%SRC%\qol_hitext.cpp" "%SRC%\qol_present.cpp"
if errorlevel 1 exit /b 1
cl %CF% /LD "%SRC%\engine_bridge.cpp" model.obj progress.obj chart_ui.obj chart_data.obj qol_core.obj qol_present.obj qol_play.obj qol_buttons.obj qol_hitext.obj /Fe:ForestChart.dll /link /DEF:"%SRC%\exports.def" user32.lib gdi32.lib advapi32.lib gdiplus.lib winmm.lib imm32.lib msimg32.lib
exit /b %errorlevel%
