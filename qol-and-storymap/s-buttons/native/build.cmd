@echo off
setlocal
set "TEMP=%~dp0..\tmp"
set "TMP=%TEMP%"
if not exist "%TEMP%" mkdir "%TEMP%"
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x86 >nul
if errorlevel 1 exit /b 1
set "SRC=%~dp0."
set "OUT=%~dp0..\build"
if not exist "%OUT%" mkdir "%OUT%"
cd /d "%OUT%"
set "CF=/nologo /std:c++17 /EHsc /MT /O2 /utf-8 /W3 /wd4100 /wd4244 /wd4267 /wd4305 /DUNICODE /D_UNICODE /I"%SRC%""
cl %CF% /c "%SRC%\model.cpp" "%SRC%\progress.cpp" "%SRC%\chart_ui.cpp" "%SRC%\chart_data.cpp"
if errorlevel 1 exit /b 1
cl %CF% "%SRC%\render_test.cpp" model.obj progress.obj chart_ui.obj chart_data.obj /Fe:render_test.exe /link user32.lib gdi32.lib advapi32.lib gdiplus.lib
if errorlevel 1 exit /b 1
cl %CF% /c "%SRC%\qol_core.cpp" "%SRC%\qol_present.cpp" "%SRC%\qol_play.cpp" "%SRC%\qol_buttons.cpp"
if errorlevel 1 exit /b 1
cl %CF% /LD "%SRC%\engine_bridge.cpp" model.obj progress.obj chart_ui.obj chart_data.obj qol_core.obj qol_present.obj qol_play.obj qol_buttons.obj /Fe:ForestChart.dll /link /DEF:"%SRC%\exports.def" user32.lib gdi32.lib advapi32.lib gdiplus.lib winmm.lib imm32.lib msimg32.lib
exit /b %errorlevel%
