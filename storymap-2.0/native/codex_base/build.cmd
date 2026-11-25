@echo off
setlocal
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x86 >nul
if errorlevel 1 exit /b 1
set "FCROOT=P:\AI\Codex\projects\forest-flowchart"
set "FCBUILD=%FCROOT%\work\ingame-chart\native-build"
if not exist "%FCBUILD%" mkdir "%FCBUILD%"
cd /d "%FCBUILD%"
cl /nologo /std:c++17 /EHsc /MT /O2 /utf-8 /DUNICODE /D_UNICODE /I"%FCROOT%\native" /c "%FCROOT%\native\model.cpp" "%FCROOT%\native\progress.cpp" "%FCROOT%\native\chart_ui.cpp"
if errorlevel 1 exit /b 1
cl /nologo /std:c++17 /EHsc /MT /O2 /utf-8 /DUNICODE /D_UNICODE /I"%FCROOT%\native" "%FCROOT%\native\demo.cpp" model.obj progress.obj chart_ui.obj /Fe:ForestChartUiTest.exe /link /SUBSYSTEM:WINDOWS user32.lib gdi32.lib advapi32.lib
if errorlevel 1 exit /b 1
cl /nologo /std:c++17 /EHsc /MT /O2 /utf-8 /DUNICODE /D_UNICODE /I"%FCROOT%\native" "%FCROOT%\native\progress_tests.cpp" model.obj progress.obj /Fe:ForestProgressTests.exe /link user32.lib advapi32.lib
if errorlevel 1 exit /b 1
cl /nologo /std:c++17 /EHsc /MT /O2 /utf-8 /DUNICODE /D_UNICODE /I"%FCROOT%\native" /LD "%FCROOT%\native\engine_bridge.cpp" model.obj progress.obj chart_ui.obj /Fe:ForestChart.dll /link /DEF:"%FCROOT%\native\exports.def" user32.lib gdi32.lib advapi32.lib
exit /b %errorlevel%
