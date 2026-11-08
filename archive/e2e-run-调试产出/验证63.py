import subprocess
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=r'D:/1_ai/_hb_lab/r58')
    return p.returncode, (p.stdout or '') + (p.stderr or '')
run('git','fetch','origin','main')
for f in ('persona-consistency/K_面作业规程_v1.0.md', 'persona-consistency/tools/score_k.py'):
    rc, out = run('git','cat-file','-s','origin/main:'+f)
    print('%-46s %s' % (f.split('/')[-1], out.strip() if rc==0 else '缺失'))
rc, out = run('git','show','origin/main:persona-consistency/tools/score_k.py')
print()
print('score_k 版本行:', [l for l in out.split(chr(10))[:2] if 'v2' in l])
print('含复制检测:', 'suspect_copy' in out)
print('含 same_rate:', 'same_rate' in out)