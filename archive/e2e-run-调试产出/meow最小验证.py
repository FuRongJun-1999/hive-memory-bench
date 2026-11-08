# -*- coding: utf-8 -*-
import subprocess, os, json, time, threading
from pathlib import Path
BIN = r"D:\dsh-home\dsh-0.2.1-rc.2\node_modules\@deepseek-ai\dsh\lib\bin.js"
NODE = r"C:\Program Files\nodejs\node.exe"
PATCH = r"D:/1_ai/_hb_lab/r58/e2e/run/patch_zhipu.yml"
environment_cfg = json.loads(Path(r"D:/program/dsh-memory-main/hive/config.local.json").read_text(encoding="utf-8"))
env = dict(os.environ)
env["DSH_HOME"] = r"D:\dsh-home"
env["PYTHONUTF8"] = "1"
env["ZHIPU_API_KEY"] = environment_cfg["HIVE_API_KEY"]
PROMPT = "请用 memory_remember 工具，把下面三段话原样记住（每段单独一条）：\n1. 玛尔塔的工位编号是 A-17。\n2. 玛尔塔的工位编号后来改成了 C-04。\n3. 主管是韩铎。\n记住后，只回答「已记住」三个字。"

def run(prompt, timeout=240):
    p = subprocess.Popen([NODE, BIN, '--profile', 'bench-meow', '--patch', PATCH, '--json', prompt],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         encoding='utf-8', errors='replace', env=env, shell=False)
    ev, tx = [], []
    t0 = time.time(); ended = [False]
    def rd():
        for ln in p.stdout:
            ln = ln.strip()
            if not ln: continue
            ev.append(ln)
            try: e = json.loads(ln)
            except Exception: continue
            if e.get('type') == 'text': tx.append(e.get('text',''))
            if e.get('type') in ('turn_end','done','end'): ended[0] = True; break
    th = threading.Thread(target=rd, daemon=True); th.start()
    while time.time()-t0 < timeout and not ended[0]:
        time.sleep(1)
        if p.poll() is not None: break
    time.sleep(2)
    try: p.kill()
    except Exception: pass
    return time.time()-t0, ev, ''.join(tx)

print('=== 写入测试 ===')
dt, ev, ans = run(PROMPT)
print('耗时 %.0fs | 事件 %d' % (dt, len(ev)))
print('答案:', ans[:300])
print()
print('=== 工具相关事件 ===')
shown = 0
for ln in ev:
    try: e = json.loads(ln)
    except Exception: continue
    if e.get('type') in ('tool_call','tool_result','tool','usage','status'):
        if shown < 12:
            print(' ', ln[:200])
            shown += 1
Path(r'D:/1_ai/_hb_lab/r58/e2e/run/meow_probe_ingest.jsonl').write_text(chr(10).join(ev), encoding='utf-8')