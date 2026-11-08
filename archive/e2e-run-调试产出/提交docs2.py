import subprocess
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=r'D:/1_ai/_hb_lab/r58')
    return p.returncode, (p.stdout or '') + (p.stderr or '')
run('git','add','docs/选择题改造与三方案对照_v1.0.md')
rc, out = run('git','status','--short','--untracked-files=no')
print('暂存:', out.strip()[:200])
rc, out = run('git','commit','-F','e2e/run/commitmsg2.txt')
print('commit rc:', rc)
print(out[-250:])
rc2, out2 = run('git','push','origin','feat/hive-mcq-182-and-scores')
print('push rc:', rc2)
print(out2[-200:])