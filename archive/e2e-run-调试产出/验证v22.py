# -*- coding: utf-8 -*-
"""用三组实测数据验证 v2.2 的复制检测是否真的能拦住 B 组。"""
import subprocess, sys, json
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
sk = R / 'persona-consistency/tools/score_k.py'
bank = R / 'persona-consistency/questions/K_persona_consistency_v2.json'
groups = [
    ('A 同会话·无诱导', R/'e2e/run/hive_Kv2_scores.json'),
    ('B 同会话·有诱导', R/'e2e/run/hive_pushback_scores.json'),
    ('C 跨会话·打乱·有诱导', R/'e2e/run/xsession_scores.json'),
]
for name, p in groups:
    print('=' * 70)
    print(name)
    print('=' * 70)
    if not p.exists():
        print('  文件缺失:', p); continue
    r = subprocess.run([sys.executable,'-X','utf8', str(sk), '--bank', str(bank), '--scores', str(p)],
                       capture_output=True, text=True, encoding='utf-8')
    out = r.stdout
    # 只打尾部（汇总部分）
    lines = out.strip().split(chr(10))
    for ln in lines[-6:]:
        print(' ', ln)
    if r.returncode != 0:
        print('  STDERR:', r.stderr[:300])