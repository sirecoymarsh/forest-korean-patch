@echo off
set "TEMP=Y:\AI\claude-work\claude-temp"
set "TMP=%TEMP%"
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul
cd /d P:\AI\forest-qol\s-buttons\tools\bin
cl /nologo /O2 /EHsc ..\mutewatch.cpp ole32.lib /Fe:mutewatch.exe
