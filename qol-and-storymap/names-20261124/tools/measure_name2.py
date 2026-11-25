import json, os, subprocess, sys, time
sys.stdout.reconfigure(encoding='utf-8')
CT = 'P:/AI/commentary-mode/forest/trial/colortest'
sys.path.insert(0, CT)
from ccc import send


def must(c):
    r = send(c)
    if not r.get('ok'):
        raise SystemExit('! %s -> %s' % (c, r))
    return r['res']


def dialog_yes(pid, timeout=10):
    t0 = time.time()
    while time.time() - t0 < timeout:
        out = subprocess.run([sys.executable, '-X', 'utf8', os.path.join(CT, 'dlg.py'), str(pid), 'yes'], capture_output=True, text=True, encoding='utf-8').stdout
        if 'post WM_COMMAND' in out:
            return True
        time.sleep(0.3)
    return False


pid = int(sys.argv[1])
must({'op': 'key', 'vk': 76, 'after': 1.5})
st = must({'op': 'state', 'cm': False}); print('loadscr', st.get('loadscr'))
must({'op': 'move', 'x': 233, 'y': 302}); must({'op': 'sleep', 'sec': 0.3})
must({'op': 'click', 'x': 233, 'y': 302, 'after': 0.8})
print('dialog yes', dialog_yes(pid))
must({'op': 'wait', 'what': 'click', 'sec': 30}); time.sleep(1.0)
print('at slot', must({'op': 'state'})['cm'].get('slot'))
must({'op': 'poke', 'a': '466460', 'v': 1, 'n': 2})
must({'op': 'test', 'w': 2, 'l': (2100 << 16) | 791, 'after': 0.2})
for _ in range(3):
    st = must({'op': 'key', 'vk': 9, 'after': 0.6})
    if st.get('tabskip') or st.get('tabreq'): break
must({'op': 'wait', 'what': 'noskip', 'sec': 60}); must({'op': 'wait', 'what': 'click', 'sec': 20})
for _ in range(8):
    s = int(must({'op': 'state'})['cm'].get('slot', -1))
    if s >= 795: break
    must({'op': 'key', 'vk': 13, 'after': 0.3}); must({'op': 'wait', 'what': 'click', 'sec': 20})
s = int(must({'op': 'state'})['cm'].get('slot', -1)); print('now slot', s)
time.sleep(1.5)
print(must({'op': 'shot', 'name': 'name_1x_%d' % s, 'settle': 1.0}))
must({'op': 'poke', 'a': '466460', 'v': 0, 'n': 2})
