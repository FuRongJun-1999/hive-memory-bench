# -*- coding: utf-8 -*-
import subprocess, os, json, time, threading
from pathlib import Path
BIN = r"D:\dsh-home\dsh-0.2.1-rc.2\node_modules\@deepseek-ai\dsh\lib\bin.js"
NODE = r"C:\Program Files\nodejs\node.exe"
PATCH = r"D:/1_ai/_hb_lab/r58/e2e/run/patch_zhipu.yml"
cfg = json.loads(Path(r"D:/program/dsh-memory-main/hive/config.local.json").read_text(encoding="utf-8"))
env = dict(os.environ); env["DSH_HOME"] = r"D:\dsh-home"; env["PYTHONUTF8"] = "1"
env["ZHIPU_API_KEY"] = cfg["HIVE_API_KEY"]
P1 = "玛尔塔的工位编号是多少？请只回答编号本身。"
P2 = "玛尔塔的工位编号曾经是什么？除了当前值，还请说出它以前的值。"

def run(prompt, timeout=240):
    p = subprocess.Popen([NODE, BIN, '--profile', 'bench-meow', '--patch', PATCH, '--json', prompt],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         encoding='utf-8', errors='replace', env=env, shell=False)
    ev, tx, calls = [], [], []
    t0 = time.time(); ended = [False]
    def rd():
        for ln in p.stdout:
            ln = ln.strip()
            if not ln: continue
            ev.append(ln)
            try: e = json.loads(ln)
            except Exception: continue
            t = e.get('type')
            if t == 'text': tx.append(e.get('text',''))
            if t == 'tool_call': calls.append((e.get('tool'), str(e.get('input'))[:150]))
            if t in ('turn_end','done','end'): ended[0] = True; break
    th = threading.Thread(target=rd, daemon=True); th.start()
    while time.time()-t0 < timeout and not ended[0]:
        time.sleep(1)
        if p.poll() is not None: break
    time.sleep(2)
    try: p.kill()
    except Exception: pass
    return time.time()-t0, calls, ''.join(tx)

for label, prompt in (('现值问', P1), ('历史问', P2)):
    print('=' * 60)
    print(label, ':', prompt)
    dt, calls, ans = run(prompt)
    print('  耗时 %.0fs' % dt)
    print('  调用的工具:', calls if calls else '（无）')
    print('  答案:', ans[:400].replace(chr(10), ' '))
    print()