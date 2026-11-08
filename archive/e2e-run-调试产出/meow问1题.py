# -*- coding: utf-8 -*-
import subprocess, os, json, time, threading
from pathlib import Path
BIN = r"D:\dsh-home\dsh-0.2.1-rc.2\node_modules\@deepseek-ai\dsh\lib\bin.js"
NODE = r"C:\Program Files\nodejs\node.exe"
PATCH = r"D:/1_ai/_hb_lab/r58/e2e/run/patch_zhipu.yml"
R = Path(r'D:/1_ai/_hb_lab/r58')
OUT = R / 'e2e/run/meow_probe'
cfg = json.loads(Path(r'D:/program/dsh-memory-main/hive/config.local.json').read_text(encoding='utf-8'))
env = dict(os.environ); env['DSH_HOME']=r'D:\dsh-home'; env['PYTHONUTF8']='1'
env['ZHIPU_API_KEY']=cfg['HIVE_API_KEY']
WARN = '【强制】只允许使用 memory_search 和 memory_read 两个工具。禁止使用 grep、glob、pwsh、read、write、skill 等任何其他工具，禁止读取工作区文件。查到后立即作答。'
def ask(qtext, timeout=280):
    prompt = WARN + chr(10) + chr(10) + '问题：' + qtext + chr(10) + chr(10) + '请只输出一行：值=<值>；状态=<状态>；序号=<序号>'
    p = subprocess.Popen([NODE, BIN, '--profile','bench-meow','--patch',PATCH,'--json',prompt],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         encoding='utf-8', errors='replace', env=env, shell=False)
    ev, tx, calls = [], [], []
    t0=time.time(); ended=[False]
    def rd():
        for ln in p.stdout:
            ln=ln.strip()
            if not ln: continue
            ev.append(ln)
            try: e=json.loads(ln)
            except Exception: continue
            t=e.get('type')
            if t=='text': tx.append(e.get('text',''))
            if t=='tool_call': calls.append(e.get('tool'))
            if t in ('turn_end','done','end'): ended[0]=True; break
    th=threading.Thread(target=rd, daemon=True); th.start()
    while time.time()-t0<timeout and not ended[0]:
        time.sleep(1)
        if p.poll() is not None: break
    time.sleep(2)
    try: p.kill()
    except Exception: pass
    return time.time()-t0, calls, ''.join(tx), ev
qs = json.loads((OUT / 'hu_questions.json').read_text(encoding='utf-8'))
q = qs[0]
print('=== 试跑第 1 题（现值）===')
print('Q:', q['question'][:100])
dt, calls, ans, ev = ask(q['question'])
print('耗时 %.0fs' % dt)
print('工具:', calls)
print('答案:', ans[:300].replace(chr(10),' '))
print('真值:', json.dumps(q['answer'], ensure_ascii=False)[:200])