# -*- coding: utf-8 -*-
import subprocess, os, json, time, threading
from pathlib import Path
BIN = r"D:\dsh-home\dsh-0.2.1-rc.2\node_modules\@deepseek-ai\dsh\lib\bin.js"
NODE = r"C:\Program Files\nodejs\node.exe"
PATCH = r"D:/1_ai/_hb_lab/r58/e2e/run/patch_deepseek.yml"
OUT = Path(r'D:/1_ai/_hb_lab/r58/e2e/run')
cfg = json.loads(Path(r'D:/program/dsh-memory-main/hive/config.local.json').read_text(encoding='utf-8'))
env = dict(os.environ)
env['DSH_HOME'] = r'D:\dsh-home'; env['PYTHONUTF8']='1'
env['DEEPSEEK_KEY'] = cfg['HIVE_API_KEY']
def run(prompt, tag, timeout=900):
    p = subprocess.Popen([NODE, BIN, '--profile','bench-mem','--patch',PATCH,'--json',prompt],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         encoding='utf-8', errors='replace', env=env, shell=False)
    ev, tx = [], []
    t0=time.time(); ended=[False]
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
    while time.time()-t0<timeout and not ended[0]:
        time.sleep(2)
        if p.poll() is not None: break
    time.sleep(3)
    try: p.kill()
    except Exception: pass
    ans = chr(10).join(tx)
    (OUT / ('lingshu_Kv2_%s_answer.txt' % tag)).write_text(ans, encoding='utf-8')
    (OUT / ('lingshu_Kv2_%s_raw.jsonl' % tag)).write_text(chr(10).join(ev), encoding='utf-8')
    print('[%s] %.0fs | 事件%d | ended=%s | 答案%d字符' % (tag, time.time()-t0, len(ev), ended[0], len(ans)))
    return ans
for tag in ('r1','r2','r3'):
    prompt = (OUT / ('lingshu_Kv2_%s.txt' % tag)).read_text(encoding='utf-8')
    ans = run(prompt, tag)
    print('   前 200:', ans[:200].replace(chr(10),' '))
print('三轮完成')