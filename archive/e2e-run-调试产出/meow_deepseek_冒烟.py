# -*- coding: utf-8 -*-
import subprocess, os, json, time, threading
from pathlib import Path
BIN = r"D:\dsh-home\dsh-0.2.1-rc.2\node_modules\@deepseek-ai\dsh\lib\bin.js"
NODE = r"C:\Program Files\nodejs\node.exe"
PATCH = r"D:/1_ai/_hb_lab/r58/e2e/run/patch_deepseek.yml"
R = Path(r'D:/1_ai/_hb_lab/r58')
OUT = R / 'e2e/run/meow_probe'
cfg = json.loads(Path(r'D:/program/dsh-memory-main/hive/config.local.json').read_text(encoding='utf-8'))
key = cfg['HIVE_API_KEY']
env = dict(os.environ)
env['DSH_HOME'] = r'D:\dsh-home'
env['PYTHONUTF8'] = '1'
env['DEEPSEEK_KEY'] = key
print('DEEPSEEK_KEY 注入（len=%d）| base=%s' % (len(key), 'https://api.deepseek.com'))

# 先做连通性冒烟
p = subprocess.Popen([NODE, BIN, '--profile','bench-meow','--patch',PATCH,'--json','只回答两个字：收到'],
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                     encoding='utf-8', errors='replace', env=env, shell=False)
ev, tx = [], []
t0 = time.time(); ended=[False]
def rd():
    for ln in p.stdout:
        ln=ln.strip()
        if not ln: continue
        ev.append(ln)
        try: e=json.loads(ln)
        except Exception: continue
        if e.get('type')=='text': tx.append(e.get('text',''))
        if e.get('type') in ('turn_end','done','end'): ended[0]=True; break
th=threading.Thread(target=rd, daemon=True); th.start()
while time.time()-t0 < 180 and not ended[0]:
    time.sleep(1)
    if p.poll() is not None: break
time.sleep(2)
try: p.kill()
except Exception: pass
print('冒烟耗时 %.0fs | 事件 %d' % (time.time()-t0, len(ev)))
print('答案:', ''.join(tx)[:150])
if not tx:
    err = p.stderr.read() if p.stderr else ''
    print('stderr:', str(err)[:600])