// mutewatch.exe <pid> — 그 프로세스가 끝날 때까지 250ms 마다 그 프로세스의 오디오 세션을 모두 음소거한다(시험 창 무음).
// 빌드: cl /nologo /O2 /EHsc mutewatch.cpp ole32.lib
#include <windows.h>
#include <mmdeviceapi.h>
#include <audiopolicy.h>
#include <cstdio>
#include <cstdlib>

static int muteAll(DWORD pid, IMMDeviceEnumerator* en) {
    int muted = 0;
    IMMDeviceCollection* devs = nullptr;
    if (FAILED(en->EnumAudioEndpoints(eRender, DEVICE_STATE_ACTIVE, &devs))) return 0;
    UINT n = 0; devs->GetCount(&n);
    for (UINT i = 0; i < n; ++i) {
        IMMDevice* dev = nullptr; if (FAILED(devs->Item(i, &dev))) continue;
        IAudioSessionManager2* mgr = nullptr;
        if (SUCCEEDED(dev->Activate(__uuidof(IAudioSessionManager2), CLSCTX_ALL, nullptr, (void**)&mgr))) {
            IAudioSessionEnumerator* se = nullptr;
            if (SUCCEEDED(mgr->GetSessionEnumerator(&se))) {
                int c = 0; se->GetCount(&c);
                for (int k = 0; k < c; ++k) {
                    IAudioSessionControl* ctl = nullptr; if (FAILED(se->GetSession(k, &ctl))) continue;
                    IAudioSessionControl2* ctl2 = nullptr;
                    if (SUCCEEDED(ctl->QueryInterface(__uuidof(IAudioSessionControl2), (void**)&ctl2))) {
                        DWORD p = 0;
                        if (SUCCEEDED(ctl2->GetProcessId(&p)) && p == pid) {
                            ISimpleAudioVolume* vol = nullptr;
                            if (SUCCEEDED(ctl->QueryInterface(__uuidof(ISimpleAudioVolume), (void**)&vol))) {
                                BOOL m = FALSE; vol->GetMute(&m);
                                if (!m) { vol->SetMute(TRUE, nullptr); ++muted; }
                                vol->Release();
                            }
                        }
                        ctl2->Release();
                    }
                    ctl->Release();
                }
                se->Release();
            }
            mgr->Release();
        }
        dev->Release();
    }
    devs->Release();
    return muted;
}

int main(int argc, char** argv) {
    if (argc < 2) { printf("usage: mutewatch <pid>\n"); return 2; }
    DWORD pid = (DWORD)strtoul(argv[1], nullptr, 10);
    HANDLE proc = OpenProcess(SYNCHRONIZE, FALSE, pid);
    if (!proc) { printf("no process %lu\n", pid); return 1; }
    CoInitializeEx(nullptr, COINIT_MULTITHREADED);
    IMMDeviceEnumerator* en = nullptr;
    if (FAILED(CoCreateInstance(__uuidof(MMDeviceEnumerator), nullptr, CLSCTX_ALL, __uuidof(IMMDeviceEnumerator), (void**)&en))) return 1;
    int total = 0;
    while (WaitForSingleObject(proc, 250) == WAIT_TIMEOUT) {
        int m = muteAll(pid, en);
        if (m) { total += m; printf("muted %d session(s)\n", m); fflush(stdout); }
    }
    printf("process ended; muted %d in all\n", total);
    en->Release(); CoUninitialize(); CloseHandle(proc);
    return 0;
}
