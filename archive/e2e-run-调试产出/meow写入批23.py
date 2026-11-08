# -*- coding: utf-8 -*-
import subprocess, os, json, time, threading
from pathlib import Path
BIN = r"D:\dsh-home\dsh-0.2.1-rc.2\node_modules\@deepseek-ai\dsh\lib\bin.js"
NODE = r"C:\Program Files\nodejs\node.exe"
PATCH = r"D:/1_ai/_hb_lab/r58/e2e/run/patch_zhipu.yml"
R = Path(r'D:/1_ai/_hb_lab/r58')
OUT = R / 'e2e/run/meow_probe'
cfg = json.loads(Path(r'D:/program/dsh-memory-main/hive/config.local.json').read_text(encoding='utf-8'))
env = dict(os.environ); env['DSH_HOME'] = r'D:\dsh-home'; env['PYTHONUTF8']='1'
env['ZHIPU_API_KEY'] = cfg['HIVE_API_KEY']
HEAD = '请用 memory_remember 工具逐条记住下面 {n} 段原文。要求：'
RULES = ['1. 每段单独调用一次 memory_remember，content 参数原样照抄该段全文，不要改写、不要摘要；',
         '2. 不要使用 grep / glob / pwsh / read / write 等其他工具；',
         '3. 全部记完后只回答「已记住」。', '']
def build_prompt(segs):
    body = chr(10).join('[%d] %s' % (s['seq'], s['text']) for s in segs)
    return HEAD.format(n=len(segs)) + chr(10) + chr(10).join(RULES) + chr(10) + body
def call(prompt, timeout=520):
    p = subprocess.Popen([NODE, BIN, '--profile', 'bench-meow', '--patch', PATCH, '--json', prompt],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         encoding='utf-8', errors='replace', env=env, shell=False)
    ev, tx, calls = [], [], []
    st = {'w': 0}
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
            if t=='tool_result' and '写入' in str(e.get('result','')): st['w']+=1
            if t in ('turn_end','done','end'): ended[0]=True; break
    th=threading.Thread(target=rd, daemon=True); th.start()
    while time.time()-t0<timeout and not ended[0]:
        time.sleep(1)
        if p.poll() is not None: break
    time.sleep(2)
    try: p.kill()
    except Exception: pass
    return time.time()-t0, len(calls), st['w'], ''.join(tx), ev
hu = json.loads((OUT / 'hu_corpus.json').read_text(encoding='utf-8'))
for idx in (1, 2):
    segs = hu[idx*20:(idx+1)*20]
    if not segs: continue
    print('=== 第 %d 批：%d 段 ===' % (idx+1, len(segs)))
    dt, nc, nw, ans, ev = call(build_prompt(segs))
    print('耗时 %.0fs | 调用 %d | 写入 %d | 答案 %s' % (dt, nc, nw, ans[:40]))
    (OUT / ('batch%d_events.jsonl' % (idx+1))).write_text(chr(10).join(ev), encoding='utf-8')
    print()
print('全部 3 批完成')