# -*- coding: utf-8 -*-
import subprocess, os, json, time, threading
from pathlib import Path
BIN = r"D:\dsh-home\dsh-0.2.1-rc.2\node_modules\@deepseek-ai\dsh\lib\bin.js"
NODE = r"C:\Program Files\nodejs\node.exe"
PATCH = r"D:/1_ai/_hb_lab/r58/e2e/run/patch_zhipu.yml"
OUT = Path(r'D:/1_ai/_hb_lab/r58/e2e/run')
zk = Path(r'E:/个人数据/智谱api.txt').read_text(encoding='utf-8').strip()
env = dict(os.environ)
env['DSH_HOME'] = r'D:\dsh-home'; env['PYTHONUTF8']='1'
env['ZHIPU_API_KEY'] = zk
prompts = json.loads((OUT / 'lingshu_Kv2_by_dim.json').read_text(encoding='utf-8'))
res_path = OUT / 'lingshu_Kv2_by_dim_results.jsonl'
done = set()
if res_path.exists():
    for ln in res_path.read_text(encoding='utf-8').splitlines():
        if ln.strip():
            done.add(json.loads(ln)['dim'])
print('已完成维度:', len(done), '/', len(prompts), flush=True)

def run(dim, prompt, timeout=600):
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
    time.sleep(2)
    try: p.kill()
    except Exception: pass
    return time.time()-t0, ended[0], ''.join(tx)

for i, (dim, prompt) in enumerate(prompts.items()):
    if dim in done:
        continue
    dt, ended, ans = run(dim, prompt)
    rec = dict(dim=dim, dt=round(dt), ended=ended, answer=ans[:1200])
    with res_path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + chr(10))
    print('[%2d/%d] %-16s %4.0fs ended=%s | %s' % (i+1, len(prompts), dim, dt, ended, ans[:70].replace(chr(10),' ')), flush=True)
print('全部完成', flush=True)