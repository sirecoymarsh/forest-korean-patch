# -*- coding: utf-8 -*-
"""놀이 사본에 되감기가 든 통합 DLL 을 넣는다 / 되돌린다. **사용자가 넣으라고 한 뒤에만** install 을 돌린다.

 check    (기본) 읽기만: 놀이 사본의 DLL·ini 상태, 게임이 떠 있는지, 넣을 DLL 을 알려 준다.
 install  게임이 꺼져 있고 놀이 사본의 DLL 이 아는 판(EXPECT)일 때만: DLL·ini 를 백업하고, DLL 을 바꾸고, ini 에 되감기 줄을 넣는다.
 restore  백업해 둔 DLL·ini 로 되돌린다(게임이 꺼져 있을 때만).

바꾸는 것은 ForestChart.dll 과 forest-qol.ini 둘뿐이다. 세이브·다른 파일은 건드리지 않는다.
사용: python -I install_play.py [check|install|restore]"""
import hashlib, os, shutil, subprocess, sys, time

PLAY = r'P:\AI\forest-kr-build\game'
NEW = r'P:\AI\forest-qol\build\ForestChart.dll'
BACKUP = r'P:\AI\forest-qol\s-rewind\play-backup-20261125'
EXPECT = '1e4bf870d00f'          # 11-24 새벽에 넣은 판(통합 소스에 되감기를 합치기 전의 빌드)
INI_AUTO_OLD = 'auto_key=1               ; A = 자동 진행(누를 때마다 ×1~×5), Backspace = 끄기'
INI_AUTO_NEW = 'auto_key=1               ; A = 자동 진행(누를 때마다 ×1~×5). 끄기는 클릭·Enter'
INI_AFTER = 'key_guide=1              ; Home = 조작 안내'
INI_ADD = ['; 되감기',
           'rewind=1                 ; Backspace = 이전 대사로 되감기(그림·소리·노란 자막까지, 누르고 있으면 계속)',
           'rewind_depth=300         ; 기억하는 걸음 수(한 걸음 약 37KB)']


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()[:12]


def running_from(folder):
    """그 폴더의 Forest.exe 가 떠 있으면 그 프로세스 번호들."""
    ps = "Get-CimInstance Win32_Process -Filter \"Name='Forest.exe'\" | ForEach-Object { '{0}|{1}' -f $_.ProcessId, $_.ExecutablePath }"
    out = subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True).stdout.decode('utf-8', 'replace')
    hits = []
    for l in out.splitlines():
        if '|' not in l: continue
        pid, path = l.split('|', 1)
        if os.path.normcase(os.path.dirname(path.strip())) == os.path.normcase(folder): hits.append(int(pid))
    return hits


def ini_new(text):
    nl = '\r\n' if '\r\n' in text else '\n'
    lines = text.split(nl)
    out = []; did_auto = did_add = False
    has_rewind = any(l.strip().startswith('rewind=') for l in lines)
    for l in lines:
        if l.rstrip() == INI_AUTO_OLD: out.append(INI_AUTO_NEW); did_auto = True; continue
        out.append(l)
        if l.rstrip() == INI_AFTER and not has_rewind: out += INI_ADD; did_add = True
    if not has_rewind and not did_add:      # 본보기 줄이 없으면 끝에
        while out and out[-1] == '': out.pop()
        out += INI_ADD + ['']; did_add = True
    return nl.join(out), did_auto, did_add


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'check'
    dll = os.path.join(PLAY, 'ForestChart.dll'); ini = os.path.join(PLAY, 'forest-qol.ini')
    cur, new = sha(dll), sha(NEW)
    pids = running_from(PLAY)
    print('play copy dll %s (expected before install: %s), new dll %s (%d bytes)' % (cur, EXPECT, new, os.path.getsize(NEW)))
    print('game running from the play copy:', pids or 'no')
    text = open(ini, 'rb').read().decode('utf-8')
    new_text, did_auto, did_add = ini_new(text)
    print('ini: auto_key comment %s, rewind lines %s' % ('to fix' if did_auto else 'as is', 'to add' if did_add else 'already there'))
    if mode == 'check':
        return 0
    if pids:
        print('REFUSED: the game is running. Close it first.'); return 2
    if mode == 'install':
        if cur == new:
            print('already installed'); return 0
        if cur != EXPECT:
            print('REFUSED: the play copy has a DLL this tool does not know (%s). Look before replacing it.' % cur); return 3
        os.makedirs(BACKUP, exist_ok=True)
        bd = os.path.join(BACKUP, 'ForestChart_%s.dll' % cur); bi = os.path.join(BACKUP, 'forest-qol_before.ini')
        if not os.path.exists(bd): shutil.copy2(dll, bd)
        if not os.path.exists(bi): shutil.copy2(ini, bi)
        assert sha(bd) == cur
        shutil.copyfile(NEW, dll)
        assert sha(dll) == new, 'copy did not land'
        if new_text != text: open(ini, 'wb').write(new_text.encode('utf-8'))
        print('installed %s over %s at %s; backups in %s' % (new, cur, time.strftime('%Y-%m-%d %H:%M:%S'), BACKUP))
        return 0
    if mode == 'restore':
        bd = os.path.join(BACKUP, 'ForestChart_%s.dll' % EXPECT); bi = os.path.join(BACKUP, 'forest-qol_before.ini')
        if not (os.path.exists(bd) and os.path.exists(bi)):
            print('REFUSED: no backup in', BACKUP); return 4
        shutil.copyfile(bd, dll); shutil.copyfile(bi, ini)
        print('restored dll %s and the ini from %s' % (sha(dll), BACKUP))
        return 0
    print('unknown mode', mode); return 1


sys.exit(main())
